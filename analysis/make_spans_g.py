"""Addresses for pre-registration 09: for each task of the fresh population, every node of the task's
code graph that resolves to a file in the task's snapshot, with its file and, when it is a function or a class, its
line range. Same resolver as every earlier experiment (analysis/nodes.py: longest module prefix, then `ast`), and the
same entry fields as arm EL ("file", "lines" as "start-end").

Writes data/cache/fresh_spans/<task>.json ({node name: {"file": ..., "lines": ...}}; not tracked: it is rebuilt from the
competition data by this script) and the tracked manifest analysis/fork_states_g/spans_manifest.json with one md5 and
the counts per task.
Usage: py -I -X utf8 analysis/make_spans_g.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402

FRESH = HERE / 'fork_states_g' / 'fresh_states.jsonl'
OUT = ROOT / 'data' / 'cache' / 'fresh_spans'
MANIFEST = HERE / 'fork_states_g' / 'spans_manifest.json'


def address(task, name):
    sp = N.span(task, name)
    if not sp:
        return None
    entry = {'file': sp['path']}
    if sp['end'] is not None:
        entry['lines'] = f"{sp['start']}-{sp['end']}"
    return entry


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for line in open(FRESH, encoding='utf-8'):
        s = json.loads(line)
        task = s['task']
        g = json.load(open(ROOT / 'data' / 'graphs' / f"{s['repo'].split('/')[1]}_{s['base_commit']}.json", encoding='utf-8'))
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
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding='utf-8', newline='\n')
    tot = {k: sum(m[k] for m in manifest.values()) for k in ('graph_nodes', 'with_file', 'with_lines')}
    print(f'{len(manifest)} tasks; graph nodes {tot["graph_nodes"]}, with a file {tot["with_file"]} '
          f'({100 * tot["with_file"] / tot["graph_nodes"]:.1f}%), with a line range {tot["with_lines"]} '
          f'({100 * tot["with_lines"] / tot["graph_nodes"]:.1f}%)')
    print(f'manifest md5 {hashlib.md5(MANIFEST.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
