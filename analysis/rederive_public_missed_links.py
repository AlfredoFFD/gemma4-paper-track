"""Independent re-derivation: gold-patch regions the public starter agent never saw, and what kind of code-graph edge
joins them to code it saw (class-member containment, callee link, caller link), plus one hop in the call graph alone
against degree-preserving rewired call graphs.

EXPLORATORY. Written from a brief (definitions in its text) without reading the project's own script or its output.
Starting point: analysis/rederive_public_missed_regions.py (an earlier independent re-derivation; parts copied, not
imported). Raw inputs: the public traces (analysis/graphloc_traces.py), data/tasks.jsonl (gold patch),
data/graphs/<repo>_<commit>.json, node spans and file text from analysis/nodes.py (ast on the task snapshot).

Definitions as implemented:
- CHANGED REGION: one per hunk of the gold patch in a modified file, in old-file line numbers: first to last removed
  line; a block of added lines not directly after a removed line adds the two old lines around the insertion point
  (old lines k and k+1 when inserted after old line k). Context lines are not part of the region. Files the patch
  creates (old side /dev/null, or every hunk -0,0) are left out. GOLD FILE: a file with at least one CHANGED REGION.
- SHOWN LINES: start_line..end_line of each read_file result with status ok (path from the result, else the call's).
- ENTITY: a graph node that nodes.span resolves with an end line (module nodes have none and are not ENTITIES).
- TARGET: the ENTITY of the region's file with the shortest span overlapping the region (ties: smallest node id).
- LINK: an undirected, non-self-loop graph edge between a SHOWN ENTITY of the run and the TARGET.
- CONTAINMENT: both ENTITIES in one file, one span inside the other (inclusive). NAMES: whole-identifier match of the
  other's last dotted component in the source lines of the naming ENTITY's span.
- CALL GRAPH: distinct undirected edges minus CONTAINMENT edges. REWIRED: seeded double-edge swaps on it, 10 attempts
  per edge, 20 seeds per graph, swaps making a self-loop or a duplicate skipped.
- Intervals: 95% percentile bootstrap over tasks, 2,000 resamples, ratio of summed counts.

Usage: py -I -X utf8 analysis/rederive_public_missed_links.py   (prints a report; writes nothing itself)
"""
import collections
import json
import random
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graphloc_traces as gt  # noqa: E402
import nodes  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DATA = HERE.parent / 'data'
N_SEEDS = 20
SWAPS_PER_EDGE = 10
N_BOOT = 2000
BOOT_SEED = 20261110
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def norm(p):
    if not isinstance(p, str):
        return None
    for pre in ('/workspace/', 'workspace/', './'):
        if p.startswith(pre):
            return p[len(pre):]
    return p


def strip_ab(p, pre):
    p = p.split('\t')[0].strip()
    if p == '/dev/null':
        return None
    return p[len(pre):] if p.startswith(pre) else p


# ---------------------------------------------------------------- gold patch -> CHANGED REGIONS
def parse_patch(patch):
    """List of [old_path, new_path, hunks]; a hunk is [a, b, body_lines]. Hunk bodies are consumed by their counts,
    so a removed line that starts with '-- ' is never taken for a file header."""
    files = []
    cur = None
    old = None
    hunk = None
    rem_old = rem_new = 0
    for line in patch.splitlines():
        if hunk is not None and (rem_old > 0 or rem_new > 0):
            k = line[:1]
            if k == '\\':
                hunk[2].append(line)
                continue
            if k in (' ', '') :
                rem_old -= 1
                rem_new -= 1
            elif k == '-':
                rem_old -= 1
            elif k == '+':
                rem_new -= 1
            hunk[2].append(line if line else ' ')
            continue
        if line.startswith('\\') and hunk is not None:
            hunk[2].append(line)
            continue
        hunk = None
        if line.startswith('--- '):
            old = strip_ab(line[4:], 'a/')
        elif line.startswith('+++ '):
            new = strip_ab(line[4:], 'b/')
            cur = [norm(old) if old else None, norm(new) if new else None, []]
            files.append(cur)
        elif line.startswith('@@') and cur is not None:
            m = HUNK.match(line)
            if m:
                a = int(m.group(1))
                b = 1 if m.group(2) is None else int(m.group(2))
                d = 1 if m.group(4) is None else int(m.group(4))
                hunk = [a, b, []]
                cur[2].append(hunk)
                rem_old, rem_new = b, d
    return files


def hunk_region(a, b, body, diag):
    """Old-file line span of one hunk's change, context excluded; None if the hunk changes nothing."""
    ln = a if b > 0 else a + 1  # for -a,0 the hunk inserts after old line a
    lines = []
    prev = None  # kind of the previous body line, "\ No newline" markers skipped
    for x in body:
        if x.startswith('\\'):
            continue
        k = x[:1]
        if k == ' ':
            ln += 1
        elif k == '-':
            lines.append(ln)
            ln += 1
        elif k == '+':
            if prev not in ('-', '+'):
                lines.extend([ln - 1, ln])  # inserted between old lines ln-1 and ln
                diag['added blocks not directly after a removed line'] += 1
        prev = k
    if not lines:
        return None
    return (min(lines), max(lines))


def changed_regions(patch, diag):
    regs = []
    for old, new, hunks in parse_patch(patch):
        if old is None or (hunks and all(h[0] == 0 and h[1] == 0 for h in hunks)):
            diag['created files left out'] += 1
            continue
        if new is None:
            diag['deleted files kept'] += 1
        elif new != old:
            diag['renamed files (old path used)'] += 1
        for a, b, body in hunks:
            r = hunk_region(a, b, body, diag)
            if r is None:
                diag['hunks with no change'] += 1
                continue
            regs.append((old, r[0], r[1]))
    return regs


def overlaps(intervals, s, e):
    return any(rs <= e and s <= re_ for rs, re_ in intervals)


# ---------------------------------------------------------------- traces
def read_results(trace):
    """(path, start, end, content) for every read_file result with status ok."""
    out = []
    for st in trace['steps']:
        for tc in st.get('tool_calls') or []:
            if tc.get('function_name') != 'read_file':
                continue
            obs = st.get('observation') or {}
            try:
                res = json.loads(obs.get('content'))
            except Exception:
                continue
            if not isinstance(res, dict) or res.get('status') != 'ok':
                continue
            path = norm(res.get('filepath') or (tc.get('arguments') or {}).get('filepath'))
            s, e = res.get('start_line'), res.get('end_line')
            if path is None or not isinstance(s, int) or not isinstance(e, int):
                continue
            out.append((path, s, e, res.get('content') or ''))
    return out


# ---------------------------------------------------------------- graphs
def load_graph(key):
    g = json.loads((DATA / 'graphs' / f'{key}.json').read_text(encoding='utf-8'))
    names = sorted({n['id'] for n in g['nodes']} | {e['source'] for e in g['edges']} | {e['target'] for e in g['edges']})
    idx = {n: i for i, n in enumerate(names)}
    edges = set()
    types = collections.defaultdict(set)
    for e in g['edges']:
        u, v = idx[e['source']], idx[e['target']]
        if u != v:
            k = (u, v) if u < v else (v, u)
            edges.add(k)
            types[k].add(e.get('type'))
    return names, idx, sorted(edges), types


def adjacency(n, edges):
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return adj


def rewire(edges, rng):
    E = list(edges)
    S = set(E)
    m = len(E)
    if m < 2:
        return E
    for _ in range(SWAPS_PER_EDGE * m):
        i = rng.randrange(m)
        j = rng.randrange(m)
        if i == j:
            continue
        a, b = E[i]
        c, d = E[j]
        if rng.random() < 0.5:
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


def inside(x, y):
    return y[0] <= x[0] and x[1] <= y[1]


def ident_re(name):
    return re.compile(r'(?<![\w])' + re.escape(name) + r'(?![\w])')


# ---------------------------------------------------------------- stats
def fmt(k, n):
    return f'{k}/{n} ({100.0 * k / n:.1f}%)' if n else f'{k}/0 (n/a)'


def boot_ratio(per_task, rng):
    T = len(per_task)
    if T == 0:
        return (float('nan'), float('nan'))
    vals = []
    for _ in range(N_BOOT):
        sn = sd = 0.0
        for _ in range(T):
            nu, de = per_task[rng.randrange(T)]
            sn += nu
            sd += de
        vals.append(sn / sd if sd else float('nan'))
    vals = sorted(v for v in vals if v == v)
    return (vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))])


# ---------------------------------------------------------------- section 0: all graph files
def all_graph_census(P):
    types = collections.Counter()
    n_rec = n_self = n_dir = n_rev = 0
    rev_by_type = collections.Counter()
    dir_by_type = collections.Counter()
    pairs_total = pairs_rev = 0
    files = sorted((DATA / 'graphs').glob('*.json'))
    for f in files:
        g = json.loads(f.read_text(encoding='utf-8'))
        pairs = set()
        for e in g['edges']:
            types[e.get('type')] += 1
            n_rec += 1
            if e['source'] == e['target']:
                n_self += 1
            else:
                pairs.add((e['source'], e['target']))
        for e in g['edges']:
            if e['source'] != e['target']:
                n_dir += 1
                dir_by_type[e.get('type')] += 1
                if (e['target'], e['source']) in pairs:
                    n_rev += 1
                    rev_by_type[e.get('type')] += 1
        pairs_total += len(pairs)
        pairs_rev += sum(1 for (s, t) in pairs if (t, s) in pairs)
    P(f'  graph files: {len(files)}; edge records: {n_rec}; self-loops: {n_self}')
    P('  edge types: ' + '; '.join(f'{k}: {v}' for k, v in types.most_common()))
    P(f'  directed edge records without self-loops: {n_dir}; with the reverse pair also stored: {fmt(n_rev, n_dir)}')
    P('    by type: ' + '; '.join(f'{k}: {fmt(rev_by_type[k], dir_by_type[k])}' for k in sorted(dir_by_type, key=str)))
    P(f'  distinct directed (source, target) pairs without self-loops: {pairs_total}; with the reverse also stored: '
      f'{fmt(pairs_rev, pairs_total)}')


# ---------------------------------------------------------------- main
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
    regions = {t: changed_regions(tasks[t]['patch'], diag) for t in run_tasks}
    gkey = {t: f"{tasks[t]['repo'].split('/')[1]}_{tasks[t]['base_commit']}" for t in run_tasks}
    kept_tasks = [t for t in run_tasks if regions[t]]

    # ---- per task: entities, containment, call graph, rewired call graphs
    T = {}
    rew_cache = {}
    g_edges_sum = g_cont_sum = 0
    cont_types = collections.Counter()
    ent_dupes = 0
    for t in kept_tasks:
        names, idx, edges, etypes = load_graph(gkey[t])
        ents = {}  # node index -> (path, start, end, name)
        by_path = collections.defaultdict(list)
        seen_span = set()
        for nm in names:
            sp = nodes.span(t, nm)
            if sp is None or sp.get('end') is None:
                continue
            p = nodes._norm(sp['path'])
            i = idx[nm]
            ents[i] = (p, sp['start'], sp['end'], nm)
            by_path[p].append((sp['start'], sp['end'], nm, i))
            key = (p, sp['qualname'])
            if key in seen_span:
                ent_dupes += 1
            seen_span.add(key)
        cont = set()
        for u, v in edges:
            if u in ents and v in ents:
                a, b = ents[u], ents[v]
                if a[0] == b[0] and (inside(a[1:3], b[1:3]) or inside(b[1:3], a[1:3])):
                    cont.add((u, v))
                    for ty in etypes[(u, v)]:
                        cont_types[ty] += 1
        call = [e for e in edges if e not in cont]
        g_edges_sum += len(edges)
        g_cont_sum += len(cont)
        ck = (gkey[t], tuple(call))
        if ck not in rew_cache:
            adjs = [adjacency(len(names), call)]
            for s in range(N_SEEDS):
                rng = random.Random(f'{gkey[t]}|callgraph-rewire|{s}')
                adjs.append(adjacency(len(names), rewire(call, rng)))
            rew_cache[ck] = adjs
        lines_cache = {}

        def span_text(i, ents=ents, t=t, lines_cache=lines_cache):
            p, s, e, _ = ents[i]
            if p not in lines_cache:
                txt = nodes.file_text(t, p)
                lines_cache[p] = txt.splitlines() if txt is not None else []
            return '\n'.join(lines_cache[p][s - 1:e])

        T[t] = {'names': names, 'ents': ents, 'by_path': by_path, 'adj': adjacency(len(names), edges),
                'cont': cont, 'call_adjs': rew_cache[ck], 'span_text': span_text, 'n_edges': len(edges)}

    # ---- per run
    recs = []  # one per (run, MISSED REGION)
    ties = 0
    names_cache = {}

    def names_(t, a, b):
        """ENTITY a NAMES ENTITY b."""
        k = (t, a, b)
        if k not in names_cache:
            last = T[t]['ents'][b][3].split('.')[-1]
            names_cache[k] = bool(ident_re(last).search(T[t]['span_text'](a)))
        return names_cache[k]

    n_runs_kept = 0
    for r in runs:
        t = r['task']
        if not regions[t]:
            diag['runs left out (task has no GOLD FILE)'] += 1
            continue
        n_runs_kept += 1
        X = T[t]
        reads = read_results(gt.load(r['path']))
        shown = collections.defaultdict(list)
        for p, s, e, _ in reads:
            shown[p]
            if s <= e:
                shown[p].append((s, e))
            else:
                diag['ok reads with start > end'] += 1
        read_paths = set(shown)
        text = '\n'.join(c for _, _, _, c in reads)
        shown_ent = set()
        for p, ivs in shown.items():
            for s, e, nm, i in X['by_path'].get(p, []):
                if overlaps(ivs, s, e):
                    shown_ent.add(i)
        for f, s, e in regions[t]:
            if overlaps(shown.get(f, []), s, e):
                continue
            rec = {'arm': r['arm'], 'task': t, 'run': r['run'], 'region': (f, s, e), 'target': None, 'left': False}
            cands = sorted((ee - ss, nm, i) for ss, ee, nm, i in X['by_path'].get(f, []) if ss <= e and s <= ee)
            if cands:
                if len(cands) > 1 and cands[0][0] == cands[1][0]:
                    ties += 1
                _, nm, ti = cands[0]
                rec['target'] = nm
                rec['read_file'] = f in read_paths
                if ti not in shown_ent:
                    rec['left'] = True
                    kinds = set()
                    for si in X['adj'][ti] & shown_ent:
                        pair = (si, ti) if si < ti else (ti, si)
                        if pair in X['cont']:
                            kinds.add('cont')
                            continue
                        c1 = names_(t, si, ti)
                        c2 = names_(t, ti, si)
                        if c1:
                            kinds.add('callee')
                        if c2:
                            kinds.add('caller')
                        if not c1 and not c2:
                            kinds.add('neither')
                    rec['kinds'] = kinds
                    rec['call'] = [bool(adj[ti] & shown_ent) for adj in X['call_adjs']]
                    rec['name_shown'] = bool(ident_re(nm.split('.')[-1]).search(text))
            recs.append(rec)

    left = [x for x in recs if x['left']]
    brng = random.Random(BOOT_SEED)

    P('RE-DERIVATION (EXPLORATORY): missed gold regions and the kind of graph edge that joins them to shown code')
    P(f'runs in traces: {len(runs)}; runs kept: {n_runs_kept}; tasks with runs: {len(run_tasks)}; tasks kept: '
      f'{len(kept_tasks)}; distinct graphs used: {len({gkey[t] for t in kept_tasks})}; rewired seeds: {N_SEEDS}; '
      f'swap attempts per edge: {SWAPS_PER_EDGE}; bootstrap seed {BOOT_SEED}')
    P('diagnostics: ' + '; '.join(f'{k}: {v}' for k, v in sorted(diag.items())))
    P(f'CHANGED REGIONS (over kept tasks): {sum(len(regions[t]) for t in kept_tasks)}; MISSED REGIONS (run-regions): '
      f'{len(recs)}; TARGET ties broken by smallest node id: {ties}; node ids resolving to an already-seen '
      f'(file, qualname): {ent_dupes}')
    P('')

    P('0. GRAPH CENSUS')
    all_graph_census(P)
    P(f'  graphs of the kept tasks (summed over {len(kept_tasks)} tasks; one graph is shared by two tasks): distinct '
      f'undirected edges without self-loops {g_edges_sum}; CONTAINMENT edges {fmt(g_cont_sum, g_edges_sum)}; '
      f'CALL GRAPH edges {g_edges_sum - g_cont_sum}')
    P('    stored types on CONTAINMENT edges (an edge can carry several): '
      + '; '.join(f'{k}: {v}' for k, v in cont_types.most_common()))
    P('')

    # ---- 1
    def kind_block(label, rs):
        n = len(rs)
        hop = [x for x in rs if x['kinds']]
        P(f'  [{label}] regions {n}; tasks {len({x["task"] for x in rs})}; distinct TARGETS '
          f'{len({(x["task"], x["target"]) for x in rs})}; one hop from a SHOWN ENTITY (some LINK) {fmt(len(hop), n)}')
        h = len(hop)
        K = lambda f: sum(1 for x in hop if f(x['kinds']))  # noqa: E731
        P(f'    of those {h}: CONTAINMENT LINK {fmt(K(lambda k: "cont" in k), h)}; CALLEE LINK '
          f'{fmt(K(lambda k: "callee" in k), h)}; CALLER LINK {fmt(K(lambda k: "caller" in k), h)}; '
          f'LINK that is neither {fmt(K(lambda k: "neither" in k), h)}')
        P(f'      CONTAINMENT only {fmt(K(lambda k: k == {"cont"}), h)}; some non-CONTAINMENT LINK '
          f'{fmt(K(lambda k: bool(k - {"cont"})), h)}; CALLEE and no CALLER '
          f'{fmt(K(lambda k: "callee" in k and "caller" not in k), h)}; CALLER and no CALLEE '
          f'{fmt(K(lambda k: "caller" in k and "callee" not in k), h)}; both {fmt(K(lambda k: {"callee", "caller"} <= k), h)}')

    P('1. REGIONS LEFT FOR THE GRAPH and the kind of LINK')
    P(f'  MISSED REGIONS {len(recs)}: with a TARGET {fmt(sum(1 for x in recs if x["target"]), len(recs))}; '
      f'TARGET is a SHOWN ENTITY {sum(1 for x in recs if x["target"] and not x["left"])}')
    kind_block('all', left)
    kind_block('TARGET in a file the run had read from', [x for x in left if x['read_file']])
    kind_block('TARGET in a file the run had not read from', [x for x in left if not x['read_file']])
    P('')

    # ---- 2
    def call_block(label, rs, den_rs=None):
        """Share of den_rs (default rs) with a CALL GRAPH LINK; only rs can have one."""
        den_rs = rs if den_rs is None else den_rs
        n = len(den_rs)
        if n == 0:
            P(f'  [{label}] none'); return
        by_task = collections.defaultdict(lambda: [0, [0] * (N_SEEDS + 1)])
        for x in den_rs:
            by_task[x['task']][0] += 1
        for x in rs:
            for s in range(N_SEEDS + 1):
                by_task[x['task']][1][s] += x['call'][s]
        k_true = sum(v[1][0] for v in by_task.values())
        per_seed = [sum(v[1][s] for v in by_task.values()) for s in range(1, N_SEEDS + 1)]
        mean_k = statistics.mean(per_seed)
        ci_t = boot_ratio([(v[1][0], v[0]) for v in by_task.values()], brng)
        ci_d = boot_ratio([(v[1][0] - statistics.mean(v[1][1:]), v[0]) for v in by_task.values()], brng)
        P(f'  [{label}] tasks {len(by_task)}; true {fmt(k_true, n)} [{100*ci_t[0]:.1f}, {100*ci_t[1]:.1f}]; rewired mean '
          f'{100*mean_k/n:.1f}% ({mean_k:.2f}/{n}), seeds {min(per_seed)} to {max(per_seed)} '
          f'({100*min(per_seed)/n:.1f} to {100*max(per_seed)/n:.1f}%); true - rewired '
          f'{100*(k_true - mean_k)/n:+.1f} pts [{100*ci_d[0]:+.1f}, {100*ci_d[1]:+.1f}]')

    P('2. ONE HOP IN THE CALL GRAPH (a LINK that is a CALL GRAPH edge): true vs REWIRED CALL GRAPHS')
    call_block('regions left for the graph', left)
    for a in ('base', 'skill'):
        call_block(f'arm {a}', [x for x in left if x['arm'] == a])
    call_block('TARGET in a file read from', [x for x in left if x['read_file']])
    call_block('TARGET in a file not read from', [x for x in left if not x['read_file']])
    call_block('ALL MISSED REGIONS (others not reached)', left, recs)
    for a in ('base', 'skill'):
        call_block(f'ALL MISSED REGIONS, arm {a}', [x for x in left if x['arm'] == a], [x for x in recs if x['arm'] == a])
    P('')

    # ---- 3
    P('3. NAME SHOWN (the TARGET\'s last name component appears as an identifier in some ok read_file text of the run)')
    groups = [
        ('with a CALLEE LINK', lambda k: 'callee' in k),
        ('with a CALLER LINK and no CALLEE LINK', lambda k: 'caller' in k and 'callee' not in k),
        ('with CONTAINMENT only', lambda k: k == {'cont'}),
        ('with a LINK that is neither, no CALLEE/CALLER', lambda k: 'neither' in k and not ({'callee', 'caller'} & k)),
        ('with no LINK', lambda k: not k),
        ('all regions left for the graph', lambda k: True),
    ]
    for label, f in groups:
        rs = [x for x in left if f(x['kinds'])]
        P(f'  {label}: {fmt(sum(x["name_shown"] for x in rs), len(rs))}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
