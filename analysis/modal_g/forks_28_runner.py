"""Pre-registration 28: forks_26_runner.py with record arm KF (analysis/make_states_28.py) added, runner arm A.

Pre-registration 26: the hosted runner of 19 (forks_19_runner.py, copied unchanged apart from the lines marked
"26") with one design added, DESIGN=25: the records of analysis/make_states_25.py (one per step and arm KH, KE, EL),
KH and KE replayed as they stand (runner arm A), EL with its note (runner arm EL), each row's fork
"<03's fork>:<record arm>:<seed>" as in the rows of 25. Records run in the file's order (the builder's fixed step
order, a step's three records together), seed-major. The docstring of 19 follows.

Experiment 19 (BUILD, not registered): the one-call replays of pre-registrations 10 and 15/17 with the model call
sent to a hosted, OpenAI-compatible inference API instead of a local vLLM server.

Why a separate runner: the runner of 10 (analysis/modal_g/forks_10_runner.py), which 17 also uses, installs the GPU
wheelhouse and starts a vLLM server unconditionally; no environment setting turns that off. Everything after the
server is kept as it is there:
  - the same harness wheels (v28) and the same replay.py, agent.yaml, sampling.yaml and system.md, read from the
    volume's inputs folder; the agent is compiled by replay.build_agent and each replay is replay.run_one_step;
  - the model is reached the way adk_submission's create_model_registry reaches the vLLM server: a LiteLlm client
    with the model `openai/<model id>`, an API base and a key, registered under the agent's configured model name,
    after the harness's litellm patch is installed; litellm.drop_params is set as in the runner of 10;
  - the states, arms, added messages and seeds come from the same files: design 10, analysis/fork_states_d (rows as
    the runner of 10 writes them); design 17, analysis/fork_states_s with one record per (state, arm), where records
    S and S0 are replayed as they stand (row arm `A`) and record S0N with its note (row arm `S0N`), as the runner of
    17 writes them.
Changes, all recorded in versions.json:
  - no reasoning parameter is sent. The harness turns the agent's thinking configuration into
    extra_body.chat_template_kwargs.enable_thinking and extra_body.thinking_token_budget; both are removed from the
    client's arguments after the agent is compiled, so the provider's default applies. No stop string is sent (the
    stop string of 10 and 17 was the closing tag of the hermes template of a local server, whose parsing is now the
    provider's). The output limit is the agent's (16,384) unless MAX_OUTPUT_TOKENS is set;
  - a model's reasoning returned in a separate field reaches the row only as its length (api.reasoning_chars); the
    row's `thought` stays empty, and the scored output is the tool call;
  - every call is wrapped: retries with exponential backoff on rate limits, 5xx answers, connection errors and
    timeouts (MAX_RETRIES); the row gains one key, `api`, with the model id the API reported, prompt and completion
    tokens, cached prompt tokens, whether the reply held a tool call, the finish reason, the attempts and their
    errors, and whether a failure was the API's (api_error) or came after a reply was received (adapter error).
    A reply with no tool call is a result, not an error, and is written like any other row.
Guards (no silent fallback): before any replay the API's model list must name the model (else exit 2); prices come
from that list (or PRICE_IN_PER_M / PRICE_OUT_PER_M) and no new call starts once the spent dollars pass MAX_DOLLARS;
after 10 API failures in a row with no success the run stops (exit 3); a reported model id other than the one asked
for is counted and flagged in summary.json.

Environment: INPUTS_DIR, COMP_DIR, OUT_DIR, AGENT_DIR, HARNESS_VARIANT, DESIGN (10 or 17), STATES_FILE, ARMS, SEEDS
(comma list), STATES_N (0 = all), CONCURRENCY, API_BASE, API_MODEL, NEBIUS_API_KEY, MAX_DOLLARS, MAX_OUTPUT_TOKENS,
MAX_RETRIES, REQUEST_TIMEOUT_S, TIME_BUDGET_S, PREFLIGHT (1/0). Writes OUT_DIR/results.jsonl (resumable: finished
(task, run, fork, arm, seed) cells are skipped, except rows whose call got no reply from the API, which move to
api_errors_retried.jsonl and are replayed again), versions.json, summary.json, and fatal.txt when it stops on a guard.
"""
import asyncio
import collections
import contextvars
import hashlib
import importlib
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

for k, v in (('LITELLM_LOCAL_MODEL_COST_MAP', 'True'), ('OTEL_SDK_DISABLED', 'true'), ('LITELLM_LOG', 'ERROR'),
             ('LITELLM_TELEMETRY', 'False')):
    os.environ.setdefault(k, v)

INPUTS = Path(os.environ['INPUTS_DIR'])
COMP = Path(os.environ['COMP_DIR'])
OUT = Path(os.environ['OUT_DIR'])
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'fatal.txt').unlink(missing_ok=True)       # a guard's stop of an earlier session is not this session's
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'          # the agent's configured model name, as in the runner of 10
HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')
DESIGN = os.environ['DESIGN']
assert DESIGN in ('10', '17', '25'), DESIGN  # 26
ARMS = [a for a in os.environ['ARMS'].split(',') if a]
SEEDS = [int(s) for s in os.environ['SEEDS'].split(',') if s]
STATES_N = int(os.environ.get('STATES_N', '0'))
CONCURRENCY = int(os.environ.get('CONCURRENCY', '8'))
API_BASE = os.environ['API_BASE'].rstrip('/')
API_MODEL = os.environ['API_MODEL']
KEY = os.environ.get('NEBIUS_API_KEY', '')
MAX_DOLLARS = float(os.environ.get('MAX_DOLLARS', '1.0'))
MAX_OUTPUT_TOKENS = int(os.environ.get('MAX_OUTPUT_TOKENS', '0') or 0)
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '6'))
REQUEST_TIMEOUT_S = float(os.environ.get('REQUEST_TIMEOUT_S', '600'))
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(5 * 3600)))
PREFLIGHT = os.environ.get('PREFLIGHT', '1') != '0'
ABORT_AFTER = 10                                  # API failures in a row, with no success, that stop the run
RECORD_ARMS_17 = {'S': 'A', 'S0': 'A', 'S0N': 'S0N'}
RECORD_ARMS_25 = {'KH': 'A', 'KE': 'A', 'EL': 'EL', 'KF': 'A'}  # 26; KF added for 28   # the runner's arm for each record arm (design 17)
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.0f}s]', *a, flush=True)


def scrub(text):
    """An error text with the key removed, in case a library ever echoes it."""
    text = str(text)
    return text.replace(KEY, '***') if KEY else text


def fatal(code, msg):
    print('FATAL:', scrub(msg), flush=True)
    (OUT / 'fatal.txt').write_text(scrub(msg) + '\n')
    sys.exit(code)


def md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


# ------------------------------------------------------------------ 1. the harness wheels (no GPU wheelhouse)
VARIANTS = {'v28': ['adk_eval_core-0.1.0', 'adk_submission-0.2.12', 'swegemma-0.2.7'],
            'latest': ['adk_eval_core-0.1.0', 'adk_submission-0.2.13', 'swegemma-0.2.11']}
harness_wheels = [str(next(INPUTS.glob(f'{stem}-*.whl'))) for stem in VARIANTS[HARNESS_VARIANT]]
log(f'installing harness variant {HARNESS_VARIANT}: {[Path(w).name for w in harness_wheels]}')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *harness_wheels], check=True)
importlib.invalidate_caches()

# ------------------------------------------------------------------ 2. preflight: the API must list the model
listing = {}
if PREFLIGHT:
    try:
        req = urllib.request.Request(API_BASE + '/models?verbose=true', headers={'Authorization': 'Bearer ' + KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r).get('data', [])
    except Exception as e:  # noqa: BLE001
        fatal(2, f'the API model list could not be read from {urllib.parse.urlparse(API_BASE).netloc}: {type(e).__name__}: {e}')
    listing = next((m for m in data if m.get('id') == API_MODEL), None)
    if listing is None:
        fatal(2, f'the API does not list the model {API_MODEL!r} ({len(data)} models listed); no fallback to another model')
pricing = (listing or {}).get('pricing') or {}
try:
    PRICE_IN = float(os.environ.get('PRICE_IN_PER_M') or float(pricing['prompt']) * 1e6) / 1e6
    PRICE_OUT = float(os.environ.get('PRICE_OUT_PER_M') or float(pricing['completion']) * 1e6) / 1e6
except (KeyError, TypeError, ValueError):
    fatal(2, f'no price for {API_MODEL!r}: neither the API listing nor PRICE_IN_PER_M / PRICE_OUT_PER_M give one')
log(f'model {API_MODEL} listed; price per million tokens: prompt {PRICE_IN * 1e6:.3f}, completion {PRICE_OUT * 1e6:.3f} dollars')

# ------------------------------------------------------------------ 3. the model client, as create_model_registry builds it
import litellm  # noqa: E402
from adk_submission import ModelRegistry  # noqa: E402
from adk_submission.resolvers.generation import install_litellm_reasoning_patch  # noqa: E402
from google.adk.models.lite_llm import LiteLlm, LiteLLMClient  # noqa: E402

litellm.drop_params = True
litellm.num_retries = 0                            # retries are this runner's, and recorded
litellm.telemetry = False
litellm.suppress_debug_info = True
install_litellm_reasoning_patch()
registry = ModelRegistry()
registry.register(TARGET, LiteLlm(model=f'openai/{API_MODEL}', api_base=API_BASE, api_key=KEY or 'EMPTY'))

CALL = contextvars.ContextVar('call', default=None)   # the api record of the replay in progress
STATS = {'calls_started': 0, 'replies': 0, 'api_failures': 0, 'retries': 0, 'rate_limited': 0, 'prompt_tokens': 0,
         'completion_tokens': 0, 'cached_prompt_tokens': 0, 'dollars': 0.0, 'consecutive_failures': 0,
         'stopped_by': None, 'reported_models': collections.Counter(), 'finish_reasons': collections.Counter(),
         'error_kinds': collections.Counter()}
FIRST_REQUEST = {}


def spent():
    return STATS['prompt_tokens'] * PRICE_IN + STATS['completion_tokens'] * PRICE_OUT


def classify(e):
    """'rate_limit', 'server', 'connection', 'timeout' (retried) or 'client' (not retried)."""
    name = type(e).__name__
    status = getattr(e, 'status_code', None)
    if isinstance(e, litellm.RateLimitError) or status == 429:
        return 'rate_limit'
    if isinstance(e, litellm.Timeout) or 'Timeout' in name:
        return 'timeout'
    if isinstance(e, litellm.APIConnectionError) or 'Connection' in name:
        return 'connection'
    if isinstance(e, (litellm.InternalServerError, litellm.ServiceUnavailableError)) or (isinstance(status, int) and status >= 500):
        return 'server'
    return 'client'


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ApiClient(LiteLLMClient):
    """LiteLLMClient with retries and a per-call record; the request itself is the one ADK built."""

    async def acompletion(self, model, messages, tools, **kwargs):
        rec = CALL.get()
        if rec is None:
            rec = {}
        if not FIRST_REQUEST:
            FIRST_REQUEST.update({k: v for k, v in kwargs.items() if k not in ('api_key', 'messages', 'tools')})
            FIRST_REQUEST.update(model=model, n_messages=len(messages), n_tools=len(tools or []))
        rec.setdefault('attempts', [])
        STATS['calls_started'] += 1
        for attempt in range(MAX_RETRIES + 1):
            t = time.time()
            try:
                resp = await litellm.acompletion(model=model, messages=messages, tools=tools, timeout=REQUEST_TIMEOUT_S, **kwargs)
            except Exception as e:  # noqa: BLE001
                kind = classify(e)
                wait = min(60.0, 2.0 ** attempt) * (1 + 0.25 * random.random())
                rec['attempts'].append({'error': scrub(f'{type(e).__name__}: {e}')[:400], 'kind': kind,
                                        'status': getattr(e, 'status_code', None), 'seconds': round(time.time() - t, 2)})
                STATS['error_kinds'][kind] += 1
                if kind == 'rate_limit':
                    STATS['rate_limited'] += 1
                if kind != 'client' and attempt < MAX_RETRIES:
                    STATS['retries'] += 1
                    await asyncio.sleep(wait)
                    continue
                rec['api_error'] = rec['attempts'][-1]['error']
                STATS['api_failures'] += 1
                STATS['consecutive_failures'] += 1
                raise
            rec['attempts'].append({'error': None, 'seconds': round(time.time() - t, 2)})
            STATS['replies'] += 1
            STATS['consecutive_failures'] = 0
            usage = _get(resp, 'usage')
            pt, ct = _get(usage, 'prompt_tokens') or 0, _get(usage, 'completion_tokens') or 0
            cached = _get(_get(usage, 'prompt_tokens_details'), 'cached_tokens') or 0
            reasoning_tok = _get(_get(usage, 'completion_tokens_details'), 'reasoning_tokens')
            choice = (_get(resp, 'choices') or [None])[0]
            msg = _get(choice, 'message')
            tcs = _get(msg, 'tool_calls') or []
            reasoning = _get(msg, 'reasoning_content') or ''
            reported = _get(resp, 'model')
            rec.update(model_reported=reported, prompt_tokens=pt, completion_tokens=ct, cached_prompt_tokens=cached,
                       reasoning_tokens=reasoning_tok, finish_reason=_get(choice, 'finish_reason'),
                       has_tool_call=bool(tcs), n_tool_calls=len(tcs), reasoning_chars=len(reasoning),
                       content_chars=len(_get(msg, 'content') or ''), response_id=_get(resp, 'id'))
            STATS['prompt_tokens'] += pt
            STATS['completion_tokens'] += ct
            STATS['cached_prompt_tokens'] += cached
            STATS['reported_models'][str(reported)] += 1
            STATS['finish_reasons'][str(rec['finish_reason'])] += 1
            STATS['dollars'] = spent()
            return resp


# ------------------------------------------------------------------ 4. states and agents (replay.py from the volume)
sys.path.insert(0, str(INPUTS))
import replay  # noqa: E402

replay.DATA = COMP  # the tools never run, but the context wants graph and embedding directories
STATES_FILE = os.environ['STATES_FILE']
recs = [json.loads(l) for l in open(STATES_FILE, encoding='utf-8')]
if DESIGN == '10':
    states = list(recs)
    random.Random(0).shuffle(states)               # the runner of 10's fixed order: a cut run is a random subset of states
    if STATES_N:
        states = states[:STATES_N]
    bad = [a for a in ARMS if any(a != 'A' and a not in s['arms'] for s in states)]
    assert not bad, f'arms not in the states: {bad}'
    jobs_all = [(s, arm, seed) for s in states for arm in ARMS for seed in SEEDS]
    n_states = len(states)
elif DESIGN == '25':  # 26
    bad = [a for a in ARMS if a not in RECORD_ARMS_25]
    assert not bad, f'design 25 arms are record arms KH, KE, EL; got {bad}'
    ids = list(dict.fromkeys(r['step_id'] for r in recs))
    keep = set(ids[:STATES_N] if STATES_N else ids)
    order = [r for r in recs if r['step_id'] in keep and r['arm'] in ARMS]
    jobs_all = [(dict(r, fork=f"{r['fork']}:{seed}"), RECORD_ARMS_25[r['arm']], seed) for seed in SEEDS for r in order]
    n_states = len(keep)
else:
    bad = [a for a in ARMS if a not in RECORD_ARMS_17]
    assert not bad, f'design 17 arms are record arms S, S0, S0N; got {bad}'
    ids = list(dict.fromkeys(r['state_id'] for r in recs))   # sha1 order of the file, as forks_17_modal.py keeps them
    keep = set(ids[:STATES_N] if STATES_N else ids)
    order = [r for r in recs if r['state_id'] in keep and r['arm'] in ARMS and r['arm'] != 'S0N'] \
        + [r for r in recs if r['state_id'] in keep and r['arm'] in ARMS and r['arm'] == 'S0N']
    jobs_all = [(r, RECORD_ARMS_17[r['arm']], seed) for r in order for seed in SEEDS]
    n_states = len(keep)
log(f'design {DESIGN}: {n_states} states, arms {ARMS}, seeds {SEEDS}, {len(jobs_all)} replays planned')

agent_dir = Path(os.environ.get('AGENT_DIR', '/root/agents/base'))
(agent_dir / 'prompts').mkdir(parents=True, exist_ok=True)
(agent_dir / 'configs').mkdir(parents=True, exist_ok=True)
shutil.copy(INPUTS / 'agent.yaml', agent_dir / 'agent.yaml')
shutil.copy(INPUTS / 'sampling.yaml', agent_dir / 'configs' / 'sampling.yaml')
shutil.copy(INPUTS / 'system.md', agent_dir / 'prompts' / 'system.md')
REMOVED = {}
agents = {}
for seed in SEEDS:
    task = {'instance_id': 'replay', 'repo': 'replay/replay', 'base_commit': ''}
    a = replay.build_agent(str(agent_dir), registry, task)
    a.generate_content_config.seed = seed
    if MAX_OUTPUT_TOKENS:
        a.generate_content_config.max_output_tokens = MAX_OUTPUT_TOKENS
    m = a.model
    if not isinstance(m, LiteLlm):
        fatal(2, f'the compiled agent does not hold a LiteLlm client but {type(m).__name__}')
    args = dict(m._additional_args or {})
    eb = dict(args.get('extra_body') or {})
    for k in ('chat_template_kwargs', 'thinking_token_budget'):
        if k in eb:
            REMOVED[f'extra_body.{k}'] = eb.pop(k)
    if 'reasoning_effort' in args:
        REMOVED['reasoning_effort'] = args.pop('reasoning_effort')
    if eb:
        args['extra_body'] = eb
    else:
        args.pop('extra_body', None)
    m._additional_args = args
    m.llm_client = ApiClient()
    agents[seed] = a
gen = agents[SEEDS[0]].generate_content_config
log('agents built; tools:', [getattr(t, 'name', getattr(t, '__name__', '?')) for t in agents[SEEDS[0]].tools])
log('removed from the request (provider default applies):', REMOVED)

freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout.splitlines()
versions = {
    'experiment': '28', 'design': DESIGN, 'harness_variant': HARNESS_VARIANT,
    'packages': [l for l in freeze if l.split('==')[0].split(' @ ')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'google-genai', 'litellm', 'openai', 'httpx')],
    'harness_wheels': [Path(w).name for w in harness_wheels],
    'md5': {'replay.py': md5(INPUTS / 'replay.py'), 'agent.yaml': md5(INPUTS / 'agent.yaml'),
            'sampling.yaml': md5(INPUTS / 'sampling.yaml'), 'system.md': md5(INPUTS / 'system.md'),
            'states_file': md5(STATES_FILE), 'runner': md5(__file__)},
    'api_host': urllib.parse.urlparse(API_BASE).netloc, 'api_model': API_MODEL, 'litellm_model': f'openai/{API_MODEL}',
    'api_listing': {k: (listing or {}).get(k) for k in ('quantization', 'context_length', 'supported_features',
                                                        'supported_sampling_parameters', 'per_request_limits', 'pricing')},
    'price_per_million': {'prompt': PRICE_IN * 1e6, 'completion': PRICE_OUT * 1e6},
    'reasoning_parameter': 'none sent (provider default)', 'removed_from_request': REMOVED,
    'reasoning_in_rows': 'length only (api.reasoning_chars); the row field thought is left empty',
    'stop_sequences': None, 'max_output_tokens': gen.max_output_tokens, 'temperature': gen.temperature, 'top_p': gen.top_p,
    'seeds': SEEDS, 'seed_note': 'sent as the request seed; whether the provider honours it is not known',
    'arms': ARMS, 'states_n': STATES_N, 'concurrency': CONCURRENCY, 'max_dollars': MAX_DOLLARS, 'max_retries': MAX_RETRIES,
    'request_timeout_s': REQUEST_TIMEOUT_S, 'time_budget_s': TIME_BUDGET_S, 'thoughts_in_history': False,
    'platform': 'modal, CPU only', 'python': sys.version,
}
(OUT / 'versions.json').write_text(json.dumps(versions, indent=1))


# ------------------------------------------------------------------ 5. the replays
def key_of(s, arm, seed):
    return (s['task'], s['run'], s.get('fork', 0), arm, seed)


done = set()
res_path = OUT / 'results.jsonl'
retried = 0
if res_path.exists():
    # On a resume, a row whose call never got a reply (api.error_kind 'api': no model output) is replayed again; it
    # moves to api_errors_retried.jsonl. Every other row, a reply without a tool call included, stays as it is.
    keep, again = [], []
    for line in open(res_path, encoding='utf-8'):
        try:
            r = json.loads(line)
        except ValueError:
            continue                                # a line cut short by a stop
        (again if (r.get('api') or {}).get('error_kind') == 'api' else keep).append(json.dumps(r) + '\n')
    if again:
        with open(OUT / 'api_errors_retried.jsonl', 'a', encoding='utf-8') as g:
            g.writelines(again)
    with open(res_path, 'w', encoding='utf-8') as g:
        g.writelines(keep)
    retried = len(again)
    for line in keep:
        r = json.loads(line)
        done.add((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']))
jobs = [j for j in jobs_all if key_of(*j) not in done]
log(f'{len(jobs)} replays to run ({len(jobs_all) - len(jobs)} already done; {retried} rows without an API reply '
    f'moved to api_errors_retried.jsonl and replayed again)')


async def one(s, arm, seed, sem):
    async with sem:
        if STATS['stopped_by']:
            return None
        if time.time() - T0 > TIME_BUDGET_S:
            STATS['stopped_by'] = 'time budget'
            return None
        if spent() >= MAX_DOLLARS:
            STATS['stopped_by'] = f'max dollars ({MAX_DOLLARS})'
            return None
        if STATS['consecutive_failures'] >= ABORT_AFTER:
            STATS['stopped_by'] = f'{ABORT_AFTER} API failures in a row'
            return None
        rec = {}
        CALL.set(rec)
        out = await replay.run_one_step(agents[seed], s, arm, seed)
        if out.get('error'):
            out['error'] = scrub(out['error'])
            rec['error_kind'] = 'api' if rec.get('api_error') else 'adapter'
        rec['reasoning_chars_in_thought'] = len(out.get('thought') or '')
        out['thought'] = ''                         # reasoning returned in a separate field: the tool call only
        out['api'] = rec
        if DESIGN == '17':
            out['record_arm'] = s['arm']
        return out


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    f = open(res_path, 'a', encoding='utf-8')
    n = 0

    async def run_and_write(s, arm, seed):
        nonlocal n
        o = await one(s, arm, seed, sem)
        if o is None:
            return
        f.write(json.dumps(o) + '\n')
        f.flush()
        n += 1
        if n % 25 == 0:
            log(f'{n} rows; {STATS["replies"]} replies, {STATS["api_failures"]} API failures, {STATS["retries"]} retries, '
                f'{STATS["rate_limited"]} rate limits, {spent():.4f} dollars')

    await asyncio.gather(*(asyncio.create_task(run_and_write(s, arm, seed)) for s, arm, seed in jobs))
    f.close()


t_run = time.time()
asyncio.run(main())
wall = time.time() - t_run

# ------------------------------------------------------------------ 6. summary
rows = [json.loads(l) for l in open(res_path, encoding='utf-8')]
by_arm = {}
for r in rows:
    a = r.get('record_arm', r['arm'])
    d = by_arm.setdefault(a, {'n': 0, 'errors': 0, 'api_errors': 0, 'adapter_errors': 0, 'with_call': 0, 'prompt_tokens': []})
    d['n'] += 1
    d['errors'] += bool(r.get('error'))
    d['api_errors'] += (r.get('api') or {}).get('error_kind') == 'api'
    d['adapter_errors'] += (r.get('api') or {}).get('error_kind') == 'adapter'
    d['with_call'] += bool(r.get('next_call'))
    if (r.get('usage') or {}).get('prompt_tokens'):
        d['prompt_tokens'].append(r['usage']['prompt_tokens'])
for d in by_arm.values():
    d['prompt_tokens_mean'] = round(statistics.mean(d['prompt_tokens']), 1) if d['prompt_tokens'] else None
    del d['prompt_tokens']
lat = [r['latency_s'] for r in rows if r.get('latency_s') is not None and not r.get('error')]
mismatch = {m: c for m, c in STATS['reported_models'].items() if m not in (API_MODEL, f'openai/{API_MODEL}')}
summary = {'design': DESIGN, 'model': API_MODEL, 'rows': len(rows), 'replays_planned_this_session': len(jobs),
           'api_error_rows_replayed_again': retried,
           'by_arm': by_arm, 'stats': {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in STATS.items()},
           'reported_model_other_than_asked': mismatch, 'dollars_this_session': round(spent(), 6),
           'wall_s_replays': round(wall, 1), 'latency_s_mean': round(statistics.mean(lat), 2) if lat else None,
           'latency_s_median': round(statistics.median(lat), 2) if lat else None,
           'seconds_per_call_at_concurrency': round(wall / STATS['calls_started'], 3) if STATS['calls_started'] else None,
           'first_request_params': {k: v for k, v in FIRST_REQUEST.items() if k != 'api_base'},
           'elapsed_s': round(time.time() - T0)}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=str))
log('summary:', json.dumps({k: summary[k] for k in ('rows', 'by_arm', 'dollars_this_session', 'seconds_per_call_at_concurrency',
                                                     'reported_model_other_than_asked')}, default=str))
log('stats:', json.dumps(summary['stats'], default=str))
if mismatch:
    log('WARNING: the API reported a model other than the one asked for:', mismatch)
if STATS['replies'] == 0 and STATS['calls_started']:
    fatal(3, f'no call reached the model ({STATS["api_failures"]} API failures); see the rows\' api.attempts')
if STATS['stopped_by'] and 'API failures' in STATS['stopped_by']:
    fatal(3, f'stopped: {STATS["stopped_by"]}')
log('done')
