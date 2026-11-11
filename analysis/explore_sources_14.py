"""Our whole runs: do the places a run never saw lie in a file it had opened? (EXPLORATORY)

Usage: py -I -X utf8 analysis/explore_sources_14.py

Nothing here was pre-registered and no model is run. analysis/public_runs_sources.py finds that, in public runs, a
third of the changed regions a run never saw lie further down a file the run had opened. This script repeats that
one split on the stored whole runs of pre-registration 14 (analysis/results/14, conditions N and NAF), and on the
tasks listed in analysis/oracle_18/tasks_18.txt (the tasks whose stored N run was not shown every changed region).

Rules, as in analysis/public_runs_sources.py: CHANGED REGION; SHOWN LINES (read_file results of status ok);
MISSED REGION; OPENED FILE (a file with such a read); a region is NEAR A NAMED LINE if some tool result of the run
named a line of its file within 10 lines of it (the ADDRESS rule of analysis/public_runs_address.py). Runs are
loaded with analysis/analyze_14.load_root; a run without a stored trace is left out and counted.
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_14 as A  # noqa: E402
from public_runs_address import calls_of, classify, is_read, norm, pct  # noqa: E402
from public_runs_time_to_fix import gold_regions, overlap  # noqa: E402


def main():
    loaded = A.load_root(HERE / 'results' / '14')
    runs = loaded[0] if isinstance(loaded, tuple) else loaded
    gold = gold_regions()
    listed = [x.strip() for x in open(HERE / 'oracle_18' / 'tasks_18.txt', encoding='utf-8') if x.strip()]
    rows, per_run, no_trace = [], [], collections.Counter()
    for (task, cond, seed), rec in sorted(runs.items()):
        trace = rec[0]
        gr = gold.get(task)
        if not gr:
            continue
        if trace is None:
            no_trace[cond] += 1
            continue
        calls = calls_of(trace)
        reads = collections.defaultdict(list)
        for call, _text, parsed in calls:
            if is_read(call) and isinstance(parsed, dict) and parsed.get('status') == 'ok':
                f = norm(parsed.get('filepath') or call['arguments'].get('filepath'))
                s, e = parsed.get('start_line'), parsed.get('end_line')
                if isinstance(s, int) and isinstance(e, int):
                    reads[f].append((s, e))
        missed = [(f, a, b) for f, regs in gr.items() for a, b in regs if not overlap(a, b, reads.get(f, []))]
        named = collections.defaultdict(set)
        for prev in calls:
            for f in {m[0] for m in missed}:
                named[f] |= classify(f, prev)[2]
        rr = []
        for f, a, b in missed:
            rr.append({'task': task, 'cond': cond, 'opened': f in reads, 'deep': f in reads and a > 150,
                       'near': f in reads and any(a - 10 <= x <= b + 10 for x in named.get(f, ()))})
        rows += rr
        per_run.append({'task': task, 'cond': cond, 'missed': len(rr), 'regions': sum(len(v) for v in gr.values()),
                        'all_opened': bool(rr) and all(x['opened'] for x in rr)})

    def block(label, sel_runs, sel_rows):
        inc = [x for x in sel_runs if x['missed']]
        of = [x for x in sel_rows if x['opened']]
        print(f'   {label}: runs {len(sel_runs)}, with a MISSED REGION {len(inc)}; MISSED REGIONS {len(sel_rows)}')
        if not sel_rows:
            return
        print(f'      in an OPENED FILE {pct(len(of), len(sel_rows))}; of those, starting below line 150 {pct(sum(x["deep"] for x in of), len(of))}, '
              f'NEAR A NAMED LINE {pct(sum(x["near"] for x in of), len(of))}')
        print(f'      runs whose MISSED REGIONS all lie in OPENED FILES: {pct(sum(x["all_opened"] for x in inc), len(inc))}')

    print('OUR WHOLE RUNS (pre-registration 14): the places a run never saw, and the files it had opened (EXPLORATORY)')
    print(f'runs without a stored trace, left out: {dict(no_trace) or 0}')
    print()
    print('1. Every task with a CHANGED REGION')
    for cond in A.CONDITIONS:
        block(cond, [x for x in per_run if x['cond'] == cond], [x for x in rows if x['cond'] == cond])
    print()
    print(f'2. The {len(listed)} tasks of analysis/oracle_18/tasks_18.txt')
    for cond in A.CONDITIONS:
        block(cond, [x for x in per_run if x['cond'] == cond and x['task'] in listed],
              [x for x in rows if x['cond'] == cond and x['task'] in listed])


if __name__ == '__main__':
    main()
