"""Pre-registration 10 (DRAFT until frozen) on Modal: the second-model design of pre-registration 05 on a model of
another family. One A100-80GB, tensor-parallel size 1, Python 3.12; the same image, wheelhouse, harness wheels (v28,
as for the other second models) and states as forks_w_modal.py; the runner is analysis/modal_g/forks_10_runner.py,
whose only difference from the one-step runner is that the model server's parser settings come from the environment.

Volume `gemma-forks-c`, mounted at /vol:
  /vol/<model dir>      the model's files, fetched once by `--mode fetch`
  /vol/inputs_g         forks_10_runner.py
  /vol/inputs_d         states.jsonl
  /vol/<out>            results.jsonl, fidelity.jsonl, versions.json, summary.json, pip_freeze.txt

Fetch the weights:  modal run forks_10_modal.py --mode fetch --repo <org/name> --model-dir model_x
Smoke test:         modal run forks_10_modal.py --mode smoke --model-dir model_x
Full run:           modal run --detach forks_10_modal.py --mode full --model-dir model_x --out out_10
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import json
import os
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-10')
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
RUNNER = '/vol/inputs_g/forks_10_runner.py'
STATES = '/vol/inputs_d/states.jsonl'
ARMS = 'A,H,E,RE'  # the second-model arms of pre-registration 05
# The agent's configuration sends a thinking-token budget with every request, and the server refuses that field unless
# it was started with a reasoning configuration. These delimiters are ones the model is not trained to write; with no
# reasoning parser set, nothing is removed from its answer.
REASONING_CONFIG = '{"reasoning_start_str": "<think>", "reasoning_end_str": "</think>"}'
# This model can put many calls in one answer (144 in one smoke answer, 7,590 tokens, 215 seconds). The registered
# outcome reads the first call only, so the answer is ended at the closing tag of its first call.
STOP_SEQUENCES = '["</tool_call>"]'
# Some answers still do not end (two of the first six ran for minutes with the stop string set). The output limit is
# 2,048 tokens instead of the agent's 16,384: 13 times the median answer of the second smoke test (156 tokens).
MAX_OUTPUT_TOKENS = '2048'


def _env(out, model_dir, parser, reasoning, template_kwargs, dtype, **extra):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    e = dict(os.environ, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp',
             MODEL_DIR=f'/vol/{model_dir}', OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='24',
             CONCURRENCY='8', TIME_BUDGET_S=str(8 * 3600), HARNESS_VARIANT='v28', ARMS=ARMS, STATES_FILE=STATES,
             TOOL_CALL_PARSER=parser, REASONING_PARSER=reasoning, CHAT_TEMPLATE_KWARGS=template_kwargs, MODEL_DTYPE=dtype,
             REASONING_CONFIG=REASONING_CONFIG, STOP_SEQUENCES=STOP_SEQUENCES, MAX_OUTPUT_TOKENS=MAX_OUTPUT_TOKENS)
    e.update(extra)
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


@app.function(image=image, volumes={M: vol}, timeout=3600, cpu=4, memory=16384, max_containers=1)
def fetch(repo: str, model_dir: str):
    """Download a model repository from Hugging Face into the volume (no GPU)."""
    from huggingface_hub import snapshot_download

    target = f'/vol/{model_dir}'
    snapshot_download(repo_id=repo, local_dir=target)
    vol.commit()
    files = sorted((os.path.getsize(os.path.join(dp, f)), os.path.relpath(os.path.join(dp, f), target))
                   for dp, _dn, fn in os.walk(target) for f in fn if '.cache' not in dp)
    print('fetched', repo, 'into', target, '|', len(files), 'files,', round(sum(s for s, _ in files) / 1e9, 2), 'GB')
    for size, name in files[-8:]:
        print(' ', round(size / 1e9, 3), 'GB', name)
    return len(files)


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=3600, cpu=8, memory=49152, max_containers=1)
def smoke(model_dir: str, parser: str = 'hermes', reasoning: str = 'none', template_kwargs: str = '', dtype: str = 'auto'):
    out = '/vol/smoke_10'  # on the volume, so that the gate can be computed locally with the frozen interface-failure rule
    if os.path.exists(out):
        for name in os.listdir(out):
            os.remove(os.path.join(out, name))
    env = _env(out, model_dir, parser, reasoning, template_kwargs, dtype, STATES_N='8', FIDELITY_N='0')  # no prompt-size pass in the smoke test
    print('python', sys.version, '| gpu', _gpu(), '| model', model_dir)
    p = subprocess.run([sys.executable, RUNNER], env=env)
    print('exit', p.returncode)
    if os.path.exists(out + '/summary.json'):
        s = json.load(open(out + '/summary.json'))
        print('rows', s.get('rows'), 'elapsed_s', s.get('elapsed_s'),
              {a: {k: d.get(k) for k in ('n', 'errors', 'with_call', 'prompt_tokens_mean')} for a, d in s.get('by_arm', {}).items()})
    vol.commit()
    return p.returncode


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=10 * 3600, cpu=8, memory=49152, max_containers=1)
def full(model_dir: str, out: str = 'out_10', parser: str = 'hermes', reasoning: str = 'none', template_kwargs: str = '',
         dtype: str = 'auto', budget_s: int = 11700):
    out = f'/vol/{out}'
    # budget_s: the runner starts no new replay after this many seconds (3.25 hours keeps the run near its budget);
    # states are taken in a fixed shuffled order, so a run cut by the budget is a random subset of states.
    # 16 requests at a time (the other runs sent 8): this model's long answers hold a slot for about a minute each.
    env = _env(out, model_dir, parser, reasoning, template_kwargs, dtype, TIME_BUDGET_S=str(budget_s), CONCURRENCY='16')
    os.makedirs(out, exist_ok=True)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': model_dir,
               'model_server': {'tool_call_parser': parser, 'reasoning_parser': reasoning,
                                'chat_template_kwargs': template_kwargs, 'dtype': dtype, 'reasoning_config': REASONING_CONFIG},
               'stop_sequences': STOP_SEQUENCES, 'max_output_tokens': MAX_OUTPUT_TOKENS, 'time_budget_s': budget_s,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, open(out + '/platform_actual.json', 'w'))

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
    open(out + '/pip_freeze.txt', 'w').write(txt)
    vol.commit()
    return p.returncode


@app.local_entrypoint()
def main(mode: str = 'smoke', repo: str = '', model_dir: str = '', out: str = 'out_10', parser: str = 'hermes',
         reasoning: str = 'none', template_kwargs: str = '', dtype: str = 'auto'):
    if mode == 'fetch':
        print('files', fetch.remote(repo, model_dir))
    elif mode == 'smoke':
        print('exit', smoke.remote(model_dir, parser, reasoning, template_kwargs, dtype))
    elif mode == 'full':
        print('exit', full.remote(model_dir, out, parser, reasoning, template_kwargs, dtype))
    else:
        raise SystemExit(f'unknown mode {mode}')
