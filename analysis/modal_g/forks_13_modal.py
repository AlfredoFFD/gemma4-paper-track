"""Pre-registration 13 on Modal: one-step replays of the 407 states with the list written as search hits, one
`file:line:definition line` per neighbor (arm EG), Gemma-4-31B, the harness wheels of Sep 30 (v28), as in
pre-registrations 04, 05 and 12.

The runner is the frozen one-step runner of pre-registration 07 (/vol/inputs_w/forks_w_runner.py, unchanged); only
the states file and the arm differ. One A100-80GB, tensor-parallel size 1, Python 3.12, the same image as the other
runs.

Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_w/forks_w_runner.py   the frozen runner
  /vol/inputs_g/states_h.jsonl      analysis/fork_states_h/states.jsonl (built by analysis/make_states_h.py)
  /vol/out_13                       results.jsonl, fidelity.jsonl, fidelity_w.jsonl, versions.json, summary.json,
                                    pip_freeze.txt, platform_actual.json

Smoke test:  modal run forks_13_modal.py --mode smoke
Full run:    modal run --detach forks_13_modal.py --mode full
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-13')
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
RUNNER = '/vol/inputs_w/forks_w_runner.py'
STATES = '/vol/inputs_g/states_h.jsonl'
OUT = '/vol/out_13'
ARMS = 'EG'
VARIANT = 'v28'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
MODEL = 'model'
SIZE = 23265352448


def _env(out, **extra):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if not os.path.exists(SERVED):
        os.makedirs(os.path.dirname(SERVED), exist_ok=True)
        os.symlink(f'{V}/{MODEL}', SERVED)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'
    e = dict(os.environ, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp',
             MODEL_DIR=SERVED, OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='24',
             CONCURRENCY='8', TIME_BUDGET_S=str(3 * 3600), HARNESS_VARIANT=VARIANT, ARMS=ARMS, STATES_FILE=STATES)
    e.update(extra)
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke():
    out = '/root/smoke_13'
    env = _env(out, STATES_N='8', FIDELITY_N='0')
    print('python', sys.version, '| gpu', _gpu())
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode)
    if os.path.exists(out + '/summary.json'):
        s = json.load(open(out + '/summary.json'))
        print('rows', s.get('rows'), 'elapsed_s', s.get('elapsed_s'),
              {a: {k: d.get(k) for k in ('n', 'errors', 'with_call', 'prompt_tokens_mean')} for a, d in s.get('by_arm', {}).items()})
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=4 * 3600, cpu=8, memory=49152, max_containers=1)
def full():
    env = _env(OUT)
    os.makedirs(OUT, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': MODEL, 'served_as': SERVED,
               'harness_variant': VARIANT, 'arms': ARMS, 'states_file': STATES,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, open(OUT + '/platform_actual.json', 'w'))

    def committer():  # rows reach the volume as they are written
        while True:
            time.sleep(600)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=committer, daemon=True).start()
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode)
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(OUT + '/pip_freeze.txt', 'w').write(txt)
    vol.commit()
    return p.returncode


@app.local_entrypoint()
def main(mode: str = 'smoke'):
    if mode == 'smoke':
        print('exit', smoke.remote())
    elif mode == 'full':
        print('exit', full.remote())
    else:
        raise SystemExit(f'unknown mode {mode}')
