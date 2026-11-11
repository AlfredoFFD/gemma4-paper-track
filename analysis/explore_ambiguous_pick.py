"""Which same-named definition is the right one? Four ways to pick one, on the ambiguous missed places (EXPLORATORY)

EXPLORATORY, written after all results were seen; nothing here was registered.

Usage: py -I -X utf8 analysis/explore_ambiguous_pick.py > analysis/results/public/explore_ambiguous_pick.txt

No model is run. Section 5 of analysis/public_runs_lexical_reach_both.py (stored output
analysis/results/public/lexical_reach_both.txt) counts the AMBIGUOUS OPEN PAIRS of the public runs: a missed place
whose TARGET's SHORT NAME is shared by at least one other node id of the task's graph. A search by name in the shown
code reaches 227 of the 356 (FORWARD, ALL), but a name names k definitions. This script asks, on those 227, how often
each of four ways of picking ONE of the k same-named nodes picks the TARGET.

Reuse. PAIR, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET, OPEN PAIR, SHORT NAME, EDGE, FORWARD (ALL), the dunder rule
and the bootstrap are those of analysis/public_runs_lexical_reach_both.py and the modules it imports; the functions
are called from them (public_runs_lexical_reach_both.kept_text, public_runs_lexical_reach.shown_words and is_dunder,
public_runs_missed_links.entities, short and call_graph, public_runs_missed_regions.nodes_of_file, reach, boot and
share, fork_states.graph_for, the trace and gold loaders). The loop that builds the PAIRS sits inside that script's
main, which returns nothing, so the loop is re-derived here with the same definitions, line for line; the gate of
section 0 checks that it gives the stored counts. The one addition to the loop: the read_file calls are also kept in
trace order (the stored loop keeps them per file only), for the NEAREST rule.

The four picks, among the k node ids of the task's graph whose SHORT NAME is the TARGET's (the TARGET included):
  EDGE          right when the TARGET is one edge of the CALL GRAPH from a SHOWN ENTITY (the stored EDGE).
  RANDOM        a uniform pick: right with probability 1/k (expected value; the stored 30.3).
  RELEASE RULE  the node the October release's resolver returns for the short name. Source: the function
                resolve_node_name in swegemma/graph/graph_utils.py of swegemma 0.2.11, read from the wheel
                data/wheelhouse/latest/swegemma-0.2.11-py3-none-any.whl (lines 341-433 of that file). The path the
                task named, data/wheelhouse/v28/src/swegemma/graph/graph_utils.py, holds swegemma 0.2.7 and has no
                such function. Importing the release is not practical (it needs networkx, numpy and cachetools, and
                this script uses the standard library only), so its rule is re-implemented below, every branch; the
                script stops unless the function's source in the wheel has the sha256 pinned in RESOLVER_SHA256.
                The lines that decide every name counted here (all node ids hold a dot, so a SHORT NAME is never a
                node id itself; it ends at least two node ids after a dot, so the first suffix branch returns):
                    378:     node_set = set(node_list)
                    379:     if query in node_set:
                    380:         return query
                    381:     if bare_query in node_set:
                    382:         return bare_query
                    384:     # 1. Exact suffix matching on delimiter boundary (., ;, /)
                    385:     candidates = [
                    386:         n
                    387:         for n in node_list
                    388:         if n.endswith(f'.{bare_query}')
                    389:         or n.endswith(f';{bare_query}')
                    390:         or n.endswith(f'/{bare_query}')
                    391:     ]
                    392:     if candidates:
                    393:         return min(
                    394:             candidates,
                    395:             key=lambda x: (len(x.split('.')), len(x), x),
                    396:         )
                The description given elsewhere (fewest dotted parts, then shortest, then first by name, among the
                nodes whose dotted name ends in the name) matches these lines; the source adds the exact-id check
                first and the delimiters ';' and '/', which no node id of these graphs holds.
  NEAREST       the APPEARANCE READ is the first read_file call of the run (trace order, status ok) whose returned
                line range, in the snapshot text, holds the SHORT NAME as a whole identifier; its file is the
                APPEARANCE FILE. Each same-named node gets its file from analysis/nodes.resolve (None if no module
                prefix matches). Pick the node whose file's directory shares the most leading components with the
                APPEARANCE FILE's directory; among those, one in the APPEARANCE FILE itself; then the smallest node id.
                The same rule with the last tie broken uniformly instead of by node id is printed beside it.
Intervals: 95% bootstrap over tasks (all pairs of a task together), 2,000 resamples, random.Random(0) created afresh
for each interval, percentiles 2.5 and 97.5 (analysis/public_runs_missed_regions.boot). A difference is the
difference of the two pooled shares within each resample.
"""
import ast
import collections
import hashlib
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_lexical_reach as X  # noqa: E402
import public_runs_lexical_reach_both as B  # noqa: E402
import public_runs_missed_links as L  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

WHEEL = ROOT / 'data' / 'wheelhouse' / 'latest' / 'swegemma-0.2.11-py3-none-any.whl'
RESOLVER_FILE = 'swegemma/graph/graph_utils.py'
RESOLVER_SHA256 = 'c10fbe3372edb95eeaec5fc68cf14aab731f89fbb6c186c47d3e467e6d85254a'

# the stored numbers of analysis/results/public/lexical_reach_both.txt, section 5
GATE = {'PAIRS': 1326, 'OPEN PAIRS': 859, 'AMBIGUOUS OPEN PAIRS': 356, 'tasks': 21, 'EDGE': 94, 'FORWARD (ALL)': 227,
        'random-pick expectation': '30.3', 'EDGE among the FORWARD reaches': 70,
        'AMBIGUOUS OPEN PAIRS without double-underscore names': 158}


def check_resolver_source():
    src = zipfile.ZipFile(WHEEL).read(RESOLVER_FILE).decode('utf-8')
    fn = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'resolve_node_name']
    if len(fn) != 1:
        sys.exit(f'stop: resolve_node_name not found once in {RESOLVER_FILE} of {WHEEL.relative_to(ROOT).as_posix()}')
    seg = ast.get_source_segment(src, fn[0])
    got = hashlib.sha256(seg.encode('utf-8')).hexdigest()
    if got != RESOLVER_SHA256:
        sys.exit(f'stop: the source of resolve_node_name has sha256 {got}, not the pinned {RESOLVER_SHA256}')
    return fn[0].lineno, fn[0].end_lineno


def _rank(x):
    return (len(x.split('.')), len(x), x)


def resolve_node_name(target_str, node_list):
    """swegemma 0.2.11 resolve_node_name, every branch, with the graph given as its list of node ids."""
    if not node_list:
        return None
    query = (target_str.decode('utf-8', errors='replace') if isinstance(target_str, bytes) else str(target_str)).strip()
    if not query:
        return None
    bare_query = query.split(';', 1)[1] if ';' in query else query
    node_list = [n.decode('utf-8', errors='replace') if isinstance(n, bytes) else str(n) for n in node_list]
    if not node_list:
        return None
    node_set = set(node_list)
    if query in node_set:
        return query
    if bare_query in node_set:
        return bare_query
    candidates = [n for n in node_list
                  if n.endswith(f'.{bare_query}') or n.endswith(f';{bare_query}') or n.endswith(f'/{bare_query}')]
    if candidates:
        return min(candidates, key=_rank)
    lower_query = bare_query.lower()
    lower_full = query.lower()
    ci_exact = [n for n in node_list if n.lower() == lower_full or n.lower() == lower_query]
    if ci_exact:
        return min(ci_exact, key=_rank)
    ci_candidates = [n for n in node_list if n.lower().endswith(f'.{lower_query}')
                     or n.lower().endswith(f';{lower_query}') or n.lower().endswith(f'/{lower_query}')]
    if ci_candidates:
        return min(ci_candidates, key=_rank)
    if not any(c.isspace() for c in bare_query):
        sub_candidates = [n for n in node_list if bare_query in n or lower_query in n.lower()]
        if sub_candidates:
            return min(sub_candidates, key=_rank)
    return None


def shared_dirs(p, q):
    a, b = p.split('/')[:-1], q.split('/')[:-1]
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def build():
    """The AMBIGUOUS OPEN PAIRS, by the loop of public_runs_lexical_reach_both.main re-derived."""
    tasks = load_tasks()
    gold = gold_regions()
    n_pairs = n_open = 0
    name_counts, resolved = {}, {}
    amb = []
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        reads = collections.defaultdict(list)
        order = []                                     # the read_file calls in trace order (added here)
        for call, _text, parsed in calls_of(load(r['path'])):
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
                    order.append((f, s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        if not missed:
            continue
        n_pairs += len(missed)
        g = graph_for(tasks[task_id])
        L.entities(task_id, g)
        if g['key'] not in name_counts:
            name_counts[g['key']] = collections.Counter(L.short(n) for n in g['ids'])
        counts = name_counts[g['key']]
        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in M.nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)
        words = X.shown_words(task_id, reads)
        cg = L.call_graph(task_id, g)[0]
        front = M.reach(cg['nbr'], shown)[0]
        read_words = {}
        for f, a, b in missed:
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            t = min(cover)[2] if cover else None
            if t is None or t in shown:
                continue
            n_open += 1
            name = L.short(t)
            k = counts[name]
            if k <= 1:
                continue
            same = sorted(n for n in g['ids'] if L.short(n) == name)
            if len(same) != k:
                sys.exit(f'stop: {len(same)} same-named node ids against a count of {k}')
            row = {'task': task_id, 'name': name, 'k': k, 'dunder': X.is_dunder(name),
                   'edge': int(t in front), 'fwd': int(name in words), 'random': 1 / k}
            # EDGE, shared: the TARGET in the reach, and a uniform pick among the same-named nodes in the reach
            in_front = [n for n in same if n in front]
            row['edge_m'] = len(in_front)
            row['edge_shared'] = (1 / len(in_front)) if t in front else 0.0
            # RELEASE RULE
            key = (g['key'], name)
            if key not in resolved:
                resolved[key] = resolve_node_name(name, g['ids'])
            pick = resolved[key]
            row['release_pick_same_name'] = int(pick is not None and L.short(pick) == name)
            row['release'] = int(pick == t)
            # NEAREST
            app = None
            for i, (rf, s, e) in enumerate(order):
                if i not in read_words:
                    read_words[i] = set(X.IDENT.findall(B.kept_text(task_id, rf, [(s, e)])))
                if name in read_words[i]:
                    app = rf
                    break
            row['has_app'] = int(app is not None)
            row['nearest'] = row['nearest_u'] = 0.0
            if app is not None:
                scored = []
                for n in same:
                    res = N.resolve(task_id, n)
                    nf = norm(res[0]) if res else None
                    scored.append(((shared_dirs(nf, app), int(nf == app)) if nf else (-1, 0), n))
                best = max(sc for sc, _n in scored)
                tied = sorted(n for sc, n in scored if sc == best)
                row['nearest'] = int(tied[0] == t)
                row['nearest_u'] = (1 / len(tied)) if t in tied else 0.0
                row['nearest_ties'] = len(tied)
                row['app_is_target_file'] = int(app == L.entities(task_id, g)[t][0])
            amb.append(row)
    return n_pairs, n_open, amb


def by_task(sel):
    out = collections.defaultdict(list)
    for x in sel:
        out[x['task']].append(x)
    return out


def total(sel, k):
    return sum(x[k] for x in sel)


def fmt_n(v):
    return f'{v:.1f}' if abs(v - round(v)) > 1e-9 else f'{round(v)}'


def share_line(label, sel, k):
    bt = by_task(sel)
    lo, hi = M.boot(bt, lambda xs: M.share(xs, k))
    n = total(sel, k)
    return (f'{label}: {fmt_n(n)} of {len(sel)} ({100 * n / len(sel):.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]; '
            f'{len(bt)} tasks)')


def diff_ci(sel, k1, k2):
    d = M.share(sel, k1) - M.share(sel, k2)
    lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, k1) - M.share(xs, k2))
    return d, lo, hi


def diff_line(label, sel, k1, k2):
    d, lo, hi = diff_ci(sel, k1, k2)
    return f'{label}: {100 * d:+.1f} points [{100 * lo:+.1f}, {100 * hi:+.1f}] ({len(by_task(sel))} tasks)'


def excluding_zero(sel):
    """The rules whose paired difference with EDGE has an interval that excludes zero, and those whose holds it."""
    out, held = [], []
    for name, k2 in (('RANDOM', 'random'), ('RELEASE RULE', 'release'), ('NEAREST', 'nearest')):
        _d, lo, hi = diff_ci(sel, 'edge', k2)
        (out if lo > 0 or hi < 0 else held).append(name)
    return out, held


def names(xs):
    return ' and '.join(xs) if len(xs) < 3 else ', '.join(xs[:-1]) + ' and ' + xs[-1]


def table(sel):
    print(f'   pairs {len(sel)} in {len(by_task(sel))} tasks; k: '
          + (lambda s: f'median {s[len(s) // 2]}, quartiles {s[len(s) // 4]} and {s[(3 * len(s)) // 4]}, '
             f'range {s[0]} to {s[-1]}')(sorted(x['k'] for x in sel)))
    print('   ' + share_line('(a) EDGE', sel, 'edge'))
    print('   ' + share_line('(b) RANDOM (expected, sum of 1/k)', sel, 'random'))
    print('   ' + share_line('(c) RELEASE RULE', sel, 'release'))
    print('   ' + share_line('(d) NEAREST', sel, 'nearest'))
    print('   beside them, not one of the four:')
    print('      ' + share_line('EDGE, shared (expected; right with 1/m when the TARGET is in the reach and m of its '
                                'same-named nodes are)', sel, 'edge_shared'))
    print('      ' + share_line('NEAREST, last tie broken uniformly (expected)', sel, 'nearest_u'))
    e = [x for x in sel if x['edge']]
    print(f'      of the {len(e)} EDGE picks, the TARGET is the only same-named node in the reach in '
          f'{sum(x["edge_m"] == 1 for x in e)}')
    print(f'      NEAREST: APPEARANCE FILE is the TARGET\'s own file in {sum(x.get("app_is_target_file", 0) for x in sel)}'
          f' of {len(sel)}; nodes tied after the file rule: '
          + (lambda s: f'median {s[len(s) // 2]}, range {s[0]} to {s[-1]}')(sorted(x['nearest_ties'] for x in sel)))
    print('   paired differences, in points of share:')
    for lab, k2 in (('EDGE minus RANDOM', 'random'), ('EDGE minus RELEASE RULE', 'release'),
                    ('EDGE minus NEAREST', 'nearest')):
        print('      ' + diff_line(lab, sel, 'edge', k2))


JUDGMENT = [
    'The release resolver was read from the wheel data/wheelhouse/latest/swegemma-0.2.11-py3-none-any.whl; the path '
    'named in the task (data/wheelhouse/v28/src/...) holds swegemma 0.2.7, whose graph_utils.py has no resolve_node_name.',
    'The resolver is re-implemented (every branch), not imported: the release imports networkx, numpy and cachetools. '
    'Its source in the wheel is pinned by sha256. It is given the graph as the list of node ids of the graph file, in '
    'file order (the order matters only for exact ties, which its third key, the id itself, breaks).',
    'EDGE counts a pick as right whenever the TARGET is in the reach (the stored rule), even when other same-named '
    'nodes are in the reach too; the line "EDGE, shared" prints the expected count if such ties were broken uniformly.',
    'RANDOM is the expected value (sum of 1/k), not a seeded draw.',
    'NEAREST: "the file where the name appeared" is the file of the first read_file call (trace order, status ok) whose '
    'line range, in the snapshot text, holds the name as a whole identifier; the rule as worded in the task, not its '
    'fallback, was used. Every FORWARD pair has such a read. "Leading directory path" counts shared leading directory '
    'components (the file name left out); ties are then broken by being in the APPEARANCE FILE itself, then by the '
    'smallest node id. A same-named node whose id resolves to no file of the snapshot ranks last.',
    'A node\'s file for NEAREST comes from analysis/nodes.resolve, so a same-named node that is not an ENTITY (no '
    'line span) still has a file.',
    '"Without double-underscore names" uses the dunder rule of analysis/public_runs_lexical_reach.is_dunder (longer '
    'than four characters, starting and ending with two underscores), as the stored 158 does.',
    'Section 3 asks the resolver for the TARGET\'s short name exactly as it stands; no other spelling (a dotted '
    'partial path, another case) was tried.',
    'A share of a fractional count (RANDOM, the uniform tie lines) is the pooled sum over the pooled pairs, '
    'bootstrapped the same way as the counts.',
]


def main():
    t0 = time.time()
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    lo_line, hi_line = check_resolver_source()
    n_pairs, n_open, amb = build()
    fr = [x for x in amb if x['fwd']]
    got = {'PAIRS': n_pairs, 'OPEN PAIRS': n_open, 'AMBIGUOUS OPEN PAIRS': len(amb), 'tasks': len(by_task(amb)),
           'EDGE': total(amb, 'edge'), 'FORWARD (ALL)': len(fr),
           'random-pick expectation': f'{sum(1 / x["k"] for x in fr):.1f}',
           'EDGE among the FORWARD reaches': total(fr, 'edge'),
           'AMBIGUOUS OPEN PAIRS without double-underscore names': sum(not x['dunder'] for x in amb)}

    print('EXPLORATORY, written after all results were seen; nothing here was registered.')
    print('PUBLIC RUNS: which same-named definition is the right one? Four ways to pick one, on the ambiguous missed places')
    print()
    print('0. GATE (the stored numbers of analysis/results/public/lexical_reach_both.txt)')
    for k, want in GATE.items():
        if got[k] != want:
            print(f'   MISMATCH: {k}: got {got[k]}, stored {want}')
            sys.exit(f'stop: the gate does not reproduce; first mismatch: {k}: got {got[k]}, stored {want}')
    print('   ' + '; '.join(f'{k} {v}' for k, v in got.items()))
    print('   reproduced')
    print(f'   resolver: resolve_node_name, lines {lo_line}-{hi_line} of {RESOLVER_FILE} in '
          f'{WHEEL.relative_to(ROOT).as_posix()}, sha256 of its source as pinned')
    if not all(x['has_app'] for x in fr):
        sys.exit('stop: a FORWARD pair without an APPEARANCE READ')
    print(f'   checks: the RELEASE RULE pick carries the TARGET\'s short name in {total(amb, "release_pick_same_name")} '
          f'of {len(amb)}; an APPEARANCE READ exists in {total(fr, "has_app")} of {len(fr)} FORWARD pairs')
    print()
    print(f'1. The {len(fr)} AMBIGUOUS OPEN PAIRS where FORWARD (ALL) reaches: which same-named definition does each '
          'rule pick?')
    table(fr)
    print()
    fr_nd = [x for x in fr if not x['dunder']]
    print(f'2. The same, without double-underscore names ({len(fr_nd)} of the {len(fr)})')
    table(fr_nd)
    print()
    amb_nd = [x for x in amb if not x['dunder']]
    print('3. All AMBIGUOUS OPEN PAIRS: is the RELEASE RULE\'s answer for the TARGET\'s short name the TARGET itself?')
    print('   ' + share_line(f'every name ({len(amb)})', amb, 'release'))
    print('   ' + share_line(f'without double-underscore names ({len(amb_nd)})', amb_nd, 'release'))
    print()

    def c(sel, k):
        return fmt_n(total(sel, k))
    print('4. In plain words')
    print(f'   On the {len(fr)} ambiguous missed places whose name stands in code the run was shown, the call edge '
          f'reaches the right definition in {c(fr, "edge")}, a uniform pick among the same-named definitions would '
          f'land on it in {c(fr, "random")} on average, the release\'s own resolver picks it in {c(fr, "release")}, '
          f'and the nearest-directory rule in {c(fr, "nearest")}. '
          f'Without double-underscore names ({len(fr_nd)} pairs) the four are {c(fr_nd, "edge")}, '
          f'{c(fr_nd, "random")}, {c(fr_nd, "release")} and {c(fr_nd, "nearest")}. '
          + ' '.join(
              f'{lab}, the interval of EDGE minus the rule '
              + (f'excludes zero against {names(ex)}' if ex else 'excludes zero against none of the three')
              + (f' and holds zero against {names(hd)}.' if hd else '.')
              for lab, (ex, hd) in (('With every name', excluding_zero(fr)),
                                    ('Without double-underscore names', excluding_zero(fr_nd))))
          + f' Over all {len(amb)} ambiguous open pairs, asking the release for the target\'s short name returns the '
          f'target in {c(amb, "release")} ({c(amb_nd, "release")} of the {len(amb_nd)} without double-underscore '
          f'names). The intervals and paired differences are printed above, on as few as '
          f'{min(len(by_task(fr)), len(by_task(fr_nd)), len(by_task(amb_nd)))} tasks.')
    print()
    print('5. JUDGMENT CALLS')
    for j in JUDGMENT:
        print('   - ' + j)
    print(f'(run time {time.time() - t0:.0f} s)', file=sys.stderr)


if __name__ == '__main__':
    main()
