"""Where the read lands, in the runs after experiment B (EXPLORATORY; no registered rule).

For each arm of a run: how often the first call is a read_file on the file of an unopened true neighbor ("opens a
listed file"), how often that read covers a listed neighbor in that file (the registered touch), and the share of the
second among the first. Experiment B's version of this is Section S3 of analysis/results/rederive_s5.txt.

Also, for the runs with a rewired list: how often the rewired entries are touched with the list shown (RE) and
without any list (A), on the same states.

Usage: py -I -X utf8 analysis/explore_mechanism.py
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey, touch_map  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

SEEDS = (1, 2, 3)
RUNS = (('Tool-channel run, Gemma-4-31B', 'd1', ('P', 'PE', 'E')),
        ('Experiment C run, Gemma-4-31B', 'c', ('H', 'ES', 'EL', 'E', 'Ep')),
        ('Gemma 4 26B-A4B', 'd2_26b', ('A', 'H', 'E', 'RE')),
        ('Gemma 4 E4B', 'd2_e4b', ('A', 'H', 'E', 'RE')),
        ('Rendering run, Gemma-4-31B', 'w', ('A', 'Aw', 'Hw', 'Ew')))


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def ratio_ci(num, den, n=2000, seed=0):
    """Share of `num` among `den` (both {state: [0/1]}), bootstrap over states."""
    import random
    keys = sorted(den)
    a = sum(sum(num[k]) for k in keys)
    b = sum(sum(den[k]) for k in keys)
    if not b:
        return None, None, None
    rng = random.Random(seed)
    boots = []
    for _ in range(n):
        s = [rng.choice(keys) for _ in keys]
        bb = sum(sum(den[k]) for k in s)
        if bb:
            boots.append(sum(sum(num[k]) for k in s) / bb)
    boots.sort()
    return a / b, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    print('Where the read lands (EXPLORATORY). Complete states of each run; 95% intervals clustered by state.')
    for title, name, arms in RUNS:
        d = HERE / 'results' / name / 'forks'
        if not (d / 'results.jsonl').exists():
            print(f'\n{title}: no results yet')
            continue
        usable = collections.defaultdict(dict)
        for r in load_rows(d / 'results.jsonl'):
            if r['arm'] in arms and r['seed'] in SEEDS and not failure(r):
                usable[skey(r)][(r['arm'], r['seed'])] = r
        need = {(a, s) for a in arms for s in SEEDS}
        complete = sorted(k for k, v in usable.items() if need <= set(v))
        print(f'\n{title}: {len(complete)} complete states')
        rew = {a: collections.defaultdict(list) for a in arms}
        for a in arms:
            opened = collections.defaultdict(list)
            hit_open = collections.defaultdict(list)
            hit = collections.defaultdict(list)
            for k in complete:
                for s in SEEDS:
                    call = usable[k][(a, s)]['next_call']
                    o = int(opens_listed_file(states[k], call))
                    h = any_true(states[k], call)
                    opened[k].append(o)
                    hit[k].append(h)
                    hit_open[k].append(int(o and h))
                    t = touch_map(states[k], call, states[k].get('rewired_entries', []), states[k].get('rewired_spans', {}))
                    rew[a][k].append(int(any(bool(v) and v != 'graph' for v in t.values())))
            no = sum(sum(v) for v in opened.values())
            nh = sum(sum(v) for v in hit_open.values())
            print(f'  {a:3s}: opens a listed file {pct(boot_ci(opened))} | reaches a listed neighbor {pct(boot_ci(hit))} | '
                  f'of the reads that open a listed file, cover a listed neighbor: {pct(ratio_ci(hit_open, opened))} ({nh}/{no})')
        if 'RE' in arms and 'A' in arms:
            for a in arms:
                vals = [v for vs in rew[a].values() for v in vs]
                print(f'  rewired entries touched under {a}: {pct(boot_ci(rew[a]))} | {sum(vals)}/{len(vals)}')
            print(f'  rewired entries, RE - A: {dpt(diff_ci(rew["RE"], rew["A"]))}')


if __name__ == '__main__':
    main()
