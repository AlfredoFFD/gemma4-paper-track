"""Do call edges lead to what runs miss, beyond a text search and beyond chance? (EXPLORATORY)

Usage: py -I -X utf8 analysis/public_runs_lexical_reach.py [--seeds 20]

Nothing here was pre-registered and no model is run. analysis/public_runs_locality_null.py counts the MISSED REGIONS
of the public runs that are one edge of the CALL GRAPH from code the run was shown (267 of 1,326). This script adds a
lexical baseline: how many of the same missed regions a text search by name, run over what the run had read, would
reach, and how often the name of a random other entity would be found the same way.

Sources and the rules CHANGED REGION, SHOWN LINES, MISSED REGION, ENTITY, SHOWN ENTITY, TARGET, CALL GRAPH: as in
analysis/public_runs_missed_regions.py and analysis/public_runs_missed_links.py, whose functions are imported. The
runs, the 1,326 pairs of a run and a MISSED REGION, and the bootstrap are theirs. Further rules:
  PAIR             a run and one of its MISSED REGIONS (1,326). A PAIR with no TARGET is NOT ADDRESSABLE.
  OPEN PAIR        a PAIR whose TARGET exists and is not a SHOWN ENTITY. A PAIR whose TARGET is a SHOWN ENTITY
                   (the run saw other lines of it) counts as reached by NO measure here, as the edge count of
                   public_runs_locality_null.py counts it; how many of those a search would find is printed apart.
  SHORT NAME       the last dotted component of a node id.
  SHOWN TEXT       the snapshot text (analysis/nodes.file_text) of the SHOWN LINES of the run, file by file: the union
                   of the line ranges its read_file calls with status ok returned. A MISSED REGION overlaps no SHOWN
                   LINES by definition, and the TARGET of an OPEN PAIR overlaps none either, so neither the region's
                   own lines nor the TARGET's definition line are ever part of it.
  EDGE             an OPEN PAIR whose TARGET is one edge of the CALL GRAPH from a SHOWN ENTITY (the 267).
  LEXICAL          an OPEN PAIR whose TARGET's SHORT NAME stands as a whole identifier
                   ([A-Za-z_][A-Za-z0-9_]*) in the SHOWN TEXT.
  LEXICAL, NO DUNDER   the same, a SHORT NAME of the form __x__ counting as not found.
  LEXICAL, UNIQUE  the same, counting only a SHORT NAME that no other node of the task's graph (any node id, ENTITY
                   or not) shares, so that a search for it returns one definition.
  CHANCE           for each OPEN PAIR and each of 20 seeds, the TARGET replaced by an ENTITY of the same graph drawn
                   uniformly from the ENTITIES that are not SHOWN ENTITIES of the run, the TARGET left out; the three
                   LEXICAL rules applied to its SHORT NAME; the mean over seeds. The seed of a draw is taken from the
                   task, the run, the region and the seed number.
  SAME-FILE CHANCE the same with the draw restricted to the ENTITIES of the TARGET's own file. An OPEN PAIR whose file
                   holds no other such ENTITY has no value; the comparison is made on the OPEN PAIRS that have one.
  OPENED           the MISSED REGION lies in a file the run read with some read_file call (any lines).
Shares are printed of all 1,326 PAIRS, of the PAIRS with a TARGET, and of the OPEN PAIRS.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analysis/public_runs_missed_regions.boot).
"""
import argparse
import collections
import hashlib
import random
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
import public_runs_missed_links as L  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import graph_for, load_tasks  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import calls_of, is_read, norm  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
VARIANTS = ('lex', 'lex_nd', 'lex_u')
VNAME = {'lex': 'LEXICAL', 'lex_nd': 'LEXICAL, NO DUNDER', 'lex_u': 'LEXICAL, UNIQUE'}


def is_dunder(name):
    return len(name) > 4 and name.startswith('__') and name.endswith('__')


def shown_words(task_id, reads):
    words = set()
    for f, spans in reads.items():
        text = N.file_text(task_id, f)
        if not text:
            continue
        lines = text.split('\n')
        keep = set()
        for s, e in spans:
            keep.update(range(max(1, s), min(len(lines), e) + 1))
        words.update(IDENT.findall('\n'.join(lines[i - 1] for i in sorted(keep))))
    return words


def lexical(name, words, counts):
    found = name in words
    return {'lex': int(found), 'lex_nd': int(found and not is_dunder(name)), 'lex_u': int(found and counts[name] == 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    tasks = load_tasks()
    gold = gold_regions()
    rows = []
    name_counts = {}
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
        words = shown_words(task_id, reads)
        cg = L.call_graph(task_id, g)[0]
        front = M.reach(cg['nbr'], shown)[0]
        pool = sorted(n for n in ent if n not in shown)
        pool_by_file = collections.defaultdict(list)
        for n in pool:
            pool_by_file[ent[n][0]].append(n)
        for f, a, b in missed:
            cover = [(e0 - s0, -s0, nid) for s0, e0, nid in M.nodes_of_file(task_id, g, f) if not (e0 < a or s0 > b)]
            t = min(cover)[2] if cover else None
            row = {'task': task_id, 'opened': f in reads, 'has_target': t is not None,
                   'target_shown': t is not None and t in shown, 'open': t is not None and t not in shown,
                   'edge': 0, 'shown_lex': 0, 'has_same_file': 0}
            for v in VARIANTS:
                row[v] = 0
                for c in ('ch', 'sf'):
                    row[f'{c}_{v}'] = 0.0
                    row[f'{c}_{v}_seeds'] = [0] * len(seeds)
            if t is not None and t in shown:
                row['shown_lex'] = int(L.short(t) in words)
            if row['open']:
                row['edge'] = int(t in front)
                row.update(lexical(L.short(t), words, counts))
                cand = [n for n in pool if n != t]
                cand_sf = [n for n in pool_by_file[ent[t][0]] if n != t]
                row['has_same_file'] = int(bool(cand_sf))
                for c, cs in (('ch', cand), ('sf', cand_sf)):
                    if not cs:
                        continue
                    for i, sd in enumerate(seeds):
                        h = hashlib.sha256(f'{c}:{task_id}:{r["path"]}:{f}:{a}:{b}:{sd}'.encode()).hexdigest()
                        pick = random.Random(int(h, 16)).choice(cs)
                        for v, val in lexical(L.short(pick), words, counts).items():
                            row[f'{c}_{v}_seeds'][i] = val
                    for v in VARIANTS:
                        row[f'{c}_{v}'] = statistics.mean(row[f'{c}_{v}_seeds'])
            rows.append(row)

    def by_task(sel):
        out = collections.defaultdict(list)
        for x in sel:
            out[x['task']].append(x)
        return out

    def ci(sel, fn):
        lo, hi = M.boot(by_task(sel), fn)
        return f'[{100 * lo:.1f}, {100 * hi:.1f}]'

    def share_line(label, sel, key):
        val = M.share(sel, key)
        return f'{label} {sum(x[key] for x in sel):g} of {len(sel)} ({100 * val:.1f}% {ci(sel, lambda xs: M.share(xs, key))})'

    def diff_line(label, sel, k1, k2):
        d = M.share(sel, k1) - M.share(sel, k2)
        lo, hi = M.boot(by_task(sel), lambda xs: M.share(xs, k1) - M.share(xs, k2))
        return f'{label} {100 * d:+.1f} points [{100 * lo:+.1f}, {100 * hi:+.1f}]'

    def seed_range(sel, key):
        sv = [sum(x[key + '_seeds'][i] for x in sel) / len(sel) for i in range(len(seeds))]
        return f'seeds {100 * min(sv):.1f} to {100 * max(sv):.1f}'

    def block(sel, title):
        with_t = [x for x in sel if x['has_target']]
        open_ = [x for x in sel if x['open']]
        sf = [x for x in open_ if x['has_same_file']]
        print(title)
        print(f'   PAIRS {len(sel)} in {len(by_task(sel))} tasks; with a TARGET {len(with_t)}, without (NOT ADDRESSABLE) '
              f'{len(sel) - len(with_t)}; TARGET a SHOWN ENTITY {sum(x["target_shown"] for x in sel)} (of those, the SHORT NAME '
              f'stands in the SHOWN TEXT {sum(x["shown_lex"] for x in sel)}; counted as reached by no measure); OPEN PAIRS {len(open_)}')
        for base_label, base in (('of all PAIRS', sel), ('of the PAIRS with a TARGET', with_t), ('of the OPEN PAIRS', open_)):
            if not base:
                continue
            print(f'   {base_label}:')
            print('      ' + share_line('EDGE', base, 'edge'))
            for v in VARIANTS:
                print('      ' + share_line(VNAME[v], base, v) + '; ' + share_line('CHANCE', base, f'ch_{v}') + f' ({seed_range(base, f"ch_{v}")})')
        if open_:
            print('   cross table of the OPEN PAIRS (EDGE by LEXICAL; with NO DUNDER; with UNIQUE):')
            for v in VARIANTS:
                both = sum(x['edge'] and x[v] for x in open_)
                eo = sum(x['edge'] and not x[v] for x in open_)
                lo_ = sum(x[v] and not x['edge'] for x in open_)
                ne = sum(not x['edge'] and not x[v] for x in open_)
                print(f'      {VNAME[v]}: edge and lexical {both}; edge only {eo}; lexical only {lo_}; neither {ne}')
            print('   differences on all PAIRS (bootstrap over tasks):')
            for v in VARIANTS:
                print('      ' + '; '.join((diff_line(f'EDGE minus {VNAME[v]}', sel, 'edge', v),
                                            diff_line(f'{VNAME[v]} minus its CHANCE', sel, v, f'ch_{v}'))))
            print(f'   SAME-FILE CHANCE, on the OPEN PAIRS whose file holds another ENTITY not shown ({len(sf)} of {len(open_)}):')
            if sf:
                print('      ' + share_line('EDGE', sf, 'edge'))
                for v in VARIANTS:
                    print('      ' + share_line(VNAME[v], sf, v) + '; ' + share_line('SAME-FILE CHANCE', sf, f'sf_{v}')
                          + f' ({seed_range(sf, f"sf_{v}")}); ' + diff_line('lexical minus same-file chance', sf, v, f'sf_{v}'))
        print()

    print('PUBLIC RUNS: call edges against a search by name and against chance, for the regions runs miss (EXPLORATORY)')
    print(f'chance draws: {len(seeds)} seeds per PAIR')
    print()
    n_edge = sum(x['edge'] for x in rows)
    print(f'Check: EDGE over all {len(rows)} PAIRS = {n_edge} '
          f'({"reproduces" if (len(rows), n_edge) == (1326, 267) else "DOES NOT reproduce"} the 267 of 1,326 '
          'in analysis/results/public/locality_null.txt)')
    print(f'PAIRS without a TARGET: {sum(not x["has_target"] for x in rows)} '
          f'({"agrees" if sum(not x["has_target"] for x in rows) == 407 else "DOES NOT agree"} with the 407 NOT ADDRESSABLE)')
    print()
    block(rows, '1-5. All PAIRS')
    block([x for x in rows if x['opened']], '6a. MISSED REGION in a file the run had OPENED')
    block([x for x in rows if not x['opened']], '6b. MISSED REGION in a file the run had never opened')


if __name__ == '__main__':
    main()
