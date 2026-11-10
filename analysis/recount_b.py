"""Independent recount of the directive/encoding experiment (pre-registrations 02 and 03).

Re-derives, from the raw per-replay rows only, the per-arm touch rates and the contrasts
B1-B4. It shares no code with the scoring used for the paper: the rules below were written
from the two pre-registrations and from the harness source (the read caps and the argument
handling of the tools), not from the project's own scorer.

Inputs (paths relative to the repository root):
  analysis/results/{v5,v6,v8}/forks/results.jsonl   one row per replay
  analysis/fork_states/states.jsonl                 one record per fork state
  data/cache/snapshot_text/<task>/...               repository file texts (for the caps)
Output: analysis/results/recount_b.txt (full), and a compact table on stdout.

Standard library only.  Usage:  python analysis/recount_b.py
"""
import collections
import json
import os
import posixpath
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNS = ('v5', 'v6', 'v8')
ARMS = ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE')
SEEDS = (1, 2, 3)
OUT_PATH = os.path.join('analysis', 'results', 'recount_b.txt')

# (mandatory, optional) parameters of the nine functions the agent framework can call.
TOOLS = {
    'run_command': (('command',), ()),
    'read_file': (('filepath',), ('start_line', 'end_line')),
    'write_file': (('filepath', 'content'), ()),
    'edit_file': (('filepath', 'old_string', 'new_string'), ('allow_multiple',)),
    'submit_patch': ((), ()),
    'get_status': ((), ()),
    'get_code_neighbors': (('node',), ('edge_type', 'max_neighbors')),
    'search_similar_code': (('query',), ('k',)),
    'get_code_subgraph': (('nodes',), ()),
}
GRAPH_TOOLS = ('get_code_neighbors', 'search_similar_code', 'get_code_subgraph')
KINDS = ('error', 'no_call', 'unknown_tool', 'malformed')
OUT = []


def emit(line=''):
    OUT.append(line)


# ----------------------------------------------------------------------------- loading

def load_rows():
    rows = []
    for v in RUNS:
        path = os.path.join(ROOT, 'analysis', 'results', v, 'forks', 'results.jsonl')
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    r['_run'] = v
                    rows.append(r)
    return rows


def load_states():
    states = {}
    path = os.path.join(ROOT, 'analysis', 'fork_states', 'states.jsonl')
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            s = json.loads(line)
            for k in ('steps', 'arms', 'graph', 'trace'):
                s.pop(k, None)
            states[(s['task'], s['run'], s['fork'])] = s
    return states


# ------------------------------------------------- the harness's argument rules (step 1)

class Rejected(Exception):
    pass


def coerce_optional_int(val):
    """The harness's coercion of start_line / end_line."""
    if val is None:
        return None
    if isinstance(val, bool):
        raise Rejected('boolean line number')
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        try:
            return int(val)
        except (ValueError, OverflowError):
            raise Rejected('non-finite line number')
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ('none', 'null', 'nil'):
            return None
        try:
            return int(s)
        except ValueError:
            pass
        try:
            f = float(s)
            if f.is_integer():
                return int(f)
        except (ValueError, OverflowError):
            pass
        raise Rejected('non-numeric line number')
    raise Rejected('line number of type ' + type(val).__name__)


def resolve_workspace_path(filepath, allow_root=False):
    """The harness's path rule; returns the path relative to the workspace root."""
    if not isinstance(filepath, str):
        raise Rejected('path of type ' + type(filepath).__name__)
    p = filepath
    if p == '/workspace':
        p = ''
    elif p.startswith('/workspace/'):
        p = p[len('/workspace/'):]
    if p.startswith('/'):
        raise Rejected('absolute path outside the workspace')
    if chr(0) in p:
        raise Rejected('null byte in path')
    norm = posixpath.normpath(p) if p else '.'
    if norm == '..' or norm.startswith('../'):
        raise Rejected('path leaves the workspace')
    rel = '' if norm == '.' else norm
    if rel == '' and not allow_root:
        raise Rejected('path is the workspace root, not a file')
    return rel


def effective_args(name, args):
    """The agent framework drops argument keys that are not parameters of the function."""
    mand, opt = TOOLS[name]
    keep = set(mand) | set(opt)
    return {k: v for k, v in args.items() if k in keep}


def classify(row):
    """(kind, detail); kind is ok, or the first that applies of error, no_call,
    unknown_tool, malformed."""
    if row.get('error'):
        return 'error', str(row.get('error'))[:80]
    call = row.get('next_call')
    if not call or not isinstance(call, dict) or not call.get('function_name'):
        return 'no_call', ''
    name = call.get('function_name')
    if name not in TOOLS:
        return 'unknown_tool', str(name)
    args = call.get('arguments')
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return 'malformed', 'arguments are not an object'
    eff = effective_args(name, args)
    mand, _opt = TOOLS[name]
    missing = [m for m in mand if m not in eff]
    if missing:
        return 'malformed', name + ': missing ' + ','.join(missing)
    try:
        if name == 'read_file':
            coerce_optional_int(eff.get('start_line'))
            coerce_optional_int(eff.get('end_line'))
            resolve_workspace_path(eff['filepath'])
        elif name in ('write_file', 'edit_file'):
            resolve_workspace_path(eff['filepath'])
            for k in ('content', 'old_string', 'new_string'):
                if k in eff and not isinstance(eff[k], str):
                    raise Rejected(k + ' of type ' + type(eff[k]).__name__)
        elif name == 'run_command':
            if not isinstance(eff['command'], str):
                raise Rejected('command of type ' + type(eff['command']).__name__)
        elif name == 'get_code_neighbors':
            if not isinstance(eff['node'], str):
                raise Rejected('node of type ' + type(eff['node']).__name__)
        elif name == 'search_similar_code':
            if not isinstance(eff['query'], str):
                raise Rejected('query of type ' + type(eff['query']).__name__)
        elif name == 'get_code_subgraph':
            if not isinstance(eff['nodes'], list):
                raise Rejected('nodes of type ' + type(eff['nodes']).__name__)
    except Rejected as e:
        return 'malformed', name + ': ' + str(e)
    return 'ok', ''


# ------------------------------------------------------------------------------- main

def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    rows = load_rows()
    states = load_states()
    emit('Independent recount, experiment B (pre-registrations 02 and 03)')
    emit('rows: %d   states: %d' % (len(rows), len(states)))
    arms_seen = collections.Counter(r['arm'] for r in rows)
    emit('rows per arm: ' + ', '.join('%s %d' % (a, arms_seen[a]) for a in ARMS))
    extra = sorted(a for a in arms_seen if a not in ARMS)
    if extra:
        emit('WARNING arms not expected: %r' % extra)

    # step 1: interface failures
    table = {}
    dup = 0
    orphan = 0
    fails = collections.Counter()
    details = collections.Counter()
    for r in rows:
        key = (r['task'], r['run'], r['fork'])
        if key not in states:
            orphan += 1
        k3 = (key, r['arm'], r['seed'])
        if k3 in table:
            dup += 1
        kind, detail = classify(r)
        r['_kind'] = kind
        table[k3] = r
        if kind != 'ok':
            fails[(r['arm'], kind)] += 1
            details[(kind, detail)] += 1
    emit('duplicate (state, arm, seed) rows: %d   rows whose state is not in the state file: %d'
         % (dup, orphan))
    emit('')
    emit('STEP 1. Interface failures, excluded in this order: error, no call, unknown tool, '
         'malformed arguments')
    emit('%-4s %6s %8s %13s %10s %6s' % ('arm', 'error', 'no_call', 'unknown_tool', 'malformed',
                                        'all'))
    for a in ARMS:
        c = [fails[(a, k)] for k in KINDS]
        emit('%-4s %6d %8d %13d %10d %6d' % (a, c[0], c[1], c[2], c[3], sum(c)))
    tot = [sum(fails[(a, k)] for a in ARMS) for k in KINDS]
    emit('%-4s %6d %8d %13d %10d %6d' % ('all', tot[0], tot[1], tot[2], tot[3], sum(tot)))
    emit('failure details:')
    for (kind, detail), n in sorted(details.items(), key=lambda x: (-x[1], x[0])):
        emit('  %5d  %s  %s' % (n, kind, detail))

    # step 2: complete states
    complete = []
    for key in sorted(states):
        ok = True
        for a in ARMS:
            for sd in SEEDS:
                r = table.get((key, a, sd))
                if r is None or r['_kind'] != 'ok':
                    ok = False
        if ok:
            complete.append(key)
    emit('')
    emit('STEP 2. Complete states (every arm x every seed has a valid row): %d of %d'
         % (len(complete), len(states)))

    out_path = os.path.join(ROOT, OUT_PATH)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(OUT) + '\n')
    print('\n'.join(OUT[:40]))
    print('full output: ' + OUT_PATH.replace(os.sep, '/'))


if __name__ == '__main__':
    main()
