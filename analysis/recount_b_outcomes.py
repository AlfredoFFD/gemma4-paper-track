"""Independent recount, part 2: the outcomes of pre-registrations 02 and 03 (runs v5, v6, v8).

recount_b.py stops after the interface failures and the complete states. This file scores the touches and
recomputes the per-arm rates and the contrasts B1-B4. The touch scorer below was written from the text of
pre-registration 02 ("Outcomes") only. It does not import fork_states.touches, analyze_forks or analyze_b.
From recount_b.py it reuses the loaders, the failure classification and the harness's argument rules.

Rules as implemented (each is a reading of the pre-registration; where the text leaves room, the choice is named):
  read_file   shows lines start..end, cut to 150 lines and to 10,000 characters from the start line (no range = from
              line 1). Touch = the shown lines overlap the node's span.
  edit_file, write_file of the node's file: touch.
  run_command only content-showing commands count: cat, sed -n 'a,bp', head, tail, grep/rg, awk, less, more.
              Output is cut to 5,000 characters. Touch = the command covers the node's file and either its shown
              lines overlap the span or the command text names the node (its last name component, as a whole word).
              grep is simulated on the repository snapshot (pattern, -i -w -v -F -E -n -A -B -C, -r, --include).
              Choices: in a recursive grep each file is held to the cap on its own; a later `| head -N` or
              `| tail -N` limits the lines; `| grep` filters them; `| wc` shows nothing; a heredoc `cat <<EOF > f`
              is not a view.
  graph tools are never a touch.

Usage:  py -I analysis/recount_b_outcomes.py      Output: analysis/results/recount_b_outcomes.txt
"""
import collections
import fnmatch
import json
import os
import random
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recount_b as R  # noqa: E402  (loaders, failure classes, argument rules; no scoring)

ROOT = R.ROOT
ARMS = R.ARMS
READ_LINES, READ_CHARS, SHELL_CHARS = 150, 10000, 5000
GREPS = ('grep', 'egrep', 'fgrep', 'rg')
VIEWERS = ('cat', 'sed', 'head', 'tail', 'awk', 'less', 'more') + GREPS
_TEXT = {}
# Sensitivity switch: RECOUNT_RECURSIVE=0 stops a recursive grep over a directory from counting as a view of
# the files under it (the pre-registered text says 'a shell view of that file').
RECURSIVE = os.environ.get('RECOUNT_RECURSIVE', '1') != '0'
SUFFIX = '' if RECURSIVE else '_named_file_only'


MISSING = set()


def file_lines(task, path):
    """Snapshot text of a file. The cache is flat: './a/b.py' is stored as '.__a__b.py.txt'."""
    key = (task, path)
    if key not in _TEXT:
        _TEXT[key] = None
        rel = path.replace(chr(92), '/')
        while rel.startswith('./'):
            rel = rel[2:]
        rel = rel.lstrip('/')
        cdir = os.path.join(ROOT, 'data', 'cache', 'snapshot_text', task)
        if not os.path.exists(os.path.join(cdir, '.complete')):
            raise SystemExit('snapshot cache missing or incomplete for ' + task)
        for cand in ('./' + rel, rel):
            p = os.path.join(cdir, cand.replace('/', '__') + '.txt')
            if os.path.isfile(p):
                with open(p, encoding='utf-8', errors='replace') as f:
                    _TEXT[key] = f.read().split(chr(10))
                break
        else:
            MISSING.add(key)
    return _TEXT[key]


def cap_chars(lines_shown, text, limit, extra=0):
    """Keep the leading lines whose first character falls inside the character limit."""
    if text is None:
        return lines_shown
    out, used = [], 0
    for ln in lines_shown:
        if used >= limit:
            break
        out.append(ln)
        used += (len(text[ln - 1]) if 0 < ln <= len(text) else 0) + 1 + extra
    return out


def norm(path):
    try:
        return R.resolve_workspace_path(path, allow_root=True)
    except Exception:  # noqa: BLE001
        return None


def span_end(span):
    return span['end'] if span.get('end') is not None else span['start']


def read_shown(task, args):
    path = norm(args.get('filepath'))
    start = R.coerce_optional_int(args.get('start_line')) or 1
    end = R.coerce_optional_int(args.get('end_line'))
    start = max(start, 1)
    text = file_lines(task, path) if path else None
    n = len(text) if text is not None else 10 ** 9
    last = min(n, start + READ_LINES - 1, end if end is not None else 10 ** 9)
    return path, cap_chars(list(range(start, last + 1)), text, READ_CHARS)


# ------------------------------------------------------------------ shell

def split_cmds(cmd):
    """[[stage, ...], ...]: commands separated by ; && || newline, stages by |. Quotes respected."""
    parts, cur, stages, q, i = [], '', [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur += c
            if c == '\\' and q == '"' and i + 1 < len(cmd):
                cur += cmd[i + 1]
                i += 1
            elif c == q:
                q = None
        elif c in '\'"':
            q = c
            cur += c
        elif cmd.startswith('&&', i) or cmd.startswith('||', i):
            stages.append(cur)
            parts.append(stages)
            cur, stages = '', []
            i += 1
        elif c in ';\n':
            stages.append(cur)
            parts.append(stages)
            cur, stages = '', []
        elif c == '|':
            stages.append(cur)
            cur = ''
        else:
            cur += c
        i += 1
    stages.append(cur)
    parts.append(stages)
    return [[s.strip() for s in st if s.strip()] for st in parts if any(s.strip() for s in st)]


def toks(stage):
    try:
        return shlex.split(stage)
    except ValueError:
        return stage.split()


def covers(target, path, recursive, includes):
    t = '' if target in ('.', './') else norm(target.rstrip('/'))
    if t is None:
        return False
    if any(ch in t for ch in '*?['):
        return fnmatch.fnmatch(path, t)
    if t == path:
        return True
    if recursive and RECURSIVE and (t == '' or path.startswith(t + '/')):
        return not includes or any(fnmatch.fnmatch(path.rsplit('/', 1)[-1], g) for g in includes)
    return False


def grep_regex(pat, mode, icase, word):
    if mode == 'F':
        rx = re.escape(pat)
    elif mode == 'E':
        rx = pat
    else:  # basic: \| \( \) \{ \} \+ \? are operators, the bare characters are literal
        rx, i = '', 0
        while i < len(pat):
            c = pat[i]
            if c == '\\' and i + 1 < len(pat):
                d = pat[i + 1]
                rx += d if d in '|(){}+?' else '\\' + d
                i += 2
                continue
            rx += '\\' + c if c in '|(){}+?' else c
            i += 1
    if word:
        rx = r'\b(?:' + rx + r')\b'
    try:
        return re.compile(rx, re.I if icase else 0)
    except re.error:
        return re.compile(re.escape(pat), re.I if icase else 0)


def parse_grep(t):
    name = t[0].rsplit('/', 1)[-1]
    o = {'mode': 'B', 'i': False, 'w': False, 'v': False, 'r': name == 'rg', 'A': 0, 'B': 0, 'quiet': False,
         'pats': [], 'inc': [], 'targets': []}
    if name in ('egrep', 'rg'):
        o['mode'] = 'E'
    if name == 'fgrep':
        o['mode'] = 'F'
    i, pos = 1, []
    while i < len(t):
        a = t[i]
        if a == '--':
            pos += t[i + 1:]
            break
        if a.startswith('--'):
            k, _, v = a[2:].partition('=')
            if k == 'include':
                if v:
                    o['inc'].append(v)
                elif i + 1 < len(t):
                    o['inc'].append(t[i + 1])
                    i += 1
            elif k in ('recursive', 'dereference-recursive'):
                o['r'] = True
            elif k == 'ignore-case':
                o['i'] = True
            elif k in ('files-with-matches', 'files-without-match', 'count', 'quiet'):
                o['quiet'] = True
            elif k in ('extended-regexp', 'perl-regexp'):
                o['mode'] = 'E'
            elif k == 'fixed-strings':
                o['mode'] = 'F'
            elif k in ('exclude', 'exclude-dir') and not v:
                i += 1
        elif a.startswith('-') and len(a) > 1:
            j = 1
            while j < len(a):
                f = a[j]
                if f in 'ABCem':
                    v = a[j + 1:]
                    if not v:
                        v = t[i + 1] if i + 1 < len(t) else '0'
                        i += 1
                    if f == 'e':
                        o['pats'].append(v)
                    elif f in 'ABC' and v.isdigit():
                        if f in 'AC':
                            o['A'] = int(v)
                        if f in 'BC':
                            o['B'] = int(v)
                    break
                if f in 'rR':
                    o['r'] = True
                elif f == 'i':
                    o['i'] = True
                elif f == 'w':
                    o['w'] = True
                elif f == 'v':
                    o['v'] = True
                elif f in 'EP':
                    o['mode'] = 'E'
                elif f == 'F':
                    o['mode'] = 'F'
                elif f in 'lLcq':
                    o['quiet'] = True
                elif f.isdigit():  # -5 = -C 5
                    o['A'] = o['B'] = int(a[j:]) if a[j:].isdigit() else 0
                    break
                j += 1
        else:
            pos.append(a)
        i += 1
    if not o['pats'] and pos:
        o['pats'].append(pos.pop(0))
    o['targets'] = pos or (['.'] if o['r'] else [])
    return o


def grep_lines(o, text):
    rxs = [grep_regex(p, o['mode'], o['i'], o['w']) for p in o['pats']]
    hit = [k + 1 for k, ln in enumerate(text) if any(r.search(ln) for r in rxs) != o['v']]
    out = set()
    for h in hit:
        out.update(range(max(1, h - o['B']), min(len(text), h + o['A']) + 1))
    return sorted(out)


def first_stage(task, t, path):
    """Lines of `path` the first stage of a pipeline shows (uncapped), or None if it does not view the file."""
    if not t:
        return None
    name = t[0].rsplit('/', 1)[-1]
    if name not in VIEWERS:
        return None
    text = file_lines(task, path)
    n = len(text) if text is not None else 10 ** 6
    every = list(range(1, n + 1))
    args = t[1:]
    if name in GREPS:
        o = parse_grep(t)
        if not any(covers(x, path, o['r'], o['inc']) for x in o['targets']):
            return None
        if o['quiet'] or text is None or not o['pats']:
            return []
        return grep_lines(o, text)
    files = [a for a in args if not a.startswith('-')]
    if name == 'cat':
        if any(a.startswith('<<') for a in args) or any(a.startswith('>') for a in args):
            return None
        return every if any(covers(f, path, False, ()) for f in files) else None
    if name in ('less', 'more'):
        return every if any(covers(f, path, False, ()) for f in files) else None
    if name in ('head', 'tail'):
        k, fs, i = '10', [], 0
        while i < len(args):
            a = args[i]
            m = re.fullmatch(r'-n?(\+?\d+)', a) or re.fullmatch(r'--lines=(\+?\d+)', a)
            if a in ('-n', '--lines') and i + 1 < len(args):
                k = args[i + 1]
                i += 1
            elif m:
                k = m.group(1)
            elif not a.startswith('-'):
                fs.append(a)
            i += 1
        if not any(covers(f, path, False, ()) for f in fs):
            return None
        plus = k.startswith('+')
        k = int(k.lstrip('+')) if k.lstrip('+').isdigit() else 10
        if name == 'head':
            return every[:k]
        if plus:
            return every[max(k - 1, 0):]
        return every[-k:] if k else []
    if name == 'sed':
        if not any(covers(f, path, False, ()) for f in (files[1:] or files)):
            return None
        if any(a.startswith('-i') or a == '--in-place' for a in args):
            return every  # an in-place edit of the file
        quiet = any(a == '--quiet' or (a.startswith('-') and not a.startswith('--') and 'n' in a) for a in args)
        script = files[0] if files else ''
        if not quiet:
            return every
        out = set()
        for m in re.finditer(r'(\d+)(?:,(\d+|\$))?p', script):
            a = int(m.group(1))
            b = n if m.group(2) == '$' else int(m.group(2)) if m.group(2) else a
            out.update(range(a, min(b, n) + 1))
        return sorted(out)
    if name == 'awk':
        if not any(covers(f, path, False, ()) for f in files[1:]):
            return None
        m = re.search(r'NR\s*>=\s*(\d+)\s*&&\s*NR\s*<=\s*(\d+)', ' '.join(args))
        return list(range(int(m.group(1)), min(int(m.group(2)), n) + 1)) if m else every
    return None


def later_stage(task, t, path, lines):
    name = t[0].rsplit('/', 1)[-1] if t else ''
    if name in ('head', 'tail'):
        m = re.search(r'-n?\s*(\d+)', ' '.join(t[1:]))
        k = int(m.group(1)) if m else 10
        if name == 'head':
            return lines[:k]
        return lines[-k:] if k else []
    if name in GREPS:
        o = parse_grep(t)
        text = file_lines(task, path)
        if text is None or not o['pats'] or o['quiet']:
            return []
        keep = set(grep_lines(o, text))
        return [x for x in lines if x in keep]
    if name in ('wc', 'md5sum', 'sha256sum'):
        return []
    return lines


def shell_touch(task, cmd, span, short):
    path = span['path']
    covered, shown = False, []
    for stages in split_cmds(cmd):
        t0 = toks(stages[0])
        lines = first_stage(task, t0, path)
        if lines is None:
            continue
        covered = True
        for st in stages[1:]:
            lines = later_stage(task, toks(st), path, lines)
        extra = 8 if t0[0].rsplit('/', 1)[-1] in GREPS else 0  # "path:NN:" style prefixes, roughly
        shown += cap_chars(lines, file_lines(task, path), SHELL_CHARS, extra)
    if not covered:
        return False
    if any(span['start'] <= ln <= span_end(span) for ln in shown):
        return True
    return bool(short and re.search(r'(?<![A-Za-z0-9_])' + re.escape(short) + r'(?![A-Za-z0-9_])', cmd))


def touch(task, call, span, node):
    if not span:
        return False
    name = call['function_name']
    if name not in ('read_file', 'edit_file', 'write_file', 'run_command'):
        return False
    args = R.effective_args(name, call.get('arguments') or {})
    if name == 'read_file':
        path, shown = read_shown(task, args)
        if path != span['path']:
            return False
        return any(span['start'] <= ln <= span_end(span) for ln in shown)
    if name in ('edit_file', 'write_file'):
        return norm(args.get('filepath')) == span['path']
    if name == 'run_command':
        short = (span.get('qualname') or node).split('.')[-1].split(':')[-1]
        return shell_touch(task, str(args.get('command') or ''), span, short)
    return False


# ------------------------------------------------------------------ rates

def stat(pick, num, den):
    """Rate (or difference of two rates) over the picked states; num and den are lists indexed like the states."""
    if isinstance(num, tuple):
        (n1, d1), (n2, d2) = num, den
        return (sum(n1[i] for i in pick) / sum(d1[i] for i in pick)
                - sum(n2[i] for i in pick) / sum(d2[i] for i in pick))
    return sum(num[i] for i in pick) / sum(den[i] for i in pick)


def boot(picks, num, den):
    return sorted(stat(pick, num, den) for pick in picks)


def q(vals, p):
    return vals[min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))]


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    out = []
    rows, states = R.load_rows(), R.load_states()
    table = {}
    for r in rows:
        kind = R.classify(r)
        r['_kind'] = kind[0] if isinstance(kind, (tuple, list)) else kind
        table[((r['task'], r['run'], r['fork']), r['arm'], r['seed'])] = r
    complete = [k for k in sorted(states)
                if all(table.get((k, a, sd)) is not None and table[(k, a, sd)]['_kind'] == 'ok'
                       for a in ARMS for sd in R.SEEDS)]
    out.append('Independent recount of outcomes (pre-registrations 02 and 03), runs v5 + v6 + v8')
    out.append('rows %d, states %d, complete states %d, replays per arm %d'
               % (len(rows), len(states), len(complete), 3 * len(complete)))

    OUTC = ('any_true', 'swapped', 'decoy', 'any_rewired')
    N = len(complete)
    cnt = {(a, o): [0] * N for a in ARMS for o in OUTC}
    den = {a: [0] * N for a in ARMS}
    per_row = {}
    for ki, k in enumerate(complete):
        if ki % 40 == 0:
            print('scoring state %d of %d' % (ki, N), file=sys.stderr, flush=True)
        s = states[k]
        nsp = s.get('neighbor_spans') or {}
        rsp = s.get('rewired_spans') or {}
        for a in ARMS:
            for sd in R.SEEDS:
                c = table[(k, a, sd)]['next_call']
                res = {
                    'any_true': any(touch(k[0], c, nsp.get(n), n) for n in s.get('unshown_true_neighbors') or []),
                    'swapped': bool(s.get('swapped_out')) and touch(k[0], c, nsp.get(s['swapped_out']), s['swapped_out']),
                    'decoy': bool(s.get('decoy')) and touch(k[0], c, s.get('decoy_span'), s['decoy']),
                    'any_rewired': any(touch(k[0], c, rsp.get(n), n) for n in s.get('rewired_entries') or []),
                }
                per_row[(k, a, sd)] = res
                den[a][ki] += 1
                for o in OUTC:
                    cnt[(a, o)][ki] += int(res[o])
    rng = random.Random(20261109)
    every = list(range(N))
    picks = [[rng.randrange(N) for _ in every] for _ in range(2000)]  # the same resamples for every cell
    out.append('')
    out.append('Rates, percent of replays, with 95% intervals clustered by state (2,000 resamples); n = touches')
    out.append('%-4s %-30s %-30s %-30s %-30s' % (('arm',) + OUTC))
    for a in ARMS:
        cells = []
        for o in OUTC:
            v = boot(picks, cnt[(a, o)], den[a])
            cells.append('%5.2f [%5.2f, %5.2f] n=%d' % (100 * stat(every, cnt[(a, o)], den[a]), 100 * q(v, .025),
                                                       100 * q(v, .975), sum(cnt[(a, o)])))
        out.append('%-4s ' % a + ' '.join('%-30s' % c for c in cells))

    def diff(label, a1, o1, a2, o2, ninety=False):
        num, dn = (cnt[(a1, o1)], cnt[(a2, o2)]), (den[a1], den[a2])
        num, dn = (num[0], dn[0]), (num[1], dn[1])
        v = boot(picks, num, dn)
        line = '%-40s %+6.2f  95%% [%+.2f, %+.2f]' % (label, 100 * stat(every, num, dn), 100 * q(v, .025), 100 * q(v, .975))
        if ninety:
            line += '  90%% [%+.2f, %+.2f]' % (100 * q(v, .05), 100 * q(v, .95))
        out.append(line)

    out.append('')
    out.append('Contrasts (percentage points)')
    diff('B1  D - H, any true', 'D', 'any_true', 'H', 'any_true')
    diff('B2  D_B = swapped | D  -  decoy | Dp', 'D', 'swapped', 'Dp', 'decoy', ninety=True)
    diff('B3  E - H, any true', 'E', 'any_true', 'H', 'any_true')
    diff('B4  D any true - RD any rewired', 'D', 'any_true', 'RD', 'any_rewired')
    diff('B4  E any true - RE any rewired', 'E', 'any_true', 'RE', 'any_rewired')
    diff('    D any true - RD any true (ref.)', 'D', 'any_true', 'RD', 'any_true')
    diff('    E any true - RE any true (ref.)', 'E', 'any_true', 'RE', 'any_true')
    diff('    E - A, any true', 'E', 'any_true', 'A', 'any_true')
    diff('    H - A, any true', 'H', 'any_true', 'A', 'any_true')
    miss_py = sorted(k for k in MISSING if k[1].endswith('.py'))
    out.append('')
    out.append('Snapshot text: %d files read; %d paths not in the snapshot (%d of them .py, e.g. files the agent '
               'created); for those, character caps and grep content matching fall back to line ranges only'
               % (sum(v is not None for v in _TEXT.values()), len(MISSING), len(miss_py)))
    path = os.path.join(ROOT, 'analysis', 'results', 'recount_b_outcomes%s.txt' % SUFFIX)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')
    with open(os.path.join(ROOT, 'analysis', 'results', 'recount_b_outcomes_rows%s.jsonl' % SUFFIX), 'w', encoding='utf-8',
              newline='\n') as f:
        for (k, a, sd), res in sorted(per_row.items()):
            f.write(json.dumps({'task': k[0], 'run': k[1], 'fork': k[2], 'arm': a, 'seed': sd, **res}) + '\n')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
