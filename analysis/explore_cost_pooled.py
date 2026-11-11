"""EXPLORATORY. Experiments 18 (seed 2, 40 tasks) and 22 (seed 3, the tasks run so far) together: what the arms
read, and where their first reads of a named file start, over both seeds.

Everything is computed by analysis/explore_cost_18.py and analysis/explore_read_starts.py; this script only puts
the two experiments side by side and pools the arms they share (N, ON, OA). A task that has a run in both seeds
enters with both; intervals are 95% bootstrap intervals over tasks, a task's runs resampled together (2,000
resamples, seed 0). Arm OF exists in 22 only and is given beside the pooled arms on the tasks of 22.

Printed: per seed and pooled, the mean LINES READ per run (the lines returned by a run's reads, with repetition)
and the paired mean differences between arms; and the first READS of a file of the note by where they start
(line 1, or a line the run had been given or had found: the classes TOP and ADDRESSED of explore_read_starts);
and, from the manifest of the notes (analysis/oracle_18/manifest.json), how the tasks that have a run in 22 differ
from the tasks of 18 that have none.

Usage:
    python analysis/explore_cost_pooled.py
Output is stored in analysis/results/22/explore_cost_pooled.txt.
"""
import collections
import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_read_starts as R  # noqa: E402
from explore_reach_22 import LABELS, load_runs, of_note  # noqa: E402

EXPERIMENTS = (('18', '2'), ('22', '3'))
ARMS = ('N', 'ON', 'OF', 'OA')


def collect():
    """{(experiment, arm, task): {'lines', 'reads', 'first': Counter of classes of first reads of note files}}"""
    gold = R.gold_regions()
    texts = R.task_texts()
    out = {}
    for exp, _seed in EXPERIMENTS:
        root = HERE / 'results' / exp
        arms = [a for a in ARMS if (root / a).is_dir()]
        if not arms:
            continue
        for (task, cond, _s), r in sorted(load_runs(root, arms).items()):
            if cond not in arms or r[0] is None or not gold.get(task):
                continue
            places = R.oracle_places(task)
            note = places if cond == 'OA' else (of_note(task) or ()) if cond == 'OF' else ()
            reads, _regs, _fr, _more = R.analyse(R.one_call_steps(r[0]), gold[task], texts.get(task, ''), places, cond, note)
            ok = [x for x in reads if 'range' in x and x['cls'] not in ('FAILED', 'OWN FILE')]
            files = {R.norm(x['file']) for x in places or ()}
            first = collections.Counter(
                ('NOTE' if x['cls'] == 'ADDRESSED' and 'NOTE' in x['kinds'] else x['cls'])
                for x in reads if x['cls'] in R.CLASSES and x['first'] and x['f'] in files)
            out[(exp, cond, task)] = {'lines': sum(x['range'][1] - x['range'][0] + 1 for x in ok), 'reads': len(ok),
                                      'first': first}
    return out


def boot(by_task, n=2000, seed=0):
    """Mean over all values, with a 95% interval over tasks (by_task: task -> list of values)."""
    tasks = sorted(by_task)
    flat = [v for t in tasks for v in by_task[t]]
    if not flat:
        return None
    rng = random.Random(seed)
    boots = []
    for _ in range(n):
        vals = [v for t in (rng.choice(tasks) for _ in tasks) for v in by_task[t]]
        boots.append(statistics.mean(vals))
    boots.sort()
    return statistics.mean(flat), boots[int(0.025 * n)], boots[int(0.975 * n) - 1], len(flat), len(tasks)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    data = collect()
    print('EXPERIMENTS 18 AND 22 TOGETHER: WHAT THE ARMS READ AND WHERE THEIR FIRST READS OF A NAMED FILE START (EXPLORATORY)')
    print()
    print('1. LINES READ per run, mean (runs)')
    for exp, seed in EXPERIMENTS:
        arms = [a for a in ARMS if any(k[0] == exp and k[1] == a for k in data)]
        print(f'   experiment {exp} (seed {seed}): ' + '; '.join(
            f'{a} {statistics.mean(v["lines"] for k, v in data.items() if k[0] == exp and k[1] == a):.1f} '
            f'({sum(1 for k in data if k[0] == exp and k[1] == a)})' for a in arms))
    print()
    print('2. LINES READ, paired by task and seed: mean difference [95% over tasks] (pairs, tasks)')
    for a, b in (('N', 'ON'), ('N', 'OA'), ('ON', 'OA'), ('ON', 'OF'), ('OF', 'OA'), ('N', 'OF')):
        parts = []
        pooled = collections.defaultdict(list)
        for exp, seed in EXPERIMENTS:
            d = collections.defaultdict(list)
            for (e, arm, task), v in data.items():
                if e == exp and arm == b and (exp, a, task) in data:
                    d[task].append(v['lines'] - data[(exp, a, task)]['lines'])
                    pooled[task].append(v['lines'] - data[(exp, a, task)]['lines'])
            r = boot(d)
            if r:
                parts.append(f'seed {seed}: {r[0]:+.1f} [{r[1]:+.1f}, {r[2]:+.1f}] ({r[3]}, {r[4]})')
        r = boot(pooled)
        if r and len(parts) > 1:
            parts.append(f'both seeds: {r[0]:+.1f} [{r[1]:+.1f}, {r[2]:+.1f}] ({r[3]}, {r[4]})')
        if parts:
            print(f'   {b} minus {a}: ' + '; '.join(parts))
    print()
    print('3. First READS of a file of the note, by where they start: line 1 (TOP); a line of the note (NOTE); a line')
    print('   the run found by itself (ADDRESSED); anything else')
    for exp, seed in EXPERIMENTS + (('both', 'both'),):
        for a in ARMS:
            tot = collections.Counter()
            for (e, arm, _task), v in data.items():
                if arm == a and (exp == 'both' or e == exp):
                    tot.update(v['first'])
            n = sum(tot.values())
            if not n or (exp == 'both' and a == 'OF'):
                continue
            other = n - tot['TOP'] - tot['NOTE'] - tot['ADDRESSED']
            print(f'   {"both seeds" if exp == "both" else "seed " + seed}, {LABELS[a]}: first reads {n}; TOP {tot["TOP"]}; NOTE {tot["NOTE"]}; '
                  f'ADDRESSED {tot["ADDRESSED"]}; other {other}')

    print()
    print("4. The tasks with a run in 22 against the tasks of 18 without one (from the manifest of the notes)")
    with open(HERE / "oracle_18" / "manifest.json", encoding="utf-8") as f:
        man = json.load(f)["tasks"]
    with open(HERE / "oracle_18" / "tasks_18.txt", encoding="utf-8") as f:
        order = [line.strip() for line in f if line.strip()]
    t22 = {k[2] for k in data if k[0] == "22"}
    t18 = {k[2] for k in data if k[0] == "18"}
    print("   positions in the task list of 18 (first is 1) of the tasks with a run in 22: "
          + ", ".join(str(order.index(t) + 1) for t in sorted(t22, key=order.index)))
    for name, sel in (("with a run in 22", sorted(t22)), ("of 18 without a run in 22", sorted(t18 - t22))):
        if not sel:
            continue
        regs = [int(man[t]["changed_regions"]) for t in sel]
        print(f"   tasks {name}: {len(sel)}; changed regions, median {statistics.median(regs):g}, sum {sum(regs)}; "
              f"fixes in one file {sum(int(man[t]['modified_files']) == 1 for t in sel)}; "
              f"fixes of four or more regions {sum(r >= 4 for r in regs)}")


if __name__ == '__main__':
    main()
