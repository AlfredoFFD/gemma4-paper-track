"""Pre-registration 14 on Modal: whole runs scored by the tests, the harness as shipped (N) or with two changes (NAF).

Launcher for wholerun_runner.py (read its header first). One A100-80GB, Python 3.12; the image, package list, harness
wheels (`latest`), vLLM settings and served model path are those of forks_09_modal.py. Added to that image, in layers
after its own: git, patch and pigz (the harness commits a baseline, diffs and applies patches with git; the 09 image
had none), the git identity of the competition's sandbox image, and the packages the tasks' tests need
(TEST_PACKAGES: the subprocess sandbox installs nothing itself and runs the tests on the image's packages).

Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_h           wholerun_runner.py, tasks.jsonl, imp.py (the shim of the competition's sandbox image)
  /vol/inputs_g           spans/<task>.json (the addresses), forks_09_runner.py (the two changes are compared with
                          it), fresh_states.jsonl (the 106 tasks of pre-registration 09)
  /vol/snapshots          <task>.tgz for the 129 tasks
  /vol/comp               graphs/ and embeddings/ of the competition data
  /vol/out_14             results (layout in wholerun_runner.py)

Before launching, from the repository root (again after any change to the runner):
  modal volume put -f gemma-forks-c analysis/modal_h/wholerun_runner.py /inputs_h/wholerun_runner.py
  modal volume put -f gemma-forks-c data/tasks.jsonl /inputs_h/tasks.jsonl
  modal volume put -f gemma-forks-c data/docker/imp.py /inputs_h/imp.py

Validate (no GPU):    modal run analysis/modal_h/wholerun_modal.py --mode validate
                      every task with a snapshot through the harness's test phase with its reference patch and with
                      an empty patch; writes /vol/out_14/validate/{validate.jsonl,tasks_ok.txt,summary_validate.json}
Plumbing (no GPU):    modal run analysis/modal_h/wholerun_modal.py --mode check      (scripted model, 3 tasks)
Smoke test:           modal run analysis/modal_h/wholerun_modal.py --mode smoke      (3 tasks, both conditions)
Full run (resumable): modal run --detach analysis/modal_h/wholerun_modal.py --mode full
                      [--condition both|N|NAF] [--seed 1] [--tasks-file /vol/out_14/validate/tasks_ok.txt]
                      [--shard 0/2] [--limit 0] [--concurrency 16] [--hours 6] [--retry-infra]
                      (--tasks-file fresh: the 106 tasks of pre-registration 09 instead of the validated list)
Two containers splitting the work: the same command twice, with --shard 0/2 and --shard 1/2; afterwards
`python analysis/modal_h/wholerun_runner.py merge <downloaded out_14>` joins the shards.
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-wholerun-14')
vol = modal.Volume.from_name('gemma-forks-c')
# The first five: what the public whole runs' sandbox had beside the hosted notebook image (their traces print pytest
# 8.4.2 with the plugins httpbin 2.1.0 and inline-snapshot 0.35.4; their notebook installs dirty-equals and trustme).
# orjson and ujson: fastapi's response classes need them (two reference patches failed without them). Pygments 2.19.2:
# the version rich's lock file pins in these snapshots; with the image's 2.21.0 three rich reference patches failed on
# syntax-highlighting assertions. Every resolved version is in pip_freeze_14.txt of each launch (on Nov 10, 2026 the
# two unpinned names resolved to orjson 3.13.0 and ujson 6.1.0). Against the environment of run 09 this adds 19
# packages and changes one version (Pygments 2.21.0 to 2.19.2).
TEST_PACKAGES = ('pytest==8.4.2', 'inline-snapshot==0.35.4', 'pytest-httpbin==2.1.0', 'dirty-equals==0.11',
                 'trustme==1.2.1', 'orjson', 'ujson', 'Pygments==2.19.2')
image = (
    modal.Image.from_registry('nvidia/cuda:12.8.0-devel-ubuntu22.04', add_python='3.12')
    .entrypoint([])
    .pip_install('vllm==0.19.1', 'litellm==1.82.4', 'google-adk==1.36.1', 'huggingface-hub>=1.5.0,<2.0',
                 # declared dependencies of the harness wheels, which the runner installs with --no-deps
                 'docker>=7.0.0', 'cachetools>=5.0.0', 'networkx>=3.0', 'python-dotenv>=1.0.0', 'rich>=13.0',
                 'pandas>=2.0.0', 'accelerate', 'scikit-learn>=1.3.0', 'pyyaml>=6.0')
    # ---- added for whole runs; the layers above are those of forks_09_modal.py
    .apt_install('git', 'patch', 'pigz')
    .run_commands('git config --system user.email "agent@eval"', 'git config --system user.name "Agent"',
                  'git config --system init.defaultBranch main')
    .pip_install(*TEST_PACKAGES)
)
M = '/vol'
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the first upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip and vLLM
INPUTS_G = '/vol/inputs_g'
INPUTS_H = '/vol/inputs_h'
RUNNER = INPUTS_H + '/wholerun_runner.py'
OUT = '/vol/out_14'
TASKS_OK = OUT + '/validate/tasks_ok.txt'  # written by mode validate: the task list of the full run, in run order
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZE = 23265352448


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _launch(mode, variant, gpu=True, commit_every=600, **settings):
    """Run the driver; the rows reach the volume as they are written."""
    launch = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '_' + mode
    if settings.get('SHARD'):
        launch += '_shard' + settings['SHARD'].replace('/', 'of')
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if gpu:
        if not os.path.exists(SERVED):
            os.makedirs(os.path.dirname(SERVED), exist_ok=True)
            os.symlink(f'{V}/model', SERVED)
        assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'
    if settings.get('TASKS_FILE') is None:  # smoke and check: the validated list once it exists
        settings['TASKS_FILE'] = TASKS_OK if os.path.exists(TASKS_OK) else 'fresh'
    env = dict(os.environ, MODE=mode, LAUNCH_ID=launch, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs',
               INPUTS_G_DIR=INPUTS_G, INPUTS_H_DIR=INPUTS_H, SNAPSHOTS_DIR='/vol/snapshots', COMP_DIR='/vol/comp',
               MODEL_DIR=SERVED if gpu else '', OUT_DIR=OUT, AGENT_DIR='/root/agents/base', TP_SIZE='1',
               HARNESS_VARIANT=variant, **{k: str(v) for k, v in settings.items()})
    d = f'{OUT}/launches/{launch}'
    os.makedirs(d, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu() if gpu else 'none', 'python': sys.version, 'served_as': SERVED if gpu else None,
               'harness_variant': variant, 'launch': launch, 'mode': mode, 'settings': {k: str(v) for k, v in settings.items()},
               'cpus': os.cpu_count(), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(d + '/platform_actual_14.json', 'w'))
    print('python', sys.version, '| gpu', _gpu() if gpu else 'none', '| variant', variant, '| launch', launch, flush=True)

    def committer():
        while True:
            time.sleep(commit_every)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=committer, daemon=True).start()
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode, flush=True)
    vol.commit()
    return p.returncode


@app.function(image=image, volumes={M: vol}, timeout=3600, cpu=8, memory=32768, max_containers=1)
def validate(variant: str = 'latest'):
    """No GPU: every task with a snapshot through the harness's test phase, with its reference patch (must resolve)
    and with an empty patch (must not). Writes validate/validate.jsonl, tasks_ok.txt and summary_validate.json."""
    return _launch('validate', variant, gpu=False, commit_every=120, TASKS_FILE='fresh', VALIDATE_CONCURRENCY=8)


@app.function(image=image, volumes={M: vol}, timeout=1800, cpu=8, memory=32768, max_containers=1)
def check(variant: str = 'latest'):
    """No GPU: the whole pipeline on the smoke tasks, both conditions, with a scripted model in place of the server."""
    return _launch('check', variant, gpu=False, commit_every=120, CONDITIONS='N,NAF', SEED=1, CONCURRENCY=6)


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=1800, cpu=8, memory=49152, max_containers=1)
def smoke(seed: int = 1, variant: str = 'latest'):
    """3 tasks, both conditions. Sessions still running 26 minutes after the start are stopped."""
    return _launch('smoke', variant, commit_every=120, CONDITIONS='N,NAF', SEED=seed, CONCURRENCY=6, HARD_STOP_S=26 * 60)


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=10 * 3600, cpu=16, memory=65536, max_containers=1)
def full(condition: str = 'both', seed: int = 1, tasks_file: str = TASKS_OK, shard: str = '', variant: str = 'latest',
         limit: int = 0, concurrency: int = 16, hours: float = 6.0, retry_infra: bool = False):
    """Resumable. No new session starts after `hours` (at most 9: the function ends after 10)."""
    return _launch('full', variant, CONDITIONS='N,NAF' if condition == 'both' else condition, SEED=seed,
                   TASKS_FILE=tasks_file, SHARD=shard, LIMIT_TASKS=limit, CONCURRENCY=concurrency,
                   TIME_BUDGET_S=int(hours * 3600), RETRY_INFRA=1 if retry_infra else 0)


@app.local_entrypoint()
def main(mode: str = 'smoke', condition: str = 'both', seed: int = 1, tasks_file: str = TASKS_OK, shard: str = '',
         variant: str = 'latest', limit: int = 0, concurrency: int = 16, hours: float = 6.0, retry_infra: bool = False):
    if mode == 'validate':
        print('exit', validate.remote(variant))
    elif mode == 'check':
        print('exit', check.remote(variant))
    elif mode == 'smoke':
        print('exit', smoke.remote(seed, variant))
    elif mode == 'full':
        assert condition in ('both', 'N', 'NAF') and hours <= 9, (condition, hours)
        print('exit', full.remote(condition, seed, tasks_file, shard, variant, limit, concurrency, hours, retry_infra))
    else:
        raise SystemExit(f'unknown mode {mode}')
