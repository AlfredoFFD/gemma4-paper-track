"""Bring the rows of experiment 19 from the Modal volume into the repository, the way 15 and 17 are stored.

Usage: py -I -X utf8 analysis/store_19.py [--src out_19] [--dest analysis/results/19] [--design 10,17] [--model <id>,...]

For every <design>/<model id with / replaced by __>/ folder under /vol/<src> of the volume gemma-forks-c (written by
analysis/modal_g/forks_19_modal.py) this copies results.jsonl, versions.json, summary.json, platform_actual.json,
pip_freeze.txt and runner.log (and, if present, api_errors_retried.jsonl and fatal.txt) to
<dest>/<design>/<model folder>/forks/. It runs `modal volume get` into a temporary
folder (from Git Bash, prefix MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8). If NEBIUS_API_KEY is set in the
environment, every file is checked not to hold it and nothing is copied if one does. Prints rows and md5 per file.
Running it twice gives identical files. Then: py -I -X utf8 analysis/analyze_19.py
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
KEEP = ('results.jsonl', 'versions.json', 'summary.json', 'platform_actual.json', 'pip_freeze.txt', 'runner.log')
IF_PRESENT = ('api_errors_retried.jsonl', 'fatal.txt')   # rows replayed again after an API failure; a guard's stop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='out_19')
    ap.add_argument('--dest', default=str(HERE / 'results' / '19'))
    ap.add_argument('--design', default='10,17')
    ap.add_argument('--model', default='', help='comma list of model ids; default every model folder found')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    want = {m.replace('/', '__') for m in args.model.split(',') if m}
    key = os.environ.get('NEBIUS_API_KEY', '')
    with tempfile.TemporaryDirectory() as tmp:
        for design in [d for d in args.design.split(',') if d]:
            p = subprocess.run(['modal', 'volume', 'get', VOLUME, f'/{args.src}/{design}', tmp, '--force'],
                               capture_output=True, text=True)
            if p.returncode:
                print(f'design {design}: nothing fetched ({p.stderr.strip()[-200:]})')
                continue
            for d in sorted((Path(tmp) / design).iterdir()):
                if not d.is_dir() or (want and d.name not in want):
                    continue
                files = [d / f for f in KEEP + IF_PRESENT if (d / f).exists()]
                if key and any(key in f.read_text(encoding='utf-8', errors='replace') for f in files):
                    raise SystemExit(f'{design}/{d.name}: a file holds the API key; nothing copied')
                out = Path(args.dest) / design / d.name / 'forks'
                out.mkdir(parents=True, exist_ok=True)
                for f in files:
                    shutil.copyfile(f, out / f.name)
                    extra = ''
                    if f.name == 'results.jsonl':
                        extra = f', {sum(1 for _ in open(f, encoding="utf-8"))} rows'
                    print(f'{design}/{d.name}/forks/{f.name}: md5 {hashlib.md5(f.read_bytes()).hexdigest()}{extra}')
                missing = [f for f in KEEP if not (d / f).exists()]
                if missing:
                    print(f'  missing on the volume: {missing}')


if __name__ == '__main__':
    main()
