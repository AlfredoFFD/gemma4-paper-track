"""Analysis of the fork replays, as pre-registered in prereg/02-discrimination-forks.md.

Inputs: analysis/fork_states/states.jsonl and a results.jsonl from the Kaggle run (plus fidelity.jsonl if present).
Usage: py -I analysis/analyze_forks.py <results_dir> [--states analysis/fork_states/states.jsonl]
Every rate comes with a 95% bootstrap interval clustered by state (2,000 resamples, seed 0).
"""
import argparse
import collections
import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fork_states import touches, valid_call  # noqa: E402

ARMS = ['A', 'P', 'Pp', 'H', 'Hp']
GRAPH_TOOLS = {'get_code_neighbors', 'get_code_subgraph', 'search_similar_code'}
KNOWN_TOOLS = GRAPH_TOOLS | {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch'}


def boot_ci(values_by_cluster, n=2000, seed=0, stat='mean'):
    """values_by_cluster: {cluster: [0/1,...]}. Bootstrap over clusters; returns (point, lo, hi)."""
    clusters = list(values_by_cluster)
    if not clusters:
        return None, None, None
    rng = random.Random(seed)
    flat = [v for c in clusters for v in values_by_cluster[c]]
    point = st.mean(flat) if flat else None
    boots = []
    for _ in range(n):
        sample = [rng.choice(clusters) for _ in clusters]
        vals = [v for c in sample for v in values_by_cluster[c]]
        if vals:
            boots.append(st.mean(vals))
    boots.sort()
    return point, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]


def diff_ci(a_by_cluster, b_by_cluster, n=2000, seed=0, level=0.95):
    """Paired-by-cluster bootstrap of mean(a) - mean(b)."""
    clusters = sorted(set(a_by_cluster) | set(b_by_cluster))
    if not clusters or not any(a_by_cluster.values()) or not any(b_by_cluster.values()):
        return None, None, None  # no eligible pairs: no estimate
    rng = random.Random(seed)

    def m(d, cl):
        vals = [v for c in cl for v in d.get(c, [])]
        return st.mean(vals) if vals else 0.0

    point = m(a_by_cluster, clusters) - m(b_by_cluster, clusters)
    boots = sorted(m(a_by_cluster, s) - m(b_by_cluster, s) for s in ([rng.choice(clusters) for _ in clusters] for _ in range(n)))
    lo = boots[int((1 - level) / 2 * len(boots))]
    hi = boots[int((1 - (1 - level) / 2) * len(boots)) - 1]
    return point, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_dir')
    ap.add_argument('--states', default=str(Path(__file__).resolve().parent / 'fork_states' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    rdir = Path(args.results_dir)
    states = {(s['task'], s['run'], s.get('fork', 0)): s for s in (json.loads(l) for l in open(args.states, encoding='utf-8'))}
    rows = [json.loads(l) for l in open(rdir / 'results.jsonl', encoding='utf-8')]
    print(f'{len(rows)} replays over {len({(r["task"], r["run"], r.get("fork", 0)) for r in rows})} states')

    # interface failures
    fail = collections.Counter()
    ok_rows = []
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
            ok_rows.append(r)
    print('interface failures (arm, kind):', dict(fail))

    # complete states only: all arms x seeds present and ok
    by_state = collections.defaultdict(dict)
    for r in ok_rows:
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in ok_rows})
    complete = {k: v for k, v in by_state.items() if len(v) == len(ARMS) * len(seeds)}
    print(f'states with every arm and seed present: {len(complete)} (seeds {seeds})')
    if not complete:
        print('No state has every arm and seed: nothing to estimate. Stopping.')
        return

    any_true = {a: collections.defaultdict(list) for a in ARMS}      # any listed true neighbor touched
    swapped = collections.defaultdict(list)                          # P,H: the swapped-out entry touched
    decoy = collections.defaultdict(list)                            # Pp,Hp: the decoy touched
    per_entry_true = {a: collections.defaultdict(list) for a in ARMS}
    base_decoy = collections.defaultdict(list)
    graph_use_A = collections.defaultdict(list)
    channel_true = {'P': collections.defaultdict(list), 'H': collections.defaultdict(list)}
    channel_decoy = {'Pp': collections.defaultdict(list), 'Hp': collections.defaultdict(list)}
    for key, reps in complete.items():
        s = states[key]
        spans = s['neighbor_spans']
        dspan = s['decoy_span']
        unshown = set(s.get('unshown_true_neighbors', s['true_neighbors']))
        flines = s.get('file_lines', {})
        for (arm, seed), r in reps.items():
            call = r['next_call']
            touched = {n: touches(call, spans[n], n, file_lines=flines.get(n))
                       for n in s['true_neighbors'] if spans.get(n) and n in unshown}
            hit_true = [bool(v) and v != 'graph' for v in touched.values()]
            any_true[arm][key].append(int(any(hit_true)))
            for v in hit_true:
                per_entry_true[arm][key].append(int(v))
            sw = touched.get(s['swapped_out'])
            dec = touches(call, dspan, s['decoy'], file_lines=flines.get(s['decoy'])) if dspan else None
            if arm in ('P', 'H'):
                swapped[key].append(int(bool(sw) and sw != 'graph'))
                channel_true[arm][key].append(int(any(hit_true)))
            if arm in ('Pp', 'Hp'):
                decoy[key].append(int(bool(dec) and dec != 'graph'))
                channel_decoy[arm][key].append(int(bool(dec) and dec != 'graph'))
            if arm == 'A':
                base_decoy[key].append(int(bool(dec) and dec != 'graph'))
                graph_use_A[key].append(int(call['function_name'] in GRAPH_TOOLS))

    def show(label, trip):
        p, lo, hi = trip
        print(f'  {label}: {p:.4f} [{lo:.4f}, {hi:.4f}]' if p is not None else f'  {label}: n/a')

    print('\nAny listed true neighbor in an unopened file touched, by arm:')
    for a in ARMS:
        show(a, boot_ci(any_true[a]))
    print('Per-entry touch rate of true entries, by arm:')
    for a in ARMS:
        show(a, boot_ci(per_entry_true[a]))
    print('Swapped-out entry touched (P and H):')
    show('swapped', boot_ci(swapped))
    print('Decoy touched (Pp and Hp), and in arm A (base):')
    show('decoy', boot_ci(decoy))
    show('decoy in A', boot_ci(base_decoy))
    print('H1: any true | P,H  minus  any listed true | A')
    ph = collections.defaultdict(list)
    for k in complete:
        ph[k] = any_true['P'][k] + any_true['H'][k]
    show('H1 diff', diff_ci(ph, any_true['A']))
    print('H2 (primary): D = swapped-out | P,H  minus  decoy | Pp,Hp')
    show('D 95%', diff_ci(swapped, decoy))
    show('D 90%', diff_ci(swapped, decoy, level=0.90))
    print('H3: any true | P  minus  any true | H (channel), and decoy | Pp minus decoy | Hp')
    show('channel true', diff_ci(channel_true['P'], channel_true['H']))
    show('channel decoy', diff_ci(channel_decoy['Pp'], channel_decoy['Hp']))
    print('H4: graph tool as the next call in arm A')
    show('graph use', boot_ci(graph_use_A))

    fid = rdir / 'fidelity.jsonl'
    if fid.exists():
        frows = [json.loads(l) for l in open(fid, encoding='utf-8')]
        rel = [abs(f['diff']) / f['logged_prompt_tokens'] for f in frows if f.get('diff') is not None]
        if rel:
            print(f'\nFidelity: n={len(rel)}, median abs relative diff={st.median(rel):.4f}, max={max(rel):.4f}, gate (<=0.02): {"PASS" if st.median(rel) <= 0.02 else "FAIL"}')


if __name__ == '__main__':
    main()
