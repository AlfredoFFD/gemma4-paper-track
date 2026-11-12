"""Records for pre-registration 25 (the place of the list): arms KH, KE and EL on the paused steps of 03 that end with
a file view.

Usage: py -I -X utf8 analysis/make_states_25.py
Reads analysis/fork_states_d/states.jsonl (the 407 paused steps of pre-registration 03, checked by md5) and writes
  analysis/fork_states_p/states.jsonl    the records for the one-step runner (NOT tracked: they hold the recorded
                                         histories, task statements and repository code)
  analysis/fork_states_p/manifest.json   counts, the fixed order, per-step flags and md5 of inputs and outputs (tracked;
                                         instance ids and graph node names only, no task text and no code)

Steps: every state whose paused history ends with a `read_file` result of status ok. All of them are kept, in a fixed
shuffled order: random.Random(ORDER_SEED) applied to the step ids as the states file lists them. Per step, three
records, one after the other in the file, in the order KH, KE, EL:
  KH  the history with its last result changed: the result object gains the last key `code_graph`, whose value is
      push_23.as_shown(value, 'PH'), value = [{"node": <03's queried node>, "neighbors": <the entries>}]: names only;
  KE  the same with push_23.as_shown(value, 'PE'): each entry as it stands (name, file, line range);
  EL  the step unchanged, with arm EL of pre-registration 04 (the note after the file view; fork_states.py, el_obs).
The entries are those of arm EL of the step, read from its own note: the queried node's true neighbors as
get_code_neighbors lists them (sorted by name, the first 50), each with the keys name, file and lines of arm E and
no definition line; a field arm E lacks stays missing. So KE's entries and EL's are the same objects in the same
order; only the place differs. The key is added as the runner of 23 adds it (wholerun23_runner.push_answers:
out = dict(tool_response); out[push_23.KEY] = shown), so it is the last key of the result, after the file's content
and its line counts. The changed result is written back as JSON text in the style of the recorded result
(make_states_s.dumps_like).

The one-step runner (analysis/modal_w/forks_w_runner.py) replays a history and can add a note; it cannot change the
last result. So records KH and KE run under the runner's arm A (nothing added: the last result is the new message)
and record EL under the runner's arm EL (replay.arm_messages adds state['arms']['EL']['user_text'], whatever the
harness wheels). A record's `fork` is "<03's fork>:<arm>", so the runner keeps the three records of a step apart;
`state_fork` is 03's fork, by which the analysis finds the step in analysis/fork_states_d/states.jsonl.

Per step the manifest flags whether 03's queried node overlaps the lines the last read showed (push_23.shown_range,
the rule by which 23's push decides what a read showed; the node's span from the states file), and whether it lies
in the file read at all.

Checks, all run on every record before anything is written (an AssertionError stops the build):
  - the input file has the md5 of pre-registration 03's states;
  - every recorded result of the kept steps has the keys status, filepath, content, start_line, end_line,
    total_lines, is_truncated, in that order;
  - the entries read from EL's note are exactly the true neighbors in their order, each with the name, file and
    lines that arm E's encoding gives from the state's spans (rebuilt here from neighbor_spans), and H's note lists
    the same names;
  - KH and KE: the history equals the step's history except in the last tool result; there, the parsed object has
    the recorded keys with the recorded values and one more key, `code_graph`, last; the text is the recorded text
    with `, "code_graph": <value>` inserted before its closing brace; and the value is byte for byte
    json.dumps(push_23.as_shown(value, arm)) for the same entries, both as stored and as the agent framework
    renders a tool result to the model (json.dumps with ensure_ascii=False, google.adk lite_llm._safe_json_serialize);
  - EL: the history equals the step's history, and its note is the state's own arm EL note;
  - KE's key and EL's note list the same names in the same order with the same file and line range.
"""
import collections
import copy
import hashlib
import json
import random
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'modal_h'))
import push_23  # noqa: E402
from make_states_s import dumps_like  # noqa: E402

STATES = HERE / 'fork_states_d' / 'states.jsonl'
STATES_MD5 = 'd3105df0dc4aa43d7bb0afbdd6123b44'        # the 407 paused steps of pre-registration 03
OUT_DIR = HERE / 'fork_states_p'
OUT = OUT_DIR / 'states.jsonl'
MANIFEST = OUT_DIR / 'manifest.json'
ORDER_SEED = 25                                       # random.Random(25): the fixed order of the steps
RECORD_ARMS = ('KH', 'KE', 'EL')                      # the order of a step's records
PUSH_ARM = {'KH': 'PH', 'KE': 'PE'}                   # push_23.as_shown's arm for each key arm
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL'}       # the one-step runner's arm for each record
READ_KEYS = ['status', 'filepath', 'content', 'start_line', 'end_line', 'total_lines', 'is_truncated']
NOTE_HEAD = 'Code graph note from the harness. get_code_neighbors(node="{node}") returned:\n'  # fork_states.E_WORDING


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def step_id(s):
    return f"{s['task']}|r{s['run']}|f{s.get('fork', 0)}"


def last_result(s):
    """(the call, the recorded result text, the parsed result) of the step's last tool result."""
    last = s['steps'][-1]
    call = (last.get('tool_calls') or [None])[0]
    text = (last.get('observation') or {}).get('content')
    try:
        obj = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        obj = None
    return call, text, obj


def ends_with_ok_read(s):
    """True if the paused history ends with a read_file result of status ok (decision 2 of pre-registration 25)."""
    call, _text, obj = last_result(s)
    return bool(call) and call['function_name'] == 'read_file' and isinstance(obj, dict) and obj.get('status') == 'ok'


def note_json(user_text, node):
    head = NOTE_HEAD.format(node=node)
    assert user_text.startswith(head), 'a note that does not start with the wording of 03'
    return json.loads(user_text[len(head):])


def e_entry_without_def(s, n):
    """Arm E's entry for n (fork_states.make_state, encoded) reduced to name, file and lines (kept, as el_obs)."""
    entry = {'name': n}
    sp = s['neighbor_spans'].get(n)
    if sp:
        entry['file'] = sp['path']
        if sp['end'] is not None:
            entry['lines'] = f"{sp['start']}-{sp['end']}"
    return entry


def node_overlap(s, obj, call):
    """(the queried node lies in the file read, its span overlaps the lines the read showed)."""
    sp = s['node_span']
    path = push_23.norm(obj.get('filepath') or (call.get('arguments') or {}).get('filepath'))
    in_file = push_23.norm(sp['path']) == path
    r = push_23.shown_range(obj)
    end = sp['end'] if sp['end'] is not None else sp['start']
    return in_file, bool(in_file and r is not None and sp['start'] <= r[1] and end >= r[0])


def build(s):
    """The three records of a step, after the checks of the module's docstring."""
    call, text, obj = last_result(s)
    assert list(obj) == READ_KEYS, f'{step_id(s)}: the recorded read result has other keys: {list(obj)}'
    el = note_json(s['arms']['EL']['user_text'], s['node'])
    h = note_json(s['arms']['H']['user_text'], s['node'])
    entries = el['neighbors']
    assert el['node'] == s['node'] and [e['name'] for e in entries] == s['true_neighbors'], step_id(s)
    assert entries == [e_entry_without_def(s, n) for n in s['true_neighbors']], f'{step_id(s)}: EL entries differ from E without def'
    assert h['neighbors'] == s['true_neighbors'], f'{step_id(s)}: H lists other names'
    value = [{'node': s['node'], 'neighbors': entries}]
    base = {k: v for k, v in s.items() if k not in ('arms', 'steps', 'fork')}
    out = {}
    for arm in RECORD_ARMS:
        rec = dict(base, fork=f"{s.get('fork', 0)}:{arm}", state_fork=s.get('fork', 0), step_id=step_id(s), arm=arm)
        if arm == 'EL':
            rec['arms'] = {'EL': {'user_text': s['arms']['EL']['user_text']}}
            rec['steps'] = s['steps']
        else:
            shown = push_23.as_shown(value, PUSH_ARM[arm])
            changed = dict(obj)                      # as wholerun23_runner.push_answers builds what the agent receives
            changed[push_23.KEY] = shown
            steps = copy.deepcopy(s['steps'])
            steps[-1]['observation']['content'] = dumps_like(text, changed)
            rec['arms'] = {}
            rec['steps'] = steps
        out[arm] = rec
    check(s, out, value, entries, text, obj)
    return out


def check(s, recs, value, entries, text, obj):
    sid = step_id(s)
    for arm in ('KH', 'KE'):
        r = recs[arm]
        assert r['steps'][:-1] == s['steps'][:-1], f'{sid} {arm}: the history differs before the last step'
        a, b = r['steps'][-1], s['steps'][-1]
        assert {k: v for k, v in a.items() if k != 'observation'} == {k: v for k, v in b.items() if k != 'observation'}
        assert {k: v for k, v in a['observation'].items() if k != 'content'} == \
            {k: v for k, v in b['observation'].items() if k != 'content'}, f'{sid} {arm}: observation fields differ'
        new_text = a['observation']['content']
        new = json.loads(new_text)
        assert list(new) == READ_KEYS + [push_23.KEY], f'{sid} {arm}: keys {list(new)}'
        assert all(new[k] == obj[k] and type(new[k]) is type(obj[k]) for k in READ_KEYS), f'{sid} {arm}: a recorded value changed'
        shown = push_23.as_shown(value, PUSH_ARM[arm])
        assert new[push_23.KEY] == shown
        ascii_only = json.dumps(obj, ensure_ascii=True) == text
        assert text.endswith('}') and new_text == text[:-1] + ', "code_graph": ' + json.dumps(shown, ensure_ascii=ascii_only) + '}', \
            f'{sid} {arm}: the stored text is not the recorded text plus the key'
        rendered_old, rendered_new = json.dumps(obj, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
        assert rendered_new == rendered_old[:-1] + ', "code_graph": ' + json.dumps(shown, ensure_ascii=False) + '}', \
            f'{sid} {arm}: the rendered result is not the recorded one plus the key'
        if arm == 'KH':
            assert all(list(e) == ['name'] for e in new[push_23.KEY][0]['neighbors'])
        else:
            assert all(list(e) == [k for k in ('name', 'file', 'lines') if k in e] for e in new[push_23.KEY][0]['neighbors'])
    el = recs['EL']
    assert el['steps'] == s['steps'] and el['arms']['EL']['user_text'] == s['arms']['EL']['user_text'], f'{sid} EL'
    ke = json.loads(recs['KE']['steps'][-1]['observation']['content'])[push_23.KEY][0]
    el_note = note_json(el['arms']['EL']['user_text'], s['node'])
    assert ke['node'] == el_note['node'] and ke['neighbors'] == el_note['neighbors'], f'{sid}: KE and EL list different entries'
    assert [e['name'] for e in json.loads(recs['KH']['steps'][-1]['observation']['content'])[push_23.KEY][0]['neighbors']] \
        == [e['name'] for e in el_note['neighbors']], f'{sid}: KH and EL list different names'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    assert md5(STATES) == STATES_MD5, f'{STATES.relative_to(ROOT).as_posix()} is not the states file of 03'
    states = [json.loads(l) for l in open(STATES, encoding='utf-8')]
    kept = [s for s in states if ends_with_ok_read(s)]
    other = collections.Counter((last_result(s)[0] or {}).get('function_name') for s in states if not ends_with_ok_read(s))
    ids = [step_id(s) for s in kept]
    assert len(set(ids)) == len(ids)
    order = list(ids)
    random.Random(ORDER_SEED).shuffle(order)
    by_id = {step_id(s): s for s in kept}
    print(f'states read: {len(states)} (md5 {STATES_MD5}); steps ending with a read_file result of status ok: '
          f'{len(kept)} in {len({s["task"] for s in kept})} tasks; left out: {dict(other)}')

    lines, flags, n_entries, n_missing, n_no_file, n_no_lines = [], {}, [], 0, 0, 0
    sizes = collections.defaultdict(list)
    for sid in order:
        s = by_id[sid]
        recs = build(s)
        for arm in RECORD_ARMS:
            lines.append(json.dumps(recs[arm]))
        call, text, obj = last_result(s)
        in_file, overlap = node_overlap(s, obj, call)
        ents = note_json(s['arms']['EL']['user_text'], s['node'])['neighbors']
        miss = sum(1 for e in ents if 'file' not in e or 'lines' not in e)
        n_entries.append(len(ents))
        n_missing += miss
        n_no_file += sum(1 for e in ents if 'file' not in e)
        n_no_lines += sum(1 for e in ents if 'file' in e and 'lines' not in e)
        for arm in ('KH', 'KE'):
            sizes[arm].append(len(recs[arm]['steps'][-1]['observation']['content']) - len(text))
        sizes['EL'].append(len(s['arms']['EL']['user_text']))
        flags[sid] = {'task': s['task'], 'node_in_file_read': in_file, 'node_overlaps_shown_lines': overlap,
                      'entries': len(ents), 'entries_without_file_or_lines': miss,
                      'unopened_true_neighbors': len(s['unshown_true_neighbors'])}
    n_overlap = sum(f['node_overlaps_shown_lines'] for f in flags.values())
    n_in_file = sum(f['node_in_file_read'] for f in flags.values())
    print(f'checks passed on every step: recorded read results have the keys {READ_KEYS} in that order; EL\'s entries '
          f'are the true neighbors with arm E\'s name, file and lines; KH and KE differ from the step\'s history in the '
          f'last tool result only, by the added last key `{push_23.KEY}`, whose text is byte for byte '
          f'push_23.as_shown for the same entries (stored and as rendered to the model); EL is the step unchanged with '
          f'its own note; KE\'s key and EL\'s note list the same entries in the same order')
    print(f'records: {len(lines)} ({len(order)} steps x {len(RECORD_ARMS)} arms {RECORD_ARMS}); runner arms {RUNNER_ARM}')
    print(f'entries per list: {sum(n_entries)} in all; median {st.median(n_entries)}, min {min(n_entries)}, '
          f'max {max(n_entries)}; without a file or without a line range: {n_missing} ({n_no_file} without a file, '
          f'{n_no_lines} with a file and no line range)')
    print(f'the queried node overlaps the lines the last read showed (push_23.shown_range): {n_overlap} of {len(order)} '
          f'steps ({len({f["task"] for f in flags.values() if f["node_overlaps_shown_lines"]})} tasks); in the file read but '
          f'not in the lines shown: {n_in_file - n_overlap}; not in the file read: {len(order) - n_in_file}')
    for arm in RECORD_ARMS:
        v = sizes[arm]
        what = 'characters added to the last result' if arm != 'EL' else 'characters of the note'
        print(f'  {arm}: {what}: median {st.median(v):.0f}, min {min(v)}, max {max(v)}')
    print(f'order: random.Random({ORDER_SEED}) over the step ids as the states file lists them; first 8 (the smoke test): '
          f'{order[:8]}')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in lines), encoding='utf-8', newline='\n')
    manifest = {
        'experiment': 'pre-registration 25: the place of the list',
        'file': OUT.relative_to(ROOT).as_posix(), 'md5': md5(OUT), 'records': len(lines),
        'builder': Path(__file__).resolve().relative_to(ROOT).as_posix(), 'builder_md5': md5(__file__),
        'inputs_md5': {'analysis/fork_states_d/states.jsonl': md5(STATES),
                       'analysis/modal_h/push_23.py': md5(push_23.__file__),
                       'analysis/make_states_s.py': md5(HERE / 'make_states_s.py')},
        'record_arms': list(RECORD_ARMS), 'runner_arm_of_record': RUNNER_ARM, 'order_seed': ORDER_SEED,
        'counts': {'states_read': len(states), 'steps': len(order), 'tasks': len({s['task'] for s in kept}),
                   'left_out_by_last_tool': dict(other), 'entries': sum(n_entries),
                   'entries_median': st.median(n_entries), 'entries_min': min(n_entries), 'entries_max': max(n_entries),
                   'entries_without_file_or_lines': n_missing, 'steps_node_overlaps_shown_lines': n_overlap,
                   'tasks_node_overlaps_shown_lines': len({f['task'] for f in flags.values() if f['node_overlaps_shown_lines']}),
                   'steps_node_in_file_read': n_in_file,
                   'characters_added_to_last_result_median': {a: st.median(sizes[a]) for a in ('KH', 'KE')},
                   'characters_of_el_note_median': st.median(sizes['EL'])},
        'order': order,
        'steps': flags,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    print(f'wrote {OUT.relative_to(ROOT).as_posix()} (md5 {manifest["md5"]}, not tracked) and '
          f'{MANIFEST.relative_to(ROOT).as_posix()} (md5 {md5(MANIFEST)})')


if __name__ == '__main__':
    main()
