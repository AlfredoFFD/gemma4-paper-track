"""Addresses for pre-registration 14: the public tasks that pre-registration 09 did not use.

analysis/make_spans_g.py wrote one address table per task of the fresh population (the 106 tasks that other teams'
traces cover). This script does the same, with the same function (`make_spans_g.address`, imported), for every other
task of data/tasks.jsonl that has a snapshot, so that whole runs can use the full public task set.

Writes data/cache/fresh_spans/<task>.json ({node name: {"file": ..., "lines": ...}}; not tracked: it is rebuilt from the
competition data by this script) and the tracked manifest analysis/fork_states_h/spans_manifest_extra.json with one
md5 and the counts per task.
Usage: py -I -X utf8 analysis/make_spans_h.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from make_spans_g import FRESH, OUT, address  # noqa: E402

MANIFEST = HERE / 'fork_states_h' / 'spans_manifest_extra.json'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    done = {json.loads(line)['task'] for line in open(FRESH, encoding='utf-8')}
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, skipped = {}, []
    for line in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8'):
        t = json.loads(line)
        task = t['instance_id']
        if task in done:
            continue
        if not (ROOT / 'data' / 'snapshots' / f'{task}.tgz').exists():
            skipped.append(task)
            continue
        g = json.load(open(ROOT / 'data' / 'graphs' / f"{t['repo'].split('/')[1]}_{t['base_commit']}.json", encoding='utf-8'))
        names = sorted({n['name'] for n in g['nodes']})
        table = {}
        for name in names:
            a = address(task, name)
            if a:
                table[name] = a
        text = json.dumps(table, sort_keys=True, ensure_ascii=False)
        (OUT / f'{task}.json').write_text(text, encoding='utf-8', newline='\n')
        manifest[task] = {'md5': hashlib.md5(text.encode('utf-8')).hexdigest(), 'graph_nodes': len(names),
                          'with_file': len(table), 'with_lines': sum(1 for v in table.values() if 'lines' in v)}
        print(f'{task}: nodes {len(names)}, with a file {len(table)}, with a line range {manifest[task]["with_lines"]}')
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding='utf-8', newline='\n')
    tot = {k: sum(m[k] for m in manifest.values()) for k in ('graph_nodes', 'with_file', 'with_lines')}
    print(f'{len(manifest)} tasks; graph nodes {tot["graph_nodes"]}, with a file {tot["with_file"]} '
          f'({100 * tot["with_file"] / max(tot["graph_nodes"], 1):.1f}%), with a line range {tot["with_lines"]} '
          f'({100 * tot["with_lines"] / max(tot["graph_nodes"], 1):.1f}%); without a snapshot: {skipped}')
    print(f'manifest md5 {hashlib.md5(MANIFEST.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
