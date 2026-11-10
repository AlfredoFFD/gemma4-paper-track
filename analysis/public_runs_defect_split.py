"""Malformed file reads in other teams' public runs, split by kind (EXPLORATORY).

Usage: py -I -X utf8 analysis/public_runs_defect_split.py

Nothing here was pre-registered and no model is run. analysis/public_runs_defect.py counts read_file calls whose
line bound sits under a mangled argument name, and reports one team's own per-run count of tool calls with a
corrupted argument key. That count covers every tool. This script (1) applies the same any-tool rule to the traces
we hold and splits it by tool, (2) counts a second malformation of file reads apart, (3) bounds how many of that
team's counted calls can be file reads, and (4) reads a fourth team's own flag for malformed calls.

Sources (local copies, not redistributed; see analysis/results/public/README.md):
  the traces read by public_runs_defect.py (starter agent and graph skill, Sep 2026; two custom agents, Oct to Nov)
  data/public_traces/petermugoya__what-the-agent-saw/data/main*_{episodes,calls,missing}.jsonl
      per-run, per-call and failed-read tables of 1,329 runs of the starter agent (Oct 2 to 5, 2026, swegemma 0.2.7)
  data/public_traces/kmussa77__gemma4-agent-traces-graph-audit/runs/<condition>/calls.csv
      per-call tables of three runs of a two-agent bundle, Gemma-4-31B (Oct 2026): `baseline` and `graph_howto`
      (129 tasks, swegemma 0.2.7) and `graph_scout` (60 tasks, swegemma 0.2.11). Argument texts are hashed.

Rules for a read_file call, the first that applies:
  MANGLED BOUND   an argument name that is not a plain identifier but reads `start_line` or `end_line` once quotes,
                  backslashes and whitespace are removed (the MANGLED of public_runs_defect.py). The agent framework
                  keeps only arguments the tool declares, so the bound is dropped and the read succeeds from line 1.
  PATH LEAK       the value of `filepath` holds the text `start_line` or `end_line`: the path string was not closed
                  and swallowed the bounds. The read fails (the file is not found).
  OTHER           neither.
  SAME FILE       the path up to the first quote, backtick, backslash or comma, without a leading /workspace/ or ./.
ANY-TOOL RULE (that of the what-the-agent-saw release, code/behavior/extract_events.py): a call of any tool with an
  argument key that holds a double quote, a newline or a space.
REJECTED EDIT (what-the-agent-saw per-call table): an edit_file or write_file call whose result has no status. The
  tool's own results carry `ok` or `error`; a call the framework refuses for a missing mandatory argument carries
  neither. Every such call is taken as one that may hold a corrupted key, which makes the floor below conservative.
FLOOR and CEILING for corrupted keys on calls other than edits, per session of that release: the ceiling is the
  release's count; the floor subtracts, run by run, the run's REJECTED EDITs (never below zero).
FLAGGED (the graph-audit release, scripts/analyze_traces.py): its own `malformed` column: arguments that are not a
  dictionary, a key outside the tool's declared set, or a `filepath` that holds a backtick, a double quote, <, >, |,
  the text start_line or end_line, or a comma followed by a word and a colon. For read_file this covers MANGLED BOUND
  and PATH LEAK together; the hashed arguments do not let them be told apart.
"""
import collections
import csv
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from public_runs_address import BOUNDS, DATA, calls_of, clean, is_read, norm, pct  # noqa: E402
from public_runs_defect import groups, mangled  # noqa: E402

WTAS = DATA / 'public_traces' / 'petermugoya__what-the-agent-saw' / 'data'
AUDIT = DATA / 'public_traces' / 'kmussa77__gemma4-agent-traces-graph-audit' / 'runs'


def any_tool_rule(args):
    return isinstance(args, dict) and any(('"' in str(k)) or ('\n' in str(k)) or (' ' in str(k)) for k in args)


def kind(call):
    if mangled(call):
        return 'MANGLED BOUND'
    fp = call['arguments'].get('filepath')
    if isinstance(fp, str) and re.search(r'start_line|end_line', fp):
        return 'PATH LEAK'
    return 'OTHER'


def same_file(call):
    return norm(re.split(r'[`"\\,]', str(call['arguments'].get('filepath') or ''))[0])


def jsonl(path):
    with io.open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def traces_part():
    print('1. The any-tool rule on the traces we hold, by tool')
    stats = []
    for label, model, rendering, paths in groups():
        by_tool = collections.Counter()
        runs_any = 0
        n_calls = n_reads = 0
        kinds = collections.Counter()
        runs = collections.defaultdict(set)
        err = collections.Counter()
        nxt = collections.defaultdict(lambda: [0, 0, 0, 0])   # with a next call, identical, same file, same file and OTHER
        for path in paths:
            try:
                calls = calls_of(json.load(io.open(path, encoding='utf-8')))
            except (ValueError, OSError):
                continue
            hit = False
            for i, (call, _text, parsed) in enumerate(calls):
                n_calls += 1
                if any_tool_rule(call.get('arguments')):
                    by_tool[call.get('function_name')] += 1
                    hit = True
                if not is_read(call):
                    continue
                n_reads += 1
                k = kind(call)
                kinds[k] += 1
                runs[k].add(str(path))
                err[k] += int(isinstance(parsed, dict) and parsed.get('status') == 'error')
                if i + 1 < len(calls):
                    b = calls[i + 1][0]
                    a = nxt[k]
                    a[0] += 1
                    if is_read(b):
                        a[1] += int(b['arguments'] == call['arguments'])
                        same = same_file(b) == same_file(call)
                        a[2] += int(same)
                        a[3] += int(same and kind(b) == 'OTHER')
            runs_any += hit
        total = sum(by_tool.values())
        print(f'   {label}, {model}: tool calls {n_calls}; counted by the rule {total} in {runs_any} of {len(paths)} runs: '
              + (', '.join(f'{t} {n}' for t, n in by_tool.most_common()) or 'none'))
        stats.append((label, model, len(paths), n_reads, kinds, runs, err, nxt))
    print()
    print('2. read_file calls by kind on the same traces')
    for label, model, n_paths, n_reads, kinds, runs, err, nxt in stats:
        print(f'   {label}, {model}: read_file calls {n_reads}')
        for k in ('MANGLED BOUND', 'PATH LEAK'):
            a = nxt[k]
            print(f'      {k:<13} {kinds[k]:>3} ({100 * kinds[k] / max(n_reads, 1):.1f} per 100 read_file calls) in {len(runs[k])} of {n_paths} runs; '
                  f'result is an error {err[k]}; next call: identical {a[1]} of {a[0]}, reads the same file {a[2]} of {a[0]}, of which well-formed {a[3]}')
        a = nxt['OTHER']
        print(f'      {"OTHER":<13} {kinds["OTHER"]:>4}; next call: identical {a[1]} of {a[0]}, reads the same file {pct(a[2], a[0])}')
    print()


def wtas_part():
    print('3. Per-run tables of the starter agent (1,329 runs, Oct 2 to 5): how many counted calls can be file reads')
    for sess in ('main1', 'main2', 'main3'):
        eps = jsonl(WTAS / f'{sess}_episodes.jsonl')
        n_tool = collections.Counter()
        rejected = collections.Counter()
        for r in jsonl(WTAS / f'{sess}_calls.jsonl'):
            n_tool[r['name']] += 1
            if r['name'] in ('edit_file', 'write_file') and r.get('status') is None:
                rejected[(r['cell'], r['instance_id'])] += 1
        ceiling = sum(e.get('n_corrupted_arg_calls', 0) for e in eps)
        ceiling_runs = sum(1 for e in eps if e.get('n_corrupted_arg_calls', 0) > 0)
        left = [max(0, e.get('n_corrupted_arg_calls', 0) - rejected.get((e['cell'], e['instance_id']), 0)) for e in eps]
        floor, floor_runs = sum(left), sum(1 for x in left if x > 0)
        reads = n_tool['read_file']
        miss = jsonl(WTAS / f'{sess}_missing.jsonl')
        leak = [m for m in miss if re.search(r'start_line|end_line', str(m.get('path')))]
        leak_runs = {(m['cell'], m['instance_id']) for m in leak}
        print(f'   session {sess}: runs {len(eps)}; tool calls {sum(n_tool.values())}, of which read_file {reads}, edit_file {n_tool["edit_file"]}, write_file {n_tool["write_file"]}')
        print(f'      calls counted by the any-tool rule {ceiling} in {ceiling_runs} runs; REJECTED EDITs {sum(rejected.values())}')
        print(f'      corrupted keys on calls other than edits: between {floor} and {ceiling}, '
              f'{100 * floor / reads:.1f} to {100 * ceiling / reads:.1f} per 100 read_file calls; '
              f'runs between {floor_runs} and {ceiling_runs} of {len(eps)} ({100 * floor_runs / len(eps):.1f}% to {100 * ceiling_runs / len(eps):.1f}%)')
        print(f'      failed reads {len(miss)}, of which PATH LEAK {len(leak)} ({100 * len(leak) / reads:.1f} per 100 read_file calls) in {len(leak_runs)} runs')
    print()


def audit_part():
    print('4. A fourth team, a two-agent bundle (Gemma-4-31B, Oct): read_file calls FLAGGED by that release\'s own rule')
    for cond, harness in (('baseline', 'swegemma 0.2.7'), ('graph_howto', 'swegemma 0.2.7'), ('graph_scout', 'swegemma 0.2.11')):
        with io.open(AUDIT / cond / 'calls.csv', encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        by_task = collections.defaultdict(list)
        for r in rows:
            by_task[r['id']].append(r)
        reads = [r for r in rows if r['tool'] == 'read_file']
        bad = [r for r in reads if r['malformed'] == '1']
        tasks_bad = {r['id'] for r in bad}
        ident = {'1': [0, 0], '0': [0, 0]}
        most = collections.Counter()
        for t in by_task.values():
            t.sort(key=lambda r: float(r['timestamp'] or 0))
            for a, b in zip(t, t[1:]):
                if a['tool'] == 'read_file':
                    ident[a['malformed']][1] += 1
                    ident[a['malformed']][0] += int(b['tool'] == 'read_file' and b['args_hash'] == a['args_hash'])
            c = collections.Counter(r['args_hash'] for r in t if r['tool'] == 'read_file' and r['malformed'] == '1')
            if c:
                most['five or more' if max(c.values()) >= 5 else 'fewer'] += 1
        print(f'   {cond} ({len(by_task)} tasks, {harness}): read_file calls {len(reads)}, FLAGGED {pct(len(bad), len(reads))}; tasks with one {pct(len(tasks_bad), len(by_task))}')
        print(f'      the next call is the identical call: after a FLAGGED read {pct(*ident["1"])}; after another read {pct(*ident["0"])}')
        print(f'      tasks in which one identical FLAGGED read was sent five or more times: {most["five or more"]} of {len(tasks_bad)}')


def main():
    print('PUBLIC RUNS: malformed file reads split by kind (EXPLORATORY)')
    print()
    traces_part()
    wtas_part()
    audit_part()


if __name__ == '__main__':
    main()
