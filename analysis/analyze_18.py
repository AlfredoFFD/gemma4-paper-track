"""Experiment 18, the registered analysis: whole runs told every place the fix changes, as names (ON) or addresses (OA).

Usage:
  py -I -X utf8 analysis/analyze_18.py [--no-write]
  py -I -X utf8 analysis/analyze_18.py --standin        (stored runs of 14 stand in for the three arms: NAF as N and as
                                                          OA, N as ON; prints only, writes nothing)

Inputs: the runs of 18 (analysis/results/18/{N,ON,OA}/seed2: one launch, seed 2, the three sessions of a task side by
side; N is the harness as shipped without a note, the control) on the 40 tasks of analysis/oracle_18/tasks_18.txt.
The stored seed-1 runs of 14 (analysis/results/14/{N,NAF}/seed1) on the same tasks are printed for description only,
as N14 and NAF14: they are other launches (the 40 tasks were selected on N14), and no rule uses them.
Every per-run outcome is that of analysis/analyze_14.py (its functions are imported: score_run, load_root,
every_region, patch_outcomes, mcnemar_p, and the bootstrap of 14, analyze_forks.diff_ci), plus one new one:
  PATCH TOUCHES EVERY CHANGED REGION   every changed region of every modified file of the reference patch is
                                       overlapped by a region of the agent's final patch (pre-patch line numbers on
                                       both sides, as analyze_14.patch_outcomes reads them); an empty patch is false.
A run ENTERS if it has a task result that is not an infrastructure failure (the rules of 14). Each rule is computed on
the tasks where both runs of its pair entered; it gets a verdict only if at least 34 such tasks exist, otherwise it
prints the numbers and "no verdict (too few tasks)". Paired by task, 95% bootstrap by task (2,000 resamples, seed 0);
verdict "more" if the interval lies above zero, "fewer" if below, else "no detectable difference"; the exact
two-sided McNemar p is printed beside. Every rule compares runs of the same launch and seed (18, seed 2):
  U1  resolved, OA against N
  U2  resolved, OA against ON
  U3  EVERY REGION SHOWN (reads), OA against N, and OA against ON
  U4  resolved, ON against N
Descriptive, no rule: per arm (N, ON, OA of 18; N14 and NAF14, other launches) shown a changed line, every region
shown, patch touches every changed region, resolved; how runs ended; tool calls (median); mangled reads; by
repository; the 2x2 of resolved in OA by resolved in ON.
Output: analysis/results/18/analyze_18.txt and analysis/results/18/runs_18.csv (--no-write: print only).
"""
import argparse
import collections
import contextlib
import csv
import io
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_14 as A  # noqa: E402
from make_population_k import parse_patch  # noqa: E402
from public_runs_address import DATA, norm  # noqa: E402
from public_runs_time_to_fix import INF, gold_regions, jsonl  # noqa: E402

ROOT_14 = HERE / 'results' / '14'
ROOT_18 = HERE / 'results' / '18'
TASKS_18 = HERE / 'oracle_18' / 'tasks_18.txt'
ARMS = ('N', 'ON', 'OA')            # experiment 18, one launch, seed 2: the rules
OTHER = ('N14', 'NAF14')            # the stored seed-1 runs of 14: description only
ALL = ARMS + OTHER
MIN_TASKS = 34
SEED_18, SEED_14 = 2, 1


def touches_every_region(patch, g):
    """PATCH TOUCHES EVERY CHANGED REGION."""
    if not g or not patch.strip():
        return False
    try:
        af = {norm(k): v['regions'] for k, v in parse_patch(patch).items()}
    except Exception:
        return False
    return all(any(not (d < a or c > b) for c, d in af.get(f, [])) for f in g for a, b in g[f])


def load(root, conditions):
    """analyze_14.load_root on a root whose condition folders are `conditions`."""
    saved = A.CONDITIONS
    A.CONDITIONS = tuple(conditions)
    try:
        return A.load_root(root)
    finally:
        A.CONDITIONS = saved


def collect(standin):
    """{(task, arm): (trace, task result, patch, extra)} for the arms of ALL, and notes about the inputs."""
    r14, n14 = load(ROOT_14, ('N', 'NAF'))
    runs = {(t, c + '14'): v for (t, c, s), v in r14.items() if s == SEED_14}
    notes = [f'14 (other launches, seed {SEED_14}): {n}' for n in n14]
    if standin:
        for (t, c), v in list(runs.items()):
            if c == 'NAF14':
                runs[(t, 'N')] = runs[(t, 'OA')] = v
            elif c == 'N14':
                runs[(t, 'ON')] = v
        notes.append('STAND-IN: N and OA are the stored NAF run of 14, ON the stored N run of 14')
    else:
        r18, n18 = load(ROOT_18, ARMS)
        runs.update({(t, c): v for (t, c, s), v in r18.items() if s == SEED_18})
        notes += [f'18 (seed {SEED_18}): {n}' for n in n18]
        other = sorted({s for (_t, _c, s) in r18} - {SEED_18})
        if other:
            notes.append(f'18: runs with another seed {other} are ignored')
    return runs, notes


def score(runs, tasks):
    gold = gold_regions()
    repo = {t['instance_id']: t.get('repo', '') for t in jsonl(DATA / 'tasks.jsonl')}
    rows = {}
    for (task, arm), (trace, result, patch, extra) in sorted(runs.items()):
        if task not in tasks or arm not in ALL:
            continue
        x = A.score_run(task, trace, result, patch, gold)
        x['repo'] = repo.get(task) or x['repo']
        x['touch_all'] = touches_every_region(patch, gold.get(task, {}))
        x['entered'] = x['infra'] is None
        x['extra'] = extra
        rows[(task, arm)] = x
    return rows


def rule(rows, tasks, name, what, a, b, fn):
    keys = [t for t in tasks if (t, a) in rows and (t, b) in rows and rows[(t, a)]['entered'] and rows[(t, b)]['entered']]
    xa = {t: [int(fn(rows[(t, a)]))] for t in keys}
    xb = {t: [int(fn(rows[(t, b)]))] for t in keys}
    d = A.diff_ci(xa, xb)
    na, nb = sum(v[0] for v in xa.values()), sum(v[0] for v in xb.values())
    disc_a = sum(1 for t in keys if xa[t][0] and not xb[t][0])
    disc_b = sum(1 for t in keys if xb[t][0] and not xa[t][0])
    p = A.mcnemar_p(disc_a, disc_b)
    print(f'   {name} {what}, {a} against {b}: {A.dpts(d)}; {a} {A.pct(na, len(keys))}, {b} {A.pct(nb, len(keys))}; '
          f'{len(keys)} tasks; {a} only {disc_a}, {b} only {disc_b}, exact McNemar p {p:.4f}')
    if len(keys) < MIN_TASKS:
        verdict = 'no verdict (too few tasks)'
    elif d[0] is None:
        verdict = 'no pairs: no estimate'
    elif d[1] > 0:
        verdict = 'more'
    elif d[2] < 0:
        verdict = 'fewer'
    else:
        verdict = 'no detectable difference'
    print(f'      verdict: {verdict}')
    return verdict


def report(rows, tasks, notes, label):
    print(f'EXPERIMENT 18: whole runs told every place the fix changes ({label})')
    print()
    print('0. Inputs')
    for n in notes:
        print(f'   {n}')
    print(f'   tasks of tasks_18.txt: {len(tasks)}')
    print()
    print(f'1. Runs per arm on the 40 tasks (N, ON, OA: experiment 18, seed {SEED_18}; N14, NAF14: other launches, '
          f'seed {SEED_14}, description only)')
    for c in ALL:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows]
        infra = [(x['task'], x['infra']) for x in sel if x['infra']]
        print(f'   {c:<5} runs {len(sel)}; entered {sum(x["entered"] for x in sel)}; without a trace '
              f'{sum(not x["trace"] for x in sel)}; infrastructure failures {len(infra)}'
              + (': ' + '; '.join(f'{t} {k}' for t, k in infra) if infra else ''))
    for c in ALL:
        m = [t for t in tasks if (t, c) not in rows]
        if m:
            print(f'   {c}: no task result for {len(m)} tasks: {", ".join(m)}')
    print()
    print(f'2. Rules (runs of 18, seed {SEED_18}; paired by task; 95% bootstrap by task, 2,000 resamples, seed 0; a '
          f'verdict needs at least {MIN_TASKS} tasks)')
    verdicts = {
        'U1': rule(rows, tasks, 'U1', 'resolved', 'OA', 'N', lambda x: x['resolved']),
        'U2': rule(rows, tasks, 'U2', 'resolved', 'OA', 'ON', lambda x: x['resolved']),
        'U3a': rule(rows, tasks, 'U3', 'EVERY REGION SHOWN', 'OA', 'N', lambda x: x['every']),
        'U3b': rule(rows, tasks, 'U3', 'EVERY REGION SHOWN', 'OA', 'ON', lambda x: x['every']),
        'U4': rule(rows, tasks, 'U4', 'resolved', 'ON', 'N', lambda x: x['resolved']),
    }
    print()
    print('3. No rule: reported (entered runs of each arm; N14 and NAF14 are other launches, seed 1, description only)')
    for c in ALL:
        sel = [rows[(t, c)] for t in tasks if (t, c) in rows and rows[(t, c)]['entered']]
        if not sel:
            print(f'   {c}: no entered runs')
            continue
        rc = collections.Counter()
        for x in sel:
            rc.update(x['reads'])
        print(f'   {c}: runs {len(sel)}; shown a changed line {A.pct(sum(x["t"] < INF for x in sel), len(sel))}; '
              f'every region shown {A.pct(sum(x["every"] for x in sel), len(sel))}; patch touches every changed region '
              f'{A.pct(sum(x["touch_all"] for x in sel), len(sel))}; patch overlaps a changed region '
              f'{A.pct(sum(x["patch_region"] for x in sel), len(sel))}; resolved {A.pct(sum(x["resolved"] for x in sel), len(sel))}')
        print(f'      tool calls median {statistics.median(x["n"] for x in sel)}; executed reads {rc["reads"]}, ranged '
              f'{rc["ranged"]}, mangled {A.pct(rc["mangled"], rc["ranged"])}')
        e = collections.Counter(x['ended'] for x in sel)
        print('      ended: ' + '; '.join(f'{k} {v}' for k, v in e.most_common()))
    repos = collections.defaultdict(lambda: {c: [0, 0] for c in ALL})
    for t in tasks:
        for c in ALL:
            x = rows.get((t, c))
            if x and x['entered']:
                repos[x['repo']][c][0] += x['resolved']
                repos[x['repo']][c][1] += 1
    print('   resolved by repository: ' + '; '.join(
        f'{r}: ' + ', '.join(f'{c} {v[c][0]}/{v[c][1]}' for c in ALL) for r, v in sorted(repos.items())))
    both = [t for t in tasks if all((t, c) in rows and rows[(t, c)]['entered'] for c in ('ON', 'OA'))]
    cells = collections.Counter((rows[(t, 'OA')]['resolved'], rows[(t, 'ON')]['resolved']) for t in both)
    print(f'   resolved, OA (rows) by ON (columns), {len(both)} tasks: OA yes ON yes {cells[(True, True)]}, OA yes ON no '
          f'{cells[(True, False)]}, OA no ON yes {cells[(False, True)]}, OA no ON no {cells[(False, False)]}')
    for c in ARMS:
        ex = [rows[(t, c)]['extra'] for t in tasks if (t, c) in rows and rows[(t, c)]['extra']]
        if ex:
            want = 0 if c == 'N' else 1
            print(f'   {c} extra.jsonl: rows {len(ex)}; note in the first user message {want} time(s), as expected, in '
                  f'{sum(e.get("note_in_first_message", 0) == want for e in ex)}; arm recorded as {c} '
                  f'{sum(e.get("arm") == c for e in ex)}; seeds {sorted({e.get("seed") for e in ex})}')
    return verdicts


def write_csv(rows, tasks, path):
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['task', 'arm', 'launch', 'seed', 'repo', 'entered', 'infrastructure', 'resolved', 't_shown',
                    'every_region', 'patch_touches_every_region', 'patch_nonempty', 'patch_gold_file', 'patch_overlaps',
                    'tool_calls', 'harness_tool_calls', 'ended', 'reads', 'ranged_reads', 'mangled_reads', 'graph_calls'])
        for t in tasks:
            for c in ALL:
                x = rows.get((t, c))
                if x is None:
                    continue
                w.writerow([t, c, '18' if c in ARMS else '14 (description only)', SEED_18 if c in ARMS else SEED_14,
                            x['repo'], int(x['entered']), x['infra'] or '', int(x['resolved']),
                            'inf' if x['t'] == INF else x['t'], int(x['every']), int(x['touch_all']), int(x['patch']),
                            int(x['patch_file']), int(x['patch_region']), x['n'], x['n_harness'], x['ended'],
                            x['reads']['reads'], x['reads']['ranged'], x['reads']['mangled'], sum(x['graph'].values())])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--standin', action='store_true')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = [line.strip() for line in open(TASKS_18, encoding='utf-8') if line.strip()]
    assert len(tasks) == 40 and len(set(tasks)) == 40, len(tasks)
    write = not (args.no_write or args.standin)
    if not args.standin and not all((ROOT_18 / c / f'seed{SEED_18}').is_dir() for c in ARMS):
        sys.exit(f'no stored runs of every arm under {ROOT_18}: run analysis/store_18.py first (or use --standin)')
    runs, notes = collect(args.standin)
    rows = score(runs, set(tasks))
    label = ('STAND-IN: N = OA = stored NAF of 14, ON = stored N of 14' if args.standin
             else f'N, ON and OA of 18, one launch, seed {SEED_18}')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report(rows, tasks, notes, label)
    text = buf.getvalue()
    print(text, end='')
    if write:
        (ROOT_18 / 'analyze_18.txt').write_text(text, encoding='utf-8', newline='\n')
        write_csv(rows, tasks, ROOT_18 / 'runs_18.csv')
        print(f'\nwritten: {ROOT_18 / "analyze_18.txt"}, {ROOT_18 / "runs_18.csv"}')


if __name__ == '__main__':
    main()
