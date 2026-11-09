"""Analysis for pre-registration 03 (arms D, D', E), pooled with the run v5 arms (A, P, P', H, H').

Usage: py -I analysis/analyze_b.py <results_dir_B> --v5 analysis/results/v5/forks [--states analysis/fork_states/states.jsonl]
Same outcome definitions, exclusions and clustered bootstrap as analyze_forks.py.
"""
import argparse
import collections
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes as N  # noqa: E402
from analyze_forks import GRAPH_TOOLS, KNOWN_TOOLS, boot_ci, diff_ci  # noqa: E402
from fork_states import touches, valid_call  # noqa: E402

ARMS_ALL = ['A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E']


def load_rows(path):
    return [json.loads(l) for l in open(path, encoding='utf-8')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_dir_b')
    ap.add_argument('--v5', default=str(Path(__file__).resolve().parent / 'results' / 'v5' / 'forks'))
    ap.add_argument('--states', default=str(Path(__file__).resolve().parent / 'fork_states' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = {(s['task'], s['run'], s.get('fork', 0)): s for s in (json.loads(l) for l in open(args.states, encoding='utf-8'))}
    rows = load_rows(Path(args.v5) / 'results.jsonl') + load_rows(Path(args.results_dir_b) / 'results.jsonl')
    print(f'{len(rows)} replays (v5 + B) over {len({(r["task"], r["run"], r.get("fork", 0)) for r in rows})} states')

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
    print('interface failures:', dict(fail))
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in ok})
    arms_present = sorted({r['arm'] for r in ok}, key=ARMS_ALL.index)
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms_present) * len(seeds)}
    print(f'arms: {arms_present}; states complete across all arms and seeds: {len(complete)}')
    if not complete:
        print('nothing to estimate')
        return

    any_true = {a: collections.defaultdict(list) for a in arms_present}
    swapped = {a: collections.defaultdict(list) for a in arms_present}
    decoy = {a: collections.defaultdict(list) for a in arms_present}
    graph_next = {a: collections.defaultdict(list) for a in arms_present}
    thought = {a: collections.defaultdict(list) for a in arms_present}
    ctoks = {a: [] for a in arms_present}
    mention_true = {a: collections.defaultdict(list) for a in arms_present}
    mention_decoy = {a: collections.defaultdict(list) for a in arms_present}
    cats = {a: collections.Counter() for a in arms_present}
    import re
    CV = re.compile(r'^\s*(cat|sed|head|tail|grep|rg|awk|less|more)\b')
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

    def show(label, trip):
        p, lo, hi = trip
        print(f'  {label}: {p:.4f} [{lo:.4f}, {hi:.4f}]' if p is not None else f'  {label}: n/a')

    print('\nAny listed true neighbor in an unopened file touched, by arm:')
    for a in arms_present:
        show(a, boot_ci(any_true[a]))
    print('Swapped-out entry touched, by arm (meaningful for P, H, D):')
    for a in arms_present:
        show(a, boot_ci(swapped[a]))
    print('Decoy touched, by arm (meaningful for Pp, Hp, Dp):')
    for a in arms_present:
        show(a, boot_ci(decoy[a]))
    if 'D' in arms_present and 'H' in arms_present:
        print('B1 framing: any true | D minus any true | H')
        show('B1', diff_ci(any_true['D'], any_true['H']))
    if 'D' in arms_present and 'Dp' in arms_present:
        p_sw = boot_ci(swapped['D'])[0]
        print(f'B2 discrimination under instruction: swapped-out | D = {p_sw:.4f} ({"informative" if p_sw is not None and p_sw >= 0.05 else "UNDERPOWERED, below the 5% floor"})')
        show('D_B 95%', diff_ci(swapped['D'], decoy['Dp']))
        show('D_B 90%', diff_ci(swapped['D'], decoy['Dp'], level=0.90))
    if 'E' in arms_present and 'H' in arms_present:
        print('B3 encoding: any true | E minus any true | H (two-sided)')
        show('B3', diff_ci(any_true['E'], any_true['H']))
    print('\nSecondary: graph tool as the next call, by arm')
    for a in arms_present:
        show(a, boot_ci(graph_next[a]))
    print('Thought present, by arm; median completion tokens')
    for a in arms_present:
        p, lo, hi = boot_ci(thought[a])
        print(f'  {a}: {p:.3f} [{lo:.3f}, {hi:.3f}] | completion tokens median {st.median(ctoks[a]):.0f}')
    print('Mentions in thought text: a fresh true entry; the decoy')
    for a in arms_present:
        pt, pd = boot_ci(mention_true[a]), boot_ci(mention_decoy[a])
        print(f'  {a}: true {pt[0]:.3f} [{pt[1]:.3f}, {pt[2]:.3f}] | decoy {pd[0]:.3f} [{pd[1]:.3f}, {pd[2]:.3f}]')
    print('Next-call mix, by arm')
    for a in arms_present:
        n = sum(cats[a].values())
        print(f'  {a}:', {k: f'{100 * v / n:.1f}%' for k, v in cats[a].most_common()})


if __name__ == '__main__':
    main()
