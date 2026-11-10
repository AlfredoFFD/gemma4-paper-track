"""Experiment E (navigation horizon; prereg/06, DRAFT): up to five model calls per replay, read-only navigation executes.

Runs inside the Modal container started by forks_k_modal.py (Linux, Python 3.12). Same wheelhouse and harness install
and the same vLLM settings as the one-step fork runner (forks_modal_runner.py). Modes (env MODE):
  fidelity  no model: for one state per task, re-execute the logged read_file and read-only run_command calls of its
            history on the Linux checkout; print exact / order-only / different counts per tool
  smoke     4 states of R, seeds 1 and 2, arms A, H, E, RE; prints stop reasons and call counts only
  full      every state of R (seeds 1-5) and U (seeds 1-3) under the four arms; resumable; one JSON line per replay in
            OUT_DIR/results_k.jsonl, one line per finished state in OUT_DIR/checkouts_k.jsonl
Replays of one state share one prepared checkout on the container's local disk; it is fingerprinted before and after
and removed when the state's replays are done.

LOCAL_TEST=1 (local plumbing only): no installs, no vLLM; every replay talks to a scripted fake model that picks
reads, greps, edits and text answers at random from the state's own files. LIMIT_R / LIMIT_U keep the first N states
of each population (after the fixed shuffle). Its rows are labelled fake.
"""
import asyncio
import collections
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

MODE = os.environ.get('MODE', 'smoke')
LOCAL_TEST = os.environ.get('LOCAL_TEST') == '1'
WHEELHOUSE = Path(os.environ.get('WHEELHOUSE_DIR', '/nonexistent'))
INPUTS = Path(os.environ['INPUTS_DIR'])          # replay.py, agent config, harness wheels (shared with the other runner)
INPUTS_K = Path(os.environ['INPUTS_K_DIR'])      # replay_k.py, population.json, states.jsonl
SNAPSHOTS = Path(os.environ['SNAPSHOTS_DIR'])    # <task>.tgz
COMP = Path(os.environ['COMP_DIR'])
MODEL_PATH = os.environ.get('MODEL_DIR', '')
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
OUT = Path(os.environ['OUT_DIR'])
OUT.mkdir(parents=True, exist_ok=True)
CHECKOUTS = Path(os.environ.get('CHECKOUT_DIR', '/tmp/checkouts_k'))
CHECKOUTS.mkdir(parents=True, exist_ok=True)

HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')
ARMS = ['A', 'H', 'E', 'RE']
K = 5
CONCURRENCY = int(os.environ.get('CONCURRENCY', '8'))
ACTIVE_STATES = int(os.environ.get('ACTIVE_STATES', '3'))  # checkouts on disk at once
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(19 * 3600)))
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.0f}s]', *a, flush=True)


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
sys.path.insert(0, str(INPUTS_K))  # replay_k.py
import replay  # noqa: E402
import replay_k  # noqa: E402

replay.DATA = COMP
ENV = replay_k.environment_record()
freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines()
versions = {
    'experiment': 'E-navigation-horizon', 'mode': MODE, 'local_test_fake_model': LOCAL_TEST,
    'harness_variant': HARNESS_VARIANT, 'k': K, 'arms': ARMS,
    'packages': [l for l in freeze if l.split('==')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'vllm', 'litellm', 'transformers', 'torch')],
    'wheelhouse_files': sorted(p.name for p in WHEELHOUSE.glob('*.whl')),
    'model_path': MODEL_PATH, 'model_files': sorted(p.name for p in Path(MODEL_PATH).glob('*'))[:40] if MODEL_PATH else [],
    'platform': 'modal' if not LOCAL_TEST else 'local-test', 'python': sys.version,
    'tensor_parallel_size': int(os.environ.get('TP_SIZE', '1')), 'concurrency': CONCURRENCY,
    'sandbox_environment': ENV, 'thoughts_in_history': False,
    'inputs_k_files': {p.name: p.stat().st_size for p in INPUTS_K.glob('*') if p.is_file()},
    'gpu': subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True,
                          text=True).stdout.strip().splitlines() if shutil.which('nvidia-smi') and not LOCAL_TEST else [],
}
(OUT / 'versions_k.json').write_text(json.dumps(versions, indent=1))
log('versions:', versions['packages'], '| sandbox environment:', ENV)

states = {}
for line in open(INPUTS_K / 'states.jsonl', encoding='utf-8'):
    s = json.loads(line)
    states[(s['task'], s['run'], s.get('fork', 0))] = s
pop = json.load(open(INPUTS_K / 'population.json', encoding='utf-8'))
members = [(tuple(r['key']), 'R', r['seeds']) for r in pop['R']] + [(tuple(r['key']), 'U', r['seeds']) for r in pop['U']]
gold_of = {tuple(r['key']): r for r in pop['R'] + pop['U']}
log(f'{len(states)} states loaded; population R {len(pop["R"])}, U {len(pop["U"])}')

# ------------------------------------------------------------------ 3. fidelity mode: no model
if MODE == 'fidelity':
    firsts = {}
    for key, _p, _s in sorted(members):
        firsts.setdefault(key[0], key)
    counts = collections.defaultdict(collections.Counter)
    with open(OUT / 'fidelity_k.jsonl', 'w') as f:
        for task, key in sorted(firsts.items()):
            try:
                rows = replay_k.fidelity_state(states[key])
            except Exception as e:  # noqa: BLE001
                rows = [{'task': task, 'run': key[1], 'tool': 'prepare', 'verdict': f'error: {type(e).__name__}: {e}'}]
            for r in rows:
                f.write(json.dumps(r) + '\n')
                v = r['verdict']
                counts[r['tool']]['exact' if v in ('exact', 'exact_path_norm') else v] += 1
    log(f'fidelity over {len(firsts)} states (one per task); sandbox environment {ENV}:')
    for tool, c in sorted(counts.items()):
        print(f'  {tool}: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())), flush=True)
    sys.exit(0)

# ------------------------------------------------------------------ 4. the model: vLLM as the one-step runner starts it
server = None
registry = None
if not LOCAL_TEST:
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
    """LOCAL_TEST only: a scripted model making five random choices among the state's own files."""
    from adk_submission import ModelRegistry
    rng = random.Random(f'{state["task"]}|{state["run"]}|{state.get("fork", 0)}|{arm}|{seed}')
    g = gold_of[(state['task'], state['run'], state.get('fork', 0))]
    files = sorted(set(g['gold_files']) | {v['path'] for v in state['neighbor_spans'].values() if v})
    script = []
    for _ in range(K):
        f = rng.choice(files)
        regions = g['gold_files'].get(f) or [[1, 40]]
        a = max(1, rng.choice(regions)[0] + rng.randint(-120, 40))
        choice = rng.random()
        if choice < 0.45:
            script.append([('read_file', {'filepath': f, 'start_line': a, 'end_line': a + rng.randint(20, 200)})])
        elif choice < 0.65:
            script.append([('run_command', {'command': f"sed -n '{a},{a + 60}p' {f}"})])
        elif choice < 0.75:
            script.append([('run_command', {'command': f'grep -rn "def " {f.split("/")[0]} | head -n 20'})])
        elif choice < 0.85:
            script.append([('read_file', {'filepath': f}), ('edit_file', {'filepath': f, 'old_string': 'x', 'new_string': 'y'})])
        elif choice < 0.93:
            script.append([('get_status', {})])
        else:
            script.append([])
    reg = ModelRegistry()
    reg.register(replay.MODEL_ALIAS, replay_k._scripted_llm(script))
    return reg


agent_dir = Path(os.environ.get('AGENT_DIR', '/root/agents/base'))
(agent_dir / 'prompts').mkdir(parents=True, exist_ok=True)
(agent_dir / 'configs').mkdir(parents=True, exist_ok=True)
shutil.copy(INPUTS / 'agent.yaml', agent_dir / 'agent.yaml')
shutil.copy(INPUTS / 'sampling.yaml', agent_dir / 'configs' / 'sampling.yaml')
shutil.copy(INPUTS / 'system.md', agent_dir / 'prompts' / 'system.md')
agent_dir = str(agent_dir)

# ------------------------------------------------------------------ 5. jobs
order = sorted(members)
random.Random(0).shuffle(order)  # fixed order, so a partial run is a random subset of states
if MODE == 'smoke':
    order = [m for m in order if m[1] == 'R'][:4]
    order = [(key, p, [1, 2]) for key, p, _ in order]
if os.environ.get('LIMIT_R') or os.environ.get('LIMIT_U'):
    lim = {'R': int(os.environ.get('LIMIT_R', '0')), 'U': int(os.environ.get('LIMIT_U', '0'))}
    order = [m for p in ('R', 'U') for m in [x for x in order if x[1] == p][:lim[p]]]
res_path = OUT / ('results_k.jsonl' if MODE == 'full' else 'smoke_k.jsonl')
done = set()
if MODE == 'full' and res_path.exists():
    for l in open(res_path):
        r = json.loads(l)
        if not r.get('error'):  # replays that ended in an error are retried on a rerun
            done.add((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']))


def task_of(state):
    return {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}


async def run_state(key, population, seeds, replay_sem, state_sem, fout, fck, tally):
    jobs = [(arm, seed) for arm in ARMS for seed in seeds if key + (arm, seed) not in done]
    if not jobs:
        return
    async with state_sem:
        if time.time() - T0 > TIME_BUDGET_S:
            return
        state = states[key]
        try:
            mgr, sid, root, prep_s = await asyncio.to_thread(replay_k.prepare_workspace, state)
        except Exception as e:  # noqa: BLE001  (no rows are written: the state stays incomplete and a rerun retries it)
            log('checkout preparation failed for', key, f'{type(e).__name__}: {e}')
            fck.write(json.dumps({'task': key[0], 'run': key[1], 'fork': key[2], 'population': population,
                                  'error': f'{type(e).__name__}: {e}'}) + '\n')
            fck.flush()
            return
        fp0 = await asyncio.to_thread(replay_k.checkout_fingerprint, root / 'workspace')
        used = replay_k.counted_calls(state)

        async def one(arm, seed):
            async with replay_sem:
                if time.time() - T0 > TIME_BUDGET_S:  # checked once a slot is free, so queued jobs stop after the budget
                    return
                try:
                    reg = fake_registry(state, arm, seed) if LOCAL_TEST else registry
                    agent, handle = replay_k.build_agent_k(agent_dir, reg, task_of(state), mgr, sid, tool_calls_used=used)
                    o = await replay_k.run_k_steps(agent, state, arm, seed, k=K, workspace=handle)
                except Exception as e:  # noqa: BLE001
                    o = {'task': key[0], 'run': key[1], 'fork': key[2], 'arm': arm, 'seed': seed, 'k': K, 'steps': [],
                         'stop': 'error', 'error': f'{type(e).__name__}: {e}', 'executed_calls': 0}
                o.update({'population': population, 'harness_variant': HARNESS_VARIANT, 'locale': ENV['locale'],
                          'checkout_prep_s': prep_s, 'fake_model': LOCAL_TEST})
                fout.write(json.dumps(o) + '\n')
                fout.flush()
                tally[o['stop'] if not o.get('error') else 'error'] += 1
                n = sum(tally.values())
                if n % 25 == 0:
                    log(f'{n} replays written: {dict(tally)}')

        try:
            await asyncio.gather(*(one(a, s) for a, s in jobs))
            fp1 = await asyncio.to_thread(replay_k.checkout_fingerprint, root / 'workspace')
            fck.write(json.dumps({'task': key[0], 'run': key[1], 'fork': key[2], 'population': population,
                                  'prep_s': prep_s, 'checkout_unchanged': fp0 == fp1, 'replays': len(jobs)}) + '\n')
            fck.flush()
            if fp0 != fp1:
                log('WARNING: checkout changed during the replays of', key)
        finally:
            await asyncio.to_thread(replay_k.remove_tree, root)


async def main():
    replay_sem, state_sem = asyncio.Semaphore(CONCURRENCY), asyncio.Semaphore(ACTIVE_STATES)
    n_jobs = sum(len(ARMS) * len(seeds) for key, _p, seeds in order) - len(done)
    log(f'mode {MODE}: {len(order)} states, {n_jobs} replays to run ({len(done)} already done)')
    tally = collections.Counter()
    ck_path = OUT / ('checkouts_k.jsonl' if MODE == 'full' else 'smoke_checkouts_k.jsonl')
    with open(res_path, 'a') as fout, open(ck_path, 'a') as fck:
        await asyncio.gather(*(run_state(key, p, seeds, replay_sem, state_sem, fout, fck, tally) for key, p, seeds in order))
    log(f'finished: {dict(tally)}')


asyncio.run(main())

# ------------------------------------------------------------------ 6. summary (stop reasons and call counts only)
rows = [json.loads(l) for l in open(res_path)]
by_arm = {}
for r in rows:
    d = by_arm.setdefault(r['arm'], {'n': 0, 'errors': 0, 'stops': collections.Counter(), 'executed_calls': [],
                                     'model_calls': []})
    d['n'] += 1
    d['errors'] += bool(r.get('error'))
    d['stops'][r['stop']] += 1
    d['executed_calls'].append(r.get('executed_calls', 0))
    d['model_calls'].append(len(r.get('steps') or []))
for d in by_arm.values():
    d['stops'] = dict(d['stops'])
    d['mean_executed_calls'] = round(sum(d['executed_calls']) / len(d['executed_calls']), 2) if d['executed_calls'] else None
    d['mean_model_calls'] = round(sum(d['model_calls']) / len(d['model_calls']), 2) if d['model_calls'] else None
    del d['executed_calls'], d['model_calls']
summary = {'mode': MODE, 'rows': len(rows), 'by_arm': by_arm, 'elapsed_s': round(time.time() - T0),
           'sandbox_environment': ENV, 'fake_model': LOCAL_TEST}
(OUT / ('summary_k.json' if MODE == 'full' else 'smoke_summary_k.json')).write_text(json.dumps(summary, indent=1))
for arm in ARMS:
    if arm in by_arm:
        d = by_arm[arm]
        print(f'arm {arm}: {d["n"]} replays, errors {d["errors"]}, stops {d["stops"]}, mean model calls '
              f'{d["mean_model_calls"]}, mean executed calls {d["mean_executed_calls"]}', flush=True)
if server is not None:
    try:
        if getattr(server, 'log_path', None) and Path(server.log_path).exists():
            shutil.copy(server.log_path, OUT / 'vllm_server_k.log')
    except Exception as e:  # noqa: BLE001
        log('could not copy the server log:', e)
    server.stop()
log('done')
