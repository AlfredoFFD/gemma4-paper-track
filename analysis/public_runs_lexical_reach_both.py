"""A search by name in both directions against the call edge, for the regions public runs miss (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_lexical_reach_both.py

Nothing here was pre-registered and no model is run. analysis/public_runs_lexical_reach.py counts, for every PAIR of a
public run and a MISSED REGION, whether the TARGET is one edge of the CALL GRAPH from code the run was shown (EDGE) and
whether the TARGET's SHORT NAME stands in the SHOWN TEXT (a search from the shown code to the names that stand in it).
An edge also leads the other way, to callers of what was shown, and a text search can go that way too: search the
repository for the name of an entity the run has seen, and the hits are the places that use it. This script counts that
direction and the union of the two.

PAIR, TARGET, SHOWN ENTITY, SHOWN TEXT, OPEN PAIR, SHORT NAME, EDGE, OPENED, the dunder and unique rules and the
bootstrap: as in analysis/public_runs_lexical_reach.py, whose functions (and those of the modules it imports) are used.
A PAIR that is not an OPEN PAIR counts as reached by no measure here. Further rules:
  TARGET TEXT      the snapshot lines (analysis/nodes.file_text) of the TARGET's span.
  FORWARD          the TARGET's SHORT NAME stands as a whole identifier in the SHOWN TEXT (the first script's LEXICAL).
  BACKWARD         the SHORT NAME of at least one SHOWN ENTITY stands as a whole identifier in the TARGET TEXT. A SHOWN
                   ENTITY that is the TARGET or has the TARGET's SHORT NAME is left out.
  EITHER           FORWARD or BACKWARD, variant by variant.
  Variants, each applied to the name searched for (the TARGET's in FORWARD, the SHOWN ENTITY's in BACKWARD):
    ALL            every name.
    NO DUNDER      a name of the form __x__ counts as not found.
    UNIQUE         only a name that no other node of the task's graph (any node id) shares.
    USE, NO DUNDER the NO DUNDER rule, and the name must stand in a USE POSITION of the searched text.
  USE POSITION     after `#` comments and triple-quoted strings are removed from the searched text: the name is
                   followed (after optional blanks) by `(` and not preceded by `def ` or `class `; or it is preceded by
                   `.` (optional blanks between); or it is one of the names of an `import ...` list on its line (every
                   identifier after `import`, up to ` as` in each comma-separated item, parentheses ignored).
                   Decorators (`@name`) and other string literals are not treated specially.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analysis/public_runs_missed_regions.boot). A difference
of two counts is the difference of the per-task sums over the summed denominator, bootstrapped the same way.
"""
import collections
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_lexical_reach as X  # noqa: E402
import public_runs_missed_links as L  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

VARIANTS = ('all', 'nd', 'u', 'use')
VNAME = {'all': 'ALL', 'nd': 'NO DUNDER', 'u': 'UNIQUE', 'use': 'USE, NO DUNDER'}
DIRS = ('fwd', 'bwd', 'eith')
DNAME = {'fwd': 'FORWARD', 'bwd': 'BACKWARD', 'eith': 'EITHER'}

TRIPLE = re.compile(r'("""|\'\'\')[\s\S]*?\1')
COMMENT = re.compile(r'#[^\n]*')
CALL = re.compile(r'(\b(?:def|class)\s+)?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
ATTR = re.compile(r'\.\s*([A-Za-z_][A-Za-z0-9_]*)')
IMPORT = re.compile(r'\bimport\s+([^\n]*)')


def use_words(text):
    """The identifiers that stand in a USE POSITION of a text."""
    text = COMMENT.sub('', TRIPLE.sub('', text))
    out = set()
    for m in CALL.finditer(text):
        if not m.group(1):
            out.add(m.group(2))
    out.update(ATTR.findall(text))
    for m in IMPORT.finditer(text):
        for item in m.group(1).replace('(', ' ').replace(')', ' ').split(','):
            item = item.split(' as ')[0]
            out.update(X.IDENT.findall(item))
    return out


def kept_text(task_id, f, spans):
    text = N.file_text(task_id, f)
    if not text:
        return ''
    lines = text.split('\n')
    keep = set()
    for s, e in spans:
        keep.update(range(max(1, s), min(len(lines), e) + 1))
    return '\n'.join(lines[i - 1] for i in sorted(keep))


def shown_use_words(task_id, reads):
    out = set()
    for f, spans in reads.items():
        out |= use_words(kept_text(task_id, f, spans))
    return out


def target_text(task_id, ent, t):
    f, a, b = ent[t]
    return '\n'.join((N.file_text(task_id, f) or '').split('\n')[a - 1:b])


def found(name, words, uses, counts):
    nd = name in words and not X.is_dunder(name)
    return {'all': int(name in words), 'nd': int(nd), 'u': int(name in words and counts[name] == 1),
            'use': int(nd and name in uses)}


def main():
    t0 = time.time()
    tasks = load_tasks()
    gold = gold_regions()
    rows = []
    name_counts = {}
    hit_names = {'nd': collections.Counter(), 'u': collections.Counter()}
    n_names = []          # per OPEN PAIR: the number of distinct SHOWN ENTITY names searched for
    for r in iter_runs():
        if r['arm'] not in ('base', 'skill') or not gold.get(r['task']):
            continue
        task_id = r['task']
        gr = gold[task_id]
        reads = collections.defaultdict(list)
        for call, _text, parsed in calls_of(load(r['path'])):
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        if not missed:
            continue
        g = graph_for(tasks[task_id])
        ent = L.entities(task_id, g)
        if g['key'] not in name_counts:
            name_counts[g['key']] = collections.Counter(L.short(n) for n in g['ids'])
        counts = name_counts[g['key']]
        shown = set()
        for f, spans in reads.items():
            for s0, e0, nid in M.nodes_of_file(task_id, g, f):
                if overlap(s0, e0, spans):
                    shown.add(nid)
        words = X.shown_words(task_id, reads)
        uses = shown_use_words(task_id, reads)
        shown_names = sorted({L.short(n) for n in shown})
        cg = L.call_graph(task_id, g)[0]
        front = M.reach(cg['nbr'], shown)[0]
        for f, a, b in missed:
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            t = min(cover)[2] if cover else None
            row = {'task': task_id, 'opened': f in reads, 'has_target': t is not None,
                   'open': t is not None and t not in shown, 'edge': 0}
            for d in DIRS:
                for v in VARIANTS:
                    row[f'{d}_{v}'] = 0
            if row['open']:
                row['edge'] = int(t in front)
                tname = L.short(t)
                row.update({f'fwd_{v}': val for v, val in found(tname, words, uses, counts).items()})
                twords = L.words_of(task_id, ent, t)
                tuses = use_words(target_text(task_id, ent, t))
                for nm in shown_names:          # names of SHOWN ENTITIES; t is not shown, so only the name rule applies
                    if nm == tname:
                        continue
                    for v, val in found(nm, twords, tuses, counts).items():
                        row[f'bwd_{v}'] |= val
                        if val and v in ('nd', 'u'):
                            hit_names[v][nm] += 1
                n_names.append(len(shown_names))
                for v in VARIANTS:
                    row[f'eith_{v}'] = int(row[f'fwd_{v}'] or row[f'bwd_{v}'])
            rows.append(row)

    def by_task(sel):
        out = collections.defaultdict(list)
        for x in sel:
            out[x['task']].append(x)
        return out

    def share_line(label, sel, key):
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, key))
        n = sum(x[key] for x in sel)
        return f'{label} {n} of {len(sel)} ({100 * n / len(sel):.1f}% [{100 * lo:.1f}, {100 * hi:.1f}])'

    def diff_line(sel, k2):
        d = M.share(sel, 'edge') - M.share(sel, k2)
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, 'edge') - M.share(xs, k2))
        return f'EDGE minus it {100 * d:+.1f} points [{100 * lo:+.1f}, {100 * hi:+.1f}]'

    def block(sel, title, cross):
        open_ = [x for x in sel if x['open']]
        print(title)
        print(f'   PAIRS {len(sel)} in {len(by_task(sel))} tasks; with a TARGET {sum(x["has_target"] for x in sel)}; '
              f'OPEN PAIRS {len(open_)}')
        for base_label, base in (('of all PAIRS', sel), ('of the OPEN PAIRS', open_)):
            print(f'   {base_label}:')
            print('      ' + share_line('EDGE', base, 'edge'))
            for v in VARIANTS:
                print(f'      {VNAME[v]}:')
                for d in DIRS:
                    print(f'         ' + share_line(DNAME[d], base, f'{d}_{v}') + '; ' + diff_line(base, f'{d}_{v}'))
        if cross:
            print('   cross tables of the OPEN PAIRS:')
            for v in VARIANTS:
                e_y = [x for x in open_ if x['edge']]
                e_n = [x for x in open_ if not x['edge']]
                print(f'      {VNAME[v]}: edge and either {sum(x[f"eith_{v}"] for x in e_y)}; edge only '
                      f'{sum(not x[f"eith_{v}"] for x in e_y)}; either only {sum(x[f"eith_{v}"] for x in e_n)}; '
                      f'neither {sum(not x[f"eith_{v}"] for x in e_n)}')
                fo = sum(x[f'fwd_{v}'] and not x[f'bwd_{v}'] for x in e_y)
                bo = sum(x[f'bwd_{v}'] and not x[f'fwd_{v}'] for x in e_y)
                bb = sum(x[f'fwd_{v}'] and x[f'bwd_{v}'] for x in e_y)
                nn = sum(not x[f'fwd_{v}'] and not x[f'bwd_{v}'] for x in e_y)
                print(f'         of the {len(e_y)} the EDGE reaches: forward only {fo}; backward only {bo}; both {bb}; '
                      f'neither {nn}')
        print()

    print('PUBLIC RUNS: a search by name in both directions against the call edge, for the regions runs miss (EXPLORATORY)')
    print()
    n_edge = sum(x['edge'] for x in rows)
    fw = tuple(sum(x[f'fwd_{v}'] for x in rows) for v in ('all', 'nd', 'u'))
    ok = (len(rows), n_edge, fw) == (1326, 267, (315, 158, 88))
    print(f'Check: PAIRS {len(rows)}, EDGE {n_edge}, FORWARD ALL / NO DUNDER / UNIQUE {fw[0]} / {fw[1]} / {fw[2]} '
          f'({"reproduces" if ok else "DOES NOT reproduce"} 1,326, 267 and 315 / 158 / 88 in '
          'analysis/results/public/lexical_reach.txt)')
    print()
    block(rows, '1. All PAIRS', True)
    block([x for x in rows if not x['opened']], '2. MISSED REGION in a file the run had never opened', True)

    sn = sorted(n_names)
    print('3. How wide the BACKWARD search is')
    print(f'   distinct SHOWN ENTITY names searched for per OPEN PAIR: median {sn[len(sn) // 2]}, quartiles '
          f'{sn[len(sn) // 4]} and {sn[(3 * len(sn)) // 4]}, range {sn[0]} to {sn[-1]}')
    for v in ('nd', 'u'):
        top = sorted(hit_names[v].items(), key=lambda kv: (-kv[1], kv[0]))[:15]
        print(f'   {VNAME[v]}: the shown names found most often in a TARGET TEXT (OPEN PAIRS where the name is found): '
              + ', '.join(f'{k} {n}' for k, n in top))
    print()

    def c(sel, k):
        return sum(x[k] for x in sel)
    no = [x for x in rows if not x['opened']]
    print('In plain words:')
    print(f'   Of the {len(rows)} missed regions, the call edge reaches {n_edge}. A search for the missed function\'s name '
          f'in the shown code reaches {c(rows, "fwd_all")} with every name and {c(rows, "fwd_nd")} without dunder names; '
          f'a search for the shown functions\' names in the missed function\'s own text reaches {c(rows, "bwd_all")} '
          f'and {c(rows, "bwd_nd")}; either direction reaches {c(rows, "eith_all")} and {c(rows, "eith_nd")}. With '
          f'only unique names, either direction reaches {c(rows, "eith_u")}; with names in a use position and no '
          f'dunder names, {c(rows, "eith_use")}. On the {len(no)} regions in files the run never opened, the edge '
          f'reaches {c(no, "edge")} and either direction {c(no, "eith_all")} (every name), {c(no, "eith_nd")} (no '
          f'dunder), {c(no, "eith_u")} (unique), {c(no, "eith_use")} (use, no dunder). Of the {n_edge} regions the '
          f'edge reaches, either direction also reaches {sum(x["edge"] and x["eith_all"] for x in rows)}, '
          f'{sum(x["edge"] and x["eith_nd"] for x in rows)}, {sum(x["edge"] and x["eith_u"] for x in rows)} and '
          f'{sum(x["edge"] and x["eith_use"] for x in rows)} in the four variants, most of them by the backward '
          f'direction alone. The backward search looks for a median of {sn[len(sn) // 2]} names per region at once, '
          f'and no chance baseline is computed for it here.')
    print(f'(run time {time.time() - t0:.0f} s; not part of the comparison of two runs)', file=sys.stderr)


if __name__ == '__main__':
    main()
