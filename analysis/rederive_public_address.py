"""Independent re-derivation: does an address (file + line number) in the observation just before a
first read_file predict a ranged read, and does the range cover the named line? (EXPLORATORY)

A second implementation of the counts of analysis/public_runs_address.py, written from the rules in that script's
docstring without its code, reading the raw trace files. Usage:
    py -I -X utf8 analysis/rederive_public_address.py
It prints the report. The classification code is as it was written blind. Added afterwards, and nothing else: the
pool of three sources that the first script reports (this script first pooled four, with the graph-skill arm), and
the report is printed, not saved. Group names are the public datasets' names (see analysis/results/public/README.md).
"""
import glob
import json
import os
import re
import shlex
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GRAPH_TOOLS = {"get_code_neighbors", "get_code_subgraph", "search_similar_code"}
VIEWERS = {"cat", "head", "tail", "sed", "nl", "less", "more", "awk"}
GROUP_ORDER = ["graphloc_starter", "graphloc_skill", "vanductan_31b", "niraberman_31b",
               "POOLED_31B", "POOL_OF_3", "vanductan_12b", "vanductan_e4b"]
POOL = {"graphloc_starter", "graphloc_skill", "vanductan_31b", "niraberman_31b"}
POOL3 = {"graphloc_starter", "vanductan_31b", "niraberman_31b"}  # the pool of analysis/public_runs_address.py
CLASSES = ["ADDRESS", "PATH_ONLY", "GRAPH_NAME", "OTHER"]


# ---------------------------------------------------------------- file discovery
def discover():
    files = []  # (group, path)
    for p in glob.glob(os.path.join(ROOT, "data", "graphloc", "out", "*", "e2e", "results", "*", "w*",
                                    "traces", "trace_*.json")):
        arm = os.path.normpath(p).split(os.sep)[-4]
        files.append(("graphloc_starter" if arm == "base" else "graphloc_skill", p))
    for p in glob.glob(os.path.join(ROOT, "data", "public_traces", "vanductan__gemma4-patchpool", "traces", "*",
                                    "traces", "trace_*.json")):
        run = os.path.normpath(p).split(os.sep)[-3]
        if run.startswith("31b_"):
            g = "vanductan_31b"
        elif run.startswith("12b_"):
            g = "vanductan_12b"
        elif run.startswith("e4b_"):
            g = "vanductan_e4b"
        else:
            g = "vanductan_other"
        files.append((g, p))
    for p in glob.glob(os.path.join(ROOT, "data", "public_traces", "niraberman__gemma4-commit-anatomy-traces",
                                    "arena_v2*", "results_*", "traces", "trace_*.json")):
        files.append(("niraberman_31b", p))
    return sorted(files)


# ---------------------------------------------------------------- helpers
def norm_file(fp):
    fp = str(fp).strip()
    changed = True
    while changed:
        changed = False
        if fp.startswith("/workspace/"):
            fp, changed = fp[len("/workspace/"):], True
        elif fp.startswith("./"):
            fp, changed = fp[2:], True
    return fp


def clean_key(k):
    return re.sub(r"[\"'\\\s]", "", str(k))


def strings_in(obj):
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(strings_in(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(strings_in(v))
    return out


def parse_result(obs):
    if not isinstance(obs, dict):
        return None
    c = obs.get("content")
    if isinstance(c, str):
        try:
            return json.loads(c)
        except Exception:
            return c
    return c


PRE = r"(?<![A-Za-z0-9_.\-])"  # start, or a non-path char before ('/' allowed: directory prefix)


def path_re(path):
    return PRE + re.escape(path)


def names_path(text, path):
    return re.search(path_re(path) + r"(?![A-Za-z0-9_])", text, re.M) is not None


def split_segments(cmd):
    """Quote-aware split of a shell command on unquoted | ; & newline ( ) ."""
    segs, cur, q, i, n = [], [], None, 0, len(cmd)
    while i < n:
        ch = cmd[i]
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            elif ch == "\\" and q == '"' and i + 1 < n:
                cur.append(cmd[i + 1])
                i += 1
        elif ch in "'\"":
            q = ch
            cur.append(ch)
        elif ch == "\\" and i + 1 < n:
            cur.append(ch + cmd[i + 1])
            i += 1
        elif ch in "|;&\n()`":
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return [s.strip() for s in segs if s.strip()]


def seg_words(seg):
    try:
        w = shlex.split(seg, posix=True)
    except Exception:
        w = seg.split()
    # drop leading env assignments and wrappers
    while w and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]) or w[0] in ("sudo", "time", "command", "exec", "$")):
        w = w[1:]
    if w and w[0] == "xargs":
        w = w[1:]
        while w and w[0].startswith("-"):
            w = w[1:]
    return w


def first_word(words):
    return os.path.basename(words[0]) if words else ""


def has_n_flag(words, allow_digits=True):
    pat = r"^-[A-Za-z]*n[A-Za-z0-9]*$" if allow_digits else r"^-[A-Za-z]*n[A-Za-z]*$"
    return any(re.match(pat, t) or t == "--line-number" or t == "--number" for t in words[1:])


def numbering_command(cmd):
    for seg in split_segments(cmd):
        w = seg_words(seg)
        fw = first_word(w)
        if fw in ("grep", "egrep", "fgrep") and has_n_flag(w):
            return True
        if fw == "git" and len(w) > 1 and w[1] == "grep" and has_n_flag(w[1:]):
            return True
        if fw == "cat" and has_n_flag(w, allow_digits=False):
            return True
        if fw == "nl":
            return True
    return False


def uses_viewer(cmd):
    return any(first_word(seg_words(seg)) in VIEWERS for seg in split_segments(cmd))


# ---------------------------------------------------------------- classification
def classify(prev, path):
    """prev = (fname, args, result) of the previous tool call, or None.
    Returns (class, way, named_lines)."""
    if prev is None:
        return "OTHER", None, set()
    fname, args, result = prev
    res_text = "\n".join(strings_in(result))
    arg_text = "\n".join(strings_in(args))
    obs_text = res_text + "\n" + arg_text
    named_i, named_ii, named_iii = set(), set(), set()
    pr = path_re(path)
    for m in re.finditer(pr + r"(?::(\d+):|-(\d+)-)", obs_text, re.M):
        named_i.add(int(m.group(1) or m.group(2)))
    for m in re.finditer(pr + r"\", line (\d+)", obs_text, re.M):
        named_ii.add(int(m.group(1)))
    if fname == "run_command":
        cmd = args.get("command", "") if isinstance(args, dict) else ""
        if isinstance(cmd, str) and names_path(cmd, path) and numbering_command(cmd):
            for line in res_text.splitlines():
                m = re.match(r"^\s*(\d+)[:\-\t]", line)
                if m:
                    named_iii.add(int(m.group(1)))
    named = named_i | named_ii | named_iii
    if named:
        way = "i" if named_i else ("ii" if named_ii else "iii")
        return "ADDRESS", way, named
    if fname in GRAPH_TOOLS:
        module = path[:-3] if path.endswith(".py") else path
        module = module.replace("/", ".")
        if module and re.search(r"(?<![A-Za-z0-9_])" + re.escape(module) + r"\.", res_text, re.M):
            return "GRAPH_NAME", None, set()
    if names_path(res_text, path) or names_path(arg_text, path):
        return "PATH_ONLY", None, set()
    return "OTHER", None, set()


# ---------------------------------------------------------------- per trace
def tool_events(steps):
    """Sequential list of (fname, args, result). A step with several tool calls gets its own
    observation for the first; later calls take observations from following steps that carry an
    observation but no tool_calls."""
    events, pending = [], []
    for s in steps:
        tc = s.get("tool_calls")
        if tc:
            pending = []
            for j, c in enumerate(tc):
                ev = [c.get("function_name"), c.get("arguments") or {}, None]
                events.append(ev)
                if j == 0:
                    ev[2] = parse_result(s.get("observation"))
                else:
                    pending.append(ev)
        elif pending and s.get("observation") is not None:
            ev = pending.pop(0)
            ev[2] = parse_result(s.get("observation"))
    return events


stats = Counter()


def asked_range(args):
    start = end = None
    for k, v in args.items():
        ck = clean_key(k)
        if ck == "start_line":
            if start is None:
                start = v
            else:
                stats["duplicate_start_key"] += 1
            if ck != k:
                stats["damaged_start_key"] += 1
        elif ck == "end_line":
            if end is None:
                end = v
            else:
                stats["duplicate_end_key"] += 1
            if ck != k:
                stats["damaged_end_key"] += 1
    return start, end


def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def window(start, end):
    hi = start + 149
    if isnum(end):
        hi = min(end, hi)
    return start, hi


def process(group, path_):
    d = json.load(open(path_, encoding="utf-8"))
    task = os.path.basename(path_)[len("trace_"):-len(".json")]
    events = tool_events(d.get("steps", []))
    seen = set()  # files read via read_file
    recs = []
    for idx, (fname, args, result) in enumerate(events):
        if fname != "read_file" or not isinstance(args, dict):
            continue
        fp = norm_file(args.get("filepath", ""))
        first = fp not in seen
        if first:
            for f2, a2, _ in events[:idx]:
                if f2 == "run_command" and isinstance(a2, dict):
                    cmd = a2.get("command", "")
                    if isinstance(cmd, str) and names_path(cmd, fp) and uses_viewer(cmd):
                        first = False
                        break
        seen.add(fp)
        prev = None
        if idx > 0:
            pf, pa, pr = events[idx - 1]
            prev = (pf, pa if isinstance(pa, dict) else {}, pr)
        cls, way, named = classify(prev, fp)
        start, end = asked_range(args)
        ranged = isnum(start) and start > 1
        covers = near = equal = False
        wlo = whi = None
        if ranged:
            wlo, whi = window(start, end)
            covers = any(wlo <= L <= whi for L in named)
            near = any(0 <= L - start <= 30 for L in named)
            equal = start in named
        total = result.get("total_lines") if isinstance(result, dict) else None
        recs.append(dict(group=group, task=task, file=fp, first=first, cls=cls, way=way, named=named,
                         start=start, end=end, ranged=ranged, covers=covers, near=near, equal=equal,
                         wlo=wlo, whi=whi, total=total))
    return recs


def random_cover(named, wlen, T):
    """Exact share of window positions (length wlen, placed inside a file of T lines) covering a named line."""
    w = max(1, min(wlen, T))
    npos = T - w + 1
    ivs = []
    for L in named:
        if 1 <= L <= T:
            lo, hi = max(1, L - w + 1), min(L, npos)
            if lo <= hi:
                ivs.append((lo, hi))
    ivs.sort()
    tot, cur_lo, cur_hi = 0, None, None
    for lo, hi in ivs:
        if cur_hi is None or lo > cur_hi + 1:
            if cur_hi is not None:
                tot += cur_hi - cur_lo + 1
            cur_lo, cur_hi = lo, hi
        else:
            cur_hi = max(cur_hi, hi)
    if cur_hi is not None:
        tot += cur_hi - cur_lo + 1
    return tot / npos


# ---------------------------------------------------------------- report
def pct(a, b):
    return f"{100.0 * a / b:5.1f}%" if b else "   n/a"


def main():
    files = discover()
    recs, nfiles, nfail = [], Counter(), Counter()
    for g, p in files:
        nfiles[g] += 1
        try:
            recs.extend(process(g, p))
        except Exception as e:  # noqa: BLE001
            nfail[g] += 1
            stats["fail:" + type(e).__name__] += 1

    def in_group(r, g):
        if g == "POOL_OF_3":
            return r["group"] in POOL3
        return r["group"] in POOL if g == "POOLED_31B" else r["group"] == g

    lines = []
    P = lines.append
    P("Independent re-derivation: address in the observation before a read_file (first reads)")
    P("=" * 96)
    for title, want_first in (("A. FIRST reads of a file", True), ("E. NOT-first reads of a file", False)):
        P("")
        P(title + ": reads, ranged (asked start > 1), % ranged")
        P(f"{'group':<18} {'class':<11} {'reads':>6} {'ranged':>7} {'%ranged':>8}")
        for g in GROUP_ORDER:
            sub = [r for r in recs if in_group(r, g) and r["first"] == want_first]
            for c in CLASSES:
                s = [r for r in sub if r["cls"] == c]
                k = sum(r["ranged"] for r in s)
                P(f"{g:<18} {c:<11} {len(s):>6} {k:>7} {pct(k, len(s)):>8}")
            k = sum(r["ranged"] for r in sub)
            P(f"{g:<18} {'(all)':<11} {len(sub):>6} {k:>7} {pct(k, len(sub)):>8}")

    for pool_name, pool in (("POOLED 31B", POOL), ("POOL OF 3", POOL3)):
        report_pool(P, recs, pool_name, pool)

    P("")
    P("F. Trace files read per group and parse failures")
    for g in sorted(nfiles):
        P(f"   {g:<18} files {nfiles[g]:>5}  failed {nfail[g]:>3}")
    P(f"   total              files {sum(nfiles.values()):>5}  failed {sum(nfail.values()):>3}")
    P("")
    P("Notes: read_file calls total %d; damaged argument names repaired: start %d, end %d; "
      "duplicate start/end keys: %d/%d; other stats: %s" % (
          len(recs), stats["damaged_start_key"], stats["damaged_end_key"],
          stats["duplicate_start_key"], stats["duplicate_end_key"],
          {k: v for k, v in stats.items() if k.startswith("fail:")}))
    print("\n".join(lines) + "\n", end="")


def report_pool(P, recs, pool_name, pool):
    pooled_first = [r for r in recs if r["group"] in pool and r["first"]]
    addr_r = [r for r in pooled_first if r["cls"] == "ADDRESS" and r["ranged"]]
    n = len(addr_r)
    P("")
    P("B. %s, class ADDRESS, ranged first reads: n = %d" % (pool_name, n))
    P(f"   covers a named line (window = [start, min(end, start+149)]): {sum(r['covers'] for r in addr_r):>5}  {pct(sum(r['covers'] for r in addr_r), n)}")
    P(f"   asked start 0..30 lines before a named line:                 {sum(r['near'] for r in addr_r):>5}  {pct(sum(r['near'] for r in addr_r), n)}")
    P(f"   asked start equals a named line:                             {sum(r['equal'] for r in addr_r):>5}  {pct(sum(r['equal'] for r in addr_r), n)}")
    wt = [r for r in addr_r if isnum(r["total"]) and r["total"] > 0]
    rnd = [random_cover(r["named"], r["whi"] - r["wlo"] + 1, int(r["total"])) for r in wt]
    act = sum(r["covers"] for r in wt)
    P(f"   reads whose own result gives total_lines: {len(wt)}")
    P(f"     random same-length window inside the file, mean exact cover share: "
      f"{(100.0 * sum(rnd) / len(rnd)) if rnd else float('nan'):.1f}%")
    P(f"     (actual cover in this same subset: {act} = {pct(act, len(wt)).strip()})")
    nonpos = sum(1 for r in addr_r if r["whi"] < r["wlo"])
    P(f"   ranged ADDRESS reads with an empty asked window (end < start): {nonpos}")

    P("")
    P("C. %s, class ADDRESS first reads, by way (first that applies: i, ii, iii)" % pool_name)
    for w, lab in (("i", "(i) path:N: / path-N-"), ("ii", "(ii) traceback path\", line N"),
                   ("iii", "(iii) grep -n / cat -n / nl on the file")):
        s = [r for r in pooled_first if r["cls"] == "ADDRESS" and r["way"] == w]
        k = sum(r["ranged"] for r in s)
        P(f"   {lab:<42} reads {len(s):>5}  ranged {k:>5}  {pct(k, len(s))}")

    P("")
    P("D. %s first reads, per-task mean of share ranged (task = file name after 'trace_')" % pool_name)
    for c in ("ADDRESS", "PATH_ONLY"):
        bt = defaultdict(list)
        for r in pooled_first:
            if r["cls"] == c:
                bt[r["task"]].append(r["ranged"])
        shares = [sum(v) / len(v) for v in bt.values()]
        m = 100.0 * sum(shares) / len(shares) if shares else float("nan")
        P(f"   {c:<10} tasks {len(shares):>4}  mean per-task % ranged {m:5.1f}%")


if __name__ == "__main__":
    main()
