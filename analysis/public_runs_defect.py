"""Mangled line-bound names in other teams' public runs: how often, where, and what follows (EXPLORATORY).

Usage: py -I -X utf8 analysis/public_runs_defect.py

Nothing here was pre-registered and no model is run. The script reads public traces of Gemma 4 agents on this
benchmark (ATIF JSON, one file per run) and one team's public per-run tables, and prints counts.

Sources (local copies, not redistributed; see analysis/results/public/README.md):
  data/graphloc/out/.../traces/trace_<task>.json       GraphLoc's 636 traces (Sep 2026): the starter agent (`base`)
      and the same agent with a graph skill (`skill`). These runs predate the harness change of Sep 30 that turned
      tool results from JSON strings into dictionaries.
  data/public_traces/vanductan__gemma4-patchpool/...    a custom agent (Oct 2026): Gemma-4-31B, 12B and E4B.
  data/public_traces/niraberman__gemma4-commit-anatomy-traces/...   another custom agent (Oct to Nov 2026), 31B.
  data/public_traces/petermugoya__what-the-agent-saw/data/main*_episodes.jsonl, main*_reads.jsonl
      per-run tables of 1,329 runs of the starter agent (Oct 2 to 5, 2026). Their column `n_corrupted_arg_calls`
      counts, per run, the tool calls with an argument key that contains a double quote, a newline or a space
      (that dataset's code/behavior/extract_events.py); its public analysis plan notes such keys in one line.
      The tables hold no argument names, so position and what followed cannot be read from them.

Rules:
  BOUNDED READ    a `read_file` call with an argument whose name reads `start_line` or `end_line` once quotes,
                  backslashes and whitespace are removed from the name.
  MANGLED         a BOUNDED READ in which such a name is not a plain identifier (for example `start_line"`). The
                  agent framework keeps only arguments the tool declares, so the bound is dropped.
  WELL-FORMED     a BOUNDED READ that is not MANGLED.
  RETURNED FROM LINE 1   the read's own result reports start_line 1.
  JUST BEFORE     the tool call immediately before the read in the trace.
  READS THE SAME FILE AGAIN   the next tool call is a `read_file` on the same file.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analyze_forks.boot_ci, diff_ci).
"""
import collections
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from public_runs_address import BOUNDS, DATA, calls_of, clean, is_read, norm, pct  # noqa: E402


def bounded(call):
    return is_read(call) and any(clean(k) in BOUNDS for k in call['arguments'])


def mangled(call):
    return is_read(call) and any((not str(k).isidentifier()) and clean(k) in BOUNDS for k in call['arguments'])


def before_group(prev):
    if prev is None:
        return 'nothing (first call of the run)'
    if is_read(prev):
        if mangled(prev):
            return 'a mangled read'
        return 'a well-formed bounded read' if bounded(prev) else 'a read with no bound'
    return str(prev.get('function_name'))


def groups():
    g = DATA / 'graphloc' / 'out'
    p = DATA / 'public_traces'
    van = p / 'vanductan__gemma4-patchpool' / 'traces'
    nir = p / 'niraberman__gemma4-commit-anatomy-traces'
    return [
        ('starter agent (GraphLoc base arm), Sep', 'Gemma-4-31B', 'JSON strings', sorted(g.glob('*/e2e/results/base/w*/traces/trace_*.json'))),
        ('graph skill (GraphLoc skill arm), Sep', 'Gemma-4-31B', 'JSON strings', sorted(g.glob('*/e2e/results/skill/w*/traces/trace_*.json'))),
        ('custom agent 1, Oct', 'Gemma-4-31B', 'dictionaries', sorted(van.glob('31b_*/traces/trace_*.json'))),
        ('custom agent 2, Oct to Nov', 'Gemma-4-31B', 'dictionaries', sorted(nir.glob('arena_v2*/results_*/traces/trace_*.json'))),
        ('custom agent 1, Oct', 'Gemma-4-12B', 'dictionaries', sorted(van.glob('12b_*/traces/trace_*.json'))),
        ('custom agent 1, Oct', 'Gemma 4 E4B', 'dictionaries', sorted(van.glob('e4b_*/traces/trace_*.json'))),
    ]


def ci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} points [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def main():
    rows = []      # one per bounded read
    per = collections.defaultdict(collections.Counter)
    names = collections.defaultdict(collections.Counter)
    for label, model, rendering, paths in groups():
        key = (label, model)
        for path in paths:
            try:
                trace = json.load(io.open(path, encoding='utf-8'))
            except (ValueError, OSError):
                per[key]['unreadable'] += 1
                continue
            task = path.stem[len('trace_'):]
            calls = calls_of(trace)
            per[key]['traces'] += 1
            per[key]['tool calls'] += len(calls)
            per[key]['read_file calls'] += sum(1 for c, _t, _p in calls if is_read(c))
            seen_bounded = False
            any_mangled = False
            for i, (call, _text, parsed) in enumerate(calls):
                if not bounded(call):
                    continue
                m = mangled(call)
                any_mangled = any_mangled or m
                nxt = calls[i + 1][0] if i + 1 < len(calls) else None
                again = None
                if nxt is not None:
                    again = is_read(nxt) and norm(nxt['arguments'].get('filepath')) == norm(call['arguments'].get('filepath'))
                again_mangled = bool(again and mangled(nxt))
                from1 = isinstance(parsed, dict) and parsed.get('status') == 'ok' and parsed.get('start_line') == 1
                rows.append({'key': key, 'model': model, 'rendering': rendering, 'task': task, 'mangled': m,
                             'first': not seen_bounded, 'before': before_group(calls[i - 1][0] if i else None),
                             'again': again, 'again_mangled': again_mangled, 'from1': from1})
                seen_bounded = True
                if m:
                    for k in call['arguments']:
                        if (not str(k).isidentifier()) and clean(k) in BOUNDS:
                            names[rendering][k] += 1
            per[key]['runs with a mangled read'] += any_mangled

    print('PUBLIC RUNS: mangled line-bound names (EXPLORATORY)')
    print()
    print('1. By source and model: bounded reads, of which mangled; runs with at least one')
    for label, model, rendering, _ in groups():
        key = (label, model)
        sel = [r for r in rows if r['key'] == key]
        t = per[key]
        nm = sum(r['mangled'] for r in sel)
        print(f'   {label:<40} {model:<12} tool results as {rendering:<13} traces {t["traces"]:>3}  tool calls {t["tool calls"]:>5}  '
              f'mangled {pct(nm, len(sel)):<20} runs {pct(t["runs with a mangled read"], t["traces"])}')
        print(f'   {"":<40} {"":<12} per 100 tool calls {100 * nm / max(1, t["tool calls"]):.1f}; per 100 read_file calls '
              f'{100 * nm / max(1, t["read_file calls"]):.1f} ({t["read_file calls"]} read_file calls)')

    def pooled(title, test):
        sel = [r for r in rows if test(r)]
        if not sel:
            return
        by = collections.defaultdict(list)
        for r in sel:
            by[r['task']].append(int(r['mangled']))
        print()
        print(title)
        print(f'   bounded reads mangled: {pct(sum(r["mangled"] for r in sel), len(sel))}; by task {ci(boot_ci(by))}')
        mg = [r for r in sel if r['mangled']]
        print(f'   mangled reads that returned the file from line 1: {pct(sum(r["from1"] for r in mg), len(mg))}')
        for name, flag in (('first bounded read of the run', True), ('later bounded reads', False)):
            s2 = [r for r in sel if r['first'] == flag]
            print(f'   {name:<32} {pct(sum(r["mangled"] for r in s2), len(s2))}')
        print('   by the call just before:')
        counts = collections.Counter(r['before'] for r in sel)
        for g, n in counts.most_common():
            s2 = [r for r in sel if r['before'] == g]
            print(f'      after {g:<34} {pct(sum(r["mangled"] for r in s2), n)}')
        a = collections.defaultdict(list)
        b = collections.defaultdict(list)
        for r in sel:
            if r['again'] is None:
                continue
            (a if r['mangled'] else b)[r['task']].append(int(r['again']))
        na, nb = sum(map(len, a.values())), sum(map(len, b.values()))
        print(f'   the next call reads the same file again: after a mangled read {pct(sum(map(sum, a.values())), na)}; '
              f'after a well-formed bounded read {pct(sum(map(sum, b.values())), nb)}')
        if na and nb:
            print(f'      difference, by task: {dci(diff_ci(a, b))}')
        ag = [r for r in sel if r['mangled'] and r['again']]
        print(f'      of the repeats after a mangled read, mangled again: {pct(sum(r["again_mangled"] for r in ag), len(ag))}')

    pooled('2. Gemma-4-31B, the two custom agents (tool results as dictionaries, Oct to Nov)',
           lambda r: r['model'] == 'Gemma-4-31B' and r['rendering'] == 'dictionaries')
    pooled('3. Gemma-4-31B, GraphLoc traces of Sep (tool results as JSON strings): starter agent and graph skill',
           lambda r: r['model'] == 'Gemma-4-31B' and r['rendering'] == 'JSON strings')
    pooled('4. Gemma-4-12B and Gemma 4 E4B, custom agent 1', lambda r: r['model'] != 'Gemma-4-31B')

    print()
    print('5. The names as written')
    for rendering in ('dictionaries', 'JSON strings'):
        print(f'   tool results as {rendering}: ' + ', '.join(f'{json.dumps(k)} x{n}' for k, n in names[rendering].most_common()))

    tables = DATA / 'public_traces' / 'petermugoya__what-the-agent-saw' / 'data'
    print()
    print('6. Per-run tables of the starter agent (1,329 runs, Oct 2 to 5): tool calls with a corrupted argument key')
    print('   (a key that contains a double quote, a newline or a space, as that dataset counts them)')
    if not tables.exists():
        print('   (tables not found locally: skipped)')
        return
    for name, note in (('main1', 'its authors call this session overloaded'), ('main2', ''), ('main3', '')):
        eps = [json.loads(l) for l in io.open(tables / f'{name}_episodes.jsonl', encoding='utf-8')]
        reads = collections.Counter()
        for line in io.open(tables / f'{name}_reads.jsonl', encoding='utf-8'):
            r = json.loads(line)
            if r.get('via') == 'read_file':
                reads[(r['cell'], r['instance_id'])] += 1
        calls = sum(e.get('n_calls') or 0 for e in eps)
        corrupt = sum(e.get('n_corrupted_arg_calls') or 0 for e in eps)
        nread = sum(reads[(e['cell'], e['instance_id'])] for e in eps)
        with_ = [e for e in eps if e.get('n_corrupted_arg_calls')]
        without = [e for e in eps if not e.get('n_corrupted_arg_calls')]
        by = collections.defaultdict(list)
        for e in eps:
            by[e['instance_id']].append(int(bool(e.get('n_corrupted_arg_calls'))))
        print(f'   session {name}: {corrupt} such calls in {calls} tool calls ({100 * corrupt / calls:.1f}%) and beside '
              f'{nread} read_file reads ({100 * corrupt / nread:.1f} per 100 reads); runs with at least one '
              f'{pct(len(with_), len(eps))}, by task {ci(boot_ci(by))}' + (f' ({note})' if note else ''))
        print(f'      resolved: runs with such a call {pct(sum(bool(e.get("resolved")) for e in with_), len(with_))}; '
              f'runs without {pct(sum(bool(e.get("resolved")) for e in without), len(without))} (not compared within task)')
        dist = collections.Counter(min(e.get('n_corrupted_arg_calls') or 0, 6) for e in eps)
        print('      such calls per run (6 = six or more): ' + ', '.join(f'{k}: {dist[k]}' for k in sorted(dist)))


if __name__ == '__main__':
    main()
