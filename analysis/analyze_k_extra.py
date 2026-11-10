"""Supplement to analyze_k.py for experiment E (pre-registration 06).

It prints what the pre-registration says is reported beside the registered output and what analyze_k.py does not print.
Usage: py -I -X utf8 analysis/analyze_k_extra.py <run_dir>

1. Interface failures by population, arm and kind, counted from the raw rows. Errors are split by type (a context
   window overflow, anything else) and by the number of model calls completed before the error.
2. K1 (E minus H on Yline in R) clustered by task, beside the state-clustered value. K1 is "robust" only if the lower
   95% bound is above 0 under both clusterings. K2 (E minus A on Yfile in U) by task as well (descriptive).
3. Descriptive, no rule: the index of the first model call with Yfile and with Yline, and the share of replays in
   which a call touches a listed true entry or a rewired entry.
4. EXPLORATORY sensitivity: replays that ended in an error after a usable first response are kept and scored on the
   calls that executed.

Scoring, the usable-replay rule and the bootstrap are imported from analyze_k.py, gates_c.py and analyze_forks.py
(frozen), not copied. Written on Nov 10, 2026, before any outcome of the full run was read: only its error messages
and progress counts had been looked at.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import ARMS, dpt, first_call_failure, pct, score  # noqa: E402
from gates_c import failure, load_states, skey  # noqa: E402

POPS = ('R', 'U')
KINDS = ('context_overflow', 'other_error', 'no_call', 'unknown_tool', 'malformed_args')


def error_kind(r):
    e = str(r.get('error') or '')
    return 'context_overflow' if ('ContextWindowExceeded' in e or 'maximum context' in e) else 'other_error'


def first_response_usable(r):
    """True if the first model response has a call the frozen failure rule accepts, whatever happened later."""
    steps = r.get('steps') or []
    first = steps[0]['calls'][0] if steps and steps[0]['calls'] else None
    call = {'function_name': first['function_name'], 'arguments': first['arguments']} if first else None
    return failure({'error': None, 'next_call': call}) is None


def complete_states(member, usable):
    return {p: sorted(k for k, (pp, g) in member.items() if pp == p
                      and {(a, s) for a in ARMS for s in g['seeds']} <= set(usable.get(k, {})))
            for p in POPS}


def table(pop, complete, scored, p, y, cluster):
    """{arm: {cluster: [values]}} on the complete states of population p; cluster is 'state' or 'task'."""
    t = {a: collections.defaultdict(list) for a in ARMS}
    for k in complete[p]:
        c = k if cluster == 'state' else k[0]
        for a in ARMS:
            for s in pop['seeds'][p]:
                t[a][c].append(scored[(k, (a, s))][y])
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--population', default=str(HERE / 'fork_states_k' / 'population.json'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(args.states)
    pop = json.load(open(args.population, encoding='utf-8'))
    member = {tuple(g['key']): (p, g) for p in POPS for g in pop[p]}
    rows = [json.loads(l) for l in open(Path(args.run_dir) / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    design = [r for r in rows if skey(r) in member and r['arm'] in ARMS and r['seed'] in member[skey(r)][1]['seeds']]
    keys = collections.Counter((skey(r), r['arm'], r['seed']) for r in design)
    expected = sum(len(g['seeds']) * len(ARMS) for p in POPS for g in pop[p])
    print(f'rows in the file: {len(rows)}; rows of the design: {len(design)} of {expected} expected; '
          f'distinct (state, arm, seed): {len(keys)}; repeated keys: {sum(1 for v in keys.values() if v > 1)}')

    # 1. interface failures from the raw rows
    n = collections.Counter()
    fail = collections.Counter()
    after = collections.Counter()
    for r in design:
        p = member[skey(r)][0]
        n[(p, r['arm'])] += 1
        kind = first_call_failure(r)
        if kind == 'error':
            kind = error_kind(r)
            after[(kind, len(r.get('steps') or []))] += 1
        if kind:
            fail[(p, r['arm'], kind)] += 1
    print('\n1. Interface failures by population and arm (excluded from every estimate):')
    for p in POPS:
        for a in ARMS:
            tot = sum(fail[(p, a, k)] for k in KINDS)
            share = f'{tot / n[(p, a)]:.4f}' if n[(p, a)] else 'n/a'
            print(f'  {p} {a:2s}: {tot}/{n[(p, a)]} = {share} (' + ', '.join(f'{k} {fail[(p, a, k)]}' for k in KINDS) + ')')
    for (kind, done), c in sorted(after.items()):
        print(f'  {kind}: {c} replays ended after {done} completed model calls')

    usable = collections.defaultdict(dict)
    for r in design:
        if not first_call_failure(r):
            usable[skey(r)][(r['arm'], r['seed'])] = r
    complete = complete_states(member, usable)
    scored = {(k, key): score(states[k], member[k][1], r) for p in POPS for k in complete[p] for key, r in usable[k].items()}
    print(f'\ncomplete states: R {len(complete["R"])} of {len(pop["R"])} ({len({k[0] for k in complete["R"]})} tasks), '
          f'U {len(complete["U"])} of {len(pop["U"])} ({len({k[0] for k in complete["U"]})} tasks)')

    # 2. the two rules under both clusterings
    print('\n2. Rules under both clusterings (points [95% interval]):')
    verdict = {}
    for tag, p, y, a, b in (('K1', 'R', 'Yline', 'E', 'H'), ('K2', 'U', 'Yfile', 'E', 'A')):
        if not complete[p]:
            print(f'  {tag}: no complete state in {p}')
            continue
        for cl in ('state', 'task'):
            t = table(pop, complete, scored, p, y, cl)
            d = diff_ci(t[a], t[b])
            verdict[(tag, cl)] = d
            print(f'  {tag} {a} - {b} on {y} in {p}, clustered by {cl} ({len(t[a])} clusters): {dpt(d)}')
    if ('K1', 'state') in verdict and verdict[('K1', 'state')][0] is not None:
        lo_s, lo_t = verdict[('K1', 'state')][1], verdict[('K1', 'task')][1]
        if lo_s > 0 and lo_t > 0:
            word = 'the legible list brings the agent to fix code within five calls; ROBUST (both lower bounds above 0)'
        elif lo_s > 0:
            word = 'the legible list brings the agent to fix code within five calls (state clustering); NOT robust to task clustering'
        else:
            word = 'no detectable gain'
        print(f'  K1 verdict: {word}')
    if ('K2', 'state') in verdict and verdict[('K2', 'state')][0] is not None:
        print('  K2 verdict: ' + ('the list delays reaching the fix' if verdict[('K2', 'state')][2] < 0 else 'no harm is claimed'))

    # 3. descriptive
    print('\n3. Descriptive (no rule):')
    for p in POPS:
        if not complete[p]:
            continue
        print(f'  population {p}:')
        for a in ARMS:
            ss = [scored[(k, (a, s))] for k in complete[p] for s in pop['seeds'][p]]
            for y in ('Yfile', 'Yline'):
                c = collections.Counter(s[f'first_{y}'] for s in ss)
                dist = ', '.join(f'call {i}: {c[i]}' for i in sorted(x for x in c if x is not None))
                print(f'    {a:2s} first model call with {y}: {dist or "none"}; never {c[None]} of {len(ss)}')
        for name, field in (('a listed true entry', 'touch_true'), ('a rewired entry', 'touch_rewired')):
            for a in ARMS:
                t = collections.defaultdict(list)
                for k in complete[p]:
                    for s in pop['seeds'][p]:
                        t[k].append(int(any(c[field] for c in scored[(k, (a, s))]['calls'])))
                vals = [v for vs in t.values() for v in vs]
                print(f'    {a:2s} any call touches {name}: {pct(boot_ci(t))} | {sum(vals)}/{len(vals)}')

    # 4. sensitivity
    print('\n4. EXPLORATORY sensitivity: replays that ended in an error after a usable first response are kept')
    usable2 = collections.defaultdict(dict)
    for r in design:
        if first_response_usable(r):
            usable2[skey(r)][(r['arm'], r['seed'])] = r
    complete2 = complete_states(member, usable2)
    scored2 = {(k, key): score(states[k], member[k][1], r) for p in POPS for k in complete2[p] for key, r in usable2[k].items()}
    print(f'  complete states: R {len(complete2["R"])}, U {len(complete2["U"])}')
    for tag, p, y, a, b in (('K1', 'R', 'Yline', 'E', 'H'), ('K2', 'U', 'Yfile', 'E', 'A')):
        if not complete2[p]:
            continue
        for cl in ('state', 'task'):
            t = table(pop, complete2, scored2, p, y, cl)
            if cl == 'state':
                for arm in (a, b):
                    vals = [v for vs in t[arm].values() for v in vs]
                    print(f'  {p} {y} {arm}: {pct(boot_ci(t[arm]))} | {sum(vals)}/{len(vals)}')
            print(f'  {tag} {a} - {b} on {y} in {p}, clustered by {cl}: {dpt(diff_ci(t[a], t[b]))} [EXPLORATORY]')


if __name__ == '__main__':
    main()
