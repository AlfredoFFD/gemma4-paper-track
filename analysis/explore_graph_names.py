"""EXPLORATORY (no rule, no model): what is an edge of the competition's code graphs, measured on the graphs alone?

Reads every graph under data/graphs/ (one JSON per repository snapshot: nodes with `id`, `name`, `text`; edges with
`type`, `source`, `target`). For each graph it asks:

  EDGE TYPES       which edge types exist.
  BOTH WAYS        how many (source, target) pairs are also stored as (target, source).
  NAME OCCURRENCE  for a node U and a graph neighbor V (either direction): does V's text hold U's SIMPLE NAME (the
                   last dotted component of its id) as an identifier token? Then one text search for U's name finds
                   V. Otherwise: does U's own text hold V's simple name? Then V's name stands in the code of U.
                   Otherwise: neither.
  SEARCH HITS      for a node U with at least one neighbor: the number of OTHER nodes of the graph whose text holds
                   U's simple name as a token (what a search for the name would return, counted in nodes), beside
                   the number of U's graph neighbors.
  NAME SHARED      whether a node's simple name is the simple name of another node of the same graph.
  ASYNC            nodes whose text starts (after decorators) with `async def`.

Tokens are identifiers ([A-Za-z_][A-Za-z0-9_]*) of the node text as the graph stores it; a node's text can be
shorter than its source (classes are stored without their methods' bodies), so NAME OCCURRENCE is a lower bound.
Nodes outside the graph (code the graph has no node for) are not searched, so SEARCH HITS is a lower bound too.

Usage: py -I -X utf8 analysis/explore_graph_names.py [--no-write]
Writes analysis/results/explore_graph_names.txt (exactly what it prints).
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
OUT = HERE / 'results' / 'explore_graph_names.txt'
TOK = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
ASYNC = re.compile(r'^\s*(?:@[^\n]*\n\s*)*async\s+def\b')


def quartiles(xs):
    xs = sorted(xs)
    return xs[len(xs) // 4], statistics.median(xs), xs[3 * len(xs) // 4]


def main():
    buf = io.StringIO()

    def p(*a):
        print(*a)
        print(*a, file=buf)

    files = sorted((ROOT / 'data' / 'graphs').glob('*.json'))
    tot = collections.Counter()
    types = collections.Counter()
    by_repo = collections.defaultdict(collections.Counter)
    deg, hits, share = [], [], []
    for f in files:
        g = json.load(open(f, encoding='utf-8'))
        repo = f.name.rsplit('_', 1)[0]
        text = {n['id']: (n.get('text') or '') for n in g['nodes']}
        simple = {i: i.rsplit('.', 1)[-1] for i in text}
        count = collections.Counter(simple.values())
        toks = {i: set(TOK.findall(t)) for i, t in text.items()}
        wanted = set(simple.values())
        holders = collections.defaultdict(set)   # simple name -> nodes whose text holds it
        for i, ts in toks.items():
            for t in ts & wanted:
                holders[t].add(i)
        pairs = set()
        for e in g['edges']:
            types[e.get('type')] += 1
            s, t = e['source'], e['target']
            if s in text and t in text and s != t:
                pairs.add((s, t))
            else:
                tot['edges with an end outside the nodes, or a self-loop'] += 1
        tot['pairs'] += len(pairs)
        tot['pairs stored both ways'] += sum((t, s) in pairs for s, t in pairs)
        nb = collections.defaultdict(set)
        for s, t in pairs:
            nb[s].add(t)
            nb[t].add(s)
        r = by_repo[repo]
        for u, vs in nb.items():
            su = simple[u]
            found = {v for v in vs if su in toks[v]}
            named = {v for v in vs - found if simple[v] in toks[u]}
            for c in (tot, r):
                c['neighbor entries'] += len(vs)
                c['found by a search of the node name'] += len(found)
                c['named in the node text'] += len(named)
                c['neither'] += len(vs) - len(found) - len(named)
            h = holders.get(su, set()) - {u}
            deg.append(len(vs))
            hits.append(len(h))
            if h:
                share.append(len(found) / len(h))
        tot['graphs'] += 1
        tot['nodes'] += len(text)
        tot['nodes with a neighbor'] += len(nb)
        tot['nodes whose simple name another node shares'] += sum(count[simple[i]] > 1 for i in text)
        tot['async nodes'] += sum(bool(ASYNC.match(t)) for t in text.values())

    p('EXPLORATORY. The competition\'s code graphs, read as text: what an edge is.')
    p(f"graphs {tot['graphs']}; nodes {tot['nodes']}; edge records by type: {dict(types)}")
    p(f"distinct (source, target) pairs between two different nodes: {tot['pairs']}; stored both ways: "
      f"{tot['pairs stored both ways']} ({100 * tot['pairs stored both ways'] / tot['pairs']:.1f}%)")
    p(f"nodes with at least one neighbor: {tot['nodes with a neighbor']} of {tot['nodes']} "
      f"({100 * tot['nodes with a neighbor'] / tot['nodes']:.1f}%)")
    p(f"nodes whose text starts with `async def`: {tot['async nodes']}")
    n = tot['neighbor entries']
    p('')
    p(f'1. NAME OCCURRENCE, over the {n} neighbor entries (a node and one of its neighbors, each direction once)')
    for k in ('found by a search of the node name', 'named in the node text', 'neither'):
        p(f'   {k}: {tot[k]} ({100 * tot[k] / n:.1f}%)')
    for repo in sorted(by_repo):
        r = by_repo[repo]
        m = r['neighbor entries']
        p(f"   {repo}: entries {m}; found by a search {100 * r['found by a search of the node name'] / m:.1f}%, "
          f"named in the node text {100 * r['named in the node text'] / m:.1f}%, neither {100 * r['neither'] / m:.1f}%")
    p('')
    p('2. SEARCH HITS against graph neighbors, per node with a neighbor')
    a, b, c = quartiles(deg)
    p(f'   graph neighbors: median {b:g} (quartiles {a} to {c}), mean {statistics.mean(deg):.1f}')
    a, b, c = quartiles(hits)
    p(f'   other nodes whose text holds the node\'s simple name: median {b:g} (quartiles {a} to {c}), '
      f'mean {statistics.mean(hits):.1f}')
    p(f'   of those nodes, the share that are graph neighbors: median {statistics.median(share):.2f}, '
      f'mean {statistics.mean(share):.2f} (nodes with at least one such node: {len(share)})')
    p('')
    p(f"3. NAME SHARED: {tot['nodes whose simple name another node shares']} of {tot['nodes']} nodes "
      f"({100 * tot['nodes whose simple name another node shares'] / tot['nodes']:.1f}%) have a simple name that "
      'another node of the same graph has too')
    if '--no-write' not in sys.argv:
        OUT.write_text(buf.getvalue(), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
