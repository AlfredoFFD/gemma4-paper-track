"""What a mangled line bound costs inside the five-call run, and what precedes it (EXPLORATORY; changes no registered number).

Usage: py -I -X utf8 analysis/explore_defect_cost.py [<run_dir>]      (default: analysis/results/k/forks)

Reads the raw replay records of the five-call experiment (pre-registration 06). Usable replays only, by the frozen
rule of analyze_k.py (no error, a first response with an acceptable call), as in analysis/explore_k.py. A ranged read
is an executed read_file call that carries a line bound; it is mangled if a bound name is not a plain identifier
(mangled_sensitivity.py). The harness drops a name it does not know, so a mangled read returns the file from line 1.

1. What the model asked for and what it got.
2. What the next model call does: does it read the same file again?
3. How much of an arm's calls go to mangled reads.
4. What came just before a ranged read, and how often the read is then mangled.
Intervals: 95% bootstrap clustered by state, 2,000 resamples (analyze_forks.boot_ci, diff_ci).
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import ARMS, first_call_failure  # noqa: E402
from gates_c import load_states, skey  # noqa: E402
from mangled_sensitivity import BOUNDS, clean  # noqa: E402


def is_read(c):
    return c.get('function_name') == 'read_file' and isinstance(c.get('arguments'), dict)


def bounded(c):
    return is_read(c) and any(clean(k) in BOUNDS for k in c['arguments'])


def mangled(c):
    return is_read(c) and any((not str(k).isidentifier()) and clean(k) in BOUNDS for k in c['arguments'])


def path(c):
    p = str(c['arguments'].get('filepath') or c['arguments'].get('"filepath"') or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def wanted_start(c):
    a = {clean(k): v for k, v in c['arguments'].items()}
    try:
        return int(a['start_line']) if 'start_line' in a else None
    except (TypeError, ValueError):
        return None


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f} [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def raw(tab):
    vals = [v for vs in tab.values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


def last_history_call(state):
    """The tool call whose result is the last thing the model saw at the pause."""
    for s in reversed(state['steps']):
        if s.get('tool_calls'):
            tc = s['tool_calls'][0]
            return {'function_name': tc['function_name'], 'arguments': tc.get('arguments') or {}}
    return None


def kind_before(prev, returned_from_1):
    if prev is None:
        return 'nothing'
    if prev['function_name'] == 'read_file' and isinstance(prev.get('arguments'), dict):
        if mangled(prev):
            return 'a read_file with a mangled bound (it returned the file from line 1)'
        if bounded(prev):
            return 'a read_file with a well-formed bound'
        return 'a read_file with no bound (it returned the file from line 1)'
    if prev['function_name'] == 'run_command':
        return 'a shell command'
    return 'another tool'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results' / 'k' / 'forks'
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    rows = [json.loads(l) for l in open(run_dir / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    usable = [r for r in rows if r['arm'] in ARMS and not first_call_failure(r)]
    print(f'EXPLORATORY. Five-call run: {len(rows)} rows, {len(usable)} usable replays.')

    n = collections.Counter()
    past150 = collections.Counter()
    got_asked = collections.Counter()
    reread = {True: collections.defaultdict(list), False: collections.defaultdict(list)}   # mangled -> state -> 0/1
    again = collections.defaultdict(list)       # after a mangled read that is followed by a read of the same file: mangled again?
    trig = {a: collections.defaultdict(lambda: collections.defaultdict(list)) for a in ('first', 'later')}
    per_arm = {a: collections.Counter() for a in ARMS}
    for r in usable:
        k = skey(r)
        steps = r.get('steps') or []
        prev = last_history_call(states[k]) if r['arm'] == 'A' else None   # arm A's first call follows the pause's tool result
        any_m = False
        for i, s in enumerate(steps):
            for c in s['calls']:
                if c.get('executed'):
                    per_arm[r['arm']]['executed'] += 1
                    per_arm[r['arm']]['mangled_reads'] += int(mangled(c))
                    any_m |= mangled(c)
            c = s['calls'][0] if len(s['calls']) == 1 else None
            if c is not None and bounded(c) and c.get('executed'):
                m = mangled(c)
                n[m] += 1
                want = wanted_start(c)
                res = c.get('result') or {}
                if want is not None:
                    past150[(m, 'known')] += 1
                    past150[(m, 'past')] += int(want > 150)
                    got_asked[(m, 'known')] += 1
                    got_asked[(m, 'same')] += int(res.get('start_line') == want)
                if i + 1 < len(steps) and len(steps[i + 1]['calls']) == 1:
                    nxt = steps[i + 1]['calls'][0]
                    same = int(is_read(nxt) and path(nxt) == path(c))
                    reread[m][k].append(same)
                    if m and same and bounded(nxt):
                        again[k].append(int(mangled(nxt)))
                if i == 0:
                    if r['arm'] == 'A':
                        trig['first'][kind_before(prev, None)][k].append(int(m))
                else:
                    pc = steps[i - 1]['calls'][-1] if steps[i - 1]['calls'] else None
                    if pc is not None and pc.get('executed'):
                        trig['later'][kind_before(pc, None)][k].append(int(m))
        per_arm[r['arm']]['replays'] += 1
        per_arm[r['arm']]['with_mangled'] += int(any_m)

    print('\n1. Executed ranged reads that are the only call of their response')
    for m, name in ((False, 'well-formed'), (True, 'mangled')):
        print(f'  {name}: {n[m]}; asked to start past line 150: {past150[(m, "past")]} of {past150[(m, "known")]} '
              f'({100 * past150[(m, "past")] / max(1, past150[(m, "known")]):.1f}%); returned from the start line asked for: '
              f'{got_asked[(m, "same")]} of {got_asked[(m, "known")]} ({100 * got_asked[(m, "same")] / max(1, got_asked[(m, "known")]):.1f}%)')

    print('\n2. The next model call reads the same file again')
    for m, name in ((False, 'after a well-formed ranged read'), (True, 'after a mangled ranged read')):
        print(f'  {name}: {pct(boot_ci(reread[m]))} | {raw(reread[m])}')
    print(f'  mangled minus well-formed: {dpt(diff_ci(reread[True], reread[False]))}')
    print(f'  of the ranged re-reads after a mangled read, mangled again: {pct(boot_ci(again))} | {raw(again)}')

    print('\n3. Mangled reads among an arm\'s executed calls')
    for a in ARMS:
        c = per_arm[a]
        print(f'  {a:2s}: {c["mangled_reads"]} of {c["executed"]} executed calls ({100 * c["mangled_reads"] / max(1, c["executed"]):.1f}%); '
              f'replays with at least one: {c["with_mangled"]} of {c["replays"]} ({100 * c["with_mangled"] / max(1, c["replays"]):.1f}%)')

    print('\n4. Share of ranged reads that are mangled, by what the model saw just before')
    print('  first call of arm A (the pause\'s own tool result is the last thing in the prompt):')
    for kind, tab in sorted(trig['first'].items()):
        print(f'    after {kind}: {pct(boot_ci(tab))} | {raw(tab)}')
    print('  calls 2 to 5, all arms (the previous call\'s result is the last thing in the prompt):')
    for kind, tab in sorted(trig['later'].items()):
        print(f'    after {kind}: {pct(boot_ci(tab))} | {raw(tab)}')


if __name__ == '__main__':
    main()
