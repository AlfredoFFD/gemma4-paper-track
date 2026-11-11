"""Store the whole runs of experiment 18 in the repository without the competition's task text or the notes.

The same stripping as analysis/store_14.py (its functions are imported): a trace's system prompt and task prompt
(every system or user message before the agent's first step) are replaced by a marker with the length and sha1 of
the text; every other step is kept. The task prompt of arms ON and OA holds the note (built from the reference
patch, so competition data too); it goes with the task prompt. The stored trace is then searched for the note of its
arm (data/cache/oracle_18/<task>.json): any string that still holds the whole note, or the note's first line, has
that text replaced by a marker as well, and the count is printed (expected: zero). Lines of the note that the
agent repeats in its own words or calls are counted and printed, not replaced (they are the agent's output).
The test logs (test_outputs/) are copied; the session logs (logs/) and mode check's first_messages/ are not.

Arms N (the control of the same launch, no note), ON and OA, seed 2; the full run is two shards (two containers).

Usage:
  py -I -X utf8 analysis/store_18.py <merged out_18 dir> [<destination, default analysis/results/18>]
  py -I -X utf8 analysis/store_18.py --pull <empty local dir> [<destination>]
      first downloads /out_18/shards of the volume gemma-forks-c into <dir> with the Modal CLI and merges the shards
      (`analysis/modal_h/wholerun18_runner.py merge <dir>`), then stores
The merged directory holds <dir>/<arm>/seed2 beside <dir>/shards/<k>of<M>/<arm>/seed2 of each launch; the per-shard
files (versions_18.json, pip_freeze_18.txt, platform_actual_18.json) are stored with the shard in their name, as 14.
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
from store_14 import KEEP, PROMPT_SOURCES, marker  # noqa: E402

ARMS = ('N', 'ON', 'OA')
NOTE_ARMS = ('ON', 'OA')
SEED_DIR = 'seed2'
PER_RUN = ('versions_18.json', 'pip_freeze_18.txt', 'platform_actual_18.json')
ORACLE = ROOT / 'data' / 'cache' / 'oracle_18'
VOLUME = 'gemma-forks-c'


def scrub(obj, texts, counts):
    """obj with every occurrence of each text replaced by its marker (in place for containers)."""
    if isinstance(obj, str):
        for t in texts:
            if t in obj:
                counts['replaced'] += obj.count(t)
                obj = obj.replace(t, marker(t))
        return obj
    if isinstance(obj, list):
        return [scrub(v, texts, counts) for v in obj]
    if isinstance(obj, dict):
        return {k: scrub(v, texts, counts) for k, v in obj.items()}
    return obj


def store_trace(src, dst, note):
    """As store_14.store_trace, then the note (and its first line) wherever it is left. (prompts replaced, counts)."""
    trace = json.loads(src.read_text(encoding='utf-8'))
    replaced = 0
    for step in trace.get('steps') or []:
        if step.get('source') not in PROMPT_SOURCES:
            break
        if step.get('message') is not None:
            step['message'] = marker(step['message'])
            replaced += 1
    counts = {'replaced': 0, 'lines_left': 0}
    if note:
        trace = scrub(trace, [note, note.splitlines()[0]], counts)
        text = json.dumps(trace, ensure_ascii=False)
        counts['lines_left'] = sum(text.count(json.dumps(line, ensure_ascii=False)[1:-1]) for line in note.splitlines()[1:])
    dst.write_text(json.dumps(trace, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    return replaced, counts


def pull(local):
    local = Path(local)
    env = dict(os.environ, MSYS_NO_PATHCONV='1', PYTHONIOENCODING='utf-8')
    local.mkdir(parents=True, exist_ok=True)
    # the CLI writes the remote folder's last component below the target: <local>/shards
    subprocess.run(['modal', 'volume', 'get', VOLUME, '/out_18/shards', local.as_posix(), '--force'], check=True, env=env)
    if not (local / 'shards').is_dir():
        sys.exit(f'the download did not produce {local / "shards"}')
    subprocess.run([sys.executable, '-I', '-X', 'utf8', str(HERE / 'modal_h' / 'wholerun18_runner.py'), 'merge', str(local)],
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
    dst_root = Path(args[1]) if len(args) > 1 else HERE / 'results' / '18'
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
