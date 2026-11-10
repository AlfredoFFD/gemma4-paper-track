"""From a fix site the agent found to the ones it missed: what the graph's neighbor lists would have held (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_coedit_sites.py [--seeds 20]

Nothing here was pre-registered and no model is run. analysis/public_runs_missed_regions.py asks whether the places
of a fix that a run never saw are linked, in the competition's code graph, to anything the run had been shown. This
script asks the narrower question an agent could act on with the shipped tool: the run has been shown one place the
fix changes; would `get_code_neighbors` on that place list a place it missed? It also scores one short list built
from those neighbor lists, and repeats everything on degree-preserving rewirings of the graph.

Sources and the rules CHANGED REGION, SHOWN LINES, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET and REWIRED: as in
analysis/public_runs_missed_regions.py. Further rules:
  SEEN SITE     the TARGET of a CHANGED REGION that SHOWN LINES of the run overlap (the entity of a place of the fix
                that the run was shown).
  OPEN REGION   a MISSED REGION whose TARGET exists and is not a SHOWN ENTITY, in a run with at least one SEEN SITE.
  LISTED        the TARGET of an OPEN REGION is a graph neighbor of a SEEN SITE of its run.
  AS PRINTED    LISTED within the first 50 neighbors in sorted order, the cap and order of the harness's
                get_code_neighbors (analysis/fork_states.harness_neighbors).
  SHORT LIST    the neighbors of the run's SEEN SITES that are not SHOWN ENTITIES, ordered by the number of SEEN SITES
                they neighbor (most first), entities outside test code before test code, then by name; its first k.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import argparse
import collections
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fork_states import MAX_NEIGHBORS, graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm, pct  # noqa: E402
from public_runs_missed_regions import boot, nodes_of_file, rewired, share, simple_neighbors  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

KS = (5, 10)


def is_test(nid):
    return nid.split('.')[0] in ('tests', 'test') or '.tests.' in nid or nid.rsplit('.', 1)[-1].startswith('test_')


def lists(nbr, sites, shown):
    """(all neighbors of the sites, the neighbors as printed, the short list in order)."""
    every, printed = set(), set()
    count = collections.Counter()
    for s in sites:
        ns = nbr.get(s, set())
        every |= ns
        printed |= set(sorted(ns)[:MAX_NEIGHBORS])
        count.update(ns)
    cand = [n for n in every if n not in shown]
    cand.sort(key=lambda n: (-count[n], is_test(n), n))
    return every, printed, cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    rows, runs = [], []
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
        g = graph_for(tasks[task_id])

        def target(f, a, b):
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            return min(cover)[2] if cover else None

        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)
        sites, open_regions = set(), []
        for f, regs in gr.items():
            for a, b in regs:
                t = target(f, a, b)
                if overlap(a, b, reads.get(f, [])):
                    if t:
                        sites.add(t)
                elif t and t not in shown:
                    open_regions.append((f, t))
        if not sites or not open_regions:
            continue
        true = lists(simple_neighbors(g), sites, shown)
        rew = [lists(rewired(g, sd), sites, shown) for sd in seeds]
        for f, t in open_regions:
            row = {'task': task_id, 'arm': r['arm'], 'opened': f in reads,
                   'listed': t in true[0], 'printed': t in true[1],
                   'r_listed': statistics.mean(int(t in x[0]) for x in rew), 'r_printed': statistics.mean(int(t in x[1]) for x in rew),
                   'r_listed_seeds': [int(t in x[0]) for x in rew], 'r_printed_seeds': [int(t in x[1]) for x in rew]}
            for k in KS:
                row[f'top{k}'] = t in true[2][:k]
                row[f'r_top{k}'] = statistics.mean(int(t in x[2][:k]) for x in rew)
                row[f'r_top{k}_seeds'] = [int(t in x[2][:k]) for x in rew]
            rows.append(row)
        runs.append({'task': task_id, 'arm': r['arm'], 'sites': len(sites), 'entries': len(true[1]),
                     'entries_new': len([n for n in true[1] if n not in shown]), 'tests': sum(1 for n in true[1] if is_test(n)),
                     'short': len(true[2]), 'any': any(x['listed'] for x in rows[-len(open_regions):]),
                     'any10': any(x['top10'] for x in rows[-len(open_regions):]),
                     'r_any10': statistics.mean(int(any(x['r_top10_seeds'][i] for x in rows[-len(open_regions):])) for i in range(len(seeds)))})

    print('PUBLIC RUNS: from a fix site the run had seen to the ones it missed (EXPLORATORY)')
    print(f'rewired graphs: {len(seeds)} seeds per graph')
    print()
    print('0. Runs and regions')
    print(f'   runs with a SEEN SITE and an OPEN REGION: {len(runs)} (base {sum(x["arm"] == "base" for x in runs)}, skill {sum(x["arm"] == "skill" for x in runs)}) '
          f'in {len({x["task"] for x in runs})} tasks; OPEN REGIONS {len(rows)}')
    print()
    print('1. Would a neighbor list of a SEEN SITE have held the missed place?')

    def line(label, sel):
        if not sel:
            return
        by = collections.defaultdict(list)
        for x in sel:
            by[x['task']].append(x)
        print(f'   {label}: regions {len(sel)}, tasks {len(by)}')
        for key, name in (('listed', 'LISTED'), ('printed', 'AS PRINTED'), ('top10', 'in a SHORT LIST of 10'), ('top5', 'in a SHORT LIST of 5')):
            rkey = 'r_' + key
            t, rw = share(sel, key), share(sel, rkey)
            seedvals = [sum(x[rkey + '_seeds'][i] for x in sel) / len(sel) for i in range(len(seeds))]
            lo, hi = boot(by, lambda xs, key=key: share(xs, key))
            dlo, dhi = boot(by, lambda xs, key=key, rkey=rkey: share(xs, key) - share(xs, rkey))
            print(f'      {name}: true {sum(x[key] for x in sel)} ({100 * t:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]); rewired {100 * rw:.1f}% '
                  f'(seeds {100 * min(seedvals):.1f} to {100 * max(seedvals):.1f}); true minus rewired {100 * (t - rw):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')

    line('all', rows)
    line('base arm', [x for x in rows if x['arm'] == 'base'])
    line('skill arm', [x for x in rows if x['arm'] == 'skill'])
    line('the missed place is in a file the run had opened', [x for x in rows if x['opened']])
    line('the missed place is in a file the run had not opened', [x for x in rows if not x['opened']])
    print(f'   runs in which a SHORT LIST of 10 holds a missed place: true {pct(sum(x["any10"] for x in runs), len(runs))}; '
          f'rewired {100 * statistics.mean(x["r_any10"] for x in runs):.1f}%; runs in which some missed place is LISTED: {pct(sum(x["any"] for x in runs), len(runs))}')
    print()
    print('2. What the lists hold')
    en = sorted(x['entries'] for x in runs)
    sh = sorted(x['short'] for x in runs)
    print(f'   SEEN SITES per run: median {statistics.median(x["sites"] for x in runs):.0f}; entries printed for them together: median {statistics.median(en):.0f} '
          f'(quartiles {en[len(en) // 4]} to {en[(3 * len(en)) // 4]}), of which not yet shown to the run {statistics.median(x["entries_new"] for x in runs):.0f} '
          f'and in test code {statistics.median(x["tests"] for x in runs):.0f}; candidates for the SHORT LIST: median {statistics.median(sh):.0f}')


if __name__ == '__main__':
    main()
