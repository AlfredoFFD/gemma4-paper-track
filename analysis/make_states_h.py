"""States file for pre-registration 13 (the address written as a search hit): arm EG added to every state of
fork_states_d.

Arm EG carries what arm E carries for each neighbor (its file, the first line of its range and its first definition
line) and writes it the way a recursive numbered search prints a hit, one neighbor per line:

    <file>:<first line>:<first definition line>

in arm E's order, under arm E's first line. An entry of arm E that has no file keeps its name alone on its line. An
entry with a file and a range and no definition line is written <file>:<first line>:<name>. Arm EG therefore differs
from arm E in the writing, and in three things it leaves out: the JSON wrapper (status, node, count), each range's
last line, and each neighbor's qualified name.

Usage: py -I -X utf8 analysis/make_states_h.py
Reads analysis/fork_states_d/states.jsonl (md5 must begin d3105df0dc4a) and writes analysis/fork_states_h/states.jsonl.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'fork_states_d' / 'states.jsonl'
OUT = HERE / 'fork_states_h' / 'states.jsonl'
SRC_MD5 = 'd3105df0dc4a'
LIST_KEY = 'neighbors'
ARM = 'EG'


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def split(text):
    """(the note's text before its JSON object, the object)."""
    i = text.index('{')
    return text[:i], json.loads(text[i:])


def hit(e):
    """One neighbor as a search hit; kind is 'hit', 'hit without definition line' or 'name only'."""
    if e.get('file') and e.get('lines'):
        m = re.match(r'^\s*(\d+)', str(e['lines']))
        assert m, e
        if e.get('def'):
            assert '\n' not in e['def'], e
            return f'{e["file"]}:{m.group(1)}:{e["def"]}', 'hit'
        return f'{e["file"]}:{m.group(1)}:{e["name"]}', 'hit without definition line'
    return e['name'], 'name only'


def eg_arm(state):
    head, obj = split(state['arms']['E']['user_text'])
    assert head + json.dumps(obj) == state['arms']['E']['user_text'], 'json.dumps does not reproduce arm E byte for byte'
    head_h, h = split(state['arms']['H']['user_text'])
    assert head == head_h and [e['name'] for e in obj[LIST_KEY]] == h[LIST_KEY], 'E and H differ beyond the entries'
    assert head.endswith('\n'), repr(head[-20:])
    lines, kinds = [], []
    for e in obj[LIST_KEY]:
        assert set(e) <= {'name', 'file', 'lines', 'def'}, sorted(e)
        text, kind = hit(e)
        lines.append(text)
        kinds.append(kind)
    return {'user_text': head + '\n'.join(lines)}, kinds


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    got = md5(SRC)
    assert got.startswith(SRC_MD5), f'{SRC} md5 {got} does not begin {SRC_MD5}'
    lines = SRC.read_text(encoding='utf-8').splitlines()
    assert json.dumps(json.loads(lines[0])) == lines[0], 'cannot reproduce the original line bytes with json.dumps defaults'
    out_lines, tally = [], {}
    chars_e = chars_eg = 0
    for line in lines:
        st = json.loads(line)
        assert ARM not in st['arms']
        new = copy.deepcopy(st)
        new['arms'][ARM], kinds = eg_arm(st)
        for k in kinds:
            tally[k] = tally.get(k, 0) + 1
        check = copy.deepcopy(new)
        del check['arms'][ARM]
        assert json.dumps(check) == line  # every other arm and field unchanged
        chars_e += len(st['arms']['E']['user_text'])
        chars_eg += len(new['arms'][ARM]['user_text'])
        out_lines.append(json.dumps(new))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in out_lines), encoding='utf-8', newline='\n')
    print(f'source: {SRC.relative_to(HERE.parent).as_posix()} md5 {got}, {len(lines)} states')
    print(f'wrote {OUT.relative_to(HERE.parent).as_posix()}: {len(out_lines)} states, md5 {md5(OUT)}; entries in arm {ARM} '
          f'by kind: {tally}; every state passed the checks')
    print(f'mean characters of the note: arm E {chars_e / len(lines):.0f}, arm {ARM} {chars_eg / len(lines):.0f}')
    ex = json.loads(out_lines[0])['arms']
    print('example, arm E :', ex['E']['user_text'][:420].replace('\n', ' | '))
    print('example, arm EG:', ex[ARM]['user_text'][:520].replace('\n', ' | '))


if __name__ == '__main__':
    main()
