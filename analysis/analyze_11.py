"""Pre-registration 11: the reading rule on the fresh episodes of pre-registration 09.

Usage: py -I -X utf8 analysis/analyze_11.py <run_dir> [--rows results_09.jsonl] [--arms N,NA,NAF]

Reads <run_dir>/results_09.jsonl (one line per episode: task, arm, seed, steps, each step a model response with its
calls: function_name, arguments, executed, result) and prints the counts and the two rules of
prereg/11-reading-rule-fresh-episodes.md. The definitions are those of analysis/public_runs_address.py, whose
functions are imported and not copied: is_read, asked, norm, classify, window, viewed_files, command_of, strings.

An episode is presented to those functions as the list of its executed calls, each with the text of its result (every
string in the result, as public_runs_address.result_of collects them) and the result itself. One class is added for
arms NA and NAF: GRAPH ADDRESS, when the call just before is a graph tool whose answer lists the read's file with a
line range; it is checked before the other classes. Rows of this run keep a read_file result without the file's text.

--rows and --arms exist so that the script can be tested on rows of the same format from another run.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import public_runs_address as P  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402

ARMS = ('N', 'NA', 'NAF')
ADDRESSED = ('NA', 'NAF')          # arms whose graph answers carry a file and a line range
CLASSES = ('ADDRESS', 'PATH ONLY', 'GRAPH NAME', 'GRAPH ADDRESS', 'OTHER')
MIN_R1, MIN_R2 = 30, 20            # first reads needed in each class of R1, and for R2
R1_ADDRESS, R1_PATH, R1_DIFF, R2_MAX = 0.65, 0.05, 0.50, 0.10


def calls_of(row):
    """The episode's executed calls in order, as (call, result text, result): the shape public_runs_address uses."""
    out = []
    for step in row.get('steps') or []:
        for c in step.get('calls') or []:
            if not c.get('executed'):
                continue
            res = c.get('result')
            texts = []
            P.strings(res, texts)
            out.append(({'function_name': c.get('function_name'), 'arguments': c.get('arguments')}, '\n'.join(texts),
                        res if isinstance(res, dict) else None))
    return out


def listed_ranges(f, prev):
    """Line ranges that the graph answer just before gives for file f: [(first, last), ...], empty if none."""
    call, _text, parsed = prev
    if call.get('function_name') not in P.GRAPH_TOOLS or not isinstance(parsed, dict):
        return []
    out = []
    for key in ('neighbors', 'nodes', 'results'):
        entries = parsed.get(key)
        for e in entries if isinstance(entries, list) else []:
            if isinstance(e, dict) and e.get('lines') and P.norm(e.get('file')) == f:
                m = re.match(r'^\s*(\d+)\s*(?:-\s*(\d+))?\s*$', str(e['lines']))
                if m:
                    out.append((int(m.group(1)), int(m.group(2) or m.group(1))))
    return out


def reads_of(row):
    """One record per executed read_file call of an episode."""
    calls = calls_of(row)
    seen = set()
    recs = []
    for i, (call, _text, _parsed) in enumerate(calls):
        if P.is_read(call):
            f = P.norm(call['arguments'].get('filepath'))
            start, end = P.asked(call)
            ranged = start is not None and start > 1
            prev = calls[i - 1] if i else None
            cls, way, lines = P.classify(f, prev)
            ranges = listed_ranges(f, prev) if (prev is not None and row['arm'] in ADDRESSED) else []
            if ranges:
                cls, way, lines = 'GRAPH ADDRESS', None, set()
            lo, hi = P.window(start, end) if ranged else (None, None)
            recs.append({'task': row['task'], 'arm': row['arm'], 'first': f not in seen, 'cls': cls, 'way': way,
                         'ranged': ranged, 'at_first_call': i == 0,
                         'covers_named': bool(ranged and any(lo <= x <= hi for x in lines)),
                         'covers_range': bool(ranged and any(not (hi < a or lo > b) for a, b in ranges))})
            seen.add(f)
        elif call.get('function_name') == 'run_command':
            seen.update(P.viewed_files(P.command_of(call)))
    return recs


def pct(k, n):
    return f'{k} of {n} ({100 * k / n:.1f}%)' if n else '0 of 0'


def by_task(recs):
    t = collections.defaultdict(list)
    for r in recs:
        t[r['task']].append(int(r['ranged']))
    return t


def ci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def rule_r1(first, label):
    a = [r for r in first if r['cls'] == 'ADDRESS']
    p = [r for r in first if r['cls'] == 'PATH ONLY']
    ka, kp = sum(r['ranged'] for r in a), sum(r['ranged'] for r in p)
    print(f'   {label}')
    print(f'      after an ADDRESS:   {pct(ka, len(a))}; by task {ci(boot_ci(by_task(a)))}; {len(by_task(a))} tasks')
    print(f'      after a PATH ONLY:  {pct(kp, len(p))}; by task {ci(boot_ci(by_task(p)))}; {len(by_task(p))} tasks')
    if len(a) < MIN_R1 or len(p) < MIN_R1:
        print(f'      R1 verdict: too few reads to test (fewer than {MIN_R1} first reads in a class)')
        return None
    d = diff_ci(by_task(a), by_task(p))
    print(f'      ADDRESS minus PATH ONLY, by task: {100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')
    checks = (ka / len(a) >= R1_ADDRESS, kp / len(p) <= R1_PATH, d[1] > R1_DIFF)
    print(f'      (a) at least {100 * R1_ADDRESS:.0f}% after an ADDRESS: {"yes" if checks[0] else "no"}; '
          f'(b) at most {100 * R1_PATH:.0f}% after a PATH ONLY: {"yes" if checks[1] else "no"}; '
          f'(c) lower bound of the difference above {100 * R1_DIFF:.0f} points: {"yes" if checks[2] else "no"}')
    ok = all(checks)
    print('      R1 verdict: ' + ('the reading rule holds in our fresh episodes' if ok
                                  else 'the reading rule does not hold as registered'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--rows', default='results_09.jsonl')
    ap.add_argument('--arms', default=','.join(ARMS))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    arms = tuple(args.arms.split(','))
    rows = [json.loads(l) for l in open(Path(args.run_dir) / args.rows, encoding='utf-8') if l.strip()]
    rows = [r for r in rows if r.get('arm') in arms]
    good = [r for r in rows if not r.get('error')]
    recs = [x for r in good for x in reads_of(r)]
    first = [r for r in recs if r['first']]

    print('PRE-REGISTRATION 11: the reading rule on the fresh episodes')
    print()
    print('0. Episodes and reads')
    for arm in arms:
        n_all = sum(r['arm'] == arm for r in rows)
        n_good = sum(r['arm'] == arm for r in good)
        answers = lined = 0
        for r in good:
            if r['arm'] != arm:
                continue
            for call, _t, parsed in calls_of(r):
                if call.get('function_name') in P.GRAPH_TOOLS:
                    answers += 1
                    lined += any(isinstance(e, dict) and e.get('lines') for key in ('neighbors', 'nodes', 'results')
                                 for e in (parsed.get(key) if isinstance(parsed, dict) and isinstance(parsed.get(key), list)
                                           else []))
        sel = [x for x in recs if x['arm'] == arm]
        print(f'   arm {arm}: {n_all} episodes, {n_all - n_good} with an error (left out); executed reads {len(sel)}, '
              f'first reads {sum(x["first"] for x in sel)}; executed graph-tool calls {answers}, answers that give a line '
              f'range {lined}')

    print()
    print('1. First reads by class: reads, of which asking past line 1')
    for scope, sel in [('all arms', first)] + [(f'arm {a}', [r for r in first if r['arm'] == a]) for a in arms]:
        for cls in CLASSES:
            s = [r for r in sel if r['cls'] == cls]
            if s:
                print(f'   {scope:<9} {cls:<14} {pct(sum(r["ranged"] for r in s), len(s))}')

    print()
    print('2. Rule R1, shell output (ADDRESS against PATH ONLY)')
    v_all = rule_r1(first, f'all arms ({", ".join(arms)})')
    v_n = rule_r1([r for r in first if r['arm'] == 'N'], 'arm N alone (the harness as shipped)') if 'N' in arms else None
    if 'N' in arms and v_all is not None and v_n is not None and v_all != v_n:
        print('   The two disagree: the claim is the weaker one.')

    print()
    print('3. Rule R2, the graph tools as shipped (arm N, first reads after a GRAPH NAME)')
    g = [r for r in first if r['arm'] == 'N' and r['cls'] == 'GRAPH NAME']
    kg = sum(r['ranged'] for r in g)
    print(f'   ask past line 1: {pct(kg, len(g))}; by task {ci(boot_ci(by_task(g)))}')
    if len(g) < MIN_R2:
        print(f'   R2 verdict: too few reads to test (fewer than {MIN_R2})')
    else:
        print('   R2 verdict: ' + ('a graph answer is read from the top' if kg / len(g) <= R2_MAX
                                   else f'more than {100 * R2_MAX:.0f}% ask past line 1: not as registered'))

    print()
    print('4. No rule: reported')
    for arm in [a for a in arms if a in ADDRESSED]:
        s = [r for r in first if r['arm'] == arm and r['cls'] == 'GRAPH ADDRESS']
        k = sum(r['ranged'] for r in s)
        print(f'   arm {arm}, first reads after a GRAPH ADDRESS: ask past line 1 {pct(k, len(s))}; of those, cover the listed '
              f'range {pct(sum(r["covers_range"] for r in s), k)}')
    a = [r for r in first if r['cls'] == 'ADDRESS']
    for way, name in (('i', '(i) path:<number>: across files'), ('ii', '(ii) traceback'),
                      ('iii', '(iii) numbered lines of the named file')):
        s = [r for r in a if r['way'] == way]
        print(f'   first reads after an ADDRESS, way {name}: {pct(sum(r["ranged"] for r in s), len(s))}')
    ar = [r for r in a if r['ranged']]
    print(f'   ranged first reads after an ADDRESS that cover a named line: {pct(sum(r["covers_named"] for r in ar), len(ar))}')
    fc = [r for r in first if r['at_first_call']]
    print(f'   first reads at the first call of an episode (classed OTHER): {pct(sum(r["ranged"] for r in fc), len(fc))}')
    later = [r for r in recs if not r['first']]
    print(f'   reads that are not the first read of the file: {pct(sum(r["ranged"] for r in later), len(later))}')


if __name__ == '__main__':
    main()
