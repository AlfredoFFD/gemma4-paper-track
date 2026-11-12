"""Pre-registration 25: the place of the list (arms KH, KE and EL on the paused steps of 03 that end with a file view).

Usage: py -I -X utf8 analysis/analyze_25.py [<run_dir>] [--states analysis/fork_states_d/states.jsonl]
                                            [--manifest analysis/fork_states_p/manifest.json]
<run_dir> (default analysis/results/25/forks) holds results.jsonl of the run: one row per replay, written by the
one-step runner (analysis/modal_g/forks_25_modal.py). A row belongs to the record with its task, run and fork; a
record's fork is "<03's fork>:<arm>" (analysis/make_states_25.py), in the run "<03's fork>:<arm>:<seed>" (the
launcher writes each record once per pass, seed-major), so the row's step is the state of 03 with that
task, run and fork in analysis/fork_states_d/states.jsonl, and its arm is the record's arm. Records KH and KE ran
under the runner's arm A, record EL under the runner's arm EL. A row that carries `skip` is a cell entered as finished
before the run, not a replay; a row whose runner arm is not its record's, or whose seed is not 1 or 2, is outside the
design; both are counted and not read.

Outcome (registered): reads a neighbor's code, the outcome of 03: the next call reads, edits or shows lines of a listed
true neighbor in a file not opened before (gates_c.any_true: analyze_b.py's rule, fork_states.touches with the
harness's caps). Every arm is scored on the same spans, those of the states file. Beside it, without a rule: opens the
neighbor's file (mangled_sensitivity.opens_listed_file). Interface failures (gates_c.failure: runner error, no call,
unknown tool, malformed arguments) are excluded and counted by arm. A (step, seed) cell is complete if all three
arms gave a usable replay at that seed. A step enters with the mean of its outcome over its complete cells, per arm,
the same cells for every arm. The rules apply if at least 200 steps have at least one complete cell; the script prints
how many steps have one complete cell and how many two, and beside the registered contrasts, without a rule, the same
contrasts on seed 1 alone.
Intervals: 95% bootstrap clustered by step, 2,000 resamples, seed 0 (analyze_forks.boot_ci and diff_ci; the steps
in sorted order), with the interval clustered by task printed beside it.
Gate: (a) at least 80% of the replays attempted in each arm hold a usable tool call; (b) EL's rate on the steps with
a complete cell lies
within [3.81, 9.19] percent, the union of arm E's stored intervals at seeds 1 and 2 on the steps that end with a file
view in the runs of 03 and 08 (analysis/explore_place_reference.py, stored output
analysis/results/explore_place_reference.txt). If the gate fails, no rule is read.
Rules: K1 = KE minus KH, "the effect holds in the push's place" if the interval lies above zero, otherwise "not
detected". K2 = EL minus KE, "the place matters" if the interval lies above zero, otherwise "not detected".
Readings fixed before the data: see READINGS. No rule: EL minus KH, the contrasts on opening the file, and every
estimate on the steps whose queried node overlaps the lines the last read showed (the manifest's flag).
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import FAILURES, any_true, failure, load_rows, load_states  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

ARMS = ('KH', 'KE', 'EL')
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL'}
SEEDS = (1, 2)
MIN_COMPLETE = 200
GATE_USABLE = 0.80
GATE_UNION = (0.0381, 0.0919)       # analysis/results/explore_place_reference.txt: E at seeds 1 and 2, 03 and 08
K1_WORDS = ("the effect holds in the push's place", 'not detected')
K2_WORDS = ('the place matters', 'not detected')
READINGS = {
    (False, True): "an address placed after a file's content is not acted on as it is in a note; the place of the list "
                   "can explain why the whole runs of 23 showed no effect",
    (True, False): 'the address effect is there in the push\'s place, so the place of the list does not explain the '
                   'null of 23',
    (True, True): 'the address effect is there in the push\'s place, so the place of the list does not explain the '
                  'null of 23; K2 is also met: the place lowers the effect without removing it',
    (False, False): 'undecided',
}


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def by_task(table):
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return dict(out)


def record_of(row):
    """(03's fork, record arm) from a row's fork "<fork>:<arm>:<seed>" (or "<fork>:<arm>"), or None."""
    parts = str(row.get('fork', '')).split(':')
    if len(parts) == 3:                                  # the launcher's fork: "<fork>:<arm>:<seed of the pass>"
        if parts[2] != str(row.get('seed')):
            return None
    elif len(parts) != 2:
        return None
    try:
        return int(parts[0]), parts[1]
    except ValueError:
        return None


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir', nargs='?', default=str(HERE / 'results' / '25' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    ap.add_argument('--manifest', default=str(HERE / 'fork_states_p' / 'manifest.json'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run = Path(args.run_dir)
    manifest = json.load(open(args.manifest, encoding='utf-8'))
    states = load_states(args.states)
    design = {}                                          # step key -> manifest flags
    for sid, f in manifest['steps'].items():
        task, r, k = sid.split('|')
        design[(task, int(r[1:]), int(k[1:]))] = f
    want_md5 = manifest['inputs_md5']['analysis/fork_states_d/states.jsonl']

    print('PRE-REGISTRATION 25: THE PLACE OF THE LIST (arms KH, KE, EL; seeds 1 and 2)')
    print(f'  states file {Path(args.states).name}: md5 {md5(args.states)} '
          f'({"as in the manifest" if md5(args.states) == want_md5 else "NOT the manifest md5 " + want_md5}); '
          f'records file of the manifest: md5 {manifest["md5"]}; steps of the design: {len(design)}')
    for name in ('platform_actual.json', 'versions_25.json', 'versions.json'):
        p = run / name
        if p.exists():
            v = json.load(open(p, encoding='utf-8'))
            keep = {k: v[k] for k in ('harness_variant', 'harness_as_registered', 'packages_after_run', 'gpu',
                                      'started_utc', 'states_file_md5', 'runner_md5', 'replays_planned') if k in v}
            print(f'  {name}: {json.dumps(keep)}')
        else:
            print(f'  {name}: not in the run directory')

    rows = load_rows(run / 'results.jsonl')
    n_skip = n_out = 0
    seen = collections.Counter()
    n_arm = collections.Counter()
    fail = collections.Counter()
    usable = collections.defaultdict(dict)
    for r in rows:
        if r.get('skip'):
            n_skip += 1
            continue
        rec = record_of(r)
        key = (r['task'], r['run'], rec[0]) if rec else None
        if rec is None or rec[1] not in ARMS or r['arm'] != RUNNER_ARM[rec[1]] or r.get('seed') not in SEEDS \
                or key not in design:
            n_out += 1
            continue
        arm = rec[1]
        seen[(key, arm, r['seed'])] += 1
        if seen[(key, arm, r['seed'])] > 1:              # a cell twice: the first row counts
            continue
        n_arm[arm] += 1
        kind = failure(r)
        if kind:
            fail[(arm, kind)] += 1
        else:
            usable[key][(arm, r['seed'])] = r
    dup = sum(1 for v in seen.values() if v > 1)
    print()
    print('1. Steps and completeness')
    print(f'  rows read: {len(rows)}; cells entered as finished (skip, not read): {n_skip}; rows outside the design: '
          f'{n_out}; cells with more than one row (the first counts): {dup}')
    print(f'  replays by arm: {dict((a, n_arm[a]) for a in ARMS)} (planned per arm: {len(design) * len(SEEDS)})')
    cells = {(k, s) for k, v in usable.items() for s in SEEDS if all((a, s) in v for a in ARMS)}
    seeds_of = collections.defaultdict(list)
    for k, s in sorted(cells):
        seeds_of[k].append(s)
    complete = sorted(seeds_of)                          # steps with at least one complete cell
    with_row = {k for (k, _a, _s) in seen}
    n_one = sum(1 for v in seeds_of.values() if len(v) == 1)
    n_two = sum(1 for v in seeds_of.values() if len(v) == 2)
    print(f'  steps with at least one replay: {len(with_row)} of {len(design)}; complete (step, seed) cells (KH, KE and '
          f'EL usable at that seed): {len(cells)} (seed 1: {sum(1 for _k, s in cells if s == 1)}, seed 2: '
          f'{sum(1 for _k, s in cells if s == 2)})')
    print(f'  steps with at least one complete cell: {len(complete)} in {len({k[0] for k in complete})} tasks (rule: at '
          f'least {MIN_COMPLETE}); with one complete cell: {n_one}; with two: {n_two}')

    print()
    print('2. Interface failures by arm (excluded; usable share over all replays attempted)')
    gate_a = True
    for a in ARMS:
        kinds = {k: fail[(a, k)] for k in FAILURES if fail[(a, k)]}
        n_fail = sum(kinds.values())
        share = (n_arm[a] - n_fail) / n_arm[a] if n_arm[a] else None
        gate_a &= share is not None and share >= GATE_USABLE
        print(f'  {a}: {n_fail} of {n_arm[a]} {kinds}; usable share '
              + (f'{100 * share:.2f}%' if share is not None else 'n/a'))

    score = {}
    for k, s in cells:
        st = states[k]
        for a in ARMS:
            call = usable[k][(a, s)]['next_call']
            score[('reads', k, a, s)] = any_true(st, call)
            score[('opens', k, a, s)] = int(bool(opens_listed_file(st, call)))

    def step_tables(keys, seeds):
        """{outcome: {arm: {step: [mean over the step's complete cells at these seeds]}}} and the replay counts; the
        same cells for every arm."""
        tab = {y: {a: {} for a in ARMS} for y in ('reads', 'opens')}
        cnt = {y: {a: [0, 0] for a in ARMS} for y in ('reads', 'opens')}
        for k in keys:
            ss = [s for s in seeds if (k, s) in cells]
            if not ss:
                continue
            for y in tab:
                for a in ARMS:
                    vals = [score[(y, k, a, s)] for s in ss]
                    tab[y][a][k] = [sum(vals) / len(vals)]
                    cnt[y][a][0] += sum(vals)
                    cnt[y][a][1] += len(vals)
        return tab, cnt

    tab, cnt = step_tables(complete, SEEDS)
    reads, opens = tab['reads'], tab['opens']
    tab1, cnt1 = step_tables(complete, (1,))

    def rates(tb, cn, indent='    '):
        for label, y in (('reads a neighbor\'s code (registered outcome)', 'reads'),
                         ('opens the neighbor\'s file (no rule)', 'opens')):
            print(f'{indent[:-2]}{label}:')
            for a in ARMS:
                t_ = boot_ci(tb[y][a])
                tt = boot_ci(by_task(tb[y][a]))
                by_t = 'n/a' if tt[0] is None else f'[{100 * tt[1]:.2f}, {100 * tt[2]:.2f}]'
                print(f'{indent}{a}: {pct(t_)}; by task {by_t} | {cn[y][a][0]}/{cn[y][a][1]} replays in '
                      f'{len(tb[y][a])} steps')

    print()
    print('3. Rates (each step enters with the mean of its outcome over its complete cells; percent, 95% interval by '
          'step; by task beside it)')
    rates(tab, cnt)

    print()
    print('4. Gate')
    print(f'  (a) every arm holds a usable tool call in at least {100 * GATE_USABLE:.0f}% of the replays attempted: '
          f'{"PASS" if gate_a else "FAIL"}')
    el = boot_ci(reads['EL'])[0] if complete else None
    gate_b = el is not None and GATE_UNION[0] <= el <= GATE_UNION[1]
    print(f'  (b) EL\'s rate on the steps with a complete cell, ' + (f'{100 * el:.2f}%' if el is not None else 'n/a')
          + f', lies within [{100 * GATE_UNION[0]:.2f}, {100 * GATE_UNION[1]:.2f}] (arm E at seeds 1 and 2 on the steps '
          f'that end with a file view, union of 03 and 08): {"PASS" if gate_b else "FAIL"}')
    gate = gate_a and gate_b
    enough = len(complete) >= MIN_COMPLETE
    if not gate:
        print('  the gate failed: no rule is read; everything below is EXPLORATORY')
    elif not enough:
        print(f'  fewer than {MIN_COMPLETE} steps with a complete cell: no rule is read; everything below is EXPLORATORY')
    readable = gate and enough

    def contrast(tb, a, b):
        return diff_ci(tb[a], tb[b]), diff_ci(by_task(tb[a]), by_task(tb[b]))

    def show(label, pair):
        d, dt = pair
        by_t = 'n/a' if dt[0] is None else f'[{100 * dt[1]:+.2f}, {100 * dt[2]:+.2f}]'
        print(f'  {label}: {dpt(d)}; by task {by_t}')
        return d

    print()
    print('5. Rules (reads a neighbor\'s code; points, 95% interval by step; by task beside it). Beside each, without a '
          'rule: the same contrast on seed 1 alone')
    k1 = show('K1, the effect in the push\'s place, KE minus KH', contrast(reads, 'KE', 'KH'))
    show('  seed 1 alone, no rule', contrast(tab1['reads'], 'KE', 'KH'))
    k2 = show('K2, the place, EL minus KE', contrast(reads, 'EL', 'KE'))
    show('  seed 1 alone, no rule', contrast(tab1['reads'], 'EL', 'KE'))
    if readable and k1[0] is not None and k2[0] is not None:
        m1, m2 = k1[1] > 0, k2[1] > 0
        print(f'  K1 verdict: {K1_WORDS[0] if m1 else K1_WORDS[1]}')
        print(f'  K2 verdict: {K2_WORDS[0] if m2 else K2_WORDS[1]}')
        print()
        print('6. The reading fixed before the data')
        print(f'  {READINGS[(m1, m2)]}')
    else:
        why = 'the gate failed' if not gate else (f'fewer than {MIN_COMPLETE} steps with a complete cell' if not enough
                                                 else 'no estimate')
        print(f'  verdicts withheld ({why}): the intervals above are EXPLORATORY')
        print()
        print('6. The reading fixed before the data: not read')

    print()
    print('7. No rule: reported')
    show('EL minus KH, reads a neighbor\'s code', contrast(reads, 'EL', 'KH'))
    show('  seed 1 alone', contrast(tab1['reads'], 'EL', 'KH'))
    for a, b in (('KE', 'KH'), ('EL', 'KE'), ('EL', 'KH')):
        show(f'{a} minus {b}, opens the neighbor\'s file', contrast(opens, a, b))
    print(f'  seed 1 alone, the {len(tab1["reads"]["KH"])} steps with a complete seed-1 cell:')
    rates(tab1, cnt1, indent='      ')
    sub = [k for k in complete if design[k]['node_overlaps_shown_lines']]
    print(f'  the steps with a complete cell whose queried node overlaps the lines the last read showed: {len(sub)} of '
          f'{len(complete)} ({len({k[0] for k in sub})} tasks; {sum(f["node_overlaps_shown_lines"] for f in design.values())} '
          f'such steps in the design)')
    if sub:
        ts, cs = step_tables(sub, SEEDS)
        rates(ts, cs, indent='      ')
        for a, b in (('KE', 'KH'), ('EL', 'KE'), ('EL', 'KH')):
            show(f'  {a} minus {b} on that subset, reads', contrast(ts['reads'], a, b))


if __name__ == '__main__':
    main()
