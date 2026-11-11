"""Independent re-derivation of pre-registration 19 (the two one-call contrasts on models of other publishers).

Written blind: from the text of prereg/19-one-call-contrasts-on-hosted-models.md (and 10, 15, 17 for the outcomes)
and the raw rows only. It does not import or read analyze_19.py, analyze_15.py, analyze_d.py or
explore_first_reads.py, nor any output of theirs. It reuses, by import, the two blind second scripts of the earlier
designs: rederive_cd.py (the design-10 scorer: fork_states.touches / valid_call, the interface-failure classes) and
rederive_15.py (the design-17 scorer: hit files, reads of a hit file, past line 1, mangled start_line).

Usage: py -I -X utf8 analysis/rederive_19.py [--root analysis/results/19] [--no-write]
Writes analysis/results/rederive_19.txt (LF) unless --no-write is given.
"""
import argparse
import collections
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_cd as RC  # noqa: E402  design 10: states, interface failures, touches
import rederive_15 as R15  # noqa: E402  design 17: hit files, outcome of a replay

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

NB = 2000
BOOT_SEED = 0
GATE = 0.80
FLOOR = {'10': 200, '17': 25}
ARMS = {'10': ('H', 'E'), '17': ('S', 'S0', 'S0N')}
SEEDS = {'10': (1, 2), '17': (1, 2, 3)}
PLANNED = {'10': 407 * 2 * 2, '17': 61 * 3 * 3}
STATES_10 = HERE / 'fork_states_d' / 'states.jsonl'
STATES_17 = HERE / 'fork_states_s' / 'states.jsonl'
MD5 = {STATES_10: 'd3105df0dc4aa43d7bb0afbdd6123b44', STATES_17: 'a90d2df2d7b6fc12591fffe2f1622a2b'}
OUT = HERE / 'results' / 'rederive_19.txt'

JUDGMENT = [
    'API failure: a row whose api.error_kind is "api" (the runner sets it when the call got no reply after its '
    'retries). Every other row is a model reply. A row with a non-empty error and api.error_kind "adapter" got a '
    'reply whose tool call the harness could not parse: it is a reply without a valid tool call.',
    'Valid tool call: design 10 by the classes of rederive_cd.py (error, no call, unknown tool among the nine '
    'declared tools, fork_states.valid_call false); design 17 by the classes of rederive_15.py (error, no call, '
    'unknown tool, arguments not an object or a required argument missing after cleaning the names; a mangled '
    'start_line is usable). The error class here holds only adapter errors, since API failures are taken out first. '
    'rederive_15.py lists six tools; the agent of 19 declares nine in both designs (its runner.log), so in design 17 '
    'a call to get_status, get_code_neighbors or get_code_subgraph is known and judged by fork_states.valid_call.',
    'Gate: valid tool calls divided by replays that got a reply (API failures left out of the denominator); the share '
    'over all replays is printed beside it. Passed if at least 80% (inclusive). One gate per model and design.',
    'Complete step: every arm and seed that was run has a usable replay: design 10 H and E, seeds 1 and 2 (4 '
    'replays); design 17 S, S0 and S0N, seeds 1 to 3 (9 replays). V2 is computed on these steps. Steps complete in '
    'S and S0 alone (the completeness of Q1 in pre-registration 15) are printed beside it as a variant, without a '
    'verdict.',
    'Design 10 outcome "the next call reads a neighbor\'s code": the outcome of pre-registration 10 (M2), any '
    'unopened true neighbor touched, fork_states.touches returning read or edit for a name in '
    'unshown_true_neighbors, as rederive_cd.score_row computes it. The variant counting only "read" is printed beside.',
    'Design 17 outcome Y1: a read of a hit file (read_file on it, or a shell view starting from cat/head/tail/sed -n '
    'with a known range) that starts past line 1, as rederive_15.score computes it; a start_line under a mangled '
    'argument name counts as asking.',
    'Rates pool the replays of the steps (each replay weight 1). Bootstrap: numpy default_rng(0), 2,000 resamples of '
    'complete steps with replacement; per resample the difference of pooled rates on the same resampled steps; '
    'percentile bounds are the order statistics b[int(0.025 n)] and b[int(0.975 n) - 1] of the sorted values. Each '
    'contrast draws its own resamples from a fresh default_rng(0).',
    '"Interval lies above zero": the lower 95% bound strictly above 0.',
    'Verdicts in this order: "no verdict: gate" if the gate fails; "no verdict: cut" for design 17 if its run was '
    'stopped by a guard or has fewer rows than planned; "no verdict: floor" if fewer complete steps than the floor '
    '(200, 25); otherwise "met" or "not met".',
    'Rows are mapped to steps by (task, run, fork): design 10 to the states of fork_states_d, design 17 to the state '
    'record whose fork id ends in :S, :S0 or :S0N (the record_arm field is checked against it). A repeated '
    '(step, arm, seed) keeps the first row and is counted.',
    'Past line 1 among reads of a hit file (no rule) is printed per arm on complete steps and on all usable replays.',
]


class Report:
    def __init__(self):
        self.lines = []

    def __call__(self, s=''):
        self.lines.append(s)
        print(s)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def read_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(x) for x in f if x.strip()]


def is_api_failure(r):
    return (r.get('api') or {}).get('error_kind') == 'api'


# ---------------------------------------------------------------- bootstrap

def boot_diff(steps, ka, na, kb, nb):
    """steps: list of keys; ka/na/kb/nb: dicts key -> hits / replays. Returns est, lo, hi (points)."""
    m = len(steps)
    if m == 0:
        return None
    a_k = np.array([ka[s] for s in steps], float)
    a_n = np.array([na[s] for s in steps], float)
    b_k = np.array([kb[s] for s in steps], float)
    b_n = np.array([nb[s] for s in steps], float)
    est = 100 * (a_k.sum() / a_n.sum() - b_k.sum() / b_n.sum())
    idx = np.random.default_rng(BOOT_SEED).integers(0, m, size=(NB, m))
    b = 100 * (a_k[idx].sum(1) / a_n[idx].sum(1) - b_k[idx].sum(1) / b_n[idx].sum(1))
    b = np.sort(b)
    return est, float(b[int(0.025 * NB)]), float(b[int(0.975 * NB) - 1])


def fmt_d(t):
    if t is None:
        return 'n/a'
    return f'{t[0]:+.2f} [{t[1]:+.2f}, {t[2]:+.2f}]'


def pct(k, n):
    return f'{k}/{n} ({100 * k / n:.2f}%)' if n else f'{k}/0 (n/a)'


def verdict(gate_ok, cut, n_complete, floor, t):
    if not gate_ok:
        return 'no verdict: gate'
    if cut:
        return 'no verdict: cut'
    if n_complete < floor:
        return 'no verdict: floor'
    return 'met' if (t is not None and t[1] > 0) else 'not met'


def summary_of(run_dir):
    f = run_dir / 'summary.json'
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding='utf-8'))


def run_facts(out, run_dir, rows):
    v = run_dir / 'versions.json'
    ver = json.loads(v.read_text(encoding='utf-8')) if v.exists() else {}
    wheels = RC.installed_wheels(run_dir, RC.REGISTERED_WHEELS)
    s = summary_of(run_dir)
    st = s.get('stats') or {}
    out(f'    harness {ver.get("harness_variant")}, wheels {wheels}; api model {ver.get("api_model")}; quantization '
        f'{(ver.get("api_listing") or {}).get("quantization")}; runner md5 {(ver.get("md5") or {}).get("runner")}; '
        f'states md5 {(ver.get("md5") or {}).get("states_file")}')
    rep = collections.Counter((r.get('api') or {}).get('model_reported') for r in rows)
    fin = collections.Counter((r.get('api') or {}).get('finish_reason') for r in rows)
    ntc = collections.Counter(min((r.get('api') or {}).get('n_tool_calls') or 0, 2) for r in rows)
    rc = [(r.get('api') or {}).get('reasoning_chars') or 0 for r in rows]
    ct = [(r.get('api') or {}).get('completion_tokens') for r in rows if (r.get('api') or {}).get('completion_tokens') is not None]
    out(f'    reported model {dict(rep)}; finish reasons {dict(fin)}; tool calls per reply (2 = two or more) '
        f'{dict(sorted(ntc.items()))}')
    out(f'    reasoning chars median {statistics.median(rc) if rc else "n/a"}, replies with reasoning '
        f'{sum(1 for x in rc if x)}/{len(rc)}; completion tokens median {statistics.median(ct) if ct else "n/a"}; '
        f'stopped_by {st.get("stopped_by")!r}; dollars {st.get("dollars")}')
    return st.get('stopped_by')


def counts_block(out, design, rows, kinds_by_arm, usable_n, api_by_arm):
    arms = ARMS[design]
    tot_rows = len(rows)
    tot_api = sum(api_by_arm.values())
    tot_valid = sum(usable_n.values())
    tot_noval = tot_rows - tot_api - tot_valid
    for a in arms:
        n = sum(1 for r in rows if r['_arm'] == a)
        k = ', '.join(f'{x} {c}' for x, c in sorted(kinds_by_arm[a].items())) or 'none'
        out(f'    {a:4s} replays {n}; API failures {api_by_arm[a]}; replies without a valid tool call '
            f'{sum(kinds_by_arm[a].values())} ({k}); valid {usable_n[a]}')
    replies = tot_rows - tot_api
    share = tot_valid / replies if replies else 0.0
    gate_ok = replies > 0 and share >= GATE
    out(f'    all arms: replays {tot_rows} (planned {PLANNED[design]}); API failures {tot_api}; replies without a valid '
        f'tool call {tot_noval}; valid {tot_valid}; share valid of replies {100 * share:.2f}% (of all replays '
        f'{100 * tot_valid / tot_rows if tot_rows else 0:.2f}%) -> gate (80%) {"PASSED" if gate_ok else "FAILED"}')
    return gate_ok


# ---------------------------------------------------------------- design 10

def design_10(out, run_dir, states):
    rows = read_jsonl(run_dir / 'results.jsonl')
    arms, seeds = ARMS['10'], SEEDS['10']
    usable = defaultdict(dict)
    kinds = defaultdict(collections.Counter)
    api = collections.Counter()
    usable_n = collections.Counter()
    dups = unknown = other = 0
    for r in rows:
        r['_arm'] = r.get('arm')
        if r['_arm'] not in arms or r.get('seed') not in seeds:
            other += 1
            continue
        k = RC.state_key(r)
        if k not in states:
            unknown += 1
        if is_api_failure(r):
            api[r['_arm']] += 1
            continue
        kind = RC.failure_kind(r)
        if kind:
            kinds[r['_arm']]['adapter error' if kind == 'error' else kind] += 1
            continue
        usable_n[r['_arm']] += 1
        slot = (r['_arm'], r['seed'])
        if slot in usable[k]:
            dups += 1
            continue
        usable[k][slot] = r
    out('  design 10 (name against address; arms H, E; seeds 1, 2)')
    stopped = run_facts(out, run_dir, rows)
    out(f'    rows outside the arms/seeds {other}; rows of unknown steps {unknown}; repeated usable cells {dups}; '
        f'node differs from the state {sum(1 for r in rows if RC.state_key(r) in states and r.get("node") != states[RC.state_key(r)]["node"])}')
    gate_ok = counts_block(out, '10', rows, kinds, usable_n, api)
    need = {(a, s) for a in arms for s in seeds}
    complete = sorted(k for k, v in usable.items() if k in states and need <= set(v))
    floor_ok = len(complete) >= FLOOR['10']
    out(f'    complete steps {len(complete)} of {len(states)} (floor {FLOOR["10"]}: {"met" if floor_ok else "NOT met"})')
    hit = {a: {} for a in arms}
    hit_read = {a: {} for a in arms}
    n = {a: {} for a in arms}
    for k in complete:
        s = states[k]
        sp = s['neighbor_spans']
        unshown = [x for x in s['unshown_true_neighbors'] if sp.get(x)]
        for a in arms:
            h = hr = 0
            for sd in seeds:
                row = usable[k][(a, sd)]
                h += RC.score_row(row, s)['true_any']
                c = row['next_call']
                hr += any(RC.touches(c, sp[x], x, line_lengths=RC.line_lengths(s['task'], sp[x]['path'])) == 'read'
                          for x in unshown)
            hit[a][k], hit_read[a][k], n[a][k] = h, hr, len(seeds)
    for a in arms:
        out(f'    {a}: next call reads a neighbor\'s code (touch, read or edit) '
            f'{pct(sum(hit[a].values()), sum(n[a].values()))}; read only {pct(sum(hit_read[a].values()), sum(n[a].values()))}')
    t = boot_diff(complete, hit['E'], n['E'], hit['H'], n['H'])
    tr = boot_diff(complete, hit_read['E'], n['E'], hit_read['H'], n['H'])
    v = verdict(gate_ok, False, len(complete), FLOOR['10'], t)
    out(f'    V1  E minus H: {fmt_d(t)} points -> {v}')
    out(f'        (read-only variant, no rule: {fmt_d(tr)})')
    if stopped:
        out(f'    note: the run was stopped by {stopped!r}; design 10 keeps its verdict if the floor is met')
    out('')
    return t, v, len(complete)


# ---------------------------------------------------------------- design 17

_info17 = None


def info_17():
    global _info17
    if _info17 is not None:
        return _info17
    recs = read_jsonl(STATES_17)
    by_state = defaultdict(dict)
    for r in recs:
        by_state[r['state_id']][r['arm']] = r
    info, fork_to = {}, {}
    for sid, rs in by_state.items():
        s = rs['S']
        task = s['task']
        last = s['steps'][-1]
        cmd = last['tool_calls'][0]['arguments']['command']
        hits, *_ = R15.parse_result(task, cmd, R15.stdout_of(R15.obs_of(last)))
        opened = R15.opened_before(task, s['steps'])
        hf = defaultdict(list)
        for h in hits:
            if h['file'] in R15.snapshot(task)[0] and h['file'] not in opened:
                hf[h['file']].append(h['line'])
        info[sid] = {'task': task, 'hitfiles': {f: sorted(set(v)) for f, v in hf.items()}}
        for arm, r in rs.items():
            fork_to[(r['task'], r['run'], r['fork'])] = (sid, arm)
    _info17 = (info, fork_to)
    return _info17


def failure_17(r):
    """rederive_15's classes, except that the three tools it does not list (get_status, get_code_neighbors,
    get_code_subgraph) are known: the agent of 19 declares all nine in both designs (runner.log, one agent.yaml)."""
    f = R15.interface_failure(r)
    if f == 'unknown tool' and r['next_call']['function_name'] in RC.KNOWN:
        return None if RC.valid_call(r['next_call']) else 'malformed call'
    return f


def design_17(out, run_dir):
    info, fork_to = info_17()
    rows = read_jsonl(run_dir / 'results.jsonl')
    arms, seeds = ARMS['17'], SEEDS['17']
    usable = {}
    kinds = defaultdict(collections.Counter)
    api = collections.Counter()
    usable_n = collections.Counter()
    seen = set()
    dups = unknown = mism = 0
    for r in rows:
        key = (r['task'], r['run'], r['fork'])
        if key not in fork_to:
            unknown += 1
            r['_arm'] = None
            continue
        sid, arm = fork_to[key]
        r['_arm'] = arm
        if r.get('record_arm') not in (None, arm):
            mism += 1
        cell = (sid, arm, r['seed'])
        if is_api_failure(r):
            api[arm] += 1
            continue
        f = failure_17(r)
        if f:
            kinds[arm]['adapter error' if f == 'runner error' else f] += 1
            continue
        usable_n[arm] += 1
        if cell in seen:
            dups += 1
            continue
        seen.add(cell)
        usable[cell] = R15.score(info[sid]['task'], r, info[sid]['hitfiles'])
    out('  design 17 (own search with and without line numbers; arms S, S0, S0N; seeds 1-3)')
    stopped = run_facts(out, run_dir, rows)
    out(f'    rows of unknown steps {unknown}; record_arm differing from the fork id {mism}; repeated usable cells {dups}')
    gate_ok = counts_block(out, '17', rows, kinds, usable_n, api)
    cut = bool(stopped) or len(rows) < PLANNED['17']
    sids = sorted(info)

    def complete(arms_):
        return [s for s in sids if all((s, a, sd) in usable for a in arms_ for sd in seeds)]
    comp = complete(arms)
    comp2 = complete(('S', 'S0'))
    floor_ok = len(comp) >= FLOOR['17']
    out(f'    complete steps (S, S0, S0N) {len(comp)} of {len(sids)} (floor {FLOOR["17"]}: '
        f'{"met" if floor_ok else "NOT met"}); complete in S and S0 alone {len(comp2)}'
        + ('; RUN CUT (guard stop or rows missing)' if cut else ''))

    def tallies(steps):
        y1 = {a: {} for a in arms}
        y2 = {a: {} for a in arms}
        n = {a: {} for a in arms}
        for s in steps:
            for a in arms:
                os_ = [usable[(s, a, sd)] for sd in seeds if (s, a, sd) in usable]
                y1[a][s] = sum(1 for o in os_ if o['reads_hit_file'] and o['past_line_1'])
                y2[a][s] = sum(1 for o in os_ if o['reads_hit_file'])
                n[a][s] = len(os_)
        return y1, y2, n
    y1, y2, n = tallies(comp)
    for a in arms:
        k1, k2, nn = sum(y1[a].values()), sum(y2[a].values()), sum(n[a].values())
        out(f'    {a:4s} Y1 {pct(k1, nn)}; reads of a hit file {pct(k2, nn)}; of those past line 1 {pct(k1, k2)}')
    t = boot_diff(comp, y1['S'], n['S'], y1['S0'], n['S0'])
    v = verdict(gate_ok, cut, len(comp), FLOOR['17'], t)
    out(f'    V2  Y1(S) minus Y1(S0): {fmt_d(t)} points -> {v}')
    t_ns = boot_diff(comp, y1['S0N'], n['S0N'], y1['S'], n['S'])
    t_n0 = boot_diff(comp, y1['S0N'], n['S0N'], y1['S0'], n['S0'])
    out(f'        no rule: Y1(S0N) minus Y1(S) {fmt_d(t_ns)}; Y1(S0N) minus Y1(S0) {fmt_d(t_n0)}')
    a1, _, a3 = tallies(comp2)
    t2 = boot_diff(comp2, a1['S'], a3['S'], a1['S0'], a3['S0'])
    out(f'        variant, steps complete in S and S0 alone ({len(comp2)}): Y1(S) minus Y1(S0) {fmt_d(t2)} (no verdict)')
    out('    no rule: of the next calls that read a hit file, how many ask past line 1 (all usable replays):')
    for a in arms:
        os_ = [o for (s, aa, sd), o in usable.items() if aa == a]
        reads = [o for o in os_ if o['reads_hit_file']]
        mg = sum(1 for o in reads if o['mangled_start'])
        out(f'      {a:4s} {pct(sum(o["past_line_1"] for o in reads), len(reads))} (via a mangled start_line {mg}); '
            f'usable replays {len(os_)}')
    out('')
    return t, v, len(comp)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(HERE / 'results' / '19'))
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    root = Path(args.root)
    out = Report()
    out('Re-derivation of pre-registration 19 (independent script, written blind from the registration texts and the raw rows)')
    out('Script: analysis/rederive_19.py; imports rederive_cd.py (design 10 scorer) and rederive_15.py (design 17 scorer).')
    for p in (STATES_10, STATES_17):
        h = md5(p)
        out(f'States file {RC.shown(p)} md5 {h} ({"as registered" if h == MD5[p] else "DIFFERS from " + MD5[p]})')
    out(f'Bootstrap by step: {NB} resamples, numpy default_rng({BOOT_SEED}), percentile 95%. Gate {int(GATE * 100)}% '
        f'valid tool calls; floors {FLOOR["10"]} (design 10) and {FLOOR["17"]} (design 17) complete steps.')
    out('')
    states10 = RC.load_states(STATES_10)
    models = sorted({d.name for des in ('10', '17') if (root / des).is_dir() for d in (root / des).iterdir()
                     if (d / 'forks' / 'results.jsonl').exists()}, key=str.lower)
    table = []
    for m in models:
        out(f'MODEL {m}')
        r10 = r17 = None
        d10 = root / '10' / m / 'forks'
        d17 = root / '17' / m / 'forks'
        if (d10 / 'results.jsonl').exists():
            r10 = design_10(out, d10, states10)
        else:
            out('  design 10: no rows')
        if (d17 / 'results.jsonl').exists():
            r17 = design_17(out, d17)
        else:
            out('  design 17: no rows')
        table.append((m, r10, r17))
    out('TABLE (difference in points with its 95% bootstrap interval by step; verdict; complete steps)')
    out(f'  {"model":40s} {"V1: E - H (design 10)":30s} {"V1 verdict":18s} {"V2: S - S0 (design 17)":30s} V2 verdict')
    for m, r10, r17 in table:
        a = (fmt_d(r10[0]) + f' n={r10[2]}') if r10 else 'no rows'
        b = (fmt_d(r17[0]) + f' n={r17[2]}') if r17 else 'no rows'
        out(f'  {m:40s} {a:30s} {(r10[1] if r10 else "no rows"):18s} {b:30s} {r17[1] if r17 else "no rows"}')
    for des, idx in (('V1', 1), ('V2', 2)):
        c = collections.Counter((r[idx][1] if r[idx] else 'no rows') for r in table)
        out(f'  {des}: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))
    out('')
    out('JUDGMENT CALLS (where the registration left room)')
    for j in JUDGMENT:
        out('  - ' + j)
    text = '\n'.join(out.lines) + '\n'
    if args.no_write:
        print('\n(--no-write: nothing written)')
        return
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print(f'\nwrote {RC.shown(OUT)}')


if __name__ == '__main__':
    main()
