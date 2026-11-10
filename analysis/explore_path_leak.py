"""A second malformed file read in the one-step replays: a path that swallowed the line bounds (EXPLORATORY).

Usage: py -I -X utf8 analysis/explore_path_leak.py

Other teams' runs show `read_file` calls whose `filepath` was not closed and took the bounds with it, for example
`rich/syntax.py` followed by a backtick and `,start_line:151` (analysis/results/public/defect_split.txt). Such a call
names no existing file. This script counts them among the next calls of every one-step run in the repository: a
`read_file` whose `filepath` holds `start_line`, `end_line`, a backtick or a quote character. It also says how the
frozen interface-failure rule (gates_c.failure) classes them. They are not the mangled bound name of Appendix D,
which keeps the path intact. A second part counts the same among the executed reads of the fresh episodes of
pre-registration 09, where such a read fails with an error. Counts only; no registered number changes.
"""
import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from explore_first_reads import RUNS  # noqa: E402  the one-step runs, in the paper's order
from gates_c import failure, load_rows  # noqa: E402

LEAK = re.compile('start_line|end_line|[`"\']')


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('EXPLORATORY. read_file next calls whose path holds a bound name or a quote character (one-step replays).')
    print()
    print(f'{"model":16s} {"run":22s} {"read_file calls":>15s} {"path leak":>10s} {"usable by the frozen rule":>26s}')
    tot = collections.Counter()
    for model, label, run, _sdir, _arms in RUNS:
        c = collections.Counter()
        for r in load_rows(HERE / 'results' / run / 'forks' / 'results.jsonl'):
            call = r.get('next_call') or {}
            if call.get('function_name') != 'read_file' or not isinstance(call.get('arguments'), dict):
                continue
            c['reads'] += 1
            if LEAK.search(str(call['arguments'].get('filepath'))):
                c['leak'] += 1
                c['usable'] += failure(r) is None
        tot.update(c)
        print(f'{model:16s} {label:22s} {c["reads"]:15d} {c["leak"]:10d} {c["usable"]:26d}')
    share = 100 * tot['leak'] / tot['reads'] if tot['reads'] else 0.0
    print(f'\nAll runs: {tot["leak"]} of {tot["reads"]} read_file next calls ({share:.2f}%); '
          f'{tot["usable"]} of them count as usable calls under the frozen rule (a call that touches no listed entry).')

    fresh = HERE / 'results' / '09' / 'forks' / 'results_09.jsonl'
    if fresh.exists():
        print('\nFresh episodes (pre-registration 09), executed read_file calls of episodes without an error:')
        by = collections.defaultdict(collections.Counter)
        for r in load_rows(fresh):
            if r.get('error'):
                continue
            for step in r.get('steps') or []:
                for call in step.get('calls') or []:
                    if call.get('function_name') != 'read_file' or not call.get('executed') \
                            or not isinstance(call.get('arguments'), dict):
                        continue
                    c = by[r['arm']]
                    c['reads'] += 1
                    if LEAK.search(str(call['arguments'].get('filepath'))):
                        c['leak'] += 1
                        c['not ok'] += (call.get('result') or {}).get('status') != 'ok'
        for arm in sorted(by):
            c = by[arm]
            print(f'  arm {arm:<4} {c["reads"]:5d} reads; path leak {c["leak"]:3d} ({100 * c["leak"] / c["reads"]:.1f}%), '
                  f'of which the read failed {c["not ok"]}')
        t = sum(c['leak'] for c in by.values())
        n = sum(c['reads'] for c in by.values())
        print(f'  all arms: {t} of {n} ({100 * t / n:.1f}%)')


if __name__ == '__main__':
    main()
