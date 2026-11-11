"""Bring the rows of experiment 24 from the Modal volume into the repository, the way 19's are stored.

Usage: py -I -X utf8 analysis/store_24.py [--src out_24] [--dest analysis/results/24] [--model <id>,...]

For every <model id with / replaced by __>/ folder under /vol/<src> of the volume gemma-forks-c (written by
analysis/modal_g/forks_24_modal.py --mode full) this copies results.jsonl, versions.json, summary.json,
platform_actual.json, pip_freeze.txt, runner.log and plan.json (and, if present, api_errors_retried.jsonl and
fatal.txt) to <dest>/<model folder>/. It runs `modal volume get` into a temporary folder (from Git Bash, prefix
MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8). It refuses a source whose name holds `check`: the rows of the plumbing check
(/vol/out_24_check) are never stored. If NEBIUS_API_KEY is set in the environment, every file is checked not to hold
it and nothing is copied if one does. Prints rows and md5 per file. Running it twice gives identical files.
Then: py -I -X utf8 analysis/analyze_24.py
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOLUME = 'gemma-forks-c'
KEEP = ('results.jsonl', 'versions.json', 'summary.json', 'platform_actual.json', 'pip_freeze.txt', 'runner.log',
        'plan.json')
IF_PRESENT = ('api_errors_retried.jsonl', 'fatal.txt')   # rows replayed again after an API failure; a guard's stop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='out_24')
    ap.add_argument('--dest', default=str(HERE / 'results' / '24'))
    ap.add_argument('--model', default='', help='comma list of model ids; default every model folder found')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if 'check' in args.src:
        raise SystemExit(f'{args.src}: the rows of the plumbing check are not stored')
    want = {m.replace('/', '__') for m in args.model.split(',') if m}
    key = os.environ.get('NEBIUS_API_KEY', '')
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run(['modal', 'volume', 'get', VOLUME, f'/{args.src}', tmp, '--force'],
                           capture_output=True, text=True)
        if p.returncode:
            raise SystemExit(f'nothing fetched ({p.stderr.strip()[-200:]})')
        root = Path(tmp) / Path(args.src).name
        if not root.is_dir():                    # `modal volume get` of a folder may land its content directly
            root = Path(tmp)
        for d in sorted(root.iterdir()):
            if not d.is_dir() or (want and d.name not in want):
                continue
            files = [d / f for f in KEEP + IF_PRESENT if (d / f).exists()]
            if key and any(key in f.read_text(encoding='utf-8', errors='replace') for f in files):
                raise SystemExit(f'{d.name}: a file holds the API key; nothing copied')
            out = Path(args.dest) / d.name
            out.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copyfile(f, out / f.name)
                extra = ''
                if f.name == 'results.jsonl':
                    extra = f', {sum(1 for _ in open(f, encoding="utf-8"))} rows'
                print(f'{d.name}/{f.name}: md5 {hashlib.md5(f.read_bytes()).hexdigest()}{extra}')
            missing = [f for f in KEEP if not (d / f).exists()]
            if missing:
                print(f'  missing on the volume: {missing}')


if __name__ == '__main__':
    main()
