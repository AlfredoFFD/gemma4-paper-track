"""Mangled argument names and the registered outcome (EXPLORATORY sensitivity; changes no registered number).

The registered scorer treats a read whose line bound arrives under a mangled name (for example 'start_line"') as the
harness executes it: the unknown argument is dropped and the read shows the file from line 1. This script asks how the
registered outcome would read if the bound the model wrote had been honored: argument names are cleaned (quotes,
backslashes and spaces removed) before the same registered scorer is applied.

Usage: py -I -X utf8 analysis/mangled_sensitivity.py
Reads the hosted runs (analysis/results/v5, v6, v8), the tool-channel run (analysis/results/d1/forks) and, when they
exist, the other runs under analysis/results/. Prints a report.
"""
import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402

SEEDS = (1, 2, 3)
BOUNDS = ('start_line', 'end_line')


def clean(name):
    return re.sub(r'[\\"\'\s]', '', str(name))


def mangled(call):
    args = (call or {}).get('arguments')
    return isinstance(args, dict) and any((not str(k).isidentifier()) and clean(k) in BOUNDS for k in args)


def intended(call):
    """The call with mangled bound names restored (a well-formed name wins if both are present)."""
    args = dict(call['arguments'])
    for k in list(args):
        if (not str(k).isidentifier()) and clean(k) in BOUNDS:
            v = args.pop(k)
            args.setdefault(clean(k), v)
    return {'function_name': call['function_name'], 'arguments': args}


def opens_listed_file(state, call):
    """True if the call is a read_file on the file of an unopened true neighbor."""
    if call.get('function_name') != 'read_file' or not isinstance(call.get('arguments'), dict):
        return False
    path = str(call['arguments'].get('filepath') or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while path.startswith(pre):
            path = path[len(pre):]
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    files = {state['neighbor_spans'][n]['path'] for n in unshown if state['neighbor_spans'].get(n)}
    return path in files


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def report(title, states_path, run_dirs, arms, contrasts):
    states = load_states(states_path)
    usable = collections.defaultdict(dict)
    for d in run_dirs:
        for r in load_rows(Path(d) / 'results.jsonl'):
            if r['arm'] in arms and r['seed'] in SEEDS and not failure(r):
                usable[skey(r)][(r['arm'], r['seed'])] = r
    need = {(a, s) for a in arms for s in SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    print(f'\n{title}: {len(complete)} complete states, arms {list(arms)}')
    reg = {a: collections.defaultdict(list) for a in arms}
    itd = {a: collections.defaultdict(list) for a in arms}
    for a in arms:
        n = m = m_listed = opened = opened_m = flips = 0
        for k in complete:
            for s in SEEDS:
                call = usable[k][(a, s)]['next_call']
                x = any_true(states[k], call)
                bad = mangled(call)
                y = any_true(states[k], intended(call)) if bad else x
                reg[a][k].append(x)
                itd[a][k].append(y)
                n += 1
                m += int(bad)
                flips += int(y != x)
                if opens_listed_file(states[k], call):
                    opened += 1
                    opened_m += int(bad)
                    m_listed += int(bad)
        print(f'  {a:3s}: registered {pct(boot_ci(reg[a]))} | bound honored {pct(boot_ci(itd[a]))} | '
              f'replays with a mangled bound {m} of {n} ({100 * m / n:.1f}%), {flips} of them change the outcome; '
              f'reads of a listed unopened file {opened}, with a mangled bound {opened_m}')
    for a, b in contrasts:
        print(f'  {a} - {b}: registered {dpt(diff_ci(reg[a], reg[b]))} | bound honored {dpt(diff_ci(itd[a], itd[b]))}')


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    res = HERE / 'results'
    print('Mangled bound names and the registered outcome (EXPLORATORY). Outcome: any unopened true neighbor touched.')
    report('Hosted runs v5 + v6 + v8 (experiments A and B)', HERE / 'fork_states' / 'states.jsonl',
           [res / 'v5' / 'forks', res / 'v6' / 'forks', res / 'v8' / 'forks'],
           ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE'), (('E', 'H'), ('D', 'H'), ('E', 'A'), ('H', 'A')))
    later = (('Tool-channel run (D1)', 'd1', ('P', 'PE', 'E'), (('PE', 'P'), ('PE', 'E'))),
             ('Experiment C run', 'c', ('Ep', 'EL', 'ES', 'E', 'H'), (('E', 'H'), ('EL', 'H'), ('ES', 'H'))),
             ('Second model 26B-A4B (D2a)', 'd2_26b', ('A', 'H', 'E', 'RE'), (('E', 'H'),)),
             ('Second model E4B (D2b)', 'd2_e4b', ('A', 'H', 'E', 'RE'), (('E', 'H'),)))
    for title, name, arms, contrasts in later:
        d = res / name / 'forks'
        if (d / 'results.jsonl').exists():
            report(title, HERE / 'fork_states_d' / 'states.jsonl', [d], arms, contrasts)
        else:
            print(f'\n{title}: no results under analysis/results/{name}/forks yet')


if __name__ == '__main__':
    main()
