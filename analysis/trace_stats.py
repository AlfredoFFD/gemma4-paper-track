"""Independent re-derivation of the GraphLoc base-arm trace numbers used in the paper (EXPLORATORY).

Re-derives, from the raw traces and with this repo's own span resolver:
- how often runs call a graph tool, and how often a call returns anything;
- uptake: after a non-empty graph result, does the agent's next read or edit touch a returned node, against the
  same count of random nodes drawn from the same files (size-matched control, 200 resamples);
- whether a returned node is later edited in the run;
- compaction (a prompt-token drop of more than 30% between consecutive calls) and overflow.
Writes analysis/trace_stats.json. Usage: py -I analysis/trace_stats.py
"""
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes as N  # noqa: E402
from fork_states import CONTENT_CMD, PATH_TOKEN, graph_for, load_tasks, parse_obs, touches  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402

GRAPH_TOOLS = ('get_code_neighbors', 'search_similar_code', 'get_code_subgraph')
READ_EDIT = ('read_file', 'edit_file', 'write_file', 'run_command')


def returned_nodes(tool, obs):
    if not isinstance(obs, dict) or obs.get('status') != 'ok':
        return []
    if tool == 'get_code_neighbors':
        return [str(x) for x in obs.get('neighbors') or []]
    if tool == 'search_similar_code':
        return [str(x.get('node_name')) for x in obs.get('results') or [] if isinstance(x, dict)]
    if tool == 'get_code_subgraph':
        return [str(x.get('id') or x.get('name') or x) for x in obs.get('nodes') or []]
    return []


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = load_tasks()
    rng = random.Random(0)
    runs_total = runs_graph_call = runs_nonempty = 0
    calls = collections.Counter()
    empty = collections.Counter()
    compaction_runs = overflow_runs = 0
    events = []
    for r in iter_runs(arm='base'):
        d = load(r['path'])
        task = tasks[r['task']]
        g = graph_for(task)
        steps = d['steps']
        agent = [s for s in steps if s['source'] == 'agent']
        runs_total += 1
        called = nonempty = False
        prev = None
        compacted = False
        for s in agent:
            pt = (s.get('metrics') or {}).get('prompt_tokens')
            if prev and pt and pt < 0.7 * prev:
                compacted = True
            prev = pt or prev
        compaction_runs += compacted
        text_all = json.dumps(d.get('final_metrics') or {}) + ' '.join((s.get('message') or '')[-300:] for s in steps[-2:])
        if 'ContextWindowExceeded' in text_all or 'context window' in text_all.lower():
            overflow_runs += 1
        for i, s in enumerate(agent):
            for tc in s.get('tool_calls') or []:
                tool = tc['function_name']
                if tool not in GRAPH_TOOLS:
                    continue
                called = True
                calls[tool] += 1
                obs = parse_obs(s)
                nodes_ret = [n for n in returned_nodes(tool, obs) if n in g['idset']]
                if not nodes_ret:
                    empty[tool] += 1
                    continue
                nonempty = True
                def _shows(a):
                    tc0 = (a.get('tool_calls') or [{}])[0]
                    fn = tc0.get('function_name')
                    if fn in ('read_file', 'edit_file', 'write_file'):
                        return True
                    if fn == 'run_command':  # only commands that show file content, not ls/find/python
                        cmd = str((tc0.get('arguments') or {}).get('command', ''))
                        return bool(CONTENT_CMD.match(cmd) and PATH_TOKEN.search(cmd))
                    return False

                nxt = next((a for a in agent[i + 1:] if _shows(a)), None)
                if nxt is None:
                    continue
                call = nxt['tool_calls'][0]
                spans = {n: N.span(r['task'], n) for n in nodes_ret}
                spans = {n: sp for n, sp in spans.items() if sp}
                if not spans:
                    continue
                hit = any(touches(call, sp, n) in ('read', 'edit') for n, sp in spans.items())
                files = {sp['path'] for sp in spans.values()}
                pool = [n for n in g['ids'] if n not in spans and (N.resolve(r['task'], n) or ('',))[0] in files]
                ctrl = []
                for _ in range(200):
                    sample = rng.sample(pool, min(len(spans), len(pool))) if pool else []
                    ctrl.append(any(touches(call, N.span(r['task'], n), n) in ('read', 'edit') for n in sample if N.span(r['task'], n)))
                later_edit_file = later_edit_span = False
                for a in agent[i + 1:]:
                    for tc2 in a.get('tool_calls') or []:
                        if tc2['function_name'] in ('edit_file', 'write_file'):
                            for n, sp in spans.items():
                                if tc2['arguments'].get('filepath') == sp['path']:
                                    later_edit_file = True
                                    old = str(tc2['arguments'].get('old_string') or '')
                                    src = N.file_text(r['task'], sp['path']) or ''
                                    lines = src.splitlines()
                                    span_text = '\n'.join(lines[sp['start'] - 1:(sp['end'] or len(lines))])
                                    if old and old.strip() and old.strip() in span_text:
                                        later_edit_span = True
                events.append({'task': r['task'], 'run': r['run'], 'tool': tool, 'n_returned': len(nodes_ret), 'n_resolved': len(spans),
                               'next_call': call['function_name'], 'hit': hit, 'control_rate': sum(ctrl) / len(ctrl) if ctrl else None,
                               'later_edit_file': later_edit_file, 'later_edit_span': later_edit_span})
        runs_graph_call += called
        runs_nonempty += nonempty
    hits = sum(e['hit'] for e in events)
    ctrl_rates = [e['control_rate'] for e in events if e['control_rate'] is not None]
    out = {
        'label': 'EXPLORATORY re-derivation of GraphLoc base-arm trace numbers, Nov 8 2026',
        'runs': runs_total, 'runs_calling_a_graph_tool': runs_graph_call, 'runs_with_a_nonempty_graph_result': runs_nonempty,
        'calls': dict(calls), 'empty_results': dict(empty),
        'uptake_events': len(events), 'uptake_hits': hits, 'uptake_rate': round(hits / len(events), 4) if events else None,
        'control_rate_mean': round(sum(ctrl_rates) / len(ctrl_rates), 4) if ctrl_rates else None,
        'later_edit_of_a_returned_file': sum(e['later_edit_file'] for e in events),
        'later_edit_inside_a_returned_span': sum(e['later_edit_span'] for e in events),
        'compaction_runs': compaction_runs, 'overflow_runs': overflow_runs,
        'events': events,
    }
    Path(__file__).resolve().parent.joinpath('trace_stats.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    for k, v in out.items():
        if k != 'events':
            print(f'{k}: {v}')


if __name__ == '__main__':
    main()
