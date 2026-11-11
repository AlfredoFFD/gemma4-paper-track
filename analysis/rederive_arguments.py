"""Independent re-derivation (EXPLORATORY): where the arguments of an agent's calls come from.

Written blind from a brief's definitions, without the project's own script or its output. It reuses the trace parsing,
READ classing, NAMED LINES, CHANGED REGIONS, SEARCH test and result loaders of analysis/rederive_read_starts.py (an
earlier independent script of the same kind), and analysis/nodes.py for function and class spans.

Parts: A file paths of read_file / edit_file; B start lines of ranged reads; C edit_file old_string; D search words;
E the places the task statement names. CONTEXT at a call = system prompt + task prompt + result text of every earlier
tool call.

Usage: py -I -X utf8 analysis/rederive_arguments.py      (prints its report; writes nothing itself)
"""
import collections
import glob
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402
import nodes  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
dg = collections.Counter()
GRAPH_TOOLS = {"get_code_neighbors", "get_code_subgraph", "search_similar_code"}
IDCH = "A-Za-z0-9_"
MARK = re.compile(r"^\[omitted: (\d+) characters, sha1 ([0-9a-f]{40})\]$")
fmt = R.fmt


def sha1(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- prompts
def prompt_steps(d):
    sys_m = user_m = None
    for s in d.get("steps", [])[:3]:
        if s.get("tool_calls"):
            continue
        if s.get("source") == "system" and sys_m is None:
            sys_m = s.get("message") or ""
        elif s.get("source") == "user" and user_m is None:
            user_m = s.get("message") or ""
    return sys_m, user_m


def build_prompt_store():
    store = {}
    for r in R.gt.iter_runs():
        d = R.gt.load(r["path"])
        s, _ = prompt_steps(d)
        if s and not MARK.match(s):
            store.setdefault(sha1(s), s)
    f = HERE / "fork_states_w" / "first_call_states.jsonl"
    for line in open(f, encoding="utf-8"):
        if line.strip():
            for st in json.loads(line).get("steps", []):
                m = st.get("message")
                if isinstance(m, str) and m:
                    store.setdefault(sha1(m), m)
    return store


def recover(msg, store, kind, source):
    if msg is None:
        dg[f"{kind} prompt missing ({source})"] += 1
        return ""
    m = MARK.match(msg.strip())
    if not m:
        return msg
    txt = store.get(m.group(2))
    if txt is None:
        dg[f"{kind} prompt NOT recovered ({source})"] += 1
        return ""
    if len(txt) != int(m.group(1)):
        dg[f"{kind} prompt recovered, length differs from the marker ({source})"] += 1
    dg[f"{kind} prompt recovered by sha1 ({source})"] += 1
    return txt


# ---------------------------------------------------------------- matching helpers
def path_re(path):
    return re.compile(r"(?<![A-Za-z0-9_.\-])" + re.escape(path) + r"(?![A-Za-z0-9_])")


def dotted_names(path):
    if not path.endswith(".py"):
        return []
    out = []
    for p in (path, path[4:] if path.startswith("src/") else None):
        if not p:
            continue
        m = p[:-3]
        if m.endswith("/__init__"):
            m = m[:-len("/__init__")]
        m = m.replace("/", ".")
        if "." in m and m not in out:
            out.append(m)
    return out


def dotted_re(name):
    return re.compile(r"(?<![A-Za-z0-9_.])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def ident_re(word):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])")


def SQ(x):
    return re.sub(r"\s+", " ", x)


UNMAP = {"n": "\n", "t": "\t", '"': '"', "'": "'"}


def UN(x):
    return re.sub(r"\\([nt\"'])", lambda m: UNMAP[m.group(1)], x)


# ---------------------------------------------------------------- a run with its context
class CRun:
    def __init__(self, path, task, store, source):
        self.run = R.Run(path, task.get("problem_statement") or "")
        d = json.load(open(path, encoding="utf-8"))
        s, u = prompt_steps(d)
        s = recover(s, store, "system", source)
        u = recover(u, store, "task", source)
        tid = task["instance_id"]
        ph = f"<TASK_TEXT:{tid}>"
        if ph in u:
            u = u.replace(ph, task.get("problem_statement") or "")
            dg[f"task-text placeholder replaced by the task statement ({source})"] += 1
        if re.search(r"<SYSTEM_PROMPT_OMITTED[^>]*>", s):
            dg[f"system prompt is a placeholder, kept as is ({source})"] += 1
        self.prompts = [s, u]
        self.calls = self.run.calls
        self._first = {}

    def first_at(self, key, rx):
        """Index of the earliest context piece holding rx: 0 = a prompt, k = result of call k; None if never."""
        if key in self._first:
            return self._first[key]
        ans = None
        if any(rx.search(p) for p in self.prompts):
            ans = 0
        else:
            for c in self.calls:
                if c["text"] and rx.search(c["text"]):
                    ans = c["idx"]
                    break
        self._first[key] = ans
        return ans

    def in_ctx(self, key, rx, k):
        f = self.first_at(key, rx)
        return f is not None and f < k

    def context(self, k):
        return "\n".join(self.prompts + [c["text"] for c in self.calls if c["idx"] < k and c["text"]])


def call_kind(c):
    fn = c["fname"]
    if fn == "run_command":
        return "OWN SEARCH" if R.is_search(R.cmd_of(c["args"])) else "COMMAND OUTPUT"
    if fn in GRAPH_TOOLS:
        return "GRAPH TOOL"
    if fn == "read_file":
        return "READ"
    return "OTHER TOOL"


def status_ok(c):
    return isinstance(c["result"], dict) and c["result"].get("status") == "ok"


# ---------------------------------------------------------------- part D: search pattern
OPT_VAL = {"-f", "-A", "-B", "-C", "-m", "-d", "-D", "-g", "-t", "-T", "--include", "--exclude", "--exclude-dir",
           "--max-count", "--after-context", "--before-context", "--context", "--glob", "--type"}


def split_pieces(cmd):
    """Quote-aware cut on unquoted | ; & ( )."""
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
        elif ch in "|;&()":
            segs.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return [s.strip() for s in segs if s.strip()]


def search_pattern(cmd):
    """(pattern or None, reason)."""
    for piece in split_pieces(cmd):
        try:
            w = shlex.split(piece, posix=True)
        except Exception:
            w = piece.split()
            dg["search piece not shell-parsable (split on blanks)"] += 1
        if not w:
            continue
        fw = os.path.basename(w[0])
        if fw in ("grep", "egrep", "fgrep", "rg", "ag", "ack") or (fw == "git" and len(w) > 1 and w[1] == "grep"):
            rest = w[2:] if fw == "git" else w[1:]
            i = 0
            while i < len(rest):
                t = rest[i]
                if t in ("-e", "--regexp", "--"):
                    return (rest[i + 1], "ok") if i + 1 < len(rest) else (None, "no pattern")
                if t.startswith("--regexp="):
                    return t[len("--regexp="):], "ok"
                if t in OPT_VAL:
                    i += 2
                    continue
                if t.startswith("-"):
                    i += 1
                    continue
                return t, "ok"
            return None, "no pattern"
        if fw == "find":
            for i, t in enumerate(w[1:-1], start=1):
                if t in ("-name", "-iname", "-path", "-ipath", "-regex"):
                    return w[i + 1], "ok"
            return None, "no pattern"
    return None, "no piece begins with a search tool"


def search_word(pat):
    best = None
    for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{2,}", pat):
        if best is None or len(m.group(0)) > len(best):
            best = m.group(0)
    return best


# ---------------------------------------------------------------- part E: place names
def place_name(tid, path, line):
    if not path.endswith(".py"):
        return None
    sc = nodes.scopes(tid, path)
    best = None
    for q, (a, b, _) in sc.items():
        if a <= line <= b:
            key = (b - a, -q.count("."), q)
            if best is None or key < best[0]:
                best = (key, q)
    return best[1].split(".")[-1] if best else None


def plain(name):
    return "_" not in name and not re.search(r"\d", name) and not re.search(r"[a-z][A-Z]", name)


def named_in(stmt, name):
    if plain(name):
        return bool(re.search(r"`" + re.escape(name) + r"`", stmt)
                    or re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\(", stmt)
                    or re.search(r"\." + re.escape(name) + r"(?![A-Za-z0-9_])", stmt))
    return bool(ident_re(name).search(stmt))


def file_named(stmt, path):
    if path_re(path).search(stmt):
        return True
    if any(dotted_re(m).search(stmt) for m in dotted_names(path)):
        return True
    return bool(ident_re(os.path.basename(path)).search(stmt))


# ---------------------------------------------------------------- main
def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    store = build_prompt_store()
    public = R.load_public_records()
    src = R.discover()
    regions_of, place_of = {}, {}
    out = []
    P = out.append
    P("RE-DERIVATION (EXPLORATORY): where the arguments of the agent's calls come from")
    P("=" * 100)
    for name, paths in src.items():
        skill = name == "public skill arm"
        A = collections.Counter()
        B = collections.Counter()
        C = collections.Counter()
        D = collections.Counter()
        Erows = []   # (class, task, shown, opened)
        Eruns = []   # (task, n regions, n named, resolved)
        for p in paths:
            tid = Path(p).stem[len("trace_"):]
            if tid not in tasks:
                tid = tid.replace("__", "/")
            task = tasks[tid]
            stmt = task.get("problem_statement") or ""
            cr = CRun(p, task, store, name)
            calls = cr.calls

            # ---- A
            used, written = set(), set()
            for c in calls:
                fn = c["fname"]
                if fn in ("read_file", "edit_file"):
                    raw = c["args"].get("filepath")
                    if not isinstance(raw, str) or not R.norm_file(raw):
                        dg["read/edit call without a usable filepath (left out of A)"] += 1
                    else:
                        fp = R.norm_file(raw)
                        A["uses"] += 1
                        if fp in written:
                            A["OWN FILE"] += 1
                        elif fp in used:
                            A["REUSE"] += 1
                        else:
                            A["FIRST USES"] += 1
                            ok = status_ok(c)
                            if cr.in_ctx(("p", fp), path_re(fp), c["idx"]):
                                cls = "IN CONTEXT"
                            elif fp.endswith(".py") and any(cr.in_ctx(("d", m), dotted_re(m), c["idx"])
                                                            for m in dotted_names(fp)):
                                cls = "DOTTED NAME"
                            else:
                                cls = "NEITHER"
                            A[cls] += 1
                            A[cls + " WORKS"] += ok
                            if cls == "IN CONTEXT":
                                rx = path_re(fp)
                                if rx.search(stmt):
                                    w = "TASK STATEMENT"
                                elif any(rx.search(x) for x in cr.prompts):
                                    w = "REST OF THE PROMPT"
                                else:
                                    k = cr.first_at(("p", fp), rx)
                                    w = call_kind(calls[k - 1])
                                A["WHERE " + w] += 1
                        used.add(fp)
                if fn == "write_file":
                    raw = c["args"].get("filepath")
                    if isinstance(raw, str) and R.norm_file(raw):
                        written.add(R.norm_file(raw))

            # ---- B
            reads, ranges = R.analyse_run(cr.run)
            for r in reads:
                if not r.get("cls") or r["cls"] == "TOP":
                    continue
                B["reads"] += 1
                named = {x[1] for x in cr.run.named_events(r["file"]) if x[0] < r["idx"]}
                ends = {e for i, s, e in ranges.get(r["file"], []) if i < r["idx"]}
                if r["start"] in named:
                    B["EXACT"] += 1
                elif r["start"] in {e + 1 for e in ends}:
                    B["NEXT ONE"] += 1
                elif r["cls"] == "PAGING":
                    B["PAGING neither"] += 1
                elif r["cls"] == "ADDRESSED":
                    B["ADDRESSED neither"] += 1
                else:
                    B["rest"] += 1

            # ---- C
            written = set()
            own = []
            for c in calls:
                fn = c["fname"]
                if fn == "edit_file":
                    old = c["args"].get("old_string")
                    fp = R.norm_file(c["args"].get("filepath")) if isinstance(c["args"].get("filepath"), str) else None
                    if isinstance(old, str) and old.strip() and fp not in written:
                        ctx = cr.context(c["idx"])
                        owntxt = "".join(own)
                        sqc = SQ(ctx)
                        u = UN(old)
                        if old in ctx:
                            cls = "VERBATIM"
                        elif SQ(old).strip() in sqc:
                            cls = "UP TO BLANKS"
                        elif SQ(u).strip() in sqc:
                            cls = "ESCAPED COPY"
                        elif SQ(u).strip() in SQ(UN(owntxt)):
                            cls = "OWN TEXT"
                        elif all((ln.strip() in ctx) or (ln.strip() in owntxt) for ln in u.splitlines() if ln.strip()):
                            cls = "IN PIECES"
                        else:
                            cls = "NEITHER"
                        C[cls] += 1
                        C[cls + " WORKS"] += status_ok(c)
                    elif isinstance(old, str) and old.strip():
                        C["on an OWN FILE (left out)"] += 1
                    else:
                        C["no usable old_string (left out)"] += 1
                    ns = c["args"].get("new_string")
                    if isinstance(ns, str):
                        own.append(ns)
                elif fn == "write_file":
                    ct = c["args"].get("content")
                    if isinstance(ct, str):
                        own.append(ct)
                    raw = c["args"].get("filepath")
                    if isinstance(raw, str) and R.norm_file(raw):
                        written.add(R.norm_file(raw))

            # ---- D
            words_used = set()
            for c in calls:
                if c["fname"] != "run_command" or not R.is_search(R.cmd_of(c["args"])):
                    continue
                D["uses"] += 1
                pat, why = search_pattern(R.cmd_of(c["args"]))
                wd = search_word(pat) if pat is not None else None
                if wd is None:
                    D["no identifier"] += 1
                    if pat is None:
                        D["no identifier: " + why] += 1
                    continue
                if wd in words_used:
                    D["REUSE"] += 1
                else:
                    D["FIRST USES"] += 1
                    res = c["result"]
                    works = status_ok(c) and isinstance(res.get("stdout"), str) and bool(res["stdout"].strip())
                    cls = "IN CONTEXT" if cr.in_ctx(("w", wd), ident_re(wd), c["idx"]) else "NEITHER"
                    D[cls] += 1
                    D[cls + " WORKS"] += works
                words_used.add(wd)

            # ---- E
            if tid not in regions_of:
                regions_of[tid] = R.changed_regions(task["patch"], collections.Counter())
                cl = []
                for f, a, b in regions_of[tid]:
                    pn = place_name(tid, f, a)
                    if pn and named_in(stmt, pn):
                        cl.append("NAMED")
                    elif file_named(stmt, f):
                        cl.append("FILE NAMED")
                    else:
                        cl.append("UNNAMED")
                    if pn is None:
                        dg["regions with no PLACE NAME (counted once per task)"] += 1
                place_of[tid] = cl
            regs = regions_of[tid]
            for (f, a, b), cl in zip(regs, place_of[tid]):
                rr = ranges.get(f)
                Erows.append((cl, tid, bool(rr) and any(s <= b and a <= e for _, s, e in rr), f in ranges))
            if regs and name in R.WITH_RESULTS:
                res = R.run_result(dict(source=name, task=tid, path=p), public)
                Eruns.append((tid, len(regs), place_of[tid].count("NAMED"), bool(res and res[0])))

        # ---------------- print
        P("")
        P(f"### {name}: runs {len(paths)}")
        P(f"A. FILE PATHS: uses {A['uses']}; OWN FILE {A['OWN FILE']}; REUSE {A['REUSE']}; FIRST USES {A['FIRST USES']}")
        P("   " + "; ".join(f"{k} {fmt(A[k], A['FIRST USES'])} (WORKS {fmt(A[k + ' WORKS'], A[k])})"
                           for k in ("IN CONTEXT", "DOTTED NAME", "NEITHER")))
        P("   WHERE (IN CONTEXT): " + "; ".join(f"{k} {A['WHERE ' + k]}" for k in
                                                ("TASK STATEMENT", "REST OF THE PROMPT", "OWN SEARCH", "COMMAND OUTPUT",
                                                 "GRAPH TOOL", "READ", "OTHER TOOL")))
        nb = B["reads"]
        P(f"B. START LINES: reads past line 1 {nb}; EXACT {fmt(B['EXACT'], nb)}; NEXT ONE {fmt(B['NEXT ONE'], nb)}; "
          f"PAGING neither {fmt(B['PAGING neither'], nb)}; ADDRESSED neither {fmt(B['ADDRESSED neither'], nb)}; "
          f"the rest {fmt(B['rest'], nb)}" + (" (the rest = pooled OTHER NUMBER/SHELL VIEW/NO NUMBER)" if skill else ""))
        nc = sum(C[k] for k in ("VERBATIM", "UP TO BLANKS", "ESCAPED COPY", "OWN TEXT", "IN PIECES", "NEITHER"))
        P(f"C. EDIT TARGETS: edits {nc} (left out: on an OWN FILE {C['on an OWN FILE (left out)']}, "
          f"no usable old_string {C['no usable old_string (left out)']})")
        P("   " + "; ".join(f"{k} {fmt(C[k], nc)} (WORKS {fmt(C[k + ' WORKS'], C[k])})"
                           for k in ("VERBATIM", "UP TO BLANKS", "ESCAPED COPY", "OWN TEXT", "IN PIECES", "NEITHER")))
        why = "; ".join(f"{k[len('no identifier: '):]} {v}" for k, v in sorted(D.items()) if k.startswith("no identifier: "))
        P(f"D. SEARCH WORDS: uses {D['uses']}; no identifier {D['no identifier']}" + (f" (of which: {why})" if why else "")
          + f"; REUSE {D['REUSE']}; FIRST USES {D['FIRST USES']}")
        P("   " + "; ".join(f"{k} {fmt(D[k], D['FIRST USES'])} (WORKS {fmt(D[k + ' WORKS'], D[k])})"
                           for k in ("IN CONTEXT", "NEITHER")))
        P("E. PLACES THE TASK NAMES (run-regions)")
        for k in ("NAMED", "FILE NAMED", "UNNAMED"):
            rows = [x for x in Erows if x[0] == k]
            op = [x for x in rows if x[3]]
            P(f"   {k:<10} regions {len(rows):>5}; tasks {len({x[1] for x in rows}):>4}; SHOWN {fmt(sum(x[2] for x in rows), len(rows))}; "
              f"in an OPENED FILE {fmt(len(op), len(rows))}; SHOWN among those {fmt(sum(x[2] for x in op), len(op))}")
        if name in R.WITH_RESULTS:
            for glab, gsel in (("1 region", lambda n: n == 1), ("2 or 3 regions", lambda n: 2 <= n <= 3),
                               ("4 or more regions", lambda n: n >= 4)):
                parts = []
                for lab, f in (("all NAMED", lambda n, k: k == n), ("some not all NAMED", lambda n, k: 0 < k < n),
                               ("none NAMED", lambda n, k: k == 0)):
                    rs = [x for x in Eruns if gsel(x[1]) and f(x[1], x[2])]
                    parts.append(f"{lab}: tasks {len({x[0] for x in rs})}, resolved {fmt(sum(x[3] for x in rs), len(rs))}")
                P(f"   tasks with {glab:<18} " + "; ".join(parts))
    P("")
    P("Diagnostics: prompts in the store " + str(len(store)) + "; "
      + "; ".join(f"{k}: {v}" for k, v in sorted(dg.items())))
    print("\n".join(out))


if __name__ == "__main__":
    main()
