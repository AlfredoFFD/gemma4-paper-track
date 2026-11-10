"""Populations of experiment E (navigation horizon; prereg/06, DRAFT): which states run, with which seeds.

Defined from pre-treatment facts only, over all 407 states of analysis/fork_states_d/states.jsonl:
- gold files: the files the task's gold patch (data/tasks.jsonl, field `patch`) touches. A file is CREATED when every
  hunk of it has the old range -0,0 (the patch format here never uses /dev/null); otherwise it is MODIFIED.
- changed regions of a modified file, one per hunk, in old-file line numbers: from the hunk's first removed line to its
  last; an insertion that does not directly follow a removed line adds the two old-file lines around its insertion
  point (p - 1 and p, where p is the old line the insertion precedes; p - 1 is clamped to 1), so a pure-insertion hunk
  spans those two lines and a mixed hunk spans everything it changes.
- R ("the list reaches the fix"): some entry of `unshown_true_neighbors` lies (by `neighbor_spans`) in a modified gold
  file. Seeds 1 to 5.
- U ("the fix is elsewhere"): not in R, and some modified gold file is not in `shown_files`. Seeds 1 to 3.
- every other state is not run.

Writes analysis/fork_states_k/population.json and prints the sizes, plus how many of the 388 states that were complete
in the pooled analysis (analysis/results/{v5,v6,v8}, ten arms, seeds 1 to 3, frozen failure rule) fall in R and U.
Usage: py -I -X utf8 analysis/make_population_k.py
"""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
STATES = HERE / 'fork_states_d' / 'states.jsonl'
TASKS = ROOT / 'data' / 'tasks.jsonl'
OUT = HERE / 'fork_states_k' / 'population.json'
ARMS = ('A', 'H', 'E', 'RE')
SEEDS = {'R': [1, 2, 3, 4, 5], 'U': [1, 2, 3]}
POOLED_RUNS = ('v5', 'v6', 'v8')
POOLED_ARMS = ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def parse_patch(patch):
    """{path: {'created': bool, 'regions': [[a, b], ...]}} from a unified diff."""
    files = collections.OrderedDict()
    cur = None
    old = None
    hunk = None  # {'points': [...], 'prev_removed': bool}

    def close():
        if cur is not None and hunk is not None and hunk['points']:
            files[cur]['regions'].append([min(hunk['points']), max(hunk['points'])])

    lines = patch.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            close()
            hunk = None
            a, b = ln[4:].strip(), lines[i + 1][4:].strip()
            path = b[2:] if b.startswith('b/') else (a[2:] if a.startswith('a/') else b)
            path = path.split('\t')[0]
            cur = path
            files.setdefault(cur, {'created': True, 'regions': []})
            i += 2
            continue
        m = HUNK.match(ln)
        if m:
            close()
            old_start, old_len = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            if not (old_start == 0 and old_len == 0):
                files[cur]['created'] = False
            old = old_start
            hunk = {'points': [], 'prev_removed': False}
            i += 1
            continue
        if hunk is not None and cur is not None:
            if ln.startswith('-'):
                hunk['points'].append(old)
                old += 1
                hunk['prev_removed'] = True
            elif ln.startswith('+'):
                if not hunk['prev_removed'] and not files[cur]['created']:
                    hunk['points'].extend([max(old - 1, 1), old])  # a pure insertion before old line `old`
                    hunk['prev_removed'] = True  # one insertion block adds its two lines once
            elif ln.startswith('\\'):
                pass
            else:  # context line
                old += 1
                hunk['prev_removed'] = False
        i += 1
    close()
    for v in files.values():
        if v['created']:
            v['regions'] = []
    return files


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def pooled_complete():
    from gates_c import failure, load_rows, skey
    usable = collections.defaultdict(set)
    for v in POOLED_RUNS:
        for r in load_rows(HERE / 'results' / v / 'forks' / 'results.jsonl'):
            if r['arm'] in POOLED_ARMS and r['seed'] in (1, 2, 3) and not failure(r):
                usable[skey(r)].add((r['arm'], r['seed']))
    need = {(a, s) for a in POOLED_ARMS for s in (1, 2, 3)}
    return {k for k, v in usable.items() if need <= v}


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    tasks = {json.loads(l)['instance_id']: json.loads(l) for l in open(TASKS, encoding='utf-8')}
    gold = {t: parse_patch(v['patch']) for t, v in tasks.items()}
    states = [json.loads(l) for l in open(STATES, encoding='utf-8')]
    pop = {'R': [], 'U': []}
    skipped = 0
    for st in states:
        key = [st['task'], st['run'], st.get('fork', 0)]
        g = gold[st['task']]
        modified = {p: v['regions'] for p, v in g.items() if not v['created']}
        shown = set(st.get('shown_files') or [])
        unshown_true = st.get('unshown_true_neighbors', [])
        spans = st.get('neighbor_spans') or {}
        reach = sorted({n for n in unshown_true if spans.get(n) and spans[n]['path'] in modified})
        unopened = sorted(p for p in modified if p not in shown)
        rec = {'key': key, 'gold_files': {p: modified[p] for p in sorted(modified)},
               'created_files': sorted(p for p, v in g.items() if v['created']),
               'unopened_gold_files': unopened, 'listed_true_in_gold_files': reach}
        if reach:
            pop['R'].append(dict(rec, seeds=SEEDS['R']))
        elif unopened:
            pop['U'].append(dict(rec, seeds=SEEDS['U']))
        else:
            skipped += 1
    out = {'source_states': str(STATES.relative_to(ROOT)).replace('\\', '/'), 'source_states_md5': md5(STATES),
           'tasks_md5': md5(TASKS), 'arms': list(ARMS), 'seeds': SEEDS,
           'R': pop['R'], 'U': pop['U'], 'not_run': skipped}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding='utf-8')
    nR, nU = len(pop['R']), len(pop['U'])
    per_arm = nR * len(SEEDS['R']) + nU * len(SEEDS['U'])
    print(f'states: {len(states)}; in R {nR}, in U {nU}, not run {skipped}')
    print(f'tasks: R {len({r["key"][0] for r in pop["R"]})}, U {len({r["key"][0] for r in pop["U"]})}, '
          f'R or U {len({r["key"][0] for r in pop["R"] + pop["U"]})}')
    print(f'replays per arm: {per_arm} (R {nR} x 5 + U {nU} x 3); arms {len(ARMS)}; total replays {per_arm * len(ARMS)}')
    comp = pooled_complete()
    keys = lambda lst: {tuple(r['key']) for r in lst}  # noqa: E731
    print(f'of the {len(comp)} states complete in the pooled analysis: in R {len(comp & keys(pop["R"]))}, '
          f'in U {len(comp & keys(pop["U"]))}')
    print(f'wrote {OUT.relative_to(ROOT)} md5 {md5(OUT)}')


if __name__ == '__main__':
    main()
