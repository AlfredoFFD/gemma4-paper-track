"""EXPLORATORY. Counts on the runs of an oracle experiment that no rule covers and no other stored report prints:
how the runs end, by arm, and where the final patch lands among the runs that do not end on the context window;
the pairs of arms, task by task; the arms by the number of changed regions of the fix; what the notes hold; and the
arms by two splits of the tasks: whether the fix changes one file or several (fixed before any run), and whether
any arm's run ended on the context window (the same tasks in every arm, but a split made by the runs themselves).

No rule of pre-registration 18 covers these cuts; they were made after the result was seen. The script reads the
per-run table that the registered analysis writes (analysis/results/18/runs_18.csv, by analysis/analyze_18.py) and
the manifest of the notes (analysis/oracle_18/manifest.json, by analysis/make_oracle_18.py), and nothing else: no
trace is opened and nothing is recomputed. Each printed count is a count of rows of that table or a sum over the
tasks of the manifest.

Columns of the table used: task, arm, launch, entered, ended, resolved, every_region, patch_overlaps,
patch_nonempty, tool_calls. Rows of other launches in the table (stored runs of earlier experiments, kept there for
comparison) are left out. Fields of the manifest used, per task: changed_regions, modified_files, places,
distinct_names, names_module, names_path, places_module_or_path.

Usage:
    python analysis/explore_endings_18.py                      # experiment 18
    python analysis/explore_endings_18.py --csv <table> --launch <n> [--manifest <file>]   # the same shape

Output of the first form is stored in analysis/results/explore_endings_18.txt.
"""
import argparse
import csv
import json
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ['N', 'ON', 'OF', 'OA']
LABEL = {'N': 'control', 'ON': 'told the functions by name', 'OF': 'told the functions with their line ranges',
         'OA': 'told every changed place by file and lines'}
WINDOW = 'context window'
CLASSES = (('1', lambda k: k == 1), ('2 or 3', lambda k: 2 <= k <= 3), ('4 to 9', lambda k: 4 <= k <= 9),
           ('10 or more', lambda k: k >= 10), ('1 to 3', lambda k: k <= 3), ('4 or more', lambda k: k >= 4))


def truth(v):
    return str(v).strip() in ('1', 'True', 'true')


def frac(k, n):
    return f'{k} of {n}' + (f' ({100.0 * k / n:.1f}%)' if n else '')


def exact_p(b, c):
    """Two-sided exact McNemar p for b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=os.path.join(HERE, 'results', '18', 'runs_18.csv'))
    ap.add_argument('--launch', default='18')
    ap.add_argument('--manifest', default=None)
    args = ap.parse_args()
    manifest = args.manifest or os.path.join(HERE, f'oracle_{args.launch}', 'manifest.json')

    with open(args.csv, encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f)
                if r.get('launch', r.get('experiment')) == args.launch and r['arm'] in ARMS and truth(r['entered'])]
    arms = [a for a in ARMS if any(r['arm'] == a for r in rows)]
    tasks = sorted({r['task'] for r in rows})
    by = {(r['task'], r['arm']): r for r in rows}

    print('EXPLORATORY: counts on the runs of the oracle experiment that no rule covers.')
    print(f'Launch {args.launch}; {len(tasks)} tasks; rows of the per-run table, one per run.')
    print()
    print('1. How the runs end, and where the final patch lands among the runs that do not end on the context window')
    for a in arms:
        rs = [r for r in rows if r['arm'] == a]
        ends = {}
        for r in rs:
            ends[r['ended']] = ends.get(r['ended'], 0) + 1
        print(f'{a} ({LABEL[a]}): {len(rs)} runs; ended: '
              + '; '.join(f'{k} {v}' for k, v in sorted(ends.items(), key=lambda kv: (-kv[1], kv[0]))))
        win = [r for r in rs if r['ended'] == WINDOW]
        rest = [r for r in rs if r['ended'] != WINDOW]
        for name, part in (('ended on the context window', win), ('the other runs', rest)):
            if not part:
                print(f'   {name}: none')
                continue
            calls = statistics.median(int(r['tool_calls']) for r in part)
            print(f'   {name}: {len(part)} runs; tool calls, median {calls:g}; '
                  f'final patch changes a file {frac(sum(truth(r["patch_nonempty"]) for r in part), len(part))}; '
                  f'overlaps a changed region {frac(sum(truth(r["patch_overlaps"]) for r in part), len(part))}; '
                  f'shown every changed region {frac(sum(truth(r["every_region"]) for r in part), len(part))}; '
                  f'resolved {frac(sum(truth(r["resolved"]) for r in part), len(part))}')
    print('All runs, for comparison with the registered analysis: final patch overlaps a changed region '
          + '; '.join(f'{a} {sum(truth(r["patch_overlaps"]) for r in rows if r["arm"] == a)}' for a in arms)
          + '; resolved ' + '; '.join(f'{a} {sum(truth(r["resolved"]) for r in rows if r["arm"] == a)}' for a in arms))
    print('The column every_region is the registered script\'s, which gives a step with several tool calls its first')
    print('result only; with every call paired with its own result the counts for whole arms are those of part 7 of')
    print('analysis/results/explore_read_starts.txt.')
    print()

    print('2. Pairs of arms, task by task (tasks with a run in both arms): the first arm only, the second arm only,')
    print('   and the exact two-sided McNemar p of those two counts')
    for col, name in (('patch_overlaps', 'final patch overlaps a changed region'), ('resolved', 'resolved'),
                      ('patch_nonempty', 'final patch changes a file')):
        print(f'   {name}')
        for i, a in enumerate(arms):
            for b in arms[i + 1:]:
                both = [t for t in tasks if (t, a) in by and (t, b) in by]
                xa = sum(truth(by[t, a][col]) and not truth(by[t, b][col]) for t in both)
                xb = sum(truth(by[t, b][col]) and not truth(by[t, a][col]) for t in both)
                bb = sum(truth(by[t, a][col]) and truth(by[t, b][col]) for t in both)
                print(f'      {a} and {b} ({len(both)} tasks): both {bb}; {a} only {xa}; {b} only {xb}; '
                      f'neither {len(both) - bb - xa - xb}; p = {exact_p(xa, xb):.4f}')
    print()

    if not os.path.exists(manifest):
        print(f'3. and 4. need the manifest of the notes, which is not at {os.path.relpath(manifest, HERE)}')
        return
    with open(manifest, encoding='utf-8') as f:
        man = json.load(f)['tasks']
    print('3. By the number of changed regions of the fix (from the manifest of the notes)')
    for name, test in CLASSES:
        sel = [t for t in tasks if t in man and test(int(man[t]['changed_regions']))]
        if not sel:
            continue
        print(f'   {name}: tasks {len(sel)}; resolved '
              + '; '.join(f'{a} {sum(truth(by[t, a]["resolved"]) for t in sel if (t, a) in by)}' for a in arms)
              + '; final patch overlaps a changed region '
              + '; '.join(f'{a} {sum(truth(by[t, a]["patch_overlaps"]) for t in sel if (t, a) in by)}' for a in arms))
    print()
    print('4. What the notes hold (sums over the tasks of the manifest)')
    ms = [man[t] for t in tasks if t in man]
    tot = {k: sum(int(m.get(k, 0)) for m in ms) for k in
           ('changed_regions', 'places', 'distinct_names', 'names_module', 'names_path', 'places_module_or_path')}
    print(f'   tasks {len(ms)}; changed regions {tot["changed_regions"]}; places of the notes {tot["places"]}; '
          f'distinct names {tot["distinct_names"]}')
    print(f'   names that are a module, not a function or a class: {frac(tot["names_module"], tot["distinct_names"])}; '
          f'names that are a file path: {tot["names_path"]}')
    print(f'   places that lie outside any function or class: {frac(tot["places_module_or_path"], tot["places"])}')
    print()
    print("5. By whether the fix changes one file or several (from the manifest; fixed before any run)")
    for name, test in (("one file", lambda k: k == 1), ("several files", lambda k: k > 1)):
        sel = [t for t in tasks if t in man and test(int(man[t]["modified_files"]))]
        print(f"   {name}: tasks {len(sel)}; final patch overlaps a changed region "
              + "; ".join(f"{a} {sum(truth(by[t, a]['patch_overlaps']) for t in sel if (t, a) in by)}" for a in arms)
              + "; resolved " + "; ".join(f"{a} {sum(truth(by[t, a]['resolved']) for t in sel if (t, a) in by)}" for a in arms)
              + "; ended on the context window "
              + "; ".join(f"{a} {sum(by[t, a]['ended'] == WINDOW for t in sel if (t, a) in by)}" for a in arms))
    print()
    print("6. By whether any arm's run of the task ended on the context window (the same tasks in every arm)")
    full = [t for t in tasks if all((t, a) in by for a in arms)]
    none = [t for t in full if all(by[t, a]["ended"] != WINDOW for a in arms)]
    some = [t for t in full if t not in none]
    for name, sel in (("no arm's run ended there", none), ("some arm's run did", some)):
        print(f"   {name}: tasks {len(sel)}; final patch overlaps a changed region "
              + "; ".join(f"{a} {sum(truth(by[t, a]['patch_overlaps']) for t in sel)}" for a in arms)
              + "; resolved " + "; ".join(f"{a} {sum(truth(by[t, a]['resolved']) for t in sel)}" for a in arms)
              + "; fixes in one file " + str(sum(int(man[t]["modified_files"]) == 1 for t in sel if t in man)))
    for a in arms:
        dead = [t for t in full if by[t, a]["ended"] == WINDOW]
        print(f"   the {len(dead)} tasks on which the run of {a} ended there: final patch overlaps a changed region "
              + "; ".join(f"{b} {sum(truth(by[t, b]['patch_overlaps']) for t in dead)}" for b in arms))


if __name__ == '__main__':
    main()
