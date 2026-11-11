"""EXPLORATORY. Pre-registration 18 (or 22): what each arm costs in file content read, and when the first edit of a
changed region happens, counted over ALL runs of an arm, so that nothing is conditioned on how a run ended.

Why. A count "among the runs that do not end on the context window" conditions on an outcome the arm itself changes.
This script shows the same two things without that: the cost of an arm as what its runs read (every run counts),
and the placement of its edits as a course over tool calls (every run stays in the denominator; a run that has
ended simply makes no further edit).

Terms (those of analysis/explore_read_starts.py, whose reading of the traces is used unchanged, with every call of a
step that holds several tool calls paired with its own result):
  CHANGED REGION   a hunk of the reference patch in a file that exists before the fix
  FIX EDIT         an `edit_file` call of status ok whose returned diff changes lines of a CHANGED REGION (an edit made
                   through the shell is not seen here; the registered count of final patches is in
                   analysis/results/18/analyze_18.txt)
  LINES READ       the lines returned by the run's `read_file` calls of status ok, counted with repetition, and the
                   distinct lines among them
Printed per arm: tool calls, reads and LINES READ per run (medians and means); the same up to the first FIX EDIT;
by tool call 5, 10, 15, 20, 30, 40 and at the end: runs with a FIX EDIT so far, runs that have ended on the context
window, runs that have ended otherwise. Then, paired by task: LINES READ and reads, each arm minus the control and
the arms against each other, mean difference with a 95% bootstrap interval over tasks. Then, as a check that does
not use the ending of single arms: the tasks on which no arm's run ended on the context window. Last, by something
fixed before any run: where the fix lies. A read without a line range returns lines 1 to 150 of a file, so a name
leads to a place in the first 150 lines at once and to a deeper one only by further reads; tasks and CHANGED
REGIONS are split at that line (a region counts as EDITED when a region of the run's final patch overlaps it).
Tasks are also split by the length of the longest file the fix changes, at the median over the tasks, and by
whether the run of ANOTHER arm ended on the context window (for each pair of arms: the tasks where the first arm's
run ended there, and what the second arm did on those same tasks).
Endings are read from the per-run table of the registered analysis (analysis/results/<n>/runs_<n>.csv).

Usage:
    python analysis/explore_cost_18.py                    # experiment 18
    python analysis/explore_cost_18.py --experiment 22    # experiment 22, once its runs are stored
Output of the first form is stored in analysis/results/explore_cost_18.txt.
"""
import argparse
import collections
import csv
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_read_starts as R  # noqa: E402
from explore_reach_22 import LABELS, load_runs, of_note  # noqa: E402

CUTS = (5, 10, 15, 20, 30, 40)
WINDOW = 'context window'


def med(v):
    return f'{statistics.median(v):g}' if v else 'none'


def mean(v):
    return f'{statistics.mean(v):.1f}' if v else 'none'


def paired(a, b, n=2000, seed=0):
    """Mean of a minus b over the tasks in both, with a 95% bootstrap interval over tasks."""
    tasks = sorted(set(a) & set(b))
    if not tasks:
        return None
    d = [a[t] - b[t] for t in tasks]
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choice(d) for _ in d) for _ in range(n))
    return statistics.mean(d), boots[int(0.025 * n)], boots[int(0.975 * n) - 1], len(tasks)


def edited(patch, x):
    """Whether a region of the final patch overlaps the CHANGED REGION x."""
    if not patch or not patch.strip():
        return False
    try:
        mine = {R.norm(k): v['regions'] for k, v in R.parse_patch(patch).items()}
    except Exception:
        return False
    return any(not (d < x['a'] or c > x['b']) for c, d in mine.get(x['f'], []))


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser()
    ap.add_argument('--experiment', default='18')
    args = ap.parse_args()
    root = HERE / 'results' / args.experiment
    arms = [a for a in ('N', 'ON', 'OF', 'OA') if (root / a).is_dir()]
    print(f'PRE-REGISTRATION {args.experiment}: WHAT EACH ARM READS, AND WHEN THE FIRST EDIT OF A CHANGED REGION HAPPENS, OVER ALL RUNS (EXPLORATORY)')
    if not arms:
        print(f'no runs under analysis/results/{args.experiment}')
        return
    ended, overlap = {}, {}
    table = root / f'runs_{args.experiment}.csv'
    if table.exists():
        with open(table, encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('launch', r.get('experiment')) == args.experiment:
                    ended[(r['task'], r['arm'])] = r['ended']
                    overlap[(r['task'], r['arm'])] = R.truth(r['patch_overlaps'])
    gold = R.gold_regions()
    texts = R.task_texts()
    runs = load_runs(root, arms)
    per = collections.defaultdict(dict)       # arm -> task -> record
    for (task, cond, seed), r in sorted(runs.items()):
        if cond not in arms or r[0] is None:
            continue
        g = gold.get(task, {})
        if not g:
            continue
        places = R.oracle_places(task)
        note = places if cond == 'OA' else (of_note(task) or ()) if cond == 'OF' else ()
        reads, regs, _fr, more = R.analyse(R.one_call_steps(r[0]), g, texts.get(task, ''), places, cond, note)
        ok = [x for x in reads if 'range' in x and x['cls'] not in ('FAILED', 'OWN FILE')]
        t0 = more['after']['t0'] if more['after'] else None
        seen = collections.defaultdict(set)
        for x in ok:
            seen[x['f']] |= set(range(x['range'][0], x['range'][1] + 1))
        upto = [x for x in ok if t0 is None or x['i'] < t0]
        per[cond][task] = {
            'calls': more['calls'], 't0': t0, 'ended': ended.get((task, cond), ''),
            'reads': len(ok), 'lines': sum(x['range'][1] - x['range'][0] + 1 for x in ok),
            'distinct': sum(len(v) for v in seen.values()),
            'reads_before': len(upto), 'lines_before': sum(x['range'][1] - x['range'][0] + 1 for x in upto),
            'overlap': overlap.get((task, cond)), 'resolved': R.truth(r[1].get('resolved')),
            'deepest': max(x['a'] for x in regs), 'n_regs': len(regs),
            'longest': max((len((R.N.file_text(task, f) or '').splitlines()) for f in g), default=0),
            'regs': [(x['a'] > R.CAP, bool(x['seen']), edited(r[2], x)) for x in regs]}
    print()
    print('1. Per arm, every run')
    for a in arms:
        rs = list(per[a].values())
        fx = [x for x in rs if x['t0'] is not None]
        print(f'pre-registration {args.experiment}, {LABELS[a]}: runs {len(rs)}')
        print(f'   per run: tool calls, median {med([x["calls"] for x in rs])}; reads, median {med([x["reads"] for x in rs])}, mean '
              f'{mean([x["reads"] for x in rs])}; LINES READ, median {med([x["lines"] for x in rs])}, mean {mean([x["lines"] for x in rs])}; '
              f'distinct lines, median {med([x["distinct"] for x in rs])}, mean {mean([x["distinct"] for x in rs])}')
        print(f'   runs with a FIX EDIT {len(fx)} of {len(rs)}; the call of the first one, median {med([x["t0"] for x in fx])}; reads '
              f'before it, median {med([x["reads_before"] for x in fx])}; LINES READ before it, median {med([x["lines_before"] for x in fx])}')
        print(f'   up to the first FIX EDIT or the end of the run, all runs: reads, median {med([x["reads_before"] for x in rs])}; '
              f'LINES READ, median {med([x["lines_before"] for x in rs])}, mean {mean([x["lines_before"] for x in rs])}')
        line = []
        for c in CUTS + (None,):
            fe = sum(x['t0'] is not None and (c is None or x['t0'] <= c) for x in rs)
            win = sum(x['ended'] == WINDOW and (c is None or x['calls'] <= c) for x in rs)
            oth = sum(x['ended'] != WINDOW and (c is None or x['calls'] <= c) for x in rs)
            line.append(f'{"the end" if c is None else "call " + str(c)}: FIX EDIT {fe}, ended on the context window {win}, ended otherwise {oth}')
        print('   by ' + '; by '.join(line))
    print()
    print('2. Paired by task: mean difference with a 95% bootstrap interval over tasks')
    for key, name in (('lines', 'LINES READ'), ('distinct', 'distinct lines read'), ('reads', 'reads'),
                      ('lines_before', 'LINES READ up to the first FIX EDIT or the end')):
        print(f'   {name}')
        for i, a in enumerate(arms):
            for b in arms[i + 1:]:
                p = paired({t: x[key] for t, x in per[b].items()}, {t: x[key] for t, x in per[a].items()})
                if p:
                    print(f'      {b} minus {a}: {p[0]:+.1f} [{p[1]:+.1f}, {p[2]:+.1f}] ({p[3]} tasks)')
    print()
    print('3. The tasks on which no arm\'s run ended on the context window (the same tasks in every arm)')
    tasks = [t for t in sorted(set.intersection(*[set(per[a]) for a in arms]))
             if all(per[a][t]['ended'] != WINDOW for a in arms)]
    print(f'   tasks {len(tasks)} of {len(set.intersection(*[set(per[a]) for a in arms]))}; runs with a FIX EDIT: '
          + '; '.join(f'{a} {sum(per[a][t]["t0"] is not None for t in tasks)}' for a in arms)
          + '; resolved: ' + '; '.join(f'{a} {sum(bool(per[a][t]["resolved"]) for t in tasks)}' for a in arms))
    common = sorted(set.intersection(*[set(per[a]) for a in arms]))
    rest = [t for t in common if t not in tasks]
    print(f'   the other {len(rest)} tasks (some arm\'s run ended on the context window): runs with a FIX EDIT: '
          + '; '.join(f'{a} {sum(per[a][t]["t0"] is not None for t in rest)}' for a in arms)
          + '; resolved: ' + '; '.join(f'{a} {sum(bool(per[a][t]["resolved"]) for t in rest)}' for a in arms))

    print()
    print(f'4. By where the fix lies (fixed before any run): line {R.CAP} is the last line a read without a range returns')
    first = arms[0]
    for name, test in (('every CHANGED REGION starts in the first 150 lines', lambda x: x['deepest'] <= R.CAP),
                       ('some CHANGED REGION starts below line 150', lambda x: x['deepest'] > R.CAP)):
        sel = [t for t in common if test(per[first][t])]
        print(f'   tasks where {name}: {len(sel)}; CHANGED REGIONS per task, median {med([per[first][t]["n_regs"] for t in sel])}')
        for label, f in (('final patch overlaps a changed region', lambda x: bool(x['overlap'])),
                         ('resolved', lambda x: bool(x['resolved'])),
                         ('ended on the context window', lambda x: x['ended'] == WINDOW)):
            print(f'      {label}: ' + '; '.join(f'{a} {sum(f(per[a][t]) for t in sel)}' for a in arms))
        print('      LINES READ per run, mean: ' + '; '.join(f'{a} {mean([per[a][t]["lines"] for t in sel])}' for a in arms))
    for name, deep in (('CHANGED REGIONS that start in the first 150 lines', False), ('CHANGED REGIONS that start below line 150', True)):
        print(f'   {name}: ' + '; '.join(
            f'{a} shown {sum(sh for t in common for d, sh, ed in per[a][t]["regs"] if d == deep)}, EDITED '
            f'{sum(ed for t in common for d, sh, ed in per[a][t]["regs"] if d == deep)} of '
            f'{sum(1 for t in common for d, sh, ed in per[a][t]["regs"] if d == deep)}' for a in arms))
    by_task = {a: {True: {}, False: {}} for a in arms}
    for a in arms:
        for t in common:
            for deep in (True, False):
                v = [ed for d, sh, ed in per[a][t]['regs'] if d == deep]
                if v:
                    by_task[a][deep][t] = sum(v) / len(v)
    print("   share of a task's regions EDITED, mean difference by task with a 95% bootstrap interval over tasks")
    for deep, name in ((False, 'regions in the first 150 lines'), (True, 'regions below line 150')):
        for i, a in enumerate(arms):
            for b in arms[i + 1:]:
                p = paired(by_task[b][deep], by_task[a][deep])
                if p:
                    print(f'      {name}, {b} minus {a}: {100 * p[0]:+.1f} points [{100 * p[1]:+.1f}, {100 * p[2]:+.1f}] ({p[3]} tasks)')

    print()
    print('5. By the length of the longest file the fix changes (fixed before any run), split at the median over the tasks')
    cut = statistics.median(per[first][t]['longest'] for t in common)
    for name, test in ((f'the longest changed file has at most {cut:g} lines', lambda x: x['longest'] <= cut),
                       (f'the longest changed file has more than {cut:g} lines', lambda x: x['longest'] > cut)):
        sel = [t for t in common if test(per[first][t])]
        print(f'   tasks where {name}: {len(sel)}; CHANGED REGIONS per task, median {med([per[first][t]["n_regs"] for t in sel])}')
        for label, f in (('final patch overlaps a changed region', lambda x: bool(x['overlap'])),
                         ('resolved', lambda x: bool(x['resolved'])),
                         ('ended on the context window', lambda x: x['ended'] == WINDOW)):
            print(f'      {label}: ' + '; '.join(f'{a} {sum(f(per[a][t]) for t in sel)}' for a in arms))
        print('      LINES READ per run, mean: ' + '; '.join(f'{a} {mean([per[a][t]["lines"] for t in sel])}' for a in arms))
    print()
    print('6. The tasks on which one arm\'s run ended on the context window, and every arm on those same tasks')
    for a in arms:
        dead = [t for t in common if per[a][t]['ended'] == WINDOW]
        live = [t for t in common if per[a][t]['ended'] != WINDOW]
        for name, sel in ((f'the run of {a} ended on the context window', dead), (f'the run of {a} did not', live)):
            print(f'   tasks where {name}: {len(sel)}; final patch overlaps a changed region: '
                  + '; '.join(f'{b} {sum(bool(per[b][t]["overlap"]) for t in sel)}' for b in arms)
                  + '; resolved: ' + '; '.join(f'{b} {sum(bool(per[b][t]["resolved"]) for t in sel)}' for b in arms))
    none = [t for t in common if all(per[a][t]['ended'] != WINDOW for a in arms)]
    some = [t for t in common if t not in none]
    for name, sel in (('no arm\'s run ended on the context window', none), ('some arm\'s run did', some)):
        print(f'   tasks where {name}: {len(sel)}; final patch overlaps a changed region: '
              + '; '.join(f'{b} {sum(bool(per[b][t]["overlap"]) for t in sel)}' for b in arms)
              + '; resolved: ' + '; '.join(f'{b} {sum(bool(per[b][t]["resolved"]) for t in sel)}' for b in arms)
              + '; the longest changed file, median lines ' + med([per[first][t]['longest'] for t in sel]))


if __name__ == '__main__':
    main()
