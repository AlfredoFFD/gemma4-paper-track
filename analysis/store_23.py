"""Store the whole runs of experiment 23 in the repository without the competition's task text.

The stripping of analysis/store_14.py, through analysis/store_18.store_trace (imported, unchanged): a trace's system
prompt and task prompt are replaced by a marker with the length and sha1 of the text; every other step is kept. The
key `code_graph` that arms PE and PH add to a read lists graph nodes of the repository (PE with their files and line
ranges, as the graph tools answer; PH by name only), so it is kept. The test logs are copied; the session logs and
mode check's pushes/ are not.
Arms N, PH and PE (any may have run alone); the full run is two shards.

Usage:
  py -I -X utf8 analysis/store_23.py [--seed 2] <merged out_23 dir> [<destination, default analysis/results/23>]
  py -I -X utf8 analysis/store_23.py [--seed 2] --pull <empty local dir> [<destination>]
      first downloads /out_23/shards of the volume gemma-forks-c into <dir> with the Modal CLI and merges the shards
      (`analysis/modal_h/wholerun23_runner.py merge <dir>`), then stores
The merged directory holds <dir>/<arm>/seed<k> beside <dir>/shards/<k>of<M>/<arm>/seed<k>; the per-shard files
(versions_23.json, pip_freeze_23.txt, platform_actual_23.json) are stored with the shard in their name. An arm that
did not run is reported and skipped. Running it twice gives identical files.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from store_14 import KEEP  # noqa: E402
from store_18 import VOLUME, store_trace  # noqa: E402

ARMS = ('N', 'PH', 'PE')
PER_RUN = ('versions_23.json', 'pip_freeze_23.txt', 'platform_actual_23.json')


def pull(local):
    local = Path(local)
    env = dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8')
    local.mkdir(parents=True, exist_ok=True)
    # the CLI writes the remote folder's last component below the target: <local>/shards
    subprocess.run(['modal', 'volume', 'get', VOLUME, '/out_23/shards', local.as_posix(), '--force'], check=True, env=env)
    if not (local / 'shards').is_dir():
        sys.exit(f'the download did not produce {local / "shards"}')
    subprocess.run([sys.executable, '-I', '-X', 'utf8', str(HERE / 'modal_h' / 'wholerun23_runner.py'), 'merge', str(local)],
                   check=True)
    return local


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    seed = 2
    if args[0] == '--seed':
        seed, args = int(args[1]), args[2:]
    seed_dir = f'seed{seed}'
    if args[0] == '--pull':
        src_root = pull(args[1])
        args = args[1:]
    else:
        src_root = Path(args[0])
    dst_root = Path(args[1]) if len(args) > 1 else HERE / 'results' / '23'
    shards = sorted(p for p in (src_root / 'shards').iterdir() if p.is_dir()) if (src_root / 'shards').is_dir() else []
    stored = 0
    for arm in ARMS:
        src = src_root / arm / seed_dir
        if not src.is_dir():
            print(f'{arm}: no {seed_dir} in {src_root / arm} (not run in this launch, or not merged): skipped')
            continue
        stored += 1
        dst = dst_root / arm / seed_dir
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
                f = shard / arm / seed_dir / name
                if f.exists():
                    stem, ext = name.rsplit('.', 1)
                    out = f'{stem}_shard{shard.name}.{ext}'
                    shutil.copyfile(f, dst / out)
                    copied.append(out)
        patches = sorted((src / 'patches').glob('*')) if (src / 'patches').is_dir() else []
        for p in patches:
            shutil.copyfile(p, dst / 'patches' / p.name)
        traces = sorted((src / 'traces').glob('*.json'))
        replaced = sum(store_trace(t, dst / 'traces' / t.name, None)[0] for t in traces)
        print(f'{arm}: copied {", ".join(copied)}; {len(patches)} patches; {len(tests)} test logs; {len(traces)} traces with '
              f'{replaced} prompt messages replaced by a marker')
    if not stored:
        sys.exit('no arm stored')


if __name__ == '__main__':
    main()
