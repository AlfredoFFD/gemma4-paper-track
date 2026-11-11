"""Store the rows of experiment 20 in the repository, as the rows of pre-registration 15 are stored
(analysis/results/15/forks/: results.jsonl, summary.json, versions.json, platform_actual.json, pip_freeze.txt and the
two empty fidelity files; the server log is not kept).

Usage: py -I -X utf8 analysis/store_20.py [--from <local dir>] [--volume-dir /out_20] [--dest analysis/results/20/forks]
Without --from, the files are fetched from the Modal volume `gemma-forks-c` (`modal volume get`; from Git Bash prefix
the command with MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8). With --from, they are copied from a local directory.
Then it checks the rows: every line parses, no line is a cell entered as finished (`skip`: forks_20_modal._finish
removes them), every row belongs to a record of analysis/fork_states_t/states.jsonl under the runner's arm of that
record, and no (record, arm, seed) cell is there twice. It prints the rows by arm and the md5 of every stored file.
Running it twice gives identical files.
"""
import argparse
import collections
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ('results.jsonl', 'summary.json', 'versions.json', 'platform_actual.json', 'pip_freeze.txt', 'fidelity.jsonl',
         'fidelity_w.jsonl')
REQUIRED = ('results.jsonl', 'versions.json', 'platform_actual.json')
RUNNER_ARM = {'NONE': 'A', 'TOLD': 'TOLD', 'TOLDX': 'TOLDX', 'ASKED': 'A'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='src')
    ap.add_argument('--volume', default='gemma-forks-c')
    ap.add_argument('--volume-dir', default='/out_20')
    ap.add_argument('--dest', default=str(HERE / 'results' / '20' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_t' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8')
    for name in FILES:
        if args.src:
            src = Path(args.src) / name
            if src.exists():
                shutil.copyfile(src, dest / name)
        else:
            p = subprocess.run(['modal', 'volume', 'get', '--force', args.volume, f'{args.volume_dir}/{name}',
                                str(dest / name)], env=env, capture_output=True, text=True)
            if p.returncode and name in REQUIRED:
                sys.exit(f'could not fetch {name}: {p.stderr.strip()[-300:]}')
        if name in REQUIRED and not (dest / name).exists():
            sys.exit(f'missing {name}')
    for name in FILES:                           # the runner writes these with the platform's line ends; store LF
        f = dest / name
        if f.exists():
            f.write_bytes(f.read_bytes().replace(b'\r\n', b'\n'))

    recs = {(r['task'], r['run'], r['fork']): r for r in map(json.loads, open(args.states, encoding='utf-8'))}
    by, cells, problems = collections.Counter(), collections.Counter(), []
    for j, line in enumerate(open(dest / 'results.jsonl', encoding='utf-8'), 1):
        row = json.loads(line)
        if row.get('skip'):
            problems.append(f'line {j}: a cell entered as finished')
            continue
        rec = recs.get((row['task'], row['run'], row['fork']))
        if rec is None or row['arm'] != RUNNER_ARM[rec['arm']]:
            problems.append(f'line {j}: no record of the states file under this arm')
            continue
        cells[(row['task'], row['run'], row['fork'], row['arm'], row['seed'])] += 1
        by[rec['arm']] += 1
    problems += [f'cell {c} is there {k} times' for c, k in cells.items() if k > 1]
    print('rows by arm:', dict(by), '| states with a row:',
          len({recs[c[:3]]['state_id'] for c in cells}), 'of', len({r['state_id'] for r in recs.values()}))
    for name in FILES:
        f = dest / name
        if f.exists():
            print(f'  {name}: md5 {hashlib.md5(f.read_bytes()).hexdigest()}')
    if problems:
        print('PROBLEMS:', *problems[:20], sep='\n  ')
        sys.exit(1)
    print('stored in', dest)


if __name__ == '__main__':
    main()
