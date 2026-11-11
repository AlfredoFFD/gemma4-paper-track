"""States file for pre-registration 15 (the agent's own search, with and without its line numbers).

Usage: py -I -X utf8 analysis/make_states_s.py
Reads the recorded base runs (data/graphloc/out/*/e2e/results/base/w*/traces/trace_*.json) and writes
analysis/fork_states_s/states.jsonl (not tracked: it holds other teams' runs).

Candidate step: a step of a recorded base run (the starter agent, Gemma-4-31B) such that
- its one call is `run_command`, the command line runs a search program (a piece of the line, cut at | ; & ( ) ` and
  newlines, begins with grep, egrep, fgrep, rg, ag or ack, with `git grep`, or with xargs followed by one of them),
  and the result has status ok;
- the output has at least one hit line in a repository file that the agent has not opened earlier in the run. A hit
  line is `path:line:text` (a path without a blank or a colon), or `line:text` when the command names exactly one
  repository file. A context line is `path-line-text` for a path that has a hit line in the same output, or
  `line-text`. A repository file is a Python file of the task's snapshot (the file list fork_states.py uses); a path
  under the sandbox's working directory is read as the path inside the repository. Opened is what fork_states.py
  counts: a `read_file` that returned content, or a cat, sed, head, tail, grep, rg, awk, less or more command on the
  file that printed something;
- the step comes before any edit_file, submit_patch, write_file onto a repository file, parallel call or compaction,
  and the next model call was logged and not compacted (the conditions of fork_states.py; its cap on the prompt size
  is not applied);
- the output has at most 40 hit lines and fewer than 5,000 characters (the harness cuts an output at 5,000).
The first two candidate steps of a run are kept. If more than 100 remain, the 100 with the smallest sha1 of
"<task>|<run>|<step index>" are the states (step index: the step's position among the run's agent steps, from 0).

Arms. The runner replays a state's history and can add a message after it; it cannot alter the last result. So each
(state, arm) is written as its own record with its own history:
  S    the history as recorded (the runner's arm A: nothing added);
  S0   the same history, with the line number removed from every hit line and context line of the last result
       (`path:123:text` -> `path:text`, `123:text` -> `text`, `path-123-text` -> `path-text`, `123-text` -> `text`);
       same lines, same order, same text (the runner's arm A on that history);
  S0N  the history of S0, then a note delivered as the notes of the earlier experiments are (a user message, the
       channel of arm E): `Line numbers of the matches above:` and one line per hit, `path:line`, in the order of
       the result (for a `line:text` hit, the path is the file as the command wrote it).
The three records of a state differ only in `fork`, `arm`, `arms` and the last result.

Other modules import from this one: repo_path, search_segments, asks_line_numbers.
"""
import collections
import copy
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_address as P  # noqa: E402
from fork_states import COMPACTION_RATIO, MAX_STDOUT_CHARS, load_tasks, norm_path, parse_obs, shows_content, valid_call  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402

ROOT = HERE.parent
OUT = HERE / 'fork_states_s' / 'states.jsonl'
ARMS = ('S', 'S0', 'S0N')
NOTE_ARM = 'S0N'
NOTE_HEAD = 'Line numbers of the matches above:'
MAX_HITS = 40
MAX_PER_RUN = 2
MAX_STATES = 100
SEARCH_PROGRAMS = ('grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack')
CUT = re.compile(r'[|;&\n()`]+')
ONE_FILE_LINE = re.compile(r'^(\d+)([:\-])(.*)$', re.S)       # line:text (hit) or line-text (context)
HIT_LINE = re.compile(r'^([^\s:]+):(\d+):(.*)$', re.S)         # path:line:text
CONTEXT_REST = re.compile(r'^(\d+)-(.*)$', re.S)               # what follows `path-` on a context line


def repo_path(p):
    """A path as a command, a tool call or a search output wrote it, as a path inside the repository.

    fork_states.norm_path removes /workspace/, workspace/ and ./ from the front; an absolute path under the sandbox's
    working directory (/tmp/<sandbox>/workspace/...) loses that front as well.
    """
    p = norm_path(p)
    if isinstance(p, str) and p.startswith('/') and '/workspace/' in p:
        p = norm_path(p.split('/workspace/', 1)[1])
    return p


def search_segments(cmd):
    """The pieces of a command line that run a search program, each as its words from the program's name on."""
    out = []
    for seg in CUT.split(str(cmd)):
        toks = seg.split()
        if not toks:
            continue
        if toks[0] == 'git' and len(toks) > 1 and toks[1] == 'grep':
            out.append(toks[1:])
        elif toks[0] == 'xargs':
            rest = [t for t in toks[1:] if not t.startswith('-')]
            if rest and rest[0] in SEARCH_PROGRAMS:
                out.append(toks[toks.index(rest[0]):])
        elif toks[0] in SEARCH_PROGRAMS:
            out.append(toks)
    return out


def asks_line_numbers(cmd):
    """True if a search piece of the command line asks for line numbers: a short option holding n, or --line-number."""
    for toks in search_segments(cmd):
        if '--line-number' in toks or any('n' in t for t in toks[1:] if t.startswith('-') and not t.startswith('--')):
            return True
    return False


def command_words(cmd):
    try:
        return shlex.split(str(cmd))
    except ValueError:
        return str(cmd).split()


def named_files(cmd, files):
    """(repository path, the word as written) for each repository file the command line names, first mention each."""
    out, seen = [], set()
    for w in command_words(cmd):
        p = repo_path(w)
        if p in files and p not in seen:
            seen.add(p)
            out.append((p, w))
    return out


def parse_output(stdout, one_file):
    """The lines of a search output and, for each, None or (kind, path as printed, digits, text).

    kind: 'hit' or 'context'; the path is None for the forms without a path (`line:text`, `line-text`), which belong to
    the one file the command names; when the command does not name exactly one file their kind is 'unplaced'.
    """
    lines = stdout.split('\n')
    kinds = [None] * len(lines)
    for j, line in enumerate(lines):
        m = ONE_FILE_LINE.match(line)
        if m:
            kind = 'unplaced' if one_file is None else ('hit' if m.group(2) == ':' else 'context')
            kinds[j] = (kind, None, m.group(1), m.group(3))
            continue
        m = HIT_LINE.match(line)
        if m:
            kinds[j] = ('hit', m.group(1), m.group(2), m.group(3))
    paths = sorted({k[1] for k in kinds if k and k[1]}, key=len, reverse=True)
    for j, line in enumerate(lines):
        if kinds[j] is None:
            for p in paths:
                m = CONTEXT_REST.match(line[len(p) + 1:]) if line.startswith(p + '-') else None
                if m:
                    kinds[j] = ('context', p, m.group(1), m.group(2))
                    break
    return lines, kinds


def without_number(line, kind):
    """A hit line or a context line with its line number and one separator removed; any other line as it is."""
    if kind is None or kind[0] == 'unplaced':
        return line
    what, path, _digits, text = kind
    if path is None:
        return text
    return path + (':' if what == 'hit' else '-') + text


def with_number(stripped, kind):
    """The inverse of without_number (used to check that nothing but the number was removed)."""
    if kind is None or kind[0] == 'unplaced':
        return stripped
    what, path, digits, text = kind
    sep = ':' if what == 'hit' else '-'
    return f'{digits}{sep}{text}' if path is None else f'{path}{sep}{digits}{sep}{text}'


def dumps_like(original, obj):
    """obj as JSON text in the style of the recorded result (the harness wrote it with json.dumps; which setting of
    ensure_ascii reproduces the recorded bytes is found from the recorded text itself)."""
    for ascii_only in (True, False):
        if json.dumps(json.loads(original), ensure_ascii=ascii_only) == original:
            return json.dumps(obj, ensure_ascii=ascii_only)
    raise AssertionError('json.dumps does not reproduce the recorded result byte for byte')


def scan_run(r, task, tally):
    """The candidate steps of one run, in order (all of them; the caller keeps the first MAX_PER_RUN)."""
    d = load(r['path'])
    files = set(N.snapshot_files(r['task']))
    steps = d['steps']
    agent = [s for s in steps if s['source'] == 'agent']
    out, opened, prev_prompt = [], set(), None
    earlier = []   # (call, result text, None) of every earlier step with a call, the shape the census's classifier takes
    for i, s in enumerate(agent):
        pt = (s.get('metrics') or {}).get('prompt_tokens')
        if prev_prompt and pt and pt < COMPACTION_RATIO * prev_prompt:
            break
        prev_prompt = pt or prev_prompt
        tcs = s.get('tool_calls') or []
        if len(tcs) > 1:
            break
        if any(tc['function_name'] in ('edit_file', 'submit_patch')
               or (tc['function_name'] == 'write_file' and repo_path(tc['arguments'].get('filepath')) in files) for tc in tcs):
            break
        c = candidate(r, task, files, steps, agent, i, opened, earlier, tally) if tcs else None
        if c:
            out.append(c)
        sc = shows_content(s)
        if sc and sc[0]:
            opened.add(repo_path(N._norm(sc[0])))
        if tcs:
            earlier.append((tcs[0], P.result_of(s)[0], None))
    return out


def candidate(r, task, files, steps, agent, i, opened, earlier, tally):
    s = agent[i]
    tc = s['tool_calls'][0]
    if tc['function_name'] != 'run_command':
        return None
    cmd = str(tc['arguments'].get('command', ''))
    o = parse_obs(s)
    if not search_segments(cmd) or not isinstance(o, dict) or o.get('status') != 'ok' or not o.get('stdout'):
        return None
    tally['search steps with output, before any edit or compaction'] += 1
    stdout = o['stdout']
    named = named_files(cmd, files)
    one_file, one_word = named[0] if len(named) == 1 else (None, None)
    lines, kinds = parse_output(stdout, one_file)
    hits = [k for k in kinds if k and k[0] == 'hit']
    if not hits:
        return None
    tally['of them, with a numbered hit line'] += 1
    scored = collections.OrderedDict()      # repository file not opened earlier -> its hit lines, in order
    for k in hits:
        p = one_file if k[1] is None else repo_path(k[1])
        if p in files and p not in opened:
            scored.setdefault(p, []).append(int(k[2]))
    nxt = agent[i + 1] if i + 1 < len(agent) else None
    cur_pt = (s.get('metrics') or {}).get('prompt_tokens')
    nxt_pt = (nxt.get('metrics') or {}).get('prompt_tokens') if nxt else None
    why = None
    if not scored:
        why = 'no hit line in a repository file not opened earlier'
    elif len(stdout) >= MAX_STDOUT_CHARS:
        why = 'output cut off'
    elif len(hits) > MAX_HITS:
        why = f'more than {MAX_HITS} hit lines'
    elif any(k and k[0] == 'unplaced' for k in kinds):
        why = 'numbered lines that belong to no one file'
    elif nxt is None or not nxt_pt:
        why = 'no logged next call'
    elif cur_pt and nxt_pt < COMPACTION_RATIO * cur_pt:
        why = 'compaction at the next call'
    if why:
        tally['  not a candidate: ' + why] += 1
        return None
    tally['candidate steps, any number per run'] += 1

    stripped = '\n'.join(without_number(line, k) for line, k in zip(lines, kinds))
    note = NOTE_HEAD + ''.join(f'\n{one_word if k[1] is None else k[1]}:{k[2]}' for k in hits)
    history = steps[:steps.index(s) + 1]
    content = s['observation']['content']
    o0 = dict(o, stdout=stripped)
    history0 = copy.deepcopy(history)
    history0[-1]['observation']['content'] = dumps_like(content, o0)

    # what the census's classifier (public_runs_address.classify) says about each scored file, before and after
    text_s, text_s0 = P.result_of(history[-1])[0], P.result_of(history0[-1])[0]
    census = {f: (P.classify(f, (tc, text_s, None))[0], P.classify(f, (tc, text_s0, None))[0]) for f in scored}
    census_lines = {f: sorted(P.classify(f, (tc, text_s, None))[2]) for f in scored}
    seen_before = sorted(f for f in scored if any(P.classify(f, e)[0] == 'ADDRESS' for e in earlier))

    lengths = {f: (len(t.splitlines()) if (t := N.file_text(r['task'], f)) is not None else None) for f in scored}
    in_snapshot = same = 0
    for k in hits:
        p = one_file if k[1] is None else repo_path(k[1])
        src = N.file_text(r['task'], p) if p in files else None
        if src is not None:
            src_lines = src.split('\n')
            in_snapshot += 1
            n = int(k[2])
            same += int(1 <= n <= len(src_lines) and src_lines[n - 1].rstrip('\r') == k[3].rstrip('\r'))
    next_call = (nxt.get('tool_calls') or [None])[0]
    key = f"{r['task']}|{r['run']}|{i}"
    base = {
        'task': r['task'], 'run': r['run'], 'state_id': key, 'sha1': hashlib.sha1(key.encode()).hexdigest(),
        'arm_source': r['arm'], 'trace': r['path'].relative_to(ROOT).as_posix(),
        'repo': task['repo'], 'base_commit': task['base_commit'], 'node': None,
        'fork_agent_step': i, 'fork_step_id': s['step_id'],
        'prompt_tokens_at_fork_call': cur_pt, 'prompt_tokens_next_call_logged': nxt_pt,
        'command': cmd, 'one_file': one_file, 'asks_line_numbers': asks_line_numbers(cmd),
        'hit_files': dict(scored), 'file_lines': lengths, 'opened_files': sorted(opened),
        'n_hit_lines': len(hits), 'n_context_lines': sum(1 for k in kinds if k and k[0] == 'context'),
        'n_other_lines': sum(1 for line, k in zip(lines, kinds) if k is None and line not in ('', '--')),
        'hit_lines_in_snapshot': in_snapshot, 'hit_lines_equal_snapshot': same,
        'census_class': census, 'census_lines': census_lines, 'files_numbered_earlier': seen_before,
        'note': note,
        'observed_next_call': next_call, 'observed_next_call_valid': valid_call(next_call) if next_call else False,
    }
    return {'base': base, 'history': history, 'history0': history0, 'lines': lines, 'kinds': kinds, 'stripped': stripped,
            'content': content}


def records(c):
    """The three records of a state, with the checks that the arms differ where they should and nowhere else."""
    b, out = c['base'], []
    for arm in ARMS:
        rec = dict(b, fork=f"{b['fork_agent_step']}:{arm}", arm=arm,
                   arms={NOTE_ARM: {'user_text': b['note']}} if arm == NOTE_ARM else {},
                   steps=c['history'] if arm == 'S' else c['history0'])
        out.append(rec)
    s, s0, s0n = out
    assert s['steps'][:-1] == s0['steps'][:-1] and s0['steps'] == s0n['steps']
    last, last0 = s['steps'][-1], s0['steps'][-1]
    assert {k: v for k, v in last.items() if k != 'observation'} == {k: v for k, v in last0.items() if k != 'observation'}
    assert {k: v for k, v in last['observation'].items() if k != 'content'} == \
        {k: v for k, v in last0['observation'].items() if k != 'content'}
    o, o0 = json.loads(last['observation']['content']), json.loads(last0['observation']['content'])
    assert last['observation']['content'] == c['content'] and list(o) == list(o0)
    assert {k: v for k, v in o.items() if k != 'stdout'} == {k: v for k, v in o0.items() if k != 'stdout'}
    lines0 = o0['stdout'].split('\n')
    assert len(lines0) == len(c['lines'])
    for line, line0, k in zip(c['lines'], lines0, c['kinds']):
        assert with_number(line0, k) == line                      # putting the number back gives the recorded line
        assert (line0 == line) == (k is None)                     # every hit and context line changed, no other line
    return out


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def counts(cs):
    return (f"{len(cs)} steps in {len({(c['base']['task'], c['base']['run']) for c in cs})} runs of "
            f"{len({c['base']['task'] for c in cs})} tasks")


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = load_tasks()
    tally = collections.Counter()
    found, runs = [], 0
    for r in iter_runs(arm='base'):
        runs += 1
        found.append(scan_run(r, tasks[r['task']], tally))
    cands = [c for per_run in found for c in per_run[:MAX_PER_RUN]]
    print(f'recorded base runs read: {runs}')
    for k in sorted(tally, key=lambda k: (k.startswith('candidate'), k.startswith('  not'))):
        print(f'  {tally[k]:4d}  {k}')
    print(f'candidate steps (at most the first {MAX_PER_RUN} of a run): {counts(cands)}')
    kept = sorted(cands, key=lambda c: c['base']['sha1'])[:MAX_STATES]
    print(f'states (at most {MAX_STATES}, smallest sha1 of "<task>|<run>|<step index>" first): {counts(kept)}')

    out_lines, t = [], collections.Counter()
    for c in kept:
        b = c['base']
        for rec in records(c):
            out_lines.append(json.dumps(rec))
        t['hit lines'] += b['n_hit_lines']
        t['context lines'] += b['n_context_lines']
        t['other lines'] += b['n_other_lines']
        t['one file named (line:text)'] += b['one_file'] is not None
        t['more than one scored file'] += len(b['hit_files']) > 1
        t['scored files'] += len(b['hit_files'])
        t['census: ADDRESS under S'] += sum(v[0] == 'ADDRESS' for v in b['census_class'].values())
        t['census: ADDRESS under S0'] += sum(v[1] == 'ADDRESS' for v in b['census_class'].values())
        t['census: same hit lines'] += sum(b['census_lines'][f] == sorted(set(b['hit_files'][f])) for f in b['hit_files'])
        t['in snapshot'] += b['hit_lines_in_snapshot']
        t['equal snapshot'] += b['hit_lines_equal_snapshot']
        t['a scored file numbered by an earlier result'] += bool(b['files_numbered_earlier'])
        t['first hits all past line 150'] += all(min(v) > 150 for v in b['hit_files'].values())
        t['asks for line numbers'] += b['asks_line_numbers']
        t['recorded next call usable'] += b['observed_next_call_valid']
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(''.join(l + '\n' for l in out_lines), encoding='utf-8', newline='\n')
    print(f'wrote {OUT.relative_to(ROOT).as_posix()}: {len(out_lines)} records ({len(kept)} states x {len(ARMS)} arms), '
          f'md5 {md5(OUT)}; every state passed the checks (S is the recorded history; S0 differs from it in the '
          f'last result only, by the removed numbers; S0N is S0 with the note)')
    print(f'in the kept results: {t["hit lines"]} hit lines, {t["context lines"]} context lines, {t["other lines"]} lines '
          f'that are neither (separators and blank lines apart); {t["asks for line numbers"]} of {len(kept)} commands ask '
          f'for line numbers')
    print(f'states whose command names one file (hits written line:text): {t["one file named (line:text)"]}; states with '
          f'more than one scored file: {t["more than one scored file"]}; scored files in all: {t["scored files"]}')
    print(f'hit lines in a repository file: {t["in snapshot"]}, of which equal to that line of the snapshot: '
          f'{t["equal snapshot"]}')
    print(f'the census\'s classifier on the scored files: ADDRESS under S {t["census: ADDRESS under S"]} of '
          f'{t["scored files"]}, with the same line numbers {t["census: same hit lines"]}; ADDRESS under S0 '
          f'{t["census: ADDRESS under S0"]}')
    print(f'states in which an earlier result had already numbered a line of a scored file: '
          f'{t["a scored file numbered by an earlier result"]}; states whose scored files all have their first hit past '
          f'line 150: {t["first hits all past line 150"]}; recorded next call usable: '
          f'{t["recorded next call usable"]} of {len(kept)}')
    pts = sorted(c['base']['prompt_tokens_next_call_logged'] for c in kept)
    print(f'logged prompt tokens at the next call: median {pts[len(pts) // 2]}, max {pts[-1]}')
    ex = next((c for c in kept if c['base']['one_file'] is None), kept[0])
    j = next(j for j, k in enumerate(ex['kinds']) if k and k[0] == 'hit')
    print(f'example ({ex["base"]["state_id"]}), one hit line of the last result:')
    print('  S  :', ex['lines'][j][:150])
    print('  S0 :', ex['stripped'].split('\n')[j][:150])
    print('  S0N: the S0 line, and in the note:', ex['base']['note'].split('\n')[1 + sum(1 for k in ex['kinds'][:j] if k and k[0] == 'hit')])


if __name__ == '__main__':
    main()
