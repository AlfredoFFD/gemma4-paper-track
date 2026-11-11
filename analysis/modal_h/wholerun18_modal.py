"""Experiment 18 on Modal: whole runs scored by the tests, the agent told every place the fix changes (ON, OA), and a
control (N) in the same launch.

A copy of wholerun_modal.py (pre-registration 14) with the smallest change: the runner is wholerun18_runner.py (read
its header first), the default conditions are N, ON and OA with seed 2, the default task list is the 40 tasks of
analysis/oracle_18/tasks_18.txt in its line order, the output root is /vol/out_18, and the notes, the manifest and
the stored records of 14 reach the container on the volume under /vol/inputs_18. The image, package list, harness
wheels (`latest`), vLLM settings, served model path, GPU and per-container load are those of 14: as 14, the full
run is TWO containers, each with half of the task list (--shard 0/2 and --shard 1/2, required), 8 sessions at a time
each (--concurrency 8 by default). No new session starts after --hours (default 1.5, at most 1.6); the function ends
after 2.75 hours (a session is stopped by the runner's guard after 45 minutes at most). Afterwards
`py -I -X utf8 analysis/store_18.py --pull <empty dir>` downloads both shards, merges them and stores the runs.

Volume `gemma-forks-c`, mounted at /vol (inputs_h, inputs_g, snapshots and comp as in 14, read only here):
  /vol/inputs_18          wholerun18_runner.py, tasks_18.txt, manifest.json, oracle/<task>.json (the notes,
                          built by analysis/make_oracle_18.py from the competition data), versions_14.json (the stored
                          versions file of the runs of 14), validate_14/{summary_validate.json,tasks_ok.txt} (the
                          validation of 14, copies of analysis/results/14/validate/)
  /vol/out_18             results (layout in wholerun_runner.py; file names with 18 in place of 14)

Before launching, from the repository root (again after any change to the runner or the notes):
  modal volume put -f gemma-forks-c analysis/modal_h/wholerun18_runner.py /inputs_18/wholerun18_runner.py
  modal volume put -f gemma-forks-c analysis/oracle_18/tasks_18.txt /inputs_18/tasks_18.txt
  modal volume put -f gemma-forks-c analysis/oracle_18/manifest.json /inputs_18/manifest.json
  modal volume put -f gemma-forks-c data/cache/oracle_18 /inputs_18/oracle
  modal volume put -f gemma-forks-c analysis/results/14/N/seed1/versions_14_shard0of2.json /inputs_18/versions_14.json
  modal volume put -f gemma-forks-c analysis/results/14/validate/summary_validate.json /inputs_18/validate_14/summary_validate.json
  modal volume put -f gemma-forks-c analysis/results/14/validate/tasks_ok.txt /inputs_18/validate_14/tasks_ok.txt

Plumbing (no GPU):    modal run analysis/modal_h/wholerun18_modal.py --mode check      (scripted model, 3 tasks, N, ON, OA)
Smoke test:           modal run analysis/modal_h/wholerun18_modal.py --mode smoke      (3 tasks, N, ON, OA)
Full run (resumable): modal run --detach analysis/modal_h/wholerun18_modal.py --mode full --shard 0/2
                      modal run --detach analysis/modal_h/wholerun18_modal.py --mode full --shard 1/2
                      [--condition N,ON,OA] [--seed 2] [--tasks-file /vol/inputs_18/tasks_18.txt] [--limit 0]
                      [--concurrency 8] [--hours 1.5] [--retry-infra]
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-wholerun-18')
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
INPUTS_18 = '/vol/inputs_18'
RUNNER = INPUTS_18 + '/wholerun18_runner.py'
OUT = '/vol/out_18'
TASKS_18 = INPUTS_18 + '/tasks_18.txt'  # the 40 tasks of experiment 18, in run order
VALIDATED_14 = INPUTS_18 + '/validate_14/summary_validate.json'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
SIZE = 23265352448
MAX_HOURS = 1.6
SHARDS = ('0/2', '1/2')  # the layout of 14: two containers, half of the tasks each


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
    if settings.get('TASKS_FILE') is None:  # smoke and check: the 40 tasks of experiment 18
        settings['TASKS_FILE'] = TASKS_18
    env = dict(os.environ, MODE=mode, LAUNCH_ID=launch, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs',
               INPUTS_G_DIR=INPUTS_G, INPUTS_H_DIR=INPUTS_H, INPUTS_18_DIR=INPUTS_18, VALIDATE_SUMMARY=VALIDATED_14,
               SNAPSHOTS_DIR='/vol/snapshots', COMP_DIR='/vol/comp',
               MODEL_DIR=SERVED if gpu else '', OUT_DIR=OUT, AGENT_DIR='/root/agents/base', TP_SIZE='1',
               HARNESS_VARIANT=variant, **{k: str(v) for k, v in settings.items()})
    d = f'{OUT}/launches/{launch}'
    os.makedirs(d, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu() if gpu else 'none', 'python': sys.version, 'served_as': SERVED if gpu else None,
               'harness_variant': variant, 'launch': launch, 'mode': mode, 'settings': {k: str(v) for k, v in settings.items()},
               'cpus': os.cpu_count(), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(d + '/platform_actual_18.json', 'w'))
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


@app.function(image=image, volumes={M: vol}, timeout=1500, cpu=8, memory=32768, max_containers=1)
def check(variant: str = 'latest'):
    """No GPU: the whole pipeline on the smoke tasks, N, ON and OA, with a scripted model in place of the server."""
    return _launch('check', variant, gpu=False, commit_every=120, CONDITIONS='N,ON,OA', SEED=2, CONCURRENCY=9)


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=1800, cpu=8, memory=49152, max_containers=1)
def smoke(seed: int = 2, variant: str = 'latest'):
    """3 tasks, N, ON and OA (9 sessions at once). Sessions still running 26 minutes after the start are stopped."""
    return _launch('smoke', variant, commit_every=120, CONDITIONS='N,ON,OA', SEED=seed, CONCURRENCY=9, HARD_STOP_S=26 * 60)


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=int(2.75 * 3600), cpu=16, memory=65536, max_containers=2)
def full(condition: str = 'N,ON,OA', seed: int = 2, tasks_file: str = TASKS_18, shard: str = '', variant: str = 'latest',
         limit: int = 0, concurrency: int = 8, hours: float = 1.5, retry_infra: bool = False):
    """Resumable. One shard. No new session starts after `hours` (at most 1.6: the function ends after 2.75)."""
    assert hours <= MAX_HOURS and shard in SHARDS, (hours, shard)
    return _launch('full', variant, CONDITIONS=condition, SEED=seed,
                   TASKS_FILE=tasks_file, SHARD=shard, LIMIT_TASKS=limit, CONCURRENCY=concurrency,
                   TIME_BUDGET_S=int(hours * 3600), RETRY_INFRA=1 if retry_infra else 0)


@app.local_entrypoint()
def main(mode: str = 'smoke', condition: str = 'N,ON,OA', seed: int = 2, tasks_file: str = TASKS_18, shard: str = '',
         variant: str = 'latest', limit: int = 0, concurrency: int = 8, hours: float = 1.5, retry_infra: bool = False):
    if mode == 'check':
        print('exit', check.remote(variant))
    elif mode == 'smoke':
        print('exit', smoke.remote(seed, variant))
    elif mode == 'full':
        conds = [c for c in condition.split(',') if c]
        assert conds and all(c in ('N', 'NAF', 'ON', 'OA') for c in conds) and hours <= MAX_HOURS, (condition, hours)
        assert shard in SHARDS, f'--shard must be one of {SHARDS} (the full run is two containers, one per shard)'
        print('exit', full.remote(','.join(conds), seed, tasks_file, shard, variant, limit, concurrency, hours, retry_infra))
    else:
        raise SystemExit(f'unknown mode {mode} (validate is not part of experiment 18: it uses the validation of 14)')
