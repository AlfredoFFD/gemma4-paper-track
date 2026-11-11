"""States file for experiment 20 ("asked or told": the same search hits, asked for by the agent or handed to it).

Usage: py -I -X utf8 analysis/make_states_t.py
Reads the recorded base runs, as analysis/make_states_s.py does, and writes analysis/fork_states_t/states.jsonl (not
tracked: it holds other teams' runs) and analysis/fork_states_t/manifest.json (tracked: counts and md5 only).

Population: the 61 states of pre-registration 15 (make_states_s.scan_run, the first two candidate steps of a run, the
100 smallest sha1), with the same keys (task, run, fork_agent_step). Each state of 15 ends with the result of the
agent's own numbered search. Here the history is cut just BEFORE that search: the step that holds the search call
and its result is removed, so the replayed history ends with the step before it. A state whose shortened history does
not end on a tool result (the step before is not an agent step with one tool call and its result) is dropped from
every arm and counted.

Arms (the note is attached as make_states_s attaches the note of arm S0N: `arms = {<arm>: {'user_text': note}}`, which
the runner delivers as one user message after the last tool result):
  NONE   the shortened history, nothing added (the runner's arm A);
  TOLD   the shortened history and a note: `Matches in the repository:` and then the hit lines of the recorded search
         result in its order, each written `path:line:text` (a `line:text` hit of a command that names one file gets
         that file as the command wrote it, the form of the note of S0N); no context line, no command, no instruction;
  TOLDX  the shortened history and a note of the same form that holds every hit line of ANOTHER recorded search. A
         search step qualifies if it meets the conditions a state's own search met in 15 (one call, `run_command`
         running a search program, status ok, a numbered hit line, at most 40 hit lines, fewer than 5,000 characters,
         no numbered line that belongs to no one file), its result names with a line number a repository file that
         the run had not opened at the paused step, and its result names NO file that the state's own search result
         names (by a hit or a context line, any file). The other search is, in this order:
           (a) source `same run`: a search at another step of the same run whose result is not already in the
               shortened history (a step after the paused one: every earlier step is in the history), the nearest by
               step (earlier wins a tie);
           (b) source `other run`, if the run has none: a search recorded in another base run of the same task, the
               one whose step index is nearest to the paused step's (earlier wins a tie, then the lower run number).
         A state with neither has no TOLDX record and is counted;
  ASKED  the history as recorded, with the agent's search and its result: arm S of pre-registration 15 (the same
         history as its record `<step>:S`; the runner's arm A), replayed in this launch so that T2 compares arms of
         one launch.

What the scorer needs, in every record:
  hit_files    the files the outcome is scored on, each with its hit lines: for NONE, TOLD and ASKED the repository
               files with a hit line in the state's own search result that the run had not opened (the hit files of
               15); for TOLDX the repository files of its note that the run had not opened;
  file_lines   the number of lines of each of those files in the snapshot;
  opened_files the files opened before the paused step (as in 15);
  note_files   every repository file with a hit line in the note;
  own_hit_files the hit files of the state's own search (the same in all arms);
  own_search_call the recorded search call (tool name and arguments) that the state of 15 ends with.
A TOLDX record also keeps its source, the run and step of the other search, and, in every record, the number of
qualifying searches in the same run after the paused step, in the same run before it (in the history, so never used),
and in the other runs of the task.
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
import make_states_s as S  # noqa: E402
from fork_states import MAX_STDOUT_CHARS, load_tasks, parse_obs  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402

ROOT = HERE.parent
OUT_DIR = HERE / 'fork_states_t'
OUT = OUT_DIR / 'states.jsonl'
MANIFEST = OUT_DIR / 'manifest.json'
ARMS = ('NONE', 'TOLD', 'TOLDX', 'ASKED')
RUNNER_ARM = {'NONE': 'A', 'TOLD': 'TOLD', 'TOLDX': 'TOLDX', 'ASKED': 'A'}
NOTE_HEAD = 'Matches in the repository:'


def search_hits(step, files):
    """The parsed numbered hits of one agent step if it is a search step as 15 defines one, else None.

    Returns {'command', 'hits': [(repository path or None, path as written, line, text)], 'named': set of repository
    files named by a hit or context line, 'named_all': every path so named, as a path inside the repository} or None.
    """
    tcs = step.get('tool_calls') or []
    if len(tcs) != 1 or tcs[0]['function_name'] != 'run_command':
        return None
    cmd = str(tcs[0]['arguments'].get('command', ''))
    o = parse_obs(step)
    if not S.search_segments(cmd) or not isinstance(o, dict) or o.get('status') != 'ok' or not o.get('stdout'):
        return None
    stdout = o['stdout']
    named = S.named_files(cmd, files)
    one_file, one_word = named[0] if len(named) == 1 else (None, None)
    lines, kinds = S.parse_output(stdout, one_file)
    hits = [k for k in kinds if k and k[0] == 'hit']
    if (not hits or len(stdout) >= MAX_STDOUT_CHARS or len(hits) > S.MAX_HITS
            or any(k and k[0] == 'unplaced' for k in kinds)):
        return None
    out = []
    for k in hits:
        written = one_word if k[1] is None else k[1]
        p = one_file if k[1] is None else S.repo_path(k[1])
        out.append((p if p in files else None, written, int(k[2]), k[3]))
    named_all = {(one_file if k[1] is None else S.repo_path(k[1])) for k in kinds if k and k[0] in ('hit', 'context')}
    return {'command': cmd, 'hits': out, 'named': {p for p in named_all if p in files}, 'named_all': named_all}


def note_of(hits):
    return NOTE_HEAD + ''.join(f'\n{written}:{line}:{text}' for _p, written, line, text in hits)


def files_with_lines(hits, keep):
    d = collections.OrderedDict()
    for p, _w, line, _t in hits:
        if p is not None and keep(p):
            d.setdefault(p, []).append(line)
    return dict(d)


def ends_on_tool_result(steps):
    """True if the last step is an agent step with one tool call and its result (the replay then ends on that
    tool result: replay.history_events makes it the last event, a function response)."""
    last = steps[-1] if steps else None
    return bool(last and last['source'] == 'agent' and len(last.get('tool_calls') or []) == 1
                and last.get('observation') is not None and last['observation'].get('content') is not None)


def build(c, runs_of_task, agent_steps):
    """The records of one state of 15, or (None, reason)."""
    b = c['base']
    d = load(ROOT / b['trace'])
    steps = d['steps']
    agent = [s for s in steps if s['source'] == 'agent']
    i = b['fork_agent_step']
    s = agent[i]
    assert c['history'][-1] is not None and c['history'][-1]['step_id'] == s['step_id'] == b['fork_step_id']
    assert str(s['tool_calls'][0]['arguments'].get('command', '')) == b['command']
    history = c['history'][:-1]
    assert history == steps[:steps.index(s)]
    if not ends_on_tool_result(history):
        last = history[-1] if history else None
        if not any(x['source'] == 'agent' for x in history):
            why = 'the search is the agent\'s first step (the history before it ends on the task prompt)'
        elif last['source'] != 'agent':
            why = f"the step before the search is a {last['source']} message, not a tool result"
        else:
            why = 'the step before the search is an agent step without one tool call and its result'
        return None, why
    files = set(N.snapshot_files(b['task']))
    own = search_hits(s, files)
    assert own is not None
    own_hit_files = b['hit_files']
    assert files_with_lines(own['hits'], lambda p: p not in set(b['opened_files'])) == own_hit_files
    opened = set(b['opened_files'])

    told_note = note_of(own['hits'])

    def qualifies(h):
        q = files_with_lines(h['hits'], lambda p: p not in opened)
        return q if q and not (h['named_all'] & own['named_all']) else None

    same_after, same_before = [], []
    for j in range(len(agent)):
        if j == i or (h := search_hits(agent[j], files)) is None or (q := qualifies(h)) is None:
            continue
        (same_after if j > i else same_before).append((j, h, q))
    others = []
    for r2 in runs_of_task[b['task']]:
        if r2['run'] == b['run']:
            continue
        for j, st2 in enumerate(agent_steps(r2)):
            if (h := search_hits(st2, files)) is not None and (q := qualifies(h)) is not None:
                others.append((r2['run'], j, h, q, st2['step_id']))
    other = None
    if same_after:
        j, h, q = min(same_after, key=lambda x: (abs(x[0] - i), x[0]))
        other = dict(source='same run', run=b['run'], step=j, step_id=agent[j]['step_id'], h=h, q=q)
    elif others:
        run2, j, h, q, sid = min(others, key=lambda x: (abs(x[1] - i), x[1] > i, x[0]))
        other = dict(source='other run', run=run2, step=j, step_id=sid, h=h, q=q)
    counts = {'same_run_after': len(same_after), 'same_run_before_in_history': len(same_before),
              'other_runs': len(others), 'other_runs_runs': len({x[0] for x in others})}

    def lengths(fs):
        return {f: (len(t.splitlines()) if (t := N.file_text(b['task'], f)) is not None else None) for f in fs}

    def equal_snapshot(hits):
        same = n = 0
        for p, _w, line, text in hits:
            src = N.file_text(b['task'], p) if p else None
            if src is None:
                continue
            n += 1
            sl = src.split('\n')
            same += int(1 <= line <= len(sl) and sl[line - 1].rstrip('\r') == text.rstrip('\r'))
        return same, n

    keep = ('task', 'run', 'state_id', 'sha1', 'arm_source', 'trace', 'repo', 'base_commit', 'node', 'fork_agent_step',
            'one_file', 'opened_files', 'files_numbered_earlier')
    common = {k: b[k] for k in keep}
    common.update(
        state_of_15=f"{i}:S", own_search_step_id=b['fork_step_id'], own_search_command=b['command'],
        own_search_call=s['tool_calls'][0], own_hit_files=own_hit_files,
        prompt_tokens_next_call_logged=b['prompt_tokens_at_fork_call'],   # the logged prompt of the call replayed here
        prompt_tokens_next_call_logged_15=b['prompt_tokens_next_call_logged'],
        observed_next_call=s['tool_calls'][0], observed_next_call_valid=b['observed_next_call_valid'],
        steps=history, toldx_candidates=counts)
    told_same = equal_snapshot(own['hits'])
    recs = []
    for arm in ARMS:
        if arm == 'TOLDX' and other is None:
            continue
        rec = dict(common, fork=f'{i}:{arm}', arm=arm)
        if arm == 'NONE':
            rec.update(arms={}, note=None, hit_files=own_hit_files, file_lines=lengths(own_hit_files),
                       note_files=sorted({p for p, *_ in own['hits'] if p}))
        elif arm == 'TOLD':
            rec.update(arms={arm: {'user_text': told_note}}, note=told_note, hit_files=own_hit_files,
                       file_lines=lengths(own_hit_files), note_files=sorted({p for p, *_ in own['hits'] if p}),
                       note_hit_lines=len(own['hits']), note_hit_lines_equal_snapshot=told_same)
        elif arm == 'ASKED':
            rec.update(arms={}, note=None, hit_files=own_hit_files, file_lines=lengths(own_hit_files),
                       note_files=sorted({p for p, *_ in own['hits'] if p}), steps=c['history'],
                       prompt_tokens_next_call_logged=b['prompt_tokens_next_call_logged'])
        else:
            h, q = other['h'], other['q']
            note = note_of(h['hits'])
            rec.update(arms={arm: {'user_text': note}}, note=note, hit_files=q, file_lines=lengths(q),
                       note_files=sorted({p for p, *_ in h['hits'] if p}), toldx_source=other['source'],
                       other_search_run=other['run'], other_search_agent_step=other['step'],
                       other_search_step_id=other['step_id'], other_search_distance=other['step'] - i,
                       other_search_command=h['command'], note_hit_lines=len(h['hits']),
                       note_hit_lines_equal_snapshot=equal_snapshot(h['hits']),
                       note_names_opened_files=sorted({p for p, *_ in h['hits'] if p in opened}))
        recs.append(rec)
    # the arms differ in the added note only; TOLD's hits are the recorded ones
    by = {r['arm']: r for r in recs}
    skip = ('steps', 'prompt_tokens_next_call_logged')
    for r in recs:
        assert {k: v for k, v in r.items() if k in common and k not in skip} == \
            {k: v for k, v in common.items() if k not in skip}
        assert r['steps'] is (c['history'] if r['arm'] == 'ASKED' else history)
    assert by['ASKED']['steps'][:-1] == by['NONE']['steps'] and by['ASKED']['steps'][-1]['step_id'] == b['fork_step_id']
    if 'TOLDX' in by:
        x = by['TOLDX']
        assert x['hit_files'] and not set(x['hit_files']) & opened
        assert x['toldx_source'] == 'other run' or x['other_search_distance'] > 0
    assert by['NONE']['arms'] == {} and by['TOLD']['arms']['TOLD']['user_text'].split('\n')[0] == NOTE_HEAD
    stdout = parse_obs(s)['stdout']
    for line in by['TOLD']['note'].split('\n')[1:]:
        assert line in stdout.split('\n') or line.split(':', 1)[1] in stdout.split('\n')
    return recs, None


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = load_tasks()
    tally = collections.Counter()
    found, runs, runs_of_task = [], 0, collections.defaultdict(list)
    for r in iter_runs(arm='base'):
        runs += 1
        runs_of_task[r['task']].append(r)
        found.append(S.scan_run(r, tasks[r['task']], tally))
    for task, rs in runs_of_task.items():
        assert len({r['run'] for r in rs}) == len(rs), f'two recorded base runs of {task} share a run number'
    cache = {}

    def agent_steps(r):
        if r['path'] not in cache:
            cache[r['path']] = [s for s in load(r['path'])['steps'] if s['source'] == 'agent']
        return cache[r['path']]
    cands = [c for per_run in found for c in per_run[:S.MAX_PER_RUN]]
    kept = sorted(cands, key=lambda c: c['base']['sha1'])[:S.MAX_STATES]
    print(f'recorded base runs read: {runs}; states of pre-registration 15 rebuilt: {S.counts(kept)}')

    out_lines, dropped, no_x, states = [], collections.Counter(), [], []
    for c in kept:
        recs, why = build(c, runs_of_task, agent_steps)
        if recs is None:
            dropped[why] += 1
            continue
        states.append(recs)
        if not any(r['arm'] == 'TOLDX' for r in recs):
            no_x.append(c['base']['state_id'])
        out_lines += [json.dumps(r) for r in recs]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in out_lines), encoding='utf-8', newline='\n')

    by_arm = collections.Counter(r['arm'] for recs in states for r in recs)
    x = [r for recs in states for r in recs if r['arm'] == 'TOLDX']
    t = [r for recs in states for r in recs if r['arm'] == 'TOLD']
    med = lambda v: statistics.median(v) if v else None  # noqa: E731
    stats = {
        'states_of_15': len(kept),
        'states_kept': len(states),
        'states_dropped': sum(dropped.values()),
        'dropped_why': dict(dropped),
        'states_with_TOLDX': len(x),
        'states_without_TOLDX': len(no_x),
        'states_without_TOLDX_why': 'no qualifying search after the paused step in the same run and none in another '
                                    'base run of the task',
        'records_by_arm': dict(by_arm),
        'records': len(out_lines),
        'runs': len({(r[0]['task'], r[0]['run']) for r in states}),
        'tasks': len({r[0]['task'] for r in states}),
        'repositories': dict(collections.Counter(r[0]['repo'] for r in states)),
        'TOLD_note_hit_lines_median': med([r['note_hit_lines'] for r in t]),
        'TOLD_note_hit_lines_range': [min(r['note_hit_lines'] for r in t), max(r['note_hit_lines'] for r in t)],
        'TOLD_hit_lines_in_snapshot_files_equal_snapshot': [sum(r['note_hit_lines_equal_snapshot'][0] for r in t),
                                                           sum(r['note_hit_lines_equal_snapshot'][1] for r in t)],
        'TOLDX_states_source_a_same_run': sum(r['toldx_source'] == 'same run' for r in x),
        'TOLDX_states_source_b_other_run': sum(r['toldx_source'] == 'other run' for r in x),
        'TOLDX_states_a_or_b': len(x),
        'states_with_a_qualifying_earlier_search_of_the_same_run_whose_result_is_in_the_history':
            sum(r[0]['toldx_candidates']['same_run_before_in_history'] > 0 for r in states),
        'states_whose_run_has_a_qualifying_later_search': sum(r[0]['toldx_candidates']['same_run_after'] > 0 for r in states),
        'states_with_a_qualifying_search_in_another_run': sum(r[0]['toldx_candidates']['other_runs'] > 0 for r in states),
        'qualifying_searches_in_other_runs_per_state_median':
            med([r[0]['toldx_candidates']['other_runs'] for r in states]),
        'base_runs_per_task': dict(collections.Counter(len(runs_of_task[task]) for task in {r[0]['task'] for r in states})),
        'qualifying_searches_in_other_runs_of_the_task_by_task_one_count_per_state': {
            task: [r[0]['toldx_candidates']['other_runs'] for r in states if r[0]['task'] == task]
            for task in sorted({r[0]['task'] for r in states})},
        'TOLDX_note_hit_lines_median': med([r['note_hit_lines'] for r in x]),
        'TOLDX_note_hit_lines_range': [min(r['note_hit_lines'] for r in x), max(r['note_hit_lines'] for r in x)] if x else None,
        'TOLDX_hit_lines_in_snapshot_files_equal_snapshot': [sum(r['note_hit_lines_equal_snapshot'][0] for r in x),
                                                            sum(r['note_hit_lines_equal_snapshot'][1] for r in x)],
        'TOLDX_distance_in_agent_steps_median_abs_same_run': med([abs(r['other_search_distance']) for r in x
                                                                  if r['toldx_source'] == 'same run']),
        'TOLDX_distance_in_agent_steps_median_abs_other_run': med([abs(r['other_search_distance']) for r in x
                                                                   if r['toldx_source'] == 'other run']),
        'TOLDX_notes_that_also_name_an_opened_file': sum(bool(r['note_names_opened_files']) for r in x),
        'TOLDX_scored_files': sum(len(r['hit_files']) for r in x),
        'TOLDX_states_whose_scored_files_all_have_first_hit_past_line_150':
            sum(all(min(v) > 150 for v in r['hit_files'].values()) for r in x),
        'TOLD_states_whose_scored_files_all_have_first_hit_past_line_150':
            sum(all(min(v) > 150 for v in r['hit_files'].values()) for r in t),
        'replays_planned_seeds_1_to_3': 3 * len(out_lines),
    }
    manifest = {'file': OUT.relative_to(ROOT).as_posix(), 'md5': S.md5(OUT),
                'builder': Path(__file__).relative_to(ROOT).as_posix(), 'builder_md5': S.md5(Path(__file__)),
                'make_states_s_md5': S.md5(HERE / 'make_states_s.py'), 'counts': stats}
    MANIFEST.write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    print(f'wrote {OUT.relative_to(ROOT).as_posix()}: {len(out_lines)} records, md5 {manifest["md5"]}; '
          f'{MANIFEST.relative_to(ROOT).as_posix()}')


if __name__ == '__main__':
    main()
