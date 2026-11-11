"""Pre-registration 16: the first model call of a fresh episode, under four task prompts.

A copy of forks_09_runner.py (pre-registration 09's runner, which stays as it is) cut down to its part "fresh" and
changed in four places. Runs inside the Modal container started by forks_16_modal.py; newest harness wheels (`latest`:
adk_submission 0.2.13, swegemma 0.2.11); analysis/replay.py and analysis/replay_k.py are used unchanged.

  1. The task prompt of a replay is the prompt of its record in first_call_states.jsonl (analysis/make_states_w.py:
     one record per task and arm), not the one of fresh_states.jsonl. Arms:
       C    the task prompt the current evaluator builds, as built
       CS   that prompt with its four lines on the graph tools replaced by the lines of the September prompt
       S    the task prompt the recorded runs of September logged, as logged
       SC   that prompt with its four lines on the graph tools replaced by the lines of the current prompt
  2. One model call (k = 1), and no tool executes: every call is classified as a stop, so a replay ends at the
     model's first response, before anything runs (the 09 runner let read-only navigation and the graph tools run).
  3. Order: arms C and CS for every task and seed first, then arms S and SC, the tasks in a fixed shuffled order. For
     a task and a pair of arms, the two calls of the first seed run first and the calls of the other seeds after
     them: their prompts are then in the server's prefix cache, so the server does not process one prompt three times
     at once (the requests themselves do not depend on this order). No new call starts once TIME_BUDGET_S seconds of
     this runner's clock have passed (its start-up included).
  4. What is printed and summarized: by arm, the rows, the errors, the responses that hold a call or a text, the empty
     responses and the prompt sizes. No tool name, no stop reason and no text of a response is printed in any mode.
As in the 09 runner: the installation of the wheels, the server and its settings, the agent directory, a checkout of
the task's snapshot (prepared once per task and pair of arms), the agent compiled by replay_k.build_agent_k on that
checkout, the seed written into its generation config, the request of a fresh episode (nothing seeded; the task
prompt is the new message) and replay_k.run_k_steps.

Modes (env MODE): smoke (the first 6 tasks of the order, seed 1: 24 calls, rows in OUT_DIR/smoke_16.jsonl), full
(seeds 1 to 3; resumable; one JSON line per call in OUT_DIR/results_16.jsonl, one line per finished task and pair of
arms in OUT_DIR/checkouts_16.jsonl). FAKE_MODEL=1: a scripted model in place of the server (plumbing only).
LOCAL_TEST=1: the same, and the wheels are not installed (the harness is importable already).
"""
import asyncio
import collections
import glob
import hashlib
import importlib
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

for k, v in (
    ('LITELLM_LOCAL_MODEL_COST_MAP', 'True'), ('TRANSFORMERS_NO_TF', '1'), ('VLLM_WORKER_MULTIPROC_METHOD', 'spawn'),
    ('VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS', '1'), ('VLLM_ENGINE_READY_TIMEOUT_S', '1200'), ('VLLM_NO_USAGE_STATS', '1'),
    ('OTEL_SDK_DISABLED', 'true'), ('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True'), ('LITELLM_LOG', 'ERROR'),
):
    os.environ.setdefault(k, v)

MODE = os.environ.get('MODE', 'smoke')
LOCAL_TEST = os.environ.get('LOCAL_TEST') == '1'
FAKE_MODEL = LOCAL_TEST or os.environ.get('FAKE_MODEL') == '1'
WHEELHOUSE = Path(os.environ.get('WHEELHOUSE_DIR', '/nonexistent'))
INPUTS = Path(os.environ['INPUTS_DIR'])          # replay.py, agent config, harness wheels (shared with the other runners)
INPUTS_G = Path(os.environ['INPUTS_G_DIR'])      # replay_k.py, first_call_states.jsonl
STATES = Path(os.environ.get('STATES_FILE') or INPUTS_G / 'first_call_states.jsonl')
SNAPSHOTS = Path(os.environ['SNAPSHOTS_DIR'])    # <task>.tgz
COMP = Path(os.environ['COMP_DIR'])
MODEL_PATH = os.environ.get('MODEL_DIR', '')
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
OUT = Path(os.environ['OUT_DIR'])
OUT.mkdir(parents=True, exist_ok=True)
CHECKOUTS = Path(os.environ.get('CHECKOUT_DIR', '/tmp/checkouts_16'))
CHECKOUTS.mkdir(parents=True, exist_ok=True)

HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'latest')
PAIRS = (('C', 'CS'), ('S', 'SC'))   # the order of the run: the first pair for every task and seed, then the second
ARMS = tuple(a for pair in PAIRS for a in pair)
K = 1                                # one model call
SEEDS = [1, 2, 3]
SMOKE_TASKS = 6
CONCURRENCY = int(os.environ.get('CONCURRENCY', '16'))
ACTIVE_STATES = int(os.environ.get('ACTIVE_STATES', '16'))  # checkouts on disk at once
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(25 * 60)))
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.0f}s]', *a, flush=True)


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ 1. install the wheelhouse, then the chosen harness
if not LOCAL_TEST:
    for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth', '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
        for pth in glob.glob(pth_pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    tmp_whl = Path('/tmp/wheelhouse')
    tmp_whl.mkdir(parents=True, exist_ok=True)
    for w in WHEELHOUSE.glob('*.whl'):
        if 'cutlass' in w.name.lower():
            continue
        name = w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name
        target = tmp_whl / name
        if not target.exists():
            os.symlink(w, target)
    wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
    log(f'installing {len(wheels)} wheelhouse wheels')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
    VARIANTS = {'v28': ['adk_eval_core-0.1.0', 'adk_submission-0.2.12', 'swegemma-0.2.7'],
                'latest': ['adk_eval_core-0.1.0', 'adk_submission-0.2.13', 'swegemma-0.2.11']}
    harness_wheels = [str(next(INPUTS.glob(f'{stem}-*.whl'))) for stem in VARIANTS[HARNESS_VARIANT]]
    log(f'installing harness variant {HARNESS_VARIANT}: {[Path(w).name for w in harness_wheels]}')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *harness_wheels], check=True)
    importlib.invalidate_caches()

# ------------------------------------------------------------------ 2. replay_k and its environment
os.environ['REPLAY_K_DATA'] = str(COMP)
os.environ['SNAPSHOTS_DIR'] = str(SNAPSHOTS)
os.environ['REPLAY_K_TMP'] = str(CHECKOUTS)
sys.path.insert(0, str(INPUTS))    # replay.py
sys.path.insert(0, str(INPUTS_G))  # replay_k.py
from google.genai import types  # noqa: E402

import replay  # noqa: E402
import replay_k  # noqa: E402

replay.DATA = COMP


# --- the two changes of this experiment (replay.py and replay_k.py themselves are unchanged)
def _arm_messages_16(state, arm, agent_name):
    """Every arm is a fresh episode, as arm N of the 09 runner: nothing seeded; the record's task prompt is the new
    message. `state` is the record of the task and the arm, so the prompt is the arm's."""
    assert arm in ARMS and state['arm'] == arm, (arm, state.get('arm'))
    text = next(s.get('message') or '' for s in state['steps'] if replay._kind(s) == 'task_prompt')
    return [], types.Content(role='user', parts=[types.Part(text=text)])


replay.arm_messages = _arm_messages_16  # replay_k.run_k_steps looks it up at call time


def _classify_call_16(name, args):
    """No tool executes: whatever the first response calls, the replay stops before it runs."""
    return 'stop'


replay_k.classify_call = _classify_call_16  # the gate and run_k_steps look it up at call time

ENV = replay_k.environment_record()
freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines()
versions = {
    'experiment': '16-first-call-under-four-task-prompts', 'mode': MODE, 'fake_model': FAKE_MODEL, 'local_test': LOCAL_TEST,
    'harness_variant': HARNESS_VARIANT, 'k': K, 'arms': list(ARMS), 'pairs_in_run_order': [list(p) for p in PAIRS],
    'seeds': SEEDS, 'time_budget_s': TIME_BUDGET_S,
    'packages': [l for l in freeze if l.split('==')[0].split(' @ ')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'google-genai', 'vllm', 'litellm',
                  'transformers', 'torch')],
    'wheelhouse_files': sorted(p.name for p in WHEELHOUSE.glob('*.whl')),
    'model_path': MODEL_PATH, 'model_files': sorted(p.name for p in Path(MODEL_PATH).glob('*'))[:40] if MODEL_PATH else [],
    'platform': 'modal' if not LOCAL_TEST else 'local-test', 'python': sys.version,
    'tensor_parallel_size': int(os.environ.get('TP_SIZE', '1')), 'concurrency': CONCURRENCY, 'active_states': ACTIVE_STATES,
    'sandbox_environment': ENV, 'thoughts_in_history': False,
    'input_md5': {p.name: md5(p) for p in (Path(__file__), STATES, Path(replay.__file__), Path(replay_k.__file__),
                                           INPUTS / 'agent.yaml', INPUTS / 'sampling.yaml', INPUTS / 'system.md') if p.exists()},
    'gpu': subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True,
                          text=True).stdout.strip().splitlines() if shutil.which('nvidia-smi') and not FAKE_MODEL else [],
}
(OUT / 'versions_16.json').write_text(json.dumps(versions, indent=1))
log('versions:', versions['packages'], '| sandbox environment:', ENV)
log('inputs (md5):', versions['input_md5'])

records = {}
for line in open(STATES, encoding='utf-8'):
    s = json.loads(line)
    assert (s['task'], s['arm']) not in records, 'a task and arm is listed twice'
    records[(s['task'], s['arm'])] = s
tasks = sorted({t for t, _a in records})
assert all((t, a) in records for t in tasks for a in ARMS), 'a task lacks an arm'
log(f'{len(records)} records loaded: {len(tasks)} tasks x {len(ARMS)} arms')

# ------------------------------------------------------------------ 3. the model: vLLM as the other runners start it
server = None
registry = None
if not FAKE_MODEL:
    import litellm  # noqa: E402
    from adk_submission import VllmConfig, VllmServer  # noqa: E402

    litellm.drop_params = True
    vllm_cfg = VllmConfig(model=MODEL_PATH, port=8000, host='127.0.0.1', tool_call_parser='gemma4', reasoning_parser='gemma4',
                          default_chat_template_kwargs={'enable_thinking': True}, max_model_len=32768, dtype='bfloat16',
                          gpu_memory_utilization=0.90, enable_auto_tool_choice=True, tensor_parallel_size=int(os.environ.get('TP_SIZE', '1')),
                          startup_timeout=60 * 25)
    server = VllmServer(vllm_cfg, adapter_manifest=None)
    server.start()
    log('vLLM up at', server.base_url)
    import urllib.request  # noqa: E402

    with urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=30) as r:
        served = json.load(r)['data'][0]['id']
    log('served model id:', served)
    registry = server.create_model_registry(aliases={TARGET: served}, model_prefix='openai/', api_key='EMPTY')


def fake_registry(state, arm, seed):
    """FAKE_MODEL only: one scripted response, drawn by a generator seeded with the task, the arm and the seed."""
    from adk_submission import ModelRegistry
    rng = random.Random(f'{state["task"]}|{arm}|{seed}')
    responses = [
        [('search_similar_code', {'query': 'validate the request body'})],
        [('search_similar_code', {'query': 'Console.print'})],
        [('get_code_neighbors', {'node': 'main'})],
        [('get_code_subgraph', {'nodes': ['main', 'run']})],
        [('read_file', {'filepath': 'README.md'})],
        [('read_file', {'filepath': 'README.md', 'start_line"': 5, 'end_line"': 9})],
        [('run_command', {'command': 'grep -rn "def " . | head -n 20'})],
        [('run_command', {'command': 'cd /workspace && find . -name "*.py" | head -n 20'})],
        [('run_command', {'command': 'ls -la'})],
        [('run_command', {'command': 'ls'}), ('search_similar_code', {'query': 'render'})],
        [('write_file', {'filepath': 'repro.py', 'content': 'print(1)\n'})],
        [('search_similar_code', {'query"': 'render'})],   # a mangled argument name
        [('no_such_tool', {})],
        [],                                                # a text answer
    ]
    reg = ModelRegistry()
    reg.register(replay.MODEL_ALIAS, replay_k._scripted_llm([rng.choice(responses)]))
    return reg


agent_dir = Path(os.environ.get('AGENT_DIR', '/root/agents/base'))
(agent_dir / 'prompts').mkdir(parents=True, exist_ok=True)
(agent_dir / 'configs').mkdir(parents=True, exist_ok=True)
shutil.copy(INPUTS / 'agent.yaml', agent_dir / 'agent.yaml')
shutil.copy(INPUTS / 'sampling.yaml', agent_dir / 'configs' / 'sampling.yaml')
shutil.copy(INPUTS / 'system.md', agent_dir / 'prompts' / 'system.md')
agent_dir = str(agent_dir)

# ------------------------------------------------------------------ 4. jobs
order = sorted(tasks)
random.Random(0).shuffle(order)  # fixed order, so a partial run is a random subset
seeds = SEEDS
if MODE == 'smoke':
    order, seeds = order[:SMOKE_TASKS], SEEDS[:1]
if os.environ.get('LIMIT_TASKS'):
    order = order[:int(os.environ['LIMIT_TASKS'])]
res_path = OUT / ('results_16.jsonl' if MODE == 'full' else 'smoke_16.jsonl')
done = set()
if MODE == 'full' and res_path.exists():
    for l in open(res_path):
        r = json.loads(l)
        if not r.get('error'):  # calls that ended in an error are retried on a rerun
            done.add((r['task'], r['arm'], r['seed']))
planned = [(t, a, s) for pair in PAIRS for t in order for s in seeds for a in pair]
STATS = {'budget_stop': False}
NEW = []  # the rows this launch writes


def task_of(state):
    return {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}


def shape(o):
    """What a row holds, without what it says: an error, a response with a call or a text, or an empty response."""
    if o.get('error') or not o.get('steps'):
        return 'error'
    first = o['steps'][0]
    return 'call or text' if first['calls'] or (first.get('text') or '').strip() else 'empty'


async def run_task(task, pair, replay_sem, state_sem, fout, fck, tally):
    jobs = [(arm, seed) for seed in seeds for arm in pair if (task, arm, seed) not in done]  # a seed's two arms side by side
    if not jobs:
        return
    async with state_sem:
        if time.time() - T0 > TIME_BUDGET_S:
            STATS['budget_stop'] = True
            return
        first = records[(task, pair[0])]  # the checkout depends on the task alone
        try:
            mgr, sid, root, prep_s = await asyncio.to_thread(replay_k.prepare_workspace, first)
        except Exception as e:  # noqa: BLE001  (no rows are written: the task stays incomplete and a rerun retries it)
            log('checkout preparation failed for', task, f'{type(e).__name__}: {e}')
            fck.write(json.dumps({'task': task, 'arms': list(pair), 'error': f'{type(e).__name__}: {e}'}) + '\n')
            fck.flush()
            return
        fp0 = await asyncio.to_thread(replay_k.checkout_fingerprint, root / 'workspace')

        async def one(arm, seed):
            async with replay_sem:
                if time.time() - T0 > TIME_BUDGET_S:  # checked once a slot is free, so queued calls stop after the budget
                    STATS['budget_stop'] = True
                    return
                state = records[(task, arm)]
                started = round(time.time() - T0, 1)
                try:
                    reg = fake_registry(state, arm, seed) if FAKE_MODEL else registry
                    agent, handle = replay_k.build_agent_k(agent_dir, reg, task_of(state), mgr, sid, tool_calls_used=0)
                    o = await replay_k.run_k_steps(agent, state, arm, seed, k=K, workspace=handle)
                except Exception as e:  # noqa: BLE001
                    o = {'task': task, 'run': 0, 'fork': 0, 'arm': arm, 'seed': seed, 'k': K, 'steps': [],
                         'stop': 'error', 'error': f'{type(e).__name__}: {e}', 'executed_calls': 0}
                o.update({'prompt_from': state['prompt_from'], 'block_from': state['block_from'],
                          'prompt_md5': state['prompt_md5'], 'started_s': started, 'harness_variant': HARNESS_VARIANT,
                          'locale': ENV['locale'], 'checkout_prep_s': prep_s, 'fake_model': FAKE_MODEL})
                fout.write(json.dumps(o) + '\n')
                fout.flush()
                NEW.append(o)
                tally[shape(o)] += 1
                n = sum(tally.values())
                if n % 100 == 0:
                    log(f'{n} calls written: {dict(tally)}')

        try:
            for stage in ([j for j in jobs if j[1] == seeds[0]], [j for j in jobs if j[1] != seeds[0]]):
                await asyncio.gather(*(one(a, s) for a, s in stage))  # the first seed, then the other seeds
            fp1 = await asyncio.to_thread(replay_k.checkout_fingerprint, root / 'workspace')
            fck.write(json.dumps({'task': task, 'arms': list(pair), 'prep_s': prep_s, 'checkout_unchanged': fp0 == fp1,
                                  'calls': len(jobs)}) + '\n')
            fck.flush()
            if fp0 != fp1:
                log('WARNING: checkout changed during the calls of', task)
        finally:
            await asyncio.to_thread(replay_k.remove_tree, root)


async def main():
    replay_sem, state_sem = asyncio.Semaphore(CONCURRENCY), asyncio.Semaphore(ACTIVE_STATES)
    n_jobs = sum(1 for cell in planned if cell not in done)
    log(f'mode {MODE}: {len(order)} tasks, seeds {seeds}, {n_jobs} calls to run ({len(planned) - n_jobs} already done); '
        f'no new call after {TIME_BUDGET_S} s')
    tally = collections.Counter()
    ck_path = OUT / ('checkouts_16.jsonl' if MODE == 'full' else 'smoke_checkouts_16.jsonl')
    with open(res_path, 'a') as fout, open(ck_path, 'a') as fck:
        for pair in PAIRS:  # arms C and CS finish for every task before arms S and SC start
            await asyncio.gather(*(run_task(t, pair, replay_sem, state_sem, fout, fck, tally) for t in order))
            log(f'arms {pair}: ' + ('cut short by the time budget' if STATS['budget_stop'] else 'finished')
                + f'; rows written so far: {dict(tally)}')


asyncio.run(main())

# ------------------------------------------------------------------ 5. summary (plumbing: no tool name, no stop reason)
rows = [json.loads(l) for l in open(res_path)]
cells = {}
for r in rows:  # one row per call; after a rerun, a call's row without an error replaces its earlier row
    key = (r['task'], r['arm'], r['seed'])
    if key not in cells or not r.get('error') or cells[key].get('error'):
        cells[key] = r
by_arm = {}
for a in ARMS:
    mine = [r for (t, arm, s), r in cells.items() if arm == a]
    sizes = [r['steps'][0]['prompt_tokens'] for r in mine if r.get('steps') and r['steps'][0].get('prompt_tokens')]
    by_arm[a] = {'planned': sum(1 for cell in planned if cell[1] == a), 'rows': len(mine),
                 'errors': sum(shape(r) == 'error' for r in mine),
                 'with_a_call_or_a_text': sum(shape(r) == 'call or text' for r in mine),
                 'empty': sum(shape(r) == 'empty' for r in mine),
                 'prompt_tokens_median': statistics.median(sizes) if sizes else None,
                 'prompt_tokens_min': min(sizes) if sizes else None, 'prompt_tokens_max': max(sizes) if sizes else None}
not_started = sum(1 for cell in planned if cell not in cells)
starts = [r['started_s'] for r in NEW if r.get('started_s') is not None]
summary = {'mode': MODE, 'rows_in_file': len(rows), 'rows_written_by_this_launch': len(NEW), 'calls_planned': len(planned),
           'calls_with_a_row': sum(1 for cell in planned if cell in cells), 'calls_not_started': not_started,
           'budget_stop': STATS['budget_stop'], 'time_budget_s': TIME_BUDGET_S,
           'first_call_started_s': min(starts) if starts else None, 'last_call_started_s': max(starts) if starts else None,
           'by_arm': by_arm, 'elapsed_s': round(time.time() - T0), 'sandbox_environment': ENV, 'fake_model': FAKE_MODEL}
(OUT / ('summary_16.json' if MODE == 'full' else 'smoke_summary_16.json')).write_text(json.dumps(summary, indent=1))


def report():
    for a, d in by_arm.items():
        print(f'arm {a}: {d["rows"]} of {d["planned"]} planned calls have a row; errors {d["errors"]}; responses with a call '
              f'or a text {d["with_a_call_or_a_text"]}; empty responses {d["empty"]}; prompt tokens median '
              f'{d["prompt_tokens_median"]} (from {d["prompt_tokens_min"]} to {d["prompt_tokens_max"]})', flush=True)
    print(f'calls planned {len(planned)}, with a row {summary["calls_with_a_row"]}, not started {not_started}; a budget stop '
          f'occurred: {STATS["budget_stop"]}; this launch wrote {len(NEW)} rows, its first call started at '
          f'{summary["first_call_started_s"]} s and its last at {summary["last_call_started_s"]} s of its clock '
          f'(no new call after {TIME_BUDGET_S} s)', flush=True)
    for text in sorted({str(r['error'])[:200] for r in cells.values() if r.get('error')}):
        print('error text:', text, flush=True)

    # prompt sizes: an arm as built or logged against the size its source logged; a swapped arm against its plain arm
    size = {}
    for (t, a, s), r in sorted(cells.items()):
        if r.get('steps') and r['steps'][0].get('prompt_tokens'):
            size.setdefault(t, {}).setdefault(a, r['steps'][0]['prompt_tokens'])
    for a, what in (('C', 'the size the whole run logged for its first model call'), ('S', 'the size the September run logged')):
        d = [size[t][a] - records[(t, a)]['logged_first_prompt_tokens'] for t in size
             if a in size[t] and records[(t, a)].get('logged_first_prompt_tokens')]
        if d:
            print(f'prompt size, arm {a} minus {what} ({len(d)} tasks): median {statistics.median(d):+.0f} tokens, '
                  f'from {min(d):+d} to {max(d):+d}', flush=True)
    for a, b in (('CS', 'C'), ('SC', 'S')):
        d = [size[t][a] - size[t][b] for t in size if a in size[t] and b in size[t]]
        if d:
            print(f'prompt size, arm {a} minus arm {b} ({len(d)} tasks): median {statistics.median(d):+.0f} tokens, '
                  f'from {min(d):+d} to {max(d):+d}', flush=True)
    if MODE == 'smoke' or FAKE_MODEL:
        for t in order:
            if t in size:
                print(f'prompt tokens, {t}: ' + ', '.join(
                    f'{a} {size[t].get(a)}' + (f' (logged {records[(t, a)]["logged_first_prompt_tokens"]})' if a in ('C', 'S') else '')
                    for a in ARMS), flush=True)
    timed = [r for r in NEW if not r.get('error') and r.get('latency_s') is not None and r.get('steps')]
    if timed:
        span = max(r['started_s'] + r['latency_s'] for r in timed) - min(r['started_s'] for r in timed)
        tokens = sum((r['steps'][0].get('completion_tokens') or 0) for r in timed)
        print(f'timing of this launch: {len(timed)} calls in {span:.0f} s' + (f' ({len(timed) / span:.2f} calls per second), '
              f'{tokens} completion tokens in all ({tokens / span:.0f} per second)' if span > 0 else '')
              + f', median seconds per call {statistics.median(r["latency_s"] for r in timed):.1f}', flush=True)


try:
    report()
except Exception as e:  # noqa: BLE001  (the rows and the summary file are written already)
    log(f'the printed report failed: {type(e).__name__}: {e}')

if server is not None:
    try:
        if getattr(server, 'log_path', None) and Path(server.log_path).exists():
            shutil.copy(server.log_path, OUT / 'vllm_server_16.log')
    except Exception as e:  # noqa: BLE001
        log('could not copy the server log:', e)
    server.stop()
log('done')
