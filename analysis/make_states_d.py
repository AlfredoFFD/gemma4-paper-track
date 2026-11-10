"""States file for experiment D1 (the tool channel; pre-registration 05): arm PE added to every experiment C state.

Arm PE is arm P's inserted get_code_neighbors call, unchanged, whose result carries arm E's entries (name, file,
line range, first definition line) in place of the bare names. Everything else in the result (status, node, count)
is arm P's. So PE differs from P only in how the entries are written, and from E only in the channel (a tool result
instead of a harness note with arm H's wording).

Usage: py -I -X utf8 analysis/make_states_d.py
Reads analysis/fork_states_c/states.jsonl (md5 must begin 9d7ad4bbd8f4) and writes analysis/fork_states_d/states.jsonl.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'fork_states_c' / 'states.jsonl'
OUT = HERE / 'fork_states_d' / 'states.jsonl'
SRC_MD5 = '9d7ad4bbd8f4'
LIST_KEY = 'neighbors'


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def e_payload(state):
    """The JSON object inside arm E's note: everything from the first '{'."""
    text = state['arms']['E']['user_text']
    return json.loads(text[text.index('{'):])


def pe_arm(state):
    p = state['arms']['P']
    e = e_payload(state)
    resp = p['response']
    assert LIST_KEY in resp and LIST_KEY in e, (state['task'], state['run'], state.get('fork'), sorted(resp), sorted(e))
    others_p = {k: v for k, v in resp.items() if k != LIST_KEY}
    others_e = {k: v for k, v in e.items() if k != LIST_KEY}
    assert others_p == others_e, f'top-level keys differ: P {others_p} | E {others_e}'
    names_p = list(resp[LIST_KEY])
    names_e = [x['name'] for x in e[LIST_KEY]]
    if names_p != names_e:
        print('STOP: arm E entry names differ from arm P names for', state['task'], state['run'], state.get('fork'))
        print('  only in P:', [n for n in names_p if n not in names_e])
        print('  only in E:', [n for n in names_e if n not in names_p])
        print('  same set, different order:', sorted(names_p) == sorted(names_e))
        sys.exit(1)
    new_resp = {k: (copy.deepcopy(e[LIST_KEY]) if k == LIST_KEY else copy.deepcopy(v)) for k, v in resp.items()}
    assert list(new_resp) == list(resp)  # same keys in the same order as arm P's result
    return {'call': copy.deepcopy(p['call']), 'response': new_resp}


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    got = md5(SRC)
    assert got.startswith(SRC_MD5), f'{SRC} md5 {got} does not begin {SRC_MD5}'
    lines = SRC.read_text(encoding='utf-8').splitlines()
    first = json.loads(lines[0])
    byte_exact = json.dumps(first) == lines[0]
    print(f'source: {SRC.relative_to(HERE.parent)} md5 {got}, {len(lines)} lines; '
          f'json.dumps with default settings reproduces line 1 byte for byte: {byte_exact}')
    assert byte_exact, 'cannot reproduce the original line bytes with json.dumps defaults'
    out_lines = []
    for line in lines:
        st = json.loads(line)
        assert 'PE' not in st['arms']
        new = copy.deepcopy(st)
        new['arms']['PE'] = pe_arm(st)
        # every other arm and field unchanged: removing PE gives back the original line byte for byte
        check = copy.deepcopy(new)
        del check['arms']['PE']
        assert json.dumps(check) == line
        assert new['arms']['PE']['call'] == st['arms']['P']['call']
        assert [x['name'] for x in new['arms']['PE']['response'][LIST_KEY]] == st['arms']['P']['response'][LIST_KEY]
        assert new['arms']['PE']['response'][LIST_KEY] == e_payload(st)[LIST_KEY]
        out_lines.append(json.dumps(new))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in out_lines), encoding='utf-8')
    n_entries = sum(len(json.loads(l)['arms']['PE']['response'][LIST_KEY]) for l in out_lines)
    print(f'wrote {OUT.relative_to(HERE.parent)}: {len(out_lines)} lines, md5 {md5(OUT)}; '
          f'{n_entries} PE entries in total; every state passed the checks')


if __name__ == '__main__':
    main()
