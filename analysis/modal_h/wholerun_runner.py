"""Pre-registration 14: whole runs of the starter agent scored by the tests, the harness as shipped or with two changes.

Runs inside the Modal container started by wholerun_modal.py. Every task goes through the competition harness's own
two-sandbox lifecycle, unchanged (swegemma.evaluate.Evaluator.evaluate_task; newest wheels, `latest`: adk_submission
0.2.13, swegemma 0.2.11, adk_eval_core 0.1.0): a subprocess sandbox with the task's snapshot, the agent session until
submit_patch, timeout or budget; then a fresh second sandbox, the agent's patch applied, the task's test_patch
applied, the tests run, `resolved` recorded. Task results, patches and test outputs are written by the harness's own
append_task_result; traces and session logs by the harness itself.

Two conditions, identical in everything else (agent, prompt, budgets, sampling, seed, sandbox, model server):
  N    the harness as shipped
  NAF  the two changes of pre-registration 09's arm NAF, applied to the compiled agent by the same functions (copied
       verbatim from analysis/modal_g/forks_09_runner.py; the copy is compared with that file at start):
       address_answers  the three graph tools' answers gain each entity's file and line range
       honor_bounds     a mangled line-bound argument name of read_file is restored before the read runs

Budgets: those of the public whole runs, which print them in every trace's task prompt: 40 tool calls, 25 minutes,
60 turns, 120 s per command. Context compaction and cache settings: those of the competition's scoring script
(data/HARNESS_README.md, section 7.2), as the public whole runs set them. Sampling: as the agent configuration sets
it. The seed is written into the compiled agent's generation config, the way replay_k.run_k_steps passes it.

Tasks: mode validate puts every task of tasks.jsonl that has a snapshot through the harness's test phase twice, with
its reference patch (must resolve) and with an empty patch (must not), and writes the tasks that pass both to
validate/tasks_ok.txt: their sorted ids shuffled with random.Random(0). The full run takes that file (TASKS_FILE) in
its line order, so a partial run is a random subset; without a file it takes the 106 tasks of
fork_states_g/fresh_states.jsonl, shuffled the same way. The two conditions of a task are scheduled side by side. One
worker process runs one session at a time (the harness's tool functions are synchronous: sessions sharing one event
loop would wait on each other's commands); CONCURRENCY workers run at once against one vLLM server.

Roles: `python wholerun_runner.py` (driver: installs the wheels, then validates, or starts the server and the
workers), `... worker`, `... validate`, `... merge <root>` (after a sharded run: builds <root>/<condition>/seed<k>/
from <root>/shards/*/; runs anywhere).
Modes (env MODE): validate (no GPU), smoke (3 tasks, both conditions), full (resumable), check (no GPU: the whole
pipeline on the smoke tasks with a scripted model in place of the server).

Output (OUT_DIR, on the volume):
  validate/              validate.jsonl (one line per task), tasks_ok.txt, summary_validate.json, test_outputs/
  <condition>/seed<k>/   task_results.jsonl, summary.json, patches/, test_outputs/, traces/, logs/ (the harness's
                         results directory), extra.jsonl (one line per session: how the agent session ended, what the
                         two changes did, interface failures), versions_14.json, platform_actual_14.json,
                         pip_freeze_14.txt (those of the last launch that wrote there)
  shards/<k>of<M>/...    the same layout, when the work is split over containers
  smoke/<launch>/...     the same layout, one folder per smoke launch; check/<launch>/... likewise
  launches/<launch>/     versions, platform record, pip freeze, job list and server log of every launch
"""
import asyncio
import collections
import contextlib
import functools
import glob
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

for k, v in (
    ('LITELLM_LOCAL_MODEL_COST_MAP', 'True'), ('TRANSFORMERS_NO_TF', '1'), ('VLLM_WORKER_MULTIPROC_METHOD', 'spawn'),
    ('VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS', '1'), ('VLLM_ENGINE_READY_TIMEOUT_S', '1200'), ('VLLM_NO_USAGE_STATS', '1'),
    ('OTEL_SDK_DISABLED', 'true'), ('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True'), ('LITELLM_LOG', 'ERROR'),
):
    os.environ.setdefault(k, v)

ROLE = sys.argv[1] if len(sys.argv) > 1 else 'driver'
MODE = os.environ.get('MODE', 'smoke')                              # validate | smoke | full | check
FAKE = MODE == 'check' or os.environ.get('FAKE_MODEL') == '1'       # a scripted model in place of the server
TASKS_FILE = os.environ.get('TASKS_FILE', '')                       # one task id per line, in run order; '' or 'fresh': the 106
WHEELHOUSE = Path(os.environ.get('WHEELHOUSE_DIR', '/nonexistent'))
INPUTS = Path(os.environ.get('INPUTS_DIR', '/nonexistent'))         # agent config and harness wheels (shared with the other runners)
INPUTS_G = Path(os.environ.get('INPUTS_G_DIR', '/nonexistent'))     # fresh_states.jsonl (the task set), spans/<task>.json, forks_09_runner.py
INPUTS_H = Path(os.environ.get('INPUTS_H_DIR', '/nonexistent'))     # this file, tasks.jsonl
SNAPSHOTS = Path(os.environ.get('SNAPSHOTS_DIR', '/nonexistent'))   # <task>.tgz
COMP = Path(os.environ.get('COMP_DIR', '/nonexistent'))             # graphs/ and embeddings/ of the competition data
MODEL_PATH = os.environ.get('MODEL_DIR', '')
OUT_ROOT = Path(os.environ.get('OUT_DIR', '/vol/out_14'))
AGENT_DIR = Path(os.environ.get('AGENT_DIR', '/root/agents/base'))
TASKS = INPUTS_H / 'tasks.jsonl'
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'latest')
EXPERIMENT = '14-whole-runs-scored-by-tests'

# The per-task budget of the public whole runs (their task prompts print it) and the scoring script's context settings.
BUDGET = {'timeout_seconds': 120, 'max_tool_calls': 40, 'max_time_minutes': 25, 'max_turns': 60}
COMPACTION = {'compaction_interval': 5, 'overlap_size': 2, 'token_threshold': 14336, 'event_retention_size': 5}
CONTEXT_CACHE = {'min_tokens': 2048, 'ttl_seconds': 1800, 'cache_intervals': 10}

ALL_CONDITIONS = ('N', 'NAF')
CONDITIONS = [c for c in os.environ.get('CONDITIONS', 'N,NAF').split(',') if c]
SEED = int(os.environ.get('SEED', '1'))
SHARD = os.environ.get('SHARD', '')                                  # 'k/M': the tasks at positions k, k+M, ... of the order
SHARD_K, SHARD_M = (int(x) for x in SHARD.split('/')) if SHARD else (0, 0)
CONCURRENCY = int(os.environ.get('CONCURRENCY', '16'))               # sessions at once
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(6 * 3600)))  # no new session starts after this
HARD_STOP_S = int(os.environ.get('HARD_STOP_S', '0'))                # smoke: running sessions are killed after this
LIMIT_TASKS = int(os.environ.get('LIMIT_TASKS', '0'))                # the first n tasks of the order (0: all)
RETRY_INFRA = os.environ.get('RETRY_INFRA') == '1'                   # re-run tasks whose last result is an infrastructure failure
GUARD_S = BUDGET['max_time_minutes'] * 60 + 1200                     # a session with both phases, at the very most
LAUNCH_ID = os.environ.get('LAUNCH_ID') or time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '_' + MODE
LAUNCH_DIR = OUT_ROOT / 'launches' / LAUNCH_ID
LOCAL = Path(os.environ.get('LOCAL_STATE_DIR', '/tmp/wholerun_14'))  # in the container: job list, claims, append lock
T0 = float(os.environ.get('DRIVER_T0') or time.time())
CURRENT = {}                                                         # the session this worker process is running

# The task result's `error` text of an infrastructure failure (the lists of analysis/analyze_14.py).
INFRA_ERRORS = ('Snapshot file not found', 'Unexpected evaluation worker error', 'Missing test specification',
                'Failed to apply test_patch', 'Evaluation error:')
CONTEXT_ERRORS = ('ContextWindowExceeded', 'context length', 'context window', 'maximum context')
SERVER_ERRORS = ('APIConnectionError', 'ServiceUnavailable', 'InternalServerError', 'Connection refused', 'ConnectError',
                 'ConnectionError', 'RemoteDisconnected', 'ServerDisconnected', 'litellm.Timeout', 'APITimeoutError',
                 'RateLimitError', 'NotFoundError', 'AuthenticationError', 'Bad Gateway', 'Gateway Timeout')


def log(*a):
    print(f'[{time.time() - T0:7.0f}s]', *a, flush=True)


# ------------------------------------------------------------------ the two changes under test
# Copied verbatim from analysis/modal_g/forks_09_runner.py (pre-registration 09); changes_identity() compares the text.

BOUNDS = ('start_line', 'end_line')
GRAPH_TOOLS = ('get_code_neighbors', 'search_similar_code', 'get_code_subgraph')


def restore_bounds(args):
    """In place: give a mangled line-bound name its plain name. Returns the plain names restored."""
    restored = []
    for name in list(args):
        plain = re.sub(r'[\\"\'\s]', '', str(name))
        if (not str(name).isidentifier()) and plain in BOUNDS:
            value = args.pop(name)
            args.setdefault(plain, value)  # a well-formed name wins if both are present
            restored.append(plain)
    return restored


def honor_bounds(agent, tally):
    """Arms AF and EF: restore mangled line-bound names of read_file before the call reaches the tool."""
    gate = agent.before_tool_callback

    def _restore_then_gate(tool, args, tool_context):
        if tool.name == 'read_file' and isinstance(args, dict) and restore_bounds(args):
            tally['restored_calls'] += 1
        return gate(tool, args, tool_context)

    agent.before_tool_callback = _restore_then_gate


_SPANS = {}


def spans_of(task):
    """{node name: {"file": ..., "lines": ...}} for the task (analysis/make_spans_g.py); empty if the file is missing."""
    if task not in _SPANS:
        p = INPUTS_G / 'spans' / f'{task}.json'
        _SPANS[task] = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    return _SPANS[task]


def _plain(name):
    name = str(name)
    return name.split(';', 1)[1] if ';' in name else name


def add_addresses(tool_name, response, spans):
    """The answer of a graph tool with an address on every entity that resolves, or None if nothing applies."""
    if not isinstance(response, dict) or response.get('status') != 'ok':
        return None

    def entry(n):
        e = {'name': n}
        e.update(spans.get(_plain(n), {}))
        return e

    out = dict(response)
    if tool_name == 'get_code_neighbors' and isinstance(response.get('neighbors'), list):
        out['neighbors'] = [entry(str(n)) for n in response['neighbors']]
        return out
    if tool_name == 'get_code_subgraph' and isinstance(response.get('nodes'), list):
        out['nodes'] = [entry(str(n)) for n in response['nodes']]
        return out
    if tool_name == 'search_similar_code' and isinstance(response.get('results'), list):
        results = []
        for item in response['results']:
            if isinstance(item, dict) and 'node_name' in item:
                new = {}
                for key, value in item.items():
                    new[key] = value
                    if key == 'node_name':
                        new.update(spans.get(_plain(value), {}))
                results.append(new)
            else:
                results.append(item)
        out['results'] = results
        return out
    return None


def address_answers(agent, spans, tally):
    """Arms NA and NAF: add addresses to the answers of the three graph tools before the model sees them."""
    previous = agent.after_tool_callback

    def _address(tool, args, tool_context, tool_response):
        if previous is not None:
            altered = previous(tool=tool, args=args, tool_context=tool_context, tool_response=tool_response)
            if altered is not None:
                tool_response = altered
        if tool.name in GRAPH_TOOLS:
            new = add_addresses(tool.name, tool_response, spans)
            if new is not None:
                tally['addressed_answers'] += 1
                return new
        return None

    agent.after_tool_callback = _address


CHANGE_NAMES = ('BOUNDS', 'GRAPH_TOOLS', '_SPANS', 'restore_bounds', 'honor_bounds', 'spans_of', '_plain',
                'add_addresses', 'address_answers')


def changes_identity(reference=None, mine=None):
    """Whether each definition above equals the one in forks_09_runner.py, compared as source text."""
    import ast

    reference = Path(reference or INPUTS_G / 'forks_09_runner.py')
    if not reference.exists():
        return {'reference': None, 'same': {}}

    def definitions(path):
        src = Path(path).read_text(encoding='utf-8')
        out = {}
        for node in ast.parse(src).body:
            if isinstance(node, ast.FunctionDef) and node.name in CHANGE_NAMES:
                out[node.name] = ast.get_source_segment(src, node)
            elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                  and getattr(node.targets[0], 'id', None) in CHANGE_NAMES):
                out[node.targets[0].id] = ast.unparse(node.value)
        return out

    a, b = definitions(reference), definitions(mine or __file__)
    return {'reference': reference.name, 'reference_md5': md5(reference),
            'same': {n: n in a and a[n] == b.get(n) for n in CHANGE_NAMES}}


def _no_gate(tool, args, tool_context):
    """Stands where replay_k's gate stood under honor_bounds in the 09 runner: here every call runs."""
    return None


def apply_condition(agent):
    """The step of the evaluator's path that is wrapped: the agent the harness has just compiled, before it builds
    its App and Runner. Both conditions get the seed; NAF also gets the two changes, in the 09 runner's order."""
    job = CURRENT
    job['compile_calls'] = job.get('compile_calls', 0) + 1
    cfg = getattr(agent, 'generate_content_config', None)
    if cfg is not None:
        cfg.seed = job['seed']  # as replay_k.run_k_steps; adk_submission forwards it with every model request
        thinking = getattr(cfg, 'thinking_config', None)
        job['sampling'] = {'temperature': cfg.temperature, 'top_p': cfg.top_p, 'max_output_tokens': cfg.max_output_tokens,
                           'thinking_budget': getattr(thinking, 'thinking_budget', None),
                           'include_thoughts': getattr(thinking, 'include_thoughts', None), 'seed': cfg.seed}
    job['seed_set'] = cfg is not None
    if job['condition'] == 'NAF':
        if agent.before_tool_callback is None:
            agent.before_tool_callback = _no_gate
        honor_bounds(agent, job['tally'])
        address_answers(agent, spans_of(job['task']), job['tally'])
        job['changes_applied'] = ['honor_bounds', 'address_answers']
    return agent


def install_observers():
    """Wrap three names the harness looks up at call time. Only the first changes anything (apply_condition); the
    other two record what the two phases returned and how long they took."""
    import swegemma.evaluate as evaluate
    import swegemma.harness.agent_runner as agent_runner

    compile_original = agent_runner.compile_submission
    phase1_original, phase2_original = evaluate.run_agent_sandbox, evaluate.verify_task

    @functools.wraps(compile_original)
    def compile_submission(*args, **kwargs):
        return apply_condition(compile_original(*args, **kwargs))

    @functools.wraps(phase1_original)
    async def run_agent_sandbox(*args, **kwargs):
        t = time.time()
        try:
            patch, error, trace = await phase1_original(*args, **kwargs)
        finally:
            CURRENT['phase1_seconds'] = round(time.time() - t, 1)
        CURRENT['agent_error'] = error
        return patch, error, trace

    @functools.wraps(phase2_original)
    async def verify_task(*args, **kwargs):
        t = time.time()
        CURRENT['phase2_ran'] = True
        try:
            return await phase2_original(*args, **kwargs)
        finally:
            CURRENT['phase2_seconds'] = round(time.time() - t, 1)

    agent_runner.compile_submission = compile_submission
    evaluate.run_agent_sandbox = run_agent_sandbox
    evaluate.verify_task = verify_task


# ------------------------------------------------------------------ small helpers

def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    rows = []
    if Path(path).exists():
        for line in open(path, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def run_root():
    """Where the condition folders live."""
    if MODE != 'full':
        return OUT_ROOT / MODE / LAUNCH_ID
    return OUT_ROOT / 'shards' / f'{SHARD_K}of{SHARD_M}' if SHARD_M else OUT_ROOT


def results_dir(cond):
    return run_root() / cond / f'seed{SEED}'


def is_infrastructure(row):
    """The task result is an infrastructure failure, by its `error` text (the rules of analysis/analyze_14.py)."""
    err = str(row.get('error') or row.get('error_message') or '')
    if any(k in err for k in INFRA_ERRORS):
        return True
    return ('Sandbox execution error' in err and not any(k.lower() in err.lower() for k in CONTEXT_ERRORS)
            and any(k in err for k in SERVER_ERRORS))


def fresh_tasks():
    """The 106 tasks of pre-registration 09 (those with a public base trace)."""
    path = INPUTS_G / 'fresh_states.jsonl'
    return sorted({json.loads(line)['task'] for line in open(path, encoding='utf-8') if line.strip()}) if path.exists() else []


def shuffled(ids):
    ids = sorted(ids)
    random.Random(0).shuffle(ids)  # fixed order, so a partial run is a random subset
    return ids


def task_order():
    """The tasks in run order: the lines of TASKS_FILE (mode validate writes it), else the 106 shuffled."""
    if TASKS_FILE and TASKS_FILE != 'fresh':
        ids = [line.strip() for line in open(TASKS_FILE, encoding='utf-8') if line.strip()]
        assert ids and len(ids) == len(set(ids)), f'{TASKS_FILE}: empty, or a task is listed twice'
        return ids
    return shuffled(fresh_tasks())


def done_tasks(cond):
    """Tasks with a result for this condition and seed, in the main folder or any shard's (the last line counts)."""
    if MODE != 'full':
        return set()
    last = {}
    paths = [OUT_ROOT / cond / f'seed{SEED}' / 'task_results.jsonl']
    paths += [Path(p) for p in sorted(glob.glob(str(OUT_ROOT / 'shards' / '*' / cond / f'seed{SEED}' / 'task_results.jsonl')))]
    for p in paths:
        for r in jsonl(p):
            last[r.get('instance_id')] = r
    return {t for t, r in last.items() if not (RETRY_INFRA and is_infrastructure(r))}


def plan_jobs():
    """(the order, [[condition, task, position in the order], ...])."""
    if MODE == 'validate':
        return [], []
    order = task_order()
    position = {t: i for i, t in enumerate(order, start=1)}
    tasks = order[:LIMIT_TASKS] if LIMIT_TASKS else order
    if MODE != 'full':  # one fastapi, one rich, one requests task: the first of each in the order (three tasks at least)
        pool = [t for t in order if (INPUTS_G / 'spans' / f'{t}.json').exists()] or order  # NAF needs the addresses
        tasks = [next(t for t in pool if t.startswith(p)) for p in ('fastapi_', 'rich_', 'requests_')
                 if any(t.startswith(p) for t in pool)]
        tasks += [t for t in pool if t not in tasks][:max(0, 3 - len(tasks))]
    if SHARD_M:
        tasks = [t for t in tasks if (position[t] - 1) % SHARD_M == SHARD_K]
    done = {c: done_tasks(c) for c in CONDITIONS}
    jobs = []
    for n, t in enumerate(tasks):  # a task's two sessions are adjacent, so they run side by side under the same load
        for c in (CONDITIONS if n % 2 == 0 else CONDITIONS[::-1]):
            if t not in done[c]:
                jobs.append([c, t, position[t]])
    return order, jobs


@contextlib.contextmanager
def append_lock():
    import fcntl

    with open(LOCAL / 'append.lock', 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def claim(jobs):
    """The first job no worker has taken yet, or None."""
    for cond, tid, idx in jobs:
        try:
            fd = os.open(str(LOCAL / 'claims' / f'{cond}__{tid}'), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        os.close(fd)
        return cond, tid, idx
    return None


def choose_locale():
    """LANG and LC_ALL of every sandbox command (the sandbox passes them through), as replay_k.choose_locale."""
    try:
        have = subprocess.run(['locale', '-a'], capture_output=True, text=True, timeout=30).stdout.lower().split()
    except (OSError, subprocess.SubprocessError):
        have = []
    name = 'en_US.UTF-8' if 'enusutf8' in {h.replace('-', '').replace('_', '') for h in have} else 'C.UTF-8'
    os.environ['LANG'] = name
    os.environ['LC_ALL'] = name
    return name


def first_line(cmd):
    try:
        return (subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip().splitlines() or [None])[0]
    except (OSError, subprocess.SubprocessError):
        return None


def missing_modules(text):
    return sorted(set(re.findall(r"No module named '([\w.]+)'", text or '')))


# ------------------------------------------------------------------ 1. install the wheelhouse, then the harness (as the 09 runner)

def install_harness():
    for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth', '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
        for pth in glob.glob(pth_pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    tmp_whl = Path('/tmp/wheelhouse')
    tmp_whl.mkdir(parents=True, exist_ok=True)
    for w in WHEELHOUSE.glob('*.whl'):
        if 'cutlass' in w.name.lower():
            continue
        name = w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name
        target = tmp_whl / name
        if not target.exists():
            os.symlink(w, target)
    wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
    log(f'installing {len(wheels)} wheelhouse wheels')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
    variants = {'v28': ['adk_eval_core-0.1.0', 'adk_submission-0.2.12', 'swegemma-0.2.7'],
                'latest': ['adk_eval_core-0.1.0', 'adk_submission-0.2.13', 'swegemma-0.2.11']}
    harness_wheels = [str(next(INPUTS.glob(f'{stem}-*.whl'))) for stem in variants[HARNESS_VARIANT]]
    log(f'installing harness variant {HARNESS_VARIANT}: {[Path(w).name for w in harness_wheels]}')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *harness_wheels], check=True)
    shim = INPUTS_H / 'imp.py'  # the competition's sandbox image ships this file (data/docker/imp.py) for Python >= 3.12
    if shim.exists() and importlib.util.find_spec('imp') is None:
        import sysconfig
        shutil.copy(shim, Path(sysconfig.get_paths()['purelib']) / 'imp.py')
        log('copied the imp shim of the competition sandbox image into site-packages')
    importlib.invalidate_caches()


def record_versions(locale_name, order, jobs):
    freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    LAUNCH_DIR.mkdir(parents=True, exist_ok=True)
    (LAUNCH_DIR / 'pip_freeze_14.txt').write_text(freeze)
    lines = freeze.splitlines()
    sandbox_env = {'locale': locale_name, 'git': first_line(['git', '--version']), 'patch': first_line(['patch', '--version']),
                   'git_identity': [first_line(['git', 'config', '--get', 'user.name']), first_line(['git', 'config', '--get', 'user.email'])],
                   'imp_shim': importlib.util.find_spec('imp') is not None, 'python': sys.version, 'platform': sys.platform}
    fingerprint = hashlib.md5(('\n'.join(sorted(lines)) + json.dumps(sandbox_env, sort_keys=True)).encode()).hexdigest()[:12]
    keep = ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'google-genai', 'vllm', 'litellm', 'transformers',
            'torch', 'pytest', 'inline-snapshot', 'dirty-equals', 'pytest-httpbin', 'trustme', 'pydantic', 'pydantic-core',
            'starlette', 'fastapi', 'httpx', 'anyio', 'rich', 'requests')
    identity = changes_identity()
    versions = {
        'experiment': EXPERIMENT, 'launch': LAUNCH_ID, 'mode': MODE, 'scripted_model': FAKE,
        'harness_variant': HARNESS_VARIANT, 'conditions': CONDITIONS, 'seed': SEED, 'shard': SHARD or None,
        'tasks_file': TASKS_FILE or 'fresh',
        'tasks_file_md5': md5(TASKS_FILE) if TASKS_FILE and TASKS_FILE != 'fresh' and Path(TASKS_FILE).exists() else None,
        'budget': BUDGET, 'events_compaction': COMPACTION, 'context_cache': CONTEXT_CACHE, 'sandbox': 'subprocess',
        'concurrency': CONCURRENCY, 'time_budget_s': TIME_BUDGET_S, 'guard_s': GUARD_S, 'retry_infrastructure': RETRY_INFRA,
        'tasks_in_order': len(order), 'order_md5': hashlib.md5(' '.join(order).encode()).hexdigest(), 'sessions_planned': len(jobs),
        'packages': [l for l in lines if l.split('==')[0].split(' @ ')[0].lower().replace('_', '-') in keep],
        'wheelhouse_files': sorted(p.name for p in WHEELHOUSE.glob('*.whl')),
        'model_path': MODEL_PATH, 'model_files': sorted(p.name for p in Path(MODEL_PATH).glob('*'))[:40] if MODEL_PATH else [],
        'platform': 'modal', 'python': sys.version, 'tensor_parallel_size': int(os.environ.get('TP_SIZE', '1')),
        'sandbox_environment': sandbox_env, 'environment_fingerprint': fingerprint, 'cpus': os.cpu_count(),
        'changes_same_as_09_runner': identity,
        'input_md5': {p.name: md5(p) for p in (Path(__file__), TASKS, INPUTS_G / 'fresh_states.jsonl', INPUTS / 'agent.yaml',
                                               INPUTS / 'sampling.yaml', INPUTS / 'system.md') if p.exists()},
        'gpu': subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], capture_output=True,
                              text=True).stdout.strip().splitlines() if shutil.which('nvidia-smi') else [],
    }
    (LAUNCH_DIR / 'versions_14.json').write_text(json.dumps(versions, indent=1))
    log('versions:', versions['packages'])
    log('sandbox environment:', sandbox_env, '| fingerprint', fingerprint)
    log('the two changes equal the 09 runner\'s definitions:', identity)
    return versions


def build_agent_dir():
    """The base agent, from the same three files as the 09 runner."""
    (AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
    (AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)
    shutil.copy(INPUTS / 'agent.yaml', AGENT_DIR / 'agent.yaml')
    shutil.copy(INPUTS / 'sampling.yaml', AGENT_DIR / 'configs' / 'sampling.yaml')
    shutil.copy(INPUTS / 'system.md', AGENT_DIR / 'prompts' / 'system.md')


# ------------------------------------------------------------------ 2. the harness configuration and the model

def make_config(cond, models, results=None):
    """The evaluation config of the public whole runs: subprocess sandbox, their budget, the scoring script's
    compaction and cache settings, the graph files of the competition data."""
    from google.adk.agents.context_cache_config import ContextCacheConfig
    try:
        from google.adk.apps._configs import EventsCompactionConfig
    except ImportError:
        from google.adk.apps.app import EventsCompactionConfig
    from swegemma.config import EvalConfig, build_submission_limits

    limits, generation = build_submission_limits()
    return EvalConfig(
        tasks_path=TASKS, snapshots_dir=SNAPSHOTS, results_dir=Path(results or results_dir(cond)), submission_dir=AGENT_DIR,
        models=models, sandbox='subprocess', timeout_seconds=BUDGET['timeout_seconds'],
        max_time_minutes=BUDGET['max_time_minutes'], max_tool_calls=BUDGET['max_tool_calls'], max_turns=BUDGET['max_turns'],
        limits=limits, generation_constraints=generation, adapter_manifest=None,
        context_cache_config=ContextCacheConfig(**CONTEXT_CACHE), events_compaction_config=EventsCompactionConfig(**COMPACTION),
        graph_dir=str(COMP / 'graphs'), embeddings_dir=str(COMP / 'embeddings'), verbose=False, display_mode='quiet')


def vllm_config():
    """The server settings of the 09 runner."""
    from adk_submission import VllmConfig

    return VllmConfig(model=MODEL_PATH, port=8000, host='127.0.0.1', tool_call_parser='gemma4', reasoning_parser='gemma4',
                      default_chat_template_kwargs={'enable_thinking': True}, max_model_len=32768, dtype='bfloat16',
                      gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
                      tensor_parallel_size=int(os.environ.get('TP_SIZE', '1')), startup_timeout=60 * 25)


def server_alive():
    if FAKE:
        return True
    for _ in range(3):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5)
    return False


def model_registry(served):
    """The registry the 09 runner takes from its server object, built here from the same settings and served id."""
    import litellm
    from adk_submission import VllmServer

    litellm.drop_params = True
    return VllmServer(vllm_config(), adapter_manifest=None).create_model_registry(
        aliases={TARGET: served}, model_prefix='openai/', api_key='EMPTY')


def scripted_registry():
    """Mode check only: a scripted model. Per task it calls a graph tool on a real node, reads a file the reference
    patch changes with mangled line-bound names, applies the reference patch, submits, and ends with a text."""
    from adk_submission import ModelRegistry
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    class _Scripted(BaseLlm):
        model: str = 'scripted'

        async def generate_content_async(self, llm_request, stream=False):
            i = CURRENT.get('scripted_calls', 0)
            CURRENT['scripted_calls'] = i + 1
            script = CURRENT['script']
            calls = script[min(i, len(script) - 1)]
            parts = [types.Part(function_call=types.FunctionCall(name=n, args=a, id=f'scripted-{i}-{j}'))
                     for j, (n, a) in enumerate(calls)] or [types.Part(text='I am done.')]
            yield LlmResponse(content=types.Content(role='model', parts=parts),
                              usage_metadata=types.GenerateContentResponseUsageMetadata(
                                  prompt_token_count=1000 + i, candidates_token_count=10, total_token_count=1010 + i))

    registry = ModelRegistry()
    registry.register(TARGET, _Scripted())
    return registry


def script_for(task):
    named = sorted(n for n, v in spans_of(task.instance_id).items() if 'lines' in v)
    changed = re.findall(r'^--- a/(\S+)', task.patch, re.M) or ['README.md']
    return [
        [('get_code_neighbors', {'node': named[len(named) // 2] if named else 'main'})],
        [('read_file', {'filepath': changed[0], 'start_line"': 5, 'end_line"': 9})],
        [('write_file', {'filepath': 'reference_14.patch', 'content': task.patch.rstrip('\n') + '\n'})],
        [('run_command', {'command': 'git apply reference_14.patch && rm -f reference_14.patch && git status --short | head -n 20'})],
        [('submit_patch', {})],
        [],
    ]


# ------------------------------------------------------------------ 3. one session, and what is recorded about it

def agent_ending(patch_submitted, agent_error):
    """How the agent session ended, from what the harness's Phase 1 itself returned (the task result's `error` is
    cleared on a resolved run and can be replaced by a reason from the tests). The labels of analysis/analyze_14.py."""
    e = agent_error or ''
    if 'Sandbox execution error' in e:
        if any(k.lower() in e.lower() for k in CONTEXT_ERRORS):
            return 'context window'
        return 'model server failed' if any(k in e for k in SERVER_ERRORS) else 'agent error (other)'
    if 'tool call budget' in e:
        return 'tool-call budget'
    if 'session timeout' in e:
        return 'time budget'
    if 'turns budget' in e or 'maximum allowed LLM turns' in e:
        return 'turns budget'
    if patch_submitted:
        return 'submitted'
    if 'without calling submit_patch' in e:
        return 'no patch'           # no submit_patch call and nothing changed on disk
    return 'no submit_patch call'   # the nudges brought no submit_patch; the changes on disk became the patch


def interface_failures(agent_error, error, test_exit_code, resolved, phase2_ran):
    """Failures apart from the model's choices, as labels. The agent side, then the test side."""
    out = []
    e = agent_error or ''
    if e.startswith('Sandbox execution error'):
        if any(k.lower() in e.lower() for k in CONTEXT_ERRORS):
            out.append('context_overflow')
        elif any(k in e for k in SERVER_ERRORS):
            out.append('model_server_error')
        else:
            out.append('agent_loop_error')
    err = error or ''
    if 'Unexpected evaluation worker error' in err or 'Snapshot file not found' in err:
        out.append('sandbox_setup_failure')
    elif err.startswith('Failed to apply agent patch'):
        out.append('agent_patch_did_not_apply')
    elif err.startswith('Failed to apply test_patch') or err.startswith('Evaluation error') or err.startswith('Missing test specification'):
        out.append('tests_could_not_run')
    elif phase2_ran and test_exit_code == 124:
        out.append('tests_timed_out')
    elif phase2_ran and test_exit_code in (2, 3, 4, 5):  # pytest: interrupted or collection error, internal error, usage error, no tests
        out.append('tests_could_not_run')
    elif phase2_ran and test_exit_code == 0 and not resolved:
        out.append('junit_check_failed')
    return out


def trace_stats(path):
    """Counts read from the saved trace alone (nothing here depends on the runner's own bookkeeping)."""
    try:
        steps = json.load(open(path, encoding='utf-8'))['steps']
    except (OSError, ValueError, KeyError):
        return {}
    st = collections.Counter()
    errors = collections.Counter()
    for s in steps:
        kind = (s.get('extra') or {}).get('event_type') or ''
        st['nudges'] += kind == 'continuation_nudge'
        st['compactions'] += kind == 'compaction'
        st['model_steps'] += s.get('source') == 'agent'
        st['max_prompt_tokens'] = max(st['max_prompt_tokens'], (s.get('metrics') or {}).get('prompt_tokens') or 0)
        for tc in s.get('tool_calls') or []:
            name, args = tc.get('function_name'), tc.get('arguments') or {}
            st['calls'] += 1
            st[f'calls_{name}'] += 1
            if name == 'read_file' and any((not str(a).isidentifier()) and re.sub(r'[\\"\'\s]', '', str(a)) in BOUNDS for a in args):
                st['reads_with_mangled_bound'] += 1
        obs = s.get('observation') or {}
        name = (obs.get('extra') or {}).get('tool_name')
        try:
            content = json.loads(obs.get('content') or 'null')
        except (ValueError, TypeError):
            content = None
        if not isinstance(content, dict):
            continue
        if content.get('status') == 'error':
            errors[f'{name}:{content.get("error_type")}'] += 1
        if name in GRAPH_TOOLS and content.get('status') == 'ok':
            st['graph_answers_ok'] += 1
            entries = content.get('neighbors') or content.get('nodes') or content.get('results') or []
            st['graph_answers_with_address'] += any(isinstance(x, dict) and ('file' in x or 'lines' in x) for x in entries)
    out = {k: int(v) for k, v in sorted(st.items())}
    out['tool_errors'] = dict(sorted(errors.items()))
    return out


def harness_versions():
    out = []
    for name in ('swegemma', 'adk_submission', 'adk_eval_core'):
        try:
            out.append(f'{name} {importlib.metadata.version(name)}')
        except importlib.metadata.PackageNotFoundError:
            out.append(f'{name} ?')
    return ', '.join(out)


async def run_session(ev, cond, task, idx, n_total, wid):
    """One task under one condition through Evaluator.evaluate_task; the harness's writer, then one line of extra.jsonl."""
    from swegemma.context import SwegemmaContext
    from swegemma.harness.verification import save_trace_artifact
    from swegemma.models import TaskResult
    from swegemma.results import append_task_result

    cfg = ev.config
    tally = collections.Counter()
    CURRENT.clear()
    CURRENT.update(condition=cond, task=task.instance_id, seed=SEED, tally=tally)
    if FAKE:
        CURRENT['script'] = script_for(task)
    context = SwegemmaContext(  # as Evaluator.run builds it for each task
        docker_manager=ev.docker, container_id='', problem_statement=task.problem_statement,
        hints_text=getattr(task, 'hints_text', '') or '', task=task, repo=task.repo, graph_dir=cfg.graph_dir,
        embeddings_dir=cfg.embeddings_dir, budget=cfg.budget, harness=cfg.harness)
    started, t = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), time.time()
    crash = None
    try:
        res = await asyncio.wait_for(ev.evaluate_task(task, task_index=idx, total_tasks=n_total, context=context), timeout=GUARD_S)
    except Exception as e:  # noqa: BLE001  (as Evaluator.run records a task whose evaluation raised)
        crash = traceback.format_exc()[-3000:]
        what = f'guard timeout after {GUARD_S} s' if isinstance(e, asyncio.TimeoutError) else f'{type(e).__name__}: {e}'
        res = TaskResult(instance_id=task.instance_id, repo=task.repo, resolved=False, agent_patch='', test_output='',
                         test_exit_code=-1, duration_seconds=time.time() - t,
                         error=f'Unexpected evaluation worker error: {what}', total_llm_calls=context.llm_calls_used,
                         tool_calls=context.tool_calls_used, task_index=idx)
        with contextlib.suppress(Exception):
            ev.docker.cleanup_all()
    safe = task.instance_id.replace('/', '__')
    trace_path = cfg.results_dir / 'traces' / f'trace_{safe}.json'
    if not trace_path.exists() and getattr(res, 'trace', None) is not None:
        save_trace_artifact(res.trace, cfg.results_dir, task.instance_id)  # the harness skips this on an evaluation error
    agent_error = CURRENT.get('agent_error')
    phase2_ran = bool(CURRENT.get('phase2_ran'))
    extra = {
        'task': task.instance_id, 'condition': cond, 'seed': SEED, 'repo': task.repo, 'order_index': idx,
        'launch': LAUNCH_ID, 'mode': MODE, 'shard': SHARD or None, 'worker': wid, 'scripted_model': FAKE,
        'harness': harness_versions(), 'harness_variant': HARNESS_VARIANT, 'started_utc': started,
        'resolved': bool(res.resolved), 'test_exit_code': res.test_exit_code, 'error': res.error, 'agent_error': agent_error,
        'agent_ending': agent_ending(context.patch_submitted, agent_error) if crash is None else 'worker error',
        'patch_submitted': bool(context.patch_submitted), 'patch_bytes': len(res.agent_patch or ''),
        'tool_calls': context.tool_calls_used, 'model_calls': context.llm_calls_used, 'total_tokens': context.total_tokens,
        'agent_minutes': round(context.agent_elapsed_seconds / 60, 2), 'wall_minutes': round((time.time() - t) / 60, 2),
        'phase1_seconds': CURRENT.get('phase1_seconds'), 'phase2_seconds': CURRENT.get('phase2_seconds'), 'phase2_ran': phase2_ran,
        'seed_set': bool(CURRENT.get('seed_set')), 'sampling': CURRENT.get('sampling'), 'compile_calls': CURRENT.get('compile_calls', 0),
        'changes_applied': CURRENT.get('changes_applied', []),
        'addressed_answers': int(tally['addressed_answers']), 'restored_calls': int(tally['restored_calls']),
        'interface_failures': interface_failures(agent_error, res.error, res.test_exit_code, res.resolved, phase2_ran),
        'missing_modules': missing_modules(res.test_output), 'trace': trace_stats(trace_path), 'crash': crash,
    }
    with append_lock():
        append_task_result(res, cfg.results_dir, None)
        with open(cfg.results_dir / 'extra.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(extra) + '\n')
    log(f'[w{wid:02d}] {cond:3s} {task.instance_id:16s} resolved={extra["resolved"]} ending={extra["agent_ending"]!r} '
        f'tools={extra["tool_calls"]} model_calls={extra["model_calls"]} agent_min={extra["agent_minutes"]} '
        f'patch={extra["patch_bytes"]} test_exit={extra["test_exit_code"]} addressed={extra["addressed_answers"]} '
        f'restored={extra["restored_calls"]} failures={extra["interface_failures"]} {(res.error or "")[:100]}')


def worker_main():
    import logging

    from swegemma.evaluate import Evaluator
    from swegemma.models import load_tasks

    logging.getLogger('opentelemetry').setLevel(logging.CRITICAL)
    wid = int(os.environ['WORKER_ID'])
    jobs = json.load(open(LOCAL / 'jobs.json'))
    n_total = int(os.environ['ORDER_LENGTH'])
    tasks = {t.instance_id: t for t in load_tasks(TASKS)}
    models = scripted_registry() if FAKE else model_registry(os.environ['SERVED_ID'])
    install_observers()
    evaluators = {}

    async def loop():
        while True:
            if time.time() - T0 > TIME_BUDGET_S:
                log(f'[w{wid:02d}] time budget reached: no new session')
                return
            if (LOCAL / 'stop').exists() or not server_alive():
                (LOCAL / 'stop').touch()
                log(f'[w{wid:02d}] the model server does not answer, or a stop was requested: no new session')
                return
            job = claim(jobs)
            if job is None:
                return
            cond, tid, idx = job
            if cond == 'NAF' and not (INPUTS_G / 'spans' / f'{tid}.json').exists():
                (LOCAL / 'stop').touch()  # the driver checks this before it starts; never run NAF without addresses
                raise SystemExit(f'[w{wid:02d}] no address file for {tid}: stopping')
            if cond not in evaluators:
                evaluators[cond] = Evaluator(make_config(cond, models))
            await run_session(evaluators[cond], cond, tasks[tid], idx, n_total, wid)

    asyncio.run(loop())


# ------------------------------------------------------------------ 4. validation: do the tests really run in this sandbox?

def validate_main():
    """Mode validate. Every task of tasks.jsonl that has a snapshot goes through the harness's test phase
    (verify_task: fresh sandbox, the patch applied, the task's test_patch applied, the tests run) twice: with its
    reference patch as the agent's patch (must come out resolved) and with an empty patch (must not). One line per
    task in validate/validate.jsonl; the tasks that pass both in validate/tasks_ok.txt, in run order."""
    from adk_submission import ModelRegistry
    from swegemma.deduplication import resolve_task_snapshot_paths
    from swegemma.evaluate import Evaluator
    from swegemma.harness.verification import verify_task
    from swegemma.models import load_tasks

    out = OUT_ROOT / 'validate'
    (out / 'test_outputs').mkdir(parents=True, exist_ok=True)
    tasks = load_tasks(TASKS)
    cfg = make_config('validate', ModelRegistry(), results=out)
    ev = Evaluator(cfg)
    paths = {t.instance_id: resolve_task_snapshot_paths(cfg.snapshots_dir, t.instance_id, t.repo) for t in tasks}
    have = [t for t in tasks if paths[t.instance_id][0].exists()]
    log(f'validate: {len(tasks)} tasks in tasks.jsonl, {len(have)} with a snapshot')
    got = collections.defaultdict(dict)

    async def run():
        sem = asyncio.Semaphore(int(os.environ.get('VALIDATE_CONCURRENCY', '6')))

        async def one(task, kind):
            async with sem:
                t = time.time()
                snap, base_snap, patch_path = paths[task.instance_id]
                try:
                    res = await verify_task(ev.docker, cfg, task, snap, base_snapshot_path=base_snap, patch_path=patch_path,
                                            agent_patch=task.patch if kind == 'gold' else '', start_time=time.perf_counter())
                    text = res.test_output or ''
                    (out / 'test_outputs' / f'{task.instance_id}.{kind}.log').write_text(text, encoding='utf-8')
                    summary = [line.strip() for line in text.splitlines() if re.search(r'\d+ (passed|failed|error)', line)]
                    r = {'resolved': bool(res.resolved), 'test_exit_code': res.test_exit_code, 'error': res.error,
                         'missing_modules': missing_modules(text), 'pytest_line': summary[-1] if summary else None}
                except Exception as e:  # noqa: BLE001
                    r = {'resolved': False, 'test_exit_code': None, 'error': f'validation raised {type(e).__name__}: {e}',
                         'missing_modules': [], 'pytest_line': None}
                r['seconds'] = round(time.time() - t, 1)
                got[task.instance_id][kind] = r

        await asyncio.gather(*(one(t, k) for t in have for k in ('gold', 'empty')))

    asyncio.run(run())
    with contextlib.suppress(Exception):
        ev.docker.cleanup_all()
    fresh = set(fresh_tasks())
    rows = []
    for task in sorted(tasks, key=lambda t: t.instance_id):
        tid = task.instance_id
        g, e = got[tid].get('gold') or {}, got[tid].get('empty') or {}
        rows.append({
            'task': tid, 'repo': task.repo, 'snapshot': tid in got,
            'gold_resolved': bool(g.get('resolved')), 'empty_resolved': bool(e.get('resolved')),
            'ok': bool(g.get('resolved')) and tid in got and not e.get('resolved'),
            'gold_test_exit_code': g.get('test_exit_code'), 'empty_test_exit_code': e.get('test_exit_code'),
            'gold_seconds': g.get('seconds'), 'empty_seconds': e.get('seconds'),
            'gold_error': g.get('error') if tid in got else 'no snapshot', 'empty_error': e.get('error'),
            'gold_pytest_line': g.get('pytest_line'), 'empty_pytest_line': e.get('pytest_line'),
            'gold_missing_modules': g.get('missing_modules', []),
            'in_fresh_states': tid in fresh, 'address_file': (INPUTS_G / 'spans' / f'{tid}.json').exists(),
            'environment_fingerprint': os.environ.get('ENV_FINGERPRINT'), 'launch': LAUNCH_ID})
    with open(out / 'validate.jsonl', 'w', encoding='utf-8') as f:
        f.writelines(json.dumps(r) + '\n' for r in rows)
    ok = shuffled(r['task'] for r in rows if r['ok'])
    (out / 'tasks_ok.txt').write_text('\n'.join(ok) + '\n', encoding='utf-8')
    by_repo = {}
    for r in rows:
        d = by_repo.setdefault(r['repo'], collections.Counter())
        d.update(tasks=1, snapshot=r['snapshot'], gold_resolved=r['gold_resolved'], empty_resolved=r['empty_resolved'], ok=r['ok'])
    seconds = [x for r in rows for x in (r['gold_seconds'], r['empty_seconds']) if x is not None]
    summary = {
        'launch': LAUNCH_ID, 'environment_fingerprint': os.environ.get('ENV_FINGERPRINT'), 'tasks': len(rows),
        'with_snapshot': sum(r['snapshot'] for r in rows), 'gold_resolved': sum(r['gold_resolved'] for r in rows),
        'empty_resolved': sum(r['empty_resolved'] for r in rows), 'ok': len(ok),
        'by_repo': {k: dict(v) for k, v in sorted(by_repo.items())},
        'tasks_ok_md5': hashlib.md5(('\n'.join(ok) + '\n').encode()).hexdigest(),
        'ok_of_the_fresh_states': sum(r['ok'] for r in rows if r['in_fresh_states']), 'fresh_states': len(fresh),
        'fresh_states_not_ok': sorted(r['task'] for r in rows if r['in_fresh_states'] and not r['ok']),
        'ok_outside_the_fresh_states': sorted(r['task'] for r in rows if r['ok'] and not r['in_fresh_states']),
        'ok_without_address_file': sorted(r['task'] for r in rows if r['ok'] and not r['address_file']),
        'seconds_per_check_mean': round(sum(seconds) / max(1, len(seconds)), 1),
    }
    (out / 'summary_validate.json').write_text(json.dumps(summary, indent=1))
    for name in ('validate.jsonl', 'tasks_ok.txt', 'summary_validate.json'):
        shutil.copy(out / name, LAUNCH_DIR / name)

    print(f'\nVALIDATION, environment {summary["environment_fingerprint"]}: {summary["tasks"]} tasks, '
          f'{summary["with_snapshot"]} with a snapshot', flush=True)
    print(f'{"repository":18s} tasks  gold resolves  empty resolves  ok (gold resolves, empty does not)')
    for repo, d in sorted(by_repo.items()):
        print(f'{repo:18s} {d["tasks"]:5d} {d["gold_resolved"]:14d} {d["empty_resolved"]:15d} {d["ok"]:4d}')
    print(f'{"all":18s} {summary["tasks"]:5d} {summary["gold_resolved"]:14d} {summary["empty_resolved"]:15d} {summary["ok"]:4d}')
    print(f'of the {len(fresh)} fresh-state tasks: {summary["ok_of_the_fresh_states"]} ok; not ok: {summary["fresh_states_not_ok"]}')
    print(f'ok outside the fresh-state tasks: {summary["ok_outside_the_fresh_states"]}')
    print(f'ok tasks without an address file (NAF cannot run them yet): {summary["ok_without_address_file"]}')
    for r in rows:
        if r['snapshot'] and not r['gold_resolved']:
            print(f'  gold does not resolve: {r["task"]:16s} exit {r["gold_test_exit_code"]} | {r["gold_pytest_line"]} | '
                  f'{r["gold_error"]} | missing modules {r["gold_missing_modules"]}')
    for r in rows:
        if r['empty_resolved']:
            print(f'  empty patch resolves:  {r["task"]:16s} exit {r["empty_test_exit_code"]} | {r["empty_pytest_line"]}')
    print(f'wrote {out}/validate.jsonl, tasks_ok.txt ({len(ok)} tasks, md5 {summary["tasks_ok_md5"]}), summary_validate.json; '
          f'{summary["seconds_per_check_mean"]} s per check', flush=True)


# ------------------------------------------------------------------ 5. summaries

def write_summary(d):
    """summary.json in the harness's format (swegemma.results), from the last line of each task in task_results.jsonl."""
    last = {}
    for r in jsonl(Path(d) / 'task_results.jsonl'):
        last[r.get('instance_id')] = r
    if not last:
        return None
    by_repo = {}
    for r in last.values():
        g = by_repo.setdefault(str(r.get('repo') or ''), {'total': 0, 'resolved': 0, 'rate': 0.0})
        g['total'] += 1
        g['resolved'] += bool(r.get('resolved'))
    for g in by_repo.values():
        g['rate'] = g['resolved'] / g['total']
    resolved = sum(bool(r.get('resolved')) for r in last.values())
    data = {'total_tasks': len(last), 'resolved': resolved, 'resolution_rate': round(resolved / len(last), 4),
            'by_repo': by_repo, 'errors': sum(1 for r in last.values() if r.get('error') is not None)}
    tmp = Path(d) / f'summary.json.tmp.{os.getpid()}'
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    tmp.replace(Path(d) / 'summary.json')
    return data


def print_table(root):
    """Per task and condition: how the session ended, calls, minutes, patch, tests, what the changes did."""
    print('\ntask             cond agent session ended   tools model agent_min patch_B test_exit resolved addressed restored '
          'graph_ok with_addr mangled failures', flush=True)
    rows = []
    for cond in CONDITIONS:
        rows += jsonl(Path(root) / cond / f'seed{SEED}' / 'extra.jsonl')
    for r in sorted(rows, key=lambda r: (r['order_index'], r['condition'])):
        tr = r.get('trace') or {}
        print(f'{r["task"]:16s} {r["condition"]:4s} {r["agent_ending"]:21s} {r["tool_calls"]:5d} {r["model_calls"]:5d} '
              f'{r["agent_minutes"]:9.2f} {r["patch_bytes"]:7d} {r["test_exit_code"]:9d} {str(r["resolved"]):8s} '
              f'{r["addressed_answers"]:9d} {r["restored_calls"]:8d} {tr.get("graph_answers_ok", 0):8d} '
              f'{tr.get("graph_answers_with_address", 0):9d} {tr.get("reads_with_mangled_bound", 0):7d} '
              f'{r["interface_failures"] or ""}', flush=True)
    for cond in CONDITIONS:
        sel = [r for r in rows if r['condition'] == cond]
        if sel:
            print(f'{cond}: {len(sel)} sessions, resolved {sum(r["resolved"] for r in sel)}, model calls per session '
                  f'{sum(r["model_calls"] for r in sel) / len(sel):.1f}, tool calls {sum(r["tool_calls"] for r in sel) / len(sel):.1f}, '
                  f'agent minutes {sum(r["agent_minutes"] for r in sel) / len(sel):.2f}, wall minutes '
                  f'{sum(r["wall_minutes"] for r in sel) / len(sel):.2f}, addressed answers {sum(r["addressed_answers"] for r in sel)}, '
                  f'restored calls {sum(r["restored_calls"] for r in sel)}, seed set {sum(r["seed_set"] for r in sel)}/{len(sel)}', flush=True)
    for r in rows:  # one line of a test log: the tests ran
        log_path = Path(root) / r['condition'] / f'seed{SEED}' / 'test_outputs' / f'{r["task"]}.log'
        if r.get('phase2_ran') and log_path.exists():
            lines = [l for l in log_path.read_text(encoding='utf-8', errors='replace').splitlines() if re.search(r'\d+ (passed|failed|error)', l)]
            print(f'test log, {r["condition"]} {r["task"]}: {lines[-1].strip() if lines else "(no pytest summary line)"}', flush=True)
    return rows


def merge_main(root):
    """After a sharded run: build <root>/<condition>/seed<k>/ from <root>/shards/*/<condition>/seed<k>/."""
    root = Path(root)
    for d in sorted(glob.glob(str(root / 'shards' / '*' / '*' / 'seed*'))):
        d = Path(d)
        dest = root / d.parent.name / d.name
        dest.mkdir(parents=True, exist_ok=True)
        for name in ('task_results.jsonl', 'extra.jsonl'):
            have = {l for l in open(dest / name, encoding='utf-8')} if (dest / name).exists() else set()
            new = [l for l in open(d / name, encoding='utf-8')] if (d / name).exists() else []
            with open(dest / name, 'a', encoding='utf-8') as f:
                f.writelines(l for l in new if l not in have)
        for sub in ('patches', 'test_outputs', 'traces', 'logs'):
            if (d / sub).is_dir():
                shutil.copytree(d / sub, dest / sub, dirs_exist_ok=True)
        print(d.relative_to(root), '->', dest.relative_to(root), write_summary(dest))


# ------------------------------------------------------------------ 6. the driver

def driver_main():
    locale_name = choose_locale()
    install_harness()
    shutil.rmtree(LOCAL / 'claims', ignore_errors=True)
    (LOCAL / 'claims').mkdir(parents=True, exist_ok=True)
    (LOCAL / 'stop').unlink(missing_ok=True)
    assert all(c in ALL_CONDITIONS for c in CONDITIONS) and CONDITIONS, CONDITIONS
    assert not SHARD or 0 <= SHARD_K < SHARD_M, SHARD
    order, jobs = plan_jobs()
    versions = record_versions(locale_name, order, jobs)
    same = versions['changes_same_as_09_runner']['same']
    if not same or not all(same.values()):
        raise SystemExit(f'the copied changes differ from forks_09_runner.py: {same}')
    build_agent_dir()
    fingerprint = versions['environment_fingerprint']
    env = dict(os.environ, DRIVER_T0=str(T0), LAUNCH_ID=LAUNCH_ID, ORDER_LENGTH=str(len(order)), ENV_FINGERPRINT=fingerprint)
    if MODE == 'validate':
        return subprocess.run([sys.executable, __file__, 'validate'], env=env).returncode

    # the task list must have been validated in this very sandbox environment, and NAF needs every task's addresses
    listed = bool(TASKS_FILE and TASKS_FILE != 'fresh')
    validated = OUT_ROOT / 'validate' / 'summary_validate.json'
    if validated.exists():
        v = json.load(open(validated))
        same_env = v.get('environment_fingerprint') == fingerprint
        log(f'validation {v.get("launch")}: {v.get("ok")} tasks ok; its environment {v.get("environment_fingerprint")} '
            f'{"equals" if same_env else "DIFFERS FROM"} this one ({fingerprint})')
        if listed and versions['tasks_file_md5'] != v.get('tasks_ok_md5'):
            log(f'WARNING: {TASKS_FILE} is not the list that validation wrote (md5 {versions["tasks_file_md5"]}, '
                f'validation {v.get("tasks_ok_md5")})')
        if MODE == 'full' and listed and not same_env and os.environ.get('ALLOW_OTHER_ENVIRONMENT') != '1':
            raise SystemExit('the task list was validated in another environment: run mode validate again with this image')
    elif MODE == 'full' and listed:
        raise SystemExit(f'{validated} is missing: run mode validate first')
    elif MODE == 'full':
        log('WARNING: no validated task list given: the tasks are the 106 of fresh_states.jsonl, not checked in this sandbox')
    if 'NAF' in CONDITIONS:
        missing = sorted({t for c, t, _ in jobs if c == 'NAF' and not (INPUTS_G / 'spans' / f'{t}.json').exists()})
        if missing:
            raise SystemExit(f'no address file under {INPUTS_G}/spans for {len(missing)} tasks of condition NAF: {missing}')
    (LOCAL / 'jobs.json').write_text(json.dumps(jobs))
    (LAUNCH_DIR / 'jobs_14.json').write_text(json.dumps({'order': order, 'jobs': jobs}))
    log(f'mode {MODE}: {len(order)} tasks in the order ({TASKS_FILE or "fresh"}), {len(jobs)} sessions to run, conditions '
        f'{CONDITIONS}, seed {SEED}, shard {SHARD or "none"}, budget {BUDGET}, results under {run_root()}')

    server, served = None, 'scripted'
    if jobs and not FAKE:  # the model: vLLM as the 09 runner starts it
        import litellm
        from adk_submission import VllmServer

        litellm.drop_params = True
        server = VllmServer(vllm_config(), adapter_manifest=None)
        server.start()
        log('vLLM up at', server.base_url)
        with urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=30) as r:
            served = json.load(r)['data'][0]['id']
        log('served model id:', served)

    n_workers = min(CONCURRENCY, len(jobs))
    t_sessions = time.time()
    procs = [subprocess.Popen([sys.executable, __file__, 'worker'], env=dict(env, WORKER_ID=str(w), SERVED_ID=served))
             for w in range(n_workers)]
    log(f'{n_workers} workers started')
    status, last_report = 'finished', time.time()
    while any(p.poll() is None for p in procs):
        time.sleep(5)
        if server is not None and server.process is not None and server.process.poll() is not None:
            status = 'the model server exited'
        elif HARD_STOP_S and time.time() - T0 > HARD_STOP_S:
            status = f'hard stop after {HARD_STOP_S} s'
        if status != 'finished':
            (LOCAL / 'stop').touch()
            log(status + ': stopping the workers; sessions still running leave no result')
            for p in procs:
                if p.poll() is None:
                    p.terminate()
            time.sleep(10)
            for p in procs:
                if p.poll() is None:
                    p.kill()
            break
        if time.time() - last_report > 300:
            last_report = time.time()
            n = {c: len(jsonl(results_dir(c) / 'extra.jsonl')) for c in CONDITIONS}
            log(f'progress: sessions written {n}, workers alive {sum(p.poll() is None for p in procs)}')
    codes = [p.wait() for p in procs]
    log(f'workers done ({status}); exit codes {collections.Counter(codes).most_common()}; '
        f'{(time.time() - t_sessions) / 60:.1f} minutes of sessions')

    for c in CONDITIONS:
        d = results_dir(c)
        if d.exists():
            log(f'{c}: summary {write_summary(d)}')
            for name in ('versions_14.json', 'platform_actual_14.json', 'pip_freeze_14.txt'):
                if (LAUNCH_DIR / name).exists():
                    shutil.copy(LAUNCH_DIR / name, d / name)
    rows = print_table(run_root())
    if server is not None:
        try:
            if getattr(server, 'log_path', None) and Path(server.log_path).exists():
                shutil.copy(server.log_path, LAUNCH_DIR / 'vllm_server_14.log')
        except Exception as e:  # noqa: BLE001
            log('could not copy the server log:', e)
        server.stop()
    wrong = [r for r in rows if r['condition'] == 'N' and (r['addressed_answers'] or r['restored_calls'] or r['changes_applied']
                                                         or (r.get('trace') or {}).get('graph_answers_with_address'))]
    if wrong:
        log('ERROR: condition N shows a change:', [(r['task'], r['addressed_answers'], r['restored_calls']) for r in wrong])
    log('done')
    return 0 if status == 'finished' and not any(codes) and not wrong else 1


if __name__ == '__main__':
    if ROLE == 'worker':
        worker_main()
    elif ROLE == 'validate':
        validate_main()
    elif ROLE == 'merge':
        merge_main(sys.argv[2])
    else:
        sys.exit(driver_main())
