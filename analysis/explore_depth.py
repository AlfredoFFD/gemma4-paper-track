"""Is a line number used more when the line is out of sight from the top of the file? (EXPLORATORY)

Usage: py -I -X utf8 analysis/explore_depth.py

A read without a range returns lines 1 to 150 (the harness's cap). This script splits first reads by whether the
line that the result just before gave is within those 150 lines (IN SIGHT from the top) or past them (OUT OF SIGHT),
and counts how many ask past line 1. Nothing here was pre-registered; it restates stored rows and runs no model.

Part 1, fresh episodes of pre-registration 09 (analysis/results/09/forks/results_09.jsonl), with the classes of
analysis/analyze_11.py and analysis/public_runs_address.py (imported, not copied):
  after an ADDRESS (the result just before names the file with a line number): the depth is the smallest line
  number that result names for the file;
  after a GRAPH ADDRESS (a graph answer that lists the file with a line range; conditions with addresses only): the
  depth is the smallest first line among the ranges that answer lists for the file.
Part 2, one-step replays (the runs of analysis/explore_first_reads.py), first reads of a listed neighbor's unopened
file: the depth is the smallest first line among the listed neighbors in that file. Conditions are grouped as in
that script: lists with line numbers and lists without.
Part 3, the same split for other teams' public runs is printed by analysis/public_runs_address.py (its section 9)
and analysis/public_runs_outside.py; it is not repeated here.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analysis/analyze_forks.py).
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_11 as A  # noqa: E402
import explore_first_reads as efr  # noqa: E402
import public_runs_address as P  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

RES = HERE / 'results'
WINDOW = 150
BINS = ((1, 50), (51, 150), (151, 300), (301, 600), (601, None))


def bin_of(x):
    for lo, hi in BINS:
        if x >= lo and (hi is None or x <= hi):
            return f'{lo} to {hi}' if hi else f'{lo} and up'


def sight(depth):
    return 'IN SIGHT' if depth <= WINDOW else 'OUT OF SIGHT'


def pct(k, n):
    return f'{k} of {n} ({100 * k / n:.1f}%)' if n else '0 of 0'


def ci(by):
    t = boot_ci(by)
    return 'n/a' if t[0] is None else f'[{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def table(recs, label):
    """recs: (task, depth, ranged). One line per sight class, one per depth bin, and the difference by task."""
    print(f'   {label}: first reads {len(recs)}')
    by = {s: collections.defaultdict(list) for s in ('IN SIGHT', 'OUT OF SIGHT')}
    for task, depth, ranged in recs:
        by[sight(depth)][task].append(int(ranged))
    for s in ('IN SIGHT', 'OUT OF SIGHT'):
        vals = [v for t in by[s].values() for v in t]
        print(f'      {s:<13} ask past line 1: {pct(sum(vals), len(vals))}; by task {ci(by[s])}; tasks {len(by[s])}')
    if by['IN SIGHT'] and by['OUT OF SIGHT']:
        d = diff_ci(by['OUT OF SIGHT'], by['IN SIGHT'])
        if d[0] is not None:
            print(f'      OUT OF SIGHT minus IN SIGHT, by task: {100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')
    for lo, hi in BINS:
        b = bin_of(lo)
        sel = [r for r in recs if bin_of(r[1]) == b]
        if sel:
            print(f'         depth {b:<11} {pct(sum(r[2] for r in sel), len(sel))}')


def fresh_part():
    rows = [json.loads(l) for l in open(RES / '09' / 'forks' / 'results_09.jsonl', encoding='utf-8') if l.strip()]
    good = [r for r in rows if not r.get('error')]
    recs = collections.defaultdict(list)
    undated = collections.Counter()
    for row in good:
        calls = A.calls_of(row)
        seen = set()
        for i, (call, _text, _parsed) in enumerate(calls):
            if P.is_read(call):
                f = P.norm(call['arguments'].get('filepath'))
                start, _end = P.asked(call)
                ranged = start is not None and start > 1
                prev = calls[i - 1] if i else None
                cls, _way, lines = P.classify(f, prev)
                ranges = A.listed_ranges(f, prev) if (prev is not None and row['arm'] in A.ADDRESSED) else []
                if ranges:
                    cls = 'GRAPH ADDRESS'
                first = f not in seen
                seen.add(f)
                if not first or cls not in ('ADDRESS', 'GRAPH ADDRESS'):
                    continue
                depth = min(a for a, _b in ranges) if cls == 'GRAPH ADDRESS' else (min(lines) if lines else None)
                if depth is None:
                    undated[cls] += 1
                    continue
                recs[(cls, 'all conditions')].append((row['task'], depth, ranged))
                recs[(cls, row['arm'])].append((row['task'], depth, ranged))
            elif call.get('function_name') == 'run_command':
                seen.update(P.viewed_files(P.command_of(call)))
    print('1. Fresh episodes (pre-registration 09), first reads by the depth of the line the result just before gave')
    for cls in ('ADDRESS', 'GRAPH ADDRESS'):
        table(recs[(cls, 'all conditions')], f'after {"an" if cls == "ADDRESS" else "a"} {cls}, all conditions')
        if undated[cls]:
            print(f'      (left out: {undated[cls]} first reads whose result names no line number for the file)')
    table(recs[('ADDRESS', 'N')], 'after an ADDRESS, the harness as shipped (condition N)')
    for arm in A.ADDRESSED:
        table(recs[('GRAPH ADDRESS', arm)], f'after a GRAPH ADDRESS, condition {arm}')


def replay_part():
    cache = {}
    recs = collections.defaultdict(list)
    for model, _label, run, sdir, arms in efr.RUNS:
        if sdir not in cache:
            cache[sdir] = load_states(HERE / sdir / 'states.jsonl')
        states = cache[sdir]
        for r in load_rows(RES / run / 'forks' / 'results.jsonl'):
            if r['arm'] not in arms or r['seed'] not in efr.SEEDS or failure(r):
                continue
            st = states[skey(r)]
            call = r['next_call']
            if not opens_listed_file(st, call):
                continue
            path = efr.norm(call['arguments'].get('filepath'))
            unshown = set(st.get('unshown_true_neighbors', st['true_neighbors']))
            starts = [st['neighbor_spans'][n]['start'] for n in unshown
                      if st['neighbor_spans'].get(n) and st['neighbor_spans'][n]['path'] == path
                      and st['neighbor_spans'][n].get('start')]
            if not starts:
                continue
            ranged, _covers, _on_first = efr.read_stats(st, call)
            kind = 'with line numbers' if r['arm'] in efr.WITH else 'without line numbers'
            recs[(model, kind)].append((r['task'], min(starts), ranged))
    print()
    print('2. One-step replays, first reads of a listed neighbor\'s unopened file, by the depth of the shallowest listed '
          'neighbor in that file')
    for key in sorted(recs):
        table(recs[key], f'{key[0]}, lists {key[1]}')


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('EXPLORATORY. Is a line number used more when the line is out of sight from the top of the file?')
    print(f'IN SIGHT: the line is within the first {WINDOW} lines, which a read without a range returns. OUT OF SIGHT: past them.')
    print()
    fresh_part()
    replay_part()


if __name__ == '__main__':
    main()
