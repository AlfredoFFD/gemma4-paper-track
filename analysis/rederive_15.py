"""Independent re-derivation of pre-registration 15 (the agent's own search, with and without its line numbers).

Written blind: from the text of prereg/15-own-search-without-line-numbers.md and the raw files only
(analysis/results/15/forks/results.jsonl, analysis/fork_states_s/states.jsonl, data/snapshots/<task>.tgz).

Usage: py -I -X utf8 analysis/rederive_15.py <run_dir> [--no-write]
Writes the report to analysis/results/rederive_15.txt (LF) unless --no-write is given.
"""
import json
import math
import posixpath
import random
import re
import shlex
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ROOT / 'analysis' / 'fork_states_s' / 'states.jsonl'
SNAP = ROOT / 'data' / 'snapshots'
OUT = ROOT / 'analysis' / 'results' / 'rederive_15.txt'

ARMS = ('S', 'S0', 'S0N')
SEEDS = (1, 2, 3)
B = 2000
SEED = 15151
FLOOR = 40
KNOWN_TOOLS = {'read_file', 'run_command', 'write_file', 'edit_file', 'search_similar_code', 'submit_patch'}
REQUIRED = {'read_file': ('filepath',), 'run_command': ('command',), 'write_file': ('filepath', 'content'),
            'edit_file': ('filepath', 'old_string', 'new_string'), 'search_similar_code': ('query',),
            'submit_patch': ()}
OPEN_PROGS = {'cat', 'sed', 'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'awk', 'less', 'more'}
SEARCH_PROGS = {'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack'}
SEPS = {'|', '||', '&&', ';', '|&', '&'}
REDIRS = {'>', '>>', '<', '<<', '2>', '&>', '2>&1'}

# ---------------------------------------------------------------- snapshots

_snap_cache = {}


def snapshot(task):
    """{path: number of lines} for every .py file of the task's snapshot (paths without ./)."""
    if task not in _snap_cache:
        files = {}
        texts = {}
        with tarfile.open(SNAP / f'{task}.tgz', 'r:gz') as tf:
            for m in tf:
                if m.isfile() and m.name.endswith('.py'):
                    name = m.name[2:] if m.name.startswith('./') else m.name
                    data = tf.extractfile(m).read().decode('utf-8', 'replace')
                    lines = data.split('\n')
                    if lines and lines[-1] == '':
                        lines = lines[:-1]
                    files[name] = len(lines)
                    texts[name] = lines
        _snap_cache[task] = (files, texts)
    return _snap_cache[task]


def norm(p):
    """Path as the agent or grep wrote it -> path relative to the repository root."""
    if not isinstance(p, str):
        return None
    p = p.strip().strip('"').strip("'")
    if '/workspace/' in p:
        p = p.split('/workspace/')[-1]
    elif p == '/workspace':
        p = '.'
    while p.startswith('./'):
        p = p[2:]
    if not p:
        return p
    p = posixpath.normpath(p)
    return p


def repo_file(task, p):
    q = norm(p)
    return q if q in snapshot(task)[0] else None

# ---------------------------------------------------------------- shell parsing


def tokens(cmd):
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return cmd.split()


def pipelines(cmd):
    """List of pipelines; each pipeline is a list of segments (token lists). Split on && ; || and on |."""
    out, pipe, seg = [], [], []
    for t in tokens(cmd):
        if t in ('|', '|&'):
            pipe.append(seg); seg = []
        elif t in SEPS:
            pipe.append(seg); out.append(pipe); pipe, seg = [], []
        else:
            seg.append(t)
    pipe.append(seg)
    out.append(pipe)
    return [[s for s in p if s] for p in out if any(p)]


def segments(cmd):
    return [s for p in pipelines(cmd) for s in p]


def prog(seg):
    i = 0
    while i < len(seg) and re.match(r'^[A-Za-z_]+=', seg[i]):
        i += 1
    if i >= len(seg):
        return None, []
    name = posixpath.basename(seg[i])
    rest = seg[i + 1:]
    if name == 'git' and rest and rest[0] == 'grep':
        return 'grep', rest[1:]
    return name, rest


def operands(rest):
    """Non-option tokens, dropping redirection targets."""
    out, skip = [], False
    for t in rest:
        if skip:
            skip = False
            continue
        if t in REDIRS:
            skip = True
            continue
        if t.startswith('-') and t != '-':
            continue
        out.append(t)
    return out


def files_named(task, cmd):
    named = []
    for seg in segments(cmd):
        name, rest = prog(seg)
        if name is None:
            continue
        for t in operands(rest):
            f = repo_file(task, t)
            if f and f not in named:
                named.append(f)
    return named


def grep_asks_numbers(name, rest):
    if name == 'rg':
        return not any(t in ('-N', '--no-line-number') for t in rest)
    for t in rest:
        if t == '--line-number':
            return True
        if t.startswith('-') and not t.startswith('--') and 'n' in t[1:]:
            # short option cluster; stop at an option that takes a value (e, f, m, A, B, C, d, D)
            for ch in t[1:]:
                if ch == 'n':
                    return True
                if ch in 'efmABCdD':
                    break
    return False

# ---------------------------------------------------------------- observations


def obs_of(step):
    o = step.get('observation') or {}
    c = o.get('content')
    if isinstance(c, str):
        try:
            return json.loads(c)
        except ValueError:
            return {'raw': c}
    return c if isinstance(c, dict) else {}


def stdout_of(obs):
    s = obs.get('stdout')
    if s is None:
        s = (obs.get('details') or {}).get('stdout')
    return s or ''


def opened_before(task, steps):
    """Files opened in the history before the last step, as the pre-registration defines opened."""
    opened = set()
    for st in steps[:-1]:
        calls = st.get('tool_calls') or []
        if not calls:
            continue
        obs = obs_of(st)
        for tc in calls:
            fn, args = tc.get('function_name'), tc.get('arguments') or {}
            if fn == 'read_file':
                if obs.get('status') == 'ok' and (obs.get('content') or ''):
                    f = repo_file(task, args.get('filepath'))
                    if f:
                        opened.add(f)
            elif fn == 'run_command':
                if not stdout_of(obs).strip():
                    continue
                for seg in segments(args.get('command') or ''):
                    name, rest = prog(seg)
                    if name not in OPEN_PROGS:
                        continue
                    for t in operands(rest):
                        f = repo_file(task, t)
                        if f:
                            opened.add(f)
    return opened


HIT_PATH = re.compile(r'^(?P<path>[^\n]*?):(?P<line>\d+):(?P<text>.*)$')
HIT_ONE = re.compile(r'^(?P<line>\d+):(?P<text>.*)$')
CTX_ONE = re.compile(r'^(?P<line>\d+)-(?P<text>.*)$')


def parse_result(task, cmd, stdout):
    """Classify each output line. Returns (hits, n_context, n_other, one_file)."""
    named = files_named(task, cmd)
    one = named[0] if len(named) == 1 else None
    hits, nctx, nother = [], 0, 0
    lines = stdout.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
    for ln in lines:
        if one is not None:
            m = HIT_ONE.match(ln)
            if m:
                hits.append({'raw_path': None, 'file': one, 'line': int(m['line']), 'text': m['text']})
                continue
            if CTX_ONE.match(ln):
                nctx += 1
                continue
        m = HIT_PATH.match(ln)
        if m:
            hits.append({'raw_path': m['path'], 'file': norm(m['path']), 'line': int(m['line']), 'text': m['text']})
            continue
        ctx = False
        for mm in re.finditer(r'-(\d+)-', ln):
            if repo_file(task, ln[:mm.start()]) or ln[:mm.start()].endswith(('.py', '.md', '.txt', '.toml')):
                ctx = True
                break
        if ctx:
            nctx += 1
        else:
            nother += 1
    return hits, nctx, nother, one, cmd


def strip_numbers(task, cmd, stdout):
    """The S0 transformation, applied to the S result, for a fidelity check."""
    named = files_named(task, cmd)
    one = named[0] if len(named) == 1 else None
    out = []
    for ln in stdout.split('\n'):
        if one is not None and HIT_ONE.match(ln):
            out.append(HIT_ONE.match(ln)['text']); continue
        if one is not None and CTX_ONE.match(ln):
            out.append(CTX_ONE.match(ln)['text']); continue
        m = HIT_PATH.match(ln)
        if m:
            out.append(m['path'] + ':' + m['text']); continue
        done = False
        for mm in re.finditer(r'-(\d+)-', ln):
            if repo_file(task, ln[:mm.start()]):
                out.append(ln[:mm.start()] + '-' + ln[mm.end():]); done = True
                break
        if not done:
            out.append(ln)
    return '\n'.join(out)

# ---------------------------------------------------------------- scoring a replay


def interface_failure(row):
    if row.get('error'):
        return 'runner error'
    nc = row.get('next_call')
    if not nc or not nc.get('function_name'):
        return 'no call'
    if nc['function_name'] not in KNOWN_TOOLS:
        return 'unknown tool'
    a = nc.get('arguments')
    if not isinstance(a, dict):
        return 'malformed call'
    names = {clean_name(k) for k in a}
    for k in REQUIRED.get(nc['function_name'], ()):
        if k not in names:
            return 'malformed call'
    return None


def clean_name(k):
    return re.sub(r'[\s"\'\\]', '', k)


def as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r'\s*-?\d+\s*', v):
        return int(v)
    return None


def shell_read(task, cmd, hitfiles):
    """(file, first, last) when the first pipeline starts from cat/head/tail/sed -n on a hit file and the
    range shown is known; else None."""
    pls = pipelines(cmd)
    if not pls or not pls[0]:
        return None
    pipe = pls[0]
    name, rest = prog(pipe[0])
    if name not in ('cat', 'head', 'tail', 'sed'):
        return None
    ops = operands(rest)
    f = None
    for t in ops:
        g = repo_file(task, t)
        if g in hitfiles:
            f = g
            break
    if f is None:
        return None
    nlines = snapshot(task)[0][f]
    rng = range_of(name, rest, nlines)
    if rng is None:
        return None
    a, b = rng
    for seg in pipe[1:]:
        n2, r2 = prog(seg)
        if n2 in ('head', 'tail', 'sed', 'cat', 'nl'):
            if n2 in ('cat', 'nl'):
                continue
            sub = range_of(n2, r2, b - a + 1)
            if sub is None:
                return None
            a, b = a + sub[0] - 1, a + sub[1] - 1
        else:
            return None
    return f, a, b


def count_opt(rest, default):
    for i, t in enumerate(rest):
        if t in ('-n', '--lines') and i + 1 < len(rest):
            return rest[i + 1]
        if t.startswith('--lines='):
            return t.split('=', 1)[1]
        if re.fullmatch(r'-n[+-]?\d+', t):
            return t[2:]
        if re.fullmatch(r'-\d+', t):
            return t[1:]
    return default


def range_of(name, rest, nlines):
    if name == 'cat':
        return 1, nlines
    if name == 'head':
        k = count_opt(rest, '10')
        if not re.fullmatch(r'\d+', k):
            return None
        return 1, min(int(k), nlines)
    if name == 'tail':
        k = count_opt(rest, '10')
        if re.fullmatch(r'\+\d+', k):
            return max(int(k[1:]), 1), nlines
        if not re.fullmatch(r'\d+', k):
            return None
        return max(nlines - int(k) + 1, 1), nlines
    if name == 'sed':
        if '-n' not in rest and not any(re.fullmatch(r'-[a-zA-Z]*n[a-zA-Z]*', t) for t in rest):
            return None
        for t in operands(rest):
            m = re.fullmatch(r"(\d+)(?:,(\d+|\$))?p", t)
            if m:
                a = int(m[1])
                b = nlines if m[2] in (None, '$') and m[2] == '$' else (int(m[2]) if m[2] else a)
                return a, b
        return None
    return None


def score(task, row, hitfiles):
    """Outcome of one usable replay."""
    nc = row['next_call']
    fn, a = nc['function_name'], nc['arguments']
    o = {'tool': fn, 'reads_hit_file': False, 'past_line_1': False, 'on_a_hit': False, 'mangled_start': False,
         'searches_again': False, 'search_asks_numbers': False, 'file': None, 'kind': fn}
    if fn == 'read_file':
        f = repo_file(task, a.get('filepath'))
        start = end = None
        mangled = False
        for k, v in a.items():
            ck = clean_name(k)
            if ck == 'start_line':
                start = as_int(v)
                mangled = mangled or (k != 'start_line')
            elif ck == 'end_line':
                end = as_int(v)
        if f in hitfiles:
            o['reads_hit_file'] = True
            o['file'] = f
            s = start if (start is not None and start >= 1) else 1
            o['past_line_1'] = s > 1
            o['mangled_start'] = mangled and s > 1
            e = end if (end is not None and end >= s) else s + 149
            e = min(e, s + 149)
            o['on_a_hit'] = any(s <= h <= e for h in hitfiles[f])
    elif fn == 'run_command':
        cmd = a.get('command') or ''
        pls = pipelines(cmd)
        first = prog(pls[0][0]) if pls and pls[0] else (None, [])
        if first[0] in SEARCH_PROGS:
            o['searches_again'] = True
            o['search_asks_numbers'] = grep_asks_numbers(*first)
            o['kind'] = 'run_command: search'
        elif first[0] == 'find':
            o['kind'] = 'run_command: find'
        elif first[0] in ('pytest',) or (first[0] and first[0].startswith('python') and 'pytest' in first[1][:2]):
            o['kind'] = 'run_command: pytest'
        elif first[0] and first[0].startswith('python'):
            o['kind'] = 'run_command: python'
        elif '<<' in cmd or re.search(r'(^|[^2&])>', cmd):
            o['kind'] = 'run_command: writes a file'
        elif first[0] in ('cat', 'head', 'tail', 'sed', 'awk', 'less', 'more', 'nl'):
            o['kind'] = 'run_command: file view'
        else:
            o['kind'] = 'run_command: other'
        r = shell_read(task, cmd, hitfiles)
        if r:
            f, s, e = r
            o['reads_hit_file'] = True
            o['file'] = f
            o['past_line_1'] = s > 1
            o['on_a_hit'] = any(s <= h <= e for h in hitfiles[f])
    o['_hits'] = hitfiles[o['file']] if o['file'] else [0]
    return o

# ---------------------------------------------------------------- statistics


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float('nan')
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def ci(vals):
    good = [v for v in vals if v is not None and not math.isnan(v)]
    return pct(good, 0.025), pct(good, 0.975), len(vals) - len(good)


def ratio(a, b):
    return a / b if b else float('nan')


def fmt_p(x):
    return 'n/a' if x is None or math.isnan(x) else f'{100 * x:.1f}'


def fmt_rate(k, n):
    return f'{k}/{n} ({fmt_p(ratio(k, n))}%)'


def fmt_ci(lo, hi):
    return f'[{fmt_p(lo)}, {fmt_p(hi)}]'

# ---------------------------------------------------------------- main


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    run_dir = Path(argv[1])
    no_write = '--no-write' in argv[2:]
    if not run_dir.is_absolute():
        run_dir = (Path.cwd() / run_dir)
    L = []
    p = L.append

    # ---- states
    recs = [json.loads(x) for x in STATES.read_text(encoding='utf-8').splitlines() if x.strip()]
    by_state = defaultdict(dict)
    for r in recs:
        by_state[r['state_id']][r['arm']] = r
    sids = sorted(by_state)
    info = {}
    checks = Counter()
    diffs = []
    for sid in sids:
        rs = by_state[sid]
        s = rs['S']
        task = s['task']
        last = s['steps'][-1]
        cmd = last['tool_calls'][0]['arguments']['command']
        out = stdout_of(obs_of(last))
        hits, nctx, nother, one, _ = parse_result(task, cmd, out)
        opened = opened_before(task, s['steps'])
        hf = defaultdict(list)
        for h in hits:
            if h['file'] in snapshot(task)[0] and h['file'] not in opened:
                hf[h['file']].append(h['line'])
        hf = {f: sorted(set(v)) for f, v in hf.items()}
        repo_hits = [h for h in hits if h['file'] in snapshot(task)[0]]
        equal = sum(1 for h in repo_hits
                    if 1 <= h['line'] <= len(snapshot(task)[1][h['file']])
                    and snapshot(task)[1][h['file']][h['line'] - 1] == h['text'])
        note = 'Line numbers of the matches above:\n' + '\n'.join(
            f"{h['raw_path'] if h['raw_path'] is not None else one_written(cmd, task)}:{h['line']}" for h in hits)
        info[sid] = {'task': task, 'run': s['run'], 'repo': s.get('repo'), 'hitfiles': hf, 'n_hits': len(hits),
                     'n_repo_hits': len(repo_hits), 'n_equal': equal, 'n_ctx': nctx, 'n_other': nother,
                     'one': one, 'opened': opened}
        # comparisons with what the record stores
        if {f: list(v) for f, v in hf.items()} != {f: sorted(v) for f, v in (s.get('hit_files') or {}).items()}:
            diffs.append(f'{sid}: hit files mine {json.dumps(hf, sort_keys=True)} vs stored '
                         f'{json.dumps(s.get("hit_files"), sort_keys=True)}')
        if set(opened) != set(norm(x) for x in (s.get('opened_files') or [])):
            stored_rel = set(norm(x) for x in (s.get('opened_files') or [])) & set(snapshot(task)[0])
            if set(opened) != stored_rel:
                diffs.append(f'{sid}: opened repo files mine {sorted(opened)} vs stored {sorted(stored_rel)}')
            else:
                checks['opened differs only in non-repository files'] += 1
        s0 = rs.get('S0')
        s0n = rs.get('S0N')
        out0 = stdout_of(obs_of(s0['steps'][-1]))
        checks['S0 result equals S result with numbers removed'] += strip_numbers(task, cmd, out) == out0
        checks['S0N last result equals S0 last result'] += obs_of(s0n['steps'][-1]) == obs_of(s0['steps'][-1])
        checks['S0 and S histories equal before the last result'] += s0['steps'][:-1] == s['steps'][:-1]
        checks['S0N history equals S0 history'] += s0n['steps'] == s0['steps']
        stored_note = ((s0n.get('arms') or {}).get('S0N') or {}).get('user_text')
        checks['S0N note equals the note derived from the S result'] += stored_note == note
        checks['S and S0 records carry no added message'] += not s.get('arms') and not s0.get('arms')
    p('Re-derivation of pre-registration 15 (independent script, written from the registration text and raw files)')
    p(f'run dir: {argv[1]}')
    p('')
    p('0. STATES (derived from the S records and their histories)')
    tasks = sorted({info[s]['task'] for s in sids})
    runs = sorted({(info[s]['task'], info[s]['run']) for s in sids})
    per_run = Counter((info[s]['task'], info[s]['run']) for s in sids)
    repos = Counter(info[s]['repo'] for s in sids)
    p(f'  states {len(sids)}, runs {len(runs)}, tasks {len(tasks)}; runs giving two states {sum(1 for v in per_run.values() if v == 2)};'
      f' by repository ' + ', '.join(f'{k} {v}' for k, v in sorted(repos.items())))
    p(f'  hit files {sum(len(info[s]["hitfiles"]) for s in sids)}; hit lines {sum(info[s]["n_hits"] for s in sids)}'
      f' (in a Python file of the snapshot {sum(info[s]["n_repo_hits"] for s in sids)}, of which equal to that snapshot line'
      f' {sum(info[s]["n_equal"] for s in sids)}); context lines {sum(info[s]["n_ctx"] for s in sids)}'
      f' (in {sum(1 for s in sids if info[s]["n_ctx"])} state); other lines {sum(info[s]["n_other"] for s in sids)}')
    p(f'  states whose command names exactly one repository file: {sum(1 for s in sids if info[s]["one"])};'
      f' states with no hit file: {sum(1 for s in sids if not info[s]["hitfiles"])}')
    far = {s for s in sids if info[s]['hitfiles'] and all(min(v) > 150 for v in info[s]['hitfiles'].values())}
    p(f'  states in which every hit file has its first hit past line 150: {len(far)}')
    for k in sorted(checks):
        p(f'  check: {k}: {checks[k]} of {len(sids)}')
    p(f'  differences from the hit files / opened files stored in the records: {len(diffs)}')
    for d in diffs:
        p('    ' + d)
    p('')

    # ---- replays
    rows = [json.loads(x) for x in (run_dir / 'results.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    fork_to_sid = {}
    for sid, rs in by_state.items():
        for arm, r in rs.items():
            fork_to_sid[(r['task'], r['run'], r['fork'])] = (sid, arm)
    cell = {}
    runner_arm = Counter()
    dup = 0
    unmatched = 0
    for r in rows:
        key = (r['task'], r['run'], r['fork'])
        if key not in fork_to_sid:
            unmatched += 1
            continue
        sid, arm = fork_to_sid[key]
        runner_arm[(arm, r['arm'])] += 1
        k = (sid, arm, r['seed'])
        if k in cell:
            dup += 1
        cell[k] = r
    p('1. REPLAYS BY ARM')
    p('  arm assignment: a row belongs to the state record whose (task, run, fork) it carries; the fork id ends in'
      ' :S, :S0 or :S0N, which is the arm of that record.')
    p('  runner arm by design arm: ' + ', '.join(f'{a} under runner arm {ra}: {n}' for (a, ra), n in sorted(runner_arm.items())))
    p(f'  rows {len(rows)}; unmatched {unmatched}; duplicate (state, arm, seed) {dup};'
      f' missing cells {len(sids) * 9 - len(cell)}')
    usable = {}
    fails = defaultdict(Counter)
    for (sid, arm, seed), r in cell.items():
        f = interface_failure(r)
        if f:
            fails[arm][f] += 1
            continue
        usable[(sid, arm, seed)] = score(info[sid]['task'], r, info[sid]['hitfiles'])
    for arm in ARMS:
        n = sum(1 for k in cell if k[1] == arm)
        u = sum(1 for k in usable if k[1] == arm)
        fl = ', '.join(f'{k} {v}' for k, v in sorted(fails[arm].items())) or 'none'
        p(f'  {arm:4s} rows {n}; interface failures: {fl}; usable {fmt_rate(u, n)}')
    for (sid, arm, seed), r in sorted(cell.items()):
        f = interface_failure(r)
        if f:
            p(f'    failure: {sid} {arm} seed {seed}: {f}')

    def complete(arms):
        return [s for s in sids if all((s, a, sd) in usable for a in arms for sd in SEEDS)]
    comp12 = complete(('S', 'S0'))
    comp3 = complete(ARMS)
    for name, cs in (('Q1 and Q2 (S, S0)', comp12), ('Q3 (S, S0, S0N)', comp3)):
        ts = sorted({info[s]['task'] for s in cs})
        p(f'  complete for {name}: {len(cs)} states of {len(ts)} tasks; incomplete: '
          + (', '.join(s for s in sids if s not in cs) or 'none'))
        p('    tasks: ' + ', '.join(ts))
    p('')

    # ---- per-state tallies
    def tally(sid, arm):
        y1 = y2 = 0
        for sd in SEEDS:
            o = usable[(sid, arm, sd)]
            y2 += o['reads_hit_file']
            y1 += o['reads_hit_file'] and o['past_line_1']
        return y1, y2, 3

    rng = random.Random(SEED)

    def resamples(states):
        n = len(states)
        bys = [[states[rng.randrange(n)] for _ in range(n)] for _ in range(B)]
        by_task = defaultdict(list)
        for s in states:
            by_task[info[s]['task']].append(s)
        tk = sorted(by_task)
        byt = []
        for _ in range(B):
            pick = [tk[rng.randrange(len(tk))] for _ in range(len(tk))]
            byt.append([s for t in pick for s in by_task[t]])
        return bys, byt

    def stats(states, arms):
        out = {}
        for a in arms:
            y1 = y2 = n = 0
            for s in states:
                t = T[(s, a)]
                y1 += t[0]; y2 += t[1]; n += t[2]
            out[a] = {'Y1': ratio(y1, n), 'Y2': ratio(y2, n), 'C': ratio(y1, y2), 'y1': y1, 'y2': y2, 'n': n}
        return out

    T = {}
    for s in sids:
        for a in ARMS:
            if all((s, a, sd) in usable for sd in SEEDS):
                T[(s, a)] = tally(s, a)

    rs12 = resamples(comp12)
    rs3 = rs12 if comp3 == comp12 else resamples(comp3)  # same states -> the same resamples

    p('2. ESTIMANDS ON COMPLETE STATES (95% bootstrap by state, 2,000 resamples, percentile)')
    results = {}
    for label, cs, rsx, arms in (('Q1/Q2 set', comp12, rs12, ('S', 'S0')), ('Q3 set', comp3, rs3, ARMS)):
        st = stats(cs, arms)
        bs = [stats(x, arms) for x in rsx[0]]
        bt = [stats(x, arms) for x in rsx[1]]
        results[label] = (st, bs, bt)
        p(f'  {label}: {len(cs)} states, {len(cs) * 3} replays per arm')
        for a in arms:
            d = st[a]
            for est, k, nn in (('Y1', 'y1', 'n'), ('Y2', 'y2', 'n'), ('C', 'y1', 'y2')):
                lo, hi, nan = ci([b[a][est] for b in bs])
                extra = f' ({nan} resamples with no read left out)' if nan else ''
                p(f'    {a:4s} {est:2s} {fmt_rate(d[k], d[nn]):>18s}  CI {fmt_ci(lo, hi)}{extra}')
    p('')

    p('3. RULES')
    st, bs, bt = results['Q1/Q2 set']

    def diff_line(name, fn, st, bs, bt):
        pt = fn(st)
        lo, hi, nan = ci([fn(b) for b in bs])
        tlo, thi, tnan = ci([fn(b) for b in bt])
        ex = ''
        if nan or tnan:
            ex = f' (left out: {nan} by state, {tnan} by task)'
        p(f'  {name}: {fmt_p(pt)} points, by state {fmt_ci(lo, hi)}, by task {fmt_ci(tlo, thi)}{ex}')
        return pt, lo, hi

    n12 = len(comp12)
    pt, lo, hi = diff_line('Q1  Y1(S) - Y1(S0)', lambda x: x['S']['Y1'] - x['S0']['Y1'], st, bs, bt)
    if n12 < FLOOR:
        p(f'      verdict: underpowered ({n12} complete states, fewer than {FLOOR})')
    else:
        p(f'      verdict: {"met" if lo > 0 else "not met"} (lower bound {"above" if lo > 0 else "not above"} 0; {n12} complete states)')
    c0 = st['S0']
    lo2, hi2, nan2 = ci([b['S0']['C'] for b in bs])
    tlo2, thi2, tnan2 = ci([b['S0']['C'] for b in bt])
    p(f'  Q2  share of reads of a hit file under S0 that ask past line 1: {fmt_rate(c0["y1"], c0["y2"])},'
      f' by state {fmt_ci(lo2, hi2)}, by task {fmt_ci(tlo2, thi2)}'
      + (f' (left out: {nan2} by state, {tnan2} by task)' if nan2 or tnan2 else ''))
    if n12 < FLOOR:
        p(f'      verdict: underpowered ({n12} complete states)')
    elif c0['y2'] < 20:
        p(f'      verdict: not testable ({c0["y2"]} reads of a hit file under S0, fewer than 20)')
    else:
        ok = ratio(c0['y1'], c0['y2']) <= 0.05
        p(f'      verdict: {"met" if ok else "not met"} (point share {"at most" if ok else "above"} 5%, {c0["y2"]} reads)')

    st, bs, bt = results['Q3 set']
    n3 = len(comp3)
    pt3, lo3, hi3 = diff_line('Q3a Y1(S0N) - Y1(S0)', lambda x: x['S0N']['Y1'] - x['S0']['Y1'], st, bs, bt)
    pt3b, lo3b, hi3b = diff_line('Q3b C(S0N) - C(S)', lambda x: x['S0N']['C'] - x['S']['C'], st, bs, bt)

    def rfun(x):
        den = x['S']['Y1'] - x['S0']['Y1']
        if not den > 0:
            return float('nan')
        return (x['S0N']['Y1'] - x['S0']['Y1']) / den
    rpt = rfun(st)
    rlo, rhi, rnan = ci([rfun(b) for b in bs])
    tlo, thi, tnan = ci([rfun(b) for b in bt])
    p(f'  Q3c R = (Y1(S0N) - Y1(S0)) / (Y1(S) - Y1(S0)): {rpt:.3f}, by state [{rlo:.3f}, {rhi:.3f}]'
      f' ({rnan} of {B} resamples with a denominator zero or negative left out), by task [{tlo:.3f}, {thi:.3f}] ({tnan} left out)')
    if n3 < FLOOR:
        p(f'      verdict: underpowered ({n3} complete states)')
    else:
        p(f'      verdict Q3a: {"met" if lo3 > 0 else "not met"} (lower bound {"above" if lo3 > 0 else "not above"} 0; {n3} complete states)')
        if hi3b < 0:
            v = 'used less often than in the agent\'s own result'
        elif lo3b > 0:
            v = 'used more often'
        else:
            v = 'no detectable difference'
        p(f'      verdict Q3b: {v}')
        if rpt >= 2 / 3:
            p('      verdict Q3c: the note carries the line number about as well as the agent\'s own result (R at least two thirds)')
        else:
            p('      verdict Q3c: R below two thirds; the condition for "the note carries the line number about as well as'
              ' the agent\'s own result" is not met')
    p('')

    p('4. DESCRIPTIVE (all usable replays of every state, by arm)')
    for arm in ARMS:
        os_ = [o for (s, a, sd), o in sorted(usable.items()) if a == arm]
        reads = [o for o in os_ if o['reads_hit_file']]
        p(f'  {arm}: usable {len(os_)}')
        p(f'    reads_hit_file {fmt_rate(len(reads), len(os_))}; past_line_1 among them {fmt_rate(sum(o["past_line_1"] for o in reads), len(reads))};'
          f' on_a_hit among them {fmt_rate(sum(o["on_a_hit"] for o in reads), len(reads))}; on_a_hit of all {fmt_rate(sum(o["on_a_hit"] for o in os_), len(os_))}')
        sa = [o for o in os_ if o['searches_again']]
        p(f'    searches_again {fmt_rate(len(sa), len(os_))}; of those asking for line numbers {fmt_rate(sum(o["search_asks_numbers"] for o in sa), len(sa))}')
        kinds = Counter(o['kind'] for o in os_)
        p('    next tool: ' + ', '.join(f'{k} {v}' for k, v in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))))
        shell = sum(1 for o in reads if o['tool'] == 'run_command')
        p(f'    reads of a hit file through a shell view: {shell}')
        near = [o for o in reads if min(info_hits(info, usable, o)) <= 150]
        farr = [o for o in reads if min(info_hits(info, usable, o)) > 150]
        p(f'    reads of a hit file whose nearest hit is at or before line 150: {len(near)}, past_line_1 {fmt_rate(sum(o["past_line_1"] for o in near), len(near))};'
          f' nearest hit past line 150: {len(farr)}, past_line_1 {fmt_rate(sum(o["past_line_1"] for o in farr), len(farr))}')
        for grp, lab in ((far, 'every hit file first hit past 150'), (set(sids) - far, 'some hit file with a hit at or before 150')):
            g = [o for (s, a, sd), o in usable.items() if a == arm and s in grp]
            p(f'    Y1 in states with {lab} ({len({s for (s, a, sd) in usable if a == arm and s in grp})} states): '
              f'{fmt_rate(sum(o["reads_hit_file"] and o["past_line_1"] for o in g), len(g))}')
        m = [o for o in reads if o['mangled_start']]
        p(f'    reads counted as asking past line 1 through a mangled argument name: {len(m)}')
    p('')
    p('5. JUDGMENT CALLS (where the registration left room)')
    for j in JUDGMENT:
        p('  - ' + j)
    return finish(L, no_write)


JUDGMENT = [
    'Arms: from the fork id suffix (:S, :S0, :S0N) of the state record each row names by (task, run, fork); the runner'
    ' arm field (A for S and S0, S0N for S0N) is only checked against it.',
    'Paths: everything up to the last "/workspace/" and any leading "./" is dropped, then normalized; a repository file'
    ' is a .py member of data/snapshots/<task>.tgz (read directly, not through the cache helper).',
    'Opened earlier: read_file with status ok and non-empty content; run_command whose stdout (top level or under'
    ' details) is non-empty, crediting every operand of a cat/sed/head/tail/grep/egrep/fgrep/rg/awk/less/more segment'
    ' that is a repository file (a directory operand opens nothing). fork_states.py itself was not opened.',
    'Hit lines: one-file form (line:text) only when the command names exactly one repository file; otherwise'
    ' path:line:text. Context lines path-line-text / line-text are counted, not scored.',
    'Interface failures: runner error (error field set), no call (next_call empty), unknown tool (not one of read_file,'
    ' run_command, write_file, edit_file, search_similar_code, submit_patch), malformed (arguments not an object or a'
    ' required argument missing after cleaning quotes, backslashes and blanks from names). A mangled start_line is usable.',
    'A mangled end_line (name equal to end_line once cleaned) is used as the end of the window for on_a_hit, as for'
    ' start_line; a start_line below 1 or absent is taken as 1; an end below the start is treated as no end.',
    'Shell reads: only the first pipeline (before && ; ||) counts; it must start with cat, head, tail or sed -n'
    ' (a p-script a,bp / a,$p / ap) on a hit file; later stages in the pipe may only be head/tail/sed -n/cat/nl,'
    ' otherwise the range is unknown and it is not a read. cat shows the whole file; no 150-line cap for shell views.',
    'searches_again: a run_command whose first program is grep, egrep, fgrep, rg, ag, ack or git grep (find and'
    ' search_similar_code are not counted, and appear under next tool); asks for line numbers: -n inside a short-option'
    ' cluster or --line-number (rg: unless -N).',
    'Q2 is decided on the point share (at most 5%), not on an interval bound; its interval is printed beside it.'
    ' It uses the states complete for S and S0, with the 40-state floor and the 20-read condition both applied.',
    'Pooled estimands: Y1, Y2 and C pool the replays of the states in a resample (C = Y1 count / Y2 count); a'
    ' resample with no read in an arm gives an undefined C and is left out (count printed when non-zero).',
    'Bootstrap: Python random.Random(15151); 2,000 resamples of states (and, separately, of tasks with all their'
    ' states); percentile interval by linear interpolation at 2.5% and 97.5%. When the Q1/Q2 and Q3 state sets are'
    ' the same, the same resamples serve both. R uses the Q3 resamples; a resample with a denominator not above 0 is'
    ' left out and counted.',
    'Q3c wording below two thirds is not given by the registration; the script then says the condition is not met.',
    'Descriptive counts use every usable replay of every state (not only complete states). The split by line 150 is'
    ' printed two ways: reads of a hit file by the nearest hit of the file read, and Y1 by states whose every hit'
    ' file has its first hit past line 150.',
]


def info_hits(info, usable, o):
    """The hit lines of the hit file the replay read."""
    return o['_hits']


def one_written(cmd, task):
    """The single repository file as the command wrote it."""
    for seg in segments(cmd):
        name, rest = prog(seg)
        for t in operands(rest):
            if repo_file(task, t):
                return t
    return '?'


def finish(L, no_write):
    text = '\n'.join(L) + '\n'
    sys.stdout.write(text)
    if not no_write:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
