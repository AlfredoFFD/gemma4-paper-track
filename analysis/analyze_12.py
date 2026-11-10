"""Pre-registration 12: a list that gives each neighbor's file and no line range (arm EPATH).

Usage: py -I -X utf8 analysis/analyze_12.py <run_dir> [--ref <run_dir of pre-registration 04>]

<run_dir> holds results.jsonl of the new run (arm EPATH, 407 states, seeds 1 to 3). The reference arms H (bare
names), EL (name, file, line range) and E (the same with the first definition line) come from the run of
pre-registration 04 on the same platform, harness wheels, states and seeds (default analysis/results/c/forks).

Everything is imported from frozen or tracked code: the interface-failure rule and the registered outcome
(gates_c.failure, gates_c.any_true), the file-level outcome (mangled_sensitivity.opens_listed_file), where a first
read of a listed neighbor's file starts (explore_first_reads.read_stats) and the bootstrap (analyze_forks).
"""
import argparse
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from explore_first_reads import read_stats  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

NEW, REF = 'EPATH', ('H', 'EL', 'E')
RULE_ARMS = ('H', 'EL', NEW)        # a state is complete if these three are usable for every seed
SEEDS = (1, 2, 3)
MIN_COMPLETE, MIN_READS, P3_MAX = 200, 30, 0.05


def usable_rows(path, arms):
    out = collections.defaultdict(dict)
    n = collections.Counter()
    fail = collections.Counter()
    for r in load_rows(path):
        if r['arm'] not in arms or r['seed'] not in SEEDS:
            continue
        n[r['arm']] += 1
        kind = failure(r)
        if kind:
            fail[(r['arm'], kind)] += 1
        else:
            out[skey(r)][(r['arm'], r['seed'])] = r
    return out, n, fail


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def by_task(table):
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--ref', default=str(HERE / 'results' / 'c' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(args.states)   # the scored fields are those of the 407 states; EPATH adds a note only
    new, n_new, f_new = usable_rows(Path(args.run_dir) / 'results.jsonl', (NEW,))
    ref, n_ref, f_ref = usable_rows(Path(args.ref) / 'results.jsonl', REF)

    print('PRE-REGISTRATION 12: a file without lines (arm EPATH), against the arms of pre-registration 04\'s run')
    print()
    for arm, n, f in [(NEW, n_new, f_new)] + [(a, n_ref, f_ref) for a in REF]:
        kinds = {k: v for (a, k), v in sorted(f.items()) if a == arm}
        src = 'this run' if arm == NEW else 'run of pre-registration 04'
        print(f'  arm {arm:<5} ({src}): {n[arm]} rows; interface failures {sum(kinds.values())} {kinds} (excluded)')

    def rows_of(key, arm):
        src = new if arm == NEW else ref
        return [src[key][(arm, s)] for s in SEEDS] if all((arm, s) in src.get(key, {}) for s in SEEDS) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in RULE_ARMS))
    print(f'  complete states (H, EL and EPATH usable for seeds 1 to 3): {len(complete)} of {len(states)}')
    exploratory = len(complete) < MIN_COMPLETE
    if exploratory:
        print(f'  fewer than {MIN_COMPLETE} complete states: everything below is EXPLORATORY')

    arms = [a for a in ('H', NEW, 'EL', 'E')]
    reads = {a: {} for a in arms}     # outcome 1: the next call reads a listed neighbor (registered outcome of 02 to 05)
    opens = {a: {} for a in arms}     # outcome 2: the next call opens a listed neighbor's file
    first = {a: collections.Counter() for a in arms}
    for k in complete:
        st = states[k]
        for a in arms:
            rs = rows_of(k, a)
            if rs is None:   # arm E is not required for completeness
                continue
            reads[a][k] = [int(bool(any_true(st, r['next_call']))) for r in rs]
            opens[a][k] = [int(bool(opens_listed_file(st, r['next_call']))) for r in rs]
            for r in rs:
                call = r['next_call']
                if call.get('function_name') == 'read_file' and opens_listed_file(st, call):
                    ranged, covers, _on_first = read_stats(st, call)
                    first[a]['reads'] += 1
                    first[a]['ranged'] += int(ranged)
                    first[a]['covers'] += int(covers)

    print()
    print('1. Rates on the complete states (percent of replays, 95% interval by state | hits/replays)')
    for a in arms:
        n = sum(len(v) for v in reads[a].values())
        note = '' if a != 'E' else f'   (arm E on the {len(reads[a])} of these states where it is usable)'
        print(f'  arm {a:<5} reads a listed neighbor: {pct(boot_ci(reads[a]))} | {sum(sum(v) for v in reads[a].values())}/{n}'
              f'; opens a listed neighbor\'s file: {pct(boot_ci(opens[a]))} | {sum(sum(v) for v in opens[a].values())}/{n}{note}')

    print()
    print('2. Rules (95% bootstrap by state; by task beside it)')
    d1 = diff_ci(reads['EL'], reads[NEW])
    d1t = diff_ci(by_task(reads['EL']), by_task(reads[NEW]))
    print(f'  P1, EL - EPATH on reading a listed neighbor: {dpt(d1)}; by task [{100 * d1t[1]:+.2f}, {100 * d1t[2]:+.2f}]')
    d2 = diff_ci(opens[NEW], opens['H'])
    d2t = diff_ci(by_task(opens[NEW]), by_task(opens['H']))
    print(f'  P2, EPATH - H on opening a listed neighbor\'s file: {dpt(d2)}; by task [{100 * d2t[1]:+.2f}, {100 * d2t[2]:+.2f}]')
    c = first[NEW]
    share = c['ranged'] / c['reads'] if c['reads'] else None
    print(f'  P3, first reads of a listed neighbor\'s file under EPATH that ask past line 1: {c["ranged"]} of {c["reads"]}'
          + (f' ({100 * share:.1f}%)' if share is not None else ''))
    if not exploratory:
        print('  P1 verdict: ' + ('the line range, not the path, gets the agent to the code' if d1[1] > 0
                                  else 'not detected: a path alone is not shown to do less than a path with lines'))
        print('  P2 verdict: ' + ('a path alone gets the agent to the file' if d2[1] > 0
                                  else 'not detected: a path alone is not shown to open more files than a bare name'))
        if c['reads'] < MIN_READS:
            print(f'  P3 verdict: too few reads to test (fewer than {MIN_READS})')
        else:
            print('  P3 verdict: ' + ('without a line number the file is read from the top' if share <= P3_MAX
                                      else f'more than {100 * P3_MAX:.0f}% ask past line 1: not as registered'))

    print()
    print('3. No rule: reported')
    print(f'  EPATH - H on reading a listed neighbor: {dpt(diff_ci(reads[NEW], reads["H"]))}')
    print(f'  EL - EPATH on opening a listed neighbor\'s file: {dpt(diff_ci(opens["EL"], opens[NEW]))}')
    print(f'  EL - H on reading a listed neighbor (both from the reference run): {dpt(diff_ci(reads["EL"], reads["H"]))}')
    for a in arms:
        c = first[a]
        print(f'  arm {a:<5} first reads of a listed neighbor\'s file: {c["reads"]}; ask past line 1 {c["ranged"]}; '
              f'cover a listed neighbor {c["covers"]}')


if __name__ == '__main__':
    main()
