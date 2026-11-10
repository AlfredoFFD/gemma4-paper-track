"""Analysis for experiment C (arms Ep, EL, ES, with E and H re-run in the same run; pre-registration 04).

Usage: py -I analysis/analyze_c.py <results_dir_C> [--states analysis/fork_states_c/states.jsonl]
Every contrast uses only arms of the experiment C run (pre-registration 04); the hosted runs are never pooled in.
Gate G1 (prompt-size fidelity) and gate G3 (drift against the hosted runs) are not computed here.
Same outcome definitions, exclusions and clustered bootstrap as analyze_forks.py and analyze_b.py.

Every arm here is a user-role note with arm H's wording, placed after arm A's messages:
  H   the true neighbor list as bare names (re-run in the experiment C run)
  E   the true list, each entry with its name, file, line range and first definition line (re-run in the experiment C run)
  Ep  arm E's entries on the decoy list: the swapped-out entry replaced by the decoy, which is written with its own fields
  EL  the true list, each entry with its name, file and line range only
  ES  the true list, each entry with its name and first definition line only
"""
import argparse
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes as N  # noqa: E402
from analyze_forks import GRAPH_TOOLS, KNOWN_TOOLS, boot_ci, diff_ci  # noqa: E402
from fork_states import touches, valid_call  # noqa: E402

ARMS_ALL = ['H', 'E', 'Ep', 'EL', 'ES']
ARMS_C = ('Ep', 'EL', 'ES')
FAILURES = ('error', 'no_call', 'unknown_tool', 'malformed_args')
CV = re.compile(r'^\s*(cat|sed|head|tail|grep|rg|awk|less|more)\b')


def load_rows(path):
    return [json.loads(l) for l in open(path, encoding='utf-8')]


def counts(by_cluster):
    """(replays with the outcome, replays, states) of a {state: [0/1, ...]} table."""
    flat = [v for vals in by_cluster.values() for v in vals]
    return sum(flat), len(flat), len(by_cluster)


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument('results_dir_c', help='results dir of the experiment C run (arms Ep, EL, ES)')
    ap.add_argument('--v5', default=str(here / 'results' / 'v5' / 'forks'), help='unused since pre-registration 04 (E and H are read from the C run)')
    ap.add_argument('--v6', default=str(here / 'results' / 'v6' / 'forks'), help='unused since pre-registration 04')
    ap.add_argument('--states', default=str(here / 'fork_states_c' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = {(s['task'], s['run'], s.get('fork', 0)): s for s in (json.loads(l) for l in open(args.states, encoding='utf-8'))}
    rows = []
    # pre-registration 04: E and H come from the experiment C run itself (same platform); the hosted runs are not pooled in
    for label, path, keep in (('C', args.results_dir_c, ARMS_C + ('E', 'H')),):
        loaded = load_rows(Path(path) / 'results.jsonl')
        kept = [r for r in loaded if r['arm'] in keep]
        print(f'run {label}: {len(loaded)} replays in the file, {len(kept)} used: {dict(collections.Counter(r["arm"] for r in kept))}')
        rows += kept
    n_arm = collections.Counter(r['arm'] for r in rows)
    ids = [(r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']) for r in rows]
    print(f'{len(rows)} replays pooled over {len({i[:3] for i in ids})} states; repeated (state, arm, seed) rows: {len(ids) - len(set(ids))}')

    fail = collections.Counter()
    ok = []
    for r in rows:
        call = r.get('next_call')
        if r.get('error'):
            fail[(r['arm'], 'error')] += 1
        elif not call:
            fail[(r['arm'], 'no_call')] += 1
        elif call['function_name'] not in KNOWN_TOOLS:
            fail[(r['arm'], 'unknown_tool')] += 1
        elif not valid_call(call):
            fail[(r['arm'], 'malformed_args')] += 1
        else:
            ok.append(r)
    print('Interface failures, by arm (excluded from every estimate below; counted apart from the model\'s choices):')
    for a in ARMS_ALL:
        if n_arm[a]:
            k = sum(fail[(a, kind)] for kind in FAILURES)
            print(f'  {a}: {k}/{n_arm[a]} replays = {k / n_arm[a]:.4f} (' + ', '.join(f'{kind} {fail[(a, kind)]}' for kind in FAILURES) + ')')
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in ok})
    arms_present = sorted({r['arm'] for r in ok}, key=ARMS_ALL.index)
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms_present) * len(seeds)}
    print(f'arms: {arms_present}; seeds: {seeds}; states complete across all arms and seeds: {len(complete)} '
          f'(of {len(by_state)} with a usable replay)')
    if not complete:
        print('nothing to estimate')
        return
    missing = [a for a in ('E', 'H') if a not in arms_present]
    if missing:
        print(f'arms {missing} are missing from this run: pre-registration 04 takes E and H from the same run, so no contrast is computed')
        return
    print('partial-run rule: ' + ('fewer than 200 complete states, so everything below is EXPLORATORY' if len(complete) < 200
                                  else 'at least 200 complete states, so the decision rules apply'))

    any_true = {a: collections.defaultdict(list) for a in arms_present}
    swapped = {a: collections.defaultdict(list) for a in arms_present}
    decoy = {a: collections.defaultdict(list) for a in arms_present}
    graph_next = {a: collections.defaultdict(list) for a in arms_present}
    thought = {a: collections.defaultdict(list) for a in arms_present}
    ctoks = {a: [] for a in arms_present}
    ptoks = {a: [] for a in arms_present}
    mention_true = {a: collections.defaultdict(list) for a in arms_present}
    mention_decoy = {a: collections.defaultdict(list) for a in arms_present}
    cats = {a: collections.Counter() for a in arms_present}
    for key, reps in complete.items():
        s = states[key]
        spans = s['neighbor_spans']
        dspan = s['decoy_span']
        unshown = set(s.get('unshown_true_neighbors', s['true_neighbors']))
        fresh = s.get('fresh_true_neighbors', list(unshown))

        def lengths(path):
            src = N.file_text(s['task'], path)
            return [len(x) for x in src.splitlines()] if src else None

        for (arm, seed), r in reps.items():
            call = r['next_call']
            touched = {n: touches(call, spans[n], n, line_lengths=lengths(spans[n]['path']))
                       for n in s['true_neighbors'] if spans.get(n) and n in unshown}
            hit = [bool(v) and v != 'graph' for v in touched.values()]
            any_true[arm][key].append(int(any(hit)))
            sw = touched.get(s['swapped_out'])
            swapped[arm][key].append(int(bool(sw) and sw != 'graph'))
            dec = touches(call, dspan, s['decoy'], line_lengths=lengths(dspan['path'])) if dspan else None
            decoy[arm][key].append(int(bool(dec) and dec != 'graph'))
            graph_next[arm][key].append(int(call['function_name'] in GRAPH_TOOLS))
            thought[arm][key].append(int(bool(r.get('thought'))))
            ctoks[arm].append((r.get('usage') or {}).get('completion_tokens') or 0)
            if (r.get('usage') or {}).get('prompt_tokens'):
                ptoks[arm].append(r['usage']['prompt_tokens'])
            th = (r.get('thought') or '') + ' ' + (r.get('text') or '')
            mention_true[arm][key].append(int(any(n.rsplit('.', 1)[-1] in th for n in fresh)))
            mention_decoy[arm][key].append(int(s['decoy'].rsplit('.', 1)[-1] in th))
            fn = call['function_name']
            if fn == 'read_file':
                cats[arm]['read_file'] += 1
            elif fn == 'run_command':
                cats[arm]['shell view' if CV.match(str(call['arguments'].get('command', ''))) else 'other shell'] += 1
            elif fn in ('edit_file', 'write_file'):
                cats[arm]['write/edit'] += 1
            elif fn in GRAPH_TOOLS:
                cats[arm]['graph'] += 1
            else:
                cats[arm]['other'] += 1

    def show(label, trip, note=''):
        p, lo, hi = trip
        print(f'  {label}: {p:.4f} [{lo:.4f}, {hi:.4f}]{note}' if p is not None else f'  {label}: n/a{note}')

    def raw(table, arm):  # the raw count behind a rate
        k, n, _ = counts(table[arm])
        return f'{arm} {k}/{n}'

    def rate(table, arm):
        k, n, m = counts(table[arm])
        show(arm, boot_ci(table[arm]), f' | {k}/{n} replays, {m} states')

    print('\nAny true neighbor in an unopened file touched, by arm (rate [95% interval] | raw count).')
    print('The outcome is the same set of true neighbors in every arm; Ep does not list one of them, the swapped-out entry.')
    for a in arms_present:
        rate(any_true, a)
    print('Swapped-out entry touched (listed under E; under Ep it is the entry the decoy replaced, so it is not listed):')
    for a in ('E', 'Ep'):
        if a in arms_present:
            rate(swapped, a)
    print('Decoy touched (listed under Ep; not listed under E, where it is the base rate):')
    for a in ('Ep', 'E'):
        if a in arms_present:
            rate(decoy, a)
    if 'E' in arms_present and 'Ep' in arms_present:
        p_sw = boot_ci(swapped['E'])[0]
        floor = 'informative' if p_sw is not None and p_sw >= 0.01 else 'UNDERPOWERED, below the 1% floor of pre-registration 04'
        print('Discrimination with arm E\'s entries: D_E = P(swapped-out touched | E) - P(decoy touched | Ep); '
              + (f'swapped-out | E = {p_sw:.4f} ({floor})' if p_sw is not None else 'swapped-out | E = n/a'))
        both = f' | swapped-out under {raw(swapped, "E")}, decoy under {raw(decoy, "Ep")}'
        show('D_E 95%', diff_ci(swapped['E'], decoy['Ep']), both)
        show('D_E 90%', diff_ci(swapped['E'], decoy['Ep'], level=0.90), both)
        print('Any true neighbor touched: Ep minus E (95% interval)')
        show('Ep minus E', diff_ci(any_true['Ep'], any_true['E']), f' | {raw(any_true, "Ep")}, {raw(any_true, "E")}')
    print('Which part of the entry carries the effect: any true neighbor touched, differences with 95% intervals')
    for a, b in (('EL', 'H'), ('ES', 'H'), ('E', 'EL'), ('E', 'ES'), ('E', 'H')):
        if a in arms_present and b in arms_present:
            show(f'{a} minus {b}' + (' (reference)' if (a, b) == ('E', 'H') else ''), diff_ci(any_true[a], any_true[b]),
                 f' | {raw(any_true, a)}, {raw(any_true, b)}')

    print('E minus each part, 90% intervals (a part is sufficient for the full effect only if the interval lies within plus or minus 2 points)')
    for b in ('EL', 'ES'):
        if b in arms_present:
            show(f'E minus {b} 90%', diff_ci(any_true['E'], any_true[b], level=0.90))
    g2 = diff_ci(any_true['E'], any_true['H'])
    print('Gate G2 (replication of B3 in this run; lower 95% bound of any true | E minus any true | H above 0): '
          + ('PASS' if g2[1] is not None and g2[1] > 0 else 'FAIL, so C1 and C2 above are EXPLORATORY'))
    print('\nSecondary (descriptive): graph tool as the next call, by arm')
    for a in arms_present:
        rate(graph_next, a)
    print('Thought present, by arm; median completion tokens; mean prompt tokens')
    for a in arms_present:
        k, n, _ = counts(thought[a])
        p, lo, hi = boot_ci(thought[a])
        ptok = f'{st.mean(ptoks[a]):.0f} (n={len(ptoks[a])})' if ptoks[a] else 'n/a'
        print(f'  {a}: {p:.3f} [{lo:.3f}, {hi:.3f}] | {k}/{n} replays | completion tokens median {st.median(ctoks[a]):.0f} | '
              f'prompt tokens mean {ptok}')
    print('Mentions in thought text: a fresh true entry; the decoy')
    for a in arms_present:
        pt, pd = boot_ci(mention_true[a]), boot_ci(mention_decoy[a])
        (kt, n, _), (kd, _, _) = counts(mention_true[a]), counts(mention_decoy[a])
        print(f'  {a}: true {pt[0]:.3f} [{pt[1]:.3f}, {pt[2]:.3f}] ({kt}/{n}) | decoy {pd[0]:.3f} [{pd[1]:.3f}, {pd[2]:.3f}] ({kd}/{n})')
    print('Next-call mix, by arm')
    for a in arms_present:
        n = sum(cats[a].values())
        print(f'  {a}:', {k: f'{v} ({100 * v / n:.1f}%)' for k, v in cats[a].most_common()})


if __name__ == '__main__':
    main()
