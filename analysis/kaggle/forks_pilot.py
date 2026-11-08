"""Gemma graph forks, pilot: one-step replays of saved Gemma-4-31B states under five arms.

Runs as a Kaggle script on a 4 x L4 session with the competition wheelhouse, the competition model and a private
inputs dataset (replay.py, states.jsonl, the base agent config, harness wheels). Writes /kaggle/working/forks/:
  versions.json   harness, vLLM and model details for the record
  fidelity.jsonl  arm A replays whose prompt size is compared with the logged size at the same step
  results.jsonl   one line per (state, arm, seed): the model's next call, its thought, token usage, latency
  summary.json    counts per arm and the fidelity numbers
Resumable: finished (state, arm, seed) lines are skipped on a rerun.
"""
import asyncio
import glob
import importlib
import json
import os
import random
import shutil
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

WHEELHOUSE = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
INPUTS = Path(glob.glob('/kaggle/input/datasets/*/gemma-graph-forks-inputs')[0])
COMP = Path('/kaggle/input/competitions/gemma-4-developer-agent')
MODEL_PATH = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
OUT = Path('/kaggle/working/forks')
OUT.mkdir(parents=True, exist_ok=True)

HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')  # harness wheels closest to the traces' era
SEEDS = [1, 2, 3]
ARMS = ['A', 'P', 'Pp', 'H', 'Hp']
FIDELITY_N = int(os.environ.get('FIDELITY_N', '12'))
STATES_N = int(os.environ.get('STATES_N', '0'))  # 0 = all
CONCURRENCY = int(os.environ.get('CONCURRENCY', '8'))
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(9 * 3600)))
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.0f}s]', *a, flush=True)


# ------------------------------------------------------------------ 1. install the wheelhouse, then the chosen harness
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

# ------------------------------------------------------------------ 2. record versions
freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines()
versions = {
    'harness_variant': HARNESS_VARIANT,
    'packages': [l for l in freeze if l.split('==')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'vllm', 'litellm', 'transformers', 'torch')],
    'wheelhouse_files': sorted(p.name for p in WHEELHOUSE.glob('*.whl')),
    'model_path': MODEL_PATH, 'model_files': sorted(p.name for p in Path(MODEL_PATH).glob('*'))[:40],
    'seeds': SEEDS, 'arms': ARMS, 'concurrency': CONCURRENCY,
    'gpu': subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True, text=True).stdout.strip().splitlines(),
}
(OUT / 'versions.json').write_text(json.dumps(versions, indent=1))
log('versions:', versions['packages'])

# ------------------------------------------------------------------ 3. start vLLM as the Getting Started notebook does
import litellm  # noqa: E402
from adk_submission import VllmConfig, VllmServer  # noqa: E402

litellm.drop_params = True
vllm_cfg = VllmConfig(model=MODEL_PATH, port=8000, host='127.0.0.1', tool_call_parser='gemma4', reasoning_parser='gemma4',
                      default_chat_template_kwargs={'enable_thinking': True}, max_model_len=32768, dtype='bfloat16',
                      gpu_memory_utilization=0.90, enable_auto_tool_choice=True, tensor_parallel_size=4,
                      startup_timeout=60 * 25)
server = VllmServer(vllm_cfg, adapter_manifest=None)
server.start()
log('vLLM up at', server.base_url)
import urllib.request  # noqa: E402

with urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=30) as r:
    served = json.load(r)['data'][0]['id']
log('served model id:', served)
registry = server.create_model_registry(aliases={TARGET: served}, model_prefix='openai/', api_key='EMPTY')

# ------------------------------------------------------------------ 4. states and agents
sys.path.insert(0, str(INPUTS))
import replay  # noqa: E402

replay.DATA = COMP  # the tools never run, but the context wants graph and embedding directories
states = [json.loads(l) for l in open(INPUTS / 'states.jsonl', encoding='utf-8')]
random.Random(0).shuffle(states)  # fixed order, so a partial run is a random subset of states
if STATES_N:
    states = states[:STATES_N]
log(f'{len(states)} states loaded')
agent_dir = Path('/kaggle/working/agents/base')  # the base agent: sample prompt, nine tools, no adapters
(agent_dir / 'prompts').mkdir(parents=True, exist_ok=True)
(agent_dir / 'configs').mkdir(parents=True, exist_ok=True)
shutil.copy(INPUTS / 'agent.yaml', agent_dir / 'agent.yaml')
shutil.copy(INPUTS / 'sampling.yaml', agent_dir / 'configs' / 'sampling.yaml')
shutil.copy(INPUTS / 'system.md', agent_dir / 'prompts' / 'system.md')
agent_dir = str(agent_dir)
agents = {}
for seed in SEEDS:
    task = {'instance_id': 'replay', 'repo': 'replay/replay', 'base_commit': ''}
    a = replay.build_agent(agent_dir, registry, task)
    a.generate_content_config.seed = seed
    agents[seed] = a
log('agents built; tools:', [getattr(t, 'name', getattr(t, '__name__', '?')) for t in agents[SEEDS[0]].tools])


def task_of(state):
    return {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}


async def one(state, arm, seed, sem):
    async with sem:
        agent = agents[seed]
        return await replay.run_one_step(agent, state, arm, seed)


# ------------------------------------------------------------------ 5. fidelity: does the rebuilt arm-A prompt match the logged size?
async def fidelity():
    sem = asyncio.Semaphore(CONCURRENCY)
    picks = states[:FIDELITY_N]
    outs = await asyncio.gather(*(one(s, 'A', SEEDS[0], sem) for s in picks))
    rows = []
    with open(OUT / 'fidelity.jsonl', 'w') as f:
        for s, o in zip(picks, outs):
            got = (o.get('usage') or {}).get('prompt_tokens')
            row = {'task': s['task'], 'run': s['run'], 'fork': s.get('fork', 0), 'logged_prompt_tokens': s['prompt_tokens_next_call_logged'],
                   'replayed_prompt_tokens': got, 'diff': (got - s['prompt_tokens_next_call_logged']) if got else None,
                   'error': o.get('error'), 'next_call': o.get('next_call'), 'observed_next_call': s.get('observed_next_call')}
            rows.append(row)
            f.write(json.dumps(row) + '\n')
    diffs = [r['diff'] for r in rows if r['diff'] is not None]
    log('fidelity diffs (replayed - logged prompt tokens):', diffs)
    return rows


fid_rows = asyncio.run(fidelity())

# ------------------------------------------------------------------ 6. the pilot
done = set()
res_path = OUT / 'results.jsonl'
if res_path.exists():
    for l in open(res_path):
        r = json.loads(l)
        done.add((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']))


async def pilot():
    sem = asyncio.Semaphore(CONCURRENCY)
    jobs = [(s, arm, seed) for s in states for arm in ARMS for seed in SEEDS
            if (s['task'], s['run'], s.get('fork', 0), arm, seed) not in done]
    log(f'{len(jobs)} replays to run ({len(done)} already done)')
    f = open(res_path, 'a')
    n_ok = n_err = 0

    async def run_and_write(s, arm, seed):
        nonlocal n_ok, n_err
        if time.time() - T0 > TIME_BUDGET_S:
            return
        o = await one(s, arm, seed, sem)
        o['decoy'] = s['decoy'] if arm in ('Pp', 'Hp') else None
        f.write(json.dumps(o) + '\n')
        f.flush()
        if o.get('error'):
            n_err += 1
        else:
            n_ok += 1
        if (n_ok + n_err) % 25 == 0:
            log(f'{n_ok} ok, {n_err} errors')

    await asyncio.gather(*(run_and_write(s, arm, seed) for s, arm, seed in jobs))
    f.close()
    log(f'pilot done: {n_ok} ok, {n_err} errors')


asyncio.run(pilot())

# ------------------------------------------------------------------ 7. summary
rows = [json.loads(l) for l in open(res_path)]
by_arm = {}
for r in rows:
    d = by_arm.setdefault(r['arm'], {'n': 0, 'errors': 0, 'with_call': 0, 'prompt_tokens': []})
    d['n'] += 1
    d['errors'] += bool(r.get('error'))
    d['with_call'] += bool(r.get('next_call'))
    if r.get('usage') and r['usage'].get('prompt_tokens'):
        d['prompt_tokens'].append(r['usage']['prompt_tokens'])
for d in by_arm.values():
    d['prompt_tokens_mean'] = round(sum(d['prompt_tokens']) / len(d['prompt_tokens']), 1) if d['prompt_tokens'] else None
    del d['prompt_tokens']
summary = {'states': len(states), 'rows': len(rows), 'by_arm': by_arm,
           'fidelity': [{k: r[k] for k in ('task', 'run', 'logged_prompt_tokens', 'replayed_prompt_tokens', 'diff', 'error')} for r in fid_rows],
           'elapsed_s': round(time.time() - T0)}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1))
log('summary:', json.dumps(summary['by_arm']))
try:
    if getattr(server, 'log_path', None) and Path(server.log_path).exists():
        shutil.copy(server.log_path, OUT / 'vllm_server.log')
except Exception as e:  # noqa: BLE001
    log('could not copy the server log:', e)
server.stop()
log('done')
