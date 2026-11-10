"""Experiment G (pre-registration 08) on Modal: one A100-80GB per function, tensor-parallel size 1, Python 3.12.

Same image, package list, wheelhouse, vLLM settings and served model path as the earlier wrappers (forks_k_modal.py,
forks_w_modal.py). The harness wheels are the newest ones on disk (`latest`: adk_submission 0.2.13, swegemma 0.2.11,
dated Oct 12) unless --variant v28 is given. Volume `gemma-forks-c`, mounted at /vol:
  /vol/C:/Program Files/Git/{wheelhouse,model,inputs}  as for the earlier runs (inputs: replay.py, agent.yaml,
                                                       sampling.yaml, system.md, the harness wheels of both variants)
  /vol/inputs_g     replay_k.py, forks_g_runner.py, population.json, states.jsonl (= analysis/fork_states_d/states.jsonl),
                    population_g.json, fresh_states.jsonl
  /vol/inputs_w     forks_w_runner.py (the one-step runner of pre-registration 07, unchanged)
  /vol/inputs_d     states.jsonl
  /vol/snapshots    <task>.tgz for the 106 traced tasks
  /vol/out_g        parts "fresh" and "fix": results_g.jsonl, checkouts_g.jsonl, versions_g.json, summary_g.json
  /vol/out_g_onestep  part "one step": results.jsonl, fidelity.jsonl, fidelity_w.jsonl, versions.json, summary.json

Smoke test (fresh and fix):   modal run forks_g_modal.py --mode smoke
Smoke test (one step):        modal run forks_g_modal.py --mode onestep-smoke
Full runs (resumable):        modal run --detach forks_g_modal.py --mode full
                              modal run --detach forks_g_modal.py --mode onestep
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-g')
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
G_INPUTS = '/vol/inputs_g'
G_SNAPSHOTS = '/vol/snapshots'
G_OUT = '/vol/out_g'
S_OUT = '/vol/out_g_onestep'
S_RUNNER = '/vol/inputs_w/forks_w_runner.py'
S_STATES = '/vol/inputs_d/states.jsonl'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
MODEL = 'model'
SIZE = 23265352448


def _link():
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if not os.path.exists(SERVED):
        os.makedirs(os.path.dirname(SERVED), exist_ok=True)
        os.symlink(f'{V}/{MODEL}', SERVED)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'


def _env_g(mode, out, variant, parts):
    _link()
    return dict(os.environ, MODE=mode, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', INPUTS_G_DIR=G_INPUTS,
                SNAPSHOTS_DIR=G_SNAPSHOTS, COMP_DIR='/root/comp', MODEL_DIR=SERVED, OUT_DIR=out,
                AGENT_DIR='/root/agents/base', TP_SIZE='1', CONCURRENCY='16', ACTIVE_STATES='4',
                CHECKOUT_DIR='/tmp/checkouts_g', TIME_BUDGET_S=str(8 * 3600), HARNESS_VARIANT=variant, PARTS=parts)


def _env_s(out, variant, arms, **extra):
    _link()
    e = dict(os.environ, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp',
             MODEL_DIR=SERVED, OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='24',
             CONCURRENCY='8', TIME_BUDGET_S=str(8 * 3600), HARNESS_VARIANT=variant, ARMS=arms, STATES_FILE=S_STATES)
    e.update(extra)
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _freeze(out, name):
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(f'{out}/{name}', 'w').write(txt)
    keep = ('vllm', 'torch', 'google-adk', 'google_adk', 'litellm', 'transformers', 'google-genai', 'google_genai',
            'huggingface', 'tokenizers', 'adk_', 'adk-', 'swegemma')
    return [line for line in txt.splitlines() if line.lower().startswith(keep)]


def _committer():  # rows reach the volume as they are written
    def loop():
        while True:
            time.sleep(600)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=loop, daemon=True).start()


def _platform(out, name, variant):
    os.makedirs(out, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': MODEL, 'served_as': SERVED,
               'harness_variant': variant, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(f'{out}/{name}', 'w'))


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke(variant: str = 'latest', parts: str = 'fresh,fix'):
    out = '/root/smoke_g'
    env = _env_g('smoke', out, variant, parts)
    print('python', sys.version, '| gpu', _gpu(), '| wheels', len(os.listdir(V + '/wheelhouse')), '| variant', variant)
    p = subprocess.run([sys.executable, G_INPUTS + '/forks_g_runner.py'], env=env)
    print('exit', p.returncode)
    if os.path.exists(out):
        print('pinned', _freeze(out, 'pip_freeze_g.txt'))
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=12 * 3600, cpu=8, memory=49152, max_containers=1)
def full(variant: str = 'latest', parts: str = 'fresh,fix'):
    env = _env_g('full', G_OUT, variant, parts)
    _platform(G_OUT, 'platform_actual_g.json', variant)
    _committer()
    p = subprocess.run([sys.executable, G_INPUTS + '/forks_g_runner.py'], env=env)
    print('exit', p.returncode)
    print('pinned', _freeze(G_OUT, 'pip_freeze_g.txt'))
    vol.commit()
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def onestep_smoke(variant: str = 'latest', arms: str = 'H,E'):
    out = '/root/smoke_g_onestep'
    env = _env_s(out, variant, arms, STATES_N='8', FIDELITY_N='6')
    print('python', sys.version, '| gpu', _gpu(), '| variant', variant)
    p = subprocess.run([sys.executable, S_RUNNER], env=env)
    print('exit', p.returncode)
    if os.path.exists(out + '/summary.json'):
        s = json.load(open(out + '/summary.json'))
        print('fidelity', json.dumps(s.get('fidelity')))
        print('fidelity_w', json.dumps(s.get('fidelity_w')))
        print('rows', s.get('rows'), 'elapsed_s', s.get('elapsed_s'),
              {a: {k: d.get(k) for k in ('n', 'errors', 'prompt_tokens_mean')} for a, d in s.get('by_arm', {}).items()})
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=10 * 3600, cpu=8, memory=49152, max_containers=1)
def onestep(variant: str = 'latest', arms: str = 'H,E'):
    env = _env_s(S_OUT, variant, arms)
    _platform(S_OUT, 'platform_actual.json', variant)
    _committer()
    p = subprocess.run([sys.executable, S_RUNNER], env=env)
    print('exit', p.returncode)
    print('pinned', _freeze(S_OUT, 'pip_freeze.txt'))
    vol.commit()
    return p.returncode


@app.local_entrypoint()
def main(mode: str = 'smoke', variant: str = 'latest', parts: str = 'fresh,fix', arms: str = 'H,E'):
    if mode == 'smoke':
        print('exit', smoke.remote(variant, parts))
    elif mode == 'full':
        print('exit', full.remote(variant, parts))
    elif mode == 'onestep-smoke':
        print('exit', onestep_smoke.remote(variant, arms))
    elif mode == 'onestep':
        print('exit', onestep.remote(variant, arms))
    else:
        raise SystemExit(f'unknown mode {mode}')
