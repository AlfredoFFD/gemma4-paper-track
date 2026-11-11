"""EXPLORATORY (not registered): how early the agent calls a graph tool, under two wordings of the task prompt.

Fresh episodes (pre-registrations 08 and 09) start from the task prompt that the recorded runs of September logged.
The whole runs of pre-registration 14 start from the task prompt the current evaluator builds (wheels of Oct 12).
Model, wheels, system prompt and sampling settings are the same in both; the first model call sees nothing but the
system prompt and the task prompt. The two task prompts describe the graph tools differently:

  September:  `search_similar_code(query)`: Find semantically similar functions/classes by keyword.
  Oct 12:     `search_similar_code(query)`: Find functions/classes with similar precomputed embeddings given a symbol
              name (...)

Per setting and condition this prints: sessions; sessions whose first model call is a graph call; with a graph call
within the first eight model calls; with one at any time (fresh episodes end after eight model calls or at the
first command that changes files); graph calls by tool. Shares carry a 95% bootstrap interval over tasks.
Where the task prompts are on this machine (they are competition data and are not stored in the repository), it also
counts the prompts that hold each wording; otherwise it says that the prompts are not here.

Usage: py -I -X utf8 analysis/explore_graph_calls.py [--no-write]
Reads analysis/results/09/forks/results_09.jsonl and analysis/results/14/<N|NAF>/seed1/traces/*.json; writes
analysis/results/explore_graph_calls.txt.
"""
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci  # noqa: E402

GRAPH = ('get_code_neighbors', 'get_code_subgraph', 'search_similar_code')
FRESH = HERE / 'results' / '09' / 'forks' / 'results_09.jsonl'
WHOLE = HERE / 'results' / '14'
OUT = HERE / 'results' / 'explore_graph_calls.txt'
WORDING = (('September', 'Find semantically similar functions/classes by keyword'),
           ('Oct 12', 'with similar precomputed embeddings given a symbol name'))
FRESH_PROMPTS = HERE / 'fork_states_g' / 'fresh_states.jsonl'
WHOLE_PROMPTS = HERE.parent / 'data' / 'forks_14_modal' / 'out_14'


def summarize(sessions):
    """sessions: list of (task, list of model calls, each a list of tool names). Returns counts and shares."""
    by_task = defaultdict(lambda: {'first': [], 'eight': [], 'any': []})
    tools = Counter()
    for task, calls in sessions:
        graph_at = [i for i, names in enumerate(calls) if any(n in GRAPH for n in names)]
        for names in calls:
            tools.update(n for n in names if n in GRAPH)
        by_task[task]['first'].append(1.0 if graph_at and graph_at[0] == 0 else 0.0)
        by_task[task]['eight'].append(1.0 if graph_at and graph_at[0] < 8 else 0.0)
        by_task[task]['any'].append(1.0 if graph_at else 0.0)
    out = {}
    for key in ('first', 'eight', 'any'):
        groups = {task: v[key] for task, v in by_task.items()}
        k = int(sum(sum(g) for g in groups.values()))
        _point, lo, hi = boot_ci(groups)
        out[key] = (k, 100 * lo, 100 * hi)
    return len(sessions), len(by_task), out, tools


def line(label, sessions):
    n, n_tasks, out, tools = summarize(sessions)
    parts = [f'{label}: {n} sessions of {n_tasks} tasks']
    for key, text in (('first', 'first model call is a graph call'),
                      ('eight', 'a graph call within the first eight model calls'), ('any', 'a graph call at any time')):
        k, lo, hi = out[key]
        parts.append(f'{text} {k} ({100 * k / n:.1f}% [{lo:.1f}, {hi:.1f}])')
    parts.append('calls by tool ' + ', '.join(f'{t} {c}' for t, c in sorted(tools.items())) if tools else 'no graph call')
    return ' | '.join(parts)


def fresh_sessions(arm):
    rows = [json.loads(l) for l in open(FRESH, encoding='utf-8')]
    return [(r['task'], [[c.get('function_name') for c in st.get('calls') or []] for st in r['steps']])
            for r in rows if r['arm'] == arm and not r.get('error')]


def whole_sessions(cond):
    out = []
    for f in sorted((WHOLE / cond / 'seed1' / 'traces').glob('*.json')):
        t = json.loads(f.read_text(encoding='utf-8'))
        calls = [[tc.get('function_name') for tc in s.get('tool_calls') or []]
                 for s in t.get('steps') or [] if s.get('source') == 'agent']
        out.append((f.stem.replace('trace_', ''), calls))
    return out


def wording_counts():
    lines = []
    if FRESH_PROMPTS.exists():
        c = Counter()
        n = 0
        for l in open(FRESH_PROMPTS, encoding='utf-8'):
            r = json.loads(l)
            text = ' '.join(str(s.get('message') or '') for s in r.get('steps') or [] if s.get('source') == 'user')
            n += 1
            for name, needle in WORDING:
                c[name] += needle in text
        lines.append(f'task prompts of the fresh episodes: {n}; with the September wording {c["September"]}, '
                     f'with the Oct 12 wording {c["Oct 12"]}')
    else:
        lines.append('task prompts of the fresh episodes: not on this machine')
    files = sorted(WHOLE_PROMPTS.glob('*/seed1/traces/*.json')) if WHOLE_PROMPTS.exists() else []
    if files:
        c = Counter()
        for f in files:
            t = json.loads(f.read_text(encoding='utf-8'))
            text = ' '.join(str(s.get('message') or '') for s in t.get('steps') or [] if s.get('source') == 'user')
            for name, needle in WORDING:
                c[name] += needle in text
        lines.append(f'task prompts of the whole runs: {len(files)}; with the September wording {c["September"]}, '
                     f'with the Oct 12 wording {c["Oct 12"]}')
    else:
        lines.append('task prompts of the whole runs: not on this machine (the stored traces omit them)')
    return lines


def main():
    buf = io.StringIO()

    def p(*a):
        print(*a)
        print(*a, file=buf)

    p('EXPLORATORY. Graph-tool calls by the agent itself, under two wordings of the task prompt.')
    p('Fresh episodes (task prompt as the September runs logged it; wheels of Oct 12; up to eight model calls):')
    for arm in ('N', 'NA', 'NAF'):
        p('  ' + line(f'condition {arm}', fresh_sessions(arm)))
    p('Whole runs (task prompt of the current evaluator; wheels of Oct 12; up to 40 tool calls):')
    for cond in ('N', 'NAF'):
        if (WHOLE / cond / 'seed1' / 'traces').is_dir():
            p('  ' + line(f'condition {cond}', whole_sessions(cond)))
        else:
            p(f'  condition {cond}: no stored traces')
    p('How the task prompts describe the graph tools:')
    for l in wording_counts():
        p('  ' + l)
    if '--no-write' not in sys.argv:
        OUT.write_text(buf.getvalue(), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
