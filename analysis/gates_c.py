"""Gates G1, G2 and G3 of experiment C (pre-registration 04), checked before any outcome of arms Ep, EL or ES is read.

Usage: py -I -X utf8 analysis/gates_c.py <C_run_dir> [--v5 analysis/results/v5/forks] [--v6 analysis/results/v6/forks]
                                          [--states analysis/fork_states_c/states.jsonl]

G1  fidelity: median absolute relative difference between replayed and logged prompt tokens (fidelity.jsonl) at most 2%.
G2  replication of B3 in this run: P(any unopened true neighbor touched | E) minus the same under H, on states
    complete across the five arms and three seeds, lower 95% bound above 0.
G3  platform drift (descriptive): this run's E against v6's E, and this run's H against v5's H, paired on the same
    (state, seed) keys, 95% interval clustered by state; flagged if the difference is above 3 points and the
    interval excludes 0.
No outcome of Ep, EL or ES is computed or printed: their rows are only counted, and their interface failures counted.
Outcome, exclusions, scorer and bootstrap are those of analyze_forks.py / analyze_c.py (imported, not copied).
"""
import argparse
import collections
import functools
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes as N  # noqa: E402
from analyze_forks import KNOWN_TOOLS, diff_ci  # noqa: E402
from fork_states import touches, valid_call  # noqa: E402

HERE = Path(__file__).resolve().parent
ARMS_C_RUN = ('Ep', 'EL', 'ES', 'E', 'H')
BLIND = ('Ep', 'EL', 'ES')          # outcomes never read here
SEEDS = (1, 2, 3)
FAILURES = ('error', 'no_call', 'unknown_tool', 'malformed_args')
MIN_COMPLETE = 200


def load_rows(path):
    return [json.loads(l) for l in open(path, encoding='utf-8')]


def load_states(path):
    return {(s['task'], s['run'], s.get('fork', 0)): s for s in (json.loads(l) for l in open(path, encoding='utf-8'))}


def skey(r):
    return (r['task'], r['run'], r.get('fork', 0))


def failure(r):
    """The interface-failure kind of a replay, or None if usable (same order of checks as analyze_c.py)."""
    call = r.get('next_call')
    if r.get('error'):
        return 'error'
    if not call:
        return 'no_call'
    if call['function_name'] not in KNOWN_TOOLS:
        return 'unknown_tool'
    if not valid_call(call):
        return 'malformed_args'
    return None


@functools.lru_cache(maxsize=None)
def _lengths(task, path):
    src = N.file_text(task, path)
    return tuple(len(x) for x in src.splitlines()) if src else None


def _ll(task, path):
    t = _lengths(task, path)
    return list(t) if t is not None else None


def touch_map(state, call, names, spans):
    """{name: touches(...)} over the given names with a span, as analyze_c.py scores them."""
    return {n: touches(call, spans[n], n, line_lengths=_ll(state['task'], spans[n]['path'])) for n in names if spans.get(n)}


def any_true(state, call):
    """1 if the call touches any true neighbor in an unopened file (graph-tool touches do not count)."""
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    t = touch_map(state, call, [n for n in state['true_neighbors'] if n in unshown], state['neighbor_spans'])
    return int(any(bool(v) and v != 'graph' for v in t.values()))


def fmt(trip, scale=100):
    p, lo, hi = trip
    return 'n/a' if p is None else f'{scale * p:+.2f} [{scale * lo:+.2f}, {scale * hi:+.2f}]'


def g1(run_dir):
    path = Path(run_dir) / 'fidelity.jsonl'
    if not path.exists():
        print(f'G1 fidelity: no {path.name} in the run directory: FAIL (cannot be checked)')
        return
    rows = load_rows(path)
    bad = [r for r in rows if r.get('error') or r.get('replayed_prompt_tokens') is None or not r.get('logged_prompt_tokens')]
    good = [r for r in rows if r not in bad]
    rel = [abs(r['replayed_prompt_tokens'] - r['logged_prompt_tokens']) / r['logged_prompt_tokens'] for r in good]
    for r in bad:
        print(f'  G1 excluded row: {r["task"]} r{r["run"]} f{r.get("fork", 0)}: {r.get("error") or "no replayed prompt size"}')
    if not rel:
        print(f'G1 fidelity: {len(rows)} rows, none usable: FAIL')
        return
    med = st.median(rel)
    print(f'G1 fidelity: {len(rows)} rows ({len(bad)} excluded), median abs relative diff {100 * med:.2f}%, '
          f'mean {100 * st.mean(rel):.2f}%, max {100 * max(rel):.2f}%: {"PASS" if med <= 0.02 else "FAIL"} (rule: median at most 2%)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('c_run_dir')
    ap.add_argument('--v5', default=str(HERE / 'results' / 'v5' / 'forks'))
    ap.add_argument('--v6', default=str(HERE / 'results' / 'v6' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_c' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(args.states)

    g1(args.c_run_dir)

    rows = [r for r in load_rows(Path(args.c_run_dir) / 'results.jsonl') if r['arm'] in ARMS_C_RUN]
    n_arm = collections.Counter(r['arm'] for r in rows)
    fail = collections.Counter()
    usable = collections.defaultdict(dict)   # state -> (arm, seed) -> row
    for r in rows:
        kind = failure(r)
        if kind:
            fail[(r['arm'], kind)] += 1
        elif r['seed'] in SEEDS:
            usable[skey(r)][(r['arm'], r['seed'])] = r
    print('Interface failures by arm (excluded):')
    for a in ARMS_C_RUN:
        k = sum(fail[(a, f)] for f in FAILURES)
        share = f'{k / n_arm[a]:.4f}' if n_arm[a] else 'n/a'
        print(f'  {a}: {k}/{n_arm[a]} = {share} (' + ', '.join(f'{f} {fail[(a, f)]}' for f in FAILURES) + ')')
    need = {(a, s) for a in ARMS_C_RUN for s in SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    rule = 'rules apply' if len(complete) >= MIN_COMPLETE else 'fewer than 200: everything is EXPLORATORY'
    print(f'Complete states (all five arms x seeds 1-3 usable): {len(complete)} of {len(states)} '
          f'(rule: at least {MIN_COMPLETE}; {rule})')

    # G2: only arms E and H are scored
    by = {a: collections.defaultdict(list) for a in ('E', 'H')}
    for k in complete:
        for a in ('E', 'H'):
            for s in SEEDS:
                by[a][k].append(any_true(states[k], usable[k][(a, s)]['next_call']))
    if complete:
        rate = {a: sum(sum(v) for v in by[a].values()) / sum(len(v) for v in by[a].values()) for a in by}
        d = diff_ci(by['E'], by['H'])
        verdict = 'PASS' if d[1] is not None and d[1] > 0 else 'FAIL'
        print(f'G2 replication (E minus H, any unopened true neighbor touched, points): {fmt(d)} | '
              f'E {100 * rate["E"]:.2f}%, H {100 * rate["H"]:.2f}%: {verdict} (rule: lower 95% bound above 0)')
    else:
        print('G2 replication: no complete state: not computed')

    # G3: this run against the hosted runs on the same (state, seed) keys, every usable pair (not only complete states)
    hosted = {'E': args.v6, 'H': args.v5}
    for a in ('E', 'H'):
        host = {}
        for r in load_rows(Path(hosted[a]) / 'results.jsonl'):
            if r['arm'] == a and not failure(r):
                host[(skey(r), r['seed'])] = r
        mine = {(k, s): v for k, d in usable.items() for (arm, s), v in d.items() if arm == a}
        keys = sorted(set(mine) & set(host))
        x, y = collections.defaultdict(list), collections.defaultdict(list)
        for k, s in keys:
            x[k].append(any_true(states[k], mine[(k, s)]['next_call']))
            y[k].append(any_true(states[k], host[(k, s)]['next_call']))
        if not keys:
            print(f'G3 drift {a}: no shared (state, seed) key: not computed')
            continue
        p, lo, hi = diff_ci(x, y)
        flag = 'PLATFORM DIFFERENCE' if p is not None and abs(p) > 0.03 and (lo > 0 or hi < 0) else 'no flag'
        src = Path(hosted[a]).parent.name
        rx = sum(sum(v) for v in x.values()) / len(keys)
        ry = sum(sum(v) for v in y.values()) / len(keys)
        print(f'G3 drift {a} (this run minus {src}, {len(keys)} pairs over {len(x)} states, points): {fmt((p, lo, hi))} | '
              f'this run {100 * rx:.2f}%, {src} {100 * ry:.2f}%: {flag} (flag: above 3 points with the interval excluding 0)')


if __name__ == '__main__':
    main()
