"""EXPLORATORY. How the runs of an oracle experiment end, by arm, and where the final patch lands among the runs
that do not end on the context window.

No rule of pre-registration 18 covers this cut; it was made after the result was seen. It reads the per-run table
that the registered analysis writes (analysis/results/18/runs_18.csv, by analysis/analyze_18.py) and nothing else:
no trace is opened and nothing is recomputed. Each printed count is a count of rows of that table.

Columns used: arm, launch, entered, ended, resolved, every_region, patch_overlaps, patch_nonempty, tool_calls.
Rows of other launches in the table (stored runs of earlier experiments, kept there for comparison) are left out.

Usage:
    python analysis/explore_endings_18.py                      # experiment 18
    python analysis/explore_endings_18.py --csv <table> --launch <n>   # another table of the same shape

Output of the first form is stored in analysis/results/explore_endings_18.txt.
"""
import argparse
import csv
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ['N', 'ON', 'OF', 'OA']
LABEL = {'N': 'control', 'ON': 'told the functions by name', 'OF': 'told the functions with their line ranges',
         'OA': 'told every changed place by file and lines'}
WINDOW = 'context window'


def truth(v):
    return str(v).strip() in ('1', 'True', 'true')


def frac(k, n):
    return f'{k} of {n}' + (f' ({100.0 * k / n:.1f}%)' if n else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=os.path.join(HERE, 'results', '18', 'runs_18.csv'))
    ap.add_argument('--launch', default='18')
    args = ap.parse_args()

    with open(args.csv, encoding='utf-8', newline='') as f:
        rows = [r for r in csv.DictReader(f)
                if r['launch'] == args.launch and r['arm'] in ARMS and truth(r['entered'])]
    arms = [a for a in ARMS if any(r['arm'] == a for r in rows)]
    tasks = sorted({r['task'] for r in rows})

    print('EXPLORATORY: how the runs end, and where the final patch lands among the runs that do not end on the')
    print(f'context window. Launch {args.launch}; {len(tasks)} tasks; rows of the per-run table, one per run.')
    print()
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
        print()

    print('All runs, for comparison with the registered analysis: final patch overlaps a changed region '
          + '; '.join(f'{a} {sum(truth(r["patch_overlaps"]) for r in rows if r["arm"] == a)}' for a in arms)
          + '; resolved ' + '; '.join(f'{a} {sum(truth(r["resolved"]) for r in rows if r["arm"] == a)}' for a in arms))
    print('The column every_region is the registered script\'s, which gives a step with several tool calls its first')
    print('result only; with every call paired with its own result the counts for whole arms are those of part 7 of')
    print('analysis/results/explore_read_starts.txt.')


if __name__ == '__main__':
    main()
