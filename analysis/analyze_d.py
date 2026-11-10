"""Analysis for experiment D (pre-registration 05): D1, the tool channel; D2, a second model.

Usage:
    py -I -X utf8 analysis/analyze_d.py d1 <D1_run_dir> [--c <C_run_dir>] [--states analysis/fork_states_d/states.jsonl]
    py -I -X utf8 analysis/analyze_d.py d2 <D2_run_dir> [--states analysis/fork_states_d/states.jsonl]

Same outcome definitions, exclusions, scorer (fork_states.touches) and clustered bootstrap (analyze_forks.boot_ci,
diff_ci: 2,000 resamples, seed 0) as analyze_c.py. Every contrast uses arms of the one run given; complete states only
(every arm of the mode and seeds 1 to 3 usable); fewer than 200 complete states makes everything EXPLORATORY.

D1 arms (31B, same platform as experiment C):
  P   inserted get_code_neighbors call; its result lists the true neighbors as bare names
  PE  the same call; its result lists arm E's entries (name, file, line range, first definition line)
  E   arm E's entries in a harness note with arm H's wording
  T1 = PE - P (PASS if the lower 95% bound is above 0); T2 = PE - E ("no channel difference" only if the 90% interval
  lies within plus or minus 2 points). --c: drift of arm E against the experiment C run, paired by state and seed.
D2 arms (second model): A (no list), H (bare names, note), E (legible, note), RE (rewired list, legible, note).
  M1 = E - H (PASS: "replicates on the second model"); H - A, E - A and E true minus RE rewired carry no rule.
  An arm with more than 20% interface failures is flagged as unreliable.
"""
import argparse
import collections
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_forks import GRAPH_TOOLS, boot_ci, diff_ci  # noqa: E402
from gates_c import FAILURES, any_true, failure, load_rows, load_states, skey, touch_map  # noqa: E402

HERE = Path(__file__).resolve().parent
SEEDS = (1, 2, 3)
MIN_COMPLETE = 200
ARMS = {'d1': ('P', 'PE', 'E'), 'd2': ('A', 'H', 'E', 'RE')}
UNRELIABLE = 0.20


def score(state, r):
    """Per-replay outcomes, scored exactly as analyze_c.py / analyze_b.py score them."""
    call = r['next_call']
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    t = touch_map(state, call, [n for n in state['true_neighbors'] if n in unshown], state['neighbor_spans'])
    sw = t.get(state['swapped_out'])
    rw = touch_map(state, call, state.get('rewired_entries', []), state.get('rewired_spans', {}))
    usage = r.get('usage') or {}
    return {'any_true': int(any(bool(v) and v != 'graph' for v in t.values())),
            'swapped': int(bool(sw) and sw != 'graph'),
            'any_rewired': int(any(bool(v) and v != 'graph' for v in rw.values())),
            'graph_next': int(call['function_name'] in GRAPH_TOOLS),
            'thought': int(bool(r.get('thought'))),
            'ctok': usage.get('completion_tokens') or 0,
            'ptok': usage.get('prompt_tokens')}


def tables(complete, usable, states, arms):
    """{outcome: {arm: {state: [values over seeds]}}} on the given complete states."""
    out = collections.defaultdict(lambda: {a: collections.defaultdict(list) for a in arms})
    for k in complete:
        for a in arms:
            for s in SEEDS:
                for name, v in score(states[k], usable[k][(a, s)]).items():
                    out[name][a][k].append(v)
    return out


def pct(trip):
    p, lo, hi = trip
    return 'n/a' if p is None else f'{100 * p:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]'


def dpt(trip):
    p, lo, hi = trip
    return 'n/a' if p is None else f'{100 * p:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]'


def raw(tab, a):
    vals = [v for vs in tab[a].values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


def load_run(run_dir, arms):
    rows = [r for r in load_rows(Path(run_dir) / 'results.jsonl') if r['arm'] in arms]
    n_arm = collections.Counter(r['arm'] for r in rows)
    fail = collections.Counter()
    usable = collections.defaultdict(dict)
    other_seeds = 0
    for r in rows:
        kind = failure(r)
        if kind:
            fail[(r['arm'], kind)] += 1
        elif r['seed'] in SEEDS:
            usable[skey(r)][(r['arm'], r['seed'])] = r
        else:
            other_seeds += 1
    return rows, n_arm, fail, usable, other_seeds


def paired_drift(rows_a, rows_b, arm, states):
    """mean(a) - mean(b) of any_true on the (state, seed) keys usable in both runs, clustered by state."""
    def index(rows):
        return {(skey(r), r['seed']): r for r in rows if r['arm'] == arm and not failure(r) and r['seed'] in SEEDS}
    ia, ib = index(rows_a), index(rows_b)
    keys = sorted(set(ia) & set(ib))
    x, y = collections.defaultdict(list), collections.defaultdict(list)
    for k, s in keys:
        x[k].append(any_true(states[k], ia[(k, s)]['next_call']))
        y[k].append(any_true(states[k], ib[(k, s)]['next_call']))
    return keys, x, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=sorted(ARMS))
    ap.add_argument('run_dir')
    ap.add_argument('--c', default=None, help='d1 only: experiment C run dir, for the descriptive drift of arm E')
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    arms = ARMS[args.mode]
    states = load_states(args.states)
    rows, n_arm, fail, usable, other_seeds = load_run(args.run_dir, arms)
    print(f'experiment {args.mode.upper()}: {len(rows)} replays of arms {list(arms)} in {args.run_dir}'
          + (f'; {other_seeds} usable rows with a seed outside 1-3 ignored' if other_seeds else ''))

    print('Interface failures by arm (excluded from every estimate; counted apart from the model\'s choices):')
    for a in arms:
        k = sum(fail[(a, f)] for f in FAILURES)
        share = k / n_arm[a] if n_arm[a] else None
        warn = ''
        if share is not None and share > UNRELIABLE:
            warn = f'  WARNING: above {UNRELIABLE:.0%}, so arm {a}\'s rates are UNRELIABLE (pre-registration 05)'
        print(f'  {a}: {k}/{n_arm[a]} = ' + (f'{share:.4f}' if share is not None else 'n/a')
              + ' (' + ', '.join(f'{f} {fail[(a, f)]}' for f in FAILURES) + ')' + warn)
    need = {(a, s) for a in arms for s in SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    print(f'complete states (every arm x seeds 1-3 usable): {len(complete)} of {len(states)}')
    if not complete:
        print('nothing to estimate')
        return
    exploratory = len(complete) < MIN_COMPLETE
    print('partial-run rule: ' + ('fewer than 200 complete states, so everything below is EXPLORATORY' if exploratory
                                  else 'at least 200 complete states, so the decision rules apply'))
    tab = tables(complete, usable, states, arms)

    def rate(name, a):
        return f'{pct(boot_ci(tab[name][a]))} | {raw(tab[name], a)}'

    print('\nPer arm, percent [95% interval] | raw count')
    for a in arms:
        ptoks = [v for vs in tab['ptok'][a].values() for v in vs if v]
        ctoks = [v for vs in tab['ctok'][a].values() for v in vs]
        print(f'  {a}: any unopened true neighbor touched {rate("any_true", a)}')
        print(f'      swapped-out entry touched {rate("swapped", a)}')
        if a == 'RE':
            print(f'      any rewired entry touched {rate("any_rewired", a)}')
        print(f'      next call is a graph tool {rate("graph_next", a)}')
        print(f'      thought text present {rate("thought", a)}')
        print(f'      completion tokens median {st.median(ctoks):.0f} | prompt tokens mean '
              + (f'{st.mean(ptoks):.0f} (n={len(ptoks)})' if ptoks else 'n/a'))

    T = tab['any_true']
    tag = ' [EXPLORATORY]' if exploratory else ''
    print('\nContrasts on any unopened true neighbor touched, points [interval]' + tag)
    if args.mode == 'd1':
        t1 = diff_ci(T['PE'], T['P'])
        print(f'  T1 PE - P 95%: {dpt(t1)}: '
              + ('PASS (the legible entries raise following inside the tool result)' if t1[1] is not None and t1[1] > 0
                 else 'FAIL (lower bound not above 0)') + tag)
        t2 = diff_ci(T['PE'], T['E'])
        t2_90 = diff_ci(T['PE'], T['E'], level=0.90)
        within = t2_90[0] is not None and t2_90[1] >= -0.02 and t2_90[2] <= 0.02
        print(f'  T2 PE - E 95%: {dpt(t2)}')
        print(f'  T2 PE - E 90%: {dpt(t2_90)}: '
              + ('no channel difference (90% interval within plus or minus 2 points)' if within
                 else 'a channel difference is not ruled out (90% interval not within plus or minus 2 points)') + tag)
        if args.c:
            c_rows = [r for r in load_rows(Path(args.c) / 'results.jsonl') if r['arm'] == 'E']
            keys, x, y = paired_drift(rows, c_rows, 'E', states)
            if keys:
                print(f'\nDrift of arm E (descriptive), this run minus the experiment C run, {len(keys)} (state, seed) pairs '
                      f'over {len(x)} states: {dpt(diff_ci(x, y))} | this run {raw({"E": x}, "E")}, '
                      f'C run {raw({"E": y}, "E")}')
            else:
                print('\nDrift of arm E: no shared (state, seed) key with the experiment C run')
    else:
        m1 = diff_ci(T['E'], T['H'])
        print(f'  M1 E - H 95%: {dpt(m1)}: '
              + ('PASS: replicates on the second model' if m1[1] is not None and m1[1] > 0
                 else 'does not replicate on the second model (lower bound not above 0)') + tag)
        print(f'  H - A 95% (no rule): {dpt(diff_ci(T["H"], T["A"]))}')
        print(f'  E - A 95% (no rule): {dpt(diff_ci(T["E"], T["A"]))}')
        print(f'  E true minus RE rewired 95% (no rule; the rewired list is not like-for-like): '
              f'{dpt(diff_ci(T["E"], tab["any_rewired"]["RE"]))}')


if __name__ == '__main__':
    main()
