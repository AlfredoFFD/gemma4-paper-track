"""Pre-registration 23 beside a shipped run of the same seed (EXPLORATORY; a count, no rule).

The launch of 23 ran the two pushed arms (PH: neighbor lists as names; PE: with file and line range) and no arm
without lists. The control arm of pre-registration 18 is the harness as shipped on 40 of the same 103 tasks with the
same seed (2), wheels and budgets, in another launch. This script counts resolved tasks on those 40 tasks in the three
runs, pair by pair, and on the other 63 tasks in the two pushed arms beside the shipped run of 14 (seed 1). It reads
only the stored task results; the 40 tasks were chosen for 18 because the shipped run of 14 had not been shown every
changed region, so they are harder than the rest.

Usage: py -I -X utf8 analysis/explore_same_seed_23.py > analysis/results/23/explore_same_seed_23.txt
"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent / 'results'


def load(rel):
    out = {}
    for line in (R / rel / 'task_results.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            out[r['instance_id']] = bool(r.get('resolved'))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    n18, n14 = load('18/N/seed2'), load('14/N/seed1')
    pe, ph = load('23/PE/seed2'), load('23/PH/seed2')
    same = sorted(set(n18) & set(pe) & set(ph))
    rest = sorted((set(pe) & set(ph) & set(n14)) - set(n18))
    print('PRE-REGISTRATION 23 BESIDE A SHIPPED RUN OF THE SAME SEED (EXPLORATORY; no rule; other launches)')
    print(f'tasks with a shipped run of seed 2 (the control of 18), PE and PH: {len(same)}')
    print(f'   resolved: shipped (18, seed 2) {sum(n18[t] for t in same)}; PH {sum(ph[t] for t in same)}; '
          f'PE {sum(pe[t] for t in same)}; shipped (14, seed 1) {sum(n14[t] for t in same)}')
    for a, b, na, nb in ((pe, n18, 'PE', 'shipped (18)'), (ph, n18, 'PH', 'shipped (18)'), (pe, ph, 'PE', 'PH')):
        only_a = sum(a[t] and not b[t] for t in same)
        only_b = sum(b[t] and not a[t] for t in same)
        print(f'   {na} against {nb}: resolved in {na} only {only_a}, in {nb} only {only_b}')
    print(f'the other tasks of the 103: {len(rest)}')
    print(f'   resolved: PH {sum(ph[t] for t in rest)}; PE {sum(pe[t] for t in rest)}; '
          f'shipped (14, seed 1) {sum(n14[t] for t in rest)}')


if __name__ == '__main__':
    main()
