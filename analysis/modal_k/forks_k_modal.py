"""Experiment E (navigation horizon; prereg/06, DRAFT) on Modal: one A100-80GB, tensor-parallel size 1, Python 3.12.

Same image, package list, wheelhouse and harness install, vLLM settings and served model path as forks_modal.py (the
one-step fork wrapper). Volume `gemma-forks-c`, mounted at /vol:
  /vol/C:/Program Files/Git/{wheelhouse,model,inputs}  as for the one-step runs (inputs: replay.py, agent.yaml,
                                                       sampling.yaml, system.md, the harness wheels)
  /vol/inputs_k     replay_k.py, forks_k_runner.py, population.json, states.jsonl (= analysis/fork_states_d/states.jsonl)
  /vol/snapshots    <task>.tgz for the 42 tasks of the population
  /vol/out_k        results_k.jsonl, checkouts_k.jsonl, versions_k.json, summary_k.json (full mode)

Fidelity (CPU only, no model):  modal run forks_k_modal.py --mode fidelity
Smoke test:                     modal run forks_k_modal.py --mode smoke
Full run (resumable):           modal run --detach forks_k_modal.py --mode full
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-k')
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
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the one-step upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip and vLLM
K_INPUTS = '/vol/inputs_k'
K_SNAPSHOTS = '/vol/snapshots'
K_OUT = '/vol/out_k'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZES = {'model': 23265352448}


def _link(model, served):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if served and not os.path.exists(served):
        os.makedirs(os.path.dirname(served), exist_ok=True)
        os.symlink(model if model.startswith('/') else f'{V}/{model}', served)  # absolute = a path under /vol


def _env(mode, out, model, served, **extra):
    _link(model, served)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    if served and model in SIZES:
        assert os.path.getsize(f'{served}/model.safetensors') == SIZES[model], 'model file incomplete'
    e = dict(os.environ, MODE=mode, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', INPUTS_K_DIR=K_INPUTS,
             SNAPSHOTS_DIR=K_SNAPSHOTS, COMP_DIR='/root/comp', MODEL_DIR=served, OUT_DIR=out,
             AGENT_DIR='/root/agents/base', TP_SIZE='1', CONCURRENCY='16', ACTIVE_STATES='4',
             CHECKOUT_DIR='/tmp/checkouts_k', TIME_BUDGET_S=str(9 * 3600))
    e.update(extra)
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _freeze(out):
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(out + '/pip_freeze_k.txt', 'w').write(txt)
    keep = ('vllm', 'torch', 'google-adk', 'google_adk', 'litellm', 'transformers', 'google-genai', 'google_genai',
            'huggingface', 'tokenizers', 'adk_', 'adk-', 'swegemma')
    return [line for line in txt.splitlines() if line.lower().startswith(keep)]


def _run(env):
    p = subprocess.run([sys.executable, K_INPUTS + '/forks_k_runner.py'], env=env)
    print('exit', p.returncode)
    return p.returncode


@app.function(image=image, volumes={M: vol}, timeout=3 * 3600, cpu=8, memory=32768, max_containers=1)
def fidelity():
    out = '/root/fidelity_k'
    rc = _run(_env('fidelity', out, 'model', ''))
    print('python', sys.version)
    return rc


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke(model: str = 'model', served: str = SERVED):
    out = '/root/smoke_k'
    env = _env('smoke', out, model, served)
    print('python', sys.version, '| gpu', _gpu(), '| wheels', len(os.listdir(V + '/wheelhouse')))
    rc = _run(env)
    if os.path.exists(out):
        print('pinned', _freeze(out))
    return rc


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=20 * 3600, cpu=8, memory=49152,
              max_containers=1)
def full(model: str = 'model', served: str = SERVED):
    out = K_OUT
    env = _env('full', out, model, served)
    os.makedirs(out, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': model, 'served_as': served,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(out + '/platform_actual_k.json', 'w'))

    def committer():  # rows reach the volume as they are written
        while True:
            time.sleep(600)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=committer, daemon=True).start()
    rc = _run(env)
    print('pinned', _freeze(out))
    vol.commit()
    return rc


@app.local_entrypoint()
def main(mode: str = 'smoke', model: str = 'model', served: str = SERVED):
    if mode == 'fidelity':
        print('exit', fidelity.remote())
    elif mode == 'smoke':
        print('exit', smoke.remote(model, served))
    else:
        print('exit', full.remote(model, served))
