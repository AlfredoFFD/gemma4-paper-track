"""Independent re-derivation (EXPLORATORY): graph-tool calls in the public starter-agent runs, arms base and skill.

Written blind from a brief's definitions, without the project's own graph-call scripts or their output. Raw inputs only:
data/graphloc/out/<notebook>/e2e/results/<arm>/w*/traces/trace_<task>.json (three notebooks, arms base and skill).
The traces are read as JSON data; nothing from data/ is executed.

How each definition was decided:
- RUN: one trace file. TASK: the file name after 'trace_'. NOTEBOOK: the directory under data/graphloc/out.
- TOOL CALLS of a run: every entry of every step's 'tool_calls' list, in step order, numbered from 1 (INDEX). Every
  tool counts toward the index (read_file, run_command, get_status, list_skills, run_skill_script, ...). In these
  traces no step holds more than one tool call, so a step's 'observation' is the result of its single call (checked
  and counted below; if a step held several, the observation would be given to the last one and the others would
  count as having no result).
- GRAPH TOOL: a call whose function_name is get_code_neighbors, search_similar_code or get_code_subgraph, exactly.
  run_skill_script calls (the skill arm's graph-localize script) are NOT graph-tool calls under this definition;
  they are counted separately at the end so the reader can see how much that choice matters.
- ANSWER of a graph-tool call: the step's observation 'content' parsed as JSON. Looking at the real results first:
  every one is a JSON object with status 'ok' and a list ('results' for search_similar_code, 'neighbors' for
  get_code_neighbors) plus a 'count' equal to the list's length. So:
    ERROR     the content is missing or not a JSON object, or it has an 'error' key, or a 'status' other than 'ok',
              or it holds none of the item lists (results, neighbors, nodes, edges);
    NON-EMPTY otherwise, when at least one of those lists has an item;
    EMPTY     otherwise (the tool returned without an error and listed nothing).
  A disagreement between 'count' and the list length is counted as a diagnostic (the list decides).
- QUERY SHAPE of a search_similar_code call, from the 'query' ARGUMENT (not the echo in the result) with str.strip():
  SEVERAL WORDS if it contains any white space; else DOTTED NAME if it contains '.'; else ONE WORD.
- Intervals: 95% percentile bootstrap over tasks (2,000 resamples; a fresh random.Random(0) for each interval). A
  resample draws the arm's tasks with replacement and takes the ratio of the summed run counts (all runs of a drawn
  task go in together); the 2.5th and 97.5th percentiles use linear interpolation between order statistics.
- Median index: statistics.median (the mean of the two middle values when the count is even).

Usage: py -I -X utf8 analysis/rederive_public_graph_calls.py > analysis/results/public/rederive_graph_calls.txt
(prints its report with LF line ends; writes nothing itself; takes no arguments)
"""
import collections
import json
import random
import re
import statistics
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "graphloc" / "out"
ARMS = ("base", "skill")
GRAPH_TOOLS = ("get_code_neighbors", "search_similar_code", "get_code_subgraph")
ITEM_KEYS = ("results", "neighbors", "nodes", "edges")
KINDS = ("NON-EMPTY", "EMPTY", "ERROR")
SHAPES = ("SEVERAL WORDS", "DOTTED NAME", "ONE WORD")
N_BOOT = 2000
diag = collections.Counter()
examples = collections.defaultdict(list)


# ---------------------------------------------------------------- reading
def discover():
    runs = []
    for nbdir in sorted(p for p in OUT.iterdir() if p.is_dir()):
        for arm in ARMS:
            for p in sorted((nbdir / "e2e" / "results" / arm).glob("w*/traces/trace_*.json")):
                runs.append(dict(notebook=nbdir.name, arm=arm, task=p.stem[len("trace_"):], path=p))
    return runs


def tool_calls(path):
    """List of (function name, arguments dict, raw observation content or None)."""
    d = json.loads(path.read_text(encoding="utf-8"))
    calls = []
    for s in d.get("steps") or []:
        tcs = s.get("tool_calls") or []
        if not tcs:
            continue
        if len(tcs) > 1:
            diag["steps with several tool calls"] += 1
        obs = s.get("observation")
        content = obs.get("content") if isinstance(obs, dict) else obs
        for j, tc in enumerate(tcs):
            args = tc.get("arguments")
            if not isinstance(args, dict):
                diag["tool call whose arguments are not an object (taken as empty)"] += 1
                args = {}
            calls.append((tc.get("function_name"), args, content if j == len(tcs) - 1 else None))
    return calls


def classify(content):
    """NON-EMPTY / EMPTY / ERROR for a graph-tool answer, with a short reason for ERROR."""
    if content is None:
        return "ERROR", "no result"
    if isinstance(content, str):
        try:
            r = json.loads(content)
        except Exception:
            return "ERROR", "result not JSON"
    else:
        r = content
    if not isinstance(r, dict):
        return "ERROR", "result not a JSON object"
    if "error" in r:
        return "ERROR", "error key"
    if r.get("status", "ok") != "ok":
        return "ERROR", "status " + str(r.get("status"))
    lists = [r[k] for k in ITEM_KEYS if isinstance(r.get(k), list)]
    if not lists:
        return "ERROR", "no item list"
    n = sum(len(x) for x in lists)
    if isinstance(r.get("count"), int) and len(lists) == 1 and r["count"] != n:
        diag["count field differs from the list length (list used)"] += 1
    return ("NON-EMPTY" if n else "EMPTY"), None


def shape(q):
    q = q.strip()
    if re.search(r"\s", q):
        return "SEVERAL WORDS"
    if "." in q:
        return "DOTTED NAME"
    return "ONE WORD"


def short(x, n=230):
    s = x if isinstance(x, str) else json.dumps(x)
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + " ..."


# ---------------------------------------------------------------- stats
def pct(vals, q):
    vals = sorted(vals)
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def boot(per_task):
    """per_task: list of (numerator, denominator) summed over a task's runs."""
    rng = random.Random(0)
    T = len(per_task)
    vals = []
    for _ in range(N_BOOT):
        sn = sd = 0
        for _ in range(T):
            a, b = per_task[rng.randrange(T)]
            sn += a
            sd += b
        if sd:
            vals.append(sn / sd)
    return pct(vals, 0.025), pct(vals, 0.975)


def fmt(k, n):
    return f"{k}/{n} ({100.0 * k / n:.1f}%)" if n else f"{k}/0 (n/a)"


def fmt_ci(recs, pred, base=lambda r: True):
    by = collections.defaultdict(lambda: [0, 0])
    for r in recs:
        if base(r):
            by[r["task"]][1] += 1
            by[r["task"]][0] += bool(pred(r))
    k = sum(v[0] for v in by.values())
    n = sum(v[1] for v in by.values())
    lo, hi = boot([tuple(v) for v in by.values()])
    return f"{fmt(k, n)} [95% CI {100 * lo:.1f}, {100 * hi:.1f}]"


# ---------------------------------------------------------------- main
def main():
    runs = discover()
    seen = set()
    recs = []
    for r in runs:
        key = (r["notebook"], r["arm"], r["task"])
        if key in seen:
            diag["run seen twice (both kept)"] += 1
        seen.add(key)
        calls = tool_calls(r["path"])
        g = []  # graph-tool calls: dict(idx, tool, kind, shape)
        n_skill_script = 0
        for i, (fn, args, content) in enumerate(calls, start=1):
            if fn is None:
                diag["tool call without a function name"] += 1
            if fn == "run_skill_script":
                n_skill_script += 1
            if fn not in GRAPH_TOOLS:
                continue
            kind, why = classify(content)
            sh = None
            if fn == "search_similar_code":
                q = args.get("query")
                if not isinstance(q, str):
                    diag["search_similar_code query argument not a string (shape ONE WORD of its JSON)"] += 1
                    q = json.dumps(q)
                if not q.strip():
                    diag["search_similar_code with an empty query"] += 1
                sh = shape(q)
            g.append(dict(idx=i, tool=fn, kind=kind, shape=sh))
            if len(examples[(kind, fn)]) < 2:  # the first two of each (kind, tool), in run order
                examples[(kind, fn)].append((fn, f"{r['notebook'][-12:]}/{r['arm']}/{r['task']} call {i}",
                                             short(args, 120), short(content if content is not None else "<none>")
                                             + (f"   [reason: {why}]" if why else "")))
        recs.append(dict(r, n_calls=len(calls), g=g, n_skill_script=n_skill_script))

    P = print
    notebooks = sorted({r["notebook"] for r in recs})
    P("RE-DERIVATION (EXPLORATORY): graph-tool calls in the public starter-agent runs (blind recount)")
    P("graph tools: " + ", ".join(GRAPH_TOOLS) + f"; bootstrap: {N_BOOT} resamples over tasks, seed 0")
    P("notebooks: " + "; ".join(f"N{i + 1} = {nb}" for i, nb in enumerate(notebooks)))
    P("")

    for arm in ARMS:
        A = [r for r in recs if r["arm"] == arm]
        W = [r for r in A if r["g"]]
        tasks = {r["task"] for r in A}
        P("=" * 100)
        P(f"ARM {arm}")
        # 1
        P("1. RUNS AND RUNS WITH A GRAPH-TOOL CALL")
        P(f"   runs {len(A)}; tasks {len(tasks)}; tool calls {sum(r['n_calls'] for r in A)}")
        P(f"   runs with >=1 graph-tool call: {fmt_ci(A, lambda r: r['g'])}")
        for i, nb in enumerate(notebooks):
            nr = [r for r in A if r["notebook"] == nb]
            P(f"     N{i + 1}: {fmt(sum(bool(r['g']) for r in nr), len(nr))}")
        P(f"   tasks with a graph-tool call in some run: {fmt(len({r['task'] for r in W}), len(tasks))}")
        # 2
        P("2. WHEN THE FIRST GRAPH-TOOL CALL COMES")
        firsts = [r["g"][0]["idx"] for r in W]
        P(f"   runs whose FIRST tool call is a graph tool: {fmt(sum(1 for x in firsts if x == 1), len(A))}")
        P(f"   runs with a graph-tool call among their first 8 tool calls: {fmt(sum(1 for x in firsts if x <= 8), len(A))}")
        if firsts:
            q = statistics.quantiles(firsts, n=4, method="inclusive") if len(firsts) > 1 else [firsts[0]] * 3
            P(f"   median INDEX of the first graph-tool call: {statistics.median(firsts)} "
              f"(quartiles {q[0]} to {q[2]}; min {min(firsts)}, max {max(firsts)}; over {len(firsts)} runs)")
        else:
            P("   median INDEX of the first graph-tool call: n/a (no run has one)")
        # 3
        P("3. WHICH GRAPH TOOL THE FIRST GRAPH-TOOL CALL IS")
        fc = collections.Counter(r["g"][0]["tool"] for r in W)
        P("   " + "; ".join(f"{t} {fmt(fc[t], len(W))}" for t in GRAPH_TOOLS))
        # 4
        P("4. GRAPH-TOOL CALLS BY ANSWER")
        allg = [c for r in A for c in r["g"]]
        kc = collections.Counter(c["kind"] for c in allg)
        P(f"   all: {len(allg)}; " + "; ".join(f"{k} {fmt(kc[k], len(allg))}" for k in KINDS))
        for t in GRAPH_TOOLS:
            tg = [c for c in allg if c["tool"] == t]
            tk = collections.Counter(c["kind"] for c in tg)
            P(f"   {t}: {len(tg)}; " + "; ".join(f"{k} {fmt(tk[k], len(tg))}" for k in KINDS))
        P(f"   graph-tool calls per run that has one: median {statistics.median([len(r['g']) for r in W]) if W else 'n/a'}, "
          f"max {max([len(r['g']) for r in W]) if W else 'n/a'}")
        # 5
        P("5. RUNS WITH >=1 NON-EMPTY ANSWER")
        ne = lambda r: any(c["kind"] == "NON-EMPTY" for c in r["g"])
        P(f"   share of all runs: {fmt_ci(A, ne)}")
        P(f"   share of the runs with a graph-tool call: {fmt(sum(ne(r) for r in W), len(W))}")
        for t in GRAPH_TOOLS:
            P(f"     with a NON-EMPTY answer from {t}: "
              f"{fmt(sum(any(c['kind'] == 'NON-EMPTY' and c['tool'] == t for c in r['g']) for r in A), len(A))}")
        # 6
        P("6. search_similar_code CALLS BY QUERY SHAPE")
        sc = [c for c in allg if c["tool"] == "search_similar_code"]
        for s in SHAPES:
            ss = [c for c in sc if c["shape"] == s]
            P(f"   {s:<14} {fmt(len(ss), len(sc))}; NON-EMPTY among them {fmt(sum(c['kind'] == 'NON-EMPTY' for c in ss), len(ss))}")
        # side note on the definition of a graph tool
        S = [r for r in A if r["n_skill_script"]]
        P("   (outside the definition) runs with a run_skill_script call: "
          f"{fmt(len(S), len(A))}; run_skill_script calls {sum(r['n_skill_script'] for r in A)}; "
          f"runs with a graph-tool call OR a run_skill_script call: {fmt(sum(bool(r['g'] or r['n_skill_script']) for r in A), len(A))}")
        P("")

    P("=" * 100)
    P("EXAMPLES OF EACH KIND OF ANSWER FOUND (shortened)")
    for k in KINDS:
        # up to three per kind, taking the tools in turn
        pools = [examples[(k, t)] for t in GRAPH_TOOLS if examples.get((k, t))]
        ex = [p[j] for j in range(2) for p in pools if j < len(p)][:3]
        if not ex:
            P(f"  {k}: none found (an ERROR would be a missing or non-JSON result, an 'error' key, a status other "
              f"than 'ok', or no item list)")
            continue
        P(f"  {k}:")
        for fn, where, a, c in ex:
            P(f"    {fn} [{where}] args {a}")
            P(f"      -> {c}")
    P("")
    P("Diagnostics: " + ("; ".join(f"{k}: {v}" for k, v in sorted(diag.items())) or "none"))


if __name__ == "__main__":
    main()
