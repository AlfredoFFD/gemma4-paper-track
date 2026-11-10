"""Pre-registration 13: the address written as a search hit (arm EG).

Usage: py -I -X utf8 analysis/analyze_13.py <run_dir> [--ref <run_dir of pre-registration 04>] [--new EG]

<run_dir> holds results.jsonl of the new run (arm EG, 407 states, seeds 1 to 3). The reference arms E (name, file,
line range and first definition line, as JSON), EL (name, file, line range) and H (bare names) come from the run of
pre-registration 04 on the same platform, harness wheels, states and seeds (default analysis/results/c/forks).

Everything is imported from frozen or tracked code: the interface-failure rule and the registered outcome
(gates_c.failure, gates_c.any_true), the file-level outcome (mangled_sensitivity.opens_listed_file), where a first
read of a listed neighbor's file starts (explore_first_reads.read_stats, norm) and the bootstrap (analyze_forks).

--new exists so that the script can be tested on a stand-in file in which another arm's rows carry the new label.
"""
import argparse
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from explore_first_reads import norm, read_stats  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

REF = ('H', 'EL', 'E')
SEEDS = (1, 2, 3)
MIN_COMPLETE, MIN_READS, WINDOW = 200, 30, 150


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


def shallowest(state, call):
    """First line of the listed neighbor that starts highest in the file the call reads (None if no span)."""
    path = norm(call['arguments'].get('filepath'))
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    starts = [state['neighbor_spans'][n]['start'] for n in unshown
              if state['neighbor_spans'].get(n) and state['neighbor_spans'][n]['path'] == path
              and state['neighbor_spans'][n].get('start')]
    return min(starts) if starts else None


def three_way(d, more, less):
    if d[0] is None:
        return 'no estimate'
    if d[1] > 0:
        return more
    if d[2] < 0:
        return less
    return 'no detectable difference'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--ref', default=str(HERE / 'results' / 'c' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    ap.add_argument('--new', default='EG')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    NEW = args.new
    states = load_states(args.states)   # the scored fields are those of the 407 states; the new arm adds a note only
    new, n_new, f_new = usable_rows(Path(args.run_dir) / 'results.jsonl', (NEW,))
    ref, n_ref, f_ref = usable_rows(Path(args.ref) / 'results.jsonl', REF)

    print(f'PRE-REGISTRATION 13: the address written as a search hit (arm {NEW}), against the arms of pre-registration '
          f'04\'s run')
    print()
    for arm, n, f in [(NEW, n_new, f_new)] + [(a, n_ref, f_ref) for a in REF]:
        kinds = {k: v for (a, k), v in sorted(f.items()) if a == arm}
        src = 'this run' if arm == NEW else 'run of pre-registration 04'
        print(f'  arm {arm:<5} ({src}): {n[arm]} rows; interface failures {sum(kinds.values())} {kinds} (excluded)')

    def rows_of(key, arm):
        src = new if arm == NEW else ref
        return [src[key][(arm, s)] for s in SEEDS] if all((arm, s) in src.get(key, {}) for s in SEEDS) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in ('E', NEW)))
    print(f'  complete states (E and {NEW} usable for seeds 1 to 3): {len(complete)} of {len(states)}')
    exploratory = len(complete) < MIN_COMPLETE
    if exploratory:
        print(f'  fewer than {MIN_COMPLETE} complete states: everything below is EXPLORATORY')

    arms = ['H', 'EL', 'E', NEW]
    reads = {a: {} for a in arms}     # outcome 1: the next call reads a listed neighbor (registered outcome of 02 to 05)
    opens = {a: {} for a in arms}     # outcome 2: the next call opens a listed neighbor's file
    ranged = {a: {} for a in arms}    # outcome 3: among those opens, the read asks past line 1 (per state: 0/1 per read)
    deep = {a: {} for a in arms}      # outcome 3 where no listed neighbor of the file starts in its first 150 lines
    first = {a: collections.Counter() for a in arms}
    for k in complete:
        st = states[k]
        for a in arms:
            rs = rows_of(k, a)
            if rs is None:   # H and EL are not required for completeness
                continue
            reads[a][k] = [int(bool(any_true(st, r['next_call']))) for r in rs]
            opens[a][k] = [int(bool(opens_listed_file(st, r['next_call']))) for r in rs]
            for r in rs:
                call = r['next_call']
                if call.get('function_name') == 'read_file' and opens_listed_file(st, call):
                    is_ranged, covers, _on_first = read_stats(st, call)
                    first[a]['reads'] += 1
                    first[a]['ranged'] += int(is_ranged)
                    first[a]['covers'] += int(covers)
                    ranged[a].setdefault(k, []).append(int(is_ranged))
                    top = shallowest(st, call)
                    if top is not None and top > WINDOW:
                        first[a]['deep'] += 1
                        first[a]['deep_ranged'] += int(is_ranged)
                        deep[a].setdefault(k, []).append(int(is_ranged))

    print()
    print('1. Rates on the complete states (percent of replays, 95% interval by state | hits/replays)')
    for a in arms:
        n = sum(len(v) for v in reads[a].values())
        note = '' if a in ('E', NEW) else f'   (on the {len(reads[a])} of these states where the arm is usable)'
        print(f'  arm {a:<5} reads a listed neighbor: {pct(boot_ci(reads[a]))} | {sum(sum(v) for v in reads[a].values())}/{n}'
              f'; opens a listed neighbor\'s file: {pct(boot_ci(opens[a]))} | {sum(sum(v) for v in opens[a].values())}/{n}{note}')

    print()
    print('2. Rules (95% bootstrap by state; by task beside it)')
    d1 = diff_ci(reads[NEW], reads['E'])
    d1t = diff_ci(by_task(reads[NEW]), by_task(reads['E']))
    print(f'  X1, {NEW} - E on reading a listed neighbor: {dpt(d1)}; by task [{100 * d1t[1]:+.2f}, {100 * d1t[2]:+.2f}]')
    cn, ce = first[NEW], first['E']
    d2 = diff_ci(ranged[NEW], ranged['E'])
    d2t = diff_ci(by_task(ranged[NEW]), by_task(ranged['E']))
    print(f'  X2, first reads of a listed neighbor\'s file that ask past line 1: {NEW} {cn["ranged"]} of {cn["reads"]}, '
          f'E {ce["ranged"]} of {ce["reads"]}; {NEW} - E {dpt(d2)}; by task '
          + ('n/a' if d2t[0] is None else f'[{100 * d2t[1]:+.2f}, {100 * d2t[2]:+.2f}]'))
    if not exploratory:
        print('  X1 verdict: ' + three_way(d1, 'written as a search hit, the address is followed more',
                                           'written as a search hit, the address is followed less'))
        if cn['reads'] < MIN_READS or ce['reads'] < MIN_READS:
            print(f'  X2 verdict: too few reads to test (fewer than {MIN_READS} in a condition)')
        else:
            print('  X2 verdict: ' + three_way(d2, 'written as a search hit, the line is asked for more often',
                                               'written as a search hit, the line is asked for less often'))

    print()
    print('3. No rule: reported')
    print(f'  {NEW} - EL on reading a listed neighbor: {dpt(diff_ci(reads[NEW], reads["EL"]))}')
    print(f'  {NEW} - H on reading a listed neighbor: {dpt(diff_ci(reads[NEW], reads["H"]))}')
    print(f'  {NEW} - E on opening a listed neighbor\'s file: {dpt(diff_ci(opens[NEW], opens["E"]))}')
    d3 = diff_ci(deep[NEW], deep['E'])
    print(f'  first reads where no listed neighbor of the file starts in its first {WINDOW} lines, asking past line 1: '
          f'{NEW} {cn["deep_ranged"]} of {cn["deep"]}, E {ce["deep_ranged"]} of {ce["deep"]}; {NEW} - E {dpt(d3)}')
    for a in arms:
        c = first[a]
        print(f'  arm {a:<5} first reads of a listed neighbor\'s file: {c["reads"]}; ask past line 1 {c["ranged"]}; '
              f'cover a listed neighbor {c["covers"]}; out of the first {WINDOW} lines {c["deep"]}, of which past line 1 '
              f'{c["deep_ranged"]}')


if __name__ == '__main__':
    main()
