"""Replay a short navigation horizon from a saved fork state: up to k model calls, read-only tools really execute.

`analysis/replay.py` makes one model call and executes nothing. This module lets the agent go on for up to k model
calls (experiment E, prereg/06, DRAFT). `read_file` and read-only shell commands (cat, head, tail, sed -n, grep, rg,
ls, find, wc, pipelines made only of these, optionally fed by xargs, an optional cd, and redirections to /dev/null)
run through the harness's REAL tool functions (swegemma.tools.workspace / execution, unchanged: budget gating, the
150-line / 10,000-character file caps, the 5,000-character shell caps, the result dicts) against a checkout of the
task's snapshot prepared the way the harness prepares a subprocess sandbox. The replay stops before executing the
first call that is anything else (edit_file, write_file, submit_patch, get_status, graph tools, python, pytest, pip,
any shell command outside the whitelist), after the k-th model call, or on a final text answer. A model response with
several calls executes its allowed calls up to the first disallowed one, which ends the replay.

The sandbox object is the harness's own SubprocessManager (the logged runs used the subprocess sandbox: their
tracebacks show /tmp/swegemma_sandbox_<id>_<rand>/workspace). A prepared directory is registered with it instead of
calling start(), which would build a venv. On Linux its exec() and copy_from() run unchanged. On Windows (local
plumbing tests only) two methods are replaced: exec() runs Git Bash instead of /bin/bash, and copy_from() maps the
drive-letter path that read_file's path resolver produces on Windows back to /workspace/...

Environment (all optional): REPLAY_K_DATA (directory with graphs/ and embeddings/; default <repo>/data),
SNAPSHOTS_DIR (the <task>.tgz archives; default <REPLAY_K_DATA>/snapshots), REPLAY_K_TMP (where checkouts go).

Local tests:
    python analysis/replay_k.py test analysis/fork_states/<task>_r<run>_f<fork>.json      (scripted fake model)
    python analysis/replay_k.py fidelity <state.json> [...]   (re-executes the logged read-only calls of each history)
"""
import asyncio
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / 'analysis', ROOT / 'data' / 'wheelhouse' / 'v28' / 'src'):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.append(str(_p))  # appended: an installed harness (the cloud image) wins over the local source copy

from google.adk.apps.app import App  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions.in_memory_session_service import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import replay  # noqa: E402

DATA = Path(os.environ.get('REPLAY_K_DATA', str(ROOT / 'data')))
SNAPSHOTS = Path(os.environ.get('SNAPSHOTS_DIR', str(DATA / 'snapshots')))
TMP_BASE = os.environ.get('REPLAY_K_TMP') or None
IS_WINDOWS = os.name == 'nt'
GIT_BASH = r'C:\Program Files\Git\bin\bash.exe'
UNCOUNTED_TOOLS = {'submit_patch', 'get_status'}  # budget_gated(count_tool_call=False)
GIT_IDENTITY = '[user]\n\tname = replay\n\temail = replay@localhost\n'
CAPTURED = {'status': 'captured', 'note': 'replay stops before a non-navigation call'}

# ----------------------------------------------------------------------------- the whitelist

READ_ONLY_PROGRAMS = {'cat', 'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'ls', 'find', 'wc', 'sed'}
_FIND_FORBIDDEN = {'-exec', '-execdir', '-ok', '-okdir', '-delete', '-fprint', '-fprint0', '-fprintf', '-fls'}
_RG_FORBIDDEN = {'--pre', '--search-zip', '-z'}  # --pre runs an arbitrary program
_SED_PRINT_SCRIPT = re.compile(r"^\s*(\d+|\$)?\s*(,\s*(\d+|\$))?\s*p\s*$|^\s*/[^/]*/\s*(,\s*/[^/]*/)?\s*p\s*$")


def _segments(command):
    """Split a shell command on | || && ; and newlines, outside quotes. None if it uses anything else risky."""
    segs, cur, quote, i = [], '', None, 0
    while i < len(command):
        c = command[i]
        if quote != "'" and (c == '`' or command[i:i + 2] == '$('):
            return None  # command substitution (an escaped \` is consumed below and never reaches here)
        if not quote and command[i:i + 2] in ('<(', '>(', '<<'):
            return None  # process substitution, heredoc
        if quote:
            cur += c
            if c == quote:
                quote = None
            elif c == '\\' and quote == '"' and i + 1 < len(command):
                cur += command[i + 1]
                i += 1
        elif c in ('"', "'"):
            quote = c
            cur += c
        elif c == '\\' and i + 1 < len(command):
            cur += c + command[i + 1]
            i += 1
        elif c == '&' and (command[i - 1:i] == '>' or command[i + 1:i + 2] == '>'):
            cur += c  # part of a redirection (2>&1, &>), judged per segment
        elif c in '|;&\n':
            if c == '&' and command[i:i + 2] != '&&':
                return None  # background job
            segs.append(cur)
            cur = ''
            if command[i:i + 2] in ('||', '&&'):
                i += 1
        else:
            cur += c
        i += 1
    if quote:
        return None
    segs.append(cur)
    return [s.strip() for s in segs if s.strip()]


def _segment_ok(seg):
    try:  # punctuation_chars splits unquoted < > & into their own tokens; quoted text stays one word
        lex = shlex.shlex(seg, posix=True, punctuation_chars='<>&')
        lex.whitespace_split = True
        words = list(lex)
    except ValueError:
        return False
    # the only redirections allowed: stdout or stderr to /dev/null, stderr into stdout
    clean, i = [], 0
    while i < len(words):
        w = words[i]
        if w in ('>', '>>', '&>', '<', '<<', '>&', '<&', '>|'):
            nxt = words[i + 1] if i + 1 < len(words) else ''
            if (w in ('>', '&>') and nxt == '/dev/null') or (w == '>&' and nxt == '1'):
                if clean and clean[-1] in ('1', '2'):
                    clean.pop()  # the fd number in 2>/dev/null
                i += 2
                continue
            return False
        clean.append(w)
        i += 1
    if not clean:
        return False
    prog = clean[0]
    if prog == 'cd':  # cd inside the workspace changes nothing on disk
        return len(clean) <= 2
    if prog == 'xargs':
        rest = [w for w in clean[1:] if not w.startswith('-')]
        return bool(rest) and rest[0] in READ_ONLY_PROGRAMS - {'sed'} and _segment_ok(' '.join(shlex.quote(w) for w in rest))
    if prog not in READ_ONLY_PROGRAMS:
        return False
    if prog == 'find' and any(w in _FIND_FORBIDDEN for w in clean):
        return False
    if prog == 'rg' and any(w.split('=')[0] in _RG_FORBIDDEN for w in clean):
        return False
    if prog == 'sed':
        opts = [w for w in clean[1:] if w.startswith('-')]
        args = [w for w in clean[1:] if not w.startswith('-')]
        if set(opts) - {'-n'} or '-n' not in opts or not args:
            return False  # sed -i, sed -e/-f, or a sed without -n
        return bool(_SED_PRINT_SCRIPT.match(args[0]))
    return True


def classify_call(name, args):
    """'exec' if the call is read-only navigation that may really run, else 'stop'."""
    if name == 'read_file':
        return 'exec'
    if name == 'run_command':
        segs = _segments(str((args or {}).get('command', '')))
        if segs and all(_segment_ok(s) for s in segs):
            return 'exec'
    return 'stop'


# ----------------------------------------------------------------------------- environment of the sandbox

_LOCALE = None


def choose_locale():
    """Set LANG and LC_ALL for every sandbox command (SubprocessManager passes them through from os.environ).

    en_US.UTF-8 if the system has it, else C.UTF-8. Returns the name used. Not applied on Windows (Git Bash tests).
    """
    global _LOCALE
    if _LOCALE is not None:
        return _LOCALE
    if IS_WINDOWS:
        _LOCALE = 'n/a (windows test)'
        return _LOCALE
    try:
        have = subprocess.run(['locale', '-a'], capture_output=True, text=True, timeout=30).stdout.lower().split()
    except (OSError, subprocess.SubprocessError):
        have = []
    norm = {h.replace('-', '').replace('_', '') for h in have}
    _LOCALE = 'en_US.UTF-8' if 'enusutf8' in norm else 'C.UTF-8'
    os.environ['LANG'] = _LOCALE
    os.environ['LC_ALL'] = _LOCALE
    return _LOCALE


def environment_record():
    return {'locale': choose_locale(), 'git': shutil.which('git') is not None, 'platform': sys.platform,
            'python': sys.version.split()[0]}


def remove_tree(path):
    """rmtree that also removes read-only files (git objects are read-only)."""
    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            func(p)
        except OSError:
            pass
    if path and Path(path).exists():
        if IS_WINDOWS:
            path = '\\\\?\\' + str(Path(path).resolve())  # long-path form: deep repository paths exceed MAX_PATH
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=onerror)
        else:
            shutil.rmtree(path, onerror=onerror)


def checkout_fingerprint(ws):
    """Hash of (relative path, size, mtime) of every file under the workspace: proves the checkout was not modified."""
    h = hashlib.sha1()
    ws = Path(ws)
    for dirpath, dirnames, filenames in os.walk(ws):
        dirnames.sort()
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            try:
                s = p.lstat()
            except OSError:
                continue
            h.update(f'{p.relative_to(ws).as_posix()}|{s.st_size}|{s.st_mtime_ns}\n'.encode('utf-8', 'replace'))
    return h.hexdigest()


# ----------------------------------------------------------------------------- the sandbox


def make_manager():
    """The harness's SubprocessManager, with two Windows-only replacements for local tests."""
    from swegemma.sandbox.subprocess import SubprocessManager

    if not IS_WINDOWS:
        choose_locale()
        return SubprocessManager(timeout_seconds=120)

    from adk_eval_core.sandbox import ExecutionResult

    class _WinManager(SubprocessManager):
        def _copy_from_sandbox(self, sandbox_id, src, dst):
            win_ws = str(Path('/workspace').resolve())  # what read_file's resolver yields on Windows, e.g. C:\workspace
            if src.startswith(win_ws):
                src = '/workspace' + src[len(win_ws):].replace('\\', '/')
            return super()._copy_from_sandbox(sandbox_id, src, dst)

        def exec(self, sandbox_id, command, *, timeout=None):
            paths = self._sandboxes[sandbox_id]
            ws = paths['workspace']
            ws_posix = '/' + ws.as_posix().replace(':', '', 1)  # C:/x -> /C/x for Git Bash
            cmd = re.sub(r'(?<![\w.-])/workspace(?![\w.-])', ws_posix, command)
            env = dict(os.environ, HOME=str(paths['tmp']), TMPDIR=str(paths['tmp']), PYTHONPATH=str(ws))
            t0 = time.perf_counter()
            try:
                p = subprocess.run([GIT_BASH, '-c', cmd], cwd=str(ws), env=env, capture_output=True,
                                   timeout=timeout or self.timeout_seconds)
                return ExecutionResult(status='ok' if p.returncode == 0 else 'error',
                                       stdout=p.stdout.decode('utf-8', errors='replace'),
                                       stderr=p.stderr.decode('utf-8', errors='replace'),
                                       exit_code=p.returncode, duration_seconds=time.perf_counter() - t0)
            except subprocess.TimeoutExpired:
                return ExecutionResult(status='timeout', exit_code=124, duration_seconds=time.perf_counter() - t0)

    return _WinManager(timeout_seconds=120)


def register_workspace(mgr, sandbox_root):
    """Register an already prepared <root>/workspace with the manager; no venv is built. Returns the sandbox id."""
    root = Path(sandbox_root)
    sid = root.name.split('_')[2] if root.name.startswith('swegemma_sandbox_') else root.name
    paths = {'root': root, 'workspace': root / 'workspace', 'tmp': root / 'tmp', 'wheels': root / 'wheels',
             'venv': root / 'venv'}
    for k in ('tmp', 'wheels'):
        paths[k].mkdir(parents=True, exist_ok=True)
    with mgr._lock:
        mgr._sandboxes[sid] = paths
        if mgr._default_sandbox_id is None:
            mgr._default_sandbox_id = sid
    return sid


def _write_history_file(ws, rel, content):
    dest = ws / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'w', encoding='utf-8', newline='\n') as f:  # the tool writes \n on Linux
        f.write(content)


def _history_writes(state, before_step_id=None):
    """(filepath, content) of the logged write_file calls that succeeded, in order, before a step id."""
    out = []
    for s in state['steps']:
        if before_step_id is not None and s.get('step_id', 0) >= before_step_id:
            break
        for tc in s.get('tool_calls') or []:
            if tc['function_name'] != 'write_file':
                continue
            obs = replay._parse((s.get('observation') or {}).get('content'))
            if isinstance(obs, dict) and obs.get('status') == 'ok':
                out.append((tc['arguments']['filepath'], tc['arguments']['content']))
    return out


def prepare_workspace(state, base_dir=None, before_step_id=None, apply_writes=True):
    """Materialize the checkout as the harness's subprocess sandbox had it at the pause point.

    Steps, in the harness's order (swegemma.harness.agent_runner / container_setup, subprocess branch): extract the
    snapshot archive into /workspace, drop circular symlinks, append the git exclude rules, write pytest.ini and
    conftest.py, make the baseline commit (with a git identity written to the sandbox HOME). The editable install and
    the test-dependency setup are skipped by the harness itself for SubprocessManager. Then the logged write_file calls
    of the history are re-applied (new scratch files; states are cut before any edit of repository code). Not
    reproduced: files that earlier shell commands created (__pycache__ from python runs, heredoc writes).
    Returns (manager, sandbox_id, sandbox_root, seconds).
    """
    from swegemma.harness.container_setup import setup_baseline_commit, setup_git_exclude, setup_workspace_test_config

    t0 = time.time()
    sid_hint = os.urandom(6).hex()[:12]
    root = Path(tempfile.mkdtemp(prefix=f'swegemma_sandbox_{sid_hint}_', dir=base_dir or TMP_BASE))
    ws = root / 'workspace'
    ws.mkdir()
    archive = SNAPSHOTS / f"{state['task']}.tgz"
    if IS_WINDOWS:
        subprocess.run([GIT_BASH, '-c', f'tar --force-local --no-same-owner -xzf {shlex.quote(archive.as_posix())} '
                                        f'-C {shlex.quote(ws.as_posix())}'], check=True, capture_output=True)
    else:
        subprocess.run(['tar', '--no-same-owner', '-xzf', str(archive), '-C', str(ws)], check=True)
    for p in list(ws.rglob('*')):  # the harness's circular-symlink removal
        if p.is_symlink() and (p.resolve() == ws.resolve() or ws.resolve().is_relative_to(p.resolve())):
            p.unlink()
    mgr = make_manager()
    sid = register_workspace(mgr, root)
    (root / 'tmp' / '.gitconfig').write_text(GIT_IDENTITY, encoding='utf-8')  # HOME of every sandbox command
    setup_git_exclude(mgr, sid)
    setup_workspace_test_config(mgr, sid, repo=state['repo'])
    setup_baseline_commit(mgr, sid, 'baseline')
    if apply_writes:
        for rel, content in _history_writes(state, before_step_id):
            _write_history_file(ws, rel, content)
    return mgr, sid, root, round(time.time() - t0, 2)


def counted_calls(state, before_step_id=None):
    n = 0
    for s in state['steps']:
        if before_step_id is not None and s.get('step_id', 0) >= before_step_id:
            break
        n += sum(1 for tc in s.get('tool_calls') or [] if tc['function_name'] not in UNCOUNTED_TOOLS)
    return n


def make_context(mgr, sid, task, tool_calls_used=0):
    from swegemma.budget import HarnessLimits
    from swegemma.context import SwegemmaContext

    ctx = SwegemmaContext(docker_manager=mgr, container_id=sid, task=task, repo=task.get('repo'),
                          graph_dir=str(DATA / 'graphs'), embeddings_dir=str(DATA / 'embeddings'),
                          max_tool_calls=40, max_time_minutes=25,
                          harness=HarnessLimits(command_timeout_seconds=120))
    ctx.tool_calls_used = tool_calls_used  # so the low-budget warning appears exactly when it did in the original run
    return ctx


# ----------------------------------------------------------------------------- the agent and the k-step loop


def build_agent_k(submission_dir, model_registry, task, mgr, sid, tool_calls_used=0):
    """Compile the submission the way the harness does, with tools bound to a context on the prepared sandbox.

    Returns (agent, handle); pass the handle to run_k_steps as `workspace`. One agent per replay: the context counts
    tool calls and the gate knows which calls of the current response may run.
    """
    from adk_submission import compile_submission
    from swegemma.config import build_submission_limits

    ctx = make_context(mgr, sid, task, tool_calls_used)
    limits, gen = build_submission_limits()
    agent = compile_submission(submission_dir=submission_dir, tool_registry=ctx.create_tools(),
                               model_registry=model_registry, limits=limits, generation_constraints=gen,
                               code_executor=None)
    gate = {'allowed': set()}

    def _gate(tool, args, tool_context):
        cid = getattr(tool_context, 'function_call_id', None)
        if cid is not None and cid in gate['allowed']:
            return None  # the real tool runs
        if cid is None and classify_call(tool.name, args) == 'exec' and not gate.get('blocked'):
            return None
        return dict(CAPTURED)

    agent.before_tool_callback = _gate
    return agent, {'ctx': ctx, 'gate': gate, 'mgr': mgr, 'sid': sid}


def summarize_result(name, resp):
    """What the replay keeps of a tool result: everything but read_file's content (kept as counts and a hash)."""
    resp = dict(resp or {})
    if name == 'read_file' and isinstance(resp.get('content'), str):
        c = resp.pop('content')
        resp['content_chars'] = len(c)
        resp['content_lines'] = c.count('\n') + 1 if c else 0
        resp['content_sha1'] = hashlib.sha1(c.encode('utf-8', 'replace')).hexdigest()
    return resp


async def run_k_steps(agent, state, arm, seed, k=5, workspace=None, timeout=900, keep_results=False):
    """Seed the arm's history, let the agent make up to k model calls; read-only navigation really executes.

    `workspace` is the handle returned by build_agent_k. Returns {'steps': [{'calls': [{'function_name', 'arguments',
    'executed', 'result'}], 'prompt_tokens', ...}], 'stop': reason, 'error': ...}. Stop reasons:
    'stop_call:<name>' (the first non-navigation call: recorded, never executed; allowed calls before it in the same
    response did execute), 'horizon' (k model calls made, the k-th call's navigation executed), 'final_text' (a
    response with no call), 'timeout', 'error'.
    """
    gate = workspace['gate']
    svc = InMemorySessionService()
    session = await svc.create_session(app_name=replay.APP_NAME, user_id=replay.USER_ID, state=replay.session_state(state))
    events, new_message = replay.arm_messages(state, arm, agent.name)
    for ev in events:
        await svc.append_event(session, ev)
    if agent.generate_content_config is not None:
        agent.generate_content_config.seed = seed
    runner = Runner(app=App(name=replay.APP_NAME, root_agent=agent), session_service=svc)
    out = {'task': state['task'], 'run': state['run'], 'fork': state.get('fork', 0), 'arm': arm, 'seed': seed, 'k': k,
           'steps': [], 'stop': None, 'error': None}
    t0 = time.time()
    agen = runner.run_async(user_id=replay.USER_ID, session_id=session.id, new_message=new_message)
    pending, stop_after = set(), None
    by_id = {}
    try:
        async for ev in agen:
            if time.time() - t0 > timeout:
                out['stop'] = 'timeout'
                break
            if ev.author != agent.name or not ev.content or not ev.content.parts:
                continue
            responses = [p.function_response for p in ev.content.parts if p.function_response]
            if responses:
                for r in responses:
                    rec = by_id.get(r.id)
                    if rec is not None and rec['executed']:
                        rec['result'] = r.response if keep_results else summarize_result(rec['function_name'], r.response)
                    pending.discard(r.id)
                if not pending:
                    if stop_after:
                        out['stop'] = stop_after
                        break
                    if len(out['steps']) >= k:
                        out['stop'] = 'horizon'
                        break
                continue
            fcs = ev.get_function_calls()
            um = ev.usage_metadata
            step = {'calls': [],
                    'thought_chars': sum(len(p.text) for p in ev.content.parts if p.thought and p.text),
                    'text': ''.join(p.text for p in ev.content.parts if p.text and not p.thought)[:2000],
                    'prompt_tokens': um.prompt_token_count if um else None,
                    'completion_tokens': um.candidates_token_count if um else None}
            out['steps'].append(step)
            if not fcs:
                out['stop'] = 'final_text'
                break
            blocked_at = next((i for i, f in enumerate(fcs) if classify_call(f.name, dict(f.args or {})) != 'exec'), None)
            allowed = fcs if blocked_at is None else fcs[:blocked_at]
            gate['allowed'] = {f.id for f in allowed if f.id is not None}
            gate['blocked'] = blocked_at is not None
            for i, f in enumerate(fcs):
                rec = {'function_name': f.name, 'arguments': dict(f.args or {}), 'id': f.id,
                       'executed': blocked_at is None or i < blocked_at, 'result': None}
                step['calls'].append(rec)
                by_id[f.id] = rec
            if blocked_at is not None:
                stop_after = f'stop_call:{fcs[blocked_at].name}'
                if not allowed:
                    out['stop'] = stop_after
                    break  # the generator is suspended before tool execution, so the call never runs
            pending = {f.id for f in fcs}
    except Exception as e:  # noqa: BLE001
        out['error'] = f'{type(e).__name__}: {e}'
        out['stop'] = 'error'
    finally:
        await agen.aclose()
    if out['stop'] is None:
        out['stop'] = 'ended'
    for st in out['steps']:
        for c in st['calls']:
            c.pop('id', None)
    out['executed_calls'] = sum(c['executed'] for st in out['steps'] for c in st['calls'])
    out['latency_s'] = round(time.time() - t0, 2)
    return out


# ----------------------------------------------------------------------------- fidelity against the logged history

_ABS = re.compile(r'(/tmp/swegemma_sandbox_[^/\s]+|/[A-Za-z]/[^\s]*?swegemma_sandbox_[^/\s]+|'
                  r'/[^\s]*?/swegemma_sandbox_[^/\s]+)/workspace')


def _norm(v):
    return _ABS.sub('<SANDBOX>/workspace', v) if isinstance(v, str) else v


def compare(logged, got):
    """'exact', 'exact_path_norm' (equal after replacing the random sandbox root), 'order_only', or 'different'."""
    if got == logged:
        return 'exact'
    nl = {k: _norm(v) for k, v in logged.items()} if isinstance(logged, dict) else logged
    ng = {k: _norm(v) for k, v in got.items()} if isinstance(got, dict) else got
    if nl == ng:
        return 'exact_path_norm'
    if isinstance(nl, dict) and isinstance(ng, dict) and set(nl) == set(ng) and all(
            nl[k] == ng[k] or (isinstance(nl[k], str) and isinstance(ng[k], str)
                               and sorted(nl[k].splitlines()) == sorted(ng[k].splitlines())) for k in nl):
        return 'order_only'
    return 'different'


def fidelity_state(state):
    """Re-execute every logged read_file and whitelisted run_command of the state's history on a fresh checkout.

    The checkout starts without the history's writes; each logged successful write_file is applied when the walk
    reaches it, so every call sees the files that existed at its step. The real tool functions are called directly
    (the same functions ADK calls), with the context's call counter set to the logged count. No model is involved.
    Returns a list of {step_id, tool, args, verdict, diff} rows.
    """
    mgr, sid, root, secs = prepare_workspace(state, apply_writes=False)
    rows = []
    try:
        ws = root / 'workspace'
        task = {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}
        n_before = 0
        for s in state['steps']:
            for j, tc in enumerate(s.get('tool_calls') or []):
                name, args = tc['function_name'], tc['arguments']
                obs = replay._parse((s.get('observation') or {}).get('content')) if j == 0 else None
                if name == 'write_file' and isinstance(obs, dict) and obs.get('status') == 'ok':
                    _write_history_file(ws, args['filepath'], args['content'])
                if j == 0 and obs is not None and name in ('read_file', 'run_command') and classify_call(name, args) == 'exec':
                    ctx = make_context(mgr, sid, task, n_before)
                    got = ctx.create_tools()[name](**args)
                    verdict = compare(obs, got)
                    diff = None
                    if verdict != 'exact':
                        diff = {key: [str(obs.get(key))[:160], str(got.get(key))[:160]] for key in set(obs) | set(got)
                                if obs.get(key) != got.get(key)}
                    rows.append({'task': state['task'], 'run': state['run'], 'step_id': s.get('step_id'), 'tool': name,
                                 'args': args, 'verdict': verdict, 'diff': diff, 'prep_s': secs})
                if name not in UNCOUNTED_TOOLS:
                    n_before += 1
    finally:
        remove_tree(root)
    return rows


# ----------------------------------------------------------------------------- local tests


def _scripted_llm(script):
    """A fake model: response i is script[i] (a list of (name, args) calls; an empty list = a text answer)."""
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse

    class _Scripted(BaseLlm):
        model: str = 'fake'

        async def generate_content_async(self, llm_request, stream=False):
            _Scripted.captured.append(llm_request)
            i = len(_Scripted.captured) - 1
            calls = _Scripted.script[min(i, len(_Scripted.script) - 1)]
            parts = [types.Part(function_call=types.FunctionCall(name=n, args=a, id=f'fake-{i}-{j}'))
                     for j, (n, a) in enumerate(calls)] or [types.Part(text='I am done.')]
            yield LlmResponse(content=types.Content(role='model', parts=parts),
                              usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=1000 + i,
                                                                                        candidates_token_count=10))

    _Scripted.captured = []
    _Scripted.script = script
    return _Scripted()


def fake_agent(state, script, mgr, sid):
    from adk_submission import ModelRegistry
    fake = _scripted_llm(script)
    reg = ModelRegistry()
    reg.register(replay.MODEL_ALIAS, fake)
    task = {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}
    agent, handle = build_agent_k(str(ROOT / 'analysis' / 'agents' / 'base'), reg, task, mgr, sid,
                                  tool_calls_used=counted_calls(state))
    return agent, handle, fake


async def _test(state_path):
    state = json.load(open(state_path, encoding='utf-8'))
    target = state['node_span']['path'] if state.get('node_span') else 'README.md'
    read = ('read_file', {'filepath': target, 'start_line': 1, 'end_line': 12})
    grep = ('run_command', {'command': f'grep -n "def " {target} | head -n 5'})
    edit = ('edit_file', {'filepath': target, 'old_string': 'import', 'new_string': 'import'})
    mgr, sid, root, secs = prepare_workspace(state)
    print('environment:', environment_record(), '| workspace prepared in', secs, 's')
    fp0 = checkout_fingerprint(root / 'workspace')
    before = (root / 'workspace' / target).read_bytes()
    cases = [('stop at an edit inside a two-call response', [[read], [grep, edit], [read]], 5),
             ('horizon k=2', [[read], [grep], [read]], 2),
             ('final text at the first response', [[]], 5)]
    for label, script, k in cases:
        agent, handle, fake = fake_agent(state, script, mgr, sid)
        out = await run_k_steps(agent, state, 'A', seed=1, k=k, workspace=handle)
        print(f'\n== {label}: stop={out["stop"]} error={out["error"]} executed_calls={out["executed_calls"]} '
              f'model calls={len(type(fake).captured)} counter={handle["ctx"].tool_calls_used} (history {counted_calls(state)})')
        for i, st in enumerate(out['steps']):
            for c in st['calls']:
                res = {kk: (str(v)[:70] if isinstance(v, str) else v) for kk, v in (c['result'] or {}).items()}
                print(f'  step {i + 1} prompt_tokens={st["prompt_tokens"]} {c["function_name"]} executed={c["executed"]} result={res}')
    print('\ntarget file unchanged:', (root / 'workspace' / target).read_bytes() == before,
          '| checkout fingerprint unchanged:', checkout_fingerprint(root / 'workspace') == fp0)
    remove_tree(root)
    print('checkout removed:', not root.exists())


def _fidelity(paths):
    tot = {}
    for sp in paths:
        state = json.load(open(sp, encoding='utf-8'))
        for r in fidelity_state(state):
            tot.setdefault(r['tool'], {}).setdefault(r['verdict'], 0)
            tot[r['tool']][r['verdict']] += 1
            if r['verdict'] not in ('exact', 'exact_path_norm'):
                print(r['task'], r['run'], r['step_id'], r['tool'], r['verdict'], json.dumps(r['args'])[:100])
    print('TOTALS', json.dumps(tot))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.argv[1] == 'test':
        asyncio.run(_test(sys.argv[2]))
    elif sys.argv[1] == 'fidelity':
        _fidelity(sys.argv[2:])
