"""Pre-registration 16 on Modal: the first model call of a fresh episode under four task prompts (arms C, CS, S, SC);
one A100-80GB, Python 3.12.

Derived from forks_09_modal.py: the same image, package list, wheelhouse, vLLM settings, served model path, harness
wheels (`latest`) and number of calls at once (16). Up to 16 checkouts are on disk at once (there: 4), so that the
calls waiting for a slot never run out. The runner is forks_16_runner.py (read its header first). Volume
`gemma-forks-c`, mounted at /vol:
  /vol/inputs_g/forks_16_runner.py        analysis/modal_g/forks_16_runner.py
  /vol/inputs_g/first_call_states.jsonl   analysis/fork_states_w/first_call_states.jsonl (analysis/make_states_w.py)
  /vol/inputs_g/replay_k.py, /vol/snapshots, /vol/comp and the shared inputs: as for forks_09_modal.py
  /vol/out_16          the full run: results_16.jsonl, checkouts_16.jsonl, versions_16.json, summary_16.json,
                       platform_actual_16.json, pip_freeze_16.txt, vllm_server_16.log
  /vol/out_16_smoke    the smoke test (it starts from nothing each time): smoke_16.jsonl, smoke_summary_16.json, ...

Before launching, from the repository root (again after any change to the runner or the states):
  modal volume put -f gemma-forks-c analysis/modal_g/forks_16_runner.py /inputs_g/forks_16_runner.py
  modal volume put -f gemma-forks-c analysis/fork_states_w/first_call_states.jsonl /inputs_g/first_call_states.jsonl

Plumbing (no GPU):    modal run analysis/modal_g/forks_16_modal.py --mode check
                      the runner in full mode on the smoke test's tasks (seeds 1 to 3) with a scripted model in
                      place of the server; nothing is kept
Smoke test:           modal run analysis/modal_g/forks_16_modal.py --mode smoke
                      6 tasks, every arm, seed 1: 24 calls; stopped 560 s after it starts at the latest
Full run:             modal run --detach analysis/modal_g/forks_16_modal.py --mode full [--minutes 25] [--concurrency 16]
                      arms C and CS for every task and seed, then arms S and SC; no new call starts after `minutes`
                      of the runner's clock (its start-up, about six minutes, included); resumable
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-16')
vol = modal.Volume.from_name('gemma-forks-c')
image = (
    modal.Image.from_registry('nvidia/cuda:12.8.0-devel-ubuntu22.04', add_python='3.12')
    .entrypoint([])
    .pip_install('vllm==0.19.1', 'litellm==1.82.4', 'google-adk==1.36.1', 'huggingface-hub>=1.5.0,<2.0',
                 # declared dependencies of the harness wheels, which the runner installs with --no-deps
                 'docker>=7.0.0', 'cachetools>=5.0.0', 'networkx>=3.0', 'python-dotenv>=1.0.0', 'rich>=13.0',
                 'pandas>=2.0.0', 'accelerate', 'scikit-learn>=1.3.0', 'pyyaml>=6.0')
)
M = '/vol'
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the first upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip and vLLM
INPUTS_G = '/vol/inputs_g'
RUNNER = INPUTS_G + '/forks_16_runner.py'
STATES = INPUTS_G + '/first_call_states.jsonl'
OUT = '/vol/out_16'
SMOKE_OUT = '/vol/out_16_smoke'
CHECK_OUT = '/root/check_16'                     # the plumbing run keeps nothing
BUDGET_MIN = 25                                  # the full run: no new call after this much of the runner's clock
SMOKE_BUDGET_S, SMOKE_LIMIT_S = 520, 560         # the smoke test: no new call after 520 s; stopped 560 s after it starts
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZE = 23265352448


def _env(mode, out, variant, gpu=True, **extra):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if gpu:
        if not os.path.exists(SERVED):
            os.makedirs(os.path.dirname(SERVED), exist_ok=True)
            os.symlink(f'{V}/model', SERVED)
        assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'
    e = dict(os.environ, MODE=mode, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', INPUTS_G_DIR=INPUTS_G,
             STATES_FILE=STATES, SNAPSHOTS_DIR='/vol/snapshots', COMP_DIR='/vol/comp', MODEL_DIR=SERVED if gpu else '',
             OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', CONCURRENCY='16', ACTIVE_STATES='16',
             CHECKOUT_DIR='/tmp/checkouts_16', TIME_BUDGET_S=str(BUDGET_MIN * 60), HARNESS_VARIANT=variant)
    e.update({k: str(v) for k, v in extra.items()})
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _run(env, limit_s):
    """The runner as its own process group; stopped, with everything it started, once limit_s have passed."""
    p = subprocess.Popen([sys.executable, RUNNER], env=env, start_new_session=True)
    try:
        return p.wait(timeout=limit_s)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        return 'stopped at the time limit'


@app.function(image=image, volumes={M: vol}, timeout=900, cpu=8, memory=16384, max_containers=1)
def check(variant: str = 'latest'):
    """No GPU: the runner in full mode on the first 6 tasks of the order (seeds 1 to 3: 72 calls), with a scripted
    model in place of the server. Nothing is kept."""
    shutil.rmtree(CHECK_OUT, ignore_errors=True)
    env = _env('full', CHECK_OUT, variant, gpu=False, FAKE_MODEL=1, LIMIT_TASKS=6, TIME_BUDGET_S=600)
    print('python', sys.version, '| no gpu, scripted model | variant', variant, flush=True)
    code = _run(env, 780)
    print('exit', code, flush=True)
    return code


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=SMOKE_LIMIT_S + 40, cpu=8, memory=49152, max_containers=1)
def smoke(variant: str = 'latest'):
    t0 = time.time()
    shutil.rmtree(SMOKE_OUT, ignore_errors=True)   # the smoke test starts from nothing
    env = _env('smoke', SMOKE_OUT, variant, TIME_BUDGET_S=SMOKE_BUDGET_S)
    print('python', sys.version, '| gpu', _gpu(), '| variant', variant, flush=True)
    code = _run(env, max(1, SMOKE_LIMIT_S - (time.time() - t0)))
    print('exit', code, flush=True)
    vol.commit()
    return code


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=(BUDGET_MIN + 35) * 60, cpu=8, memory=49152, max_containers=1)
def full(variant: str = 'latest', minutes: int = BUDGET_MIN, concurrency: int = 16):
    env = _env('full', OUT, variant, TIME_BUDGET_S=minutes * 60, CONCURRENCY=concurrency, ACTIVE_STATES=max(16, concurrency))
    os.makedirs(OUT, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'served_as': SERVED, 'harness_variant': variant,
               'time_budget_minutes': minutes, 'concurrency': concurrency, 'active_states': env['ACTIVE_STATES'],
               'states_file': STATES, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(OUT + '/platform_actual_16.json', 'w'))

    def committer():  # rows reach the volume as they are written
        while True:
            time.sleep(120)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=committer, daemon=True).start()
    code = _run(env, (minutes + 10) * 60)          # calls under way at the budget finish; then the runner ends by itself
    print('exit', code, flush=True)
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(OUT + '/pip_freeze_16.txt', 'w').write(txt)
    vol.commit()
    return code


@app.local_entrypoint()
def main(mode: str = 'smoke', variant: str = 'latest', minutes: int = BUDGET_MIN, concurrency: int = 16):
    if mode == 'check':
        print('exit', check.remote(variant))
    elif mode == 'smoke':
        print('exit', smoke.remote(variant))
    elif mode == 'full':
        assert 1 <= minutes <= BUDGET_MIN + 20 and 1 <= concurrency <= 64, (minutes, concurrency)
        print('exit', full.remote(variant, minutes, concurrency))
    else:
        raise SystemExit(f'unknown mode {mode}')
