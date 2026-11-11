"""EXPLORATORY (no rule, no model): the shape of the reference fixes of the tasks of pre-registration 14.

For each of the tasks whose stored N run of pre-registration 14 entered the analysis
(analysis/results/14/runs_14.csv), the reference patch of data/tasks.jsonl is split into its hunks (one per `@@`
header). Printed, by the number of hunks of the fix (1; 2 or 3; 4 to 9; 10 or more):

  tasks; of them resolved and shown every changed region by the stored N run (columns of runs_14.csv);
  tasks whose hunks lie in more than one file;
  REPEATS: hunks that share at least half of their own changed lines with another hunk of the same fix (a changed
           line is an added or a removed line, stripped of blanks at both ends, at least 8 characters long; a hunk
           with no such line is never a repeat);
  hunks by kind of file (the package's Python files; docs_src/; documentation; tests; other).

Usage: py -I -X utf8 analysis/explore_fix_shape.py [--no-write]
Writes analysis/results/explore_fix_shape.txt (exactly what it prints).
"""
import collections
import csv
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / 'results' / 'explore_fix_shape.txt'
BANDS = ('1', '2 or 3', '4 to 9', '10 or more')


def hunks(patch):
    out, cur_file, cur = [], None, None
    for line in patch.splitlines():
        if line.startswith('+++ '):
            path = line[4:].strip()
            cur_file, cur = (path[2:] if path.startswith('b/') else path), None
        elif line.startswith('--- '):
            cur = None
        elif line.startswith('@@'):
            cur = {'file': cur_file or '', 'lines': set()}
            out.append(cur)
        elif cur is not None and line[:1] in '+-':
            text = line[1:].strip()
            if len(text) >= 8:
                cur['lines'].add(line[0] + text)
    return out


def kind(f):
    if f.startswith('docs_src/'):
        return 'docs_src'
    if f.startswith('docs/') or f.endswith(('.md', '.rst')):
        return 'documentation'
    if f.startswith('tests/') or '/tests/' in f:
        return 'tests'
    return 'package' if f.endswith('.py') else 'other'


def band(n):
    return BANDS[0] if n == 1 else BANDS[1] if n <= 3 else BANDS[2] if n <= 9 else BANDS[3]


def main():
    buf = io.StringIO()

    def p(*a):
        print(*a)
        print(*a, file=buf)

    runs = {r['task']: r for r in csv.DictReader(open(HERE / 'results' / '14' / 'runs_14.csv', encoding='utf-8'))
            if r['condition'] == 'N' and r['entered'] == '1'}
    agg = collections.defaultdict(collections.Counter)
    n_tasks = 0
    for line in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8'):
        t = json.loads(line)
        r = runs.get(t['instance_id'])
        if not r:
            continue
        hs = hunks(t['patch'])
        if not hs:
            continue
        n_tasks += 1
        a = agg[band(len(hs))]
        a['tasks'] += 1
        a['hunks'] += len(hs)
        a['resolved'] += r['resolved'] == '1'
        a['every'] += r['every_region'] == '1'
        a['several files'] += len({h['file'] for h in hs}) > 1
        for i, h in enumerate(hs):
            a['hunks in ' + kind(h['file'])] += 1
            if h['lines'] and any(len(h['lines'] & o['lines']) >= len(h['lines']) / 2
                                  for j, o in enumerate(hs) if j != i and o['lines']):
                a['repeats'] += 1
    p('EXPLORATORY. The reference fixes of the tasks of pre-registration 14, by their number of hunks.')
    p(f'tasks: {n_tasks}')
    for b in BANDS:
        a = agg[b]
        if not a['tasks']:
            continue
        p(f"hunks {b}: tasks {a['tasks']}; resolved by the stored N run {a['resolved']}; shown every changed region "
          f"{a['every']}; fixes in more than one file {a['several files']}; hunks {a['hunks']}, of which REPEATS "
          f"{a['repeats']} ({100 * a['repeats'] / a['hunks']:.0f}%); hunks by kind of file: package "
          f"{a['hunks in package']}, docs_src {a['hunks in docs_src']}, documentation {a['hunks in documentation']}, "
          f"tests {a['hunks in tests']}, other {a['hunks in other']}")
    if '--no-write' not in sys.argv:
        OUT.write_text(buf.getvalue(), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
