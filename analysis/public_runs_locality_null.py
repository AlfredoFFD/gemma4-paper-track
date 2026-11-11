"""Is it the graph, or is it locality? Nulls that keep the files (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_locality_null.py [--seeds 20]

Nothing here was pre-registered and no model is run. analysis/public_runs_missed_links.py and
analysis/public_runs_coedit_sites.py compare the competition's code graph with a rewiring that keeps every node's
degree. That rewiring also destroys locality: the places of a fix cluster in the files a run read, and so do call
edges. This script repeats the two counts against nulls that keep locality, and adds precision beside recall.

Sources and the rules CHANGED REGION, SHOWN LINES, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET, CONTAINMENT, CALL
GRAPH, SEEN SITE and AS PRINTED: as in those two scripts. Further rules:
  BLOCK            of a node: the file its ENTITY lies in, or the directory of that file. A node that resolves to
                   no file gets its dotted name without the last component (file level) or without the last two
                   (directory level).
  DEGREE NULL      the rewiring of analysis/public_runs_missed_regions.py: ends exchanged between any two edges.
  SAME-FILE NULL   seeded exchanges of edge ends inside a file: pick an edge and one of its ends, pick another edge
                   with an end in the same file, exchange those two ends (10 attempts per edge; skipped if it would
                   make a self-loop or a duplicate edge). Every node keeps its degree and every edge keeps the two
                   files it joins. An edge whose file has no other edge end to exchange with stays where it is.
  SAME-DIRECTORY NULL   the same with directories in place of files.
  MOVED            the share of a graph's edges that are not in its rewired copy.
  FRONTIER         the nodes one edge of the CALL GRAPH from a run's SHOWN ENTITIES, the SHOWN ENTITIES left out.
  PRINTED ENTRIES  the union, over a run's SEEN SITES, of the first 50 neighbors of each in sorted order (every
                   edge of the graph, as the harness's get_code_neighbors prints them), the SHOWN ENTITIES left out.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import argparse
import collections
import hashlib
import posixpath
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import public_runs_missed_links as L  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import MAX_NEIGHBORS, graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm, pct  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

SWAPS_PER_EDGE = 10
NULLS = ('degree', 'directory', 'file')
_null = {}


def block_of(ent, level):
    def f(n):
        if n in ent:
            return ent[n][0] if level == 'file' else posixpath.dirname(ent[n][0])
        parts = n.split('.')
        k = 1 if level == 'file' else 2
        return 'node:' + '.'.join(parts[:-k])
    return f


def local_null(g, seed, level, ent):
    """(neighbor sets, MOVED) after exchanges of edge ends inside a BLOCK. g: {'key': ..., 'nbr': {node: set}}."""
    key = (g['key'], seed, level)
    if key in _null:
        return _null[key]
    base = M.simple_neighbors(g)
    edges = [list(e) for e in sorted({tuple(sorted((u, v))) for u, vs in base.items() for v in vs})]
    original = {tuple(e) for e in edges}
    eset = set(original)
    blk = block_of(ent, level)
    ends = collections.defaultdict(list)          # block -> [(edge index, side)]; an edge end never leaves its block
    for i, (u, v) in enumerate(edges):
        ends[blk(u)].append((i, 0))
        ends[blk(v)].append((i, 1))
    rng = random.Random(int(hashlib.sha256(f"{g['key']}:{level}:{seed}".encode()).hexdigest(), 16))
    for _ in range(SWAPS_PER_EDGE * len(edges)):
        i, si = rng.randrange(len(edges)), rng.randrange(2)
        a, b = edges[i][1 - si], edges[i][si]
        j, sj = rng.choice(ends[blk(b)])
        if j == i:
            continue
        c, d = edges[j][1 - sj], edges[j][sj]
        if b == d or a == d or c == b:
            continue
        e1, e2 = tuple(sorted((a, d))), tuple(sorted((c, b)))
        if e1 in eset or e2 in eset:
            continue
        eset.discard(tuple(sorted((a, b))))
        eset.discard(tuple(sorted((c, d))))
        eset.add(e1)
        eset.add(e2)
        edges[i][si], edges[j][sj] = d, b
    nbr = collections.defaultdict(set)
    for u, v in edges:
        nbr[u].add(v)
        nbr[v].add(u)
    _null[key] = (nbr, 1 - len(eset & original) / len(original) if original else 0.0)
    return _null[key]


def null_graph(g, seed, kind, ent):
    if kind == 'degree':
        nbr = M.rewired(g, seed)
        true = {tuple(sorted((u, v))) for u, vs in M.simple_neighbors(g).items() for v in vs}
        new = {tuple(sorted((u, v))) for u, vs in nbr.items() for v in vs}
        return nbr, (1 - len(true & new) / len(true) if true else 0.0)
    return local_null(g, seed, kind, ent)


def printed(nbr, sites, shown):
    out = set()
    for s in sites:
        out |= set(sorted(nbr.get(s, set()))[:MAX_NEIGHBORS])
    return out - shown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    rows, per_task = [], collections.defaultdict(lambda: collections.Counter())
    moved = {(w, k): [] for w in ('call', 'full') for k in NULLS}
    prec = {(w, k): [0.0, 0.0] for w in ('call', 'full') for k in ('true',) + NULLS}    # [hits, entries]
    seen_graph = set()
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        reads = collections.defaultdict(list)
        for call, _text, parsed in calls_of(load(r['path'])):
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        if not missed:
            continue
        per_task[task_id]['n'] += len(missed)
        g = graph_for(tasks[task_id])
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
        cg = L.call_graph(task_id, g)[0]
        full = {'key': g['key'] + ':every edge', 'nbr': M.simple_neighbors(g)}
        call_null = {k: [null_graph(cg, sd, k, ent) for sd in seeds] for k in NULLS}
        # the DEGREE NULL of the whole graph is the one of public_runs_coedit_sites.py (same seeds), so the two agree
        full_null = {k: [null_graph(g if k == 'degree' else full, sd, k, ent) for sd in seeds] for k in NULLS}
        if g['key'] not in seen_graph:
            seen_graph.add(g['key'])
            for k in NULLS:
                moved[('call', k)].append(statistics.mean(m for _n, m in call_null[k]))
                moved[('full', k)].append(statistics.mean(m for _n, m in full_null[k]))
        front = M.reach(cg['nbr'], shown)[0]
        front_null = {k: [M.reach(n, shown)[0] for n, _m in call_null[k]] for k in NULLS}
        pr = printed(full['nbr'], sites, shown)
        pr_null = {k: [printed(n, sites, shown) for n, _m in full_null[k]] for k in NULLS}
        open_targets = set()
        for f, a, b in missed:
            t = target(f, a, b)
            if t is None or t in shown:
                continue
            open_targets.add(t)
            row = {'task': task_id, 'opened': f in reads, 'site_run': bool(sites), 'call': t in front, 'printed': t in pr}
            for k in NULLS:
                row[f'call_{k}_seeds'] = [int(t in x) for x in front_null[k]]
                row[f'printed_{k}_seeds'] = [int(t in x) for x in pr_null[k]]
                row[f'call_{k}'] = statistics.mean(row[f'call_{k}_seeds'])
                row[f'printed_{k}'] = statistics.mean(row[f'printed_{k}_seeds'])
            rows.append(row)
            per_task[task_id]['call'] += row['call']
            for k in NULLS:
                per_task[task_id][f'call_{k}'] += row[f'call_{k}']
        prec[('call', 'true')][0] += len(open_targets & front)
        prec[('call', 'true')][1] += len(front)
        for k in NULLS:
            prec[('call', k)][0] += statistics.mean(len(open_targets & x) for x in front_null[k])
            prec[('call', k)][1] += statistics.mean(len(x) for x in front_null[k])
        if sites:
            prec[('full', 'true')][0] += len(open_targets & pr)
            prec[('full', 'true')][1] += len(pr)
            for k in NULLS:
                prec[('full', k)][0] += statistics.mean(len(open_targets & x) for x in pr_null[k])
                prec[('full', k)][1] += statistics.mean(len(x) for x in pr_null[k])

    names = {'degree': 'DEGREE NULL', 'directory': 'SAME-DIRECTORY NULL', 'file': 'SAME-FILE NULL'}

    def by_task(sel):
        out = collections.defaultdict(list)
        for x in sel:
            out[x['task']].append(x)
        return out

    def line(label, sel, key):
        by = by_task(sel)
        t = M.share(sel, key)
        lo, hi = M.boot(by, lambda xs: M.share(xs, key))
        print(f'   {label}: regions {len(sel)}, tasks {len(by)}; true graph {sum(x[key] for x in sel)} ({100 * t:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}])')
        for k in NULLS:
            nk = f'{key}_{k}'
            dlo, dhi = M.boot(by, lambda xs, nk=nk: M.share(xs, key) - M.share(xs, nk))
            sv = [sum(x[nk + '_seeds'][i] for x in sel) / len(sel) for i in range(len(seeds))]
            print(f'      {names[k]} {100 * M.share(sel, nk):.1f}% (seeds {100 * min(sv):.1f} to {100 * max(sv):.1f}); '
                  f'true minus null {100 * (t - M.share(sel, nk)):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')

    print('PUBLIC RUNS: the graph against nulls that keep locality (EXPLORATORY)')
    print(f'rewired graphs: {len(seeds)} seeds per graph and null')
    print()
    print('0. How much each null changes a graph (MOVED, mean over the graphs of these tasks)')
    for w, label in (('call', 'CALL GRAPH'), ('full', 'every edge')):
        print(f'   {label}: ' + '; '.join(f'{names[k]} {100 * statistics.mean(moved[(w, k)]):.1f}% of edges' for k in NULLS))
    print()
    print('1. MISSED REGIONS one edge of the CALL GRAPH from shown code')
    n_all = sum(c['n'] for c in per_task.values())
    trows = [dict({'task': t, 'n': c['n'], 'call': c['call']}, **{f'call_{k}': c[f'call_{k}'] for k in NULLS})
             for t, c in per_task.items()]
    hit = sum(x['call'] for x in trows)
    lo, hi = M.boot(by_task(trows), lambda xs: sum(x['call'] for x in xs) / sum(x['n'] for x in xs))
    print(f'   over ALL {n_all} MISSED REGIONS in {len(trows)} tasks (the ones with no TARGET or a shown TARGET count as not reached): '
          f'true graph {hit} ({100 * hit / n_all:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}])')
    for k in NULLS:
        nk = f'call_{k}'
        val = sum(x[nk] for x in trows) / n_all
        dlo, dhi = M.boot(by_task(trows), lambda xs, nk=nk: (sum(x['call'] for x in xs) - sum(x[nk] for x in xs)) / sum(x['n'] for x in xs))
        sv = [sum(x[nk + '_seeds'][i] for x in rows) / n_all for i in range(len(seeds))]
        print(f'      {names[k]} {100 * val:.1f}% (seeds {100 * min(sv):.1f} to {100 * max(sv):.1f}); '
              f'true minus null {100 * (hit / n_all - val):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')
    line('the regions left for the graph (inside an ENTITY, TARGET not shown)', rows, 'call')
    line('of those, TARGET in a file the run had opened', [x for x in rows if x['opened']], 'call')
    line('of those, TARGET in a file the run had not opened', [x for x in rows if not x['opened']], 'call')
    print()
    print('2. From a SEEN SITE, AS PRINTED (every edge; the first 50 neighbors of each SEEN SITE in sorted order)')
    line('regions left for the graph in runs with a SEEN SITE', [x for x in rows if x['site_run']], 'printed')
    print()
    print('3. Precision: of the nodes a list would hold, how many are TARGETS of the run\'s regions left for the graph')
    for w, label in (('call', 'FRONTIER (one edge of the CALL GRAPH from everything shown)'), ('full', 'PRINTED ENTRIES (lists of the SEEN SITES)')):
        print(f'   {label}:')
        for k in ('true',) + NULLS:
            h, n = prec[(w, k)]
            print(f'      {"true graph" if k == "true" else names[k]}: {h:.1f} TARGETS among {n:.1f} nodes ({100 * h / n:.2f} per 100 nodes)')


if __name__ == '__main__':
    main()
