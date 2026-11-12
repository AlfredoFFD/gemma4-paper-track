"""EXPLORATORY, written before any replay of pre-registration 25: the stored arms E and H (and EL) on the paused steps
that end with a file view, and the reference interval the gate of 25 uses.

Usage: py -I -X utf8 analysis/explore_place_reference.py   (no arguments; prints the report)
Stored output: analysis/results/explore_place_reference.txt is exactly this script's stdout (LF line ends).

Runs read (all stored in this repository):
  03  pre-registration 03 on the Sep 30 wheels: analysis/results/v5, v6 and v8 (/forks/results.jsonl; arms A, P, P',
      H, H' / D, D', E / RD, RE), the run analysis/analyze_b.py reads; a step is complete if all ten arms gave a usable
      call at seeds 1 to 3 (analyze_b's rule; 388 steps);
  08  pre-registration 08, part "one step", on the Oct 12 wheels: analysis/results/g_onestep/forks (arms H and E);
      complete if both arms are usable at seeds 1 to 3 (analyze_g's rule; 399 steps);
  04  pre-registration 04 (experiment C) on the Sep 30 wheels: analysis/results/c/forks (arms Ep, EL, ES, E, H);
      complete if all five arms are usable at seeds 1 to 3 (gates_c's rule). The only stored run with arm EL.
Steps that end with a file view: make_states_25.ends_with_ok_read (the paused history ends with a read_file result of
status ok), on analysis/fork_states_d/states.jsonl. For each run, the complete steps of its own rule that end with a
file view; "seeds 1 and 2" are the same steps with the rows of seed 3 left out.
Scorer and exclusions: gates_c.failure and gates_c.any_true (the registered outcome of 03: the next call reads, edits
or shows lines of a listed true neighbor in a file not opened before; fork_states.touches with the harness's caps),
the same rule analyze_b.py applies in its main. Intervals: analyze_forks.boot_ci and diff_ci, clustered by step,
2,000 resamples, seed 0; clustered by task beside them for the differences. boot_ci resamples the steps in the order
its table lists them (diff_ci sorts them first), so a rate's interval depends on that order: each run's steps are
listed as its stored analysis lists them (03: analyze_b, by the first usable row in v5, v6, v8; 08: analyze_g, sorted;
04: gates_c, sorted), and for 03 and 08 the other order is printed beside, not used by the gate.
Before the subsets, the script reproduces the stored all-step numbers of 03 (analysis/results/analyze_b.txt) and 08
(analysis/results/g/analyze_g.txt) with this scoring.
The gate's interval: the union of arm E's intervals at seeds 1 and 2 on the steps that end with a file view, in the
runs of 03 and 08.
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402
from make_states_25 import ends_with_ok_read  # noqa: E402

RES = HERE / 'results'
RUNS = {  # order: the order of the steps that analyze_forks.boot_ci resamples, as the stored analysis of the run has it
    '03': {'dirs': ('v5', 'v6', 'v8'), 'arms': ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE'), 'order': 'rows',
           'label': 'pre-registration 03, Sep 30 wheels (analysis/results/v5 + v6 + v8)',
           'want': {'E': '8.25 [5.76, 10.91]', 'H': '2.75 [1.37, 4.30]', 'E-H': '+5.50 [+3.44, +7.65]', 'n': 388},
           'want_src': 'analysis/results/analyze_b.txt'},
    '08': {'dirs': ('g_onestep',), 'arms': ('H', 'E'), 'order': 'sorted',
           'label': 'pre-registration 08, part "one step", Oct 12 wheels (analysis/results/g_onestep)',
           'want': {'E': '8.52 [6.18, 11.19]', 'H': '2.92 [1.50, 4.59]', 'E-H': '+5.60 [+3.76, +7.77]', 'n': 399},
           'want_src': 'analysis/results/g/analyze_g.txt'},
    '04': {'dirs': ('c',), 'arms': ('Ep', 'EL', 'ES', 'E', 'H'), 'order': 'sorted',
           'label': 'pre-registration 04 (experiment C), Sep 30 wheels (analysis/results/c)', 'want': None},
}
SHOW = ('H', 'EL', 'E')
SEEDS_ALL, SEEDS_12 = (1, 2, 3), (1, 2)
OUT = []


def add(s=''):
    OUT.append(s)


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def by_task(table):
    out = collections.defaultdict(list)
    for k, v in table.items():
        out[k[0]] += v
    return dict(out)


def raw(table):
    vals = [x for v in table.values() for x in v]
    return f'{sum(vals)} of {len(vals)}'


def load_run(name, states):
    spec = RUNS[name]
    usable = collections.defaultdict(dict)
    rows = []
    for d in spec['dirs']:
        rows += load_rows(RES / d / 'forks' / 'results.jsonl')
    for r in rows:
        if r['arm'] in spec['arms'] and r['seed'] in SEEDS_ALL and not failure(r):
            usable[skey(r)][(r['arm'], r['seed'])] = r
    need = {(a, s) for a in spec['arms'] for s in SEEDS_ALL}
    complete = [k for k, v in usable.items() if need <= set(v)]   # first usable row first, as analyze_b orders them
    if spec['order'] == 'sorted':
        complete = sorted(complete)
    score = {}
    for k in complete:
        for (a, s), r in usable[k].items():
            score[(k, a, s)] = any_true(states[k], r['next_call'])
    return rows, usable, complete, score


def table(score, keys, arm, seeds):
    return {k: [score[(k, arm, s)] for s in seeds] for k in keys}


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    except (AttributeError, ValueError):
        pass
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    read_end = {k for k, s in states.items() if ends_with_ok_read(s)}
    add('EXPLORATORY, written before any replay of pre-registration 25. The stored arms E and H (and EL) on the paused')
    add('  steps that end with a file view, and the reference interval of 25\'s gate. Outcome: the registered one of 03')
    add('  (gates_c.any_true: the next call reads, edits or shows lines of a listed true neighbor in a file not opened')
    add('  before). Percent of replays, 95% bootstrap by step (2,000 resamples, seed 0); differences in points.')
    add('')
    add(f'States: analysis/fork_states_d/states.jsonl, {len(states)} paused steps; {len(read_end)} end with a read_file '
        f'result of status ok ({len({k[0] for k in read_end})} tasks), {len(states) - len(read_end)} do not.')
    union = []
    for name in ('03', '08', '04'):
        spec = RUNS[name]
        rows, usable, complete, score = load_run(name, states)
        fail = collections.Counter(r['arm'] for r in rows if r['arm'] in spec['arms'] and failure(r))
        add('')
        add(f'{name}: {spec["label"]}')
        add(f'  {len(rows)} rows; interface failures by arm (excluded): {dict(sorted(fail.items()))}; complete steps '
            f'(arms {", ".join(spec["arms"])}, seeds 1 to 3): {len(complete)}')
        arms = [a for a in SHOW if a in spec['arms']]
        if spec['want']:
            got = {a: pct(boot_ci(table(score, complete, a, SEEDS_ALL))) for a in ('E', 'H')}
            got['E-H'] = dpt(diff_ci(table(score, complete, 'E', SEEDS_ALL), table(score, complete, 'H', SEEDS_ALL)))
            same = all(got[k] == spec['want'][k] for k in ('E', 'H', 'E-H')) and len(complete) == spec['want']['n']
            add(f'  reproduction on all {len(complete)} complete steps, seeds 1 to 3: E {got["E"]}, H {got["H"]}, '
                f'E minus H {got["E-H"]} (stored in {spec["want_src"]}: E {spec["want"]["E"]}, H {spec["want"]["H"]}, '
                f'E minus H {spec["want"]["E-H"]}, {spec["want"]["n"]} steps): {"reproduced" if same else "NOT REPRODUCED"}')
        keys = [k for k in complete if k in read_end]
        add(f'  complete steps that end with a file view: {len(keys)} in {len({k[0] for k in keys})} tasks')
        for label, seeds in (('seeds 1 to 3', SEEDS_ALL), ('seeds 1 and 2', SEEDS_12)):
            tabs = {a: table(score, keys, a, seeds) for a in arms}
            add(f'  {label}:')
            for a in arms:
                add(f'    {a:2s} {pct(boot_ci(tabs[a]))} | {raw(tabs[a])}')
            for a, b in (('E', 'H'), ('EL', 'H'), ('E', 'EL')):
                if a in tabs and b in tabs:
                    add(f'    {a} minus {b}: by step {dpt(diff_ci(tabs[a], tabs[b]))}; by task '
                        f'{dpt(diff_ci(by_task(tabs[a]), by_task(tabs[b])))}')
            if seeds == SEEDS_12 and name in ('03', '08'):
                union.append((name, boot_ci(tabs['E'])))
        if name in ('03', '08'):                   # sensitivity lines, not used by the gate
            other = sorted(keys) if spec['order'] == 'rows' else [k for k in usable if k in set(keys)]
            add(f'  not used by the gate: E at seeds 1 and 2 with the steps resampled in the other order '
                f'({"sorted" if spec["order"] == "rows" else "first usable row first"}): '
                f'{pct(boot_ci(table(score, other, "E", SEEDS_12)))}')
            need = {(a, s) for a in spec['arms'] for s in SEEDS_12}
            k12 = [k for k, v in usable.items() if need <= set(v) and k in read_end]
            k12 = sorted(k12) if spec['order'] == 'sorted' else k12
            sc = {k: [any_true(states[k], usable[k][('E', s)]['next_call']) for s in SEEDS_12] for k in k12}
            add(f'  not used by the gate: steps complete at seeds 1 and 2 alone that end with a file view: {len(k12)}; '
                f'E {pct(boot_ci(sc))} | {raw(sc)}')
    add('')
    add('Reference interval of the gate of 25: arm E at seeds 1 and 2, steps that end with a file view')
    for name, t in union:
        add(f'  {name}: E {pct(t)}')
    (n1, a), (n2, b) = union
    if a[1] <= b[2] and b[1] <= a[2]:
        lo, hi = min(a[1], b[1]), max(a[2], b[2])
        add(f'  the two intervals overlap; their union: [{100 * lo:.2f}, {100 * hi:.2f}] percent')
    else:
        add(f'  the two intervals do not overlap; their union is two pieces: [{100 * a[1]:.2f}, {100 * a[2]:.2f}] and '
            f'[{100 * b[1]:.2f}, {100 * b[2]:.2f}] percent')
    print('\n'.join(OUT))


if __name__ == '__main__':
    main()
