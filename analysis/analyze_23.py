"""Experiment 23, the registered analysis: whole runs in which the code graph's answers are pushed at the agent after
its reads, with addresses (PE) or as names (PH), against the harness as shipped (N).

Usage:
  py -I -X utf8 analysis/analyze_23.py [--seed 2] [--no-write]
  py -I -X utf8 analysis/analyze_23.py --standin        (the stored seed-1 runs of 14 stand in: N as N, N as PH, NAF as
                                                          PE, their pushes replayed offline; prints only, writes nothing)

Inputs: analysis/results/23/{N,PH,PE}/seed<k> on the 103 validated tasks of pre-registration 14
(analysis/results/14/validate/tasks_ok.txt). Any arm may have run alone. The stored N run of 14 (seed 1) is read as
another launch: for description, and for the comparisons with N when N did not run in this launch.

Per run, the outcomes of analysis/analyze_14.py score_run, computed by its functions on every tool call paired with its
OWN result (a step with several calls holds the first result in its observation and the others in the 'system' steps
that follow it; analyze_14's loader gives them to the last call or loses them; the pairing is that of
analysis/rederive_18.load_calls_paired), plus PATCH TOUCHES EVERY CHANGED REGION (analyze_18), CONTEXT-WINDOW ENDING,
and:
  READ          a read_file call whose paired result has status ok; its FILE is the result's filepath (else the
                argument) without a leading /workspace/, workspace/ or ./
  START         of a READ: none if the call gives no start_line argument (under any spelling); otherwise the
                start_line the result returned (the asked one if none was returned). A misspelled start_line is
                answered from line 1, so its START is 1. "Past line 1": START > 1.
  LINES READ    per run: the sum over READs of (returned end_line - start_line + 1), repetitions counted (as
                analysis/rederive_reads_22.py)
  PUSHED LIST   a READ whose result carries the key `code_graph` (the trace records what the agent received). Its
                entries with file and line range come from the run's extra.jsonl (in push order; the names are checked
                against the trace); for PE the trace's own entries hold them too. The pushes are also replayed offline
                with analysis/modal_h/push_23.py on the run's READs (data/graphs, data/cache/fresh_spans) and compared.
  A1 READ       the run's first READ of a file that holds an entry of a pushed list, made after that push, when the
                run had made no READ of that file before it
Rules, paired by task on the tasks where both runs entered, 95% bootstrap by task (2,000 resamples, seed 0,
analyze_forks.diff_ci), a verdict only with at least 80 such tasks, exact McNemar p beside where the outcome is binary:
  G0  gate, no verdict: the share of entered PE runs, and of entered PH runs, with at least one pushed list. The rules
      below are read only if every push arm of this launch has a share of at least 80%.
  A1  the address at the first read: per run, the share of its A1 READs that start past line 1; per task, PE minus
      PH, on the tasks where both runs have at least one A1 READ (at least MIN_A1 such tasks besides the floor of
      80): "an address moves the read" if the interval lies above zero, else "not detected"
  A2  reading: LINES READ per run, PE minus PH: "an address saves reading" if the interval lies below zero, else
      "not detected"
  A3  resolved, PE against PH: "more" / "fewer" / "no detectable difference"
  P1  resolved, PE against N; P2 resolved, PH against N: the same three words
  H1  harm: context-window ending, PE minus N and PH minus N: "harm" if an interval lies above zero, else "no
      detectable harm"
A rule whose two arms did not both run in this launch has no verdict; if N did not run, P1, P2 and H1 are printed
against the stored N run of 14 (seed 1), marked as another launch, without a verdict.
No rule: uptake (pushed entries whose file is READ within the three calls after the push; whether that READ starts
inside the pushed range); A1 READs and their starts; shown every changed region; shown a changed line within eight
calls; final patch overlaps a changed region; tool calls, reads, LINES READ, graph-tool calls; characters pushed per
run; endings; by repository.
Output: analysis/results/23/analyze_23.txt (exactly the text --no-write prints) and analysis/results/23/runs_23.csv.
"""
import argparse
import collections
import csv
import io
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'modal_h'))
import analyze_14 as A  # noqa: E402
import analyze_18 as B  # noqa: E402
import push_23 as P  # noqa: E402
from public_runs_address import GRAPH_TOOLS, norm, result_of  # noqa: E402
from public_runs_time_to_fix import INF, first_shown, gold_regions, jsonl  # noqa: E402

ROOT_23 = HERE / 'results' / '23'
ROOT_14 = HERE / 'results' / '14'
TASKS = ROOT_14 / 'validate' / 'tasks_ok.txt'
GRAPHS = A.DATA / 'graphs'
SPANS = A.DATA / 'cache' / 'fresh_spans'
ARMS = ('N', 'PH', 'PE')
PUSH_ARMS = ('PH', 'PE')
MIN_TASKS = 80
MIN_A1 = 20
GATE = 0.80
UPTAKE_CALLS = 3
K = 8
KEY = P.KEY


# ---------------------------------------------------------------- per run

def paired_calls(trace):
    """[(call, result text, parsed result)] with every call paired with its own result (rederive_18's pairing)."""
    steps = (trace or {}).get('steps') or []
    out, i = [], 0
    while i < len(steps):
        tcs = steps[i].get('tool_calls') or []
        if not tcs:
            i += 1
            continue
        obs = [steps[i]]
        j = i + 1
        while j < len(steps) and not steps[j].get('tool_calls') and steps[j].get('source') == 'system' and 'observation' in steps[j]:
            obs.append(steps[j])
            j += 1
        for k, tc in enumerate(tcs):
            text, parsed = result_of(obs[k]) if k < len(obs) else ('', None)
            out.append((tc, text, parsed))
        i = j
    return out


def is_ok_read(call, parsed):
    return A.is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok'


def read_file_of(call, parsed):
    return norm(parsed.get('filepath') or call['arguments'].get('filepath'))


def start_of(call, parsed):
    """START of a READ (None: no start_line argument)."""
    s, _e = A.asked(call)
    if not any(A.clean(k) == 'start_line' for k in call['arguments']):
        return None
    got = parsed.get('start_line')
    return got if isinstance(got, int) else s


def lines_read(calls):
    n = 0
    for c, _t, p in calls:
        if is_ok_read(c, p):
            s, e = p.get('start_line'), p.get('end_line')
            if isinstance(s, int) and isinstance(e, int) and e >= s:
                n += e - s + 1
    return n


_GRAPH = {}


def replay_pushes(task, calls, meta):
    """[(call index, value)] that push_23 gives on the run's READs (offline: data/graphs, data/cache/fresh_spans)."""
    t = meta[task]
    key = f"{t['repo'].split('/')[1]}_{t['base_commit']}"
    if key not in _GRAPH:
        _GRAPH[key] = P.neighbor_sets(json.load(open(GRAPHS / f'{key}.json', encoding='utf-8')))
    pusher = P.Pusher(_GRAPH[key], json.loads((SPANS / f'{task}.json').read_text(encoding='utf-8')))
    out = []
    for i, (c, _t, p) in enumerate(calls):
        if not A.is_read(c):
            continue
        r = P.shown_range(p)
        if r is None:
            continue
        value = pusher.on_read(p.get('filepath') or c['arguments'].get('filepath'), *r)
        if value:
            out.append((i, value))
    return out


def names_of(value):
    return [n.get('name') for v in value if isinstance(v, dict) for n in v.get('neighbors') or [] if isinstance(n, dict)]


def pushes_of(task, arm, calls, extra, meta, replay_only, chk):
    """[(call index, [entry with name, file, lines], characters the agent received)] of a run, and how it was read."""
    replayed = replay_pushes(task, calls, meta)
    if replay_only:
        return [(i, [{'node': v['node'], **n} for v in val for n in v['neighbors']],
                 len(json.dumps(P.as_shown(val, arm), ensure_ascii=False))) for i, val in replayed], 'replayed'
    in_trace = [(i, p[KEY]) for i, (c, _t, p) in enumerate(calls)
                if A.is_read(c) and isinstance(p, dict) and isinstance(p.get(KEY), list)]
    rec = list((extra or {}).get('pushes') or [])
    if [i for i, _v in replayed] != [i for i, _v in in_trace] or [names_of(v) for _i, v in replayed] != \
            [names_of(v) for _i, v in in_trace]:
        chk['runs whose offline replay of the push differs from the trace'] += 1
    if rec and len(rec) != len(in_trace):
        chk['runs whose extra.jsonl counts other pushes than the trace'] += 1
    out = []
    for k, (i, value) in enumerate(in_trace):
        chars = len(json.dumps(value, ensure_ascii=False))
        if k < len(rec) and [e.get('name') for e in rec[k].get('entries') or []] == names_of(value):
            out.append((i, rec[k]['entries'], chars))
            continue
        if k < len(rec):
            chk['pushes whose names differ between extra.jsonl and the trace'] += 1
        ents = [{'node': v.get('node'), **n} for v in value if isinstance(v, dict) for n in v.get('neighbors') or []
                if isinstance(n, dict)]
        if not all('file' in e and 'lines' in e for e in ents):
            chk['pushes without file and lines in the trace or extra.jsonl (left without A1 and uptake)'] += 1
            ents = [e for e in ents if 'file' in e and 'lines' in e]
        out.append((i, ents, chars))
    return out, 'trace'


def a1_reads(calls, pushes):
    """[START past line 1 (bool)] of the run's A1 READs."""
    pushed_at = {}
    for i, ents, _c in pushes:
        for e in ents:
            pushed_at.setdefault(norm(e['file']), i)
    first = {}
    for i, (c, _t, p) in enumerate(calls):
        if is_ok_read(c, p):
            first.setdefault(read_file_of(c, p), (i, start_of(c, p)))
    return [s is not None and s > 1 for f, ip in pushed_at.items() if f in first and first[f][0] > ip
            for _i, s in [first[f]]]


def uptake(calls, pushes, g):
    """Pushed entries; of them, whose file is READ within the UPTAKE_CALLS calls after the push; of those, whose first
    such READ starts inside the pushed range; and of those, whose range holds a changed region. The same for the
    entries in another file than the read that got the push."""
    c = collections.Counter()
    for i, ents, _c in pushes:
        src = read_file_of(calls[i][0], calls[i][2])
        later = [(cl, p) for cl, _t, p in calls[i + 1:i + 1 + UPTAKE_CALLS] if is_ok_read(cl, p)]
        for e in ents:
            f = norm(e.get('file'))
            for tag in ('', '_other') if f != src else ('',):
                c['entries' + tag] += 1
            r = P.span(e)
            hit = next(((cl, p) for cl, p in later if read_file_of(cl, p) == f), None)
            if hit is None:
                continue
            s = start_of(*hit)
            for tag in ('', '_other') if f != src else ('',):
                c['entries_read' + tag] += 1
                if r is not None and s is not None and r[0] <= s <= r[1]:
                    c['entries_read_inside' + tag] += 1
                    c['entries_inside_hold_change' + tag] += any(not (r[1] < a or r[0] > b) for a, b in g.get(f, []))
    return {k + tag: c[k + tag] for k in ('entries', 'entries_read', 'entries_read_inside', 'entries_inside_hold_change')
            for tag in ('', '_other')}


def score_run(task, arm, trace, result, patch, gold, extra, meta, replay_only, chk):
    """analyze_14.score_run, on paired calls, and the outcomes of experiment 23."""
    calls = paired_calls(trace) if trace is not None else []
    g = gold.get(task, {})
    t_shown = first_shown(calls, g, task=task, shell=True)[0]
    ended, infra, bad_patch = A.classify_ending(result, calls, trace is not None)
    pf, po = A.patch_outcomes(patch, g)
    graph = collections.Counter(c.get('function_name') for c, _t, _p in calls if c.get('function_name') in GRAPH_TOOLS)
    inter = A.interface_counts(trace, calls)
    if bad_patch:
        inter['patch did not apply in the test container'] += 1
    if ended == 'context window':
        inter['context window exceeded (session ended)'] += 1
    x = {'task': task, 'gold': bool(g), 'resolved': A.truth(result.get('resolved')), 't': t_shown,
         'every': A.every_region(calls, g), 'patch': bool(patch.strip()), 'patch_file': pf, 'patch_region': po,
         'n': len(calls), 'n_harness': result.get('tool_calls'), 'ended': ended, 'infra': infra,
         'trace': trace is not None, 'reads': A.read_counts(calls), 'graph': graph, 'interface': inter,
         'repo': result.get('repo') or ''}
    x['touch_all'] = B.touches_every_region(patch, g)
    x['ctx'] = ended == 'context window'
    x['entered'] = infra is None
    x['lines'] = lines_read(calls)
    if arm in PUSH_ARMS and trace is not None:
        pushes, how = pushes_of(task, arm, calls, extra, meta, replay_only, chk)
    else:
        pushes, how = [], 'none'
        if trace is not None and any(isinstance(p, dict) and KEY in p for _c, _t, p in calls):
            chk['runs of an arm without a push whose trace holds the key'] += 1
    x['pushes'] = len(pushes)
    x['push_source'] = how
    x['push_chars'] = sum(ch for _i, _e, ch in pushes)
    x['a1'] = a1_reads(calls, pushes)
    x.update(uptake(calls, pushes, g))
    return x


# ---------------------------------------------------------------- loading

def load_arm(root, arm, seed):
    saved = A.CONDITIONS
    A.CONDITIONS = (arm,)
    try:
        runs, notes = A.load_root(root)
    finally:
        A.CONDITIONS = saved
    return {t: v for (t, c, s), v in runs.items() if c == arm and s == seed}, notes


def collect(standin, seed):
    n14, notes14 = load_arm(ROOT_14, 'N', 1)
    runs = {'N14': n14}
    notes = [f'14 (another launch, seed 1): {n}' for n in notes14 if n.startswith('N/')]
    if standin:
        naf, _ = load_arm(ROOT_14, 'NAF', 1)
        runs['N'], runs['PH'], runs['PE'] = n14, n14, naf
        notes.append('STAND-IN: N and PH are the stored N run of 14, PE the stored NAF run of 14 (seed 1); no agent saw a '
                     'push: the pushes of PH and PE are replayed offline on their reads')
        return runs, notes
    for arm in ARMS:
        if (ROOT_23 / arm / f'seed{seed}').is_dir():
            runs[arm], n = load_arm(ROOT_23, arm, seed)
            notes += [f'23 (seed {seed}): {x}' for x in n if x.startswith(f'{arm}/')]
        else:
            notes.append(f'23: arm {arm} has no stored runs for seed {seed} (not run in this launch)')
    return runs, notes


def score(runs, tasks, standin, chk):
    gold = gold_regions()
    meta = {t['instance_id']: t for t in jsonl(A.DATA / 'tasks.jsonl')}
    rows = {}
    for arm, by_task in runs.items():
        for task, (trace, result, patch, extra) in by_task.items():
            if task in tasks:
                c = collections.Counter()
                x = score_run(task, arm, trace, result, patch, gold, extra, meta, standin and arm in PUSH_ARMS, c)
                for k, v in c.items():
                    chk[f'{arm}: {k}'] += v
                x['repo'] = meta.get(task, {}).get('repo') or x['repo']
                x['extra'] = extra
                rows[(task, arm)] = x
    return rows


# ---------------------------------------------------------------- rules

def verdict_of(d, n, words, floor_ok, gate_ok, same_launch, extra_floor=None):
    if not same_launch:
        return 'no verdict (another launch, or an arm not run: description only)'
    if not gate_ok:
        return 'not read (gate G0 not met)'
    if n < MIN_TASKS:
        return f'no verdict (fewer than {MIN_TASKS} tasks)'
    if extra_floor is not None and not floor_ok:
        return extra_floor
    if d[0] is None:
        return 'no pairs: no estimate'
    if words[0] and d[1] > 0:
        return words[0]
    if words[1] and d[2] < 0:
        return words[1]
    return words[2]


def entered_pairs(rows, tasks, a, b):
    return [t for t in tasks if (t, a) in rows and (t, b) in rows and rows[(t, a)]['entered'] and rows[(t, b)]['entered']]


def binary_rule(rows, tasks, name, what, a, b, fn, words, gate_ok, same_launch):
    keys = entered_pairs(rows, tasks, a, b)
    xa = {t: [int(fn(rows[(t, a)]))] for t in keys}
    xb = {t: [int(fn(rows[(t, b)]))] for t in keys}
    d = A.diff_ci(xa, xb)
    da = sum(1 for t in keys if xa[t][0] and not xb[t][0])
    db = sum(1 for t in keys if xb[t][0] and not xa[t][0])
    print(f'   {name} {what}, {a} against {b}: {A.dpts(d)}; {a} {A.pct(sum(v[0] for v in xa.values()), len(keys))}, '
          f'{b} {A.pct(sum(v[0] for v in xb.values()), len(keys))}; {len(keys)} tasks; {a} only {da}, {b} only {db}, exact '
          f'McNemar p {A.mcnemar_p(da, db):.4f}')
    v = verdict_of(d, len(keys), words, True, gate_ok, same_launch)
    print(f'      verdict: {v}')
    return v


def rule_a1(rows, tasks, gate_ok, same_launch):
    keys = entered_pairs(rows, tasks, 'PE', 'PH')
    both = [t for t in keys if rows[(t, 'PE')]['a1'] and rows[(t, 'PH')]['a1']]
    share = {arm: {t: [statistics.mean(rows[(t, arm)]['a1'])] for t in both} for arm in ('PE', 'PH')}
    d = A.diff_ci(share['PE'], share['PH'])
    pooled = {arm: (sum(sum(rows[(t, arm)]['a1']) for t in keys), sum(len(rows[(t, arm)]['a1']) for t in keys))
              for arm in ('PE', 'PH')}
    print(f'   A1 first READ of a pushed file past line 1, per task PE minus PH: {A.dpts(d)} on {len(both)} tasks with an '
          f'A1 READ in both runs (of {len(keys)} tasks where both entered); per-task share, mean: PE '
          f'{100 * statistics.mean(v[0] for v in share["PE"].values()) if both else float("nan"):.1f}%, PH '
          f'{100 * statistics.mean(v[0] for v in share["PH"].values()) if both else float("nan"):.1f}%; all A1 READs: '
          f'PE {A.pct(*pooled["PE"])}, PH {A.pct(*pooled["PH"])} past line 1; runs with an A1 READ: PE '
          f'{sum(bool(rows[(t, "PE")]["a1"]) for t in keys)}, PH {sum(bool(rows[(t, "PH")]["a1"]) for t in keys)}')
    v = verdict_of(d, len(keys), ('an address moves the read', None, 'not detected'), len(both) >= MIN_A1, gate_ok,
                   same_launch, extra_floor=f'no verdict (fewer than {MIN_A1} tasks with an A1 READ in both runs)')
    print(f'      verdict: {v}')
    return v


def rule_a2(rows, tasks, gate_ok, same_launch):
    keys = entered_pairs(rows, tasks, 'PE', 'PH')
    xa = {t: [rows[(t, 'PE')]['lines']] for t in keys}
    xb = {t: [rows[(t, 'PH')]['lines']] for t in keys}
    d = A.diff_ci(xa, xb)
    med = {arm: statistics.median(v[0] for v in x.values()) if keys else 0 for arm, x in (('PE', xa), ('PH', xb))}
    fmt = 'n/a' if d[0] is None else f'{d[0]:+.1f} lines [{d[1]:+.1f}, {d[2]:+.1f}]'
    print(f'   A2 LINES READ per run, PE minus PH: {fmt}; mean PE '
          f'{statistics.mean(v[0] for v in xa.values()) if keys else 0:.1f}, PH '
          f'{statistics.mean(v[0] for v in xb.values()) if keys else 0:.1f}; median PE {med["PE"]:g}, PH {med["PH"]:g}; '
          f'{len(keys)} tasks')
    v = verdict_of(d, len(keys), (None, 'an address saves reading', 'not detected'), True, gate_ok, same_launch)
    print(f'      verdict: {v}')
    return v


def gate(rows, tasks, arms_run):
    print('2. G0, gate (no verdict): entered runs with at least one pushed list; the rules are read only if every push '
          f'arm of this launch has at least {100 * GATE:.0f}%')
    ok = True
    for arm in PUSH_ARMS:
        if arm not in arms_run:
            print(f'   {arm}: not run in this launch')
            continue
        sel = [rows[(t, arm)] for t in tasks if (t, arm) in rows and rows[(t, arm)]['entered']]
        got = sum(x['pushes'] > 0 for x in sel)
        share = got / len(sel) if sel else 0.0
        ok &= bool(sel) and share >= GATE
        how = collections.Counter(x['push_source'] for x in sel)
        print(f'   {arm}: {A.pct(got, len(sel))} (pushes read from: {dict(how)})')
        ex = [x['extra'] for x in sel if x['extra']]
        if ex and any('pushed_reads' in e for e in ex):
            print(f'      from extra.jsonl: runs with a push {sum((e.get("pushed_reads") or 0) > 0 for e in ex)} of '
                  f'{len(ex)}; pushed reads {sum(e.get("pushed_reads") or 0 for e in ex)} (in the traces '
                  f'{sum(x["pushes"] for x in sel)}); entries {sum(e.get("pushed_entries") or 0 for e in ex)} (in the '
                  f'traces {sum(x["entries"] for x in sel)}); characters the agent received '
                  f'{sum(e.get("push_chars") or 0 for e in ex)} (in the traces {sum(x["push_chars"] for x in sel)})')
    print(f'   gate: {"MET" if ok else "NOT MET"}')
    return ok


def rules(rows, tasks, arms_run, gate_ok):
    three = ('more', 'fewer', 'no detectable difference')
    harm = ('harm', None, 'no detectable harm')
    push_both = 'PE' in arms_run and 'PH' in arms_run
    out = {'A1': rule_a1(rows, tasks, gate_ok, push_both), 'A2': rule_a2(rows, tasks, gate_ok, push_both),
           'A3': binary_rule(rows, tasks, 'A3', 'resolved', 'PE', 'PH', lambda x: x['resolved'], three, gate_ok,
                             push_both)}
    control = 'N' if 'N' in arms_run else 'N14'
    if control == 'N14':
        print('   N did not run in this launch: P1, P2 and H1 have no verdict. The same comparisons against the stored N '
              'run of 14 (seed 1, ANOTHER LAUNCH, description only):')
    for name, arm in (('P1', 'PE'), ('P2', 'PH')):
        out[name] = binary_rule(rows, tasks, name, 'resolved', arm, control, lambda x: x['resolved'], three, gate_ok,
                                arm in arms_run and control == 'N')
    for arm in PUSH_ARMS:
        out[f'H1 {arm}'] = binary_rule(rows, tasks, 'H1', 'context-window ending (harm)', arm, control,
                                       lambda x: x['ctx'], harm, gate_ok, arm in arms_run and control == 'N')
    return out


# ---------------------------------------------------------------- report

def med(v):
    v = list(v)
    return f'{statistics.median(v):g}' if v else 'none'


def report(rows, tasks, notes, label, arms_run, chk):
    arms = [c for c in ('N', 'PH', 'PE', 'N14') if any((t, c) in rows for t in tasks)]
    print(f'EXPERIMENT 23: whole runs with the code graph\'s answers pushed at the agent, as names (PH) and with addresses '
          f'(PE), against the harness as shipped (N) ({label})')
    print()
    print('0. Inputs')
    for n in notes:
        print(f'   {n}')
    print(f'   tasks: {len(tasks)} (the validated list of pre-registration 14)')
    print('   checks: ' + ('; '.join(f'{k} {v}' for k, v in sorted(chk.items())) or 'none'))
    print()
    print('1. Runs per arm (N, PH, PE: this launch; N14: the stored N run of 14, seed 1, another launch)')
    for c in arms:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows]
        infra = [(x['task'], x['infra']) for x in sel if x['infra']]
        print(f'   {c:<4} runs {len(sel)}; entered {sum(x["entered"] for x in sel)}; without a trace '
              f'{sum(not x["trace"] for x in sel)}; infrastructure failures {len(infra)}'
              + (': ' + '; '.join(f'{t} {k}' for t, k in infra) if infra else ''))
    print()
    gate_ok = gate(rows, tasks, arms_run)
    print()
    print(f'3. Rules (paired by task on the tasks where both runs entered; 95% bootstrap by task, 2,000 resamples, seed 0; '
          f'a verdict needs at least {MIN_TASKS} tasks)')
    verdicts = rules(rows, tasks, arms_run, gate_ok)
    print()
    print('4. No rule: reported (entered runs of each arm; N14: another launch)')
    for c in arms:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows and rows[(t, c)]['entered']]
        if not sel:
            continue
        rc, gc = collections.Counter(), collections.Counter()
        for x in sel:
            rc.update(x['reads'])
            gc.update(x['graph'])
        print(f'   {c}: runs {len(sel)}; resolved {A.pct(sum(x["resolved"] for x in sel), len(sel))}; shown a changed line '
              f'within {K} calls {A.pct(sum(x["t"] <= K for x in sel), len(sel))}; every region shown '
              f'{A.pct(sum(x["every"] for x in sel), len(sel))}; patch overlaps a changed region '
              f'{A.pct(sum(x["patch_region"] for x in sel), len(sel))}; patch touches every changed region '
              f'{A.pct(sum(x["touch_all"] for x in sel), len(sel))}; context-window endings {A.pct(sum(x["ctx"] for x in sel), len(sel))}')
        print(f'      tool calls median {med(x["n"] for x in sel)}; executed reads {rc["reads"]} (ranged {rc["ranged"]}, '
              f'mangled {rc["mangled"]}); LINES READ per run mean {statistics.mean(x["lines"] for x in sel):.1f}, median '
              f'{med(x["lines"] for x in sel)}; runs with a graph-tool call {A.pct(sum(bool(x["graph"]) for x in sel), len(sel))}, '
              f'calls ' + ', '.join(f'{k} {gc[k]}' for k in GRAPH_TOOLS))
        pushed = [x for x in sel if x['pushes']]
        a1 = [s for x in sel for s in x['a1']]
        print(f'      pushed lists {sum(x["pushes"] for x in sel)} in {len(pushed)} runs (per run median '
              f'{med(x["pushes"] for x in sel)}); entries {sum(x["entries"] for x in sel)}; characters the agent received per '
              f'run median {med(x["push_chars"] for x in sel)}, max {max(x["push_chars"] for x in sel)}')
        print(f'      uptake: entries whose file is READ within {UPTAKE_CALLS} calls {sum(x["entries_read"] for x in sel)} of '
              f'{sum(x["entries"] for x in sel)} (runs {sum(x["entries_read"] > 0 for x in sel)}); that READ starts inside the '
              f'pushed range {sum(x["entries_read_inside"] for x in sel)}, of which the range holds a changed region '
              f'{sum(x["entries_inside_hold_change"] for x in sel)}')
        print(f'         entries in another file than the read that got the push: {sum(x["entries_other"] for x in sel)}; '
              f'file READ within {UPTAKE_CALLS} calls {sum(x["entries_read_other"] for x in sel)} (runs '
              f'{sum(x["entries_read_other"] > 0 for x in sel)}); starts inside the pushed range '
              f'{sum(x["entries_read_inside_other"] for x in sel)}, of which the range holds a changed region '
              f'{sum(x["entries_inside_hold_change_other"] for x in sel)}')
        print(f'      A1 READs {len(a1)} in {sum(bool(x["a1"]) for x in sel)} runs; past line 1 {A.pct(sum(a1), len(a1))}')
        e = collections.Counter(x['ended'] for x in sel)
        print('      ended: ' + '; '.join(f'{k} {v}' for k, v in e.most_common()))
    print('   by repository (entered runs): resolved; context-window endings; LINES READ per run, mean; A1 READs past line '
          '1; pushed entries whose file is READ within 3 calls')
    repos = sorted({rows[(t, c)]['repo'] for t in tasks for c in arms if (t, c) in rows})
    for r in repos:
        parts = []
        for c in arms:
            sel = [rows[(t, c)] for t in tasks if (t, c) in rows and rows[(t, c)]['entered'] and rows[(t, c)]['repo'] == r]
            if not sel:
                continue
            a1 = [s for x in sel for s in x['a1']]
            parts.append(f'{c} {sum(x["resolved"] for x in sel)}/{len(sel)}, {sum(x["ctx"] for x in sel)}, '
                         f'{statistics.mean(x["lines"] for x in sel):.0f}, {sum(a1)}/{len(a1)}, '
                         f'{sum(x["entries_read"] for x in sel)}/{sum(x["entries"] for x in sel)}')
        print(f'      {r}: ' + '; '.join(parts))
    return verdicts


def write_csv(rows, tasks, path, seed):
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['task', 'arm', 'launch', 'seed', 'repo', 'entered', 'infrastructure', 'resolved', 't_shown',
                    f'shown_within_{K}', 'every_region', 'patch_overlaps', 'patch_touches_every_region',
                    'context_window_ending', 'lines_read', 'pushes', 'push_chars', 'pushed_entries', 'entries_read_within_3',
                    'entries_read_inside_range', 'a1_reads', 'a1_past_line_1', 'tool_calls', 'ended', 'reads', 'graph_calls'])
        for t in tasks:
            for c in ('N', 'PH', 'PE', 'N14'):
                x = rows.get((t, c))
                if x is None:
                    continue
                w.writerow([t, 'N' if c == 'N14' else c, '14' if c == 'N14' else '23', 1 if c == 'N14' else seed, x['repo'],
                            int(x['entered']), x['infra'] or '', int(x['resolved']), 'inf' if x['t'] == INF else x['t'],
                            int(x['t'] <= K), int(x['every']), int(x['patch_region']), int(x['touch_all']), int(x['ctx']),
                            x['lines'], x['pushes'], x['push_chars'], x['entries'], x['entries_read'],
                            x['entries_read_inside'], len(x['a1']), sum(x['a1']), x['n'], x['ended'], x['reads']['reads'],
                            sum(x['graph'].values())])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--standin', action='store_true')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--seed', type=int, default=2)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = [line.strip() for line in open(TASKS, encoding='utf-8') if line.strip()]
    assert len(tasks) == 103 and len(set(tasks)) == 103, len(tasks)
    if not args.standin and not any((ROOT_23 / a / f'seed{args.seed}').is_dir() for a in PUSH_ARMS):
        sys.exit(f'no stored PH or PE runs under {ROOT_23}: run analysis/store_23.py first (or use --standin)')
    runs, notes = collect(args.standin, args.seed)
    chk = collections.Counter()
    rows = score(runs, set(tasks), args.standin, chk)
    arms_run = [a for a in ARMS if a in runs]
    label = ('STAND-IN: N and PH = stored N of 14, PE = stored NAF of 14, pushes replayed' if args.standin
             else f'seed {args.seed}')
    buf = io.StringIO()
    saved, sys.stdout = sys.stdout, buf
    try:
        report(rows, tasks, notes, label, arms_run, chk)
    finally:
        sys.stdout = saved
    text = buf.getvalue()
    sys.stdout.write(text)
    if not (args.no_write or args.standin):
        (ROOT_23 / 'analyze_23.txt').write_text(text, encoding='utf-8', newline='\n')
        write_csv(rows, tasks, ROOT_23 / 'runs_23.csv', args.seed)
        print(f'written: {ROOT_23 / "analyze_23.txt"} (the text above) and {ROOT_23 / "runs_23.csv"}', file=sys.stderr)


if __name__ == '__main__':
    main()
