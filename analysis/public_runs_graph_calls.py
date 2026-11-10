"""Graph-tool calls in the public September runs of the starter agent: did it ask, and was it answered? (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_graph_calls.py

Nothing here was pre-registered and no model is run. The end-to-end notebooks of the GraphLoc writeup ran the
starter agent on the same tasks with and without a graph skill (three notebooks, arms `base` and `skill`, Sep 25 to
27, 2026, before the harness wheels of Oct 12). This script counts how often the agent called one of the harness's
three graph tools in those runs, when, and how often the tool returned anything.

Source (local copy, not redistributed; see analysis/results/public/README.md):
  data/graphloc/out/<notebook>/e2e/results/<arm>/w*/traces/trace_<task>.json

Rules:
  GRAPH TOOL        get_code_neighbors, search_similar_code or get_code_subgraph.
  CALL INDEX        the position of a tool call in the run, from 1, counting every tool call.
  NON-EMPTY ANSWER  the call's result has status ok and returns at least one entity: `count` above 0, or a
                    non-empty `results`, `neighbors` or `nodes` list.
  EMPTY ANSWER      status ok and no entity. Any other result is an ERROR.
  QUERY SHAPE       of a search_similar_code call: SEVERAL WORDS if the query holds whitespace, DOTTED NAME if it
                    holds a dot and no whitespace, ONE WORD otherwise.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analyze_forks.boot_ci).
"""
import collections
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, pct  # noqa: E402

GRAPH_TOOLS = ('get_code_neighbors', 'search_similar_code', 'get_code_subgraph')
WITHIN = 8  # the length of the fresh episodes these runs are set beside


def answer(parsed):
    if not isinstance(parsed, dict) or parsed.get('status') != 'ok':
        return 'ERROR'
    n = parsed.get('count')
    if isinstance(n, int) and n > 0:
        return 'NON-EMPTY'
    if any(parsed.get(k) for k in ('results', 'neighbors', 'nodes')):
        return 'NON-EMPTY'
    return 'EMPTY'


def shape(query):
    q = str(query or '').strip()
    if any(c.isspace() for c in q):
        return 'SEVERAL WORDS'
    return 'DOTTED NAME' if '.' in q else 'ONE WORD'


def ci(by):
    t = boot_ci(by)
    return f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def main():
    print('PUBLIC RUNS OF SEPTEMBER: graph-tool calls of the starter agent (EXPLORATORY)')
    print()
    for arm, title in (('base', 'starter agent'), ('skill', 'the same agent with a graph skill')):
        runs = []
        by_tool = collections.defaultdict(collections.Counter)
        shapes = collections.defaultdict(collections.Counter)
        first_tool = collections.Counter()
        per_notebook = collections.defaultdict(lambda: [0, 0])
        for r in iter_runs(arm=arm):
            calls = calls_of(load(r['path']))
            idx = []
            got = False
            for i, (call, _text, parsed) in enumerate(calls, 1):
                name = call.get('function_name')
                if name not in GRAPH_TOOLS:
                    continue
                a = answer(parsed)
                by_tool[name][a] += 1
                got = got or a == 'NON-EMPTY'
                if not idx:
                    first_tool[name] += 1
                idx.append(i)
                if name == 'search_similar_code':
                    args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
                    shapes[shape(args.get('query'))][a] += 1
            runs.append({'task': r['task'], 'first': idx[0] if idx else None, 'n': len(idx), 'answered': got})
            per_notebook[r['run']][0] += 1
            per_notebook[r['run']][1] += bool(idx)
        n = len(runs)
        asked = [x for x in runs if x['first'] is not None]

        def share(pred):
            by = collections.defaultdict(list)
            for x in runs:
                by[x['task']].append(int(pred(x)))
            return ci(by)

        print(f'{arm} arm ({title}): runs {n}, tasks {len({x["task"] for x in runs})}')
        print(f'   runs with a GRAPH TOOL call: {pct(len(asked), n)}; by task {share(lambda x: x["first"] is not None)}')
        print(f'      as the first call of the run: {pct(sum(x["first"] == 1 for x in asked), n)}; within the first {WITHIN} calls: '
              f'{pct(sum(x["first"] <= WITHIN for x in asked), n)}; median CALL INDEX of the first one: {statistics.median(x["first"] for x in asked):.0f}')
        print('      per notebook: ' + ', '.join(f'{v[1]} of {v[0]}' for _k, v in sorted(per_notebook.items())))
        print(f'      the first GRAPH TOOL call of a run is: ' + ', '.join(f'{t} {c}' for t, c in first_tool.most_common()))
        print(f'   runs with at least one NON-EMPTY ANSWER: {pct(sum(x["answered"] for x in runs), n)}; by task {share(lambda x: x["answered"])}; '
              f'of the runs that asked {pct(sum(x["answered"] for x in asked), len(asked))}')
        total = sum(sum(c.values()) for c in by_tool.values())
        print(f'   GRAPH TOOL calls: {total}')
        for tool in GRAPH_TOOLS:
            c = by_tool[tool]
            t = sum(c.values())
            print(f'      {tool:<20} {t:>4}   NON-EMPTY {c["NON-EMPTY"]:>3}, EMPTY {c["EMPTY"]:>3}, ERROR {c["ERROR"]:>3}')
        print('   search_similar_code calls by QUERY SHAPE: ' + '; '.join(
            f'{s} {sum(c.values())} (NON-EMPTY {c["NON-EMPTY"]})' for s, c in sorted(shapes.items(), key=lambda kv: -sum(kv[1].values()))))
        print()


if __name__ == '__main__':
    main()
