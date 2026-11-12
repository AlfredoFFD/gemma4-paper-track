"""Pre-registration 25 on Modal (the place of the list): one-step replays of the records of analysis/make_states_25.py
under arms KH, KE and EL, seeds 1 and 2. Gemma-4-31B, the harness wheels of Oct 12 (`latest`: adk_eval_core 0.1.0,
adk_submission 0.2.13, swegemma 0.2.11), the one-step machinery of pre-registration 08 (the image, package list,
wheelhouse, vLLM settings, served model path and concurrency 8 of forks_g_modal.py, part "one step"). The functions
below follow those of forks_15_modal.py and forks_20_modal.py line for line where they can.

The runner is the frozen one-step runner of pre-registration 07 (/vol/inputs_w/forks_w_runner.py, unchanged; its md5
is checked against analysis/modal_w/forks_w_runner.py before anything runs). It replays every record of its states
file under every arm it is given, for seeds 1 to 3, in the order of its own seeded shuffle (random.Random(0)), and it
leaves out the cells its results file already holds. The states file has one record per (step, arm), each with its
own history, in the builder's fixed order of the steps (random.Random(25); each step's records KH, KE, EL one after
the other). The order of the run is seed-major: pass 1 runs seed 1 over every step in that order, the three arms of a
step together; pass 2 runs seed 2 in the same order, until the cap. Every step is covered once before any step is
covered twice, and what the cap cuts is a random subset of seed 2. One invocation of the runner does both passes (no
second server start-up): before it starts, this script
  - checks the states file on the volume against the md5 in analysis/fork_states_p/manifest.json;
  - writes each (step, arm) record once per pass, with fork "<03's fork>:<arm>:<seed>", the passes one after the
    other, so that the runner's shuffle turns them back into that order;
  - gives the runner two arms: A replays a record as it stands (records KH and KE: the changed last result is the new
    message), EL adds the record's note (record EL, arm EL of pre-registration 04);
  - enters every cell outside the design in the results file as finished, marked `skip`: a record under the other
    arm, and every seed but its pass's. The runner then meets the cells in the planned order. After the run these
    lines are removed from results.jsonl (the runner's own summary.json counted them as rows).
No new replay starts once 40 minutes of the runner's clock have passed (both passes together, its start-up of five to
six minutes included); replays under way then finish and the runner writes its summary. Should the runner still be
running at 46 minutes, it is stopped, so that the rows are cleaned and committed before the container's own limit of
50 minutes. One container, one GPU, no retry: the full run refuses to start if its results file already holds a replay.
The runner's own prompt-size check is off (FIDELITY_N=0).

Volume `gemma-forks-c`, mounted at /vol:
  /vol/inputs_w/forks_w_runner.py    the frozen runner (also run by 15, 17 and 20)
  /vol/inputs_25/states_25.jsonl     analysis/fork_states_p/states.jsonl (built by analysis/make_states_25.py)
  /vol/out_25                        the full run: results.jsonl, summary.json, versions.json (written by the runner),
                                     versions_25.json (the package versions after the run), platform_actual.json,
                                     pip_freeze.txt, vllm_server.log, fidelity.jsonl and fidelity_w.jsonl (both empty)
  /vol/out_25_smoke                  the smoke test (it starts from nothing each time): the first 8 steps of the order,
                                     every arm, seed 1 (24 replays)

Commands, from the repository root in Git Bash (modal is the CLI of the Python on PATH):
  build the records:  py -I -X utf8 analysis/make_states_25.py
  local check:        py -X utf8 analysis/modal_g/forks_25_modal.py --check
                      (without -I: the modal package needs the user's site-packages, as the modal CLI does)
                      (no Modal call: compiles this file, the runner and replay.py, checks the local states file
                      against the manifest, plans the smoke test and the full run in a temporary folder and walks the
                      runner's job list over each plan)
  upload:             MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 modal volume put -f gemma-forks-c analysis/fork_states_p/states.jsonl /inputs_25/states_25.jsonl
  smoke test:         MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 modal run analysis/modal_g/forks_25_modal.py --mode smoke
  full run:           MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 modal run --detach analysis/modal_g/forks_25_modal.py --mode full
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

app = modal.App('gemma-forks-25')
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
STATES = '/vol/inputs_25/states_25.jsonl'
OUT = '/vol/out_25'
SMOKE_OUT = '/vol/out_25_smoke'
RUNNER_STATES = '/root/states_25/runner_states.jsonl'   # the records in the order the runner needs; stays in the container
ARMS = 'A,EL'                                            # the runner's arms
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL'}          # the runner's arm for each record (make_states_25.RUNNER_ARM)
RECORD_ARMS = ('KH', 'KE', 'EL')                         # the order of a step's records (make_states_25.RECORD_ARMS)
RUNNER_SEEDS = (1, 2, 3)                                 # fixed inside the runner
SEEDS = (1, 2)                                           # the design
SMOKE_STATES, SMOKE_SEEDS = 8, (1,)                      # the smoke test: the first 8 steps of the order, seed 1
BUDGET_S = 40 * 60                                       # no new replay after this much of the runner's clock (both passes)
HARD_STOP_S = BUDGET_S + 6 * 60                          # the runner is stopped if it still runs this long after the start
TIMEOUT_S = BUDGET_S + 10 * 60                           # the container's own limit (50 minutes)
SMOKE_BUDGET_S, SMOKE_LIMIT_S = 570, 660                 # the smoke test: no new replay after 9.5 minutes, stopped at 11
CONCURRENCY = 8                                          # as the one-step part of 08 (forks_g_modal._env_s)
VARIANT = 'latest'
HARNESS = {'adk_eval_core': '0.1.0', 'adk_submission': '0.2.13', 'swegemma': '0.2.11'}  # the wheels of `latest`
PACKAGES = ('swegemma', 'adk_submission', 'adk_eval_core', 'google-adk', 'google-genai', 'litellm', 'vllm', 'torch',
            'transformers')
MODES = ('smoke', 'full')
# Served under the same path string as on the hosted notebooks, so the model name the agent framework sees is identical.
SERVED = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
MODEL = 'model'
SIZE = 23265352448


def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


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
             CONCURRENCY=str(CONCURRENCY), TIME_BUDGET_S=str(BUDGET_S), HARNESS_VARIANT=VARIANT, ARMS=ARMS,
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


def step_order(recs):
    """The step ids in the order of the run: as the states file lists them (the builder wrote them in its order)."""
    return list(dict.fromkeys(r['step_id'] for r in recs))


def _plan(out, n_states=0, seeds=SEEDS, states=STATES, runner_states=RUNNER_STATES, expect_md5=None):
    """Write the runner's states file and enter the cells outside the design as finished.

    Seed-major: each (step, arm) record is written once per pass, its fork "<03's fork>:<arm>:<seed>", and only that
    seed's cell is left to run; the records of pass 1 (seed 1, every step in the order, a step's three arms together)
    come before those of pass 2 (seed 2, the same order). Returns (the records in the order of the run, the number of
    cells entered, the md5 of the states file read). n_states keeps the first steps of the order.
    """
    raw = open(states, 'rb').read()
    md5 = md5_bytes(raw)
    assert expect_md5 is None or md5 == expect_md5, f'states file md5 {md5}, the manifest says {expect_md5}'
    recs = [json.loads(l) for l in raw.decode('utf-8').splitlines()]
    ids = step_order(recs)
    by = {(r['step_id'], r['arm']): r for r in recs}
    assert len(by) == len(recs) == len(ids) * len(RECORD_ARMS), 'every step has exactly one record per arm'
    assert [(r['step_id'], r['arm']) for r in recs] == [(k, a) for k in ids for a in RECORD_ARMS], 'records out of order'
    if n_states:
        ids = ids[:n_states]
    order = [dict(by[(k, a)], fork=f"{by[(k, a)]['fork']}:{seed}", pass_seed=seed)
             for seed in seeds for k in ids for a in RECORD_ARMS]
    where = list(range(len(order)))
    random.Random(0).shuffle(where)              # the runner's shuffle: afterwards position j holds line where[j]
    lines = [None] * len(order)
    for j, r in enumerate(order):
        lines[where[j]] = r
    check = list(lines)
    random.Random(0).shuffle(check)
    assert [r['fork'] + r['step_id'] for r in check] == [r['fork'] + r['step_id'] for r in order]
    os.makedirs(os.path.dirname(runner_states), exist_ok=True)
    with open(runner_states, 'w', encoding='utf-8') as f:
        for r in lines:
            f.write(json.dumps(r) + '\n')
    os.makedirs(out, exist_ok=True)
    res = out + '/results.jsonl'
    rows, whole = _read_rows(res)
    if not whole:
        _write_rows(res, [line for line, _row in rows])
    have = {_cell(row) for _line, row in rows}
    entered = 0
    with open(res, 'a', encoding='utf-8') as f:
        for r in order:
            for arm in ARMS.split(','):
                for seed in RUNNER_SEEDS:
                    cell = {'task': r['task'], 'run': r['run'], 'fork': r['fork'], 'arm': arm, 'seed': seed}
                    if (arm != RUNNER_ARM[r['arm']] or seed != r['pass_seed']) and _cell(cell) not in have:
                        f.write(json.dumps(dict(cell, skip='not in the design')) + '\n')
                        entered += 1
    return order, entered, md5


def _finish(out, order):
    """Remove the cells entered as finished from results.jsonl and print, by arm, rows, errors, rows with a call and
    prompt sizes. Nothing about what the calls were."""
    rec_of = {(r['task'], r['run'], r['fork']): r for r in order}
    kept = [(line, row) for line, row in _read_rows(out + '/results.jsonl')[0] if not row.get('skip')]
    _write_rows(out + '/results.jsonl', [line for line, _row in kept])
    by, size, cells = {}, {}, {}
    for _line, row in kept:
        rec = rec_of.get((row['task'], row['run'], row['fork']))
        if rec is None:                          # a row of a record that is not in this plan
            continue
        d = by.setdefault(rec['arm'], {'rows': 0, 'errors': 0, 'with_call': 0})
        d['rows'] += 1
        d['errors'] += bool(row.get('error'))
        d['with_call'] += bool(row.get('next_call'))
        cells.setdefault(rec['step_id'], set()).add((rec['arm'], row['seed']))
        got = (row.get('usage') or {}).get('prompt_tokens')
        if got:
            size.setdefault(rec['arm'], {}).setdefault((rec['step_id'], row['seed']), got)
    print('replays by arm (rows, runner errors, rows with a call):', {a: by.get(a) for a in RECORD_ARMS})
    seeds = sorted({s for c in cells.values() for _a, s in c})
    full = sum(1 for c in cells.values() if c >= {(a, s) for a in RECORD_ARMS for s in seeds})
    for s in seeds:
        print(f'seed {s}: steps with a row for every arm: '
              f'{sum(1 for c in cells.values() if {(a, s) for a in RECORD_ARMS} <= c)}')
    print(f'steps with at least one row: {len(cells)} of {len({r["step_id"] for r in order})}; with a row for every '
          f'arm at seeds {seeds}: {full}')
    logged = {r['step_id']: r['prompt_tokens_next_call_logged'] for r in order if r['arm'] == 'KH'}
    kh = size.get('KH', {})
    if kh:
        d = [kh[k] - logged[k[0]] for k in kh if logged.get(k[0])]
        if d:
            print(f'prompt size, KH minus the size logged for the recorded call ({len(d)} replays): median '
                  f'{statistics.median(d):+.0f} tokens, from {min(d):+d} to {max(d):+d}')
    for a, b in (('KE', 'KH'), ('EL', 'KH'), ('EL', 'KE')):
        d = [size[a][k] - size[b][k] for k in size.get(a, {}) if k in size.get(b, {})]
        if d:
            print(f'prompt size, {a} minus {b} ({len(d)} replays): median {statistics.median(d):+.0f} tokens, '
                  f'from {min(d):+d} to {max(d):+d}')


def _check_inputs(states_md5, runner_md5):
    """The states file and the runner on the volume are the ones this launch was checked with."""
    got_s = md5_bytes(open(STATES, 'rb').read())
    got_r = md5_bytes(open(RUNNER, 'rb').read())
    replay_md5 = md5_bytes(open(SRC + '/inputs/replay.py', 'rb').read()) if os.path.exists(SRC + '/inputs/replay.py') else None
    print(f'states file md5 {got_s} (manifest {states_md5}); runner md5 {got_r} (local {runner_md5}); replay.py on the '
          f'volume md5 {replay_md5}', flush=True)
    assert got_s == states_md5, 'the states file on the volume is not the one of the manifest: upload it again'
    assert got_r == runner_md5, 'the runner on the volume is not analysis/modal_w/forks_w_runner.py'
    return {'states_file_md5': got_s, 'runner_md5': got_r, 'replay_py_md5': replay_md5}


def _versions(out):
    """The package versions after the runner installed the wheels, and whether the harness is the one registered."""
    code = ('import importlib.metadata as m, json\n'
            f'names = {list(PACKAGES)!r}\n'
            'out = {}\n'
            'for n in names:\n'
            '    try:\n'
            '        out[n] = m.version(n)\n'
            '    except m.PackageNotFoundError:\n'
            '        out[n] = None\n'
            'print(json.dumps(out))\n')
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    try:
        got = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {'error': p.stderr[-500:]}
    wheels = {}
    for stem, ver in HARNESS.items():
        path = f'{SRC}/inputs/{stem}-{ver}-py3-none-any.whl'
        wheels[os.path.basename(path)] = md5_bytes(open(path, 'rb').read()) if os.path.exists(path) else None
    rec = {'harness_variant': VARIANT, 'harness_registered': HARNESS, 'packages_after_run': got,
           'harness_as_registered': all(got.get(k) == v for k, v in HARNESS.items()), 'harness_wheel_md5': wheels}
    json.dump(rec, open(out + '/versions_25.json', 'w'), indent=1)
    print('versions:', json.dumps(rec), flush=True)
    return rec


def _committer(every_s=300):  # rows reach the volume as they are written
    def loop():
        while True:
            time.sleep(every_s)
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=loop, daemon=True).start()


def _run_runner(env, t0, limit_s):
    p = subprocess.Popen([sys.executable, RUNNER], env=env, start_new_session=True)
    try:
        return p.wait(timeout=max(1, limit_s - (time.time() - t0)))
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        return 'stopped at the time limit'


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=SMOKE_LIMIT_S + 120, cpu=8, memory=49152,
              max_containers=1)
def smoke(states_md5: str, runner_md5: str):
    t0 = time.time()
    inputs = _check_inputs(states_md5, runner_md5)
    shutil.rmtree(SMOKE_OUT, ignore_errors=True)   # the smoke test starts from nothing
    order, entered, md5 = _plan(SMOKE_OUT, n_states=SMOKE_STATES, seeds=SMOKE_SEEDS, expect_md5=states_md5)
    env = _env(SMOKE_OUT, TIME_BUDGET_S=SMOKE_BUDGET_S)
    print('python', sys.version, '| gpu', _gpu(), '| states file md5', md5, '| records', len(order),
          '| cells entered as finished', entered, '| replays planned', len(order), flush=True)
    code = _run_runner(env, t0, SMOKE_LIMIT_S)
    print('exit', code)
    vol.commit()                                   # the rows as the runner left them, before anything is rewritten
    _finish(SMOKE_OUT, order)
    _versions(SMOKE_OUT)
    json.dump(dict(inputs, smoke=True, records=len(order), seeds=list(SMOKE_SEEDS)), open(SMOKE_OUT + '/platform_actual.json', 'w'))
    vol.commit()
    return code


@app.function(image=image, gpu='A100-80GB', volumes={M: vol}, timeout=TIMEOUT_S, cpu=8, memory=49152, max_containers=1)
def full(states_md5: str, runner_md5: str):
    t0 = time.time()
    inputs = _check_inputs(states_md5, runner_md5)
    rows, _whole = _read_rows(OUT + '/results.jsonl')
    done = [row for _line, row in rows if not row.get('skip')]
    if done:
        raise SystemExit(f'{OUT}/results.jsonl already holds {len(done)} replays: one launch, no retry')
    shutil.rmtree(OUT, ignore_errors=True)         # a launch that stopped before its first replay leaves nothing behind
    order, entered, md5 = _plan(OUT, expect_md5=states_md5)
    env = _env(OUT)
    json.dump(dict(inputs, platform='modal', gpu=_gpu(), python=sys.version, model_dir=MODEL, served_as=SERVED,
                   harness_variant=VARIANT, harness_wheels=HARNESS, concurrency=CONCURRENCY, arms=ARMS,
                   runner_arm_of_record=RUNNER_ARM, states_file=STATES, records=len(order),
                   steps=len({r['step_id'] for r in order}), seeds=list(SEEDS),
                   order='seed-major: pass 1 runs seed 1 over every step in the builder\'s order (random.Random(25)), '
                         'a step\'s records KH, KE, EL together; pass 2 runs seed 2 in the same order, until the cap',
                   cells_entered_as_finished=entered, replays_planned=len(order), time_budget_s=BUDGET_S,
                   hard_stop_s=HARD_STOP_S, container_timeout_s=TIMEOUT_S,
                   started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())),
              open(OUT + '/platform_actual.json', 'w'))
    print('python', sys.version, '| gpu', _gpu(), '| records', len(order), '| replays planned', len(order),
          '| cells entered as finished', entered, flush=True)
    _committer()
    code = _run_runner(env, t0, HARD_STOP_S)
    print('exit', code)
    vol.commit()                                   # the rows as the runner left them, before anything is rewritten
    _finish(OUT, order)
    _versions(OUT)
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(OUT + '/pip_freeze.txt', 'w').write(txt)
    vol.commit()
    return code


def _local_paths():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    return {'root': root, 'states': root / 'analysis' / 'fork_states_p' / 'states.jsonl',
            'manifest': root / 'analysis' / 'fork_states_p' / 'manifest.json',
            'runner': root / 'analysis' / 'modal_w' / 'forks_w_runner.py', 'replay': root / 'analysis' / 'replay.py'}


def _launch_inputs():
    p = _local_paths()
    manifest = json.load(open(p['manifest'], encoding='utf-8'))
    return manifest['md5'], md5_bytes(p['runner'].read_bytes())


@app.local_entrypoint()
def main(mode: str = 'smoke'):
    if mode not in MODES:
        raise SystemExit(f'unknown mode {mode}; the modes are {MODES}')
    states_md5, runner_md5 = _launch_inputs()
    print('states file md5 (manifest):', states_md5, '| runner md5 (local):', runner_md5)
    if mode == 'smoke':
        print('exit', smoke.remote(states_md5, runner_md5))
    else:
        print('exit', full.remote(states_md5, runner_md5))


def _walk_runner(runner_states, results):
    """The runner's job list over a plan, as forks_w_runner.py builds it: its shuffle, then every record x arm x seed
    whose cell the results file does not hold."""
    states = [json.loads(l) for l in open(runner_states, encoding='utf-8')]
    random.Random(0).shuffle(states)
    done = {_cell(r) for _line, r in _read_rows(results)[0]}
    return [(s, arm, seed) for s in states for arm in ARMS.split(',') for seed in RUNNER_SEEDS
            if (s['task'], s['run'], s['fork'], arm, seed) not in done]


def local_check():
    """No Modal call: syntax, inputs and the plans of the smoke test and the full run, on this machine."""
    import py_compile
    import tempfile
    p = _local_paths()
    for f in (__file__, p['runner'], p['replay']):
        py_compile.compile(str(f), doraise=True)
    print('compiled: this launcher, analysis/modal_w/forks_w_runner.py, analysis/replay.py')
    assert BUDGET_S < HARD_STOP_S < TIMEOUT_S and SMOKE_BUDGET_S < SMOKE_LIMIT_S, 'time limits out of order'
    print(f'time limits: no new replay after {BUDGET_S // 60} min of the runner\'s clock; runner stopped at '
          f'{HARD_STOP_S // 60} min; container limit {TIMEOUT_S // 60} min; smoke test {SMOKE_BUDGET_S} s / '
          f'{SMOKE_LIMIT_S} s; modes {MODES}')
    manifest = json.load(open(p['manifest'], encoding='utf-8'))
    got = md5_bytes(p['states'].read_bytes())
    assert got == manifest['md5'], f'local states file md5 {got}, manifest {manifest["md5"]}: rebuild or re-check'
    assert manifest['runner_arm_of_record'] == RUNNER_ARM and tuple(manifest['record_arms']) == RECORD_ARMS
    print(f'states file {got} = manifest; {manifest["records"]} records, {manifest["counts"]["steps"]} steps; runner md5 '
          f'{md5_bytes(p["runner"].read_bytes())}')
    order_m = manifest['order']
    with tempfile.TemporaryDirectory() as tmp:
        for label, n, seeds in (('smoke test', SMOKE_STATES, SMOKE_SEEDS), ('full run', 0, SEEDS)):
            out = os.path.join(tmp, label.replace(' ', '_'))
            rs = os.path.join(out, 'runner_states.jsonl')
            order, entered, _md5 = _plan(out, n_states=n, seeds=seeds, states=str(p['states']), runner_states=rs,
                                         expect_md5=manifest['md5'])
            jobs = _walk_runner(rs, os.path.join(out, 'results.jsonl'))
            want_steps = order_m[:n] if n else order_m
            assert len(jobs) == len(want_steps) * len(RECORD_ARMS) * len(seeds), f'{label}: {len(jobs)} jobs'
            assert [seed for _s, _a, seed in jobs] == sorted(seed for _s, _a, seed in jobs),                 f'{label}: a seed-2 replay comes before a seed-1 replay'
            pos = {k: i for i, k in enumerate(want_steps)}
            for seed in seeds:                       # each pass: every step in the manifest's order, a step whole
                pj = [(s, arm) for s, arm, sd in jobs if sd == seed]
                assert list(dict.fromkeys(s['step_id'] for s, _a in pj)) == want_steps, f'{label}: pass {seed} order'
                assert all(pos[x[0]['step_id']] <= pos[y[0]['step_id']] for x, y in zip(pj, pj[1:])),                     f'{label}: pass {seed}: a step starts before the previous one is done'
                assert [s['arm'] for s, _a in pj[:3]] == list(RECORD_ARMS)
            for s, arm, seed in jobs:
                assert arm == RUNNER_ARM[s['arm']] and seed == s['pass_seed'], f'{label}: a cell outside the design'
            first = [(s['arm'], arm, seed) for s, arm, seed in jobs[:len(RECORD_ARMS) + 1]]
            print(f'{label}: {len(order)} records, {entered} cells entered as finished, {len(jobs)} replays to run, '
                  f'seed-major (all steps at seed 1 in the manifest\'s order, then all at seed 2; a step whole within a '
                  f'pass); first jobs '
                  f'(record, runner arm, seed): {first}')
            if label == 'smoke test':                # _finish on stand-in rows (no model): skips removed, counts printed
                with open(os.path.join(out, 'results.jsonl'), 'a', encoding='utf-8') as f:
                    for s, arm, seed in jobs:
                        f.write(json.dumps({'task': s['task'], 'run': s['run'], 'fork': s['fork'], 'arm': arm,
                                            'seed': seed, 'next_call': None, 'error': 'stand-in row',
                                            'usage': {'prompt_tokens': 1000}}) + '\n')
                _finish(out, order)
                left = [r for _l, r in _read_rows(os.path.join(out, 'results.jsonl'))[0]]
                assert len(left) == len(jobs) and not any(r.get('skip') for r in left)
    print('local check passed. Next: upload, then the smoke test, then the full run (commands in this file\'s docstring)')


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        local_check()
    else:
        raise SystemExit('run as `py -X utf8 analysis/modal_g/forks_25_modal.py --check`, or through `modal run`')
