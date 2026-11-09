"""Replay one agent step from a saved fork state, under one arm, through the official harness's agent.

The history up to the fork is loaded into an ADK session exactly as the original run produced it (user task
prompt, model thoughts and tool calls, tool results). The arm's final piece is delivered as the new message:
arm A, the fork's own tool result; arms P and P', an inserted get_code_neighbors call plus its result; arms H
and H', a harness note with the same text. The agent then makes one model call, and the first function call
it emits is recorded. No tool ever executes: the run stops at the model's response and a before-tool callback
short-circuits any execution.

Used on Kaggle against the vLLM server, and locally with a fake model to check the plumbing:
    py analysis/replay.py test analysis/fork_states/<task>_r<run>.json
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from google.adk.apps.app import App
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ARMS = ('A', 'P', 'Pp', 'H', 'Hp')
APP_NAME = 'swegemma_eval'
USER_ID = 'eval_user'
MODEL_ALIAS = 'gemma-4-31b-it-qat-w4a16-ct'


def _parse(content):
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {'raw': content}
    return content


def _kind(step):
    return (step.get('extra') or {}).get('event_type') or ('tool' if step.get('tool_calls') else step['source'])


INCLUDE_THOUGHTS = False  # the original prompts did not carry earlier thoughts (fidelity check of Nov 8/9), so neither do the forks


def history_events(state, agent_name, include_thoughts=None):
    """ADK events for the history up to and including the fork step's tool result.

    Thought text is left out by default: the pilot of Nov 8 showed that re-sending it as reasoning makes the
    rebuilt prompt larger than the logged one by about the thoughts' size in the arms that end with a tool result,
    while the arms that end with a user note matched the logged size. The original runs therefore did not carry
    earlier thoughts, and including them would also make the tool-result arms differ from the note arms.
    """
    if include_thoughts is None:
        include_thoughts = INCLUDE_THOUGHTS
    inv = f"inv-{state['task']}-r{state['run']}-f{state.get('fork', 0)}"
    events, k = [], 0
    for s in state['steps']:
        kind = _kind(s)
        if kind == 'system_instruction':
            continue  # the agent renders its own instruction from prompts/system.md
        if s['source'] == 'user':
            events.append(Event(invocation_id=inv, author='user',
                                content=types.Content(role='user', parts=[types.Part(text=s.get('message') or '')])))
            continue
        parts = []
        if s.get('message') and (kind != 'thinking' or include_thoughts):
            parts.append(types.Part(text=s['message'], thought=(kind == 'thinking')))
        calls = []
        for tc in s.get('tool_calls') or []:
            k += 1
            cid = f'call_{k}'
            calls.append((cid, tc))
            parts.append(types.Part(function_call=types.FunctionCall(name=tc['function_name'], args=tc['arguments'], id=cid)))
        if parts:
            events.append(Event(invocation_id=inv, author=agent_name, content=types.Content(role='model', parts=parts)))
        if s.get('observation') is not None and calls:
            cid, tc = calls[0]
            resp = _parse(s['observation'].get('content'))
            events.append(Event(invocation_id=inv, author=agent_name, content=types.Content(role='user', parts=[
                types.Part(function_response=types.FunctionResponse(name=tc['function_name'], response=resp, id=cid))])))
    return events


def arm_messages(state, arm, agent_name):
    """(events to seed, new_message) for one arm. The seeded prefix is identical across arms."""
    events = history_events(state, agent_name)
    assert events and events[-1].content.parts[0].function_response, 'history must end with the fork tool result'
    if arm == 'A':
        last = events.pop()
        return events, types.Content(role='user', parts=last.content.parts)
    payload = state['arms'][arm]
    if arm in ('P', 'Pp'):
        inv = events[-1].invocation_id
        cid = 'call_inserted'
        events.append(Event(invocation_id=inv, author=agent_name, content=types.Content(role='model', parts=[
            types.Part(function_call=types.FunctionCall(name=payload['call']['name'], args=payload['call']['args'], id=cid))])))
        new = types.Content(role='user', parts=[types.Part(function_response=types.FunctionResponse(
            name=payload['call']['name'], response=payload['response'], id=cid))])
        return events, new
    if arm in ('H', 'Hp'):
        return events, types.Content(role='user', parts=[types.Part(text=payload['user_text'])])
    raise ValueError(arm)


def session_state(state):
    task_prompt = next((s.get('message') for s in state['steps'] if _kind(s) == 'task_prompt'), '')
    return {'problem_description': task_prompt}


def build_agent(submission_dir, model_registry, task):
    """Compile the submission the way the harness does, with tools bound to a context that never executes."""
    from adk_submission import compile_submission
    from swegemma.config import build_submission_limits
    from swegemma.context import SwegemmaContext

    ctx = SwegemmaContext(docker_manager=None, task=task, repo=task.get('repo'),
                          graph_dir=str(DATA / 'graphs'), embeddings_dir=str(DATA / 'embeddings'),
                          max_tool_calls=40, max_time_minutes=25)
    limits, gen = build_submission_limits()
    agent = compile_submission(submission_dir=submission_dir, tool_registry=ctx.create_tools(),
                               model_registry=model_registry, limits=limits, generation_constraints=gen,
                               code_executor=None)

    def _no_exec(tool, args, tool_context):
        return {'status': 'captured', 'note': 'replay stops at the first model response'}

    agent.before_tool_callback = _no_exec
    return agent


async def run_one_step(agent, state, arm, seed, timeout=900):
    """Seed a session with the arm's history, make one model call, return what the model did next."""
    svc = InMemorySessionService()
    session = await svc.create_session(app_name=APP_NAME, user_id=USER_ID, state=session_state(state))
    events, new_message = arm_messages(state, arm, agent.name)
    for ev in events:
        await svc.append_event(session, ev)
    if agent.generate_content_config is not None:
        agent.generate_content_config.seed = seed
    runner = Runner(app=App(name=APP_NAME, root_agent=agent), session_service=svc)
    out = {'task': state['task'], 'run': state['run'], 'fork': state.get('fork', 0), 'arm': arm, 'seed': seed, 'node': state['node'],
           'next_call': None, 'thought': '', 'text': '', 'usage': None, 'error': None, 'latency_s': None}
    t0 = time.time()
    agen = runner.run_async(user_id=USER_ID, session_id=session.id, new_message=new_message)
    try:
        async for ev in agen:
            if ev.author != agent.name or not ev.content or not ev.content.parts:
                continue
            fcs = ev.get_function_calls()
            out['thought'] = ''.join(p.text for p in ev.content.parts if p.thought and p.text)
            out['text'] = ''.join(p.text for p in ev.content.parts if p.text and not p.thought)
            if ev.usage_metadata:
                um = ev.usage_metadata
                out['usage'] = {'prompt_tokens': um.prompt_token_count, 'completion_tokens': um.candidates_token_count,
                                'total_tokens': um.total_token_count}
            if fcs:
                out['next_call'] = {'function_name': fcs[0].name, 'arguments': dict(fcs[0].args or {})}
                out['all_calls'] = [{'function_name': f.name, 'arguments': dict(f.args or {})} for f in fcs]
                break
            if ev.is_final_response():
                break
    except Exception as e:  # noqa: BLE001
        out['error'] = f'{type(e).__name__}: {e}'
    finally:
        await agen.aclose()
    out['latency_s'] = round(time.time() - t0, 2)
    return out


# ----------------------------------------------------------------------------- local plumbing test


class FakeLlm:
    """Stands in for the model locally: records each request and answers with one read_file call."""

    def __new__(cls, *a, **k):
        from google.adk.models.base_llm import BaseLlm
        from google.adk.models.llm_response import LlmResponse

        class _Fake(BaseLlm):
            model: str = 'fake'

            async def generate_content_async(self, llm_request, stream=False):
                _Fake.captured.append(llm_request)
                yield LlmResponse(content=types.Content(role='model', parts=[
                    types.Part(text='thinking about it', thought=True),
                    types.Part(function_call=types.FunctionCall(name='read_file', args={'filepath': 'x.py'}, id='fake-1'))]))

        _Fake.captured = []
        return _Fake()


async def _dump_messages(llm_request):
    from google.adk.models.lite_llm import _get_completion_inputs
    res = await _get_completion_inputs(llm_request, 'openai/gemma4-fake')
    return res[0], res[1]


async def _test(state_path):
    from adk_submission import ModelRegistry
    state = json.load(open(state_path, encoding='utf-8'))
    task = {'instance_id': state['task'], 'repo': state['repo'], 'base_commit': state['base_commit']}
    fake = FakeLlm()
    reg = ModelRegistry()
    reg.register(MODEL_ALIAS, fake)
    agent = build_agent(str(ROOT / 'analysis' / 'agents' / 'base'), reg, task)
    print('agent:', agent.name, '| tools:', [getattr(t, 'name', getattr(t, '__name__', '?')) for t in agent.tools])
    print('generate_content_config:', agent.generate_content_config)
    dumps = {}
    for arm in ARMS:
        type(fake).captured.clear()
        out = await run_one_step(agent, state, arm, seed=1)
        req = type(fake).captured[-1]
        messages, tools = await _dump_messages(req)
        dumps[arm] = messages
        print(f'\n=== arm {arm}: {len(messages)} messages, {len(tools)} tool decls, next_call={out["next_call"]}, error={out["error"]}')
        for m in messages[-3:]:
            role = m.get('role')
            body = m.get('content') if m.get('content') else ''
            tc = m.get('tool_calls')
            rc = m.get('reasoning_content')
            print(f'  [{role}] content={str(body)[:160]!r} tool_calls={json.dumps(tc)[:160] if tc else None} reasoning={str(rc)[:60]!r}')
    base = dumps['A']
    for arm in ARMS[1:]:
        n = len(base) - 1
        same = dumps[arm][:n] == base[:n]
        print(f'prefix of {n} messages identical between A and {arm}: {same}')
    print('\nsystem message (first 200 chars):', repr(str(base[0].get('content'))[:200]))
    print('tool declaration names:', [t['function']['name'] for t in tools])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.argv[1] == 'test':
        asyncio.run(_test(sys.argv[2]))
