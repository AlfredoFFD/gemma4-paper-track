"""EXPLORATORY. Pre-registration 22: where each arm's file reads start and how each arm reaches the places of the
fix, with the arm that is told the functions with their line ranges (OF) beside the three arms of 18.

Descriptive only; the rules of 22 are in analysis/analyze_22.py. This script adds no reading of its own: it loads
the runs of an oracle experiment the way analysis/explore_read_starts.py loads those of 18 (every call of a step
with several tool calls paired with its own result) and prints that script's part 1 (where a READ starts) and
part 7 (how the PLACES of the note are reached) for each arm. Terms are those of that script.

What differs by arm is which lines the run was given at its start (SOURCE NOTE):
  N, ON   none (ON's note holds dotted names, no line)
  OF      the line range of every definition the note names (parsed from the OF note: "- <file>, lines a-b (<name>)";
          a module or a path is named without lines and gives none)
  OA      the line range of every PLACE (the changed places, about twenty lines each)
The PLACES whose reaching is counted are the same in every arm: the changed places of the task's note of 18
(data/cache/oracle_18/<task>.json), so that the arms can be compared. The OF notes are read from
data/cache/oracle_22/<task>.json (built by analysis/make_oracle_22.py; not tracked).

Usage:
    python analysis/explore_reach_22.py                               # experiment 22 (analysis/results/22, seed 3)
    python analysis/explore_reach_22.py --experiment 18               # the three arms of 18: must print what part 7
                                                                      # of analysis/results/explore_read_starts.txt prints
Output of the first form is stored in analysis/results/explore_reach_22.txt.
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_read_starts as R  # noqa: E402

LABELS = {'N': 'arm N (control)', 'ON': "arm ON (the fix's places told as names)",
          'OF': 'arm OF (the functions told with their line ranges)',
          'OA': "arm OA (the fix's places told as files and lines)"}
OF_LINE = re.compile(r'^- (.+?), lines (\d+)-(\d+) \((.+)\)\s*$')


def of_note(task):
    """The line ranges of the task's OF note, as dicts with file, start and end; None when the note is not here."""
    path = R.DATA / 'cache' / 'oracle_22' / (str(task).replace('/', '__') + '.json')
    if not path.exists():
        return None
    with io.open(path, encoding='utf-8') as f:
        text = json.load(f).get('OF') or ''
    out = []
    for line in text.splitlines():
        m = OF_LINE.match(line)
        if m:
            out.append({'file': m.group(1), 'start': int(m.group(2)), 'end': int(m.group(3))})
    return out


def load_runs(root, arms):
    saved = R.A.CONDITIONS
    R.A.CONDITIONS = tuple(arms)
    try:
        loaded = R.A.load_root(root)
    finally:
        R.A.CONDITIONS = saved
    return loaded[0] if isinstance(loaded, tuple) else loaded


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser()
    ap.add_argument('--experiment', default='22')
    ap.add_argument('--root', default=None)
    ap.add_argument('--arms', default=None)
    args = ap.parse_args()
    root = Path(args.root) if args.root else HERE / 'results' / args.experiment
    arms = [a for a in (args.arms.split(',') if args.arms else ('N', 'ON', 'OF', 'OA')) if (root / a).is_dir()]
    print(f'PRE-REGISTRATION {args.experiment}: WHERE EACH ARM\'S READS START AND HOW IT REACHES THE PLACES OF THE FIX (EXPLORATORY)')
    if not arms:
        print(f'no runs under analysis/results/{args.experiment}')
        return
    gold = R.gold_regions()
    texts = R.task_texts()
    runs = load_runs(root, arms)
    done = {}
    for arm in arms:
        label = f'pre-registration {args.experiment}, {LABELS[arm]}'
        rows, kept, files_all, raws = [], [], [], []
        missing = 0
        for (task, cond, seed), r in sorted(runs.items()):
            if cond != arm or r[0] is None:
                continue
            places = R.oracle_places(task)
            if arm == 'OA':
                note = places
            elif arm == 'OF':
                note = of_note(task)
                missing += note is None
            else:
                note = ()
            g = gold.get(task, {})
            reads, rr, fr, more = R.analyse(R.one_call_steps(r[0]), g, texts.get(task, ''), places, arm, note or ())
            key = f'seed {seed}'
            for x in reads:
                x.update(task=task, key=key)
            for x in more['places']:
                x.update(task=task, key=key)
            rows += reads
            files_all += fr
            kept.append({'task': task, 'key': key, 'resolved': R.truth(r[1].get('resolved')), 'regs': rr, 'patch': r[2],
                         'after': more['after'], 'places': more['places'], 'arm': arm, 'calls': more['calls']})
            raws.append((task, r[0]))
        done[arm] = (label, rows, kept, files_all, raws, missing)
    print()
    print('1. Where a READ starts')
    for arm in arms:
        label, rows, kept, files_all, raws, missing = done[arm]
        print(f'{label}: runs {len(kept)}, tasks {len({k["task"] for k in kept})}'
              + (f'; OF notes not on this machine for {missing} tasks' if missing else ''))
        R.part1(label, rows, note=arm in ('OF', 'OA'))
    print()
    print('7. How each arm reaches the places of the note')
    for arm in arms:
        label, rows, kept, files_all, raws, missing = done[arm]
        raw_every = n_steps = n_calls = 0
        for task, raw in raws:
            g = gold.get(task, {})
            if g:
                raw_every += all(x['seen'] for x in R.analyse(raw, g, texts.get(task, ''))[1])
            for s in raw.get('steps', []):
                if len(s.get('tool_calls') or []) > 1:
                    n_steps += 1
                    n_calls += len(s['tool_calls'])
        R.part7(label, kept, rows, (raw_every, n_steps, n_calls))


if __name__ == '__main__':
    main()
