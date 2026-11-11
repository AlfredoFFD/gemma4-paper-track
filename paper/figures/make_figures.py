"""Regenerate Figures 1 to 3, the appendix figure and Tables 1 and 2 from the raw replay logs and the stored reports.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py [--out <dir>]
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py --run C <run_dir> --run E <run_dir>

Writes, next to this script (or into --out):
  fig_design.png/.svg      Figure 1, the method: one paused step, the one message that differs, the outcome
  table_samples.png/.svg   Table 1, what each experiment built, analyzed and left out, from samples_table.json
  fig_results.png/.svg     Figure 2, opens a neighbor's file against reads a neighbor's code, by what the list prints:
                           the first experiment and the parts of the address (pre-registrations 02 to 04, 12 and, once
                           it has run, 13)
  fig_extensions.png/.svg  Figure 3, addresses against bare names in every registered variation (a forest)
  table_rules.png/.svg     Table 2, the registered rules the argument rests on (a digest), from rules_main.json
  fig_appendix.png/.svg    appendix: the parts of an entry and a false entry; five-call replays
(Figures 4 and 5 are make_fig_law.py and make_fig_runs.py.)

Every plotted number is computed here from the raw per-replay rows with the registered code path of its experiment:
  B    the definitions of analysis/rederive_s5.py (hit, opens_file, invalid_kind; it imports the registered scorer),
       loaded without running it (load_rederive_defs), on the pooled hosted runs v5, v6, v8;
  C    analysis/analyze_c.py (its exclusions, complete-state rule and state order; scorer from gates_c / fork_states);
  D1, D2a, D2b  analysis/analyze_d.py (load_run, tables, imported);
  E    analysis/analyze_k.py (score, first_call_failure, imported; its usable-replay and complete-state rules);
  F    analysis/analyze_w.py (its arms, seeds and complete-state rule; any_true and failure from gates_c).
  S    analysis/analyze_g.py, part "one step" (arms H and E on the newest harness wheels; pre-registration 08);
  D2q  analysis/analyze_d.py as for D2a and D2b, on the run with a model of another family (pre-registration 10);
  P    analysis/analyze_12.py (a file without lines, pre-registration 12; its functions imported, its main() repeated
       without the printing), with the reference arms of the run of pre-registration 04 (the directory of C);
  X    analysis/analyze_13.py in the same way (the address written as a search hit, pre-registration 13).
Rates use the frozen bootstrap analyze_forks.boot_ci fed per-state lists in the order the registered script feeds it
(which fixes the interval); differences use analyze_forks.diff_ci. Before anything is saved, every plotted value of a
run whose registered output file exists is checked against the numbers printed there, and any mismatch stops the
script. Runs whose directory does not exist yet are skipped with a printed note ("not drawn: ..."), so the script can
be rerun as the runs arrive. A run that exists but has no registered output yet is drawn and reported as UNCHECKED.
The default run directories are in RUN_DIRS; --run TAG RUN_DIR overrides one (the checks still read the registered
output file of that tag).
The intervals clustered by task in Figure 3 are computed here with the same frozen bootstrap and checked against
analysis/results/explore_supplement.txt where that report prints them.

The tables are data files. A table of rules holds one item per registered rule, and no estimate in it stands
unverified. An estimate is typed and then verified, or left out and then built, from the values this script computes
("check": the keys of contrasts) or from lines of stored reports ("report": file, pattern, and "expect", the text the
pattern's groups give); a mismatch or a missing line stops the script, and numbers that nothing supplies are listed.
An outcome is typed, or read from the verdict a stored report prints ("outcome": file, pattern, and "words", which
turn the report's verdict into the table's word). A rule marked "pending": true may wait for its report: until that
file exists both of its cells say "pending", and from then on they are read from it.
  rules_table.json    every registered rule, counted as Appendix A counts them (a row labelled "Gate" there is a gate,
                      every other row is a rule): checked and tallied here, drawn only with --full-table (the paper
                      gives the full list as the markdown table of Appendix A);
  rules_main.json     Table 2, the digest: a flat list of rules in four columns, with no typed estimate;
  samples_table.json  Table 1: every number is a named value that is read from a stored report ("file" and "pattern",
                      or "json" and "field"), worked out from other values, or typed with a "source"; the typed ones
                      are listed.
"""
import argparse
import ast
import collections
import contextlib
import functools
import io
import json
import operator
import re
import statistics
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
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
H_STATES = ANALYSIS / 'fork_states_h' / 'states.jsonl'      # optional: the search-hit condition (pre-registration 13)
TABLE_JSON = FIG / 'rules_table.json'                       # every registered rule: checked and tallied
DIGEST_JSON = FIG / 'rules_main.json'                       # Table 2, the digest of the rules
SAMPLES_JSON = FIG / 'samples_table.json'                   # Table 1, the samples
SUPPLEMENT_TXT = RES / 'explore_supplement.txt'             # the intervals clustered by task

# Later runs: default run directory (the directory the registered script is given), the raw rows file inside it,
# and the registered output files the plotted numbers are checked against.
RUN_DIRS = {'C': RES / 'c' / 'forks', 'D1': RES / 'd1' / 'forks', 'D2a': RES / 'd2_26b' / 'forks',
            'D2b': RES / 'd2_e4b' / 'forks', 'E': RES / 'k' / 'forks', 'F': RES / 'w' / 'forks',
            'S': RES / 'g_onestep' / 'forks', 'D2q': RES / 'qwen' / 'forks', 'P': RES / '12' / 'forks',
            'X': RES / '13' / 'forks'}
ROWS_FILE = {'C': 'results.jsonl', 'D1': 'results.jsonl', 'D2a': 'results.jsonl', 'D2b': 'results.jsonl',
             'E': 'results_k.jsonl', 'F': 'results.jsonl', 'S': 'results.jsonl', 'D2q': 'results.jsonl',
             'P': 'results.jsonl', 'X': 'results.jsonl'}
OUTPUTS = {'C': [RES / 'c' / 'analyze_c.txt', RES / 'c' / 'gates_c.txt'],
           'D1': [RES / 'd1' / 'analyze_d1.txt'],
           'D2a': [RES / 'd2_26b' / 'analyze_d2_26b.txt'],
           'D2b': [RES / 'd2_e4b' / 'analyze_d2_e4b.txt'],
           'E': [RES / 'k' / 'analyze_k.txt', RES / 'k' / 'analyze_k_extra.txt', RES / 'k' / 'explore_k.txt'],
           'F': [RES / 'w' / 'analyze_w.txt'],
           'S': [RES / 'g' / 'analyze_g.txt'],
           'D2q': [RES / 'qwen' / 'analyze_d2_qwen.txt'],
           'P': [RES / '12' / 'analyze_12.txt'],
           'X': [RES / '13' / 'analyze_13.txt']}
REFERENCE = {'P': 'C', 'X': 'C'}     # runs whose reference conditions come from another run's directory

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
    'none': '#c6c6c6',      # no list
    'bare': '#8e8e8e',      # lists without line numbers
    'legible': '#1f6fb4',   # lists with line numbers (the one accent)
    'rewired': '#c47a3d',   # the rewired list and the false entry
}
TINT = {'none': '#e6e6e6', 'bare': '#d2d2d2', 'legible': '#a9c8e6', 'rewired': '#e6c3a5'}

# The conditions of the first experiment whose rates are computed, with the outcome that is registered for each:
# 's1' any unopened true neighbor touched; 'rew' any rewired entry touched.
ARM_SPECS = [dict(arm='A', field='s1'), dict(arm='P', field='s1'), dict(arm='H', field='s1'),
             dict(arm='D', field='s1'), dict(arm='E', field='s1'), dict(arm='RD', field='rew'),
             dict(arm='RE', field='rew')]

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
import analyze_12 as A12  # noqa: E402
import analyze_13 as A13  # noqa: E402
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


def by_task(table):
    """{state: [0/1, ...]} regrouped by task (the first field of a state key), for the task-clustered interval."""
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return out


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
                by_task={'B3': d_pct(by_task(t[('E', 's1')]), by_task(t[('H', 's1')]))},
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
    return dict(n_rows=len(rows), n_complete=len(complete), n_states=len(states), rates=rates, diffs=diffs, arms=arms,
                seeds=seeds, points=points,
                by_task={'G2': d_pct(by_task(T['E']), by_task(T['H']))} if {'E', 'H'} <= set(arms) else {})


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
        tasks = {'T1': d_pct(by_task(T['PE']), by_task(T['P']))}
    else:
        diffs = {'M1': d_pct(T['E'], T['H'])}
        tasks = {'M1': d_pct(by_task(T['E']), by_task(T['H']))}
    return dict(n_rows=len(rows), n_complete=len(complete), n_states=len(states), rates=rates, diffs=diffs,
                by_task=tasks)


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
                diffs={'S1': d_pct(T['E'], T['H'])}, by_task={'S1': d_pct(by_task(T['E']), by_task(T['H']))})


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
    # F2 as analyze_w.py scores it: the first call is a read_file with a misspelled line-bound name (its `mangled`)
    mang = {a: collections.defaultdict(list) for a in AW.ARMS}
    for k in complete:
        for a in AW.ARMS:
            for s in AW.SEEDS:
                mang[a][k].append(int(AW.mangled(usable[k][(a, s)]['next_call'])))
    rates.update({f'mangled_{a}': r_pct(mang[a]) for a in AW.ARMS})
    # F1: analyze_w.fidelity on the original-rendering fidelity file (its report line is swallowed)
    with contextlib.redirect_stdout(io.StringIO()):
        f1 = AW.fidelity(Path(run_dir) / 'fidelity_w.jsonl', 'Aw')
    return dict(n_rows=len(rows), n_complete=len(complete), n_states=len(states), rates=rates, points={'F1': f1},
                diffs={'F3': d_pct(hit['Ew'], hit['Hw']), 'F2': d_pct(mang['A'], mang['Aw'])},
                by_task={'F3': d_pct(by_task(hit['Ew']), by_task(hit['Hw']))})


def _one_condition(mod, run_dir, ref_dir, new, complete_arms, arms):
    """What analyze_12.py and analyze_13.py share, as their main() does it and minus the printing: the usable rows of
    the new condition (its run) and of the reference conditions (the run of pre-registration 04), the complete
    states in sorted order, and per state the two outcomes and the first reads of a listed neighbor's file."""
    states = mod.load_states(D_STATES)
    fresh, n_new, _f = mod.usable_rows(Path(run_dir) / 'results.jsonl', (new,))
    ref, _n, _f = mod.usable_rows(Path(ref_dir) / 'results.jsonl', mod.REF)

    def rows_of(key, arm):
        src = fresh if arm == new else ref
        return [src[key][(arm, s)] for s in mod.SEEDS] if all((arm, s) in src.get(key, {}) for s in mod.SEEDS) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in complete_arms))
    reads = {a: {} for a in arms}       # the next call reads a listed neighbor (the registered outcome of 02 to 05)
    opens = {a: {} for a in arms}       # the next call opens a listed neighbor's file
    ranged = {a: {} for a in arms}      # among those opens, the read asks past line 1 (per state: 0/1 per read)
    first = {a: collections.Counter() for a in arms}
    for k in complete:
        st = states[k]
        for a in arms:
            rs = rows_of(k, a)
            if rs is None:
                continue
            reads[a][k] = [int(bool(mod.any_true(st, r['next_call']))) for r in rs]
            opens[a][k] = [int(bool(mod.opens_listed_file(st, r['next_call']))) for r in rs]
            for r in rs:
                call = r['next_call']
                if call.get('function_name') == 'read_file' and mod.opens_listed_file(st, call):
                    is_ranged, _covers, _on_first = mod.read_stats(st, call)
                    first[a]['reads'] += 1
                    first[a]['ranged'] += int(is_ranged)
                    ranged[a].setdefault(k, []).append(int(is_ranged))
    rates = {(a, f): r_pct(t[a]) for a in arms for f, t in (('reads', reads), ('opens', opens))}
    return dict(n_rows=n_new[new], n_complete=len(complete), n_states=len(states), rates=rates, first=first,
                n_arm={a: len(reads[a]) for a in arms}), reads, opens, ranged


def exp_12(run_dir, ref_dir):
    """analyze_12.py: a file without lines (condition EPATH) beside bare names (H), file and lines (EL) and addresses
    (E, on the complete states where it is usable). Rules P1 and P2; the counts of P3."""
    new = A12.NEW
    e, reads, opens, _ranged = _one_condition(A12, run_dir, ref_dir, new, A12.RULE_ARMS, ['H', new, 'EL', 'E'])
    e['diffs'] = {'P1': d_pct(reads['EL'], reads[new]), 'P2': d_pct(opens[new], opens['H'])}
    return e


def exp_13(run_dir, ref_dir, new='EG'):
    """analyze_13.py: the address written as a search hit (condition EG) beside addresses as JSON (E); H and EL on the
    complete states where they are usable. Rules X1 and X2."""
    e, reads, _opens, ranged = _one_condition(A13, run_dir, ref_dir, new, ('E', new), ['H', 'EL', 'E', new])
    e['diffs'] = {'X1': d_pct(reads[new], reads['E']), 'X2': d_pct(ranged[new], ranged['E'])}
    e['new'] = new
    return e


LOADERS = {'C': exp_c, 'D1': lambda d: exp_d(d, 'd1'), 'D2a': lambda d: exp_d(d, 'd2'),
           'D2b': lambda d: exp_d(d, 'd2'), 'E': exp_e, 'F': exp_f, 'S': exp_s, 'D2q': lambda d: exp_d(d, 'd2'),
           'P': exp_12, 'X': exp_13}        # P and X also take the directory of their reference run
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
    # F2 (misspelled line-bound names in the first call) and F1 (prompt size, original rendering)
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


def check_parts(tag, e, path, ck):
    """Pre-registrations 12 (tag P) and 13 (tag X): the stored output of analyze_12.py or analyze_13.py."""
    txt = path.read_text(encoding='utf-8')
    m = re.search(r'complete states \(.*?\): (\d+) of (\d+)', txt)
    if m:
        ck.same(f'{tag} complete states', e['n_complete'], m.group(1), 1, None)
        ck.same(f'{tag} states', e['n_states'], m.group(2), 1, None)
    else:
        ck.missing(f'{tag} complete states')
    rate_pat = re.compile(r"^  arm (\w+)\s+reads a listed neighbor: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+); "
                          r"opens a listed neighbor's file: ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+)", re.M)
    printed = {m.group(1): m.groups()[1:] for m in rate_pat.finditer(txt)}
    for (arm, field), v in e['rates'].items():
        if v is None:
            continue
        p = printed.get(arm)
        if p is None:
            ck.missing(f'{tag} {arm}')
            continue
        off = 0 if field == 'reads' else 5
        ck.triple(f'{tag} {arm} {field}', v.raw, p[off:off + 3])
        ck.same(f'{tag} {arm} {field} hits', v.k, p[off + 3], 1, None)
        ck.same(f'{tag} {arm} {field} n', v.n, p[off + 4], 1, None)
    num = r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]'
    rules = {'P1': r'^  P1, .*?: ' + num, 'P2': r'^  P2, .*?: ' + num, 'X1': r'^  X1, .*?: ' + num,
             'X2': r'^  X2, .*; \w+ - E ' + num}
    for k, d in e['diffs'].items():
        m = re.search(rules[k], txt, re.M)
        if d is None and m is None:
            continue
        ck.triple(f'{tag} {k}', d.raw, m.groups()) if (d is not None and m) else ck.missing(f'{tag} {k}')
    for arm, c in e['first'].items():      # first reads of a listed neighbor's file, and how many ask past line 1
        m = re.search(rf"^  arm {arm}\s+first reads of a listed neighbor's file: (\d+); ask past line 1 (\d+)", txt,
                      re.M)
        if m is None:
            ck.missing(f'{tag} {arm} first reads')
            continue
        ck.same(f'{tag} {arm} first reads', c['reads'], m.group(1), 1, None)
        ck.same(f'{tag} {arm} first reads past line 1', c['ranged'], m.group(2), 1, None)


def check_by_task(exps, ck):
    """The task-clustered intervals of Figure 3 against explore_supplement.txt, where that report prints them."""
    ck.lines.append('  intervals clustered by task (explore_supplement.txt):')
    if not SUPPLEMENT_TXT.exists():
        ck.lines.append(f'    no {SUPPLEMENT_TXT.relative_to(ROOT).as_posix()}: UNCHECKED')
        return
    txt = SUPPLEMENT_TXT.read_text(encoding='utf-8')
    num = r'\n\s+95% by state:.*\n\s+95% by task:\s+([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]'
    where = {('B', 'B3'): ('', 'B3 encoding: E minus H'), ('C', 'G2'): ('', 'Gate G2: E minus H'),
             ('D1', 'T1'): ('', 'T1: PE minus P'), ('F', 'F3'): ('', 'F3: Ew minus Hw'),
             ('D2a', 'M1'): ('second model Gemma 4 26B-A4B', 'M1: E minus H'),
             ('D2b', 'M1'): ('second model Gemma 4 E4B', 'M1: E minus H')}
    for tag, key, _a, _b, label in FOREST:
        d = (exps.get(tag) or {}).get('by_task', {}).get(key)
        if d is None:
            continue
        section, head = where.get((tag, key), (None, None))
        part = txt.split(section, 1)[1] if section and section in txt else txt
        m = re.search(re.escape(head) + num, part) if head else None
        if m:
            ck.triple(f'{label}, by task', d.raw, m.groups())
        else:
            ck.lines.append(f'    {label}, by task: computed {_fmt(d.val, True)} [{_fmt(d.lo)}, {_fmt(d.hi)}]; the '
                            'report does not print it: UNCHECKED')


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
    if tag in ('P', 'X'):
        check_parts(tag, e, paths[0], ck)
        return
    (check_f if tag == 'F' else lambda e_, p_, c_: check_d(tag, e_, p_, c_))(e, paths[0], ck)


# ---------------------------------------------------------------- drawing helpers
def _fmt(v, sign=False, dec=2):
    s = f'{v:+.{dec}f}' if sign else f'{v:.{dec}f}'
    return s.replace('-', MINUS)


def _bar(ax, y, v, color, h, show_ci=False, ci_below=False, size=8.5, dec=2, extra=None, unit='%'):
    """A rate as a bar with its 95% interval; the value is printed with its unit so that it reads as a rate."""
    val, lo, hi = v[:3]
    ax.barh(y, val, height=h, color=color, edgecolor='none', zorder=2)
    ax.errorbar(val, y, xerr=[[val - lo], [hi - val]], fmt='none', ecolor=INK, elinewidth=0.8,
                capsize=2.2, capthick=0.8, zorder=3)
    if ci_below:   # value on top, interval under it (narrow panels)
        ax.text(hi, y, f' {_fmt(val, dec=dec)}{unit}', va='bottom', ha='left', fontsize=size, color=INK, zorder=4)
        ax.text(hi, y, f'  [{_fmt(lo, dec=dec)}, {_fmt(hi, dec=dec)}]', va='top', ha='left', fontsize=size - 1.5,
                color=MUTED, zorder=4)
        return
    t = ax.text(hi, y, f' {_fmt(val, dec=dec)}{unit}', va='center', ha='left', fontsize=size, color=INK, zorder=4)
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


# ---------------------------------------------------------------- Figure 2: file opened against code read
# (condition, label, the list gives line numbers). First block: the first experiment (pre-registrations 02 and 03).
FIRST_ROWS = [('A', 'no list', False), ('P', 'bare names, as the tool\'s own result', False),
              ('H', 'bare names, as a note', False), ('D', 'names with an instruction', False),
              ('E', 'addresses', True)]
# Second block: the parts of the address (pre-registrations 04 and 12), every list a note. The condition with file,
# lines and definition line carries one name in both blocks: addresses.
PART_ROWS = [('H', 'bare names', False), ('EPATH', 'file only', False), ('EL', 'file and lines', True),
             ('E', 'addresses', True)]


def result_blocks(exps):
    """[(block title, [(label, opens-file rate, reads-code rate, has line numbers[, a remark under the label])])] for
    Figure 2."""
    b = exps['B']
    blocks = [(f'First experiment, {b["n_complete"]:,} paused steps',
               [(label, b['values'][(arm, 'opened')], b['values'][(arm, 's1')], lines)
                for arm, label, lines in FIRST_ROWS])]
    p = exps.get('P')
    if p is None:
        print('  not drawn: Figure 2, the block of the parts of the address: no run of pre-registration 12 yet')
        return blocks
    rows = []
    for arm, label, lines in PART_ROWS:
        if p['n_arm'][arm] != p['n_complete']:     # a condition that is usable on fewer of the block's steps
            label += f' ({p["n_arm"][arm]:,} steps)'
        rows.append((label, p['rates'][(arm, 'opens')], p['rates'][(arm, 'reads')], lines))
    x = exps.get('X')
    if x is not None:       # the same addresses written as search hits, on the steps complete in its own run
        new, label = x['new'], 'search hits'
        if x['n_arm'][new] != p['n_complete']:
            label += f' ({x["n_arm"][new]:,} steps)'
        # its registered comparison is with addresses on the same steps, which are not the row above's
        paired = f'addresses on these steps: {_fmt(x["rates"][("E", "reads")].val)}%'
        rows.append((label, x['rates'][(new, 'opens')], x['rates'][(new, 'reads')], True, paired))
    blocks.append((f'Parts of the address, {p["n_complete"]:,} paused steps', rows))
    return blocks


def fig_results(exps, out_dir):
    """One axis, two blocks. For each way of writing the neighbor list: how often the agent's next call opens a
    listed neighbor's file (tint) and how often it reads the neighbor's code (full color, the registered outcome).
    Blue marks the lists that give line numbers."""
    blocks = result_blocks(exps)
    n_rows = sum(len(rows) for _t, rows in blocks)
    head, pitch = 0.62, 1.0
    height = n_rows * pitch + head * len(blocks)
    fig_h = 0.375 * height + 1.22
    fig, ax = plt.subplots(figsize=(7.0, fig_h))
    left = 0.345
    tr = blended_transform_factory(fig.transFigure, ax.transData)
    xmax, ticks, labels, bold, remarks = 0.0, [], [], [], []
    y = 0.0
    for title, rows in blocks:
        y -= head
        ax.text(0.012, y + 0.36, title, transform=tr, ha='left', va='center', fontsize=8.6, color=INK,
                fontweight='bold')
        for label, opened, read, lines, *remark in rows:
            yc = y - pitch / 2
            g = 'legible' if lines else 'bare'
            _bar(ax, yc + 0.19, opened, TINT[g], 0.36, show_ci=True, size=7.8)
            _bar(ax, yc - 0.19, read, COLORS[g], 0.36, show_ci=True, size=7.8)
            xmax = max(xmax, opened.hi, read.hi)
            ticks.append(yc)
            labels.append(label)
            bold.append(lines)
            remarks.append(remark[0] if remark else None)
            y -= pitch
    ax.set_yticks(ticks, labels, fontsize=8.6)
    for t, b in zip(ax.get_yticklabels(), bold):
        if b:
            t.set_fontweight('bold')
    ax.set_ylim(y - 0.05, 0.0)
    ax.set_xlim(0, _room(xmax, (0.975 - left) * 7.0, 1.2))
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=8.2, length=3)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.set_xlabel('% of replays: the agent\'s next call (whiskers: 95% interval, clustered by paused step)',
                  fontsize=8.2)
    fig.suptitle('Names get the agent to the file. Addresses get it to the code.', x=0.012, y=1 - 0.05 / fig_h,
                 ha='left', va='top', fontsize=10.5, color=INK)
    pair = lambda shade: (Patch(facecolor=shade['bare']), Patch(facecolor=shade['legible']))   # noqa: E731
    fig.legend([pair(TINT), pair(COLORS)], ['opens a neighbor\'s file (at any line)', 'reads a neighbor\'s code'],
               handler_map={tuple: HandlerTuple(ndivide=None, pad=0.25)}, loc='upper left',
               bbox_to_anchor=(0.008, 1 - 0.36 / fig_h), ncol=2, frameon=False, fontsize=7.9, handlelength=2.0,
               handletextpad=0.5, columnspacing=1.5, borderaxespad=0.0)
    fig.text(0.975, 1 - 0.405 / fig_h, 'blue: the list gives line numbers', ha='right', va='top', fontsize=7.9,
             color=COLORS['legible'])
    fig.subplots_adjust(left=left, right=0.975, top=1 - 0.66 / fig_h, bottom=0.50 / fig_h)
    if any(remarks):        # a label with a remark moves up and the remark goes under it, small and grey
        fig.canvas.draw()   # to measure where the tick labels end
        for t, yc, remark in zip(ax.get_yticklabels(), ticks, remarks):
            if not remark:
                continue
            gap = (ax.get_window_extent().x0 - t.get_window_extent().x1) * 72 / fig.dpi
            at = dict(xy=(0, yc), xycoords=ax.get_yaxis_transform(), textcoords='offset points', ha='right',
                      va='baseline')
            ax.annotate(t.get_text(), xytext=(-gap, 1.4), fontsize=t.get_fontsize(), fontweight=t.get_fontweight(),
                        color=t.get_color(), **at)
            ax.annotate(remark, xytext=(-gap, -7.6), fontsize=6.7, color=INK2, **at)
            t.set_visible(False)
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_results.{ext}', dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------- Figure 3 (the forest) and the appendix figure
EXP_NAME = {'B': 'experiment B', 'C': 'experiment C', 'D1': 'experiment D1', 'D2a': 'experiment D2a',
            'D2b': 'experiment D2b', 'E': 'experiment E', 'F': 'experiment F', 'S': 'experiment S (newest wheels)',
            'D2q': 'experiment D2q (another model family)', 'P': 'pre-registration 12 (a file without lines)',
            'X': 'pre-registration 13 (the address as a search hit)'}
# Figure text names runs in words, never by experiment letter
RUN_NAME = {'B': 'hosted run', 'C': 'rented GPU', 'D1': 'tool-channel run', 'D2a': 'second-model run',
            'D2b': 'second-model run', 'E': 'five-call run', 'F': 'rendering run', 'S': 'newest-wheels run',
            'D2q': 'other-family run'}
# Figure 3: (source, contrast key, condition with addresses, condition with bare names, label)
FOREST = [
    ('B', 'B3', 'E', 'H', 'the first experiment'),
    ('C', 'G2', 'E', 'H', 'a second GPU platform'),
    ('D1', 'T1', 'PE', 'P', 'the list as the tool\'s own result'),
    ('F', 'F3', 'Ew', 'Hw', 'tool results rendered as before Sep 30'),
    ('S', 'S1', 'E', 'H', 'the current harness (release of Oct 12)'),
    ('D2a', 'M1', 'E', 'H', 'a smaller model, Gemma 4 26B-A4B'),
    ('D2b', 'M1', 'E', 'H', 'a smaller model, Gemma 4 E4B'),
    ('D2q', 'M1', 'E', 'H', 'another model family, Qwen2.5-Coder-32B'),
]
# Appendix, first panel, the run on the second GPU platform: (rate key, the list gives line numbers, label)
PARTS = [('H', False, 'bare names'), ('ES', False, 'names with the first definition line'),
         ('EL', True, 'file and lines'), ('E', True, 'addresses')]
FALSE_ENTRY = [('swapped_E', 'legible', 'a true neighbor, with its address'),
               ('decoy_Ep', 'rewired', 'a false entry, written the same way')]
# Appendix, second panel, the five-call replays: (condition, line color, marker, line style, label)
K_LINES = [('A', '#a3a3a3', 'o', (0, (4, 2)), 'no list'),
           ('H', '#5f5f5f', 's', '-', 'bare names'),
           ('RE', COLORS['rewired'], 'D', '-', 'rewired list, with addresses'),
           ('E', COLORS['legible'], 'o', '-', 'addresses')]
K_BARS = [('A', 'none'), ('H', 'bare'), ('E', 'legible'), ('RE', 'rewired')]
K_WORDS = {'A': 'no list', 'H': 'bare names', 'E': 'addresses', 'RE': 'rewired list'}

W_IN = 7.0
LEFT = 0.40          # label column
TITLE_H, AXIS_H, GAP_H = 0.30, 0.46, 0.20


def _panel_title(fig, y_top, tag, title):
    if not tag:   # a figure with one panel: the title alone
        fig.text(0.012, y_top, title, ha='left', va='top', fontsize=10, color=INK)
        return
    fig.text(0.012, y_top, tag, ha='left', va='top', fontsize=10, fontweight='bold', color=INK)
    fig.text(0.058, y_top - 0.004, title, ha='left', va='top', fontsize=9.2, color=INK)


def _sub(n_complete, n_states=None):
    """The steps a result stands on: those where every condition and seed of its run gave a well-formed call."""
    s = f'{n_complete:,} of {n_states:,} paused steps' if n_states else f'{n_complete:,} paused steps'
    return s + (' (exploratory: fewer than 200)' if n_complete < MIN_COMPLETE else '')


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


def fig_extensions(exps, out_dir, which=('a', 'b', 'c'), name='fig_extensions'):
    """Panels: a, addresses against bare names in every registered variation (Figure 3); b, the parts of an entry and
    a false entry; c, the five-call replays. The main text uses panel a alone; the appendix figure holds b and c."""
    panels = []   # (key, height in inches of the plot area, draw function)
    n_all = exps['B']['info'][0]      # the paused steps every run starts from

    # (a) forest plot
    rows = []
    for src, key, a, b, label in FOREST:
        e = exps.get(src)
        if e is None:
            if 'a' in which:
                print(f'  not drawn: Figure 3 row "{label}" ({RUN_NAME[src]}): no {EXP_NAME[src]} run yet')
            continue
        d = e['diffs'].get(key)
        if d is None:
            print(f'  not drawn: Figure 3 row "{label}": {key} not estimable in the {EXP_NAME[src]} run')
            continue
        if e.get('n_states', n_all) != n_all:
            raise SystemExit(f'{EXP_NAME[src]} starts from {e["n_states"]} paused steps, not {n_all}')
        rows.append(dict(label=label, sub=_sub(e['n_complete'], n_all), d=d, dt=e.get('by_task', {}).get(key),
                         ra=e['rates'][a], rb=e['rates'][b]))
    if rows:
        def draw_a(fig, bottom, height):
            fh = fig.get_figheight()
            left, right = LEFT, 0.665
            ax = fig.add_axes([left, bottom + AXIS_H / fh, right - left, height / fh])
            tr = blended_transform_factory(fig.transFigure, ax.transData)
            lows = [r['d'].lo for r in rows] + [r['dt'].lo for r in rows if r['dt']]
            highs = [r['d'].hi for r in rows] + [r['dt'].hi for r in rows if r['dt']]
            ax.set_xlim(min(-1.0, min(lows) - 0.8), _nice(max(highs), 2) + 0.4)
            ax.axvline(0, color=MUTED, lw=0.8, zorder=1)
            up, down = 0.17, -0.21      # the two lines of a row: clustered by paused step, and by task under it
            for i, r in enumerate(rows):
                y = -i
                d, dt = r['d'], r['dt']
                ax.plot([d.lo, d.hi], [y + up, y + up], color=INK, lw=1.2, solid_capstyle='butt', zorder=2)
                for xx in (d.lo, d.hi):
                    ax.plot([xx, xx], [y + up - 0.09, y + up + 0.09], color=INK, lw=0.9, zorder=2)
                ax.plot(d.val, y + up, marker='s', ms=5.2, color=COLORS['legible'], mec='white', mew=0.5, zorder=3)
                ax.text(left - 0.012, y + up, r['label'], transform=tr, ha='right', va='center', fontsize=8.7,
                        color=INK)
                ax.text(left - 0.012, y + down, r['sub'], transform=tr, ha='right', va='center', fontsize=7.2,
                        color=MUTED)
                ax.text(0.682, y + up, f'{_fmt(d.val, True)} [{_fmt(d.lo)}, {_fmt(d.hi)}]', transform=tr, ha='left',
                        va='center', fontsize=8.5, color=INK)
                ax.text(0.862, y + up, f'{_fmt(r["ra"].val)}%, {_fmt(r["rb"].val)}%', transform=tr, ha='left',
                        va='center', fontsize=7.6, color=INK2)
                if dt:      # the same contrast with tasks as the clusters: a thin line, level with its numbers
                    ax.plot([dt.lo, dt.hi], [y + down, y + down], color=MUTED, lw=0.7, solid_capstyle='butt', zorder=2)
                    for xx in (dt.lo, dt.hi):
                        ax.plot([xx, xx], [y + down - 0.06, y + down + 0.06], color=MUTED, lw=0.7, zorder=2)
                    ax.text(0.682, y + down, f'by task [{_fmt(dt.lo)}, {_fmt(dt.hi)}]', transform=tr, ha='left',
                            va='center', fontsize=7.2, color=MUTED)
            top = 0.78
            ax.text(0.682, top, 'points [95% interval]', transform=tr, ha='left', va='bottom', fontsize=7.2,
                    color=MUTED, style='italic')
            ax.text(0.862, top, 'rates: addresses,\nbare names', transform=tr, ha='left', va='bottom', fontsize=7.2,
                    color=MUTED, style='italic', linespacing=1.15)
            ax.set_ylim(-(len(rows) - 1) - 0.62, top + 0.42)
            ax.set_yticks([])
            ax.spines[['top', 'right', 'left']].set_visible(False)
            ax.tick_params(axis='x', labelsize=8.5, length=3)
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
                lambda v, _: '0' if abs(v) < 1e-9 else f'{v:+.0f}'.replace('-', MINUS)))
            ax.set_xlabel('addresses minus bare names, in percentage points of replays\nwhose next call reads a '
                          'neighbor\'s code', fontsize=8.2, linespacing=1.2)
            return f'Addresses against bare names in every registered variation (the same {n_all:,} paused steps)'
        panels.append(('a', 0.50 * len(rows) + 0.34, draw_a, 0.14))

    # (b) the run on the second platform: which part of an entry, and a false entry
    c = exps.get('C')
    if c is None:
        print('  not drawn: appendix figure, parts of an entry: no experiment C run yet')
    else:
        parts = [q for q in PARTS if c['rates'].get(q[0]) is not None]
        fals = [f for f in FALSE_ENTRY if c['rates'].get(f[0]) is not None]
        for q in PARTS:
            if q not in parts:
                print(f'  not drawn: appendix figure, bar "{q[2]}": condition not in the experiment C run')
        if len(fals) < len(FALSE_ENTRY) or c['diffs'].get('C1') is None:
            print('  not drawn: appendix figure, the false-entry pair: a condition is not in the experiment C run')
            fals = []
        brows = [('header', 'The whole list, by how each neighbor is written: the next call reads a neighbor\'s code')]
        brows += [('bar', key, 'legible' if lines else 'bare', text) for key, lines, text in parts]
        if fals:
            brows += [('header', 'One entry of the list: the next call reads that entry\'s code')]
            brows += [('bar', *f) for f in fals]
            brows += [('diff', 'C1', None, 'the difference, true minus false')]
        n_units = sum(0.9 if kind == 'header' else 1.0 for kind, *_ in brows)

        def draw_b(fig, bottom, height):
            fh = fig.get_figheight()
            ax = fig.add_axes([LEFT, bottom + AXIS_H / fh, 0.97 - LEFT, height / fh])
            vals = [c['rates'][r[1]] for r in brows if r[0] == 'bar']
            xlim = (0, _room(max(v.hi for v in vals), (0.97 - LEFT) * W_IN, 1.9))
            ticks, labels, bold = [], [], []
            y = 0.0
            for kind, key, group, text in ((r + (None, None))[:4] for r in brows):
                if kind == 'header':
                    y -= 0.2 if y == 0 else 0.5
                    ax.text(0, y, key, ha='left', va='center', fontsize=8, color=INK2, style='italic',
                            transform=ax.get_yaxis_transform())
                    y -= 0.7
                    continue
                if kind == 'diff':      # the difference of the two rates above, labelled so that it is not read as one
                    d = c['diffs'][key]
                    true, false = c['rates']['swapped_E'], c['rates']['decoy_Ep']
                    met = d.lo > 0 and false.val < true.val / 2
                    ax.text(0, y, f' {_fmt(d.val, True)} points [{_fmt(d.lo)}, {_fmt(d.hi)}]', ha='left', va='center',
                            fontsize=8.5, color=INK, transform=ax.get_yaxis_transform())
                    ax.text(0.34, y, f'registered rule {"met" if met else "not met"}', ha='left', va='center',
                            fontsize=7.4, color=INK2, transform=ax.get_yaxis_transform())
                else:
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
            _xaxis(ax, xlim, '% of replays (whiskers: 95% interval, clustered by paused step)')
            ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
            return f'The parts of an address, and a false entry (second GPU platform, {_sub(c["n_complete"], n_all)})'
        panels.append(('b', 0.27 * n_units + 0.12, draw_b, 0.0))

    # (c) the five-call replays: reaching the fix, call by call
    k = exps.get('E')
    if k is None:
        print('  not drawn: appendix figure, five calls: no experiment E run yet')
    elif ('R', 'Yline', 5, 'A') not in k['curves']:
        print('  not drawn: appendix figure, five calls: no complete step where a listed neighbor is in a changed file')
    else:
        cv = k['curves']
        show_u = ('U', 'Yfile', 5, 'A') in cv
        head_in = 0.40      # two lines above each plot say which paused steps it holds and what it counts

        def draw_c(fig, bottom, height):
            fh = fig.get_figheight()
            height = height - head_in
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
            ax.set_xlim(0.75, 6.12)
            # values at call 5, moved apart just enough to stay legible
            gap = 8.6 / 72 / (height / ymax)   # one label height in data units
            ly = _spread([v for _, _, v in ends], gap)
            for (arm, color, v), yy in zip(ends, ly):
                ax.text(5.17, yy, f'{K_WORDS[arm]} {_fmt(v, dec=1)}%', ha='left', va='center',
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
            bracket(3.1, 3, f'addresses minus bare names: {_fmt(d3.val, True, 1)} points [{_fmt(d3.lo, dec=1)}, '
                            f'{_fmt(d3.hi, dec=1)}]\nexploratory', 73, 'center')
            bracket(4.9, 5, f'addresses minus bare names: {_fmt(d5.val, True)} points [{_fmt(d5.lo)}, {_fmt(d5.hi)}]\n'
                            f'registered rule {"met" if d5.lo > 0 else "not met"}', 86, 'right')
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_xticks(calls)
            ax.tick_params(labelsize=8, length=3)
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
            ax.set_yticks([0, 20, 40, 60, 80, 100])
            ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
            ax.set_xlabel(f'model call ({k["n_pop"]["R"]:,} paused steps, {cv[("R", "Yline", 5, "A")].n:,} replays per '
                          'condition)', fontsize=8)
            ax.set_ylabel('% of replays', fontsize=8)
            ax.legend(loc='lower right', bbox_to_anchor=(1.0, 0.02), ncol=2, frameon=False, fontsize=7.4,
                      handlelength=2.0, handletextpad=0.5, columnspacing=1.0, borderaxespad=0.0)
            top_l = bottom + (AXIS_H + height) / fh
            fig.text(cr[0], top_l + 0.24 / fh, 'Where a listed neighbor lies in a file the fix changes', ha='left',
                     va='bottom', fontsize=8.4, color=INK)
            fig.text(cr[0], top_l + 0.07 / fh, 'shown a line the fix changes by the end of each model call',
                     ha='left', va='bottom', fontsize=7.4, color=INK2)
            if show_u:
                ur = (0.775, 0.975)
                au = fig.add_axes([ur[0], bottom + AXIS_H / fh, ur[1] - ur[0], height * 0.62 / fh])
                uv = [cv[('U', 'Yfile', 5, a)] for a, _g in K_BARS]
                for i, (a, g) in enumerate(K_BARS):
                    _bar(au, -i, cv[('U', 'Yfile', 5, a)], COLORS[g], 0.55, ci_below=True, size=7.6, dec=1)
                au.set_yticks([-i for i in range(len(K_BARS))], [K_WORDS[a] for a, _g in K_BARS])
                au.tick_params(axis='y', labelsize=7.4)
                au.set_ylim(-len(K_BARS) + 0.45, 0.55)
                _xaxis(au, (0, _room(max(v.hi for v in uv), (ur[1] - ur[0]) * W_IN, 0.66)),
                       f'{k["n_pop"]["U"]:,} paused steps,\n{uv[0].n:,} replays per condition', size=7.6)
                au.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
                top_u = bottom + (AXIS_H + height * 0.62) / fh
                fig.text(ur[0] - 0.085, top_u + 0.30 / fh, 'Where no listed neighbor does', ha='left', va='bottom',
                         fontsize=8.4, color=INK)
                fig.text(ur[0] - 0.085, top_u + 0.05 / fh, 'opens a file the fix changes\nwithin five calls',
                         ha='left', va='bottom', fontsize=7.4, color=INK2, linespacing=1.15)
            else:
                print('  not drawn: appendix figure, bars where no listed neighbor is in a changed file: no complete '
                      'step')
            return 'Five-call replays, with reads executing: does the list bring the agent to the fix?'
        panels.append(('c', 2.6 + head_in, draw_c, 0.12))

    panels = [(h, draw, extra) for key, h, draw, extra in panels if key in which]
    if not panels:
        print(f'  not drawn: {name}: no run available')
        return False
    H_IN = sum(TITLE_H + h + AXIS_H + extra for h, _d, extra in panels) + GAP_H * (len(panels) - 1) + 0.08
    fig = plt.figure(figsize=(W_IN, H_IN))
    top = H_IN - 0.06
    for i, (h, draw, extra) in enumerate(panels):
        bottom = top - TITLE_H - h - AXIS_H - extra      # extra: room for a second line under the axis
        title = draw(fig, (bottom + extra) / H_IN, h)
        _panel_title(fig, top / H_IN, '' if len(panels) == 1 else f'({chr(97 + i)})', title)
        top = bottom - GAP_H
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'{name}.{ext}', dpi=300)
    plt.close(fig)
    return True


# ---------------------------------------------------------------- Tables 1 and 2: data files, rendered here
def _display(s):
    """Typographic minus for negative numbers and for 'X - Y' between words; nothing else changes."""
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
# The verdicts a rule may carry unless its table names its own ("outcomes" in the data file), in the order of the
# tally; they are the words of Appendix A. "no detectable difference" is for a rule that registered both directions
# (its interval may exclude 0 either way) when the interval holds 0; "asked for less often" for one that found the
# direction that is not a claim of the paper; "underpowered" for one whose own condition for being informative
# failed. A gate (a row marked "gate": true) is "passed" or "failed" and is not counted among the rules.
OUTCOMES = ('met', 'not met', 'no detectable difference', 'asked for less often', 'not tested', 'underpowered',
            'pending')
GATE_OUTCOMES = ('passed', 'failed')


def _verdict(outcome):
    """An outcome as (its word, which the tally counts; the colon or comma after it; what follows): 'met',
    'not met: no harm', 'asked for less often, narrowly'."""
    m = re.match(r'([^:,]*)([:,]?)(.*)', outcome.strip(), re.S)
    return m.group(1).strip(), m.group(2), m.group(3).strip()
# The tables are read in a writeup that shows an image about 800 px wide. Their type is set so that a capital
# letter is then about 12 px high: 10.6 pt on a page 7 inches wide (the figures' annotations are smaller).
TABLE_FS = 10.6
MAX_ROWS = 45      # a table of rules with more rows than this (rules and group headers) is drawn as two images


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
    """Values the figure code computes, by the key a rule of a table names in "check"."""
    out = {}
    src = {'B1': ('B', 'B1'), 'B3': ('B', 'B3'), 'B4_D': ('B', 'B4_D'), 'B4_E': ('B', 'B4_E'), 'G2': ('C', 'G2'),
           'C1': ('C', 'C1'), 'C2_EL': ('C', 'C2_EL'), 'C2_ES': ('C', 'C2_ES'), 'E_EL_90': ('C', 'E_EL_90'),
           'T1': ('D1', 'T1'), 'T2_90': ('D1', 'T2_90'), 'M1_D2a': ('D2a', 'M1'), 'M1_D2b': ('D2b', 'M1'),
           'K1': ('E', 'K1'), 'K1_task': ('E', 'K1_task'), 'K2': ('E', 'K2'), 'F2': ('F', 'F2'), 'F3': ('F', 'F3'),
           'S1': ('S', 'S1'), 'M2': ('D2q', 'M1'), 'P1': ('P', 'P1'), 'P2': ('P', 'P2'), 'X1': ('X', 'X1'),
           'X2': ('X', 'X2')}
    for key, (tag, k) in src.items():
        d = (exps.get(tag) or {}).get('diffs', {}).get(k)
        if d is not None:
            out[key] = d
    for key, tag in (('G1', 'C'), ('F1', 'F')):
        v = (exps.get(tag) or {}).get('points', {}).get(key)
        if v is not None:
            out[key] = v
    return out


def _plain(s):
    """A cell as it is compared with a report: ASCII minus, no thousands separators."""
    return s.replace(MINUS, '-').replace(',', '')


def _expected(template, groups):
    """The text a report line gives in an estimate: {0} is a group as the report prints it, {0:u} the same without a
    leading plus sign (the way the tables write the bounds of an interval), {0:n} a whole number with thousands
    separators."""
    def one(m):
        g = groups[int(m.group(1))]
        return g.lstrip('+') if m.group(2) == ':u' else f'{int(g):,}' if m.group(2) == ':n' else g
    return re.sub(r'\{(\d+)(:[un])?\}', one, template)


def _triple(d, key=''):
    """A computed contrast as the tables write it, '+5.50 [3.44, 7.65]'; a key that ends in _90 names a 90% interval,
    and the cell then says so: '+1.59, 90% [0.00, 3.17]'."""
    return f'{d.val:+.2f}{", 90%" if key.endswith("_90") else ""} [{d.lo:.2f}, {d.hi:.2f}]'


def read_values(spec, name):
    """The named values of a table: {name: number or text}, and the ones that are typed, with their sources.

    A value is read from a stored report ({"file", "pattern"}: the first group of the first match; with "count":
    true the group is a list the report prints, such as [1, 2, 3], and the value is how many items it has; with
    "count": a pattern, the value is how often that pattern occurs in the group) or from a stored JSON file ({"json",
    "field"}; with "count": true the field is a list and the value is its length; with "count": a pattern, how many
    of its items the pattern matches), worked out from other values ({"sum": [names]}, {"minus": [name, names to
    subtract]}, {"product": [names]}, {"min": [names]}, {"max": [names]}) or typed ({"value", "source"}). A JSON
    value may carry a typed "value" for the time its file is not in the repository yet: it is then listed as typed,
    and once the file exists the two must agree. "equals": name makes the script stop unless the value equals that
    other value (two reports, or a report and a count, that must agree). A missing file or line stops the script,
    unless the value is marked {"optional": true}; it is then None, and min and max pass over it."""
    defs, out, typed = spec.get('values', {}), {}, []
    ops = {'sum': sum, 'minus': lambda p: p[0] - sum(p[1:]), 'product': lambda p: functools.reduce(operator.mul, p),
           'min': min, 'max': max}

    def get(key):
        if key in out:
            return out[key]
        if key not in defs:
            raise SystemExit(f'{name}: the text names a value "{key}" that the file does not define')
        d = defs[key]
        op = next((o for o in ops if o in d), None)
        if 'file' in d:
            path = ROOT / d['file']
            m = re.search(d['pattern'], path.read_text(encoding='utf-8'), re.M) if path.exists() else None
            if m is None and not d.get('optional'):
                raise SystemExit(f'{name}: value "{key}": no line for {d["pattern"]!r} in {d["file"]}')
            v = None if m is None else m.group(1)
            if v is not None and isinstance(d.get('count'), str):
                v = len(re.findall(d['count'], v))
            elif v is not None and d.get('count'):
                try:
                    items = ast.literal_eval(v)
                except (ValueError, SyntaxError):
                    items = None
                if not isinstance(items, (list, tuple)) or len(set(items)) != len(items):
                    raise SystemExit(f'{name}: value "{key}": {v!r} in {d["file"]} is not a list of distinct items')
                v = len(items)
            elif v is not None and re.fullmatch(r'\d[\d,]*', v):
                v = int(v.replace(',', ''))
        elif 'json' in d:
            path = ROOT / d['json']
            if path.exists():
                v = json.loads(path.read_text(encoding='utf-8'))
                for part in d['field'].split('.'):
                    v = v[part]
                if d.get('count'):
                    if not isinstance(v, list):
                        raise SystemExit(f'{name}: value "{key}": {d["field"]} in {d["json"]} is not a list')
                    v = len(v) if d['count'] is True else sum(1 for item in v if re.search(d['count'], str(item)))
                if 'value' in d and d['value'] != v:
                    raise SystemExit(f'{name}: value "{key}" is typed as {d["value"]} and {d["json"]} gives {v}')
            elif 'value' in d:
                v = d['value']
                typed.append((key, v, d.get('source') or f'{d["json"]}, field {d["field"]} (file not there yet)'))
            elif d.get('optional'):
                v = None
            else:
                raise SystemExit(f'{name}: value "{key}": {d["json"]} is missing')
        elif op:
            parts = [get(k) for k in d[op]]
            if op in ('min', 'max'):
                parts = [p for p in parts if p is not None]
            v = None if not parts or any(p is None for p in parts) else ops[op](parts)
        else:
            v = d['value']
            typed.append((key, v, d.get('source') or 'NO SOURCE GIVEN'))
        if 'equals' in d and v is not None and get(d['equals']) is not None and v != get(d['equals']):
            raise SystemExit(f'{name}: value "{key}" is {v} and "{d["equals"]}" is {get(d["equals"])}: they must agree')
        out[key] = v
        return v

    for key in defs:
        get(key)
    return out, typed


def _fill(text, values, name):
    """Put the named values into a text: {name}; whole numbers get thousands separators."""
    def one(m):
        key = m.group(1)
        if key not in values:
            raise SystemExit(f'{name}: the text names a value "{key}" that the file does not define')
        v = values[key]
        return 'pending' if v is None else f'{v:,}' if isinstance(v, int) else str(v)
    return re.sub(r'\{(\w+)\}', one, text)


def rule_rows(spec):
    """Every rule of a table of rules, with the title of its group ('' in a flat list, the form of the digest)."""
    return ([(g['title'], row) for g in spec.get('groups', []) for row in g['rows']]
            + [('', row) for row in spec.get('rules', [])])


def _label(row):
    """How the checks name a rule: its text, after its identifier where the table gives one."""
    rule = ' '.join(row['rule'].split())        # a rule may fix where its text breaks in the table
    return f'"{row["id"]}: {rule}"' if row.get('id') else f'"{rule}"'


def tally(rows, outcomes=OUTCOMES):
    """How many registered rules carry each outcome: (the counts, a line that states them). Not counted: a row marked
    "count": false (a second reading of a rule that another row counts) and a row marked "gate": true (by the
    convention of Appendix A a row labelled "Gate" there is a gate, and every other row is a rule)."""
    rules = [row for row in rows if row.get('count', True) and not row.get('gate')]
    count = collections.Counter(row['outcome'] if row.get('as_reported') else _verdict(row['outcome'])[0]
                                for row in rules)
    order = [k for k in outcomes if count[k]] + sorted(k for k in count if k not in outcomes)
    gates = sum(1 for row in rows if row.get('gate'))
    return count, (f'{len(rules)} rules: ' + ', '.join(f'{k} {count[k]}' for k in order)
                   + (f'; gates listed and not counted: {gates}' if gates else ''))


def _derive(row, comp, name, notes):
    """Fill the cells that a rule does not type. An estimate that is left out is built from the rule's "check" keys
    (the values computed here) and its "report" lines, in that order, joined by "join" (', ' unless given). An
    outcome given as {"file", "pattern", "words"} is the verdict that the stored report prints (the pattern's first
    group), turned into the table's word by "words"; a verdict that "words" does not hold is shown as the report
    words it, and noted. A rule marked "pending": true may wait for its report: while a file it reads is missing,
    both cells say "pending". Any other missing file or line stops the script."""
    label = _label(row)
    waiting = []

    def text_of(file):
        path = ROOT / file
        if path.exists():
            return path.read_text(encoding='utf-8')
        if not row.get('pending'):
            raise SystemExit(f'{name}, {label}: {file} does not exist')
        waiting.append(file)
        return None

    if 'estimate' not in row:
        pieces = []
        for k in row.get('check') or []:
            if k not in comp:
                raise SystemExit(f'{name}, {label}: no computed value {k} (its run is not available)')
            pieces.append(f'{100 * comp[k]:.2f}%' if k in POINT_KEYS else _triple(comp[k], k))
        for r in row.get('report') or []:
            text = text_of(r['file'])
            if text is None:
                continue
            m = re.search(r['pattern'], text, re.M)
            if m is None:
                raise SystemExit(f'{name}, {label}: no line for {r["pattern"]!r} in {r["file"]}')
            pieces.append(_expected(r['expect'], m.groups()))
        if not pieces and not waiting:
            raise SystemExit(f'{name}, {label}: no estimate, and no "check" or "report" to build one from')
        row['estimate'] = 'pending' if waiting else row.get('join', ', ').join(pieces)
    if isinstance(row['outcome'], dict):
        said_by = row['outcome']
        text = text_of(said_by['file'])
        if text is None:
            row['outcome'] = 'pending'
        else:
            m = re.search(said_by['pattern'], text, re.M)
            if m is None:
                raise SystemExit(f'{name}, {label}: no line for {said_by["pattern"]!r} in {said_by["file"]}')
            said = m.group(1).strip()
            row['outcome'] = said_by['words'].get(said, said)
            if said not in said_by['words']:
                row['as_reported'] = True
                notes.append(f'{name}, {label}: the verdict "{said}" of {said_by["file"]} has no word among the '
                             'outcomes of this table and is shown as the report words it')


def prepare_table(spec, name, comp=None):
    """Check the form of a table's data, read its values, build the cells that are not typed and fill its texts.
    Returns (the filled spec, typed values, notes to print). A table of rules has "groups" (a title, its
    pre-registrations, its rules: rule, estimate, outcome) or, as a flat list, "rules" (the same with an "id" before
    each); a table of samples has "rows" of "cells". A table of rules may name the only outcomes it takes
    ("outcomes"); otherwise the word before a colon or comma must be one of OUTCOMES. comp: the values computed
    here, by the key a rule names in "check"."""
    values, typed = read_values(spec, name)
    out = json.loads(json.dumps(spec))
    notes = []
    for row in out.get('rows', []):
        ready = row.pop('cells_when', None)
        if ready and (ROOT / ready['file']).exists():       # the row's final text, once its report exists
            row['cells'] = ready['cells']
        row['cells'] = [_fill(c, values, name) for c in row['cells']]
    for _title, row in rule_rows(out):
        _derive(row, comp or {}, name, notes)
        verdict = _verdict(row['outcome'])[0]
        if row.get('gate'):
            allowed, word = GATE_OUTCOMES, row['outcome']
        elif 'outcomes' in out:                              # a table that names its outcomes takes exactly those
            allowed, word = tuple(out['outcomes']), row['outcome']
        else:
            allowed, word = OUTCOMES, verdict
        if word not in allowed and not row.get('as_reported'):
            raise SystemExit(f'{name}, {_label(row)}: outcome "{row["outcome"]}" is not one of {", ".join(allowed)}')
        if (row['estimate'].strip().lower() == 'pending') != (verdict == 'pending'):
            raise SystemExit(f'{name}, {_label(row)}: pending in one cell and not in the other')
        row['estimate'] = _fill(row['estimate'], values, name)
        row['rule'] = _fill(row['rule'], values, name)
    fill = lambda text: _fill(text, {**values, 'tally': '{tally}'}, name)    # noqa: E731 (the tally: when drawn)
    out['note'] = fill(out.get('note', ''))
    out['note_split'] = [fill(text) for text in out.get('note_split', [])]
    return out, typed, notes


def _contradiction(outcome, text):
    """What in an estimate contradicts its outcome, or None. Only an estimate with one interval is read, as the cell
    prints it: "met" with a lower bound below 0, "not met" with a lower bound above 0, "no detectable difference"
    with an interval that excludes 0. This is a necessary condition of the rules of the digest (each asks at least
    for a lower bound above 0), not the rule itself, which the registered script applies; a bound printed as 0 is
    taken either way."""
    found = _estimates(text)
    if len(found) != 1:
        return None
    lo, hi = (float(x.replace(MINUS, '-')) for x in found[0][1:])
    word = _verdict(outcome)[0]
    if (word == 'met' and lo < 0) or (word == 'not met' and lo > 0):
        return f'a lower bound of {lo:g}'
    if word == 'no detectable difference' and (lo > 0 or hi < 0):
        return f'an interval [{lo:g}, {hi:g}] that excludes 0'
    return None


def check_table(spec, exps, ck, name):
    """Every estimate of a table of rules against the values computed here ("check") or a line of a stored report
    ("report"), whether it was typed or built from them; a typed rule that is pending prints what its run or report
    now gives, to be pasted in. In a table marked "check_outcomes": true an outcome may not contradict the interval
    of its estimate."""
    comp = checkable(exps)
    ck.lines.append(f'  {name}, estimates against the computed values and the stored reports:')
    loose = []
    for _title, row in rule_rows(spec):
        label = _label(row)
        text, pending = row['estimate'], row['estimate'].strip().lower() == 'pending'
        covered = ['90%'] if any(k.endswith('_90') for k in row.get('check') or []) and ', 90% [' in text else []
        found, k_found = _estimates(text), 0
        for k in row.get('check') or []:
            if k not in comp:
                if not pending:
                    ck.lines.append(f'    {label} {k}: no computed value (run not available): not checked')
                continue
            if pending:
                ck.lines.append(f'    {label} is pending; computed {k}: {comp[k].val:+.2f} [{comp[k].lo:.2f}, '
                                f'{comp[k].hi:.2f}]')
                continue
            if k in POINT_KEYS:
                m = re.search(NUM, text)
                if m:
                    ck.same(f'{label} {k}', comp[k], m.group(0).replace(MINUS, '-'), 100, 2)
                    covered.append(m.group(0).replace(MINUS, '-'))
                else:
                    ck.missing(f'{label} {k}')
                continue
            if k_found >= len(found):
                ck.missing(f'{label} {k} (no "[lo, hi]" left in the estimate)')
                continue
            pt, lo, hi = (None if x is None else x.replace(MINUS, '-') for x in found[k_found])
            k_found += 1
            if pt is not None:
                ck.same(f'{label} {k} point', comp[k].raw[0], pt, 100, 2)
                covered.append(pt)
            ck.same(f'{label} {k} lo', comp[k].raw[1], lo, 100, 2)
            ck.same(f'{label} {k} hi', comp[k].raw[2], hi, 100, 2)
            covered += [f'[{lo} {hi}]']
        for r in row.get('report') or []:
            path = ROOT / r['file']
            if not path.exists():
                if not pending:
                    ck.missing(f'{label}: {r["file"]} does not exist')
                continue
            m = re.search(r['pattern'], path.read_text(encoding='utf-8'), re.M)
            if m is None:
                ck.missing(f'{label}: no line for {r["pattern"]!r} in {r["file"]}')
                continue
            want = _expected(r['expect'], m.groups())
            if pending:
                ck.lines.append(f'    {label} is pending; {r["file"]} gives: {want}')
                continue
            ok = _plain(want) in _plain(text)
            ck.lines.append(f'    {label}: "{want}" from {r["file"]} {"match" if ok else "MISMATCH"}')
            if not ok:
                ck.bad.append(label)
            covered.append(_plain(want))
        if not pending:      # numbers of the estimate that nothing above verified
            rest = _plain(text)
            for c in sorted(covered, key=len, reverse=True):
                rest = rest.replace(c, ' ')
            left = re.findall(r'(?<![\w.])[+-]?\d+(?:\.\d+)?%?', rest)
            if left:
                loose.append(f'    {label}: typed and not verified: {", ".join(left)}')
        if spec.get('check_outcomes') and not pending and len(found) == 1:
            against = _contradiction(row['outcome'], text)
            ck.lines.append(f'    {label}: outcome "{row["outcome"]}" beside its interval: '
                            + (f'{against}: MISMATCH' if against else 'match'))
            if against:
                ck.bad.append(label)
    ck.lines += loose


def table_lint(spec, name):
    """Numbers written by hand into the texts of a table: the cells of a table of samples (every other number there
    is a named value), the wording of the rules of a flat list of rules (its estimates are verified apart), and the
    note under either."""
    def written(text):
        rest = re.sub(r'\{\w+\}', ' ', text)
        rest = re.sub(r'pre-registrations? \d+(?:(?:, | and | to )\d+)*', ' ', rest)
        return re.findall(r'(?<![\w.\-])\d[\d,]*(?:\.\d+)?(?![\w\-])', rest)

    out = []
    for i, row in enumerate(spec.get('rows', []), 1):
        ready = (row.get('cells_when') or {}).get('cells', [])
        for j, cell in enumerate(row.get('cells', []) + ready):
            if written(cell):
                out.append(f'    {name}, row {i}, column {j % len(row["cells"]) + 1}: written in the text: '
                           + ', '.join(written(cell)))
    for row in spec.get('rules', []):
        if written(row['rule']):
            out.append(f'    {name}, rule {row.get("id", "")}: written in the wording: ' + ', '.join(written(row['rule'])))
    if ('rows' in spec or 'rules' in spec) and written(spec.get('note', '')):
        out.append(f'    {name}, the note: written in the text: ' + ', '.join(written(spec['note'])))
    return out


def _draw_table(cols, fracs, body, note, out_dir, name):
    """One table image. body: ('band', bold text, grey text) for a group header across the page, or
    ('row', [cell, ...]) where a cell is a list of lines and a line a list of (text, size, weight, color, style)
    pieces set one after another."""
    fs, lh = TABLE_FS, TABLE_FS * 1.30
    pad_x, pad_y = 5.0, 3.4
    W = W_IN * 72
    xs = [W * sum(fracs[:i]) for i in range(len(fracs))]
    head = [_wrap_pts(c, W * fracs[i] - 2 * pad_x, fs, 'bold') for i, c in enumerate(cols)]
    head_h = max(len(h) for h in head) * lh + 2 * pad_y
    heights = [lh + 2 * pad_y + 1.5 if kind == 'band' else max(len(c) for c in rest[0]) * lh + 2 * pad_y
               for kind, *rest in body]
    note_fs = fs - 2.4
    note_lines = _wrap_pts(_display(note), W - 2 * pad_x, note_fs) if note else []
    note_h = len(note_lines) * note_fs * 1.32 + (2 * pad_y if note_lines else 0)
    H = head_h + sum(heights) + note_h + 4
    fig = plt.figure(figsize=(W_IN, H / 72))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis('off')
    renderer = fig.canvas.get_renderer()

    def put(x, y, pieces):
        for text, size, weight, color, style in pieces:
            t = ax.text(x, y, text, ha='left', va='baseline', fontsize=size, fontweight=weight, color=color,
                        style=style)
            x += t.get_window_extent(renderer).width * 72 / fig.dpi + size * 0.28

    y = H - 2
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    for i, h in enumerate(head):
        for k, line in enumerate(h):
            put(xs[i] + pad_x, y - pad_y - (k + 0.78) * lh, [(line, fs, 'bold', INK, 'normal')])
    y -= head_h
    ax.plot([0, W], [y, y], color=INK2, lw=0.6)
    for (kind, *rest), h in zip(body, heights):
        if kind == 'band':
            ax.add_patch(plt.Rectangle((0, y - h), W, h, fc='#f1f1f1', ec='none', zorder=0))
            put(pad_x, y - pad_y - 0.75 - 0.78 * lh, [(rest[0], fs, 'bold', INK, 'normal'),
                                                       (rest[1], fs - 2.2, 'normal', INK2, 'normal')])
        else:
            for i, cell in enumerate(rest[0]):
                for k, pieces in enumerate(cell):
                    put(xs[i] + pad_x, y - pad_y - (k + 0.78) * lh, pieces)
            ax.plot([0, W], [y - h, y - h], color=RULE_LIGHT, lw=0.5)
        y -= h
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    for k, line in enumerate(note_lines):
        ax.text(pad_x, y - pad_y - k * note_fs * 1.32, line, ha='left', va='top', fontsize=note_fs, color=INK2)
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'{name}.{ext}', dpi=300)
    plt.close(fig)


def _outcome_cell(outcome, width, counted=True, two_colors=False):
    """The outcome as it is written ('met', 'not met: no harm', 'asked for less often, narrowly'), all of it in the
    style of its verdict; when it does not fit on one line it breaks after the verdict. The verdict of a row that
    the tally does not count (a second reading of a rule, or a gate) is set in plain grey. two_colors (the digest):
    "met" in the accent, every other outcome in the color of the text."""
    fs = TABLE_FS
    verdict, sep, why = _verdict(outcome)
    plain = ('normal', INK, 'normal')
    if two_colors:
        style = ('bold', COLORS['legible'], 'normal') if outcome == 'met' else (
            'normal', INK, 'italic' if outcome == 'pending' else 'normal')
    else:
        style = {'met': ('bold', COLORS['legible'], 'normal'), 'not met': ('bold', INK, 'normal'),
                 'not tested': ('normal', INK2, 'normal'), 'underpowered': ('normal', INK2, 'normal'),
                 'pending': ('normal', MUTED, 'italic')}.get(verdict, plain)
    if not counted:
        style = ('normal', INK2, 'normal')
    wrap = lambda text: _wrap_pts(text, width, fs, style[0], style[2])      # noqa: E731
    whole = f'{verdict}{sep} {why}' if why else verdict
    pieces = wrap(whole) if len(wrap(whole)) == 1 or not why else wrap(verdict + sep) + wrap(why)
    return [[(l, fs, *style)] for l in pieces]


def fig_table(spec, out_dir, name='table_rules'):
    """Render a prepared table and return the names of the images written.

    A table of rules in groups (the full list): three columns; each group is a band across the page (its question in
    bold, its pre-registrations in grey) and each rule one row. With more than MAX_ROWS rows, or with "split": true
    in its data, it is drawn as two images, the second starting at the group named in "split_before", each with the
    tally of its own rules in its note ("note_split": the note of each part; without it both carry "note"). A flat
    list of rules (the digest): four columns, the rule's identifier, its question, the estimate and the outcome, in
    two colors ("met" in the accent, all else in the color of the text), no bands and no marks. A table of samples:
    rows of cells, the first cell bold."""
    fs = TABLE_FS
    cols = spec['columns']
    fracs = spec.get('widths') or [1 / len(cols)] * len(cols)
    width = [W_IN * 72 * f - 10.0 for f in fracs]
    plain = lambda text, i, weight='normal', color=INK: [[(l, fs, weight, color, 'normal')]      # noqa: E731
                                                         for l in _wrap_pts(_display(text), width[i], fs, weight)]
    if 'rules' in spec:
        body = []
        for row in spec['rules']:
            slant = 'italic' if row['estimate'].strip().lower() == 'pending' else 'normal'
            est = [[(l, fs, 'normal', INK, slant)] for l in _wrap_pts(_display(row['estimate']), width[2], fs)]
            body.append(('row', [plain(row['id'], 0), plain(row['rule'], 1), est,
                                 _outcome_cell(row['outcome'], width[3], two_colors=True)]))
        _draw_table(cols, fracs, body, spec.get('note', ''), out_dir, name)
        return [name]
    if 'groups' not in spec:
        body = [('row', [plain(c, i, 'bold' if i == 0 else 'normal') for i, c in enumerate(row['cells'])])
                for row in spec['rows']]
        _draw_table(cols, fracs, body, spec.get('note', ''), out_dir, name)
        return [name]
    parts = [spec['groups']]
    n_rows = sum(1 + len(g['rows']) for g in spec['groups'])
    titles = [g['title'] for g in spec['groups']]
    if (n_rows > MAX_ROWS or spec.get('split')) and spec.get('split_before') in titles[1:]:
        cut = titles.index(spec['split_before'])
        parts = [spec['groups'][:cut], spec['groups'][cut:]]
    names = []
    for k, groups in enumerate(parts):
        body = []
        for g in groups:
            body.append(('band', g['title'], g.get('prereg', '')))
            for row in g['rows']:
                pend = row['estimate'].strip().lower() == 'pending'
                rule = plain(row['rule'], 0)
                if len(rule) > 1:
                    print(f'  {name}: the rule "{row["rule"]}" does not fit on one line')
                est = [[(l, fs, 'normal', MUTED if pend else INK, 'italic' if pend else 'normal')]
                       for l in _wrap_pts(_display(row['estimate']), width[1], fs)]
                counted = row.get('count', True) and not row.get('gate')
                body.append(('row', [rule, est, _outcome_cell(row['outcome'], width[2], counted)]))
        _count, line = tally([row for g in groups for row in g['rows']])
        names.append(name if k == 0 else f'{name}_{k + 1}')
        own = spec.get('note_split') or []
        note = own[k] if len(parts) > 1 and len(own) == len(parts) else spec.get('note', '')
        _draw_table(cols, fracs, body, note.replace('{tally}', line), out_dir, names[-1])
    return names


# ---------------------------------------------------------------- Figure 1: design
def _new_file_gloss(tc):
    """Three words under a write_file call of the history, so that it is not taken for an edit of the repository. A
    paused step is cut before the agent has edited a repository file: analysis/fork_states.py stops at any edit_file
    and at a write_file onto a file of the repository, so a write_file that the history shows made a new file. One
    made at the top of the working directory, as a script that reproduces the issue is, is called a scratch file."""
    if tc['function_name'] != 'write_file':
        return None
    path = str((tc.get('arguments') or {}).get('filepath') or '').replace('\\', '/')
    return '(a scratch file)' if '/' not in path.strip('./') else '(a new file)'


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
    """One real paused step (default: the first in the file)."""
    with open(states_path, encoding='utf-8') as f:
        for line in f:
            s = json.loads(line)
            k = (s['task'], s['run'], s.get('fork', 0))
            if key is None or k == key:
                return s
    raise SystemExit(f'paused step {key} not found in {states_path}')


def _wrap(text, width, indent='  '):
    out = []
    for para in text.split('\n'):
        lead = len(para) - len(para.lstrip(' '))
        out += textwrap.wrap(para.lstrip(' '), width, initial_indent=' ' * lead,
                             subsequent_indent=' ' * lead + indent, break_long_words=False,
                             break_on_hyphens=False) or ['']
    return out


WORD = {1: 'one', 2: 'two', 3: 'three'}
LINE_NUMBERS = ('file and lines', 'addresses', 'search hits')      # the conditions whose list gives line numbers
# The conditions, in the words every figure and table uses, each with what its message holds
CONDITIONS = [
    ('no list', 'nothing is added'),
    ('bare names', 'the neighbors as the tool prints them'),
    ('names with an instruction', 'bare names and an instruction to read them'),
    ('file only', 'each neighbor with its file'),
    ('file and lines', 'with its file and line range'),
    ('addresses', 'file, line range and first definition line'),
    ('search hits', 'the same addresses as file:line:definition'),
    ('false entry', 'one true neighbor swapped for a non-neighbor'),
    ('rewired list', 'neighbors from a degree-preserving rewiring of the graph'),
]


def _list_lines(body, width, shown=2):
    """A stored JSON list message, trimmed for display: its opening as stored, its first entries one per line (a
    long entry is broken between its fields), and the count of the entries left out. Nothing is reworded: the
    function first checks that the pieces it shows add up to the stored text."""
    obj = json.loads(body)
    items = obj['neighbors']
    opening = body[:body.index('[') + 1]
    closing = body[body.rindex(']'):]
    if opening + ', '.join(json.dumps(e) for e in items) + closing != body:
        raise SystemExit('fig_design: the stored list message is not written as json.dumps writes it')
    lines = [opening]
    for e in items[:shown]:
        if not isinstance(e, dict):
            lines.append(' ' + json.dumps(e) + ',')
            continue
        fields = [f'{json.dumps(k)}: {json.dumps(v)}' for k, v in e.items()]
        cur = ' {' + fields[0]
        for field in fields[1:]:
            if len(cur) + 2 + len(field) + 2 > width:
                lines.append(cur + ',')
                cur = '  ' + field
            else:
                cur += ', ' + field
        lines.append(cur + '},')
    lines.append(f' … {len(items) - shown} more{closing}')
    return [piece for line in lines for piece in _wrap(line, width, indent='   ')]


def example_forms(s, hits, width):
    """[(label, accent, the message's first line, its lines as displayed)] for bare names, addresses and, when the
    paused step is given with its search-hit condition, search hits. Every text is read from the stored conditions
    of one paused step and trimmed in one way: the first two entries, then how many more."""
    out = []
    for label, arm, accent in (('bare names', 'H', False), ('addresses', 'E', True)):
        head, body = s['arms'][arm]['user_text'].split('\n', 1)
        out.append((label, accent, head, _list_lines(body, width)))
    if hits is not None:
        head, *rows = hits['arms']['EG']['user_text'].split('\n')
        if head != out[0][2]:
            raise SystemExit('fig_design: the search-hit condition does not begin with the line the others begin with')
        lines = [piece for row in rows[:2] for piece in _wrap(row, width, indent='   ')]
        out.append(('search hits', True, head, lines + [f'… {len(rows) - 2} more lines']))
    if len({head for _l, _a, head, _lines in out}) != 1:
        raise SystemExit('fig_design: the example conditions do not share their first line')
    return out


def fig_design(key, exps, out_dir):
    """One paused step, the one message that differs between conditions, and the outcome."""
    s = pick_example(B_STATES, key)
    hits = pick_example(H_STATES, (s['task'], s['run'], s.get('fork', 0))) if H_STATES.exists() else None
    n_states, _n_complete, _n_arms, seeds = exps['B']['info']
    W_IN = 7.0
    U = W_IN * 72 / 100                  # points per x unit; y units are the same size
    PAD = 1.4
    T, BS, MS, ES = 8.6, 7.4, 6.6, 6.1   # title, body, monospace of the history, monospace of the examples
    blue = COLORS['legible']

    def step(size, gap=1.32):
        return size * gap / U

    def prose(text, w_units, size=BS, weight='normal', style='normal'):
        """A text wrapped to a box of w_units, by the width of its letters."""
        return _wrap_pts(text, (w_units - 2 * PAD) * U, size, weight, style)

    # Everything is laid out before the page is sized. A block is (lines, size, monospace, color, weight, style,
    # space after it); a box is its title and its blocks, and the last block may be pinned to the box's foot.
    cols = [(1.0, 26.0), (30.0, 24.0), (57.0, 18.5), (78.5, 20.5)]
    calls = [tc for st in s['steps'] if st.get('source') == 'agent' for tc in (st.get('tool_calls') or [])]
    calls = calls[:s['tool_calls_before_fork']]
    width = int((cols[0][1] - 2 * PAD) * U / (MS * 0.602))
    show = list(range(len(calls))) if len(calls) <= 4 else [0, 1, None, len(calls) - 1]
    history = [(['the task prompt (an issue), then'], BS, False, INK2, 'normal', 'normal', 0.9)]
    for i in show:
        if i is None:
            history.append(([f'… {len(calls) - 3} more calls'], MS, True, MUTED, 'normal', 'normal', 0.7))
            continue
        last = i == len(calls) - 1
        gloss = _new_file_gloss(calls[i])
        history.append((_call_lines(calls[i], width), MS, True, INK if last else INK2, 'bold' if last else 'normal',
                        'normal', 0.1 if gloss else 0.7))
        if gloss:
            history.append((['    ' + gloss], MS, False, MUTED, 'normal', 'italic', 0.7))
    boxes = [
        ('1  A recorded run, paused', MUTED, 'white', history,
         (prose('This result shows file content: the run is paused here.', cols[0][1], style='italic'), BS, False, INK,
          'normal', 'italic', 0)),
        ('2  One message is added', blue, '#f3f7fb',
         [(prose('The graph neighbors of a function the agent has just read, written in one of the ways below.',
                 cols[1][1]), BS, False, INK, 'normal', 'normal', 1.4),
          (prose('Nothing else differs between conditions.', cols[1][1], weight='bold'), BS, False, blue, 'bold',
           'normal', 1.4),
          (prose('The agent did not ask for the list.', cols[1][1]), BS, False, INK2, 'normal', 'normal', 0)], None),
        ('3  One model call', MUTED, 'white',
         [(prose('The harness\'s own agent makes its next call. No tool runs.', cols[2][1]), BS, False, INK, 'normal',
           'normal', 1.4),
          (prose(f'{n_states:,} paused steps, {len(seeds)} seeds per condition.', cols[2][1]), BS, False, INK2,
           'normal', 'normal', 0)], None),
        ('4  What the call does', MUTED, 'white',
         [(['opens a neighbor\'s file'], BS, False, INK, 'bold', 'normal', 0),
          (prose('it reads that file, at any line', cols[3][1]), BS, False, INK2, 'normal', 'normal', 0.8),
          (['reads a neighbor\'s code'], BS, False, INK, 'bold', 'normal', 0),
          (prose('it reads lines of a listed neighbor in a file not yet opened', cols[3][1]), BS, False, INK2, 'normal',
           'normal', 0.8)],
         (prose('Compared: addresses against bare names; each against no list.', cols[3][1]), BS, False, INK, 'normal',
          'normal', 0)),
    ]

    def height(blocks):
        return sum(len(lines) * step(size) + after for lines, size, _m, _c, _w, _s, after in blocks)

    top_h = max(PAD + step(T) + 1.0 + height(blocks) + (1.2 + height([foot]) if foot else 0) + PAD - 0.4
                for _t, _ec, _fc, blocks, foot in boxes)

    label_w = 11.0                                        # the column of the example labels
    forms = example_forms(s, hits, int((98.0 - 2 * PAD - label_w) * U / (ES * 0.602)))
    cell_w = (98.0 - 2 * PAD) / 3
    cells = [(name, _wrap_pts(text, (cell_w - 2.0) * U, BS)) for name, text in CONDITIONS]
    rows = [cells[i:i + 3] for i in range(0, len(cells), 3)]
    row_h = [step(BS) * (1 + max(len(lines) for _n, lines in row)) + 0.9 for row in rows]
    forms_h = sum(step(ES) * (1 + len(lines)) + 1.3 for _l, _a, _h, lines in forms)
    link_h = 4.6
    low_h = PAD + step(T) + 1.6 + sum(row_h) + 0.8 + step(6.8) + 1.0 + forms_h + PAD - 1.3
    ytop = 1.0 + top_h + link_h + low_h + 1.0
    H_IN = ytop * U / 72

    fig = plt.figure(figsize=(W_IN, H_IN))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, ytop)
    ax.axis('off')

    def box(x0, y0, w, h, ec=MUTED, fc='white', lw=0.8):
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle='round,pad=0,rounding_size=1.2', fc=fc, ec=ec,
                                    lw=lw, zorder=1))

    def lines_at(x, y, lines, size, mono=False, color=INK, weight='normal', style='normal'):
        for ln in lines:
            ax.text(x, y, ln, ha='left', va='top', fontsize=size, family=MONO if mono else None, color=color,
                    fontweight=weight, style=style)
            y -= step(size)
        return y

    def arrow(x0, y0, x1, y1, color=INK2):
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=1.0, shrinkA=0, shrinkB=0))

    # the four steps
    top = ytop - 1.0
    for (x, w), (title, ec, fc, blocks, foot) in zip(cols, boxes):
        box(x, top - top_h, w, top_h, ec=ec, fc=fc, lw=1.0 if ec == blue else 0.8)
        y = lines_at(x + PAD, top - PAD, [title], T, weight='bold') - 1.0
        for lines, size, mono, color, weight, style, after in blocks:
            y = lines_at(x + PAD, y, lines, size, mono, color, weight, style) - after
        if foot:
            lines, size, mono, color, weight, style, _after = foot
            lines_at(x + PAD, top - top_h + PAD - 0.4 + len(lines) * step(size), lines, size, mono, color, weight,
                     style)
    ymid = top - top_h / 2
    for (xa, wa), (xb, _) in zip(cols, cols[1:]):
        arrow(xa + wa + 0.4, ymid, xb - 0.4, ymid)

    # the message, by condition: what each one holds, then some of them as stored
    by, bh = 1.0, low_h
    box(1.0, by, 98.0, bh, ec=blue, lw=1.0)
    xc = cols[1][0] + cols[1][1] / 2
    arrow(xc, top - top_h, xc, by + bh + 0.2, color=blue)
    y = by + bh - PAD
    ax.text(1.0 + PAD, y, 'The added message, by condition', ha='left', va='top', fontsize=T, fontweight='bold',
            color=INK)
    ax.text(99.0 - PAD, y - 0.25, 'blue: the list gives line numbers', ha='right', va='top', fontsize=7.2, color=blue)
    y -= step(T) + 1.6
    for row, rh in zip(rows, row_h):
        for j, (name, lines) in enumerate(row):
            xx = 1.0 + PAD + j * cell_w
            yy = lines_at(xx, y, [name], BS, weight='bold', color=blue if name in LINE_NUMBERS else INK)
            lines_at(xx, yy, lines, BS, color=INK2)
        y -= rh
    y -= 0.8
    ax.plot([1.0 + PAD, 99.0 - PAD], [y + 0.5, y + 0.5], color=RULE_LIGHT, lw=0.6)
    ax.text(1.0 + PAD, y - 0.2, f'{WORD[len(forms)].capitalize()} of them, as this paused step stores them (the first '
            'line is the same in every one):', ha='left', va='top', fontsize=6.8, color=INK2, style='italic')
    y -= step(6.8) + 1.0
    for label, accent, head, lines in forms:
        ax.text(1.0 + PAD, y, label, ha='left', va='top', fontsize=BS, fontweight='bold', color=blue if accent else INK)
        yy = lines_at(1.0 + PAD + label_w, y - (BS - ES) * 0.8 / U, [head], ES, mono=True, color=MUTED)
        lines_at(1.0 + PAD + label_w, yy, lines, ES, mono=True, color=INK)
        y -= step(ES) * (1 + len(lines)) + 1.3
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_design.{ext}', dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------- main
def load_all(run_dirs):
    """Every run that exists, with the registered code path of its experiment: {tag: its rates, contrasts, counts}."""
    exps = {'B': exp_b()}
    for tag, d in run_dirs.items():
        rows_path = Path(d) / ROWS_FILE[tag]
        if not rows_path.exists():
            where = rows_path.relative_to(ROOT).as_posix() if rows_path.is_relative_to(ROOT) else rows_path
            print(f'not drawn: {EXP_NAME[tag]} (no {where} yet)')
            continue
        e = LOADERS[tag](d, run_dirs[REFERENCE[tag]]) if tag in REFERENCE else LOADERS[tag](d)
        exps[tag] = e
        tag_ex = ' [EXPLORATORY: fewer than 200 complete states]' if e['n_complete'] < MIN_COMPLETE else ''
        print(f'{EXP_NAME[tag]}: {e["n_rows"]} replays, {e["n_complete"]} complete states{tag_ex}')
    return exps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', nargs=2, action='append', default=[], metavar=('TAG', 'RUN_DIR'),
                    help=f'override the run directory of one later run; TAG is one of {", ".join(RUN_DIRS)}')
    ap.add_argument('--table', default=str(TABLE_JSON), help='the data file of every registered rule (checked and '
                    'tallied; drawn only with --full-table)')
    ap.add_argument('--digest', default=str(DIGEST_JSON), help='the data file of Table 2 (the digest of the rules)')
    ap.add_argument('--samples', default=str(SAMPLES_JSON), help='the data file of Table 1 (the samples)')
    ap.add_argument('--full-table', action='store_true', help='also draw every registered rule, as table_rules_full')
    ap.add_argument('--example', default=None, help='paused step for fig_design as task,run,fork (default: the first)')
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

    exps = load_all(run_dirs)

    ck = Checks()
    check_b(exps['B'], ck)
    for tag in RUN_DIRS:
        if tag in exps:
            check_later(tag, exps[tag], ck)
    check_by_task(exps, ck)
    comp = checkable(exps)
    raw, spec, typed, notes = {}, {}, [], []
    names = {'full': Path(args.table).name, 'digest': Path(args.digest).name, 'samples': Path(args.samples).name}
    for kind, path in (('full', args.table), ('digest', args.digest), ('samples', args.samples)):
        with open(path, encoding='utf-8') as f:
            raw[kind] = json.load(f)
        spec[kind], typed_values, said = prepare_table(raw[kind], names[kind], comp)
        typed += [(names[kind], *t) for t in typed_values]
        notes += said
    check_table(spec['full'], exps, ck, f'{names["full"]} (every registered rule)')
    check_table(spec['digest'], exps, ck, f'{names["digest"]} (Table 2)')
    print('Checks (plotted values and the estimates of the tables against the registered outputs):')
    n_ok = sum(1 for l in ck.lines if l.endswith(' match'))
    print('\n'.join(l for l in ck.lines if args.verbose or not l.endswith(' match')))
    print(f'  {n_ok} values match their registered output' + ('' if args.verbose else ' (--verbose lists each)'))
    if ck.bad:
        raise SystemExit(f'check failed for {ck.bad}; no figure saved')
    print('  all checks passed')
    count, line = tally([row for _t, row in rule_rows(spec['full'])])
    print(f'  {names["full"]}, every registered rule, counted as Appendix A counts them: {line}')
    in_digest = [row for _t, row in rule_rows(spec['digest'])]
    print(f'  {names["digest"]}, Table 2: {tally(in_digest, tuple(spec["digest"].get("outcomes", OUTCOMES)))[1]}')
    said_rules = re.search(r'(\d+) registered rules', spec['digest'].get('note', ''))
    if said_rules and int(said_rules.group(1)) != sum(count.values()):      # the digest's note against the full list
        raise SystemExit(f'the note of {names["digest"]} says {said_rules.group(1)} registered rules and '
                         f'{names["full"]} counts {sum(count.values())}; no figure saved')
    for note in notes:
        print(f'  NOTE: {note}')
    lint = (table_lint(raw['digest'], f'{names["digest"]} (Table 2)')
            + table_lint(raw['samples'], f'{names["samples"]} (Table 1)'))
    if typed or lint:
        print('  Numbers of the tables that are typed, not read from a report:')
        for name, key, value, source in typed:
            print(f'    {name}: {key} = {value} (source: {source})')
        print('\n'.join(lint))

    fig_results(exps, out_dir)
    fig_extensions(exps, out_dir, which=('a',))
    fig_extensions(exps, out_dir, which=('b', 'c'), name='fig_appendix')
    tables = fig_table(spec['digest'], out_dir, 'table_rules') + fig_table(spec['samples'], out_dir, 'table_samples')
    if args.full_table:
        full = fig_table(spec['full'], out_dir, 'table_rules_full')
        if len(full) > 1:
            print(f'  the full list has more than {MAX_ROWS} rows and is drawn as two images: {full[0]} and {full[1]}')
        tables += full
    key = None
    if args.example:
        t, r, f = args.example.split(',')
        key = (t, int(r) if r.isdigit() else r, int(f))
    fig_design(key, exps, out_dir)
    print(f'wrote fig_design, fig_results, fig_extensions, fig_appendix, {", ".join(tables)} (.png and .svg) in '
          f'{out_dir}')


if __name__ == '__main__':
    main()
