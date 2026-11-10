"""What the agent does right after a read whose line bound was dropped, in the fresh episodes (EXPLORATORY).

Usage: py -I -X utf8 analysis/explore_defect_fresh.py

Reads analysis/results/09/forks/results_09.jsonl (pre-registration 09) and uses the harness as shipped (condition N)
unless stated. A RANGED READ is an executed read_file whose arguments carry a line bound under any spelling. It is
MANGLED if a bound sits under a name that is not a plain identifier and reads start_line or end_line once quotes,
backslashes and spaces are removed (analysis/mangled_sensitivity.mangled, imported). For each ranged read that is not
the last executed call of its episode, the script looks at the next executed call:
  SAME FILE AGAIN   it is a read_file of the same file (the path without a leading /workspace/, workspace/ or ./);
  WELL-FORMED       that read carries a line bound and none is mangled;
  SAME LINES        that read's start line (as the model wrote it, under any spelling) equals the start line the
                    mangled read asked for.
Nothing here was pre-registered; it restates stored rows and runs no model.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analysis/analyze_forks.py).
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from mangled_sensitivity import BOUNDS, clean, mangled  # noqa: E402

ROWS = HERE / 'results' / '09' / 'forks' / 'results_09.jsonl'


def norm(p):
    p = str(p or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def is_read(c):
    return c.get('function_name') == 'read_file' and isinstance(c.get('arguments'), dict)


def ranged(c):
    return is_read(c) and any(clean(k) in BOUNDS for k in c['arguments'])


def start_of(c):
    for k, v in c['arguments'].items():
        if clean(k) == 'start_line':
            try:
                return int(str(v).strip().strip('"\''))
            except ValueError:
                return None
    return None


def pct(k, n):
    return f'{k} of {n} ({100 * k / n:.1f}%)' if n else '0 of 0'


def ci(by):
    t = boot_ci(by)
    return 'n/a' if t[0] is None else f'[{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def part(rows, arm):
    recs = []
    last = collections.Counter()
    for r in rows:
        if r.get('arm') != arm or r.get('error'):
            continue
        calls = [c for step in r.get('steps') or [] for c in step.get('calls') or [] if c.get('executed')]
        for i, c in enumerate(calls):
            if not ranged(c):
                continue
            kind = 'mangled' if mangled(c) else 'well-formed'
            if i + 1 == len(calls):
                last[kind] += 1
                continue
            nxt = calls[i + 1]
            same = is_read(nxt) and norm(nxt['arguments'].get('filepath')) == norm(c['arguments'].get('filepath'))
            recs.append({'task': r['task'], 'kind': kind, 'same': same,
                         'well': same and ranged(nxt) and not mangled(nxt),
                         'again': same and mangled(nxt),
                         'same_lines': same and start_of(nxt) is not None and start_of(nxt) == start_of(c)})
    print(f'condition {arm}')
    by = {}
    for kind in ('mangled', 'well-formed'):
        s = [x for x in recs if x['kind'] == kind]
        by[kind] = collections.defaultdict(list)
        for x in s:
            by[kind][x['task']].append(int(x['same']))
        print(f'   after a {kind} ranged read ({len(s)} with a next call; {last[kind]} were the last call of their episode):')
        print(f'      next call reads the SAME FILE AGAIN: {pct(sum(x["same"] for x in s), len(s))}; by task {ci(by[kind])}')
        print(f'         of which WELL-FORMED {sum(x["well"] for x in s)}, mangled again {sum(x["again"] for x in s)}, '
              f'no line bound {sum(x["same"] and not x["well"] and not x["again"] for x in s)}; SAME LINES '
              f'{sum(x["same_lines"] for x in s)}')
    if by['mangled'] and by['well-formed']:
        d = diff_ci(by['mangled'], by['well-formed'])
        if d[0] is not None:
            print(f'   mangled minus well-formed on SAME FILE AGAIN, by task: {100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    rows = [json.loads(l) for l in open(ROWS, encoding='utf-8') if l.strip()]
    print('EXPLORATORY. Fresh episodes: the call after a ranged read, by whether its line bound was mangled.')
    for arm in ('N', 'NA', 'NAF'):
        part(rows, arm)
    print('In condition NAF the mangled bound is honored, so the read returns the lines asked for.')


if __name__ == '__main__':
    main()
