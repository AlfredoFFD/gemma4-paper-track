"""Experiment 22: the notes of the four arms. ON and OA are those of experiment 18, copied byte for byte; OF is new.

OF, the functions with their lines: the header line of ON and OA, then one line per DISTINCT NAME of the ON note, in
the ON note's order:
  - <file path>, lines <start>-<end> (<NAME>)     for a NAME that is a function or class: the span of that definition
                                                  in the task's snapshot (analysis/nodes.py `scopes`, decorators
                                                  included; the definition make_oracle_18.py named)
  - <file path> (<NAME>)                          for a NAME that is a module (the place lies in no definition) or a
                                                  path (a file that is not Python)
So OF holds what ON holds plus where each named definition is, and nothing about which lines inside it change.

Reads data/cache/oracle_18/<task>.json, checks every ON and OA note against the md5 of analysis/oracle_18/manifest.json
and that the ON note is rebuilt from the stored places, and writes data/cache/oracle_22/<task>.json ({"ON", "OF",
"OA"}; not tracked: built from the competition data) and the tracked manifest analysis/oracle_22/manifest.json (per
task: counts and the md5 of each note, and whether ON and OA equal those of 18; no file path, line number or name).
Usage: py -I -X utf8 analysis/make_oracle_22.py
"""
import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from make_oracle_18 import HEADER, module_name  # noqa: E402

TASKS = HERE / 'oracle_18' / 'tasks_18.txt'
MANIFEST_18 = HERE / 'oracle_18' / 'manifest.json'
SRC = ROOT / 'data' / 'cache' / 'oracle_18'
OUT = ROOT / 'data' / 'cache' / 'oracle_22'
TRACKED = HERE / 'oracle_22'


def md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def of_note(task, places):
    """(OF text, names with a line range, names without)."""
    lines, seen, with_range, without = [HEADER], set(), 0, 0
    for p in places:
        name = p['name']
        if name in seen:
            continue
        seen.add(name)
        if p['kind'] == 'scope':
            qual = name[len(module_name(p['file'])) + 1:]
            assert name == f'{module_name(p["file"])}.{qual}', (task, 'name and module disagree')
            s, e, _d = N.scopes(task, p['file'])[qual]
            assert s <= p['first_changed_line'] <= e, (task, 'the named definition does not hold the place')
            lines.append(f'- {p["file"]}, lines {s}-{e} ({name})')
            with_range += 1
        else:
            lines.append(f'- {p["file"]} ({name})')
            without += 1
    return '\n'.join(lines), with_range, without


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = [line.strip() for line in open(TASKS, encoding='utf-8') if line.strip()]
    m18 = json.loads(MANIFEST_18.read_text(encoding='utf-8'))['tasks']
    OUT.mkdir(parents=True, exist_ok=True)
    TRACKED.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for task in tasks:
        src = json.loads((SRC / f'{task}.json').read_text(encoding='utf-8'))
        on, oa = src['ON'], src['OA']
        names = []
        for p in src['places']:
            if p['name'] not in names:
                names.append(p['name'])
        assert on == '\n'.join([HEADER] + [f'- {n}' for n in names]), (task, 'the ON note is not rebuilt from its places')
        of, with_range, without = of_note(task, src['places'])
        note = {'ON': on, 'OF': of, 'OA': oa}
        (OUT / f'{task}.json').write_text(json.dumps(note, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
                                           encoding='utf-8', newline='\n')
        manifest[task] = {'ON_md5': md5(on), 'OF_md5': md5(of), 'OA_md5': md5(oa), 'OF_chars': len(of),
                          'ON_chars': len(on), 'OA_chars': len(oa), 'names_with_lines': with_range,
                          'names_without_lines': without, 'ON_equals_18': md5(on) == m18[task]['ON_md5'],
                          'OA_equals_18': md5(oa) == m18[task]['OA_md5']}
        assert manifest[task]['ON_equals_18'] and manifest[task]['OA_equals_18'], (task, 'ON or OA differs from 18')
    doc = {'experiment': 22, 'header': HEADER, 'tasks_md5': hashlib.md5(TASKS.read_bytes()).hexdigest(),
           'oracle_18_manifest_md5': hashlib.md5(MANIFEST_18.read_bytes()).hexdigest(), 'tasks': manifest}
    (TRACKED / 'manifest.json').write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    w = sum(m['names_with_lines'] for m in manifest.values())
    wo = sum(m['names_without_lines'] for m in manifest.values())
    ch = [m['OF_chars'] for m in manifest.values()]
    print(f'{len(manifest)} tasks; ON and OA equal those of 18 for all; distinct names {w + wo}: with a line range {w}, '
          f'without {wo}')
    print(f'OF note characters: median {statistics.median(ch)}, max {max(ch)}, min {min(ch)} (ON median '
          f'{statistics.median(m["ON_chars"] for m in manifest.values())}, OA median '
          f'{statistics.median(m["OA_chars"] for m in manifest.values())})')
    print(f'wrote {len(manifest)} notes under data/cache/oracle_22 and analysis/oracle_22/manifest.json (md5 '
          f'{hashlib.md5((TRACKED / "manifest.json").read_bytes()).hexdigest()})')


if __name__ == '__main__':
    main()
