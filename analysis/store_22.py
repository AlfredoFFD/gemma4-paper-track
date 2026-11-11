"""Store the whole runs of experiment 22 in the repository without the competition's task text or the notes.

As analysis/store_18.py (its store_trace is imported, unchanged): a trace's system prompt and task prompt are replaced
by a marker with the length and sha1 of the text; the trace is then searched for the note of its arm
(data/cache/oracle_22/<task>.json: ON, OF or OA) and any string still holding the whole note, or its first line, has
that text replaced by a marker as well (expected: zero); lines of the note the agent repeats are counted, not
replaced. The test logs are copied; the session logs and mode check's first_messages/ are not.

Arms N (no note), ON, OF and OA, seed 3; the full run is two shards (two containers), and one shard may have run alone.

Usage:
  py -I -X utf8 analysis/store_22.py <merged out_22 dir> [<destination, default analysis/results/22>]
  py -I -X utf8 analysis/store_22.py --pull <empty local dir> [<destination>]
      first downloads /out_22/shards of the volume gemma-forks-c into <dir> with the Modal CLI and merges the shards
      (`analysis/modal_h/wholerun22_runner.py merge <dir>`), then stores
The merged directory holds <dir>/<arm>/seed3 beside <dir>/shards/<k>of<M>/<arm>/seed3 of each launch; the per-shard
files (versions_22.json, pip_freeze_22.txt, platform_actual_22.json) are stored with the shard in their name.
Running it twice gives identical files.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from store_14 import KEEP  # noqa: E402
from store_18 import VOLUME, store_trace  # noqa: E402

ARMS = ('N', 'ON', 'OF', 'OA')
NOTE_ARMS = ('ON', 'OF', 'OA')
SEED_DIR = 'seed3'
PER_RUN = ('versions_22.json', 'pip_freeze_22.txt', 'platform_actual_22.json')
ORACLE = ROOT / 'data' / 'cache' / 'oracle_22'


def pull(local):
    local = Path(local)
    env = dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8')
    local.mkdir(parents=True, exist_ok=True)
    # the CLI writes the remote folder's last component below the target: <local>/shards
    subprocess.run(['modal', 'volume', 'get', VOLUME, '/out_22/shards', local.as_posix(), '--force'], check=True, env=env)
    if not (local / 'shards').is_dir():
        sys.exit(f'the download did not produce {local / "shards"}')
    subprocess.run([sys.executable, '-I', '-X', 'utf8', str(HERE / 'modal_h' / 'wholerun22_runner.py'), 'merge', str(local)],
                   check=True)
    return local


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if args[0] == '--pull':
        src_root = pull(args[1])
        args = args[1:]
    else:
        src_root = Path(args[0])
    dst_root = Path(args[1]) if len(args) > 1 else HERE / 'results' / '22'
    shards = sorted(p for p in (src_root / 'shards').iterdir() if p.is_dir()) if (src_root / 'shards').is_dir() else []
    for arm in ARMS:
        src = src_root / arm / SEED_DIR
        if not src.is_dir():
            sys.exit(f'missing {src}: run the merge step first')
        dst = dst_root / arm / SEED_DIR
        for sub in ('traces', 'patches', 'test_outputs'):
            if (dst / sub).is_dir():
                shutil.rmtree(dst / sub)
            (dst / sub).mkdir(parents=True)
        tests = sorted(p for p in (src / 'test_outputs').glob('*') if p.is_file()) if (src / 'test_outputs').is_dir() else []
        for p in tests:
            shutil.copyfile(p, dst / 'test_outputs' / p.name)
        copied = []
        for name in KEEP:
            if (src / name).exists():
                shutil.copyfile(src / name, dst / name)
                copied.append(name)
        for shard in shards:
            for name in PER_RUN:
                f = shard / arm / SEED_DIR / name
                if f.exists():
                    stem, ext = name.rsplit('.', 1)
                    out = f'{stem}_shard{shard.name}.{ext}'
                    shutil.copyfile(f, dst / out)
                    copied.append(out)
        patches = sorted((src / 'patches').glob('*')) if (src / 'patches').is_dir() else []
        for p in patches:
            shutil.copyfile(p, dst / 'patches' / p.name)
        traces = sorted((src / 'traces').glob('*.json'))
        replaced, scrubbed, left, no_note = 0, 0, 0, 0
        for t in traces:
            task = t.stem[len('trace_'):]
            nf = ORACLE / f'{task}.json'
            note = json.loads(nf.read_text(encoding='utf-8'))[arm] if nf.exists() and arm in NOTE_ARMS else None
            no_note += note is None and arm in NOTE_ARMS
            r, c = store_trace(t, dst / 'traces' / t.name, note)
            replaced += r
            scrubbed += c['replaced']
            left += c['lines_left']
        print(f'{arm}: copied {", ".join(copied)}; {len(patches)} patches; {len(tests)} test logs; {len(traces)} traces with '
              f'{replaced} prompt messages replaced by a marker; the note or its first line found elsewhere and replaced '
              f'{scrubbed} times (expected 0); lines of the note repeated in the agent\'s own output, kept: {left}; '
              f'traces without a note file {no_note}')


if __name__ == '__main__':
    main()
