"""Records for pre-registration 28 (the key first): arm KF on the paused steps of 25.

KF is record KE of analysis/fork_states_p/states.jsonl (built by analysis/make_states_25.py) with one change: in the
last tool result, the key `code_graph` moves from the last place (after the file's content) to the first place, before
`status`. The text is KE's recorded text with the substring `, "code_graph": <value>` removed from before the closing
brace and `"code_graph": <value>, ` inserted after the opening brace; the value is byte for byte KE's. Everything else in
the record is KE's, except `arm` ("KF") and `fork` ("<03's fork>:KF"). The runner replays KF as it stands (runner arm A).

Checks (each asserted): the parsed KF object equals the parsed KE object as a dict; its keys are `code_graph` followed
by KE's other keys in order; no other step of the history differs from KE's; one KF record per KE record.

Usage: py -I -X utf8 analysis/make_states_28.py   (writes analysis/fork_states_p/states_28.jsonl, not tracked, and
prints its md5)
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'fork_states_p' / 'states.jsonl'
OUT = HERE / 'fork_states_p' / 'states_28.jsonl'
KEY = '"code_graph": '


def main():
    out = []
    n = 0
    for line in open(SRC, encoding='utf-8'):
        r = json.loads(line)
        if r['arm'] != 'KE':
            continue
        last = r['steps'][-1]
        text = last['observation']['content']
        i = text.rfind(', ' + KEY)
        assert i > 0 and text.endswith('}'), r['fork']
        value = text[i + 2 + len(KEY):-1]
        kf_text = '{' + KEY + value + ', ' + text[1:i] + '}'
        a, b = json.loads(text), json.loads(kf_text)
        assert a == b, r['fork']
        assert list(b) == ['code_graph'] + [k for k in a if k != 'code_graph'], (r['fork'], list(b))
        assert json.dumps(b['code_graph']) == json.dumps(a['code_graph'])
        k = dict(r)
        k['steps'] = list(r['steps'][:-1]) + [dict(last, observation=dict(last['observation'], content=kf_text))]
        assert k['steps'][:-1] == r['steps'][:-1]
        k['arm'] = 'KF'
        k['fork'] = r['fork'].rsplit(':', 1)[0] + ':KF'
        out.append(json.dumps(k) + '\n')
        n += 1
    OUT.write_text(''.join(out), encoding='utf-8', newline='\n')
    print(f'{n} KF records -> {OUT.relative_to(HERE.parent)}; md5 {hashlib.md5(OUT.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
