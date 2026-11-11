"""EXPLORATORY (no rule): in the whole runs of pre-registration 14, how runs that were shown every changed region
of the reference patch fare against the others.

Reads the per-run table that the registered analysis writes (analysis/results/14/runs_14.csv; columns
`every_region`, `resolved`, `t_shown`, `has_gold_file`, `condition`). EVERY REGION SHOWN is the registered
script's own measure: every changed region of every file the reference patch modifies is overlapped by the lines
some `read_file` call returned (shell views and the agent's own edits do not count). A run with no file to show
(the reference patch only creates files) is left out, as in the registered report.

Prints, per condition and for both together: runs shown every changed region and how many of them resolved; the
other runs and how many of them resolved; among the runs that failed, how many had been shown a changed line and how
many had not been shown every changed region.
Usage: py -I -X utf8 analysis/explore_every_region.py [--no-write]
Writes analysis/results/explore_every_region.txt.
"""
import csv
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'results' / '14' / 'runs_14.csv'
OUT = HERE / 'results' / 'explore_every_region.txt'
NEVER = ('', 'inf', 'None')


def main():
    rows = [r for r in csv.DictReader(open(SRC, encoding='utf-8')) if r['entered'] == '1' and r['has_gold_file'] == '1']
    buf = io.StringIO()

    def p(*a):
        print(*a)
        print(*a, file=buf)

    p('EXPLORATORY. Whole runs of pre-registration 14: runs shown every changed region against the others.')
    p(f'runs that enter the analysis and have a file to show: {len(rows)}')
    tot = {'every': 0, 'every_res': 0, 'rest': 0, 'rest_res': 0}
    for cond in ('N', 'NAF'):
        r = [x for x in rows if x['condition'] == cond]
        ev = [x for x in r if x['every_region'] == '1']
        rest = [x for x in r if x['every_region'] != '1']
        failed = [x for x in r if x['resolved'] != '1']
        f_shown = [x for x in failed if x['t_shown'] not in NEVER]
        f_not_every = [x for x in failed if x['every_region'] != '1']
        ev_res = sum(x['resolved'] == '1' for x in ev)
        rest_res = sum(x['resolved'] == '1' for x in rest)
        p(f'condition {cond}: {len(r)} runs | shown every changed region {len(ev)}, of which resolved {ev_res} | '
          f'the other {len(rest)}, of which resolved {rest_res} | failed {len(failed)}, of which shown a changed line '
          f'{len(f_shown)} and not shown every changed region {len(f_not_every)}')
        tot['every'] += len(ev)
        tot['every_res'] += ev_res
        tot['rest'] += len(rest)
        tot['rest_res'] += rest_res
    p(f'both conditions: shown every changed region {tot["every"]}, of which resolved {tot["every_res"]} | '
      f'the other {tot["rest"]}, of which resolved {tot["rest_res"]}')
    if '--no-write' not in sys.argv:
        OUT.write_text(buf.getvalue(), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
