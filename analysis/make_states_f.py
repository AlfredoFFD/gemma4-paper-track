"""States file for pre-registration 12 (a file without lines): arm EPATH added to every state of fork_states_d.

Arm EPATH is arm EL's note with the line range removed from every entry: each neighbor keeps its name and its file.
Everything else in the note (its first line, status, node, count, the order of the entries) is arm EL's. So EPATH
differs from EL only by the missing "lines" field, and from arm H (bare names) only by the added "file" field.

Usage: py -I -X utf8 analysis/make_states_f.py
Reads analysis/fork_states_d/states.jsonl (md5 must begin d3105df0dc4a) and writes analysis/fork_states_f/states.jsonl.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'fork_states_d' / 'states.jsonl'
OUT = HERE / 'fork_states_f' / 'states.jsonl'
SRC_MD5 = 'd3105df0dc4a'
LIST_KEY = 'neighbors'
ARM = 'EPATH'


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def split(text):
    """(the note's text before its JSON object, the object)."""
    i = text.index('{')
    return text[:i], json.loads(text[i:])


def epath_arm(state):
    head, el = split(state['arms']['EL']['user_text'])
    assert head + json.dumps(el) == state['arms']['EL']['user_text'], 'json.dumps does not reproduce arm EL byte for byte'
    head_h, h = split(state['arms']['H']['user_text'])
    assert head == head_h and [e['name'] for e in el[LIST_KEY]] == h[LIST_KEY], 'EL and H differ beyond the entries'
    new = copy.deepcopy(el)
    for e in new[LIST_KEY]:
        assert set(e) <= {'name', 'file', 'lines'}, sorted(e)
        e.pop('lines', None)
    return {'user_text': head + json.dumps(new)}, sum('file' in e for e in new[LIST_KEY]), len(new[LIST_KEY])


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    got = md5(SRC)
    assert got.startswith(SRC_MD5), f'{SRC} md5 {got} does not begin {SRC_MD5}'
    lines = SRC.read_text(encoding='utf-8').splitlines()
    assert json.dumps(json.loads(lines[0])) == lines[0], 'cannot reproduce the original line bytes with json.dumps defaults'
    out_lines, with_file, entries = [], 0, 0
    for line in lines:
        st = json.loads(line)
        assert ARM not in st['arms']
        new = copy.deepcopy(st)
        new['arms'][ARM], k, n = epath_arm(st)
        with_file += k
        entries += n
        check = copy.deepcopy(new)
        del check['arms'][ARM]
        assert json.dumps(check) == line  # every other arm and field unchanged
        assert '"lines"' not in new['arms'][ARM]['user_text']
        out_lines.append(json.dumps(new))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in out_lines), encoding='utf-8', newline='\n')
    print(f'source: {SRC.relative_to(HERE.parent).as_posix()} md5 {got}, {len(lines)} states')
    print(f'wrote {OUT.relative_to(HERE.parent).as_posix()}: {len(out_lines)} states, md5 {md5(OUT)}; {entries} entries in arm '
          f'{ARM}, {with_file} with a file; every state passed the checks')
    ex = json.loads(out_lines[0])['arms']
    print('example, arm H    :', ex['H']['user_text'][:230].replace('\n', ' | '))
    print('example, arm EPATH:', ex[ARM]['user_text'][:300].replace('\n', ' | '))
    print('example, arm EL   :', ex['EL']['user_text'][:330].replace('\n', ' | '))


if __name__ == '__main__':
    main()
