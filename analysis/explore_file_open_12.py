#!/usr/bin/env python3
"""EXPLORATORY, written after all results were seen: does the line range add to OPENING the neighbor's file at all,
beyond the file alone? The looser outcome of pre-registration 12 for its main contrast.

Usage: py -I -X utf8 analysis/explore_file_open_12.py   (no arguments; prints the report)
Stored output: analysis/results/explore_file_open_12.txt is exactly this script's stdout (LF line ends).

Everything scored by the code analyze_12.py imports: gates_c.failure (interface failures), gates_c.any_true ("reads
a neighbor's code"), mangled_sensitivity.opens_listed_file ("opens the neighbor's file": a read_file of the file of
an unopened true neighbor, at any line), explore_first_reads.bounds / read_stats (where the read starts), and the
bootstrap of analyze_forks (boot_ci, diff_ci; 2,000 resamples, seed 0).
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from explore_first_reads import bounds, norm, read_stats  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

SEEDS = (1, 2, 3)
SOURCES = {  # arm: (results dir, arm label in that run, where it comes from)
    'A': ('w', 'A', 'run of pre-registration 07 (no list, rebuilt tool results as in every earlier replay)'),
    'H': ('c', 'H', 'run of pre-registration 04 (bare names)'),
    'EPATH': ('12', 'EPATH', 'run of pre-registration 12 (name and file, no lines)'),
    'EL': ('c', 'EL', 'run of pre-registration 04 (name, file and line range)'),
    'E': ('c', 'E', 'run of pre-registration 04 (name, file, line range and first definition line)'),
}
ARMS = ('A', 'H', 'EPATH', 'EL', 'E')
RULE_ARMS = ('H', 'EL', 'EPATH')   # analyze_12's completeness rule
OUT = []


def add(s=''):
    OUT.append(s)


def pct(t):
    return 'n/a' if t[0] is None else '%.2f%% [%.2f, %.2f]' % (100 * t[0], 100 * t[1], 100 * t[2])


def dpt(t):
    return 'n/a' if t[0] is None else '%+.2f [%+.2f, %+.2f]' % (100 * t[0], 100 * t[1], 100 * t[2])


def by_task(table):
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return dict(out)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    except (AttributeError, ValueError):
        pass
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    usable = {}
    nrows, nfail = collections.Counter(), collections.Counter()
    for arm, (d, lab, _src) in SOURCES.items():
        u = collections.defaultdict(dict)
        for r in load_rows(HERE / 'results' / d / 'forks' / 'results.jsonl'):
            if r['arm'] != lab or r['seed'] not in SEEDS:
                continue
            nrows[arm] += 1
            if failure(r):
                nfail[arm] += 1
            else:
                u[skey(r)][r['seed']] = r
        usable[arm] = u

    def rows_of(k, arm):
        u = usable[arm].get(k, {})
        return [u[s] for s in SEEDS] if all(s in u for s in SEEDS) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in RULE_ARMS))
    complete_a = [k for k in complete if rows_of(k, 'A') is not None]

    reads = {a: {} for a in ARMS}
    opens = {a: {} for a in ARMS}
    starts = {a: collections.Counter() for a in ARMS}
    for k in complete:
        st = states[k]
        unshown = set(st.get('unshown_true_neighbors', st['true_neighbors']))
        for a in ARMS:
            rs = rows_of(k, a)
            if rs is None:
                continue
            reads[a][k] = [int(bool(any_true(st, r['next_call']))) for r in rs]
            opens[a][k] = [int(bool(opens_listed_file(st, r['next_call']))) for r in rs]
            for r in rs:
                call = r['next_call']
                if not opens_listed_file(st, call):
                    continue
                c = starts[a]
                c['open'] += 1
                ranged, covers, on_first = read_stats(st, call)
                c['past1'] += int(ranged)
                c['covers'] += int(covers)
                c['on_first'] += int(on_first)
                start, _end = bounds(call['arguments'])
                path = norm(call['arguments'].get('filepath'))
                s0 = start if start is not None else 1
                inside = any(sp['path'] == path and sp.get('start') is not None and sp.get('end') is not None
                             and sp['start'] <= s0 <= sp['end']
                             for sp in (st['neighbor_spans'][n] for n in unshown if st['neighbor_spans'].get(n)))
                c['inside'] += int(inside)
                c['inside_past1'] += int(inside and s0 > 1)

    add("EXPLORATORY: PRE-REGISTRATION 12, DOES THE LINE RANGE ADD TO OPENING THE NEIGHBOR'S FILE AT ALL?")
    add("EXPLORATORY. Written after all results were seen; nothing here was registered beyond the gate's numbers.")
    add('')
    add('ARMS AND WHERE THEIR ROWS COME FROM (states analysis/fork_states_d, seeds 1 to 3, interface failures out by')
    add('gates_c.failure; every run on the same rented A100-80GB platform with harness wheels v28)')
    for a in ARMS:
        d, lab, src = SOURCES[a]
        add('  %-5s results/%s/forks arm %s: %s; %d rows, %d interface failures' % (a, d, lab, src, nrows[a], nfail[a]))
    add('  Complete steps (analyze_12 rule: H, EL and EPATH usable for seeds 1 to 3): %d of %d.' % (
        len(complete), len(states)))
    add('  Arm E is scored on the complete steps where it is usable (%d); arm A likewise (%d), and contrasts with A'
        % (len(reads['E']), len(complete_a)))
    add('  are on those %d steps.' % len(complete_a))
    add('')

    add('0. GATE (analyze_12 scorer and bootstrap, by step)')
    p1 = diff_ci(reads['EL'], reads['EPATH'])
    p2 = diff_ci(opens['EPATH'], opens['H'])
    add('  P1, EL - EPATH on reads a neighbor\'s code: %s (stored +4.56 [+2.74, +6.63])' % dpt(p1))
    add('  P2, EPATH - H on opens the neighbor\'s file: %s (stored +1.33 [-0.08, +2.82])' % dpt(p2))
    ok = (tuple(round(100 * x, 2) for x in p1) == (4.56, 2.74, 6.63)
          and tuple(round(100 * x, 2) for x in p2) == (1.33, -0.08, 2.82))
    add('  ' + ('reproduced' if ok else 'NOT reproduced: see the differences above'))
    add('')

    add('1. RATES (percent of replays, 95% bootstrap by step | hits/replays)')
    for a in ARMS:
        n = sum(len(v) for v in reads[a].values())
        add('  %-5s on %d steps: opens the neighbor\'s file %s | %d/%d; reads a neighbor\'s code %s | %d/%d' % (
            a, len(reads[a]), pct(boot_ci(opens[a])), sum(map(sum, opens[a].values())), n,
            pct(boot_ci(reads[a])), sum(map(sum, reads[a].values())), n))
    add('')

    add('2. CONTRASTS ON "OPENS THE NEIGHBOR\'S FILE" (points; 95% bootstrap by step | by task; 2,000 resamples, seed 0)')

    def contrast(name, x, y, keys):
        dx = {k: opens[x][k] for k in keys}
        dy = {k: opens[y][k] for k in keys}
        add('  %s, %d steps: %s | by task %s' % (name, len(keys), dpt(diff_ci(dx, dy)),
                                                dpt(diff_ci(by_task(dx), by_task(dy)))))

    contrast('EL - EPATH (file and lines minus file only)', 'EL', 'EPATH', complete)
    contrast('EL - H (file and lines minus names)', 'EL', 'H', complete)
    contrast('EPATH - A (file only minus no list)', 'EPATH', 'A', complete_a)
    contrast('EPATH - H (file only minus names; the gate\'s P2)', 'EPATH', 'H', complete)
    contrast('H - A (names minus no list)', 'H', 'A', complete_a)
    add('')

    add('3. WHERE THE READS THAT OPEN A NEIGHBOR\'S FILE START (per arm; start = the start line the model wrote,')
    add('   line 1 if none; inside = the start line within the line range of an unopened true neighbor in that file)')
    for a in ARMS:
        c = starts[a]
        add('  %-5s opens %d; start past line 1 %d; start inside a neighbor\'s range %d (of them past line 1 %d);'
            ' read window covers a range %d; starts on a range\'s first line %d' % (
                a, c['open'], c['past1'], c['inside'], c['inside_past1'], c['covers'], c['on_first']))
    add('')

    add('JUDGMENT CALLS')
    for i, t in enumerate([
        'No-list arm: pre-registration 12 has none. Arm A of the run of pre-registration 07 is used: same states file,'
        ' seeds, platform and wheels as the runs of 04 and 12, tool results rendered as in the earlier replays. It is'
        ' a third run; the earlier between-run differences were about half a point.',
        'Completeness: analyze_12\'s rule (H, EL, EPATH usable for every seed); A and E on the subset where they are'
        ' usable too. Section 1 rates of H, EPATH and EL are on all complete steps.',
        'Inside a range: start <= line <= end of the span of any unopened true neighbor in the file read'
        ' (fork_states_d neighbor_spans); a read with no start line counts as line 1. "Covers" and "starts on a'
        ' range\'s first line" are read_stats of explore_first_reads (a window of 150 lines from a start past 1).',
        'By task: diff_ci of analyze_forks with tasks as clusters (every replay of the task\'s steps pooled).',
    ], 1):
        words, line, lines = t.split(), '%2d.' % i, []
        for w in words:
            if len(line) + 1 + len(w) > 112:
                lines.append(line)
                line = '   '
            line += ' ' + w
        lines.append(line)
        OUT.extend(lines)
    sys.stdout.write('\n'.join(OUT) + '\n')


if __name__ == '__main__':
    main()
