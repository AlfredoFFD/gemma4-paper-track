"""Regenerate the paper's figures and Table 1 from the raw replay logs.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py --run C <run_dir> --run E <run_dir>

Writes, next to this script:
  fig_design.png/.svg      Figure 1, the method (one real state of experiment B)
  fig_results.png/.svg     Figure 2, experiment B: registered outcome by arm; file opened versus lines read
  fig_extensions.png/.svg  Figure 3, replications and extensions (experiments C, D1, D2a, D2b, E, F)
  table_rules.png/.svg     Table 1, one row per pre-registered rule, rendered from rules_table.json

Every plotted number is computed here from the raw per-replay rows with the registered code path of its experiment:
  B    the definitions of analysis/rederive_s5.py (hit, opens_file, invalid_kind; it imports the registered scorer),
       loaded without running it (load_rederive_defs), on the pooled hosted runs v5, v6, v8;
  C    analysis/analyze_c.py (its exclusions, complete-state rule and state order; scorer from gates_c / fork_states);
  D1, D2a, D2b  analysis/analyze_d.py (load_run, tables, imported);
  E    analysis/analyze_k.py (score, first_call_failure, imported; its usable-replay and complete-state rules);
  F    analysis/analyze_w.py (its arms, seeds and complete-state rule; any_true and failure from gates_c).
  S    analysis/analyze_g.py, part "one step" (arms H and E on the newest harness wheels; pre-registration 08);
  D2q  analysis/analyze_d.py as for D2a and D2b, on the run with a model of another family (pre-registration 10).
Rates use the frozen bootstrap analyze_forks.boot_ci fed per-state lists in the order the registered script feeds it
(which fixes the interval); differences use analyze_forks.diff_ci. Before anything is saved, every plotted value of a
run whose registered output file exists is checked against the numbers printed there, and any mismatch stops the
script. Runs whose directory does not exist yet are skipped with a printed note ("not drawn: ..."), so the script can
be rerun as the runs arrive. A run that exists but has no registered output yet is drawn and reported as UNCHECKED.
The default run directories are in RUN_DIRS; --run TAG RUN_DIR overrides one (the checks still read the registered
output file of that tag).
"""
import argparse
import ast
import collections
import contextlib
import io
import json
import re
import statistics
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402
from matplotlib.textpath import text_to_path  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

FIG = Path(__file__).resolve().parent
ROOT = FIG.parents[1]
ANALYSIS = ROOT / 'analysis'
RES = ANALYSIS / 'results'
REDERIVE = ANALYSIS / 'rederive_s5.py'
REDERIVE_TXT = RES / 'rederive_s5.txt'
EXPLORE_TXT = RES / 'explore_b.txt'
B_STATES = ANALYSIS / 'fork_states' / 'states.jsonl'
B_RUNS = [RES / v for v in ('v5', 'v6', 'v8')]
C_STATES = ANALYSIS / 'fork_states_c' / 'states.jsonl'
D_STATES = ANALYSIS / 'fork_states_d' / 'states.jsonl'
K_POP = ANALYSIS / 'fork_states_k' / 'population.json'
TABLE_JSON = FIG / 'rules_table.json'

# Later runs: default run directory (the directory the registered script is given), the raw rows file inside it,
# and the registered output files the plotted numbers are checked against.
RUN_DIRS = {'C': RES / 'c' / 'forks', 'D1': RES / 'd1' / 'forks', 'D2a': RES / 'd2_26b' / 'forks',
            'D2b': RES / 'd2_e4b' / 'forks', 'E': RES / 'k' / 'forks', 'F': RES / 'w' / 'forks',
            'S': RES / 'g_onestep' / 'forks', 'D2q': RES / 'qwen' / 'forks'}
ROWS_FILE = {'C': 'results.jsonl', 'D1': 'results.jsonl', 'D2a': 'results.jsonl', 'D2b': 'results.jsonl',
             'E': 'results_k.jsonl', 'F': 'results.jsonl', 'S': 'results.jsonl', 'D2q': 'results.jsonl'}
OUTPUTS = {'C': [RES / 'c' / 'analyze_c.txt', RES / 'c' / 'gates_c.txt'],
           'D1': [RES / 'd1' / 'analyze_d1.txt'],
           'D2a': [RES / 'd2_26b' / 'analyze_d2_26b.txt'],
           'D2b': [RES / 'd2_e4b' / 'analyze_d2_e4b.txt'],
           'E': [RES / 'k' / 'analyze_k.txt', RES / 'k' / 'analyze_k_extra.txt', RES / 'k' / 'explore_k.txt'],
           'F': [RES / 'w' / 'analyze_w.txt'],
           'S': [RES / 'g' / 'analyze_g.txt'],
           'D2q': [RES / 'qwen' / 'analyze_d2_qwen.txt']}

# Registered experiment B values (percent of replays), checked before any figure is saved.
REGISTERED = {('A', 's1'): 2.15, ('P', 's1'): 3.01, ('H', 's1'): 2.75, ('D', 's1'): 4.30, ('E', 's1'): 8.25,
              ('RD', 'rew'): 0.52, ('RE', 'rew'): 1.03}
# Registered 95% intervals of the paper's table (frozen bootstrap, analyze_forks.boot_ci), asserted before saving.
REGISTERED_CI = {('A', 's1'): (0.86, 3.61), ('P', 's1'): (1.55, 4.64), ('H', 's1'): (1.37, 4.30),
                 ('D', 's1'): (2.58, 6.10), ('E', 's1'): (5.76, 10.91), ('RD', 'rew'): (0.00, 1.29),
                 ('RE', 'rew'): (0.34, 1.89)}
# Registered experiment B contrasts (points [95% interval], analyze_forks.diff_ci), as in the paper.
REGISTERED_DIFF = {'B1': (1.55, 0.60, 2.66), 'B3': (5.50, 3.44, 7.65), 'B4_D': (3.78, 2.15, 5.67),
                   'B4_E': (7.22, 4.64, 9.97)}

# ---------------------------------------------------------------- style
INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
RULE_LIGHT = '#e1e1e1'
COLORS = {
    'none': '#c6c6c6',      # nothing added
    'bare': '#8e8e8e',      # bare-name arms (P, H, D)
    'legible': '#1f6fb4',   # the legible arm E (the one accent)
    'partial': '#8fb5dc',   # partial-legible variants (EL, ES), a tint of the accent
    'rewired': '#c47a3d',   # rewired controls (R_D, R_E) and the decoy
}
TINT = {k: v for k, v in {'none': '#e6e6e6', 'bare': '#d2d2d2', 'legible': '#a9c8e6',
                          'partial': '#cfe0f0', 'rewired': '#e6c3a5'}.items()}

# Figure 2, experiment B only. field: 's1' any unopened true neighbor touched; 'rew' any rewired entry touched.
# section: bars are grouped by section, with a gap and a small header between sections. mech: also in panel (b).
ARM_SPECS = [
    dict(arm='A', src='B', field='s1', group='none', section='true', mech=True, label='no list'),
    dict(arm='P', src='B', field='s1', group='bare', section='true', label='bare names, as a tool result'),
    dict(arm='H', src='B', field='s1', group='bare', section='true', mech=True, label='bare names, as a note'),
    dict(arm='D', src='B', field='s1', group='bare', section='true', mech=True,
         label='bare names, with an instruction'),
    dict(arm='E', src='B', field='s1', group='legible', section='true', mech=True,
         label='addresses: file, lines, first line'),
    dict(arm='RD', src='B', field='rew', group='rewired', section='rewired',
         label='rewired, bare names, instruction', code='R$_D$'),
    dict(arm='RE', src='B', field='rew', group='rewired', section='rewired', label='rewired, with addresses',
         code='R$_E$'),
]
SECTION_HEADERS = {
    'true': 'the true list: the next call reads a listed neighbor',
    'rewired': 'a rewired list: the next call reads a listed entry',
}
SECTION_ORDER = ['true', 'rewired']

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK, 'xtick.major.width': 0.6, 'ytick.major.size': 0,
    'mathtext.default': 'regular', 'svg.fonttype': 'none', 'savefig.facecolor': 'white',
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
})
MONO = 'DejaVu Sans Mono'
MINUS = '−'


# ---------------------------------------------------------------- the project's own definitions
def load_rederive_defs():
    """Execute only the imports, constants and function definitions of analysis/rederive_s5.py.

    Its loading, scoring loop and report writing (all at module level) are skipped, so nothing heavy runs and
    analysis/results/rederive_s5.txt is never rewritten.
    """
    tree = ast.parse(REDERIVE.read_text(encoding='utf-8'))
    keep_names = {'HERE', 'ROOT', 'ARMS', 'GRAPH', 'KNOWN', 'VIEW', 'NB', 'OUT', '_ll'}
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            body.append(node)
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id in keep_names
                                                  for t in node.targets):
            body.append(node)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and ast.unparse(node.value.func) == 'sys.path.insert'):
            body.append(node)
    ns = {'__file__': str(REDERIVE), '__name__': 'rederive_s5_defs'}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(REDERIVE), 'exec'), ns)
    for need in ('hit', 'opens_file', 'invalid_kind', 'rate_ci', 'ARMS'):
        assert need in ns, f'{need} not found in {REDERIVE}'
    return ns


R = load_rederive_defs()
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))
# The registered scripts of the later runs (their main() is not run; only functions and constants are used).
import analyze_c as AC  # noqa: E402
import analyze_d as AD  # noqa: E402
import analyze_g as AG  # noqa: E402
import analyze_k as AK  # noqa: E402
import analyze_k_extra as AKX  # noqa: E402
import analyze_w as AW  # noqa: E402
import gates_c as GC  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402  frozen bootstrap
from fork_states import touches  # noqa: E402  frozen scorer

Rate = collections.namedtuple('Rate', 'val lo hi n k raw')   # percent; raw = (p, lo, hi) as fractions
Diff = collections.namedtuple('Diff', 'val lo hi raw')


def r_pct(by_state):
    """Rate of a {state: [0/1, ...]} table with the frozen boot_ci, clusters drawn in the dict's order."""
    p, lo, hi = boot_ci(by_state)
    vals = [v for vs in by_state.values() for v in vs]
    if p is None:
        return None
    return Rate(100 * p, 100 * lo, 100 * hi, len(vals), sum(vals), (p, lo, hi))


def d_pct(a, b, level=0.95):
    p, lo, hi = diff_ci(a, b, level=level)
    return None if p is None else Diff(100 * p, 100 * lo, 100 * hi, (p, lo, hi))


# ---------------------------------------------------------------- experiment B (hosted runs)
def results_files(run_dir):
    run_dir = Path(run_dir)
    for p in (run_dir / 'forks' / 'results.jsonl', run_dir / 'results.jsonl'):
        if p.exists():
            return p
    raise FileNotFoundError(f'no results.jsonl under {run_dir}')


def load_source(states_path, run_dirs, arms=None):
    """Minimum copy of rederive_s5.py's loading block: states, valid replays, complete states.

    Returns states, complete {state key: {(arm, seed): row}}, seeds.
    """
    states = {}
    for line in open(states_path, encoding='utf-8'):
        s = json.loads(line)
        s.pop('steps', None)
        states[(s['task'], s['run'], s.get('fork', 0))] = s
    rows = []
    for d in run_dirs:
        rows += [json.loads(line) for line in open(results_files(d), encoding='utf-8')]
    arms = list(arms) if arms else sorted({r['arm'] for r in rows})
    by_state = collections.defaultdict(dict)
    for r in rows:
        if r['arm'] not in arms or R['invalid_kind'](r):
            continue
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in rows})
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms) * len(seeds) and k in states}
    return states, complete, seeds


def score(states, complete):
    """Per-replay outcomes as in rederive_s5.py's record loop: s1 (S1), rew (S1, rewired), opened (S3)."""
    hit, opens_file = R['hit'], R['opens_file']
    recs = []
    for key, reps in complete.items():
        s = states[key]
        task, sp = s['task'], s['neighbor_spans']
        unshown = [n for n in s['unshown_true_neighbors'] if sp.get(n)]
        rsp = s.get('rewired_spans') or {}
        rew = [n for n in s.get('rewired_entries', []) if rsp.get(n)]
        unshown_files = {sp[n]['path'] for n in unshown}
        for (arm, seed), r in reps.items():
            c = r['next_call']
            recs.append(dict(key=key, arm=arm, seed=seed,
                             s1=any(hit(c, sp[n], n, task) for n in unshown),
                             rew=any(hit(c, rsp[n], n, task) for n in rew),
                             opened=any(opens_file(c, f) for f in unshown_files)))
    return recs


def per_state(recs, arm, field):
    """{state: [0/1 per seed]} for one arm, states in the order analyze_b.py builds them (first appearance among the
    valid rows read v5, v6, v8: load_source keeps that order in `complete` and score() walks it)."""
    by_state = {}
    for r in recs:
        if r['arm'] == arm:
            by_state.setdefault(r['key'], []).append(int(r[field]))
    return by_state


def rate(recs, arm, field):
    """Rate with the frozen bootstrap analyze_forks.boot_ci (Python's random, seed 0, 2,000 resamples, clusters =
    states), fed in analyze_b.py's state order."""
    return r_pct(per_state(recs, arm, field))


def exp_b():
    states, complete, seeds = load_source(B_STATES, B_RUNS, R['ARMS'])
    recs = score(states, complete)
    print(f'experiment B: {len(complete)} complete states, seeds {seeds}, {len(recs)} replays')
    values = {}
    for s in ARM_SPECS:
        for field in {s['field'], 'opened', 's1'}:
            values[(s['arm'], field)] = rate(recs, s['arm'], field)
    t = {(a, f): per_state(recs, a, f) for a in ('H', 'D', 'E', 'RD', 'RE') for f in ('s1', 'rew')}
    diffs = {'B1': d_pct(t[('D', 's1')], t[('H', 's1')]), 'B3': d_pct(t[('E', 's1')], t[('H', 's1')]),
             'B4_D': d_pct(t[('D', 's1')], t[('RD', 'rew')]), 'B4_E': d_pct(t[('E', 's1')], t[('RE', 'rew')])}
    info = (len(states), len(complete), len(R['ARMS']), seeds)
    return dict(values=values, diffs=diffs, n_complete=len(complete), info=info,
                rates={'E': values[('E', 's1')], 'H': values[('H', 's1')]})


# ---------------------------------------------------------------- later runs, each with its registered code path
def exp_c(run_dir):
    """analyze_c.py's main(), minus printing: rows of arms Ep, EL, ES, E, H; its failure chain (gates_c.failure, the
    same order of checks); complete states across every arm and seed present, in order of first appearance among the
    usable rows; the scorer and line lengths of analyze_c (fork_states.touches with gates_c._ll)."""
    states = GC.load_states(C_STATES)
    rows = [r for r in GC.load_rows(Path(run_dir) / 'results.jsonl') if r['arm'] in AC.ARMS_C + ('E', 'H')]
    ok = [r for r in rows if GC.failure(r) is None]
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[GC.skey(r)][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in ok})
    arms = sorted({r['arm'] for r in ok}, key=AC.ARMS_ALL.index)
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms) * len(seeds)}
    tab = {o: {a: collections.defaultdict(list) for a in arms} for o in ('any_true', 'swapped', 'decoy')}
    for key, reps in complete.items():
        s = states[key]
        spans, dspan = s['neighbor_spans'], s['decoy_span']
        unshown = set(s.get('unshown_true_neighbors', s['true_neighbors']))
        for (arm, seed), r in reps.items():
            call = r['next_call']
            touched = GC.touch_map(s, call, [n for n in s['true_neighbors'] if n in unshown], spans)
            tab['any_true'][arm][key].append(int(any(bool(v) and v != 'graph' for v in touched.values())))
            sw = touched.get(s['swapped_out'])
            tab['swapped'][arm][key].append(int(bool(sw) and sw != 'graph'))
            dec = touches(call, dspan, s['decoy'], line_lengths=GC._ll(s['task'], dspan['path'])) if dspan else None
            tab['decoy'][arm][key].append(int(bool(dec) and dec != 'graph'))
    T = tab['any_true']
    rates = {a: r_pct(T[a]) for a in arms}
    rates['swapped_E'] = r_pct(tab['swapped']['E']) if 'E' in arms else None
    rates['decoy_Ep'] = r_pct(tab['decoy']['Ep']) if 'Ep' in arms else None
    diffs = {}
    if {'E', 'H'} <= set(arms):
        diffs['G2'] = d_pct(T['E'], T['H'])
        for a in ('EL', 'ES'):
            if a in arms:
                diffs[f'C2_{a}'] = d_pct(T[a], T['H'])
    if {'E', 'Ep'} <= set(arms):
        diffs['C1'] = d_pct(tab['swapped']['E'], tab['decoy']['Ep'])
    if {'E', 'EL'} <= set(arms):
        diffs['E_EL_90'] = d_pct(T['E'], T['EL'], 0.90)
    # gate G1 as gates_c.g1 computes it (that function only prints): median absolute relative prompt-size difference
    points = {}
    fid = Path(run_dir) / 'fidelity.jsonl'
    if fid.exists():
        good = [r for r in GC.load_rows(fid) if not (r.get('error') or r.get('replayed_prompt_tokens') is None
                                                     or not r.get('logged_prompt_tokens'))]
        rel = [abs(r['replayed_prompt_tokens'] - r['logged_prompt_tokens']) / r['logged_prompt_tokens'] for r in good]
        points['G1'] = statistics.median(rel) if rel else None
    return dict(n_rows=len(rows), n_complete=len(complete), rates=rates, diffs=diffs, arms=arms, seeds=seeds,
                points=points)


def exp_d(run_dir, mode):
    """analyze_d.py: load_run, the complete-state rule of its main(), tables (imported)."""
    arms = AD.ARMS[mode]
    states = GC.load_states(D_STATES)
    rows, _n_arm, _fail, usable, _other = AD.load_run(run_dir, arms)
    need = {(a, s) for a in arms for s in AD.SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    T = AD.tables(complete, usable, states, arms)['any_true']
    rates = {a: r_pct(T[a]) for a in arms}
    if mode == 'd1':
        diffs = {'T1': d_pct(T['PE'], T['P']), 'T2': d_pct(T['PE'], T['E']), 'T2_90': d_pct(T['PE'], T['E'], 0.90)}
    else:
        diffs = {'M1': d_pct(T['E'], T['H'])}
    return dict(n_rows=len(rows), n_complete=len(complete), n_states=len(states), rates=rates, diffs=diffs)


def exp_s(run_dir):
    """analyze_g.py's part "one step", minus printing: arms H and E, seeds 1 to 3, gates_c.failure, complete states in
    sorted order, any_true from gates_c."""
    states = GC.load_states(D_STATES)
    rows = [r for r in GC.load_rows(Path(run_dir) / 'results.jsonl')
            if r['arm'] in AG.ONE_ARMS and r['seed'] in AG.ONE_SEEDS]
    usable = collections.defaultdict(dict)
    for r in rows:
        if GC.failure(r) is None:
            usable[GC.skey(r)][(r['arm'], r['seed'])] = r
    need = {(a, s) for a in AG.ONE_ARMS for s in AG.ONE_SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    T = {a: {k: [GC.any_true(states[k], usable[k][(a, s)]['next_call']) for s in AG.ONE_SEEDS] for k in complete}
         for a in AG.ONE_ARMS}
    return dict(n_rows=len(rows), n_complete=len(complete), n_states=len(states), rates={a: r_pct(T[a]) for a in AG.ONE_ARMS},
                diffs={'S1': d_pct(T['E'], T['H'])})


def exp_e(run_dir):
    """analyze_k.py's main(), minus printing: usable replays (first_call_failure), complete states per population,
    score (imported), per-state tables in sorted state order."""
    states = GC.load_states(D_STATES)
    pop = json.load(open(K_POP, encoding='utf-8'))
    member = {tuple(g['key']): (p, g) for p in ('R', 'U') for g in pop[p]}
    rows = [json.loads(l) for l in open(Path(run_dir) / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    usable = collections.defaultdict(dict)
    for r in rows:
        k = GC.skey(r)
        if k in member and r['arm'] in AK.ARMS and r['seed'] in member[k][1]['seeds'] and not AK.first_call_failure(r):
            usable[k][(r['arm'], r['seed'])] = r
    complete = {p: sorted(k for k, (pp, g) in member.items() if pp == p
                          and {(a, s) for a in AK.ARMS for s in g['seeds']} <= set(usable.get(k, {})))
                for p in ('R', 'U')}
    rates, diffs, tabs, curves = {}, {}, {}, {}
    for p in ('R', 'U'):
        if not complete[p]:
            continue
        scored = {(k, key): AK.score(states[k], member[k][1], r) for k in complete[p] for key, r in usable[k].items()}
        seeds = pop['seeds'][p]
        tabs[p] = {y: {a: {k: [scored[(k, (a, s))][y] for s in seeds] for k in complete[p]} for a in AK.ARMS}
                   for y in ('Yline', 'Yfile')}
        for y in ('Yline', 'Yfile'):
            for a in AK.ARMS:
                rates[(p, y, a)] = r_pct(tabs[p][y][a])
            # analysis/explore_k.py section 1 (exploratory): reached by the end of model call kk, i.e. first_<y> is
            # not None and at most kk; same complete states and score; states in sorted order, seeds in order
            for kk in range(1, 6):
                t = {a: {k: [int(scored[(k, (a, s))][f'first_{y}'] is not None
                                 and scored[(k, (a, s))][f'first_{y}'] <= kk) for s in seeds] for k in complete[p]}
                     for a in AK.ARMS}
                for a in AK.ARMS:
                    curves[(p, y, kk, a)] = r_pct(t[a])
                curves[(p, y, kk, 'E - H')] = d_pct(t['E'], t['H'])
                curves[(p, y, kk, 'E - A')] = d_pct(t['E'], t['A'])
        if p == 'R':   # K1 clustered by task, as analyze_k_extra.py computes it
            t = AKX.table(pop, complete, scored, 'R', 'Yline', 'task')
            diffs['K1_task'] = d_pct(t['E'], t['H'])
    if 'R' in tabs:
        diffs['K1'] = d_pct(tabs['R']['Yline']['E'], tabs['R']['Yline']['H'])
    if 'U' in tabs:
        diffs['K2'] = d_pct(tabs['U']['Yfile']['E'], tabs['U']['Yfile']['A'])
    n_c = {p: len(complete[p]) for p in ('R', 'U')}
    return dict(n_rows=len(rows), n_complete=min(n_c.values()), n_pop=n_c, n_total={p: len(pop[p]) for p in ('R', 'U')},
                seeds=pop['seeds'], rates=rates, diffs=diffs, curves=curves)


def exp_f(run_dir):
    """analyze_w.py's main(), minus printing: arms and seeds of analyze_w, gates_c.failure, complete states sorted,
    gates_c.any_true."""
    states = GC.load_states(D_STATES)
    rows = [r for r in GC.load_rows(Path(run_dir) / 'results.jsonl') if r['arm'] in AW.ARMS]
    usable = collections.defaultdict(dict)
    for r in rows:
        if not GC.failure(r) and r['seed'] in AW.SEEDS:
            usable[GC.skey(r)][(r['arm'], r['seed'])] = r
    need = {(a, s) for a in AW.ARMS for s in AW.SEEDS}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    hit = {a: collections.defaultdict(list) for a in AW.ARMS}
    for k in complete:
        for a in AW.ARMS:
            for s in AW.SEEDS:
                hit[a][k].append(GC.any_true(states[k], usable[k][(a, s)]['next_call']))
    rates = {a: r_pct(hit[a]) for a in AW.ARMS}
    # F2 as analyze_w.py scores it: the first call is a read_file with a mangled line-bound name
    mang = {a: collections.defaultdict(list) for a in AW.ARMS}
    for k in complete:
        for a in AW.ARMS:
            for s in AW.SEEDS:
                mang[a][k].append(int(AW.mangled(usable[k][(a, s)]['next_call'])))
    rates.update({f'mangled_{a}': r_pct(mang[a]) for a in AW.ARMS})
    # F1: analyze_w.fidelity on the original-rendering fidelity file (its report line is swallowed)
    with contextlib.redirect_stdout(io.StringIO()):
        f1 = AW.fidelity(Path(run_dir) / 'fidelity_w.jsonl', 'Aw')
    return dict(n_rows=len(rows), n_complete=len(complete), rates=rates, points={'F1': f1},
                diffs={'F3': d_pct(hit['Ew'], hit['Hw']), 'F2': d_pct(mang['A'], mang['Aw'])})


LOADERS = {'C': exp_c, 'D1': lambda d: exp_d(d, 'd1'), 'D2a': lambda d: exp_d(d, 'd2'),
           'D2b': lambda d: exp_d(d, 'd2'), 'E': exp_e, 'F': exp_f, 'S': exp_s, 'D2q': lambda d: exp_d(d, 'd2')}
MIN_COMPLETE = 200   # every pre-registration: below this, everything is EXPLORATORY


# ---------------------------------------------------------------- checks against the registered outputs
class Checks:
    def __init__(self):
        self.lines, self.bad = [], []

    def same(self, label, mine, printed, scale, prec):
        """mine: a fraction (or count); printed: the string the registered script printed with scale and prec."""
        if isinstance(mine, int) and prec is None:
            ok = mine == int(printed)
            shown = f'{mine} vs printed {printed}'
        else:
            a, b = f'{scale * mine:+.{prec}f}', f'{float(printed):+.{prec}f}'
            ok = a == b
            shown = f'{a} vs printed {b}'
        self.lines.append(f'    {label}: {shown} {"match" if ok else "MISMATCH"}')
        if not ok:
            self.bad.append(label)

    def triple(self, label, raw, printed, scale=100, prec=2):
        for name, m, p in zip(('point', 'lo', 'hi'), raw, printed):
            self.same(f'{label} {name}', m, p, scale, prec)

    def missing(self, label):
        self.lines.append(f'    {label}: not printed in the registered output: MISMATCH')
        self.bad.append(label)


def _blocks(path, heads):
    """Lines of a registered output, each tagged with the block (the last header of `heads` seen above it)."""
    cur = None
    for line in path.read_text(encoding='utf-8').splitlines():
        for tag, head in heads.items():
            if head in line:
                cur = tag
        yield cur, line


def check_b(b, ck):
    """Experiment B: rates against rederive_s5.txt and the registered values; contrasts against explore_b.txt's
    'frozen contrasts' (analyze_forks.diff_ci) and the registered values."""
    heads = {'s1': 'any unopened true neighbor touched', 'rew': 'any rewired entry touched', 'opened': 'S3. File level',
             None: 'swapped-out entry touched'}
    pat = re.compile(r'^\s{4}(\w+)\s+([\d.]+)% \[([\d.]+), ([\d.]+)\] \(n=(\d+)\)')
    printed = {}
    for blk, line in _blocks(REDERIVE_TXT, heads):
        m = pat.match(line)
        if blk and m and (m.group(1), blk) not in printed:
            printed[(m.group(1), blk)] = m.groups()[1:]
    ck.lines.append('  experiment B (rederive_s5.txt points and n; registered rates and intervals; explore_b.txt):')
    for k, v in sorted(b['values'].items()):
        p = printed.get(k)
        if p is None:
            ck.missing(f'B {k[0]} {k[1]}')
            continue
        # the point estimate and n must equal the re-derivation's (its intervals come from another bootstrap)
        ck.same(f'B {k[0]} {k[1]} point', v.raw[0], p[0], 100, 2)
        ck.same(f'B {k[0]} {k[1]} n', v.n, p[3], 1, None)
        if k in REGISTERED:
            ck.same(f'B {k[0]} {k[1]} registered rate', v.raw[0], str(REGISTERED[k]), 100, 2)
            ck.same(f'B {k[0]} {k[1]} registered lo', v.raw[1], str(REGISTERED_CI[k][0]), 100, 2)
            ck.same(f'B {k[0]} {k[1]} registered hi', v.raw[2], str(REGISTERED_CI[k][1]), 100, 2)
    txt = EXPLORE_TXT.read_text(encoding='utf-8')
    num = r'([+-][\d.]+) \[ *([+-][\d.]+), +([+-][\d.]+)\]'
    found = {'B1': re.search(r'D - H\s+' + num, txt), 'B3': re.search(r'E - H\s+' + num, txt),
             'B4_D': re.search(r'D true - RD rewired\s+' + num, txt), 'B4_E': re.search(r'E true - RE rewired\s+' + num, txt)}
    for k, d in b['diffs'].items():
        if found[k] is None:
            ck.missing(f'B {k} (explore_b.txt)')
        else:
            ck.triple(f'B {k} vs explore_b.txt', d.raw, found[k].groups())
        ck.triple(f'B {k} vs registered', d.raw, [str(x) for x in REGISTERED_DIFF[k]])


def check_d(tag, e, path, ck):
    mode = 'd1' if tag == 'D1' else 'd2'
    txt = path.read_text(encoding='utf-8').splitlines()
    rate_pat = re.compile(r'^  (\w+): any unopened true neighbor touched ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+)')
    diff_pat = re.compile(r'^  (T1|T2|M1) \w+ - \w+ (95|90)%: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]')
    rates, diffs, n_rows, n_comp = {}, {}, None, None
    for line in txt:
        if m := re.match(r'^experiment D\d: (\d+) replays', line):
            n_rows = m.group(1)
        if m := re.match(r'^complete states \(every arm x seeds 1-3 usable\): (\d+) of', line):
            n_comp = m.group(1)
        if m := rate_pat.match(line):
            rates[m.group(1)] = m.groups()[1:]
        if m := diff_pat.match(line):
            diffs[m.group(1) + ('_90' if m.group(2) == '90' else '')] = m.groups()[2:]
    for label, mine, pr in (('replays', e['n_rows'], n_rows), ('complete states', e['n_complete'], n_comp)):
        ck.same(f'{tag} {label}', mine, pr, 1, None) if pr is not None else ck.missing(f'{tag} {label}')
    for a in AD.ARMS[mode]:
        if a not in rates:
            ck.missing(f'{tag} {a}')
            continue
        ck.triple(f'{tag} {a}', e['rates'][a].raw, rates[a][:3])
        ck.same(f'{tag} {a} hits', e['rates'][a].k, rates[a][3], 1, None)
        ck.same(f'{tag} {a} n', e['rates'][a].n, rates[a][4], 1, None)
    for k, d in e['diffs'].items():
        ck.triple(f'{tag} {k}', d.raw, diffs[k]) if k in diffs else ck.missing(f'{tag} {k}')


def check_c(e, paths, ck):
    a_path, g_path = paths
    if a_path.exists():
        heads = {'any': 'Any true neighbor in an unopened file touched, by arm', 'swapped': 'Swapped-out entry touched',
                 'decoy': 'Decoy touched', None: 'Discrimination with arm E'}
        heads2 = {None: 'Secondary (descriptive)'}
        rate_pat = re.compile(r'^  (\w+): (\d\.\d+) \[(\d\.\d+), (\d\.\d+)\] \| (\d+)/(\d+) replays, (\d+) states')
        diff_pat = re.compile(r'^  (D_E 95%|E minus H \(reference\)|EL minus H|ES minus H|E minus EL 90%): '
                              r'(-?\d\.\d+) \[(-?\d\.\d+), (-?\d\.\d+)\]')
        rates, diffs, n_comp = {}, {}, None
        for blk, line in _blocks(a_path, {**heads, **heads2}):
            if m := re.search(r'states complete across all arms and seeds: (\d+)', line):
                n_comp = m.group(1)
            if (m := rate_pat.match(line)) and blk:
                rates[(blk, m.group(1))] = m.groups()[1:]
            if m := diff_pat.match(line):
                diffs[m.group(1)] = m.groups()[1:]
        ck.same('C complete states', e['n_complete'], n_comp, 1, None) if n_comp else ck.missing('C complete states')
        want = [(('any', a), e['rates'].get(a)) for a in e['arms']]
        want += [(('swapped', 'E'), e['rates'].get('swapped_E')), (('decoy', 'Ep'), e['rates'].get('decoy_Ep'))]
        for key, mine in want:
            if mine is None:
                continue
            if key not in rates:
                ck.missing(f'C {key}')
                continue
            ck.triple(f'C {key[0]} {key[1]}', mine.raw, rates[key][:3], scale=1, prec=4)
            ck.same(f'C {key[0]} {key[1]} hits', mine.k, rates[key][3], 1, None)
            ck.same(f'C {key[0]} {key[1]} n', mine.n, rates[key][4], 1, None)
        names = {'G2': 'E minus H (reference)', 'C2_EL': 'EL minus H', 'C2_ES': 'ES minus H', 'C1': 'D_E 95%',
                 'E_EL_90': 'E minus EL 90%'}
        for k, d in e['diffs'].items():
            ck.triple(f'C {k}', d.raw, diffs[names[k]], scale=1, prec=4) if names[k] in diffs else ck.missing(f'C {k}')
    else:
        ck.lines.append(f'    C: no {a_path.relative_to(ROOT).as_posix()} yet: rates UNCHECKED')
    if g_path.exists() and 'G2' in e['diffs']:
        m = re.search(r'^G2 replication .*?: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\] \| E ([\d.]+)%, H ([\d.]+)%',
                      g_path.read_text(encoding='utf-8'), re.M)
        if m is None:
            ck.missing('C G2 (gates_c.txt)')
        else:
            ck.triple('C G2 vs gates_c.txt', e['diffs']['G2'].raw, m.groups()[:3])
            ck.same('C E rate vs gates_c.txt', e['rates']['E'].raw[0], m.group(4), 100, 2)
            ck.same('C H rate vs gates_c.txt', e['rates']['H'].raw[0], m.group(5), 100, 2)
        g = re.search(r'^G1 fidelity: .*?median abs relative diff ([\d.]+)%', g_path.read_text(encoding='utf-8'), re.M)
        if e['points'].get('G1') is not None:
            ck.same('C G1 median vs gates_c.txt', e['points']['G1'], g.group(1), 100, 2) if g else ck.missing('C G1')
    elif not g_path.exists():
        ck.lines.append(f'    C: no {g_path.relative_to(ROOT).as_posix()} yet: G2 not checked against it')


def check_e(e, paths, ck):
    k_path, x_path = paths[:2]
    if k_path.exists():
        rate_pat = re.compile(r'^  (Yline|Yfile) (\w+)\s*: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+)')
        diff_pat = re.compile(r'^  (Yline|Yfile) (\w+) - (\w+): ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]')
        rates, diffs, n_comp, pop = {}, {}, {}, None
        for line in k_path.read_text(encoding='utf-8').splitlines():
            if m := re.match(r'^complete states: R (\d+) of \d+, U (\d+) of', line):
                n_comp = {'R': m.group(1), 'U': m.group(2)}
            if m := re.match(r'^population (R|U) ', line):
                pop = m.group(1)
            if (m := rate_pat.match(line)) and pop:
                rates[(pop, m.group(1), m.group(2))] = m.groups()[2:]
            if (m := diff_pat.match(line)) and pop:
                diffs[(pop, m.group(1), m.group(2), m.group(3))] = m.groups()[3:]
        for p in ('R', 'U'):
            ck.same(f'E complete states {p}', e['n_pop'][p], n_comp[p], 1, None) if n_comp else ck.missing('E complete')
        for key, mine in e['rates'].items():
            if key not in rates:
                ck.missing(f'E {key}')
                continue
            ck.triple(f'E {" ".join(key)}', mine.raw, rates[key][:3])
            ck.same(f'E {" ".join(key)} hits', mine.k, rates[key][3], 1, None)
            ck.same(f'E {" ".join(key)} n', mine.n, rates[key][4], 1, None)
        where = {'K1': ('R', 'Yline', 'E', 'H'), 'K2': ('U', 'Yfile', 'E', 'A')}
        for k, d in ((k, d) for k, d in e["diffs"].items() if k in where):
            ck.triple(f'E {k}', d.raw, diffs[where[k]]) if where[k] in diffs else ck.missing(f'E {k}')
    else:
        ck.lines.append(f'    E: no {k_path.relative_to(ROOT).as_posix()} yet: UNCHECKED')
    if x_path.exists():
        txt = x_path.read_text(encoding='utf-8')
        for k, (p, y, a, b) in {'K1': ('R', 'Yline', 'E', 'H'), 'K2': ('U', 'Yfile', 'E', 'A')}.items():
            if k not in e['diffs']:
                continue
            for cl, key in (('state', k), ('task', k + '_task')):
                if key not in e['diffs']:
                    continue
                m = re.search(rf'^  {k} {a} - {b} on {y} in {p}, clustered by {cl} \(\d+ clusters\): '
                              r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', txt, re.M)
                ck.triple(f'E {key} vs analyze_k_extra.txt', e['diffs'][key].raw, m.groups()) if m else ck.missing(
                    f'E {key} extra')
    x_path = paths[2]
    if x_path.exists():
        # analysis/explore_k.py section 1: every arm and the two differences, by call, one decimal
        num = r'([+-]?[\d.]+) \[([+-]?[\d.]+), ([+-]?[\d.]+)\]'
        pop = None
        found = 0
        for line in x_path.read_text(encoding='utf-8').splitlines():
            if m := re.match(r'^1\. Population (R|U), (\d+) complete states', line):
                pop = m.group(1)
                ck.same(f'E explore_k complete states {pop}', e['n_pop'][pop], m.group(2), 1, None)
            if line.startswith('2. '):
                pop = None
            if pop and (m := re.match(r'^  (Yline|Yfile) by call (\d): (.*)$', line)):
                y, kk = m.group(1), int(m.group(2))
                for part in m.group(3).split('; '):
                    name, _, rest = part.partition(' ') if not part.startswith('E - ') else (part[:5], ' ', part[6:])
                    mm = re.fullmatch(num, rest.strip())
                    key = (pop, y, kk, name)
                    if mm is None or key not in e['curves']:
                        ck.missing(f'E explore_k {key}')
                        continue
                    ck.triple(f'E explore_k {pop} {y} call {kk} {name}', e['curves'][key].raw, mm.groups(), prec=1)
                    found += 1
        if found != len(e['curves']):
            ck.missing(f'E explore_k: {found} of {len(e["curves"])} curve values printed')
    else:
        ck.lines.append(f'    E: no {x_path.relative_to(ROOT).as_posix()} yet: curves UNCHECKED')
    # the curves at call 5 are the registered five-call outcomes
    for (p, y, kk, a), v in e['curves'].items():
        if kk == 5 and (p, y, a) in e['rates']:
            ck.triple(f'E curve {p} {y} call 5 {a} vs registered rate', v.raw, [f'{100 * x:.2f}' for x in e['rates'][(p, y, a)].raw])


def check_f(e, path, ck):
    rate_pat = re.compile(r'^  (\w+)\s*: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+)$')
    rates, f3, n_comp = {}, None, None
    for blk, line in _blocks(path, {'F3': 'F3. Any unopened true neighbor touched', None: 'Descriptive: the first call'}):
        if m := re.match(r'^complete states: (\d+) of', line):
            n_comp = m.group(1)
        if blk == 'F3' and (m := rate_pat.match(line)):
            rates[m.group(1)] = m.groups()[1:]
        if m := re.match(r'^  F3 Ew - Hw: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', line):
            f3 = m.groups()
    ck.same('F complete states', e['n_complete'], n_comp, 1, None) if n_comp else ck.missing('F complete states')
    for a in AW.ARMS:
        if a not in rates:
            ck.missing(f'F {a}')
            continue
        ck.triple(f'F {a}', e['rates'][a].raw, rates[a][:3])
        ck.same(f'F {a} hits', e['rates'][a].k, rates[a][3], 1, None)
        ck.same(f'F {a} n', e['rates'][a].n, rates[a][4], 1, None)
    ck.triple('F F3', e['diffs']['F3'].raw, f3) if f3 else ck.missing('F F3')
    # F2 (mangled line-bound names in the first call) and F1 (prompt size, original rendering)
    mrates, f2, f1 = {}, None, None
    for blk, line in _blocks(path, {'F2': 'F2. First call is a read_file', None: 'F3. Any unopened'}):
        if blk == 'F2' and (m := re.match(r'^  (\w+)\s*: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+);', line)):
            mrates[m.group(1)] = m.groups()[1:]
        if m := re.match(r'^  F2 A - Aw: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', line):
            f2 = m.groups()
        if m := re.match(r'^  Aw \(string results.*?median absolute relative difference ([\d.]+)%', line):
            f1 = m.group(1)
    for a in AW.ARMS:
        if a not in mrates:
            ck.missing(f'F mangled {a}')
            continue
        ck.triple(f'F mangled {a}', e['rates'][f'mangled_{a}'].raw, mrates[a][:3])
        ck.same(f'F mangled {a} hits', e['rates'][f'mangled_{a}'].k, mrates[a][3], 1, None)
    ck.triple('F F2', e['diffs']['F2'].raw, f2) if f2 else ck.missing('F F2')
    if e['points'].get('F1') is not None:
        ck.same('F F1 median', e['points']['F1'], f1, 100, 2) if f1 else ck.missing('F F1')


def check_s(e, path, ck):
    """The one-step part of analyze_g.py's stored output."""
    txt = path.read_text(encoding='utf-8')
    part = txt.split('PART "one step"')[1] if 'PART "one step"' in txt else ''
    if m := re.search(r'complete states: (\d+) of', part):
        ck.same('S complete states', e['n_complete'], m.group(1), 1, None)
    else:
        ck.missing('S complete states')
    for a in AG.ONE_ARMS:
        m = re.search(rf'any unopened true neighbor touched, arm {a}: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+)', part)
        if not m:
            ck.missing(f'S {a}')
            continue
        ck.triple(f'S {a}', e['rates'][a].raw, m.groups()[:3])
        ck.same(f'S {a} hits', e['rates'][a].k, m.group(4), 1, None)
        ck.same(f'S {a} n', e['rates'][a].n, m.group(5), 1, None)
    m = re.search(r'S1 E - H: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', part)
    ck.triple('S S1', e['diffs']['S1'].raw, m.groups()) if m else ck.missing('S S1')


def check_later(tag, e, ck):
    paths = OUTPUTS[tag]
    ck.lines.append(f'  experiment {tag}:')
    if tag == 'C':
        check_c(e, paths, ck)
        return
    if tag == 'E':
        check_e(e, paths, ck)
        return
    if not paths[0].exists():
        ck.lines.append(f'    no {paths[0].relative_to(ROOT).as_posix()} yet: plotted values UNCHECKED')
        return
    if tag == 'S':
        check_s(e, paths[0], ck)
        return
    (check_f if tag == 'F' else lambda e_, p_, c_: check_d(tag, e_, p_, c_))(e, paths[0], ck)


# ---------------------------------------------------------------- drawing helpers
def _label(spec):
    return spec['label']   # conditions are named in words; the arm letters stay in the appendix


def _fmt(v, sign=False, dec=2):
    s = f'{v:+.{dec}f}' if sign else f'{v:.{dec}f}'
    return s.replace('-', MINUS)


def _bar(ax, y, v, color, h, show_ci=False, ci_below=False, size=8.5, dec=2, extra=None):
    val, lo, hi = v[:3]
    ax.barh(y, val, height=h, color=color, edgecolor='none', zorder=2)
    ax.errorbar(val, y, xerr=[[val - lo], [hi - val]], fmt='none', ecolor=INK, elinewidth=0.8,
                capsize=2.2, capthick=0.8, zorder=3)
    if ci_below:   # value on top, interval under it (narrow panels)
        ax.text(hi, y, f' {_fmt(val, dec=dec)}', va='bottom', ha='left', fontsize=size, color=INK, zorder=4)
        ax.text(hi, y, f'  [{_fmt(lo, dec=dec)}, {_fmt(hi, dec=dec)}]', va='top', ha='left', fontsize=size - 1.5,
                color=MUTED, zorder=4)
        return
    t = ax.text(hi, y, f' {_fmt(val, dec=dec)}', va='center', ha='left', fontsize=size, color=INK, zorder=4)
    if show_ci:   # the interval, small and grey, right after the value
        t = ax.annotate(f' [{_fmt(lo, dec=dec)}, {_fmt(hi, dec=dec)}]', xy=(1, 0.5), xycoords=t, va='center',
                        ha='left', fontsize=size - 1.5, color=MUTED, zorder=4)
    if extra:      # e.g. the raw count, after the interval
        ax.annotate(f'   {extra}', xy=(1, 0.5), xycoords=t, va='center', ha='left', fontsize=size - 1.5, color=INK2,
                    zorder=4)


def _xaxis(ax, xlim, label, size=8.5):
    ax.set_xlim(*xlim)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=size, length=3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.set_xlabel(label, fontsize=size)


def _room(hi_max, width_in, text_in):
    """An x limit that leaves text_in inches after the largest upper bound, on an axis width_in inches wide."""
    return hi_max / max(0.2, 1 - text_in / width_in)


def _nice(x, step):
    return (int(x / step) + 1) * step


# ---------------------------------------------------------------- figure 2: results (experiment B)
def fig_results(values, out_dir):
    specs = ARM_SPECS
    rows = []  # (kind, payload)
    for sec in SECTION_ORDER:
        sec_specs = [s for s in specs if s['section'] == sec]
        if not sec_specs:
            continue
        rows.append(('header', SECTION_HEADERS[sec]))
        rows += [('bar', s) for s in sec_specs]
    mech = [s for s in specs if s.get('mech')]
    n_a = len(rows) - 0.4
    n_b = len(mech) * 1.0 + 0.6
    fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(7.0, 0.30 * (n_a + n_b) + 1.55),
                                     gridspec_kw=dict(height_ratios=[n_a, n_b], hspace=0.32))
    xmax = max(v[2] for v in values.values())
    xlim = (0, (int(xmax / 2) + 1) * 2 + 0.6)

    # panel (a)
    ticks, ticklabels = [], []
    y = 0.0
    for kind, payload in rows:
        if kind == 'header':
            y -= 0.2 if y == 0 else 0.45
            ax_a.text(0, y, payload, ha='left', va='center', fontsize=8, color=INK2, style='italic',
                      transform=ax_a.get_yaxis_transform())
            y -= 0.8
            continue
        s = payload
        _bar(ax_a, y, values[(s['arm'], s['field'])], COLORS[s['group']], 0.62, show_ci=True)
        ticks.append(y)
        ticklabels.append(_label(s))
        y -= 1.0
    ax_a.set_ylim(y + 0.45, 0.1)
    ax_a.set_yticks(ticks, ticklabels)
    for t, s in zip(ax_a.get_yticklabels(), [p for k, p in rows if k == 'bar']):
        if s['group'] == 'legible':
            t.set_fontweight('bold')

    # panel (b): two bars per arm, file opened (tint) and the neighbor's own lines read (full color)
    ticks_b = []
    for i, s in enumerate(mech):
        yc = -i * 1.0
        g = s['group'] if s['group'] in ('legible', 'partial') else 'bare'
        _bar(ax_b, yc + 0.19, values[(s['arm'], 'opened')], TINT[g], 0.36)
        _bar(ax_b, yc - 0.19, values[(s['arm'], 's1')], COLORS[g], 0.36)
        ticks_b.append(yc)
    ax_b.set_yticks(ticks_b, [_label(s) for s in mech])
    for t, s in zip(ax_b.get_yticklabels(), mech):
        if s['group'] == 'legible':
            t.set_fontweight('bold')
    ax_b.legend(handles=[Patch(facecolor=TINT['bare'], label="opens a listed neighbor's file"),
                         Patch(facecolor=COLORS['bare'], label="reads the neighbor's own lines")],
                loc='upper left', bbox_to_anchor=(-0.01, 1.0), ncol=2, frameon=False, fontsize=8,
                handlelength=1.1, handletextpad=0.5, columnspacing=1.4, borderaxespad=0.0)

    for ax, tag in ((ax_a, '(a)'), (ax_b, '(b)')):
        ax.set_xlim(*xlim)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='x', labelsize=8.5, length=3)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
        ax.text(-0.40 / 0.57 + 0.01, 1.0, tag, transform=ax.transAxes, ha='left', va='top', fontsize=10,
                fontweight='bold', color=INK)
    ax_a.set_xlabel('% of replays', fontsize=8.5)
    ax_b.set_xlabel('% of replays (whiskers: 95% interval, clustered by state)', fontsize=8.5)
    ax_b.set_ylim(-(len(mech) - 1) - 0.55, 1.25)
    fig.subplots_adjust(left=0.40, right=0.97, top=0.98, bottom=0.07)
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_results.{ext}', dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------- figure 3: replications and extensions
EXP_NAME = {'B': 'experiment B', 'C': 'experiment C', 'D1': 'experiment D1', 'D2a': 'experiment D2a',
            'D2b': 'experiment D2b', 'E': 'experiment E', 'F': 'experiment F', 'S': 'experiment S (newest wheels)',
            'D2q': 'experiment D2q (another model family)'}
# Figure text names runs in words, never by experiment letter
RUN_NAME = {'B': 'hosted run', 'C': 'rented GPU', 'D1': 'tool-channel run', 'D2a': 'second-model run',
            'D2b': 'second-model run', 'E': 'five-call run', 'F': 'rendering run', 'S': 'newest-wheels run',
            'D2q': 'other-family run'}
# Panel (a): (source, contrast key, legible arm, bare arm, label, code)
FOREST = [
    ('B', 'B3', 'E', 'H', 'Gemma-4-31B, list as a note', 'E − H'),
    ('C', 'G2', 'E', 'H', 'the same, second platform', 'E − H'),
    ('D1', 'T1', 'PE', 'P', 'list as the tool\'s own result', 'PE − P'),
    ('F', 'F3', 'Ew', 'Hw', 'tool results rendered as in the recorded runs', 'Ew − Hw'),
    ('S', 'S1', 'E', 'H', 'harness wheels of Oct 12', 'E − H'),
    ('D2a', 'M1', 'E', 'H', 'Gemma 4 26B-A4B', 'E − H'),
    ('D2b', 'M1', 'E', 'H', 'Gemma 4 E4B', 'E − H'),
    ('D2q', 'M1', 'E', 'H', 'Qwen2.5-Coder-32B', 'E − H'),
]
# Panel (b), the rented-GPU run: (rate key, color group, label, code)
PARTS = [('H', 'bare', 'name', 'H'), ('ES', 'partial', 'name + first line of the definition', 'ES'),
         ('EL', 'partial', 'name + file + line range', 'EL'), ('E', 'legible', 'name + file + line range + first line', 'E')]
FALSE_ENTRY = [('swapped_E', 'legible', 'a true neighbor, with its address', 'E'),
               ('decoy_Ep', 'rewired', 'a false one, written the same way', 'E′')]
# Panel (c), the five-call run: (arm, line color, marker, line style, label)
K_LINES = [('A', '#a3a3a3', 'o', (0, (4, 2)), 'no list'),
           ('H', '#5f5f5f', 's', '-', 'bare names'),
           ('RE', COLORS['rewired'], 'D', '-', 'rewired list, with addresses'),
           ('E', COLORS['legible'], 'o', '-', 'addresses')]
K_BARS = [('A', 'none'), ('H', 'bare'), ('E', 'legible'), ('RE', 'rewired')]
K_WORDS = {'A': 'no list', 'H': 'bare names', 'E': 'addresses', 'RE': 'rewired'}

W_IN = 7.0
LEFT = 0.40          # label column, as in Figure 2
TITLE_H, AXIS_H, GAP_H = 0.30, 0.46, 0.20


def _panel_title(fig, y_top, tag, title):
    fig.text(0.012, y_top, tag, ha='left', va='top', fontsize=10, fontweight='bold', color=INK)
    fig.text(0.058, y_top - 0.004, title, ha='left', va='top', fontsize=9.2, color=INK)


def _sub(n_complete):
    return f'{n_complete:,} complete states' + (' (exploratory: fewer than 200)' if n_complete < MIN_COMPLETE else '')


def _spread(ys, gap):
    """Label positions near ys (same order as ys), at least gap apart, moved as little as possible."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = [ys[i] for i in order]
    for _ in range(50):
        moved = False
        for j in range(1, len(pos)):
            if pos[j] - pos[j - 1] < gap - 1e-9:
                mid = (pos[j] + pos[j - 1]) / 2
                pos[j - 1], pos[j] = mid - gap / 2, mid + gap / 2
                moved = True
        if not moved:
            break
    out = [0.0] * len(ys)
    for i, y in zip(order, pos):
        out[i] = y
    return out


def fig_extensions(exps, out_dir):
    panels = []   # (height in inches of the plot area, draw function)

    # (a) forest plot
    rows = []
    for src, key, a, b, label, code in FOREST:
        e = exps.get(src)
        if e is None:
            print(f'  not drawn: Figure 3(a) row "{label} ({code}), {RUN_NAME[src]}": no {EXP_NAME[src]} run yet')
            continue
        d = e['diffs'].get(key)
        if d is None:
            print(f'  not drawn: Figure 3(a) row "{label}": {key} not estimable in the {EXP_NAME[src]} run')
            continue
        rows.append(dict(label=label, sub=_sub(e['n_complete']), d=d, ra=e['rates'][a], rb=e['rates'][b], a=a, b=b))
    if rows:
        def draw_a(fig, bottom, height):
            fh = fig.get_figheight()
            left, right = LEFT, 0.665
            ax = fig.add_axes([left, bottom + AXIS_H / fh, right - left, height / fh])
            tr = blended_transform_factory(fig.transFigure, ax.transData)
            lo_min = min(min(r['d'].lo for r in rows), 0)
            hi_max = max(r['d'].hi for r in rows)
            ax.set_xlim(min(-1.0, lo_min - 0.8), _nice(hi_max, 2) + 0.4)
            ax.axvline(0, color=MUTED, lw=0.8, zorder=1)
            for i, r in enumerate(rows):
                y = -i
                d = r['d']
                ax.plot([d.lo, d.hi], [y, y], color=INK, lw=1.1, solid_capstyle='butt', zorder=2)
                for xx in (d.lo, d.hi):
                    ax.plot([xx, xx], [y - 0.09, y + 0.09], color=INK, lw=0.9, zorder=2)
                ax.plot(d.val, y, marker='s', ms=5.2, color=COLORS['legible'], mec='white', mew=0.5, zorder=3)
                ax.text(left - 0.012, y + 0.08, r['label'], transform=tr, ha='right', va='bottom', fontsize=8.7,
                        color=INK)
                ax.text(left - 0.012, y + 0.02, r['sub'], transform=tr, ha='right', va='top', fontsize=7.2,
                        color=MUTED)
                ax.text(0.682, y, f'{_fmt(d.val, True)} [{_fmt(d.lo)}, {_fmt(d.hi)}]', transform=tr, ha='left',
                        va='center', fontsize=8.5, color=INK)
                ax.text(0.862, y, f'{_fmt(r["ra"].val)}% vs {_fmt(r["rb"].val)}%', transform=tr, ha='left',
                        va='center', fontsize=7.6, color=INK2)
            top = 0.75
            ax.text(0.682, top, 'points [95% interval]', transform=tr, ha='left', va='bottom', fontsize=7.2,
                    color=MUTED, style='italic')
            ax.text(0.862, top, 'addresses vs names', transform=tr, ha='left', va='bottom', fontsize=7.2,
                    color=MUTED, style='italic')
            ax.set_ylim(-(len(rows) - 1) - 0.55, top + 0.35)
            ax.set_yticks([])
            ax.spines[['top', 'right', 'left']].set_visible(False)
            ax.tick_params(axis='x', labelsize=8.5, length=3)
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
                lambda v, _: '0' if abs(v) < 1e-9 else f'{v:+.0f}'.replace('-', MINUS)))
            ax.set_xlabel('addresses minus bare names: replays whose next call reads a listed neighbor, percentage points',
                          fontsize=8.2)
            return '(a)', 'Addresses against bare names, in every setting tested (the same 407 paused steps)'
        panels.append((0.50 * len(rows) + 0.30, draw_a))

    # (b) the rented-GPU run: which part of an entry, and a false entry
    c = exps.get('C')
    if c is None:
        print('  not drawn: Figure 3(b): no experiment C run yet')
    else:
        parts = [q for q in PARTS if c['rates'].get(q[0]) is not None]
        fals = [f for f in FALSE_ENTRY if c['rates'].get(f[0]) is not None]
        for q in PARTS:
            if q not in parts:
                print(f'  not drawn: Figure 3(b) bar "{q[2]} ({q[3]})": arm not in the experiment C run')
        if len(fals) < len(FALSE_ENTRY):
            print('  not drawn: Figure 3(b) false-entry pair: arm E or Ep not in the experiment C run')
            fals = []
        brows = [('header', 'each neighbor written as (the next call reads a listed neighbor)')]
        brows += [('bar', *q) for q in parts]
        if fals:
            brows += [('header', 'one entry of the list (the next call reads that entry)')]
            brows += [('bar', *f) for f in fals]
        n_units = sum(1.0 if kind == 'bar' else 0.9 for kind, *_ in brows)

        def draw_b(fig, bottom, height):
            fh = fig.get_figheight()
            ax = fig.add_axes([LEFT, bottom + AXIS_H / fh, 0.97 - LEFT, height / fh])
            vals = [c['rates'][r[1]] for r in brows if r[0] == 'bar']
            xlim = (0, _room(max(v.hi for v in vals), (0.97 - LEFT) * W_IN, 1.75))
            ticks, labels, bold = [], [], []
            y = 0.0
            for r in brows:
                if r[0] == 'header':
                    y -= 0.2 if y == 0 else 0.5
                    ax.text(0, y, r[1], ha='left', va='center', fontsize=8, color=INK2, style='italic',
                            transform=ax.get_yaxis_transform())
                    y -= 0.7
                    continue
                _, key, group, text, code = r
                v = c['rates'][key]
                extra = f'{v.k:,} of {v.n:,} replays' if key in ('swapped_E', 'decoy_Ep') else None
                _bar(ax, y, v, COLORS[group], 0.62, show_ci=True, extra=extra)
                ticks.append(y)
                labels.append(text)
                bold.append(key == 'E')
                y -= 1.0
            ax.set_ylim(y + 0.45, 0.1)
            ax.set_yticks(ticks, labels)
            for t, b in zip(ax.get_yticklabels(), bold):
                if b:
                    t.set_fontweight('bold')
            _xaxis(ax, xlim, f'% of replays, {_sub(c["n_complete"])} (whiskers: 95% interval)')
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
            return '(b)', 'Which part of an entry does the work, and a false entry'
        panels.append((0.27 * n_units + 0.12, draw_b))

    # (c) the five-call run: reaching the fix, call by call
    k = exps.get('E')
    if k is None:
        print('  not drawn: Figure 3(c): no experiment E run yet')
    elif ('R', 'Yline', 5, 'A') not in k['curves']:
        print('  not drawn: Figure 3(c): no complete state where the list reaches the fix')
    else:
        cv = k['curves']
        show_u = ('U', 'Yfile', 5, 'A') in cv

        def draw_c(fig, bottom, height):
            fh = fig.get_figheight()
            cr = (0.085, 0.62 if show_u else 0.80)
            ax = fig.add_axes([cr[0], bottom + AXIS_H / fh, cr[1] - cr[0], height / fh])
            calls = [1, 2, 3, 4, 5]
            ends = []
            for arm, color, marker, ls, label in K_LINES:
                ys = [cv[('R', 'Yline', kk, arm)].val for kk in calls]
                strong = arm == 'E'
                ax.plot(calls, ys, color=color, lw=2.0 if strong else 1.3, ls=ls, marker=marker,
                        ms=5.0 if strong else 4.2, mfc=color, mec='white', mew=0.6, zorder=4 if strong else 3,
                        label=label)
                ends.append((arm, color, ys[-1]))
            ymax = 100
            ax.set_ylim(0, ymax)
            ax.set_xlim(0.75, 5.95)
            # values at call 5, moved apart just enough to stay legible
            gap = 8.6 / 72 / (height / ymax)   # one label height in data units
            ly = _spread([v for _, _, v in ends], gap)
            for (arm, color, v), yy in zip(ends, ly):
                ax.text(5.17, yy, f'{K_WORDS[arm]} {_fmt(v, dec=1)}', ha='left', va='center',
                        fontsize=7.6, color=color if arm != 'A' else INK2,
                        fontweight='bold' if arm == 'E' else 'normal')
                if abs(yy - v) > 0.4:
                    ax.plot([5.06, 5.15], [v, yy], color=MUTED, lw=0.5)

            def bracket(x, kk, text, ytext, ha):
                e_, h_ = cv[('R', 'Yline', kk, 'E')].val, cv[('R', 'Yline', kk, 'H')].val
                ax.plot([x, x], [h_, e_], color=INK, lw=0.8, zorder=5)
                for yy in (h_, e_):
                    ax.plot([x - 0.05, x], [yy, yy], color=INK, lw=0.8, zorder=5)
                ax.plot([x, x], [e_ + 0.8, ytext - 1.0], color=MUTED, lw=0.5, ls=(0, (2, 1.5)), zorder=2)
                ax.text(x + (0.06 if ha == 'right' else 0), ytext, text, ha=ha, va='bottom', fontsize=7.2,
                        color=INK2, linespacing=1.2, zorder=6)

            d3, d5 = cv[('R', 'Yline', 3, 'E - H')], k['diffs']['K1']
            bracket(3.1, 3, f'addresses minus names {_fmt(d3.val, True, 1)} [{_fmt(d3.lo, dec=1)}, {_fmt(d3.hi, dec=1)}]\n'
                            'exploratory', 74, 'center')
            bracket(4.9, 5, f'addresses minus names {_fmt(d5.val, True)} [{_fmt(d5.lo)}, {_fmt(d5.hi)}]\n'
                            'registered rule not met', 86, 'right')
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_xticks(calls)
            ax.tick_params(labelsize=8, length=3)
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
            ax.set_yticks([0, 20, 40, 60, 80, 100])
            ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
            ax.set_xlabel(f'model call (where the list reaches the fix: {k["n_pop"]["R"]} states, '
                          f'{cv[("R", "Yline", 5, "A")].n} replays per arm)', fontsize=8)
            ax.set_ylabel('shown a line the fix changes by that call', fontsize=8)
            ax.legend(loc='lower right', bbox_to_anchor=(1.0, 0.02), ncol=2, frameon=False, fontsize=7.4,
                      handlelength=2.0, handletextpad=0.5, columnspacing=1.0, borderaxespad=0.0)
            if show_u:
                ur = (0.745, 0.975)
                au = fig.add_axes([ur[0], bottom + AXIS_H / fh, ur[1] - ur[0], height * 0.62 / fh])
                uv = [cv[('U', 'Yfile', 5, a)] for a, _g in K_BARS]
                for i, (a, g) in enumerate(K_BARS):
                    _bar(au, -i, cv[('U', 'Yfile', 5, a)], COLORS[g], 0.55, ci_below=True, size=7.6, dec=1)
                au.set_yticks([-i for i in range(len(K_BARS))], [K_WORDS[a] for a, _g in K_BARS])
                au.tick_params(axis='y', labelsize=7.4)
                au.set_ylim(-len(K_BARS) + 0.45, 0.55)
                _xaxis(au, (0, _room(max(v.hi for v in uv), (ur[1] - ur[0]) * W_IN, 0.62)),
                       f'{k["n_pop"]["U"]} states, {uv[0].n} replays per arm', size=7.6)
                au.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
                top_u = bottom + (AXIS_H + height * 0.62) / fh
                fig.text(ur[0] - 0.03, top_u + 0.30 / fh, 'where the fix is elsewhere', ha='left', va='bottom',
                         fontsize=8.4, color=INK)
                fig.text(ur[0] - 0.03, top_u + 0.05 / fh, 'opens a file the fix changes\nwithin five calls',
                         ha='left', va='bottom', fontsize=7.4, color=INK2, linespacing=1.15)
            else:
                print('  not drawn: Figure 3(c) bars where the fix is elsewhere: no complete state')
            return '(c)', 'Within five model calls, with reads executing'
        panels.append((2.6, draw_c))

    if not panels:
        print('  not drawn: Figure 3: no run available')
        return False
    H_IN = sum(TITLE_H + h + AXIS_H for h, _ in panels) + GAP_H * (len(panels) - 1) + 0.08
    fig = plt.figure(figsize=(W_IN, H_IN))
    top = H_IN - 0.06
    for h, draw in panels:
        bottom = top - TITLE_H - h - AXIS_H
        tag, title = draw(fig, bottom / H_IN, h)
        _panel_title(fig, top / H_IN, tag, title)
        top = bottom - GAP_H
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_extensions.{ext}', dpi=300)
    plt.close(fig)
    return True


# ---------------------------------------------------------------- Table 1: the pre-registered rules
def _display(s):
    """Typographic minus for negative numbers and for 'X - Y' between arm names; nothing else changes."""
    s = re.sub(r'(?<![\w.])-(?=\d)', MINUS, s)
    return re.sub(r'(?<=\w) - (?=\w)', f' {MINUS} ', s)


def _text_w(s, size, weight='normal', style='normal'):
    prop = FontProperties(family='sans-serif', size=size, weight=weight, style=style)
    return text_to_path.get_text_width_height_descent(s, prop, ismath=False)[0]


def _wrap_pts(text, width_pt, size, weight='normal', style='normal'):
    out = []
    for para in text.split('\n'):
        line = ''
        for word in para.split(' '):
            cand = f'{line} {word}' if line else word
            if line and _text_w(cand, size, weight, style) > width_pt:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


NUM = r'[+\-−]?\d+\.\d+'


def _estimates(text):
    """Each '[lo, hi]' in a cell, in order, with the last decimal number written between it and the previous bracket
    (its point estimate, or None when the bracket stands alone, as in 'clustered by task [lo, hi]')."""
    out, prev = [], 0
    for m in re.finditer(rf'\[({NUM}), ({NUM})\]', text):
        pts = re.findall(NUM, text[prev:m.start()])
        out.append((pts[-1] if pts else None, m.group(1), m.group(2)))
        prev = m.end()
    return out


POINT_KEYS = {'G1', 'F1'}   # a single value (no interval): compared with the first decimal number of the cell


def checkable(exps):
    """Values the figure code computes, by the key a table row names in "check" (estimate cell) or "check_outcome"
    (outcome cell)."""
    out = {}
    src = {'B1': ('B', 'B1'), 'B3': ('B', 'B3'), 'B4_D': ('B', 'B4_D'), 'B4_E': ('B', 'B4_E'), 'G2': ('C', 'G2'),
           'C1': ('C', 'C1'), 'C2_EL': ('C', 'C2_EL'), 'C2_ES': ('C', 'C2_ES'), 'E_EL_90': ('C', 'E_EL_90'),
           'T1': ('D1', 'T1'), 'T2_90': ('D1', 'T2_90'), 'M1_D2a': ('D2a', 'M1'), 'M1_D2b': ('D2b', 'M1'),
           'K1': ('E', 'K1'), 'K1_task': ('E', 'K1_task'), 'K2': ('E', 'K2'), 'F2': ('F', 'F2'), 'F3': ('F', 'F3'),
           'S1': ('S', 'S1'), 'M2': ('D2q', 'M1')}
    for key, (tag, k) in src.items():
        d = (exps.get(tag) or {}).get('diffs', {}).get(k)
        if d is not None:
            out[key] = d
    for key, tag in (('G1', 'C'), ('F1', 'F')):
        v = (exps.get(tag) or {}).get('points', {}).get(key)
        if v is not None:
            out[key] = v
    return out


def check_table(spec, exps, ck):
    comp = checkable(exps)
    ck.lines.append(f'  Table 1 ({TABLE_JSON.name}) against the computed values:')
    for i, row in enumerate(spec['rows'], 1):
        name = f'row {i} ({row["rule"][:34]}...)'
        for field, keys in (('estimate', row.get('check') or []), ('outcome', row.get('check_outcome') or [])):
            text = row[field]
            if keys and text.strip().lower() == 'pending':
                ready = [k for k in keys if k in comp and k not in POINT_KEYS]
                if ready:
                    ck.lines.append(f'    {name} is pending; computed: ' + '; '.join(
                        f'{k} {_fmt(comp[k].val, True)} [{_fmt(comp[k].lo)}, {_fmt(comp[k].hi)}]' for k in ready))
                continue
            found = _estimates(text)
            j = 0
            for k in keys:
                if k not in comp:
                    ck.lines.append(f'    {name} {k}: no computed value (run not available): not checked')
                    continue
                if k in POINT_KEYS:
                    m = re.search(NUM, text)
                    ck.same(f'{name} {k}', comp[k], m.group(0).replace(MINUS, '-'), 100, 2) if m else ck.missing(
                        f'{name} {k}')
                    continue
                if j >= len(found):
                    ck.missing(f'{name} {k} (no "[lo, hi]" left in the {field} cell)')
                    continue
                pt, lo, hi = (None if x is None else x.replace(MINUS, '-') for x in found[j])
                j += 1
                if pt is not None:
                    ck.same(f'{name} {k} point', comp[k].raw[0], pt, 100, 2)
                ck.same(f'{name} {k} lo', comp[k].raw[1], lo, 100, 2)
                ck.same(f'{name} {k} hi', comp[k].raw[2], hi, 100, 2)


def fig_table(spec, out_dir):
    W = W_IN * 72
    fs, lh = 7.6, 7.6 * 1.30
    pad_x, pad_y = 4.0, 3.6
    fracs = spec.get('widths', [0.15, 0.42, 0.27, 0.16])
    cols = spec['columns']
    xs = [W * sum(fracs[:i]) for i in range(len(fracs))]
    ws = [W * f for f in fracs]
    head = [_wrap_pts(c, ws[i] - 2 * pad_x, fs, 'bold') for i, c in enumerate(cols)]
    body = []
    prev = None
    for row in spec['rows']:
        first = row['experiment'] != prev
        prev = row['experiment']
        exp_lines = ([(l, 'bold', INK, 'normal') for l in _wrap_pts(row['experiment'], ws[0] - 2 * pad_x, fs, 'bold')]
                     + [(l, 'normal', MUTED, 'normal') for l in _wrap_pts(row.get('prereg', ''), ws[0] - 2 * pad_x,
                                                                           fs - 0.6)] if first else [])
        pend = row['estimate'].strip().lower() == 'pending'
        # the verdict (before any ';') is styled; a qualifier after it is set quietly on the lines below
        oc = row['outcome'].strip()
        cut = min([i for i in (oc.find(';'), oc.find(':')) if i >= 0], default=-1)
        verdict, qual = (oc, '') if cut < 0 else (oc[:cut].strip(), oc[cut + 1:].strip())
        ocl = verdict.lower()
        positive = ocl in ('met', 'passed')
        o_color = MUTED if ocl == 'pending' else (COLORS['legible'] if positive else INK)
        o_style = 'italic' if ocl == 'pending' else 'normal'
        o_weight = 'bold' if positive or ocl == 'not met' else 'normal'
        cells = [exp_lines,
                 [(l, 'normal', INK, 'normal') for l in _wrap_pts(_display(row['rule']), ws[1] - 2 * pad_x, fs)],
                 [(l, 'normal', MUTED if pend else INK, 'italic' if pend else 'normal')
                  for l in _wrap_pts(_display(row['estimate']), ws[2] - 2 * pad_x, fs)],
                 [(l, o_weight, o_color, o_style) for l in _wrap_pts(_display(verdict), ws[3] - 2 * pad_x, fs, o_weight)]
                 + [(l, 'normal', INK2, 'normal') for l in (_wrap_pts(_display(qual), ws[3] - 2 * pad_x, fs)
                                                            if qual else [])]]
        body.append((first, cells))
    head_h = max(len(h) for h in head) * lh + 2 * pad_y
    row_h = [max(len(c) for c in cells) * lh + 2 * pad_y for _, cells in body]
    note = _wrap_pts(spec.get('note', ''), W - 2 * pad_x, fs - 0.8) if spec.get('note') else []
    note_h = len(note) * (fs - 0.8) * 1.3 + (pad_y * 2 if note else 0)
    H = head_h + sum(row_h) + note_h + 4
    fig = plt.figure(figsize=(W_IN, H / 72))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis('off')

    def put(x, y, lines):
        for text, weight, color, style in lines:
            ax.text(x, y, text, ha='left', va='top', fontsize=fs, fontweight=weight, color=color, style=style)
            y -= lh

    y = H - 2
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    for i, h in enumerate(head):
        put(xs[i] + pad_x, y - pad_y, [(l, 'bold', INK, 'normal') for l in h])
    y -= head_h
    ax.plot([0, W], [y, y], color=INK2, lw=0.6)
    for (first, cells), h in zip(body, row_h):
        if first and y < H - 2 - head_h - 0.1:
            ax.plot([0, W], [y, y], color=RULE_LIGHT, lw=0.6)
        for i, cell in enumerate(cells):
            yy = y - pad_y
            for text, weight, color, style in cell:
                size = fs - 0.6 if (i == 0 and color == MUTED) else fs
                ax.text(xs[i] + pad_x, yy, text, ha='left', va='top', fontsize=size, fontweight=weight, color=color,
                        style=style)
                yy -= lh
        y -= h
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    yy = y - pad_y
    for line in note:
        ax.text(pad_x, yy, line, ha='left', va='top', fontsize=fs - 0.8, color=MUTED)
        yy -= (fs - 0.8) * 1.3
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'table_rules.{ext}', dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------- figure 1: design
def _call_lines(tc, width):
    """One tool call of the history as one or more short monospace lines."""
    fn, a = tc['function_name'], tc.get('arguments') or {}
    if fn == 'read_file':
        arg = str(a.get('filepath'))
        tail = f"lines {a.get('start_line')}–{a.get('end_line')}" if a.get('start_line') else ''
    elif fn in ('write_file', 'edit_file'):
        arg, tail = str(a.get('filepath')), ''
    elif fn == 'run_command':
        cmd = str(a.get('command', ''))
        arg, tail = (cmd[:width - 3] + '…' if len(cmd) > width - 2 else cmd), ''
    else:
        arg, tail = '', ''
    one = f'{fn} {arg}'.strip()
    lines = [one] if len(one) <= width else [fn] + _wrap('  ' + arg, width)
    return lines + (['  ' + tail] if tail else [])


def pick_example(states_path, key=None):
    """One real state (default: the first in the file)."""
    for line in open(states_path, encoding='utf-8'):
        s = json.loads(line)
        k = (s['task'], s['run'], s.get('fork', 0))
        if key is None or k == key:
            return s
    raise SystemExit(f'state {key} not found')


def _wrap(text, width, indent='  '):
    out = []
    for para in text.split('\n'):
        lead = len(para) - len(para.lstrip(' '))
        out += textwrap.wrap(para.lstrip(' '), width, initial_indent=' ' * lead,
                             subsequent_indent=' ' * lead + indent, break_long_words=False,
                             break_on_hyphens=False) or ['']
    return out


def example_formats(s):
    """The bare-name list as the tool prints it (arm P's result) and arm E's entries, from the state, cut to two.

    Display only: entries after the second are counted, the "node" key (already in the call) is left out, and
    lines are broken to fit; every value shown is read from the state's own arm texts.
    """
    p_resp = s['arms']['P']['response']
    names = p_resp['neighbors']
    bare = (f'get_code_neighbors(\n  node="{p_resp["node"]}")\nreturned:\n'
            '{"status": "ok",\n "neighbors": [\n'
            + ''.join(f'   "{n}",\n' for n in names[:2])
            + f'   … {len(names) - 2} more],\n "count": {p_resp["count"]}}}')
    head, body = s['arms']['E']['user_text'].split('returned:\n', 1)
    e_resp = json.loads(body)
    items = e_resp['neighbors']
    ents = []
    for e in items[:2]:
        ents.append(' {"name": "%s",\n  "file": "%s", "lines": "%s",\n  "def": "%s"},'
                    % (e['name'], e['file'], e['lines'], e['def']))
    # same text, broken onto lines for display: after the first sentence and before node=
    head = head.strip().replace('. get_code_neighbors(', '.\nget_code_neighbors(\n  ')
    legible = (head + ' returned:\n{"status": "ok", "neighbors": [\n' + '\n'.join(ents)
               + f'\n … {len(items) - 2} more], "count": {e_resp["count"]}}}')
    return bare, legible


def fig_design(s, n_states, n_complete, n_arms, seeds, out_dir):
    W_IN, H_IN = 7.0, 5.0
    U = W_IN * 72 / 100                  # points per x unit; y units are the same size
    fig = plt.figure(figsize=(W_IN, H_IN))
    ax = fig.add_axes([0, 0, 1, 1])
    ytop = H_IN * 72 / U
    ax.set_xlim(0, 100)
    ax.set_ylim(0, ytop)
    ax.axis('off')
    PAD = 1.4

    def box(x0, y0, w, h, ec=MUTED, fc='white', lw=0.8):
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle='round,pad=0,rounding_size=1.2', fc=fc, ec=ec,
                                    lw=lw, zorder=1))

    def lines_at(x, y, lines, size, mono=False, color=INK, weight='normal', style='normal', gap=1.32):
        for ln in lines:
            ax.text(x, y, ln, ha='left', va='top', fontsize=size, family=MONO if mono else None, color=color,
                    fontweight=weight, style=style)
            y -= size * gap / U
        return y

    def chars(w_units, size, mono):
        return int((w_units - 2 * PAD) * U / (size * (0.602 if mono else 0.53)))

    def arrow(x0, y0, x1, y1, color=INK2):
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=1.0, shrinkA=0, shrinkB=0))

    T, TS, BS, MS = 8.6, 8.6, 7.4, 6.6   # title, title size, body size, mono size
    top, h = ytop - 1.0, 34.0
    cols = [(1.0, 28.0), (32.0, 30.0), (65.0, 15.5), (83.5, 15.5)]

    # 1. a real run, paused right after a tool result that shows file content
    x, w = cols[0]
    box(x, top - h, w, h)
    y = lines_at(x + PAD, top - PAD, ['1  A real run, paused'], TS, weight='bold') - 1.0
    y = lines_at(x + PAD, y, ['issue text (task prompt)'], BS, color=INK2) - 0.9
    calls = [tc for st in s['steps'] if st.get('source') == 'agent' for tc in (st.get('tool_calls') or [])]
    calls = calls[:s['tool_calls_before_fork']]
    width = chars(w, MS, True)
    show = list(range(len(calls)))
    if len(calls) > 4:
        show = [0, 1, None, len(calls) - 1]
    for i in show:
        if i is None:
            y = lines_at(x + PAD, y, [f'… {len(calls) - 3} more calls'], MS, mono=True, color=MUTED) - 0.7
            continue
        last = i == len(calls) - 1
        y = lines_at(x + PAD, y, _call_lines(calls[i], width), MS, mono=True, color=INK if last else INK2,
                     weight='bold' if last else 'normal') - 0.7
    lines_at(x + PAD, top - h + PAD + BS * 1.3 / U, ['the file is open: pause here'], BS, color=INK,
             style='italic')

    # 2. the one piece that differs per arm
    x, w = cols[1]
    box(x, top - h, w, h, ec=COLORS['legible'], fc='#f3f7fb')
    y = lines_at(x + PAD, top - PAD, ['2  One piece added, per arm'], TS, weight='bold') - 1.0
    arms_txt = [('A', 'nothing added'), ('P', 'the list as a get_code_neighbors result'),
                ('H', 'the list as a harness note'), ('D', 'the list in an instruction to read them'),
                ('E', "H's note; each entry with file, lines and first line"),
                ('R$_D$, R$_E$', None), ('', 'D and E with a degree-preserving rewired list')]
    cw = 4.2
    for code, t in arms_txt:
        legible = code == 'E'
        if t is None:   # a long code on its own line, its description on the next
            y = lines_at(x + PAD, y, [code], BS, weight='bold')
            continue
        lines_at(x + PAD, y, [code], BS, weight='bold', color=COLORS['legible'] if legible else INK)
        y = lines_at(x + PAD + cw, y, _wrap(t, chars(w - cw, BS, False), indent=''), BS,
                     color=COLORS['legible'] if legible else INK) - 0.5

    # 3. the next call
    x, w = cols[2]
    box(x, top - h, w, h)
    y = lines_at(x + PAD, top - PAD, ['3  Next call'], TS, weight='bold') - 1.0
    cw3 = chars(w, BS, False)
    y = lines_at(x + PAD, y, _wrap('The model makes one call; no tool runs.', cw3, ''), BS) - 1.6
    words = {10: 'ten'}
    lines_at(x + PAD, y, _wrap(f'{n_states} paused states, {len(seeds)} seeds per arm ({n_complete} complete in '
                               f'all {words.get(n_arms, n_arms)} arms)', cw3, ''), BS, color=INK2)

    # 4. the score
    x, w = cols[3]
    box(x, top - h, w, h)
    y = lines_at(x + PAD, top - PAD, ['4  Scored'], TS, weight='bold') - 1.0
    y = lines_at(x + PAD, y, _wrap('Does it read or edit the lines of a listed neighbor in a file not yet '
                                   'opened?', cw3, ''), BS) - 1.6
    lines_at(x + PAD, y, _wrap('Compared with arm A, the no-list base rate.', cw3, ''), BS, color=INK2)

    ymid = top - h / 2
    for (xa, wa), (xb, _) in zip(cols, cols[1:]):
        arrow(xa + wa + 0.4, ymid, xb - 0.4, ymid)

    # the two list formats, side by side, fed from box 2
    bare, legible = example_formats(s)
    by, bh = 1.0, top - h - 6.0
    left, right = (1.0, 43.0), (46.0, 53.0)
    box(left[0], by, left[1], bh, ec=COLORS['bare'])
    box(right[0], by, right[1], bh, ec=COLORS['legible'], lw=1.1)
    y = lines_at(left[0] + PAD, by + bh - PAD, ['bare names (P, H, D)'], T, weight='bold') - 0.9
    y = lines_at(left[0] + PAD, y, _wrap(bare, chars(left[1], MS, True)), MS, mono=True)
    lines_at(left[0] + PAD, by + PAD + 2 * BS * 1.32 / U,
             _wrap('P returns this as the tool result; H and D carry the same JSON in a note or an instruction.',
                   chars(left[1], BS, False), ''), BS, color=INK2)
    y = lines_at(right[0] + PAD, by + bh - PAD, ['names + file + lines + first line (E)'], T, weight='bold',
                 color=COLORS['legible']) - 0.9
    lines_at(right[0] + PAD, y, _wrap(legible, chars(right[1], MS, True), indent='       '), MS, mono=True)

    yc = by + bh + 2.6
    xc = cols[1][0] + cols[1][1] / 2
    ax.plot([xc, xc], [top - h, yc], color=COLORS['legible'], lw=0.9)
    xl, xr = left[0] + left[1] / 2, right[0] + right[1] / 2
    ax.plot([xl, xr], [yc, yc], color=COLORS['legible'], lw=0.9)
    for xx in (xl, xr):
        arrow(xx, yc, xx, by + bh + 0.2, color=COLORS['legible'])
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_design.{ext}', dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', nargs=2, action='append', default=[], metavar=('TAG', 'RUN_DIR'),
                    help=f'override the run directory of one later run; TAG is one of {", ".join(RUN_DIRS)}')
    ap.add_argument('--table', default=str(TABLE_JSON), help='the data file of Table 1')
    ap.add_argument('--example', default=None, help='state for fig_design as task,run,fork (default: first state)')
    ap.add_argument('--out', default=str(FIG))
    ap.add_argument('--verbose', action='store_true', help='list every checked value, not only the summary')
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dirs = dict(RUN_DIRS)
    for tag, d in args.run:
        if tag not in run_dirs:
            ap.error(f'--run: unknown tag {tag}; use one of {", ".join(RUN_DIRS)}')
        run_dirs[tag] = Path(d)

    exps = {'B': exp_b()}
    for tag, d in run_dirs.items():
        rows_path = Path(d) / ROWS_FILE[tag]
        if not rows_path.exists():
            print(f'not drawn: {EXP_NAME[tag]} (no {rows_path.relative_to(ROOT).as_posix() if rows_path.is_relative_to(ROOT) else rows_path} yet)')
            continue
        e = LOADERS[tag](d)
        exps[tag] = e
        tag_ex = ' [EXPLORATORY: fewer than 200 complete states]' if e['n_complete'] < MIN_COMPLETE else ''
        print(f'{EXP_NAME[tag]}: {e["n_rows"]} replays, {e["n_complete"]} complete states{tag_ex}')

    ck = Checks()
    check_b(exps['B'], ck)
    for tag in RUN_DIRS:
        if tag in exps:
            check_later(tag, exps[tag], ck)
    spec = json.load(open(args.table, encoding='utf-8'))
    check_table(spec, exps, ck)
    print('Checks (plotted values against the registered outputs):')
    n_ok = sum(1 for l in ck.lines if l.endswith(' match'))
    print('\n'.join(l for l in ck.lines if args.verbose or not l.endswith(' match')))
    print(f'  {n_ok} values match their registered output' + ('' if args.verbose else ' (--verbose lists each)'))
    if ck.bad:
        raise SystemExit(f'check failed for {ck.bad}; no figure saved')
    print('  all checks passed')

    fig_results(exps['B']['values'], out_dir)
    fig_extensions(exps, out_dir)
    fig_table(spec, out_dir)
    key = None
    if args.example:
        t, r, f = args.example.split(',')
        key = (t, int(r) if r.isdigit() else r, int(f))
    fig_design(pick_example(B_STATES, key), *exps['B']['info'], out_dir)
    print(f'wrote fig_design, fig_results, fig_extensions, table_rules (.png and .svg) in {out_dir}')


if __name__ == '__main__':
    main()
