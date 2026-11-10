"""Whole runs in public data: when the agent is first shown a line the fix changes, and what follows (EXPLORATORY).

Usage: py -I -X utf8 analysis/public_runs_time_to_fix.py

Nothing here was pre-registered and no model is run. The script reads other teams' public runs of Gemma 4 agents on
this benchmark and the gold patches of data/tasks.jsonl. Its main part is a public experiment: the end-to-end
notebooks of the GraphLoc writeup ran the starter agent on the same tasks with and without a skill that prints
graph-ranked candidates as `<path>:<line> <name>` (three notebooks, arms `base` and `skill`). That writeup reports
the resolve rate. Here each run is scored by when the agent was first shown a line the gold patch changes.

Sources (local copies, not redistributed; see analysis/results/public/README.md):
  data/graphloc/out/<notebook>/e2e/results/<arm>/w*/traces/trace_<task>.json   traces of both arms
  data/graphloc/out/<notebook>/e2e/records/rec_w*.jsonl                        per run: resolved, the agent's patch
  data/public_traces/vanductan__gemma4-patchpool/                              a custom agent, 31B, 12B and E4B
  data/public_traces/niraberman__gemma4-commit-anatomy-traces/                 another custom agent, 31B
  data/public_traces/petermugoya__what-the-agent-saw/data/main*_{episodes,reads}.jsonl
      per-run and per-read tables of 1,329 runs of the starter agent. A row of the read table is a read_file call or
      a shell viewer with the file and the lines the model ASKED for; a read whose bound sat under a mangled name
      returned lines 1 to 150 instead, so the line-level count from these tables is an upper bound.

Rules:
  CHANGED REGION   the old-file line span of each hunk of the gold patch in a file the patch modifies
                   (analysis/make_population_k.parse_patch; files the patch creates are left out).
  GOLD FILE        a file with at least one CHANGED REGION. Runs of tasks with no GOLD FILE are left out.
  CALL INDEX       the position of a tool call in the run, from 1, counting every tool call.
  SHOWN A CHANGED LINE at call i: a read_file call with status ok on a GOLD FILE whose returned
                   start_line..end_line overlaps a CHANGED REGION; or (GraphLoc traces) a run_command with output
                   that the frozen scorer treats as a view of that one file over lines that overlap a CHANGED REGION
                   (fork_states.touches with a name that never matches, as analysis/analyze_k.py uses it).
  SHOWN OR MATCHED (wider, reported apart): as above, or a run_command whose output holds a numbered line inside a
                   CHANGED REGION: `<path>:<n>:` or `<path>-<n>-` for a GOLD FILE, or a line that begins `<n>:` or
                   `<n>-` when the command names that file and no other .py file and is a grep -n, cat -n or nl.
  EVERY REGION SHOWN  every CHANGED REGION of every GOLD FILE is overlapped by the returned range of some read_file
                   call of the run (a stricter reading of having seen the fix; shell views are not counted).
  FINAL PATCH      the agent's patch in the run record, parsed like the gold patch. It TOUCHES A GOLD FILE if any
                   file in it is one; it OVERLAPS A CHANGED REGION if one of its own regions in a GOLD FILE does.
  LIST HAS THE FIX (skill arm): the first skill answer of the run lists a `<path>:<line>` in a GOLD FILE whose 150
                   lines from <line> overlap a CHANGED REGION.
  CEILING          (never-shown runs / runs) x (resolved rate of shown runs - resolved rate of never-shown runs):
                   what resolution would gain if every never-shown run resolved at the rate of the shown ones.
Pairs are (notebook, task). Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import collections
import csv
import io
import json
import random
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import SENTINEL, _single_file, _stdout  # noqa: E402
from fork_states import touches  # noqa: E402
from gates_c import _ll  # noqa: E402
from graphloc_traces import NOTEBOOKS, ROOT as GRAPHLOC, iter_runs, load  # noqa: E402
from make_population_k import parse_patch  # noqa: E402
from public_runs_address import (DATA, NUMBERED, PATHCH, SKILL_LINE, calls_of, is_read, norm,  # noqa: E402
                                 numbering_command, pct)

INF = float('inf')
PUBLIC = DATA / 'public_traces'
KS = (3, 5, 10, 20)


def overlap(a, b, regions):
    return any(not (b < s or a > e) for s, e in regions)


def jsonl(path):
    with io.open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def truth(v):
    return v is True or str(v).strip().lower() in ('true', '1', '1.0')


def gold_regions():
    out = {}
    for t in jsonl(DATA / 'tasks.jsonl'):
        files = parse_patch(t['patch'])
        out[t['instance_id']] = {norm(p): v['regions'] for p, v in files.items() if not v['created'] and v['regions']}
    return out


def graphloc_records():
    out = {}
    for nb, run in NOTEBOOKS.items():
        for p in sorted((GRAPHLOC / nb / 'e2e' / 'records').glob('rec_w*.jsonl')):
            for r in jsonl(p):
                out[(run, r.get('arm'), r.get('id'))] = (truth(r.get('resolved')), r.get('patch') or '')
    return out


def first_shown(calls, g, task=None, shell=False):
    """(first CALL INDEX shown by a read or a shell view, first under the wider rule, first read of a GOLD FILE)."""
    t_line = t_wide = t_file = INF
    for i, (call, _text, parsed) in enumerate(calls, 1):
        name = call.get('function_name')
        args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
        if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
            f = norm(parsed.get('filepath') or args.get('filepath'))
            if f in g:
                t_file = min(t_file, i)
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int) and overlap(s, e, g[f]):
                    t_line = min(t_line, i)
        elif shell and name == 'run_command' and isinstance(parsed, dict) and _stdout(parsed):
            cmd = str(args.get('command', ''))
            out = _stdout(parsed)
            for f, regions in g.items():
                if t_wide == INF:
                    nums = {int(m.group(1)) for m in re.finditer(
                        r'(?:(?<![' + PATHCH + r'])|(?<=/))' + re.escape(f) + r'[:\-](\d+)[:\-]', out)}
                    others = [t for t in re.findall(r'[' + PATHCH + r'/]+\.py', cmd) if norm(t) != f]
                    if f in cmd and not others and numbering_command(cmd):
                        nums |= {int(m.group(1)) for m in NUMBERED.finditer(out)}
                    if any(overlap(n, n, regions) for n in nums):
                        t_wide = i
                if t_line == INF and f in cmd and _single_file(cmd, f):
                    c2 = {'function_name': name, 'arguments': args}
                    ll = _ll(task, f)
                    if any(touches(c2, {'path': f, 'start': a, 'end': b}, SENTINEL, line_lengths=ll) == 'read' for a, b in regions):
                        t_line = i
    return t_line, min(t_wide, t_line), t_file


def share_line(label, runs):
    """One line for a set of runs: {'task', 't', 'resolved'}."""
    n = len(runs)
    by = collections.defaultdict(list)
    for r in runs:
        by[r['task']].append(int(r['t'] < INF))
    t = boot_ci(by)
    shown = [r for r in runs if r['t'] < INF]
    never = [r for r in runs if r['t'] == INF]
    failed = [r for r in runs if not r['resolved']]
    rs = sum(r['resolved'] for r in shown) / max(len(shown), 1)
    rn = sum(r['resolved'] for r in never) / max(len(never), 1)
    print(f'   {label}: runs {n}, tasks {len(by)}; shown a changed line {len(shown)} ({100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]); '
          f'of {len(failed)} runs not resolved {pct(sum(r["t"] < INF for r in failed), len(failed))}')
    print(f'      resolved: shown {pct(sum(r["resolved"] for r in shown), len(shown))}, never shown {pct(sum(r["resolved"] for r in never), len(never))}; '
          f'CEILING {100 * (len(never) / n) * (rs - rn):+.1f} points; shown within k calls: '
          + ', '.join(f'{k}: {100 * sum(r["t"] <= k for r in runs) / n:.1f}%' for k in KS))


def graphloc_part(gold):
    rec = graphloc_records()
    rows = {}
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill'):
            continue
        g = gold.get(r['task'], {})
        calls = calls_of(load(r['path']))
        t_line, t_wide, t_file = first_shown(calls, g, task=r['task'], shell=True)
        seen = collections.defaultdict(set)
        for call, _text, parsed in calls:
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if f in g and isinstance(s, int) and isinstance(e, int):
                    seen[f].update(i for i, (a, b) in enumerate(g[f]) if not (e < a or s > b))
        resolved, patch = rec.get((r['run'], r['arm'], r['task']), (False, ''))
        try:
            af = {norm(k): v for k, v in parse_patch(patch).items()} if patch.strip() else {}
        except Exception:
            af = {}
        x = {'task': r['task'], 'n': len(calls), 't': t_line, 'wide': t_wide, 'file': t_file, 'resolved': resolved,
             'patch': bool(patch.strip()), 'patch_file': any(f in g for f in af),
             'patch_region': any(f in g and any(overlap(a, b, g[f]) for a, b in v['regions']) for f, v in af.items()),
             'edit': INF, 'skill_at': None, 'arm': r['arm'], 'every': bool(g) and all(len(seen[f]) == len(g[f]) for f in g),
             'regions': sum(len(v) for v in g.values())}
        for i, (call, text, _p) in enumerate(calls, 1):
            name = call.get('function_name')
            args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
            if name in ('edit_file', 'write_file') and norm(args.get('filepath')) in g:
                x['edit'] = min(x['edit'], i)
            elif name == 'run_skill_script' and x['skill_at'] is None:
                listed = [(norm(m.group(1)), int(m.group(2))) for m in SKILL_LINE.finditer(text or '')]
                if listed:
                    x['skill_at'] = i
                    x['list_fix'] = any(f in g and overlap(ln, ln + 149, g[f]) for f, ln in listed)
                    x['list_file'] = any(f in g for f, _ in listed)
                    x['next_listed'] = x['next_fix'] = False
                    if i < len(calls):
                        nx, _t, npar = calls[i]
                        if is_read(nx) and isinstance(npar, dict) and npar.get('status') == 'ok':
                            nf = norm(npar.get('filepath') or nx['arguments'].get('filepath'))
                            ns, ne = npar.get('start_line'), npar.get('end_line')
                            if isinstance(ns, int) and isinstance(ne, int):
                                x['next_listed'] = any(f == nf and ns <= ln <= ne for f, ln in listed)
                                x['next_fix'] = nf in g and overlap(ns, ne, g[nf])
        rows[(r['run'], r['arm'], r['task'])] = x
    pairs = sorted({(run, task) for run, arm, task in rows if (run, 'base', task) in rows and (run, 'skill', task) in rows})
    kept = [(run, task) for run, task in pairs if gold.get(task)]
    print('1. A public experiment: the starter agent with and without a skill that prints `path:line name` (Gemma-4-31B, Sep)')
    print(f'   pairs with both arms {len(pairs)}; with a GOLD FILE {len(kept)} ({len({t for _, t in kept})} tasks)')
    for arm in ('base', 'skill'):
        sel = [rows[(run, arm, task)] for run, task in kept]
        fin = [x['t'] for x in sel if x['t'] < INF]
        print(f'   {arm}: runs {len(sel)}; resolved {pct(sum(x["resolved"] for x in sel), len(sel))}; tool calls per run {statistics.mean(x["n"] for x in sel):.1f}; '
              f'ever shown a changed line {pct(len(fin), len(sel))}, median CALL INDEX {statistics.median(fin):.0f}')
        print('      shown within k calls: ' + ', '.join(f'{k}: {pct(sum(x["t"] <= k for x in sel), len(sel))}' for k in KS))

    def diff(key, k):
        a, b = collections.defaultdict(list), collections.defaultdict(list)
        for run, task in kept:
            a[task].append(int(rows[(run, 'skill', task)][key] <= k))
            b[task].append(int(rows[(run, 'base', task)][key] <= k))
        d = diff_ci(a, b)
        return f'{100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]'

    print('   skill minus base, by task:')
    for k in KS:
        print(f'      shown a changed line within {k} calls {diff("t", k)}; SHOWN OR MATCHED {diff("wide", k)}')
    print(f'      read a GOLD FILE within 5 calls {diff("file", 5)}; edited one within 10 calls {diff("edit", 10)}')
    a, b = collections.defaultdict(list), collections.defaultdict(list)
    for run, task in kept:
        a[task].append(int(rows[(run, 'skill', task)]['resolved']))
        b[task].append(int(rows[(run, 'base', task)]['resolved']))
    d = diff_ci(a, b)
    print(f'      resolved {100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')
    both = collections.defaultdict(list)
    for run, task in kept:
        x, y = rows[(run, 'skill', task)]['t'], rows[(run, 'base', task)]['t']
        if x < INF and y < INF:
            both[task].append(x - y)
    flat = [v for vs in both.values() for v in vs]
    rng = random.Random(0)
    tasks = sorted(both)
    boots = sorted(statistics.mean([v for t in (rng.choice(tasks) for _ in tasks) for v in both[t]]) for _ in range(2000))
    print(f'      CALL INDEX when first shown, pairs where both arms were shown ({len(flat)} pairs, {len(tasks)} tasks): '
          f'{statistics.mean(flat):+.2f} calls [{boots[50]:+.2f}, {boots[1949]:+.2f}], median {statistics.median(flat):+.1f}')
    print()
    print('2. Inside the skill arm')
    sk = [rows[(run, 'skill', task)] for run, task in kept]
    used = [x for x in sk if x['skill_at'] is not None]
    print(f'   runs with a skill answer that lists candidates {pct(len(used), len(sk))}, the first at CALL INDEX (median) {statistics.median(x["skill_at"] for x in used):.0f}; '
          f'the list names a GOLD FILE {pct(sum(x["list_file"] for x in used), len(used))}; LIST HAS THE FIX {pct(sum(x["list_fix"] for x in used), len(used))}')
    for label, grp in (('LIST HAS THE FIX', [x for x in used if x['list_fix']]), ('the list does not', [x for x in used if not x['list_fix']])):
        n = len(grp)
        print(f'   {label} ({n} runs): next call reads a listed line {pct(sum(x["next_listed"] for x in grp), n)}; next call shows a changed line '
              f'{pct(sum(x["next_fix"] for x in grp), n)}; shown within 5 calls {pct(sum(x["t"] <= 5 for x in grp), n)}; resolved {pct(sum(x["resolved"] for x in grp), n)}')
    print()
    print('3. From seeing the lines to fixing them (both arms)')
    allr = [rows[(run, arm, task)] for run, task in kept for arm in ('base', 'skill')]
    n = len(allr)
    steps = (('shown a changed line', lambda x: x['t'] < INF), ('FINAL PATCH not empty', lambda x: x['patch']),
             ('TOUCHES A GOLD FILE', lambda x: x['patch_file']), ('OVERLAPS A CHANGED REGION', lambda x: x['patch_region']),
             ('resolved', lambda x: x['resolved']))
    print(f'   {n} runs: ' + '; '.join(f'{lab} {pct(sum(map(fn, allr)), n)}' for lab, fn in steps))
    shown = [x for x in allr if x['t'] < INF]
    miss = [x for x in shown if not x['patch_region']]

    def where(x):
        return 'no patch' if not x['patch'] else ('the gold file, elsewhere in it' if x['patch_file'] else 'other files only')

    kinds = collections.Counter(where(x) for x in miss)
    print(f'   of {len(shown)} runs shown a changed line: FINAL PATCH OVERLAPS A CHANGED REGION {pct(sum(x["patch_region"] for x in shown), len(shown))}, '
          f'of which resolved {pct(sum(x["resolved"] for x in shown if x["patch_region"]), sum(x["patch_region"] for x in shown))}')
    failed = [x for x in allr if not x['resolved']]
    print(f'   of {len(failed)} runs that did not resolve: shown a changed line {pct(sum(x["t"] < INF for x in failed), len(failed))}; '
          f'FINAL PATCH TOUCHES A GOLD FILE {pct(sum(x["patch_file"] for x in failed), len(failed))}; '
          f'OVERLAPS A CHANGED REGION {pct(sum(x["patch_region"] for x in failed), len(failed))}')
    print(f'   the other {len(miss)}: ' + '; '.join(f'{k} {v} (resolved {sum(x["resolved"] for x in miss if where(x) == k)})' for k, v in kinds.most_common()))
    by = collections.defaultdict(list)
    for x in allr:
        by[x['task']].append(int(x['every']))
    t = boot_ci(by)
    ev = [x for x in allr if x['every']]
    nev = [x for x in allr if not x['every']]
    print(f'   EVERY REGION SHOWN {len(ev)} of {n} ({100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]): base {sum(x["every"] for x in allr if x["arm"] == "base")}, '
          f'skill {sum(x["every"] for x in allr if x["arm"] == "skill")}; resolved when so {pct(sum(x["resolved"] for x in ev), len(ev))}, when not {pct(sum(x["resolved"] for x in nev), len(nev))}')
    print('   by the number of CHANGED REGIONS of the task: ' + '; '.join(
        f'{lab}: {len({x["task"] for x in grp})} tasks, shown a changed line {100 * sum(x["t"] < INF for x in grp) / len(grp):.1f}%, every region {100 * sum(x["every"] for x in grp) / len(grp):.1f}%, '
        f'resolved {100 * sum(x["resolved"] for x in grp) / len(grp):.1f}%' for lab, grp in (
            ('one', [x for x in allr if x['regions'] == 1]), ('two', [x for x in allr if x['regions'] == 2]),
            ('three or four', [x for x in allr if 3 <= x['regions'] <= 4]), ('five or more', [x for x in allr if x['regions'] >= 5]))))
    for key, label in ((lambda x: x['t'] < INF, 'shown a changed line'), (lambda x: x['every'], 'EVERY REGION SHOWN')):
        kinds2 = collections.defaultdict(lambda: {True: [], False: []})
        for x in allr:
            kinds2[x['task']][bool(key(x))].append(int(x['resolved']))
        mixed = [v for v in kinds2.values() if v[True] and v[False]]
        w = sum(min(len(v[True]), len(v[False])) for v in mixed)
        yes = sum(min(len(v[True]), len(v[False])) * statistics.mean(v[True]) for v in mixed) / w
        no = sum(min(len(v[True]), len(v[False])) * statistics.mean(v[False]) for v in mixed) / w
        print(f'   within task ({len(mixed)} tasks with runs of both kinds, each weighted by its smaller group): {label}: resolved {100 * yes:.1f}% against {100 * no:.1f}%')
    cells = collections.defaultdict(lambda: [0, 0, 0])
    for run, task in kept:
        bx, kx = rows[(run, 'base', task)], rows[(run, 'skill', task)]
        c = cells[(bx['t'] < INF, kx['t'] < INF)]
        c[0] += 1
        c[1] += int(bx['resolved'])
        c[2] += int(kx['resolved'])
    one = cells[(True, False)], cells[(False, True)]
    print(f'   pairs in which only one arm was shown a changed line: {one[0][0] + one[1][0]}; the arm that was shown resolved '
          f'{one[0][1] + one[1][2]}, the other {one[0][2] + one[1][1]}')
    print('   resolved by when a changed line was first shown: ' + '; '.join(
        f'{lab} {pct(sum(x["resolved"] for x in grp), len(grp))}' for lab, grp in (
            ('calls 1 to 3', [x for x in allr if x['t'] <= 3]), ('4 to 6', [x for x in allr if 4 <= x['t'] <= 6]),
            ('7 to 12', [x for x in allr if 7 <= x['t'] <= 12]), ('13 or later', [x for x in allr if 13 <= x['t'] < INF]),
            ('never', [x for x in allr if x['t'] == INF]))))

    def ceiling(sel):
        sh = [x for x in sel if x['t'] < INF]
        nv = [x for x in sel if x['t'] == INF]
        if not sel or not sh:
            return 0.0
        return (len(nv) / len(sel)) * (sum(x['resolved'] for x in sh) / len(sh) - (sum(x['resolved'] for x in nv) / len(nv) if nv else 0.0))

    by_task = collections.defaultdict(list)
    for x in allr:
        by_task[x['task']].append(x)
    tasks = sorted(by_task)
    rng = random.Random(0)
    boots = sorted(ceiling([x for t in (rng.choice(tasks) for _ in tasks) for x in by_task[t]]) for _ in range(2000))
    never_tasks = collections.Counter(x['task'] for x in allr if x['t'] == INF)
    print(f'   CEILING {100 * ceiling(allr):+.1f} points [{100 * boots[50]:+.1f}, {100 * boots[1949]:+.1f}]; the never-shown runs are in {len(never_tasks)} tasks, '
          f'{sum(1 for c in never_tasks.values() if c == 6)} of them never shown in any of their 6 runs')
    print()
    print('4. Runs shown a changed line by call k, for a figure (counts of ' + str(len(kept)) + ' runs per arm)')
    print('   k:     ' + ' '.join(f'{k:>3}' for k in range(1, 31)))
    for arm in ('base', 'skill'):
        sel = [rows[(run, arm, task)] for run, task in kept]
        print(f'   {arm + ":":<7}' + ' '.join(f'{sum(x["t"] <= k for x in sel):>3}' for k in range(1, 31)))
    print()
    print('5. The same share in other sources (first line of each: both arms of part 1)')
    share_line('starter agent, with and without the skill, Sep', allr)


def other_part(gold):
    van = PUBLIC / 'vanductan__gemma4-patchpool'
    res = {}
    with io.open(van / 'runs_long.csv', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            res[(r['run_tag'], r['instance_id'])] = truth(r['resolved'])
    nir = PUBLIC / 'niraberman__gemma4-commit-anatomy-traces'
    nres = {}
    for arena in ('arena_v25', 'arena_v26'):
        for r in jsonl(nir / arena / f'{arena}_summary.jsonl'):
            nres[(arena, r.get('bundle'), r['instance_id'])] = truth(r.get('resolved'))
    groups = (
        ('custom agent 1, Gemma-4-31B, Oct', sorted(van.glob('traces/31b_*/traces/trace_*.json')), lambda p: res.get((p.parts[-3], p.stem[6:]), False)),
        ('custom agent 2, Gemma-4-31B, Oct to Nov', sorted(nir.glob('arena_v2*/results_*/traces/trace_*.json')),
         lambda p: nres.get((p.parts[-4], p.parts[-3][len('results_'):], p.stem[6:]), False)),
        ('custom agent 1, Gemma-4-12B, Oct', sorted(van.glob('traces/12b_*/traces/trace_*.json')), lambda p: res.get((p.parts[-3], p.stem[6:]), False)),
        ('custom agent 1, Gemma 4 E4B, Oct', sorted(van.glob('traces/e4b_*/traces/trace_*.json')), lambda p: res.get((p.parts[-3], p.stem[6:]), False)),
    )
    for label, paths, resolved_of in groups:
        runs = []
        for p in paths:
            task = p.stem[len('trace_'):]
            g = gold.get(task, {})
            if g:
                t_line, _w, _f = first_shown(calls_of(json.load(io.open(p, encoding='utf-8'))), g)
                runs.append({'task': task, 't': t_line, 'resolved': resolved_of(p)})
        share_line(label, runs)
    w = PUBLIC / 'petermugoya__what-the-agent-saw' / 'data'
    for sess, note in (('main2', ''), ('main3', ''), ('main1', ', a session its authors call overloaded')):
        eps = {(e['cell'], e['instance_id']): e for e in jsonl(w / f'{sess}_episodes.jsonl')}
        line, anyfile = {}, {}
        for r in jsonl(w / f'{sess}_reads.jsonl'):
            g = gold.get(r['instance_id'], {})
            f = norm(r.get('file'))
            if f not in g:
                continue
            key = (r['cell'], r['instance_id'])
            anyfile[key] = min(anyfile.get(key, INF), r['call'] + 1)
            lo, hi = r.get('lo'), r.get('hi')
            if isinstance(lo, int) and isinstance(hi, int) and overlap(lo, hi, g[f]):
                line[key] = min(line.get(key, INF), r['call'] + 1)
        for label, table in ((f'starter agent, Oct, tables of session {sess}{note}: lines as asked', line),
                             (f'the same, file level (read a GOLD FILE)', anyfile)):
            share_line(label, [{'task': k[1], 't': table.get(k, INF), 'resolved': truth(e.get('resolved'))}
                               for k, e in eps.items() if gold.get(k[1])])


def main():
    gold = gold_regions()
    print('PUBLIC RUNS, WHOLE RUNS: when the agent is first shown a line the fix changes (EXPLORATORY)')
    print()
    graphloc_part(gold)
    other_part(gold)


if __name__ == '__main__':
    main()
