"""Independent re-derivation (EXPLORATORY): how runs move to new code, and whether the code graph's call edges match.

Written blind from a brief's definitions, without the project's own script or its output. It imports the two earlier
independent scripts (analysis/rederive_read_starts.py: trace parsing, classed READS, NAMED LINE sources, SEARCH test;
analysis/rederive_arguments.py: CONTEXT, part A FIRST USE / WHERE, part D search words) and analysis/nodes.py
(resolve, span, scopes, file_text) on the competition's graphs in data/graphs.

Usage: py -I -X utf8 analysis/rederive_graph_moves.py      (prints its report; writes nothing itself)
"""
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402
import rederive_arguments as A  # noqa: E402
import nodes  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
dg = collections.Counter()
fmt = R.fmt
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
RUN = re.compile(r"[A-Za-z0-9_]+")


# ---------------------------------------------------------------- graph entities
class Graph:
    def __init__(self, tid, task):
        self.ok = False
        key = f"{task['repo'].split('/')[-1]}_{task['base_commit']}"
        f = ROOT / "data" / "graphs" / f"{key}.json"
        if not f.exists():
            dg["tasks with no graph file"] += 1
            return
        g = json.loads(f.read_text(encoding="utf-8"))
        self.ok = True
        self.ent = {}  # id -> (file, start, end, snapshot path)
        for n in g["nodes"]:
            nid = n.get("id")
            if nid in self.ent or not isinstance(nid, str):
                continue
            r = nodes.resolve(tid, nid)
            if r is None:
                continue
            sp = nodes.span(tid, nid)
            if not sp or sp.get("start") is None or sp.get("end") is None or not sp.get("qualname"):
                continue
            self.ent[nid] = (R.norm_file(r[0]), sp["start"], sp["end"], r[0])
        self.by_file = collections.defaultdict(list)
        for nid, (f_, s, e, _) in self.ent.items():
            self.by_file[f_].append((s, e, nid))
        self.adj = collections.defaultdict(set)
        dropped = cont = 0
        for e in g["edges"]:
            u, v = e.get("source"), e.get("target")
            if u not in self.ent or v not in self.ent:
                dropped += 1
                continue
            if u == v:
                continue
            fu, su, eu, _ = self.ent[u]
            fv, sv, ev, _ = self.ent[v]
            if fu == fv and (su, eu) != (sv, ev) and ((su <= sv and ev <= eu) or (sv <= su and eu <= ev)):
                cont += 1
                continue
            self.adj[u].add(v)
            self.adj[v].add(u)
        dg["graph edges dropped (an end is not an ENTITY), summed over tasks"] += dropped
        dg["graph edges dropped as CONTAINMENT, summed over tasks"] += cont
        dg["ENTITIES, summed over tasks"] += len(self.ent)
        dg["CALL EDGE pairs, summed over tasks"] += sum(len(x) for x in self.adj.values()) // 2
        self._lines_ids = {}

    def idents_of(self, nid, tid):
        if nid not in self._lines_ids:
            f_, s, e, sp = self.ent[nid]
            txt = nodes.file_text(tid, sp)
            if txt is None:
                dg["ENTITY whose snapshot text is missing"] += 1
                self._lines_ids[nid] = set()
            else:
                self._lines_ids[nid] = set(IDENT.findall("\n".join(txt.splitlines()[s - 1:e])))
        return self._lines_ids[nid]


def last(nid):
    return nid.split(".")[-1]


# ---------------------------------------------------------------- part A first uses (as in rederive_arguments)
def first_uses(cr, stmt):
    """path -> (class, WHERE or None) at the run's FIRST USE of the path."""
    out = {}
    used, written = set(), set()
    calls = cr.calls
    for c in calls:
        fn = c["fname"]
        if fn in ("read_file", "edit_file"):
            raw = c["args"].get("filepath")
            if isinstance(raw, str) and R.norm_file(raw):
                fp = R.norm_file(raw)
                if fp not in written and fp not in used:
                    if cr.in_ctx(("p", fp), A.path_re(fp), c["idx"]):
                        rx = A.path_re(fp)
                        if rx.search(stmt):
                            w = "TASK STATEMENT"
                        elif any(rx.search(x) for x in cr.prompts):
                            w = "REST OF THE PROMPT"
                        else:
                            w = A.call_kind(calls[cr.first_at(("p", fp), rx) - 1])
                        out[fp] = ("IN CONTEXT", w)
                    elif fp.endswith(".py") and any(cr.in_ctx(("d", m), A.dotted_re(m), c["idx"])
                                                    for m in A.dotted_names(fp)):
                        out[fp] = ("DOTTED NAME", None)
                    else:
                        out[fp] = ("NEITHER", None)
                used.add(fp)
        if fn == "write_file":
            raw = c["args"].get("filepath")
            if isinstance(raw, str) and R.norm_file(raw):
                written.add(R.norm_file(raw))
    return out


# ---------------------------------------------------------------- main
def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    store = A.build_prompt_store()
    graphs = {}
    out = []
    P = out.append
    P("RE-DERIVATION (EXPLORATORY): searches, and moves to new code against the graph's call edges")
    P("=" * 100)
    for name, paths in R.discover().items():
        S = collections.Counter()
        def_runs = 0
        M = []  # move records
        for p in paths:
            tid = Path(p).stem[len("trace_"):]
            if tid not in tasks:
                tid = tid.replace("__", "/")
            task = tasks[tid]
            stmt = task.get("problem_statement") or ""
            if tid not in graphs:
                graphs[tid] = Graph(tid, task)
            G = graphs[tid]
            cr = A.CRun(p, task, store, name)
            run = cr.run
            reads, _ = R.analyse_run(run)
            classed = {r["idx"]: r for r in reads if r.get("cls") and r.get("rstart") is not None}
            fu = first_uses(cr, stmt)

            shown, frontier = set(), set()
            screen, other_ids = set(), set()
            files_read = set()
            defs_shown = set()
            run_has_def_search = False
            for c in run.calls:
                k = c["idx"]
                # ---- searches (state = everything before this call)
                if c["fname"] == "run_command" and R.is_search(R.cmd_of(c["args"])):
                    S["SEARCHES"] += 1
                    pat, _why = A.search_pattern(R.cmd_of(c["args"]))
                    wd = A.search_word(pat) if pat is not None else None
                    if wd is None:
                        S["without an identifier"] += 1
                    else:
                        S["with a word"] += 1
                        in_task = bool(A.ident_re(wd).search(stmt))
                        if in_task:
                            cls = "TASK"
                        elif wd in defs_shown:
                            cls = "DEFINITION SHOWN"
                        elif wd in screen:
                            cls = "CODE SHOWN"
                        elif wd in other_ids:
                            cls = "OTHER RESULT"
                        else:
                            cls = "NEW"
                        S[cls] += 1
                        S["word in the TASK STATEMENT"] += in_task
                        if wd in defs_shown:
                            res = c["result"]
                            hit = A.status_ok(c) and isinstance(res.get("stdout"), str) and bool(res["stdout"].strip())
                            S["word is a DEFINITION SHOWN"] += 1
                            S["word is a DEFINITION SHOWN, also in the task"] += in_task
                            S["word is a DEFINITION SHOWN, HITS"] += hit
                            run_has_def_search = True
                # ---- moves
                r = classed.get(k)
                if r is not None:
                    f_, rs, re_ = r["file"], r["rstart"], r["rend"]
                    new = set()
                    if G.ok:
                        new = {nid for s, e, nid in G.by_file.get(f_, []) if s <= re_ and rs <= e} - shown
                    if new and shown:
                        along = any(G.adj[n] & shown for n in new)
                        notshown = len(G.ent) - len(shown)
                        fr = frontier - shown
                        chance = len(fr) / notshown if notshown else None
                        if chance is None:
                            dg["MOVE with every ENTITY already shown (left out of the mean)"] += 1
                        tonew = f_ not in files_read
                        if r["cls"] == "PAGING":
                            how = "READING ON"
                        elif (r["cls"] == "ADDRESSED" and "OWN SEARCH" in r["near_src"]) or \
                                (tonew and fu.get(f_) == ("IN CONTEXT", "OWN SEARCH")):
                            how = "OWN SEARCH"
                        elif tonew and fu.get(f_, (None, None))[1] in ("TASK STATEMENT", "REST OF THE PROMPT"):
                            how = "TOP OF A LISTED FILE"
                        else:
                            how = "OTHER"
                        shown_last = {last(x) for x in shown}
                        nbsc = any(last(n) in screen for n in new)
                        nase = any(G.idents_of(n, tid) & shown_last for n in new)
                        M.append(dict(along=along, chance=chance, tonew=tonew, how=how, nbsc=nbsc, nase=nase))
                    # update the state with this read
                    shown |= new
                    for n in new:
                        frontier |= G.adj[n]
                    res = c["result"]
                    if isinstance(res, dict) and isinstance(res.get("content"), str):
                        screen |= set(IDENT.findall(res["content"]))
                    files_read.add(f_)
                    for q, (_s, _e, dl) in nodes.scopes(tid, f_).items():
                        if rs <= dl <= re_:
                            defs_shown.add(q.split(".")[-1])
                if c["fname"] != "read_file" and c["text"]:
                    other_ids |= set(RUN.findall(c["text"]))
            def_runs += run_has_def_search

        # ---------------- print
        P("")
        P(f"### {name}: runs {len(paths)}")
        nw = S["with a word"]
        P(f"1. SEARCHES {S['SEARCHES']}; without an identifier {S['without an identifier']}; with a word {nw}")
        P("   " + "; ".join(f"{k} {fmt(S[k], nw)}" for k in ("TASK", "DEFINITION SHOWN", "CODE SHOWN", "OTHER RESULT", "NEW")))
        nd = S["word is a DEFINITION SHOWN"]
        P(f"   word in the TASK STATEMENT {fmt(S['word in the TASK STATEMENT'], nw)}; word is the simple name of a "
          f"DEFINITION SHOWN {fmt(nd, nw)} (runs with one: {def_runs}/{len(paths)}; also in the task "
          f"{fmt(S['word is a DEFINITION SHOWN, also in the task'], nd)}; HIT {fmt(S['word is a DEFINITION SHOWN, HITS'], nd)})")

        def block(label, ms):
            ch = [m["chance"] for m in ms if m["chance"] is not None]
            mean = f"{sum(ch) / len(ch):.3f}" if ch else "n/a"
            P(f"   {label}: MOVES {len(ms)}; ALONG A CALL EDGE {fmt(sum(m['along'] for m in ms), len(ms))}; "
              f"mean BY CHANCE {mean}")

        P("2. MOVES")
        block("all", M)
        block("TO A NEW FILE", [m for m in M if m["tonew"]])
        al = [m for m in M if m["along"]]
        for lab, ms in (("all MOVES", M), ("MOVES ALONG A CALL EDGE", al)):
            P(f"   HOW, {lab}: " + "; ".join(f"{k} {fmt(sum(m['how'] == k for m in ms), len(ms))}"
                                            for k in ("READING ON", "OWN SEARCH", "TOP OF A LISTED FILE", "OTHER")))
        P(f"   all MOVES: NAMED BY SHOWN CODE {fmt(sum(m['nbsc'] for m in M), len(M))}; NAMES A SHOWN ENTITY "
          f"{fmt(sum(m['nase'] for m in M), len(M))}; either {fmt(sum(m['nbsc'] or m['nase'] for m in M), len(M))}")
        P(f"   MOVES ALONG A CALL EDGE: NAMED BY SHOWN CODE {fmt(sum(m['nbsc'] for m in al), len(al))}; "
          f"NAMES A SHOWN ENTITY {fmt(sum(m['nase'] for m in al), len(al))}")
    P("")
    P("Diagnostics: " + "; ".join(f"{k}: {v}" for k, v in sorted(dg.items())))
    adg = {k: v for k, v in A.dg.items() if "NOT recovered" in k or "missing" in k}
    P("Prompt recovery problems: " + (str(adg) if adg else "none"))
    print("\n".join(out))


if __name__ == "__main__":
    main()
