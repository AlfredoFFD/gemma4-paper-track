"""Regenerate the paper's figures from the raw replay logs.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py \
        --run C analysis/fork_states_c/states.jsonl <run_dir> [<run_dir> ...] \
        --run D1 analysis/fork_states_d/states.jsonl <run_dir>

Writes fig_results.png/.svg and fig_design.png/.svg next to this script.

Every plotted number is computed here from the raw per-replay logs with the project's own analysis code:
the definitions (hit, opens_file, invalid_kind) are taken verbatim from analysis/rederive_s5.py, which in turn
imports the registered scorer (fork_states.touches, valid_call); the intervals come from the frozen bootstrap of the
paper's table, analysis/analyze_forks.boot_ci, fed per-state lists in analyze_b.py's state order.
rederive_s5.py does all of its work at module level and rewrites analysis/results/rederive_s5.txt when run, so it
is not imported or run: its source is parsed and only its imports, constants and function definitions are
executed (load_rederive_defs). The loader below is the minimum copy of its loading block, generalized to take a
states file and run directories. Before anything is saved, the experiment B values are checked against the
registered values and against the intervals printed in analysis/results/rederive_s5.txt (sections S1 and S3).

Arms from later runs (Ep, EL, ES from experiment C; PE from experiment D) are already listed in ARM_SPECS. They
are drawn only when their run is passed with --run; each such run is scored on its own states file and its own
complete states (every arm of that run, every seed, valid), never pooled with experiment B.
"""
import argparse
import ast
import collections
import json
import re
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

FIG = Path(__file__).resolve().parent
ROOT = FIG.parents[1]
ANALYSIS = ROOT / 'analysis'
REDERIVE = ANALYSIS / 'rederive_s5.py'
REDERIVE_TXT = ANALYSIS / 'results' / 'rederive_s5.txt'
B_STATES = ANALYSIS / 'fork_states' / 'states.jsonl'
B_RUNS = [ANALYSIS / 'results' / v for v in ('v5', 'v6', 'v8')]

# Registered experiment B values (percent of replays), checked before any figure is saved.
REGISTERED = {('A', 's1'): 2.15, ('P', 's1'): 3.01, ('H', 's1'): 2.75, ('D', 's1'): 4.30, ('E', 's1'): 8.25,
              ('RD', 'rew'): 0.52, ('RE', 'rew'): 1.03}
# Registered 95% intervals of the paper's table (frozen bootstrap, analyze_forks.boot_ci), asserted before saving.
REGISTERED_CI = {('A', 's1'): (0.86, 3.61), ('P', 's1'): (1.55, 4.64), ('H', 's1'): (1.37, 4.30),
                 ('D', 's1'): (2.58, 6.10), ('E', 's1'): (5.76, 10.91), ('RD', 'rew'): (0.00, 1.29),
                 ('RE', 'rew'): (0.34, 1.89)}

# ---------------------------------------------------------------- style
INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
COLORS = {
    'none': '#c6c6c6',      # nothing added
    'bare': '#8e8e8e',      # bare-name arms (P, H, D)
    'legible': '#1f6fb4',   # the legible arm E (the one accent)
    'partial': '#8fb5dc',   # later partial-legible variants (EL, ES, Ep, PE), a tint of the accent
    'rewired': '#c47a3d',   # rewired controls (R_D, R_E)
}
TINT = {k: v for k, v in {'none': '#e6e6e6', 'bare': '#d2d2d2', 'legible': '#a9c8e6',
                          'partial': '#cfe0f0', 'rewired': '#e6c3a5'}.items()}

# One spec per plotted arm. src 'B' = experiment B (always loaded); any other src is drawn only when a run with
# that tag is passed with --run. field: 's1' any unopened true neighbor touched; 'rew' any rewired entry touched.
# section: bars are grouped by section, with a gap and a small header between sections. mech: also in panel (b).
ARM_SPECS = [
    dict(arm='A', src='B', field='s1', group='none', section='true', mech=True, label='nothing added'),
    dict(arm='P', src='B', field='s1', group='bare', section='true', label='tool result, bare names'),
    dict(arm='H', src='B', field='s1', group='bare', section='true', mech=True, label='note, bare names'),
    dict(arm='D', src='B', field='s1', group='bare', section='true', mech=True, label='instruction, bare names'),
    dict(arm='E', src='B', field='s1', group='legible', section='true', mech=True,
         label='note, names + file + lines + first line'),
    # experiment C (pre-registration 04): notes in H's wording, scored in the C run only
    dict(arm='EL', src='C', field='s1', group='partial', section='C', label='note, names + file + lines'),
    dict(arm='ES', src='C', field='s1', group='partial', section='C', label='note, names + first line'),
    dict(arm='Ep', src='C', field='s1', group='partial', section='C',
         label='note with locations, decoy swapped in'),
    # experiment D (pre-registration 05), D1: the legible list as the tool's own result
    dict(arm='PE', src='D1', field='s1', group='partial', section='D1',
         label='tool result, names + file + lines + first line'),
    dict(arm='RD', src='B', field='rew', group='rewired', section='rewired', label='instruction, rewired list',
         code='R$_D$'),
    dict(arm='RE', src='B', field='rew', group='rewired', section='rewired', label='note with locations, rewired list',
         code='R$_E$'),
]
SECTION_HEADERS = {
    'true': 'true list: any unopened true neighbor touched',
    'C': 'experiment C run: any unopened true neighbor touched',
    'D1': 'experiment D run: any unopened true neighbor touched',
    'rewired': 'rewired list: any rewired entry touched',
}
SECTION_ORDER = ['true', 'C', 'D1', 'rewired']

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK, 'xtick.major.width': 0.6, 'ytick.major.size': 0,
    'mathtext.default': 'regular', 'svg.fonttype': 'none', 'savefig.facecolor': 'white',
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
})
MONO = 'DejaVu Sans Mono'


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
from analyze_forks import boot_ci  # noqa: E402  frozen bootstrap (analysis/ is on sys.path via rederive_s5's imports)


def results_files(run_dir):
    run_dir = Path(run_dir)
    for p in (run_dir / 'forks' / 'results.jsonl', run_dir / 'results.jsonl'):
        if p.exists():
            return p
    raise FileNotFoundError(f'no results.jsonl under {run_dir}')


def load_source(states_path, run_dirs, arms=None):
    """Minimum copy of rederive_s5.py's loading block: states, valid replays, complete states.

    arms=None takes the arms present in the run's rows (later runs); experiment B passes rederive_s5.ARMS.
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


def rate(recs, arm, field):
    """(rate %, lo %, hi %, n) with the frozen bootstrap analyze_forks.boot_ci (Python's random, seed 0, 2,000
    resamples, clusters = states).

    boot_ci draws clusters in the order of its dict, so the per-state lists are built in the order analyze_b.py
    builds them: states in order of first appearance among the valid rows read v5, v6, v8. load_source keeps that
    order in `complete` and score() walks it, so recs are already in that order.
    """
    by_state = {}
    for r in recs:
        if r['arm'] == arm:
            by_state.setdefault(r['key'], []).append(int(r[field]))
    p, lo, hi = boot_ci(by_state)
    return 100 * p, 100 * lo, 100 * hi, sum(len(v) for v in by_state.values())


# ---------------------------------------------------------------- checks against the registered numbers
def printed_rates():
    """Parse S1 ('any unopened true neighbor', 'any rewired entry') and S3 rate lines of rederive_s5.txt."""
    blocks = {'s1': 'any unopened true neighbor touched', 'rew': 'any rewired entry touched',
              'opened': 'S3. File level'}
    txt = REDERIVE_TXT.read_text(encoding='utf-8').splitlines()
    pat = re.compile(r'^\s{4}(\w+)\s+([\d.]+)% \[([\d.]+), ([\d.]+)\] \(n=(\d+)\)')
    got = {}
    for field, head in blocks.items():
        i = next(j for j, l in enumerate(txt) if head in l) + 1
        while i < len(txt) and (m := pat.match(txt[i])):
            got[(m.group(1), field)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)), int(m.group(5)))
            i += 1
    return got


def check(values):
    """values: {(arm, field): (rate, lo, hi, n)} for experiment B. Raises before anything is saved."""
    printed = printed_rates()
    lines, bad = [], []
    for k, v in sorted(values.items()):
        # the point estimate and n must equal the re-derivation's (its intervals come from another bootstrap)
        p = printed.get(k)
        ok_p = p is not None and abs(v[0] - p[0]) <= 0.005 and v[3] == p[3]
        reg, ci = REGISTERED.get(k), REGISTERED_CI.get(k)
        ok_r = reg is None or round(v[0], 2) == reg
        ok_ci = ci is None or (abs(v[1] - ci[0]) <= 0.005 and abs(v[2] - ci[1]) <= 0.005)
        lines.append(f'  {k[0]:3s} {k[1]:6s} {v[0]:6.2f}% [{v[1]:.4f}, {v[2]:.4f}] n={v[3]}'
                     f'  point vs rederive_s5.txt {"match" if ok_p else "MISMATCH " + str(p)}'
                     + (f'; registered {reg:.2f} {"OK" if ok_r else "OFF"}' if reg is not None else '')
                     + (f'; registered CI [{ci[0]:.2f}, {ci[1]:.2f}] {"OK" if ok_ci else "OFF"}'
                        if ci is not None else ''))
        if not (ok_p and ok_r and ok_ci):
            bad.append(k)
    print('Checks (plotted vs printed and registered values):')
    print('\n'.join(lines))
    if bad:
        raise SystemExit(f'check failed for {bad}; no figure saved')
    print('  all checks passed')


# ---------------------------------------------------------------- figure 1: results
def _label(spec):
    code = spec.get('code', spec['arm'])
    return f'{spec["label"]}  ({code})'


def _bar(ax, y, v, color, h, show_ci=False):
    val, lo, hi, _ = v
    ax.barh(y, val, height=h, color=color, edgecolor='none', zorder=2)
    ax.errorbar(val, y, xerr=[[val - lo], [hi - val]], fmt='none', ecolor=INK, elinewidth=0.8,
                capsize=2.2, capthick=0.8, zorder=3)
    t = ax.text(hi + 0.25, y, f'{val:.2f}', va='center', ha='left', fontsize=8.5, color=INK, zorder=4)
    if show_ci:   # the interval, small and grey, right after the value
        ax.annotate(f' [{lo:.2f}, {hi:.2f}]', xy=(1, 0.5), xycoords=t, va='center', ha='left', fontsize=7,
                    color=MUTED, zorder=4)


def fig_results(values, specs, out_dir):
    # rows of panel (a): sections in order, a gap row (with a header) before each section
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
        _bar(ax_a, y, values[(s['arm'], s['field'], s['src'])], COLORS[s['group']], 0.62, show_ci=True)
        ticks.append(y)
        ticklabels.append(_label(s))
        y -= 1.0
    ax_a.set_ylim(y + 0.45, 0.1)
    ax_a.set_yticks(ticks, ticklabels)
    for t, s in zip(ax_a.get_yticklabels(), [p for k, p in rows if k == 'bar']):
        if s['group'] == 'legible':
            t.set_fontweight('bold')

    # panel (b): two bars per arm, file opened (tint) and the neighbor's own lines read (full color)
    # panel (b) colors by measure: light = file opened, full = own lines read; the legible arms keep the accent
    ticks_b = []
    for i, s in enumerate(mech):
        yc = -i * 1.0
        g = s['group'] if s['group'] in ('legible', 'partial') else 'bare'
        _bar(ax_b, yc + 0.19, values[(s['arm'], 'opened', s['src'])], TINT[g], 0.36)
        _bar(ax_b, yc - 0.19, values[(s['arm'], 's1', s['src'])], COLORS[g], 0.36)
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


# ---------------------------------------------------------------- figure 2: design
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
    ap.add_argument('--run', nargs='+', action='append', default=[], metavar='TAG STATES RUN_DIR',
                    help='a later run: its tag (as in ARM_SPECS src), its states file, one or more run directories')
    ap.add_argument('--example', default=None, help='state for fig_design as task,run,fork (default: first state)')
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = {'B': (B_STATES, B_RUNS, R['ARMS'])}
    for spec in args.run:
        if len(spec) < 3:
            ap.error('--run needs TAG STATES RUN_DIR [RUN_DIR ...]')
        sources[spec[0]] = (Path(spec[1]), [Path(p) for p in spec[2:]], None)

    values, info = {}, {}
    for tag, (st_path, dirs, arms) in sources.items():
        states, complete, seeds = load_source(st_path, dirs, arms)
        recs = score(states, complete)
        info[tag] = (len(states), len(complete), len(arms or {r['arm'] for r in recs}), seeds)
        print(f'source {tag}: {len(complete)} complete states, seeds {seeds}, {len(recs)} replays')
        present = {r['arm'] for r in recs}
        for s in ARM_SPECS:
            if s['src'] == tag and s['arm'] in present:
                for field in {s['field'], 'opened', 's1'}:
                    values[(s['arm'], field, tag)] = rate(recs, s['arm'], field)
    specs = [s for s in ARM_SPECS if (s['arm'], s['field'], s['src']) in values]
    skipped = [s['arm'] for s in ARM_SPECS if s not in specs]
    if skipped:
        print(f'not drawn (run not given): {skipped}')

    check({(a, f): v for (a, f, t), v in values.items() if t == 'B'})

    fig_results(values, specs, out_dir)
    key = None
    if args.example:
        t, r, f = args.example.split(',')
        key = (t, int(r) if r.isdigit() else r, int(f))
    fig_design(pick_example(B_STATES, key), *info['B'], out_dir)
    print(f'wrote {out_dir / "fig_results.png"}, {out_dir / "fig_design.png"} (+ .svg)')


if __name__ == '__main__':
    main()
