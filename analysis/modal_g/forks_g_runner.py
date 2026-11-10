"""Experiment G (pre-registration 08): the argument defect in fresh episodes, and a patched harness against the stock one.

Runs inside the Modal container started by forks_g_modal.py (Linux, Python 3.12). Same wheelhouse install, the same
vLLM settings and the same replay code as the five-call runner (analysis/modal_k/forks_k_runner.py); the harness wheels
are chosen by HARNESS_VARIANT (the wrapper passes `latest`: adk_submission 0.2.13, swegemma 0.2.11). analysis/replay.py
and analysis/replay_k.py are used unchanged. Two parts share one model server:

  fresh  one new episode per task of fork_states_g/fresh_states.jsonl and seed (1 to 3): nothing is seeded, the task
         prompt the original harness logged for the task is the new message (arm N). Up to 8 model calls; read_file and
         read-only shell commands execute; the episode stops before the first other call, as in the five-call experiment.
  fix    every state of R (seeds 11 to 15) and U (seeds 11 to 13) of fork_states_k/population.json, up to 5 model
         calls, three arms:
         A   the stock harness, no list (as in the five-call experiment)
         AF  arm A with one change: before a read_file call runs, an argument name that is not a plain identifier and
             reads start_line or end_line once quotes, backslashes and spaces are removed is given that name (a
             well-formed name wins if both are present), so the read returns the lines the model asked for. The call
             the model wrote is recorded unchanged.
         EF  the same change, and arm E's legible note as the new message (both proposed changes together)

Modes (env MODE):
  smoke  3 fresh tasks and 3 states of R, the first two seeds of each; prints stop reasons and call counts, each fresh task's first
         prompt size beside the logged one, and whether restored bounds were honored (plumbing only)
  full   everything; resumable; one JSON line per replay in OUT_DIR/results_g.jsonl, one line per finished state or
         task in OUT_DIR/checkouts_g.jsonl
Replays of one state (or task) share one prepared checkout on the container's local disk; it is fingerprinted before
and after and removed when its replays are done.

LOCAL_TEST=1 (local plumbing only): no installs, no vLLM; a scripted fake model picks reads, greps, edits and text
answers at random and writes about half of its line bounds under a mangled name. LIMIT_FRESH / LIMIT_R / LIMIT_U keep
the first N members of each population (after the fixed shuffle). Its rows are labelled fake.
"""
import asyncio
import collections
import glob
import importlib
import json
import os
import random
import re
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
INPUTS = Path(os.environ['INPUTS_DIR'])          # replay.py, agent config, harness wheels (shared with the other runners)
INPUTS_G = Path(os.environ['INPUTS_G_DIR'])      # replay_k.py, population.json, states.jsonl, population_g.json, fresh_states.jsonl
SNAPSHOTS = Path(os.environ['SNAPSHOTS_DIR'])    # <task>.tgz
COMP = Path(os.environ['COMP_DIR'])
MODEL_PATH = os.environ.get('MODEL_DIR', '')
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
OUT = Path(os.environ['OUT_DIR'])
OUT.mkdir(parents=True, exist_ok=True)
CHECKOUTS = Path(os.environ.get('CHECKOUT_DIR', '/tmp/checkouts_g'))
CHECKOUTS.mkdir(parents=True, exist_ok=True)

HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')
ARMS_OF = {'FRESH': ['N'], 'R': ['A', 'AF', 'EF'], 'U': ['A', 'AF', 'EF']}
K_OF = {'FRESH': 8, 'R': 5, 'U': 5}
SEEDS_OF = {'FRESH': [1, 2, 3], 'R': [11, 12, 13, 14, 15], 'U': [11, 12, 13]}
BASE_ARM = {'AF': 'A', 'EF': 'E'}  # the arm whose messages a patched arm seeds
PARTS = [p for p in os.environ.get('PARTS', 'fresh,fix').split(',') if p]
BOUNDS = ('start_line', 'end_line')
CONCURRENCY = int(os.environ.get('CONCURRENCY', '8'))
ACTIVE_STATES = int(os.environ.get('ACTIVE_STATES', '3'))  # checkouts on disk at once
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(8 * 3600)))
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
sys.path.insert(0, str(INPUTS_G))  # replay_k.py
from google.genai import types  # noqa: E402

import replay  # noqa: E402
import replay_k  # noqa: E402

replay.DATA = COMP

# --- the two additions of this experiment (replay.py and replay_k.py themselves are unchanged)
_orig_arm_messages = replay.arm_messages


def _arm_messages_g(state, arm, agent_name):
    """N: a fresh episode (nothing seeded; the logged task prompt is the new message). AF, EF: arm A's, E's messages."""
    if arm == 'N':
        text = next(s.get('message') or '' for s in state['steps'] if replay._kind(s) == 'task_prompt')
        return [], types.Content(role='user', parts=[types.Part(text=text)])
    return _orig_arm_messages(state, BASE_ARM.get(arm, arm), agent_name)


replay.arm_messages = _arm_messages_g  # replay_k.run_k_steps looks it up at call time


def restore_bounds(args):
    """In place: give a mangled line-bound name its plain name. Returns the plain names restored."""
    restored = []
    for name in list(args):
        plain = re.sub(r'[\\"\'\s]', '', str(name))
        if (not str(name).isidentifier()) and plain in BOUNDS:
            value = args.pop(name)
            args.setdefault(plain, value)  # a well-formed name wins if both are present
            restored.append(plain)
    return restored


def honor_bounds(agent, tally):
    """Arms AF and EF: restore mangled line-bound names of read_file before the call reaches the tool."""
    gate = agent.before_tool_callback

    def _restore_then_gate(tool, args, tool_context):
        if tool.name == 'read_file' and isinstance(args, dict) and restore_bounds(args):
            tally['restored_calls'] += 1
        return gate(tool, args, tool_context)

    agent.before_tool_callback = _restore_then_gate


ENV = replay_k.environment_record()
freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines()
versions = {
    'experiment': 'G-fresh-episodes-and-honored-bounds', 'mode': MODE, 'local_test_fake_model': LOCAL_TEST,
    'harness_variant': HARNESS_VARIANT, 'k': K_OF, 'arms': ARMS_OF, 'seeds': SEEDS_OF, 'parts': PARTS,
    'packages': [l for l in freeze if l.split('==')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'vllm', 'litellm', 'transformers', 'torch')],
    'wheelhouse_files': sorted(p.name for p in WHEELHOUSE.glob('*.whl')),
    'model_path': MODEL_PATH, 'model_files': sorted(p.name for p in Path(MODEL_PATH).glob('*'))[:40] if MODEL_PATH else [],
    'platform': 'modal' if not LOCAL_TEST else 'local-test', 'python': sys.version,
    'tensor_parallel_size': int(os.environ.get('TP_SIZE', '1')), 'concurrency': CONCURRENCY,
    'sandbox_environment': ENV, 'thoughts_in_history': False,
    'inputs_g_files': {p.name: p.stat().st_size for p in INPUTS_G.glob('*') if p.is_file()},
    'gpu': subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True,
                          text=True).stdout.strip().splitlines() if shutil.which('nvidia-smi') and not LOCAL_TEST else [],
}
(OUT / 'versions_g.json').write_text(json.dumps(versions, indent=1))
log('versions:', versions['packages'], '| sandbox environment:', ENV)

states = {}
for line in open(INPUTS_G / 'states.jsonl', encoding='utf-8'):
    s = json.loads(line)
    states[(s['task'], s['run'], s.get('fork', 0))] = s
fresh = {}
for line in open(INPUTS_G / 'fresh_states.jsonl', encoding='utf-8'):
    s = json.loads(line)
    fresh[(s['task'], 0, 0)] = s
assert not set(states) & set(fresh)
states.update(fresh)
pop = json.load(open(INPUTS_G / 'population.json', encoding='utf-8'))
members = []
if 'fresh' in PARTS:
    members += [(key, 'FRESH', SEEDS_OF['FRESH']) for key in fresh]
if 'fix' in PARTS:
    members += [(tuple(r['key']), p, SEEDS_OF[p]) for p in ('R', 'U') for r in pop[p]]
gold_of = {tuple(r['key']): r for r in pop['R'] + pop['U']}
gold_of.update({key: s for key, s in fresh.items()})
log(f'{len(states)} states loaded; fresh tasks {len(fresh)}, R {len(pop["R"])}, U {len(pop["U"])}')

# ------------------------------------------------------------------ 3. the model: vLLM as the other runners start it
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


def fake_registry(state, arm, seed, k):
    """LOCAL_TEST only: a scripted model; about half of its line bounds are written under a mangled name."""
    from adk_submission import ModelRegistry
    rng = random.Random(f'{state["task"]}|{state["run"]}|{state.get("fork", 0)}|{"A" if arm == "AF" else arm}|{seed}')  # A and AF share a script
    g = gold_of[(state['task'], state['run'], state.get('fork', 0))]
    files = sorted(set(g['gold_files']) | {v['path'] for v in (state.get('neighbor_spans') or {}).values() if v}) or ['README.md']
    script = []
    for _ in range(k):
        f = rng.choice(files)
        regions = g['gold_files'].get(f) or [[1, 40]]
        a = max(1, rng.choice(regions)[0] + rng.randint(-120, 40))
        choice = rng.random()
        if choice < 0.6:
            sl, el = ('start_line"', 'end_line"') if rng.random() < 0.5 else ('start_line', 'end_line')
            script.append([('read_file', {'filepath': f, sl: a, el: a + rng.randint(20, 200)})])
        elif choice < 0.75:
            script.append([('run_command', {'command': f"sed -n '{a},{a + 60}p' {f}"})])
        elif choice < 0.85:
            script.append([('run_command', {'command': f'grep -rn "def " {f.split("/")[0]} | head -n 20'})])
        elif choice < 0.92:
            script.append([('read_file', {'filepath': f}), ('edit_file', {'filepath': f, 'old_string': 'x', 'new_string': 'y'})])
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

# ------------------------------------------------------------------ 4. jobs
order = sorted(members)
random.Random(0).shuffle(order)  # fixed order, so a partial run is a random subset
order = [m for m in order if m[1] == 'FRESH'] + [m for m in order if m[1] != 'FRESH']  # the fresh part first; R and U stay interleaved in the shuffled order
if MODE == 'smoke':
    order = [m for m in order if m[1] == 'FRESH'][:3] + [m for m in order if m[1] == 'R'][:3]
    order = [(key, p, seeds[:2]) for key, p, seeds in order]
if any(os.environ.get(v) for v in ('LIMIT_FRESH', 'LIMIT_R', 'LIMIT_U')):
    lim = {'FRESH': int(os.environ.get('LIMIT_FRESH', '0')), 'R': int(os.environ.get('LIMIT_R', '0')),
           'U': int(os.environ.get('LIMIT_U', '0'))}
    order = [m for p in ('FRESH', 'R', 'U') for m in [x for x in order if x[1] == p][:lim[p]]]
res_path = OUT / ('results_g.jsonl' if MODE == 'full' else 'smoke_g.jsonl')
done = set()
if MODE == 'full' and res_path.exists():
    for l in open(res_path):
        r = json.loads(l)
        if not r.get('error'):  # replays that ended in an error are retried on a rerun
            done.add((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']))


def task_of(state):
    return {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}


async def run_state(key, population, seeds, replay_sem, state_sem, fout, fck, tally):
    arms, k = ARMS_OF[population], K_OF[population]
    jobs = [(arm, seed) for arm in arms for seed in seeds if key + (arm, seed) not in done]
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
                honored = collections.Counter()
                try:
                    reg = fake_registry(state, arm, seed, k) if LOCAL_TEST else registry
                    agent, handle = replay_k.build_agent_k(agent_dir, reg, task_of(state), mgr, sid, tool_calls_used=used)
                    if arm in BASE_ARM:
                        honor_bounds(agent, honored)
                    o = await replay_k.run_k_steps(agent, state, arm, seed, k=k, workspace=handle)
                except Exception as e:  # noqa: BLE001
                    o = {'task': key[0], 'run': key[1], 'fork': key[2], 'arm': arm, 'seed': seed, 'k': k, 'steps': [],
                         'stop': 'error', 'error': f'{type(e).__name__}: {e}', 'executed_calls': 0}
                o.update({'population': population, 'harness_variant': HARNESS_VARIANT, 'locale': ENV['locale'],
                          'checkout_prep_s': prep_s, 'fake_model': LOCAL_TEST, 'restored_calls': honored['restored_calls']})
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
    n_jobs = sum(len(ARMS_OF[p]) * len(seeds) for key, p, seeds in order) - len(done)
    log(f'mode {MODE}: {len(order)} states or tasks, {n_jobs} replays to run ({len(done)} already done)')
    tally = collections.Counter()
    ck_path = OUT / ('checkouts_g.jsonl' if MODE == 'full' else 'smoke_checkouts_g.jsonl')
    with open(res_path, 'a') as fout, open(ck_path, 'a') as fck:
        for part in (('FRESH',), ('R', 'U')):  # the fresh part finishes before the fix part starts
            await asyncio.gather(*(run_state(key, p, seeds, replay_sem, state_sem, fout, fck, tally)
                                   for key, p, seeds in order if p in part))
            log(f'part {part} finished: {dict(tally)}')


asyncio.run(main())

# ------------------------------------------------------------------ 5. summary (stop reasons, call counts, plumbing)
rows = [json.loads(l) for l in open(res_path)]
by_arm = {}
for r in rows:
    d = by_arm.setdefault(f'{r["population"]}/{r["arm"]}', {'n': 0, 'errors': 0, 'stops': collections.Counter(),
                                                           'executed_calls': [], 'model_calls': []})
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
summary = {'mode': MODE, 'rows': len(rows), 'by_population_and_arm': by_arm, 'elapsed_s': round(time.time() - T0),
           'sandbox_environment': ENV, 'fake_model': LOCAL_TEST}
(OUT / ('summary_g.json' if MODE == 'full' else 'smoke_summary_g.json')).write_text(json.dumps(summary, indent=1))
for name, d in sorted(by_arm.items()):
    print(f'{name}: {d["n"]} replays, errors {d["errors"]}, stops {d["stops"]}, mean model calls '
          f'{d["mean_model_calls"]}, mean executed calls {d["mean_executed_calls"]}', flush=True)

if MODE == 'smoke' or LOCAL_TEST:  # plumbing only: prompt sizes of the fresh start, and whether restored bounds were honored
    for r in rows:
        if r['population'] == 'FRESH' and r.get('steps'):
            logged = states[(r['task'], 0, 0)]['logged_first_prompt_tokens']
            print(f'fresh {r["task"]} seed {r["seed"]}: first prompt {r["steps"][0]["prompt_tokens"]} tokens, logged {logged}', flush=True)
    plumb = collections.Counter()
    for r in rows:
        for st in r.get('steps') or []:
            for c in st['calls']:
                a = c['arguments'] if isinstance(c['arguments'], dict) else {}
                bad = [n for n in a if (not str(n).isidentifier()) and re.sub(r'[\\"\'\s]', '', str(n)) in BOUNDS]
                if c['function_name'] != 'read_file' or not c['executed'] or not bad:
                    continue
                res = c.get('result') or {}
                want = next((a[n] for n in a if re.sub(r'[\\"\'\s]', '', str(n)) == 'start_line'), None)
                plumb[(r['arm'], 'mangled reads executed')] += 1
                plumb[(r['arm'], 'returned from line 1')] += int(res.get('start_line') == 1)
                plumb[(r['arm'], 'returned from the start line the model wrote')] += int(want is not None and res.get('start_line') == want)
    for (arm, what), n in sorted(plumb.items()):
        print(f'plumbing, arm {arm}: {what}: {n}', flush=True)
    print('restored_calls recorded by arm:', dict(collections.Counter({a: sum(r.get('restored_calls', 0) for r in rows if r['arm'] == a)
                                                                    for a in {r['arm'] for r in rows}})), flush=True)

if server is not None:
    try:
        if getattr(server, 'log_path', None) and Path(server.log_path).exists():
            shutil.copy(server.log_path, OUT / 'vllm_server_g.log')
    except Exception as e:  # noqa: BLE001
        log('could not copy the server log:', e)
    server.stop()
log('done')
