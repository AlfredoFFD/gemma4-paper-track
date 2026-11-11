"""Figures of the rebuilt paper: models, asked against told, what an edge is, where reads start, told where the fix is.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures_v2.py [--out <dir>] [--r22 <file>]

Writes, next to this script (or into --out), each as .png (200 dpi) and .svg:
  fig_models      a name against an address, and a search with and without its line numbers, by model (eleven models)
  fig_asked_told  a line the agent was told is used, less often than one it asked for
  fig_graph       what an edge of the code graph is
  fig_moves       where a file read starts, and how many places a fix has
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
  analysis/results/explore_read_starts.txt   where reads start (section 1), the cut by number of changed regions
                                             (section 3), exploratory
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
}

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
    ('Qwen3-30B', 'qwen3-30b-a3b'), ('Qwen3-235B', 'qwen3-235b-a22b'), ('gpt-oss-120B', 'gpt-oss-120b'),
    ('DeepSeek-V4.1-Flash', 'deepseek-v4.1-flash'), ('GLM-5.3-Flash', 'glm-5.3-flash'),
    ('MiniMax-M3.1-Flash', 'minimax-m3.1-flash'), ('Nemotron-3-Super-120B', 'nemotron-3-super-120b'),
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
    h_in = TOP + rows_h + AXIS + 0.13 * len(note) + 0.10
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
        ax.text(r['hi'] + 1.6, yc, f'{r["k"]} of {r["n"]} ({100 * r["k"] / r["n"]:.1f}%)', ha='left', va='center',
                fontsize=7.8, color=INK, zorder=4)
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
    return v


def fig_graph(out):
    v = parse_graph()
    if v['pairs'] != v['entries']:
        stop('explore_graph_names.txt: the distinct pairs and the entries of section 1 differ')
    X0, X1 = 0.30, 6.70
    TOP = 0.42
    BAR_Y, BAR_H = TOP + 0.62, 0.36
    h_in = BAR_Y + BAR_H + 0.72 + 0.32 + 5 * 0.19 + 0.30
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'What an edge of the code graph is', ha='left', va='top', fontsize=10.5, color=INK)
    page.text(0.09, 0.34, f'The {v["entries"]:,} neighbor relations of the competition\'s {v["graphs"]} code graphs '
              '(a node and one of its neighbors, each direction once)', ha='left', va='top', fontsize=7.8,
              color=INK2)
    parts = (('search', BLUE, 'white', 'The neighbor contains the function\'s name:\none search finds it'),
             ('text', LIGHT, INK, 'The neighbor\'s name is in the function\'s own text'),
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
    ys = BAR_Y + BAR_H + 0.72
    page.text(0.30, ys, 'The graphs, as stored', ha='left', va='top', fontsize=8.6, color=INK, fontweight='bold')
    # the count of edge records is not drawn: it exceeds the neighbor relations (452,588 against 449,902) and the
    # report does not say by what (duplicate records, self loops), so the image names the types only
    types = f'{next(iter(v["types"]))} only' if len(v['types']) == 1 else ', '.join(v['types'])
    facts = (
        ('edge types', types),
        ('pairs stored both ways', f'{v["both"]:,} of {v["pairs"]:,} ({v["both_pct"]}%)'),
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
CLASSES = (('TOP', 'from the top of a file', PALE), ('PAGING', 'continues or overlaps an earlier read', GREY),
           ('ADDRESSED', 'at a line an earlier result numbered', BLUE), ('SHELL VIEW', 'after a shell view', DARK),
           ('NO NUMBER', 'none of these', INK))
BUCKETS = ('2 or 3', '4 to 9', '10 or more')
STARTER = r'^starter agent, public runs of September \(GraphLoc base arm\)'
INDEP = RES / 'explore_independence.txt'          # the count of the right panel (exploratory)
INDEP2 = RES / 'rederive_independence.txt'        # the same count by a second script
# Typed, from the coordinator's message, only to check the parsed values (never drawn): (read every file, shown every
# region, resolved) of the runs, for fixes in one file and in several files (explore_independence.txt, first set).
TYPED_FILES = {'one': (195, 166, 84, 225), 'several': (33, 18, 8, 90)}


def parse_moves():
    s = Source(STARTS)
    s1, e1 = s.block(r'^1\. Where a READ starts', 'section 1', end=r'^2\. ')
    m, ln = s.find(STARTER + r': runs (\d+), tasks (\d+)$', 'section 1, the starter set', s1, e1)
    runs, tasks = int(m.group(1)), int(m.group(2))
    s.record('fig_moves', 'left: starter public runs; tasks', f'{runs}; {tasks}', ln)
    b0, b1 = s.block(STARTER + r': runs \d+', 'section 1, the starter set', lo=s1, hi=e1)
    m, ln = s.find(r'READS (\d+): not of status ok (\d+) \(left out\), of an OWN FILE (\d+) \(apart\); classed (\d+)',
                   'the classed reads of the starter set', b0, b1)
    classed = int(m.group(4))
    s.record('fig_moves', 'left: reads; not ok; own file; classed', '; '.join(m.groups()), ln)
    counts = {}
    for key, _label, _c in CLASSES + (('OTHER NUMBER', '', ''),):
        m, ln = s.find(rf'^\s+{key}\s+(\d+) of (\d+) \(', f'class {key} of the starter set', b0, b1)
        if int(m.group(2)) != classed:
            stop(f'explore_read_starts.txt: class {key} is out of {m.group(2)}, not {classed}')
        counts[key] = int(m.group(1))
        s.record('fig_moves', f'left: starter set, class {key} (all reads)', f'{m.group(1)} of {m.group(2)}', ln)
    if counts.pop('OTHER NUMBER'):
        stop('explore_read_starts.txt: the starter set has reads of class OTHER NUMBER, which the figure does not draw')
    if sum(counts.values()) != classed:
        stop('explore_read_starts.txt: the classes of the starter set do not add up to the classed reads')
    m, ln = s.find(r'^all (\d+) sets: first READS of a file (\d+); of class NO NUMBER (\d+)', 'all sets', s1, e1)
    allsets = tuple(int(g) for g in m.groups())
    s.record('fig_moves', 'left: all sets; first reads; of them NO NUMBER', '; '.join(m.groups()), ln)
    # the runs the other panels count: those of tasks with a CHANGED REGION (section 3); the task without one is fixed
    # by adding a file (it has no GOLD FILE: analyze_14.txt, line 16; checked in population_rows)
    s3, e3 = s.block(r'^3\. Where the fix lies', 'section 3', end=r'^\d\. ')
    m, ln = s.find(STARTER + r': runs of tasks with a CHANGED REGION (\d+), tasks (\d+)$', 'section 3, the starter set',
                   s3, e3)
    cr_runs, cr_tasks = int(m.group(1)), int(m.group(2))
    if cr_runs > runs or cr_tasks > tasks:
        stop(f'explore_read_starts.txt: {cr_runs} runs of {cr_tasks} tasks with a changed region, of {runs}, {tasks}')
    s.record('fig_moves', 'left caption: runs; tasks with a CHANGED REGION', f'{cr_runs}; {cr_tasks}', ln)
    return dict(runs=runs, tasks=tasks, cr_runs=cr_runs, cr_tasks=cr_tasks, classed=classed, counts=counts,
                allsets=allsets, **parse_files())


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
    s.record('fig_moves', 'right: one file: tasks; read the file; shown every region; resolved',
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
    s.record('fig_moves', 'right: several files: tasks; read every file', f'{t}; {rd} of {n}', ln)
    s.record('fig_moves', 'right: several files: shown every region; resolved', f'{sh}, {rs} of {n}', ln2)
    for k, typed in TYPED_FILES.items():
        got = (files[k]['read'], files[k]['shown'], files[k]['resolved'], files[k]['n'])
        if got != typed:
            stop(f'fig_moves: {k} file(s): the file prints {got}, the message types {typed}')
    # by number of regions: runs shown every region, observed and as independent regions at the one-region rate
    buckets = {}
    for bk in BUCKETS:
        h0, h1 = s.block(rf'^   fixes with {re.escape(bk)} CHANGED REGIONS: tasks \d+, runs \d+$', f'fixes with {bk}',
                         end=r'^   \S', lo=b0, hi=b1)
        m, ln = s.find(r'SHOWN every region (\d+) of (\d+) \(', f'{bk}: shown every region', h0, h1)
        k, n = int(m.group(1)), int(m.group(2))
        m2, ln2 = s.find(r'runs SHOWN every region if regions were independent: CONSTANT RATE ([\d.]+);',
                         f'{bk}: CONSTANT RATE', h0, h1)
        buckets[bk] = dict(k=k, n=n, expected=float(m2.group(1)))
        s.record('fig_moves', f'right, note: {bk} regions: shown every region; CONSTANT RATE (line {ln2})',
                 f'{k} of {n}; {m2.group(1)}', ln)
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
    for bk in BUCKETS:
        m, ln = r.find(rf'^   {re.escape(bk)}\s+tasks +\d+; runs +(\d+); .*shown every region (\d+)/(\d+) '
                       r'\([\d.]+%\); expected if independent ([\d.]+)$', f'recount: {bk}', c0, c1)
        x = buckets[bk]
        if (int(m.group(2)), int(m.group(3)), float(m.group(4))) != (x['k'], x['n'], x['expected']):
            stop(f'rederive_independence.txt, line {ln}: the recount differs for {bk} regions')
        r.record('fig_moves', f'recount: {bk} regions: shown every region; expected', f'{m.group(2)} of {m.group(3)}; '
                 f'{m.group(4)}', ln)
    return dict(files=files, buckets=buckets)


def fig_moves(out):
    d = parse_moves()
    TOP = 0.42
    A_HEAD, ROW = 0.42, 0.25
    rows_a = ROW * len(CLASSES)
    LAB_R, X0, X1 = 2.62, 2.74, 6.55
    B_TOP = TOP + A_HEAD + rows_a + 0.42 + 0.30 + 0.20
    B_HEAD, B_H, B_AX = 0.46, 1.95, 0.42
    NOTE_H = 0.40
    h_in = B_TOP + B_HEAD + B_H + B_AX + NOTE_H + 0.28
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'Where a file read starts, and where a fix is lost', ha='left', va='top', fontsize=10.5,
              color=INK)
    # panel (a), unchanged
    page.text(0.09, TOP, '(a)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, TOP + 0.005, 'Where a file read starts', ha='left', va='top', fontsize=9.0, color=INK)
    page.text(W_IN - 0.10, TOP + 0.02, f'the starter agent\'s {d["runs"]} public runs of {d["tasks"]} tasks: '
              f'{d["classed"]:,} reads', ha='right', va='top', fontsize=7.6, color=INK2)
    if d['tasks'] - d['cr_tasks'] != 1:
        stop(f'fig_moves: {d["tasks"] - d["cr_tasks"]} tasks without a changed region; the caption says one')
    page.text(W_IN - 0.10, TOP + 0.18, f'(all runs; {WORDS[d["tasks"] - d["cr_tasks"]]} task is fixed by adding a file, '
              f'so the other panels count {d["cr_runs"]} runs of {d["cr_tasks"]} tasks)', ha='right', va='top',
              fontsize=7.0, color=INK2)
    y0 = TOP + A_HEAD
    ax = axes_at(fig, X0, X1, y0, y0 + rows_a)
    ax.set_xlim(0, 100)
    ax.set_ylim(rows_a, 0)
    for v in (25, 50, 75, 100):
        ax.plot([v, v], [0.02, rows_a], color=GRID, lw=0.6, zorder=0)
    for i, (key, label, color) in enumerate(CLASSES):
        k = d['counts'][key]
        share = 100 * k / d['classed']
        yc = ROW * (i + 0.5)
        ax.barh(yc, share, height=0.15, color=color, edgecolor=color, linewidth=0.6, zorder=2)
        ax.text(share + 1.2, yc, f'{k:,} of {d["classed"]:,} ({share:.1f}%)', ha='left', va='center', fontsize=7.6,
                color=INK, zorder=3)
        page.text(LAB_R, y0 + yc, label, ha='right', va='center', fontsize=8.2, color=INK)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=7.8, length=3)
    ax.set_xlabel('share of the reads, by where the read starts', fontsize=7.8)
    n_sets, first, none = d['allsets']
    page.text(0.36, y0 + rows_a + 0.50, f'First reads of a file that start past line 1 with no line number in hand, '
              f'over all {WORDS.get(n_sets, n_sets)} sets of runs: {none:,} of {first:,}.', ha='left', va='top',
              fontsize=8.0, color=INK)
    # panel (b): a fix in one file, and a fix in several
    files = d['files']
    page.text(0.09, B_TOP, '(b)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, B_TOP + 0.005, 'A fix in one file, and a fix in several', ha='left', va='top', fontsize=9.0,
              color=INK)
    page.text(W_IN - 0.10, B_TOP + 0.02, f'the starter agent\'s public runs, without the skill: '
              f'{files["one"]["n"] + files["several"]["n"]} runs', ha='right', va='top', fontsize=7.6, color=INK2)
    bx = axes_at(fig, 0.80, 6.90, B_TOP + B_HEAD, B_TOP + B_HEAD + B_H)
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
    bk = d['buckets']
    obs = ', '.join(f'{100 * bk[b]["k"] / bk[b]["n"]:.0f}%' for b in BUCKETS)
    exp = ', '.join(f'{100 * bk[b]["expected"] / bk[b]["n"]:.0f}%' for b in BUCKETS)
    note = wrap(f'By number of regions, runs shown every region: {obs} for 2 to 3, 4 to 9 and 10 or more; regions '
                f'shown independently at the one-region rate would give {exp}.', 125)
    yn = B_TOP + B_HEAD + B_H + B_AX
    for i, line in enumerate(note):
        page.text(0.36, yn + 0.14 * i, line, ha='left', va='top', fontsize=7.6, color=INK2)
    page.text(0.09, h_in - 0.07, 'Both panels are exploratory: counted on stored runs, with no registered rule; panel '
              '(b) recounted by a second script.', ha='left', va='bottom', fontsize=6.9, color=MUTED)
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
    s.record('fig_oracle', f'(a) first seed on the {n_ran} tasks of 22: resolved N; ON; OA (heads line {hl}, tasks '
             f'line {tl}; seed-3 columns equal analyze_22.txt)',
             '; '.join(f'{out[a]["resolved"]} of {n_ran}' for a in out), line)
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
    words = dict((k, lab) for k, lab, _c in ARMS18)
    colors = dict((k, c) for k, _l, c in ARMS18)
    TITLE = ('Told where the fix is: the form of the note changes what the agent reads, not detectably what it '
             'resolves')
    KEY_Y = 0.46
    HEAD_Y = 0.78
    P0, P1 = 1.32, 3.22                     # the plot area of every panel, top and bottom
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
    size = 10.5
    title = page.text(0.09, 0.07, TITLE, ha='left', va='top', fontsize=size, color=INK)
    while width_in(fig, title) > W_IN - 0.18:
        size -= 0.1
        title.set_fontsize(size)
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
    texts.append(page.text(XA[0], P1 + 0.50, f'second seed: {d22["ran"]} of {d22["total"]} tasks, no rule has a '
                           'verdict', ha='left', va='center', fontsize=6.9, color=INK2, style='italic'))
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
              'parentheses is the pre-registration; all rules: Appendix A.')


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
    return [interval_text(*b3), rng]


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
    s.record('table_rules_v2', f'12 P2, EPATH - H, opens a listed neighbor\'s file (verdict "{v.group(1)}", line '
             f'{vline})', _pts(m.groups()), line)
    return [_pts(m.groups())], VERDICT_WORDS.get(v.group(1), v.group(1))


def est_04():
    s = Source(R04)
    m, line = s.find(r'^  D_E 95%: .*\| swapped-out under E (\d+)/(\d+), decoy under Ep (\d+)/\2$', 'rule C1')
    v = f'{int(m.group(1)):,} against {int(m.group(3)):,} of {int(m.group(2)):,}'
    s.record('table_rules_v2', '04 C1: swapped-out under E against decoy under Ep', v, line)
    return [v]


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
    return parts, verdicts[0]


VERDICT_WORDS = {'more': 'more (met)', 'not detected': 'no detectable difference'}   # a report's verdict, in the
# table's words


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


TABLE_ROWS = (   # (first column, the estimates, the outcome: a string, or None when the function gives it)
    ("Names against no list, reads a neighbor's code (02)", est_02, 'not met'),
    ('Addresses against names (03); on ten other models (05, 10, 19)', est_03_and_ten, 'met; met on each'),
    ('File and lines against file only (12)', est_12, 'met'),
    ("File only against names, opens the neighbor's file (12)", est_12_p2, None),
    ('True against false entry (04)', est_04, 'met'),
    ('True against rewired list (03)', est_03_b4, 'not met'),
    ('Search with against without line numbers (15); on eight other models (17, 19)', est_15_and_eight,
     'met; met on each'),
    ('Told against nothing (20)', lambda: est_20('T1'), 'met'),
    ('Told as a share of asked; registered threshold two thirds (20)', lambda: est_20('T2'),
     'not met: told is used less'),
    ('Next call is a search, told against nothing (20)', est_20_t4, None),
    (lambda: f'Told its own hits against those of another search, {states_t3()} steps (20)', lambda: est_20('T3'),
     'not met'),
    ('Whole runs, both changes against as shipped, resolved (14)', est_14, 'no detectable difference'),
    ('The September wording of the tool lines against the current one, under either listing (16)', est_16_wording,
     None),
    ('First call goes to a graph tool, the September file listing against the current one, under either wording of '
     'the tool lines (16)', est_16_listing, None),
    ('Oracle, lines against control, resolved (18)', lambda: est_18((('U1', 'OA', 'N'),)), None),
    ('Oracle, names against control; lines against names (18)',
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


def table_rules(out, r22):
    rows = []
    for label, fn, outcome in TABLE_ROWS:
        label = label() if callable(label) else label       # a label with a parsed number in it
        got = fn()
        if got is None:          # a row drawn only when its rules are met (W1 and W2)
            continue
        rows.append((label, *got) if outcome is None else (label, got, outcome))
    p22 = Path(r22) if r22 else R22
    if p22.exists():
        rows += rows_22(p22)
    cols = ['Rule (registration)', 'Estimate', 'Outcome']
    fracs = [0.575, 0.255, 0.170]
    W = W_IN * 72
    body = []
    for label, parts, outcome in rows:
        cell1 = [[(line, TABLE_FS, 'normal', INK, 'normal')] for line in
                 _wrap_pts(_display(label), W * fracs[0] - 10, TABLE_FS)]
        est_lines = []
        for k, p in enumerate(parts):
            est_lines += _wrap_pts(_display(p) + (';' if k < len(parts) - 1 else ''), W * fracs[1] - 10, TABLE_FS)
        cell2 = [[(line, TABLE_FS, 'normal', INK, 'normal')] for line in est_lines]
        # the met color for "met" and for a registered difference that was found ("more", "fewer", or the words a
        # registration gives one, as W3's "more graph calls with ..."); neutral for "not met", no detectable difference
        met = (outcome.split(';')[0].split(' (')[0] in ('met', 'more', 'fewer')
               or outcome.startswith(('more graph calls', 'fewer graph calls')))
        style = ('bold', BLUE, 'normal') if met else ('normal', INK, 'normal')
        o_lines = []
        for k, part in enumerate(outcome.split('; ')):
            o_lines += _wrap_pts(part + (';' if k < len(outcome.split('; ')) - 1 else ''), W * fracs[2] - 10, TABLE_FS,
                                 style[0])
        cell3 = [[(line, TABLE_FS, *style)] for line in o_lines]
        body.append(('row', [cell1, cell2, cell3]))
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
        (label, first, '3.1'),
        ('Steps paused after the agent\'s own search', f'{n_search} steps; {n_cut} can also be cut one call earlier',
         '3.2'),
        ('Public runs of the starter agent [2]',
         f'{all_tasks} tasks, {WORDS[pub_per]} runs with the skill and {WORDS[pub_per]} without ({all_runs} runs '
         f'each); counts of changed regions use the {pub_tasks} tasks whose fix changes an existing line '
         f'({pub_per * pub_tasks} runs)', '4, 5'),
        ('Our runs, harness as shipped (Oct 12)', f'the {ours} tasks our sandbox can score, one run each', '4, 5'),
        ('Oracle runs', oracle, '6'),
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
