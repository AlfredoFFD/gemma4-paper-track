"""List the Python files of every task snapshot once, so node names can be mapped to files without re-reading 21 GB.

Writes data/cache/snapshot_files/<instance_id>.json: a sorted list of .py paths inside the snapshot.
"""
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / 'data' / 'snapshots'
OUT = ROOT / 'data' / 'cache' / 'snapshot_files'


def index_one(tgz: Path) -> list[str]:
    out = OUT / (tgz.stem + '.json')
    if out.exists():
        return json.loads(out.read_text())
    files = []
    with tarfile.open(tgz, 'r:gz') as tf:
        for m in tf:
            if m.isfile() and m.name.endswith('.py'):
                files.append(m.name)
    files.sort()
    out.write_text(json.dumps(files))
    return files


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    OUT.mkdir(parents=True, exist_ok=True)
    tgzs = sorted(SNAP.glob('*.tgz'))
    for i, t in enumerate(tgzs, 1):
        files = index_one(t)
        print(f'{i:3d}/{len(tgzs)} {t.stem}: {len(files)} .py files, first={files[0] if files else None}', flush=True)
