"""Pre-registration 09 on Modal: fresh episodes, graph tools as shipped or with addresses; one A100-80GB, Python 3.12.

Same image, package list, wheelhouse, vLLM settings and served model path as forks_g_modal.py. Newest harness wheels
(`latest`). Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_g           replay_k.py, forks_09_runner.py, population.json, states.jsonl, fresh_states.jsonl
  /vol/inputs_g/spans     <task>.json: the addresses (analysis/make_spans_g.py)
  /vol/snapshots          <task>.tgz for the 106 traced tasks
  /vol/comp               graphs/ and embeddings/ of the competition data
  /vol/out_09             results_09.jsonl, checkouts_09.jsonl, versions_09.json, summary_09.json

Smoke test:           modal run forks_09_modal.py --mode smoke
Full run (resumable): modal run --detach forks_09_modal.py --mode full
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-09')
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
RUNNER = INPUTS_G + '/forks_09_runner.py'
OUT = '/vol/out_09'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZE = 23265352448


def _env(mode, out, variant):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if not os.path.exists(SERVED):
        os.makedirs(os.path.dirname(SERVED), exist_ok=True)
        os.symlink(f'{V}/model', SERVED)
    assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'
    return dict(os.environ, MODE=mode, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', INPUTS_G_DIR=INPUTS_G,
                SNAPSHOTS_DIR='/vol/snapshots', COMP_DIR='/vol/comp', MODEL_DIR=SERVED, OUT_DIR=out,
                AGENT_DIR='/root/agents/base', TP_SIZE='1', CONCURRENCY='16', ACTIVE_STATES='4',
                CHECKOUT_DIR='/tmp/checkouts_09', TIME_BUDGET_S=str(6 * 3600), HARNESS_VARIANT=variant, PARTS='fresh')


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _freeze(out):
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(out + '/pip_freeze_09.txt', 'w').write(txt)
    keep = ('vllm', 'torch', 'google-adk', 'google_adk', 'litellm', 'transformers', 'google-genai', 'google_genai',
            'huggingface', 'tokenizers', 'adk_', 'adk-', 'swegemma')
    return [line for line in txt.splitlines() if line.lower().startswith(keep)]


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke(variant: str = 'latest'):
    out = '/root/smoke_09'
    env = _env('smoke', out, variant)
    print('python', sys.version, '| gpu', _gpu(), '| variant', variant)
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode)
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=10 * 3600, cpu=8, memory=49152, max_containers=1)
def full(variant: str = 'latest'):
    env = _env('full', OUT, variant)
    os.makedirs(OUT, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'served_as': SERVED, 'harness_variant': variant,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, open(OUT + '/platform_actual_09.json', 'w'))

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
    print('pinned', _freeze(OUT))
    vol.commit()
    return p.returncode


@app.local_entrypoint()
def main(mode: str = 'smoke', variant: str = 'latest'):
    if mode == 'smoke':
        print('exit', smoke.remote(variant))
    elif mode == 'full':
        print('exit', full.remote(variant))
    else:
        raise SystemExit(f'unknown mode {mode}')
