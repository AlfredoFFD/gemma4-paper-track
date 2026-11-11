"""EXPLORATORY (no pre-registration): does the next call open a hit or noted file AT ALL, on the stored replays of
pre-registrations 15 and 20.

Usage: py -I -X utf8 analysis/explore_file_open_15_20.py > analysis/results/explore_file_open_15_20.txt

The registered outcome of both experiments is "the next call reads a hit (or noted) file past line 1"
(analyze_15.score: reads_hit_file and past_line_1). A reader can object that past line 1 hardly happens without a
printed line number. This script counts the outcome that needs no line number: the next call reads a hit or noted
file at all (analyze_15.score's reads_hit_file: a `read_file` on that file, or a `run_command` whose pipeline starts
from cat, head, tail or sed -n on it and shows a known range of lines), with or without a line range; and splits those
reads by where they start (line 1 or no line range; past line 1).

Everything is reused from the registered scripts: the loaders (analyze_15's main, repeated here because it has no
loader function; analyze_20.load_cells), the usable rows (gates_c.failure), the complete states, the files that count
(each record's `hit_files`: the hit files or noted files, unopened before), the scorer (analyze_15.score), the
bootstrap (analyze_forks.boot_ci and diff_ci, analyze_15.ratio_ci: 2,000 resamples, seed 0, over states; by task
beside it). The registered outcome is recomputed first and checked against the registered reports
(analysis/results/15/analyze_15.txt, analysis/results/20/analyze_20.txt); the script stops if it does not reproduce.
"""
import collections
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_15 as A15  # noqa: E402
import analyze_20 as A20  # noqa: E402
from analyze_15 import bounds_asked, by_task, dpt, pct, rat, ratio_ci, score, share, span  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import failure, load_rows  # noqa: E402

SEEDS = (1, 2, 3)
REG15 = HERE / 'results' / '15' / 'analyze_15.txt'
REG20 = HERE / 'results' / '20' / 'analyze_20.txt'


def outcomes(rec, call):
    """The registered score of a next call, and where a read of a hit file starts."""
    x = score(rec, call)
    where = None
    if x['reads_hit_file']:
        if x['past_line_1']:
            where = 'past line 1'
        elif call['function_name'] == 'read_file':
            where = 'read_file, no start line' if bounds_asked(call)[0] is None else 'read_file, start line 1 or below'
        else:
            where = 'shell view from line 1'
    return x, where


def tally(keys, sc):
    """{y1, open}: {state: [0/1 per replay]}, and a Counter of where the reads start; sc(k) -> [(x, where)]."""
    y1, op, c = {}, {}, collections.Counter()
    for k in keys:
        xs = sc(k)
        y1[k] = [int(x['reads_hit_file'] and x['past_line_1']) for x, _w in xs]
        op[k] = [int(x['reads_hit_file']) for x, _w in xs]
        for x, w in xs:
            c['replays'] += 1
            c['open'] += x['reads_hit_file']
            c['y1'] += x['reads_hit_file'] and x['past_line_1']
            if w:
                c[w] += 1
    return {'y1': y1, 'open': op, 'n': c}


def check(lines, reg_path, label):
    text = reg_path.read_text(encoding='utf-8')
    missing = [s for s in lines if s not in text]
    print(f'  reproduction check against {reg_path.relative_to(HERE.parent).as_posix()}: '
          + (f'{len(lines)} of {len(lines)} registered lines reproduced' if not missing else 'FAILED'))
    if missing:
        for s in missing:
            print('    not found: ' + s.strip())
        print(f'STOP: the registered outcome of {label} is not reproduced')
        sys.exit(1)


def condition_block(a, t, pad):
    c = t['n']
    top = c['open'] - c['y1']
    print(f'  {a:<{pad}} replays {c["replays"]}; registered outcome (reads a hit or noted file past line 1) '
          f'{share(c["y1"], c["replays"])}')
    print(f'  {"":<{pad}} OPENS THE FILE AT ALL {share(c["open"], c["replays"])}; {pct(boot_ci(t["open"]))} by state, '
          f'by task {span(boot_ci(by_task(t["open"]))).replace("+", "")}')
    print(f'  {"":<{pad}}   of those, start at line 1 or give no line range {top} (read_file with no start line '
          f'{c["read_file, no start line"]}, read_file starting at line 1 or below {c["read_file, start line 1 or below"]}, '
          f'shell view from line 1 {c["shell view from line 1"]}); start past line 1 {c["past line 1"]}')


# ---------------------------------------------------------------- pre-registration 15

def run_15():
    recs = [json.loads(l) for l in open(HERE / 'fork_states_s' / 'states.jsonl', encoding='utf-8')]
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs}
    states = {A15.state_key(r): r for r in recs if r['arm'] == 'S'}
    usable = collections.defaultdict(dict)
    for row in load_rows(HERE / 'results' / '15' / 'forks' / 'results.jsonl'):
        if row.get('skip'):
            continue
        rec = by_fork.get((row.get('task'), row.get('run'), row.get('fork')))
        if rec is None or row.get('arm') != A15.RUNNER_ARM[rec['arm']] or row.get('seed') not in SEEDS:
            continue
        if not failure(row):
            usable[A15.state_key(rec)][(rec['arm'], row['seed'])] = row

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    pair, full = complete(('S', 'S0')), complete(A15.ARMS)

    def sc(a):
        return lambda k: [outcomes(states[k], usable[k][(a, s)]['next_call']) for s in SEEDS]

    tp = {a: tally(pair, sc(a)) for a in ('S', 'S0')}
    tf = {a: tally(full, sc(a)) for a in A15.ARMS}

    print('PRE-REGISTRATION 15 (arms S: the search result as it was; S0: its line numbers stripped; S0N: stripped, '
          'with a note of the hit lines)')
    print(f'  states complete for Q1 (S and S0): {len(pair)}; for Q3 (S, S0 and S0N): {len(full)} of {len(states)}')

    # the registered lines, formatted as analyze_15 formats them
    reg = []
    for a in A15.ARMS:
        c = tf[a]['n']
        reg.append(f'    arm {a:<4} Y1, reads a hit file past line 1: {pct(boot_ci(tf[a]["y1"]))} | {c["y1"]}/{c["replays"]}; '
                   f'Y2, reads a hit file: {pct(boot_ci(tf[a]["open"]))} | {c["open"]}/{c["replays"]};')
    d1 = diff_ci(tp['S']['y1'], tp['S0']['y1'])
    d1t = diff_ci(by_task(tp['S']['y1']), by_task(tp['S0']['y1']))
    reg.append(f'  Q1, Y1 under S minus Y1 under S0: {dpt(d1)}; by task {span(d1t)}')
    d3 = diff_ci(tf['S0N']['y1'], tf['S0']['y1'])
    d3t = diff_ci(by_task(tf['S0N']['y1']), by_task(tf['S0']['y1']))
    reg.append(f'  Q3, Y1 under S0N minus Y1 under S0: {dpt(d3)}; by task {span(d3t)}')
    r = ratio_ci(tf['S0N']['y1'], tf['S0']['y1'], tf['S']['y1'], tf['S0']['y1'])
    reg.append(f'  Q3, R = (Y1 under S0N minus Y1 under S0) / (Y1 under S minus Y1 under S0): {rat(r)};')
    check(reg, REG15, 'pre-registration 15')

    print(f'  per condition, on the {len(full)} states complete in all three arms (95% bootstrap by state; by task beside it):')
    for a in A15.ARMS:
        condition_block(a, tf[a], 4)

    print('  differences on OPENS THE FILE AT ALL, in points (95% bootstrap by state; by task beside it):')
    e1 = diff_ci(tp['S']['open'], tp['S0']['open'])
    e1t = diff_ci(by_task(tp['S']['open']), by_task(tp['S0']['open']))
    print(f'    as Q1, S minus S0 (with against without line numbers), {len(pair)} states: {dpt(e1)}; by task {span(e1t)}')
    e3 = diff_ci(tf['S0N']['open'], tf['S0']['open'])
    e3t = diff_ci(by_task(tf['S0N']['open']), by_task(tf['S0']['open']))
    print(f'    as Q3, S0N minus S0 (the note against nothing), {len(full)} states: {dpt(e3)}; by task {span(e3t)}')
    e4 = diff_ci(tf['S0N']['open'], tf['S']['open'])
    e4t = diff_ci(by_task(tf['S0N']['open']), by_task(tf['S']['open']))
    print(f'    S0N minus S (the note against the line numbers in the result), {len(full)} states: {dpt(e4)}; '
          f'by task {span(e4t)}')
    rr = ratio_ci(tf['S0N']['open'], tf['S0']['open'], tf['S']['open'], tf['S0']['open'])
    rrt = ratio_ci(by_task(tf['S0N']['open']), by_task(tf['S0']['open']), by_task(tf['S']['open']),
                   by_task(tf['S0']['open']))
    print(f'    as Q3\'s ratio, (S0N minus S0) / (S minus S0): {rat(rr)}; left out {rr[3]} of 2000; by task '
          + ('[n/a]' if rrt[1] is None else f'[{rrt[1]:.2f}, {rrt[2]:.2f}]') + f', left out {rrt[3]}')
    return {'t': tf, 'e1': e1, 'e3': e3, 'e4': e4, 'r': rr, 'd1': d1}


# ---------------------------------------------------------------- experiment 20

def run_20():
    recs = [json.loads(l) for l in open(HERE / 'fork_states_t' / 'states.jsonl', encoding='utf-8')]
    rec_of = {(A20.state_key(r), r['arm']): r for r in recs}
    rec_of.update({(A20.state_key(r), 'ASKED15'): r for r in recs if r['arm'] == 'ASKED'})
    states = sorted({A20.state_key(r) for r in recs})
    has_x = {k for k in states if (k, 'TOLDX') in rec_of}
    args = types.SimpleNamespace(run_dir=str(HERE / 'results' / '20' / 'forks'),
                                 asked=str(HERE / 'results' / '15' / 'forks'), standin=False)
    cells, _skipped, _stray = A20.load_cells(args, recs)
    usable = collections.defaultdict(dict)
    for k, arm, seed, row in cells:
        if arm == 'TOLDX' and k not in has_x:
            continue
        if not failure(row):
            usable[k][(arm, seed)] = row

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    def sc(a):
        return lambda k: [outcomes(rec_of[(k, a)], usable[k][(a, s)]['next_call']) for s in SEEDS]

    print('EXPERIMENT 20 (arms NONE: nothing added; TOLD: the hits in a note; TOLDX: the hits of another search in a '
          'note; ASKED: one call later, after its own search; ASKED15: the stored rows of 15\'s arm S, description only)')
    own = {a: tally(complete((a,)), sc(a)) for a in A20.ALL_ARMS}

    reg = []
    for a in A20.ALL_ARMS:
        keys = complete((a,))
        reg.append(f'  arm {a:<5} {len(keys)} states; USES THE LINE {pct(boot_ci(own[a]["y1"]))} | '
                   f'{own[a]["n"]["y1"]}/{3 * len(keys)}; SEARCHES')
    k1, k2, k3 = complete(('TOLD', 'NONE')), complete(('TOLD', 'ASKED')), complete(('TOLD', 'TOLDX'))
    p1 = {a: tally(k1, sc(a)) for a in ('TOLD', 'NONE')}
    p2 = {a: tally(k2, sc(a)) for a in ('TOLD', 'ASKED')}
    p3 = {a: tally(k3, sc(a)) for a in ('TOLD', 'TOLDX')}
    d1 = diff_ci(p1['TOLD']['y1'], p1['NONE']['y1'])
    d1t = diff_ci(by_task(p1['TOLD']['y1']), by_task(p1['NONE']['y1']))
    reg.append(f'  T1, USES THE LINE under TOLD minus under NONE: {dpt(d1)}; by task {span(d1t)}')
    r2 = ratio_ci(p2['TOLD']['y1'], {}, p2['ASKED']['y1'], {})
    reg.append(f'  T2, the ratio TOLD / ASKED on USES THE LINE: {rat(r2)};')
    d3 = diff_ci(p3['TOLD']['y1'], p3['TOLDX']['y1'])
    d3t = diff_ci(by_task(p3['TOLD']['y1']), by_task(p3['TOLDX']['y1']))
    reg.append(f'  T3, USES THE LINE under TOLD minus under TOLDX (TOLDX scored on the files of its own note): {dpt(d3)}; '
               f'by task {span(d3t)}')
    check(reg, REG20, 'experiment 20')

    print('  per condition, each arm on its states complete in it (95% bootstrap by state; by task beside it):')
    for a in A20.ALL_ARMS:
        print(f'  {a:<7} {len(complete((a,)))} states')
        condition_block('', own[a], 7)

    print('  differences on OPENS THE FILE AT ALL, in points unless a ratio (95% bootstrap by state; by task beside it):')
    e1 = diff_ci(p1['TOLD']['open'], p1['NONE']['open'])
    e1t = diff_ci(by_task(p1['TOLD']['open']), by_task(p1['NONE']['open']))
    print(f'    as T1, TOLD minus NONE, {len(k1)} states: {dpt(e1)}; by task {span(e1t)}')
    e2 = ratio_ci(p2['TOLD']['open'], {}, p2['ASKED']['open'], {})
    e2t = ratio_ci(by_task(p2['TOLD']['open']), {}, by_task(p2['ASKED']['open']), {})
    print(f'    as T2, the ratio TOLD / ASKED, {len(k2)} states: {rat(e2)}; left out {e2[3]} of 2000; by task '
          + ('[n/a]' if e2t[1] is None else f'[{e2t[1]:.2f}, {e2t[2]:.2f}]') + f', left out {e2t[3]}')
    e2d = diff_ci(p2['TOLD']['open'], p2['ASKED']['open'])
    e2dt = diff_ci(by_task(p2['TOLD']['open']), by_task(p2['ASKED']['open']))
    print(f'    TOLD minus ASKED, {len(k2)} states: {dpt(e2d)}; by task {span(e2dt)}')
    e3 = diff_ci(p3['TOLD']['open'], p3['TOLDX']['open'])
    e3t = diff_ci(by_task(p3['TOLD']['open']), by_task(p3['TOLDX']['open']))
    print(f'    as T3, TOLD minus TOLDX (own hits against another search\'s, TOLDX scored on the files of its own note), '
          f'{len(k3)} states: {dpt(e3)}; by task {span(e3t)}')
    kr = complete(('TOLD', 'NONE', 'ASKED'))
    pr = {a: tally(kr, sc(a)) for a in ('TOLD', 'NONE', 'ASKED')}
    rr = ratio_ci(pr['TOLD']['open'], pr['NONE']['open'], pr['ASKED']['open'], pr['NONE']['open'])
    print(f'    (TOLD minus NONE) / (ASKED minus NONE), the form of 15\'s ratio, {len(kr)} states: {rat(rr)}; '
          f'left out {rr[3]} of 2000')
    return {'own': own, 'e1': e1, 'e2': e2, 'e2d': e2d, 'e3': e3, 'rr': rr, 'd1': d1, 'r2': r2, 'd3': d3}


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
    print('EXPLORATORY: no pre-registration covers this count. Outcome: the next call opens a hit or noted file at all '
          '(analyze_15.score, reads_hit_file), with or without a line range; the registered outcome (past line 1) '
          'reproduced beside it')
    print()
    a = run_15()
    print()
    b = run_20()
    print()

    def n(t, k):
        return t['n'][k], t['n']['replays']

    def pc(k, m):
        return f'{k} of {m} ({100 * k / m:.1f}%)'

    s, s0, s0n = (a['t'][x] for x in ('S', 'S0', 'S0N'))
    no, to, tx, ak = (b['own'][x] for x in ('NONE', 'TOLD', 'TOLDX', 'ASKED'))
    print('What the counts say. '
          f'In 15 the file is opened at all in {pc(*n(s, "open"))} of the replays with the line numbers, '
          f'{pc(*n(s0, "open"))} without them and {pc(*n(s0n, "open"))} with the note (this is the registered Y2 of 15, '
          f'printed there already). With against without line numbers is {dpt(a["e1"])} points on opening, against '
          f'{dpt(a["d1"])} on the registered outcome: a part of the effect survives an outcome that needs no line '
          f'number, and the rest is where the read starts (without numbers {s0["n"]["open"] - s0["n"]["y1"]} of '
          f'{s0["n"]["open"]} reads start at the top). The note does not raise opening over the stripped result '
          f'({dpt(a["e3"])}); it moves where the read starts, and it stays below the result with its numbers '
          f'({dpt(a["e4"])}). '
          f'In 20 the noted file is opened at all in {pc(*n(no, "open"))} under NONE, {pc(*n(to, "open"))} under TOLD, '
          f'{pc(*n(tx, "open"))} under TOLDX and {pc(*n(ak, "open"))} under ASKED. TOLD minus NONE is '
          f'{dpt(b["e1"])} points on opening, against {dpt(b["d1"])} on the registered outcome, so the effect of telling '
          f'does not rest on the definition: without the note the agent mostly searches and rarely opens the file. '
          f'TOLD as a share of ASKED is {rat(b["e2"])} on opening against {rat(b["r2"])} on the registered outcome '
          f'(TOLD minus ASKED {dpt(b["e2d"])}), and own hits against another search\'s (TOLD minus TOLDX) is '
          f'{dpt(b["e3"])} on opening against {dpt(b["d3"])} on the registered outcome: on opening at all the agent '
          f'follows its own hits more than another search\'s, which the registered outcome did not detect. '
          f'Exploratory: the outcome and these comparisons were chosen after the registered results were seen.')


if __name__ == '__main__':
    main()
