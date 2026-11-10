"""Experiment F (pre-registration 07) on Modal: fork replays with the history's tool results rendered as the
original runs' harness delivered them (arms ending in 'w'). A copy of analysis/modal/forks_modal.py that runs
analysis/modal_w/forks_w_runner.py (uploaded to /inputs_w in the volume) instead of the experiment C/D runner.

One A100-80GB, tensor-parallel size 1, Python 3.12.

Volume layout (root of the volume, called R below):
  R/inputs      replay.py, states file(s), agent config, harness wheels, forks_modal_runner.py
  R/wheelhouse  the competition wheelhouse (cp312 wheels)
  R/<model>     model directory (default "model")
  R/<out>       output directory (default "out"): results.jsonl, fidelity.jsonl, versions.json, summary.json

Smoke test:  modal run forks_modal.py --mode smoke
Full run:    modal run --detach forks_modal.py --mode full
Other runs:  add --model <dir> --out <dir> --arms A,H,E --states <file> --served <path>
             (--model and --states may be absolute container paths under /vol, e.g. /vol/model_12b and
             /vol/inputs_d/states.jsonl; from Git Bash prefix the command with MSYS_NO_PATHCONV=1)
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-w')
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
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip and vLLM
RUNNER = '/vol/inputs_w/forks_w_runner.py'
# The model is served under the same path string as on the hosted notebooks, so the model name the agent
# framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZES = {'model': 23265352448}


def _link(model, served):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if not os.path.exists(served):
        os.makedirs(os.path.dirname(served), exist_ok=True)
        os.symlink(model if model.startswith('/') else f'{V}/{model}', served)  # absolute = a path under /vol


def _env(out, model, served, arms, states, experiment, **extra):
    _link(model, served)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    if model in SIZES:
        assert os.path.getsize(f'{served}/model.safetensors') == SIZES[model], 'model file incomplete'
    e = dict(os.environ, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp',
             MODEL_DIR=served, OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='24',
             CONCURRENCY='8', TIME_BUDGET_S=str(19 * 3600))
    if arms:
        e['ARMS'] = arms
    if states:
        e['STATES_FILE'] = states
    if experiment:
        e['EXPERIMENT'] = experiment
    e.update(extra)
    return e


def _gpu():
    return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                          capture_output=True, text=True).stdout.strip()


def _freeze(out):
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(out + '/pip_freeze.txt', 'w').write(txt)
    keep = ('vllm', 'torch', 'google-adk', 'google_adk', 'litellm', 'transformers', 'google-genai', 'google_genai',
            'huggingface', 'tokenizers', 'adk_', 'adk-', 'swegemma')
    return [line for line in txt.splitlines() if line.lower().startswith(keep)]


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke(model: str = 'model', served: str = SERVED, arms: str = '', states: str = '', experiment: str = ''):
    out = '/root/smoke'
    env = _env(out, model, served, arms, states, experiment, STATES_N='8', FIDELITY_N='6')
    print('python', sys.version, '| gpu', _gpu(), '| wheels', len(os.listdir(V + '/wheelhouse')))
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode)
    if os.path.exists(out):
        print('pinned', _freeze(out))
    if os.path.exists(out + '/versions.json'):
        v = json.load(open(out + '/versions.json'))
        print('versions', {k: v[k] for k in v if k != 'wheelhouse_files'})
    if os.path.exists(out + '/summary.json'):
        s = json.load(open(out + '/summary.json'))
        print('fidelity', json.dumps(s.get('fidelity')))
        print('fidelity_w', json.dumps(s.get('fidelity_w')))
        print('rows', s.get('rows'), 'elapsed_s', s.get('elapsed_s'),
              {a: {k: d.get(k) for k in ('n', 'errors', 'prompt_tokens_mean')} for a, d in s.get('by_arm', {}).items()})
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=20 * 3600, cpu=8, memory=49152,
              max_containers=1)
def full(model: str = 'model', out: str = 'out', served: str = SERVED, arms: str = '', states: str = '',
         experiment: str = ''):
    env = _env(f'{V}/{out}', model, served, arms, states, experiment)
    out = f'{V}/{out}'
    os.makedirs(out, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': model, 'served_as': served,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(out + '/platform_actual.json', 'w'))

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
    print('pinned', _freeze(out))
    vol.commit()
    return p.returncode


@app.local_entrypoint()
def main(mode: str = 'smoke', model: str = 'model', out: str = 'out', served: str = SERVED, arms: str = '',
         states: str = '', experiment: str = ''):
    if mode == 'smoke':
        print('exit', smoke.remote(model, served, arms, states, experiment))
    else:
        print('exit', full.remote(model, out, served, arms, states, experiment))
