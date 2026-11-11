"""Experiment 24 (BUILD, not registered): the design of pre-registration 20 ("asked or told": arms NONE, TOLD, TOLDX and
ASKED on the paused steps of analysis/make_states_t.py) replayed on the hosted models of pre-registration 19, with the
model call sent to an OpenAI-compatible inference API instead of a local vLLM server.

What is reused, and how:
  - the messages. They are built exactly as in 20: the same states file (analysis/fork_states_t/states.jsonl, one
    record per (step, arm), each with its own history and, for TOLD and TOLDX, its note under
    `arms[<arm>]['user_text']`), the same replay.py, agent.yaml, sampling.yaml and system.md read from the volume's
    inputs folder (the files 19 and 20 read), the agent compiled by replay.build_agent and each replay made by
    replay.run_one_step. A record is replayed under the runner arm of 20 (forks_20_modal.RUNNER_ARM): records NONE
    and ASKED under arm A (nothing added: the history ends on its last tool result), records TOLD and TOLDX under the
    arm of the same name (replay.arm_messages delivers the note as one user message after the last tool result).
    The order of the steps is that of 20 (forks_20_modal.state_order, random.Random(20) over the steps as the file
    lists them; each step's records NONE, TOLD, TOLDX, ASKED one after the other, then seeds 1 to 3); the launcher
    computes it with the function of 20 and hands it over in PLAN_FILE.
  - the API path of 19. analysis/modal_g/forks_19_runner.py cannot be imported: it installs the harness wheels,
    reads the API's model list and runs its replays when it is loaded. Its code is therefore reused by copy, and
    every part that touches the request or the reply is kept as it is there: the harness wheels (v28), the LiteLlm
    client registered under the agent's configured model name, litellm.drop_params, the reasoning parameters removed
    after the agent is compiled (so the provider's default applies), no stop string, the agent's output limit, the
    temperature and top-p of sampling.yaml, the seed sent per replay (seeds 1 to 3, one agent per seed), the retries,
    the price guard, the preflight, the stop after 10 API failures in a row, the resume rule, the row's `api` record,
    the row's `thought` left empty.
What differs from 19's runner (all recorded in versions.json):
  - the states and jobs come from 20's states file and the plan, not from DESIGN 10 or 17; a row gains
    `record_arm` (NONE, TOLD, TOLDX or ASKED) and `state_id`, and keeps 20's row form otherwise (arm = the runner arm,
    fork = '<agent step>:<record arm>');
  - the row gains `raw_reply`: the reply as the API returned it (the text content, the tool calls with their
    argument strings unparsed, the reasoning text if the API returns it in a separate field, the finish reason). The
    scored output is still the first tool call as the agent framework parsed it (`next_call`);
  - MAX_CALLS caps the API attempts of a session (retries included); 0 = no cap. The plumbing check sets it;
  - CAPTURE_REQUESTS=1 (the plumbing check only) writes every request's messages, tool names and sampling
    parameters to OUT_DIR/requests.jsonl, so the check can compare the arms' messages.

Environment: INPUTS_DIR, COMP_DIR, OUT_DIR, AGENT_DIR, HARNESS_VARIANT, STATES_FILE, PLAN_FILE, SEEDS (comma list),
CONCURRENCY, API_BASE, API_MODEL, NEBIUS_API_KEY, MAX_DOLLARS, MAX_OUTPUT_TOKENS, MAX_RETRIES, MAX_CALLS,
REQUEST_TIMEOUT_S, TIME_BUDGET_S, PREFLIGHT (1/0), CAPTURE_REQUESTS (1/0). Writes OUT_DIR/results.jsonl (resumable:
finished (task, run, fork, arm, seed) cells are skipped, except rows whose call got no reply from the API, which move
to api_errors_retried.jsonl and are replayed again), versions.json, summary.json, and fatal.txt when it stops on a
guard. The key is read from the environment only; it is never written, and every error text is scrubbed of it.
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
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'          # the agent's configured model name, as in the runners of 10, 19 and 20
HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')
SEEDS = [int(s) for s in os.environ['SEEDS'].split(',') if s]
CONCURRENCY = int(os.environ.get('CONCURRENCY', '8'))
API_BASE = os.environ['API_BASE'].rstrip('/')
API_MODEL = os.environ['API_MODEL']
KEY = os.environ.get('NEBIUS_API_KEY', '')
MAX_DOLLARS = float(os.environ.get('MAX_DOLLARS', '1.0'))
MAX_OUTPUT_TOKENS = int(os.environ.get('MAX_OUTPUT_TOKENS', '0') or 0)
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '6'))
MAX_CALLS = int(os.environ.get('MAX_CALLS', '0') or 0)
REQUEST_TIMEOUT_S = float(os.environ.get('REQUEST_TIMEOUT_S', '600'))
TIME_BUDGET_S = int(os.environ.get('TIME_BUDGET_S', str(5 * 3600)))
PREFLIGHT = os.environ.get('PREFLIGHT', '1') != '0'
CAPTURE = os.environ.get('CAPTURE_REQUESTS', '0') == '1'
ABORT_AFTER = 10                                  # API failures in a row, with no success, that stop the run
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


def plain(obj):
    """A JSON-ready copy of a message or reply object (dicts, lists, pydantic and litellm objects)."""
    if isinstance(obj, dict):
        return {str(k): plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, 'model_dump'):
        return plain(obj.model_dump())
    if hasattr(obj, '__dict__'):
        return plain({k: v for k, v in vars(obj).items() if not k.startswith('_')})
    return str(obj)


# ------------------------------------------------------------------ 1. the harness wheels (no GPU wheelhouse), as in 19
VARIANTS = {'v28': ['adk_eval_core-0.1.0', 'adk_submission-0.2.12', 'swegemma-0.2.7'],
            'latest': ['adk_eval_core-0.1.0', 'adk_submission-0.2.13', 'swegemma-0.2.11']}
harness_wheels = [str(next(INPUTS.glob(f'{stem}-*.whl'))) for stem in VARIANTS[HARNESS_VARIANT]]
log(f'installing harness variant {HARNESS_VARIANT}: {[Path(w).name for w in harness_wheels]}')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *harness_wheels], check=True)
importlib.invalidate_caches()

# ------------------------------------------------------------------ 2. preflight: the API must list the model, as in 19
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

# ------------------------------------------------------------------ 3. the model client, as create_model_registry builds it (as in 19)
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
CELL = contextvars.ContextVar('cell', default=None)   # (task, run, fork, record arm, seed) of the replay in progress
STATS = {'calls_started': 0, 'attempts': 0, 'replies': 0, 'api_failures': 0, 'retries': 0, 'rate_limited': 0,
         'prompt_tokens': 0, 'completion_tokens': 0, 'cached_prompt_tokens': 0, 'dollars': 0.0,
         'consecutive_failures': 0, 'stopped_by': None, 'reported_models': collections.Counter(),
         'finish_reasons': collections.Counter(), 'error_kinds': collections.Counter()}
FIRST_REQUEST = {}
REQ_PATH = OUT / 'requests.jsonl'
if CAPTURE:
    REQ_PATH.write_text('')


def spent():
    return STATS['prompt_tokens'] * PRICE_IN + STATS['completion_tokens'] * PRICE_OUT


def calls_capped():
    return bool(MAX_CALLS) and STATS['attempts'] >= MAX_CALLS


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


class CallCapReached(RuntimeError):
    pass


class ApiClient(LiteLLMClient):
    """LiteLLMClient with retries and a per-call record; the request itself is the one ADK built (as in 19), plus the
    raw reply and, in the plumbing check, the request's messages."""

    async def acompletion(self, model, messages, tools, **kwargs):
        rec = CALL.get()
        if rec is None:
            rec = {}
        if not FIRST_REQUEST:
            FIRST_REQUEST.update({k: v for k, v in kwargs.items() if k not in ('api_key', 'messages', 'tools')})
            FIRST_REQUEST.update(model=model, n_messages=len(messages), n_tools=len(tools or []))
        if CAPTURE:
            tl = plain(tools or [])
            cell = CELL.get() or (None,) * 5
            with open(REQ_PATH, 'a', encoding='utf-8') as g:
                g.write(json.dumps({
                    'task': cell[0], 'run': cell[1], 'fork': cell[2], 'record_arm': cell[3], 'seed': cell[4],
                    'model': model, 'messages': plain(messages),
                    'tool_names': [_get(_get(t, 'function'), 'name') for t in tl],
                    'tools_md5': hashlib.md5(json.dumps(tl, sort_keys=True).encode()).hexdigest(),
                    'params': {k: plain(v) for k, v in kwargs.items() if k not in ('api_key', 'api_base', 'messages', 'tools')},
                }) + '\n')
        rec.setdefault('attempts', [])
        STATS['calls_started'] += 1
        for attempt in range(MAX_RETRIES + 1):
            if calls_capped():
                rec['api_error'] = f'MAX_CALLS ({MAX_CALLS}) reached before this attempt'
                STATS['api_failures'] += 1
                STATS['stopped_by'] = STATS['stopped_by'] or f'max calls ({MAX_CALLS})'
                raise CallCapReached(rec['api_error'])
            STATS['attempts'] += 1
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
                if kind != 'client' and attempt < MAX_RETRIES and not calls_capped():
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
            rec['raw_reply'] = {
                'content': _get(msg, 'content'),
                'tool_calls': [{'id': _get(tc, 'id'), 'type': _get(tc, 'type'),
                                'name': _get(_get(tc, 'function'), 'name'),
                                'arguments': _get(_get(tc, 'function'), 'arguments')} for tc in tcs],
                'reasoning_content': reasoning or None,
                'finish_reason': _get(choice, 'finish_reason'),
            }
            STATS['prompt_tokens'] += pt
            STATS['completion_tokens'] += ct
            STATS['cached_prompt_tokens'] += cached
            STATS['reported_models'][str(reported)] += 1
            STATS['finish_reasons'][str(rec['finish_reason'])] += 1
            STATS['dollars'] = spent()
            return resp


# ------------------------------------------------------------------ 4. states, plan and agents (replay.py from the volume)
sys.path.insert(0, str(INPUTS))
import replay  # noqa: E402

replay.DATA = COMP  # the tools never run, but the context wants graph and embedding directories
STATES_FILE = os.environ['STATES_FILE']
PLAN_FILE = os.environ['PLAN_FILE']
plan = json.load(open(PLAN_FILE, encoding='utf-8'))
RUNNER_ARM = plan['runner_arm']                   # forks_20_modal.RUNNER_ARM
RECORD_ARMS = plan['record_arms']                 # forks_20_modal.RECORD_ARMS: the order of a step's records
recs = [json.loads(l) for l in open(STATES_FILE, encoding='utf-8')]
by = {(r['state_id'], r['arm']): r for r in recs}
assert set(r['arm'] for r in recs) <= set(RECORD_ARMS), 'a record arm outside the plan'
missing = [k for k in plan['order'] if (k, 'NONE') not in by]
assert not missing, f'steps of the plan not in the states file: {missing[:3]}'
order = [by[(k, a)] for k in plan['order'] for a in RECORD_ARMS if (k, a) in by]
jobs_all = [(r, RUNNER_ARM[r['arm']], seed) for r in order for seed in SEEDS]
log(f'{len(plan["order"])} steps, {len(order)} records, seeds {SEEDS}, {len(jobs_all)} replays planned '
    f'({dict(collections.Counter(r["arm"] for r in order))} records by arm)')

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
    'experiment': '24', 'harness_variant': HARNESS_VARIANT,
    'packages': [l for l in freeze if l.split('==')[0].split(' @ ')[0].lower().replace('_', '-') in
                 ('swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'google-genai', 'litellm', 'openai', 'httpx')],
    'harness_wheels': [Path(w).name for w in harness_wheels],
    'md5': {'replay.py': md5(INPUTS / 'replay.py'), 'agent.yaml': md5(INPUTS / 'agent.yaml'),
            'sampling.yaml': md5(INPUTS / 'sampling.yaml'), 'system.md': md5(INPUTS / 'system.md'),
            'states_file': md5(STATES_FILE), 'plan_file': md5(PLAN_FILE), 'runner': md5(__file__)},
    'plan': {'steps': len(plan['order']), 'records': len(order), 'order_source': plan.get('order_source'),
             'runner_arm': RUNNER_ARM, 'record_arms': RECORD_ARMS},
    'api_host': urllib.parse.urlparse(API_BASE).netloc, 'api_model': API_MODEL, 'litellm_model': f'openai/{API_MODEL}',
    'api_listing': {k: (listing or {}).get(k) for k in ('quantization', 'context_length', 'supported_features',
                                                        'supported_sampling_parameters', 'per_request_limits', 'pricing')},
    'price_per_million': {'prompt': PRICE_IN * 1e6, 'completion': PRICE_OUT * 1e6},
    'reasoning_parameter': 'none sent (provider default)', 'removed_from_request': REMOVED,
    'reasoning_in_rows': 'row field thought left empty, as in 19; the reasoning text, if the API returns it in a '
                         'separate field, is in raw_reply.reasoning_content and its length in api.reasoning_chars',
    'stop_sequences': None, 'max_output_tokens': gen.max_output_tokens, 'temperature': gen.temperature, 'top_p': gen.top_p,
    'seeds': SEEDS, 'seed_note': 'sent as the request seed; whether the provider honours it is not known',
    'concurrency': CONCURRENCY, 'max_dollars': MAX_DOLLARS, 'max_retries': MAX_RETRIES, 'max_calls': MAX_CALLS,
    'capture_requests': CAPTURE, 'request_timeout_s': REQUEST_TIMEOUT_S, 'time_budget_s': TIME_BUDGET_S,
    'thoughts_in_history': False, 'platform': 'modal, CPU only', 'python': sys.version,
}
(OUT / 'versions.json').write_text(json.dumps(versions, indent=1))


# ------------------------------------------------------------------ 5. the replays (as in 19)
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
        if calls_capped():
            STATS['stopped_by'] = f'max calls ({MAX_CALLS})'
            return None
        if STATS['consecutive_failures'] >= ABORT_AFTER:
            STATS['stopped_by'] = f'{ABORT_AFTER} API failures in a row'
            return None
        rec = {}
        CALL.set(rec)
        CELL.set((s['task'], s['run'], s.get('fork', 0), s['arm'], seed))
        out = await replay.run_one_step(agents[seed], s, arm, seed)
        if out.get('error'):
            out['error'] = scrub(out['error'])
            rec['error_kind'] = 'api' if rec.get('api_error') else 'adapter'
        rec['reasoning_chars_in_thought'] = len(out.get('thought') or '')
        out['thought'] = ''                         # reasoning returned in a separate field: the tool call only
        out['raw_reply'] = rec.pop('raw_reply', None)
        out['api'] = rec
        out['record_arm'] = s['arm']
        out['state_id'] = s['state_id']
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

# ------------------------------------------------------------------ 6. summary (as in 19, by record arm)
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
summary = {'experiment': '24', 'model': API_MODEL, 'rows': len(rows), 'replays_planned': len(jobs_all),
           'replays_planned_this_session': len(jobs), 'api_error_rows_replayed_again': retried,
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
