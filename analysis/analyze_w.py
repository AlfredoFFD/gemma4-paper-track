"""Analysis for experiment F (pre-registration 07): how earlier tool results are rendered in the replayed history.

Usage: py -I -X utf8 analysis/analyze_w.py <run_dir> [--states analysis/fork_states_d/states.jsonl]

Arms of one run, same states and seeds:
  A   nothing added; every tool result of the history is a dictionary, as harness v28 delivers it and as every
      earlier replay rebuilt it
  Aw  arm A with every tool result of the history delivered as {'result': '<logged JSON string>'}, as the harness
      version of the original runs delivered it
  Hw  arm H's note (bare names) on the Aw history
  Ew  arm E's note (name, file, lines, first definition line) on the Aw history

F1  prompt size: on the fidelity states, the median absolute relative difference between Aw's prompt size and the
    size logged by the original run. "The rendering accounts for the size gap" if it is at most 0.5%.
F2  mangled names: share of usable replays whose first call is a read_file with a mangled line-bound name, A minus
    Aw. "The v28 rendering raises mangled bound names" if the lower 95% bound is above 0.
F3  the encoding effect under the original rendering: Ew minus Hw on any unopened true neighbor touched. "Holds
    under the original runs' rendering" if the lower 95% bound is above 0.
Descriptive, no rule: Aw minus A on the registered outcome; the first call's tool by arm; agreement of the first call
with the original run's own next call (same tool; same tool and file) under A and under Aw; the original runs' own
rate of mangled bound names at the same states.

Scorer, exclusions and bootstrap are those of the earlier experiments (gates_c.py, analyze_forks.py: imported).
Complete states only (the four arms and seeds 1 to 3 usable); below 200 complete states everything is EXPLORATORY.
"""
import argparse
import collections
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import FAILURES, any_true, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import BOUNDS, clean, mangled  # noqa: E402

ARMS = ('A', 'Aw', 'Hw', 'Ew')
SEEDS = (1, 2, 3)
MIN_COMPLETE = 200


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def raw(tab):
    vals = [v for vs in tab.values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


def fidelity(path, label):
    if not path.exists():
        print(f'  {label}: no {path.name}')
        return None
    rows = load_rows(path)
    good = [r for r in rows if not r.get('error') and r.get('replayed_prompt_tokens') and r.get('logged_prompt_tokens')]
    if not good:
        print(f'  {label}: {len(rows)} rows, none usable')
        return None
    rel = [(r['replayed_prompt_tokens'] - r['logged_prompt_tokens']) / r['logged_prompt_tokens'] for r in good]
    med = st.median(abs(x) for x in rel)
    exact = sum(1 for r in good if r['replayed_prompt_tokens'] == r['logged_prompt_tokens'])
    below = sum(1 for x in rel if x < 0)
    print(f'  {label}: {len(good)} of {len(rows)} rows usable; median absolute relative difference {100 * med:.2f}%, '
          f'mean {100 * st.mean(abs(x) for x in rel):.2f}%, max {100 * max(abs(x) for x in rel):.2f}%; '
          f'replayed equals logged in {exact}, below it in {below}, above it in {len(good) - exact - below}')
    return med


def bounded(call):
    args = (call or {}).get('arguments')
    return (call or {}).get('function_name') == 'read_file' and isinstance(args, dict) and any(clean(k) in BOUNDS for k in args)


def norm(p):
    p = str(p or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run = Path(args.run_dir)
    states = load_states(args.states)

    print('F1. Prompt size against the size the original run logged at the same step')
    fidelity(run / 'fidelity.jsonl', 'A  (dictionary results, harness v28)')
    med_w = fidelity(run / 'fidelity_w.jsonl', 'Aw (string results, as the original runs)')
    if med_w is not None:
        print('  F1 verdict: ' + ('the rendering accounts for the size gap (median at most 0.5%)' if med_w <= 0.005
                                  else 'the rendering does not account for the size gap (median above 0.5%)'))

    rows = [r for r in load_rows(run / 'results.jsonl') if r['arm'] in ARMS]
    n_arm = collections.Counter(r['arm'] for r in rows)
    fail = collections.Counter()
    usable = collections.defaultdict(dict)
    for r in rows:
        kind = failure(r)
        if kind:
            fail[(r['arm'], kind)] += 1
        elif r['seed'] in SEEDS:
            usable[skey(r)][(r['arm'], r['seed'])] = r
    print(f'\n{len(rows)} replays of arms {list(ARMS)}')
    print('Interface failures by arm (excluded):')
    for a in ARMS:
        k = sum(fail[(a, f)] for f in FAILURES)
        print(f'  {a:2s}: {k}/{n_arm[a]} (' + ', '.join(f'{f} {fail[(a, f)]}' for f in FAILURES) + ')')
    need = {(a, s) for a in ARMS for s in SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    tag = '' if len(complete) >= MIN_COMPLETE else ' [EXPLORATORY: fewer than 200 complete states]'
    print(f'complete states: {len(complete)} of {len(states)}{tag}')
    if not complete:
        return

    hit = {a: collections.defaultdict(list) for a in ARMS}
    mang = {a: collections.defaultdict(list) for a in ARMS}
    counts = {a: collections.Counter() for a in ARMS}
    tools = {a: collections.Counter() for a in ARMS}
    orig = collections.Counter()
    for k in complete:
        oc = states[k].get('observed_next_call') or {}
        orig['states'] += 1
        orig['bounded'] += int(bounded(oc))
        orig['mangled'] += int(mangled(oc))
        for a in ARMS:
            for s in SEEDS:
                call = usable[k][(a, s)]['next_call']
                hit[a][k].append(any_true(states[k], call))
                m = int(mangled(call))
                mang[a][k].append(m)
                counts[a]['bounded'] += int(bounded(call))
                counts[a]['mangled'] += m
                tools[a][call['function_name']] += 1
                same_tool = call['function_name'] == oc.get('function_name')
                counts[a]['same tool'] += int(same_tool)
                if same_tool and call['function_name'] == 'read_file':
                    counts[a]['read_file in both'] += 1
                    counts[a]['read_file in both, same file'] += int(
                        norm((call.get('arguments') or {}).get('filepath')) == norm((oc.get('arguments') or {}).get('filepath')))

    print(f'\nF2. First call is a read_file with a mangled line-bound name, percent of replays [95% interval] | raw{tag}')
    for a in ARMS:
        b = counts[a]['bounded']
        print(f'  {a:2s}: {pct(boot_ci(mang[a]))} | {raw(mang[a])}; of the {b} reads with a line bound: '
              + (f'{100 * counts[a]["mangled"] / b:.1f}%' if b else 'n/a'))
    d = diff_ci(mang['A'], mang['Aw'])
    print(f'  F2 A - Aw: {dpt(d)}: ' + ('the v28 rendering raises mangled bound names (lower bound above 0)'
                                         if d[1] is not None and d[1] > 0 else 'no detectable difference (lower bound not above 0)') + tag)
    b = orig['bounded']
    print(f'  original runs, their own next call at the same {orig["states"]} states: {orig["mangled"]} mangled of {b} reads with a line bound'
          + (f' ({100 * orig["mangled"] / b:.1f}%)' if b else ''))

    print(f'\nF3. Any unopened true neighbor touched, percent [95% interval] | raw{tag}')
    for a in ARMS:
        print(f'  {a:2s}: {pct(boot_ci(hit[a]))} | {raw(hit[a])}')
    d = diff_ci(hit['Ew'], hit['Hw'])
    print(f'  F3 Ew - Hw: {dpt(d)}: ' + ("the encoding effect holds under the original runs' rendering (lower bound above 0)"
                                          if d[1] is not None and d[1] > 0 else 'not detected under the original rendering (lower bound not above 0)') + tag)
    print(f'  Aw - A (no rule): {dpt(diff_ci(hit["Aw"], hit["A"]))}')
    print(f'  Ew - Aw (no rule): {dpt(diff_ci(hit["Ew"], hit["Aw"]))}')
    print(f'  Hw - Aw (no rule): {dpt(diff_ci(hit["Hw"], hit["Aw"]))}')

    print('\nDescriptive: the first call, by arm')
    n = len(complete) * len(SEEDS)
    for a in ARMS:
        mix = ', '.join(f'{t} {100 * c / n:.1f}%' for t, c in tools[a].most_common())
        print(f'  {a:2s}: {mix}')
    print('Descriptive: agreement with the original run\'s own next call (A and Aw only share the original\'s last message)')
    for a in ('A', 'Aw'):
        rb = counts[a]['read_file in both']
        print(f'  {a:2s}: same tool {100 * counts[a]["same tool"] / n:.1f}% of replays; read_file in both {rb}, '
              + (f'same file in {100 * counts[a]["read_file in both, same file"] / rb:.1f}% of those' if rb else 'n/a'))


if __name__ == '__main__':
    main()
