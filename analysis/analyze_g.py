"""Analysis of experiment G (pre-registration 08): fresh episodes, a patched harness, and the newest harness wheels.

Usage: py -I -X utf8 analysis/analyze_g.py <run_dir> [--onestep <onestep_run_dir>]
  <run_dir>          results_g.jsonl from analysis/modal_g/forks_g_runner.py (parts "fresh" and "fix")
  <onestep_run_dir>  results.jsonl and fidelity.jsonl from the one-step runner (arms H and E)

Part "fresh" (arm N: a new episode from the task prompt, up to 8 model calls, read-only calls execute)
  N1  among executed read_file calls that carry a line bound, the share whose bound name is mangled. "The defect
      occurs in fresh episodes" if the lower 95% bound (clustered by task) is above 2.1%, the share in the 318
      original traces.
Part "fix" (states of R with seeds 11 to 15 and of U with seeds 11 to 13, five model calls; arms A stock, AF bounds
honored, EF bounds honored plus the legible note)
  G1  EF minus A on Yline (shown a line the gold patch changes), all complete states of R and U together, seeds 11 to
      13. "The two changes together bring the agent to the fix's lines" if the lower 95% bound is above 0, clustered
      by state; robust only if also above 0 clustered by task.
  G2  AF minus A on Yline, same states and seeds. "Honoring the bound alone raises reach" if the lower 95% bound is
      above 0; otherwise no detectable gain from the argument fix alone.
  G3  EF minus AF on Yline in R, seeds 11 to 15. "The legible list adds reach beyond the argument fix" if the lower
      95% bound is above 0; otherwise no detectable gain from the list once the bound is honored.
Part "one step" (arms H and E on the 407 states, seeds 1 to 3)
  S1  E minus H on any unopened true neighbor touched. "The encoding effect holds on this harness" if the lower 95%
      bound is above 0. Applies if at least 200 states are complete.
Everything else printed here is descriptive.

Scoring, exclusions and the bootstrap are imported from the frozen modules (analyze_k.score and first_call_failure,
gates_c.failure and any_true, analyze_forks.boot_ci and diff_ci, mangled_sensitivity.clean and BOUNDS): 95% bootstrap
intervals, 2,000 resamples, seed 0.
"""
import argparse
import collections
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import first_call_failure, score, stop_group  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import BOUNDS, clean  # noqa: E402

FRESH_SEEDS = (1, 2, 3)
FIX_ARMS = ('A', 'AF', 'EF')
FIX_SEEDS = (11, 12, 13)                                    # the pooled contrasts G1 and G2
POP_SEEDS = {'R': (11, 12, 13, 14, 15), 'U': (11, 12, 13)}  # what ran; G3 uses all five seeds of R
ONE_ARMS = ('H', 'E')
ONE_SEEDS = (1, 2, 3)
ORIGINAL_SHARE = 0.021  # 42 of 2,012 ranged reads in the 318 original traces (analysis/mangled_args.py)
MIN_COMPLETE_ONE = 200
K_FIX = 5


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def raw(tab):
    vals = [v for vs in tab.values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


def has_bound(args):
    return isinstance(args, dict) and any(clean(k) in BOUNDS for k in args)


def is_mangled(args):
    return isinstance(args, dict) and any((not str(k).isidentifier()) and clean(k) in BOUNDS for k in args)


def ranged_reads(r):
    """(model call index, mangled, returned start line) of every executed read_file call with a line bound."""
    out = []
    for i, step in enumerate(r.get('steps') or [], 1):
        for c in step['calls']:
            if c['function_name'] == 'read_file' and c['executed'] and has_bound(c['arguments']):
                out.append((i, int(is_mangled(c['arguments'])), (c.get('result') or {}).get('start_line')))
    return out


def error_kind(r):
    e = str(r.get('error') or '')
    return 'context_overflow' if ('ContextWindowExceeded' in e or 'maximum context' in e) else 'other_error'


# ----------------------------------------------------------------------------- part "fresh"

def part_fresh(rows, fresh):
    print('PART "fresh": new episodes from the task prompt, arm N, seeds 1 to 3, up to 8 model calls')
    design = [r for r in rows if r.get('population') == 'FRESH' and r['arm'] == 'N' and r['seed'] in FRESH_SEEDS
              and r['task'] in fresh]
    keys = collections.Counter((r['task'], r['seed']) for r in design)
    print(f'  episodes in the file: {len(design)} of {len(fresh) * len(FRESH_SEEDS)} expected; repeated keys: '
          f'{sum(1 for v in keys.values() if v > 1)}')
    errs = collections.Counter(error_kind(r) for r in design if r.get('error'))
    ok = [r for r in design if not r.get('error')]
    print(f'  episodes that ended in an error (excluded): {sum(errs.values())} {dict(errs)}; analyzed: {len(ok)} from '
          f'{len({r["task"] for r in ok})} tasks')
    stops = collections.Counter(stop_group(r.get('stop')) for r in ok)
    print('  stop reasons: ' + ', '.join(f'{k} {v}' for k, v in sorted(stops.items(), key=lambda x: (-x[1], x[0]))))
    if ok:
        print(f'  model calls per episode: mean {st.mean(len(r.get("steps") or []) for r in ok):.2f}; executed calls: mean '
              f'{st.mean(r.get("executed_calls", 0) for r in ok):.2f}')
    rel = []
    for r in ok:
        got = (r.get('steps') or [{}])[0].get('prompt_tokens')
        logged = fresh[r['task']]['logged_first_prompt_tokens']
        if got and logged:
            rel.append((got - logged) / logged)
    if rel:
        print(f'  first prompt against the size the original run logged (descriptive): median difference '
              f'{100 * st.median(rel):+.2f}%, median absolute {100 * st.median(abs(x) for x in rel):.2f}%, '
              f'range {100 * min(rel):+.2f}% to {100 * max(rel):+.2f}% ({len(rel)} episodes)')
    by_task = collections.defaultdict(list)
    later = collections.defaultdict(list)
    first = collections.defaultdict(list)
    n_line1 = n_mangled = 0
    episodes_with_read = episodes_with_mangled = 0
    for r in ok:
        rr = ranged_reads(r)
        episodes_with_read += bool(rr)
        episodes_with_mangled += any(m for _i, m, _s in rr)
        for i, m, start in rr:
            by_task[r['task']].append(m)
            (first if i == 1 else later)[r['task']].append(m)
            if m:
                n_mangled += 1
                n_line1 += int(start == 1)
    n = sum(len(v) for v in by_task.values())
    print(f'  executed read_file calls with a line bound: {n} in {episodes_with_read} episodes ({len(by_task)} tasks)')
    t = boot_ci(by_task)
    print(f'  N1 share with a mangled bound name: {pct(t)} | {raw(by_task)}')
    if t[0] is not None:
        verdict = ('the defect occurs in fresh episodes' if t[1] > ORIGINAL_SHARE
                   else 'not shown above the original traces\' share')
        print(f'  N1 verdict (rule: lower bound above {100 * ORIGINAL_SHARE:.1f}%): {verdict}')
    print(f'  mangled reads that returned the file from line 1: {n_line1} of {n_mangled}; episodes with at least one '
          f'mangled read: {episodes_with_mangled} of {len(ok)}')
    print(f'  at the first model call: {pct(boot_ci(first))} | {raw(first)}; at later calls (each follows a tool result): '
          f'{pct(boot_ci(later))} | {raw(later)}')


# ----------------------------------------------------------------------------- part "fix"

def tables(complete, scored, y, cluster, arms=FIX_ARMS, seeds=FIX_SEEDS):
    t = {a: collections.defaultdict(list) for a in arms}
    for k in complete:
        c = k if cluster == 'state' else k[0]
        for a in arms:
            for s in seeds:
                t[a][c].append(scored[(k, (a, s))][y])
    return t


def part_fix(rows, states, pop, label, usable_rule):
    member = {tuple(g['key']): (p, g) for p in ('R', 'U') for g in pop[p]}
    design = [r for r in rows if r.get('population') in ('R', 'U') and skey(r) in member and r['arm'] in FIX_ARMS
              and r['seed'] in POP_SEEDS[member[skey(r)][0]]]
    usable = collections.defaultdict(dict)
    for r in design:
        if usable_rule(r):
            usable[skey(r)][(r['arm'], r['seed'])] = r
    complete = sorted(k for k, (p, _g) in member.items()
                      if {(a, s) for a in FIX_ARMS for s in POP_SEEDS[p]} <= set(usable.get(k, {})))
    scored = {(k, key): score(states[k], member[k][1], r) for k in complete for key, r in usable[k].items()}
    in_r = [k for k in complete if member[k][0] == 'R']
    in_u = [k for k in complete if member[k][0] == 'U']
    print(f'  {label}complete states: {len(complete)} of {len(member)} (R {len(in_r)}, U {len(in_u)}; '
          f'{len({k[0] for k in complete})} tasks)')
    if not complete:
        return design, complete, scored, member
    out = {}
    for y in ('Yline', 'Yfile'):
        t = tables(complete, scored, y, 'state')
        for a in FIX_ARMS:
            print(f'  {label}{y} {a:2s}: {pct(boot_ci(t[a]))} | {raw(t[a])}')
    for tag, a, b in (('G1', 'EF', 'A'), ('G2', 'AF', 'A')):
        for cl in ('state', 'task'):
            t = tables(complete, scored, 'Yline', cl)
            d = diff_ci(t[a], t[b])
            out[(tag, cl)] = d
            print(f'  {label}{tag} {a} - {b} on Yline, clustered by {cl} ({len(t[a])} clusters): {dpt(d)}')
    t = tables(complete, scored, 'Yline', 'state')
    print(f'  {label}descriptive EF - AF on Yline, R and U together, seeds 11 to 13: {dpt(diff_ci(t["EF"], t["AF"]))}')
    for cl in ('state', 'task'):
        t = tables(in_r, scored, 'Yline', cl, seeds=POP_SEEDS['R'])
        d = diff_ci(t['EF'], t['AF']) if in_r else (None, None, None)
        out[('G3', cl)] = d
        print(f'  {label}G3 EF - AF on Yline in R, seeds 11 to 15, clustered by {cl} ({len(t["EF"])} clusters): {dpt(d)}')
    return design, complete, scored, member, out, in_r, in_u


def part_fix_all(rows, states, pop):
    print('\nPART "fix": states of R (seeds 11 to 15) and U (seeds 11 to 13), five model calls; A stock, AF bounds '
          'honored, EF bounds honored plus the legible note. G1 and G2 use seeds 11 to 13 of every state.')
    res = part_fix(rows, states, pop, '', lambda r: not first_call_failure(r))
    design = res[0]
    member = res[3]
    expected = sum(len(FIX_ARMS) * len(POP_SEEDS[p]) for p, _g in member.values())
    keys = collections.Counter((skey(r), r['arm'], r['seed']) for r in design)
    print(f'  rows of the design: {len(design)} of {expected} expected; repeated keys: {sum(1 for v in keys.values() if v > 1)}')
    fail = collections.Counter()
    n = collections.Counter()
    for r in design:
        n[r['arm']] += 1
        kind = first_call_failure(r)
        if kind == 'error':
            kind = error_kind(r)
        if kind:
            fail[(r['arm'], kind)] += 1
    for a in FIX_ARMS:
        kinds = {k: v for (arm, k), v in sorted(fail.items()) if arm == a}
        print(f'  interface failures, arm {a}: {sum(kinds.values())} of {n[a]} {kinds} (excluded from every estimate)')
    if len(res) < 7:
        return
    _design, complete, scored, member, out, in_r, in_u = res
    g1s, g1t, g2s = out[('G1', 'state')], out[('G1', 'task')], out[('G2', 'state')]
    if g1s[0] is not None:
        if g1s[1] > 0 and g1t[1] > 0:
            word = "the two changes together bring the agent to the fix's lines within five calls; ROBUST (both lower bounds above 0)"
        elif g1s[1] > 0:
            word = "the two changes together bring the agent to the fix's lines within five calls (state clustering); NOT robust to task clustering"
        else:
            word = 'no detectable gain from the two changes together'
        print(f'  G1 verdict: {word}')
    if g2s[0] is not None:
        print('  G2 verdict: ' + ('honoring the bound alone raises reach within five calls' if g2s[1] > 0
                                  else 'no detectable gain from the argument fix alone'))
    g3s = out[('G3', 'state')]
    if g3s[0] is not None:
        print('  G3 verdict: ' + ('the legible list adds reach beyond the argument fix' if g3s[1] > 0
                                  else 'no detectable gain from the list once the bound is honored'))
    print('  descriptive, by population, every seed that ran (points [95% interval], clustered by state):')
    for name, ks, ys in (('R', in_r, ('Yline',)), ('U', in_u, ('Yline', 'Yfile'))):
        if not ks:
            continue
        for y in ys:
            t = tables(ks, scored, y, 'state', seeds=POP_SEEDS[name])
            rates = ', '.join(f'{a} {pct(boot_ci(t[a]))}' for a in FIX_ARMS)
            print(f'    {name} {y}: {rates}')
            print(f'    {name} {y}: EF - A {dpt(diff_ci(t["EF"], t["A"]))}; AF - A {dpt(diff_ci(t["AF"], t["A"]))}; '
                  f'EF - AF {dpt(diff_ci(t["EF"], t["AF"]))}')
    print('  descriptive, shown a changed line by the end of each model call (all complete states, percent of replays):')
    for a in FIX_ARMS:
        firsts = [scored[(k, (a, s))]['first_Yline'] for k in complete for s in FIX_SEEDS]
        cum = [100 * sum(1 for f in firsts if f is not None and f <= c) / len(firsts) for c in range(1, K_FIX + 1)]
        mean_calls = st.mean(f if f is not None else K_FIX + 1 for f in firsts)
        print(f'    {a:2s}: ' + ', '.join(f'call {c}: {v:.1f}' for c, v in enumerate(cum, 1))
              + f'; mean calls to the first changed line, never counted as {K_FIX + 1}: {mean_calls:.2f}')
    for c in range(1, K_FIX + 1):
        t = {a: collections.defaultdict(list) for a in FIX_ARMS}
        for k in complete:
            for a in FIX_ARMS:
                for s in FIX_SEEDS:
                    f = scored[(k, (a, s))]['first_Yline']
                    t[a][k].append(int(f is not None and f <= c))
        print(f'    by call {c}: EF - A {dpt(diff_ci(t["EF"], t["A"]))}; AF - A {dpt(diff_ci(t["AF"], t["A"]))}')
    print('  descriptive, executed read_file calls with a line bound, by arm:')
    usable = collections.defaultdict(dict)
    for r in design:
        if not first_call_failure(r):
            usable[skey(r)][(r['arm'], r['seed'])] = r
    for a in FIX_ARMS:
        n_r = n_m = n_l1 = n_first = n_first_m = 0
        for k in complete:
            for s in POP_SEEDS[member[k][0]]:
                for i, m, start in ranged_reads(usable[k][(a, s)]):
                    n_r += 1
                    n_m += m
                    n_l1 += int(bool(m) and start == 1)
                    n_first += int(i == 1)
                    n_first_m += int(i == 1 and bool(m))
        share = f'{100 * n_m / n_r:.1f}%' if n_r else 'n/a'
        first = f'{100 * n_first_m / n_first:.1f}%' if n_first else 'n/a'
        later = f'{100 * (n_m - n_first_m) / (n_r - n_first):.1f}%' if n_r - n_first else 'n/a'
        print(f'    {a:2s}: {n_r} reads, mangled {n_m} ({share}); first call {first}, later calls {later}; mangled reads '
              f'that returned the file from line 1: {n_l1}')
    print('  descriptive, stop reasons and executed calls:')
    for a in FIX_ARMS:
        ss = [scored[(k, (a, s))] for k in complete for s in POP_SEEDS[member[k][0]]]
        c = collections.Counter(stop_group(x['stop']) for x in ss)
        shares = ', '.join(f'{g} {100 * v / len(ss):.1f}%' for g, v in sorted(c.items(), key=lambda x: (-x[1], x[0])))
        print(f'    {a:2s}: n {len(ss)}; {shares}; mean executed calls {st.mean(x["executed_calls"] for x in ss):.2f}')
    print('  sensitivity (as in the five-call experiment): replays that ended in an error after a usable first response '
          'are kept and scored on the calls that executed')

    def first_response_usable(r):
        steps = r.get('steps') or []
        first = steps[0]['calls'][0] if steps and steps[0]['calls'] else None
        call = {'function_name': first['function_name'], 'arguments': first['arguments']} if first else None
        return failure({'error': None, 'next_call': call}) is None

    part_fix(rows, states, pop, 'sensitivity: ', first_response_usable)


# ----------------------------------------------------------------------------- part "one step"

def part_onestep(run_dir, states):
    print('\nPART "one step": arms H (bare names) and E (legible) on the 407 states, seeds 1 to 3')
    rows = [r for r in load_rows(Path(run_dir) / 'results.jsonl') if r['arm'] in ONE_ARMS and r['seed'] in ONE_SEEDS]
    fail = collections.Counter()
    usable = collections.defaultdict(dict)
    for r in rows:
        kind = failure(r)
        if kind:
            fail[(r['arm'], kind)] += 1
        else:
            usable[skey(r)][(r['arm'], r['seed'])] = r
    n_arm = collections.Counter(r['arm'] for r in rows)
    for a in ONE_ARMS:
        kinds = {k: v for (arm, k), v in sorted(fail.items()) if arm == a}
        print(f'  arm {a}: {n_arm[a]} rows; interface failures {sum(kinds.values())} {kinds} (excluded)')
    need = {(a, s) for a in ONE_ARMS for s in ONE_SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    print(f'  complete states: {len(complete)} of {len(states)}')
    tab = {a: {k: [any_true(states[k], usable[k][(a, s)]['next_call']) for s in ONE_SEEDS] for k in complete}
           for a in ONE_ARMS}
    for a in ONE_ARMS:
        print(f'  any unopened true neighbor touched, arm {a}: {pct(boot_ci(tab[a]))} | {raw(tab[a])}')
    d = diff_ci(tab['E'], tab['H'])
    print(f'  S1 E - H: {dpt(d)}')
    if d[0] is not None:
        if len(complete) < MIN_COMPLETE_ONE:
            print(f'  S1 verdict: fewer than {MIN_COMPLETE_ONE} complete states: EXPLORATORY')
        else:
            print('  S1 verdict: ' + ('the encoding effect holds on this harness' if d[1] > 0
                                      else 'not detected on this harness'))
    for name in ('fidelity.jsonl', 'fidelity_w.jsonl'):
        p = Path(run_dir) / name
        if not p.exists():
            continue
        fr = [r for r in load_rows(p) if not r.get('error') and r.get('replayed_prompt_tokens') and r.get('logged_prompt_tokens')]
        if fr:
            rel = [(r['replayed_prompt_tokens'] - r['logged_prompt_tokens']) / r['logged_prompt_tokens'] for r in fr]
            diffs = sorted(r['replayed_prompt_tokens'] - r['logged_prompt_tokens'] for r in fr)
            print(f'  {name} (descriptive): {len(fr)} states, replayed minus logged prompt size: median '
                  f'{100 * st.median(rel):+.2f}%, median absolute {100 * st.median(abs(x) for x in rel):.2f}%; tokens '
                  f'min {diffs[0]}, median {st.median(diffs)}, max {diffs[-1]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--onestep', default=None)
    ap.add_argument('--population', default=str(HERE / 'fork_states_k' / 'population.json'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    ap.add_argument('--fresh', default=str(HERE / 'fork_states_g' / 'fresh_states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(args.states)
    pop = json.load(open(args.population, encoding='utf-8'))
    fresh = {s['task']: s for s in (json.loads(l) for l in open(args.fresh, encoding='utf-8'))}
    res = Path(args.run_dir) / 'results_g.jsonl'
    rows = [json.loads(l) for l in open(res, encoding='utf-8') if l.strip()] if res.exists() else []
    for name in ('versions_g.json',):
        p = Path(args.run_dir) / name
        if p.exists():
            v = json.load(open(p, encoding='utf-8'))
            print(f'run: harness variant {v.get("harness_variant")}; packages {v.get("packages")}; parts {v.get("parts")}')
    if rows:
        part_fresh(rows, fresh)
        part_fix_all(rows, states, pop)
    else:
        print(f'no results_g.jsonl under {args.run_dir}')
    if args.onestep:
        part_onestep(args.onestep, states)


if __name__ == '__main__':
    main()
