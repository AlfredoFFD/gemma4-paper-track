"""The reading pattern of analysis/public_runs_address.py in public trajectories outside the competition (EXPLORATORY).

Usage: py -I -X utf8 analysis/public_runs_outside.py            reads the local copies made by fetch_outside_rows.py
       py -I -X utf8 analysis/public_runs_outside.py --viewer   reads the same rows through the dataset viewer,
                                                                in memory, and writes nothing

Nothing here was pre-registered and no model is run. Two public sets of agent trajectories, rows 0 to 799 of each:
  A. SWE-bench/SWE-smith-trajectories, split `tool` (MIT): SWE-agent with function calling, Claude 3.7 Sonnet.
     A READ is a call of the editor tool `str_replace_editor` with command `view` on a file (a view of a directory,
     whose result begins "Here's the files and directories", is not a read). Its range is `view_range` = [start, end].
     The file is `path` without a leading `/testbed/`.
  C. nebius/SWE-rebench-openhands-trajectories, split `train` (CC-BY-4.0): OpenHands 0.54 with function calling,
     Qwen3-Coder-480B-A35B-Instruct. Same tool as source A (`str_replace_editor` with `view` and `view_range`);
     the shell tool is `execute_bash`; the file is `path` without its leading `/workspace/<checkout>/`. This
     source is read through the dataset viewer only.
  D. SWE-Gym/OpenHands-Sampled-Trajectories, split `train.raw` (no license stated on its card): OpenHands with
     function calling; the model is the part of `run_id` before `_maxiter` (GPT-4o in the rows read). Parsed as
     source C. Read through the dataset viewer only.
  B. nebius/SWE-agent-trajectories, split `train` (CC-BY-4.0): classic SWE-agent, Llama-based models.
     The command of a step is the first line of the last fenced block of an `ai` item; the next `user` item is its
     result. A READ is `open <path>` or `open <path> <line>`; an open with a line shows about 100 lines around it.

Rules, the same as in public_runs_address.py with the tool names of each harness:
  FIRST READ   no earlier READ of that file in the trajectory and no earlier shell command that names the file and
               uses a viewer (cat, head, tail, sed, nl, less, more, awk).
  JUST BEFORE  the call or command immediately before the read, with its result.
  ADDRESS      the result just before names the file with a line number: (i) the file's path followed by
               `:<number>:` or `-<number>-`; (ii) a traceback, the path followed by `", line <number>`; (iii) the
               command just before names the file and is grep with `-n`, `cat -n`, `nl` or (source B) `search_file`,
               and its output has lines that begin with a number followed by `:`, `-` or a tab, or (source B) lines
               that begin `Line <number>:`.
  PATH ONLY    not ADDRESS, and the file's path appears in the result or the command just before.
  OTHER        neither.
  RANGED       source A: `view_range` with a start greater than 1. Source B: a line argument greater than 1.
  COVERS       source A: a named line lies inside [start, end] (an end of -1 or none means the end of the file).
               Source B: a named line lies within 50 lines of the line argument.
Intervals: 95% bootstrap over issues (the row's `instance_id`), 2,000 resamples, seed 0.
"""
import argparse
import collections
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from fetch_outside_rows import OUT, SOURCES, rows_of  # noqa: E402
from public_runs_address import NUMBERED, PATHCH, numbering_command, pct, viewed_files  # noqa: E402

ROWS = 800
FENCE = re.compile(r'```(?:\w*)\n(.*?)```', re.S)


def rel(path):
    p = str(path or '').strip().strip('"\'')
    p = re.sub(r'^/workspace/[^/]+/', '', p)
    for pre in ('/testbed/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def names_file(text, f):
    return re.search(r'(?:(?<![' + PATHCH + r'])|(?<=/))' + re.escape(f) + r'(?![A-Za-z0-9_])', text) is not None


def classify(f, cmd, text, search_file=False):
    esc = re.escape(f)
    lines = {int(m.group(1)) for m in re.finditer(r'(?:(?<![' + PATHCH + r'])|(?<=/))' + esc + r'[:\-](\d+)[:\-]', text)}
    lines |= {int(m.group(1)) for m in re.finditer(esc + r'",? line (\d+)', text)}
    if cmd and names_file(cmd, f):
        if numbering_command(cmd):
            lines |= {int(m.group(1)) for m in NUMBERED.finditer(text)}
        if search_file and cmd.startswith('search_file'):
            lines |= {int(m.group(1)) for m in re.finditer(r'^Line (\d+):', text, re.M)}
    if lines:
        return 'ADDRESS', lines
    if names_file(text, f) or (cmd and names_file(cmd, f)):
        return 'PATH ONLY', set()
    return 'OTHER', set()


def source_a(rows, key='messages', shell=('bash',)):
    for row in rows:
        msgs = json.loads(row[key]) if isinstance(row[key], str) else row[key]
        seen = set()
        prev_cmd, prev_text = '', ''
        i = 0
        while i < len(msgs):
            m = msgs[i]
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                fn = (m['tool_calls'][0].get('function') or {})
                try:
                    args = json.loads(fn.get('arguments') or '{}')
                except ValueError:
                    args = {}
                text = ''
                if i + 1 < len(msgs) and msgs[i + 1].get('role') == 'tool':
                    c = msgs[i + 1].get('content')
                    if isinstance(c, list):
                        c = '\n'.join(str(x.get('text', '')) for x in c if isinstance(x, dict))
                    text = str(c or '').replace('\r\n', '\n')
                listing = "Here's the files and directories" in text[:120]
                if fn.get('name') == 'str_replace_editor' and args.get('command') == 'view' and not listing:
                    f = rel(args.get('path'))
                    vr = args.get('view_range')
                    start = end = None
                    if isinstance(vr, list) and len(vr) == 2:
                        try:
                            start, end = int(vr[0]), int(vr[1])
                        except (TypeError, ValueError):
                            start = end = None
                    ranged = start is not None and start > 1
                    cls, lines = classify(f, prev_cmd, prev_text)
                    hi = float('inf') if (end is None or end < 0) else end
                    yield {'issue': row.get('instance_id'), 'model': row.get('model'), 'first': f not in seen, 'cls': cls,
                           'ranged': ranged, 'covers': bool(ranged and any(start <= x <= hi for x in lines)),
                           'minline': min(lines) if lines else None}
                    seen.add(f)
                    prev_cmd = 'str_replace_editor view ' + str(args.get('path'))
                elif fn.get('name') in shell:
                    prev_cmd = str(args.get('command') or '')
                    seen.update(rel(t) for t in viewed_files(prev_cmd))
                else:
                    prev_cmd = str(fn.get('name'))
                prev_text = text
                i += 2
                continue
            i += 1


def source_b(rows):
    for row in rows:
        traj = row['trajectory']
        seen = set()
        prev_cmd, prev_text = '', ''
        for j, item in enumerate(traj):
            if item.get('role') != 'ai':
                continue
            blocks = FENCE.findall(item.get('text') or '')
            if not blocks:
                continue
            cmd = blocks[-1].strip().split('\n')[0]
            text = ''
            if j + 1 < len(traj) and traj[j + 1].get('role') == 'user':
                text = traj[j + 1].get('text') or ''
            mo = re.match(r'open\s+(\S+)(?:\s+(\d+))?\s*$', cmd)
            if mo:
                f = rel(mo.group(1))
                line = int(mo.group(2)) if mo.group(2) else None
                ranged = line is not None and line > 1
                cls, lines = classify(f, prev_cmd, prev_text, search_file=True)
                yield {'issue': row.get('instance_id'), 'model': row.get('model_name'), 'first': f not in seen, 'cls': cls,
                       'ranged': ranged, 'covers': bool(ranged and any(abs(x - line) <= 50 for x in lines)),
                       'minline': min(lines) if lines else None}
                seen.add(f)
            else:
                seen.update(rel(t) for t in viewed_files(cmd))
            prev_cmd, prev_text = cmd, text


def ci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} points [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def report(title, rows, extract, window, note, model=None):
    rows = list(rows)
    recs = list(extract(rows))
    issues = {r.get('instance_id') for r in rows}
    repos = {re.sub(r'-\d+$', '', str(i)).split('.')[0] for i in issues}
    models = collections.Counter(r.get('model') or r.get('model_name') or model for r in rows)
    print(title)
    print(f'   trajectories {len(rows)}, issues {len(issues)}, repositories {len(repos)}; models: '
          + ', '.join(f'{k} x{n}' for k, n in models.most_common()))
    for which, flag in (('first reads', True), ('later reads', False)):
        by = {c: collections.defaultdict(list) for c in ('ADDRESS', 'PATH ONLY', 'OTHER')}
        for r in recs:
            if r['first'] == flag:
                by[r['cls']][r['issue']].append(int(r['ranged']))
        print(f'   {which}:')
        for cls in ('ADDRESS', 'PATH ONLY', 'OTHER'):
            sel = [r for r in recs if r['first'] == flag and r['cls'] == cls]
            extra = ''
            if cls == 'ADDRESS':
                rg = [r for r in sel if r['ranged']]
                extra = f'; of the RANGED, COVERS {pct(sum(r["covers"] for r in rg), len(rg))}'
            print(f'      {cls:<10} RANGED {pct(sum(r["ranged"] for r in sel), len(sel)):<22} by issue {ci(boot_ci(by[cls]))}{extra}')
        if flag:
            print(f'      ADDRESS minus PATH ONLY, by issue: {dci(diff_ci(by["ADDRESS"], by["PATH ONLY"]))}')
            sel = [r for r in recs if r['first'] and r['cls'] == 'ADDRESS']
            near = [r for r in sel if r['minline'] <= window]
            far = [r for r in sel if r['minline'] > window]
            print(f'      ADDRESS by the smallest named line: within the first {window} lines RANGED {pct(sum(r["ranged"] for r in near), len(near))}; '
                  f'past line {window} RANGED {pct(sum(r["ranged"] for r in far), len(far))} ({note})')
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--viewer', action='store_true', help='read the rows through the dataset viewer instead of local copies')
    args = ap.parse_args()
    print('PUBLIC TRAJECTORIES OUTSIDE THE COMPETITION: where a first read of a file starts (EXPLORATORY)')
    print(f'rows 0 to {ROWS - 1} of each source; read ' + ('through the dataset viewer, in memory' if args.viewer else 'from local copies'))
    print()
    titles = ('A. SWE-agent with function calling, Claude 3.7 Sonnet (SWE-bench/SWE-smith-trajectories, split tool)',
              'B. Classic SWE-agent, Llama-based models (nebius/SWE-agent-trajectories, split train)')
    views = ((150, 'a view without a range shows the whole file here; 150 is the cap of the competition harness'),
             (100, 'an open without a line shows lines 1 to 100 here'))
    for (dataset, split, stem), title, extract, (window, note) in zip(SOURCES, titles, (source_a, source_b), views):
        local = OUT / f'{stem}_rows_0_{ROWS - 1}.jsonl'
        if args.viewer:
            rows = rows_of(dataset, split, ROWS)
        elif local.exists():
            rows = (json.loads(line) for line in io.open(local, encoding='utf-8'))
        else:
            print(title)
            print(f'   local copy not found ({local.name}); run analysis/fetch_outside_rows.py, or pass --viewer')
            print()
            continue
        report(title, rows, extract, window, note)
    if args.viewer:
        report('C. OpenHands with function calling, Qwen3-Coder-480B (nebius/SWE-rebench-openhands-trajectories, split train)',
               rows_of('nebius/SWE-rebench-openhands-trajectories', 'train', ROWS),
               lambda rows: source_a(rows, key='trajectory', shell=('execute_bash',)), 150,
               'a view without a range shows the whole file here; 150 is the cap of the competition harness',
               model='Qwen3-Coder-480B-A35B-Instruct')
        gym = []
        for row in rows_of('SWE-Gym/OpenHands-Sampled-Trajectories', 'train.raw', ROWS):
            row['model'] = str(row.get('run_id') or '').split('_maxiter')[0]
            gym.append(row)
        report('D. OpenHands with function calling, models by run id (SWE-Gym/OpenHands-Sampled-Trajectories, split train.raw)',
               gym, lambda rows: source_a(rows, key='messages', shell=('execute_bash',)), 150,
               'a view without a range shows the whole file here; 150 is the cap of the competition harness')
    else:
        print('C. OpenHands with function calling, Qwen3-Coder-480B: read through the dataset viewer only (pass --viewer)')
        print('D. OpenHands with function calling, SWE-Gym sampled trajectories: read through the dataset viewer only (pass --viewer)')


if __name__ == '__main__':
    main()
