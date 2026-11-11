"""Experiment 24 on Modal (BUILD, not registered): the design of pre-registration 20 ("asked or told": arms NONE, TOLD,
TOLDX and ASKED on the 53 paused steps of analysis/make_states_t.py, three seeds) replayed on the seven hosted models
of pre-registration 19, through the same OpenAI-compatible API. CPU only: no GPU, no vLLM.

The runner is analysis/modal_g/forks_24_runner.py (its docstring says what it keeps from 19's runner and 20's message
building, and what it changes); it is shipped in the image, not read from the volume. The states file, the harness
wheels and the agent files are the ones 19 and 20 read from the volume; the states file is checked by md5.

The plan (the steps and their order) is computed on this machine, at launch, by the functions of 20
(analysis/modal_g/forks_20_modal.py: state_order, RECORD_ARMS, RUNNER_ARM) from analysis/fork_states_t/states.jsonl,
which must have the md5 of the file on the volume; it is handed to the container as a plan file. Full run: all 53
steps in 20's order (random.Random(20)), each step's records NONE, TOLD, TOLDX, ASKED one after the other, seeds 1 to
3: 555 replays per model.

The API key is read from the local environment at launch and handed to the containers as an ephemeral secret
(modal.Secret.from_dict); it is never written to the volume, to a log or to a file of this repository. Each model runs
in its own container (all models of one launch in parallel). Output of the full run: /vol/out_24/<model id with /
replaced by __>/ with results.jsonl, versions.json, summary.json, platform_actual.json, pip_freeze.txt, runner.log,
plan.json (store with analysis/store_24.py).

Modes:
  --mode check   the plumbing check: ONE model, the first 2 steps of 20's order that have a TOLDX record, every arm,
                 seeds 1 to 3 (24 replays), at most 30 API attempts (retries included), the requests captured. Rows
                 go to /vol/out_24_check/<model>/ (cleared first; analysis/store_24.py never reads it). The container
                 then checks, per step and seed: every arm returned a parsed tool call; TOLD's messages are NONE's plus
                 one user message equal to the note; TOLDX's the same with its own note; ASKED's are NONE's plus the
                 recorded search call (an assistant message calling run_command with the recorded command) and its
                 result (a tool message); the tool declarations and sampling parameters are the same in every arm;
                 ASKED's prompt tokens equal those of 19's replay of the same step under arm S on the same model
                 (/vol/out_19/17/<model>/results.jsonl: the same request, so the same count). Exit 1 if a check fails.
  --mode full    the full run of every model given (--model all: the seven models of 19).
Commands (from Git Bash, the key loaded inside the same command; prefix MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8):
  modal run analysis/modal_g/forks_24_modal.py --mode check [--model Qwen/Qwen3-30B-A3B-Instruct-2507]
  modal run --detach analysis/modal_g/forks_24_modal.py --mode full --model all [--max-dollars 3]
--concurrency 0 (the default) takes the concurrency 19 used for that model (4 for the two Qwen3 models, 8 for the
others); --max-dollars is per model.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import modal

app = modal.App('gemma-forks-24')
vol = modal.Volume.from_name('gemma-forks-c')
_HERE = os.path.dirname(os.path.abspath(__file__))
image = (
    modal.Image.debian_slim(python_version='3.12')
    .pip_install('litellm==1.82.4', 'google-adk==1.36.1', 'google-genai==2.11.0',
                 # declared dependencies of the harness wheels that their imports need (installed with --no-deps), as in 19
                 'docker>=7.0.0', 'cachetools>=5.0.0', 'networkx>=3.0', 'python-dotenv>=1.0.0', 'rich>=13.0',
                 'pandas>=2.0.0', 'numpy>=2.0.0', 'scikit-learn>=1.3.0', 'pyyaml>=6.0')
    .add_local_file(os.path.join(_HERE, 'forks_24_runner.py'), '/root/forks_24_runner.py')
)
M = '/vol'
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the first upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip
RUNNER = '/root/forks_24_runner.py'
API_BASE = 'https://api.studio.nebius.com/v1'
VARIANT = 'v28'
STATES = '/vol/inputs_g/states_t.jsonl'           # analysis/fork_states_t/states.jsonl, uploaded for 20
STATES_MD5 = '750b3e0952608bf023e69a338f26b030'   # the md5 frozen in pre-registration 20
LOCAL_STATES = os.path.join(os.path.dirname(_HERE), 'fork_states_t', 'states.jsonl')
OUT, CHECK_OUT = 'out_24', 'out_24_check'
ROWS_19 = '/vol/out_19/17'                        # 19's design-17 rows (the check compares ASKED's prompt size)
SEEDS = (1, 2, 3)
CHECK_STEPS, CHECK_MAX_CALLS, CHECK_MAX_RETRIES = 2, 30, 2
# The seven models of pre-registration 19 (all passed its gate) and the concurrency each ran at there.
MODELS = ('Qwen/Qwen3-30B-A3B-Instruct-2507', 'Qwen/Qwen3-235B-A22B-Instruct-2507', 'openai/gpt-oss-120b',
          'deepseek-ai/DeepSeek-V4.1-Flash-1017', 'zai-org/GLM-5.3-Flash', 'MiniMaxAI/MiniMax-M3.1-Flash',
          'nvidia/nemotron-3-super-120b-a12b')
CONCURRENCY_19 = {'Qwen/Qwen3-30B-A3B-Instruct-2507': 4, 'Qwen/Qwen3-235B-A22B-Instruct-2507': 4}


def slug(model):
    return model.replace('/', '__')


def _md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def _replay(model, odir, plan, opts, capture):
    """Run the runner for one model into odir. Returns (exit code, seconds)."""
    if not os.path.islink(V):
        os.symlink(SRC, V)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    if not os.environ.get('NEBIUS_API_KEY'):
        raise RuntimeError('NEBIUS_API_KEY is not in the container environment')
    got = _md5(STATES)
    if got != STATES_MD5:
        raise RuntimeError(f'states file has md5 {got}, expected {STATES_MD5}')
    os.makedirs(odir, exist_ok=True)
    plan_path = odir + '/plan.json'
    json.dump(plan, open(plan_path, 'w'), indent=1)
    conc = opts['concurrency'] or CONCURRENCY_19.get(model, 8)
    env = dict(os.environ, INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp', OUT_DIR=odir,
               AGENT_DIR=f'/root/agents/{slug(model)}', HARNESS_VARIANT=VARIANT, STATES_FILE=STATES,
               PLAN_FILE=plan_path, SEEDS=','.join(map(str, SEEDS)), CONCURRENCY=str(conc), API_BASE=opts['api_base'],
               API_MODEL=model, MAX_DOLLARS=str(opts['max_dollars']), MAX_OUTPUT_TOKENS=str(opts['max_output_tokens']),
               MAX_RETRIES=str(opts['max_retries']), MAX_CALLS=str(opts['max_calls']),
               TIME_BUDGET_S=str(int(opts['budget_hours'] * 3600)), PREFLIGHT='0' if opts['no_preflight'] else '1',
               CAPTURE_REQUESTS='1' if capture else '0',
               PRICE_IN_PER_M=str(opts['price_in'] or ''), PRICE_OUT_PER_M=str(opts['price_out'] or ''))
    from urllib.parse import urlparse
    json.dump({'platform': 'modal, CPU only (4 cores)', 'python': sys.version, 'api_host': urlparse(opts['api_base']).netloc,
               'api_model': model, 'experiment': '24', 'mode': opts['mode'], 'seeds': list(SEEDS), 'states_file': STATES,
               'states_file_md5': got, 'steps': len(plan['order']), 'concurrency': conc,
               'max_dollars': opts['max_dollars'], 'max_calls': opts['max_calls'], 'max_retries': opts['max_retries'],
               'max_output_tokens': opts['max_output_tokens'] or 'the agent configuration', 'harness_variant': VARIANT,
               'runner_md5': _md5(RUNNER), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
              open(odir + '/platform_actual.json', 'w'), indent=1)
    stop = threading.Event()

    def committer():  # rows reach the volume as they are written
        while not stop.wait(300):
            try:
                vol.commit()
            except Exception as e:  # noqa: BLE001
                print('commit failed:', e)

    threading.Thread(target=committer, daemon=True).start()
    t0 = time.time()
    with open(odir + '/runner.log', 'w') as logf:
        p = subprocess.Popen([sys.executable, RUNNER], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            print(f'[{model}]', line, end='')
            logf.write(line)
        code = p.wait()
    stop.set()
    txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    open(odir + '/pip_freeze.txt', 'w').write(txt)
    vol.commit()
    return code, round(time.time() - t0, 1)


def _result(odir, code, seconds):
    summ = json.load(open(odir + '/summary.json')) if os.path.exists(odir + '/summary.json') else None
    fatal = open(odir + '/fatal.txt').read().strip() if os.path.exists(odir + '/fatal.txt') else None
    return {'exit': code, 'seconds': seconds, 'summary': summ, 'fatal': fatal}


@app.function(image=image, volumes={M: vol}, cpu=4, memory=4096, timeout=6 * 3600)
def run(model: str, plan: dict, opts: dict):
    odir = f'/vol/{OUT}/{slug(model)}'
    code, sec = _replay(model, odir, plan, opts, capture=False)
    return _result(odir, code, sec)


# ------------------------------------------------------------------ the plumbing check

TOOL_ROLES = ('tool', 'tool_responses')   # as in forks_20_check.py


def _text(m):
    body = m.get('content')
    return body if isinstance(body, str) else ''.join(p.get('text', '') for p in body or [] if isinstance(p, dict))


def _commands(obj):
    """Every `command` argument in a message, through nested lists, dicts and JSON-encoded strings."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'command' and isinstance(v, str):
                out.append(v)
            out += _commands(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _commands(v)
    elif isinstance(obj, str) and obj[:1] in '{[':
        try:
            out += _commands(json.loads(obj))
        except ValueError:
            pass
    return out


def _verify(odir, plan, model):
    """The checks of the docstring, on the rows and requests of the check. Returns (report lines, failures)."""
    recs = [json.loads(l) for l in open(STATES, encoding='utf-8')]
    by = {(r['task'], r['run'], r['fork']): r for r in recs}
    rows = [json.loads(l) for l in open(odir + '/results.jsonl', encoding='utf-8')]
    reqs = [json.loads(l) for l in open(odir + '/requests.jsonl', encoding='utf-8')]
    req = {}
    for q in reqs:                                 # the first request of a cell (a retry sends the same one again)
        req.setdefault((q['task'], q['run'], q['fork'], q['seed']), q)
    row = {(r['task'], r['run'], r['fork'], r['seed']): r for r in rows}
    s19 = {}
    p19 = f'{ROWS_19}/{slug(model)}/results.jsonl'
    if os.path.exists(p19):
        for l in open(p19, encoding='utf-8'):
            r = json.loads(l)
            if r.get('record_arm') == 'S' and (r.get('usage') or {}).get('prompt_tokens'):
                s19[(r['task'], r['run'], r['fork'], r['seed'])] = r['usage']['prompt_tokens']
    lines, bad, last = [], 0, None
    att =sum(len((r.get('api') or {}).get('attempts') or []) for r in rows)
    lines.append(f'rows {len(rows)}, requests captured {len(reqs)}, API attempts {att}, '
                 f'rows with a parsed tool call {sum(bool(r.get("next_call")) for r in rows)}, '
                 f'rows with an error {sum(bool(r.get("error")) for r in rows)}')
    for sid in plan['order']:
        mine = [r for r in recs if r['state_id'] == sid]
        rec = {r['arm']: r for r in mine}
        none = rec['NONE']
        for seed in SEEDS:
            cell = {a: (none['task'], none['run'], r['fork'], seed) for a, r in rec.items()}
            got = {a: req.get(c) for a, c in cell.items()}
            out = {a: row.get(c) for a, c in cell.items()}
            parts = []
            for a in plan['record_arms']:
                if a not in rec:
                    continue
                o = out[a] or {}
                ok = bool(o.get('next_call') and not o.get('error'))
                bad += not ok
                parts.append(f'{a} parsed call: ' + (o['next_call']['function_name'] if ok
                                                     else f'NONE (error {str(o.get("error"))[:120]})'))
            if any(got[a] is None for a in rec):
                bad += 1
                lines.append(f'{sid} seed {seed}: a request was not captured: {[a for a in rec if got[a] is None]}')
                continue
            base = got['NONE']['messages']
            ok_last = base[-1].get('role') in TOOL_ROLES
            asked = got['ASKED']['messages']
            ok_asked = (asked[:-2] == base and asked[-2].get('role') == 'assistant'
                        and none['own_search_command'] in _commands(asked[-2]) and asked[-1].get('role') in TOOL_ROLES)
            checks = [f'NONE ends on a tool result: {ok_last}',
                      f'ASKED = NONE + the recorded search call ({asked[-2].get("role")}, run_command with the recorded '
                      f'command) + its result ({asked[-1].get("role")}): {ok_asked}']
            bad += not (ok_last and ok_asked)
            for a in ('TOLD', 'TOLDX'):
                if a not in rec:
                    continue
                m = got[a]['messages']
                ok = (m[:-1] == base and len(m) == len(base) + 1 and m[-1].get('role') == 'user'
                      and _text(m[-1]) == rec[a]['note'])
                checks.append(f'{a} = NONE + one user message equal to its note ({len(rec[a]["note"])} chars): {ok}')
                bad += not ok
            same_tools = len({got[a]['tools_md5'] for a in rec}) == 1
            same_params = len({json.dumps(got[a]['params'], sort_keys=True) for a in rec}) == 1
            seed_sent = all(got[a]['params'].get('seed') == seed for a in rec)
            checks.append(f'same tool declarations in every arm: {same_tools}; same sampling parameters: {same_params}; '
                          f'seed {seed} sent: {seed_sent}')
            bad += not (same_tools and same_params and seed_sent)
            k19 = (none['task'], none['run'], rec['ASKED']['state_of_15'], seed)
            pt = ((out['ASKED'] or {}).get('usage') or {}).get('prompt_tokens')
            if k19 in s19 and pt:
                checks.append(f'ASKED prompt tokens {pt}, 19\'s arm S on this step and seed {s19[k19]}: '
                              f'{"equal" if pt == s19[k19] else "DIFFERENT"}')
                bad += pt != s19[k19]
            else:
                checks.append('ASKED prompt tokens: no row of 19 to compare with')
            lines.append(f'{sid} seed {seed}: ' + '; '.join(parts))
            lines += ['    ' + c for c in checks]
            last = (got, base)
    if last:
        ex, base = last[0]['TOLD'], last[1]
        lines.append(f'tool names declared: {ex["tool_names"]}')
        lines.append(f'sampling parameters sent (TOLD, last step and seed): {json.dumps(ex["params"], sort_keys=True)[:600]}')
        lines.append(f'messages in NONE (last step): {len(base)}; roles of the last three: {[m.get("role") for m in base[-3:]]}')
    lines.append(f'checks failed: {bad}')
    return lines, bad


@app.function(image=image, volumes={M: vol}, cpu=4, memory=4096, timeout=1800, max_containers=1)
def check(model: str, plan: dict, opts: dict):
    odir = f'/vol/{CHECK_OUT}/{slug(model)}'
    shutil.rmtree(odir, ignore_errors=True)       # the check starts from nothing
    code, sec = _replay(model, odir, plan, opts, capture=True)
    res = _result(odir, code, sec)
    lines, bad = _verify(odir, plan, model) if os.path.exists(odir + '/requests.jsonl') else (['no requests captured'], 1)
    open(odir + '/check_report.txt', 'w').write('\n'.join(lines) + '\n')
    vol.commit()
    res.update(report=lines, failed=bad)
    return res


# ------------------------------------------------------------------ local entrypoint

def make_plan(mode):
    """The steps and their order, by the functions of pre-registration 20, from the local copy of the states file."""
    sys.path.insert(0, _HERE)
    from forks_20_modal import RECORD_ARMS, RUNNER_ARM, state_order   # noqa: E402  (local only)
    got = _md5(LOCAL_STATES)
    if got != STATES_MD5:
        raise SystemExit(f'{LOCAL_STATES} has md5 {got}, expected {STATES_MD5}: rebuild it with analysis/make_states_t.py')
    recs = [json.loads(l) for l in open(LOCAL_STATES, encoding='utf-8')]
    order = state_order(recs)
    src = 'forks_20_modal.state_order (random.Random(20) over the steps as the file lists them)'
    if mode == 'check':
        has_x = {r['state_id'] for r in recs if r['arm'] == 'TOLDX'}
        order = [k for k in order if k in has_x][:CHECK_STEPS]
        src += f'; the check keeps the first {CHECK_STEPS} steps of that order that have a TOLDX record'
    return {'order': order, 'record_arms': list(RECORD_ARMS), 'runner_arm': dict(RUNNER_ARM), 'order_source': src,
            'states_md5': got}


def _row(m, r):
    s = r['summary'] or {}
    stt = s.get('stats') or {}
    ba = s.get('by_arm') or {}
    n = sum(v['n'] for v in ba.values())
    wc = sum(v['with_call'] for v in ba.values())
    pts = [v['prompt_tokens_mean'] for v in ba.values() if v.get('prompt_tokens_mean')]
    print(f'{m:42s} {r["exit"]:>4} {n:5d} {stt.get("calls_started", 0):5d} {stt.get("attempts", 0):5d} {wc:6d} '
          f'{stt.get("api_failures", 0):6d} {stt.get("retries", 0):5d} {stt.get("rate_limited", 0):4d} '
          f'{(sum(pts) / len(pts)) if pts else 0:7.0f} {s.get("dollars_this_session", 0):8.4f} '
          f'{r["seconds"]:7.1f} {s.get("latency_s_mean") or 0:6.2f}')
    if r['fatal']:
        print(f'    FATAL: {r["fatal"]}')
    if s.get('reported_model_other_than_asked'):
        print(f'    WARNING reported model ids: {s["reported_model_other_than_asked"]}')


@app.local_entrypoint()
def main(mode: str = 'check', model: str = 'Qwen/Qwen3-30B-A3B-Instruct-2507', concurrency: int = 0,
         max_dollars: float = 3.0, api_base: str = API_BASE, max_output_tokens: int = 0, max_retries: int = 8,
         no_preflight: bool = False, budget_hours: float = 5.0, price_in: float = 0.0, price_out: float = 0.0):
    key = os.environ.get('NEBIUS_API_KEY', '')
    if not key:
        raise SystemExit('NEBIUS_API_KEY is not set in the local environment')
    models = list(MODELS) if model == 'all' else [m for m in model.split(',') if m]
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        raise SystemExit(f'not a model of pre-registration 19: {unknown}')
    if mode not in ('check', 'full'):
        raise SystemExit(f'unknown mode {mode}')
    if mode == 'check' and len(models) != 1:
        raise SystemExit('the check runs on ONE model')
    plan = make_plan(mode)
    opts = dict(mode=mode, concurrency=concurrency, max_dollars=max_dollars if mode == 'full' else min(max_dollars, 0.5),
                api_base=api_base, max_output_tokens=max_output_tokens,
                max_retries=max_retries if mode == 'full' else CHECK_MAX_RETRIES,
                max_calls=0 if mode == 'full' else CHECK_MAX_CALLS, no_preflight=no_preflight,
                budget_hours=budget_hours if mode == 'full' else 0.4, price_in=price_in, price_out=price_out)
    print(f'mode {mode}: {len(plan["order"])} steps ({plan["order_source"]}); states md5 {plan["states_md5"]}; '
          f'models {models}')
    fn = (check if mode == 'check' else run).with_options(secrets=[modal.Secret.from_dict({'NEBIUS_API_KEY': key})])
    calls = [(m, fn.spawn(m, plan, opts)) for m in models]
    failed = False
    print(f'\n{"model":42s} {"exit":>4s} {"rows":>5s} {"calls":>5s} {"tries":>5s} {"w/call":>6s} {"apierr":>6s} '
          f'{"retry":>5s} {"429":>4s} {"ptok":>7s} {"dollars":>8s} {"seconds":>7s} {"lat":>6s}')
    for m, c in calls:
        try:
            res = c.get()
        except Exception as e:  # noqa: BLE001
            print(f'{m:42s} FAILED: {type(e).__name__}: {e}')
            failed = True
            continue
        _row(m, res)
        failed |= res['exit'] != 0
        if mode == 'check':
            print('\n'.join(res['report']))
            failed |= bool(res['failed'])
    if failed:
        raise SystemExit(1)
