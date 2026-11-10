"""Fix sites the agent never saw: what kind of graph edge joins them to code it saw? (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_missed_links.py [--seeds 20]

Nothing here was pre-registered and no model is run. analysis/public_runs_missed_regions.py finds that a place of the
fix which a public run never saw is often one hop, in the competition's code graph, from code the run had been
shown. The graph files label every edge `calls` and store each edge in both directions, and they also link a class
to its members (both noted in a public audit of the 127 graphs, Kaggle discussion 745731). So a link at one hop can
be three different things, which this script tells apart from the source code: the missed place is another member
of a class the run was reading; the code the run was shown calls the missed place; or the missed place calls the
code the run was shown. It then repeats the comparison with rewired graphs on the graph without class-member edges.

Sources and the rules CHANGED REGION, SHOWN LINES, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET and REWIRED: as in
analysis/public_runs_missed_regions.py. The regions counted are the ones that script leaves for the graph: a MISSED
REGION inside an ENTITY whose TARGET is not a SHOWN ENTITY. Further rules:
  LINK          a pair (SHOWN ENTITY of the run, TARGET) joined by an edge of the graph (undirected, no self-loops).
  CONTAINMENT   a LINK whose two ENTITIES lie in one file with the span of one inside the span of the other (a
                class and one of its members).
  NAMES         an ENTITY names another if the last component of the other's dotted name stands, as a whole
                identifier, in the source lines of its span.
  CALLEE LINK   a LINK that is not CONTAINMENT in which the SHOWN ENTITY NAMES the TARGET (shown code -> missed
                place: the name of the missed place stands in the code of an entity the run was shown part of).
  CALLER LINK   a LINK that is not CONTAINMENT in which the TARGET NAMES the SHOWN ENTITY (missed place -> shown
                code: nothing in the shown entity says so).
  NAME SHOWN    the last component of the TARGET's dotted name stands, as a whole identifier, in the text returned
                by a read_file call of the run with status ok.
  CALL GRAPH    the graph without its CONTAINMENT edges; its rewiring is the procedure of
                analysis/public_runs_missed_regions.rewired applied to it.
  SEEN SITE, LISTED   as in analysis/public_runs_coedit_sites.py: the TARGET of a CHANGED REGION the run was shown;
                a region left for the graph is LISTED if its TARGET is a graph neighbor of a SEEN SITE of its run.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0.
"""
import argparse
import collections
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import DATA, graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm, pct  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_ent = {}
_words = {}
_call_graph = {}


def entities(task_id, g):
    """node id -> (file, first line, last line) for every ENTITY of the task's graph."""
    if task_id not in _ent:
        M.nodes_of_file(task_id, g, '')            # fills the per-file table of public_runs_missed_regions
        table = {}
        for path in list(M._by_file[task_id]):
            for s0, e0, nid in M.nodes_of_file(task_id, g, path):
                table[nid] = (path, s0, e0)
        _ent[task_id] = table
    return _ent[task_id]


def contains(ent, u, v):
    if u not in ent or v not in ent:
        return False
    (f, a, b), (f2, c, d) = ent[u], ent[v]
    return f == f2 and (a, b) != (c, d) and ((a <= c and d <= b) or (c <= a and b <= d))


def words_of(task_id, ent, nid):
    """The identifiers in the source lines of an ENTITY."""
    key = (task_id, nid)
    if key not in _words:
        f, a, b = ent[nid]
        text = N.file_text(task_id, f) or ''
        _words[key] = set(IDENT.findall('\n'.join(text.split('\n')[a - 1:b])))
    return _words[key]


def short(nid):
    return nid.rsplit('.', 1)[-1]


def stored_edges():
    """Over every graph file: (files, edge types, directed edges without self-loops, those whose reverse is stored)."""
    types = collections.Counter()
    files = n = both = 0
    for p in sorted((DATA / 'graphs').glob('*.json')):
        raw = json.load(open(p, encoding='utf-8'))
        types.update(str(x.get('type')) for x in raw['edges'])
        e = {(x['source'], x['target']) for x in raw['edges'] if x['source'] != x['target']}
        files += 1
        n += len(e)
        both += sum(1 for u, v in e if (v, u) in e)
    return files, types, n, both


def call_graph(task_id, g):
    """(the graph without CONTAINMENT edges, in the form M.rewired takes; number of edges; CONTAINMENT edges)."""
    if g['key'] not in _call_graph:
        ent = entities(task_id, g)
        nbr = M.simple_neighbors(g)
        keep = collections.defaultdict(set)
        n_all = n_cont = 0
        for u, vs in nbr.items():
            for v in vs:
                if u < v:
                    n_all += 1
                    if contains(ent, u, v):
                        n_cont += 1
                    else:
                        keep[u].add(v)
                        keep[v].add(u)
        _call_graph[g['key']] = ({'key': g['key'] + ':call graph', 'nbr': keep}, n_all, n_cont)
    return _call_graph[g['key']]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    rows, runs, entries = [], [], []
    graphs = {}
    n_missed = 0

    def kinds_of(task_id, ent, t, links):
        k = collections.Counter()
        for s in links:
            if contains(ent, s, t):
                k['containment'] += 1
                continue
            fwd = short(t) in words_of(task_id, ent, s)
            back = short(s) in words_of(task_id, ent, t)
            k['callee'] += fwd
            k['caller'] += back
            k['unnamed'] += (not fwd and not back)
        return k

    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        reads = collections.defaultdict(list)
        screen = set()
        for call, _text, parsed in calls_of(load(r['path'])):
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
                    screen.update(IDENT.findall(str(parsed.get('content') or '')))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        if not missed:
            continue
        n_missed += len(missed)
        g = graph_for(tasks[task_id])
        ent = entities(task_id, g)
        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in M.nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)

        def target(f, a, b):
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            return min(cover)[2] if cover else None

        sites = {target(f, a, b) for f, regs in gr.items() for a, b in regs if overlap(a, b, reads.get(f, []))} - {None}
        nbr = M.simple_neighbors(g)
        cg, n_all, n_cont = call_graph(task_id, g)
        graphs[g['key']] = (n_all, n_cont)
        one_cg = M.reach(cg['nbr'], shown)[0]
        rew_maps = [M.rewired(cg, sd) for sd in seeds]
        rew_cg = [M.reach(m, shown)[0] for m in rew_maps]
        n_open = 0
        for f, a, b in missed:
            t = target(f, a, b)
            if t is None or t in shown:
                continue
            n_open += 1
            links = sorted(nbr.get(t, set()) & shown)
            kinds = kinds_of(task_id, ent, t, links)
            row = {'task': task_id, 'arm': r['arm'], 'opened': f in reads, 'target': t, 'd1': bool(links),
                   'containment': kinds['containment'] > 0, 'callee': kinds['callee'] > 0, 'caller': kinds['caller'] > 0,
                   'unnamed': kinds['unnamed'] > 0, 'name': short(t) in screen,
                   'cg1': t in one_cg, 'r_cg1_seeds': [int(t in o) for o in rew_cg]}
            row['call'] = row['callee'] or row['caller'] or row['unnamed']
            row['r_cg1'] = statistics.mean(row['r_cg1_seeds'])
            row['site_run'] = bool(sites)
            from_sites = sorted(nbr.get(t, set()) & sites)
            k2 = kinds_of(task_id, ent, t, from_sites)
            row['listed'] = bool(from_sites)
            row['s_containment'] = k2['containment'] > 0
            row['s_callee'] = k2['callee'] > 0
            row['s_caller'] = k2['caller'] > 0
            row['s_call'] = k2['callee'] > 0 or k2['caller'] > 0 or k2['unnamed'] > 0
            row['cg_listed'] = any(t in cg['nbr'].get(s, ()) for s in sites)
            row['r_cg_listed_seeds'] = [int(any(t in m.get(s, ()) for s in sites)) for m in rew_maps]
            row['r_cg_listed'] = statistics.mean(row['r_cg_listed_seeds'])
            rows.append(row)
        if n_open:
            runs.append({'task': task_id, 'arm': r['arm'], 'list': len(M.reach(nbr, shown)[0]), 'list_cg': len(one_cg)})
        if n_open and sites:
            # every entry a neighbor list of the run's SEEN SITES would hold, by kind of LINK, and whether it is a missed place
            open_targets = {x['target'] for x in rows[-n_open:]}
            cand = set()
            for s in sites:
                cand |= nbr.get(s, set())
            for n in sorted(cand - shown):
                if n not in ent:
                    kind = 'not an ENTITY'
                else:
                    k = kinds_of(task_id, ent, n, sorted(nbr.get(n, set()) & sites))
                    call = k['callee'] or k['caller'] or k['unnamed']
                    kind = ('CONTAINMENT only' if k['containment'] and not call else
                            'CALLER LINK and CALLEE LINK' if k['caller'] and k['callee'] else
                            'CALLER LINK only' if k['caller'] else 'CALLEE LINK only' if k['callee'] else 'neither named')
                entries.append({'task': task_id, 'kind': kind, 'hit': n in open_targets})

    def tasks_of(sel):
        by = collections.defaultdict(list)
        for x in sel:
            by[x['task']].append(x)
        return by

    def ci(sel, key):
        lo, hi = M.boot(tasks_of(sel), lambda xs: M.share(xs, key))
        return f'{pct(sum(x[key] for x in sel), len(sel))} [{100 * lo:.1f}, {100 * hi:.1f}]'

    print('PUBLIC RUNS: fix sites the agent never saw, and the kind of graph edge that joins them to code it saw (EXPLORATORY)')
    print(f'rewired graphs: {len(seeds)} seeds per graph')
    print()
    print('0. Regions and graphs')
    print(f'   MISSED REGIONS left for the graph (inside an ENTITY, TARGET not shown): {len(rows)} in {len(tasks_of(rows))} tasks, '
          f'{len({(x["task"], x["target"]) for x in rows})} distinct TARGETS; one hop from a SHOWN ENTITY: {sum(x["d1"] for x in rows)}')
    tot_all, tot_cont = sum(a for a, _c in graphs.values()), sum(c for _a, c in graphs.values())
    print(f'   graphs of these tasks: {len(graphs)}; edges {tot_all}, of which CONTAINMENT {pct(tot_cont, tot_all)}')
    files, types, n_dir, n_both = stored_edges()
    print(f'   all {files} graph files: edge types {dict(sorted(types.items()))}; directed edges without self-loops {n_dir}, '
          f'of which the reverse edge is stored too {pct(n_both, n_dir)}')
    print()
    print('1. The regions one hop from a SHOWN ENTITY, by kind of LINK (a region can have several)')
    hop = [x for x in rows if x['d1']]
    print(f'   regions {len(hop)}, tasks {len(tasks_of(hop))}')
    print(f'   CONTAINMENT (another member of a class the run was shown part of, or that class): {ci(hop, "containment")}')
    print(f'   CALLEE LINK (shown code names the missed place): {ci(hop, "callee")}')
    print(f'   CALLER LINK (the missed place names shown code): {ci(hop, "caller")}')
    print(f'   a LINK that is not CONTAINMENT and in which neither names the other: {ci(hop, "unnamed")}')
    only_cont = [x for x in hop if x['containment'] and not x['call']]
    print(f'   CONTAINMENT only: {pct(len(only_cont), len(hop))}; some LINK that is not CONTAINMENT: {pct(sum(x["call"] for x in hop), len(hop))}')
    print(f'   CALLEE LINK and no CALLER LINK {sum(x["callee"] and not x["caller"] for x in hop)}; CALLER LINK and no CALLEE LINK '
          f'{sum(x["caller"] and not x["callee"] for x in hop)}; both {sum(x["callee"] and x["caller"] for x in hop)}')
    for label, sel in (('TARGET in a file the run had opened', [x for x in hop if x['opened']]),
                       ('TARGET in a file the run had not opened', [x for x in hop if not x['opened']])):
        print(f'   {label}: regions {len(sel)}; CONTAINMENT only {sum(x["containment"] and not x["call"] for x in sel)}; '
              f'CALLEE LINK {sum(x["callee"] for x in sel)}; CALLER LINK {sum(x["caller"] for x in sel)}; neither named {sum(x["unnamed"] for x in sel)}')
    print()
    print('2. One hop in the CALL GRAPH (no CONTAINMENT edges), true against rewired')

    def line(label, sel, key='cg1'):
        if not sel:
            return
        by = tasks_of(sel)
        rkey = 'r_' + key
        t, rw = M.share(sel, key), M.share(sel, rkey)
        seedvals = [sum(x[rkey + '_seeds'][i] for x in sel) / len(sel) for i in range(len(seeds))]
        lo, hi = M.boot(by, lambda xs: M.share(xs, key))
        dlo, dhi = M.boot(by, lambda xs: M.share(xs, key) - M.share(xs, rkey))
        print(f'   {label}: regions {len(sel)}, tasks {len(by)}; true {sum(x[key] for x in sel)} ({100 * t:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]); '
              f'rewired {100 * rw:.1f}% (seeds {100 * min(seedvals):.1f} to {100 * max(seedvals):.1f}); '
              f'true minus rewired {100 * (t - rw):+.1f} points [{100 * dlo:+.1f}, {100 * dhi:+.1f}]')

    line('all', rows)
    line('base arm', [x for x in rows if x['arm'] == 'base'])
    line('skill arm', [x for x in rows if x['arm'] == 'skill'])
    line('TARGET in a file the run had opened', [x for x in rows if x['opened']])
    line('TARGET in a file the run had not opened', [x for x in rows if not x['opened']])
    by = tasks_of(rows)
    print(f'   mean of per-task shares ({len(by)} tasks): true {100 * statistics.mean(M.share(v, "cg1") for v in by.values()):.1f}%, '
          f'rewired {100 * statistics.mean(M.share(v, "r_cg1") for v in by.values()):.1f}%')
    print(f'   over ALL {n_missed} MISSED REGIONS (the others count as not reached): true {pct(sum(x["cg1"] for x in rows), n_missed)}; '
          f'rewired {100 * sum(x["r_cg1"] for x in rows) / n_missed:.1f}%')
    print()
    print('3. Did the name of the missed place stand in what the run had read? (NAME SHOWN)')
    for label, sel in (('regions with a CALLEE LINK', [x for x in hop if x['callee']]),
                       ('regions with a CALLER LINK and no CALLEE LINK', [x for x in hop if x['caller'] and not x['callee']]),
                       ('regions with CONTAINMENT only', only_cont),
                       ('regions with no LINK', [x for x in rows if not x['d1']])):
        if sel:
            print(f'   {label}: {ci(sel, "name")}')
    print()
    print('4. Size of the neighbor list of everything a run had seen (runs with a region left for the graph)')
    a, b = sorted(x['list'] for x in runs), sorted(x['list_cg'] for x in runs)
    print(f'   runs {len(runs)}; with every edge: median {statistics.median(a):.0f} (quartiles {a[len(a) // 4]} to {a[(3 * len(a)) // 4]}); '
          f'in the CALL GRAPH: median {statistics.median(b):.0f} (quartiles {b[len(b) // 4]} to {b[(3 * len(b)) // 4]})')
    print()
    print('5. From a SEEN SITE to a missed place (runs with a SEEN SITE)')
    sel = [x for x in rows if x['site_run']]
    lst = [x for x in sel if x['listed']]
    print(f'   regions left for the graph {len(sel)} in {len(tasks_of(sel))} tasks; LISTED {len(lst)}')
    print(f'   LISTED by kind of LINK to a SEEN SITE: CONTAINMENT only {sum(x["s_containment"] and not x["s_call"] for x in lst)}; '
          f'CALLEE LINK (the SEEN SITE names the missed place) {sum(x["s_callee"] for x in lst)}; '
          f'CALLER LINK (the missed place names the SEEN SITE) {sum(x["s_caller"] for x in lst)}; '
          f'CALLER LINK and no CALLEE LINK {sum(x["s_caller"] and not x["s_callee"] for x in lst)}; both {sum(x["s_caller"] and x["s_callee"] for x in lst)}')
    line('LISTED in the CALL GRAPH', sel, 'cg_listed')
    print()
    print('6. What the neighbor lists of the SEEN SITES hold, entry by entry (entries not yet shown to the run; one per run and node)')
    print(f'   entries {len(entries)} in {len(tasks_of(entries))} tasks; a missed place of the fix: {pct(sum(x["hit"] for x in entries), len(entries))}')
    for kind in ('CALLER LINK only', 'CALLEE LINK only', 'CALLER LINK and CALLEE LINK', 'CONTAINMENT only', 'neither named', 'not an ENTITY'):
        ks = [x for x in entries if x['kind'] == kind]
        if ks:
            lo, hi = M.boot(tasks_of(ks), lambda xs: M.share(xs, 'hit'))
            print(f'   {kind}: entries {len(ks)} ({100 * len(ks) / len(entries):.1f}% of entries); a missed place of the fix '
                  f'{pct(sum(x["hit"] for x in ks), len(ks))} [{100 * lo:.1f}, {100 * hi:.1f}]')


if __name__ == '__main__':
    main()
