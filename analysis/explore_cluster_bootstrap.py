"""EXPLORATORY: registered one-call contrasts with their intervals resampled by step (as registered) and by task.

Usage: py -I -X utf8 analysis/explore_cluster_bootstrap.py > analysis/results/explore_cluster_bootstrap.txt

The registered intervals of the one-call experiments resample paused steps (states). Steps of one task are not
independent (the 407 states come from 205 runs of 77 tasks), so this script prints, for each contrast below, the
point estimate and two 95% intervals side by side:
  by step  the registered interval: analyze_forks.diff_ci (or analyze_15.ratio_ci for a ratio) over states,
           2,000 resamples, seed 0, recomputed here and checked as text against the stored registered output;
  by task  the same function over tasks: every replay of every step of a task is one cluster (all steps of a task
           resampled together), 2,000 resamples, seed 0.
The task of a step is the first field of its state key (task, run, fork), as in the state files
(analysis/fork_states*/states.jsonl).

Contrasts (each on the steps complete in its experiment, by that experiment's own rule):
  03 B3  addresses (E) minus names (H), any listed true neighbor in an unopened file touched; runs v5, v6, v8 pooled,
         states complete in all ten arms (as analysis/analyze_b.py); states analysis/fork_states/states.jsonl.
  12 P1  file and lines (EL, run of 04) minus file only (EPATH), reads a listed neighbor (analysis/analyze_12.py).
  12 P2  file only (EPATH) minus names (H), opens a listed neighbor's file (the other rule of 12; printed too).
  15 Q1  the search result with line numbers (S) minus without (S0), Y1 (analysis/analyze_15.py).
  20 T1  TOLD minus NONE, USES THE LINE; T2 the ratio TOLD / ASKED (analysis/analyze_20.py).
Loaders, outcome definitions and bootstrap functions are imported from the registered scripts; nothing is changed.
The script prints to stdout only.
"""
import collections
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import diff_ci  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402
import analyze_12 as A12  # noqa: E402
import analyze_15 as A15  # noqa: E402
import analyze_20 as A20  # noqa: E402

R = HERE / 'results'
SEEDS = (1, 2, 3)


def by_task(table):
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return out


def stored_has(rel, text):
    return 'reproduces the stored interval' if text in (R / rel).read_text(encoding='utf-8') else \
        f'DOES NOT reproduce the stored text "{text}"'


def size(keys):
    return f'{len(keys)} steps, {len({(k[0], k[1]) for k in keys})} runs, {len({k[0] for k in keys})} tasks'


def counts(table):
    return f'{sum(sum(v) for v in table.values())}/{sum(len(v) for v in table.values())}'


def d(t):
    return f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def span(t):
    return f'[{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def width(t):
    return 100 * (t[2] - t[1])


ROWS = []   # (label, estimate, by step, by task, steps, tasks) for the summary table


def report(label, a_name, b_name, ta, tb, stored_rel, stored_text_of):
    keys = sorted(ta)
    ds = diff_ci(ta, tb)
    dt = diff_ci(by_task(ta), by_task(tb))
    print(f'  {label}')
    print(f'    {size(keys)} | {a_name} {counts(ta)}, {b_name} {counts(tb)}')
    print(f'    by step: {d(ds)} | {stored_has(stored_rel, stored_text_of(ds))} ({stored_rel})')
    print(f'    by task: {d(dt)} | width {width(dt):.2f} points against {width(ds):.2f} by step '
          f'(x{width(dt) / width(ds):.2f}); lower bound above 0: by step {ds[1] > 0}, by task {dt[1] > 0}')
    ROWS.append((label.split(':')[0], f'{100 * ds[0]:+.2f}', span(ds), span(dt), len(keys), len({k[0] for k in keys})))


# ---------------------------------------------------------------- 03 B3

def pr03():
    print('Pre-registration 03, rule B3 (runs v5, v6, v8 pooled; analysis/analyze_b.py)')
    states = load_states(HERE / 'fork_states' / 'states.jsonl')
    rows = []
    for run in ('v5', 'v6', 'v8'):
        rows += load_rows(R / run / 'forks' / 'results.jsonl')
    ok = collections.defaultdict(dict)
    for r in rows:
        if not failure(r):
            ok[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    arms = {a for v in ok.values() for a, _s in v}
    seeds = {s for v in ok.values() for _a, s in v}
    complete = sorted(k for k, v in ok.items() if len(v) == len(arms) * len(seeds))
    print(f'  {len(arms)} arms, seeds {sorted(seeds)}; states complete in every arm and seed: {len(complete)} of '
          f'{len(states)} ({size(list(states))} in the state file)')
    tab = {a: {k: [any_true(states[k], ok[k][(a, s)]['next_call']) for s in sorted(seeds)] for k in complete}
           for a in ('A', 'H', 'E')}
    report('03 B3: addresses (E) minus names (H)', 'E', 'H', tab['E'], tab['H'], 'analyze_b.txt',
           lambda t: f'B3: {t[0]:.4f} [{t[1]:.4f}, {t[2]:.4f}]')
    hs, ht = diff_ci(tab['H'], tab['A']), diff_ci(by_task(tab['H']), by_task(tab['A']))
    print(f'    no rule here: names (H) minus no list (A) on the same {len(complete)} steps: {counts(tab["H"])} against '
          f'{counts(tab["A"])}; {d(hs)} by step, {span(ht)} by task')
    print()


# ---------------------------------------------------------------- 12 P1, P2

def pr12():
    print('Pre-registration 12, rules P1 and P2 (arm EPATH of run 12; H, EL from the run of 04; analysis/analyze_12.py)')
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    new, _n, _f = A12.usable_rows(R / '12' / 'forks' / 'results.jsonl', (A12.NEW,))
    ref, _n, _f = A12.usable_rows(R / 'c' / 'forks' / 'results.jsonl', A12.REF)

    def rows_of(k, arm):
        src = new if arm == A12.NEW else ref
        return [src[k][(arm, s)] for s in SEEDS] if all((arm, s) in src.get(k, {}) for s in SEEDS) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in A12.RULE_ARMS))
    reads = {a: {k: [int(bool(any_true(states[k], r['next_call']))) for r in rows_of(k, a)] for k in complete}
             for a in A12.RULE_ARMS}
    opens = {a: {k: [int(bool(opens_listed_file(states[k], r['next_call']))) for r in rows_of(k, a)] for k in complete}
             for a in A12.RULE_ARMS}
    report('12 P1: file and lines (EL) minus file only (EPATH), reads a listed neighbor', 'EL', 'EPATH',
           reads['EL'], reads['EPATH'], '12/analyze_12.txt', lambda t: f'P1, EL - EPATH on reading a listed neighbor: {d(t)}')
    report('12 P2: file only (EPATH) minus names (H), opens a listed neighbor\'s file', 'EPATH', 'H',
           opens['EPATH'], opens['H'], '12/analyze_12.txt',
           lambda t: f'P2, EPATH - H on opening a listed neighbor\'s file: {d(t)}')
    print()


# ---------------------------------------------------------------- 15 Q1

def pr15():
    print('Pre-registration 15, rule Q1 (analysis/analyze_15.py)')
    recs = [json.loads(l) for l in open(HERE / 'fork_states_s' / 'states.jsonl', encoding='utf-8')]
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs}
    states = {A15.state_key(r): r for r in recs if r['arm'] == 'S'}
    usable = collections.defaultdict(dict)
    for row in load_rows(R / '15' / 'forks' / 'results.jsonl'):
        if row.get('skip'):
            continue
        rec = by_fork.get((row.get('task'), row.get('run'), row.get('fork')))
        if rec is None or row.get('arm') != A15.RUNNER_ARM[rec['arm']] or row.get('seed') not in SEEDS:
            continue
        if not failure(row):
            usable[A15.state_key(rec)][(rec['arm'], row['seed'])] = row
    pair = sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in ('S', 'S0') for s in SEEDS))
    y1 = {a: {} for a in ('S', 'S0')}
    for k in pair:
        for a in ('S', 'S0'):
            sc = [A15.score(states[k], usable[k][(a, s)]['next_call']) for s in SEEDS]
            y1[a][k] = [int(x['reads_hit_file'] and x['past_line_1']) for x in sc]
    report('15 Q1: with line numbers (S) minus without (S0), reads a hit file past line 1', 'S', 'S0',
           y1['S'], y1['S0'], '15/analyze_15.txt', lambda t: f'Q1, Y1 under S minus Y1 under S0: {d(t)}')
    print()


# ---------------------------------------------------------------- 20 T1, T2

def pr20():
    print('Experiment 20, rules T1 and T2 (analysis/analyze_20.py)')
    recs = [json.loads(l) for l in open(HERE / 'fork_states_t' / 'states.jsonl', encoding='utf-8')]
    rec_of = {(A20.state_key(r), r['arm']): r for r in recs}
    states = sorted({A20.state_key(r) for r in recs})
    args = SimpleNamespace(run_dir=str(R / '20' / 'forks'), asked=str(R / '15' / 'forks'), standin=False)
    cells, _skipped, _stray = A20.load_cells(args, recs)
    usable = collections.defaultdict(dict)
    for k, arm, seed, row in cells:
        if arm in A20.ARMS and not failure(row):
            usable[k][(arm, seed)] = row

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    def uses(keys, a):
        out = {}
        for k in keys:
            sc = [A15.score(rec_of[(k, a)], usable[k][(a, s)]['next_call']) for s in SEEDS]
            out[k] = [int(x['reads_hit_file'] and x['past_line_1']) for x in sc]
        return out

    k1 = complete(('TOLD', 'NONE'))
    report('20 T1: TOLD minus NONE, uses the line', 'TOLD', 'NONE', uses(k1, 'TOLD'), uses(k1, 'NONE'),
           '20/analyze_20.txt', lambda t: f'T1, USES THE LINE under TOLD minus under NONE: {d(t)}')
    k2 = complete(('TOLD', 'ASKED'))
    told, asked = uses(k2, 'TOLD'), uses(k2, 'ASKED')
    rs = A15.ratio_ci(told, {}, asked, {})
    rt = A15.ratio_ci(by_task(told), {}, by_task(asked), {})
    text = f'T2, the ratio TOLD / ASKED on USES THE LINE: {rs[0]:.2f} [{rs[1]:.2f}, {rs[2]:.2f}]'
    print('  20 T2: the ratio TOLD / ASKED, uses the line')
    print(f'    {size(k2)} | TOLD {counts(told)}, ASKED {counts(asked)}')
    print(f'    by step: {rs[0]:.2f} [{rs[1]:.2f}, {rs[2]:.2f}], left out {rs[3]} | '
          f'{stored_has("20/analyze_20.txt", text)} (20/analyze_20.txt)')
    print(f'    by task: {rt[0]:.2f} [{rt[1]:.2f}, {rt[2]:.2f}], left out {rt[3]} | two thirds inside the interval: '
          f'by step {rs[1] <= 2 / 3 <= rs[2]}, by task {rt[1] <= 2 / 3 <= rt[2]}')
    ROWS.append(('20 T2 (ratio)', f'{rs[0]:.2f}', f'[{rs[1]:.2f}, {rs[2]:.2f}]', f'[{rt[1]:.2f}, {rt[2]:.2f}]',
                 len(k2), len({k[0] for k in k2})))
    print()


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
    print('EXPLORATORY: registered one-call contrasts, 95% intervals resampling steps (as registered) and tasks')
    print('(2,000 resamples, seed 0; differences in points, the ratio as a ratio). No verdict is changed or made here.')
    print()
    pr03()
    pr12()
    pr15()
    pr20()
    print('Summary')
    print(f'  {"contrast":<14} {"estimate":>9}  {"by step (registered)":<22} {"by task":<22} {"steps":>5} {"tasks":>5}')
    for label, est, s, t, n, nt in ROWS:
        print(f'  {label:<14} {est:>9}  {s:<22} {t:<22} {n:>5} {nt:>5}')


if __name__ == '__main__':
    main()
