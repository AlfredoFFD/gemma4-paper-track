"""Figures of the rebuilt paper: models, asked against told, what an edge is, where reads start, told where the fix is.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures_v2.py [--out <dir>] [--r22 <file>]

Writes, next to this script (or into --out), each as .png (200 dpi) and .svg:
  fig_models      a name against an address, and a search with and without its line numbers, by model (eleven models)
  fig_asked_told  a line the agent was told is used, less often than one it asked for
  fig_graph       what an edge of the code graph is
  fig_moves       (a) a fix in one file and in several; (b) the regions a run was never shown, within one call edge of
                  code it was shown (true and rewired graphs) or of a text search by name
  fig_oracle      told where the fix is: (a) resolved, first seed (18) and second seed (22); (b) where the first read
                  of a file of the note starts; (c) lines read per run (b and c: second seed, exploratory). Without
                  analyze_22.txt, the earlier one-seed drawing (shown every region, patch overlaps, resolved)
  table_rules_v2  the registered rules of the rebuilt paper: rule, estimate, outcome (the drawing of make_figures.py's
                  table of rules, copied); the wording of the rules and outcomes is text in TABLE_ROWS, every estimate
                  is read from the report its row names; private/table1-rows-nov11.md, when present, is only compared

Every number drawn is parsed from a stored output; when a line cannot be found the script stops with an error and
draws nothing from a fallback. The sources:
  analysis/results/19/analyze_19.txt         seven hosted models, designs 10 and 17 (the table at its top)
  analysis/results/analyze_b.txt             Gemma-4-31B, pre-registration 03, rule B3 (its registered report; the
                                             digest paper/figures/rules_main.json holds no number for B3, only the key
                                             of a check, so the estimate is read from the report)
  analysis/results/15/analyze_15.txt         Gemma-4-31B, pre-registration 15, rule Q1
  analysis/results/20/analyze_20.txt         pre-registration 20: section 2 (USES THE LINE per arm), checked against
                                             the counts of section 3
  analysis/results/explore_graph_names.txt   the code graphs read as text (exploratory)
  analysis/results/explore_graph_ambiguity.txt  part A, the short names a search returns (fig_graph), exploratory
  analysis/results/explore_read_starts.txt   the public runs (sections 1 and 3; table_populations), exploratory
  analysis/results/explore_independence.txt  a fix in one file and in several (fig_moves a); rederive_independence.txt
                                             the same count by a second script
  analysis/results/public/locality_null.txt  part 1, the true graph and three rewired graphs (fig_moves b), exploratory
  analysis/results/public/lexical_reach.txt  section 1-5, a text search by name (fig_moves b), exploratory
  analysis/results/public/lexical_reach_both.txt  section 1, a name search in both directions (fig_moves b), exploratory
  analysis/results/explore_cluster_bootstrap.txt  its last line: addresses minus names by task (table_rules_v2)
  analysis/results/rederive_18.txt           pre-registration 18, shown every changed region (every call paired with
                                             its result)
  analysis/results/18/analyze_18.txt         pre-registration 18, final patch overlaps a changed region, resolved
Optional, drawn when it exists (the script works without it):
  analysis/results/22/analyze_22.txt         pre-registration 22, seed 3, four arms (sections 1 to 3); --r22 reads another
                                             file of the same format instead (for a test on the stand-in output)
  analysis/results/explore_reach_22.txt      part 7, first reads of a file of the note per arm (fig_oracle b);
                                             required when analyze_22.txt exists
  analysis/results/22/explore_cost_22.txt    LINES READ per run (section 1) and paired differences (section 2)
                                             (fig_oracle c); required when analyze_22.txt exists
The only typed numbers are the two estimates the brief gives for Gemma-4-31B (TYPED below): they are not drawn, they
are compared with the numbers parsed from the reports, and a difference stops the script.
At the end the script prints every parsed number with its file and line.
"""
import argparse
import json
import os
import re
import functools
import textwrap
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

FIG = Path(__file__).resolve().parent
ROOT = FIG.parents[1]
RES = ROOT / 'analysis' / 'results'
R19 = RES / '19' / 'analyze_19.txt'
R03 = RES / 'analyze_b.txt'
R15 = RES / '15' / 'analyze_15.txt'
R20 = RES / '20' / 'analyze_20.txt'
GRAPH = RES / 'explore_graph_names.txt'
AMBIG = RES / 'explore_graph_ambiguity.txt'
STARTS = RES / 'explore_read_starts.txt'
RED18 = RES / 'rederive_18.txt'
R18 = RES / '18' / 'analyze_18.txt'
R22 = RES / '22' / 'analyze_22.txt'          # optional
REACH22 = RES / 'explore_reach_22.txt'        # required when R22 exists (fig_oracle b)
COST22 = RES / '22' / 'explore_cost_22.txt'   # required when R22 exists (fig_oracle c)
RED22 = RES / 'rederive_22.txt'               # required when R22 exists (fig_oracle a, the first seed on 22's tasks)

# Typed, from the registered reports, only to check the parsed values (never drawn):
TYPED = {
    'B3': ('+5.50', '3.44', '7.65'),     # analysis/results/analyze_b.txt, line "  B3: 0.0550 [0.0344, 0.0765]"
    'Q1': ('+56.67', '45.00', '69.44'),  # analysis/results/15/analyze_15.txt, line "  Q1, Y1 under S minus ..."
    'S1': ('+5.60', '3.76', '7.77'),     # analysis/results/g/analyze_g.txt, line "  S1 E - H: +5.60 [+3.76, +7.77]"
    'B1': ('+1.55', '0.60', '2.66'),     # analysis/results/analyze_b.txt, line "  B1: 0.0155 [0.0060, 0.0266]"
}
R08 = RES / 'g' / 'analyze_g.txt'     # pre-registration 08, rule S1 (one step on the newest wheels)
RUNS_PER_ARM = 103   # typed, from the brief, only to check the task results of 14 (NAF) and 23 (PH, PE): never drawn

# ---------------------------------------------------------------- style (as make_figures.py, make_fig_runs.py)
INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
PALE, GREY, DARK = '#c6c6c6', '#8e8e8e', '#5f5f5f'
LIGHT, BLUE = '#8fb5dc', '#1f6fb4'
GRID, HAIR = '#ececec', '#e4e4e4'
MINUS = '−'
W_IN = 7.0
DPI = 200
WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven', 8: 'eight', 9: 'nine'}

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK2, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
})

PARSED = []      # (figure, quantity, value, file, line)
wrap = functools.partial(textwrap.wrap, break_on_hyphens=False)   # never split pre-registration


def rel(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def stop(msg):
    raise SystemExit(f'make_figures_v2: {msg}')


class Source:
    """A stored output, read as lines; every search reports the line it found."""

    def __init__(self, path):
        path = Path(path)
        if not path.exists():
            stop(f'{rel(path)} is missing')
        self.path = path
        self.lines = path.read_text(encoding='utf-8').splitlines()

    def find(self, pattern, what, lo=0, hi=None):
        """(match, 1-based line number) of the first line in [lo, hi) (0-based indices) that matches."""
        rx = re.compile(pattern)
        for i in range(lo, len(self.lines) if hi is None else hi):
            m = rx.search(self.lines[i])
            if m:
                return m, i + 1
        stop(f'no line for {what} in {rel(self.path)}')

    def block(self, head, what, end=r'^\S', lo=0, hi=None):
        """0-based [start, stop) of the lines under the first line matching `head` (from lo), up to the next line
        matching `end` (by default the next line that does not start with a blank)."""
        _m, n = self.find(head, what, lo, hi)
        stop_at = len(self.lines) if hi is None else hi
        for j in range(n, stop_at):
            if re.search(end, self.lines[j]):
                return n, j
        return n, stop_at

    def record(self, fig, quantity, value, line):
        PARSED.append((fig, quantity, value, rel(self.path), line))


def num(s):
    return s.replace('-', MINUS)


def interval_text(point, lo, hi):
    """'+5.50 [3.44, 7.65]' from three printed strings (a minus sign where a value is negative)."""
    point = point if point[0] in '+-' else '+' + point
    return f'{num(point)} [{num(lo.lstrip("+"))}, {num(hi.lstrip("+"))}]'


def page_of(h_in):
    fig = plt.figure(figsize=(W_IN, h_in))
    page = fig.add_axes([0, 0, 1, 1])              # the whole page, in inches from the top left
    page.set_xlim(0, W_IN)
    page.set_ylim(h_in, 0)
    page.axis('off')
    return fig, page


def axes_at(fig, x0, x1, y0, y1):
    """Axes from x0 to x1 and y0 (top) to y1 (bottom), in inches from the top left of the page."""
    h_in = fig.get_figheight()
    ax = fig.add_axes([x0 / W_IN, 1 - y1 / h_in, (x1 - x0) / W_IN, (y1 - y0) / h_in])
    ax.set_facecolor('none')
    return ax


def check_fits(fig, page, name):
    """Stop when any text of the page runs past its edges (clipped text)."""
    fig.canvas.draw()                      # lays out the axis labels and ticks
    renderer = fig.canvas.get_renderer()
    w, h = fig.get_figwidth() * fig.dpi, fig.get_figheight() * fig.dpi
    for ax in fig.axes:
        drawn = [ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() if ax.axison else []
        for t in ax.texts + drawn:
            if not t.get_text() or not t.get_visible():
                continue
            bb = t.get_window_extent(renderer)
            if bb.x0 < -0.5 or bb.y0 < -0.5 or bb.x1 > w + 0.5 or bb.y1 > h + 0.5:
                stop(f'{name}: the text "{t.get_text()[:40]}" runs past the edge of the figure')


def save(fig, page, out, name):
    check_fits(fig, page, name)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'{name}.{ext}', dpi=DPI)
    plt.close(fig)


def width_in(fig, t):
    return t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi


# ================================================================ fig_models
HOSTED = (  # short label, a token of the model's name in analyze_19.txt
    # the same short names as fig_asked_told (HOSTED24)
    ('Qwen3-30B', 'qwen3-30b-a3b'), ('Qwen3-235B', 'qwen3-235b-a22b'), ('gpt-oss-120b', 'gpt-oss-120b'),
    ('DeepSeek-V4.1', 'deepseek-v4.1-flash'), ('GLM-5.3', 'glm-5.3-flash'),
    ('MiniMax-M3.1', 'minimax-m3.1-flash'), ('Nemotron-3', 'nemotron-3-super-120b'),
)
# The models registered earlier, on a rented GPU: the report of rule M1 (addresses minus bare names) of each run, as
# make_figures.py reads them for fig_extensions (its run tags D2a, D2b, D2q); the first line of each report names its
# run directory, which is checked. Qwen2.5-Coder-32B's search contrast is rule Q1 of pre-registration 17.
EARLIER = (
    ('Gemma-4-26B-A4B', RES / 'd2_26b' / 'analyze_d2_26b.txt', 'analysis/results/d2_26b/forks', None),
    ('Gemma-4-E4B', RES / 'd2_e4b' / 'analyze_d2_e4b.txt', 'analysis/results/d2_e4b/forks', None),
    ('Qwen2.5-Coder-32B', RES / 'qwen' / 'analyze_d2_qwen.txt', 'analysis/results/qwen/forks',
     RES / '17' / 'analyze_17.txt'),
)
ROW19 = re.compile(r'^(\S+)\s+.+?\s+(10|17)\s+\d+\s+[\d.]+%\s+\w+\s+[\d.]+\s+\w+\s+[\d.]+\s+'
                   r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]\s+(V\d) (.+?)\s*$')
Q1 = r'^  Q1, Y1 under S minus Y1 under S0: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]'


def rule_q1(path, label):
    s = Source(path)
    m, line = s.find(Q1, f'rule Q1 ({label})')
    _v, vline = s.find(r'^  Q1 verdict: met', f'the verdict of Q1 ({label})')
    s.record('fig_models', f'right: {label}, rule Q1 (verdict met, line {vline})', interval_text(*m.groups()), line)
    return m.groups()


VERDICTS = {}     # (model, 'left' or 'right') -> the verdict its report prints (filled by parse_models)


@functools.lru_cache(maxsize=None)
def parse_models():
    """[(group label or None, [(model, left estimate, right estimate or None)])]; read once (the table uses it too)"""
    s19 = Source(R19)
    _m, end = s19.find(r'^Per run, details', 'the end of the table of analyze_19.txt')
    rows = {}
    for i in range(end - 1):
        m = ROW19.match(s19.lines[i])
        if not m:
            continue
        name, design = m.group(1), m.group(2)
        short = [lab for lab, tok in HOSTED if tok in name.lower()]
        if len(short) != 1:
            stop(f'analyze_19.txt, line {i + 1}: the model {name} matches {len(short)} short names')
        key = (short[0], design)
        if key in rows:
            stop(f'analyze_19.txt: two rows for {key}')
        rows[key] = dict(est=m.groups()[2:5], verdict=f'{m.group(6)} {m.group(7)}', line=i + 1, model=name)
        VERDICTS[(short[0], 'left' if design == '10' else 'right')] = m.group(7)
    for lab, _tok in HOSTED:
        for design in ('10', '17'):
            if (lab, design) not in rows:
                stop(f'analyze_19.txt: no row for {lab}, design {design}')
            r = rows[(lab, design)]
            s19.record('fig_models', f'{"left" if design == "10" else "right"}: {lab} ({r["model"]}, design {design}); '
                       f'{r["verdict"]}', interval_text(*r['est']), r['line'])
    if len(rows) != 2 * len(HOSTED):
        stop(f'analyze_19.txt: {len(rows)} rows, not {2 * len(HOSTED)}')
    # Gemma-4-31B: rule B3 of pre-registration 03 (fractions in the report: turned into points, exactly)
    s03 = Source(R03)
    m, line = s03.find(r'^  B3: (-?[\d.]+) \[(-?[\d.]+), (-?[\d.]+)\]', 'rule B3')
    b3 = tuple(f'{Decimal(g) * 100:.2f}' for g in m.groups())
    b3 = ('+' + b3[0] if not b3[0].startswith('-') else b3[0], b3[1], b3[2])
    s03.record('fig_models', 'left: Gemma-4-31B, rule B3 (fractions x 100)', interval_text(*b3), line)
    q1 = rule_q1(R15, 'Gemma-4-31B')
    for k, got in (('B3', b3), ('Q1', q1)):
        if interval_text(*got) != interval_text(*TYPED[k]):
            stop(f'{k}: the report prints {interval_text(*got)}, the brief types {interval_text(*TYPED[k])}')
    earlier = []
    for lab, path, run_dir, q_path in EARLIER:
        s = Source(path)
        _h, hline = s.find(rf'^experiment D2: \d+ replays of arms .* in {re.escape(run_dir)}$',
                           f'the run directory {run_dir} on the first line')
        if hline != 1:
            stop(f'{rel(path)}: the run directory is not named on its first line')
        m, line = s.find(r'^  M1 E - H 95%: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]: (\w+)', f'rule M1 ({lab})')
        s.record('fig_models', f'left: {lab}, rule M1 E - H ({m.group(4)})', interval_text(*m.groups()[:3]), line)
        VERDICTS[(lab, 'left')] = 'met' if m.group(4) == 'PASS' else m.group(4)
        earlier.append((lab, m.groups()[:3], rule_q1(q_path, lab) if q_path else None))
        if q_path:
            VERDICTS[(lab, 'right')] = 'met'       # rule_q1 stops unless its report says "Q1 verdict: met"
    return [(None, [('Gemma-4-31B', b3, q1)]),
            ('registered earlier (rented GPU)', earlier),
            ('pre-registration 19 (hosted API)', [(lab, rows[(lab, '10')]['est'], rows[(lab, '17')]['est'])
                                                  for lab, _t in HOSTED])]


def nice_step(span):
    for step in (2, 5, 10, 20, 25, 50):
        if span / step <= 6:
            return step
    return 100


def fig_models(out):
    groups = parse_models()
    TOP, HEAD, ROW, GROUP_H, AXIS = 0.42, 0.50, 0.245, 0.24, 0.66
    LAB_R = 1.58
    A1, T1 = (1.70, 3.10), 3.17
    A2, T2 = (4.36, 5.64), 5.71
    # vertical layout, in inches below the top of the rows: a group label takes GROUP_H, a row ROW
    layout, y = [], 0.0
    for glabel, rows in groups:
        if glabel:
            layout.append(('group', glabel, y))
            y += GROUP_H
        for r in rows:
            layout.append(('row', r, y + ROW / 2))
            y += ROW
    rows_h = y + 0.03
    n_models = sum(len(rows) for _g, rows in groups)
    if n_models != 11:
        stop(f'fig_models: {n_models} models, not eleven')
    note = wrap(
        'Gemma-4-31B: pre-registrations 03 and 15. Registered earlier: Gemma-4-26B-A4B and Gemma-4-E4B, '
        'pre-registration 05; Qwen2.5-Coder-32B, pre-registrations 10 (left) and 17 (right). Hosted API: '
        'pre-registration 19. The other models replay Gemma-4-31B\'s recorded steps. Intervals: 95% bootstrap by '
        'paused step.', 128)
    h_in = TOP + HEAD + rows_h + AXIS + 0.13 * len(note) + 0.10
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'A name against an address, and a search with and without its line numbers, by model',
              ha='left', va='top', fontsize=10.5, color=INK)
    y0 = TOP + HEAD
    for side, ((a0, a1), tx, head, sub, xlabel) in enumerate((
            (A1, T1, 'A name against an address', 'addresses minus bare names',
             'points of replays whose next call\nreads a neighbor\'s code'),
            (A2, T2, 'A search, with and without line numbers', 'with minus without',
             'points of replays whose next call\nreads a hit file past line 1'))):
        page.text(a0, TOP + 0.08, head, ha='left', va='top', fontsize=9.0, color=INK)
        page.text(a0, TOP + 0.27, sub, ha='left', va='top', fontsize=7.8, color=INK2)
        ax = axes_at(fig, a0, a1, y0, y0 + rows_h)
        vals = [r[1 + side] for kind, r, _y in layout if kind == 'row' and r[1 + side] is not None]
        lo = min(0.0, min(float(v[1]) for v in vals))
        hi = max(float(v[2]) for v in vals)
        step = nice_step(hi - lo)
        xmin = step * (int(lo // step)) if lo < 0 else 0
        xmax = step * (int(hi // step) + 1)
        ax.set_xlim(xmin - 0.04 * (xmax - xmin), xmax + 0.02 * (xmax - xmin))
        ax.set_ylim(rows_h, 0)
        ticks = [v for v in range(int(xmin), int(xmax) + 1, step)]
        for v in ticks:
            ax.plot([v, v], [0.02, rows_h], color=MUTED if v == 0 else GRID, lw=0.8 if v == 0 else 0.6, zorder=1)
        for kind, r, yc in layout:
            if kind != 'row':
                continue
            est = r[1 + side]
            first = r[0] == 'Gemma-4-31B'
            if est is None:      # a model this contrast was not run on: the row stays, and says so
                page.text(tx, y0 + yc, 'not run', ha='left', va='center', fontsize=7.6, color=MUTED, style='italic')
                continue
            p, l, h = (float(x) for x in est)
            col = INK if first else GREY
            ax.plot([l, h], [yc, yc], color=col, lw=1.3 if first else 1.0, solid_capstyle='butt', zorder=2)
            for v in (l, h):
                ax.plot([v, v], [yc - 0.045, yc + 0.045], color=col, lw=0.9, zorder=2)
            ax.plot(p, yc, marker='s', ms=5.6 if first else 4.6, mfc=BLUE if first else DARK, mec='white', mew=0.5,
                    zorder=3)
            t = page.text(tx, y0 + yc, interval_text(*est), ha='left', va='center', fontsize=7.6,
                          color=INK if first else INK2, fontweight='bold' if first else 'normal')
            limit = A2[0] - 0.05 if side == 0 else W_IN - 0.04
            if tx + width_in(fig, t) > limit:
                stop(f'fig_models: the estimate "{t.get_text()}" runs into the next column')
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: '0' if abs(v) < 1e-9 else num(f'{v:+.0f}')))
        ax.set_yticks([])
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='x', labelsize=7.8, length=3)
        ax.set_xlabel(xlabel, fontsize=7.8, linespacing=1.25)
    for kind, r, yy in layout:
        if kind == 'group':      # a thin rule across the page, the group's small grey label under it
            page.plot([0.12, W_IN - 0.06], [y0 + yy + 0.035] * 2, color=HAIR, lw=0.7, zorder=0)
            page.text(0.12, y0 + yy + GROUP_H / 2 + 0.035, r, ha='left', va='center', fontsize=7.2, color=MUTED,
                      style='italic')
        else:
            page.text(LAB_R, y0 + yy, r[0], ha='right', va='center', fontsize=8.4, color=INK,
                      fontweight='bold' if r[0] == 'Gemma-4-31B' else 'normal')
    yn = y0 + rows_h + AXIS
    for i, line in enumerate(note):
        page.text(0.09, yn + 0.13 * i, line, ha='left', va='top', fontsize=6.9, color=MUTED)
    save(fig, page, out, 'fig_models')


# ================================================================ fig_asked_told
ARMS20 = (('NONE', 'nothing added', PALE), ('TOLDX', 'told the hits of another search', GREY),
          ('TOLD', 'told the hits its own search would return', LIGHT), ('ASKED', 'it searched itself', BLUE))


def parse_asked_told():
    s = Source(R20)
    lo, hi = s.block(r'^2\. Rates', 'section 2 of analyze_20.txt', end=r'^\d\. ')
    d_lo, d_hi = s.block(r'^3\. Descriptive', 'section 3 of analyze_20.txt', end=r'^\S')
    d_lo, d_hi = s.block(r'^\s+all:$', 'section 3, all states', end=r'^\s{2}\S', lo=d_lo)
    out = {}
    for arm, _label, _c in ARMS20:
        m, line = s.find(rf'^  arm {arm}\s+(\d+) states; USES THE LINE ([\d.]+) \[([\d.]+), ([\d.]+)\] \| (\d+)/(\d+);',
                         f'USES THE LINE, arm {arm}', lo, hi)
        states, rate, r_lo, r_hi, k, n = m.groups()
        md, dline = s.find(rf'^\s+arm {arm}\s+reads a noted file past line 1 (\d+) of (\d+) \(', f'section 3, arm {arm}',
                           d_lo, d_hi)
        if md.groups() != (k, n):
            stop(f'analyze_20.txt: arm {arm}: section 2 counts {k}/{n}, section 3 {md.group(1)} of {md.group(2)}')
        if int(n) % int(states):
            stop(f'analyze_20.txt: arm {arm}: {n} replays on {states} states')
        s.record('fig_asked_told', f'{arm}: USES THE LINE, % [95%] (count checked on line {dline})',
                 f'{rate} [{r_lo}, {r_hi}] | {k} of {n}, {states} states', line)
        out[arm] = dict(rate=float(rate), lo=float(r_lo), hi=float(r_hi), k=int(k), n=int(n), states=int(states))
    return out


R24 = RES / '24' / 'analyze_24.txt'
HOSTED24 = (  # short label, a token of the model's name in analyze_24.txt
    ('DeepSeek-V4.1', 'deepseek-v4.1'), ('MiniMax-M3.1', 'minimax-m3.1'), ('Nemotron-3', 'nemotron-3'),
    ('gpt-oss-120b', 'gpt-oss-120b'), ('Qwen3-235B', 'qwen3-235b'), ('Qwen3-30B', 'qwen3-30b'), ('GLM-5.3', 'glm-5.3'),
)
INTERVAL = r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\] \((\d+)\)'


@functools.lru_cache(maxsize=None)
def parse_24():
    """Pre-registration 24 (the design of 20 on seven hosted models; registered: the first line of its report, "BUILD,
    not registered", is stale, as a dated note in prereg/24 says). Per model: USES THE LINE under NONE, TOLD, ASKED
    (section 1); W1 and W2 with their verdicts (section 2); the counts and the reading of section 3. The reference row
    of Gemma-4-31B is read apart and not counted."""
    s = Source(R24)
    lo, hi = s.block(r'^1\. Rates by arm', 'section 1 of analyze_24.txt', end=r'^\d\. ')
    _h, hl = s.find(r'USES THE LINE, % of replays:\s+NONE\s+TOLD\s+ASKED\s+TOLDX \| SEARCHES:\s+NONE\s+TOLD\s*$',
                    'the column heads of section 1', lo, hi)
    rx1 = re.compile(r'^(\S+(?: \(pre-registration 20; refe)?)\s.*?\s(in|out) \([\d.]+% usable\) \|\s+([\d.]+)\s+([\d.]+)\s+'
                     r'([\d.]+)\s+([\d.]+) \|\s+[\d.]+\s+[\d.]+\s*$')
    models, ref = {}, None
    for i in range(hl, hi):
        m = rx1.match(s.lines[i])
        if not m:
            continue
        rates = dict(NONE=m.group(3), TOLD=m.group(4), ASKED=m.group(5))
        if m.group(1).startswith('Gemma-4-31B'):
            ref = dict(rates=rates, line=i + 1)
            continue
        short = [lab for lab, tok in HOSTED24 if tok in m.group(1).lower()]
        if len(short) != 1 or m.group(2) != 'in':
            stop(f'analyze_24.txt, line {i + 1}: {m.group(1)} matches {short}, gate {m.group(2)}')
        models[short[0]] = dict(name=m.group(1), rates=rates, line=i + 1)
        s.record('fig_asked_told', f'(b) {short[0]}: USES THE LINE % under NONE; TOLD; ASKED (heads line {hl})',
                 '; '.join(rates.values()), i + 1)
    if sorted(models) != sorted(lab for lab, _t in HOSTED24) or ref is None:
        stop(f'analyze_24.txt: section 1 has {sorted(models)}, reference {ref is not None}')
    lo, hi = s.block(r'^2\. Rules, one verdict per model', 'section 2 of analyze_24.txt', end=r'^\d\. ')
    rx2 = re.compile(rf'^(\S+(?: \(pre-registration 20; refe)?)\s+{INTERVAL}\s+{INTERVAL}\s+{INTERVAL}')
    for i in range(lo, hi):
        m = rx2.match(s.lines[i])
        if not m or m.group(1).startswith('Gemma-4-31B'):
            continue
        v = re.match(r'^\s+W1 (.+?)\s+W2 (.+?)\s+W3 (.+?)\s*$', s.lines[i + 1])
        if not v:
            stop(f'analyze_24.txt, line {i + 2}: no verdicts under {m.group(1)}')
        short = [lab for lab, tok in HOSTED24 if tok in m.group(1).lower()]
        if len(short) != 1 or models[short[0]]['name'] != m.group(1):
            stop(f'analyze_24.txt, line {i + 1}: {m.group(1)} is not one model of section 1')
        x = models[short[0]]
        x.update(w1=m.group(1 + 1), w2=m.group(1 + 5), w1v=v.group(1), w2v=v.group(2), rline=i + 1)
        s.record('fig_asked_told', f'(b) {short[0]}: W1; W2 (verdicts "{v.group(1)}"; "{v.group(2)[:30]}", line '
                 f'{i + 2})', f'{x["w1"]}; {x["w2"]}', i + 1)
    if any('w1' not in x for x in models.values()):
        stop('analyze_24.txt: a model of section 1 has no rules in section 2')
    lo, hi = s.block(r'^3\. Reading across models', 'section 3 of analyze_24.txt', end=r'^\d\. ')
    m, cl = s.find(r'^  W1 met on (\d+); W1 and W2 both met on (\d+); W3 met on \d+ \(of (\d+) through the gate\)$',
                   'the counts of section 3', lo, hi)
    r, rl = s.find(r'^  READING: ([^:]+):', 'the reading of section 3', lo, hi)
    counts = dict(w1=int(m.group(1)), both=int(m.group(2)), n=int(m.group(3)), reading=r.group(1))
    s.record('table_rules_v2', '24: W1 met on; W1 and W2 both met on; of (models through the gate)',
             f'{m.group(1)}; {m.group(2)}; {m.group(3)}', cl)
    s.record('table_rules_v2', '24: the reading of section 3', r.group(1), rl)
    # the counts must be the verdicts' own
    if counts['n'] != len(models) or counts['w1'] != sum(x['w1v'] == 'used' for x in models.values()) or \
            counts['both'] != sum(x['w1v'] == 'used' and x['w2v'] == 'used less than asked' for x in models.values()):
        stop('analyze_24.txt: the counts of section 3 are not those of the verdicts of section 2')
    return dict(models=models, ref=ref, counts=counts)


def est_24(rule):
    """Rows of pre-registration 24: the smallest and largest difference over the models that have a verdict on the
    rule (a model under the floor of complete steps has none), and the outcome."""
    d = parse_24()
    key = 'w1' if rule == 'W1' else 'w2'
    ms = {k: x for k, x in d['models'].items() if not x[key + 'v'].startswith('no verdict')}
    if rule == 'W2':      # the outcome: the verdicts counted, every model's verdict one of the three words
        words = [x['w2v'].split(' (')[0] for x in d['models'].values()]
        kinds = ('used less than asked', 'no detectable difference', 'no verdict')
        if any(w not in kinds for w in words):
            stop(f'analyze_24.txt: a W2 verdict outside {kinds}: {words}')
        n_less, n_none, n_nov = (words.count(k) for k in kinds)
        if n_less != d['counts']['both'] or n_less + n_none + n_nov != d['counts']['n']:
            stop(f'analyze_24.txt: W2 verdicts {n_less}, {n_none}, {n_nov} against section 3')
    lo_m = min(ms, key=lambda k: Decimal(ms[k][key]))
    hi_m = max(ms, key=lambda k: Decimal(ms[k][key]))
    rng = f'{num(ms[lo_m][key])} to {num(ms[hi_m][key])}'
    PARSED.append(('table_rules_v2', f'24 {rule}: over the {len(ms)} models with a verdict, smallest ({lo_m}, line '
                   f'{ms[lo_m]["rline"]}); largest ({hi_m}, line {ms[hi_m]["rline"]})', rng, rel(R24),
                   f'{ms[lo_m]["rline"]}, {ms[hi_m]["rline"]}'))
    c = d['counts']
    if rule == 'W1':
        if c['w1'] != c['n'] or len(ms) != c['n']:
            stop(f'analyze_24.txt: W1 is met on {c["w1"]} of {c["n"]}; the row says met on each')
        return [rng], 'met on each'
    if len(ms) != n_less + n_none or n_nov != c['n'] - len(ms):
        stop(f'analyze_24.txt: W2 models with a verdict {len(ms)}, verdicts {n_less} + {n_none}, no verdict {n_nov}')
    outcome = (f'met on {n_less} of the {len(ms)} models with a verdict; no detectable difference on {n_none}; '
               f'no verdict on {n_nov}')
    PARSED.append(('table_rules_v2', '24 W2: verdicts used less; no detectable difference; no verdict (lines 20-32)',
                   f'{n_less}; {n_none}; {n_nov}', rel(R24), '20-32'))
    return [f'{rng} over the {WORDS[len(ms)]} models with a verdict'], outcome


def fig_asked_told(out):
    d = parse_asked_told()
    seeds = {d[a]['n'] // d[a]['states'] for a, _l, _c in ARMS20}
    if len(seeds) != 1:
        stop(f'fig_asked_told: replays per paused step differ by condition: {seeds}')
    TOP, ROW, AXIS = 0.62, 0.36, 0.52
    LAB_R, X0, X1 = 2.62, 2.74, 6.55
    note = wrap(
        f'Pre-registration 20. {d["NONE"]["states"]} paused steps that follow the agent\'s own search, each replayed {WORDS[seeds.pop()]} '
        f'times; the hits of another search exist for {d["TOLDX"]["states"]} of them. Intervals: 95% bootstrap by '
        'paused step.', 128)
    rows_h = ROW * len(ARMS20)
    # panel (b), below: the same three arms on the seven hosted models of pre-registration 24, Gemma-4-31B first
    d24 = parse_24()
    ref = d24['ref']['rates']
    for arm in ('NONE', 'TOLD', 'ASKED'):         # the reference row of 24 is the row of 20 drawn above
        if f'{d[arm]["rate"]:.1f}' != ref[arm]:
            stop(f'analyze_24.txt, line {d24["ref"]["line"]}: Gemma-4-31B {arm} {ref[arm]}, analyze_20.txt '
                 f'{d[arm]["rate"]}')
    order = sorted(d24['models'], key=lambda k: -float(d24['models'][k]['rates']['TOLD']))
    note_b = wrap(f'These models continue Gemma-4-31B\'s histories: the search in the history is not their own. '
                  f'Pre-registration 24, registered.', 128)
    B_TOP = TOP + rows_h + AXIS + 0.13 * len(note) + 0.30
    ROWB, GAP = 0.23, 0.14
    RB0 = B_TOP + 0.66
    rows_b = ROWB * (1 + len(order)) + GAP
    YB = RB0 + rows_b + AXIS
    h_in = YB + 0.13 * len(note_b) + 0.10
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'A line the agent was told is used, less often than one it asked for', ha='left', va='top',
              fontsize=10.5, color=INK)
    page.text(0.09, 0.34, 'After a search for code, what the agent had of the hits before its next call:', ha='left',
              va='top', fontsize=7.8, color=INK2)
    ax = axes_at(fig, X0, X1, TOP, TOP + rows_h)
    ax.set_xlim(0, 100)
    ax.set_ylim(rows_h, 0)
    for v in (25, 50, 75, 100):
        ax.plot([v, v], [0.02, rows_h], color=GRID, lw=0.6, zorder=0)
    for i, (arm, label, color) in enumerate(ARMS20):
        r = d[arm]
        yc = ROW * (i + 0.5)
        ax.barh(yc, r['rate'], height=0.17, color=color, edgecolor=color, linewidth=0.6, zorder=2)
        ax.plot([r['lo'], r['hi']], [yc, yc], color=INK, lw=1.0, zorder=3)
        for v in (r['lo'], r['hi']):
            ax.plot([v, v], [yc - 0.04, yc + 0.04], color=INK, lw=0.9, zorder=3)
        value = f'{r["k"]} of {r["n"]} ({100 * r["k"] / r["n"]:.1f}%)'
        if arm == 'TOLDX':     # the hits of another search exist on only some of the paused steps
            value += f' ({r["states"]} of the {d["NONE"]["states"]} steps)'
        vt = ax.text(r['hi'] + 1.6, yc, value, ha='left', va='center', fontsize=7.8, color=INK, zorder=4)
        if X0 + (r['hi'] + 1.6) / 100 * (X1 - X0) + width_in(fig, vt) > W_IN - 0.09:
            stop(f'fig_asked_told: the value "{value}" runs past the page')
        page.text(LAB_R, TOP + yc, label, ha='right', va='center', fontsize=8.4, color=INK,
                  fontweight='bold' if arm in ('TOLD', 'ASKED') else 'normal')
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=7.8, length=3)
    ax.set_xlabel('share of replays whose next call reads a noted file past line 1', fontsize=7.8)
    yn = TOP + rows_h + AXIS
    for i, line in enumerate(note):
        page.text(0.09, yn + 0.13 * i, line, ha='left', va='top', fontsize=6.9, color=MUTED)
    # ---- panel (b)
    page.plot([0.09, W_IN - 0.09], [B_TOP - 0.12] * 2, color=HAIR, lw=0.7)
    page.text(0.09, B_TOP, f'The same hits on {WORDS[len(order)]} hosted models', ha='left', va='top', fontsize=9.0,
              color=INK)
    marks = (('NONE', 'nothing added', PALE, GREY), ('TOLD', 'told in a note', LIGHT, LIGHT),
             ('ASKED', 'in a search result', BLUE, BLUE))
    x = X0
    for _arm, lab, fc, ec in marks:            # the key, one row, at the left edge of the axis
        page.plot(x, B_TOP + 0.30, marker='o', ms=5.6, mfc=fc, mec=ec, mew=0.8, ls='none')
        t = page.text(x + 0.09, B_TOP + 0.30, lab, ha='left', va='center', fontsize=7.6, color=INK)
        x += 0.09 + width_in(fig, t) + 0.28
    page.plot(X0, B_TOP + 0.47, marker='D', ms=4.0, mfc=INK, mec=INK, ls='none')
    page.text(X0 + 0.09, B_TOP + 0.47, 'note used less than the search result (registered rule met)', ha='left',
              va='center', fontsize=7.6, color=INK)
    bx = axes_at(fig, X0, X1, RB0, RB0 + rows_b)
    bx.set_xlim(0, 100)
    bx.set_ylim(rows_b, 0)
    for v in (25, 50, 75, 100):
        bx.plot([v, v], [0.02, rows_b], color=GRID, lw=0.6, zorder=0)
    rows = [('Gemma-4-31B (above)', {a: d[a]['rate'] for a in ('NONE', 'TOLD', 'ASKED')}, False, ROWB / 2)]
    for k, lab in enumerate(order):
        x24 = d24['models'][lab]
        rows.append((lab, {a: float(x24['rates'][a]) for a in ('NONE', 'TOLD', 'ASKED')},
                     x24['w2v'] == 'used less than asked', ROWB * (k + 1.5) + GAP))
    for lab, rates, w2, yc in rows:
        vals = list(rates.values())
        bx.plot([min(vals), max(vals)], [yc, yc], color=MUTED, lw=0.8, zorder=2)
        for arm, _l, fc, ec in marks:
            bx.plot(rates[arm], yc, marker='o', ms=5.6, mfc=fc, mec=ec, mew=0.8, ls='none',
                    zorder=4 if arm == 'ASKED' else 3, clip_on=False)      # a mark at 0% is drawn whole
        page.text(LAB_R, RB0 + yc, lab, ha='right', va='center', fontsize=8.0, color=INK,
                  style='italic' if lab.startswith('Gemma') else 'normal')
        if w2:
            page.plot(X1 + 0.16, RB0 + yc, marker='D', ms=4.0, mfc=INK, mec=INK, ls='none')
        nov = re.match(r'no verdict \(below the floor: (\d+) complete steps', d24['models'].get(lab, {}).get('w2v', ''))
        if nov:        # its dots are rates on different steps per arm; no registered result
            page.text(W_IN - 0.08, RB0 + yc, f'no verdict ({nov.group(1)} complete steps)', ha='right', va='center',
                      fontsize=6.8, color=MUTED, style='italic')
            PARSED.append(('fig_asked_told', f'(b) {lab}: W2 no verdict, complete steps', nov.group(1), rel(R24),
                           d24['models'][lab]['rline'] + 1))
        elif lab in d24['models'] and d24['models'][lab]['w2v'].startswith('no verdict'):
            stop(f'analyze_24.txt: the W2 verdict of {lab} does not parse: {d24["models"][lab]["w2v"]}')
    PARSED.append(('fig_asked_told', '(b) order (by TOLD); W2 met on', f'{", ".join(order)}; '
                   f'{", ".join(lab for lab, _r, w2, _y in rows if w2)}', rel(R24), 'section 2'))
    bx.plot([0, 100], [ROWB + GAP / 2] * 2, color=HAIR, lw=0.7, zorder=1)      # Gemma-4-31B set apart
    bx.set_yticks([])
    bx.set_xticks([0, 25, 50, 75, 100])
    bx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    bx.spines[['top', 'right', 'left']].set_visible(False)
    bx.tick_params(axis='x', labelsize=7.8, length=3)
    bx.set_xlabel('share of replays whose next call reads a noted file past line 1', fontsize=7.8)
    for i, line in enumerate(note_b):
        page.text(0.09, YB + 0.13 * i, line, ha='left', va='top', fontsize=6.9, color=MUTED)
    save(fig, page, out, 'fig_asked_told')


# ================================================================ fig_graph
def parse_graph():
    s = Source(GRAPH)
    v = {}
    m, ln = s.find(r'^graphs (\d+); nodes (\d+); edge records by type: \{(.*)\}$', 'graphs, nodes and edge types')
    v['graphs'], v['nodes'] = int(m.group(1)), int(m.group(2))
    types = dict((k, int(n)) for k, n in re.findall(r"'([^']+)': (\d+)", m.group(3)))
    if not types:
        stop('explore_graph_names.txt: no edge types')
    v['types'], v['records'] = types, sum(types.values())
    s.record('fig_graph', 'graphs; nodes; edge records by type', f'{v["graphs"]}; {v["nodes"]}; {types}', ln)
    m, ln = s.find(r'^distinct \(source, target\) pairs between two different nodes: (\d+); stored both ways: (\d+) '
                   r'\(([\d.]+)%\)', 'pairs stored both ways')
    v['pairs'], v['both'], v['both_pct'] = int(m.group(1)), int(m.group(2)), m.group(3)
    s.record('fig_graph', 'pairs; stored both ways', f'{v["pairs"]}; {v["both"]} ({v["both_pct"]}%)', ln)
    m, ln = s.find(r'^nodes with at least one neighbor: (\d+) of (\d+) \(([\d.]+)%\)', 'nodes with a neighbor')
    v['with'], v['with_n'], v['with_pct'] = int(m.group(1)), int(m.group(2)), m.group(3)
    s.record('fig_graph', 'nodes with a neighbor', f'{v["with"]} of {v["with_n"]} ({v["with_pct"]}%)', ln)
    m, ln = s.find(r'^nodes whose text starts with `async def`: (\d+)', 'async def')
    v['async'] = int(m.group(1))
    s.record('fig_graph', 'nodes whose text starts with async def', str(v['async']), ln)
    lo, hi = s.block(r'^1\. NAME OCCURRENCE, over the (\d+) neighbor entries', 'section 1', end=r'^\d\. ')
    m, ln = s.find(r'^1\. NAME OCCURRENCE, over the (\d+) neighbor entries', 'section 1')
    v['entries'] = int(m.group(1))
    s.record('fig_graph', 'neighbor entries (section 1)', str(v['entries']), ln)
    for key, pat in (('search', r'found by a search of the node name'), ('text', r'named in the node text'),
                     ('neither', r'neither')):
        m, ln = s.find(rf'^\s+{pat}: (\d+) \(([\d.]+)%\)', f'section 1, {key}', lo, hi)
        v[key], v[key + '_pct'] = int(m.group(1)), m.group(2)
        s.record('fig_graph', f'section 1: {pat}', f'{m.group(1)} ({m.group(2)}%)', ln)
    if v['search'] + v['text'] + v['neither'] != v['entries']:
        stop('explore_graph_names.txt: the three parts of section 1 do not add up to its total')
    m, ln = s.find(r'^\s+graph neighbors: median (\d+) \(quartiles (\d+) to (\d+)\), mean ([\d.]+)',
                   'graph neighbors per node')
    v['median'], v['q1'], v['q3'] = (int(g) for g in m.groups()[:3])
    s.record('fig_graph', 'graph neighbors per node with a neighbor: median (quartiles)',
             f'{v["median"]} ({v["q1"]} to {v["q3"]})', ln)
    # part A of the ambiguity report: how many relations have a neighbor's short name no other node of the graph
    # shares, and how many definitions a search returns where one does
    a = Source(AMBIG)
    lo, hi = a.block(r'^A\. ALL GRAPHS, per neighbor relation', 'part A', end=r'^\S')
    m, ln = a.find(r'^   all relations: relations (\d+)$', 'the relations of part A', lo, hi)
    if int(m.group(1)) != v['entries']:
        stop(f'explore_graph_ambiguity.txt, line {ln}: {m.group(1)} relations, explore_graph_names.txt {v["entries"]}')
    m, ln = a.find(r'^     short name unique in its graph: (\d+) \(([\d.]+)%\)$', 'short name unique', ln, ln + 1)
    v['unique'], v['unique_pct'] = int(m.group(1)), m.group(2)
    a.record('fig_graph', 'part A: short name unique in its graph', f'{m.group(1)} ({m.group(2)}%)', ln)
    m, ln = a.find(r'^     among shared: median (\d+), mean [\d.]+$', 'among shared: median', ln, hi)
    v['shared_median'] = int(m.group(1))
    a.record('fig_graph', 'part A: among shared, median candidates', m.group(1), ln)
    return v


def fig_graph(out):
    v = parse_graph()
    if v['pairs'] != v['entries']:
        stop('explore_graph_names.txt: the distinct pairs and the entries of section 1 differ')
    X0, X1 = 0.30, 6.70
    TOP = 0.42
    BAR_Y, BAR_H = TOP + 0.62, 0.36
    pct = Decimal(v['unique_pct']).quantize(Decimal(1), rounding='ROUND_HALF_UP')
    amb = wrap(f'For {pct}% of relations no other node shares the neighbor\'s short name; where one does, a search for '
               f'it returns a median of {v["shared_median"]} definitions.', 112)
    AMB_Y = BAR_Y + BAR_H + 0.66
    STORED = AMB_Y + 0.15 * len(amb) + 0.24          # the head of the facts, under the line of short names
    h_in = STORED + 0.32 + 5 * 0.19 + 0.30
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'What an edge of the code graph is', ha='left', va='top', fontsize=10.5, color=INK)
    # the subtitle says every ordered pair is stored in the other direction too: the counts must say so
    if not v['entries'] == v['pairs'] == v['both']:
        stop(f'fig_graph: relations {v["entries"]}, pairs {v["pairs"]}, stored both ways {v["both"]}: the subtitle '
             'says every ordered pair is stored in the other direction too')
    subtitle = (f'The {v["entries"]:,} neighbor relations of the competition\'s {v["graphs"]} code graphs: ordered pairs '
                '(a node and one of its neighbors), each also stored in the other direction')
    if _text_w(subtitle, 7.8) / 72 > 0.92 * (W_IN - 0.18):     # two lines, broken after the colon
        subtitle = subtitle.replace(': ', ':\n', 1)
    sub = page.text(0.09, 0.34, subtitle, ha='left', va='top', fontsize=7.8, color=INK2, linespacing=1.3)
    if 0.09 + width_in(fig, sub) > W_IN - 0.09:
        stop('fig_graph: the subtitle does not fit')
    # a priority classification: the first class is tested first, the second counts only what the first did not take
    parts = (('search', BLUE, 'white', 'Tested first: the neighbor contains the\nfunction\'s name, so one search finds it'),
             ('text', LIGHT, INK, 'Otherwise: the neighbor\'s name is in\nthe function\'s own text'),
             ('neither', PALE, INK, 'neither'))
    x = X0
    scale = (X1 - X0) / v['entries']
    for key, color, ink, desc in parts:
        w = v[key] * scale
        page.add_patch(Rectangle((x, BAR_Y), w, BAR_H, fc=color, ec='white', lw=0.8))
        share = f'{v[key + "_pct"]}%'
        if key != 'neither':
            page.text(x + 0.10, BAR_Y + BAR_H / 2, share, ha='left', va='center', fontsize=10, color=ink,
                      fontweight='bold')
            page.text(x + 0.02, BAR_Y + BAR_H + 0.08, desc, ha='left', va='top', fontsize=8.0, color=INK,
                      linespacing=1.3)
            page.text(x + 0.02, BAR_Y + BAR_H + 0.08 + 0.15 * (1 + desc.count('\n')) + 0.02,
                      f'{v[key]:,} of {v["entries"]:,}', ha='left', va='top', fontsize=7.4, color=INK2)
        else:
            page.plot([x + w / 2] * 2, [BAR_Y - 0.03, BAR_Y - 0.11], color=MUTED, lw=0.6)
            page.text(x + w, BAR_Y - 0.14, f'neither: {v[key]:,} ({share})', ha='right', va='bottom', fontsize=7.6,
                      color=INK)
        x += w
    for k, line in enumerate(amb):
        page.text(0.30, AMB_Y + 0.15 * k, line, ha='left', va='top', fontsize=7.8, color=INK)
    ys = STORED
    page.text(0.30, ys, 'The graphs, as stored', ha='left', va='top', fontsize=8.6, color=INK, fontweight='bold')
    # the count of edge records is not drawn: it exceeds the neighbor relations (452,588 against 449,902) and the
    # report does not say by what (duplicate records, self loops), so the image names the types only
    types = f'{next(iter(v["types"]))} only' if len(v['types']) == 1 else ', '.join(v['types'])
    facts = (
        ('edge types', types),
        ('ordered pairs also stored the other way', f'{v["both"]:,} of {v["pairs"]:,} ({v["both_pct"]}%)'),
        ('nodes with a neighbor', f'{v["with"]:,} of {v["with_n"]:,} ({v["with_pct"]}%)'),
        ('graph neighbors per node', f'median {v["median"]} (quartiles {v["q1"]} to {v["q3"]}), '
                                     'among the nodes with a neighbor'),
        ('nodes that start with "async def"', f'{v["async"]:,}'),
    )
    for i, (k, val) in enumerate(facts):
        y = ys + 0.25 + 0.19 * i
        page.text(2.65, y, k, ha='right', va='top', fontsize=8.0, color=INK2)
        page.text(2.78, y, val, ha='left', va='top', fontsize=8.0, color=INK)
    page.text(0.09, h_in - 0.07, 'Exploratory: the stored graphs read as text, with no registered rule.', ha='left',
              va='bottom', fontsize=6.9, color=MUTED)
    save(fig, page, out, 'fig_graph')


# ================================================================ fig_moves
STARTER = r'^starter agent, public runs of September \(GraphLoc base arm\)'
INDEP = RES / 'explore_independence.txt'          # the count of panel (a) (exploratory)
INDEP2 = RES / 'rederive_independence.txt'        # the same count by a second script
# Typed, from the coordinator's message, only to check the parsed values (never drawn): (read every file, shown every
# region, resolved) of the runs, for fixes in one file and in several files (explore_independence.txt, first set).
TYPED_FILES = {'one': (195, 166, 84, 225), 'several': (33, 18, 8, 90)}
# Panel (b): the regions a public run was never shown, and how many lie one call edge from code it was shown (the true
# graph and three rewired graphs), or carry a name a text search over its shown code finds (exploratory).
LOCALITY = RES / 'public' / 'locality_null.txt'
LEXICAL = RES / 'public' / 'lexical_reach.txt'
NULLS = (('DEGREE', "keeping each node's degree"), ('SAME-DIRECTORY', 'keeping each edge in its directory'),
         ('SAME-FILE', "keeping each edge's two files"))
# Typed, from the brief, only to check the parsed values (never drawn): true minus each null, and LEXICAL.
TYPED_REACH = {'DEGREE': '+8.8 [1.8, 13.0]', 'SAME-DIRECTORY': '+4.9 [-0.7, 8.4]', 'SAME-FILE': '+1.9 [-2.9, 5.0]',
               'LEXICAL': '315 of 1326', 'LEXICAL, NO DUNDER': '158 of 1326',
               'EDGE minus LEXICAL': '-3.6 [-11.6, 1.2]', 'EDGE minus LEXICAL, NO DUNDER': '+8.2 [0.4, 13.3]',
               'EITHER': '425 of 1326', 'EDGE minus EITHER': '-11.9 [-17.4, -5.9]', 'edge and either': 256,
               'backward only': 211, 'stand-in pairs': 829, 'EDGE minus stand-in': '+18.2 [7.6, 24.0]',
               'EITHER minus stand-in': '+17.7 [8.3, 23.1]'}
# A search by name in both directions, uses only and without names such as __init__ (exploratory).
BOTH = RES / 'public' / 'lexical_reach_both.txt'


def parse_reach_public():
    """Part 1 of locality_null.txt (all missed regions: the true graph and the three nulls) and section 1-5 of
    lexical_reach.txt (all pairs: EDGE, LEXICAL, EDGE minus LEXICAL)."""
    s = Source(LOCALITY)
    m, ln = s.find(r'^rewired graphs: (\d+) seeds per graph and null$', 'the seeds of the nulls')
    seeds = int(m.group(1))
    s.record('fig_moves', '(b) rewired graphs per graph and null (seeds)', str(seeds), ln)
    lo, hi = s.block(r'^1\. MISSED REGIONS one edge of the CALL GRAPH', 'part 1 of locality_null.txt', end=r'^\d\. ')
    m, ln = s.find(r'^   over ALL (\d+) MISSED REGIONS in (\d+) tasks .*: true graph (\d+) \(([\d.]+)% \[([\d.]+), '
                   r'([\d.]+)\]\)$', 'the true graph over all missed regions', lo, hi)
    n, tasks, k = int(m.group(1)), int(m.group(2)), int(m.group(3))
    v = dict(n=n, tasks=tasks, seeds=seeds,true=dict(k=k, pct=m.group(4), lo=m.group(5), hi=m.group(6)), nulls={})
    s.record('fig_moves', '(b) all missed regions; tasks; true graph (share [95%])',
             f'{n}; {tasks}; {k} ({m.group(4)}% [{m.group(5)}, {m.group(6)}])', ln)
    for key, _label in NULLS:
        # the first line of each null under the line of all regions (the lines that follow are subsets)
        m, nl = s.find(rf'^      {key} NULL ([\d.]+)% \(seeds ([\d.]+) to ([\d.]+)\); true minus null ([+-][\d.]+) points '
                       r'\[([+-][\d.]+), ([+-][\d.]+)\]$', f'the {key} null over all regions', ln, ln + len(NULLS))
        diff = interval_text(*m.groups()[3:6])
        if diff != num(TYPED_REACH[key]):
            stop(f'locality_null.txt, line {nl}: {key} true minus null {diff}, the brief types {TYPED_REACH[key]}')
        v['nulls'][key] = dict(pct=m.group(1), diff=diff)
        s.record('fig_moves', f'(b) {key} NULL: share (seeds {m.group(2)} to {m.group(3)}); true minus null [95%]',
                 f'{m.group(1)}%; {diff}', nl)
    x = Source(LEXICAL)
    lo, hi = x.block(r'^1-5\. All PAIRS$', 'section 1-5 of lexical_reach.txt', end=r'^\S')
    m, ln = x.find(r'^   PAIRS (\d+) in (\d+) tasks;', 'the pairs of section 1-5', lo, hi)
    if (int(m.group(1)), int(m.group(2))) != (n, tasks):
        stop(f'lexical_reach.txt, line {ln}: {m.group(1)} pairs in {m.group(2)} tasks, locality_null.txt {n} in {tasks}')
    a, _l = x.find(r'^   of all PAIRS:$', 'the shares of all pairs', lo, hi)
    m, el = x.find(r'^      EDGE (\d+) of (\d+) \(([\d.]+)% \[([\d.]+), ([\d.]+)\]\)$', 'EDGE of all pairs', _l, _l + 1)
    if (int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), m.group(5)) != \
            (k, n, v['true']['pct'], v['true']['lo'], v['true']['hi']):
        stop(f'lexical_reach.txt, line {el}: EDGE {m.group(0).strip()} is not the true graph of locality_null.txt')
    x.record('fig_moves', '(b) EDGE of all pairs (= the true graph of locality_null.txt)', m.group(0).strip(), el)
    m, ll = x.find(r'^      LEXICAL (\d+) of (\d+) \(([\d.]+)% \[([\d.]+), ([\d.]+)\]\);', 'LEXICAL of all pairs',
                   el, el + 1)
    if f'{m.group(1)} of {m.group(2)}' != TYPED_REACH['LEXICAL'] or int(m.group(2)) != n:
        stop(f'lexical_reach.txt, line {ll}: LEXICAL {m.group(1)} of {m.group(2)}, the brief types '
             f'{TYPED_REACH["LEXICAL"]}')
    v['lex'] = dict(k=int(m.group(1)), pct=m.group(3), lo=m.group(4), hi=m.group(5))
    x.record('fig_moves', '(b) LEXICAL of all pairs (share [95%])',
             f'{m.group(1)} of {m.group(2)} ({m.group(3)}% [{m.group(4)}, {m.group(5)}])', ll)
    m, nl = x.find(r'^      LEXICAL, NO DUNDER (\d+) of (\d+) \(([\d.]+)% \[([\d.]+), ([\d.]+)\]\);',
                   'LEXICAL, NO DUNDER of all pairs', ll, ll + 1)
    if f'{m.group(1)} of {m.group(2)}' != TYPED_REACH['LEXICAL, NO DUNDER'] or int(m.group(2)) != n:
        stop(f'lexical_reach.txt, line {nl}: LEXICAL, NO DUNDER {m.group(1)} of {m.group(2)}, the brief types '
             f'{TYPED_REACH["LEXICAL, NO DUNDER"]}')
    v['lexnd'] = dict(k=int(m.group(1)), pct=m.group(3), lo=m.group(4), hi=m.group(5))
    x.record('fig_moves', '(b) LEXICAL, NO DUNDER of all pairs (share [95%])',
             f'{m.group(1)} of {m.group(2)} ({m.group(3)}% [{m.group(4)}, {m.group(5)}])', nl)
    d0, _d = x.find(r'^   differences on all PAIRS', 'the differences of all pairs', lo, hi)
    m, dl = x.find(r'^      EDGE minus LEXICAL ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\];',
                   'EDGE minus LEXICAL', _d, _d + 1)
    v['lex']['diff'] = interval_text(*m.groups())
    if v['lex']['diff'] != num(TYPED_REACH['EDGE minus LEXICAL']):
        stop(f'lexical_reach.txt, line {dl}: EDGE minus LEXICAL {v["lex"]["diff"]}, the brief types '
             f'{TYPED_REACH["EDGE minus LEXICAL"]}')
    x.record('fig_moves', '(b) EDGE minus LEXICAL, all pairs [95%]', v['lex']['diff'], dl)
    m, dl = x.find(r'^      EDGE minus LEXICAL, NO DUNDER ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\];',
                   'EDGE minus LEXICAL, NO DUNDER', dl, dl + 1)
    v['lexnd']['diff'] = interval_text(*m.groups())
    if v['lexnd']['diff'] != num(TYPED_REACH['EDGE minus LEXICAL, NO DUNDER']):
        stop(f'lexical_reach.txt, line {dl}: EDGE minus LEXICAL, NO DUNDER {v["lexnd"]["diff"]}, the brief types '
             f'{TYPED_REACH["EDGE minus LEXICAL, NO DUNDER"]}')
    x.record('fig_moves', '(b) EDGE minus LEXICAL, NO DUNDER, all pairs [95%]', v['lexnd']['diff'], dl)
    # the search in both directions (uses only, no names such as __init__): section 1 of lexical_reach_both.txt
    b = Source(BOTH)
    lo, hi = b.block(r'^1\. All PAIRS$', 'section 1 of lexical_reach_both.txt', end=r'^\d\. ')
    m, ln = b.find(r'^   PAIRS (\d+) in (\d+) tasks;', 'the pairs of section 1', lo, hi)
    if (int(m.group(1)), int(m.group(2))) != (n, tasks):
        stop(f'lexical_reach_both.txt, line {ln}: {m.group(1)} pairs in {m.group(2)} tasks, locality_null.txt {n} in '
             f'{tasks}')
    _m, al = b.find(r'^   of all PAIRS:$', 'the shares of all pairs', lo, hi)
    _m, ol = b.find(r'^   of the OPEN PAIRS:$', 'the end of the shares of all pairs', al, hi)
    m, el = b.find(r'^      EDGE (\d+) of (\d+) \(', 'EDGE of all pairs', al, ol)
    if (int(m.group(1)), int(m.group(2))) != (k, n):
        stop(f'lexical_reach_both.txt, line {el}: EDGE {m.group(1)} of {m.group(2)}, the true graph {k} of {n}')
    _m, ul = b.find(r'^      USE, NO DUNDER:$', 'the sub-block USE, NO DUNDER of all pairs', al, ol)
    m, il = b.find(r'^         EITHER (\d+) of (\d+) \(([\d.]+)% \[([\d.]+), ([\d.]+)\]\); EDGE minus it ([+-][\d.]+) '
                   r'points \[([+-][\d.]+), ([+-][\d.]+)\]$', 'EITHER under USE, NO DUNDER', ul, min(ul + 3, ol))
    if f'{m.group(1)} of {m.group(2)}' != TYPED_REACH['EITHER'] or int(m.group(2)) != n:
        stop(f'lexical_reach_both.txt, line {il}: EITHER {m.group(1)} of {m.group(2)}, the brief types '
             f'{TYPED_REACH["EITHER"]}')
    v['both'] = dict(k=int(m.group(1)), pct=m.group(3), lo=m.group(4), hi=m.group(5),
                     diff=interval_text(*m.groups()[5:8]))
    if v['both']['diff'] != num(TYPED_REACH['EDGE minus EITHER']):
        stop(f'lexical_reach_both.txt, line {il}: EDGE minus EITHER {v["both"]["diff"]}, the brief types '
             f'{TYPED_REACH["EDGE minus EITHER"]}')
    b.record('fig_moves', '(b) USE, NO DUNDER: EITHER of all pairs (share [95%])',
             f'{m.group(1)} of {m.group(2)} ({m.group(3)}% [{m.group(4)}, {m.group(5)}])', il)
    b.record('fig_moves', '(b) USE, NO DUNDER: EDGE minus EITHER, all pairs [95%]', v['both']['diff'], il)
    _m, cl = b.find(r'^   cross tables of the OPEN PAIRS:$', 'the cross tables', lo, hi)
    m, xl = b.find(r'^      USE, NO DUNDER: edge and either (\d+); edge only (\d+);', 'cross table USE, NO DUNDER',
                   cl, hi)
    both_k, edge_only = int(m.group(1)), int(m.group(2))
    m2, yl = b.find(r'^         of the (\d+) the EDGE reaches: forward only (\d+); backward only (\d+); both (\d+); '
                    r'neither (\d+)$', 'the split of the edge under USE, NO DUNDER', xl, xl + 1)
    of_k, fwd, bwd, bb, nei = (int(g) for g in m2.groups())
    if not (both_k + edge_only == of_k == k and fwd + bwd + bb == both_k and nei == edge_only):
        stop(f'lexical_reach_both.txt, lines {xl}-{yl}: edge and either {both_k} + edge only {edge_only} against '
             f'{of_k} and the true graph {k}; forward {fwd} + backward {bwd} + both {bb}; neither {nei}')
    if (both_k, bwd) != (TYPED_REACH['edge and either'], TYPED_REACH['backward only']):
        stop(f'lexical_reach_both.txt, lines {xl}-{yl}: {both_k} and {bwd}, the brief types '
             f'{TYPED_REACH["edge and either"]} and {TYPED_REACH["backward only"]}')
    v['both'].update(edge_and=both_k, backward_only=bwd)
    b.record('fig_moves', '(b) USE, NO DUNDER cross table: edge and either; edge only (sum = true graph)',
             f'{both_k}; {edge_only} (= {of_k})', xl)
    b.record('fig_moves', '(b) USE, NO DUNDER: of the edge reaches, forward only; backward only; both; neither',
             f'{fwd}; {bwd}; {bb}; {nei}', yl)
    # section 4: the true missed function against another function of its file (a stand-in), on the open pairs
    lo, hi = b.block(r'^4\. Against a SAME-FILE STAND-IN', 'section 4 of lexical_reach_both.txt', end=r'^\S')
    m, pl = b.find(r'^   OPEN PAIRS whose file holds another ENTITY not shown: (\d+) of (\d+);', 'the pairs of section 4',
                   lo, hi)
    sf_n, sf_of = int(m.group(1)), m.group(2)
    m, el = b.find(r'^   EDGE: true (\d+) of (\d+) \(([\d.]+)%\); stand-in [\d.]+ \(.*\); true minus stand-in ([+-][\d.]+) '
                   r'points \[([+-][\d.]+), ([+-][\d.]+)\]$', 'EDGE against the stand-in', lo, hi)
    if int(m.group(2)) != sf_n or sf_n != TYPED_REACH['stand-in pairs']:
        stop(f'lexical_reach_both.txt, lines {pl} and {el}: {sf_n} and {m.group(2)} pairs, the brief types '
             f'{TYPED_REACH["stand-in pairs"]}')
    sf_edge = interval_text(*m.groups()[3:6])
    if sf_edge != num(TYPED_REACH['EDGE minus stand-in']):
        stop(f'lexical_reach_both.txt, line {el}: EDGE true minus stand-in {sf_edge}, the brief types '
             f'{TYPED_REACH["EDGE minus stand-in"]}')
    b.record('fig_moves', '(b) section 4: open pairs with a same-file stand-in', f'{sf_n} of {sf_of}', pl)
    b.record('fig_moves', '(b) section 4: EDGE true minus stand-in [95%]', sf_edge, el)
    _m, ul = b.find(r'^   USE, NO DUNDER:$', 'the sub-block USE, NO DUNDER of section 4', lo, hi)
    m, il = b.find(r'^      EITHER: true (\d+) of (\d+) \(([\d.]+)%\); stand-in [\d.]+ \(.*\); true minus stand-in '
                   r'([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]$', 'EITHER against the stand-in, USE, NO DUNDER',
                   ul, min(ul + 3, hi))
    if int(m.group(2)) != sf_n:
        stop(f'lexical_reach_both.txt, line {il}: {m.group(2)} pairs, line {pl} {sf_n}')
    sf_either = interval_text(*m.groups()[3:6])
    if sf_either != num(TYPED_REACH['EITHER minus stand-in']):
        stop(f'lexical_reach_both.txt, line {il}: EITHER true minus stand-in {sf_either}, the brief types '
             f'{TYPED_REACH["EITHER minus stand-in"]}')
    b.record('fig_moves', '(b) section 4: USE, NO DUNDER EITHER true minus stand-in [95%]', sf_either, il)
    v['both'].update(sf_n=sf_n, sf_edge=sf_edge, sf_either=sf_either)
    return v


def parse_files():
    """The right panel: the first set of explore_independence.txt (the starter agent's public runs, base arm)."""
    s = Source(INDEP)
    b0, b1 = s.block(STARTER + r': runs of tasks with a CHANGED REGION \d+, tasks \d+$', 'the first set')
    files = {}
    m, ln = s.find(r'^   fixes whose regions lie in one file: tasks (\d+), runs (\d+); the run read the file (\d+) of '
                   r'(\d+) \([\d.]+%\); SHOWN every region (\d+) of (\d+) \([\d.]+%\); resolved (\d+) of (\d+) \(',
                   'fixes in one file', b0, b1)
    t, n, rd, n1, sh, n2, rs, n3 = (int(g) for g in m.groups())
    if not n == n1 == n2 == n3:
        stop(f'explore_independence.txt, line {ln}: runs {n}, {n1}, {n2}, {n3}')
    files['one'] = dict(tasks=t, n=n, read=rd, shown=sh, resolved=rs)
    s.record('fig_moves', '(a) one file: tasks; read the file; shown every region; resolved',
             f'{t}; {rd}, {sh}, {rs} of {n}', ln)
    m, ln = s.find(r'^   fixes whose regions lie in several files: tasks (\d+), runs (\d+); .*; runs that read every '
                   r'file of the fix (\d+) of (\d+) \(', 'fixes in several files', b0, b1)
    t, n, rd, n1 = (int(g) for g in m.groups())
    m2, ln2 = s.find(r'^      2 or more regions, several files: tasks (\d+), runs (\d+); .*; runs SHOWN every region '
                     r'(\d+) of (\d+) \([\d.]+%\) \(CONSTANT RATE [\d.]+\); resolved (\d+) of (\d+) \(',
                     '2 or more regions, several files', b0, b1)
    t2, n2, sh, n3, rs, n4 = (int(g) for g in m2.groups())
    if not (t == t2 and n == n1 == n2 == n3 == n4):
        stop(f'explore_independence.txt, lines {ln} and {ln2}: tasks {t}, {t2}; runs {n}, {n1}, {n2}, {n3}, {n4}')
    files['several'] = dict(tasks=t, n=n, read=rd, shown=sh, resolved=rs)
    s.record('fig_moves', '(a) several files: tasks; read every file', f'{t}; {rd} of {n}', ln)
    s.record('fig_moves', '(a) several files: shown every region; resolved', f'{sh}, {rs} of {n}', ln2)
    for k, typed in TYPED_FILES.items():
        got = (files[k]['read'], files[k]['shown'], files[k]['resolved'], files[k]['n'])
        if got != typed:
            stop(f'fig_moves: {k} file(s): the file prints {got}, the message types {typed}')
    # the second script must agree on every count drawn that it prints
    r = Source(INDEP2)
    c0, c1 = r.block(r'^### 1\. public starter agent, base arm', 'the first set of the recount', end=r'^### ')
    m, ln = r.find(r'^   tasks (\d+); runs (\d+); runs that READ the file (\d+)/(\d+) \([\d.]+%\); shown every region '
                   r'(\d+)/(\d+)', 'recount: one file', c0, c1)
    one = files['one']
    if tuple(int(g) for g in m.groups()) != (one['tasks'], one['n'], one['read'], one['n'], one['shown'], one['n']):
        stop(f'rederive_independence.txt, line {ln}: the recount differs for fixes in one file')
    r.record('fig_moves', 'recount: one file: tasks; runs; read; shown every region', '; '.join(m.groups()), ln)
    m, ln = r.find(r'^   tasks (\d+); runs (\d+); FILES OF THE FIX \d+; .*runs that READ every file (\d+)/(\d+)',
                   'recount: several files', c0, c1)
    sev = files['several']
    if tuple(int(g) for g in m.groups()) != (sev['tasks'], sev['n'], sev['read'], sev['n']):
        stop(f'rederive_independence.txt, line {ln}: the recount differs for fixes in several files')
    r.record('fig_moves', 'recount: several files: tasks; runs; read every file', '; '.join(m.groups()), ln)
    m, ln = r.find(r'^   2 or more  IN SEVERAL FILES tasks +(\d+); runs +(\d+); .*shown every region (\d+)/(\d+)',
                   'recount: several files, shown every region', c0, c1)
    if tuple(int(g) for g in m.groups()) != (sev['tasks'], sev['n'], sev['shown'], sev['n']):
        stop(f'rederive_independence.txt, line {ln}: the recount differs for shown every region, several files')
    r.record('fig_moves', 'recount: several files: shown every region', f'{m.group(3)} of {m.group(4)}', ln)
    return dict(files=files)


def fig_moves(out):
    files = parse_files()['files']
    r = parse_reach_public()
    TITLE = 'Runs miss the rest of a fix, and a call edge leads there one time in five'
    title_lines = [TITLE] if _text_w(TITLE, 10.5) / 72 <= W_IN - 0.18 else \
        [TITLE[:TITLE.index(',') + 1], TITLE[TITLE.index(',') + 2:]]
    TOP = 0.42 + 0.20 * (len(title_lines) - 1)
    A_HEAD, A_H, A_AX = 0.46, 1.95, 0.42
    B_TOP = TOP + A_HEAD + A_H + A_AX + 0.30
    ROW, SUB, GAP = 0.25, 0.22, 0.16
    B_HEAD = 0.36
    rows_b = ROW + SUB + ROW * len(NULLS) + GAP + 3 * ROW
    # the note under the axis label on the search in both directions; one line if it fits, else two
    bo = r['both']
    note = (f'Of the {r["true"]["k"]} places a call edge reaches, {bo["edge_and"]} are also reached by the name search '
            f'in either direction. Against another function of the same file as a stand-in for the missed one, the '
            f'edge and that search pick out the true place about equally often ({bo["sf_edge"]} and {bo["sf_either"]} '
            f'points; {bo["sf_n"]:,} pairs).')
    # wrapped at 90% of the room: the drawn width runs some 6% over the width _text_w measures at this size
    note = '\n'.join(_wrap_pts(note, 0.90 * (W_IN - 0.10 - 0.36) * 72, 7.2))
    NOTE_H = 0.15 * (note.count('\n') + 1)
    h_in = B_TOP + B_HEAD + rows_b + 0.48 + NOTE_H + 0.20 + 0.28
    fig, page = page_of(h_in)
    for k, line in enumerate(title_lines):
        t = page.text(0.09, 0.07 + 0.20 * k, line, ha='left', va='top', fontsize=10.5, color=INK)
        if width_in(fig, t) > W_IN - 0.18:
            stop(f'fig_moves: the title line "{line[:40]}" does not fit')
    # panel (a): a fix in one file, and a fix in several (unchanged, the former panel b)
    page.text(0.09, TOP, '(a)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, TOP + 0.005, 'A fix in one file, and a fix in several', ha='left', va='top', fontsize=9.0,
              color=INK)
    page.text(W_IN - 0.10, TOP + 0.02, f'the starter agent\'s public runs, without the skill: '
              f'{files["one"]["n"] + files["several"]["n"]} runs', ha='right', va='top', fontsize=7.6, color=INK2)
    bx = axes_at(fig, 0.80, 6.90, TOP + A_HEAD, TOP + A_HEAD + A_H)
    series = (('read', 'the run reads every file of the fix', LIGHT),
              ('shown', 'is shown every changed region', BLUE),
              ('resolved', 'resolves the task', GREY))
    groups = (('one', 'fix in one file'), ('several', 'fix in several files'))
    bw = 0.26
    for gi, (gk, _gl) in enumerate(groups):
        g = files[gk]
        for si, (key, _label, color) in enumerate(series):
            x = gi + (si - 1) * (bw + 0.03)
            share = 100 * g[key] / g['n']
            bx.bar(x, share, width=bw, color=color, edgecolor=color, linewidth=0.6, zorder=2)
            bx.text(x, share + 2.0, f'{g[key]} of {g["n"]}', ha='center', va='bottom', fontsize=7.4, color=INK,
                    zorder=5)
    bx.set_xlim(-0.55, len(groups) - 0.45 + 0.95)     # room on the right for the key
    bx.set_ylim(0, 100)
    bx.set_xticks(range(len(groups)))
    bx.set_xticklabels([f'{gl}\n{files[gk]["tasks"]} tasks, {files[gk]["n"]} runs' for gk, gl in groups],
                       fontsize=7.8)
    bx.set_yticks([0, 20, 40, 60, 80, 100])
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    bx.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    bx.set_axisbelow(True)
    bx.spines[['top', 'right']].set_visible(False)
    bx.tick_params(labelsize=7.8, length=3)
    bx.tick_params(axis='x', length=0)
    bx.set_ylabel('share of runs', fontsize=8.0)
    kx, ky = 0.66, 0.90
    for key, label, color in series:
        bx.add_patch(Rectangle((kx, ky - 0.025), 0.025, 0.05, transform=bx.transAxes, fc=color, ec='none', zorder=6))
        bx.text(kx + 0.04, ky, label, transform=bx.transAxes, ha='left', va='center', fontsize=7.6, color=INK, zorder=6)
        ky -= 0.085
    # panel (b): the regions a run was never shown, within reach of code it was shown
    page.text(0.09, B_TOP, '(b)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, B_TOP + 0.005, 'Regions a run was never shown: within reach of code it was shown', ha='left',
              va='top', fontsize=9.0, color=INK)
    LAB_R, X0, X1, DIFF_R = 2.50, 2.62, 4.42, W_IN - 0.10
    XMAX = 40
    y0 = B_TOP + B_HEAD
    ax = axes_at(fig, X0, X1, y0, y0 + rows_b)
    ax.set_xlim(0, XMAX)
    ax.set_ylim(rows_b, 0)
    for g in range(10, XMAX + 1, 10):
        ax.plot([g, g], [0.02, rows_b], color=GRID, lw=0.6, zorder=0)
    n = r['n']
    room = (LAB_R - 0.09) * 72

    def bar(yc, share, color, label, value, diff=None, size=8.2):
        if share > XMAX - 2:
            stop(f'fig_moves: the bar "{label}" of panel (b) runs past the axis')
        if _text_w(label, size) > room:
            stop(f'fig_moves: the label "{label}" does not fit left of the bars')
        # the value text must end left of the right column (with a small gap)
        v_end = X0 + (share + 0.4) / XMAX * (X1 - X0) + _text_w(value, 7.6) / 72
        d_start = DIFF_R - (_text_w(_display(diff), 7.2) / 72 if diff else 0)
        if v_end > d_start - 0.08:
            stop(f'fig_moves: the value "{value}" runs into the right column ({v_end:.2f} against {d_start:.2f} in)')
        ax.barh(yc, share, height=0.15, color=color, edgecolor=color, linewidth=0.6, zorder=2)
        ax.text(share + 0.4, yc, value, ha='left', va='center', fontsize=7.6, color=INK, zorder=3)
        page.text(LAB_R, y0 + yc, label, ha='right', va='center', fontsize=size, color=INK)
        if diff:
            page.text(DIFF_R, y0 + yc, diff, ha='right', va='center', fontsize=7.2, color=INK2)

    def fitting(labels, size=8.2):
        """The first label that fits left of the bars, or a stop."""
        ok = next((s for s in labels if _text_w(s, size) <= room), None)
        if ok is None:
            stop(f'fig_moves: no label of {labels} fits left of the bars')
        return ok

    t = r['true']
    bar(ROW / 2, float(t['pct']), BLUE, 'one call edge (the true graph)',
        f'{t["k"]} of {n:,} ({t["pct"]}% [{t["lo"]}, {t["hi"]}])')
    y = ROW
    page.text(LAB_R, y0 + y + SUB / 2 + 0.02, 'the same under a rewired graph', ha='right', va='center', fontsize=7.4,
              color=INK2, style='italic')
    # the header of the right column stands above the first row, so that it heads the rewired and the search rows
    page.text(DIFF_R, y0 - 0.07, 'true graph minus this, points [95%]', ha='right', va='center', fontsize=7.0,
              color=MUTED)
    y += SUB
    for key, label in NULLS:
        nl = r['nulls'][key]
        bar(y + ROW / 2, float(nl['pct']), LIGHT, label, f'{nl["pct"]}% (mean of {r["seeds"]} rewirings)'
            if key == NULLS[0][0] else f'{nl["pct"]}%', nl['diff'], size=7.8)
        y += ROW
    ax.plot([0, XMAX], [y + GAP / 2] * 2, color=HAIR, lw=0.6, zorder=1, clip_on=False)
    y += GAP
    lx = r['lex']
    # three text searches, one family: forward by name, the same without dunder names, both directions (uses only)
    lab_size = 8.2 if _text_w("the missed function's name in the shown code", 8.2) <= room else 7.8
    bar(y + ROW / 2, float(lx['pct']), GREY, fitting(["the missed function's name in the shown code"], lab_size),
        f'{lx["k"]} of {n:,} ({lx["pct"]}% [{lx["lo"]}, {lx["hi"]}])', lx['diff'], size=lab_size)
    y += ROW
    nd = r['lexnd']
    bar(y + ROW / 2, float(nd['pct']), GREY,
        fitting(['the same without names such as __init__', 'the same, without __init__ and its like'], lab_size),
        f'{nd["k"]} of {n:,} ({nd["pct"]}% [{nd["lo"]}, {nd["hi"]}])', nd['diff'], size=lab_size)
    y += ROW
    bar(y + ROW / 2, float(bo['pct']), GREY,
        fitting(['names in use, either direction (no __init__)', 'a name in use, either direction'], lab_size),
        f'{bo["k"]} of {n:,} ({bo["pct"]}% [{bo["lo"]}, {bo["hi"]}])', bo['diff'], size=lab_size)
    ax.set_yticks([])
    ax.set_xticks(range(0, XMAX + 1, 10))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=7.8, length=3)
    ax.set_xlabel(f'share of the {n:,} pairs of a run and a changed region it was never shown ({r["tasks"]} tasks)',
                  fontsize=7.8)
    nt = page.text(0.36, y0 + rows_b + 0.50, note, ha='left', va='top', fontsize=7.2, color=INK2, linespacing=1.25)
    if 0.36 + width_in(fig, nt) > W_IN - 0.10:
        stop(f'fig_moves: the note under panel (b) does not fit ({width_in(fig, nt):.2f} in): {note!r}')
    page.text(0.36, y0 + rows_b + 0.52 + NOTE_H, 'Public runs of the starter agent, both arms; exploratory.',
              ha='left', va='top', fontsize=6.9, color=MUTED)
    page.text(0.09, h_in - 0.07, 'Both panels are exploratory: counted on stored runs, with no registered rule; panel '
              '(a) recounted by a second script.', ha='left', va='bottom', fontsize=6.9, color=MUTED)
    save(fig, page, out, 'fig_moves')


# ================================================================ fig_oracle
MID = '#4f82b8'      # OF: between ON (GREY) and OA (BLUE) in hue, and in grey value (about 121 against 142 and 95)
GREEN, GREEN_TINT = '#2e7d4f', '#a3d4b4'   # fig_oracle (b): classes of first reads, no arm color (grey ~96, ~192)
ARMS18 = (('N', 'control', PALE), ('ON', 'names', GREY), ('OF', 'names with line ranges', MID),
          ('OA', 'changed lines', BLUE))
OUTCOMES = (('every', 'shown every\nchanged region', 'registered'),        # rules of pre-registration 18
            ('overlap', 'final patch overlaps\na changed region', 'not registered: seen after the run'),
            ('resolved', 'resolved\n(the tests pass)', 'registered'))
SEC3 = (r'^   {arm}: runs (\d+); shown a changed line \d+ of \d+ \([\d.]+%\); every region shown (\d+) of (\d+) '
        r'\([\d.]+%\); patch touches every changed region \d+ of \d+ \([\d.]+%\); patch overlaps a changed region (\d+) '
        r'of (\d+) \([\d.]+%\); resolved (\d+) of (\d+) \(')


def section3(s, arms, fig_label, sec_lo, sec_hi):
    res = {}
    for arm in arms:
        m, ln = s.find(SEC3.format(arm=arm), f'section 3, arm {arm}', sec_lo, sec_hi)
        runs, every, n1, overlap, n2, resolved, n3 = (int(g) for g in m.groups())
        if not runs == n1 == n2 == n3:
            stop(f'{rel(s.path)}: arm {arm}: runs {runs}, {n1}, {n2}, {n3}')
        res[arm] = dict(runs=runs, every=every, overlap=overlap, resolved=resolved)
        s.record('fig_oracle', f'{fig_label} {arm}: every region shown; patch overlaps; resolved (of runs)',
                 f'{every}; {overlap}; {resolved} (of {runs})', ln)
    return res


def parse_oracle(r22):
    sr = Source(RED18)
    m, ln = sr.find(r'^shown every changed region\s+(\d+)/(\d+) \([\d.]+%\)\s+(\d+)/(\d+) \([\d.]+%\)\s+(\d+)/(\d+) '
                    r'\([\d.]+%\)\s*$', 'shown every changed region (N, ON, OA)')
    g = [int(x) for x in m.groups()]
    every = {'N': g[0], 'ON': g[2], 'OA': g[4]}
    if not g[1] == g[3] == g[5]:
        stop('rederive_18.txt: the arms are out of different numbers of runs')
    _h, hl = sr.find(r'^\s+N\s+ON\s+OA\s*$', 'the column heads of section 2 of rederive_18.txt')
    if hl > ln:
        stop('rederive_18.txt: the column heads N, ON, OA are not above the line of shown every changed region')
    sr.record('fig_oracle', 'seed 2: shown every changed region, N; ON; OA (columns, heads on line %d)' % hl,
              f'{g[0]}; {g[2]}; {g[4]} of {g[1]}', ln)
    s18 = Source(R18)
    lo, hi = s18.block(r'^3\. No rule: reported', 'section 3 of analyze_18.txt', end=r'^\d\. ')
    sec = section3(s18, ('N', 'ON', 'OA'), 'seed 2 (analyze_18)', lo, hi)
    seed2 = {a: dict(every=every[a], overlap=sec[a]['overlap'], resolved=sec[a]['resolved'], runs=sec[a]['runs'])
             for a in ('N', 'ON', 'OA')}
    if any(seed2[a]['runs'] != g[1] for a in seed2):
        stop('analyze_18.txt and rederive_18.txt: different numbers of runs')
    seed3 = None
    p22 = Path(r22) if r22 else R22
    if p22.exists():
        s22 = Source(p22)
        lo, hi = s22.block(r'^3\. No rule: reported', 'section 3 of analyze_22.txt', end=r'^\d\. ')
        seed3 = section3(s22, ('N', 'ON', 'OF', 'OA'), 'seed 3 (analyze_22)', lo, hi)
        seed3['_file'] = rel(p22)
    return seed2, sec, seed3


@functools.lru_cache(maxsize=None)
def parse_22(path):
    """The report of pre-registration 22: arms, tasks of the task list, tasks that ran, resolved per arm (section 3),
    the rules of section 2 with their verdicts and the registered floor of tasks. Read once (the tables use it too)."""
    s = Source(path)
    m, line = s.find(r'^EXPERIMENT 22: .*, arms ([\w, ]+) \(', 'the arms of 22')
    arms = [a.strip() for a in m.group(1).split(',')]
    s.record('fig_oracle', 'seed 3: arms of 22', ', '.join(arms), line)
    m, line = s.find(r'^   tasks of tasks_18\.txt: (\d+)$', 'the tasks of the task list (analyze_22.txt)')
    total = int(m.group(1))
    s.record('fig_oracle', 'seed 3: tasks of the task list', str(total), line)
    lo, hi = s.block(r'^1\. Runs per arm', 'section 1 of analyze_22.txt', end=r'^\d\. ')
    ran = {}
    for arm in arms:
        m, line = s.find(rf'^   {arm}\s+runs (\d+); entered (\d+);', f'section 1, arm {arm}', lo, hi)
        if m.group(1) != m.group(2):
            stop(f'{rel(path)}, line {line}: arm {arm}: runs {m.group(1)}, entered {m.group(2)}')
        ran[arm] = int(m.group(1))
        s.record('fig_oracle', f'seed 3, {arm}: runs entered (one per task)', m.group(1), line)
    if len(set(ran.values())) != 1:
        stop(f'{rel(path)}: the arms of 22 ran on different numbers of tasks: {ran}')
    n_ran = ran[arms[0]]
    lo, hi = s.block(r'^3\. No rule: reported', 'section 3 of analyze_22.txt', end=r'^\d\. ')
    sec = section3(s, arms, 'seed 3 (analyze_22), (a) draws resolved', lo, hi)
    if any(sec[a]['runs'] != n_ran for a in arms):
        stop(f'{rel(path)}: sections 1 and 3 count different runs')
    m, fline = s.find(r'^2\. Rules .*; a verdict needs at least (\d+) tasks\)$', 'section 2 and its floor of tasks')
    floor = int(m.group(1))
    s.record('fig_oracle', 'seed 3: a verdict needs at least (tasks)', str(floor), fline)
    lo, hi = s.block(r'^2\. Rules', 'section 2 of analyze_22.txt', end=r'^\d\. ')
    rules = []
    for i in range(lo, hi):
        m = re.match(r'^   (L\d) .*; (\d+) tasks; ', s.lines[i])
        if not m:
            continue
        v = re.match(r'^\s+verdict: (.+)$', s.lines[i + 1]) if i + 1 < hi else None
        if not v:
            stop(f'{rel(path)}, line {i + 2}: no verdict under rule {m.group(1)}')
        if int(m.group(2)) != n_ran:
            stop(f'{rel(path)}, line {i + 1}: rule {m.group(1)} on {m.group(2)} tasks, not {n_ran}')
        rules.append((m.group(1), v.group(1).strip(), i + 2))
    if not rules:
        stop(f'{rel(path)}: no rule L1 to L7 in section 2')
    verdicts = {v for _r, v, _l in rules}
    s.record('fig_oracle', f'seed 3: rules of section 2 ({len(rules)} lines, {rules[0][0]} to {rules[-1][0]}); '
             'their verdicts', '; '.join(sorted(verdicts)), f'{rules[0][2]}-{rules[-1][2]}')
    return dict(arms=arms, total=total, ran=n_ran, sec=sec, floor=floor, rules=rules,
                no_verdict=all(v.startswith('no verdict') for v in verdicts), file=rel(path))


def parse_reach(path, arms):
    """Part 7 of explore_reach_22.txt: per arm, the first reads of a file of the note (TOP, at a line the note gave,
    at a line of the run's own search)."""
    s = Source(path)
    lo, hi = s.block(r'^7\. How each arm reaches', 'part 7 of explore_reach_22.txt', end=r'^\d+\. ')
    out, arm = {}, None
    for i in range(lo, hi):
        h = re.match(r'^pre-registration 22, arm (\w+) \(', s.lines[i])
        if h:
            arm = h.group(1)
            continue
        m = re.match(r'^   first READS of a file of the note (\d+): TOP (\d+), ADDRESSED (\d+); ADDRESSED with a line of '
                     r'the NOTE near (\d+)$', s.lines[i])
        if not m:
            continue
        if arm is None or arm in out:
            stop(f'{rel(path)}, line {i + 1}: a line of first reads with no arm, or a second one for {arm}')
        n, top, addr, near = (int(g) for g in m.groups())
        if top + addr != n or near > addr:
            stop(f'{rel(path)}, line {i + 1}: TOP {top} + ADDRESSED {addr} is not {n}, or NOTE near {near} > {addr}')
        out[arm] = dict(n=n, top=top, note=near, own=addr - near)
        s.record('fig_oracle', f'(b) {arm}: first reads of a file of the note; TOP; ADDRESSED; with a line of the NOTE',
                 f'{n}; {top}; {addr}; {near}', i + 1)
    if sorted(out) != sorted(arms):
        stop(f'{rel(path)}: part 7 has first reads for {sorted(out)}, not {sorted(arms)}')
    return out


def parse_cost(path, arms, n_ran):
    """explore_cost_22.txt: the mean LINES READ per run of each arm (section 1) and the paired differences OF minus ON,
    OA minus ON and ON minus N (section 2, LINES READ)."""
    s = Source(path)
    lo, hi = s.block(r'^1\. Per arm, every run', 'section 1 of explore_cost_22.txt', end=r'^\d\. ')
    mean = {}
    for arm in arms:
        m, h = s.find(rf'^pre-registration 22, arm {arm} \(.*\): runs (\d+)$', f'section 1, arm {arm}', lo, hi)
        if int(m.group(1)) != n_ran:
            stop(f'{rel(path)}, line {h}: arm {arm} has {m.group(1)} runs, analyze_22.txt {n_ran}')
        m, line = s.find(r'^   per run: .*; LINES READ, median [\d.]+, mean ([\d.]+);', f'LINES READ, arm {arm}', h, h + 1)
        mean[arm] = Decimal(m.group(1))
        s.record('fig_oracle', f'(c) {arm}: LINES READ per run, mean (runs {n_ran}, line {h})', m.group(1), line)
    lo, hi = s.block(r'^2\. Paired by task', 'section 2 of explore_cost_22.txt', end=r'^\d\. ')
    b0, b1 = s.block(r'^   LINES READ$', 'section 2, LINES READ', end=r'^   \S', lo=lo, hi=hi)
    diffs = {}
    for a, b in (('OF', 'ON'), ('OA', 'ON'), ('ON', 'N')):
        m, line = s.find(rf'^      {a} minus {b}: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\] \((\d+) tasks\)$',
                         f'LINES READ, {a} minus {b}', b0, b1)
        if int(m.group(4)) != n_ran:
            stop(f'{rel(path)}, line {line}: {a} minus {b} on {m.group(4)} tasks, not {n_ran}')
        diffs[(a, b)] = tuple(Decimal(g) for g in m.groups()[:3])
        s.record('fig_oracle', f'(c) LINES READ, {a} minus {b} [95%] ({m.group(4)} tasks)',
                 f'{m.group(1)} [{m.group(2)}, {m.group(3)}]', line)
    return mean, diffs


def whole(d):
    """A printed decimal to a whole number, half away from zero, with a typographic minus."""
    return num(str(d.quantize(Decimal(1), rounding='ROUND_HALF_UP')))


def signed(d):
    """As whole(), with a plus sign on a positive number."""
    w = whole(d)
    return w if w.startswith(MINUS) or w == '0' else '+' + w


def parse_same_tasks(n_ran, seed3):
    """Part 6 of rederive_22.txt: RESOLVED per arm at seed 2 (experiment 18) on the tasks of 22, with the seed-3 columns
    checked against analyze_22.txt."""
    s = Source(RED22)
    lo, hi = s.block(r'^6\. THE TWO SEEDS ON THE SAME TASKS', 'part 6 of rederive_22.txt', end=r'^\d\. ')
    m, tl = s.find(r'^  tasks: N (\d+), ON (\d+), OA (\d+)$', 'part 6, tasks per arm', lo, hi)
    if any(int(g) != n_ran for g in m.groups()):
        stop(f'rederive_22.txt, line {tl}: tasks per arm {m.groups()}, not {n_ran}')
    _h, hl = s.find(r'^\s+N seed 2\s+N seed 3\s+ON seed 2\s+ON seed 3\s+OA seed 2\s+OA seed 3\s*$', 'part 6, column heads',
                    lo, hi)
    cols = re.findall(r'(\w+) seed (\d)', s.lines[hl - 1])
    m, line = s.find(r'^RESOLVED\s+(.*)$', 'part 6, RESOLVED', lo, hi)
    cells = re.findall(r'(\d+)/(\d+) \([\d.]+%\)', m.group(1))
    if len(cells) != len(cols) or line != hl + 1:
        stop(f'rederive_22.txt, line {line}: {len(cells)} cells under {len(cols)} column heads (line {hl})')
    got = {(a, int(sd)): (int(k), int(n)) for (a, sd), (k, n) in zip(cols, cells)}
    for (a, sd), (k, n) in got.items():
        if n != n_ran:
            stop(f'rederive_22.txt, line {line}: {a} seed {sd} out of {n}, not {n_ran}')
        if sd == 3 and k != seed3[a]['resolved']:
            stop(f'rederive_22.txt, line {line}: {a} seed 3 resolved {k}, analyze_22.txt {seed3[a]["resolved"]}')
    out = {a: dict(resolved=got[(a, 2)][0], runs=n_ran) for a in ('N', 'ON', 'OA')}
    # the first seed on the other tasks (those without a run of 22): one line, wrapped onto the lines under it
    _m, ol = s.find(r'^  Seed 2 on the tasks without a run of 22 \(for comparison\):', 'part 6, the other tasks', lo, hi)
    j = ol
    while j < hi and s.lines[j].startswith('    '):
        j += 1
    text = ' '.join(x.strip() for x in s.lines[ol - 1:j])
    other = {}
    for a in ('N', 'ON', 'OA'):
        mo = re.search(rf'(?:: |; ){a} resolved (\d+)/(\d+) \(', text)
        if not mo:
            stop(f'rederive_22.txt, lines {ol}-{j}: no resolved count for {a} on the other tasks')
        other[a] = (int(mo.group(1)), int(mo.group(2)))
    s.record('fig_oracle', '(a) note: first seed on the other tasks, resolved N; ON; OA',
             '; '.join(f'{k} of {n}' for k, n in other.values()), f'{ol}-{j}')
    out['_other'] = other
    s.record('fig_oracle', f'(a) first seed on the {n_ran} tasks of 22: resolved N; ON; OA (heads line {hl}, tasks '
             f'line {tl}; seed-3 columns equal analyze_22.txt)',
             '; '.join(f'{out[a]["resolved"]} of {n_ran}' for a in ('N', 'ON', 'OA')), line)
    return out


def fig_oracle(out, r22):
    p22 = Path(r22) if r22 else R22
    if not p22.exists():
        return fig_oracle_one_seed(out, r22)
    s18 = Source(R18)
    lo, hi = s18.block(r'^3\. No rule: reported', 'section 3 of analyze_18.txt', end=r'^\d\. ')
    seed2 = section3(s18, ('N', 'ON', 'OA'), 'seed 2 (analyze_18), (a) draws resolved', lo, hi)
    if len({seed2[a]['runs'] for a in seed2}) != 1:
        stop('analyze_18.txt: the arms are out of different numbers of runs')
    d22 = parse_22(p22)
    arms22 = d22['arms']
    if arms22 != ['N', 'ON', 'OF', 'OA']:
        stop(f'fig_oracle: the arms of 22 are {arms22}, not N, ON, OF, OA')
    n18 = seed2['N']['runs']
    if n18 != d22['total']:
        stop(f'fig_oracle: experiment 18 has {n18} runs per arm, the task list {d22["total"]} tasks')
    reach = parse_reach(REACH22, arms22)
    mean, diffs = parse_cost(COST22, arms22, d22['ran'])
    if not d22['no_verdict']:
        stop('fig_oracle: a rule of 22 has a verdict; the footnote says none has')
    same20 = parse_same_tasks(d22['ran'], d22['sec'])
    other20 = same20.pop('_other')
    for a in ('N', 'ON', 'OA'):        # the two halves of the first seed add up to its 40 tasks
        if (same20[a]['resolved'] + other20[a][0], d22['ran'] + other20[a][1]) != (seed2[a]['resolved'], n18):
            stop(f'fig_oracle: arm {a}: {same20[a]["resolved"]} + {other20[a][0]} resolved, not '
                 f'{seed2[a]["resolved"]} of {n18}')
    words = dict((k, lab) for k, lab, _c in ARMS18)
    colors = dict((k, c) for k, _l, c in ARMS18)
    TITLE = ('Told where the fix is: the form of the note changes what the agent reads; resolved tasks do not '
             'detectably differ between names, ranges and lines')
    # one line at the size of the other figures' titles, or two broken after the colon
    title_lines = [TITLE] if _text_w(TITLE, 10.5) / 72 <= W_IN - 0.18 else \
        [TITLE[:TITLE.index(':') + 1], TITLE[TITLE.index(':') + 2:]]
    if _text_w(title_lines[-1], 10.5) / 72 > W_IN - 0.18:       # and after the semicolon, when that is still too wide
        rest = title_lines.pop()
        title_lines += [rest[:rest.index(';') + 1], rest[rest.index(';') + 2:]]
    DY = 0.20 * (len(title_lines) - 1)
    KEY_Y = 0.46 + DY
    HEAD_Y = 0.78 + DY
    P0, P1 = 1.32 + DY, 3.22 + DY           # the plot area of every panel, top and bottom
    XA = (0.50, 3.05)
    XB = (3.35, 4.95)
    XC = (5.22, 6.90)
    FS = 7.2
    texts = []                              # every text drawn, checked for overlaps at the end
    foot = wrap(f'First seed: pre-registration 18, registered. Second seed: pre-registration 22, {d22["ran"]} of its '
                f'{d22["total"]} tasks ran, no rule has a verdict.', 152) + ['Panels b and c are exploratory.']
    FOOT = P1 + 1.66                        # the footnote, under the notes of panels b and c
    h_in = FOOT + 0.13 * len(foot) + 0.08
    fig, page = page_of(h_in)
    # the takeaway, one line: the size of the other figures' titles, made smaller only if it would not fit
    for k, line in enumerate(title_lines):
        title = page.text(0.09, 0.07 + 0.20 * k, line, ha='left', va='top', fontsize=10.5, color=INK)
        if width_in(fig, title) > W_IN - 0.18:
            stop(f'fig_oracle: the title line "{line[:40]}" does not fit')
        texts.append(title)
    # the key of the arms, one row across the page
    x = 0.50
    for key, label, color in ARMS18:
        page.add_patch(Rectangle((x, KEY_Y - 0.045), 0.16, 0.09, fc=color, ec='none'))
        t = page.text(x + 0.21, KEY_Y, label, ha='left', va='center', fontsize=7.8, color=INK)
        texts.append(t)
        x += 0.21 + width_in(fig, t) + 0.28
    if x > W_IN:
        stop('fig_oracle: the key runs past the page')
    heads = ((XA, '(a)', ['Tasks resolved'], None),
             (XB, '(b)', ['Where the first read', "of a note's file starts"], 'second seed'),
             (XC, '(c)', ['Lines of file content', 'a run reads'], 'second seed'))
    for (x0, _x1), tag, lines, sub in heads:
        x0 = x0 - (0.42 if tag == '(a)' else 0.0)
        texts.append(page.text(x0, HEAD_Y, tag, ha='left', va='top', fontsize=8.8, fontweight='bold', color=INK))
        for k, line in enumerate(lines):
            texts.append(page.text(x0 + 0.26, HEAD_Y + 0.005 + 0.15 * k, line, ha='left', va='top', fontsize=8.4,
                                   color=INK))
        if sub:
            texts.append(page.text(x0 + 0.26, HEAD_Y + 0.005 + 0.15 * len(lines), sub, ha='left', va='top',
                                   fontsize=7.0, color=INK2, style='italic'))
    # (a) resolved, share of runs: the first seed on all its tasks and on the tasks of 22, the second seed on those
    ax = axes_at(fig, XA[0], XA[1], P0, P1)
    groups = ((['N', 'ON', 'OA'], {a: seed2[a] for a in ('N', 'ON', 'OA')}, n18,
               f'first seed,\n{n18} tasks'),
              (['N', 'ON', 'OA'], same20, d22['ran'], f'first seed,\nthe same {d22["ran"]} tasks'),
              (arms22, d22['sec'], d22['ran'], f'second seed,\nthose {d22["ran"]} tasks'))
    xs, centers, x = [], [], 0.0
    top_share = 0.0
    for gi, (garms, vals, n, _lab) in enumerate(groups):
        start = x
        for arm in garms:
            share = 100 * vals[arm]['resolved'] / n
            top_share = max(top_share, share)
            xs.append((x, arm, share, vals[arm]['resolved'], n))
            x += 1.0
        centers.append((start + x - 1.0) / 2)
        x += 0.75
    ymax = 10 * (int((top_share + 9.999) // 10) + 1)
    bars_a = []
    for xb, arm, share, k, n in xs:
        bars_a.append(ax.bar(xb, share, width=0.78, color=colors[arm], edgecolor=colors[arm], linewidth=0.6,
                             zorder=2)[0])
        texts.append(ax.text(xb, share + 0.012 * ymax * 1.5, f'{k}\nof {n}', ha='center', va='bottom', fontsize=6.6,
                             color=INK, zorder=3, linespacing=1.05))
    ax.set_xlim(-0.6, x - 0.75 - 0.4)
    ax.set_ylim(0, ymax)
    ax.set_yticks(range(0, ymax + 1, 10))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.set_xticks(centers)
    ax.set_xticklabels([g[3] for g in groups], fontsize=7.2, linespacing=1.2)
    ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=7.4, length=3)
    ax.tick_params(axis='x', length=0)
    ax.set_ylabel('share of runs resolved', fontsize=7.6)
    n_other = {n for _k, n in other20.values()}
    if len(n_other) != 1:
        stop(f'rederive_22.txt: the other tasks differ by arm: {other20}')
    note_a = (f'second seed: {d22["ran"]} of {d22["total"]} tasks, no rule has a verdict; on the other '
              f'{n_other.pop()} tasks of the first seed: ' + ', '.join(str(other20[a][0]) for a in ('N', 'ON', 'OA')))
    for k, line in enumerate(_wrap_pts(note_a, (XB[0] - 0.15 - XA[0]) * 72, 6.9, style='italic')):
        texts.append(page.text(XA[0], P1 + 0.50 + 0.13 * k, line, ha='left', va='center', fontsize=6.9, color=INK2,
                               style='italic'))
    # (b) and (c): one horizontal bar per arm, its label above it
    ROWS = len(arms22)
    row_h = (P1 - P0) / ROWS
    BAR = 0.17
    # the classes of (b) take no arm color: white with an outline, a dark green and a light tint of it
    segs = (('top', 'starts at line 1', 'white', INK), ('note', 'reads at a line the note gave', GREEN, 'white'),
            ('own', 'reads at a line of its own search', GREEN_TINT, INK))
    bx = axes_at(fig, XB[0], XB[1], P0, P1)
    bx.set_xlim(0, 100)
    bx.set_ylim(P1 - P0, 0)
    scale_b = (XB[1] - XB[0]) / 100
    for i, arm in enumerate(arms22):
        r = reach[arm]
        yc = row_h * (i + 0.62)
        label = 'control (same files)' if arm == 'N' else words[arm]
        texts.append(page.text(XB[0], P0 + yc - BAR / 2 - 0.035, label, ha='left', va='bottom', fontsize=FS,
                               color=INK))
        texts.append(page.text(XB[1], P0 + yc - BAR / 2 - 0.035, f'{r["n"]} reads', ha='right', va='bottom',
                               fontsize=6.6, color=INK2))
        left = 0.0
        for key, _lab, color, ink in segs:
            k = r[key]
            w = 100 * k / r['n']
            if k:
                edge = MUTED if color == 'white' else 'white'
                bx.barh(yc, w, left=left, height=BAR, color=color, edgecolor=edge, linewidth=0.6, zorder=2)
                t = bx.text(left + w / 2, yc, str(k), ha='center', va='center', fontsize=6.8, color=ink, zorder=3)
                texts.append(t)
                if width_in(fig, t) + 0.04 > w * scale_b:
                    stop(f'fig_oracle (b): the count {k} of arm {arm} does not fit its segment')
            left += w
        if abs(left - 100) > 1e-9:
            stop(f'fig_oracle (b): the shares of arm {arm} add to {left}')
    bx.set_yticks([])
    bx.set_xticks([0, 50, 100])
    bx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    bx.spines[['top', 'right', 'left']].set_visible(False)
    bx.tick_params(axis='x', labelsize=7.2, length=3)
    bx.set_xlabel("share of the arm's first reads", fontsize=7.2)
    ky = P1 + 0.50
    for _key, lab, color, _ink in segs:
        page.add_patch(Rectangle((XB[0], ky - 0.04), 0.14, 0.08, fc=color, ec=MUTED if color == 'white' else 'none',
                                 lw=0.6))
        texts.append(page.text(XB[0] + 0.20, ky, lab, ha='left', va='center', fontsize=6.9, color=INK))
        ky += 0.14
    # (c) mean lines read per run, and the two paired differences under it
    cx = axes_at(fig, XC[0], XC[1], P0, P1)
    cmax = float(max(mean.values()))
    step = 500
    xmax_c = step * (int(cmax // step) + 1)
    cx.set_xlim(0, xmax_c * 1.12)
    cx.set_ylim(P1 - P0, 0)
    for i, arm in enumerate(arms22):
        yc = row_h * (i + 0.62)
        v = float(mean[arm])
        texts.append(page.text(XC[0], P0 + yc - BAR / 2 - 0.035, words[arm], ha='left', va='bottom', fontsize=FS,
                               color=INK))
        cx.barh(yc, v, height=BAR, color=colors[arm], edgecolor=colors[arm], linewidth=0.6, zorder=2)
        texts.append(cx.text(v + 0.015 * xmax_c, yc, f'{int(whole(mean[arm])):,}', ha='left', va='center',
                             fontsize=6.8, color=INK, zorder=3))
    cx.set_yticks([])
    cx.set_xticks(range(0, xmax_c + 1, step))
    cx.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    cx.spines[['top', 'right', 'left']].set_visible(False)
    cx.tick_params(axis='x', labelsize=7.2, length=3)
    cx.set_xlabel('lines read per run, mean', fontsize=7.2)
    diff_lines = []
    for k, (a, b) in enumerate((('OF', 'ON'), ('OA', 'ON'), ('ON', 'N'))):
        p, lo, hi = diffs[(a, b)]
        diff_lines += [f'{words[a]} minus {words[b]}:',
                       f'{signed(p)}{" lines" if k == 0 else ""} [{signed(lo)}, {signed(hi)}]']
    PARSED.append(('fig_oracle', '(c) the three differences as drawn', ' | '.join(diff_lines), 'as parsed above', '-'))
    ky = P1 + 0.50
    for k, line in enumerate(diff_lines):
        texts.append(page.text(XC[0], ky + 0.13 * k + 0.04 * (k // 2), line, ha='left', va='center',
                               fontsize=6.9, color=INK if k % 2 else INK2))
    texts.append(page.text(XC[0], ky + 0.13 * len(diff_lines) + 0.04 * (len(diff_lines) // 2),
                           f'paired by task, 95% bootstrap ({d22["ran"]} tasks)', ha='left', va='center', fontsize=6.7,
                           color=MUTED, style='italic'))
    yn = FOOT
    for i, line in enumerate(foot):
        texts.append(page.text(0.09, yn + 0.13 * i, line, ha='left', va='top', fontsize=6.9, color=MUTED))
    # no two texts overlap (tick labels included)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for a in (ax, bx, cx):
        texts += [t for t in a.get_xticklabels() + a.get_yticklabels() + [a.xaxis.label, a.yaxis.label]
                  if t.get_text()]
    boxes = [(t, t.get_window_extent(renderer)) for t in texts]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][1].overlaps(boxes[j][1]):
                stop(f'fig_oracle: "{boxes[i][0].get_text()[:30]}" overlaps "{boxes[j][0].get_text()[:30]}"')
    # in (a), no count runs into a bar other than its own
    counts_a = [t for t in ax.texts]
    for i, t in enumerate(counts_a):
        tb = t.get_window_extent(renderer)
        for j, bar in enumerate(bars_a):
            if i != j and tb.overlaps(bar.get_window_extent(renderer)):
                stop(f'fig_oracle (a): the count "{t.get_text()}" runs into another bar')
    save(fig, page, out, 'fig_oracle')
    return True


def fig_oracle_one_seed(out, r22):
    """The earlier drawing (shown every region, final patch overlaps, resolved), used when analyze_22.txt is absent."""
    seed2, reg18, seed3 = parse_oracle(r22)
    n = seed2['N']['runs']
    arms = [a for a in ARMS18 if a[0] in seed2 or (seed3 and a[0] in seed3)]
    TOP = 0.42
    KEY_H = 0.30 + (0.40 if seed3 else 0)
    PLOT_H, AX_H = 2.15, 0.70
    note = ['Pre-registration 18: one whole run per task and arm, seed 2, on the same tasks. Shown every changed region: '
            'counted with every tool call paired with its result (the independent re-derivation of 18); the final '
            'patch and resolved: the registered analysis of 18.']
    if seed3:
        note.append(f'Seed 3: the registered analysis of 22 for every count; it counts the regions shown as the '
                    f'registered analysis of 18 does, which gives {reg18["N"]["every"]}, {reg18["ON"]["every"]} and '
                    f'{reg18["OA"]["every"]} for seed 2.')
    note = wrap(' '.join(note), 132)
    h_in = TOP + KEY_H + PLOT_H + AX_H + 0.13 * len(note) + 0.10
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, f'Told where the fix is ({n} tasks, {"two seeds" if seed3 else "one seed"})', ha='left',
              va='top', fontsize=10.5, color=INK)
    # the key: one swatch per arm, in one row, or in two columns when there are four arms
    x, y = 0.36, TOP + 0.10
    for i, (key, label, color) in enumerate(arms):
        if len(arms) > 3:
            x, y = (0.36, 3.60)[i % 2], TOP + 0.10 + 0.20 * (i // 2)
        page.add_patch(Rectangle((x, y - 0.045), 0.16, 0.09, fc=color, ec='none'))
        t = page.text(x + 0.22, y, label, ha='left', va='center', fontsize=7.8, color=INK)
        x += 0.22 + width_in(fig, t) + 0.22
        if x > W_IN or (len(arms) > 3 and i % 2 == 0 and x > 3.60):
            stop('fig_oracle: the key runs past its column')
    if seed3:
        y += 0.20
        page.add_patch(Rectangle((0.36, y - 0.045), 0.16, 0.09, fc=GREY, ec=GREY, lw=0.8))
        t = page.text(0.58, y, 'solid: pre-registration 18 (seed 2)', ha='left', va='center', fontsize=7.6, color=INK2)
        x = 0.58 + width_in(fig, t) + 0.30
        page.add_patch(Rectangle((x, y - 0.045), 0.16, 0.09, fc=GREY, ec=GREY, lw=0.8, alpha=0.35))
        page.add_patch(Rectangle((x, y - 0.045), 0.16, 0.09, fc='none', ec=GREY, lw=0.8))
        page.text(x + 0.22, y, f'light: pre-registration 22 (seed 3)', ha='left', va='center', fontsize=7.6, color=INK2)
    ax = axes_at(fig, 0.80, 6.90, TOP + KEY_H, TOP + KEY_H + PLOT_H)
    bars = []      # (arm, seed) in the order drawn within a group
    for key, _label, _c in arms:
        if key in seed2:
            bars.append((key, 2))
        if seed3 and key in seed3:
            bars.append((key, 3))
    bw = 0.8 / len(bars) * (0.88 if seed3 else 0.80)
    pitch = 0.8 / len(bars)
    colors = {k: c for k, _l, c in arms}
    for gi, (okey, _olabel, _st) in enumerate(OUTCOMES):
        for bi, (arm, seed) in enumerate(bars):
            xb = gi + (bi - (len(bars) - 1) / 2) * pitch
            val = (seed2 if seed == 2 else seed3)[arm][okey]
            c = colors[arm]
            if seed == 2:
                ax.bar(xb, val, width=bw, color=c, edgecolor=c, linewidth=0.6, zorder=2)
            else:
                ax.bar(xb, val, width=bw, color=c, alpha=0.35, linewidth=0, zorder=2)
                ax.bar(xb, val, width=bw, fill=False, edgecolor=c, linewidth=0.8, zorder=2)
            ax.text(xb, val + 0.5, str(val), ha='center', va='bottom', fontsize=7.4 if not seed3 else 6.8, color=INK,
                    zorder=3)
    ax.set_xlim(-0.55, len(OUTCOMES) - 0.45)
    ax.set_ylim(0, n)
    ax.set_xticks(range(len(OUTCOMES)))
    ax.set_xticklabels([lab for _k, lab, _s in OUTCOMES], fontsize=8.2)
    x0, x1 = ax.get_xlim()
    for gi, (_k, _lab, status) in enumerate(OUTCOMES):    # under each group: whether its outcome was registered
        page.text(0.80 + (gi - x0) / (x1 - x0) * (6.90 - 0.80), TOP + KEY_H + PLOT_H + 0.43, status, ha='center',
                  va='top', fontsize=7.2, color=MUTED, style='italic')
    ax.set_yticks(range(0, n + 1, 10))
    ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=7.8, length=3)
    ax.tick_params(axis='x', length=0)
    ax.set_ylabel(f'tasks, of {n}', fontsize=8.0)
    yn = TOP + KEY_H + PLOT_H + AX_H
    for i, line in enumerate(note):
        page.text(0.09, yn + 0.13 * i, line, ha='left', va='top', fontsize=6.9, color=MUTED)
    save(fig, page, out, 'fig_oracle')
    return seed3 is not None


# ================================================================ table_rules_v2
# The drawing of make_figures.py's table of rules (_draw_table and its helpers), copied here so that this script does
# not import make_figures.py (whose import runs the registered loaders). Unchanged except that it takes the color of
# the outcome cells from this script.
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.textpath import text_to_path  # noqa: E402

TABLE_FS = 10.6          # as make_figures.py: a capital about 12 px high in a writeup about 800 px wide
RULE_LIGHT = '#e1e1e1'
R02 = RES / 'explore_supplement.txt'     # what rules_main.json's row "02" points at
R03B4 = RES / 'explore_b.txt'            # what rules_main.json's row "03 B4" points at
R04 = RES / 'c' / 'analyze_c.txt'
R12 = RES / '12' / 'analyze_12.txt'
R14 = RES / '14' / 'analyze_14.txt'
R16 = RES / '16' / 'analyze_16.txt'
R17 = RES / '17' / 'analyze_17.txt'
TABLE_MD = ROOT / 'private' / 'table1-rows-nov11.md'     # optional: the paper's rows, only to compare the numbers
TABLE_NOTE = ('Estimates are differences in points with 95% bootstrap intervals unless marked. The number in '
              'parentheses is the pre-registration. Reasons 3 and 4 rest on exploratory counts and have no rule. '
              'Appendix A lists every registered rule.')
BOOT = RES / 'explore_cluster_bootstrap.txt'      # its last line: addresses minus names, the interval by task
OUTCOME_WORDS = ('met', 'not met', 'no detectable difference', 'no verdict')   # every part of an outcome starts so


def outcome_parts(outcome):
    """An outcome's parts: split at '; ' outside parentheses (a parenthesis may hold its own semicolon)."""
    parts, depth, cur = [], 0, ''
    i = 0
    while i < len(outcome):
        c = outcome[i]
        depth += (c == '(') - (c == ')')
        if depth == 0 and outcome.startswith('; ', i):
            parts.append(cur)
            cur, i = '', i + 2
            continue
        cur += c
        i += 1
    return parts + [cur]


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


def _draw_table(cols, fracs, body, note, out_dir, name):
    """One table image (make_figures.py). body: ('row', [cell, ...]) where a cell is a list of lines and a line a list
    of (text, size, weight, color, style) pieces set one after another."""
    fs, lh = TABLE_FS, TABLE_FS * 1.30
    pad_x, pad_y = 5.0, 3.4
    W = W_IN * 72
    xs = [W * sum(fracs[:i]) for i in range(len(fracs))]
    head = [_wrap_pts(c, W * fracs[i] - 2 * pad_x, fs, 'bold') for i, c in enumerate(cols)]
    head_h = max(len(h) for h in head) * lh + 2 * pad_y
    heights = [max(len(c) for c in rest[0]) * lh + 2 * pad_y for _kind, *rest in body]
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

    def put(x, y, pieces, limit):
        for text, size, weight, color, style in pieces:
            t = ax.text(x, y, text, ha='left', va='baseline', fontsize=size, fontweight=weight, color=color,
                        style=style)
            x += t.get_window_extent(renderer).width * 72 / fig.dpi + size * 0.28
            if x - size * 0.28 > limit + 0.5:
                stop(f'{name}: "{text}" runs past its column')

    y = H - 2
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    for i, h in enumerate(head):
        for k, line in enumerate(h):
            put(xs[i] + pad_x, y - pad_y - (k + 0.78) * lh, [(line, fs, 'bold', INK, 'normal')], W)
    y -= head_h
    ax.plot([0, W], [y, y], color=INK2, lw=0.6)
    for (_kind, *rest), h in zip(body, heights):
        for i, cell in enumerate(rest[0]):
            right = W * sum(fracs[:i + 1])
            for k, pieces in enumerate(cell):
                put(xs[i] + pad_x, y - pad_y - (k + 0.78) * lh, pieces, right)
        ax.plot([0, W], [y - h, y - h], color=RULE_LIGHT, lw=0.5)
        y -= h
    ax.plot([0, W], [y, y], color=INK2, lw=0.9)
    for k, line in enumerate(note_lines):
        ax.text(pad_x, y - pad_y - k * note_fs * 1.32, line, ha='left', va='top', fontsize=note_fs, color=INK2)
    fig.canvas.draw()
    check_fits(fig, ax, name)
    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'{name}.{ext}', dpi=DPI)
    plt.close(fig)


# The rows, in the paper's order: the wording of the first and third columns (text, not numbers) and how the second
# is read. An estimate is a list of parts joined by "; "; each part is read from a stored output by a function below.
def _pts(groups):
    return interval_text(*groups)


def est_02():
    s = Source(R02)
    _m, n = s.find(r'^  Following: P and H pooled minus A$', 'rule 02 (P and H pooled minus A)')
    m, line = s.find(r'^\s+95% by state: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule 02, by state', n, n + 1)
    s.record('table_rules_v2', '02: P and H pooled minus A, by state', _pts(m.groups()), line)
    return [_pts(m.groups())]


def est_03_and_ten():
    groups = parse_models()
    b3 = groups[0][1][0][1]
    others = [(lab, left) for _g, rows in groups[1:] for lab, left, _r in rows]
    if len(others) != 10:
        stop(f'table_rules_v2: {len(others)} other models for the name against the address, not ten')
    bad = [lab for lab, _e in others if VERDICTS.get((lab, 'left')) != 'met']
    if bad:
        stop(f'table_rules_v2: not met on {bad}: the row cannot say "met on each"')
    pts = sorted(others, key=lambda r: float(r[1][0]))
    rng = f'{num(pts[0][1][0])} to {num(pts[-1][1][0])}'
    PARSED.append(('table_rules_v2', f'03 B3; the ten others, lowest {pts[0][0]}, highest {pts[-1][0]} (each met)',
                   f'{interval_text(*b3)}; {rng}', 'as fig_models', '-'))
    return [interval_text(*b3), rng], 'met; met on each' + by_task_03(len(others))


def by_task_03(n_others):
    """The interval by task (tasks resampled) of addresses minus names: the last line of explore_cluster_bootstrap.txt
    counts the models whose interval lies above zero, Gemma-4-31B (03 B3, its summary row) among them. Returns the
    words added to the outcome, or '' (and a note in the printout) when the lines are not as expected."""
    if not BOOT.exists():
        PARSED.append(('table_rules_v2', '03 by task: not drawn', 'no file', rel(BOOT), '-'))
        return ''
    s = Source(BOOT)
    last = max(i for i, x in enumerate(s.lines) if x.strip())
    m = re.match(r'^Addresses minus names by task, (\d+) models .*: interval above zero on (\d+) of (\d+); not above '
                 r'zero: (.+?) \[([+-][\d.]+), ([+-][\d.]+)\]$', s.lines[last])
    b = re.compile(r'^  03 B3\s+([+-][\d.]+)\s+\[[+-][\d.]+, [+-][\d.]+\]\s+\[([+-][\d.]+), ([+-][\d.]+)\]')
    b3 = [(i, b.match(x)) for i, x in enumerate(s.lines) if b.match(x)]
    if not m or len(b3) != 1 or not int(m.group(1)) == int(m.group(3)) == n_others + 1:
        PARSED.append(('table_rules_v2', '03 by task: the last line is not as expected; outcome left "met; met on each"',
                       s.lines[last][:60], rel(BOOT), last + 1))
        return ''
    above, total = int(m.group(2)), int(m.group(3))
    gemma_above = Decimal(b3[0][1].group(2)) > 0
    others_above = above - (1 if gemma_above else 0)
    if not (gemma_above and (above, total) == (10, 11)):
        PARSED.append(('table_rules_v2', f'03 by task: above zero on {above} of {total} (Gemma-4-31B above: '
                       f'{gemma_above}); outcome left "met; met on each"', s.lines[last][:60], rel(BOOT), last + 1))
        return ''
    s.record('table_rules_v2', f'03 by task: interval above zero on (of models); not above (line {last + 1}); 03 B3 by '
             f'task (line {b3[0][0] + 1})', f'{above} of {total}; {m.group(4)} [{m.group(5)}, {m.group(6)}]; '
             f'[{b3[0][1].group(2)}, {b3[0][1].group(3)}]', last + 1)
    return f' (with tasks resampled: on {WORDS[others_above]})'


def est_12():
    s = Source(R12)
    m, line = s.find(r'^  P1, .*?: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule P1')
    s.record('table_rules_v2', '12 P1', _pts(m.groups()), line)
    return [_pts(m.groups())]


def est_12_p2():
    """Rule P2 of pre-registration 12: EPATH (a file, no lines) minus H (bare names), on opening a listed neighbor's
    file, with the verdict the report prints."""
    s = Source(R12)
    m, line = s.find(r"^  P2, EPATH - H on opening a listed neighbor's file: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]",
                     'rule P2')
    v, vline = s.find(r'^  P2 verdict: (.+?):', 'the verdict of P2')
    # registered as "met if the lower bound is above 0" (Appendix A): drawn "not met", as the appendix has it; the
    # report's own word ("not detected") is printed here only
    if Decimal(m.group(2)) > 0 or v.group(1) != 'not detected':
        stop(f'analyze_12.txt, line {line}: P2 has lower bound {m.group(2)}, verdict "{v.group(1)}"; the row says not met')
    s.record('table_rules_v2', f'12 P2, EPATH - H, opens a listed neighbor\'s file (verdict "{v.group(1)}", line '
             f'{vline})', _pts(m.groups()), line)
    return [_pts(m.groups())]


def steps_02():
    """The paused steps complete in every arm and seed of pre-registration 02's run (the run row 02 reports)."""
    s = Source(RES / 'analyze_a.txt')
    m, line = s.find(r'^states with every arm and seed present: (\d+) ', 'the complete states of 02')
    s2 = Source(R02)
    m2, line2 = s2.find(r'^  complete: (\d+) states, \d+ tasks$', 'the complete states of 02 (supplement)')
    if m.group(1) != m2.group(1):
        stop(f'analyze_a.txt line {line}: {m.group(1)} states; explore_supplement.txt line {line2}: {m2.group(1)}')
    s.record('table_rules_v2', f'02: steps complete in every arm and seed (= explore_supplement.txt:{line2})',
             m.group(1), line)
    return int(m.group(1))


def est_04():
    s = Source(R04)
    m, line = s.find(r'^  D_E 95%: .*\| swapped-out under E (\d+)/(\d+), decoy under Ep (\d+)/\2$', 'rule C1')
    v = f'{int(m.group(1)):,} against {int(m.group(3)):,} of {int(m.group(2)):,}'
    s.record('table_rules_v2', '04 C1: swapped-out under E against decoy under Ep', v, line)
    return [v]


def est_05_t1():
    """Rule T1 of pre-registration 05 (experiment D1): PE minus P, the entries legible inside the tool result."""
    s = Source(RES / 'd1' / 'analyze_d1.txt')
    m, line = s.find(r'^  T1 PE - P 95%: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]: (\w+)', 'rule T1 of 05')
    if m.group(4) != 'PASS':
        stop(f'analyze_d1.txt, line {line}: T1 is {m.group(4)}; the row says met')
    s.record('table_rules_v2', f'05 T1, PE - P ({m.group(4)})', _pts(m.groups()[:3]), line)
    return [_pts(m.groups()[:3])]


def est_04_es():
    """Rule C2 of pre-registration 04, its part ES (each entry with name and first definition line only, prereg/04
    line 27) minus H: "raises following" if the lower 95% bound is above 0. Fractions in the report, turned into
    points exactly."""
    s = Source(R04)
    m, line = s.find(r'^  ES minus H: (-?[\d.]+) \[(-?[\d.]+), (-?[\d.]+)\] \| ES \d+/\d+, H \d+/\d+$', 'C2, ES minus H')
    pts = [f'{Decimal(g) * 100:.2f}' for g in m.groups()]
    pts[0] = pts[0] if pts[0].startswith('-') else '+' + pts[0]
    if Decimal(m.group(2)) > 0:
        stop(f'analyze_c.txt, line {line}: ES minus H has its lower bound above 0; the row says not met')
    s.record('table_rules_v2', '04 C2, ES minus H (fractions x 100)', interval_text(*pts), line)
    return [interval_text(*pts)]


def est_13_x1():
    """Rule X1 of pre-registration 13: EG (the address written as a search hit) minus E (the address in a list), on
    reading a listed neighbor, with the verdict the report prints."""
    s = Source(RES / '13' / 'analyze_13.txt')
    m, line = s.find(r'^  X1, EG - E on reading a listed neighbor: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule X1')
    v, vline = s.find(r'^  X1 verdict: (.+)$', 'the verdict of X1')
    s.record('table_rules_v2', f'13 X1, EG - E (verdict "{v.group(1)}", line {vline})', _pts(m.groups()), line)
    return [_pts(m.groups())], v.group(1).strip()


def est_03_b4():
    s = Source(R03B4)
    m, line = s.find(r'^  E matched true - RE rewired, touch\s+([+-][\d.]+) \[ *([+-][\d.]+), +([+-][\d.]+)\]',
                     'rule B4 (E matched true - RE rewired)')
    s.record('table_rules_v2', '03 B4: E matched true - RE rewired, touch', _pts(m.groups()), line)
    return [_pts(m.groups())]


def est_15_and_eight():
    groups = parse_models()
    q1 = groups[0][1][0][2]
    others = [(lab, right) for _g, rows in groups[1:] for lab, _l, right in rows if right is not None]
    if len(others) != 8:
        stop(f'table_rules_v2: {len(others)} other models for the search, not eight')
    bad = [lab for lab, _e in others if VERDICTS.get((lab, 'right')) != 'met']
    if bad:
        stop(f'table_rules_v2: not met on {bad}: the row cannot say "met on each"')
    pts = sorted(others, key=lambda r: float(r[1][0]))
    rng = f'{num(pts[0][1][0])} to {num(pts[-1][1][0])}'
    PARSED.append(('table_rules_v2', f'15 Q1; the eight others, lowest {pts[0][0]}, highest {pts[-1][0]} (each met)',
                   f'{interval_text(*q1)}; {rng}', 'as fig_models', '-'))
    return [interval_text(*q1), rng]


def est_20(rule):
    s = Source(R20)
    if rule == 'T2':
        m, line = s.find(r'^  T2, the ratio TOLD / ASKED on USES THE LINE: ([\d.]+) \[([\d.]+), ([\d.]+)\]', 'rule T2')
        v = f'{m.group(1)} [{m.group(2)}, {m.group(3)}]'
    else:
        m, line = s.find(rf'^  {rule}, USES THE LINE under .*?: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]',
                         f'rule {rule}')
        v = _pts(m.groups())
    s.record('table_rules_v2', f'20 {rule}', v, line)
    return [v]


def est_20_t2():
    """Rule T2 of pre-registration 20 with its outcome: the ratio is under the registered two thirds, and its interval
    includes two thirds (both checked on the parsed values)."""
    s = Source(R20)
    m, line = s.find(r'^  T2, the ratio TOLD / ASKED on USES THE LINE: ([\d.]+) \[([\d.]+), ([\d.]+)\]', 'rule T2')
    pt, lo, hi = (Decimal(g) for g in m.groups())
    third2 = Decimal(2) / Decimal(3)
    if not (pt < third2 and lo <= third2 <= hi):
        stop(f'analyze_20.txt, line {line}: T2 {m.group(1)} [{m.group(2)}, {m.group(3)}]; the outcome says under two '
             'thirds with an interval that includes it')
    _v, vline = s.find(r'^  T2 verdict: .*below two thirds', 'the verdict of T2', line, line + 1)
    v = f'{m.group(1)} [{m.group(2)}, {m.group(3)}]'
    s.record('table_rules_v2', f'20 T2 (verdict below two thirds, line {vline}); under 2/3, interval includes 2/3', v,
             line)
    return [v], f'not met ({m.group(1)} is under two thirds; the interval includes it)'


def est_08_s1():
    """Rule S1 of pre-registration 08: E minus H, one step on the newest wheels (analyze_g.txt, part "one step")."""
    s = Source(R08)
    lo, hi = s.block(r'^PART "one step"', 'part "one step" of analyze_g.txt', end=r'^PART ')
    m, line = s.find(r'^  S1 E - H: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]$', 'rule S1 of 08', lo, hi)
    v, vline = s.find(r'^  S1 verdict: (.+)$', 'the verdict of S1', line, line + 1)
    if v.group(1) != 'the encoding effect holds on this harness':
        stop(f'analyze_g.txt, line {vline}: S1 verdict "{v.group(1)}"; the row says met')
    est = _pts(m.groups())
    if est != interval_text(*TYPED['S1']):
        stop(f'analyze_g.txt, line {line}: S1 {est}, the brief types {interval_text(*TYPED["S1"])}')
    s.record('table_rules_v2', f'08 S1, E - H, one step (verdict "{v.group(1)}", line {vline})', est, line)
    return [est]


def est_03_b1():
    """Rule B1 of pre-registration 03: D minus H, from its registered report (fractions, turned into points exactly)."""
    s = Source(R03)
    m, line = s.find(r'^  B1: (-?[\d.]+) \[(-?[\d.]+), (-?[\d.]+)\]$', 'rule B1 of 03')
    pts = [f'{Decimal(g) * 100:.2f}' for g in m.groups()]
    pts[0] = pts[0] if pts[0].startswith('-') else '+' + pts[0]
    if Decimal(m.group(2)) <= 0:
        stop(f'analyze_b.txt, line {line}: B1 has its lower bound at or under 0; the row says met')
    est = interval_text(*pts)
    if est != interval_text(*TYPED['B1']):
        stop(f'analyze_b.txt, line {line}: B1 {est}, the brief types {interval_text(*TYPED["B1"])}')
    s.record('table_rules_v2', '03 B1, D - H (fractions x 100; lower bound above 0)', est, line)
    return [est]


def est_20_t4():
    """Rule T4 of pre-registration 20: SEARCHES under TOLD minus under NONE, with the verdict the report prints."""
    s = Source(R20)
    m, line = s.find(r'^  T4, SEARCHES under TOLD minus under NONE: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule T4')
    v, vline = s.find(r'^  T4 verdict: (\w[\w ]*?):', 'the verdict of T4')
    s.record('table_rules_v2', f'20 T4, SEARCHES, TOLD minus NONE (verdict "{v.group(1)}", line {vline})',
             _pts(m.groups()), line)
    return [_pts(m.groups())], v.group(1)


def states_t3():
    """The paused steps rule T3 of pre-registration 20 is computed on (states complete in TOLD and TOLDX)."""
    s = Source(R20)
    m, line = s.find(r'^  states complete for T3 \(.*\): (\d+) of (\d+) \(floor \d+\)$', 'the states of T3')
    s.record('table_rules_v2', '20 T3: complete states (of those with a TOLDX record)', f'{m.group(1)} of {m.group(2)}',
             line)
    return int(m.group(1))


def est_14():
    s = Source(R14)
    m, line = s.find(r'^   T1 resolved: ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule T1 of 14')
    s.record('table_rules_v2', '14 T1 resolved', _pts(m.groups()), line)
    return [_pts(m.groups())]


def est_16_wording():
    """Rules W1 and W2 of pre-registration 16: the September wording of the tool lines against the current one, under
    the current listing (W1, CS minus C) and under the September listing (W2, S minus SC). Drawn only when both are
    met; returns (estimates, outcome) or None."""
    s = Source(R16)
    lo, hi = s.block(r'^1\. Rules', 'section 1 of analyze_16.txt', end=r'^\d\. ')
    parts, verdicts = [], []
    for rule, arms in (('W1', 'CS minus C'), ('W2', 'S minus SC')):
        m, line = s.find(rf'^  {rule}, {arms} .*?: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]$', f'rule {rule}', lo, hi)
        v, vline = s.find(rf'^  {rule} verdict: (.+?) \(', f'the verdict of {rule}', lo, hi)
        s.record('table_rules_v2', f'16 {rule}, {arms} (verdict "{v.group(1)}", line {vline})', _pts(m.groups()), line)
        parts.append(_pts(m.groups()))
        verdicts.append(v.group(1))
    return (parts, 'met') if verdicts == ['met', 'met'] else None


def est_16_listing():
    """Rule W3 of pre-registration 16: the September listing against the current one, under the current wording (SC
    minus C) and under the September wording (S minus CS), with the verdict the report prints for each."""
    s = Source(R16)
    lo, hi = s.block(r'^1\. Rules', 'section 1 of analyze_16.txt', end=r'^\d\. ')
    parts, verdicts = [], []
    for arms, wording in (('SC minus C', 'current'), ('S minus CS', 'September')):
        m, line = s.find(rf'^  W3, {arms} .*?: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]$', f'rule W3, {arms}', lo, hi)
        v, vline = s.find(rf'^  W3 verdict, under the {wording} wording: (.+)$', f'the verdict of W3 ({wording})', lo, hi)
        s.record('table_rules_v2', f'16 W3, {arms} (verdict "{v.group(1)}", line {vline})', _pts(m.groups()), line)
        parts.append(_pts(m.groups()))
        verdicts.append(v.group(1).strip())
    if verdicts[0] != verdicts[1]:
        stop(f'analyze_16.txt: W3 has two verdicts: {verdicts}')
    return parts, VERDICT_WORDS.get(verdicts[0], verdicts[0])


VERDICT_WORDS = {'more': 'met', 'not detected': 'no detectable difference',   # a report's verdict, in the table's words
                 'more graph calls with the September listing': "met (more graph calls with September's listing)"}


def est_18(rules):
    """Rules of pre-registration 18 with the verdict the report prints under each; returns (estimates, outcome)."""
    s = Source(R18)
    out, verdicts = [], []
    for rule, a, b in rules:
        m, line = s.find(rf'^   {rule} resolved, {a} against {b}: ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]',
                         f'rule {rule} of 18')
        v, _vline = s.find(r'^\s+verdict: (.+)$', f'the verdict of {rule}', line, line + 1)
        s.record('table_rules_v2', f'18 {rule} resolved, {a} against {b} (verdict "{v.group(1)}")',
                 _pts(m.groups()), line)
        out.append(_pts(m.groups()))
        verdicts.append(v.group(1).strip())
    if len(set(verdicts)) != 1:
        stop(f'analyze_18.txt: the rules {[r[0] for r in rules]} of one row have different verdicts {verdicts}')
    return out, VERDICT_WORDS.get(verdicts[0], verdicts[0])


TABLE_ROWS = (   # (reason, first column, the estimates, the outcome: a string, or None when the function gives it);
    # ordered by the paper's five reasons (rows of 22 come last, under reason 5)
    # reason 1: the graph's answers seldom reach the agent
    (1, 'First call goes to a graph tool, the September file listing against the current one, under either wording '
        'of the tool lines (16)', est_16_listing, None),
    (1, 'First call goes to a graph tool, the September wording of the tool lines against the current one, under '
        'either listing (16)', est_16_wording, None),
    (1, 'Told against nothing (20)', lambda: est_20('T1'), 'met'),
    (1, 'Told as a share of asked; registered threshold two thirds (20)', est_20_t2, None),
    (1, 'Next call is a search, told against nothing (20)', est_20_t4, None),
    (1, lambda: f'Told its own hits against those of another search, {states_t3()} steps (20)', lambda: est_20('T3'),
     'not met'),
    (1, lambda: f'A line in a note against nothing, {WORDS[len(parse_24()["models"])]} hosted models (24)',
     lambda: est_24('W1'), None),
    (1, lambda: f'The same line in a search result against in a note, {WORDS[len(parse_24()["models"])]} hosted '
                'models (24)', lambda: est_24('W2'), None),
    # reason 2: the answers are names, and the agent acts on addresses
    (2, 'Addresses against names (03); on ten other models (05, 10, 19)', est_03_and_ten, None),
    (2, 'Addresses against names inside a tool result (05)', est_05_t1, 'met'),
    (2, 'Addresses against names on the October release (08)', est_08_s1, 'met'),
    (2, lambda: f"Names against no list, reads a neighbor's code, on {steps_02()} steps (02)", est_02, 'not met'),
    (2, 'Names with an instruction to read them against names (03)', est_03_b1, 'met'),
    (2, 'File and lines against file only (12)', est_12, 'met'),
    (2, "File only against names, opens the neighbor's file (12)", est_12_p2, 'not met'),
    (2, 'Names with their definition line against names (04)', est_04_es, 'not met'),
    (2, 'Addresses written as search hits against as a list (13)', est_13_x1, None),
    (2, 'True against false entry (04)', est_04, 'met'),
    (2, 'True against rewired list (03)', est_03_b4, 'not met'),
    (2, 'Search with against without line numbers (15); on eight other models (17, 19)', est_15_and_eight,
     'met; met on each'),
    # whole runs (14, then 23; the paper's Section 4): 23 drawn only when analysis/results/23/analyze_23.txt exists
    (2, 'Whole runs: tool answers with addresses and the line-bound repair, against as shipped, resolved (14)', est_14,
     'no detectable difference'),
    (2, 'Graph neighbors pushed with file reads, with addresses against as names: first reads of a listed file that '
        'start past line 1 (23)', lambda: est_23('A1'), None),
    (2, 'The same: lines read per run (23)', lambda: est_23('A2'), None),
    (2, 'The same: resolved (23)', lambda: est_23('A3'), None),
    # reason 5: knowing where is not enough
    (5, 'Oracle, lines against control, resolved (18)', lambda: est_18((('U1', 'OA', 'N'),)), None),
    (5, 'Oracle, names against control; lines against names (18)',
     lambda: est_18((('U4', 'ON', 'N'), ('U2', 'OA', 'ON'))), None),
)
def rows_22(path):
    """Pre-registration 22 as ONE row: the resolved count of each arm (section 3), the rules it registered (section 2),
    and why none has a verdict (the registered floor of tasks)."""
    d = parse_22(Path(path))
    if not d['no_verdict']:
        stop(f'{d["file"]}: a rule of 22 has a verdict; the one row of the table says none has')
    if d['ran'] >= d['floor']:
        stop(f'{d["file"]}: {d["ran"]} tasks ran, not under the floor of {d["floor"]}')
    words = dict((k, lab) for k, lab, _c in ARMS18)
    label = (f'Second seed of the oracle runs, {WORDS[len(d["arms"])]} arms, {d["ran"]} of {d["total"]} tasks ran '
             '(22)')
    est = ('resolved: ' + ', '.join(f'{words[a]} {d["sec"][a]["resolved"]}' for a in d['arms']) +
           f' of {d["ran"]}')
    outcome = f'no verdict: under the registered floor of {d["floor"]} tasks'
    PARSED.append(('table_rules_v2', '22, one row: label | estimate | outcome', f'{label} | {est} | {outcome}',
                   'as fig_oracle (analyze_22.txt)', '-'))
    return [(label, [est], outcome)]


def _numbers(text):
    return [Decimal(x.replace('−', '-').replace(',', '')) for x in re.findall(r'[+\-−]?\d[\d,]*(?:\.\d+)?', text)]


def compare_markdown(rows):
    """Each estimate against the paper's row (when the private file is there): every number, rounded half up to the
    decimals the paper prints, must be the paper's number."""
    if not TABLE_MD.exists():
        return ['no private table file: the estimates were not compared with the paper']
    md = {}
    for line in TABLE_MD.read_text(encoding='utf-8').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 3 and cells[0] not in ('Rule (registration)', '---'):
            md[cells[0]] = cells[1]
    out = []
    for label, parts, _o in rows:
        mine = '; '.join(parts)
        paper = md.get(label)
        if paper is None:
            out.append(f'{label}: not in the paper\'s table; drawn {mine}')
            continue
        want = re.findall(r'[+\-−]?\d[\d,]*(?:\.\d+)?', paper)
        got = _numbers(mine)
        verdict = 'match'
        if len(want) != len(got):
            verdict = 'MISMATCH (a different count of numbers)'
        else:
            for w, g in zip(want, got):
                q = Decimal(1).scaleb(-len(w.split('.')[1])) if '.' in w else Decimal(1)
                if g.quantize(q, rounding='ROUND_HALF_UP') != Decimal(w.replace('−', '-').replace(',', '')):
                    verdict = f'MISMATCH ({g} rounds to {g.quantize(q, rounding="ROUND_HALF_UP")}, the paper has {w})'
                    break
        out.append(f'{label}: drawn {mine} | paper {paper} | {verdict}')
    return out


# ---------------------------------------------------------------- pre-registration 23 (three rows, drawn only when its
# registered report exists). REPORT_23 (environment) points the parser at another file, for testing; a stand-in report
# (its first line says STAND-IN) is refused when the output directory is paper/figures.
R23 = RES / '23' / 'analyze_23.txt'
OUT_DIR = [FIG]          # set by main()
V23 = {'A1': {'an address moves the read': 'met', 'not detected': 'not met'},
       'A2': {'an address saves reading': 'met', 'not detected': 'not met'},
       'A3': {'more': 'met (more)', 'fewer': 'met (fewer)', 'no detectable difference': 'no detectable difference'}}
EST = r'(?:n/a|([+-][\d.]+) {unit} \[([+-][\d.]+), ([+-][\d.]+)\])'


def _verdict_23(rule, v, line):
    """The table's words for a verdict of 23 as the report prints it (analysis/analyze_23.py, verdict_of)."""
    if v in V23[rule]:
        return V23[rule][v], True
    if v.startswith('no verdict'):
        return v, False
    if v == 'not read (gate G0 not met)':
        return 'no verdict (gate G0 not met)', False
    if v == 'no pairs: no estimate':
        return 'no verdict (no pairs: no estimate)', False
    stop(f'analyze_23.txt, line {line}: {rule} verdict "{v}" is none of the words the script prints')


@functools.lru_cache(maxsize=None)
def parse_23():
    """G0 (the two shares and the gate), A1, A2 and A3 of the registered report of 23; None when it does not exist."""
    path = Path(os.environ['REPORT_23']) if os.environ.get('REPORT_23') else R23
    if not path.exists():
        return None
    s = Source(path)
    if not s.lines or not s.lines[0].startswith('EXPERIMENT 23: '):
        stop(f'{rel(path)}: the first line is not the report of experiment 23')
    if 'STAND-IN' in s.lines[0] and Path(OUT_DIR[0]).resolve() == FIG.resolve():
        stop(f'{rel(path)} is a stand-in report: its numbers are never drawn into {rel(FIG)}')
    g0, g1 = s.block(r'^2\. G0, gate', 'section 2 (G0) of analyze_23.txt', end=r'^\d\. ')
    shares = {}
    for arm in ('PH', 'PE'):
        m, ln = s.find(rf'^   {arm}: (?:(\d+) of (\d+) \(([\d.]+)%\)|(not run in this launch))', f'G0, {arm}', g0, g1)
        shares[arm] = None if m.group(4) else (int(m.group(1)), int(m.group(2)), m.group(3))
        s.record('table_rules_v2', f'23 G0, {arm}: entered runs with a pushed list',
                 'not run' if m.group(4) else f'{m.group(1)} of {m.group(2)} ({m.group(3)}%)', ln)
    m, gl = s.find(r'^   gate: (MET|NOT MET)$', 'G0, the gate', g0, g1)
    gate = m.group(1) == 'MET'
    reached = all(x is not None and x[1] and 5 * x[0] >= 4 * x[1] for x in shares.values())    # at least 80%
    if gate != reached:
        stop(f'analyze_23.txt, line {gl}: gate {m.group(1)}, the shares {shares}')
    s.record('table_rules_v2', '23 G0, the gate (at least 80% in each push arm)', m.group(1), gl)
    r0, r1 = s.block(r'^3\. Rules', 'section 3 (rules) of analyze_23.txt', end=r'^\d\. ')
    out = dict(gate=gate)
    m, ln = s.find(r'^   A1 first READ of a pushed file past line 1, per task PE minus PH: ' + EST.format(unit='points') +
                   r' on (\d+) tasks with an A1 READ in both runs \(of (\d+) tasks where both entered\)', 'rule A1',
                   r0, r1)
    est = 'no estimate' if m.group(1) is None else f'{_pts(m.groups()[:3])} on {m.group(4)} tasks'
    out['A1'] = dict(est=[est], line=ln)
    s.record('table_rules_v2', '23 A1, first reads past line 1, PE - PH (points; tasks with an A1 read in both; of '
             'tasks both entered)', f'{est} (of {m.group(5)})', ln)
    m, ln = s.find(r'^   A2 LINES READ per run, PE minus PH: ' + EST.format(unit='lines') + r'; .*; (\d+) tasks$',
                   'rule A2', r0, r1)
    est = 'no estimate' if m.group(1) is None else f'{_pts(m.groups()[:3])} lines'
    out['A2'] = dict(est=[est], line=ln)
    s.record('table_rules_v2', '23 A2, lines read per run, PE - PH (tasks)', f'{est} ({m.group(4)} tasks)', ln)
    m, ln = s.find(r'^   A3 resolved, PE against PH: ' + EST.format(unit='points') + r'; PE (\d+) of (\d+)(?: \([\d.]+%\))?, '
                   r'PH (\d+) of (\d+)(?: \([\d.]+%\))?; (\d+) tasks;', 'rule A3', r0, r1)
    if not m.group(5) == m.group(7) == m.group(8):
        stop(f'analyze_23.txt, line {ln}: A3 counts of {m.group(5)}, {m.group(7)} and {m.group(8)} tasks')
    counts = f'{int(m.group(4)):,} against {int(m.group(6)):,} of {int(m.group(8)):,}'
    est = 'no estimate' if m.group(1) is None else _pts(m.groups()[:3])
    out['A3'] = dict(est=[counts, est], line=ln)
    s.record('table_rules_v2', '23 A3, resolved, PE against PH of the tasks both entered; PE - PH (points)',
             f'{counts}; {est}', ln)
    for rule in ('A1', 'A2', 'A3'):
        v, vl = s.find(r'^      verdict: (.+)$', f'the verdict of {rule}', out[rule]['line'], out[rule]['line'] + 1)
        words, real = _verdict_23(rule, v.group(1).strip(), vl)
        if real and not gate:
            stop(f'analyze_23.txt, line {vl}: {rule} prints the verdict "{v.group(1)}" with the gate G0 not met')
        if real and out[rule]['est'][-1] == 'no estimate':
            stop(f'analyze_23.txt, line {vl}: {rule} prints a verdict without an estimate')
        out[rule]['outcome'] = words
        s.record('table_rules_v2', f'23 {rule} verdict (as the table words it: {words})', v.group(1).strip(), vl)
    return out


def est_23(rule):
    """A row of 23: (estimates, outcome), or None (the row is not drawn) while the report does not exist."""
    d = parse_23()
    return None if d is None else (d[rule]['est'], d[rule]['outcome'])


def table_rules(out, r22):
    rows, reasons = [], []
    for reason, label, fn, outcome in TABLE_ROWS:
        label = label() if callable(label) else label       # a label with a parsed number in it
        got = fn()
        if got is None:          # a row drawn only when its rules are met (W1 and W2)
            continue
        rows.append((label, *got) if outcome is None else (label, got, outcome))
        reasons.append(reason)
    p22 = Path(r22) if r22 else R22
    if p22.exists():
        rows += rows_22(p22)
        reasons.append(5)
    if reasons != sorted(reasons):
        stop(f'table_rules_v2: the rows are not ordered by reason: {reasons}')
    # one vocabulary of outcomes: every part starts with met, not met, no detectable difference or no verdict
    for label, _p, outcome in rows:
        for part in outcome_parts(outcome):
            if not any(part == w or part.startswith(w + ' ') or part.startswith(w + ':') for w in OUTCOME_WORDS):
                stop(f'table_rules_v2: the outcome "{part}" of "{label[:40]}" is not in the words {OUTCOME_WORDS}')
    cols = ['Reason', 'Rule (registration)', 'Estimate', 'Outcome']
    fracs = [0.095, 0.48, 0.255, 0.170]
    W = W_IN * 72
    body = []
    for reason, (label, parts, outcome) in zip(reasons, rows):
        cell0 = [[(str(reason), TABLE_FS, 'normal', INK, 'normal')]]
        cell1 = [[(line, TABLE_FS, 'normal', INK, 'normal')] for line in
                 _wrap_pts(_display(label), W * fracs[1] - 10, TABLE_FS)]
        est_lines = []
        for k, p in enumerate(parts):
            est_lines += _wrap_pts(_display(p) + (';' if k < len(parts) - 1 else ''), W * fracs[2] - 10, TABLE_FS)
        cell2 = [[(line, TABLE_FS, 'normal', INK, 'normal')] for line in est_lines]
        # the met color when the first part of the outcome is met (or met on each); neutral otherwise
        met = outcome.split(';')[0].split(' (')[0] in ('met', 'met on each')
        style = ('bold', BLUE, 'normal') if met else ('normal', INK, 'normal')
        o_lines = []
        o_parts = outcome_parts(outcome)
        for k, part in enumerate(o_parts):
            o_lines += _wrap_pts(part + (';' if k < len(o_parts) - 1 else ''), W * fracs[3] - 10, TABLE_FS, style[0])
        cell3 = [[(line, TABLE_FS, *style)] for line in o_lines]
        body.append(('row', [cell0, cell1, cell2, cell3]))
    _draw_table(cols, fracs, body, TABLE_NOTE, out, 'table_rules_v2')
    return compare_markdown(rows)


# ================================================================ table_populations
STATES_B = ROOT / 'analysis' / 'fork_states' / 'states.jsonl'      # the first replay population
MANIFEST_T = ROOT / 'analysis' / 'fork_states_t' / 'manifest.json'
TASKS_18 = ROOT / 'analysis' / 'oracle_18' / 'tasks_18.txt'
TABLE2_MD = ROOT / 'private' / 'table2-rows-nov11.md'               # optional: the paper's rows, only to compare
POP_FRACS = [0.47, 0.42, 0.11]                                       # the widths of the columns of table_populations


def population_rows(r22):
    """The five populations, every size read from a stored file; [(population, size, where)]."""
    import json
    # 1. the paused steps of the first replays: states, runs and tasks of the states file; the report's header agrees
    states = [json.loads(line) for line in STATES_B.read_text(encoding='utf-8').splitlines() if line.strip()]
    n_states = len(states)
    n_runs = len({(s['task'], s['run']) for s in states})
    n_tasks = len({s['task'] for s in states})
    PARSED.append(('table_populations', 'paused steps; runs; tasks (states file)', f'{n_states}; {n_runs}; {n_tasks}',
                   rel(STATES_B), f'1-{n_states}'))
    sb = Source(R03)
    m, line = sb.find(r'^\d+ replays .* over (\d+) states$', 'the states of analyze_b.txt')
    if int(m.group(1)) != n_states:
        stop(f'analyze_b.txt counts {m.group(1)} states, the states file {n_states}')
    sb.record('table_populations', 'states (header of analyze_b.txt)', m.group(1), line)
    # 2. the search steps (pre-registration 15) and those that can be cut one call earlier (20)
    s15 = Source(R15)
    m, line = s15.find(r'^  (\d+) states, \d+ records;', 'the states of analyze_15.txt')
    n_search = int(m.group(1))
    s15.record('table_populations', 'search steps (header of analyze_15.txt)', m.group(1), line)
    man = json.loads(MANIFEST_T.read_text(encoding='utf-8'))['counts']
    if man['states_of_15'] != n_search:
        stop(f'fork_states_t/manifest.json: states_of_15 {man["states_of_15"]}, analyze_15.txt {n_search}')
    n_cut = man['states_kept']
    PARSED.append(('table_populations', 'search steps; kept when cut one call earlier (manifest counts)',
                   f'{man["states_of_15"]}; {n_cut}', rel(MANIFEST_T), 'counts'))
    # 3. the public runs of the starter agent, without and with the skill (section 3 of explore_read_starts.txt)
    ss = Source(STARTS)
    s3, e3 = ss.block(r'^3\. Where the fix lies', 'section 3', end=r'^\d\. ')
    pub = []
    for head, what in ((STARTER, 'without the skill'),
                       (r'^the same agent with a graph skill, public runs \(GraphLoc skill arm\)', 'with the skill')):
        m, line = ss.find(head + r': runs of tasks with a CHANGED REGION (\d+), tasks (\d+)$', f'public runs, {what}',
                          s3, e3)
        runs, tasks = int(m.group(1)), int(m.group(2))
        if runs % tasks:
            stop(f'explore_read_starts.txt: {what}: {runs} runs on {tasks} tasks')
        pub.append((tasks, runs // tasks))
        ss.record('table_populations', f'public runs {what}: runs; tasks', f'{runs}; {tasks}', line)
    if pub[0] != pub[1]:
        stop(f'explore_read_starts.txt: the two public sets differ: {pub}')
    pub_tasks, pub_per = pub[0]
    # every run of the two public sets (section 1); one task is fixed by adding a file (no GOLD FILE in analyze_14.txt,
    # line 16) and so has no CHANGED REGION
    s1, e1 = ss.block(r'^1\. Where a READ starts', 'section 1', end=r'^2\. ')
    allpub = []
    for head, what in ((STARTER, 'without the skill'),
                       (r'^the same agent with a graph skill, public runs \(GraphLoc skill arm\)', 'with the skill')):
        m, line = ss.find(head + r': runs (\d+), tasks (\d+)$', f'all public runs, {what}', s1, e1)
        allpub.append((int(m.group(1)), int(m.group(2))))
        ss.record('table_populations', f'all public runs {what}: runs; tasks', f'{m.group(1)}; {m.group(2)}', line)
    if allpub[0] != allpub[1]:
        stop(f'explore_read_starts.txt: the two public sets differ: {allpub}')
    all_runs, all_tasks = allpub[0]
    if all_runs != pub_per * all_tasks or all_runs - pub_per * pub_tasks != pub_per * (all_tasks - pub_tasks):
        stop(f'explore_read_starts.txt: {all_runs} runs of {all_tasks} tasks against {pub_per} runs of {pub_tasks}')
    s14 = Source(R14)
    m, line = s14.find(r'tasks with no GOLD FILE \(.*\): (\S+)$', 'the tasks with no gold file')
    no_gold = m.group(1).split(', ')
    s14.record('table_populations', 'tasks with no GOLD FILE (fixed by adding a file)', ', '.join(no_gold), line)
    if len(no_gold) != all_tasks - pub_tasks:
        stop(f'analyze_14.txt: {len(no_gold)} tasks with no gold file, {all_tasks - pub_tasks} public tasks without a '
             'changed region')
    # the replay contrasts on the first population: the steps complete in all arms of each (03, 04, 12)
    complete = []
    for path, pat in ((R03, r'^arms: .*; states complete across all arms and seeds: (\d+)$'),
                      (R04, r'^arms: .*; states complete across all arms and seeds: (\d+) \(of \d+'),
                      (R12, r'^  complete states \(.*\): (\d+) of \d+$')):
        sc = Source(path)
        m, line = sc.find(pat, f'the complete states of {rel(path)}')
        complete.append(int(m.group(1)))
        sc.record('table_populations', 'steps complete in all arms of the contrast', m.group(1), line)
    # 4. our runs as shipped (pre-registration 14)
    s14 = Source(R14)
    m, line = s14.find(r'^   N\s+runs with a task result (\d+) \(seed 1: (\d+)\)', 'our runs as shipped')
    ours, ours_seed1 = int(m.group(1)), int(m.group(2))
    m2, line2 = s14.find(r'ENTER the paired analysis (\d+) \((\d+) tasks;', 'the tasks of 14')
    if not ours == ours_seed1 == int(m2.group(1)) == int(m2.group(2)):
        stop(f'analyze_14.txt: runs {ours}, seed 1 {ours_seed1}, tasks {m2.group(2)}')
    s14.record('table_populations', 'our runs as shipped (N): runs, all seed 1; tasks (line %d)' % line2,
               f'{ours}; {m2.group(2)}', line)
    # 4a. our other whole-run arms: 14 with addresses and the line-bound repair (NAF, seed 1); 23 pushed (PH, PE, seed 2,
    # drawn only when its registered report exists). One task result per task: lines, and distinct task ids.
    def task_results(path):
        if not path.exists():
            stop(f'{rel(path)} is missing')
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
        ids = {r['instance_id'] for r in rows}
        if len(ids) != len(rows) or len(rows) != RUNS_PER_ARM:
            stop(f'{rel(path)}: {len(rows)} task results, {len(ids)} distinct tasks; the row says {RUNS_PER_ARM}, one '
                 'run each')
        PARSED.append(('table_populations', 'task results; distinct tasks', f'{len(rows)}; {len(ids)}', rel(path),
                       f'1-{len(rows)}'))
        return len(rows)
    n14 = task_results(RES / '14' / 'NAF' / 'seed1' / 'task_results.jsonl')
    more_ours = [("the same with addresses in the tools' answers and the line-bound repair (14)",
                  f'{n14} tasks, one run each', '4')]
    if R23.exists():
        n23 = {arm: task_results(RES / '23' / arm / 'seed2' / 'task_results.jsonl') for arm in ('PH', 'PE')}
        more_ours.append(('the same with graph neighbors pushed with file reads, as names and with addresses (23)',
                          f'{n23["PE"]} tasks, one run each, seed 2', '4'))
    # 4b. the first model calls of pre-registration 16: its arms, its seeds, the tasks complete on every arm
    s16 = Source(R16)
    m, line = s16.find(r'^PRE-REGISTRATION 16: .*\(arms ([\w, ]+)\)$', 'the arms of 16')
    arms16 = [a.strip() for a in m.group(1).split(',')]
    m2, line2 = s16.find(r'^  \d+ tasks, .*calls planned \d+ \(seeds ([\d, ]+)\);', 'the seeds of 16')
    seeds16 = [x.strip() for x in m2.group(1).split(',')]
    m3, line3 = s16.find(r'^  tasks complete on every arm \(.*\): (\d+) of \d+$', 'the tasks of 16')
    m4, _l4 = s16.find(r'^1\. Rules, on the (\d+) tasks complete on every arm', 'the tasks of the rules of 16')
    if m3.group(1) != m4.group(1):
        stop(f'analyze_16.txt: {m3.group(1)} tasks complete, the rules on {m4.group(1)}')
    p16 = dict(arms=len(arms16), seeds=len(seeds16), tasks=int(m3.group(1)))
    s16.record('table_populations', f'16: arms (line {line}); seeds (line {line2}); tasks complete on every arm',
               f'{", ".join(arms16)}; {", ".join(seeds16)}; {m3.group(1)}', line3)
    # 5. the oracle runs (18, and 22 when its report exists)
    t18 = [t for t in TASKS_18.read_text(encoding='utf-8').split() if t]
    PARSED.append(('table_populations', 'oracle tasks (task list)', str(len(t18)), rel(TASKS_18), f'1-{len(t18)}'))
    s18 = Source(R18)
    m, line = s18.find(r'^   tasks of tasks_18\.txt: (\d+)$', 'the tasks of analyze_18.txt')
    if int(m.group(1)) != len(t18):
        stop(f'analyze_18.txt: {m.group(1)} tasks, the task list {len(t18)}')
    m, line = s18.find(r'^1\. Runs per arm on the (\d+) tasks \(([\w, ]+): experiment 18', 'the arms of 18')
    arms18 = [a.strip() for a in m.group(2).split(',')]
    s18.record('table_populations', 'oracle: tasks; arms of 18', f'{m.group(1)}; {", ".join(arms18)}', line)
    oracle = f'{len(t18)} of those tasks, {WORDS[len(arms18)]} arms'
    p22 = Path(r22) if r22 else R22
    if p22.exists():
        d22 = parse_22(p22)
        if d22['total'] != len(t18):
            stop(f'{d22["file"]}: {d22["total"]} tasks in the task list, tasks_18.txt {len(t18)}')
        oracle = (f'{len(t18)} tasks, one seed, {WORDS[len(arms18)]} arms; second seed, {WORDS[len(d22["arms"])]} '
                  f'arms, {d22["ran"]} of the {d22["total"]} tasks')
        PARSED.append(('table_populations', 'oracle row, with the second seed', oracle,
                       'as fig_oracle (analyze_22.txt)', '-'))
    first = (f'{n_states} steps of {n_runs} public runs, {n_tasks} tasks; a contrast uses the {min(complete)} to '
             f'{max(complete)} steps complete in all its arms')
    label = 'Steps paused after a file view that shows a function with graph neighbors'
    width = W_IN * 72 * POP_FRACS[1] - 10
    if len(_wrap_pts(first, width, TABLE_FS)) > len(_wrap_pts(label, W_IN * 72 * POP_FRACS[0] - 10, TABLE_FS)):
        first = f'{n_states} steps of {n_runs} public runs, {n_tasks} tasks'      # the addition does not fit
    PARSED.append(('table_populations', 'first row, size as drawn', first, 'as parsed above', '-'))
    return [
        (label, first, '4'),
        ('Steps paused after the agent\'s own search', f'{n_search} steps; {n_cut} can also be cut one call earlier',
         '3, 4'),
        ('Public runs of the starter agent [2]',
         f'{all_tasks} tasks, {WORDS[pub_per]} runs with the skill and {WORDS[pub_per]} without ({all_runs} runs '
         f'each); counts of changed regions use the {pub_tasks} tasks whose fix changes an existing line '
         f'({pub_per * pub_tasks} runs)', '3, 5, 6'),
        ('Our runs, harness as shipped (Oct 12)', f'the {ours} tasks our sandbox can score, one run each', '3, 4'),
        *more_ours,
        (f'First calls under {WORDS[p16["arms"]]} task prompts',
         f'{p16["tasks"]} tasks, {WORDS[p16["seeds"]]} seeds, one model call each', '3'),
        ('Oracle runs', oracle, '7'),
    ]


def table_populations(out, r22):
    rows = population_rows(r22)
    with22 = (Path(r22) if r22 else R22).exists()
    if TABLE2_MD.exists():     # the paper's rows: every size must be the one built from the stored files
        md = []
        for line in TABLE2_MD.read_text(encoding='utf-8').splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) == 3 and cells[0] not in ('Population', '---'):
                md.append(tuple(cells))
        # the paper's table is being rewritten from this one, so a difference is printed, not a stop
        if len(md) != len(rows):
            print(f'table_populations: {len(md)} rows in the paper, {len(rows)} here')
        for k, (mine, paper) in enumerate(zip(rows, md)):
            for i, col in enumerate(('population', 'size', 'where')):
                if mine[i] != paper[i] and not (i == 1 and with22 and k == len(rows) - 1):
                    print(f'table_populations, row {k + 1}, {col}: drawn "{mine[i]}" | paper "{paper[i]}"')
    cols = ['Population', 'Size', 'Where']
    fracs = POP_FRACS
    W = W_IN * 72
    body = []
    for row in rows:
        body.append(('row', [[[(line, TABLE_FS, 'normal', INK, 'normal')] for line in
                               _wrap_pts(cell, W * fracs[i] - 10, TABLE_FS)] for i, cell in enumerate(row)]))
    _draw_table(cols, fracs, body, None, out, 'table_populations')
    return rows


# ================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    ap.add_argument('--r22', default=None, help='read this file in place of analysis/results/22/analyze_22.txt')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    OUT_DIR[0] = out
    fig_models(out)
    fig_asked_told(out)
    fig_graph(out)
    fig_moves(out)
    with22 = fig_oracle(out, args.r22)
    against_paper = table_rules(out, args.r22)
    table_populations(out, args.r22)
    w1 = max(len(r[0]) for r in PARSED)
    w2 = max(len(r[1]) for r in PARSED)
    w3 = max(len(r[2]) for r in PARSED)
    print('Parsed numbers (figure, quantity, value, file:line)')
    for figname, q, v, f, ln in PARSED:
        print(f'  {figname:<{w1}}  {q:<{w2}}  {v:<{w3}}  {f}:{ln}')
    print(f'fig_oracle: seed 3 (pre-registration 22) {"drawn" if with22 else "not drawn: no " + rel(R22)}')
    print('table_rules_v2, each estimate against the row of the paper (rounded half up to its decimals):')
    for line in against_paper:
        print(f'  {line}')
    print(f'wrote fig_models, fig_asked_told, fig_graph, fig_moves, fig_oracle, table_rules_v2 and table_populations (.png at {DPI} dpi, '
          f'.svg) in {out}')


if __name__ == '__main__':
    main()
