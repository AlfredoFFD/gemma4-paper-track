"""EXPLORATORY (no rule, no model call): what a text search for a neighbor's name returns, against what the graph returns.

The graph names one definition per neighbor. A search for `def <name>` or `class <name>` returns every definition of
that short name. This script counts, offline, how often those differ, and whether the stored replays show the agent
going to the listed definition or to a same-named one. Nothing here is registered; every number is EXPLORATORY.

Definitions
  graph            one JSON under data/graphs/ (127 repository snapshots); a node is an entry of `nodes` (its `id` is
                   a dotted name); a neighbor relation is an ordered pair (U, V) of two different nodes with an edge
                   between them in either direction, each direction once (449,902 relations, as in
                   analysis/explore_graph_names.py).
  short name       the last dotted component of a node id.
  candidates       for a relation (U, V): the nodes of the same graph whose short name equals V's, V included. This is
                   what a search for the name returns, counted in graph nodes only (code without a node is not
                   counted, so it is a lower bound).
  decoys           candidates other than V. other-file decoys: decoys whose file differs from V's file;
                   same-file decoys: decoys in V's own file (methods of the same name on other classes of one file).
  file             a node's file in a snapshot of its graph's commit: analysis/nodes.py `resolve` (the longest prefix of
                   the dotted id that names a .py file of the snapshot, both package and bare module forms). For part A
                   the snapshot is that of the first task (by instance id) whose repository and base commit give the
                   graph; a node with no matching prefix has no file and is never counted as an other-file decoy.
  span             analysis/nodes.py `span`: the file plus the line range of the definition found with `ast`.
  expected precision  mean over relations of 1 / (number of candidates): the chance that one definition picked at
                   random among the search hits is the graph's neighbor. With other-file decoys only: 1 / (1 + other-
                   file decoys), i.e. a search that is told the file is free to tell same-file definitions apart.
  dunder           a short name that starts and ends with two underscores (`__init__` and the like).
  test file        a file path with a `test` or `tests` or `testing` directory, or a file named test_*.py, *_test.py
                   or conftest.py; for a node with no file, a dotted id with a component `test`, `tests` or test_*.
  "excluding dunder and tests": relations whose V is a dunder or in a test file are dropped, and candidates in test
                   files are not counted.
  paused steps     the 407 states of analysis/fork_states_c/states.jsonl (pre-registrations 03, 04 and 12; the same
                   keys as analysis/fork_states/states.jsonl). Each has the node just shown (`node`) and the neighbors
                   listed for it (`true_neighbors`).
  unopened         the registered scorer's notion (analysis/analyze_c.py): `unshown_true_neighbors` of the state, with
                   a span in `neighbor_spans`.
  usable neighbor  (part C) an unopened listed neighbor V with at least one decoy that has a span with a line range,
                   lies in another file than V, and is neither the shown node nor itself a listed neighbor.
  complete in 04   states with a usable replay under all five arms and three seeds of run c (pre-registration 04's
                   run), after the interface-failure exclusions of analysis/analyze_c.py.
  touch            analysis/fork_states.py `touches` with the files' line lengths, as the registered scorers of 03 and
                   04 call it (a graph-tool mention does not count); interface failures excluded as they exclude them.
  opened file      (part D) the file of a read_file, edit_file or write_file call, or every *.py path in a run_command
                   whose stages include cat, sed, head, tail, grep, rg, awk, less or more; paths normalized as the
                   harness does.

Stored replays of part D (Gemma-4-31B, no new run): run v5 (pre-registration 02, arm H: bare names, pooled into 03
as its comparison), run v6 (pre-registration 03: arm D, the instruction with bare names in the tool's JSON; arm E,
name, file, lines and first definition line), run c (pre-registration 04: arms H and E re-run; arm EL, name, file
and lines). States for v5 and v6 come from analysis/fork_states/states.jsonl, for c from
analysis/fork_states_c/states.jsonl, as the registered scorers read them.

Usage: py -I -X utf8 analysis/explore_graph_ambiguity.py [--no-write]
Writes analysis/results/explore_graph_ambiguity.txt (exactly what it prints).
"""
import collections
import io
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from analyze_forks import KNOWN_TOOLS  # noqa: E402
from fork_states import PATH_TOKEN, VIEW_CMDS, norm_path, touches, valid_call  # noqa: E402

OUT = HERE / 'results' / 'explore_graph_ambiguity.txt'
STATES_C = HERE / 'fork_states_c' / 'states.jsonl'
STATES_B = HERE / 'fork_states' / 'states.jsonl'
RUNS_D = [('v5', STATES_B, ('H',)), ('v6', STATES_B, ('D', 'E')), ('c', STATES_C, ('H', 'E', 'EL'))]
BARE = {'H', 'D'}
TEST_PATH = re.compile(r'(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$')
NAMED = "run_command naming a usable neighbor's short name"
BUCKETS = (('1', 1, 1), ('2', 2, 2), ('3-5', 3, 5), ('6-20', 6, 20), ('>20', 21, 10**9))

buf = io.StringIO()


def p(*a):
    print(*a)
    print(*a, file=buf)


def short(i):
    return i.rsplit('.', 1)[-1]


def dunder(name):
    return len(name) > 4 and name.startswith('__') and name.endswith('__')


def is_test(node_id, path):
    if path:
        return bool(TEST_PATH.search(path))
    return any(c in ('test', 'tests') or c.startswith('test_') for c in node_id.split('.'))


def pct(k, n):
    return f'{k} ({100 * k / n:.1f}%)' if n else f'{k} (n/a)'


def buckets(xs):
    n = len(xs)
    return ', '.join(f'{lab}: {pct(sum(lo <= x <= hi for x in xs), n)}' for lab, lo, hi in BUCKETS)


def summarize(label, rows, indent='   '):
    """rows: list of (candidates, other-file decoys, same-file decoys)."""
    n = len(rows)
    p(f'{indent}{label}: relations {n}')
    if not n:
        return
    c = [r[0] for r in rows]
    sh = [x for x in c if x > 1]
    p(f'{indent}  short name unique in its graph: {pct(n - len(sh), n)}')
    p(f'{indent}  candidates per relation: {buckets(c)}')
    if sh:
        p(f'{indent}  among shared: median {statistics.median(sh):g}, mean {statistics.mean(sh):.1f}')
    p(f'{indent}  expected precision of the search (mean 1/candidates): {statistics.mean(1 / x for x in c):.3f}')
    of = [r[1] for r in rows]
    ofs = [x for x in of if x > 0]
    p(f'{indent}  with at least one other-file decoy: {pct(len(ofs), n)}; with same-file decoys only: '
      f'{pct(sum(r[1] == 0 and r[2] > 0 for r in rows), n)}')
    p(f'{indent}  1 + other-file decoys: {buckets([1 + x for x in of])}')
    if ofs:
        p(f'{indent}  other-file decoys among those with any: median {statistics.median(ofs):g}, '
          f'mean {statistics.mean(ofs):.1f}; distinct other files: median '
          f'{statistics.median([r[3] for r in rows if r[1] > 0]):g}')
    p(f'{indent}  expected precision, other files only (mean 1/(1 + other-file decoys)): '
      f'{statistics.mean(1 / (1 + x) for x in of):.3f}')


def graph_info(key, task):
    g = json.load(open(ROOT / 'data' / 'graphs' / f'{key}.json', encoding='utf-8'))
    ids = [n['id'] for n in g['nodes']]
    idset = set(ids)
    file = {}
    for i in ids:
        r = N.resolve(task, i)
        file[i] = r[0] if r else None
    by_short = collections.defaultdict(list)
    for i in ids:
        by_short[short(i)].append(i)
    nb = collections.defaultdict(set)
    for e in g['edges']:
        s, t = e['source'], e['target']
        if s in idset and t in idset and s != t:
            nb[s].add(t)
            nb[t].add(s)
    return {'ids': ids, 'file': file, 'by_short': by_short, 'nb': nb}


def relation_row(info, v, strict):
    """(candidates, other-file decoys, same-file decoys, distinct other files) for a neighbor V."""
    f = info['file']
    cands = info['by_short'][short(v)]
    if strict:
        cands = [c for c in cands if not is_test(c, f[c])]
    other = [c for c in cands if c != v and f[c] and f[v] and f[c] != f[v]]
    same = [c for c in cands if c != v and f[c] and f[c] == f[v]]
    return (len(cands), len(other), len(same), len({f[c] for c in other}))


def part_a(tasks_by_key, keep_keys):
    rows_all, rows_strict = [], []
    by_repo = collections.defaultdict(list)
    sub_all, sub_strict = [], []
    kept = {}
    unresolved = total_nodes = 0
    for gf in sorted((ROOT / 'data' / 'graphs').glob('*.json')):
        key = gf.stem
        task = tasks_by_key[key]
        info = graph_info(key, task)
        unresolved += sum(v is None for v in info['file'].values())
        total_nodes += len(info['ids'])
        repo = key.rsplit('_', 1)[0]
        for u, vs in info['nb'].items():
            for v in vs:
                r = relation_row(info, v, False)
                rows_all.append(r)
                by_repo[repo].append(r)
                if key in keep_keys:
                    sub_all.append(r)
                if not (dunder(short(v)) or is_test(v, info['file'][v])):
                    rs = relation_row(info, v, True)
                    rows_strict.append(rs)
                    if key in keep_keys:
                        sub_strict.append(rs)
        if key in keep_keys:
            kept[key] = info
    return rows_all, rows_strict, by_repo, sub_all, sub_strict, kept, unresolved, total_nodes


class Lines:
    def __init__(self):
        self.cache = {}

    def __call__(self, task, path):
        k = (task, path)
        if k not in self.cache:
            src = N.file_text(task, path)
            self.cache[k] = [len(x) for x in src.splitlines()] if src else None
        return self.cache[k]


def state_decoys(s, info, span_cache):
    """{unopened listed neighbor: [(decoy id, decoy span), ...]} for the usable neighbors of a state."""
    task = s['task']
    spans = s['neighbor_spans']
    listed = set(s['true_neighbors']) | {s['node']}
    out = {}
    for v in s.get('unshown_true_neighbors', s['true_neighbors']):
        sp = spans.get(v)
        if not sp:
            continue
        ds = []
        for c in info['by_short'][short(v)]:
            if c in listed:
                continue
            k = (task, c)
            if k not in span_cache:
                span_cache[k] = N.span(task, c)
            cs = span_cache[k]
            if cs and cs['end'] is not None and cs['path'] != sp['path']:
                ds.append((c, cs))
        if ds:
            out[v] = ds
    return out


def strict_decoys(s, dec):
    out = {}
    for v, ds in dec.items():
        if dunder(short(v)) or is_test(v, s['neighbor_spans'][v]['path']):
            continue
        ds2 = [(c, cs) for c, cs in ds if not is_test(c, cs['path'])]
        if ds2:
            out[v] = ds2
    return out


def complete_in_c():
    rows = [json.loads(l) for l in open(HERE / 'results' / 'c' / 'forks' / 'results.jsonl', encoding='utf-8')]
    rows = [r for r in rows if r['arm'] in ('Ep', 'EL', 'ES', 'E', 'H')]
    by_state = collections.defaultdict(set)
    for r in rows:
        call = r.get('next_call')
        if r.get('error') or not call or call['function_name'] not in KNOWN_TOOLS or not valid_call(call):
            continue
        by_state[(r['task'], r['run'], r.get('fork', 0))].add((r['arm'], r['seed']))
    arms = {a for v in by_state.values() for a, _ in v}
    seeds = {sd for v in by_state.values() for _, sd in v}
    return {k for k, v in by_state.items() if len(v) == len(arms) * len(seeds)}


def part_c_report(label, states, decs):
    use = [(s, d) for s, d in zip(states, decs) if d]
    p(f'   {label}: steps {len(states)}; usable steps (at least one usable neighbor) {pct(len(use), len(states))}; '
      f'tasks {len({s["task"] for s, _ in use})} of {len({s["task"] for s in states})}')
    if not use:
        return
    nn = [len(d) for _, d in use]
    nd = [len({c for ds in d.values() for c, _ in ds}) for _, d in use]
    unop = [len({c for ds in d.values() for c, cs in ds if cs['path'] not in set(s.get('shown_files', []))})
            for s, d in use]
    p(f'      per usable step: usable neighbors median {statistics.median(nn):g}, mean {statistics.mean(nn):.1f}, '
      f'total {sum(nn)}; distinct decoys median {statistics.median(nd):g}, mean {statistics.mean(nd):.1f}, total '
      f'{sum(nd)}; decoys in a file the agent has not opened: total {sum(unop)} (steps with at least one: '
      f'{sum(x > 0 for x in unop)})')
    p(f'      usable steps with 1 / 2 / 3+ usable neighbors: {sum(x == 1 for x in nn)} / {sum(x == 2 for x in nn)} / '
      f'{sum(x >= 3 for x in nn)}')
    by_repo = collections.defaultdict(list)
    for s, d in use:
        by_repo[s['repo'].split('/')[1]].append(s)
    tot = collections.Counter(s['repo'].split('/')[1] for s in states)
    p('      by repository: ' + '; '.join(
        f'{r} {len(v)} of {tot[r]} steps, {len({s["task"] for s in v})} tasks' for r, v in sorted(by_repo.items())))


def opened_files(call):
    name, args = call['function_name'], call['arguments']
    if name in ('read_file', 'edit_file', 'write_file'):
        return {norm_path(args.get('filepath'))}
    if name == 'run_command':
        cmd = str(args.get('command', ''))
        stages = [x.strip().split() for x in cmd.split('|')]
        if any(t and t[0] in VIEW_CMDS for t in stages):
            return {norm_path(x) for x in PATH_TOKEN.findall(cmd)}
    return set()


FILE_KINDS = ("opens a usable neighbor's file", 'opens a file opened before the step', "opens another listed neighbor's file",
              "opens a same-named definition's file (unopened)", 'opens another file', 'opens no file')


def part_d_table(kept, lines, span_cache, strict):
    p('')
    p('   ' + ('EXCLUDING dunder neighbors and test files (neighbors and decoys)' if strict else 'ALL listed unopened neighbors'))
    p(f'   {"run arm":9} {"replays":>7} | {"unique: touched":>20} | {"shared, other file: touched":>27} | '
      f'{"decoy touched, unopened file (V not)":>36} | {"decoy, opened file":>18} | {"shared, rest: touched":>21}')
    file_rows = []
    for run, spath, arms in RUNS_D:
        states = {(s['task'], s['run'], s.get('fork', 0)): s for s in (json.loads(l) for l in open(spath, encoding='utf-8'))}
        decs = {}
        for k, s in states.items():
            d = state_decoys(s, kept[s['graph']], span_cache)
            decs[k] = strict_decoys(s, d) if strict else d
        rows = [json.loads(l) for l in open(HERE / 'results' / run / 'forks' / 'results.jsonl', encoding='utf-8')]
        for arm in arms:
            c = collections.Counter()
            fc = collections.Counter()
            for r in rows:
                if r['arm'] != arm:
                    continue
                call = r.get('next_call')
                if r.get('error') or not call or call['function_name'] not in KNOWN_TOOLS or not valid_call(call):
                    continue
                key = (r['task'], r['run'], r.get('fork', 0))
                s = states[key]
                task = s['task']
                spans = s['neighbor_spans']
                shown = set(s.get('shown_files', []))
                info = kept[s['graph']]
                dec = decs[key]
                c['replays'] += 1

                def hit(sp, node):
                    t = touches(call, sp, node, line_lengths=lines(task, sp['path']))
                    return bool(t) and t != 'graph'

                for v in s.get('unshown_true_neighbors', s['true_neighbors']):
                    if not spans.get(v):
                        continue
                    if strict and (dunder(short(v)) or is_test(v, spans[v]['path'])):
                        continue
                    tv = hit(spans[v], v)
                    if v in dec:
                        cls = 'other'
                        tu = any(hit(cs, cn) for cn, cs in dec[v] if cs['path'] not in shown)
                        to = any(hit(cs, cn) for cn, cs in dec[v] if cs['path'] in shown)
                        c['dec_u'] += tu
                        c['dec_u_only'] += tu and not tv
                        c['dec_o'] += to
                    elif len(info['by_short'][short(v)]) == 1:
                        cls = 'unique'
                    else:
                        cls = 'same'
                    c[cls] += 1
                    c[cls + '_t'] += tv
                if dec:
                    fc['n'] += 1
                    opened = opened_files(call)
                    nfiles = {spans[v]['path'] for v in dec}
                    dfiles = {cs['path'] for ds in dec.values() for _, cs in ds}
                    lfiles = {sp['path'] for sp in spans.values() if sp}
                    if not opened:
                        kind = 5
                    elif opened & nfiles:
                        kind = 0
                    elif opened & shown:
                        kind = 1
                    elif opened & lfiles:
                        kind = 2
                    elif opened & dfiles:
                        kind = 3
                    else:
                        kind = 4
                    fc[FILE_KINDS[kind]] += 1
                    if call['function_name'] == 'run_command':
                        cmd = str(call['arguments'].get('command', ''))
                        if any(re.search(r'\b' + re.escape(short(v)) + r'\b', cmd) for v in dec):
                            fc[NAMED] += 1

            def rt(k, n):
                return f'{c[k]:>4}/{c[n]:<5} ({100 * c[k] / max(c[n], 1):4.2f}%)'

            p(f'   {run + " " + arm:9} {c["replays"]:>7} | {rt("unique_t", "unique"):>20} | {rt("other_t", "other"):>27} | '
              f'{c["dec_u"]:>4} ({c["dec_u_only"]:>3}) of {c["other"]:<5}{"":17} | {c["dec_o"]:>18} | '
              f'{rt("same_t", "same"):>21}')
            file_rows.append((run, arm, fc))
    p('   Where the next call goes, replays whose state lists at least one usable neighbor (first match wins):')
    for run, arm, fc in file_rows:
        n = fc['n']
        p(f'   {run} {arm}{" (bare names)" if arm in BARE else " (addresses)"}: replays {n}; '
          + '; '.join(f'{k} {pct(fc[k], n)}' for k in FILE_KINDS) + f'; {NAMED}: {pct(fc[NAMED], n)}')


def part_d(kept, lines, span_cache):
    p('')
    p('D. STORED REPLAYS (Gemma-4-31B; no new run): listed unopened neighbors split by their name, touches by the')
    p('   registered scorer. Classes: unique = no other node of the graph has the short name; shared, other file =')
    p('   a usable neighbor of part C; shared, rest = shared within its file only, or every other-file definition')
    p('   lacks a span or is itself listed. Counts are (replay, entry) pairs. "decoy touched" = any same-named')
    p('   definition of a usable neighbor touched, split by whether the decoy file was opened before the step; in')
    p('   brackets the pairs where the listed neighbor itself was not touched.')
    part_d_table(kept, lines, span_cache, False)
    part_d_table(kept, lines, span_cache, True)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = sorted((json.loads(l) for l in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8')),
                   key=lambda t: t['instance_id'])
    tasks_by_key = {}
    for t in tasks:
        tasks_by_key.setdefault(f"{t['repo'].split('/')[1]}_{t['base_commit']}", t['instance_id'])
    states_c = [json.loads(l) for l in open(STATES_C, encoding='utf-8')]
    keep_keys = {s['graph'] for s in states_c}

    p('EXPLORATORY. What a text search for a neighbor\'s short name returns, against the one definition the graph names.')
    p('Definitions in the docstring of analysis/explore_graph_ambiguity.py.')
    (rows_all, rows_strict, by_repo, sub_all, sub_strict, kept, unresolved,
     total_nodes) = part_a(tasks_by_key, keep_keys)
    p(f'graphs 127; nodes {total_nodes}, of which with no file in the snapshot: {pct(unresolved, total_nodes)}')
    p('')
    p('A. ALL GRAPHS, per neighbor relation (a node and one of its neighbors, each direction once)')
    summarize('all relations', rows_all)
    summarize('excluding dunder neighbors and test files', rows_strict)
    for repo in sorted(by_repo):
        rr = by_repo[repo]
        p(f'   {repo}: relations {len(rr)}; unique {100 * sum(r[0] == 1 for r in rr) / len(rr):.1f}%; '
          f'with an other-file decoy {100 * sum(r[1] > 0 for r in rr) / len(rr):.1f}%; expected precision '
          f'{statistics.mean(1 / r[0] for r in rr):.3f}')

    p('')
    p(f'B. GRAPHS OF THE PAUSED STEPS ({len(keep_keys)} graphs, {len({s["task"] for s in states_c})} tasks, '
      f'{len(states_c)} steps)')
    summarize('all relations of these graphs', sub_all)
    summarize('the same, excluding dunder neighbors and test files', sub_strict)
    listed, listed_strict = [], []
    for s in states_c:
        info = kept[s['graph']]
        f = dict(info['file'])
        for v in s['true_neighbors']:
            r = N.resolve(s['task'], v)
            f[v] = r[0] if r else None
        info2 = dict(info, file=f)
        for v in s['true_neighbors']:
            listed.append(relation_row(info2, v, False))
            if not (dunder(short(v)) or is_test(v, f[v])):
                listed_strict.append(relation_row(info2, v, True))
    summarize('neighbors LISTED at the 407 paused steps (one row per step and listed neighbor)', listed)
    summarize('listed, excluding dunder neighbors and test files', listed_strict)

    p('')
    p('C. USABLE STEPS for a same-name experiment: an unopened listed neighbor with a same-named definition, with a')
    p('   line span, in another file (not the shown node, not itself listed)')
    span_cache = {}
    decs = [state_decoys(s, kept[s['graph']], span_cache) for s in states_c]
    sdecs = [strict_decoys(s, d) for s, d in zip(states_c, decs)]
    comp = complete_in_c()
    ck = [i for i, s in enumerate(states_c) if (s['task'], s['run'], s.get('fork', 0)) in comp]
    part_c_report('all 407 steps', states_c, decs)
    part_c_report('all 407 steps, excluding dunder neighbors and test files', states_c, sdecs)
    part_c_report(f'steps complete in 04\'s run ({len(ck)})', [states_c[i] for i in ck], [decs[i] for i in ck])
    part_c_report('steps complete in 04\'s run, excluding dunder neighbors and test files',
                  [states_c[i] for i in ck], [sdecs[i] for i in ck])
    names = collections.Counter(short(v) for d in decs for v in d)
    p('   most common short names among usable neighbors (all 407 steps, counted per step): '
      + ', '.join(f'{k} {v}' for k, v in names.most_common(12)))

    part_d(kept, Lines(), span_cache)
    if '--no-write' not in sys.argv:
        OUT.write_text(buf.getvalue(), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
