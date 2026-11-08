"""Load GraphLoc's public end-to-end traces (ATIF JSON written by the competition harness).

Layout per notebook: e2e/results/<arm>/w<worker>/traces/trace_<task>.json
Steps: 1 = system instruction, 2 = task prompt, then agent steps (thinking / text / tool calls + observation).
Usage: py -I analysis/graphloc_traces.py summary | neighbors | steps <task> [run] [arm]
"""
import collections
import json
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'graphloc' / 'out'
NOTEBOOKS = {
    'graphloc-end-to-end-gemma-4-agent-skill': 1,
    'graphloc-end-to-end-repeat-run-2': 2,
    'graphloc-end-to-end-repeat-run-3': 3,
}
EDIT_TOOLS = {'edit_file', 'write_file'}


def iter_runs(root=ROOT, arm=None):
    for nb, run in NOTEBOOKS.items():
        for p in sorted((root / nb).glob('e2e/results/*/w*/traces/trace_*.json')):
            a = p.parts[-4]
            if arm and a != arm:
                continue
            yield {'run': run, 'arm': a, 'worker': p.parts[-3], 'task': p.stem[len('trace_'):], 'path': p}


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def step_kind(s):
    ex = s.get('extra') or {}
    return ex.get('event_type') or ('tool' if s.get('tool_calls') else s.get('source'))


def summary():
    kinds = collections.Counter()
    tools = collections.Counter()
    per = collections.Counter()
    compaction = collections.Counter()
    for r in iter_runs():
        d = load(r['path'])
        per[(r['arm'], r['run'])] += 1
        seen_c = False
        for s in d['steps']:
            kinds[step_kind(s)] += 1
            for tc in s.get('tool_calls', []):
                tools[(r['arm'], tc['function_name'])] += 1
            if 'compact' in str(step_kind(s)).lower():
                seen_c = True
        compaction[(r['arm'], seen_c)] += 1
    print('runs per (arm, run):', dict(per))
    print('step kinds:', dict(kinds))
    print('runs with a compaction step (arm, bool):', dict(compaction))
    for (a, t), n in sorted(tools.items()):
        print(f'  {a:6s} {t:22s} {n}')


def neighbors():
    """Print every get_code_neighbors call in the base arm with its exact observation text."""
    for r in iter_runs(arm='base'):
        d = load(r['path'])
        for s in d['steps']:
            for tc in s.get('tool_calls', []):
                if tc['function_name'] == 'get_code_neighbors':
                    obs = (s.get('observation') or {}).get('content', '')
                    print(f"--- {r['task']} run{r['run']} step{s['step_id']} args={tc['arguments']}")
                    print('    obs:', str(obs)[:700].replace('\n', ' '))


def steps(task, run=1, arm='base'):
    for r in iter_runs(arm=arm):
        if r['task'] == task and r['run'] == int(run):
            d = load(r['path'])
            for s in d['steps']:
                msg = (s.get('message') or '')
                tcs = [(tc['function_name'], {k: str(v)[:70] for k, v in tc['arguments'].items()}) for tc in s.get('tool_calls', [])]
                obs = (s.get('observation') or {}).get('content') if s.get('observation') else None
                print(f"[{s['step_id']:3d}] {s['source']:6s} {str(step_kind(s)):18s} metrics={s.get('metrics')}")
                if msg:
                    print('      msg:', msg[:300].replace('\n', ' '))
                if tcs:
                    print('      calls:', tcs)
                if obs is not None:
                    print('      obs:', str(obs)[:300].replace('\n', ' '))
            return
    print('not found')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'summary'
    if cmd == 'summary':
        summary()
    elif cmd == 'neighbors':
        neighbors()
    elif cmd == 'steps':
        steps(*sys.argv[2:])
