"""Independent re-derivation (EXPLORATORY, blind): what lies within reach of the code a public starter-agent run was shown.

Written from a brief's definitions only, without reading the project's own scripts or outputs on this question.
Imports from the earlier blind re-derivation analysis/rederive_public_missed_links.py (hunk parsing, read_file parsing,
graph loading) and the shared helper analysis/nodes.py (node spans on the task snapshot). Raw inputs: the public traces
(analysis/graphloc_traces.py; arms base and skill, 3 runs x 106 tasks each), data/tasks.jsonl, data/graphs/, and
data/snapshots/.

Definitions as implemented:
- CHANGED REGION: one per hunk of the reference patch in a file the patch modifies, in old-file line numbers, from the
  first to the last removed line; a block of added lines not directly after a removed line contributes the two old
  lines it is inserted between. Context lines excluded. Files the patch creates are left out.
- SHOWN: start_line..end_line of every read_file result with status ok (path from the result, else the call's).
- MISSED PAIR: (run, CHANGED REGION of its task) with no SHOWN line overlapping the region.
- NODE: a graph node that nodes.span resolves to a function, method or class span (decorators included). Module nodes
  have no span and are never TARGETS nor SHOWN NODES (a sensitivity line counts them as shown when their file was read).
- TARGET: the NODE in the region's file with the shortest span overlapping the region (ties: smallest node id).
  SHOWN NODE: a NODE whose span overlaps a SHOWN line range.
- GRAPH: every stored edge (all are typed 'calls', including class->member edges), made undirected, self-loops
  dropped, duplicates (both directions) merged.
- EDGE REACH: the TARGET exists, is not SHOWN, and is adjacent in the GRAPH to some SHOWN NODE.
- NAME REACH: the TARGET exists, is not SHOWN, and its short name (last dotted part of the node id) matches
  (?<!\\w)name(?!\\w) in the snapshot text of the SHOWN line ranges (all files, .py or not, read from the snapshot
  archive). The variant without dunder names counts a pair only if the short name does not start and end with '__'.
- REWIRED GRAPHS, 20 seeds: double-edge swaps (a-b, c-d) -> (a-d, c-b), 10 attempts per edge of each swap group, a swap
  skipped if it would make a self-loop or a duplicate edge. (a) one group: all edges. (b) groups: edges whose two end
  nodes lie in the same directory, one group per directory; edges across directories or with an end node outside the
  snapshot never move. (c) groups: edges by their unordered pair of files; the second edge is oriented so that each
  new edge keeps the old file pair. Edge reach is recounted on each rewired graph with the same SHOWN NODES.
- Intervals: 95% percentile bootstrap over tasks, 2,000 resamples, random.Random(0) fresh for each interval; a share is
  the ratio of summed counts; a difference is per task (count A - count B) over the summed denominator.
- The 'class->member containment' sensitivity line of the first block (kept as first written): an edge whose two ends are
  NODES in one file with one span inside the other (inclusive), whatever their kinds.
- Second block, WITHOUT CLASS-TO-MEMBER LINKS: an undirected edge is left out when one end is a CLASS NODE and the other
  end is a NODE in the same file whose span lies inside the class's span (inclusive) and is not the class itself. A CLASS
  NODE is a NODE whose qualname is bound, in an ast walk of the snapshot file that keeps the first definition of each
  qualname (the same walk and order as nodes.scopes), to an ast.ClassDef. Members at any depth count (methods, nested
  classes, functions nested in methods). Function-in-function nesting edges are kept. The three rewirings are run
  afresh on the remaining edges only (same groups rule, seeds f'{graph}|nc-{mode}|{s}'); SHOWN NODES, TARGETS and NAME
  REACH are unchanged.

Usage: py -I -X utf8 analysis/rederive_public_reach.py > analysis/results/public/rederive_reach.txt
"""
import ast
import collections
import functools
import json
import random
import re
import statistics
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graphloc_traces as gt  # noqa: E402
import nodes  # noqa: E402
import rederive_public_missed_links as ml  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
DATA = HERE.parent / 'data'
N_SEEDS = 20
SWAPS_PER_EDGE = 10
N_BOOT = 2000
MODES = ['a', 'b', 'c']
MODE_LABEL = {'a': '(a) degree-preserving, all edges',
              'b': '(b) swaps within one directory',
              'c': '(c) swaps keeping each edge\'s file pair'}


# ---------------------------------------------------------------- rewiring
def rewire(edges, groups, rng, fileof, mode):
    """edges: list of (u, v), u < v. groups: list of lists of positions in edges (stable under the swaps)."""
    E = list(edges)
    S = set(E)
    for P in groups:
        m = len(P)
        if m < 2:
            continue
        for _ in range(SWAPS_PER_EDGE * m):
            i = P[rng.randrange(m)]
            j = P[rng.randrange(m)]
            if i == j:
                continue
            a, b = E[i]
            c, d = E[j]
            if mode == 'c':
                fa, fb = fileof[a], fileof[b]
                if fa != fb:
                    if fileof[c] != fa:
                        c, d = d, c
                elif rng.random() < 0.5:
                    c, d = d, c
            elif rng.random() < 0.5:
                c, d = d, c
            if a == d or c == b:
                continue
            k1 = (a, d) if a < d else (d, a)
            k2 = (c, b) if c < b else (b, c)
            if k1 in S or k2 in S or k1 == k2:
                continue
            S.discard(E[i]); S.discard(E[j])
            S.add(k1); S.add(k2)
            E[i], E[j] = k1, k2
    return E


def build_rewired(ck, edges, fileof, n_names, tag, grp_stats):
    dirof = [None if f is None else (f.rsplit('/', 1)[0] if '/' in f else '') for f in fileof]
    groups = {'a': [list(range(len(edges)))], 'b': collections.defaultdict(list), 'c': collections.defaultdict(list)}
    for pos, (u, v) in enumerate(edges):
        if dirof[u] is not None and dirof[u] == dirof[v]:
            groups['b'][dirof[u]].append(pos)
        if fileof[u] is not None and fileof[v] is not None:
            groups['c'][tuple(sorted((fileof[u], fileof[v])))].append(pos)
    glist = {'a': groups['a'],
             'b': [groups['b'][k] for k in sorted(groups['b'])],
             'c': [groups['c'][k] for k in sorted(groups['c'])]}
    for m in MODES:
        grp_stats[m][0] += sum(len(g) for g in glist[m] if len(g) >= 2)
        grp_stats[m][1] += len(edges)
    return {m: [adjacency(n_names, rewire(edges, glist[m], random.Random(f'{ck}|{tag}{m}|{s}'), fileof, m))
                for s in range(N_SEEDS)] for m in MODES}


@functools.lru_cache(maxsize=None)
def class_quals(task, path):
    """Qualnames bound to an ast.ClassDef, first definition of each qualname kept (as nodes.scopes does)."""
    src = nodes.file_text(task, path)
    kinds = {}
    if src is None:
        return frozenset()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return frozenset()

    def walk(node, chain):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                c = chain + [child.name]
                kinds.setdefault('.'.join(c), isinstance(child, ast.ClassDef))
                walk(child, c)
            else:
                walk(child, chain)

    walk(tree, [])
    return frozenset(q for q, k in kinds.items() if k)


def adjacency(n, edges):
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return adj


# ---------------------------------------------------------------- stats
def fmt(k, n):
    return f'{k}/{n} ({100.0 * k / n:.1f}%)' if n else f'{k}/0 (n/a)'


def boot(per_task):
    """per_task: list of (num, den). 95% percentile interval of sum(num)/sum(den) over task resamples."""
    rng = random.Random(0)
    T = len(per_task)
    vals = []
    for _ in range(N_BOOT):
        sn = sd = 0.0
        for _ in range(T):
            nu, de = per_task[rng.randrange(T)]
            sn += nu
            sd += de
        if sd:
            vals.append(sn / sd)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


def ci(per_task, signed=False):
    lo, hi = boot(per_task)
    return f'[{100*lo:+.1f}, {100*hi:+.1f}]' if signed else f'[{100*lo:.1f}, {100*hi:.1f}]'


# ---------------------------------------------------------------- snapshot text of any file
def snapshot_texts(task, paths):
    """path -> list of lines, for the requested paths, read from the task's snapshot archive."""
    out = {}
    need = set(paths)
    py = {p for p in need if p.endswith('.py')}
    for p in py:
        txt = nodes.file_text(task, p)
        if txt is not None:
            out[p] = txt.splitlines()
    rest = need - set(out)
    if rest:
        with tarfile.open(DATA / 'snapshots' / f'{task}.tgz', 'r:gz') as tf:
            for m in tf:
                if not m.isfile():
                    continue
                nm = nodes._norm(m.name)
                if nm in rest:
                    out[nm] = tf.extractfile(m).read().decode('utf-8', 'replace').splitlines()
    return out


def main():
    out = []
    P = out.append
    diag = collections.Counter()
    tasks = {}
    for line in (DATA / 'tasks.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t['instance_id']] = t
    runs = list(gt.iter_runs())
    run_tasks = sorted({r['task'] for r in runs})
    regions = {t: ml.changed_regions(tasks[t]['patch'], diag) for t in run_tasks}
    gkey = {t: f"{tasks[t]['repo'].split('/')[1]}_{tasks[t]['base_commit']}" for t in run_tasks}
    kept = [t for t in run_tasks if regions[t]]

    # ---- runs: reads
    run_reads = []
    need_paths = collections.defaultdict(set)
    for r in runs:
        if not regions[r['task']]:
            diag['runs left out (task has no CHANGED REGION)'] += 1
            continue
        reads = [(p, s, e) for p, s, e, _ in ml.read_results(gt.load(r['path']))]
        run_reads.append((r, reads))
        for p, s, e in reads:
            need_paths[r['task']].add(p)

    # ---- per task graph, nodes, rewirings
    G = {}
    rew_cache = {}
    rew_cache2 = {}
    n_cont_total = n_edges_total = n_cm_total = 0
    grp_stats = {m: [0, 0] for m in MODES}  # edges in a group of size >= 2, all edges
    grp_stats2 = {m: [0, 0] for m in MODES}
    for t in kept:
        names, idx, edges, _ = ml.load_graph(gkey[t])
        by_path = collections.defaultdict(list)
        spans = {}
        is_class = set()
        fileof = [None] * len(names)
        for nm in names:
            i = idx[nm]
            rv = nodes.resolve(t, nm)
            if rv is not None:
                fileof[i] = nodes._norm(rv[0])
            sp = nodes.span(t, nm)
            if sp is None or sp.get('end') is None:
                continue
            p = nodes._norm(sp['path'])
            spans[i] = (p, sp['start'], sp['end'])
            by_path[p].append((sp['start'], sp['end'], nm, i))
            if sp['qualname'] in class_quals(t, sp['path']):
                is_class.add(i)
        module_nodes = collections.defaultdict(set)  # path -> module node indices
        for nm in names:
            i = idx[nm]
            if i not in spans and fileof[i] is not None:
                sp = nodes.span(t, nm)
                if sp is not None and sp.get('end') is None:
                    module_nodes[fileof[i]].add(i)
        cont = set()
        for u, v in edges:
            if u in spans and v in spans:
                a, b = spans[u], spans[v]
                if a[0] == b[0] and ((a[1] <= b[1] and b[2] <= a[2]) or (b[1] <= a[1] and a[2] <= b[2])):
                    cont.add((u, v))
        n_cont_total += len(cont)
        n_edges_total += len(edges)

        def in_class(c, x):
            return (c in is_class and x != c and x in spans and spans[x][0] == spans[c][0]
                    and spans[c][1] <= spans[x][1] and spans[x][2] <= spans[c][2])
        cm = {(u, v) for u, v in edges if in_class(u, v) or in_class(v, u)}
        edges2 = [e for e in edges if e not in cm]
        n_cm_total += len(cm)
        ck = gkey[t]
        if ck not in rew_cache:
            rew_cache[ck] = build_rewired(ck, edges, fileof, len(names), '', grp_stats)
            rew_cache2[ck] = build_rewired(ck, edges2, fileof, len(names), 'nc-', grp_stats2)
        noncont = [e for e in edges if e not in cont]
        G[t] = {'names': names, 'by_path': by_path, 'adj': adjacency(len(names), edges),
                'adj_nc': adjacency(len(names), noncont), 'rw': rew_cache[ck], 'module_nodes': module_nodes,
                'adj2': adjacency(len(names), edges2), 'rw2': rew_cache2[ck],
                'n_edges': len(edges), 'n_unresolved': sum(1 for f in fileof if f is None), 'n_names': len(names)}

    # ---- snapshot text per task
    texts = {}
    for t in kept:
        texts[t] = snapshot_texts(t, need_paths[t])

    # ---- per run, per missed pair
    recs = []
    ties = 0
    for r, reads in run_reads:
        t = r['task']
        X = G[t]
        shown = collections.defaultdict(list)
        for p, s, e in reads:
            shown[p]
            if s <= e:
                shown[p].append((s, e))
            else:
                diag['ok reads with start > end'] += 1
        shown_nodes = set()
        for p, ivs in shown.items():
            for s, e, nm, i in X['by_path'].get(p, []):
                if ml.overlaps(ivs, s, e):
                    shown_nodes.add(i)
        shown_mod = set(shown_nodes)
        for p in shown:
            shown_mod |= X['module_nodes'].get(p, set())
        parts = []
        for p, s, e in reads:
            lines = texts[t].get(p)
            if lines is None:
                diag['ok reads of a path not in the snapshot'] += 1
                continue
            if e > len(lines):
                diag['ok reads ending past the snapshot file end'] += 1
            parts.append('\n'.join(lines[max(s, 1) - 1:e]))
        text = '\n'.join(parts)
        for f, s, e in regions[t]:
            if ml.overlaps(shown.get(f, []), s, e):
                continue
            rec = {'task': t, 'arm': r['arm'], 'target': None, 'tshown': False, 'edge': False, 'name': False,
                   'name_nd': False, 'rw': {m: [False] * N_SEEDS for m in MODES}, 'edge_nc': False, 'edge_mod': False,
                   'edge2': False, 'rw2': {m: [False] * N_SEEDS for m in MODES}}
            cands = sorted((ee - ss, nm, i) for ss, ee, nm, i in X['by_path'].get(f, []) if ss <= e and s <= ee)
            if cands:
                if len(cands) > 1 and cands[0][0] == cands[1][0]:
                    ties += 1
                _, nm, ti = cands[0]
                rec['target'] = nm
                rec['tshown'] = ti in shown_nodes
                if not rec['tshown']:
                    rec['edge'] = bool(X['adj'][ti] & shown_nodes)
                    rec['edge_nc'] = bool(X['adj_nc'][ti] & shown_nodes)
                    rec['edge_mod'] = bool(X['adj'][ti] & shown_mod)
                    rec['edge2'] = bool(X['adj2'][ti] & shown_nodes)
                    for m in MODES:
                        rec['rw'][m] = [bool(adj[ti] & shown_nodes) for adj in X['rw'][m]]
                        rec['rw2'][m] = [bool(adj[ti] & shown_nodes) for adj in X['rw2'][m]]
                    short = nm.split('.')[-1]
                    rec['name'] = bool(re.search(r'(?<!\w)' + re.escape(short) + r'(?!\w)', text))
                    rec['name_nd'] = rec['name'] and not (short.startswith('__') and short.endswith('__'))
            recs.append(rec)

    # ---- report
    def per_task(rs, num, den=None):
        """[(num, den)] per task over the tasks present in den (default rs)."""
        den = rs if den is None else den
        d = collections.OrderedDict()
        for x in den:
            d.setdefault(x['task'], [0, 0])[1] += 1
        for x in rs:
            d[x['task']][0] += num(x)
        return [tuple(v) for v in d.values()]

    n = len(recs)
    P('RE-DERIVATION (EXPLORATORY, blind): reach from the code a public starter-agent run was shown')
    P(f'runs: {len(runs)}; runs kept: {len(run_reads)}; tasks with runs: {len(run_tasks)}; tasks kept: {len(kept)}; '
      f'distinct graphs: {len(rew_cache)}; rewired seeds: {N_SEEDS}; swap attempts per edge of a group: {SWAPS_PER_EDGE}; '
      f'bootstrap: {N_BOOT} resamples over tasks, seed 0')
    P('diagnostics: ' + '; '.join(f'{k}: {v}' for k, v in sorted(diag.items())))
    P(f'CHANGED REGIONS over kept tasks: {sum(len(regions[t]) for t in kept)}; TARGET ties broken by node id: {ties}')
    P(f'graph edges (undirected, summed over kept tasks): {n_edges_total}; of which class->member containment: '
      f'{fmt(n_cont_total, n_edges_total)}')
    for m in MODES:
        P(f'  {MODE_LABEL[m]}: edges in a swap group of size >= 2 {fmt(*grp_stats[m])} (summed over distinct graphs)')
    P('')

    P('1. MISSED PAIRS')
    for label, sel in [('all', lambda x: True), ('arm base', lambda x: x['arm'] == 'base'),
                       ('arm skill', lambda x: x['arm'] == 'skill')]:
        rs = [x for x in recs if sel(x)]
        wt = [x for x in rs if x['target']]
        P(f'  [{label}] missed pairs {len(rs)} (tasks {len({x["task"] for x in rs})}); with a TARGET {fmt(len(wt), len(rs))}; '
          f'TARGET shown {fmt(sum(x["tshown"] for x in wt), len(wt))}; TARGET exists and not shown '
          f'{sum(1 for x in wt if not x["tshown"])}')
    P('')

    P('2. EDGE REACH (share of all missed pairs)')
    k = sum(x['edge'] for x in recs)
    P(f'  all: {fmt(k, n)} {ci(per_task(recs, lambda x: x["edge"]))}')
    for a in ('base', 'skill'):
        rs = [x for x in recs if x['arm'] == a]
        P(f'  arm {a}: {fmt(sum(x["edge"] for x in rs), len(rs))} {ci(per_task(rs, lambda x: x["edge"]))}')
    P(f'  sensitivity, class->member containment edges removed: {fmt(sum(x["edge_nc"] for x in recs), n)}')
    P(f'  sensitivity, module nodes of read files also count as shown: {fmt(sum(x["edge_mod"] for x in recs), n)}')
    P('')

    P('3. EDGE REACH ON REWIRED GRAPHS (mean over seeds; range over seeds; true - rewired with interval)')
    P(f'  true: {fmt(k, n)}')
    for m in MODES:
        per_seed = [sum(x['rw'][m][s] for x in recs) for s in range(N_SEEDS)]
        mean_k = statistics.mean(per_seed)
        pt = per_task(recs, lambda x, m=m: x['edge'] - statistics.mean(x['rw'][m]))
        P(f'  {MODE_LABEL[m]}: mean {mean_k:.2f}/{n} ({100*mean_k/n:.1f}%), seeds {min(per_seed)} to {max(per_seed)} '
          f'({100*min(per_seed)/n:.1f} to {100*max(per_seed)/n:.1f}%); true - rewired {100*(k - mean_k)/n:+.1f} pts '
          f'{ci(pt, signed=True)}')
    P('')

    P('4. NAME REACH (share of all missed pairs)')
    kn = sum(x['name'] for x in recs)
    knd = sum(x['name_nd'] for x in recs)
    P(f'  all names: {fmt(kn, n)} {ci(per_task(recs, lambda x: x["name"]))}')
    P(f'  dunder names left out: {fmt(knd, n)} {ci(per_task(recs, lambda x: x["name_nd"]))}')
    for a in ('base', 'skill'):
        rs = [x for x in recs if x['arm'] == a]
        P(f'  arm {a}: all names {fmt(sum(x["name"] for x in rs), len(rs))}; dunder left out '
          f'{fmt(sum(x["name_nd"] for x in rs), len(rs))}')
    P('')

    P('5. EDGE REACH minus NAME REACH (points of all missed pairs)')
    P(f'  edge - name (all names): {100*(k - kn)/n:+.1f} pts '
      f'{ci(per_task(recs, lambda x: int(x["edge"]) - int(x["name"])), signed=True)}')
    P(f'  edge - name (dunder left out): {100*(k - knd)/n:+.1f} pts '
      f'{ci(per_task(recs, lambda x: int(x["edge"]) - int(x["name_nd"])), signed=True)}')
    P('')

    P('6. CROSS TABLE on missed pairs whose TARGET exists and was not shown')
    ns = [x for x in recs if x['target'] and not x['tshown']]
    for key, lab in (('name', 'all names'), ('name_nd', 'dunder names left out')):
        c = collections.Counter((x['edge'], x[key]) for x in ns)
        P(f'  [{lab}] n={len(ns)}')
        P(f'                   name yes   name no')
        P(f'    edge yes      {c[(True, True)]:9d} {c[(True, False)]:9d}')
        P(f'    edge no       {c[(False, True)]:9d} {c[(False, False)]:9d}')
    P('')

    # ---- second block
    k2 = sum(x['edge2'] for x in recs)
    P('WITHOUT CLASS-TO-MEMBER LINKS')
    P(f'graph edges left out (class node to a node inside its span, same file; summed over kept tasks): '
      f'{fmt(n_cm_total, n_edges_total)}; edges remaining {n_edges_total - n_cm_total}')
    for m in MODES:
        P(f'  {MODE_LABEL[m]}: remaining edges in a swap group of size >= 2 {fmt(*grp_stats2[m])} '
          f'(summed over distinct graphs)')
    P('')
    P('2b. EDGE REACH (share of all missed pairs)')
    P(f'  all: {fmt(k2, n)} {ci(per_task(recs, lambda x: x["edge2"]))}')
    for a in ('base', 'skill'):
        rs = [x for x in recs if x['arm'] == a]
        P(f'  arm {a}: {fmt(sum(x["edge2"] for x in rs), len(rs))} {ci(per_task(rs, lambda x: x["edge2"]))}')
    P('')
    P('3b. EDGE REACH ON REWIRED GRAPHS (remaining edges rewired; mean over seeds; range over seeds; '
      'true - rewired with interval)')
    P(f'  true: {fmt(k2, n)}')
    for m in MODES:
        per_seed = [sum(x['rw2'][m][s] for x in recs) for s in range(N_SEEDS)]
        mean_k = statistics.mean(per_seed)
        pt = per_task(recs, lambda x, m=m: x['edge2'] - statistics.mean(x['rw2'][m]))
        P(f'  {MODE_LABEL[m]}: mean {mean_k:.2f}/{n} ({100*mean_k/n:.1f}%), seeds {min(per_seed)} to {max(per_seed)} '
          f'({100*min(per_seed)/n:.1f} to {100*max(per_seed)/n:.1f}%); true - rewired {100*(k2 - mean_k)/n:+.1f} pts '
          f'{ci(pt, signed=True)}')
    P('')
    P('5b. EDGE REACH minus NAME REACH (points of all missed pairs)')
    P(f'  edge - name (all names): {100*(k2 - kn)/n:+.1f} pts '
      f'{ci(per_task(recs, lambda x: int(x["edge2"]) - int(x["name"])), signed=True)}')
    P(f'  edge - name (dunder left out): {100*(k2 - knd)/n:+.1f} pts '
      f'{ci(per_task(recs, lambda x: int(x["edge2"]) - int(x["name_nd"])), signed=True)}')
    P('')
    P('6b. CROSS TABLE on missed pairs whose TARGET exists and was not shown')
    for key, lab in (('name', 'all names'), ('name_nd', 'dunder names left out')):
        c = collections.Counter((x['edge2'], x[key]) for x in ns)
        P(f'  [{lab}] n={len(ns)}')
        P(f'                   name yes   name no')
        P(f'    edge yes      {c[(True, True)]:9d} {c[(True, False)]:9d}')
        P(f'    edge no       {c[(False, True)]:9d} {c[(False, False)]:9d}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
