"""Independent re-derivation: gold-patch regions the starter agent never saw, and whether the code graph links them to code it saw.

EXPLORATORY. Written from a brief only (definitions in its text), without reading the project's own script or output.
Raw inputs: the public traces (analysis/graphloc_traces.py), data/tasks.jsonl (gold patch), data/graphs/<repo>_<commit>.json,
and node spans from analysis/nodes.py (ast on the task snapshot).

Definitions as implemented:
- CHANGED REGION: old-file span of each gold hunk `@@ -a,b +c,d @@` (a..a+b-1; b = 0 -> line a; a missing count = 1),
  in files the patch modifies. A file is CREATED when every one of its hunks is `-0,0`; such files are left out.
- SHOWN LINES: start_line..end_line of every read_file result with status ok, on the result's filepath (else the argument's);
  paths normalized by stripping a leading `/workspace/`, `workspace/` or `./`.
- MISSED REGION: a changed region no shown line overlaps. ENTITY: a graph node nodes.span resolves with an end line.
- TARGET: shortest overlapping ENTITY in the region's file (ties: smallest node id). DISTANCE on the undirected graph,
  self-loops dropped, multi-source BFS from the run's SHOWN ENTITIES through any node.
- REWIRED: seeded double-edge swaps, 10 attempts per edge, 20 seeds per graph, degree preserving.
- Intervals: 95% percentile bootstrap over tasks, 2,000 resamples, ratio of summed counts.

Usage: py -I -X utf8 analysis/rederive_public_missed_regions.py   (prints a report; writes nothing itself)
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
BOOT_SEED = 777001
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


def parse_patch(patch):
    """file -> list of (a, b) old-side hunk starts and counts; plus diagnostics."""
    files = collections.OrderedDict()
    cur = None
    for line in patch.splitlines():
        if line.startswith('--- '):
            cur = ('old', strip_ab(line[4:], 'a/'))
        elif line.startswith('+++ ') and cur and cur[0] == 'old':
            old = cur[1]
            new = strip_ab(line[4:], 'b/')
            cur = ('file', norm(old) if old else None, norm(new) if new else None)
            files.setdefault(cur, [])
        elif line.startswith('@@') and cur and cur[0] == 'file':
            m = HUNK.match(line)
            if m:
                a = int(m.group(1))
                b = 1 if m.group(2) is None else int(m.group(2))
                files[cur].append((a, b))
    return files


def changed_regions(patch, diag):
    regs = []
    for (_, old, new), hunks in parse_patch(patch).items():
        if old is None or all(a == 0 and b == 0 for a, b in hunks):
            diag['created files left out'] += 1
            continue
        if new is None:
            diag['deleted files kept'] += 1
        for a, b in hunks:
            if a == 0 and b == 0:
                diag['-0,0 hunk in a modified file (kept as line 0)'] += 1
            regs.append((old, a, a if b == 0 else a + b - 1))
    return regs


def overlaps(intervals, s, e):
    return any(rs <= e and s <= re_ for rs, re_ in intervals)


def shown_lines(trace):
    shown = collections.defaultdict(list)
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
            shown[path]  # a file read with status ok counts as read even if the span is empty
            if s <= e:
                shown[path].append((s, e))
    return shown


# ---------------------------------------------------------------- graphs
def load_graph(key):
    g = json.loads((DATA / 'graphs' / f'{key}.json').read_text(encoding='utf-8'))
    names = sorted({n['id'] for n in g['nodes']} | {e['source'] for e in g['edges']} | {e['target'] for e in g['edges']})
    idx = {n: i for i, n in enumerate(names)}
    edges = set()
    for e in g['edges']:
        u, v = idx[e['source']], idx[e['target']]
        if u != v:
            edges.add((u, v) if u < v else (v, u))
    return names, idx, sorted(edges)


def adjacency(n, edges):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
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


def bfs2(adj, sources):
    dist = {s: 0 for s in sources}
    frontier = list(sources)
    for d in (1, 2):
        nxt = []
        for u in frontier:
            for v in adj[u]:
                if v not in dist:
                    dist[v] = d
                    nxt.append(v)
        frontier = nxt
    return dist


# ---------------------------------------------------------------- stats
def fmt(k, n):
    return f'{k}/{n} ({100.0 * k / n:.1f}%)' if n else f'{k}/0 (n/a)'


def boot_ratio(per_task, rng):
    """per_task: list of (num, den). Percentile interval of sum(num)/sum(den) over task resamples."""
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


def quart(xs):
    if not xs:
        return 'n/a'
    q = statistics.quantiles(xs, n=4, method='inclusive')
    return f'median {statistics.median(xs):.1f}, quartiles {q[0]:.1f} to {q[2]:.1f} (n={len(xs)})'


# ---------------------------------------------------------------- main
def main():
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
    repo = {t: tasks[t]['repo'] for t in run_tasks}

    # graphs: true + rewired adjacency per graph key
    graphs = {}
    for k in sorted({gkey[t] for t in run_tasks if regions[t]}):
        names, idx, edges = load_graph(k)
        adjs = [adjacency(len(names), edges)]
        for s in range(N_SEEDS):
            rng = random.Random(f'{k}|rewire|{s}')
            adjs.append(adjacency(len(names), rewire(edges, rng)))
        graphs[k] = (names, idx, adjs, len(edges))

    # entities per task
    entities = {}
    for t in run_tasks:
        if not regions[t]:
            continue
        names, idx, _, _ = graphs[gkey[t]]
        by_path = collections.defaultdict(list)
        n_ent = 0
        for nm in names:
            sp = nodes.span(t, nm)
            if sp is None or sp.get('end') is None:
                continue
            by_path[nodes._norm(sp['path'])].append((sp['start'], sp['end'], nm, idx[nm]))
            n_ent += 1
        entities[t] = by_path
        diag['entities (summed over tasks)'] += n_ent

    recs = []      # one per (run, missed region)
    runrecs = []   # one per kept run
    ties = 0
    for r in runs:
        t = r['task']
        if not regions[t]:
            diag['runs left out (task has no gold file)'] += 1
            continue
        tr = gt.load(r['path'])
        shown = shown_lines(tr)
        names, idx, adjs, _ = graphs[gkey[t]]
        ents = entities[t]
        shown_ent = set()
        for p, ivs in shown.items():
            for s, e, nm, i in ents.get(p, []):
                if overlaps(ivs, s, e):
                    shown_ent.add(i)
        dists = [bfs2(adj, shown_ent) for adj in adjs]
        frontier = [sum(1 for v in d.values() if v == 1) for d in dists]
        missed = [(f, s, e) for f, s, e in regions[t] if not overlaps(shown.get(f, []), s, e)]
        some_shown = len(missed) < len(regions[t])
        rid = (r['run'], r['arm'], t)
        rr = {'rid': rid, 'arm': r['arm'], 'task': t, 'repo': repo[t], 'n_missed': len(missed),
              'some_shown': some_shown, 'frontier': frontier, 'within1': [False] * (N_SEEDS + 1),
              'n_shown_ent': len(shown_ent)}
        for f, s, e in missed:
            cands = [(ee - ss, nm, i) for ss, ee, nm, i in ents.get(f, []) if ss <= e and s <= ee]
            rec = {'rid': rid, 'arm': r['arm'], 'task': t, 'repo': repo[t], 'region': (f, s, e),
                   'some_shown': some_shown, 'read_file': None, 'target': None, 'd': None}
            if cands:
                cands.sort()
                if len(cands) > 1 and cands[0][0] == cands[1][0]:
                    ties += 1
                _, nm, i = cands[0]
                rec['target'] = nm
                tf = nodes._norm(nodes.span(t, nm)['path'])
                rec['read_file'] = tf in shown
                if i in shown_ent:
                    rec['d'] = [0] * (N_SEEDS + 1)
                else:
                    rec['d'] = [d.get(i, 3) for d in dists]  # 3 = farther than 2
                for k in range(N_SEEDS + 1):
                    if rec['d'][k] <= 1:
                        rr['within1'][k] = True
            recs.append(rec)
        runrecs.append(rr)

    out = []
    P = out.append
    brng = random.Random(BOOT_SEED)
    arms = ['base', 'skill']

    P('RE-DERIVATION (EXPLORATORY): missed gold regions and the code graph, public starter-agent runs')
    P(f'runs in traces: {len(runs)}; tasks with runs: {len(run_tasks)}; graphs used: {len(graphs)}; '
      f'rewired seeds per graph: {N_SEEDS}; swap attempts per edge: {SWAPS_PER_EDGE}')
    P('diagnostics: ' + '; '.join(f'{k}: {v}' for k, v in sorted(diag.items())))
    P(f'TARGET ties broken by node id: {ties}')
    P('')

    # ---- 1
    P('1. RUNS AND MISSED REGIONS')
    for label, sel in [('base', lambda x: x['arm'] == 'base'), ('skill', lambda x: x['arm'] == 'skill'), ('both', lambda x: True)]:
        rs = [x for x in runrecs if sel(x)]
        wm = [x for x in rs if x['n_missed']]
        P(f'  [{label}] runs kept {len(rs)} (tasks {len({x["task"] for x in rs})}); '
          f'runs with >=1 MISSED REGION {fmt(len(wm), len(rs))}; '
          f'of those: shown some CHANGED REGION {fmt(sum(x["some_shown"] for x in wm), len(wm))}, '
          f'shown none {fmt(sum(not x["some_shown"] for x in wm), len(wm))}; '
          f'MISSED REGIONS {sum(x["n_missed"] for x in rs)} '
          f'(of {sum(len(regions[x["task"]]) for x in rs)} run-regions); tasks with a missed region {len({x["task"] for x in wm})}')
    P('')

    # ---- 2
    P('2. ADDRESSABILITY AND DISTANCE 0')
    addr = [x for x in recs if x['target'] is not None]
    left = [x for x in addr if x['d'][0] != 0]
    P(f'  MISSED REGIONS {len(recs)}: addressable {fmt(len(addr), len(recs))}, not addressable {fmt(len(recs) - len(addr), len(recs))}')
    na_py = sum(1 for x in recs if x['target'] is None and x['region'][0].endswith('.py'))
    P(f'    not addressable in .py files: {na_py}; in other files: {len(recs) - len(addr) - na_py}')
    P(f'  addressable at DISTANCE 0 (TARGET is a SHOWN ENTITY): {fmt(len(addr) - len(left), len(addr))}')
    P(f'  LEFT FOR THE GRAPH: regions {len(left)}; tasks {len({x["task"] for x in left})}; '
      f'distinct (task, region) {len({(x["task"], x["region"]) for x in left})}; '
      f'distinct TARGETS {len({(x["task"], x["target"]) for x in left})}')
    P(f'    TARGET in a file the run had read from: {fmt(sum(x["read_file"] for x in left), len(left))}')
    P('')

    # ---- 3
    def block(label, rs):
        if not rs:
            P(f'  [{label}] none'); return
        by_task = collections.defaultdict(list)
        for x in rs:
            by_task[x['task']].append(x)
        P(f'  [{label}] regions {len(rs)}, tasks {len(by_task)}')
        for name, cut in [('DISTANCE 1', 1), ('DISTANCE 1 or 2', 2)]:
            k_true = sum(1 for x in rs if x['d'][0] <= cut)
            per_seed = [sum(1 for x in rs if x['d'][s] <= cut) / len(rs) for s in range(1, N_SEEDS + 1)]
            rew_mean = statistics.mean(per_seed)
            pt_true = [(sum(1 for x in v if x['d'][0] <= cut), len(v)) for v in by_task.values()]
            pt_diff = [(sum(1 for x in v if x['d'][0] <= cut)
                        - sum(sum(1 for x in v if x['d'][s] <= cut) for s in range(1, N_SEEDS + 1)) / N_SEEDS, len(v))
                       for v in by_task.values()]
            ci_t = boot_ratio(pt_true, brng)
            ci_d = boot_ratio(pt_diff, brng)
            diff = k_true / len(rs) - rew_mean
            P(f'    {name:16s} true {fmt(k_true, len(rs))} [{100*ci_t[0]:.1f}, {100*ci_t[1]:.1f}]; '
              f'rewired mean {100*rew_mean:.1f}% (~{rew_mean*len(rs):.1f}/{len(rs)}), seeds {100*min(per_seed):.1f} to {100*max(per_seed):.1f}%; '
              f'true - rewired {100*diff:+.1f} pts [{100*ci_d[0]:+.1f}, {100*ci_d[1]:+.1f}]')

    P('3. REGIONS LEFT FOR THE GRAPH: TRUE vs REWIRED (by-task 95% bootstrap intervals)')
    block('all', left)
    for a in arms:
        block(f'arm {a}', [x for x in left if x['arm'] == a])
    block('TARGET in a file read', [x for x in left if x['read_file']])
    block('TARGET in a file not read', [x for x in left if not x['read_file']])
    block('run shown some CHANGED REGION', [x for x in left if x['some_shown']])
    block('run shown no CHANGED REGION', [x for x in left if not x['some_shown']])
    for rp in sorted({x['repo'] for x in left}):
        block(f'repo {rp}', [x for x in left if x['repo'] == rp])
    P('')

    # ---- 4
    P('4. ALL MISSED REGIONS WITHIN ONE HOP (DISTANCE 0 or 1; not addressable counts as not within)')
    def w1(x, s):
        return x['d'] is not None and x['d'][s] <= 1
    k_true = sum(w1(x, 0) for x in recs)
    per_seed = [sum(w1(x, s) for x in recs) for s in range(1, N_SEEDS + 1)]
    by_task = collections.defaultdict(list)
    for x in recs:
        by_task[x['task']].append(x)
    ci = boot_ratio([(sum(w1(x, 0) for x in v), len(v)) for v in by_task.values()], brng)
    P(f'  regions: true {fmt(k_true, len(recs))} [{100*ci[0]:.1f}, {100*ci[1]:.1f}]; rewired mean '
      f'{statistics.mean(per_seed):.1f}/{len(recs)} ({100*statistics.mean(per_seed)/len(recs):.1f}%), '
      f'seeds {min(per_seed)} to {max(per_seed)}')
    wm = [x for x in runrecs if x['n_missed']]
    rk_true = sum(x['within1'][0] for x in wm)
    rk_seed = [sum(x['within1'][s] for x in wm) for s in range(1, N_SEEDS + 1)]
    P(f'  runs with a MISSED REGION in which some MISSED REGION is within one hop: true {fmt(rk_true, len(wm))}; '
      f'rewired mean {statistics.mean(rk_seed):.1f}/{len(wm)} ({100*statistics.mean(rk_seed)/len(wm):.1f}%), seeds {min(rk_seed)} to {max(rk_seed)}')
    for a in arms:
        wa = [x for x in wm if x['arm'] == a]
        ks = [sum(x['within1'][s] for x in wa) for s in range(1, N_SEEDS + 1)]
        P(f'    arm {a}: true {fmt(sum(x["within1"][0] for x in wa), len(wa))}; rewired mean {statistics.mean(ks):.1f}, seeds {min(ks)} to {max(ks)}')
    P('')

    # ---- 5
    P('5. FRONTIER SIZE per run with a MISSED REGION (nodes at DISTANCE 1 that are not SHOWN ENTITIES, any node kind)')
    P(f'  true: {quart([x["frontier"][0] for x in wm])}')
    P(f'  rewired (per run, mean over the {N_SEEDS} seeds; then median and quartiles over runs): '
      f'{quart([statistics.mean(x["frontier"][1:]) for x in wm])}')
    med_seed = [statistics.median([x['frontier'][s] for x in wm]) for s in range(1, N_SEEDS + 1)]
    P(f'  rewired per-seed median over runs: {min(med_seed):.1f} to {max(med_seed):.1f}')
    P(f'  runs with no SHOWN ENTITY: {sum(1 for x in wm if x["n_shown_ent"] == 0)}; '
      f'runs with an empty true frontier: {sum(1 for x in wm if x["frontier"][0] == 0)}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
