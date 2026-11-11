"""Experiment 20 on Modal ("asked or told"): one-step replays of the states of analysis/make_states_t.py under four
arms: the history just before the agent's own numbered search, with nothing added (NONE), with the hits of that search
handed over in a note (TOLD), and with the hits of another recorded search in a note (TOLDX); and the history as
recorded, with the agent's search and its result (ASKED: arm S of pre-registration 15, replayed again in this launch). Gemma-4-31B, the harness wheels of Sep 30 (v28): the model, server
settings, sampling, seeds (1 to 3) and concurrency (8) of pre-registration 15 (analysis/modal_g/forks_15_modal.py,
whose functions this file follows line for line where it can).

The runner is the frozen one-step runner of pre-registration 07 (/vol/inputs_w/forks_w_runner.py, unchanged). It
replays every record of its states file under every arm it is given, for seeds 1 to 3, in the order of its own
seeded shuffle (random.Random(0)), and leaves out the cells its results file already holds. The states file has one
record per (state, arm), each with its own history. So, before the runner starts, this script
  - takes the states in a fixed random order, random.Random(20) applied to the states as the file lists them, and
    writes the records for the runner so that its shuffle turns them into that order, each state's records NONE,
    TOLD, TOLDX and ASKED one after the other: a run cut short by the budget is then a random subset of states;
  - gives the runner three arms: A replays a record as it stands (records NONE and ASKED), TOLD and TOLDX add the
    record's note (records TOLD and TOLDX), as the note of arm S0N was added in 15;
  - enters every cell outside the design in the results file as finished, marked `skip` (a record under another arm
    than its own and, in the smoke test, seeds 2 and 3); after the run these lines are removed from results.jsonl
    (the runner's own summary.json counted them as rows).
No new replay starts once `--minutes` (default 30, at most 35) of the runner's clock have passed, its start-up (five
to six minutes) included; replays under way then finish and the runner writes its summary and stops. The runner's own
prompt-size check is off (FIDELITY_N=0); the prompts of NONE and ASKED are compared with the sizes logged for the
calls they replay (NONE: the search call; ASKED: the call after the search), from the results.
Projected time: 555 replays (53 states x NONE, TOLD, ASKED and 26 x TOLDX, three seeds); pre-registration 15 ran 549
replays of the same states on this platform in 22 minutes, start-up included, so the default budget of 30 minutes is
kept.

Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_w/forks_w_runner.py   the frozen runner
  /vol/inputs_g/states_t.jsonl      analysis/fork_states_t/states.jsonl (analysis/make_states_t.py)
  /vol/inputs_g/states_s.jsonl      the states of 15 (read by the check only)
  /vol/inputs_g/forks_20_check.py   analysis/modal_g/forks_20_check.py (read by the check only)
  /vol/out_20                       results.jsonl, versions.json, summary.json, pip_freeze.txt, platform_actual.json,
                                    vllm_server.log, fidelity.jsonl and fidelity_w.jsonl (both empty)
  /vol/out_20_smoke                 the smoke test: 8 states, every arm, seed 1

Upload (again after any rebuild):
  modal volume put -f gemma-forks-c analysis/fork_states_t/states.jsonl /inputs_g/states_t.jsonl
  modal volume put -f gemma-forks-c analysis/modal_g/forks_20_check.py /inputs_g/forks_20_check.py
Plumbing (no GPU):  modal run analysis/modal_g/forks_20_modal.py --mode check [--n-states 6]
                    the plan of the full run, then a stand-in model in place of the server on the first n states of
                    the order, every arm, seeds 1 to 3, through replay.run_one_step as the runner calls it; it checks
                    the requests (ASKED is the request of 15's arm S; NONE is ASKED without its last two messages;
                    TOLD and TOLDX are NONE plus one user message equal to the note) and writes the rows to
                    analysis/fork_states_t/check/ on this machine (not tracked, not on the volume)
Smoke test:         modal run analysis/modal_g/forks_20_modal.py --mode smoke
Full run:           modal run --detach analysis/modal_g/forks_20_modal.py --mode full [--minutes 30]
Store the rows:     py -I -X utf8 analysis/store_20.py
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

app = modal.App('gemma-forks-20')
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
CHECK = '/vol/inputs_g/forks_20_check.py'
STATES = '/vol/inputs_g/states_t.jsonl'
STATES_15 = '/vol/inputs_g/states_s.jsonl'
OUT = '/vol/out_20'
SMOKE_OUT = '/vol/out_20_smoke'
CHECK_OUT = '/root/check_20'                             # the plumbing run keeps nothing on the volume
RUNNER_STATES = '/root/states_20/runner_states.jsonl'   # the records in the order the runner needs; stays in the container
ARMS = 'A,TOLD,TOLDX'                                    # the runner's arms
RUNNER_ARM = {'NONE': 'A', 'TOLD': 'TOLD', 'TOLDX': 'TOLDX', 'ASKED': 'A'}  # the runner's arm for each record
RECORD_ARMS = ('NONE', 'TOLD', 'TOLDX', 'ASKED')                  # the order of a state's records
RUNNER_SEEDS = (1, 2, 3)                                 # fixed inside the runner
ORDER_SEED = 20                                          # random.Random(20): the order of the states
MINUTES, MAX_MINUTES = 30, 35                            # no new replay after this much of the runner's clock
SMOKE_STATES, SMOKE_SEEDS = 8, (1,)
SMOKE_BUDGET_S, SMOKE_LIMIT_S = 570, 660                 # the smoke test: no new replay after 9.5 minutes, stopped at 11
VARIANT = 'v28'
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
MODEL = 'model'
SIZE = 23265352448


def _env(out, gpu=True, **extra):
    if not os.path.islink(V):
        os.symlink(SRC, V)
    if gpu:
        if not os.path.exists(SERVED):
            os.makedirs(os.path.dirname(SERVED), exist_ok=True)
            os.symlink(f'{V}/{MODEL}', SERVED)
        assert os.path.getsize(f'{SERVED}/model.safetensors') == SIZE, 'model file incomplete'
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    e = dict(os.environ, WHEELHOUSE_DIR=V + '/wheelhouse', INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp',
             MODEL_DIR=SERVED if gpu else '', OUT_DIR=out, AGENT_DIR='/root/agents/base', TP_SIZE='1', FIDELITY_N='0',
             CONCURRENCY='8', TIME_BUDGET_S=str(MINUTES * 60), HARNESS_VARIANT=VARIANT, ARMS=ARMS,
             STATES_FILE=RUNNER_STATES)
    e.update({k: str(v) for k, v in extra.items()})
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


def state_order(recs):
    """The state ids in the order of the run: random.Random(20) applied to the states as the file lists them."""
    ids = list(dict.fromkeys(r['state_id'] for r in recs))
    random.Random(ORDER_SEED).shuffle(ids)
    return ids


def _plan(out, n_states=0, seeds=RUNNER_SEEDS, states=STATES, runner_states=RUNNER_STATES):
    """Write the runner's states file and enter the cells outside the design as finished.

    Returns (the records in the order of the run, the number of cells entered, the md5 of the states file read).
    n_states keeps the first states of the order.
    """
    raw = open(states, 'rb').read()
    recs = [json.loads(l) for l in raw.decode('utf-8').splitlines()]
    ids = state_order(recs)
    if n_states:
        ids = ids[:n_states]
    by = {(r['state_id'], r['arm']): r for r in recs}
    order = [by[(k, a)] for k in ids for a in RECORD_ARMS if (k, a) in by]
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
    prompt sizes (arms NONE and ASKED against the sizes logged for the calls they replay). Nothing about what the
    calls were."""
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
    print('states with at least one row:', len({rec_of[(row['task'], row['run'], row['fork'])]['state_id']
                                                for _l, row in kept if (row['task'], row['run'], row['fork']) in rec_of}),
          'of', len({r['state_id'] for r in order}))
    for arm in ('NONE', 'ASKED'):
        logged = {r['state_id']: r['prompt_tokens_next_call_logged'] for r in order if r['arm'] == arm}
        s = size.get(arm, {})
        if s:
            diffs = [s[k] - logged[k] for k in s]
            rel = [abs(s[k] - logged[k]) / logged[k] for k in s]
            print(f'prompt size, arm {arm} minus the logged size ({len(s)} states): median '
                  f'{statistics.median(diffs):+.0f} tokens, median absolute relative difference '
                  f'{100 * statistics.median(rel):.2f}%, largest {100 * max(rel):.2f}%')
    for a, b in (('TOLD', 'NONE'), ('TOLDX', 'NONE'), ('ASKED', 'NONE')):
        d = [size[a][k] - size[b][k] for k in size.get(a, {}) if k in size.get(b, {})]
        if d:
            print(f'prompt size, {a} minus {b} ({len(d)} states): median {statistics.median(d):+.0f} tokens, '
                  f'from {min(d):+d} to {max(d):+d}')


@app.function(image=image, volumes={M: vol}, timeout=900, cpu=2, memory=8192, max_containers=1)
def check(n_states: int = 6):
    """No GPU: the plan of the full run on a copy of nothing, then a stand-in model on the first n_states states of the
    order, every arm, seeds 1 to 3. Nothing is written to the volume; the rows are returned."""
    shutil.rmtree(CHECK_OUT, ignore_errors=True)
    order_full, entered_full, md5 = _plan(CHECK_OUT + '/plan_full', runner_states=CHECK_OUT + '/plan_full/runner.jsonl')
    print('python', sys.version, '| no gpu, stand-in model | states file md5', md5, '| full plan: records',
          len(order_full), 'states', len({r['state_id'] for r in order_full}), 'cells entered as finished', entered_full,
          '| replays to run', sum(1 for _ in order_full) * len(RUNNER_SEEDS), flush=True)
    order, entered, _ = _plan(CHECK_OUT, n_states=n_states)
    env = _env(CHECK_OUT, gpu=False, STATES_15=STATES_15)
    p = subprocess.run([sys.executable, CHECK], env=env)
    print('check exit', p.returncode, flush=True)
    raw = open(CHECK_OUT + '/results.jsonl', encoding='utf-8').read()
    _finish(CHECK_OUT, order)
    report = open(CHECK_OUT + '/check_report.txt', encoding='utf-8').read() if os.path.exists(CHECK_OUT + '/check_report.txt') else ''
    return {'exit': p.returncode, 'results_with_skips': raw, 'results': open(CHECK_OUT + '/results.jsonl', encoding='utf-8').read(),
            'report': report, 'states_md5': md5, 'records': len(order), 'entered': entered}


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=SMOKE_LIMIT_S + 60, cpu=8, memory=49152, max_containers=1)
def smoke():
    t0 = time.time()
    shutil.rmtree(SMOKE_OUT, ignore_errors=True)   # the smoke test starts from nothing
    order, entered, md5 = _plan(SMOKE_OUT, n_states=SMOKE_STATES, seeds=SMOKE_SEEDS)
    env = _env(SMOKE_OUT, TIME_BUDGET_S=SMOKE_BUDGET_S)
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


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=(MAX_MINUTES + 25) * 60, cpu=8, memory=49152, max_containers=1)
def full(minutes: int = MINUTES):
    assert 1 <= minutes <= MAX_MINUTES, minutes
    order, entered, md5 = _plan(OUT)
    env = _env(OUT, TIME_BUDGET_S=minutes * 60)
    json.dump({'platform': 'modal', 'gpu': _gpu(), 'python': sys.version, 'model_dir': MODEL, 'served_as': SERVED,
               'harness_variant': VARIANT, 'arms': ARMS, 'runner_arm_of_record': RUNNER_ARM, 'states_file': STATES,
               'states_file_md5': md5, 'records': len(order), 'states': len({r['state_id'] for r in order}),
               'order': 'states in the order of random.Random(20) over the file\'s states; each state\'s records NONE, '
                        'TOLD, TOLDX, ASKED one after the other',
               'cells_entered_as_finished': entered, 'time_budget_s': minutes * 60,
               'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(OUT + '/platform_actual.json', 'w'))

    def committer():  # rows reach the volume as they are written
        while True:
            time.sleep(300)
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
def main(mode: str = 'check', minutes: int = MINUTES, n_states: int = 6):
    if mode == 'check':
        from pathlib import Path
        got = check.remote(n_states)
        dst = Path(__file__).resolve().parents[1] / 'fork_states_t' / 'check'   # not tracked: stand-in rows
        dst.mkdir(parents=True, exist_ok=True)
        (dst / 'results.jsonl').write_text(got['results'], encoding='utf-8', newline='\n')
        (dst / 'check_report.txt').write_text(got['report'], encoding='utf-8', newline='\n')
        print(got['report'])
        print('exit', got['exit'], '| states md5', got['states_md5'], '| records', got['records'], '| rows written to', dst)
    elif mode == 'smoke':
        print('exit', smoke.remote())
    elif mode == 'full':
        assert 1 <= minutes <= MAX_MINUTES, f'--minutes must be from 1 to {MAX_MINUTES}'
        print('exit', full.remote(minutes))
    else:
        raise SystemExit(f'unknown mode {mode}')
