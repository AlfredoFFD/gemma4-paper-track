"""Population of experiment G (pre-registration 08), part "fresh": one new episode per task with a public base trace.

For every task of GraphLoc's public base traces (106 tasks, three runs each) this writes one pseudo-state: no history,
only the task prompt the original harness logged for that task (the three runs of a task logged the same prompt, which
is checked here), the size of the first prompt the original run logged, and the gold patch's modified files with their
changed regions (same definition as analysis/make_population_k.py, imported). Nothing here depends on any replay.

The part "fix" of experiment G uses analysis/fork_states_k/population.json unchanged (R and U), with new seeds: 11 to
15 in R and 11 to 13 in U.

Writes analysis/fork_states_g/fresh_states.jsonl and analysis/fork_states_g/population_g.json.
Usage: .venv/Scripts/python.exe -I -X utf8 analysis/make_population_g.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from graphloc_traces import iter_runs, load, step_kind  # noqa: E402
from make_population_k import parse_patch  # noqa: E402

TASKS = ROOT / 'data' / 'tasks.jsonl'
POP_K = HERE / 'fork_states_k' / 'population.json'
OUT_DIR = HERE / 'fork_states_g'
FRESH = {'k': 8, 'arms': ['N'], 'seeds': [1, 2, 3]}
FIX = {'k': 5, 'arms': ['A', 'AF', 'EF'], 'seeds': {'R': [11, 12, 13, 14, 15], 'U': [11, 12, 13]}}


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = {json.loads(l)['instance_id']: json.loads(l) for l in open(TASKS, encoding='utf-8')}
    prompts, first_tokens = {}, {}
    for r in iter_runs(arm='base'):
        steps = load(r['path'])['steps']
        prompt = next(s.get('message') or '' for s in steps if step_kind(s) == 'task_prompt')
        first = next((s['metrics']['prompt_tokens'] for s in steps if s.get('source') == 'agent' and s.get('metrics')), None)
        prompts.setdefault(r['task'], set()).add(prompt)
        first_tokens.setdefault(r['task'], set()).add(first)
    assert all(len(v) == 1 for v in prompts.values()), 'the runs of a task logged different task prompts'
    assert all(len(v) == 1 and None not in v for v in first_tokens.values()), 'the runs of a task logged different first prompt sizes'
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(OUT_DIR / 'fresh_states.jsonl', 'w', encoding='utf-8', newline='\n') as f:
        for t in sorted(prompts):
            prompt = next(iter(prompts[t]))
            gold = parse_patch(tasks[t]['patch'])
            state = {'task': t, 'run': 0, 'fork': 0, 'repo': tasks[t]['repo'], 'base_commit': tasks[t]['base_commit'],
                     'steps': [{'step_id': 2, 'source': 'user', 'message': prompt, 'extra': {'event_type': 'task_prompt'}}],
                     'logged_first_prompt_tokens': next(iter(first_tokens[t])),
                     'gold_files': {p: v['regions'] for p, v in sorted(gold.items()) if not v['created']},
                     'created_files': sorted(p for p, v in gold.items() if v['created'])}
            f.write(json.dumps(state) + '\n')
            rows.append({'task': t, 'repo': state['repo'], 'logged_first_prompt_tokens': state['logged_first_prompt_tokens'],
                         'prompt_chars': len(prompt), 'prompt_sha1': hashlib.sha1(prompt.encode('utf-8')).hexdigest()})
    pop_k = json.load(open(POP_K, encoding='utf-8'))
    out = {'tasks_md5': md5(TASKS), 'population_k_md5': md5(POP_K), 'fresh_states_md5': md5(OUT_DIR / 'fresh_states.jsonl'),
           'fresh': dict(FRESH, tasks=rows),
           'fix': dict(FIX, source='analysis/fork_states_k/population.json, R and U unchanged, new seeds',
                       R=len(pop_k['R']), U=len(pop_k['U']))}
    (OUT_DIR / 'population_g.json').write_text(json.dumps(out, indent=1), encoding='utf-8', newline='\n')
    repos = {}
    for r in rows:
        repos[r['repo']] = repos.get(r['repo'], 0) + 1
    print(f'fresh: {len(rows)} tasks {repos}, seeds {FRESH["seeds"]}, k {FRESH["k"]}: {len(rows) * len(FRESH["seeds"])} episodes')
    n_fix = sum(len(pop_k[p]) * len(FIX['seeds'][p]) for p in ('R', 'U')) * len(FIX['arms'])
    print(f'fix: R {len(pop_k["R"])} + U {len(pop_k["U"])} states, seeds {FIX["seeds"]}, arms {FIX["arms"]}, k {FIX["k"]}: {n_fix} replays')
    print(f'wrote {OUT_DIR.relative_to(ROOT).as_posix()}/fresh_states.jsonl md5 {out["fresh_states_md5"]}')
    print(f'wrote {OUT_DIR.relative_to(ROOT).as_posix()}/population_g.json md5 {md5(OUT_DIR / "population_g.json")}')


if __name__ == '__main__':
    main()
