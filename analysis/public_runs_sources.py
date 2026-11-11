"""The places of a fix that a run never saw: which source would have pointed there, and how long a list? (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_sources.py [--seeds 20]

Nothing here was pre-registered and no model is run. For every changed region that a public run never saw, this
script asks which source of pointers would have held it, how many entries the agent would have had to sift, and in
how many runs a source holds everything the run missed. It also asks how stable "shown every changed region" is
within a task.

Sources and the rules CHANGED REGION, SHOWN LINES, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET, CALL GRAPH, SEEN
SITE and AS PRINTED: as in analysis/public_runs_missed_links.py and analysis/public_runs_coedit_sites.py. An
OPENED FILE is a file with a read_file result of status ok in the run. Further rules, one per source:
  OPENED FILE     the region lies in an OPENED FILE. List: the ENTITIES of the run's OPENED FILES that are not SHOWN
                  (an outline of the files it has open). Split by whether the region starts within lines 1 to 150,
                  and by whether some tool result of the run named a line of that file within 10 lines of the region
                  (the ADDRESS rule of analysis/public_runs_address.py applied to every result of the run).
  SAME DIRECTORY  the region lies in a file that is not an OPENED FILE, in the directory of one. List: the ENTITIES
                  of the files of those directories that are not OPENED FILES.
  ONE CALL        the TARGET is one edge of the CALL GRAPH from a SHOWN ENTITY. List: all such nodes, not SHOWN.
  TWO CALLS       the TARGET is within two edges. List: all such nodes.
  PRINTED         the TARGET is among the first 50 neighbors, in sorted order and over every edge, of a SEEN SITE.
                  List: those neighbors of all the run's SEEN SITES, not SHOWN.
  EMBEDDING k     the TARGET is among the k nodes nearest, by cosine in the competition's node embeddings
                  (data/embeddings), to a SEEN SITE. List: those nodes for all the run's SEEN SITES, not SHOWN.
  PRINTED OR EMBEDDING k   either of the two.
  SAME-FILE NULL  for EMBEDDING k: each of the k nodes replaced by a node drawn at random from the same file (a node
                  that resolves to no file: from the nodes with the same dotted name without its last component).
A source COVERS a region if the region meets its rule. Shares are of all MISSED REGIONS; a region with no TARGET, or
whose TARGET is a SHOWN ENTITY, can be covered by the first two sources only. ENTRIES PER COVERED REGION is the
summed length of the lists of the runs to which the source applies, divided by the regions it covers.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import argparse
import ast
import collections
import hashlib
import posixpath
import random
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_missed_links as L  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import DATA, MAX_NEIGHBORS, graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, classify, is_read, norm, pct  # noqa: E402
from public_runs_locality_null import block_of  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

KS = (5, 10, 20, 50)
_emb = {}
_defs = {}


def definitions(task_id, path):
    """(spans of every `async def`, spans of every def or class) in a file of the task's snapshot, decorators included."""
    key = (task_id, path)
    if key not in _defs:
        asyncs, every = [], []
        try:
            tree = ast.parse(N.file_text(task_id, path) or '')
        except SyntaxError:
            tree = None
        for node in (ast.walk(tree) if tree is not None else ()):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                span = (min([node.lineno] + [d.lineno for d in node.decorator_list]), node.end_lineno)
                every.append(span)
                if isinstance(node, ast.AsyncFunctionDef):
                    asyncs.append(span)
        _defs[key] = (asyncs, every)
    return _defs[key]


def embeddings(g):
    """(node ids, unit vectors) of a graph's embedding file."""
    if g['key'] not in _emb:
        z = np.load(DATA / 'embeddings' / f"{g['key']}.npz")   # plain float arrays: no pickle is needed or allowed
        ids = list(z.files)
        mat = np.stack([np.asarray(z[k], dtype=np.float32) for k in ids])
        mat /= np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-12)
        _emb[g['key']] = (ids, {n: i for i, n in enumerate(ids)}, mat, {})
    return _emb[g['key']]


def nearest(g, site, k):
    """The k nodes nearest to a node, the node itself left out (empty if it has no embedding)."""
    ids, index, mat, cache = embeddings(g)
    if site not in index:
        return []
    if site not in cache:
        sims = mat @ mat[index[site]]
        sims[index[site]] = -2.0
        top = np.argpartition(-sims, max(KS))[:max(KS)]
        cache[site] = [ids[i] for i in top[np.argsort(-sims[top], kind='stable')]]
    return cache[site][:k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    names = ['OPENED FILE', 'SAME DIRECTORY', 'OPENED FILE or SAME DIRECTORY', 'ONE CALL', 'TWO CALLS', 'PRINTED'] + \
            [f'EMBEDDING {k}' for k in KS] + [f'PRINTED OR EMBEDDING {k}' for k in (10, 50)]
    rows, runs, every = [], [], []
    async_nodes = {}
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        trace = calls_of(load(r['path']))
        reads = collections.defaultdict(list)
        for call, _text, parsed in trace:
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        every.append({'task': task_id, 'arm': r['arm'], 'every': int(not missed)})
        if not missed:
            continue
        named = collections.defaultdict(set)
        for prev in trace:
            for f in {m[0] for m in missed}:
                named[f] |= classify(f, prev)[2]
        g = graph_for(tasks[task_id])
        async_nodes[g['key']] = (sum(1 for x in g['text1'].values() if x.startswith('async def')), len(g['ids']))
        ent = L.entities(task_id, g)
        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in M.nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)

        def target(f, a, b):
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            return min(cover)[2] if cover else None

        sites = {target(f, a, b) for f, regs in gr.items() for a, b in regs if overlap(a, b, reads.get(f, []))} - {None}
        opened = set(reads)
        dirs = {posixpath.dirname(f) for f in opened}
        cg = L.call_graph(task_id, g)[0]
        one, two = M.reach(cg['nbr'], shown)
        full = M.simple_neighbors(g)
        printed = set()
        for s in sites:
            printed |= set(sorted(full.get(s, set()))[:MAX_NEIGHBORS])
        printed -= shown
        emb = {k: set().union(*[nearest(g, s, k) for s in sites]) - shown if sites else set() for k in KS}
        blk = block_of(ent, 'file')
        pool = collections.defaultdict(list)
        for n in g['ids']:
            pool[blk(n)].append(n)
        emb_null = {k: [] for k in KS}
        for sd in seeds:
            rng = random.Random(int(hashlib.sha256(f"{g['key']}:{r['path']}:{sd}".encode()).hexdigest(), 16))
            drawn = {s: [rng.choice(pool[blk(n)]) for n in nearest(g, s, max(KS))] for s in sorted(sites)}
            for k in KS:
                emb_null[k].append(set().union(*[set(v[:k]) for v in drawn.values()]) - shown if sites else set())
        lists = {'OPENED FILE': sum(1 for n, (f, _a, _b) in ent.items() if f in opened and n not in shown),
                 'SAME DIRECTORY': sum(1 for n, (f, _a, _b) in ent.items() if f not in opened and posixpath.dirname(f) in dirs),
                 'ONE CALL': len(one), 'TWO CALLS': len(one) + len(two), 'PRINTED': len(printed)}
        lists['OPENED FILE or SAME DIRECTORY'] = lists['OPENED FILE'] + lists['SAME DIRECTORY']
        for k in KS:
            lists[f'EMBEDDING {k}'] = len(emb[k])
        for k in (10, 50):
            lists[f'PRINTED OR EMBEDDING {k}'] = len(printed | emb[k])
        run_rows = []
        for f, a, b in missed:
            t = target(f, a, b)
            open_t = t is not None and t not in shown
            row = {'task': task_id, 'site_run': bool(sites), 'has_target': open_t,
                   'OPENED FILE': f in opened, 'SAME DIRECTORY': f not in opened and posixpath.dirname(f) in dirs,
                   'top': f in opened and a <= 150, 'deep': f in opened and a > 150,
                   'near': f in opened and any(a - 10 <= x <= b + 10 for x in named.get(f, ())),
                   'ONE CALL': open_t and t in one, 'TWO CALLS': open_t and (t in one or t in two),
                   'PRINTED': open_t and t in printed}
            row['OPENED FILE or SAME DIRECTORY'] = row['OPENED FILE'] or row['SAME DIRECTORY']
            asyncs, defs = definitions(task_id, f)
            row['no_target'] = t is None
            row['async'] = bool(overlap(a, b, asyncs))
            row['in_def'] = bool(overlap(a, b, defs))
            for k in KS:
                row[f'EMBEDDING {k}'] = open_t and t in emb[k]
                row[f'null {k}'] = statistics.mean(int(open_t and t in x) for x in emb_null[k])
            for k in (10, 50):
                row[f'PRINTED OR EMBEDDING {k}'] = row['PRINTED'] or row[f'EMBEDDING {k}']
            rows.append(row)
            run_rows.append(row)
        runs.append({'task': task_id, 'site_run': bool(sites), 'lists': lists,
                     'all': {nm: all(x[nm] for x in run_rows) for nm in names}})

    def by_task(sel):
        out = collections.defaultdict(list)
        for x in sel:
            out[x['task']].append(x)
        return out

    def ci(sel, key):
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, key))
        return f'{pct(sum(x[key] for x in sel), len(sel))} [{100 * lo:.1f}, {100 * hi:.1f}]'

    n = len(rows)
    print('PUBLIC RUNS: the places of a fix a run never saw, by the source that would have held them (EXPLORATORY)')
    print()
    print('0. Base')
    print(f'   runs with a MISSED REGION {len(runs)} in {len(by_task(runs))} tasks, of which with a SEEN SITE {sum(x["site_run"] for x in runs)}; '
          f'MISSED REGIONS {n}, of which with a TARGET that is not SHOWN {sum(x["has_target"] for x in rows)}, '
          f'in runs with a SEEN SITE {sum(x["site_run"] for x in rows)}')
    print()
    print('1. Sources: MISSED REGIONS covered (of all), list length, runs whose MISSED REGIONS are all covered')
    for nm in names:
        cov = sum(x[nm] for x in rows)
        applies = [x for x in runs if x['site_run']] if ('PRINTED' in nm or 'EMBEDDING' in nm) else runs
        ln = sorted(x['lists'][nm] for x in applies)
        total = sum(ln)
        print(f'   {nm}: covers {ci(rows, nm)}; list length median {statistics.median(ln):.0f} (quartiles {ln[len(ln) // 4]} to {ln[(3 * len(ln)) // 4]}); '
              f'ENTRIES PER COVERED REGION {total / cov if cov else float("nan"):.1f}; all covered in {pct(sum(x["all"][nm] for x in runs), len(runs))} runs')
    print()
    print('2. The regions in an OPENED FILE')
    of = [x for x in rows if x['OPENED FILE']]
    print(f'   regions {len(of)}: start within lines 1 to 150 {pct(sum(x["top"] for x in of), len(of))}, deeper {pct(sum(x["deep"] for x in of), len(of))}; '
          f'a tool result of the run had named a line within 10 lines of the region {ci(of, "near")}')
    print(f'   of the deeper ones: a line within 10 lines had been named {pct(sum(x["near"] for x in of if x["deep"]), sum(x["deep"] for x in of))}; '
          f'of those within lines 1 to 150: {pct(sum(x["near"] for x in of if x["top"]), sum(x["top"] for x in of))}')
    print()
    print('3. Sources that start from a SEEN SITE, in the runs that have one')
    sr = [x for x in rows if x['site_run']]
    print(f'   regions {len(sr)} in {len(by_task(sr))} tasks')
    for nm in ['PRINTED'] + [f'EMBEDDING {k}' for k in KS] + [f'PRINTED OR EMBEDDING {k}' for k in (10, 50)]:
        print(f'   {nm}: covers {ci(sr, nm)}')
    for k in KS:
        key, nk = f'EMBEDDING {k}', f'null {k}'
        dlo, dhi = M.boot(by_task(sr), lambda xs, key=key, nk=nk: M.share(xs, key) - M.share(xs, nk))
        print(f'   EMBEDDING {k} against its SAME-FILE NULL: {100 * M.share(sr, key):.1f}% against {100 * M.share(sr, nk):.1f}%; '
              f'difference {100 * (M.share(sr, key) - M.share(sr, nk)):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')
    print()
    print('4. Is "shown every CHANGED REGION" a property of the task? (all runs with a CHANGED REGION)')
    bt = by_task(every)
    full6 = {t: [x['every'] for x in v] for t, v in bt.items() if len(v) == 6}
    agree = sum(1 for v in full6.values() if len(set(v)) == 1)
    k = 6
    grand = statistics.mean(x for v in full6.values() for x in v)
    msb = k * sum((statistics.mean(v) - grand) ** 2 for v in full6.values()) / (len(full6) - 1)
    msw = sum((x - statistics.mean(v)) ** 2 for v in full6.values() for x in v) / (len(full6) * (k - 1))
    icc = (msb - msw) / (msb + (k - 1) * msw)
    print(f'   runs {len(every)} in {len(bt)} tasks; tasks with six runs {len(full6)}; shown every region in {pct(sum(x["every"] for x in every), len(every))} runs')
    print(f'   tasks whose six runs agree: {pct(agree, len(full6))} (all six shown every region {sum(1 for v in full6.values() if all(v))}, '
          f'none of the six {sum(1 for v in full6.values() if not any(v))}); share of the variance between tasks (one-way intraclass correlation): {icc:.2f}')
    for arm in ('base', 'skill'):
        v3 = [[x['every'] for x in v if x['arm'] == arm] for v in bt.values()]
        v3 = [v for v in v3 if len(v) == 3]
        print(f'   {arm} arm alone: tasks whose three runs agree {pct(sum(1 for v in v3 if len(set(v)) == 1), len(v3))}')
    print()
    print('5. MISSED REGIONS that no graph node covers (no TARGET)')
    nt = [x for x in rows if x['no_target']]
    print(f'   graphs of these tasks: {len(async_nodes)}; nodes whose source starts with `async def`: '
          f'{sum(a for a, _n in async_nodes.values())} of {sum(n for _a, n in async_nodes.values())}')
    print(f'   no TARGET: {pct(len(nt), n)}; of those, inside an `async def` {pct(sum(x["async"] for x in nt), len(nt))}; inside another function or class '
          f'{pct(sum(x["in_def"] and not x["async"] for x in nt), len(nt))}; outside any definition {pct(sum(not x["in_def"] for x in nt), len(nt))}')
    wt = [x for x in rows if not x['no_target']]
    print(f'   with a TARGET, yet inside an `async def` (the TARGET is an ENTITY around or beside it): {pct(sum(x["async"] for x in wt), len(wt))}')
    print(f'   all MISSED REGIONS inside an `async def`: {pct(sum(x["async"] for x in rows), n)}')
    for nm in ('OPENED FILE', 'SAME DIRECTORY', 'OPENED FILE or SAME DIRECTORY'):
        print(f'   the regions with no TARGET covered by {nm}: {pct(sum(x[nm] for x in nt), len(nt))}; '
              f'the regions with a TARGET: {pct(sum(x[nm] for x in wt), len(wt))}')
    for nm in ('ONE CALL', 'EMBEDDING 5', 'EMBEDDING 50'):
        print(f'   {nm}, of the regions with a TARGET only: {pct(sum(x[nm] for x in wt), len(wt))}')


if __name__ == '__main__':
    main()
