"""Pre-registration 14: whole runs of the starter agent scored by the harness's tests, N against NAF.

Usage:
  py -I -X utf8 analysis/analyze_14.py <root> [--csv] [--csv-out <path>]
  py -I -X utf8 analysis/analyze_14.py --standin-graphloc [--csv-out <path>]

<root>/<condition>/seed<k>/ for condition N (the harness as shipped) and NAF (graph-tool answers carry each entity's
file and line range; a mangled line-bound argument name is restored before the read runs), k = 1, 2, ... Each is a
results directory of `swegemma eval` (data/HARNESS_README.md, section 9.2): task_results.jsonl, summary.json,
patches/<task>.patch, traces/trace_<task>.json, test_outputs/, logs/. An optional extra.jsonl (one JSON object per
task, key `task`) written by the runner is read defensively and summarized; it changes no outcome.

--standin-graphloc reads the public whole runs of the GraphLoc notebooks (same harness traces) through the same
per-run functions: N = arm `base`, NAF = arm `skill`, seed = notebook (1 to 3), task result = the notebook's run
record. It then checks the quantities that analysis/public_runs_time_to_fix.py also computes against its stored
output (analysis/results/public/time_to_fix.txt).

Definitions are those of analysis/public_runs_time_to_fix.py (CHANGED REGION, GOLD FILE, CALL INDEX, SHOWN A CHANGED
LINE, EVERY REGION SHOWN, FINAL PATCH, CEILING); its functions are imported. Per run (task, condition, seed):
  resolved          the harness's verdict from the tests (task result `resolved`).
  t_shown           first CALL INDEX at which the agent is SHOWN A CHANGED LINE, read or shell view
                    (first_shown(..., shell=True)[0]); infinity if never.
  every_region      EVERY REGION SHOWN.
  patch_gold_file   FINAL PATCH TOUCHES A GOLD FILE; patch_overlaps: it OVERLAPS A CHANGED REGION. The patch is
                    patches/<task>.patch, else the task result's agent_patch (or patch); an empty patch is false.
  tool_calls        every tool call in the trace (submit_patch and rejected calls included, as in the public-run
                    script); the harness's own count (which leaves out submit_patch and get_status) is shown beside.
  ended             how the session ended, from the task result's `error` text, else from the trace (see ENDINGS).
INFRASTRUCTURE FAILURE (the run does not enter the paired analysis): the task result's error says the sandbox or
snapshot could not be set up, the evaluation worker failed, the model server failed, or the tests could not be run
for a reason other than the patch (missing test specification, test patch did not apply, evaluation error). A
model-side ending (a budget, the context window, no patch, a patch that does not apply) is an outcome.
A task ENTERS the paired analysis for a seed if both conditions have a task result for it and neither is an
infrastructure failure. Tasks with no GOLD FILE are left out of the line-level outcomes only.

Rules (NAF minus N, paired by task and seed; 95% bootstrap clustered by task, 2,000 resamples, seed 0,
analyze_forks.diff_ci); they apply if at least 60 distinct tasks enter, otherwise everything is EXPLORATORY:
  T1 resolved:            lower bound > 0 "more tasks solved"; upper bound < 0 "fewer tasks solved"; else
                          "no detectable difference".
  T2 t_shown <= 8:        lower bound > 0 "sooner"; else "not detected".
  T3 patch_overlaps:      lower bound > 0 "the final patch reaches the fix more often"; upper bound < 0 "the final
                          patch reaches the fix less often"; else "no detectable difference".
"""
import argparse
import collections
import csv
import io
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from graphloc_traces import NOTEBOOKS, ROOT as GRAPHLOC, iter_runs  # noqa: E402
from make_population_k import parse_patch  # noqa: E402
from mangled_sensitivity import BOUNDS, clean, mangled  # noqa: E402
from public_runs_address import DATA, GRAPH_TOOLS, asked, calls_of, is_read, norm  # noqa: E402
from public_runs_time_to_fix import INF, first_shown, gold_regions, jsonl, overlap, truth  # noqa: E402

CONDITIONS = ('N', 'NAF')
ARMS = {'base': 'N', 'skill': 'NAF'}          # stand-in only
MIN_TASKS = 60
T2_K = 8
KS = (3, 5, 8, 10, 20)
STANDARD = {'task_results.jsonl', 'summary.json', 'patches', 'traces', 'test_outputs', 'logs', 'extra.jsonl'}

# The task result's `error` text, as the harness writes it (swegemma 0.2.11: evaluate.py, harness/agent_runner.py,
# harness/verification.py). Checked in this order; the first match decides.
INFRA = (
    ('Snapshot file not found', 'sandbox could not be set up (snapshot missing)'),
    ('Unexpected evaluation worker error', 'sandbox could not be set up (worker error, e.g. container setup)'),
    ('Missing test specification', 'tests could not be run (no test specification)'),
    ('Failed to apply test_patch', 'tests could not be run (test patch did not apply)'),
    ('Evaluation error:', 'tests could not be run (evaluation container error)'),
)
CONTEXT = ('ContextWindowExceeded', 'context length', 'context window', 'maximum context')
MODEL_SERVER = ('APIConnectionError', 'ServiceUnavailable', 'InternalServerError', 'Connection refused',
                'ConnectError', 'ConnectionError', 'RemoteDisconnected', 'ServerDisconnected', 'litellm.Timeout',
                'APITimeoutError', 'RateLimitError', 'NotFoundError', 'AuthenticationError', 'Bad Gateway',
                'Gateway Timeout')
ENDINGS = (('tool call budget', 'tool-call budget'), ('session timeout', 'time budget'), ('turns budget', 'turns budget'),
           ('maximum allowed LLM turns', 'turns budget'), ('without calling submit_patch', 'no patch'))

# Stored output of analysis/public_runs_time_to_fix.py (analysis/results/public/time_to_fix.txt), stand-in only.
STORED = {
    'pairs with both arms and a GOLD FILE': 315,
    'N shown within 5 calls': 173, 'NAF shown within 5 calls': 224,
    'N resolved': 92, 'NAF resolved': 95,
    'N ever shown a changed line': 278, 'NAF ever shown a changed line': 278,
    'EVERY REGION SHOWN (both arms, of 630)': 372,
    'runs not resolved (both arms)': 443, 'of these, FINAL PATCH OVERLAPS A CHANGED REGION': 115,
    'N tool calls per run': 26.1, 'NAF tool calls per run': 24.3,
    'CEILING, both arms (points)': 3.1,
    'CALL INDEX when first shown, NAF minus N, pairs both shown': 263,
}


# ---------------------------------------------------------------- per run

def classify_ending(result, calls, have_trace):
    """(ending kind, infrastructure kind or None, the patch did not apply)."""
    err = str(result.get('error') or result.get('error_message') or '')
    for key, kind in INFRA:
        if key in err:
            return 'infrastructure', kind, False
    if 'Sandbox execution error' in err:
        if any(k.lower() in err.lower() for k in CONTEXT):
            return 'context window', None, False
        if any(k in err for k in MODEL_SERVER):
            return 'infrastructure', 'model server failed', False
        return 'agent error (other)', None, False
    for key, kind in ENDINGS:
        if key in err:
            return kind, None, False
    bad_patch = 'Failed to apply agent patch' in err
    if not have_trace:
        return 'unknown (no trace)', None, bad_patch
    if any(c.get('function_name') == 'submit_patch' for c, _t, _p in calls):
        return 'submitted', None, bad_patch
    return 'no submit_patch call, no reason recorded', None, bad_patch


def every_region(calls, g):
    """EVERY REGION SHOWN, as public_runs_time_to_fix.graphloc_part computes it."""
    seen = collections.defaultdict(set)
    for call, _text, parsed in calls:
        if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
            f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
            s, e = parsed.get('start_line'), parsed.get('end_line')
            if f in g and isinstance(s, int) and isinstance(e, int):
                seen[f].update(i for i, (a, b) in enumerate(g[f]) if not (e < a or s > b))
    return bool(g) and all(len(seen[f]) == len(g[f]) for f in g)


def patch_outcomes(patch, g):
    """(FINAL PATCH TOUCHES A GOLD FILE, OVERLAPS A CHANGED REGION), as in public_runs_time_to_fix.graphloc_part."""
    if not patch.strip():
        return False, False
    try:
        af = {norm(k): v for k, v in parse_patch(patch).items()}
    except Exception:
        af = {}
    return (any(f in g for f in af),
            any(f in g and any(overlap(a, b, g[f]) for a, b in v['regions']) for f, v in af.items()))


def read_counts(calls):
    """Executed read_file calls; ranged (a bound under any spelling); mangled bound name; mangled with a start asked
    whose returned range starts there."""
    c = collections.Counter()
    for call, _text, parsed in calls:
        if not is_read(call) or not (isinstance(parsed, dict) and 'status' in parsed):
            continue          # a call the harness rejected before running it has no status
        c['reads'] += 1
        if any(clean(k) in BOUNDS for k in call['arguments']):
            c['ranged'] += 1
            if mangled(call):
                c['mangled'] += 1
                start, _end = asked(call)
                if start is not None and parsed.get('status') == 'ok':
                    c['mangled with a start, ok'] += 1
                    c['mangled start honored'] += int(parsed.get('start_line') == start)
    return c


def interface_counts(trace, calls):
    """Interface failures visible in the trace."""
    c = collections.Counter()
    for call, text, parsed in calls:
        name = call.get('function_name')
        if (isinstance(parsed, dict) and 'status' not in parsed and 'error' in parsed) or str(text).startswith('Invoking `'):
            c[f'call rejected, missing arguments ({name})'] += 1
        elif name == 'edit_file' and isinstance(parsed, dict) and parsed.get('status') == 'error':
            msg = ' '.join(str(parsed.get('error_message') or parsed.get('error_type') or '').split()[:5])
            c[f'edit_file error: {msg}'] += 1
    for s in (trace or {}).get('steps', []):
        if (s.get('extra') or {}).get('event_type') == 'continuation_nudge':
            c['continuation nudge (turn ended without a call; a cut-off tool call is one cause)'] += 1
    return c


def score_run(task, trace, result, patch, gold):
    """Every per-run outcome of the pre-registration. trace is the parsed trace or None."""
    calls = calls_of(trace) if trace is not None else []
    g = gold.get(task, {})
    t_shown = first_shown(calls, g, task=task, shell=True)[0]
    ended, infra, bad_patch = classify_ending(result, calls, trace is not None)
    pf, po = patch_outcomes(patch, g)
    graph = collections.Counter(c.get('function_name') for c, _t, _p in calls if c.get('function_name') in GRAPH_TOOLS)
    inter = interface_counts(trace, calls)
    if bad_patch:
        inter['patch did not apply in the test container'] += 1
    if ended == 'context window':
        inter['context window exceeded (session ended)'] += 1
    return {'task': task, 'gold': bool(g), 'resolved': truth(result.get('resolved')), 't': t_shown,
            'every': every_region(calls, g), 'patch': bool(patch.strip()), 'patch_file': pf, 'patch_region': po,
            'n': len(calls), 'n_harness': result.get('tool_calls'), 'ended': ended, 'infra': infra,
            'trace': trace is not None, 'reads': read_counts(calls), 'graph': graph, 'interface': inter,
            'repo': result.get('repo') or ''}


# ---------------------------------------------------------------- loading

def load_json(path):
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_root(root):
    """{(task, condition, seed): (trace or None, task result, patch text, extra dict)} and notes about the inputs."""
    runs, notes = {}, []
    for cond_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if cond_dir.name not in CONDITIONS:
            notes.append(f'folder {cond_dir.name}/ is not a condition: ignored')
            continue
        for sd in sorted(p for p in cond_dir.iterdir() if p.is_dir() and p.name.startswith('seed')):
            try:
                seed = int(sd.name[len('seed'):])
            except ValueError:
                notes.append(f'{cond_dir.name}/{sd.name}: not seed<k>, ignored')
                continue
            tag = f'{cond_dir.name}/{sd.name}'
            path = sd / 'task_results.jsonl'
            if not path.exists():
                notes.append(f'{tag}: no task_results.jsonl')
                continue
            lines = jsonl(path)
            res = {}
            for r in lines:
                res[r.get('instance_id') or r.get('task_id')] = r     # a task written twice: the last line counts
            if len(lines) != len(res):
                notes.append(f'{tag}: {len(lines) - len(res)} task results written more than once (the last counts)')
            extra = {}
            if (sd / 'extra.jsonl').exists():
                for r in jsonl(sd / 'extra.jsonl'):
                    extra[r.get('task') or r.get('instance_id')] = r
            summ = load_json(sd / 'summary.json')
            if isinstance(summ, dict) and summ.get('resolved') is not None:
                mine = sum(truth(r.get('resolved')) for r in res.values())
                if summ.get('resolved') != mine:
                    notes.append(f'{tag}: summary.json says resolved {summ.get("resolved")}, task_results.jsonl {mine}')
            others = sorted(p.name for p in sd.iterdir() if p.name not in STANDARD)
            if others:
                notes.append(f'{tag}: other files {others}')
            no_trace = no_patch = 0
            for task, r in res.items():
                safe = str(task).replace('/', '__')
                trace = load_json(sd / 'traces' / f'trace_{safe}.json')
                no_trace += trace is None
                pp = sd / 'patches' / f'{safe}.patch'
                if pp.exists():
                    patch = pp.read_text(encoding='utf-8', errors='replace')
                else:
                    patch = r.get('agent_patch') or r.get('patch') or ''
                    no_patch += bool((r.get('agent_patch_size') or 0) > 0 and not patch)
                runs[(task, cond_dir.name, seed)] = (trace, r, patch, extra.get(task, {}))
            traced = {p.stem[len('trace_'):] for p in (sd / 'traces').glob('trace_*.json')} if (sd / 'traces').exists() else set()
            orphan = len(traced - {str(t).replace('/', '__') for t in res})
            notes.append(f'{tag}: {len(res)} task results; trace missing {no_trace}; patch size > 0 but no patch text '
                         f'{no_patch}; traces without a task result {orphan}; extra.jsonl rows {len(extra)}')
    return runs, notes


def load_graphloc():
    """The stand-in: GraphLoc's public runs (N = base, NAF = skill, seed = notebook)."""
    rec = {}
    for nb, run in NOTEBOOKS.items():
        for p in sorted((GRAPHLOC / nb / 'e2e' / 'records').glob('rec_w*.jsonl')):
            for r in jsonl(p):
                rec[(run, r.get('arm'), r.get('id'))] = r      # the last record counts, as graphloc_records()
    runs, notes = {}, []
    for r in iter_runs():
        if r['arm'] not in ARMS:
            continue
        res = rec.get((r['run'], r['arm'], r['task']))
        if res is None:
            notes.append(f'no record for {r["task"]} notebook {r["run"]} arm {r["arm"]}')
            continue
        runs[(r['task'], ARMS[r['arm']], r['run'])] = (load_json(r['path']), res, res.get('patch') or '', {})
    notes.append(f'{len(runs)} runs with a trace and a record')
    return runs, notes


# ---------------------------------------------------------------- statistics

def boot_mean(by_task):
    """Mean and 95% bootstrap by task, as public_runs_time_to_fix.py computes the CALL INDEX difference."""
    flat = [v for vs in by_task.values() for v in vs]
    if not flat:
        return None, None, None
    rng = random.Random(0)
    tasks = sorted(by_task)
    boots = sorted(statistics.mean([v for t in (rng.choice(tasks) for _ in tasks) for v in by_task[t]]) for _ in range(2000))
    return statistics.mean(flat), boots[50], boots[1949]


def ceiling(sel):
    """CEILING, the formula of public_runs_time_to_fix.py."""
    sh = [x for x in sel if x['t'] < INF]
    nv = [x for x in sel if x['t'] == INF]
    if not sel or not sh:
        return 0.0
    return (len(nv) / len(sel)) * (sum(x['resolved'] for x in sh) / len(sh) - (sum(x['resolved'] for x in nv) / len(nv) if nv else 0.0))


def ceiling_ci(sel):
    by_task = collections.defaultdict(list)
    for x in sel:
        by_task[x['task']].append(x)
    tasks = sorted(by_task)
    if not tasks:
        return 0.0, 0.0, 0.0
    rng = random.Random(0)
    boots = sorted(ceiling([x for t in (rng.choice(tasks) for _ in tasks) for x in by_task[t]]) for _ in range(2000))
    return ceiling(sel), boots[50], boots[1949]


def mcnemar_p(b, c):
    """Exact two-sided McNemar p on the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def pct(m, n):
    return f'{m} of {n} ({100 * m / n:.1f}%)' if n else f'{m} of 0'


def rate(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dpts(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} points [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def paired(rows, keys, fn):
    """({task: [fn(NAF row)]}, {task: [fn(N row)]}) over the given (task, seed) keys."""
    a, b = collections.defaultdict(list), collections.defaultdict(list)
    for task, seed in keys:
        a[task].append(int(fn(rows[(task, 'NAF', seed)])))
        b[task].append(int(fn(rows[(task, 'N', seed)])))
    return a, b


# ---------------------------------------------------------------- report

def report(rows, label):
    seeds = sorted({s for _t, _c, s in rows})
    print(f'PRE-REGISTRATION 14: whole runs scored by tests, NAF minus N ({label})')
    print()
    print('1. Runs, infrastructure failures, pairs')
    for cond in CONDITIONS:
        sel = [x for (t, c, s), x in rows.items() if c == cond]
        print(f'   {cond:<4} runs with a task result {len(sel)} (' + ', '.join(
            f'seed {s}: {sum(1 for (t, c, s2) in rows if c == cond and s2 == s)}' for s in seeds) + ')'
            + f'; without a trace {sum(not x["trace"] for x in sel)}')
    infra = sorted(((t, c, s), x['infra']) for (t, c, s), x in rows.items() if x['infra'])
    kinds = collections.Counter((c, k) for (t, c, s), k in infra)
    print(f'   infrastructure failures {len(infra)}: ' + ('; '.join(f'{c} {k}: {v}' for (c, k), v in sorted(kinds.items())) or 'none'))
    for (t, c, s), k in infra:
        print(f'      {c} seed {s} {t}: {k}')
    keys = sorted((t, s) for (t, c, s) in rows if c == 'N' and (t, 'NAF', s) in rows)
    entered = [(t, s) for t, s in keys if not rows[(t, 'N', s)]['infra'] and not rows[(t, 'NAF', s)]['infra']]
    one_side = sorted({(t, c, s) for (t, c, s) in rows if (t, 'NAF' if c == 'N' else 'N', s) not in rows})
    tasks = sorted({t for t, _s in entered})
    gold_keys = [(t, s) for t, s in entered if rows[(t, 'N', s)]['gold']]
    print(f'   pairs with a task result in both conditions {len(keys)}; ENTER the paired analysis {len(entered)} '
          f'({len(tasks)} tasks; ' + ', '.join(f'seed {s}: {sum(1 for _t, s2 in entered if s2 == s)}' for s in seeds) + ')')
    print(f'   runs whose other condition has no task result {len(one_side)}' + (': ' + ', '.join(f'{t} {c} seed {s}' for t, c, s in one_side[:20]) if one_side else ''))
    no_gold = sorted({t for t, s in entered if not rows[(t, 'N', s)]['gold']})
    print(f'   entered pairs with a GOLD FILE {len(gold_keys)} ({len({t for t, _s in gold_keys})} tasks); tasks with no GOLD '
          f'FILE (left out of the line-level outcomes only): {", ".join(no_gold) or "none"}')
    exploratory = len(tasks) < MIN_TASKS
    if exploratory:
        print(f'   fewer than {MIN_TASKS} tasks enter: EVERYTHING BELOW IS EXPLORATORY')

    print()
    print('2. Rules (NAF minus N, paired by task and seed; 95% bootstrap clustered by task, 2,000 resamples, seed 0)')
    rules = (('T1', 'resolved', entered, lambda x: x['resolved'], ('more tasks solved', 'fewer tasks solved', 'no detectable difference')),
             ('T2', f't_shown <= {T2_K}', gold_keys, lambda x: x['t'] <= T2_K, ('sooner', None, 'not detected')),
             ('T3', 'patch_overlaps', gold_keys, lambda x: x['patch_region'],
              ('the final patch reaches the fix more often', 'the final patch reaches the fix less often', 'no detectable difference')))
    for name, what, ks, fn, words in rules:
        a, b = paired(rows, ks, fn)
        d = diff_ci(a, b)
        na, nb = sum(map(sum, a.values())), sum(map(sum, b.values()))
        print(f'   {name} {what}: {dpts(d)}; NAF {pct(na, len(ks))}, N {pct(nb, len(ks))}; {len({t for t, _s in ks})} tasks')
        if d[0] is None:
            verdict = 'no pairs: no estimate'
        elif d[1] > 0:
            verdict = words[0]
        elif words[1] and d[2] < 0:
            verdict = words[1]
        else:
            verdict = words[2]
        print(f'      verdict: {verdict}' + (' (EXPLORATORY: fewer than 60 tasks)' if exploratory else ''))

    print()
    print('3. No rule: reported (entered pairs; line-level outcomes on pairs with a GOLD FILE)')
    for cond in CONDITIONS:
        sel = [rows[(t, cond, s)] for t, s in entered]
        gsel = [rows[(t, cond, s)] for t, s in gold_keys]

        def by(xs, fn):
            out = collections.defaultdict(list)
            for x in xs:
                out[x['task']].append(fn(x))
            return out

        print(f'   {cond}: runs {len(sel)}; resolved {rate(boot_ci(by(sel, lambda x: int(x["resolved"]))))} '
              f'({sum(x["resolved"] for x in sel)}); tool calls per run {rate_mean(boot_ci(by(sel, lambda x: x["n"])))}, '
              f'harness count {fmt_mean([x["n_harness"] for x in sel])}')
        for lab, fn in (('ever shown a changed line', lambda x: int(x['t'] < INF)), (f't_shown <= {T2_K}', lambda x: int(x['t'] <= T2_K)),
                        ('EVERY REGION SHOWN', lambda x: int(x['every'])), ('FINAL PATCH not empty', lambda x: int(x['patch'])),
                        ('FINAL PATCH TOUCHES A GOLD FILE', lambda x: int(x['patch_file'])),
                        ('FINAL PATCH OVERLAPS A CHANGED REGION', lambda x: int(x['patch_region']))):
            print(f'      {lab}: {rate(boot_ci(by(gsel, fn)))} ({sum(map(fn, gsel))} of {len(gsel)})')
        print('      shown a changed line within k calls: ' + ', '.join(f'{k}: {pct(sum(x["t"] <= k for x in gsel), len(gsel))}' for k in KS)
              + f'; never: {pct(sum(x["t"] == INF for x in gsel), len(gsel))}')
        c = ceiling_ci(gsel)
        print(f'      CEILING {100 * c[0]:+.1f} points [{100 * c[1]:+.1f}, {100 * c[2]:+.1f}]')

    both = collections.defaultdict(list)
    for t, s in gold_keys:
        x, y = rows[(t, 'NAF', s)]['t'], rows[(t, 'N', s)]['t']
        if x < INF and y < INF:
            both[t].append(x - y)
    m = boot_mean(both)
    flat = [v for vs in both.values() for v in vs]
    print(f'   CALL INDEX when first shown, NAF minus N, pairs where both were shown ({len(flat)} pairs, {len(both)} tasks): '
          + ('n/a' if m[0] is None else f'{m[0]:+.2f} calls [{m[1]:+.2f}, {m[2]:+.2f}], median {statistics.median(flat):+.1f}'))
    cells = collections.Counter((rows[(t, 'N', s)]['resolved'], rows[(t, 'NAF', s)]['resolved']) for t, s in entered)
    b, cc = cells[(True, False)], cells[(False, True)]
    print(f'   McNemar, resolved (rows N, columns NAF): both {cells[(True, True)]}, N only {b}, NAF only {cc}, neither '
          f'{cells[(False, False)]}; exact two-sided p {mcnemar_p(b, cc):.3f} (pairs of the same task across seeds are '
          f'not independent; the rule uses the clustered interval)')
    repos = collections.defaultdict(lambda: {c: [0, 0] for c in CONDITIONS})
    for t, s in entered:
        for cond in CONDITIONS:
            x = rows[(t, cond, s)]
            repos[x['repo']][cond][0] += x['resolved']
            repos[x['repo']][cond][1] += 1
    print('   resolved by repository: ' + '; '.join(f'{r}: N {v["N"][0]}/{v["N"][1]}, NAF {v["NAF"][0]}/{v["NAF"][1]}'
                                                  for r, v in sorted(repos.items())))
    print('   endings (entered runs):')
    for cond in CONDITIONS:
        e = collections.Counter(rows[(t, cond, s)]['ended'] for t, s in entered)
        print(f'      {cond}: ' + '; '.join(f'{k} {v}' for k, v in e.most_common()))
    print('   reads (entered runs; RANGED = a line bound under any spelling; mangled = the name is start_line or end_line')
    print('   once quotes, backslashes and spaces are removed, and is not exactly that, as the model wrote it):')
    for cond in CONDITIONS:
        rc = collections.Counter()
        for t, s in entered:
            rc.update(rows[(t, cond, s)]['reads'])
        print(f'      {cond}: executed read_file {rc["reads"]}; ranged {rc["ranged"]}; of these mangled {pct(rc["mangled"], rc["ranged"])}; '
              f'mangled reads with an asked start that ran ok {rc["mangled with a start, ok"]}, the returned range starts '
              f'at the asked start {rc["mangled start honored"]}')
    print('   graph tools (entered runs):')
    for cond in CONDITIONS:
        gc = collections.Counter()
        used = 0
        for t, s in entered:
            x = rows[(t, cond, s)]
            gc.update(x['graph'])
            used += bool(x['graph'])
        print(f'      {cond}: runs with a graph-tool call {pct(used, len(entered))}; calls ' +
              (', '.join(f'{k} {gc[k]}' for k in GRAPH_TOOLS)))
    print('   interface failures seen in the traces and task results (entered runs; runs with at least one, calls):')
    for cond in CONDITIONS:
        ic, ir = collections.Counter(), collections.Counter()
        for t, s in entered:
            x = rows[(t, cond, s)]['interface']
            ic.update(x)
            ir.update(set(x))
        print(f'      {cond}: ' + ('; '.join(f'{k}: {ir[k]} runs, {v}' for k, v in ic.most_common()) or 'none'))
    return entered, gold_keys


def rate_mean(t):
    return 'n/a' if t[0] is None else f'{t[0]:.1f} [{t[1]:.1f}, {t[2]:.1f}]'


def fmt_mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return f'{statistics.mean(vals):.1f}' if vals else 'n/a'


def extra_report(runs, entered):
    """What the runner's extra.jsonl says, by condition (entered runs). Changes no outcome."""
    have = any(e for (_t, _c, _s), (_tr, _r, _p, e) in runs.items())
    print()
    print("4. The runner's per-task record (extra.jsonl)")
    if not have:
        print('   none found')
        return
    keep = {(t, c, s) for t, s in entered for c in CONDITIONS}
    for cond in CONDITIONS:
        stats = collections.defaultdict(collections.Counter)
        rows = [e for k, (_tr, _r, _p, e) in runs.items() if k in keep and k[1] == cond and e]
        for e in rows:
            for k, v in e.items():
                if k in ('task', 'instance_id'):
                    continue
                if isinstance(v, bool):
                    stats[k]['true'] += v
                elif isinstance(v, (int, float)):
                    stats[k]['sum'] += v
                    stats[k]['nonzero'] += bool(v)
                elif isinstance(v, str):
                    stats[k][f'"{v[:40]}"'] += 1
                elif isinstance(v, (list, dict)):
                    stats[k]['non-empty'] += bool(v)
                    if isinstance(v, dict):
                        for k2, v2 in v.items():
                            if isinstance(v2, (int, float, bool)):
                                stats[f'{k}.{k2}']['sum'] += v2
                else:
                    stats[k]['null'] += 1
        print(f'   {cond}: {len(rows)} rows')
        for k in sorted(stats):
            print(f'      {k}: ' + ', '.join(f'{a} {round(b, 3)}' for a, b in stats[k].most_common(6)))


def standin_check(rows):
    """The quantities public_runs_time_to_fix.py also computes, on its population: every pair of (notebook, task)
    with both arms and a GOLD FILE, no exclusion for infrastructure."""
    keys = sorted((t, s) for (t, c, s) in rows if c == 'N' and (t, 'NAF', s) in rows and rows[(t, 'N', s)]['gold'])
    allr = [rows[(t, c, s)] for t, s in keys for c in CONDITIONS]
    failed = [x for x in allr if not x['resolved']]
    both = collections.defaultdict(list)
    for t, s in keys:
        x, y = rows[(t, 'NAF', s)]['t'], rows[(t, 'N', s)]['t']
        if x < INF and y < INF:
            both[t].append(x - y)
    got = {'pairs with both arms and a GOLD FILE': len(keys)}
    for cond in CONDITIONS:
        sel = [rows[(t, cond, s)] for t, s in keys]
        got[f'{cond} shown within 5 calls'] = sum(x['t'] <= 5 for x in sel)
        got[f'{cond} resolved'] = sum(x['resolved'] for x in sel)
        got[f'{cond} ever shown a changed line'] = sum(x['t'] < INF for x in sel)
        got[f'{cond} tool calls per run'] = round(statistics.mean(x['n'] for x in sel), 1)
    got['EVERY REGION SHOWN (both arms, of 630)'] = sum(x['every'] for x in allr)
    got['runs not resolved (both arms)'] = len(failed)
    got['of these, FINAL PATCH OVERLAPS A CHANGED REGION'] = sum(x['patch_region'] for x in failed)
    c = ceiling_ci(allr)
    got['CEILING, both arms (points)'] = round(100 * c[0], 1)
    got['CALL INDEX when first shown, NAF minus N, pairs both shown'] = sum(map(len, both.values()))
    m = boot_mean(both)
    print()
    print('5. Stand-in check against analysis/results/public/time_to_fix.txt (its population: all pairs with both arms')
    print('   and a GOLD FILE, no exclusion for infrastructure; N = base, NAF = skill)')
    for k, v in STORED.items():
        print(f'   {k:<62} stored {v:<7} here {got[k]:<7} {"same" if got[k] == v else "DIFFERS"}')
    print(f'   (beside: CEILING interval here [{100 * c[1]:+.1f}, {100 * c[2]:+.1f}], stored [+1.0, +5.3]; CALL INDEX '
          f'difference here {m[0]:+.2f} [{m[1]:+.2f}, {m[2]:+.2f}], stored -1.95 [-2.72, -1.16])')
    differs = [(t, s) for t, s in keys if rows[(t, 'N', s)]['infra'] or rows[(t, 'NAF', s)]['infra']]
    print(f'   pairs of this population that the rules of pre-registration 14 leave out as infrastructure failures: {len(differs)} '
          + ', '.join(f'{t} notebook {s}' for t, s in differs))


def write_csv(rows, entered, path):
    keep = set(entered)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['task', 'condition', 'seed', 'repo', 'entered', 'infrastructure', 'has_gold_file', 'resolved',
                    't_shown', f'shown_within_{T2_K}', 'every_region', 'patch_nonempty', 'patch_gold_file',
                    'patch_overlaps', 'tool_calls', 'harness_tool_calls', 'ended', 'reads', 'ranged_reads',
                    'mangled_reads', 'graph_calls'])
        for (t, c, s), x in sorted(rows.items()):
            w.writerow([t, c, s, x['repo'], int((t, s) in keep), x['infra'] or '', int(x['gold']), int(x['resolved']),
                        'inf' if x['t'] == INF else x['t'], int(x['t'] <= T2_K), int(x['every']), int(x['patch']),
                        int(x['patch_file']), int(x['patch_region']), x['n'], x['n_harness'], x['ended'],
                        x['reads']['reads'], x['reads']['ranged'], x['reads']['mangled'], sum(x['graph'].values())])
    print(f'\nper-run table written: {path} ({len(rows)} rows)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?')
    ap.add_argument('--standin-graphloc', action='store_true')
    ap.add_argument('--csv', action='store_true', help='write <root>/runs_14.csv')
    ap.add_argument('--csv-out', help='write the per-run table here instead')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if args.standin_graphloc:
        runs, notes = load_graphloc()
        label = 'STAND-IN: GraphLoc public runs, N = base, NAF = skill, seed = notebook'
    elif args.root:
        root = Path(args.root)
        runs, notes = load_root(root)
        label = str(root.name)
    else:
        ap.error('give <root> or --standin-graphloc')
    gold = gold_regions()
    tasks_repo = {t['instance_id']: t.get('repo', '') for t in jsonl(DATA / 'tasks.jsonl')}
    rows = {}
    for (task, cond, seed), (trace, result, patch, _extra) in sorted(runs.items()):
        x = score_run(task, trace, result, patch, gold)
        x['repo'] = tasks_repo.get(task) or x['repo']
        rows[(task, cond, seed)] = x
    print('0. Inputs')
    for n in notes:
        print(f'   {n}')
    print()
    entered, _gold_keys = report(rows, label)
    extra_report(runs, entered)
    if args.standin_graphloc:
        standin_check(rows)
    out = args.csv_out or (str(Path(args.root) / 'runs_14.csv') if args.csv and args.root else None)
    if out:
        write_csv(rows, entered, out)
    elif args.csv:
        print('\n--csv in the stand-in mode needs --csv-out: nothing written')


if __name__ == '__main__':
    main()
