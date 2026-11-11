"""Experiment 19 on Modal (BUILD, not registered): the one-call contrasts of pre-registration 10 (bare names against
addresses in a note) and of pre-registrations 15/17 (the agent's own search with and without its line numbers) on
models of other families, served by a hosted OpenAI-compatible inference API. CPU only: no GPU, no vLLM.

The runner is analysis/modal_g/forks_19_runner.py (its docstring says what it keeps from the runner of 10 and 17 and
what it changes); it is shipped in the image, not read from the volume. The states, the harness wheels and the
agent files are the ones the runs of 10 and 17 read from the volume; the states files are checked by md5.

Designs (defaults are the full run):
  10  analysis/fork_states_d/states.jsonl (407 states), arms H (bare names, note) and E (name, file, lines,
      definition line, note): the contrast M2 of pre-registration 10; 2 replays per state (seeds 1 and 2)
  17  analysis/fork_states_s/states.jsonl (61 states), record arms S, S0, S0N; 3 replays per state (seeds 1 to 3)

The API key is read from the local environment at launch and handed to the containers as an ephemeral secret
(modal.Secret.from_dict); it is never written to the volume, to a log or to a file of this repository.
Each model runs in its own container (all models of one launch in parallel); within a container the designs run
one after the other. Output: /vol/<out>/<design>/<model id with / replaced by __>/ with results.jsonl, versions.json,
summary.json, platform_actual.json, pip_freeze.txt, runner.log.

Smoke test (rows to /vol/out_19_smoke, cleared first):
  modal run analysis/modal_g/forks_19_modal.py --smoke --design 17 --limit 4 --seeds 1 --model <id>[,<id>...]
  modal run analysis/modal_g/forks_19_modal.py --smoke --design 10 --limit 6 --seeds 1 --model <id>[,<id>...]
Full run:
  modal run --detach analysis/modal_g/forks_19_modal.py --design 10,17 --model <id>[,<id>...] --max-dollars <d>
With the API pointed at nothing (must fail loudly):
  modal run analysis/modal_g/forks_19_modal.py --smoke --design 17 --limit 1 --seeds 1 --model <id> \
      --api-base http://127.0.0.1:9/v1
Load the key inside the same command (set -a; . <env file>; set +a) and prefix with
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8 from Git Bash. --max-dollars is per model and design.
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

app = modal.App('gemma-forks-19')
vol = modal.Volume.from_name('gemma-forks-c')
_HERE = os.path.dirname(os.path.abspath(__file__))
image = (
    modal.Image.debian_slim(python_version='3.12')
    .pip_install('litellm==1.82.4', 'google-adk==1.36.1', 'google-genai==2.11.0',
                 # declared dependencies of the harness wheels that their imports need (installed with --no-deps)
                 'docker>=7.0.0', 'cachetools>=5.0.0', 'networkx>=3.0', 'python-dotenv>=1.0.0', 'rich>=13.0',
                 'pandas>=2.0.0', 'numpy>=2.0.0', 'scikit-learn>=1.3.0', 'pyyaml>=6.0')
    .add_local_file(os.path.join(_HERE, 'forks_19_runner.py'), '/root/forks_19_runner.py')
)
M = '/vol'
SRC = os.environ.get('FORKS_VOLUME_ROOT', '/vol/C:/Program Files/Git')  # where the first upload landed in the volume
V = '/root/v'  # symlink to SRC: no spaces or colons in the paths handed to pip
RUNNER = '/root/forks_19_runner.py'
API_BASE = 'https://api.studio.nebius.com/v1'
VARIANT = 'v28'
DESIGNS = {
    '10': {'states': '/vol/inputs_d/states.jsonl', 'md5': 'd3105df0dc4aa43d7bb0afbdd6123b44', 'arms': 'H,E', 'seeds': 2},
    '17': {'states': '/vol/inputs_g/states_s.jsonl', 'md5': 'a90d2df2d7b6fc12591fffe2f1622a2b', 'arms': 'S,S0,S0N', 'seeds': 3},
}


def slug(model):
    return model.replace('/', '__')


def _md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


@app.function(image=image, volumes={M: vol}, cpu=4, memory=4096, timeout=6 * 3600)
def run(model: str, designs: list, opts: dict):
    """Run the given designs for one model, one after the other. Returns {design: summary or failure}."""
    if not os.path.islink(V):
        os.symlink(SRC, V)
    os.makedirs('/root/comp/graphs', exist_ok=True)
    os.makedirs('/root/comp/embeddings', exist_ok=True)
    if not os.environ.get('NEBIUS_API_KEY'):
        raise RuntimeError('NEBIUS_API_KEY is not in the container environment')
    out = {}
    for design in designs:
        d = DESIGNS[design]
        got = _md5(d['states'])
        if got != d['md5']:
            raise RuntimeError(f'states file of design {design} has md5 {got}, expected {d["md5"]}')
        seeds = ','.join(str(s) for s in range(1, (opts['seeds'] or d['seeds']) + 1))
        arms = opts['arms'] or d['arms']
        odir = f"/vol/{opts['out']}/{design}/{slug(model)}"
        if opts['smoke']:
            shutil.rmtree(odir, ignore_errors=True)   # a smoke test starts from nothing
        os.makedirs(odir, exist_ok=True)
        env = dict(os.environ, INPUTS_DIR=V + '/inputs', COMP_DIR='/root/comp', OUT_DIR=odir,
                   AGENT_DIR=f'/root/agents/{design}_{slug(model)}', HARNESS_VARIANT=VARIANT, DESIGN=design,
                   STATES_FILE=d['states'], ARMS=arms, SEEDS=seeds, STATES_N=str(opts['limit']),
                   CONCURRENCY=str(opts['concurrency']), API_BASE=opts['api_base'], API_MODEL=model,
                   MAX_DOLLARS=str(opts['max_dollars']), MAX_OUTPUT_TOKENS=str(opts['max_output_tokens']),
                   MAX_RETRIES=str(opts['max_retries']), TIME_BUDGET_S=str(int(opts['budget_hours'] * 3600)),
                   PREFLIGHT='0' if opts['no_preflight'] else '1',
                   PRICE_IN_PER_M=str(opts['price_in'] or ''), PRICE_OUT_PER_M=str(opts['price_out'] or ''))
        from urllib.parse import urlparse
        json.dump({'platform': 'modal, CPU only (4 cores)', 'python': sys.version, 'api_host': urlparse(opts['api_base']).netloc,
                   'api_model': model, 'design': design, 'arms': arms, 'seeds': seeds, 'states_file': d['states'],
                   'states_file_md5': got, 'states_n': opts['limit'], 'concurrency': opts['concurrency'],
                   'max_dollars': opts['max_dollars'], 'max_output_tokens': opts['max_output_tokens'] or 'the agent configuration',
                   'harness_variant': VARIANT, 'runner_md5': _md5(RUNNER), 'smoke': opts['smoke'],
                   'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
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
                print(f'[{model} {design}]', line, end='')
                logf.write(line)
            code = p.wait()
        stop.set()
        txt = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
        open(odir + '/pip_freeze.txt', 'w').write(txt)
        vol.commit()
        summ = json.load(open(odir + '/summary.json')) if os.path.exists(odir + '/summary.json') else None
        fatal = open(odir + '/fatal.txt').read().strip() if os.path.exists(odir + '/fatal.txt') else None
        out[design] = {'exit': code, 'seconds': round(time.time() - t0, 1), 'summary': summ, 'fatal': fatal}
    return out


@app.local_entrypoint()
def main(model: str = '', design: str = '10,17', arms: str = '', seeds: int = 0, limit: int = 0, concurrency: int = 8,
         max_dollars: float = 5.0, out: str = 'out_19', smoke: bool = False, api_base: str = API_BASE,
         max_output_tokens: int = 0, max_retries: int = 8, no_preflight: bool = False, budget_hours: float = 5.0,
         price_in: float = 0.0, price_out: float = 0.0):
    key = os.environ.get('NEBIUS_API_KEY', '')
    if not key:
        raise SystemExit('NEBIUS_API_KEY is not set in the local environment')
    models = [m for m in model.split(',') if m]
    designs = [d for d in design.split(',') if d]
    if not models or any(d not in DESIGNS for d in designs):
        raise SystemExit(f'give --model and --design among {sorted(DESIGNS)}')
    if smoke and out == 'out_19':
        out = 'out_19_smoke'
    opts = dict(arms=arms, seeds=seeds, limit=limit, concurrency=concurrency, max_dollars=max_dollars, out=out,
                smoke=smoke, api_base=api_base, max_output_tokens=max_output_tokens, max_retries=max_retries,
                no_preflight=no_preflight, budget_hours=budget_hours, price_in=price_in, price_out=price_out)
    fn = run.with_options(secrets=[modal.Secret.from_dict({'NEBIUS_API_KEY': key})])
    calls = [(m, fn.spawn(m, designs, opts)) for m in models]
    failed = False
    print(f'\n{"model":42s} {"des":>3s} {"exit":>4s} {"rows":>5s} {"calls":>5s} {"w/call":>6s} {"apierr":>6s} {"retry":>5s} '
          f'{"429":>4s} {"ptok":>7s} {"dollars":>8s} {"s/call":>6s} {"lat":>6s}')
    for m, c in calls:
        try:
            res = c.get()
        except Exception as e:  # noqa: BLE001
            print(f'{m:42s} FAILED: {type(e).__name__}: {e}')
            failed = True
            continue
        for d, r in res.items():
            s = r['summary'] or {}
            stt = s.get('stats') or {}
            ba = s.get('by_arm') or {}
            n = sum(v['n'] for v in ba.values())
            wc = sum(v['with_call'] for v in ba.values())
            pts = [v['prompt_tokens_mean'] for v in ba.values() if v.get('prompt_tokens_mean')]
            print(f'{m:42s} {d:>3s} {r["exit"]:>4} {n:5d} {stt.get("calls_started", 0):5d} {wc:6d} {stt.get("api_failures", 0):6d} '
                  f'{stt.get("retries", 0):5d} {stt.get("rate_limited", 0):4d} '
                  f'{(sum(pts) / len(pts)) if pts else 0:7.0f} {s.get("dollars_this_session", 0):8.4f} '
                  f'{s.get("seconds_per_call_at_concurrency") or 0:6.2f} {s.get("latency_s_mean") or 0:6.2f}')
            if r['fatal']:
                print(f'    FATAL: {r["fatal"]}')
            if s.get('reported_model_other_than_asked'):
                print(f'    WARNING reported model ids: {s["reported_model_other_than_asked"]}')
            failed |= r['exit'] != 0
    if failed:
        raise SystemExit(1)
