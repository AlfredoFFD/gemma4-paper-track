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
import hashlib
import random
import re
import statistics
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
SF_SEEDS = list(range(1, 21))      # the 20 seeds of analysis/public_runs_lexical_reach.py (its default --seeds 20)
SF_KEYS = ('edge',) + tuple(f'{d}_{v}' for d in DIRS for v in VARIANTS)

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
        pool = sorted(n for n in ent if n not in shown)
        pool_by_file = collections.defaultdict(list)
        for n in pool:
            pool_by_file[ent[n][0]].append(n)

        def measures(p):
            """EDGE, FORWARD, BACKWARD and EITHER, every variant, with entity p in the place of the TARGET."""
            pname = L.short(p)
            out = {'edge': int(p in front)}
            out.update({f'fwd_{v}': val for v, val in found(pname, words, uses, counts).items()})
            pw = L.words_of(task_id, ent, p)
            pu = use_words(target_text(task_id, ent, p))
            for v in VARIANTS:
                out[f'bwd_{v}'] = 0
            for nm in shown_names:
                if nm == pname:
                    continue
                for v, val in found(nm, pw, pu, counts).items():
                    out[f'bwd_{v}'] |= val
            for v in VARIANTS:
                out[f'eith_{v}'] = int(out[f'fwd_{v}'] or out[f'bwd_{v}'])
            return out

        for f, a, b in missed:
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            t = min(cover)[2] if cover else None
            row = {'task': task_id, 'opened': f in reads, 'has_target': t is not None,
                   'open': t is not None and t not in shown, 'edge': 0}
            for d in DIRS:
                for v in VARIANTS:
                    row[f'{d}_{v}'] = 0
            if t is not None:       # section 5: how many nodes of the task's graph carry the TARGET's SHORT NAME
                row['k'] = counts[L.short(t)]
                row['tdunder'] = X.is_dunder(L.short(t))
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
                # SAME-FILE STAND-IN: the draws of analysis/public_runs_lexical_reach.py, reproduced seed by seed
                cand_sf = [n for n in pool_by_file[ent[t][0]] if n != t]
                row['has_same_file'] = int(bool(cand_sf))
                row['self_check'] = int(measures(t) == {k: row[k] for k in SF_KEYS})
                for k in SF_KEYS:
                    row[f'sf_{k}_seeds'] = [0] * len(SF_SEEDS)
                if cand_sf:
                    for i, sd in enumerate(SF_SEEDS):
                        h = hashlib.sha256(f'sf:{task_id}:{r["path"]}:{f}:{a}:{b}:{sd}'.encode()).hexdigest()
                        pick = random.Random(int(h, 16)).choice(cand_sf)
                        for k, val in measures(pick).items():
                            row[f'sf_{k}_seeds'][i] = val
                for k in SF_KEYS:
                    row[f'sf_{k}'] = statistics.mean(row[f'sf_{k}_seeds'])
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

    # 4. Against a stand-in from the TARGET's own file
    open_all = [x for x in rows if x['open']]
    sf = [x for x in open_all if x['has_same_file']]

    def tot(k):
        return round(sum(x[k] for x in sf), 4)

    def sf_line(label, k):
        n = len(sf)
        sv = [sum(x[f'sf_{k}_seeds'][i] for x in sf) / n for i in range(len(SF_SEEDS))]
        d = M.share(sf, k) - M.share(sf, f'sf_{k}')
        lo, hi = M.boot(by_task(sf), lambda xs: M.share(xs, k) - M.share(xs, f'sf_{k}'))
        return (f'{label}: true {tot(k):g} of {n} ({100 * tot(k) / n:.1f}%); stand-in {tot(f"sf_{k}"):g} '
                f'({100 * tot(f"sf_{k}") / n:.1f}%, seeds {100 * min(sv):.1f} to {100 * max(sv):.1f}); '
                f'true minus stand-in {100 * d:+.1f} points [{100 * lo:+.1f}, {100 * hi:+.1f}]')

    print()
    print('4. Against a SAME-FILE STAND-IN (the TARGET replaced by another ENTITY of its file that the run was not shown)')
    print('   The draws of analysis/public_runs_lexical_reach.py reproduced, not imported (its draws sit inside its main):')
    print('   the pool is the ENTITIES of the TARGET\'s file that are not SHOWN ENTITIES, the TARGET left out; for seeds')
    print('   1 to 20 the pick is random.Random(int(sha256("sf:<task>:<run path>:<file>:<first line>:<last line>:<seed>"),')
    print('   16)).choice(pool). Each measure is applied with the pick in the place of the TARGET (BACKWARD searches the')
    print('   pick\'s own text, leaving out shown names equal to the pick\'s SHORT NAME); stand-in = mean over the 20 seeds.')
    print(f'   OPEN PAIRS whose file holds another ENTITY not shown: {len(sf)} of {len(open_all)}; measures recomputed on '
          f'the true TARGET agree with sections 1-2 on {sum(x["self_check"] for x in open_all)} of {len(open_all)} OPEN PAIRS')
    got = tuple((tot(f'fwd_{v}'), tot(f'sf_fwd_{v}')) for v in ('all', 'nd', 'u'))
    want = ((299, 252.95), (142, 175.8), (80, 71))
    print(f'   Check: FORWARD ALL / NO DUNDER / UNIQUE true vs stand-in '
          + ' / '.join(f'{a:g} vs {b:g}' for a, b in got)
          + f' ({"reproduces" if got == want else "DOES NOT reproduce"} 299 vs 252.95, 142 vs 175.8, 80 vs 71 in '
          'analysis/results/public/lexical_reach.txt)')
    print('   ' + sf_line('EDGE', 'edge'))
    for v in VARIANTS:
        print(f'   {VNAME[v]}:')
        for d in DIRS:
            print('      ' + sf_line(DNAME[d], f'{d}_{v}'))

    def dd(k):
        return 100 * (M.share(sf, k) - M.share(sf, f'sf_{k}'))
    print()
    print('In plain words (section 4):')
    print(f'   On the {len(sf)} open pairs, the call edge reaches the true missed function in {tot("edge"):g} and a '
          f'function drawn from the same file in {tot("sf_edge"):g} on average ({dd("edge"):+.1f} points). For the '
          f'name searches, true minus stand-in is, for ALL, NO DUNDER, UNIQUE and USE, NO DUNDER in turn: forward '
          + ', '.join(f'{dd(f"fwd_{v}"):+.1f}' for v in VARIANTS) + '; backward '
          + ', '.join(f'{dd(f"bwd_{v}"):+.1f}' for v in VARIANTS) + '; either '
          + ', '.join(f'{dd(f"eith_{v}"):+.1f}' for v in VARIANTS)
          + ' points. The intervals are printed above; a difference whose interval holds zero is not told apart '
          'from the stand-in here.')

    # 5. Missed places behind an ambiguous short name
    def q(vals):
        s = sorted(vals)
        return f'median {s[len(s) // 2]}, quartiles {s[len(s) // 4]} and {s[(3 * len(s)) // 4]}, range {s[0]} to {s[-1]}'

    def cnt_line(label, sel, k):
        n = sum(x[k] for x in sel)
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, k))
        return f'{label} {n} of {len(sel)} ({100 * n / len(sel):.1f}% [{100 * lo:.1f}, {100 * hi:.1f}])'

    def edge_minus(sel, k):
        d = M.share(sel, 'edge') - M.share(sel, k)
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, 'edge') - M.share(xs, k))
        return f'EDGE minus EITHER {100 * d:+.1f} points [{100 * lo:+.1f}, {100 * hi:+.1f}]'

    def sf_line2(label, sel, k):
        n = len(sel)
        sv = [sum(x[f'sf_{k}_seeds'][i] for x in sel) / n for i in range(len(SF_SEEDS))]
        t_, s_ = round(sum(x[k] for x in sel), 4), round(sum(x[f'sf_{k}'] for x in sel), 4)
        d = M.share(sel, k) - M.share(sel, f'sf_{k}')
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, k) - M.share(xs, f'sf_{k}'))
        return (f'{label}: true {t_:g} of {n} ({100 * t_ / n:.1f}%); stand-in {s_:g} ({100 * s_ / n:.1f}%, seeds '
                f'{100 * min(sv):.1f} to {100 * max(sv):.1f}); true minus stand-in {100 * d:+.1f} points '
                f'[{100 * lo:+.1f}, {100 * hi:+.1f}]')

    with_t = [x for x in rows if x['has_target']]
    print()
    print('5. Missed places behind an ambiguous short name')
    print('   AMBIGUOUS: the TARGET\'s SHORT NAME is shared by at least one other node id of the task\'s graph; UNIQUE: it')
    print('   is not. This is the notion of the UNIQUE variant of analysis/public_runs_lexical_reach.py (the count of the')
    print('   SHORT NAME over all node ids of the graph, ENTITY or not, equal to 1). k = the number of node ids that carry')
    print('   the name, the TARGET included.')
    print('   (a) slices')
    for base_label, base in (('PAIRS with a TARGET', with_t), ('OPEN PAIRS', [x for x in with_t if x['open']])):
        for dl, sub in (('every name', base), ('names without two leading and trailing underscores',
                                                [x for x in base if not x['tdunder']])):
            amb = [x for x in sub if x['k'] > 1]
            uni = [x for x in sub if x['k'] == 1]
            print(f'      {base_label}, {dl}: {len(sub)} in {len(by_task(sub))} tasks; AMBIGUOUS {len(amb)} in '
                  f'{len(by_task(amb))} tasks (k: {q([x["k"] for x in amb]) if amb else "none"}); UNIQUE {len(uni)} in '
                  f'{len(by_task(uni))} tasks')
    open_ = [x for x in rows if x['open']]
    slices = (('AMBIGUOUS', [x for x in open_ if x['k'] > 1]), ('UNIQUE', [x for x in open_ if x['k'] == 1]),
              ('AMBIGUOUS, no double-underscore names', [x for x in open_ if x['k'] > 1 and not x['tdunder']]))
    print('   (b) reach on the OPEN PAIRS of each slice')
    for name, sel in slices:
        print(f'      {name} ({len(sel)} OPEN PAIRS in {len(by_task(sel))} tasks):')
        print('         ' + cnt_line('EDGE', sel, 'edge'))
        for v in ('use', 'all'):
            print(f'         {VNAME[v]}: ' + '; '.join(cnt_line(DNAME[d], sel, f'{d}_{v}') for d in DIRS)
                  + '; ' + edge_minus(sel, f'eith_{v}'))
    amb = slices[0][1]
    fr = [x for x in amb if x['fwd_all']]
    exp_id = sum(1 / x['k'] for x in fr)
    print('   (c) AMBIGUOUS OPEN PAIRS: which definition a search by name points to')
    print(f'      FORWARD (ALL) reaches {len(fr)} of {len(amb)}; picking one of the k same-named nodes at random would '
          f'identify the TARGET in {exp_id:.1f} of them on average (mean of 1/k over those pairs '
          f'{exp_id / len(fr) if fr else 0:.3f}; k among them: {q([x["k"] for x in fr]) if fr else "none"})')
    print(f'      EDGE reaches {sum(x["edge"] for x in amb)} of the {len(amb)} (an edge names the node itself); of the '
          f'{len(fr)} FORWARD reaches, the EDGE also reaches {sum(x["edge"] for x in fr)}')
    amb_sf = [x for x in amb if x['has_same_file']]
    print(f'   (d) SAME-FILE STAND-IN of section 4 on the AMBIGUOUS OPEN PAIRS whose file holds another ENTITY not shown '
          f'({len(amb_sf)} of {len(amb)}):')
    print('      ' + sf_line2('EDGE', amb_sf, 'edge'))
    print('      ' + sf_line2('EITHER (USE, NO DUNDER)', amb_sf, 'eith_use'))
    uni_o = slices[1][1]
    amb_nd = slices[2][1]

    def s(sel, k):
        return f'{sum(x[k] for x in sel)} of {len(sel)}'
    print()
    print('In plain words (section 5):')
    print(f'   Of the {len(with_t)} missed places with a TARGET, {sum(x["k"] > 1 for x in with_t)} have a short name that '
          f'another node of the graph shares; of the {len(open_)} open pairs, {len(amb)} '
          f'({len(amb_nd)} without double-underscore names). On the ambiguous open pairs the edge reaches '
          f'{s(amb, "edge")}, the forward search (every name) {s(amb, "fwd_all")} and either direction with names in a '
          f'use position {s(amb, "eith_use")}; on the unique open pairs the edge reaches {s(uni_o, "edge")} and either '
          f'direction (use, no dunder) {s(uni_o, "eith_use")}. Of the {len(fr)} ambiguous pairs the forward search '
          f'reaches, a random pick among the same-named nodes would land on the right one in {exp_id:.1f} on average, '
          f'and the edge reaches {sum(x["edge"] for x in fr)} of those {len(fr)}. Against the same-file stand-in on the '
          f'{len(amb_sf)} ambiguous pairs that have one, the edge reaches {sum(x["edge"] for x in amb_sf)} against '
          f'{sum(x["sf_edge"] for x in amb_sf):.1f}, and either direction (use, no dunder) '
          f'{sum(x["eith_use"] for x in amb_sf)} against {sum(x["sf_eith_use"] for x in amb_sf):.1f}.')
    print(f'(run time {time.time() - t0:.0f} s; not part of the comparison of two runs)', file=sys.stderr)


if __name__ == '__main__':
    main()
