"""Independent re-derivation (EXPLORATORY): where read_file calls start, and what the run held when it chose the start.

Written blind from a brief's definitions, without the project's own script or its output. Raw inputs only: the public
starter-agent traces (analysis/graphloc_traces.py, arms base and skill), the vanductan and niraberman public traces,
our whole runs of 14 (analysis/results/14/<N|NAF>/seed*/traces), and data/tasks.jsonl (reference patch and task text).
Helpers for READ parsing, shell-command splitting and path matching were copied from
analysis/rederive_public_address.py and adapted to the brief; the hunk walk is new (CHANGED REGION is the removed and
insertion-neighbour lines of a hunk, not the whole hunk).

Usage: py -I -X utf8 analysis/rederive_read_starts.py      (prints its report; writes nothing)
"""
import collections
import glob
import json
import os
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import graphloc_traces as gt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VIEWERS = {"cat", "head", "tail", "sed", "nl", "less", "more", "awk"}
SOURCES = ["TASK TEXT", "OWN SEARCH", "COMMAND OUTPUT", "OTHER TOOL"]
CLASSES = ["TOP", "PAGING", "ADDRESSED", "SHELL VIEW", "NO NUMBER"]
diag = collections.Counter()


# ---------------------------------------------------------------- discovery
def discover():
    src = collections.OrderedDict((k, []) for k in [
        "public starter arm base", "public skill arm", "vanductan 31b", "niraberman",
        "vanductan 12b", "vanductan e4b", "ours N", "ours NAF"])
    for r in gt.iter_runs(arm="base"):
        src["public starter arm base"].append(str(r["path"]))
    for r in gt.iter_runs(arm="skill"):
        src["public skill arm"].append(str(r["path"]))
    for p in sorted(glob.glob(str(ROOT / "data" / "public_traces" / "vanductan__gemma4-patchpool" / "traces" / "*"
                                  / "traces" / "trace_*.json"))):
        run = Path(p).parts[-3]
        for pre, key in (("31b_", "vanductan 31b"), ("12b_", "vanductan 12b"), ("e4b_", "vanductan e4b")):
            if run.startswith(pre):
                src[key].append(p)
                break
        else:
            diag["vanductan run of another model (left out)"] += 1
    src["niraberman"] = sorted(glob.glob(str(ROOT / "data" / "public_traces" / "niraberman__gemma4-commit-anatomy-traces"
                                             / "arena_v2*" / "results_*" / "traces" / "trace_*.json")))
    for arm in ("N", "NAF"):
        src["ours " + arm] = sorted(glob.glob(str(ROOT / "analysis" / "results" / "14" / arm / "seed*" / "traces"
                                                  / "trace_*.json")))
    return src


# ---------------------------------------------------------------- small helpers
def norm_file(fp):
    if not isinstance(fp, str):
        return None
    fp = fp.strip()
    changed = True
    while changed:
        changed = False
        for pre in ("/workspace/", "workspace/", "./"):
            if fp.startswith(pre):
                fp, changed = fp[len(pre):], True
    return fp


def clean_key(k):
    return re.sub(r"[\"'\\\s]", "", str(k))


def isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


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
            diag["result content not JSON (kept as text)"] += 1
            return c
    return c


PRE = r"(?<![A-Za-z0-9_.\-])"            # a directory prefix ('/') is allowed, a longer file name is not
POST = r"(?![A-Za-z0-9_]|[.\-][A-Za-z0-9_])"  # not the head of a longer file name


def names_path(text, path):
    return re.search(PRE + re.escape(path) + POST, text) is not None


def split_segments(cmd):
    """Quote-aware split of a shell command on unquoted | ; & newline ( ) and backquote."""
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
    while w:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w[0]) or w[0] in ("sudo", "time", "command", "exec", "$", "!"):
            w = w[1:]
        elif w[0] == "timeout" and len(w) > 1:
            w = w[2:]
        elif w[0] == "xargs":
            w = w[1:]
            while w and w[0].startswith("-"):
                w = w[1:]
        else:
            break
    return w


def first_word(words):
    return os.path.basename(words[0]) if words else ""


def has_n_flag(words):
    return any(re.match(r"^-[A-Za-z]*n[A-Za-z0-9]*$", t) or t == "--line-number" for t in words)


def numbering_command(cmd):
    """grep / egrep / fgrep / rg / git grep with -n, cat -n, or nl, in some segment of the command."""
    for seg in split_segments(cmd):
        w = seg_words(seg)
        fw = first_word(w)
        if fw in ("grep", "egrep", "fgrep", "rg") and has_n_flag(w[1:]):
            return True
        if fw == "git" and "grep" in w[1:4]:
            k = w.index("grep", 1)
            if has_n_flag(w[k + 1:]):
                return True
        if fw == "cat" and any(re.match(r"^-[A-Za-z]*n[A-Za-z]*$", t) or t == "--number" for t in w[1:]):
            return True
        if fw == "nl":
            return True
    return False


def uses_viewer(cmd):
    return any(first_word(seg_words(seg)) in VIEWERS for seg in split_segments(cmd))


def cmd_of(args):
    c = args.get("command") if isinstance(args, dict) else None
    return c if isinstance(c, str) else ""


# ---------------------------------------------------------------- named lines
def named_in_text(text, path, links=False):
    """Ways (i) and (ii) (and, for the task text, #L links). Returns a set of line numbers."""
    out = set()
    e = re.escape(path)
    for m in re.finditer(PRE + e + r"(?::(\d+):|-(\d+)-)", text):
        out.add(int(m.group(1) or m.group(2)))
    for m in re.finditer(e + r"\", line (\d+)", text):
        out.add(int(m.group(1)))
    if links:
        for m in re.finditer(PRE + e + r"#L(\d+)(?:-L(\d+))?", text):
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            lo, hi = min(a, b), max(a, b)
            if hi - lo > 5000:
                diag["task-text link range over 5000 lines (kept)"] += 1
            out.update(range(lo, hi + 1))
    return out


NUMLINE = re.compile(r"^[ \t]*(\d+)[:\-\t]", re.M)


class Run:
    def __init__(self, path, task_text):
        d = json.load(open(path, encoding="utf-8"))
        self.calls = []  # dicts: idx (from 1), fname, args, result, text
        for s in d.get("steps", []):
            tcs = s.get("tool_calls") or []
            if not tcs:
                if s.get("observation") is not None:
                    diag["observation on a step with no tool call (ignored)"] += 1
                continue
            if len(tcs) > 1:
                diag["steps with several tool calls"] += 1
            for j, tc in enumerate(tcs):
                res = parse_result(s.get("observation")) if j == len(tcs) - 1 else None
                if j == len(tcs) - 1 and s.get("observation") is None:
                    diag["tool-call step with no observation"] += 1
                args = tc.get("arguments")
                if not isinstance(args, dict):
                    args = {}
                text = "\n".join(strings_in(res)) if res is not None else ""
                self.calls.append(dict(idx=len(self.calls) + 1, fname=tc.get("function_name"), args=args,
                                       result=res, text=text))
        self.task_text = task_text
        self._named = {}

    def named_events(self, path):
        """List of (call index, line, source) for every NAMED LINE of `path`; task text has index 0."""
        if path in self._named:
            return self._named[path]
        ev = [(0, L, "TASK TEXT") for L in named_in_text(self.task_text, path, links=True)]
        for c in self.calls:
            if c["fname"] == "read_file":
                continue
            if c["fname"] == "run_command":
                cmd = cmd_of(c["args"])
                own = numbering_command(cmd)
                src = "OWN SEARCH" if own else "COMMAND OUTPUT"
            else:
                cmd, own, src = "", False, "OTHER TOOL"
            if c["text"]:
                for L in named_in_text(c["text"], path):
                    ev.append((c["idx"], L, src))
                if own and names_path(cmd, path):
                    for m in NUMLINE.finditer(c["text"]):
                        ev.append((c["idx"], int(m.group(1)), "OWN SEARCH"))
        self._named[path] = ev
        return ev


# ---------------------------------------------------------------- reads
def asked(args):
    start = end = None
    seen_s = seen_e = False
    for k, v in args.items():
        ck = clean_key(k)
        if ck in ("start_line", "end_line"):
            if ck != k:
                diag["mangled argument name repaired: " + ck] += 1
            if (ck == "start_line" and seen_s) or (ck == "end_line" and seen_e):
                diag["duplicate argument (first kept): " + ck] += 1
                continue
            if not isnum(v):
                diag["argument not a number (absent): " + ck] += 1
                v = None
            if ck == "start_line":
                start, seen_s = v, True
            else:
                end, seen_e = v, True
    return start, end


def window(s, e):
    if e is None or e < s:
        return s, s + 149
    return s, min(e, s + 149)


def paging_kind(s, wend, earlier):
    for rs, re_ in earlier:
        if rs <= s <= re_:
            return "INSIDE"
    for rs, re_ in earlier:
        if re_ < s <= re_ + 10:
            return "NEXT"
    for rs, re_ in earlier:
        if s < rs and rs <= wend + 10:
            return "BACK"
    return None


def analyse_run(run):
    """Returns the per-read records and the per-file returned ranges of a run."""
    written = {}   # file -> earliest call index of an ok write_file
    ranges = collections.defaultdict(list)  # file -> list of (call idx, start, end) of ok reads
    reads = []
    for c in run.calls:
        if c["fname"] == "write_file":
            r = c["result"]
            fp = norm_file(c["args"].get("filepath"))
            if fp and isinstance(r, dict) and r.get("status") == "ok":
                written.setdefault(fp, c["idx"])
            continue
        if c["fname"] != "read_file":
            continue
        fp = norm_file(c["args"].get("filepath")) or ""
        r = c["result"]
        ok = isinstance(r, dict) and r.get("status") == "ok"
        s, e = asked(c["args"])
        rec = dict(idx=c["idx"], file=fp, ok=ok, start=s, end=e, first=not ranges.get(fp))
        if ok:
            rs, re_ = r.get("start_line"), r.get("end_line")
            if not (isnum(rs) and isnum(re_)):
                diag["ok read without numeric returned range"] += 1
                rs = re_ = None
            rec.update(rstart=rs, rend=re_, total=r.get("total_lines"))
            rec["own"] = fp in written and written[fp] < c["idx"]
            earlier = [(a, b) for _, a, b in ranges.get(fp, [])]
            rec["top"] = s is None or s <= 1
            rec["paging"] = rec["addressed"] = None
            rec["near_src"] = set()
            rec["wstart"] = rec["wend"] = None
            if not rec["top"]:
                ws, we = window(s, e)
                rec["wstart"], rec["wend"] = ws, we
                rec["paging"] = paging_kind(s, we, earlier)
                ev = [x for x in run.named_events(fp) if x[0] < c["idx"]]
                near = [x for x in ev if ws - 10 <= x[1] <= we + 10]
                rec["addressed"] = bool(near)
                rec["near_src"] = {x[2] for x in near}
            held = [x for x in run.named_events(fp) if x[0] < c["idx"]]
            rec["held_src"] = {x[2] for x in held}
            shell = False
            for c2 in run.calls[:c["idx"] - 1]:
                if c2["fname"] == "run_command":
                    cmd = cmd_of(c2["args"])
                    if names_path(cmd, fp) and uses_viewer(cmd):
                        shell = True
                        break
            rec["shell"] = shell
            if rec["top"]:
                cls = "TOP"
            elif rec["paging"]:
                cls = "PAGING"
            elif rec["addressed"]:
                cls = "ADDRESSED"
            elif shell:
                cls = "SHELL VIEW"
            else:
                cls = "NO NUMBER"
            rec["cls"] = None if rec["own"] else cls
            rec["cls_any"] = cls
            if rs is not None:
                ranges[fp].append((c["idx"], rs, re_))
        reads.append(rec)
    return reads, ranges


# ---------------------------------------------------------------- changed regions
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def strip_ab(p, pre):
    p = p.split("\t")[0].strip()
    if p == "/dev/null":
        return None
    return norm_file(p[len(pre):] if p.startswith(pre) else p)


def parse_patch(patch, dg):
    """[(old path, new path, [(a, b, tags)])]; tags is the hunk body as ' ', '-', '+'."""
    files = []
    lines = patch.splitlines()
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("--- ") and i + 1 < n and lines[i + 1].startswith("+++ "):
            files.append([strip_ab(line[4:], "a/"), strip_ab(lines[i + 1][4:], "b/"), []])
            i += 2
            continue
        m = HUNK.match(line)
        if m and files:
            a = int(m.group(1))
            b = 1 if m.group(2) is None else int(m.group(2))
            c = 1 if m.group(4) is None else int(m.group(4))
            ro, rn, tags = b, c, []
            i += 1
            while i < n and (ro > 0 or rn > 0):
                t = lines[i]
                if t.startswith("\\"):
                    i += 1
                    continue
                tag = t[:1] if t else " "
                if tag == " ":
                    ro, rn = ro - 1, rn - 1
                elif tag == "-":
                    ro -= 1
                elif tag == "+":
                    rn -= 1
                else:
                    dg["unexpected line inside a hunk (hunk cut)"] += 1
                    break
                tags.append(tag)
                i += 1
            files[-1][2].append((a, b, tags))
            continue
        i += 1
    return files


def changed_regions(patch, dg=None):
    """List of (file, first, last) in old-file numbers; one per hunk; created files left out."""
    if dg is None:
        dg = diag
    regs = []
    for old, new, hunks in parse_patch(patch, dg):
        if old is None or all(a == 0 and b == 0 for a, b, _ in hunks):
            dg["patch files created (left out)"] += 1
            continue
        if new is None:
            dg["patch files deleted (kept)"] += 1
        for a, b, tags in hunks:
            if a == 0 and b == 0:
                dg["-0,0 hunk in a modified file (left out)"] += 1
                continue
            got = set()
            o = a if b > 0 else a + 1  # number of the next old line
            old_after = [0] * (len(tags) + 1)
            for k in range(len(tags) - 1, -1, -1):
                old_after[k] = old_after[k + 1] + (tags[k] != "+")
            prev = None
            for k, t in enumerate(tags):
                if t == "-":
                    got.add(o)
                    o += 1
                elif t == " ":
                    o += 1
                elif prev not in ("+", "-"):
                    # first line of an added block that does not directly follow a removed line
                    if o - 1 >= 1:
                        got.add(o - 1)
                    if old_after[k] > 0 or b == 0:
                        got.add(o)
                    else:
                        dg["insertion after the hunk's last old line (line after not taken)"] += 1
                prev = t
            if not got:
                dg["hunk with no region lines (left out)"] += 1
                continue
            regs.append((old, min(got), max(got)))
    return regs


# ---------------------------------------------------------------- stretch
def stretch_end(first_range, ranges):
    reach = first_range[1]
    changed = True
    while changed:
        changed = False
        for _, a, b in ranges:
            if a <= reach + 11 and b > reach:
                reach = b
                changed = True
    return reach


# ---------------------------------------------------------------- report helpers
def fmt(k, n):
    return f"{k}/{n} ({100.0 * k / n:.1f}%)" if n else f"{k}/0 (n/a)"


def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    regions_of = {}
    runrecs = []

    src = discover()
    out = []
    P = out.append
    P("RE-DERIVATION (EXPLORATORY): where read_file calls start, and what the run held")
    P("=" * 100)
    grand_first = grand_nonum = 0
    grand_first_noskill = grand_nonum_noskill = 0
    skill_pooled_first_nonum = 0

    for name, paths in src.items():
        skill = name == "public skill arm"
        allreads = []
        runs_with_nonum = runs_with_pooled = 0
        n_runs = 0
        top_files = top_short = 0
        reg_total = reg_deep = 0
        deep_open = held = held_shown = notheld = notheld_shown = 0
        deep_shown = 0
        firstshow = collections.Counter()
        firstshow_neither_top = 0
        for p in paths:
            tid = Path(p).stem[len("trace_"):]
            if tid not in tasks:
                tid = tid.replace("__", "/")
            if tid not in tasks:
                diag["trace with an unknown task (left out)"] += 1
                continue
            task = tasks[tid]
            run = Run(p, task.get("problem_statement") or "")
            n_runs += 1
            reads, ranges = analyse_run(run)
            allreads.extend(reads)
            if any(r.get("cls") == "NO NUMBER" for r in reads):
                runs_with_nonum += 1
            if any(r.get("cls") in ("SHELL VIEW", "NO NUMBER") for r in reads):
                runs_with_pooled += 1
            # 5. stretch from the top
            firstok = {}
            for r in reads:
                if r["ok"] and r["file"] not in firstok:
                    firstok[r["file"]] = r
            for fp, r in firstok.items():
                if r["own"] or not r["top"] or r["rstart"] != 1:
                    continue
                if not (isnum(r["total"]) and r["total"] > 150):
                    continue
                top_files += 1
                if stretch_end((r["rstart"], r["rend"]), ranges[fp]) <= 160:
                    top_short += 1
            # 6. changed regions
            if tid not in regions_of:
                regions_of[tid] = changed_regions(task["patch"])
            runrecs.append(dict(source=name, task=tid, path=p, regions=regions_of[tid], run=run, reads=reads,
                                shown=[any(rs <= b_ and a_ <= re_ for _, rs, re_ in ranges.get(f_, []))
                                       for f_, a_, b_ in regions_of[tid]]))
            readsby = {r["idx"]: r for r in reads}
            for fp, a, b in regions_of[tid]:
                reg_total += 1
                if a <= 150:
                    continue
                reg_deep += 1
                if fp not in ranges:
                    continue
                deep_open += 1
                show = None
                for idx, rs, re_ in ranges[fp]:
                    if rs <= b and a <= re_:
                        show = idx
                        break
                cutoff = show if show is not None else len(run.calls) + 1
                h = any(x[0] < cutoff and a - 10 <= x[1] <= b + 10 for x in run.named_events(fp))
                if h:
                    held += 1
                    held_shown += show is not None
                else:
                    notheld += 1
                    notheld_shown += show is not None
                if show is not None:
                    deep_shown += 1
                    r = readsby[show]
                    pg, ad = bool(r["paging"]), bool(r["addressed"])
                    if pg and not ad:
                        firstshow["PAGING and not ADDRESSED"] += 1
                    elif pg and ad:
                        firstshow["PAGING and ADDRESSED"] += 1
                    elif ad:
                        firstshow["ADDRESSED and not PAGING"] += 1
                    else:
                        firstshow["neither"] += 1
                        firstshow_neither_top += r["top"]
                    if r["own"]:
                        diag["deep region first shown by a read of an OWN FILE"] += 1

        # ---- 1
        n = len(allreads)
        notok = sum(not r["ok"] for r in allreads)
        own = sum(r["ok"] and r["own"] for r in allreads)
        classed = [r for r in allreads if r.get("cls")]
        first = [r for r in classed if r["first"]]
        later = [r for r in classed if not r["first"]]
        P("")
        P(f"### {name}: runs {n_runs}")
        P("1. READS")
        P(f"   READS {n}; not of status ok {fmt(notok, n)}; of an OWN FILE (status ok) {fmt(own, n)}; "
          f"classed {fmt(len(classed), n)}; classed FIRST READS {fmt(len(first), len(classed))}")

        def lab(c):
            if skill and c in ("SHELL VIEW", "NO NUMBER"):
                return "OTHER NUMBER/SHELL VIEW/NO NUMBER"
            return c

        labels = ["TOP", "PAGING", "ADDRESSED"] + (["OTHER NUMBER/SHELL VIEW/NO NUMBER"] if skill
                                                   else ["SHELL VIEW", "NO NUMBER"])
        for title, sub in (("all classed", classed), ("FIRST READS", first), ("later reads", later)):
            cnt = collections.Counter(lab(r["cls"]) for r in sub)
            P(f"   {title:<12} n={len(sub)}: " + "; ".join(f"{L} {fmt(cnt[L], len(sub))}" for L in labels))
        pg = [r for r in classed if r["cls"] == "PAGING"]
        kc = collections.Counter(r["paging"] for r in pg)
        P(f"   PAGING by kind (all classed; FIRST READS cannot page): "
          + "; ".join(f"{k} {fmt(kc[k], len(pg))}" for k in ("INSIDE", "NEXT", "BACK")))

        # ---- 2
        P("2. ASKED STARTS THAT ARE MULTIPLES OF 100")
        nonum_lab = "OTHER NUMBER/SHELL VIEW/NO NUMBER (pooled)" if skill else "NO NUMBER"
        nonum = [r for r in classed if (r["cls"] in ("SHELL VIEW", "NO NUMBER") if skill else r["cls"] == "NO NUMBER")]
        addr = [r for r in classed if r["cls"] == "ADDRESSED"]
        P(f"   {nonum_lab}: {fmt(sum(r['start'] % 100 == 0 for r in nonum), len(nonum))}")
        P(f"   ADDRESSED: {fmt(sum(r['start'] % 100 == 0 for r in addr), len(addr))}")
        P(f"   runs with a READ of class NO NUMBER: {fmt(runs_with_nonum, n_runs)}"
          + (f" (strict NO NUMBER, OTHER NUMBER not separated); with a READ of the pooled class: "
             f"{fmt(runs_with_pooled, n_runs)}" if skill else ""))

        # ---- 3
        P("3. SOURCES OF THE NAMED LINES WITHIN 10 LINES OF THE WINDOW, ADDRESSED reads")
        P("   " + "; ".join(f"{s} {fmt(sum(s in r['near_src'] for r in addr), len(addr))}" for s in SOURCES))
        P(f"   OWN SEARCH and no other SOURCE {fmt(sum(r['near_src'] == {'OWN SEARCH'} for r in addr), len(addr))}")

        # ---- 4
        P("4. CLASSED FIRST READS of a file for which the run held a NAMED LINE before the read")
        hf = [r for r in first if r["held_src"]]
        groups = collections.OrderedDict([
            ("OWN SEARCH among the sources", lambda s: "OWN SEARCH" in s),
            ("COMMAND OUTPUT and no OWN SEARCH", lambda s: "COMMAND OUTPUT" in s and "OWN SEARCH" not in s),
            ("TASK TEXT only", lambda s: s == {"TASK TEXT"}),
            ("any other mix (OTHER TOOL, with or without TASK TEXT)",
             lambda s: "OWN SEARCH" not in s and "COMMAND OUTPUT" not in s and s != {"TASK TEXT"}),
        ])
        P(f"   held any: {fmt(len(hf), len(first))} of classed FIRST READS; ADDRESSED among them "
          f"{fmt(sum(r['cls'] == 'ADDRESSED' for r in hf), len(hf))}")
        for g, f in groups.items():
            sub = [r for r in hf if f(r["held_src"])]
            P(f"   {g:<55} reads {len(sub):>5}; ADDRESSED {fmt(sum(r['cls'] == 'ADDRESSED' for r in sub), len(sub))}")
        nh = [r for r in first if not r["held_src"]]
        P(f"   (held none: {len(nh)}; ADDRESSED among them {sum(r['cls'] == 'ADDRESSED' for r in nh)})")

        # ---- 5
        P("5. FILES WHOSE FIRST READ WAS TOP FROM LINE 1, total_lines > 150")
        P(f"   files {top_files}; STRETCH FROM THE TOP ends at or before line 160: {fmt(top_short, top_files)}")

        # ---- 6
        P("6. CHANGED REGIONS (per run)")
        P(f"   regions {reg_total}; DEEP {fmt(reg_deep, reg_total)}; DEEP in an OPENED FILE {fmt(deep_open, reg_deep)}")
        P(f"   of those: HELD A NUMBER {fmt(held, deep_open)}, SHOWN among them {fmt(held_shown, held)}; "
          f"not held {fmt(notheld, deep_open)}, SHOWN among them {fmt(notheld_shown, notheld)}")
        P(f"   DEEP and SHOWN {deep_shown}; the READ that first showed them: "
          + "; ".join(f"{k} {fmt(firstshow[k], deep_shown)}" for k in
                      ("PAGING and not ADDRESSED", "PAGING and ADDRESSED", "ADDRESSED and not PAGING", "neither"))
          + f"   (of 'neither', TOP reads: {firstshow_neither_top})")

        nf = len(first)
        nn = sum(r["cls"] in (("SHELL VIEW", "NO NUMBER") if skill else ("NO NUMBER",)) for r in first)
        nstrict = sum(r["cls"] == "NO NUMBER" for r in first)
        grand_first += nf
        grand_nonum += nn
        if skill:
            skill_pooled_first_nonum = nn
            skill_strict = nstrict
        else:
            grand_first_noskill += nf
            grand_nonum_noskill += nn

    P("")
    P("Diagnostics: " + "; ".join(f"{k}: {v}" for k, v in sorted(diag.items())))
    P("")
    P(f"OVER THE EIGHT SOURCES: classed FIRST READS {grand_first}; of class NO NUMBER {fmt(grand_nonum, grand_first)} "
      f"(the skill arm adds its pooled OTHER NUMBER/SHELL VIEW/NO NUMBER count {skill_pooled_first_nonum}, "
      f"of which strict NO NUMBER {skill_strict}; without the skill arm: {fmt(grand_nonum_noskill, grand_first_noskill)})")
    parts_7_8(P, runrecs)
    part_9(P, runrecs)
    print("\n".join(out))


# ---------------------------------------------------------------- parts 7 and 8: results and final patches
WITH_RESULTS = ["public starter arm base", "public skill arm", "ours N", "ours NAF"]


def is_true(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v == 1
    return isinstance(v, str) and v.strip().lower() in ("true", "1", "1.0")


def load_public_records():
    recs = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "graphloc" / "out" / "*" / "e2e" / "records" / "rec_w*.jsonl"))):
        nb = Path(f).parts[-4]
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("arm") not in ("base", "skill"):
                continue
            key = (nb, d["arm"], d.get("id"))
            if key in recs:
                diag8["public record seen twice (last kept)"] += 1
            recs[key] = (is_true(d.get("resolved")), d.get("patch") or "")
    return recs


_ours_cache = {}


def ours_results(seed_dir):
    if seed_dir in _ours_cache:
        return _ours_cache[seed_dir]
    rows = {}
    f = Path(seed_dir) / "task_results.jsonl"
    if f.exists():
        for line in open(f, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                tid = d.get("instance_id") or d.get("task_id")
                if tid in rows:
                    diag8["our task seen twice in task_results (last kept)"] += 1
                rows[tid] = d
    _ours_cache[seed_dir] = rows
    return rows


diag8 = collections.Counter()


def run_result(rr, public):
    """(resolved, final patch text) or None when there is no result for the run."""
    p = Path(rr["path"])
    if rr["source"].startswith("public"):
        key = (p.parts[-7], p.parts[-4], rr["task"])
        return public.get(key)
    if rr["source"].startswith("ours"):
        seed_dir = p.parent.parent
        d = ours_results(str(seed_dir)).get(rr["task"])
        if d is None:
            return None
        pf = seed_dir / "patches" / (rr["task"].replace("/", "__") + ".patch")
        if pf.exists():
            patch = pf.read_text(encoding="utf-8", errors="replace")
            diag8["our final patch from the patches/ file"] += 1
        else:
            patch = d.get("agent_patch") or d.get("patch") or ""
            diag8["our final patch from the task_results line" if patch else "our final patch empty"] += 1
        return (is_true(d.get("resolved")), patch if isinstance(patch, str) else "")
    return None


def median(xs):
    return sorted(xs)[len(xs) // 2] if xs else "n/a"


def parts_7_8(P, runrecs):
    public = load_public_records()
    kept = [r for r in runrecs if r["regions"]]
    diag8["runs left out of 7 and 8 (task has no CHANGED REGION)"] = len(runrecs) - len(kept)
    for r in kept:
        r["all_shown"] = all(r["shown"])
        res = run_result(r, public) if r["source"] in WITH_RESULTS else None
        if r["source"] in WITH_RESULTS and res is None:
            diag8["run with no result found (" + r["source"] + ")"] += 1
        r["has_result"] = res is not None
        r["resolved"] = bool(res and res[0])
        fpr = changed_regions(res[1], diag8) if res is not None else []
        r["fpr"] = fpr
        r["edited"] = [any(ff == f and fa <= b and a <= fb for ff, fa, fb in fpr) for f, a, b in r["regions"]]
        r["has_patch"] = bool(fpr)

    def nfiles(r):
        return len({f for f, _, _ in r["regions"]})

    def deepest(r):
        return max(a for _, a, _ in r["regions"])

    def band_line(x):
        return "<=150" if x <= 150 else "151-450" if x <= 450 else "451-900" if x <= 900 else ">900"

    P("")
    P("=" * 100)
    P("7. RUNS OF TASKS WITH A CHANGED REGION: tasks, runs, SHOWN EVERY REGION, resolved (where results exist)")
    for name in [k for k in dict.fromkeys(r["source"] for r in runrecs)]:
        rs = [r for r in kept if r["source"] == name]
        withres = name in WITH_RESULTS
        P("")
        P(f"### {name}: tasks {len({r['task'] for r in rs})}, runs {len(rs)}")

        def row(label, sub):
            s = f"   {label:<22} tasks {len({r['task'] for r in sub}):>4}; runs {len(sub):>4}; " \
                f"SHOWN EVERY REGION {fmt(sum(r['all_shown'] for r in sub), len(sub))}"
            if withres:
                s += f"; resolved {fmt(sum(r['resolved'] for r in sub), len(sub))}"
            P(s)

        P(" a. by the number of CHANGED REGIONS of the task")
        for lab, f in (("1", lambda n: n == 1), ("2 or 3", lambda n: 2 <= n <= 3), ("4 to 9", lambda n: 4 <= n <= 9),
                       ("10 or more", lambda n: n >= 10)):
            row(lab, [r for r in rs if f(len(r["regions"]))])
        P(" b. by the number of files with a CHANGED REGION")
        for lab, f in (("1", lambda n: n == 1), ("2", lambda n: n == 2), ("3 or more", lambda n: n >= 3)):
            row(lab, [r for r in rs if f(nfiles(r))])
        P(" c. by the first line of the task's deepest CHANGED REGION")
        for lab in ("<=150", "151-450", "451-900", ">900"):
            row(lab, [r for r in rs if band_line(deepest(r)) == lab])
        P(" d. tasks with exactly one CHANGED REGION, by its first line")
        for lab in ("<=150", "151-450", "451-900", ">900"):
            row(lab, [r for r in rs if len(r["regions"]) == 1 and band_line(r["regions"][0][1]) == lab])

    P("")
    P("=" * 100)
    P("8. RESULTS, FINAL PATCHES AND EDITED REGIONS (sources with results)")
    for name in WITH_RESULTS:
        for glab, gsel in (("ONE CHANGED REGION", lambda r: len(r["regions"]) == 1),
                           ("TWO OR MORE CHANGED REGIONS", lambda r: len(r["regions"]) >= 2)):
            rs = [r for r in kept if r["source"] == name and gsel(r) and r["has_result"]]
            P("")
            P(f"### {name}, tasks with {glab}: tasks {len({r['task'] for r in rs})}")
            res = [r for r in rs if r["resolved"]]
            unres = [r for r in rs if not r["resolved"]]
            P(f" a. runs {len(rs)}; resolved {fmt(len(res), len(rs))}; no patch {fmt(sum(not r['has_patch'] for r in rs), len(rs))}; "
              f"median FINAL PATCH REGIONS {median([len(r['fpr']) for r in rs])}; "
              f"median CHANGED REGIONS {median([len(r['regions']) for r in rs])}")

            def three(sub):
                never = sum(not r["all_shown"] for r in sub)
                se = sum(r["all_shown"] and not all(r["edited"]) for r in sub)
                sa = sum(r["all_shown"] and all(r["edited"]) for r in sub)
                return (f"a region never SHOWN {fmt(never, len(sub))}; every region SHOWN, not every one EDITED "
                        f"{fmt(se, len(sub))}; every region SHOWN and EDITED {fmt(sa, len(sub))}")

            P(f" b. not resolved ({len(unres)}): " + three(unres))
            ae = sum(all(r["edited"]) for r in res)
            se = sum(any(r["edited"]) and not all(r["edited"]) for r in res)
            ne = sum(not any(r["edited"]) for r in res)
            P(f" c. resolved ({len(res)}): every region EDITED {fmt(ae, len(res))}; some but not all {fmt(se, len(res))}; "
              f"none {fmt(ne, len(res))}; SHOWN EVERY REGION {fmt(sum(r['all_shown'] for r in res), len(res))}")
            hp = [r for r in rs if r["has_patch"]]
            hpu = [r for r in hp if not r["resolved"]]
            regs = [(s, e) for r in hp for s, e in zip(r["shown"], r["edited"])]
            P(f" d. HAS A PATCH: runs {len(hp)}; resolved {fmt(sum(r['resolved'] for r in hp), len(hp))}; "
              f"median FINAL PATCH REGIONS {median([len(r['fpr']) for r in hp])}")
            P(f"    not resolved ({len(hpu)}): " + three(hpu))
            nsh = sum(s for s, _ in regs)
            P(f"    CHANGED REGIONS of these runs {len(regs)}; SHOWN {fmt(nsh, len(regs))}; "
              f"EDITED among the SHOWN {fmt(sum(s and e for s, e in regs), nsh)}")
            regs = [(s, e) for r in rs for s, e in zip(r["shown"], r["edited"])]
            nsh = sum(s for s, _ in regs)
            P(f" e. all CHANGED REGIONS of the group {len(regs)}; SHOWN {fmt(nsh, len(regs))}; "
              f"EDITED {fmt(sum(e for _, e in regs), len(regs))}; EDITED among the SHOWN {fmt(sum(s and e for s, e in regs), nsh)}")
    P("")
    P("Diagnostics, parts 7 and 8: " + "; ".join(f"{k}: {v}" for k, v in sorted(diag8.items())))


# ---------------------------------------------------------------- part 9: what a run does after its first fix edit
diag9 = collections.Counter()
SEARCHERS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "find"}


def is_search(cmd):
    for seg in split_segments(cmd):
        w = seg_words(seg)
        if first_word(w) in SEARCHERS:
            return True
        if first_word(w) == "git" and len(w) > 1 and w[1] == "grep":
            return True
    return False


def overlaps(a, b, c, d):
    return a <= d and c <= b


def part_9(P, runrecs):
    kept = [r for r in runrecs if r["regions"]]
    P("")
    P("=" * 100)
    P("9. AFTER THE FIRST FIX EDIT (runs of tasks with a CHANGED REGION)")
    for r in kept:
        run, regs = r["run"], r["regions"]
        reg_files = {f for f, _, _ in regs}
        fix = []  # (call idx, set of indices of CHANGED REGIONS it overlaps)
        for c in run.calls:
            if c["fname"] != "edit_file":
                continue
            res = c["result"]
            if not (isinstance(res, dict) and res.get("status") == "ok"):
                continue
            fp = norm_file(res.get("filepath")) or norm_file(c["args"].get("filepath"))
            if fp not in reg_files:
                continue
            d = res.get("diff")
            if not isinstance(d, str) or not d.strip():
                diag9["ok edit_file on a region file with no diff"] += 1
                continue
            eregs = changed_regions(d, diag9)
            if any(ef != fp for ef, _, _ in eregs):
                diag9["edit diff naming another file than the result (diff's own file used)"] += 1
            hit = {i for i, (f, a, b) in enumerate(regs)
                   for ef, ea, eb in eregs if ef == f and overlaps(a, b, ea, eb)}
            if hit:
                fix.append((c["idx"], hit))
        r["fix"] = fix
        r["n_calls"] = len(run.calls)
        if not fix:
            continue
        t0, first_hit = fix[0]
        r["t0"] = t0
        r["after"] = len(run.calls) - t0
        r["search_after"] = any(c["idx"] > t0 and c["fname"] == "run_command" and is_search(cmd_of(c["args"]))
                                for c in run.calls)
        okreads = [x for x in r["reads"] if x["ok"] and x["rstart"] is not None]
        seen = collections.defaultdict(set)
        new_read = False
        new_files = set()
        before_files = {x["file"] for x in okreads if not x["own"] and x["idx"] < t0}
        for x in okreads:  # in call order
            if x["own"]:
                continue
            lines = set(range(x["rstart"], x["rend"] + 1))
            if x["idx"] > t0 and lines - seen[x["file"]]:
                new_read = True
                if x["file"] not in before_files:
                    new_files.add(x["file"])
            seen[x["file"]] |= lines
        r["new_read"] = new_read
        r["new_file"] = bool(new_files)
        ns = [i for i, (f, a, b) in enumerate(regs)
              if not any(x["file"] == f and x["idx"] <= t0 and overlaps(a, b, x["rstart"], x["rend"]) for x in okreads)]
        r["not_shown_t0"] = ns
        r["shown_later"] = [i for i in ns
                            if any(x["file"] == regs[i][0] and x["idx"] > t0
                                   and overlaps(regs[i][1], regs[i][2], x["rstart"], x["rend"]) for x in okreads)]
        r["later_other"] = any(idx > t0 and (hit - first_hit) for idx, hit in fix[1:])

    for name in dict.fromkeys(r["source"] for r in runrecs):
        withres = name in WITH_RESULTS
        P("")
        P(f"### {name}")
        for glab, gsel, multi in (("ONE CHANGED REGION", lambda r: len(r["regions"]) == 1, False),
                                  ("TWO OR MORE CHANGED REGIONS", lambda r: len(r["regions"]) >= 2, True)):
            rs = [r for r in kept if r["source"] == name and gsel(r)]
            fx = [r for r in rs if r["fix"]]
            P(f" [{glab}]")
            P(f" a. runs {len(rs)}; with a FIX EDIT {fmt(len(fx), len(rs))}; median t0 {median([r['t0'] for r in fx])}; "
              f"median tool calls of the run {median([r['n_calls'] for r in fx])}")
            P(f" b. median calls AFTER IT {median([r['after'] for r in fx])}; SEARCH after {fmt(sum(r['search_after'] for r in fx), len(fx))}; "
              f"NEW READ {fmt(sum(r['new_read'] for r in fx), len(fx))}; NEW FILE {fmt(sum(r['new_file'] for r in fx), len(fx))}; "
              f"neither SEARCH nor NEW READ {fmt(sum(not r['search_after'] and not r['new_read'] for r in fx), len(fx))}")
            if not multi:
                continue
            wn = [r for r in fx if r["not_shown_t0"]]
            nreg = sum(len(r["not_shown_t0"]) for r in wn)
            nlat = sum(len(r["shown_later"]) for r in wn)
            P(f" c. runs with a region NOT SHOWN AT t0 {fmt(len(wn), len(fx))}; such regions {nreg}; SHOWN LATER {fmt(nlat, nreg)}; "
              f"runs with one SHOWN LATER {fmt(sum(bool(r['shown_later']) for r in wn), len(wn))}; "
              f"of those runs, SEARCH or NEW READ after {fmt(sum(r['search_after'] or r['new_read'] for r in wn), len(wn))}")
            lo = [r for r in fx if r["later_other"]]
            no = [r for r in fx if not r["later_other"]]
            s = f" d. LATER FIX EDIT OF ANOTHER REGION {fmt(len(lo), len(fx))}"
            if withres:
                s += (f"; resolved among them {fmt(sum(r.get('resolved', False) for r in lo), len(lo))}; "
                      f"resolved among the runs with a FIX EDIT and none {fmt(sum(r.get('resolved', False) for r in no), len(no))}")
            P(s)
    P("")
    P("Diagnostics, part 9: " + "; ".join(f"{k}: {v}" for k, v in sorted(diag9.items())))


if __name__ == "__main__":
    main()
