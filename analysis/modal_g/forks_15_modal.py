"""Pre-registration 15 on Modal: one-step replays of the states of analysis/make_states_s.py under three arms: the
agent's own numbered search result as recorded (S), the same result with its line numbers removed (S0), and S0 with
the removed numbers handed back in a note (S0N). Gemma-4-31B, the harness wheels of Sep 30 (v28), as in
pre-registrations 04, 05, 12 and 13.

The runner is the frozen one-step runner of pre-registration 07 (/vol/inputs_w/forks_w_runner.py, unchanged). One
A100-80GB, tensor-parallel size 1, Python 3.12, the same image as the other runs.

The runner replays every record of its states file under every arm it is given, for seeds 1 to 3, in the order of
its own seeded shuffle, and it leaves out the (record, arm, seed) cells that its results file already holds. The
states file has one record per (state, arm), each with its own history. So, before the runner starts, this script
  - writes the records for the runner in an order that the runner's shuffle turns into the registered order: the
    records S and S0 of every state first, then the records S0N (a budget stop then leaves S and S0 whole);
  - gives the runner two arms: A replays a record as it stands (records S and S0), S0N adds the record's note
    (records S0N);
  - enters every cell outside the design in the results file as finished, marked `skip`: a record S or S0 under
    S0N, a record S0N under A and, in the smoke test, seeds 2 and 3. After the run these lines are removed from
    results.jsonl; the runner's own summary.json counted them as rows.
No new replay starts once 50 minutes of the runner's clock have passed (its start-up, five to six minutes, included).
The runner's own prompt-size check is off (FIDELITY_N=0): arm S is the recorded history itself, so its prompt size is
compared with the logged size on every state, from the results.

Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_w/forks_w_runner.py   the frozen runner
  /vol/inputs_g/states_s.jsonl      analysis/fork_states_s/states.jsonl (built by analysis/make_states_s.py)
  /vol/out_15                       results.jsonl, versions.json, summary.json, pip_freeze.txt, platform_actual.json,
                                    vllm_server.log, fidelity.jsonl and fidelity_w.jsonl (both empty)
  /vol/out_15_smoke                 the smoke test: 8 states, every arm, seed 1 (24 replays)

Upload:      modal volume put gemma-forks-c analysis/fork_states_s/states.jsonl /inputs_g/states_s.jsonl
Smoke test:  modal run forks_15_modal.py --mode smoke
Full run:    modal run --detach forks_15_modal.py --mode full
From Git Bash prefix every command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8.
"""
import hashlib
import json
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-15')
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
STATES = '/vol/inputs_g/states_s.jsonl'
OUT = '/vol/out_15'
SMOKE_OUT = '/vol/out_15_smoke'
RUNNER_STATES = '/root/states_15/runner_states.jsonl'   # the records in the order the runner needs; stays in the container
ARMS = 'A,S0N'                                           # the runner's arms
RUNNER_ARM = {'S': 'A', 'S0': 'A', 'S0N': 'S0N'}         # the runner's arm for each record
RUNNER_SEEDS = (1, 2, 3)                                 # fixed inside the runner
BUDGET_S = 50 * 60                                       # no new replay after this much of the runner's clock
SMOKE_STATES, SMOKE_SEEDS = 8, (1,)
SMOKE_BUDGET_S, SMOKE_LIMIT_S = 570, 660                 # the smoke test: no new replay after 9.5 minutes, stopped at 11
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
             MODEL_DIR=SERVED, OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='0',
             CONCURRENCY='8', TIME_BUDGET_S=str(BUDGET_S), HARNESS_VARIANT=VARIANT, ARMS=ARMS, STATES_FILE=RUNNER_STATES)
    e.update(extra)
    return e


def _gpu():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'none'


def _cell(r):
    return (r['task'], r['run'], r['fork'], r['arm'], r['seed'])


def _read_rows(path):
    """(line, row) for every whole line of a results file, and whether the file needs no repair; a line cut short
    by a stop is dropped."""
    out, whole = [], True
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try:
                row = json.loads(line)
            except ValueError:
                whole = False
                continue
            if not line.endswith('\n'):
                whole, line = False, line + '\n'
            out.append((line, row))
    return out, whole


def _write_rows(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def _plan(out, n_states=0, seeds=RUNNER_SEEDS, states=STATES, runner_states=RUNNER_STATES):
    """Write the runner's states file and enter the cells outside the design as finished.

    Returns (the records in the registered order, the number of cells entered, the md5 of the states file read).
    The states file lists its states by the sha1 of their id, smallest first; n_states keeps the first ones.
    """
    raw = open(states, 'rb').read()
    recs = [json.loads(l) for l in raw.decode('utf-8').splitlines()]
    ids = list(dict.fromkeys(r['state_id'] for r in recs))
    keep = set(ids[:n_states] if n_states else ids)
    order = [r for r in recs if r['state_id'] in keep and r['arm'] != 'S0N'] \
        + [r for r in recs if r['state_id'] in keep and r['arm'] == 'S0N']
    where = list(range(len(order)))
    random.Random(0).shuffle(where)              # the runner's shuffle: afterwards position j holds line where[j]
    lines = [None] * len(order)
    for j, r in enumerate(order):
        lines[where[j]] = r
    check = list(lines)
    random.Random(0).shuffle(check)
    assert [(r['state_id'], r['arm']) for r in check] == [(r['state_id'], r['arm']) for r in order]
    os.makedirs(os.path.dirname(runner_states), exist_ok=True)
    with open(runner_states, 'w', encoding='utf-8') as f:
        for r in lines:
            f.write(json.dumps(r) + '\n')
    os.makedirs(out, exist_ok=True)
    res = out + '/results.jsonl'
    rows, whole = _read_rows(res)                # rows of an earlier, interrupted run are kept: the runner resumes
    if not whole:
        _write_rows(res, [line for line, _row in rows])
    have = {_cell(row) for _line, row in rows}
    entered = 0
    with open(res, 'a', encoding='utf-8') as f:
        for r in order:
            for arm in ARMS.split(','):
                for seed in RUNNER_SEEDS:
                    cell = {'task': r['task'], 'run': r['run'], 'fork': r['fork'], 'arm': arm, 'seed': seed}
                    if (arm != RUNNER_ARM[r['arm']] or seed not in seeds) and _cell(cell) not in have:
                        f.write(json.dumps(dict(cell, skip='not in the design')) + '\n')
                        entered += 1
    return order, entered, hashlib.md5(raw).hexdigest()


def _finish(out, order):
    """Remove the cells entered as finished from results.jsonl and print, by arm, rows, errors, rows with a call and
    prompt sizes (arm S against the size logged for the same step). Nothing about what the calls were."""
    rec_of = {(r['task'], r['run'], r['fork']): r for r in order}
    kept = [(line, row) for line, row in _read_rows(out + '/results.jsonl')[0] if not row.get('skip')]
    _write_rows(out + '/results.jsonl', [line for line, _row in kept])
    by, size = {}, {}
    for _line, row in kept:
        rec = rec_of.get((row['task'], row['run'], row['fork']))
        if rec is None:                          # a row of a record that is not in this plan
            continue
        d = by.setdefault(rec['arm'], {'rows': 0, 'errors': 0, 'with_call': 0})
        d['rows'] += 1
        d['errors'] += bool(row.get('error'))
        d['with_call'] += bool(row.get('next_call'))
        got = (row.get('usage') or {}).get('prompt_tokens')
        if got:
            size.setdefault(rec['arm'], {}).setdefault(rec['state_id'], got)
    print('replays by arm:', {a: by.get(a) for a in RUNNER_ARM})
    logged = {r['state_id']: r['prompt_tokens_next_call_logged'] for r in order}
    s = size.get('S', {})
    if s:
        diffs = [s[k] - logged[k] for k in s]
        rel = [abs(s[k] - logged[k]) / logged[k] for k in s]
        print(f'prompt size, arm S minus the logged size ({len(s)} states): median {statistics.median(diffs):+.0f} tokens, '
              f'median absolute relative difference {100 * statistics.median(rel):.2f}%, largest {100 * max(rel):.2f}%')
    for a, b in (('S0', 'S'), ('S0N', 'S0')):
        d = [size[a][k] - size[b][k] for k in size.get(a, {}) if k in size.get(b, {})]
        if d:
            print(f'prompt size, {a} minus {b} ({len(d)} states): median {statistics.median(d):+.0f} tokens, '
                  f'from {min(d):+d} to {max(d):+d}')


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=SMOKE_LIMIT_S + 60, cpu=8, memory=49152, max_containers=1)
def smoke():
    t0 = time.time()
    shutil.rmtree(SMOKE_OUT, ignore_errors=True)   # the smoke test starts from nothing
    order, entered, md5 = _plan(SMOKE_OUT, n_states=SMOKE_STATES, seeds=SMOKE_SEEDS)
    env = _env(SMOKE_OUT, TIME_BUDGET_S=str(SMOKE_BUDGET_S))
    print('python', sys.version, '| gpu', _gpu(), '| states file md5', md5, '| records', len(order),
          '| cells entered as finished', entered)
    p = subprocess.Popen([sys.executable, RUNNER], env=env, start_new_session=True)
    try:
        code = p.wait(timeout=max(1, SMOKE_LIMIT_S - (time.time() - t0)))
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        code = 'stopped at the time limit'
    print('exit', code)
    vol.commit()                                   # the rows as the runner left them, before anything is rewritten
    _finish(SMOKE_OUT, order)
    vol.commit()
    return code


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=90 * 60, cpu=8, memory=49152, max_containers=1)
def full():
    order, entered, md5 = _plan(OUT)
    env = _env(OUT)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': MODEL, 'served_as': SERVED,
               'harness_variant': VARIANT, 'arms': ARMS, 'runner_arm_of_record': RUNNER_ARM, 'states_file': STATES,
               'states_file_md5': md5, 'records': len(order), 'states': len({r['state_id'] for r in order}),
               'order': 'records S and S0 of every state, then records S0N', 'cells_entered_as_finished': entered,
               'time_budget_s': BUDGET_S, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(OUT + '/platform_actual.json', 'w'))

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
    vol.commit()                                   # the rows as the runner left them, before anything is rewritten
    _finish(OUT, order)
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
