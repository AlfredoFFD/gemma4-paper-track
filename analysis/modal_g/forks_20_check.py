"""Plumbing check of experiment 20 without a GPU (run by `forks_20_modal.py --mode check`; nothing about the model).

It does what the frozen runner (analysis/modal_w/forks_w_runner.py) does with the states file that forks_20_modal._plan
wrote, with a stand-in model in place of the vLLM server: installs the harness wheels of the variant (the wheelhouse is
not needed: no server starts), imports the replay module from INPUTS_DIR, builds one agent per seed from the base agent
config, shuffles the records with random.Random(0), and for every (record, arm, seed) cell its results file does not
hold yet calls replay.run_one_step and appends the row (with `decoy`: None) as the runner does. Calls run one at a
time.

The stand-in answers with a scripted call chosen from the record, the arm and the seed, so that the analysis meets
every outcome: a read of a noted file past line 1, a read from line 1, the recorded search again, the recorded pattern
with other options, an edit, an unrelated command, a malformed call. It also keeps every request, and the check
compares them, for every state and seed:
  - ASKED against arm S of pre-registration 15 (the record `<step>:S` of STATES_15, replayed the same way under arm A):
    the same messages;
  - NONE against ASKED: the messages of NONE are those of ASKED without its last two (the search call and its result),
    the second to last message of ASKED calls run_command with the recorded search command, and NONE ends on a tool
    result;
  - TOLD and TOLDX against NONE: the messages of NONE, then exactly one user message whose text equals the note.
Writes OUT_DIR/results.jsonl and OUT_DIR/check_report.txt; exits 1 if a check fails.
"""
import asyncio
import importlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

INPUTS = Path(os.environ['INPUTS_DIR'])
COMP = Path(os.environ['COMP_DIR'])
OUT = Path(os.environ['OUT_DIR'])
STATES_FILE = Path(os.environ['STATES_FILE'])
STATES_15 = Path(os.environ['STATES_15'])
ARMS = os.environ['ARMS'].split(',')
HARNESS_VARIANT = os.environ.get('HARNESS_VARIANT', 'v28')
SEEDS = [1, 2, 3]
T0 = time.time()
VARIANTS = {'v28': ['adk_eval_core-0.1.0', 'adk_submission-0.2.12', 'swegemma-0.2.7'],
            'latest': ['adk_eval_core-0.1.0', 'adk_submission-0.2.13', 'swegemma-0.2.11']}
report = []


def log(*a):
    line = ' '.join(str(x) for x in a)
    report.append(line)
    print(f'[{time.time() - T0:5.0f}s]', line, flush=True)


if os.environ.get('LOCAL_TEST') != '1':
    wheels = [str(next(INPUTS.glob(f'{stem}-*.whl'))) for stem in VARIANTS[HARNESS_VARIANT]]
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
    importlib.invalidate_caches()
sys.path.insert(0, str(INPUTS))
import replay  # noqa: E402
from adk_submission import ModelRegistry  # noqa: E402
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.genai import types  # noqa: E402

replay.DATA = COMP
CURRENT = {}
CAPTURED = []


def scripted(rec, arm, seed, k):
    """(tool, arguments) for one cell: a fixed script over the record's own data."""
    hit = next(iter(rec['hit_files']))
    line = rec['hit_files'][hit][0]
    if arm == 'S15':                             # a record of 15 (it has no own_search_call field)
        return 'read_file', {'filepath': hit}
    cmd = rec['own_search_call']['arguments'].get('command', '')
    menu = [
        ('read_file', {'filepath': hit, 'start_line': max(2, line - 5), 'end_line': line + 20}),   # uses the line
        ('read_file', {'filepath': hit}),                                                           # from line 1
        ('run_command', {'command': cmd}),                                                          # the same search
        ('run_command', {'command': cmd.replace('grep -rn', 'grep -rn -i', 1) if 'grep -rn' in cmd else cmd + ' -i'}),
        ('edit_file', {'filepath': hit, 'old_string': 'a', 'new_string': 'b'}),
        ('run_command', {'command': 'ls'}),
        ('read_file', {'start_line': 3}),                                                           # malformed
    ]
    return menu[(k + seed + ARMS.index(arm)) % len(menu)]


class Stand(BaseLlm):
    model: str = 'stand-in'

    async def generate_content_async(self, llm_request, stream=False):
        CAPTURED.append(llm_request)
        name, args = scripted(*CURRENT['cell'])
        yield LlmResponse(content=types.Content(role='model', parts=[
            types.Part(text='stand-in', thought=True),
            types.Part(function_call=types.FunctionCall(name=name, args=args, id='stand-1'))]))


stand = Stand()
reg = ModelRegistry()
reg.register(replay.MODEL_ALIAS, stand)
agent_dir = Path(os.environ.get('AGENT_DIR', '/root/agents/base'))
(agent_dir / 'prompts').mkdir(parents=True, exist_ok=True)
(agent_dir / 'configs').mkdir(parents=True, exist_ok=True)
shutil.copy(INPUTS / 'agent.yaml', agent_dir / 'agent.yaml')
shutil.copy(INPUTS / 'sampling.yaml', agent_dir / 'configs' / 'sampling.yaml')
shutil.copy(INPUTS / 'system.md', agent_dir / 'prompts' / 'system.md')
agents = {}
for seed in SEEDS:
    a = replay.build_agent(str(agent_dir), reg, {'instance_id': 'replay', 'repo': 'replay/replay', 'base_commit': ''})
    a.generate_content_config.seed = seed
    agents[seed] = a

states = [json.loads(l) for l in open(STATES_FILE, encoding='utf-8')]
random.Random(0).shuffle(states)                 # the runner's shuffle
s15 = {(r['task'], r['run'], r['fork']): r for r in map(json.loads, open(STATES_15, encoding='utf-8'))}
order_k = {}
res_path = OUT / 'results.jsonl'
done = set()
for l in open(res_path, encoding='utf-8'):
    r = json.loads(l)
    done.add((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']))
jobs = [(s, arm, seed) for s in states for arm in ARMS for seed in SEEDS
        if (s['task'], s['run'], s.get('fork', 0), arm, seed) not in done]
log(f'{len(states)} records loaded; {len(jobs)} replays to run ({len(done)} cells already in the results file)')
log('run order of the states (first appearance in the runner\'s job list):',
    list(dict.fromkeys(s['state_id'] for s, _a, _s in jobs)))


async def messages_of(rec, arm, seed, k):
    CURRENT['cell'] = (rec, arm, seed, k)
    CAPTURED.clear()
    out = await replay.run_one_step(agents[seed], rec, 'A' if arm == 'S15' else arm, seed)
    msgs, _tools = await replay._dump_messages(CAPTURED[-1])
    return out, msgs


TOOL_ROLES = ('tool', 'tool_responses')   # litellm groups the tool results of one turn under 'tool_responses'


def commands_in(obj):
    """Every `command` argument found in a message, through nested lists, dicts and JSON-encoded strings."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'command' and isinstance(v, str):
                out.append(v)
            out += commands_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out += commands_in(v)
    elif isinstance(obj, str) and obj[:1] in '{[':
        try:
            out += commands_in(json.loads(obj))
        except ValueError:
            pass
    elif obj is not None and not isinstance(obj, (int, float, bool)):
        out += commands_in(getattr(obj, '__dict__', None) or (obj.model_dump() if hasattr(obj, 'model_dump') else None))
    return out


def text_of(m):
    body = m.get('content')
    return body if isinstance(body, str) else ''.join(p.get('text', '') for p in body or [] if isinstance(p, dict))


async def main():
    got = {}
    with open(res_path, 'a', encoding='utf-8') as f:
        for k, (s, arm, seed) in enumerate(jobs):
            out, msgs = await messages_of(s, arm, seed, k)
            out['decoy'] = None
            f.write(json.dumps(out) + '\n')
            got[(s['state_id'], s['arm'], seed)] = msgs
    bad = 0
    for sid in dict.fromkeys(s['state_id'] for s, _a, _s in jobs):
        none_rec = next(s for s in states if s['state_id'] == sid and s['arm'] == 'NONE')
        rec15 = s15[(none_rec['task'], none_rec['run'], none_rec['state_of_15'])]
        for seed in SEEDS:
            base = got.get((sid, 'NONE', seed))
            if base is None:
                continue
            _o, m15 = await messages_of(rec15, 'S15', seed, 0)
            asked = got.get((sid, 'ASKED', seed))
            ok_a = asked == m15
            cmds = commands_in(asked[-2]) if asked else []
            ok_s = bool(asked) and asked[:-2] == base and none_rec['own_search_command'] in cmds \
                and asked[-1].get('role') in TOOL_ROLES
            ok_last = base[-1].get('role') in TOOL_ROLES
            line = (f'{sid} seed {seed}: ASKED = arm S of 15 ({len(m15)} messages): {ok_a}; NONE has {len(base)} '
                    f'messages, ends on a tool result: {ok_last}, = ASKED without its search call and result: {ok_s}')
            bad += not ok_a
            for arm in ('TOLD', 'TOLDX'):
                m = got.get((sid, arm, seed))
                if m is None:
                    continue
                note = next(s for s in states if s['state_id'] == sid and s['arm'] == arm)['note']
                ok = m[:-1] == base and len(m) == len(base) + 1 and m[-1].get('role') == 'user' and text_of(m[-1]) == note
                line += f'; {arm} = NONE plus one user message equal to the note: {ok}'
                bad += not ok
            bad += not (ok_s and ok_last)
            if not (ok_s and ok_last):
                first = next((j for j, (a, b) in enumerate(zip(m15, base)) if a != b), None)
                line += (f'\n    roles, NONE: {[m.get("role") for m in base[-3:]]}; S of 15: {[m.get("role") for m in m15[-4:]]};'
                         f' first differing message: {first}'
                         + ('' if first is None else f'\n    NONE: {json.dumps(base[first], default=str)[:400]}'
                            f'\n    S15 : {json.dumps(m15[first], default=str)[:400]}'))
            log(line)
    log(f'request checks failed: {bad}')
    return bad


bad = asyncio.run(main())
(OUT / 'check_report.txt').write_text('\n'.join(report) + '\n', encoding='utf-8')
sys.exit(1 if bad else 0)
