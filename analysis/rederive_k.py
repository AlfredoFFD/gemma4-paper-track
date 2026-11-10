"""Independent re-derivation of experiment E (pre-registration 06, navigation horizon) from the raw replay rows.

Usage: py -I -X utf8 analysis/rederive_k.py <run_dir> [--out analysis/results/rederive_k.txt]

<run_dir> holds results_k.jsonl. The report is printed and written to --out.

Independence: only the frozen scorer (fork_states.touches / valid_call / shell_view_range / norm_path) and the file
reader (nodes.file_text, for line lengths and the character caps) are imported. Loading, usable replays, interface
failures, complete states, the gold-patch parser (gold files, created versus modified, changed regions), target
files, Yfile, Yline, the bootstrap, the contrasts and the verdicts are written here from the pre-registration text.
Population membership and seeds come from analysis/fork_states_k/population.json; its stored gold files and regions
are never used for scoring, only compared with this script's own parse.
"""
import argparse
import collections
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from fork_states import norm_path, touches, valid_call  # noqa: E402  frozen scorer (touches calls shell_view_range)
import nodes as N  # noqa: E402  file contents for line lengths and the character caps

ARMS = ['A', 'H', 'E', 'RE']
POPS = ['R', 'U']
KNOWN_TOOLS = {'read_file', 'edit_file', 'write_file', 'run_command', 'get_code_neighbors', 'search_similar_code',
               'get_code_subgraph', 'get_status', 'submit_patch'}
GRAPH_TOOLS = {'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
EXPECTED_ARGS = {'read_file': {'filepath', 'start_line', 'end_line'}, 'run_command': {'command'},
                 'edit_file': {'filepath', 'old_string', 'new_string'}, 'write_file': {'filepath', 'content'},
                 'get_code_neighbors': {'node'}, 'search_similar_code': {'query', 'top_k', 'k'},
                 'get_code_subgraph': {'nodes', 'depth'}, 'get_status': set(), 'submit_patch': set()}
NB = 2000
NO_NODE = '\x00no-node\x00'  # target files have no node: a short name that can never appear in a command
FROZEN_MD5 = {'data/tasks.jsonl': 'b3d40066102b495a9f5b0bcfe494a65e',
              'analysis/fork_states_d/states.jsonl': 'd3105df0dc4aa43d7bb0afbdd6123b44',
              'analysis/fork_states_k/population.json': '036df3cef4d68a4a65ed29919a4cd18d'}

AMBIGUITIES = """\
Readings taken where the pre-registration text leaves a choice (so differences from the first implementation can be traced):
  A1 Usable replay. "The first call" is the first call of the first model response; only that call is checked for an
     unknown tool or malformed arguments (frozen fork_states.valid_call). Other calls of the first response are scored
     as they are. Order of kinds when several apply: error, no call, unknown tool, malformed.
  A2 Error rows. Any row with a non-empty error field (or stop 'error') is an error, whatever step it happened at. The
     step is reported as the model call that failed = number of recorded steps + 1. Timeouts without an error field are
     not errors.
  A3 Duplicate rows for one (state, arm, seed): the runner retries errored replays on a rerun. Raw counts use every
     row. For scoring, the first row without an error is used; if every row has an error, the key is an error.
  A4 Yfile, read_file: an executed read_file whose result status is 'ok' and whose filepath argument, after the frozen
     norm_path, equals a target file.
  A5 Yfile, shell: an executed run_command with non-empty output that the frozen touches() scores as 'read' for the
     target {path: file, start: 1, end: None} with no node (a short name that never matches, so a grep stage never
     counts) and the file's line lengths from nodes.file_text. "Non-empty output" = the stdout string has length > 0,
     taken from result.stdout, or from result.details.stdout when the command returned an error status (a non-zero
     exit code still shows its stdout to the model). stderr is not output.
  A6 Yfile, stopping call: the first call of the replay recorded with executed = false (the call that stopped it), if
     its tool is edit_file or write_file and its filepath (norm_path) is a target file. Its arguments are not checked
     with valid_call (the text says only "an edit_file or write_file on a target file"); the count of malformed ones
     is reported.
  A7 Yline, read_file: the returned range is the result's start_line and end_line fields (the replay keeps them).
     When those fields are missing, the range is start_line plus the content line count. The count of reads where
     end_line - start_line + 1 differs from content_lines is reported, with Yline under the content-derived range.
  A8 Yline, shell: also requires non-empty output (as A5), and a single-file view. Overlap is decided by the frozen
     touches() with the changed region as the target span (so the 5,000-character cap and the pipeline range are the
     frozen scorer's).
  A9 "Single-file shell view", primary (most literal) reading: in the pipeline stage the frozen scorer takes as the
     source (the first stage whose command word is a view command and that names the file), the file operands, after
     removing options, option arguments (head/tail -n N, -c N; sed's script), and redirections, are exactly the one
     target file; no recursive flag; and no later stage names a file of its own. Stricter: additionally the command is
     one simple command (no '|', ';', '&&', '||'). Looser: no single-file check (any frozen-scorer range counts).
  A10 Changed regions: one region per hunk, from the smallest to the largest old-file line among its removed lines and
     the insertion points (old line before and after an insertion run that does not directly follow a removed line).
     "\\ No newline" lines are ignored. An insertion before line 1 is clipped to line 1; an insertion after the last
     line keeps the line number after the last line. A hunk header with old count 0 inserts after its old start line.
  A11 Gold file paths: the '--- a/' path for modified (and deleted) files, the '+++ b/' path for created files; a file
     is created when every hunk of it has old range -0,0. Target files: modified gold files not in shown_files.
  A12 Listed-entry touches: every executed call plus the stopping call, scored with frozen touches(); 'read' or 'edit'
     count, 'graph' never. Reported for all true neighbors, unshown true neighbors, and rewired entries, in every arm.
  A13 First-call index: the 1-based index of the model response holding the first call that meets the outcome.
  A14 Bootstrap: clusters resampled with replacement, numpy default_rng(0) reseeded for each interval, 2,000
     resamples; the statistic is the pooled rate (sum over resampled clusters / count); contrasts resample the same
     clusters for both arms; 95% interval = numpy percentiles 2.5 and 97.5 (linear interpolation).
"""

OUT = []


def out(s=''):
    OUT.append(s)
    print(s)


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rel(p):
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return '<outside the repository>/' + p.name


# ---------------------------------------------------------------- gold patch parser (own code, from the Design text)

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _patch_path(s):
    p = s.split('\t')[0].strip()
    if p == '/dev/null':
        return None
    if p.startswith('a/') or p.startswith('b/'):
        p = p[2:]
    return p


def parse_gold(patch):
    """{path: {'created': bool, 'regions': [(a, b), ...]}} plus a count of clipped insertion points."""
    files = {}
    clipped = 0
    lines = patch.split('\n')
    i = 0
    cur = None
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            old, new = _patch_path(ln[4:]), _patch_path(lines[i + 1][4:])
            key = old if old is not None else new
            cur = files.setdefault(key, {'hunks': [], 'old': old, 'new': new})
            i += 2
            continue
        m = HUNK.match(ln)
        if m and cur is not None:
            os_, oc = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
            ns, nc = int(m.group(3)), int(m.group(4)) if m.group(4) is not None else 1
            old_ln = os_ if oc > 0 else os_ + 1  # with count 0 the start names the line the insertion follows
            o_seen = n_seen = 0
            prev = None
            points = []
            hunk_clipped = 0
            i += 1
            while i < len(lines) and (o_seen < oc or n_seen < nc):
                b = lines[i]
                tag = b[:1]
                if tag == '\\':
                    i += 1
                    continue
                if tag == '-':
                    points.append(old_ln)
                    old_ln += 1
                    o_seen += 1
                    prev = '-'
                elif tag == '+':
                    if prev not in ('-', '+'):  # an insertion run not directly after a removed line
                        lo, hi = old_ln - 1, old_ln
                        if lo < 1:
                            lo = 1
                            hunk_clipped += 1
                        points += [lo, hi]
                    n_seen += 1
                    prev = '+'
                else:  # context (a blank line inside the counts is context too)
                    old_ln += 1
                    o_seen += 1
                    n_seen += 1
                    prev = ' '
                i += 1
            cur['hunks'].append({'old': (os_, oc), 'new': (ns, nc), 'clipped': hunk_clipped,
                                 'region': (min(points), max(points)) if points else None})
            continue
        i += 1
    res = {}
    for key, f in files.items():
        created = bool(f['hunks']) and all(h['old'] == (0, 0) for h in f['hunks'])
        path = f['new'] if created and f['new'] else key
        regs = [h['region'] for h in f['hunks'] if h['region'] is not None]
        if not created:
            clipped += sum(h['clipped'] for h in f['hunks'])
        res[path] = {'created': created, 'regions': regs, 'renamed': f['old'] is not None and f['new'] is not None
                     and f['old'] != f['new'], 'deleted': f['new'] is None}
    return res, clipped


# ---------------------------------------------------------------- shell helpers (own code: single-file reading)

VIEW = {'cat', 'sed', 'head', 'tail', 'grep', 'rg', 'less', 'more', 'awk'}  # the frozen scorer's view commands
REDIR_TOKEN = re.compile(r'^(\d*>>?|&>|\d*<|>&|\d*>&\d*)(\S*)$')


def _toks(stage):
    try:
        return shlex.split(stage)
    except ValueError:
        return stage.split()


def _drop_redirections(toks):
    outl, i = [], 0
    while i < len(toks):
        t = toks[i]
        m = REDIR_TOKEN.match(t)
        if m:
            if not m.group(2) and not t.endswith('&1') and i + 1 < len(toks):
                i += 1  # '>' '/dev/null' as two tokens
            i += 1
            continue
        outl.append(t)
        i += 1
    return outl


def file_operands(toks):
    """(operands, recursive) of one simple command: the words that name files, for the view commands."""
    toks = _drop_redirections(toks)
    if not toks:
        return [], False
    prog, rest = toks[0], toks[1:]
    ops, recursive = [], False
    script_needed = prog in ('sed', 'awk', 'grep', 'rg')
    takes_arg = {'head': {'-n', '-c', '--lines', '--bytes'}, 'tail': {'-n', '-c', '--lines', '--bytes'},
                 'sed': {'-e', '-f', '--expression', '--file'}, 'awk': {'-F', '-v', '-f'},
                 'grep': {'-e', '-f', '-m', '-A', '-B', '-C', '--max-count'},
                 'rg': {'-e', '-f', '-m', '-A', '-B', '-C', '-g', '-t', '-T', '--glob', '--type'}}.get(prog, set())
    i = 0
    end_opts = False
    while i < len(rest):
        t = rest[i]
        if not end_opts and t == '--':
            end_opts = True
        elif not end_opts and t.startswith('-') and t != '-':
            if prog in ('grep', 'rg') and (t in ('-r', '-R', '--recursive') or (not t.startswith('--') and ('r' in t[1:] or 'R' in t[1:]))):
                recursive = True
            if t in takes_arg:
                if prog in ('sed', 'awk', 'grep', 'rg') and t in ('-e', '-f', '--expression', '--file'):
                    script_needed = False
                i += 1
        elif script_needed:
            script_needed = False  # sed script, awk program, grep pattern
        else:
            ops.append(t)
        i += 1
    if prog == 'rg':
        recursive = True  # rg searches directories recursively by default
    return ops, recursive


def single_file_view(cmd, path, strict=False):
    """Primary (literal) and stricter readings of 'single-file shell view' for one target path."""
    stages = [s.strip() for s in cmd.split('|') if s.strip()]  # the frozen scorer's split
    toks_of = [_toks(s) for s in stages]
    src = None
    for i, t in enumerate(toks_of):
        if t and t[0] in VIEW and any(norm_path(x) == path for x in t[1:]):
            src = i
            break
    if src is None:
        return False
    ops, recursive = file_operands(toks_of[src])
    if recursive or len(ops) != 1 or norm_path(ops[0]) != path:
        return False
    for t in toks_of[src + 1:]:
        if t and t[0] in VIEW and file_operands(t)[0]:
            return False  # a later stage shows a file of its own
    if strict and (len(stages) > 1 or re.search(r';|&&|\|\|', cmd)):
        return False
    return True


def shell_stdout(res):
    if not isinstance(res, dict):
        return None, None
    if 'stdout' in res:
        return res.get('stdout'), res.get('status')
    d = res.get('details')
    if isinstance(d, dict) and 'stdout' in d:
        return d.get('stdout'), res.get('status')
    return None, res.get('status')


# ---------------------------------------------------------------- arguments

ap = argparse.ArgumentParser()
ap.add_argument('run_dir')
ap.add_argument('--out', default=str(ROOT / 'analysis' / 'results' / 'rederive_k.txt'))
cli = ap.parse_args()
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
run_dir = Path(cli.run_dir)
res_path = run_dir / 'results_k.jsonl'

# ---------------------------------------------------------------- load inputs
tasks = {}
for l in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8'):
    t = json.loads(l)
    tasks[t['instance_id']] = t
states = {}
for l in open(HERE / 'fork_states_d' / 'states.jsonl', encoding='utf-8'):
    s = json.loads(l)
    s.pop('steps', None)
    s.pop('arms', None)
    states[(s['task'], s['run'], s.get('fork', 0))] = s
pop = json.load(open(HERE / 'fork_states_k' / 'population.json', encoding='utf-8'))
member = {}
for p in POPS:
    for r in pop[p]:
        member[tuple(r['key'])] = (p, list(r['seeds']))
rows = [json.loads(l) for l in open(res_path, encoding='utf-8') if l.strip()]

gold = {}
clipped_total = 0
for tid, t in tasks.items():
    g, c = parse_gold(t.get('patch') or '')
    gold[tid] = g
    clipped_total += c


def modified_files(task):
    return {f: v['regions'] for f, v in gold.get(task, {}).items() if not v['created']}


def created_files(task):
    return sorted(f for f, v in gold.get(task, {}).items() if v['created'])


def targets_of(key):
    s = states[key]
    shown = set(s['shown_files'])
    return {f: regs for f, regs in modified_files(key[0]).items() if f not in shown}


_ll = {}


def line_lengths(task, path):
    if (task, path) not in _ll:
        txt = N.file_text(task, path)
        _ll[(task, path)] = [len(x) for x in txt.splitlines()] if txt is not None else None
    return _ll[(task, path)]


# ---------------------------------------------------------------- header
out('Independent re-derivation of experiment E (pre-registration 06), blind to analysis/analyze_k.py.')
out(f'Run file: {rel(res_path)} (md5 {md5(res_path)}), {len(rows)} rows.')
for f, want in FROZEN_MD5.items():
    got = md5(ROOT / f)
    out(f'Input {f}: md5 {got} {"matches the frozen value" if got == want else "DIFFERS from the frozen value " + want}')
vals = lambda k: dict(collections.Counter(str(r.get(k)) for r in rows))  # noqa: E731
out(f'Row metadata: harness_variant {vals("harness_variant")}; locale {vals("locale")}; fake_model {vals("fake_model")}; k {vals("k")}')
out()
for line in AMBIGUITIES.splitlines():
    out(line)
out()

# ---------------------------------------------------------------- S0: gold patch check against population.json
out('S0. Gold patch parse (own parser) versus the regions stored in population.json (not used for scoring)')
out(f'  tasks parsed: {len(gold)}; insertion points clipped to line 1: {clipped_total}; '
    f'renamed files: {sum(v["renamed"] for g in gold.values() for v in g.values())}; '
    f'deleted files: {sum(v["deleted"] for g in gold.values() for v in g.values())}')
dis = collections.Counter()
dis_examples = []
task_seen = set()
for p in POPS:
    for r in pop[p]:
        key = tuple(r['key'])
        task = key[0]
        mine_mod = {f: sorted(tuple(x) for x in regs) for f, regs in modified_files(task).items()}
        theirs_mod = {f: sorted(tuple(x) for x in regs) for f, regs in r['gold_files'].items()}
        if task not in task_seen:
            task_seen.add(task)
            if set(mine_mod) != set(theirs_mod):
                dis['modified file set'] += 1
                dis_examples.append((task, 'modified files', sorted(set(mine_mod) ^ set(theirs_mod))))
            for f in set(mine_mod) & set(theirs_mod):
                if mine_mod[f] != theirs_mod[f]:
                    dis['regions of a file'] += 1
                    dis_examples.append((task, f, {'mine': mine_mod[f], 'population.json': theirs_mod[f]}))
            if created_files(task) != sorted(r['created_files']):
                dis['created file set'] += 1
                dis_examples.append((task, 'created files', {'mine': created_files(task), 'population.json': r['created_files']}))
        if key not in states:
            dis['state missing from states.jsonl'] += 1
            continue
        if sorted(targets_of(key)) != sorted(r['unopened_gold_files']):
            dis['target (unopened modified) files'] += 1
            dis_examples.append((key, 'targets', {'mine': sorted(targets_of(key)), 'population.json': r['unopened_gold_files']}))
        s = states[key]
        listed = sorted(n for n in s['unshown_true_neighbors'] if (s['neighbor_spans'].get(n) or {}).get('path') in mine_mod)
        if listed != sorted(r['listed_true_in_gold_files']):
            dis['unshown true entries in modified files'] += 1
            dis_examples.append((key, 'listed_true_in_gold_files', {'mine': listed, 'population.json': r['listed_true_in_gold_files']}))
# membership re-derived over all states
my_R, my_U = set(), set()
for key, s in states.items():
    mod = modified_files(key[0])
    if any((s['neighbor_spans'].get(n) or {}).get('path') in mod for n in s['unshown_true_neighbors']):
        my_R.add(key)
    elif targets_of(key):
        my_U.add(key)
pop_R = {tuple(r['key']) for r in pop['R']}
pop_U = {tuple(r['key']) for r in pop['U']}
out(f'  tasks compared: {len(task_seen)}; disagreements: {dict(dis) if dis else "none"}')
for ex in dis_examples[:20]:
    out(f'    {ex}')
out(f'  re-derived populations over all {len(states)} states: R {len(my_R)} (tasks {len({k[0] for k in my_R})}), '
    f'U {len(my_U)} (tasks {len({k[0] for k in my_U})}); population.json: R {len(pop_R)} (tasks {len({k[0] for k in pop_R})}), '
    f'U {len(pop_U)} (tasks {len({k[0] for k in pop_U})})')
out(f'  membership differences: R only mine {sorted(my_R - pop_R)[:10]}, R only population.json {sorted(pop_R - my_R)[:10]}, '
    f'U only mine {sorted(my_U - pop_U)[:10]}, U only population.json {sorted(pop_U - my_U)[:10]}')
out(f'  seeds in population.json: {pop.get("seeds")}')
no_text = sorted({(k[0], f) for k in pop_R | pop_U if k in states for f in targets_of(k) if line_lengths(k[0], f) is None})
out(f'  target files without text from nodes.file_text (character caps not applied to shell views): {len(no_text)} {no_text[:8]}')
out()

# ---------------------------------------------------------------- S1: raw rows, interface failures


def failure(r):
    if r.get('error') or r.get('stop') == 'error':
        return 'error'
    steps = r.get('steps') or []
    if not steps or not steps[0].get('calls'):
        return 'no_call'
    c = steps[0]['calls'][0]
    if c.get('function_name') not in KNOWN_TOOLS:
        return 'unknown_tool'
    if not valid_call(c):
        return 'malformed'
    return None


def first_response_usable(r):
    """Sensitivity (a): the first response has a call the frozen rule accepts, whatever happened later."""
    steps = r.get('steps') or []
    if not steps or not steps[0].get('calls'):
        return False
    c = steps[0]['calls'][0]
    return c.get('function_name') in KNOWN_TOOLS and valid_call(c)


out('S1. Rows, interface failures and usable replays (raw rows)')
pop_of_row = collections.Counter()
mismatch_pop, not_member, bad_seed = 0, 0, 0
for r in rows:
    key = (r['task'], r['run'], r.get('fork', 0))
    m = member.get(key)
    if m is None:
        not_member += 1
        continue
    if r.get('population') != m[0]:
        mismatch_pop += 1
    if r['seed'] not in m[1]:
        bad_seed += 1
    pop_of_row[(m[0], r['arm'])] += 1
out('  rows by population and arm: ' + '; '.join(f'{p}: ' + ', '.join(f'{a} {pop_of_row[(p, a)]}' for a in ARMS) for p in POPS))
out(f'  rows of states outside population.json: {not_member}; rows whose population field disagrees with population.json: '
    f'{mismatch_pop}; rows with a seed outside the population\'s seeds: {bad_seed}; arms seen: {sorted({r["arm"] for r in rows})}')
keycount = collections.Counter((r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed']) for r in rows)
out(f'  (state, arm, seed) keys: {len(keycount)}; keys with more than one row: {sum(v > 1 for v in keycount.values())}')
fail_kind = collections.Counter()
err_detail = collections.Counter()
for r in rows:
    k = failure(r)
    fail_kind[(r['arm'], k)] += 1
    if k == 'error':
        etype = (r.get('error') or 'stop=error').split(':', 1)[0]
        err_detail[(r['arm'], etype, len(r.get('steps') or []) + 1)] += 1
out('  interface failures by arm (raw rows):')
for a in ARMS:
    n = sum(v for (aa, _), v in fail_kind.items() if aa == a)
    parts = ', '.join(f'{k} {fail_kind[(a, k)]}' for k in ('error', 'no_call', 'unknown_tool', 'malformed'))
    out(f'    {a:3s} rows {n}: {parts}; usable {fail_kind[(a, None)]}')
out('  errors by arm, type and the model call at which they happened (= recorded steps + 1):')
for (a, et, st), v in sorted(err_detail.items()):
    out(f'    {a:3s} {et} at model call {st}: {v}')
first_bad = collections.Counter()
for r in rows:
    k = failure(r)
    if k in ('unknown_tool', 'malformed'):
        c = r['steps'][0]['calls'][0]
        first_bad[(k, c.get('function_name'), tuple(sorted(c.get('arguments') or {})) if isinstance(c.get('arguments'), dict) else 'non-dict')] += 1
for (k, fn, ks), v in sorted(first_bad.items(), key=lambda x: -x[1]):
    out(f'    first-call {k}: {fn} {ks}: {v}')

# pick one row per key (A3)
by_key = collections.defaultdict(list)
for r in rows:
    by_key[(r['task'], r['run'], r.get('fork', 0), r['arm'], r['seed'])].append(r)


def chosen(rs):
    ok = [r for r in rs if not (r.get('error') or r.get('stop') == 'error')]
    return ok[0] if ok else rs[-1]


final = {k: chosen(v) for k, v in by_key.items()}
retried = sum(1 for v in by_key.values() if len(v) > 1 and any(not (r.get('error') or r.get('stop') == 'error') for r in v))
out(f'  keys whose error row was followed by a successful retry (the retry is scored): {retried}')
fk_final = collections.Counter((k[3], failure(r)) for k, r in final.items())
out('  after choosing one row per key: ' + '; '.join(
    f'{a} usable {fk_final[(a, None)]} of {sum(v for (aa, _), v in fk_final.items() if aa == a)}' for a in ARMS))
out()

# ---------------------------------------------------------------- S1b: argument names
out('S1b. Argument names that differ from the tool declarations (all calls, raw rows)')
odd = collections.Counter()
odd_accept = collections.Counter()
for r in rows:
    for si, st in enumerate(r.get('steps') or []):
        for ci, c in enumerate(st.get('calls') or []):
            fn = c.get('function_name')
            a = c.get('arguments')
            if not isinstance(a, dict):
                odd[(fn, 'non-dict arguments')] += 1
                continue
            extra = set(a) - EXPECTED_ARGS.get(fn, set())
            if fn in EXPECTED_ARGS and extra:
                tag = tuple(sorted(x if len(x) < 40 else x[:37] + '...' for x in extra))
                odd[(fn, tag)] += 1
                odd_accept[(fn, 'first call' if si == 0 and ci == 0 else 'later call', valid_call(c))] += 1
for (fn, tag), v in odd.most_common(15):
    out(f'  {fn}: unexpected keys {tag}: {v}')
for (fn, pos, ok), v in sorted(odd_accept.items()):
    out(f'    {fn} {pos}, frozen valid_call {"accepts" if ok else "rejects"}: {v}')
path_odd = collections.Counter()
for r in rows:
    for st in r.get('steps') or []:
        for c in st.get('calls') or []:
            fp = (c.get('arguments') or {}).get('filepath') if isinstance(c.get('arguments'), dict) else None
            if isinstance(fp, str) and re.search(r'[`,:]|start_line|end_line', fp):
                path_odd[(c.get('function_name'), c.get('executed'), (c.get('result') or {}).get('status'))] += 1
out(f'  filepath arguments carrying other arguments inside the string (backtick, comma, start_line...): {dict(path_odd)}')
out()

# ---------------------------------------------------------------- scoring of one replay
paths_used = collections.Counter()
diag = collections.Counter()


def score(r, key):
    task = key[0]
    s = states[key]
    tg = targets_of(key)
    steps = r.get('steps') or []
    res = {'yfile': False, 'yline': False, 'yline_strict': False, 'yline_loose': False, 'yline_content': False,
           'yfile_okonly': False, 'f_file': None, 'f_line': None, 'executed': 0, 'model_calls': len(steps),
           'stop': r.get('stop'), 'touch_true': False, 'touch_unshown': False, 'touch_rew': False}
    unshown = set(s['unshown_true_neighbors'])
    nb = [(n, sp) for n, sp in s['neighbor_spans'].items() if sp and n in set(s['true_neighbors'])]
    rw = [(n, sp) for n, sp in (s.get('rewired_spans') or {}).items() if sp and n in set(s.get('rewired_entries') or [])]
    stop_seen = False

    def mark(field, first, idx):
        if not res[field]:
            res[field] = True
            if first and res[first] is None:
                res[first] = idx

    def listed_touch(c):
        if c.get('function_name') in GRAPH_TOOLS:
            return
        cmd = str((c.get('arguments') or {}).get('command', '')) if c.get('function_name') == 'run_command' else None
        for group, field in ((nb, 'touch_true'), (rw, 'touch_rew')):
            for n, sp in group:
                if cmd is not None and sp['path'] not in cmd:
                    continue  # a shell view must name the file (frozen scorer: a token equal to the path)
                v = touches(c, sp, n, line_lengths=line_lengths(task, sp['path']))
                if v in ('read', 'edit'):
                    res[field] = True
                    if field == 'touch_true' and n in unshown:
                        res['touch_unshown'] = True

    for idx, st in enumerate(steps, 1):
        for c in st.get('calls') or []:
            fn = c.get('function_name')
            args = c.get('arguments') if isinstance(c.get('arguments'), dict) else {}
            if not c.get('executed'):
                if not stop_seen:
                    stop_seen = True
                    listed_touch(c)
                    if fn in ('edit_file', 'write_file') and isinstance(args.get('filepath'), str) \
                            and norm_path(args['filepath']) in tg:
                        if not res['yfile']:
                            paths_used['Yfile first reached by the stopping edit/write'] += 1
                        mark('yfile', 'f_file', idx)
                        res['yfile_okonly'] = True
                        diag[f'stopping {fn} on a target file' + ('' if valid_call(c) else ' (malformed)')] += 1
                continue
            res['executed'] += 1
            listed_touch(c)
            rr = c.get('result')
            if rr is None:
                diag['executed call with no recorded result'] += 1
                continue
            if fn == 'read_file':
                if not isinstance(rr, dict) or rr.get('status') != 'ok':
                    continue
                p = norm_path(args.get('filepath'))
                if p not in tg:
                    continue
                if isinstance(rr.get('filepath'), str) and norm_path(rr['filepath']) != p:
                    diag['read_file result filepath differs from the argument'] += 1
                if not res['yfile']:
                    paths_used['Yfile first reached by read_file'] += 1
                mark('yfile', 'f_file', idx)
                res['yfile_okonly'] = True
                a0 = rr.get('start_line')
                b0 = rr.get('end_line')
                nl = rr.get('content_lines')
                if isinstance(a0, int) and isinstance(b0, int):
                    a, b = a0, b0
                else:
                    diag['read_file ok without start_line/end_line in its result'] += 1
                    a = a0 if isinstance(a0, int) else 1
                    b = a + (nl or 1) - 1
                ac, bc = a, (a + nl - 1 if isinstance(nl, int) and nl > 0 else b)
                if (ac, bc) != (a, b):
                    diag['read_file on a target: returned end_line differs from start_line + content_lines - 1'] += 1
                diag['read_file with status ok on a target file (Yfile)'] += 1
                hit = any(not (b < r0 or a > r1) for r0, r1 in tg[p])
                hitc = any(not (bc < r0 or ac > r1) for r0, r1 in tg[p])
                if hit:
                    if not res['yline']:
                        paths_used['Yline first reached by read_file'] += 1
                    mark('yline', 'f_line', idx)
                    res['yline_strict'] = res['yline_loose'] = True
                if hitc:
                    res['yline_content'] = True
            elif fn == 'run_command':
                cmd = str(args.get('command', ''))
                stdout, status = shell_stdout(rr)
                nonempty = isinstance(stdout, str) and len(stdout) > 0
                for f, regs in tg.items():
                    if f not in cmd:
                        continue
                    ll = line_lengths(task, f)
                    if touches(c, {'path': f, 'start': 1, 'end': None}, NO_NODE, line_lengths=ll) != 'read':
                        if re.match(r'\s*(grep|rg)\b', cmd):
                            diag['grep/rg command naming a target file (never a view)'] += 1
                        continue
                    if not nonempty:
                        diag['frozen-scorer view of a target file with empty output (not counted)'] += 1
                        continue
                    if status != 'ok':
                        diag['frozen-scorer view of a target file with output but an error status (counted)'] += 1
                    else:
                        res['yfile_okonly'] = True
                    if not res['yfile']:
                        paths_used['Yfile first reached by a shell view'] += 1
                    diag['frozen-scorer view of a target file with output (Yfile)'] += 1
                    mark('yfile', 'f_file', idx)
                    over = any(touches(c, {'path': f, 'start': r0, 'end': r1}, NO_NODE, line_lengths=ll) == 'read'
                               for r0, r1 in regs)
                    if not over:
                        continue
                    res['yline_loose'] = True
                    if single_file_view(cmd, f):
                        diag['single-file shell view overlapping a changed region (Yline)'] += 1
                        if not res['yline']:
                            paths_used['Yline first reached by a single-file shell view'] += 1
                        mark('yline', 'f_line', idx)
                        res['yline_content'] = True
                        if single_file_view(cmd, f, strict=True):
                            res['yline_strict'] = True
                    else:
                        diag['shell view overlapping a changed region but not single-file (Yfile only)'] += 1
    return res


# ---------------------------------------------------------------- analysis sets


def build(mode):
    """mode 'primary': usable = no error and a valid first call. mode 'keep_errors': error rows with a usable first
    response are kept and scored on what executed. Returns (recs, complete keys per population)."""
    recs = {}
    for k, r in final.items():
        skey = k[:3]
        if skey not in member or skey not in states:
            continue
        p, seeds = member[skey]
        if k[3] not in ARMS or k[4] not in seeds:
            continue
        ok = failure(r) is None if mode == 'primary' else first_response_usable(r)
        if not ok:
            continue
        recs[k] = r
    complete = {p: [] for p in POPS}
    for skey, (p, seeds) in member.items():
        if all(skey + (a, sd) in recs for a in ARMS for sd in seeds):
            complete[p].append(skey)
    return recs, complete


recs_p, complete_p = build('primary')
paths_used.clear()
diag.clear()
scored = {}
for p in POPS:
    for skey in complete_p[p]:
        for a in ARMS:
            for sd in member[skey][1]:
                k = skey + (a, sd)
                scored[k] = dict(score(recs_p[k], skey), pop=p, state=skey, task=skey[0], arm=a, seed=sd)
partial_ok = len(complete_p['R']) >= 40
LABEL = '' if partial_ok else ' [EXPLORATORY: fewer than 40 complete states of R]'

out('S2. Complete states (every arm and every seed of the population usable)')
for p in POPS:
    ks = complete_p[p]
    out(f'  {p}: {len(ks)} of {len(pop[p])} states complete, {len({k[0] for k in ks})} tasks; '
        f'states with at least one row: {len({k[:3] for k in final if k[:3] in member and member[k[:3]][0] == p})}')
out(f'  partial-run rule (at least 40 complete states of R): {"MET" if partial_ok else "NOT MET: everything below is EXPLORATORY"}')
out(f'  scored replays: {len(scored)}')
out()

# ---------------------------------------------------------------- bootstrap


def _clusters(pairs):
    S, C = collections.defaultdict(float), collections.defaultdict(int)
    for cid, v in pairs:
        S[cid] += v
        C[cid] += 1
    cl = sorted(C)
    return cl, np.array([S[c] for c in cl]), np.array([C[c] for c in cl], dtype=float)


def boot_rate(pairs):
    cl, s, n = _clusters(pairs)
    if not cl:
        return None
    idx = np.random.default_rng(0).integers(0, len(cl), size=(NB, len(cl)))
    b = s[idx].sum(1) / n[idx].sum(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return 100 * s.sum() / n.sum(), 100 * lo, 100 * hi, int(s.sum()), int(n.sum()), len(cl)


def boot_diff(pa, pb):
    ca, sa, na = _clusters(pa)
    cb, sb, nb_ = _clusters(pb)
    if not ca or ca != cb:
        return None
    idx = np.random.default_rng(0).integers(0, len(ca), size=(NB, len(ca)))
    b = sa[idx].sum(1) / na[idx].sum(1) - sb[idx].sum(1) / nb_[idx].sum(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return 100 * (sa.sum() / na.sum() - sb.sum() / nb_.sum()), 100 * lo, 100 * hi, len(ca)


def pairs(sc, p, arm, field, by='state'):
    return [(v[by], float(v[field])) for v in sc.values() if v['pop'] == p and v['arm'] == arm]


def fmt_rate(t):
    if t is None:
        return 'n/a (no complete state)'
    return f'{t[0]:6.2f}% ({t[3]}/{t[4]}) [{t[1]:.2f}, {t[2]:.2f}]'


def fmt_diff(t):
    if t is None:
        return 'n/a'
    return f'{t[0]:+6.2f} [{t[1]:+.2f}, {t[2]:+.2f}] ({t[3]} clusters)'


out(f'S3. Rates per population and arm (percent of replays, raw counts, 95% bootstrap clustered by state){LABEL}')
for p in POPS:
    for field, lab in (('yline', 'Yline'), ('yfile', 'Yfile')):
        out(f'  {p} {lab}:')
        for a in ARMS:
            out(f'    {a:3s} {fmt_rate(boot_rate(pairs(scored, p, a, field)))}')
out()

CONTRASTS = [('E', 'H'), ('E', 'A'), ('H', 'A'), ('RE', 'A')]
out(f'S4. Contrasts (percentage points, paired by state, 95% bootstrap clustered by state){LABEL}')
for p in POPS:
    for field, lab in (('yline', 'Yline'), ('yfile', 'Yfile')):
        for a, b in CONTRASTS:
            out(f'  {p} {lab} {a} - {b}: {fmt_diff(boot_diff(pairs(scored, p, a, field), pairs(scored, p, b, field)))}')
out()


def k1(sc, field='yline'):
    by_state = boot_diff(pairs(sc, 'R', 'E', field), pairs(sc, 'R', 'H', field))
    by_task = boot_diff(pairs(sc, 'R', 'E', field, 'task'), pairs(sc, 'R', 'H', field, 'task'))
    return by_state, by_task


def k1_verdict(by_state, by_task):
    if by_state is None:
        return 'not computable (no complete state of R)'
    v = ('The legible list brings the agent to fix code within five calls' if by_state[1] > 0
         else 'no detectable gain')
    robust = by_task is not None and by_state[1] > 0 and by_task[1] > 0
    if by_state[1] > 0:
        v += '; robust (lower bound above 0 under both clusterings)' if robust else '; not robust (the by-task lower bound is not above 0)'
    return v


def k2(sc, field='yfile'):
    return boot_diff(pairs(sc, 'U', 'E', field), pairs(sc, 'U', 'A', field))


def k2_verdict(d):
    if d is None:
        return 'not computable (no complete state of U)'
    return 'The list delays reaching the fix' if d[2] < 0 else 'no harm is claimed'


bs, bt = k1(scored)
d2 = k2(scored)
out(f'Rules{LABEL}')
out(f'  K1 (E - H on Yline in R), clustered by state: {fmt_diff(bs)}')
out(f'  K1 clustered by task:                        {fmt_diff(bt)}')
out(f'  K1 verdict: {k1_verdict(bs, bt)}')
out(f'  K2 (E - A on Yfile in U), clustered by state: {fmt_diff(d2)}')
out(f'  K2 verdict: {k2_verdict(d2)}')
out()

# ---------------------------------------------------------------- S5 descriptive
out(f'S5. Descriptive (no rule){LABEL}')
for p in POPS:
    out(f'  {p}: stop reasons, share of replays by arm')
    for a in ARMS:
        vs = [v for v in scored.values() if v['pop'] == p and v['arm'] == a]
        c = collections.Counter(v['stop'] for v in vs)
        out(f'    {a:3s} n={len(vs)}: ' + ', '.join(f'{k} {100 * n / len(vs):.1f}%' for k, n in c.most_common()) if vs else f'    {a:3s} n=0')
    out(f'  {p}: mean executed calls and mean model calls by arm')
    for a in ARMS:
        vs = [v for v in scored.values() if v['pop'] == p and v['arm'] == a]
        if vs:
            out(f'    {a:3s} executed {np.mean([v["executed"] for v in vs]):.2f}, model calls {np.mean([v["model_calls"] for v in vs]):.2f}')
    for f, lab in (('f_file', 'Yfile'), ('f_line', 'Yline')):
        out(f'  {p}: index of the first model call with {lab} (counts 1..5, never)')
        for a in ARMS:
            vs = [v for v in scored.values() if v['pop'] == p and v['arm'] == a]
            c = collections.Counter(v[f] for v in vs)
            out(f'    {a:3s} ' + ', '.join(f'{i}: {c[i]}' for i in range(1, 6)) + f', never: {c[None]}')
    out(f'  {p}: share of replays where any executed or stopping call touches (frozen touches, read or edit; graph calls never count)')
    for a in ARMS:
        vs = [v for v in scored.values() if v['pop'] == p and v['arm'] == a]
        if vs:
            out(f'    {a:3s} a true entry {100 * np.mean([v["touch_true"] for v in vs]):.1f}%, '
                f'an unshown true entry {100 * np.mean([v["touch_unshown"] for v in vs]):.1f}%, '
                f'a rewired entry {100 * np.mean([v["touch_rew"] for v in vs]):.1f}%')
out('  (A, H and E show no rewired list and A shows no list at all: those shares are base rates for the same nodes.)')
out()

# ---------------------------------------------------------------- S6 structural counts
out('S6. Code paths (scored replays; structural, no arm split)')
for k, v in sorted(paths_used.items()):
    out(f'  {k}: {v} replays')
for k, v in sorted(diag.items()):
    out(f'  {k}: {v} calls')
allc = collections.Counter()
for k, v in scored.items():
    r = recs_p[k]
    for st in r.get('steps') or []:
        for c in st.get('calls') or []:
            allc[(c.get('function_name'), bool(c.get('executed')))] += 1
out('  calls in scored replays (tool, executed): ' + ', '.join(f'{a}/{b}: {n}' for (a, b), n in sorted(allc.items())))
mis = sum(1 for k in scored if recs_p[k].get('executed_calls') is not None
          and recs_p[k]['executed_calls'] != scored[k]['executed'])
out(f'  rows whose executed_calls field differs from the recount of executed flags: {mis}')
bad_stop = 0
for k in scored:
    r = recs_p[k]
    st = r.get('stop') or ''
    first_unexec = next((c for s_ in r.get('steps') or [] for c in s_.get('calls') or [] if not c.get('executed')), None)
    if st.startswith('stop_call:') and (first_unexec is None or first_unexec.get('function_name') != st.split(':', 1)[1]):
        bad_stop += 1
    if not st.startswith('stop_call:') and first_unexec is not None:
        bad_stop += 1
out(f'  rows whose stop reason disagrees with the first non-executed call: {bad_stop}')
multi = sum(1 for k in scored for s_ in recs_p[k].get('steps') or [] if len(s_.get('calls') or []) > 1)
out(f'  model responses with more than one call: {multi}')
out()

# ---------------------------------------------------------------- S7 sensitivity
out('S7. Sensitivity checks (EXPLORATORY)')
recs_e, complete_e = build('keep_errors')
paths_used.clear()
diag.clear()
scored_e = {}
for p in POPS:
    for skey in complete_e[p]:
        for a in ARMS:
            for sd in member[skey][1]:
                k = skey + (a, sd)
                scored_e[k] = dict(score(recs_e[k], skey), pop=p, state=skey, task=skey[0], arm=a, seed=sd)
kept = sum(1 for k in scored_e if failure(recs_e[k]) == 'error')
out(f'  (a) EXPLORATORY: error rows kept when the first response is usable, scored on what executed: complete R '
    f'{len(complete_e["R"])}, U {len(complete_e["U"])}; error rows kept among scored replays: {kept}')
bs_e, bt_e = k1(scored_e)
d2_e = k2(scored_e)
out(f'      K1 by state {fmt_diff(bs_e)}; by task {fmt_diff(bt_e)}; verdict as worded: {k1_verdict(bs_e, bt_e)}')
out(f'      K2 {fmt_diff(d2_e)}; verdict as worded: {k2_verdict(d2_e)}')
out('  (b) EXPLORATORY: K1 under the readings of "single-file shell view" (primary data set)')
for field, lab in (('yline', 'literal (primary)'), ('yline_strict', 'stricter: one simple command, no pipe or list'),
                   ('yline_loose', 'looser: any frozen-scorer range, multi-file included')):
    b1, b2 = k1(scored, field)
    n_hits = sum(v[field] for v in scored.values() if v['pop'] == 'R')
    out(f'      {lab}: R replays with Yline {n_hits}; K1 by state {fmt_diff(b1)}; by task {fmt_diff(b2)}; {k1_verdict(b1, b2)}')
out('  (c) EXPLORATORY: other reading choices')
b1, b2 = k1(scored, 'yline_content')
out(f'      Yline with read_file ranges from start_line + content_lines (A7): R replays with Yline '
    f'{sum(v["yline_content"] for v in scored.values() if v["pop"] == "R")}; K1 by state {fmt_diff(b1)}; by task {fmt_diff(b2)}')
d = k2(scored, 'yfile_okonly')
out(f'      Yfile counting shell output only when the status is ok (A5): U replays with Yfile '
    f'{sum(v["yfile_okonly"] for v in scored.values() if v["pop"] == "U")} (vs {sum(v["yfile"] for v in scored.values() if v["pop"] == "U")}); K2 {fmt_diff(d)}')

outp = Path(cli.out)
outp.parent.mkdir(parents=True, exist_ok=True)
outp.write_text('\n'.join(OUT) + '\n', encoding='utf-8')
print(f'\nwritten: {rel(outp)}')
