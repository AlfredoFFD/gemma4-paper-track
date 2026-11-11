"""Store the whole runs of pre-registration 14 in the repository without the competition's task text.

The harness writes one results directory per condition (task_results.jsonl, summary.json, patches/, traces/, logs/,
test_outputs/) and the runner adds extra.jsonl and, per shard, versions_14.json, pip_freeze_14.txt and
platform_actual_14.json. A trace begins with the harness's system prompt and the task prompt, which holds the task
statement of the competition's task file. Competition data is not redistributed, so the copy kept here replaces the
text of those two messages (every system or user message before the agent's first step) by a marker with the
length and the sha1 of the text. Every other step is copied unchanged: the agent's messages, its tool calls and
their results, and the harness's later reminders. The test logs (test_outputs/) are copied; the session logs
(logs/) are not, because they repeat both prompts.

Usage: py -I -X utf8 analysis/store_14.py <merged out_14 dir> [<destination, default analysis/results/14>]
The merged directory is what `analysis/modal_h/wholerun_runner.py merge` writes: <dir>/N/seed1 and <dir>/NAF/seed1,
beside <dir>/shards/<k>of<M>/<condition>/seed1 of each launch.
Prints, per condition, the files copied and the number of messages replaced. Running it twice gives identical files.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEEP = ('task_results.jsonl', 'extra.jsonl', 'summary.json')
PER_SHARD = ('versions_14.json', 'pip_freeze_14.txt', 'platform_actual_14.json')
PROMPT_SOURCES = ('system', 'user')


def marker(text):
    """The text that stands in for a prompt: its length and sha1, so two copies can be compared without the text."""
    raw = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, sort_keys=True)
    return f'[omitted: {len(raw)} characters, sha1 {hashlib.sha1(raw.encode("utf-8")).hexdigest()}]'


def store_trace(src, dst):
    trace = json.loads(src.read_text(encoding='utf-8'))
    replaced = 0
    for step in trace.get('steps') or []:
        if step.get('source') not in PROMPT_SOURCES:
            break  # the agent's first step: everything from here on is kept as it is
        if step.get('message') is not None:
            step['message'] = marker(step['message'])
            replaced += 1
    dst.write_text(json.dumps(trace, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    return replaced


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src_root = Path(sys.argv[1])
    dst_root = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / 'results' / '14'
    shards = sorted(p for p in (src_root / 'shards').iterdir() if p.is_dir()) if (src_root / 'shards').is_dir() else []
    for cond in ('N', 'NAF'):
        src = src_root / cond / 'seed1'
        if not src.is_dir():
            sys.exit(f'missing {src}: run the merge step first')
        dst = dst_root / cond / 'seed1'
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
            for name in PER_SHARD:
                f = shard / cond / 'seed1' / name
                if f.exists():
                    stem, ext = name.rsplit('.', 1)
                    out = f'{stem}_shard{shard.name}.{ext}'
                    shutil.copyfile(f, dst / out)
                    copied.append(out)
        patches = sorted((src / 'patches').glob('*')) if (src / 'patches').is_dir() else []
        for p in patches:
            shutil.copyfile(p, dst / 'patches' / p.name)
        traces = sorted((src / 'traces').glob('*.json'))
        replaced = sum(store_trace(t, dst / 'traces' / t.name) for t in traces)
        print(f'{cond}: copied {", ".join(copied)}; {len(patches)} patches; {len(tests)} test logs; {len(traces)} '
              f'traces with {replaced} prompt messages replaced by a marker')


if __name__ == '__main__':
    main()
