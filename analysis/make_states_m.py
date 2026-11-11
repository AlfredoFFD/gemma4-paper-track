"""States file for pre-registration 18 (the graph neighbors of a fix site the agent has just been shown).

Usage: py -I -X utf8 analysis/make_states_m.py
Reads the recorded base runs (data/graphloc/out/*/e2e/results/base/w*/traces/trace_*.json; the starter agent,
Gemma-4-31B, 318 runs; not the runs with the skill) and writes analysis/fork_states_m/states.jsonl (not tracked: it
holds other teams' runs).

Rules taken from analysis/public_runs_coedit_sites.py and analysis/public_runs_time_to_fix.py (their functions are
imported, not copied):
  CHANGED REGION  public_runs_time_to_fix.gold_regions: per hunk of the gold patch, the old-file lines it removes or
                  inserts between, without the hunk's context lines.
  SHOWN           a read_file result with status ok whose returned start_line..end_line overlaps the lines in
                  question (shell views are not counted), as in public_runs_coedit_sites.py.
  ENTITY, TARGET  the graph node whose span (analysis/nodes.py) overlaps a region; the TARGET of a region is the
                  one with the shortest span (public_runs_missed_regions.nodes_of_file, as coedit_sites uses it).
  SHOWN ENTITY    an ENTITY whose span overlaps lines SHOWN by some read of the run.
  SEEN SITE S     the TARGET of a CHANGED REGION that some read of the run SHOWS. Its step is the first agent step
                  whose read_file result SHOWS a CHANGED REGION whose TARGET is S.
  MISSED TARGET T of S: the TARGET of a CHANGED REGION that no read of the run SHOWS at any call, T not a SHOWN
                  ENTITY (the OPEN REGION of coedit_sites), T other than S, and T among the neighbors of S AS PRINTED
                  (the first 50 in sorted order of S's graph neighbors without self-loops: coedit_sites.lists). Every
                  MISSED TARGET is also checked to be in S's list as the harness prints it
                  (fork_states.harness_neighbors), the list the arms carry.
Candidate step: the step of a SEEN SITE S that has at least one MISSED TARGET, such that the step comes before any
edit_file, submit_patch, write_file onto a repository file, parallel call or compaction, and the next model call was
logged and not compacted (the conditions of fork_states.py; its cap on the prompt size is not applied, as in
pre-registration 15). When the first read of two SEEN SITES with MISSED TARGETS is the same step, the step is one
candidate and its node is the site with more MISSED TARGETS (then the smaller name). At most the first two
candidate steps of a run are kept; if more than 90 remain, the 90 with the smallest sha1 of
"<task>|<run>|<step index>" (step index: the step's position among the run's agent steps, from 0).

Arms, built for node S as fork_states.make_state builds arms H and E for its node (same wording, channel and entry
format): A nothing added; H the note `Code graph note from the harness. get_code_neighbors(node="S") returned:` and
the JSON object {status, node, neighbors, count} with S's printed list as bare names; E the same with each entry
{name, file, lines, def}. One record per state; the runner's arm A replays it as it stands, arms H and E add the note.
"""
import collections
import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from fork_states import (COMPACTION_RATIO, E_WORDING, H_WORDING, graph_for, harness_neighbors, load_tasks,  # noqa: E402
                         norm_path, shows_content, touches, valid_call)
from gates_c import _ll  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm, result_of  # noqa: E402
from public_runs_coedit_sites import lists  # noqa: E402
from public_runs_missed_regions import nodes_of_file, simple_neighbors  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

ROOT = HERE.parent
OUT = HERE / 'fork_states_m' / 'states.jsonl'
ARMS = ('A', 'H', 'E')
MAX_PER_RUN = 2
MAX_STATES = 90
MIN_STATES = 25


def read_range(call, parsed):
    """(file, start, end) a read_file result returned, as coedit_sites reads it; None otherwise."""
    if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
        f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
        s, e = parsed.get('start_line'), parsed.get('end_line')
        if isinstance(s, int) and isinstance(e, int):
            return f, s, e
    return None


def cut_index(agent, files, edits=True):
    """(index of the first agent step that ends the replayable part, reason): the loop of fork_states.build_states."""
    prev = None
    for i, s in enumerate(agent):
        pt = (s.get('metrics') or {}).get('prompt_tokens')
        if prev and pt and pt < COMPACTION_RATIO * prev:
            return i, 'a compaction'
        prev = pt or prev
        tcs = s.get('tool_calls') or []
        if len(tcs) > 1:
            return i, 'a parallel call'
        if edits and any(tc['function_name'] in ('edit_file', 'submit_patch')
                         or (tc['function_name'] == 'write_file' and norm_path(tc['arguments'].get('filepath')) in files)
                         for tc in tcs):
            return i, 'an edit, submit_patch or write_file onto a repository file'
    return len(agent), None


def next_ok(agent, i):
    """None if the next model call after step i was logged and not compacted (fork_states.make_state), else why not."""
    if i + 1 >= len(agent):
        return 'no next step'
    cur = (agent[i].get('metrics') or {}).get('prompt_tokens')
    nxt = (agent[i + 1].get('metrics') or {}).get('prompt_tokens')
    if not nxt:
        return 'next call not logged'
    if cur and nxt < COMPACTION_RATIO * cur:
        return 'compaction at the next call'
    return None


def scan_run(r, task, gold, tally):
    """The candidate steps of one run, in order, and the counts of its filters."""
    tid = r['task']
    gr = gold.get(tid)
    if not gr:
        return [], {}
    d = load(r['path'])
    g = graph_for(task)
    files = set(N.snapshot_files(tid))
    steps = d['steps']
    agent = [s for s in steps if s['source'] == 'agent']

    def target(f, a, b):  # coedit_sites.main's target()
        cover = [(e0 - s0, -s0, nid) for s0, e0, nid in nodes_of_file(tid, g, f) if not (e0 < a or s0 > b)]
        return min(cover)[2] if cover else None

    reads = collections.defaultdict(list)
    for call, _text, parsed in calls_of(d):
        rr = read_range(call, parsed)
        if rr:
            reads[rr[0]].append((rr[1], rr[2]))
    shown = set()
    for f, spans in reads.items():
        for s0, e0, nid in nodes_of_file(tid, g, f):
            if overlap(s0, e0, spans):
                shown.add(nid)
    sites, open_targets = set(), set()
    for f, regs in gr.items():
        for a, b in regs:
            t = target(f, a, b)
            if overlap(a, b, reads.get(f, [])):
                if t:
                    sites.add(t)
            elif t and t not in shown:
                open_targets.add(t)
    flags = {'sites': bool(sites)}
    if not sites:
        return [], flags

    # the first step that shows each site (a step's result goes to its last call, as in public_runs_address.calls_of)
    first, first_regions = {}, collections.defaultdict(list)
    for i, s in enumerate(agent):
        tcs = s.get('tool_calls') or []
        if not tcs:
            continue
        rr = read_range(tcs[-1], result_of(s)[1])
        if not rr or rr[0] not in gr:
            continue
        f, s0, e0 = rr
        for a, b in gr[f]:
            if overlap(a, b, [(s0, e0)]):
                t = target(f, a, b)
                if t and (t not in first or first[t] == i):
                    first[t] = i
                    first_regions[t].append([f, a, b])
    assert set(first) == sites
    nbr = simple_neighbors(g)
    missed_of = {}
    for S in sites:
        printed = lists(nbr, {S}, shown)[1]
        harness = set(harness_neighbors(g, S))
        mt = sorted(t for t in open_targets if t != S and t in printed)
        tally['missed targets as printed but not in the harness list'] += sum(t not in harness for t in mt)
        missed_of[S] = [t for t in mt if t in harness]
    tally['seen sites'] += len(sites)
    with_mt = [S for S in sites if missed_of[S]]
    tally['seen sites with a missed target'] += len(with_mt)
    flags['site_mt'] = bool(with_mt)
    if not with_mt:
        return [], flags
    by_step = collections.defaultdict(list)
    for S in with_mt:
        by_step[first[S]].append(S)
    tally['steps of a seen site with a missed target'] += len(by_step)
    tally['  of them, steps that first show two or more such sites'] += sum(len(v) > 1 for v in by_step.values())
    cut, why = cut_index(agent, files)
    cut_noedit, _ = cut_index(agent, files, edits=False)
    out = []
    for i in sorted(by_step):
        reason = (f'after {why}' if i >= cut else next_ok(agent, i))
        reason_noedit = ('after a parallel call or a compaction' if i >= cut_noedit else next_ok(agent, i))
        if reason_noedit is None:
            tally['  candidate steps without the before-any-edit condition'] += 1
        if reason:
            tally['  not a candidate: ' + reason] += 1
            continue
        S = sorted(by_step[i], key=lambda n: (-len(missed_of[n]), n))[0]
        out.append(make_state(r, task, g, steps, agent, i, S, missed_of[S], first_regions[S], by_step[i], shown, files))
    flags['candidate'] = bool(out)
    return out, flags


def make_state(r, task, g, steps, agent, i, S, missed, regions, sites_here, shown, files):
    tid = r['task']
    s = agent[i]
    nxt = agent[i + 1]
    listed = harness_neighbors(g, S)
    spans = {n: N.span(tid, n) for n in listed}
    opened = set()
    for st in agent[:i + 1]:
        sc = shows_content(st)
        if sc and sc[0]:
            opened.add(N._norm(sc[0]))

    def encoded(n):  # fork_states.make_state's arm-E entry
        entry = {'name': n}
        sp = spans.get(n)
        if sp:
            entry['file'] = sp['path']
            if sp['end'] is not None:
                entry['lines'] = f"{sp['start']}-{sp['end']}"
        if g['text1'].get(n):
            entry['def'] = g['text1'][n]
        return entry

    h_obs = {'status': 'ok', 'node': S, 'neighbors': listed, 'count': len(listed)}
    e_obs = {'status': 'ok', 'node': S, 'neighbors': [encoded(n) for n in listed], 'count': len(listed)}
    next_call = (nxt.get('tool_calls') or [None])[0]
    obs_missed, obs_listed = {}, {}
    if next_call:
        for n in listed:
            if spans.get(n):
                v = touches(next_call, spans[n], n, line_lengths=_ll(tid, spans[n]['path']))
                obs_listed[n] = v
                if n in missed:
                    obs_missed[n] = v
    key = f"{tid}|{r['run']}|{i}"
    return {
        'task': tid, 'run': r['run'], 'fork': i, 'state_id': key, 'sha1': hashlib.sha1(key.encode()).hexdigest(),
        'arm_source': r['arm'], 'trace': r['path'].relative_to(ROOT).as_posix(),
        'repo': task['repo'], 'base_commit': task['base_commit'], 'graph': g['key'],
        'fork_agent_step': i, 'fork_step_id': s['step_id'], 'tool_calls_before_fork': i + 1,
        'prompt_tokens_at_fork_call': (s.get('metrics') or {}).get('prompt_tokens'),
        'prompt_tokens_next_call_logged': (nxt.get('metrics') or {}).get('prompt_tokens'),
        'node': S, 'node_span': N.span(tid, S), 'site_regions_shown': regions, 'sites_first_shown_here': sorted(sites_here),
        'listed': listed, 'list_spans': spans, 'missed_targets': missed,
        'missed_in_opened_file': {t: bool(spans[t]) and spans[t]['path'] in opened for t in missed},
        'missed_is_shown_entity': {t: t in shown for t in missed}, 'opened_files': sorted(opened),
        'file_lines': {n: (len(t.splitlines()) if (t := N.file_text(tid, sp['path'])) else None)
                       for n, sp in spans.items() if sp},
        'arms': {'H': {'user_text': H_WORDING.format(node=S, json=json.dumps(h_obs))},
                 'E': {'user_text': E_WORDING.format(node=S, json=json.dumps(e_obs))}},
        'observed_next_call': next_call, 'observed_next_call_valid': valid_call(next_call) if next_call else False,
        'observed_touch_missed': obs_missed, 'observed_touch_listed': obs_listed,
        'steps': steps[:steps.index(s) + 1],
    }


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def counts(cs):
    return (f"{len(cs)} steps in {len({(c['task'], c['run']) for c in cs})} runs of {len({c['task'] for c in cs})} tasks")


def quart(xs):
    xs = sorted(xs)
    return f'median {statistics.median(xs):g} (quartiles {xs[len(xs) // 4]} to {xs[(3 * len(xs)) // 4]})'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = load_tasks()
    gold = gold_regions()
    tally = collections.Counter()
    level = collections.defaultdict(set)   # filter -> {(task, run)}
    found = []
    for r in iter_runs(arm='base'):
        level['recorded base runs'].add((r['task'], r['run']))
        if not gold.get(r['task']):
            found.append([])
            continue
        level['with a CHANGED REGION'].add((r['task'], r['run']))
        cs, flags = scan_run(r, tasks[r['task']], gold, tally)
        for k, name in (('sites', 'with a SEEN SITE'), ('site_mt', 'with a SEEN SITE that has a MISSED TARGET'),
                        ('candidate', 'with a candidate step')):
            if flags.get(k):
                level[name].add((r['task'], r['run']))
        found.append(cs)
    print('runs and tasks at each filter:')
    for name in ('recorded base runs', 'with a CHANGED REGION', 'with a SEEN SITE', 'with a SEEN SITE that has a MISSED TARGET',
                 'with a candidate step'):
        print(f'  {name}: {len(level[name])} runs of {len({t for t, _ in level[name]})} tasks')
    print('steps:')
    for k in ('seen sites', 'seen sites with a missed target', 'steps of a seen site with a missed target'):
        print(f'  {tally[k]:4d}  {k}')
    for k in sorted(k for k in tally if k.startswith('  ')):
        print(f'  {tally[k]:4d}  {k.strip()}')
    print(f'  {tally["missed targets as printed but not in the harness list"]:4d}  missed targets as printed but not in the '
          f'harness list (left out)')
    cands = [c for per_run in found for c in per_run]
    print(f'candidate steps, any number per run: {counts(cands)}')
    cands = [c for per_run in found for c in per_run[:MAX_PER_RUN]]
    print(f'candidate steps (at most the first {MAX_PER_RUN} of a run): {counts(cands)}')
    kept = sorted(cands, key=lambda c: c['sha1'])[:MAX_STATES]
    print(f'states (at most {MAX_STATES}, smallest sha1 of "<task>|<run>|<step index>" first): {counts(kept)}')
    if len(kept) < MIN_STATES:
        print(f'FEWER THAN {MIN_STATES} STATES: stop (no states file written). Without the before-any-edit condition: '
              f'{tally["  candidate steps without the before-any-edit condition"]} candidate steps, any number per run')
        return
    for c in kept:  # checks
        assert c['missed_targets'] and all(t in c['listed'] and t != c['node'] for t in c['missed_targets'])
        assert c['steps'][-1]['step_id'] == c['fork_step_id'] and c['steps'][-1]['tool_calls'][0]['function_name'] == 'read_file'
        assert not any(c['missed_is_shown_entity'].values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(json.dumps(c) + '\n' for c in kept), encoding='utf-8', newline='\n')
    print(f'wrote {OUT.relative_to(ROOT).as_posix()}: {len(kept)} records (one per state), md5 {md5(OUT)}')
    by_repo = collections.Counter(c['repo'] for c in kept)
    print(f'by repository: {dict(by_repo)}; runs giving two states: '
          f'{sum(v == 2 for v in collections.Counter((c["task"], c["run"]) for c in kept).values())}')
    print(f'names in the printed list: {quart([len(c["listed"]) for c in kept])}; missed targets in it: '
          f'{quart([len(c["missed_targets"]) for c in kept])}')
    mt = [(c, t) for c in kept for t in c['missed_targets']]
    print(f'missed targets in all: {len(mt)}; in a file the run had opened by the step: '
          f'{sum(c["missed_in_opened_file"][t] for c, t in mt)}; states with every missed target in an opened file: '
          f'{sum(all(c["missed_in_opened_file"].values()) for c in kept)}, with none: '
          f'{sum(not any(c["missed_in_opened_file"].values()) for c in kept)}')
    print(f'missed targets in the same file as the node: '
          f'{sum(bool(c["list_spans"].get(t)) and c["list_spans"][t]["path"] == (c["node_span"] or {}).get("path") for c, t in mt)}')
    print(f'steps that first show two or more sites with missed targets: {sum(len(c["sites_first_shown_here"]) > 1 for c in kept)}')
    pts = sorted(c['prompt_tokens_next_call_logged'] for c in kept)
    print(f'logged prompt tokens at the next call: median {pts[len(pts) // 2]}, max {pts[-1]}; tool calls before the step: '
          f'{quart([c["tool_calls_before_fork"] for c in kept])}')
    print(f'recorded next call usable: {sum(c["observed_next_call_valid"] for c in kept)} of {len(kept)}; it reads, views, '
          f'searches or edits a missed target: {sum(any(v in ("read", "edit") for v in c["observed_touch_missed"].values()) for c in kept)}; '
          f'an entity of the list: {sum(any(v in ("read", "edit") for v in c["observed_touch_listed"].values()) for c in kept)}')
    ex = kept[0]
    t = ex['missed_targets'][0]
    j = ex['listed'].index(t)
    e_entries = json.loads(ex['arms']['E']['user_text'].split('\n', 1)[1])['neighbors']
    print(f'example ({ex["state_id"]}), list of {len(ex["listed"])} names, a missed target at position {j + 1}:')
    print('  H entry:', json.dumps(ex['listed'][j]))
    print('  E entry:', json.dumps(e_entries[j]))


if __name__ == '__main__':
    main()
