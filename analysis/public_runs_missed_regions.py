"""Fix sites the agent never saw: does the code graph link them to code it did see? (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_missed_regions.py [--seeds 20]

Nothing here was pre-registered and no model is run. analysis/public_runs_time_to_fix.py finds that in the public
end-to-end runs behind GraphLoc the agent is shown a line of the fix in most runs but every place the fix touches in
fewer. This script takes the places it missed and asks whether the competition's code graph connects them to code the
agent had been shown, and whether a degree-preserving rewiring of the same graph would connect them as often.

Sources (local copies, not redistributed; see analysis/results/public/README.md):
  data/graphloc/out/<notebook>/e2e/results/<arm>/w*/traces/trace_<task>.json   both arms, three notebooks
  data/tasks.jsonl (gold patches), data/graphs/<repo>_<commit>.json (the competition's code graphs),
  data/snapshots (through analysis/nodes.py: a node's file and line span, by `ast`)

Rules:
  CHANGED REGION, GOLD FILE, the runs kept: as in analysis/public_runs_time_to_fix.py.
  SHOWN LINES     the lines returned by the run's read_file calls with status ok (start_line..end_line). Shell views
                  are not counted.
  MISSED REGION   a CHANGED REGION of the task that no SHOWN LINES of the run overlap.
  ENTITY          a node of the task's code graph whose file and line span analysis/nodes.py resolves (functions,
                  methods, classes; a node that is a whole module has no span and is left out).
  SHOWN ENTITY    an ENTITY whose span overlaps SHOWN LINES of its file.
  TARGET          of a MISSED REGION: the ENTITY with the shortest span among those whose span overlaps the region.
                  A region with no such ENTITY is NOT ADDRESSABLE by the graph.
  DISTANCE        0 if the TARGET is itself a SHOWN ENTITY (the agent saw other lines of it); 1 if it is not, and it
                  is a graph neighbor of a SHOWN ENTITY; 2 if it is a neighbor of a neighbor; FARTHER otherwise.
                  Edges are undirected, as the harness's get_code_neighbors lists them; self-loops are dropped.
  FRONTIER        the ENTITIES and other nodes at DISTANCE 1 from the run's SHOWN ENTITIES: what a neighbor list of
                  everything the agent had seen would hold.
  REWIRED         the same graph after seeded double-edge swaps (10 per edge, a swap skipped if it would make a
                  self-loop or a duplicate edge: the procedure of analysis/fork_states.rewired_neighbors, with the
                  seed taken from the graph's key and a seed number). Every node keeps its degree.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import argparse
import collections
import hashlib
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from fork_states import graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm, pct  # noqa: E402
from public_runs_time_to_fix import gold_regions, graphloc_records, overlap  # noqa: E402

SWAPS_PER_EDGE = 10


def simple_neighbors(g):
    nbr = collections.defaultdict(set)
    for u, vs in g['nbr'].items():
        for v in vs:
            if u != v:
                nbr[u].add(v)
                nbr[v].add(u)
    return nbr


_rewired = {}


def rewired(g, seed):
    """Neighbor sets after seeded double-edge swaps; the loop of fork_states.rewired_neighbors with its own seed."""
    key = (g['key'], seed)
    if key in _rewired:
        return _rewired[key]
    base = simple_neighbors(g)
    edges = sorted({tuple(sorted((u, v))) for u, vs in base.items() for v in vs})
    rng = random.Random(int(hashlib.sha256(f"{g['key']}:{seed}".encode()).hexdigest(), 16))
    edge_set = set(edges)
    for _ in range(SWAPS_PER_EDGE * len(edges)):
        i, j = rng.randrange(len(edges)), rng.randrange(len(edges))
        if i == j:
            continue
        a, b = edges[i]
        c, d = edges[j]
        if rng.random() < 0.5:
            c, d = d, c
        if a == d or c == b:
            continue
        e1, e2 = tuple(sorted((a, d))), tuple(sorted((c, b)))
        if e1 in edge_set or e2 in edge_set:
            continue
        edge_set.discard(edges[i])
        edge_set.discard(edges[j])
        edge_set.add(e1)
        edge_set.add(e2)
        edges[i], edges[j] = e1, e2
    nbr = collections.defaultdict(set)
    for u, v in edges:
        nbr[u].add(v)
        nbr[v].add(u)
    _rewired[key] = nbr
    return nbr


_by_file = {}
_spans = {}


def nodes_of_file(task_id, g, path):
    """[(start, end, node id)] of the graph's ENTITIES in one file of the task's snapshot."""
    if task_id not in _by_file:
        table = collections.defaultdict(list)
        for nid in g['ids']:
            r = N.resolve(task_id, nid)
            if r:
                table[norm(r[0])].append(nid)
        _by_file[task_id] = table
    key = (task_id, path)
    if key not in _spans:
        out = []
        for nid in _by_file[task_id].get(path, ()):
            sp = N.span(task_id, nid)
            if sp and sp.get('end') is not None and sp.get('qualname'):
                out.append((sp['start'], sp['end'], nid))
        _spans[key] = out
    return _spans[key]


def reach(nbr, shown):
    """(nodes at distance 1, nodes at distance 2) from the shown set."""
    one = set()
    for s in shown:
        one |= nbr.get(s, set())
    one -= shown
    two = set()
    for m in one:
        two |= nbr.get(m, set())
    two -= shown
    two -= one
    return one, two


def boot(by_task, fn, n=2000, seed=0):
    tasks = sorted(by_task)
    rng = random.Random(seed)
    vals = sorted(fn([x for t in (rng.choice(tasks) for _ in tasks) for x in by_task[t]]) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


def share(rows, key):
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    rec = graphloc_records()
    regions = []   # one per missed region of a run
    runs = []      # one per run with a missed region
    n_runs = collections.Counter()
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        n_runs[r['arm']] += 1
        reads = collections.defaultdict(list)
        for call, _text, parsed in calls_of(load(r['path'])):
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        n_regions = sum(len(v) for v in gr.values())
        if not missed:
            continue
        g = graph_for(tasks[task_id])
        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)
        true = simple_neighbors(g)
        one, two = reach(true, shown)
        rew = [reach(rewired(g, sd), shown) for sd in seeds]
        repo = tasks[task_id]['repo']
        resolved = rec.get((r['run'], r['arm'], task_id), (False, ''))[0]
        run_rows = []
        for f, a, b in missed:
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            row = {'task': task_id, 'arm': r['arm'], 'repo': repo, 'some': len(missed) < n_regions, 'addressable': bool(cover),
                   'region': (task_id, f, a, b), 'target': None, 'opened': f in reads,
                   'd0': False, 'd1': False, 'd2': False, 'r1': 0.0, 'r2': 0.0, 'r1_seeds': [0] * len(seeds), 'r2_seeds': [0] * len(seeds)}
            if cover:
                target = min(cover)[2]
                row['target'] = target
                row['d0'] = target in shown
                if not row['d0']:
                    row['d1'] = target in one
                    row['d2'] = row['d1'] or target in two
                    row['r1_seeds'] = [int(target in o) for o, _t in rew]
                    row['r2_seeds'] = [int(target in o or target in t) for o, t in rew]
                    row['r1'] = statistics.mean(row['r1_seeds'])
                    row['r2'] = statistics.mean(row['r2_seeds'])
            regions.append(row)
            run_rows.append(row)
        runs.append({'task': task_id, 'arm': r['arm'], 'repo': repo, 'some': len(missed) < n_regions, 'resolved': resolved,
                     'shown': len(shown), 'frontier': len(one), 'frontier_tests': sum(1 for x in one if x.split('.')[0] in ('tests', 'test')),
                     'frontier2': len(one) + len(two), 'frontier_rew': statistics.mean(len(o) for o, _t in rew),
                     'any1': any(x['d1'] for x in run_rows), 'any1_rew': statistics.mean(
                         int(any(x['r1_seeds'][k] for x in run_rows)) for k in range(len(seeds)))})

    print('PUBLIC RUNS: fix sites the agent never saw, and whether the code graph links them to code it saw (EXPLORATORY)')
    print(f'rewired graphs: {len(seeds)} seeds per graph')
    print()
    print('0. Runs and regions')
    for arm in ('base', 'skill'):
        sel = [x for x in runs if x['arm'] == arm]
        print(f'   {arm}: runs {n_runs[arm]}; with a MISSED REGION {len(sel)}, of which shown some CHANGED REGION {sum(x["some"] for x in sel)} '
              f'and shown none {sum(not x["some"] for x in sel)}; MISSED REGIONS {sum(1 for x in regions if x["arm"] == arm)}')
    print(f'   both: runs with a MISSED REGION {len(runs)} in {len({x["task"] for x in runs})} tasks; MISSED REGIONS {len(regions)}')
    print()
    print('1. Can the graph address a MISSED REGION at all?')
    addr = [x for x in regions if x['addressable']]
    seen = [x for x in addr if x['d0']]
    open_ = [x for x in addr if not x['d0']]
    print(f'   some ENTITY covers it: {pct(len(addr), len(regions))}; NOT ADDRESSABLE {len(regions) - len(addr)}')
    print(f'   of the addressable ones, the TARGET is itself a SHOWN ENTITY (DISTANCE 0): {pct(len(seen), len(addr))}')
    print(f'   left for the graph (addressable, TARGET not shown): {len(open_)} regions in {len({x["task"] for x in open_})} tasks; '
          f'distinct regions {len({x["region"] for x in open_})}, distinct TARGETS {len({(x["task"], x["target"]) for x in open_})}; '
          f'TARGET in a file the run had opened {pct(sum(x["opened"] for x in open_), len(open_))}')
    print()
    print('2. Reach from shown code, true graph against rewired graphs (regions left for the graph)')

    def line(label, rows):
        if not rows:
            return
        by = collections.defaultdict(list)
        for x in rows:
            by[x['task']].append(x)
        out = [f'   {label}: regions {len(rows)}, tasks {len(by)}']
        for key, rkey, name in (('d1', 'r1', 'one hop'), ('d2', 'r2', 'two hops')):
            t = share(rows, key)
            rw = share(rows, rkey)
            seedvals = [sum(x[rkey + '_seeds'][k] for x in rows) / len(rows) for k in range(len(seeds))]
            lo, hi = boot(by, lambda xs, key=key: share(xs, key))
            dlo, dhi = boot(by, lambda xs, key=key, rkey=rkey: share(xs, key) - share(xs, rkey))
            out.append(f'      within {name}: true {sum(x[key] for x in rows)} ({100 * t:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]); '
                       f'rewired {100 * rw:.1f}% (seeds {100 * min(seedvals):.1f} to {100 * max(seedvals):.1f}); '
                       f'true minus rewired {100 * (t - rw):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')
        print('\n'.join(out))

    line('all', open_)
    for arm in ('base', 'skill'):
        line(f'{arm} arm', [x for x in open_ if x['arm'] == arm])
    line('TARGET in a file the run had opened', [x for x in open_ if x['opened']])
    line('TARGET in a file the run had not opened', [x for x in open_ if not x['opened']])
    line('runs shown some CHANGED REGION', [x for x in open_ if x['some']])
    line('runs shown none', [x for x in open_ if not x['some']])
    for repo in sorted({x['repo'] for x in open_}):
        line(repo, [x for x in open_ if x['repo'] == repo])
    per_task = collections.defaultdict(list)
    for x in open_:
        per_task[x['task']].append(x)
    print(f'   mean of per-task shares ({len(per_task)} tasks): within one hop true {100 * statistics.mean(share(v, "d1") for v in per_task.values()):.1f}%, '
          f'rewired {100 * statistics.mean(share(v, "r1") for v in per_task.values()):.1f}%; within two hops true '
          f'{100 * statistics.mean(share(v, "d2") for v in per_task.values()):.1f}%, rewired {100 * statistics.mean(share(v, "r2") for v in per_task.values()):.1f}%')
    print(f'   over ALL {len(regions)} MISSED REGIONS: within one hop {pct(sum(x["d1"] for x in regions), len(regions))}; '
          f'within two hops {pct(sum(x["d2"] for x in regions), len(regions))}; '
          f'rewired {100 * share(regions, "r1"):.1f}% and {100 * share(regions, "r2"):.1f}%')
    print(f'   runs in which some MISSED REGION is within one hop: true {pct(sum(x["any1"] for x in runs), len(runs))}; '
          f'rewired {100 * statistics.mean(x["any1_rew"] for x in runs):.1f}%')
    print()
    print('3. What a neighbor list of everything the agent had seen would hold (runs with a MISSED REGION)')
    for label, sel in (('all', runs), ('base arm', [x for x in runs if x['arm'] == 'base']), ('skill arm', [x for x in runs if x['arm'] == 'skill']),
                       ('runs with a MISSED REGION within one hop', [x for x in runs if x['any1']])):
        if not sel:
            continue
        fr = sorted(x['frontier'] for x in sel)
        print(f'   {label}: runs {len(sel)}; SHOWN ENTITIES median {statistics.median(x["shown"] for x in sel):.0f}; FRONTIER median {statistics.median(fr):.0f} '
              f'(quartiles {fr[len(fr) // 4]} to {fr[(3 * len(fr)) // 4]}), of which tests {statistics.median(x["frontier_tests"] for x in sel):.0f}; '
              f'rewired FRONTIER median {statistics.median(x["frontier_rew"] for x in sel):.0f}; within two hops median {statistics.median(x["frontier2"] for x in sel):.0f}')
    hit = [x for x in open_ if x['d1']]
    print(f'   precision: MISSED REGIONS within one hop {len(hit)}; summed FRONTIER of the runs that hold them '
          f'{sum(x["frontier"] for x in runs if x["any1"])} nodes in {sum(1 for x in runs if x["any1"])} runs')


if __name__ == '__main__':
    main()
