"""Export fork-ready states from GraphLoc's public base-arm traces. EXPLORATORY until the pre-registration freezes.

A state is the message history of a real Gemma-4-31B run, cut right after the first tool result that shows file
content, before the agent has edited repository code and before any compaction. For each state the script also
builds the arm payloads: the real get_code_neighbors result for one node already in view (arm P) and the same
list with one neighbor swapped for a decoy (arm P'). Output: analysis/fork_states/<task>_r<run>.json, a summary
CSV, and a states.jsonl bundle for the replay notebook.

Rules (fixed here before any replay ran):
- fork steps: the first MAX_STATES_PER_RUN agent steps whose tool result shows file content (read_file with
  content, or a cat/sed/head/tail/grep/rg/awk command with stdout), before any edit_file, submit_patch, or
  write_file onto an existing repository file and before any compaction (prompt tokens never fell below 70% of the
  previous call), each with a logged prompt of at most MAX_PROMPT tokens at the next call. States from one run are
  not independent; the analysis clusters by task;
- in-view nodes: graph nodes named in the task prompt (traceback frame lines removed, since they name File and
  line) or in any tool result up to the fork (the Oct 1 audit's mention rule: a dotted name, or a short name of
  at least 4 chars shared by at most 5 nodes);
- queried node: an in-view node with 2..50 graph neighbors and a resolvable span that is either inside a file
  range the agent has already opened or named with a dotted path in the issue, ranked by (inside an opened range,
  named in the issue, degree between 2 and 20, higher degree, name). This rule replaced a first version on
  Nov 8, before any replay, after that version chose hub classes named in every issue (the FastAPI class, 50
  neighbors; File and line from traceback frames) for every state;
- the compared entries: the swapped-out true neighbor is chosen with a seeded RNG among true neighbors whose file
  the agent has not opened (preferring one whose file holds no other listed entry); the decoy is a node in a file
  the agent has not opened that holds no listed entry, not a neighbor, not gold, not in view, not a test, with a
  resolvable span, drawn from the swapped-out entry's directory (else the queried node's directory, else the
  package). It takes the swapped-out entry's place and the list is re-sorted, as the harness sorts. Rationale: most
  true neighbors sit in the file just opened, so re-reading it would count as following; both compared entries
  need a new read.
"""
import collections
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nodes as N  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / 'analysis' / 'fork_states'
UNITS = ROOT / 'experiments' / '00-pointer-audit' / 'results' / 'units.csv'

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*')
CONTENT_CMD = re.compile(r'^\s*(cat|sed|head|tail|grep|rg|awk|less|more)\b')
PATH_TOKEN = re.compile(r'[\w./-]+\.py')
SED_RANGE = re.compile(r"sed\s+-n\s+'?(\d+),(\d+)p'?")
TRACEBACK_LINE = re.compile(r'^\s*File ".*", line \d+.*$', re.M)
MAX_AMBIGUITY = 5
MAX_NEIGHBORS = 50
PREFERRED_DEGREE = 20
MAX_STATES_PER_RUN = 3
MAX_FILE_LINES = 150      # harness read_file cap (swegemma/budget.py)
MAX_FILE_CHARS = 10000    # harness read_file cap
MAX_STDOUT_CHARS = 5000   # harness run_command cap
COMPACTION_RATIO = 0.7
MAX_PROMPT = 12500
H_WORDING = 'Code graph note from the harness. get_code_neighbors(node="{node}") returned:\n{json}'


def load_tasks():
    return {json.loads(l)['instance_id']: json.loads(l) for l in open(DATA / 'tasks.jsonl', encoding='utf-8')}


def load_gold():
    gold_ids, gold_paths = collections.defaultdict(set), collections.defaultdict(set)
    for u in csv.DictReader(open(UNITS, encoding='utf-8')):
        gold_paths[u['instance_id']].add(u['path'])
        if u['addressable'] == 'True' and u['graph_id']:
            gold_ids[u['instance_id']].add(u['graph_id'])
    return gold_ids, gold_paths


_graphs = {}


def graph_for(task):
    key = f"{task['repo'].split('/')[1]}_{task['base_commit']}"
    if key not in _graphs:
        g = json.load(open(DATA / 'graphs' / f'{key}.json', encoding='utf-8'))
        ids = [n['id'] for n in g['nodes']]
        nbr = collections.defaultdict(set)
        for e in g['edges']:  # self-loops stay: the harness lists the node itself when it calls itself
            nbr[e['source']].add(e['target'])
            nbr[e['target']].add(e['source'])
        by_short = collections.defaultdict(list)
        for i in ids:
            by_short[i.rsplit('.', 1)[-1]].append(i)
        _graphs[key] = {'key': key, 'ids': ids, 'idset': set(ids), 'nbr': nbr, 'by_short': by_short}
    return _graphs[key]


def harness_neighbors(g, node):
    """What get_code_neighbors returns for the node: out- and in-neighbors, deduplicated, sorted, capped at 50."""
    return sorted(g['nbr'].get(node, set()))[:MAX_NEIGHBORS]


def mentioned(g, text):
    toks = set(IDENT.findall(text))
    dotted = {k for k in toks if '.' in k}
    parts = {p for k in toks for p in k.split('.')}
    found = set()
    for tok in dotted:
        found.update(i for i in g['ids'] if i == tok or i.endswith('.' + tok))
    for p in parts:
        if len(p) >= 4 and not p.startswith('__'):
            cands = g['by_short'].get(p, [])
            if 0 < len(cands) <= MAX_AMBIGUITY:
                found.update(cands)
    return found


def parse_obs(step):
    obs = step.get('observation')
    if not obs:
        return None
    c = obs.get('content')
    if isinstance(c, str):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            return {'raw': c}
    return c


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def visible_range(start, end, line_lengths, max_lines=MAX_FILE_LINES, max_chars=MAX_FILE_CHARS):
    """The lines a harness read actually shows, after its line cap and character cap (rules of read_file)."""
    total = len(line_lengths)
    if total == 0:
        return None
    start = max(start or 1, 1)
    end = min(end if end is not None else total, total)
    if start > end:
        return None
    if max_lines is not None and end - start + 1 > max_lines:
        end = start + max_lines - 1
    if max_chars is not None:
        used = 0
        last = start - 1
        for ln in range(start, end + 1):
            if used >= max_chars:  # this line starts beyond the cut: not shown at all
                break
            last = ln
            used += line_lengths[ln - 1] + 1
        end = last
    return (start, end) if end >= start else None


def shows_content(step):
    """(path, start, end, text) if this step's tool result shows file content, else None.

    The range is what the harness returned, not what was asked: read_file reports its start and end, and the
    content line count tells how many lines survived the character cap; a shell view's range starts at the sed or
    head start (1 for cat) and spans the stdout's line count.
    """
    if not step.get('tool_calls'):
        return None
    tc = step['tool_calls'][0]
    o = parse_obs(step) or {}
    name, args = tc['function_name'], tc['arguments']
    if name == 'read_file' and o.get('status') == 'ok' and o.get('content'):
        start = _int(o.get('start_line')) or _int(args.get('start_line')) or 1
        n = o['content'].count('\n') + 1
        return (args.get('filepath'), start, start + n - 1, o['content'])
    if name == 'run_command' and o.get('status') == 'ok' and o.get('stdout'):
        cmd = str(args.get('command', ''))
        if CONTENT_CMD.match(cmd):
            paths = PATH_TOKEN.findall(cmd)
            m, m1 = SED_RANGE.search(cmd), SED_LINE.search(cmd)
            a = int(m.group(1)) if m else int(m1.group(1)) if m1 else 1
            n = o['stdout'].count('\n') + 1
            first = CONTENT_CMD.match(cmd).group(1)
            if first in ('grep', 'rg', 'awk') or 'tail' in cmd.split('|')[0]:
                return (paths[-1] if paths else None, None, None, o['stdout'])  # lines unknown; names still count
            return (paths[-1] if paths else None, a, a + n - 1, o['stdout'])
    return None


HEAD_N = re.compile(r'\bhead\s+(?:-n\s*|-)(\d+)')
TAIL_N = re.compile(r'\btail\s+(?:-n\s*|-)(\d+)')
SED_LINE = re.compile(r"sed\s+-n\s+'?(\d+)p'?")
INT_LIKE = re.compile(r'^\s*-?\d+\s*$')


def valid_call(call):
    """False for calls whose arguments the harness could not have executed (malformed): they are interface failures."""
    if not call or not isinstance(call.get('arguments'), dict):
        return False
    name, args = call.get('function_name'), call['arguments']
    if name == 'read_file':
        if not isinstance(args.get('filepath'), str) or not args['filepath']:
            return False
        bounds = []
        for k in ('start_line', 'end_line'):
            v = args.get(k)
            if v is None:
                bounds.append(None)
                continue
            if isinstance(v, bool) or not (isinstance(v, int) or (isinstance(v, str) and INT_LIKE.match(v))):
                return False
            iv = int(v)
            if iv < 1:
                return False
            bounds.append(iv)
        if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
            return False
        return True
    if name == 'edit_file':
        return (isinstance(args.get('filepath'), str) and bool(args['filepath'])
                and isinstance(args.get('old_string'), str) and isinstance(args.get('new_string'), str))
    if name == 'write_file':
        return isinstance(args.get('filepath'), str) and bool(args['filepath']) and isinstance(args.get('content'), str)
    if name == 'run_command':
        return isinstance(args.get('command'), str) and bool(args['command'].strip())
    if name == 'get_code_neighbors':
        return isinstance(args.get('node'), str)
    if name == 'search_similar_code':
        return isinstance(args.get('query'), str)
    if name == 'get_code_subgraph':
        return isinstance(args.get('nodes'), (list, str))
    return name in ('get_status', 'submit_patch')


VIEW_CMDS = ('cat', 'sed', 'head', 'tail', 'grep', 'rg', 'less', 'more', 'awk')


def _count_arg(toks, default=10):
    """The N of head/tail: -n N, -nN, -N, --lines=N; else the default."""
    for i, t in enumerate(toks[1:], 1):
        if t in ('-n', '--lines') and i + 1 < len(toks) and toks[i + 1].lstrip('-+').isdigit():
            return int(toks[i + 1].lstrip('-+'))
        if t.startswith('--lines=') and t[8:].lstrip('-+').isdigit():
            return int(t[8:].lstrip('-+'))
        if t.startswith('-n') and t[2:].lstrip('-+').isdigit():
            return int(t[2:].lstrip('-+'))
        if t.startswith('-') and t[1:].isdigit():
            return int(t[1:])
    return default


def shell_view_range(cmd, path, short, file_lines):
    """Which lines of `path` a shell pipeline shows.

    Returns ('lines', a, b) for a known line range, ('named', None, None) when a grep stage selects lines by the
    node's own name, or None when the pipeline shows nothing of that file (ls, echo, find, python, wc, an unknown
    subset of lines, or a tail without a known file length). Stages are split on '|' and each command word is
    read from its own tokens, so a path such as headers.py never reads as a head command.
    """
    import shlex
    stages = [s.strip() for s in cmd.split('|') if s.strip()]
    toks_of = []
    for st in stages:
        try:
            toks_of.append(shlex.split(st))
        except ValueError:
            toks_of.append(st.split())
    src = None
    for i, toks in enumerate(toks_of):
        if toks and toks[0] in VIEW_CMDS and any(t == path or t.endswith('/' + path) or t == './' + path for t in toks[1:]):
            src = i
            break
    if src is None:
        return None
    a, b = 1, file_lines if file_lines else None  # None = up to the end of a file of unknown length
    named = False
    for i in range(src, len(toks_of)):
        toks = toks_of[i]
        if not toks:
            continue
        c = toks[0]
        st = stages[i]
        if c in ('cat', 'less', 'more'):
            continue
        if c == 'sed':
            m, m1 = SED_RANGE.search(st), SED_LINE.search(st)
            if m:
                a2, b2 = int(m.group(1)), int(m.group(2))
            elif m1:
                a2 = b2 = int(m1.group(1))
            else:
                return ('named', None, None) if named else None  # pattern-based sed: unknown lines
            if i == src:
                a, b = a2, b2
            else:  # sed on a stream counts lines from the stream's first line
                a, b = a + a2 - 1, (a + b2 - 1 if b is None else min(b, a + b2 - 1))
        elif c == 'head':
            n = _count_arg(toks)
            b = a + n - 1 if b is None else min(b, a + n - 1)
        elif c == 'tail':
            n = _count_arg(toks)
            if b is None:
                return None
            a = max(a, b - n + 1)
        elif c in ('grep', 'rg', 'awk'):
            if c != 'awk' and short in st:
                named = True
            else:
                return ('named', None, None) if named else None
        else:
            return None  # wc, python, xargs ...: nothing of the file is shown
    if named:
        return ('named', None, None)
    return ('lines', a, b)


def touches(call, target, node_id, file_lines=None, line_lengths=None):
    """How the next call touches a target node: 'read', 'edit', 'graph', or None.

    The lines a call shows are what the harness would return: read_file is capped at 150 lines and 10,000
    characters from its start line; a shell view (cat, sed, head, tail, grep, rg, less, more) of the target's file
    shows its pipeline's line range, capped at 5,000 characters of output. `line_lengths` (characters per line of
    the target's file) makes the character caps exact; without it only the line caps apply. Malformed calls (see
    valid_call) never count.
    """
    if not valid_call(call):
        return None
    name, args = call['function_name'], call['arguments']
    path, s, e = target['path'], target['start'], target['end']
    short = node_id.rsplit('.', 1)[-1]
    if line_lengths is not None and file_lines is None:
        file_lines = len(line_lengths)

    def overlap(a, b):
        if a is None and b is None:
            return True
        a = a if a is not None else 1
        b = b if b is not None else 10**9
        return not (b < s or (e is not None and a > e))

    def capped(a, b, max_chars):
        """Apply a character cap to a line range using the file's line lengths; (a, b) when lengths are unknown."""
        if line_lengths is None:
            return a, b
        v = visible_range(a, b, line_lengths, max_lines=None, max_chars=max_chars)
        return v if v else (None, None)

    if name == 'read_file':
        if args.get('filepath') != path:
            return None
        a = _int(args.get('start_line')) or 1
        b = _int(args.get('end_line'))
        if line_lengths is not None:
            v = visible_range(a, b, line_lengths)
            return 'read' if v and overlap(*v) else None
        b = min(b, a + MAX_FILE_LINES - 1) if b is not None else a + MAX_FILE_LINES - 1
        return 'read' if overlap(a, b) else None
    if name in ('edit_file', 'write_file'):
        return 'edit' if args.get('filepath') == path else None
    if name == 'run_command':
        view = shell_view_range(str(args.get('command', '')), path, short, file_lines)
        if view is None:
            return None
        kind, a, b = view
        if kind == 'named':
            return 'read'
        a2, b2 = capped(a, b, MAX_STDOUT_CHARS)
        if a2 is None:
            return None
        return 'read' if overlap(a2, b2) else None
    if name in ('get_code_neighbors', 'get_code_subgraph', 'search_similar_code'):
        blob = json.dumps(args)
        return 'graph' if node_id in blob or ('.' + short) in blob or f'"{short}"' in blob else None
    return None


def build_states(r, tasks, gold_ids, gold_paths):
    """All fork states of one run: up to MAX_STATES_PER_RUN content-showing steps before any edit or compaction."""
    d = load(r['path'])
    task = tasks[r['task']]
    g = graph_for(task)
    files = set(N.snapshot_files(r['task']))
    steps = d['steps']
    agent = [s for s in steps if s['source'] == 'agent']
    forks, reason, prev_prompt = [], None, None
    for i, s in enumerate(agent):
        pt = (s.get('metrics') or {}).get('prompt_tokens')
        if prev_prompt and pt and pt < COMPACTION_RATIO * prev_prompt:
            reason = 'compaction_before_fork'
            break
        prev_prompt = pt or prev_prompt
        if len(s.get('tool_calls') or []) > 1:
            reason = 'parallel_calls'
            break
        for tc in s.get('tool_calls') or []:
            n, a = tc['function_name'], tc['arguments']
            if n in ('edit_file', 'submit_patch') or (n == 'write_file' and a.get('filepath') in files):
                reason = f'{n}_before_fork'
                break
        if reason:
            break
        if shows_content(s):
            forks.append(i)
            if len(forks) >= MAX_STATES_PER_RUN:
                break
    if not forks:
        return [{'task': r['task'], 'run': r['run'], 'fork': 0, 'excluded': reason or 'no_file_content_shown'}]
    out = []
    for k, fork_idx in enumerate(forks):
        st = make_state(r, task, g, files, steps, agent, fork_idx, gold_ids, gold_paths)
        st['fork'] = k
        out.append(st)
    return out


def make_state(r, task, g, files, steps, agent, fork_idx, gold_ids, gold_paths):
    task_prompt = next((s.get('message') or '' for s in steps if (s.get('extra') or {}).get('event_type') == 'task_prompt'), '')
    if fork_idx + 1 >= len(agent):
        return {'task': r['task'], 'run': r['run'], 'excluded': 'no_next_step'}
    nxt = agent[fork_idx + 1]
    cur_pt = (agent[fork_idx].get('metrics') or {}).get('prompt_tokens')
    nxt_pt = (nxt.get('metrics') or {}).get('prompt_tokens')
    if cur_pt and nxt_pt and nxt_pt < COMPACTION_RATIO * cur_pt:
        return {'task': r['task'], 'run': r['run'], 'excluded': 'compaction_at_fork'}
    if not nxt_pt or nxt_pt > MAX_PROMPT:
        return {'task': r['task'], 'run': r['run'], 'excluded': f'prompt_over_max'}

    # in-view nodes: task prompt + every tool result so far. Shown ranges: (path, start, end) per content view.
    shown_ranges = collections.defaultdict(list)
    texts = [task_prompt]
    for s in agent[:fork_idx + 1]:
        sc = shows_content(s)
        if sc and sc[0]:
            shown_ranges[N._norm(sc[0])].append((sc[1], sc[2]))
        o = s.get('observation')
        if o and o.get('content'):
            texts.append(str(o['content']))
    issue_text = TRACEBACK_LINE.sub('', task_prompt)  # traceback frames name File and line, which are node names
    issue_nodes = mentioned(g, issue_text)
    dotted_issue = {i for tok in {k for k in set(IDENT.findall(issue_text)) if '.' in k}
                    for i in g['ids'] if i == tok or i.endswith('.' + tok)}
    in_view = set(issue_nodes)
    for t in texts[1:]:
        in_view |= mentioned(g, t)
    spans = {}
    for n in in_view:
        sp = N.span(r['task'], n)
        if sp:
            spans[n] = sp

    def in_shown(n):
        for a, b in shown_ranges.get(spans[n]['path'], []):
            if a is None or b is None:
                continue  # a grep, awk or tail view: the lines shown are unknown, so the node does not count as shown
            if spans[n]['end'] is None or not (b < spans[n]['start'] or a > spans[n]['end']):
                return True
        return False

    cands = [n for n in in_view if n in spans and 2 <= len(harness_neighbors(g, n)) <= MAX_NEIGHBORS
             and (in_shown(n) or n in dotted_issue)]
    if not cands:
        return {'task': r['task'], 'run': r['run'], 'excluded': 'no_queryable_node_in_view', 'in_view': len(in_view)}
    # Rank: inside a range the agent has already opened, then named in the issue, then a moderate degree
    # (2..PREFERRED_DEGREE, so a swapped entry is visible in the list), then higher degree, then name.
    cands.sort(key=lambda n: (not in_shown(n), n not in issue_nodes,
                              not (2 <= len(harness_neighbors(g, n)) <= PREFERRED_DEGREE),
                              -min(len(harness_neighbors(g, n)), PREFERRED_DEGREE), n))
    node = cands[0]
    shown_files = set(shown_ranges)
    true_nb = harness_neighbors(g, node)
    nb_spans = {n: N.span(r['task'], n) for n in true_nb}

    # The compared entries must both live in files the agent has not opened: following either takes a new read.
    rng = random.Random(int(hashlib.sha256(f"{r['task']}_r{r['run']}".encode()).hexdigest(), 16))
    node_path = spans[node]['path']
    nb_files = collections.Counter(sp['path'] for sp in nb_spans.values() if sp)
    unshown_true = [n for n in true_nb if nb_spans[n] and nb_spans[n]['path'] not in shown_files]
    # The swapped-out entry must be as fresh as the decoy: file unopened and name not yet seen in the prompt or
    # any tool result (the decoy is drawn from outside the in-view set by construction).
    fresh_true = [n for n in unshown_true if n not in in_view]
    if not fresh_true:
        return {'task': r['task'], 'run': r['run'], 'excluded': 'no_fresh_true_neighbor', 'node': node}

    def is_test(path):
        return '/tests/' in '/' + path or path.rsplit('/', 1)[-1].startswith('test_')

    alone = [n for n in fresh_true if nb_files[nb_spans[n]['path']] == 1]  # its file holds no other listed entry
    nontest = [n for n in fresh_true if not is_test(nb_spans[n]['path'])]
    swap_pool = sorted(set(alone) & set(nontest)) or sorted(nontest) or sorted(alone) or sorted(fresh_true)
    swapped = rng.choice(swap_pool)
    swapped_dir = nb_spans[swapped]['path'].rsplit('/', 1)[0] if '/' in nb_spans[swapped]['path'] else ''
    node_dir = node_path.rsplit('/', 1)[0] if '/' in node_path else ''
    banned = set(true_nb) | in_view | gold_ids[r['task']] | {node}
    pools = {'swapped_dir': [], 'node_dir': [], 'package': []}
    for n in g['ids']:
        if n in banned:
            continue
        sp = N.span(r['task'], n)
        if not sp or sp['path'] in gold_paths[r['task']] or sp['path'] in shown_files or sp['path'] in nb_files:
            continue
        if is_test(sp['path']):
            continue
        d = sp['path'].rsplit('/', 1)[0] if '/' in sp['path'] else ''
        if d == swapped_dir:
            pools['swapped_dir'].append(n)
        elif d == node_dir:
            pools['node_dir'].append(n)
        elif d.split('/')[0] == node_dir.split('/')[0]:
            pools['package'].append(n)
    pool_kind = next((k for k in ('swapped_dir', 'node_dir', 'package') if pools[k]), None)
    if pool_kind is None:
        return {'task': r['task'], 'run': r['run'], 'excluded': 'no_decoy_candidate', 'node': node}
    pool = pools[pool_kind]
    decoy = rng.choice(sorted(pool))
    decoy_list = sorted([n for n in true_nb if n != swapped] + [decoy])
    p_obs = {'status': 'ok', 'node': node, 'neighbors': true_nb, 'count': len(true_nb)}
    pp_obs = {'status': 'ok', 'node': node, 'neighbors': decoy_list, 'count': len(decoy_list)}

    next_call = (nxt.get('tool_calls') or [None])[0]
    observed, observed_unshown = {}, {}
    if next_call:
        for n in true_nb:
            if nb_spans[n]:
                src = N.file_text(r['task'], nb_spans[n]['path'])
                ll = [len(x) for x in src.splitlines()] if src else None
                observed[n] = touches(next_call, nb_spans[n], n, line_lengths=ll)
                if n in unshown_true:
                    observed_unshown[n] = observed[n]
    return {
        'task': r['task'], 'run': r['run'], 'arm_source': r['arm'], 'trace': str(r['path'].relative_to(ROOT)),
        'repo': task['repo'], 'base_commit': task['base_commit'], 'graph': g['key'],
        'fork_agent_step': fork_idx, 'fork_step_id': agent[fork_idx]['step_id'],
        'prompt_tokens_at_fork_call': cur_pt, 'prompt_tokens_next_call_logged': nxt_pt,
        'tool_calls_before_fork': fork_idx + 1,
        'node': node, 'node_span': spans[node], 'node_named_in_issue': node in issue_nodes,
        'node_in_shown_file': node_path in shown_files, 'in_view_count': len(in_view),
        'true_neighbors': true_nb, 'neighbor_spans': nb_spans, 'shown_files': sorted(shown_files),
        'unshown_true_neighbors': unshown_true, 'fresh_true_neighbors': fresh_true,
        'decoy': decoy, 'decoy_span': N.span(r['task'], decoy), 'decoy_pool': pool_kind, 'decoy_pool_size': len(pool),
        'swapped_out': swapped, 'swapped_out_alone_in_file': swapped in alone,
        'swapped_out_is_test': is_test(nb_spans[swapped]['path']),
        'decoy_position': decoy_list.index(decoy), 'swapped_position': true_nb.index(swapped), 'decoy_list': decoy_list,
        'arms': {
            'P': {'call': {'name': 'get_code_neighbors', 'args': {'node': node}}, 'response': p_obs},
            'Pp': {'call': {'name': 'get_code_neighbors', 'args': {'node': node}}, 'response': pp_obs},
            'H': {'user_text': H_WORDING.format(node=node, json=json.dumps(p_obs))},
            'Hp': {'user_text': H_WORDING.format(node=node, json=json.dumps(pp_obs))},
        },
        'observed_next_call': next_call, 'observed_next_call_valid': valid_call(next_call) if next_call else False,
        'observed_next_thinking': (nxt.get('message') or '')[:2000],
        'observed_touch': observed, 'observed_touch_unshown': observed_unshown,
        'file_lines': {n: (len(t.splitlines()) if (t := N.file_text(r['task'], sp['path'])) else None)
                       for n, sp in list(nb_spans.items()) + [(decoy, N.span(r['task'], decoy))] if sp},
        'gold_ids': sorted(gold_ids[r['task']]),
        'steps': steps[:steps.index(agent[fork_idx]) + 1],
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    gold_ids, gold_paths = load_gold()
    rows, states = [], []
    for old in OUT.glob('*.json'):
        old.unlink()
    for r in iter_runs(arm='base'):
      for st in build_states(r, tasks, gold_ids, gold_paths):
        if 'excluded' in st:
            rows.append({'task': st['task'], 'run': st['run'], 'fork': st.get('fork', 0), 'status': st['excluded']})
            continue
        (OUT / f"{st['task']}_r{st['run']}_f{st['fork']}.json").write_text(json.dumps(st, indent=1), encoding='utf-8')
        states.append(st)
        rows.append({'task': st['task'], 'run': st['run'], 'fork': st['fork'], 'status': 'ok', 'node': st['node'],
                     'n_true': len(st['true_neighbors']), 'n_unshown_true': len(st['unshown_true_neighbors']),
                     'prompt_next': st['prompt_tokens_next_call_logged'],
                     'calls_before': st['tool_calls_before_fork'], 'named_in_issue': st['node_named_in_issue'],
                     'decoy_pool': st['decoy_pool'], 'observed_touch_any': any(v for v in st['observed_touch'].values()),
                     'observed_touch_unshown': any(v for v in st['observed_touch_unshown'].values())})
    with open(OUT / 'summary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['task', 'run', 'fork', 'status', 'node', 'n_true', 'n_unshown_true', 'prompt_next',
                                          'calls_before', 'named_in_issue', 'decoy_pool', 'observed_touch_any',
                                          'observed_touch_unshown'])
        w.writeheader()
        w.writerows(rows)
    with open(OUT / 'states.jsonl', 'w', encoding='utf-8') as f:
        for st in states:
            f.write(json.dumps(st) + '\n')
    c = collections.Counter(r['status'] for r in rows)
    print('fork candidates:', len(rows), '| eligible states:', len(states), '| runs with a state:',
          len({(s['task'], s['run']) for s in states}), '| tasks with a state:', len({s['task'] for s in states}))
    for k, v in c.most_common():
        print(f'  {k}: {v}')
    if states:
        import statistics as stt
        print('true-neighbor count: median', stt.median(len(s['true_neighbors']) for s in states),
              'max', max(len(s['true_neighbors']) for s in states))
        print('named in issue:', sum(s['node_named_in_issue'] for s in states),
              '| in shown file:', sum(s['node_in_shown_file'] for s in states))
        print('observed next call touches a listed neighbor:',
              sum(any(v for v in s['observed_touch'].values()) for s in states),
              '| one in an unopened file:', sum(any(v for v in s['observed_touch_unshown'].values()) for s in states))
        print('prompt tokens at next call: median', stt.median(s['prompt_tokens_next_call_logged'] for s in states))


if __name__ == '__main__':
    main()
