"""Exploratory views of the five-call experiment (pre-registration 06 fixes rules at five calls only; nothing here is a rule).

1. Reaching the fix by call: share of replays that have been shown a line the gold patch changes (Yline), or have
   opened a file it changes (Yfile), by the end of model call k = 1..5, per arm, with E minus H at each k.
   Complete states and scoring are those of analyze_k.py (imported).
2. Mangled line-bound names inside the horizon: read_file calls whose bound arrives under a mangled name, by arm and
   by position (first model call, later calls), and what the tool returned for them. Every usable replay is used.

Usage: py -I -X utf8 analysis/explore_k.py [run_dir]
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import ARMS, first_call_failure, score  # noqa: E402
from gates_c import load_states, skey  # noqa: E402
from mangled_sensitivity import BOUNDS, clean, mangled  # noqa: E402


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f} [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results' / 'k' / 'forks'
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    pop = json.load(open(HERE / 'fork_states_k' / 'population.json', encoding='utf-8'))
    member = {tuple(g['key']): (p, g) for p in ('R', 'U') for g in pop[p]}
    rows = [json.loads(l) for l in open(run / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    usable = collections.defaultdict(dict)
    for r in rows:
        k = skey(r)
        if k in member and r['arm'] in ARMS and r['seed'] in member[k][1]['seeds'] and not first_call_failure(r):
            usable[k][(r['arm'], r['seed'])] = r
    print('Five-call experiment, exploratory views (no registered rule).')
    for p in ('R', 'U'):
        seeds = pop['seeds'][p]
        complete = sorted(k for k, (pp, g) in member.items() if pp == p
                          and {(a, s) for a in ARMS for s in seeds} <= set(usable.get(k, {})))
        scored = {(k, a, s): score(states[k], member[k][1], usable[k][(a, s)]) for k in complete for a in ARMS for s in seeds}
        print(f'\n1. Population {p}, {len(complete)} complete states: reached by the end of model call k, percent [95% interval]')
        for y in ('Yline', 'Yfile'):
            for kk in range(1, 6):
                tab = {a: collections.defaultdict(list) for a in ARMS}
                for (k, a, s), sc in scored.items():
                    first = sc[f'first_{y}']
                    tab[a][k].append(int(first is not None and first <= kk))
                line = '; '.join(f'{a} {pct(boot_ci(tab[a]))}' for a in ARMS)
                print(f'  {y} by call {kk}: {line}; E - H {dpt(diff_ci(tab["E"], tab["H"]))}; E - A {dpt(diff_ci(tab["E"], tab["A"]))}')

    print('\n2. read_file calls with a mangled line-bound name inside the horizon (every usable replay)')
    cnt = collections.defaultdict(collections.Counter)
    for k, d in usable.items():
        for (a, s), r in d.items():
            for si, step in enumerate(r.get('steps') or [], 1):
                for c in step['calls']:
                    if c['function_name'] != 'read_file' or not isinstance(c.get('arguments'), dict):
                        continue
                    args = c['arguments']
                    if not any(clean(x) in BOUNDS for x in args):
                        continue
                    where = 'first call' if si == 1 else 'later calls'
                    cnt[(a, where)]['bounded'] += 1
                    if mangled({'function_name': 'read_file', 'arguments': args}):
                        cnt[(a, where)]['mangled'] += 1
                        res = c.get('result') or {}
                        asked = next((v for x, v in args.items() if clean(x) == 'start_line' and not str(x).isidentifier()), None)
                        if c.get('executed') and res.get('status') == 'ok' and asked not in (None, 1) and res.get('start_line') == 1:
                            cnt[(a, where)]['asked another start line, got line 1'] += 1
    for where in ('first call', 'later calls'):
        for a in ARMS:
            c = cnt[(a, where)]
            b = c['bounded']
            print(f'  {a:2s}, {where}: {c["mangled"]} of {b} reads with a line bound' + (f' ({100 * c["mangled"] / b:.1f}%)' if b else '')
                  + f'; asked for another start line and got the file from line 1: {c["asked another start line, got line 1"]}')
    tot = collections.Counter()
    for c in cnt.values():
        tot.update(c)
    print(f'  all arms and calls: {tot["mangled"]} of {tot["bounded"]} reads with a line bound ({100 * tot["mangled"] / tot["bounded"]:.1f}%); '
          f'asked for another start line and got the file from line 1: {tot["asked another start line, got line 1"]}')


if __name__ == '__main__':
    main()
