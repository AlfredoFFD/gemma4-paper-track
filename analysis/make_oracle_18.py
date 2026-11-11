"""Experiment 18: the oracle notes. Every place the accepted fix changes, as bare names (arm ON) or as addresses (arm OA).

Tasks: those of analysis/results/14/runs_14.csv whose N run entered the analysis, has a GOLD FILE and was NOT shown
every changed region (entered == 1, has_gold_file == 1, every_region != 1). There are exactly 40. Their ids go to the
tracked file analysis/oracle_18/tasks_18.txt in run order: the sorted ids shuffled with random.Random(18).

Per task, from the reference patch (the CHANGED REGIONS of analysis/analyze_14.py: per modified file, the intervals of
changed lines in pre-patch line numbers, as public_runs_time_to_fix.gold_regions builds them; files the patch creates
are left out):
  PLACES  every changed region padded by PAD lines on each side and clipped to the file (its line count in the task's
          snapshot); regions of a file that overlap or lie within MERGE lines of each other (the next place starts at
          most MERGE lines after the current one ends) are merged.
  NAME    of a place: the smallest definition of that file's own syntax tree in the task's snapshot whose span
          contains the place's first changed line (the smallest pre-patch line of the changed regions merged into
          it). Definitions are those of analysis/nodes.py `scopes` (Python `ast`: FunctionDef, AsyncFunctionDef and
          ClassDef, nested ones included, decorators included in the span); a tie in span length goes to the deeper
          qualified name. The NAME is `<module>.<qualname>`: the module's dotted name (the file path with `.py`,
          `/__init__` and a leading `src/` removed and `/` read as `.`) and the chain of enclosing class and function
          names. The competition's code graph is not used (it has no `async def` nodes). With no enclosing definition
          (module-level code) the NAME is the module's dotted name; for a file that is not Python it is the file path.
  ON      one line per distinct NAME, in order of first appearance (files sorted, lines ascending).
  OA      one line per place, same order: `- <file path>, lines <start>-<end> (in <NAME>)`.
Both notes start with the line `Note: the accepted fix for this issue changes code in these places:`.

Writes data/cache/oracle_18/<task>.json ({"ON": text, "OA": text, "places": [...]}; not tracked: it is built from the
competition data) and the tracked manifest analysis/oracle_18/manifest.json, which holds per task only counts and the
md5 of each note (no file path, line number or name). Prints the counts.
Usage: py -I -X utf8 analysis/make_oracle_18.py
"""
import collections
import csv
import hashlib
import json
import random
import statistics
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from make_population_k import parse_patch  # noqa: E402
from public_runs_address import norm  # noqa: E402

RUNS_14 = HERE / 'results' / '14' / 'runs_14.csv'
TASKS = ROOT / 'data' / 'tasks.jsonl'
SNAPSHOTS = ROOT / 'data' / 'snapshots'
OUT = ROOT / 'data' / 'cache' / 'oracle_18'
TRACKED = HERE / 'oracle_18'
N_TASKS = 40
SEED = 18
PAD = 10
MERGE = 5
HEADER = 'Note: the accepted fix for this issue changes code in these places:'


def md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def select_tasks():
    rows = list(csv.DictReader(open(RUNS_14, encoding='utf-8', newline='')))
    ids = sorted(r['task'] for r in rows if r['condition'] == 'N' and r['entered'] == '1'
                 and r['has_gold_file'] == '1' and r['every_region'] != '1')
    assert len(ids) == N_TASKS, f'{len(ids)} tasks, expected {N_TASKS}'
    assert len(set(ids)) == len(ids)
    random.Random(SEED).shuffle(ids)
    return ids


def snapshot_text(task, path):
    """The text of a file of the task's snapshot (pre-patch), or None."""
    if path.endswith('.py'):
        return N.file_text(task, path)
    with tarfile.open(SNAPSHOTS / f'{task}.tgz', 'r:gz') as tf:
        for name in (path, './' + path):
            try:
                m = tf.getmember(name)
            except KeyError:
                continue
            return tf.extractfile(m).read().decode('utf-8', 'replace')
    return None


def module_name(path):
    p = path[:-3] if path.endswith('.py') else path
    if p.endswith('/__init__'):
        p = p[:-len('/__init__')]
    if p.startswith('src/'):
        p = p[len('src/'):]
    return p.replace('/', '.')


def places_of(regions, n_lines):
    """Padded, clipped and merged places: [(start, end, first changed line)], ascending."""
    padded = sorted((max(1, a - PAD), min(n_lines, b + PAD), max(1, min(a, n_lines))) for a, b in regions)
    out = []
    for s, e, first in padded:
        assert s <= e, (s, e)
        if out and s <= out[-1][1] + MERGE:
            ps, pe, pf = out[-1]
            out[-1] = (ps, max(pe, e), min(pf, first))
        else:
            out.append((s, e, first))
    return out


def name_of(task, path, line, lines):
    """(NAME, kind, in an async function) for a place of `path` whose first changed line is `line`.
    kind: scope, module or path."""
    if not path.endswith('.py'):
        return path, 'path', False
    module = module_name(path)
    best = None
    for qual, (s, e, d) in N.scopes(task, path).items():
        if s <= line <= e:
            key = (e - s, -qual.count('.'))
            if best is None or key < best[0]:
                best = (key, qual, d)
    if best is None:
        return module, 'module', False
    return f'{module}.{best[1]}', 'scope', lines[best[2] - 1].lstrip().startswith('async def')


def build(task, t):
    files = parse_patch(t['patch'])
    g = {norm(p): v['regions'] for p, v in files.items() if not v['created'] and v['regions']}
    places = []
    for path in sorted(g):
        text = snapshot_text(task, path)
        assert text is not None, f'{task}: a changed file is not in the snapshot'
        lines = text.splitlines()
        n_lines = len(lines) or 1
        for s, e, first in places_of(g[path], n_lines):
            name, kind, is_async = name_of(task, path, first, lines)
            places.append({'file': path, 'start': s, 'end': e, 'first_changed_line': first, 'name': name, 'kind': kind,
                           'async': is_async})
    names = []
    for p in places:
        if p['name'] not in names:
            names.append(p['name'])
    on = '\n'.join([HEADER] + [f'- {n}' for n in names])
    oa = '\n'.join([HEADER] + [f'- {p["file"]}, lines {p["start"]}-{p["end"]} (in {p["name"]})' for p in places])
    kinds = {p['name']: p['kind'] for p in places}
    counts = {'modified_files': len(g), 'changed_regions': sum(len(v) for v in g.values()), 'places': len(places),
              'distinct_names': len(names), 'names_module_or_path': sum(kinds[n] != 'scope' for n in names),
              'names_module': sum(kinds[n] == 'module' for n in names), 'names_path': sum(kinds[n] == 'path' for n in names),
              'places_in_async': sum(p['async'] for p in places),
              'places_module_or_path': sum(p['kind'] != 'scope' for p in places), 'ON_chars': len(on), 'OA_chars': len(oa), 'ON_md5': md5(on),
              'OA_md5': md5(oa)}
    return {'ON': on, 'OA': oa, 'places': places}, counts


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    order = select_tasks()
    tasks = {json.loads(line)['instance_id']: json.loads(line) for line in open(TASKS, encoding='utf-8') if line.strip()}
    OUT.mkdir(parents=True, exist_ok=True)
    TRACKED.mkdir(parents=True, exist_ok=True)
    (TRACKED / 'tasks_18.txt').write_text('\n'.join(order) + '\n', encoding='utf-8', newline='\n')
    manifest = {}
    print(f'{"task":16s} files regions places names module/path')
    for task in order:
        t = tasks[task]
        note, counts = build(task, t)
        text = json.dumps(note, ensure_ascii=False, indent=1, sort_keys=True)
        (OUT / f'{task}.json').write_text(text + '\n', encoding='utf-8', newline='\n')
        manifest[task] = counts
        print(f'{task:16s} {counts["modified_files"]:5d} {counts["changed_regions"]:7d} {counts["places"]:6d} '
              f'{counts["distinct_names"]:5d} {counts["names_module_or_path"]:11d}')
    doc = {'experiment': 18, 'pad': PAD, 'merge': MERGE, 'header': HEADER, 'order_seed': SEED,
           'tasks_18_md5': hashlib.md5((TRACKED / 'tasks_18.txt').read_bytes()).hexdigest(), 'tasks': manifest}
    (TRACKED / 'manifest.json').write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    tot = {k: sum(m[k] for m in manifest.values()) for k in ('modified_files', 'changed_regions', 'places', 'distinct_names',
                                                             'names_module_or_path', 'names_module', 'names_path',
                                                             'places_in_async', 'places_module_or_path')}
    per = [m['places'] for m in manifest.values()]
    print(f'\n{len(manifest)} tasks; totals: {tot}')
    print(f'places per task: min {min(per)}, median {statistics.median(per)}, max {max(per)}; '
          f'distribution {dict(sorted(collections.Counter(per).items()))}')
    print(f'names that are a module or a path: {tot["names_module_or_path"]} of {tot["distinct_names"]} '
          f'({100 * tot["names_module_or_path"] / tot["distinct_names"]:.1f}%; module {tot["names_module"]}, path '
          f'{tot["names_path"]})')
    print(f'places in an async function: {tot["places_in_async"]} of {tot["places"]}; places whose name is a module '
          f'or a path: {tot["places_module_or_path"]} of {tot["places"]}')
    print(f'note length, characters: ON median {statistics.median(m["ON_chars"] for m in manifest.values())}, '
          f'OA median {statistics.median(m["OA_chars"] for m in manifest.values())}')
    print(f'wrote {TRACKED / "tasks_18.txt"} (md5 {doc["tasks_18_md5"]}), {TRACKED / "manifest.json"} (md5 '
          f'{hashlib.md5((TRACKED / "manifest.json").read_bytes()).hexdigest()}), {len(manifest)} notes under {OUT}')


if __name__ == '__main__':
    main()
