"""EXPLORATORY. The oracle experiment over both seeds with every task counted once.

Pre-registration 18 ran the 40 tasks with seed 2; pre-registration 22 ran 20 of them again with seed 3. Pooling the
runs counts those 20 tasks twice, and they are the easier half. Here a task's outcome in an arm is the mean over
the seeds it has (one run, or two), so that every task weighs the same: a task resolved in one of its two runs
counts one half. No rule covers this; the registrations allow the two seeds together as description only.

Reads the per-run tables of the two registered analyses and nothing else:
  analysis/results/18/runs_18.csv   (rows of launch 18: arms N, ON, OA, seed 2, 40 tasks)
  analysis/results/22/runs_22.csv   (rows of experiment 22: arms N, ON, OF, OA, seed 3; it also repeats the rows of
                                     18, which are checked against the first table and not used twice)
Printed, for the arms both seeds share (N the control, ON the functions by name, OA every changed place by file and
lines): the sum over the 40 tasks of each task's mean outcome, for resolved, for a final patch that overlaps a
changed region, and for a run shown every changed region as the registered scripts count it; the differences
between arms as the mean over tasks of the per-task difference, in points, with a 95% bootstrap interval over tasks
(2,000 resamples, seed 0); and the same on the tasks with one seed and on the tasks with two. Arm OF (the functions
with their line ranges) ran with seed 3 only and is printed for its 20 tasks beside the other arms' seed-3 runs.

Usage:
    python analysis/explore_oracle_once.py
Output is stored in analysis/results/22/explore_oracle_once.txt.
"""
import collections
import csv
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T18 = HERE / 'results' / '18' / 'runs_18.csv'
T22 = HERE / 'results' / '22' / 'runs_22.csv'
SHARED = ('N', 'ON', 'OA')
LABEL = {'N': 'control', 'ON': 'names', 'OF': 'ranges', 'OA': 'lines'}
MEASURES = (('resolved', 'resolved'), ('patch_overlaps', 'final patch overlaps a changed region'),
            ('every_region', 'shown every changed region (as the registered scripts count it)'))


def truth(v):
    return str(v).strip() in ('1', 'True', 'true')


def rows_of(path, key, value):
    with open(path, encoding='utf-8', newline='') as f:
        return [r for r in csv.DictReader(f) if r.get(key) == value and truth(r['entered'])]


def interval(d, n=2000, seed=0):
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choice(d) for _ in d) for _ in range(n))
    return boots[int(0.025 * n)], boots[int(0.975 * n) - 1]


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    r18 = rows_of(T18, 'launch', '18')
    r22 = rows_of(T22, 'experiment', '22')
    again = rows_of(T22, 'experiment', '18')
    same = {(r['task'], r['arm']): (r['resolved'], r['patch_overlaps'], r['every_region']) for r in r18} == \
           {(r['task'], r['arm']): (r['resolved'], r['patch_overlaps'], r['every_region']) for r in again}
    runs = collections.defaultdict(list)          # (task, arm) -> runs
    for r in r18 + r22:
        runs[(r['task'], r['arm'])].append(r)
    tasks = sorted({r['task'] for r in r18})
    twice = sorted({r['task'] for r in r22})
    once = [t for t in tasks if t not in twice]
    print('THE ORACLE EXPERIMENT OVER BOTH SEEDS, EVERY TASK COUNTED ONCE (EXPLORATORY; no rule)')
    print(f'tasks {len(tasks)}: with one run an arm (seed 2) {len(once)}, with two (seeds 2 and 3) {len(twice)}; '
          f'runs: ' + ', '.join(f'{a} {sum(len(runs[(t, a)]) for t in tasks)}' for a in SHARED)
          + f'; the rows of 18 repeated in the table of 22 equal those of the table of 18: {"yes" if same else "NO"}')
    print()

    def score(task, arm, col):
        rs = runs[(task, arm)]
        return sum(truth(r[col]) for r in rs) / len(rs)

    for col, name in MEASURES:
        print(name)
        for label, sel in (('all tasks', tasks), ('tasks with one run an arm', once), ('tasks with two runs an arm', twice)):
            if not sel:
                continue
            tot = {a: sum(score(t, a, col) for t in sel) for a in SHARED}
            print(f'   {label} ({len(sel)}): ' + '; '.join(f'{LABEL[a]} {tot[a]:g}' for a in SHARED)
                  + ' (a task\'s mean over its runs, summed over tasks)')
            for a, b in (('ON', 'N'), ('OA', 'N'), ('OA', 'ON')):
                d = [100 * (score(t, a, col) - score(t, b, col)) for t in sel]
                lo, hi = interval(d)
                print(f'      {LABEL[a]} minus {LABEL[b]}: {statistics.mean(d):+.2f} points [{lo:+.2f}, {hi:+.2f}]; tasks where '
                      f'{LABEL[a]} is higher {sum(x > 0 for x in d)}, lower {sum(x < 0 for x in d)}')
        print()
    print('Runs pooled, for comparison (every run counts once, so the tasks with two runs count twice)')
    for col, name in MEASURES:
        print(f'   {name}: ' + '; '.join(
            f'{LABEL[a]} {sum(truth(r[col]) for t in tasks for r in runs[(t, a)])} of {sum(len(runs[(t, a)]) for t in tasks)}'
            for a in SHARED))
    print()
    print('Arm OF (ranges), seed 3, beside the other arms on its tasks and seed')
    s3 = {(r['task'], r['arm']): r for r in r22}
    arms3 = [a for a in ('N', 'ON', 'OF', 'OA') if any(k[1] == a for k in s3)]
    for col, name in MEASURES:
        print(f'   {name}: ' + '; '.join(
            f'{LABEL[a]} {sum(truth(s3[(t, a)][col]) for t in twice if (t, a) in s3)} of {sum((t, a) in s3 for t in twice)}'
            for a in arms3))


if __name__ == '__main__':
    main()
