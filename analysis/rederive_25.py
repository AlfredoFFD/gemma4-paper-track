"""Independent re-derivation of pre-registration 25 (the place of the list).

Written blind: from the frozen text of prereg/25-the-place-of-the-list.md alone (with the definitions it takes over
from earlier registrations), without sight of the registered analysis of this experiment, of its launcher, of its
state builder or of any output of theirs. It reads only the replay rows (analysis/results/25/forks/results.jsonl, or
the file given with --rows), the manifest analysis/fork_states_p/manifest.json (the 322 steps, their order and the
flag "the queried node overlaps the lines the last read showed") and the 407 paused steps of 03
(analysis/fork_states_d/states.jsonl, whose spans every arm is scored on).

It imports, unchanged, the frozen pieces the registration names: the scorer gates_c.any_true ("reads a neighbor's
code"), the interface-failure rule gates_c.failure, the looser outcome mangled_sensitivity.opens_listed_file ("opens
the neighbor's file") and the bootstrap analyze_forks.boot_ci / diff_ci (2,000 resamples, seed 0).

Usage: py -I -X utf8 analysis/rederive_25.py [--rows <path>] [--no-write]
Without options it prints the report and writes the same text to analysis/results/rederive_25.txt (LF).
--rows reads another results file and never writes the stored file; --no-write prints only.
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import any_true, failure  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

ROWS_DEFAULT = HERE / 'results' / '25' / 'forks' / 'results.jsonl'
MANIFEST = HERE / 'fork_states_p' / 'manifest.json'
STATES = HERE / 'fork_states_d' / 'states.jsonl'
OUT = HERE / 'results' / 'rederive_25.txt'
STATES_MD5 = 'd3105df0dc4aa43d7bb0afbdd6123b44'
ARMS = ('KH', 'KE', 'EL')
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL'}
SEEDS = (1, 2)
GATE_USABLE = 0.80
BAND = (3.81, 9.19)          # percent, inclusive
FLOOR = 200
READ_KEYS = ['status', 'filepath', 'content', 'start_line', 'end_line', 'total_lines', 'is_truncated']
OUTCOMES = (('reads', 'reads a neighbor\'s code (registered)'), ('opens', 'opens the neighbor\'s file (no rule)'))

L = []


def p(s=''):
    L.append(s)


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def sid_of(task, run, fork):
    return f'{task}|r{run}|f{fork}'


def npath(x):
    x = str(x or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while x.startswith(pre):
            x = x[len(pre):]
    return x


# ---------------------------------------------------------------- formatting

def frate(t):
    pt, lo, hi = t
    return 'n/a' if pt is None else f'{100 * pt:.2f}% [{100 * lo:.2f}, {100 * hi:.2f}]'


def fdiff(t):
    pt, lo, hi = t
    return 'n/a' if pt is None else f'{100 * pt:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]'


# ---------------------------------------------------------------- steps

def load_steps():
    man = json.loads(MANIFEST.read_text(encoding='utf-8'))
    states = {}
    for line in STATES.read_text(encoding='utf-8').splitlines():
        if line.strip():
            s = json.loads(line)
            states[sid_of(s['task'], s['run'], s['fork'])] = s
    # independent derivation of the 322 steps: the paused history ends with a read_file result of status ok
    mine, keys_ok, overlap, in_file = set(), 0, {}, {}
    last_tool = Counter()
    for sid, s in states.items():
        last = s['steps'][-1]
        tc = (last.get('tool_calls') or [{}])[0]
        last_tool[tc.get('function_name')] += 1
        if tc.get('function_name') != 'read_file':
            continue
        c = (last.get('observation') or {}).get('content')
        try:
            obs = json.loads(c) if isinstance(c, str) else (c or {})
        except ValueError:
            obs = {}
        if not isinstance(obs, dict) or obs.get('status') != 'ok':
            continue
        mine.add(sid)
        keys_ok += list(obs.keys()) == READ_KEYS
        ns = s.get('node_span') or {}
        same = bool(ns) and npath(ns.get('path')) == npath(obs.get('filepath'))
        in_file[sid] = same
        a, b = obs.get('start_line'), obs.get('end_line')
        overlap[sid] = bool(same and isinstance(a, int) and isinstance(b, int)
                            and ns.get('start') is not None and ns['start'] <= b and (ns.get('end') or ns['start']) >= a)
    return man, states, mine, keys_ok, overlap, in_file, last_tool


# ---------------------------------------------------------------- one set of estimates

def cell_values(U, steps, seeds_of, key):
    """{step: {arm: mean of the outcome over the step's complete cells}} for steps with at least one."""
    out = {}
    for s in steps:
        cs = seeds_of(s)
        if cs:
            out[s] = {a: sum(U[(s, a, sd)][key] for sd in cs) / len(cs) for a in ARMS}
    return out


def by_step(vals, arm):
    return {s: [vals[s][arm]] for s in sorted(vals)}


def by_task(vals, arm, task_of):
    d = defaultdict(list)
    for s in sorted(vals):
        d[task_of[s]].append(vals[s][arm])
    return {t: d[t] for t in sorted(d)}


def rate_line(vals, arm, task_of):
    return frate(boot_ci(by_step(vals, arm))), frate(boot_ci(by_task(vals, arm, task_of)))


def contrast(vals, a, b, task_of):
    return diff_ci(by_step(vals, a), by_step(vals, b)), diff_ci(by_task(vals, a, task_of), by_task(vals, b, task_of))


def block(title, U, steps, seeds_of, task_of, indent='  '):
    """Every arm's rate on both outcomes and the three contrasts on both outcomes, with the by-task interval."""
    vals = {k: cell_values(U, steps, seeds_of, k) for k, _ in OUTCOMES}
    n = len(vals['reads'])
    nt = len({task_of[s] for s in vals['reads']})
    p(f'{indent}{title}: {n} steps ({nt} tasks)')
    if not n:
        p(f'{indent}  no step: nothing estimated')
        return vals
    for k, lab in OUTCOMES:
        p(f'{indent}  {lab}')
        for a in ARMS:
            r1, r2 = rate_line(vals[k], a, task_of)
            p(f'{indent}    {a}: {r1}; by task {r2}')
        for name, x, y in (('K1 KE - KH', 'KE', 'KH'), ('K2 EL - KE', 'EL', 'KE'), ('EL - KH', 'EL', 'KH')):
            c1, c2 = contrast(vals[k], x, y, task_of)
            p(f'{indent}    {name}: {fdiff(c1)} points; by task {fdiff(c2)}')
    return vals


# ---------------------------------------------------------------- main

def main(argv):
    rows_path = ROWS_DEFAULT
    write = True
    if '--rows' in argv:
        i = argv.index('--rows')
        if i + 1 >= len(argv):
            print('--rows needs a path')
            return 2
        rows_path = Path(argv[i + 1])
        write = False
    if '--no-write' in argv:
        write = False
    if not rows_path.exists():
        print(f'results file not found: {rows_path.as_posix() if rows_path != ROWS_DEFAULT else "analysis/results/25/forks/results.jsonl"}')
        return 1

    p('Re-derivation of pre-registration 25, the place of the list (independent script, written blind from the frozen')
    p('registration text; imports gates_c.any_true / failure, mangled_sensitivity.opens_listed_file and')
    p('analyze_forks.boot_ci / diff_ci unchanged)')
    p('')

    # ---- steps
    man, states, mine, keys_ok, overlap, in_file, last_tool = load_steps()
    h = md5(STATES)
    p('0. STEPS')
    p(f'  states file analysis/fork_states_d/states.jsonl md5 {h} ({"as registered" if h == STATES_MD5 else "DIFFERS"});'
      f' {len(states)} paused steps; last tool: ' + ', '.join(f'{k} {v}' for k, v in sorted(last_tool.items(), key=str)))
    p(f'  manifest analysis/fork_states_p/manifest.json md5 {md5(MANIFEST)}; records md5 named there {man.get("md5")}')
    steps = sorted(man['steps'])
    task_of = {s: man['steps'][s]['task'] for s in steps}
    p(f'  manifest: {len(steps)} steps in {len(set(task_of.values()))} tasks; order of {len(man["order"])} '
      f'(a permutation of the steps: {sorted(man["order"]) == steps})')
    p(f'  re-derived here (history ends with read_file, status ok): {len(mine)} steps; equal to the manifest\'s set:'
      f' {mine == set(steps)}; read results with the seven keys in the registered order: {keys_ok} of {len(mine)}')
    missing_state = [s for s in steps if s not in states]
    if missing_state:
        p(f'  manifest steps without a paused step in the states file: {len(missing_state)}')
    flag = {s: bool(man['steps'][s]['node_overlaps_shown_lines']) for s in steps}
    sub = [s for s in steps if flag[s]]
    agree = sum(1 for s in steps if overlap.get(s) == flag[s])
    nf = sum(1 for s in steps if in_file.get(s) and not overlap.get(s))
    p(f'  node overlaps the lines shown (manifest flag): {len(sub)} steps ({len({task_of[s] for s in sub})} tasks);'
      f' re-derived here by path and line overlap: {sum(1 for s in steps if overlap.get(s))}, agreeing with the flag'
      f' on {agree} of {len(steps)}; in the file read but outside the lines {nf}; not in that file '
      f'{sum(1 for s in steps if not in_file.get(s))}')
    p('')

    # ---- rows
    raw = [json.loads(x) for x in rows_path.read_text(encoding='utf-8').splitlines() if x.strip()]
    cell, unmatched, bad_seed, dup, bad_fork = {}, 0, 0, 0, 0
    runner = Counter()
    for r in raw:
        parts = str(r.get('fork')).split(':')
        if len(parts) != 3:
            bad_fork += 1
            continue
        f0, arm, sd = parts
        try:
            sid = sid_of(r['task'], r['run'], int(f0))
            sd = int(sd)
        except (ValueError, KeyError):
            bad_fork += 1
            continue
        if sid not in man['steps'] or arm not in ARMS:
            unmatched += 1
            continue
        if sd not in SEEDS or r.get('seed') != sd:
            bad_seed += 1
            continue
        runner[(arm, r.get('arm'))] += 1
        k = (sid, arm, sd)
        if k in cell:
            dup += 1
            continue
        cell[k] = r
    p('1. ROWS')
    p(f'  results file md5 {md5(rows_path)}; rows {len(raw)}; kept {len(cell)}; fork id not of the form'
      f' <fork>:<arm>:<seed> {bad_fork}; not a step or arm of 25 {unmatched}; seed outside 1-2 or differing from the fork'
      f' id {bad_seed}; repeated (step, arm, seed) {dup} (first kept)')
    p('  runner arm by design arm: ' + ', '.join(f'{a} under {ra}: {n} ({"as registered" if ra == RUNNER_ARM[a] else "NOT as registered"})'
                                                for (a, ra), n in sorted(runner.items(), key=str)))
    for sd in SEEDS:
        p(f'  seed {sd}: rows ' + ', '.join(f'{a} {sum(1 for k in cell if k[1] == a and k[2] == sd)}' for a in ARMS)
          + f'; steps with any row {len({k[0] for k in cell if k[2] == sd})}')
    order = man['order']
    for sd in SEEDS:
        have = {k[0] for k in cell if k[2] == sd}
        if have:
            last = max(order.index(s) for s in have)
            gaps = sum(1 for s in order[:last + 1] if s not in have)
            p(f'  seed {sd}: last step reached is position {last + 1} of the fixed order; steps before it without a row {gaps}')
    for vf in ('versions.json', 'versions_25.json'):
        f = rows_path.parent / vf
        if f.exists():
            try:
                v = json.loads(f.read_text(encoding='utf-8'))
            except ValueError:
                p(f'  {vf}: not readable as JSON')
                continue
            items = [(k, x) for k, x in v.items() if not isinstance(x, (dict, list))] if isinstance(v, dict) else []
            p(f'  {vf}: ' + '; '.join(f'{k}={str(x)[:60]}' for k, x in items[:12]))
            if isinstance(v, dict):
                for k, x in v.items():
                    if isinstance(x, (dict, list)) and any(w in k.lower() for w in ('harness', 'wheel', 'version', 'package')):
                        p(f'    {k}: {json.dumps(x, sort_keys=True)[:300]}')
        else:
            p(f'  {vf}: not next to the results file')
    p('')

    # ---- interface failures, usable replays
    U, fails = {}, defaultdict(Counter)
    for k, r in cell.items():
        f = failure(r)
        if f:
            fails[k[1]][f] += 1
            continue
        st = states[k[0]]
        call = r['next_call']
        U[k] = {'reads': any_true(st, call), 'opens': int(bool(opens_listed_file(st, call)))}
    p('2. INTERFACE FAILURES BY ARM (gates_c.failure; excluded) AND GATE (a)')
    gate_a = True
    share = {}
    for a in ARMS:
        n = sum(1 for k in cell if k[1] == a)
        u = sum(1 for k in U if k[1] == a)
        share[a] = u / n if n else 0.0
        gate_a = gate_a and n > 0 and share[a] >= GATE_USABLE
        fl = ', '.join(f'{x} {fails[a][x]}' for x in ('error', 'no_call', 'unknown_tool', 'malformed_args'))
        p(f'  {a}: attempted {n}; {fl}; usable {u} ({100 * share[a]:.2f}%)')
    p(f'  GATE (a), at least 80% of the replays attempted in each arm usable: {"PASSED" if gate_a else "FAILED"}')
    p('')

    # ---- cells
    def complete_seeds(s):
        return [sd for sd in SEEDS if all((s, a, sd) in U for a in ARMS)]

    def seed1(s):
        return [1] if all((s, a, 1) in U for a in ARMS) else []

    ncs = Counter(len(complete_seeds(s)) for s in steps)
    entering = [s for s in steps if complete_seeds(s)]
    floor_ok = len(entering) >= FLOOR
    p('3. COMPLETE CELLS (a (step, seed) cell is complete if all three arms are usable at that seed)')
    p(f'  complete cells: seed 1 {sum(1 for s in steps if 1 in complete_seeds(s))}, seed 2 '
      f'{sum(1 for s in steps if 2 in complete_seeds(s))}')
    p(f'  steps with two complete cells {ncs[2]}; with one {ncs[1]}; with none {ncs[0]}')
    p(f'  steps entering (at least one complete cell): {len(entering)} in {len({task_of[s] for s in entering})} tasks;'
      f' floor of 200: {"met" if floor_ok else "NOT met"}')
    p('')

    # ---- gate (b)
    vals = {k: cell_values(U, steps, complete_seeds, k) for k, _ in OUTCOMES}
    el = boot_ci(by_step(vals['reads'], 'EL'))
    el_t = boot_ci(by_task(vals['reads'], 'EL', task_of))
    gate_b = el[0] is not None and BAND[0] <= 100 * el[0] <= BAND[1]
    p('4. GATE (b): EL\'s rate (reads a neighbor\'s code) on the steps with a complete cell within [3.81, 9.19] percent')
    p(f'  EL {frate(el)} by step; by task {frate(el_t)}; point {"inside" if gate_b else "OUTSIDE"} the band')
    p(f'  GATE (b): {"PASSED" if gate_b else "FAILED"}')
    gate = gate_a and gate_b
    p(f'  GATE: {"PASSED" if gate else "FAILED"}')
    p('')

    # ---- rules
    p('5. RULES (95% bootstrap clustered by step, 2,000 resamples, seed 0, each step its mean over its complete cells;'
      ' interval clustered by task beside)')
    k1, k1t = contrast(vals['reads'], 'KE', 'KH', task_of)
    k2, k2t = contrast(vals['reads'], 'EL', 'KE', task_of)
    allowed = gate and floor_ok
    p(f'  K1 KE - KH: {fdiff(k1)} points; by task {fdiff(k1t)}')
    p(f'  K2 EL - KE: {fdiff(k2)} points; by task {fdiff(k2t)}')
    if not gate:
        p('  No rule is read: the gate failed. The result is reported as a failed replication.')
    elif not floor_ok:
        p(f'  No verdict: fewer than 200 steps have a complete cell ({len(entering)}).')
    else:
        m1 = k1[1] is not None and k1[1] > 0
        m2 = k2[1] is not None and k2[1] > 0
        v1 = 'The effect holds in the push\'s place' if m1 else 'not detected'
        v2 = 'The place matters' if m2 else 'not detected'
        p(f'  K1 verdict: {v1}')
        p(f'  K2 verdict: {v2}')
        p('  Reading fixed in the registration:')
        if m1:
            p('    K1 met: the address effect is there in the push\'s place, so the place of the list does not explain the'
              ' null of 23' + (' (K2 also met: the place lowers the effect without removing it).' if m2 else '.'))
        elif m2:
            p('    K1 not detected and K2 met: an address placed after a file\'s content is not acted on as it is in a'
              ' note; the place of the list can explain why the whole runs of 23 showed no effect.')
        else:
            p('    K1 not detected and K2 not detected: undecided.')
    p('')

    # ---- no rule
    p('6. REPORTED WITHOUT A RULE')
    block('a. All steps with a complete cell (seeds 1 and 2, each step its mean over its complete cells)',
          U, steps, complete_seeds, task_of)
    block('b. Seed 1 alone (steps with a complete seed-1 cell)', U, steps, seed1, task_of)
    block(f'c. The {len(sub)} steps whose queried node overlaps the lines the last read showed, seeds 1 and 2',
          U, sub, complete_seeds, task_of)
    block(f'd. The same {len(sub)} steps, seed 1 alone', U, sub, seed1, task_of)
    p(f'  e. Interface failures by arm: in section 2. Steps of subset c with a complete cell: '
      f'{sum(1 for s in sub if complete_seeds(s))}; with two {sum(1 for s in sub if len(complete_seeds(s)) == 2)}')
    p('  f. Descriptive, every usable replay (complete cell or not), pooled shares:')
    for a in ARMS:
        us = [U[k] for k in U if k[1] == a]
        p(f'    {a}: usable {len(us)}; reads {sum(o["reads"] for o in us)} '
          f'({100 * sum(o["reads"] for o in us) / len(us) if us else 0:.2f}%); opens {sum(o["opens"] for o in us)} '
          f'({100 * sum(o["opens"] for o in us) / len(us) if us else 0:.2f}%)')
    p('')

    # ---- judgment calls, with the other reading where it can be computed
    p('7. JUDGMENT CALLS')
    planned = len(steps) * len(SEEDS)
    alt_a = all(sum(1 for k in U if k[1] == a) / planned >= GATE_USABLE for a in ARMS)
    p('  - Gate (a) denominator: the replays attempted in an arm = its kept rows (a row exists, so the replay started);'
      ' replays the cap never started are not attempted. Other reading, the 644 planned per arm: '
      + ', '.join(f'{a} {100 * sum(1 for k in U if k[1] == a) / planned:.2f}%' for a in ARMS)
      + f' -> {"passed" if alt_a else "failed"}.')
    p('  - Gate (b) is read on EL\'s point estimate (mean over entering steps of the step means), bounds inclusive,'
      ' unrounded. Other reading, the whole by-step interval inside the band: '
      + ('n/a' if el[0] is None else ('yes' if BAND[0] <= 100 * el[1] and 100 * el[2] <= BAND[1] else 'no')) + '.')
    pooled = {}
    for a in ARMS:
        pooled[a] = {s: [U[(s, a, sd)]['reads'] for sd in complete_seeds(s)] for s in entering}
    pk1 = diff_ci(pooled['KE'], pooled['KH'])
    pk2 = diff_ci(pooled['EL'], pooled['KE'])
    pel = boot_ci({s: pooled['EL'][s] for s in sorted(pooled['EL'])})
    p('  - A step enters with one value per arm, the mean over its complete cells (1 or 2), so every step weighs the'
      ' same; rates are means of step means. Other reading, every complete cell a replay of its own (steps with two'
      f' cells weigh double): EL {frate(pel)}; K1 {fdiff(pk1)}; K2 {fdiff(pk2)}.')
    tup = sorted(steps, key=lambda s: (task_of[s], int(s.split('|r')[1].split('|')[0]), int(s.rsplit('|f', 1)[1])))
    p('  - "The steps in sorted order": sorted by the manifest id <task>|r<run>|f<fork> as strings (boot_ci resamples'
      ' in the order of its dict; diff_ci sorts its own keys). Sorting by (task, run, fork) as numbers gives '
      + ('the same order here.' if tup == steps else 'a DIFFERENT order here.'))
    p('  - Clustered by task: each task is one cluster holding the means of its entering steps; tasks in sorted order.')
    p('  - Rows: a row belongs to the step (task, run, 03\'s fork) and arm named by its fork id <fork>:<arm>:<seed>;'
      ' its seed field must equal the id\'s seed; seeds other than 1 and 2 are ignored; a repeated (step, arm, seed)'
      ' keeps the first row. The runner arm field (A for KH and KE, EL for EL) is only checked.')
    p('  - Usable: gates_c.failure (runner error, no call, unknown tool, malformed arguments), applied to every arm alike;'
      ' both outcomes are scored on usable replays of complete cells only.')
    p('  - "Interval above zero": its lower bound strictly above 0. Verdicts are printed only when both parts of the gate'
      ' pass and at least 200 steps have a complete cell; the reading fixed in the registration is printed with them.')
    p('  - The 276-step subset uses the manifest flag (push_23.shown_range was not opened); a check by path and line'
      f' overlap of the node span and the read result agrees on {agree} of {len(steps)} steps.')
    p('  - Seed 1 alone: a step enters if all three arms are usable at seed 1, whatever seed 2 gave.')
    p('  - "All estimates on the 276 steps": every arm\'s rates and the three contrasts, on both outcomes, at seeds 1'
      ' and 2 and at seed 1 alone, with no rule, no gate and no floor.')
    p('  - The registered outcome counts every true neighbor of the states file in an unopened file (any_true); 03\'s'
      ' lists hold at most 50, and no step of the states file has more than 50 true neighbors, so every scored'
      f' neighbor is listed: {all(len(states[s]["true_neighbors"]) <= 50 for s in steps)}.')

    text = '\n'.join(L) + '\n'
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stdout.buffer.flush()
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
