"""Experiment 22, the registered analysis: the second seed of experiment 18 (seed 3), arms N, ON, OF and OA.

Usage:
  py -I -X utf8 analysis/analyze_22.py [--no-write]
  py -I -X utf8 analysis/analyze_22.py --standin        (the stored runs of 18 stand in for those of 22, OF taken from
                                                          ON; prints only, writes nothing)

Inputs: the runs of 22 (analysis/results/22/{N,ON,OF,OA}/seed3; one launch, seed 3; on the 40 tasks of
analysis/oracle_18/tasks_18.txt) are the rules. The stored runs of 18 (analysis/results/18/{N,ON,OA}/seed2) are read
for a pooled description only. Per-run outcomes are those of analysis/analyze_18.py (its functions are imported and
not changed: score, rule, load; and through it analyze_14), plus the share of a task's changed regions shown by reads.
Rules: paired by task on the tasks where both runs entered, 95% bootstrap by task (2,000 resamples, seed 0), a verdict
only with at least 34 such tasks ("more" / "fewer" / "no detectable difference"), exact McNemar p beside
(analyze_18.rule):
  L1  resolved, OA against N
  L2  resolved, ON against N
  L3  final patch overlaps a changed region, OA against ON
  L4  final patch overlaps a changed region, ON against N
  L5  final patch overlaps a changed region, OF against ON; and OA against OF
  L6  resolved, OF against N; and OA against OF
  L7  shown every changed region, ON against N; and OF against ON
If only one shard has run, fewer than 34 tasks enter and every rule prints its numbers and "no verdict (too few tasks)".
No rule: the counts of section 3 of analyze_18 for the four arms; by number of changed regions (1; 2 or 3; 4 to 9; 10
or more) resolved, shown every region and patch overlap per arm; the mean share of a task's changed regions shown per
arm; POOLED over seeds 2 (18) and 3 (22) for N, ON and OA: resolved, shown every region, patch overlap, each as a share
of task-runs with a bootstrap by task (a task's two runs resampled together), and the differences OA-N, ON-N, OA-ON
(paired by task and seed, bootstrap by task).
Output: analysis/results/22/analyze_22.txt (exactly the text --no-write prints) and analysis/results/22/runs_22.csv.
"""
import argparse
import collections
import csv
import io
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_14 as A  # noqa: E402
import analyze_18 as B  # noqa: E402
from public_runs_address import norm  # noqa: E402
from public_runs_time_to_fix import INF, gold_regions  # noqa: E402

ROOT_22 = HERE / 'results' / '22'
ARMS = ('N', 'ON', 'OF', 'OA')        # experiment 22, seed 3: the rules
POOL = ('N', 'ON', 'OA')              # pooled with experiment 18
OTHER = tuple(f'{c}18' for c in POOL)  # experiment 18, seed 2: description only
SEED_22, SEED_18 = 3, 2
BUCKETS = ('1', '2-3', '4-9', '10 or more')


def size_bucket(n):
    return '1' if n == 1 else '2-3' if n <= 3 else '4-9' if n <= 9 else '10 or more'


def shown_regions(calls, g):
    """The task's changed regions shown by a read (a read_file answer of status ok overlapping it)."""
    seen = set()
    for call, _text, parsed in calls:
        if A.is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
            f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
            s, e = parsed.get('start_line'), parsed.get('end_line')
            if f in g and isinstance(s, int) and isinstance(e, int):
                seen.update((f, i) for i, (a, b) in enumerate(g[f]) if not (e < a or s > b))
    return seen


def collect(standin):
    r18, n18 = B.load(B.ROOT_18, POOL)
    runs = {(t, f'{c}18'): v for (t, c, s), v in r18.items() if s == SEED_18}
    notes = [f'18 (seed {SEED_18}, pooled description only): {n}' for n in n18]
    if standin:
        for (t, c), v in list(runs.items()):
            runs[(t, c[:-2])] = v
            if c == 'ON18':
                runs[(t, 'OF')] = v
        notes.append('STAND-IN: N, ON and OA are the stored runs of 18 (seed 2), OF is the ON run')
    else:
        r22, n22 = B.load(ROOT_22, ARMS)
        runs.update({(t, c): v for (t, c, s), v in r22.items() if s == SEED_22})
        notes += [f'22 (seed {SEED_22}): {n}' for n in n22]
        other = sorted({s for (_t, _c, s) in r22} - {SEED_22})
        if other:
            notes.append(f'22: runs with another seed {other} are ignored')
    return runs, notes


def score(runs, tasks):
    saved = B.ALL
    B.ALL = ARMS + OTHER  # analyze_18.score keeps the arms of its ALL
    try:
        rows = B.score(runs, tasks)
    finally:
        B.ALL = saved
    gold = gold_regions()
    for (task, arm), x in rows.items():
        trace = runs[(task, arm)][0]
        g = gold.get(task, {})
        total = sum(len(v) for v in g.values())
        x['regions'] = total
        x['share'] = len(shown_regions(A.calls_of(trace) if trace is not None else [], g)) / total if total else 0.0
    return rows


def describe(rows, tasks):
    """Section 3 of analyze_18, for the four arms of 22."""
    for c in ARMS:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows and rows[(t, c)]['entered']]
        if not sel:
            print(f'   {c}: no entered runs')
            continue
        rc = collections.Counter()
        for x in sel:
            rc.update(x['reads'])
        print(f'   {c}: runs {len(sel)}; shown a changed line {A.pct(sum(x["t"] < INF for x in sel), len(sel))}; '
              f'every region shown {A.pct(sum(x["every"] for x in sel), len(sel))}; patch touches every changed region '
              f'{A.pct(sum(x["touch_all"] for x in sel), len(sel))}; patch overlaps a changed region '
              f'{A.pct(sum(x["patch_region"] for x in sel), len(sel))}; resolved {A.pct(sum(x["resolved"] for x in sel), len(sel))}')
        print(f'      tool calls median {statistics.median(x["n"] for x in sel)}; executed reads {rc["reads"]}, ranged '
              f'{rc["ranged"]}, mangled {A.pct(rc["mangled"], rc["ranged"])}; mean share of changed regions shown '
              f'{statistics.mean(x["share"] for x in sel):.3f}')
        e = collections.Counter(x['ended'] for x in sel)
        print('      ended: ' + '; '.join(f'{k} {v}' for k, v in e.most_common()))
    repos = collections.defaultdict(lambda: {c: [0, 0] for c in ARMS})
    sizes = collections.defaultdict(lambda: {c: collections.Counter() for c in ARMS})
    for t in tasks:
        for c in ARMS:
            x = rows.get((t, c))
            if x and x['entered']:
                repos[x['repo']][c][0] += x['resolved']
                repos[x['repo']][c][1] += 1
                sizes[size_bucket(x['regions'])][c].update(runs=1, resolved=int(x['resolved']), every=int(x['every']),
                                                           overlap=int(x['patch_region']))
    print('   resolved by repository: ' + '; '.join(
        f'{r}: ' + ', '.join(f'{c} {v[c][0]}/{v[c][1]}' for c in ARMS) for r, v in sorted(repos.items())))
    print('   by number of changed regions (per arm: resolved / shown every region / patch overlaps, of runs):')
    for k in BUCKETS:
        if k in sizes:
            print(f'      {k}: ' + '; '.join(f'{c} {v["resolved"]}/{v["every"]}/{v["overlap"]} of {v["runs"]}'
                                            for c, v in sizes[k].items()))
    both = [t for t in tasks if all((t, c) in rows and rows[(t, c)]['entered'] for c in ('ON', 'OA'))]
    cells = collections.Counter((rows[(t, 'OA')]['resolved'], rows[(t, 'ON')]['resolved']) for t in both)
    print(f'   resolved, OA (rows) by ON (columns), {len(both)} tasks: OA yes ON yes {cells[(True, True)]}, OA yes ON no '
          f'{cells[(True, False)]}, OA no ON yes {cells[(False, True)]}, OA no ON no {cells[(False, False)]}')
    for c in ARMS:
        ex = [rows[(t, c)]['extra'] for t in tasks if (t, c) in rows and rows[(t, c)]['extra']]
        if ex:
            want = 0 if c == 'N' else 1
            print(f'   {c} extra.jsonl: rows {len(ex)}; note in the first user message {want} time(s), as expected, in '
                  f'{sum(e.get("note_in_first_message", 0) == want for e in ex)}; arm recorded as {c} '
                  f'{sum(e.get("arm") == c for e in ex)}; seeds {sorted({e.get("seed") for e in ex})}')


def pooled(rows, tasks):
    """Seeds 2 (18) and 3 (22) together for N, ON and OA, bootstrap by task."""
    outcomes = (('resolved', lambda x: int(x['resolved'])), ('shown every changed region', lambda x: int(x['every'])),
                ('final patch overlaps a changed region', lambda x: int(x['patch_region'])))

    def runs_of(c):
        return {t: [rows[k] for k in ((t, c), (t, f'{c}18')) if k in rows and rows[k]['entered']] for t in tasks}

    for name, fn in outcomes:
        parts = []
        for c in POOL:
            by = {t: [fn(x) for x in xs] for t, xs in runs_of(c).items() if xs}
            n = sum(map(len, by.values()))
            parts.append(f'{c} {A.rate(A.boot_ci(by))} ({sum(map(sum, by.values()))} of {n})')
        print(f'   {name}: ' + '; '.join(parts))
        diffs = []
        for a, b in (('OA', 'N'), ('ON', 'N'), ('OA', 'ON')):
            xa, xb = collections.defaultdict(list), collections.defaultdict(list)
            for t in tasks:
                for sa, sb in (((t, a), (t, b)), ((t, f'{a}18'), (t, f'{b}18'))):
                    if sa in rows and sb in rows and rows[sa]['entered'] and rows[sb]['entered']:
                        xa[t].append(fn(rows[sa]))
                        xb[t].append(fn(rows[sb]))
            pairs = sum(map(len, xa.values()))
            diffs.append(f'{a}-{b} {A.dpts(A.diff_ci(xa, xb))} ({pairs} pairs, {len(xa)} tasks)')
        print('      differences, paired by task and seed: ' + '; '.join(diffs))


def report(rows, tasks, notes, label):
    print(f'EXPERIMENT 22: the second seed of experiment 18, arms N, ON, OF, OA ({label})')
    print()
    print('0. Inputs')
    for n in notes:
        print(f'   {n}')
    print(f'   tasks of tasks_18.txt: {len(tasks)}')
    print()
    print(f'1. Runs per arm on the 40 tasks (N, ON, OF, OA: experiment 22, seed {SEED_22}; N18, ON18, OA18: experiment 18, '
          f'seed {SEED_18}, pooled description only)')
    for c in ARMS + OTHER:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows]
        infra = [(x['task'], x['infra']) for x in sel if x['infra']]
        print(f'   {c:<5} runs {len(sel)}; entered {sum(x["entered"] for x in sel)}; without a trace '
              f'{sum(not x["trace"] for x in sel)}; infrastructure failures {len(infra)}'
              + (': ' + '; '.join(f'{t} {k}' for t, k in infra) if infra else ''))
        m = [t for t in tasks if (t, c) not in rows]
        if m:
            print(f'      no task result for {len(m)} tasks' + (f': {", ".join(m)}' if len(m) < 40 else ''))
    print()
    print(f'2. Rules (runs of 22, seed {SEED_22}; paired by task; 95% bootstrap by task, 2,000 resamples, seed 0; a verdict '
          f'needs at least {B.MIN_TASKS} tasks)')
    resolved, overlap, every = (lambda x: x['resolved']), (lambda x: x['patch_region']), (lambda x: x['every'])
    verdicts = {
        'L1': B.rule(rows, tasks, 'L1', 'resolved', 'OA', 'N', resolved),
        'L2': B.rule(rows, tasks, 'L2', 'resolved', 'ON', 'N', resolved),
        'L3': B.rule(rows, tasks, 'L3', 'final patch overlaps a changed region', 'OA', 'ON', overlap),
        'L4': B.rule(rows, tasks, 'L4', 'final patch overlaps a changed region', 'ON', 'N', overlap),
        'L5a': B.rule(rows, tasks, 'L5', 'final patch overlaps a changed region', 'OF', 'ON', overlap),
        'L5b': B.rule(rows, tasks, 'L5', 'final patch overlaps a changed region', 'OA', 'OF', overlap),
        'L6a': B.rule(rows, tasks, 'L6', 'resolved', 'OF', 'N', resolved),
        'L6b': B.rule(rows, tasks, 'L6', 'resolved', 'OA', 'OF', resolved),
        'L7a': B.rule(rows, tasks, 'L7', 'shown every changed region', 'ON', 'N', every),
        'L7b': B.rule(rows, tasks, 'L7', 'shown every changed region', 'OF', 'ON', every),
    }
    print()
    print('3. No rule: reported (entered runs of each arm of 22)')
    describe(rows, tasks)
    print()
    print(f'4. No rule: POOLED over seeds {SEED_18} (experiment 18) and {SEED_22} (experiment 22), N, ON and OA; shares of '
          f'task-runs, 95% bootstrap by task (a task\'s two runs resampled together)')
    pooled(rows, tasks)
    return verdicts


def write_csv(rows, tasks, path):
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['task', 'arm', 'experiment', 'seed', 'repo', 'entered', 'infrastructure', 'resolved', 't_shown',
                    'every_region', 'changed_regions', 'share_shown', 'patch_touches_every_region', 'patch_nonempty',
                    'patch_gold_file', 'patch_overlaps', 'tool_calls', 'harness_tool_calls', 'ended', 'reads',
                    'ranged_reads', 'mangled_reads', 'graph_calls'])
        for t in tasks:
            for c in ARMS + OTHER:
                x = rows.get((t, c))
                if x is None:
                    continue
                exp, seed, arm = ('22', SEED_22, c) if c in ARMS else ('18', SEED_18, c[:-2])
                w.writerow([t, arm, exp, seed, x['repo'], int(x['entered']), x['infra'] or '', int(x['resolved']),
                            'inf' if x['t'] == INF else x['t'], int(x['every']), x['regions'], round(x['share'], 4),
                            int(x['touch_all']), int(x['patch']), int(x['patch_file']), int(x['patch_region']), x['n'],
                            x['n_harness'], x['ended'], x['reads']['reads'], x['reads']['ranged'], x['reads']['mangled'],
                            sum(x['graph'].values())])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--standin', action='store_true')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = [line.strip() for line in open(B.TASKS_18, encoding='utf-8') if line.strip()]
    assert len(tasks) == 40 and len(set(tasks)) == 40, len(tasks)
    if not args.standin and not all((ROOT_22 / c / f'seed{SEED_22}').is_dir() for c in ARMS):
        sys.exit(f'no stored runs of every arm under {ROOT_22}: run analysis/store_22.py first (or use --standin)')
    runs, notes = collect(args.standin)
    rows = score(runs, set(tasks))
    label = 'STAND-IN: the stored runs of 18 as 22, OF = ON' if args.standin else f'one launch per shard, seed {SEED_22}'
    buf = io.StringIO()
    saved, sys.stdout = sys.stdout, buf
    try:
        report(rows, tasks, notes, label)
    finally:
        sys.stdout = saved
    text = buf.getvalue()
    sys.stdout.write(text)
    if not (args.no_write or args.standin):
        (ROOT_22 / 'analyze_22.txt').write_text(text, encoding='utf-8', newline='\n')
        write_csv(rows, tasks, ROOT_22 / 'runs_22.csv')
        print(f'written: {ROOT_22 / "analyze_22.txt"} (the text above) and {ROOT_22 / "runs_22.csv"}', file=sys.stderr)


if __name__ == '__main__':
    main()
