"""Figures of the rebuilt paper: models, asked against told, what an edge is, where reads start, told where the fix is.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures_v2.py [--out <dir>] [--r22 <file>]

Writes, next to this script (or into --out), each as .png (200 dpi) and .svg:
  fig_models      a name against an address, and a search with and without its line numbers, on eight models
  fig_asked_told  a line the agent was told is used, less often than one it asked for
  fig_graph       what an edge of the code graph is
  fig_moves       where a file read starts, and how many places a fix has
  fig_oracle      told where the fix is: names make the agent look, lines make its patch land

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
  analysis/results/22/analyze_22.txt         pre-registration 22, seed 3, four arms (section 3); --r22 reads another
                                             file of the same format instead (for a test on the stand-in output)
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
MODELS = (  # short label, a token of the model's name in analyze_19.txt (None: Gemma-4-31B, from the registered reports)
    ('Gemma-4-31B', None), ('Qwen3-30B', 'qwen3-30b-a3b'), ('Qwen3-235B', 'qwen3-235b-a22b'),
    ('gpt-oss-120B', 'gpt-oss-120b'), ('DeepSeek-V4.1-Flash', 'deepseek-v4.1-flash'), ('GLM-5.3-Flash', 'glm-5.3-flash'),
    ('MiniMax-M3.1-Flash', 'minimax-m3.1-flash'), ('Nemotron-3-Super-120B', 'nemotron-3-super-120b'),
)
ROW19 = re.compile(r'^(\S+)\s+.+?\s+(10|17)\s+\d+\s+[\d.]+%\s+\w+\s+[\d.]+\s+\w+\s+[\d.]+\s+'
                   r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]\s+(V\d) (.+?)\s*$')


def parse_models():
    s19 = Source(R19)
    _m, end = s19.find(r'^Per run, details', 'the end of the table of analyze_19.txt')
    rows = {}
    for i in range(end - 1):
        m = ROW19.match(s19.lines[i])
        if not m:
            continue
        name, design = m.group(1), m.group(2)
        short = [lab for lab, tok in MODELS if tok and tok in name.lower()]
        if len(short) != 1:
            stop(f'analyze_19.txt, line {i + 1}: the model {name} matches {len(short)} short names')
        key = (short[0], design)
        if key in rows:
            stop(f'analyze_19.txt: two rows for {key}')
        rows[key] = dict(est=m.groups()[2:5], verdict=f'{m.group(6)} {m.group(7)}', line=i + 1, model=name)
    for lab, tok in MODELS[1:]:
        for design in ('10', '17'):
            if (lab, design) not in rows:
                stop(f'analyze_19.txt: no row for {lab}, design {design}')
            r = rows[(lab, design)]
            s19.record('fig_models', f'{"left" if design == "10" else "right"}: {lab} ({r["model"]}, design {design}); '
                       f'{r["verdict"]}', interval_text(*r['est']), r['line'])
    if len(rows) != 2 * (len(MODELS) - 1):
        stop(f'analyze_19.txt: {len(rows)} rows, not {2 * (len(MODELS) - 1)}')
    # Gemma-4-31B: rule B3 of pre-registration 03 (fractions in the report: turned into points, exactly)
    s03 = Source(R03)
    m, line = s03.find(r'^  B3: (-?[\d.]+) \[(-?[\d.]+), (-?[\d.]+)\]', 'rule B3')
    b3 = tuple(f'{Decimal(g) * 100:.2f}' for g in m.groups())
    b3 = ('+' + b3[0] if not b3[0].startswith('-') else b3[0], b3[1], b3[2])
    s03.record('fig_models', 'left: Gemma-4-31B, rule B3 (fractions x 100)', interval_text(*b3), line)
    s15 = Source(R15)
    m, line = s15.find(r'^  Q1, Y1 under S minus Y1 under S0: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', 'rule Q1')
    q1 = m.groups()
    _v, vline = s15.find(r'^  Q1 verdict: met', 'the verdict of Q1')
    s15.record('fig_models', 'right: Gemma-4-31B, rule Q1 (verdict met, line %d)' % vline, interval_text(*q1), line)
    for k, got in (('B3', b3), ('Q1', q1)):
        if interval_text(*got) != interval_text(*TYPED[k]):
            stop(f'{k}: the report prints {interval_text(*got)}, the brief types {interval_text(*TYPED[k])}')
    left = [b3] + [rows[(lab, '10')]['est'] for lab, _t in MODELS[1:]]
    right = [q1] + [rows[(lab, '17')]['est'] for lab, _t in MODELS[1:]]
    return left, right


def nice_step(span):
    for step in (2, 5, 10, 20, 25, 50):
        if span / step <= 6:
            return step
    return 100


def fig_models(out):
    left, right = parse_models()
    labels = [lab for lab, _t in MODELS]
    TOP, HEAD, ROW, AXIS = 0.42, 0.50, 0.255, 0.66
    LAB_R = 1.58
    A1, T1 = (1.70, 3.10), 3.17
    A2, T2 = (4.36, 5.64), 5.71
    rows_h = ROW * len(labels)
    note = wrap(
        'Gemma-4-31B: pre-registrations 03 and 15. The other seven models: the same two contrasts replayed through a '
        'hosted API (pre-registration 19). Intervals: 95% bootstrap by paused step.', 128)
    h_in = TOP + HEAD + rows_h + AXIS + 0.13 * len(note) + 0.10
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'A name against an address, and a search with and without its line numbers, on eight models',
              ha='left', va='top', fontsize=10.5, color=INK)
    y0 = TOP + HEAD
    for (a0, a1), tx, vals, head, sub, xlabel in (
            (A1, T1, left, 'A name against an address', 'addresses minus bare names',
             'points of replays whose next call\nreads a neighbor\'s code'),
            (A2, T2, right, 'A search, with and without line numbers', 'with minus without',
             'points of replays whose next call\nreads a hit file past line 1')):
        page.text(a0, TOP + 0.08, head, ha='left', va='top', fontsize=9.0, color=INK)
        page.text(a0, TOP + 0.27, sub, ha='left', va='top', fontsize=7.8, color=INK2)
        ax = axes_at(fig, a0, a1, y0, y0 + rows_h)
        los = [float(v[1]) for v in vals]
        his = [float(v[2]) for v in vals]
        lo, hi = min(0.0, min(los)), max(his)
        step = nice_step(hi - lo)
        xmin = step * (int(lo // step)) if lo < 0 else 0
        xmax = step * (int(hi // step) + 1)
        ax.set_xlim(xmin - 0.04 * (xmax - xmin), xmax + 0.02 * (xmax - xmin))
        ax.set_ylim(rows_h, 0)
        ticks = [v for v in range(int(xmin), int(xmax) + 1, step)]
        for v in ticks:
            ax.plot([v, v], [0.02, rows_h], color=MUTED if v == 0 else GRID, lw=0.8 if v == 0 else 0.6, zorder=1)
        for i, (p, l, h) in enumerate(vals):
            yc = ROW * (i + 0.5)
            first = i == 0
            col = INK if first else GREY
            ax.plot([float(l), float(h)], [yc, yc], color=col, lw=1.3 if first else 1.0, solid_capstyle='butt',
                    zorder=2)
            for v in (float(l), float(h)):
                ax.plot([v, v], [yc - 0.045, yc + 0.045], color=col, lw=0.9, zorder=2)
            ax.plot(float(p), yc, marker='s', ms=5.6 if first else 4.6, mfc=BLUE if first else DARK, mec='white',
                    mew=0.5, zorder=3)
            t = page.text(tx, y0 + yc, interval_text(p, l, h), ha='left', va='center', fontsize=7.6,
                          color=INK if first else INK2, fontweight='bold' if first else 'normal')
            limit = A2[0] - 0.05 if tx == T1 else W_IN - 0.04
            if tx + width_in(fig, t) > limit:
                stop(f'fig_models: the estimate "{t.get_text()}" runs into the next column')
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: '0' if abs(v) < 1e-9 else num(f'{v:+.0f}')))
        ax.set_yticks([])
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='x', labelsize=7.8, length=3)
        ax.set_xlabel(xlabel, fontsize=7.8, linespacing=1.25)
    for i, lab in enumerate(labels):
        yc = y0 + ROW * (i + 0.5)
        page.text(LAB_R, yc, lab, ha='right', va='center', fontsize=8.4, color=INK,
                  fontweight='bold' if i == 0 else 'normal')
    page.plot([0.12, W_IN - 0.06], [y0 + ROW] * 2, color=HAIR, lw=0.6, zorder=0)
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
    if len(v['types']) == 1:
        (k, n), = v['types'].items()
        types = f'{k} only ({n:,} edge records)'
    else:
        types = ', '.join(f'{k} ({n:,} edge records)' for k, n in v['types'].items())
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
BUCKETS = ('1', '2 or 3', '4 to 9', '10 or more')
STARTER = r'^starter agent, public runs of September \(GraphLoc base arm\)'
OURS = r'^our whole runs of pre-registration 14, condition N'


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
    s3, e3 = s.block(r'^3\. Where the fix lies', 'section 3', end=r'^\d\. ')

    def by_regions(head, what, resolved=True):
        b0, b1 = s.block(head, what, lo=s3, hi=e3)
        c0, c1 = s.block(r'^\s+by the number of CHANGED REGIONS of the task$', f'{what}: by regions',
                         end=r'^\s{3}\S', lo=b0, hi=b1)
        res = {}
        for b in BUCKETS:
            m, ln = s.find(rf'^\s+{re.escape(b)}: tasks (\d+); runs shown every region (\d+) of (\d+) \([\d.]+%\); '
                           r'resolved (\d+) of (\d+) \(', f'{what}, {b}', c0, c1)
            t, k_s, n_s, k_r, n_r = (int(g) for g in m.groups())
            if n_s != n_r:
                stop(f'explore_read_starts.txt: {what}, {b}: {n_s} and {n_r} runs')
            res[b] = dict(tasks=t, shown=k_s, resolved=k_r, n=n_s)
            s.record('fig_moves', f'right: {what}, {b} region(s): tasks; shown every; resolved',
                     f'{t}; {k_s} of {n_s}; {k_r} of {n_r}', ln)
        return res

    starter = by_regions(STARTER + r': runs of tasks with a CHANGED REGION', 'starter public runs')
    m, ln = s.find(STARTER + r': runs of tasks with a CHANGED REGION (\d+), tasks (\d+)', 'section 3, starter', s3, e3)
    s.record('fig_moves', 'right: starter, runs of tasks with a changed region; tasks', '; '.join(m.groups()), ln)
    ours = by_regions(OURS + r': runs of tasks with a CHANGED REGION', 'our runs as shipped (N)')
    m2, ln = s.find(OURS + r': runs of tasks with a CHANGED REGION (\d+), tasks (\d+)', 'section 3, ours', s3, e3)
    s.record('fig_moves', 'right: ours (N), runs of tasks with a changed region; tasks', '; '.join(m2.groups()), ln)
    return dict(runs=runs, tasks=tasks, classed=classed, counts=counts, allsets=allsets, starter=starter, ours=ours,
                ours_runs=int(m2.group(1)), starter_runs=int(m.group(1)))


def fig_moves(out):
    d = parse_moves()
    TOP = 0.42
    A_HEAD, ROW = 0.34, 0.25
    rows_a = ROW * len(CLASSES)
    LAB_R, X0, X1 = 2.62, 2.74, 6.55
    B_TOP = TOP + A_HEAD + rows_a + 0.42 + 0.30 + 0.20
    B_HEAD, B_H, B_AX = 0.58, 2.05, 0.50
    h_in = B_TOP + B_HEAD + B_H + B_AX + 0.28
    fig, page = page_of(h_in)
    page.text(0.09, 0.07, 'Where a file read starts, and how many places a fix has', ha='left', va='top',
              fontsize=10.5, color=INK)
    # panel (a)
    page.text(0.09, TOP, '(a)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, TOP + 0.005, 'Where a file read starts', ha='left', va='top', fontsize=9.0, color=INK)
    page.text(W_IN - 0.10, TOP + 0.02, f'the starter agent\'s {d["runs"]} public runs of {d["tasks"]} tasks: '
              f'{d["classed"]:,} reads', ha='right', va='top', fontsize=7.6, color=INK2)
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
    # panel (b)
    page.text(0.09, B_TOP, '(b)', ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, B_TOP + 0.005, 'Shown every place the fix changes, and resolved, by how many places it has',
              ha='left', va='top', fontsize=9.0, color=INK)
    page.text(0.36, B_TOP + 0.21, f'bars: the starter agent\'s public runs ({d["starter_runs"]} runs of tasks with a '
              f'changed region); markers: our runs as shipped ({d["ours_runs"]} runs, one per task)', ha='left',
              va='top', fontsize=7.6, color=INK2)
    page.text(0.09, h_in - 0.07, 'Both panels are exploratory: counted on stored runs, with no registered rule.',
              ha='left', va='bottom', fontsize=6.9, color=MUTED)
    bx = axes_at(fig, 0.80, 6.90, B_TOP + B_HEAD, B_TOP + B_HEAD + B_H)
    series = (('shown', 'shown every changed region', BLUE), ('resolved', 'resolved (the tests pass)', GREY))
    bw = 0.34
    for gi, b in enumerate(BUCKETS):
        st, ou = d['starter'][b], d['ours'][b]
        for si, (key, _label, color) in enumerate(series):
            x = gi + (si - 0.5) * (bw + 0.04)
            share = 100 * st[key] / st['n']
            bx.bar(x, share, width=bw, color=color, edgecolor=color, linewidth=0.6, zorder=2)
            mine = 100 * ou[key] / ou['n']
            bx.plot(x, mine, marker='D', ms=5.0, mfc='white', mec=INK, mew=1.0, zorder=4)
            bx.text(x, max(share, mine) + 3.6,f'{st[key]} of {st["n"]}', ha='center', va='bottom', fontsize=6.9,
                    color=INK, zorder=5)
    bx.set_xlim(-0.6, len(BUCKETS) - 0.4)
    bx.set_ylim(0, 100)
    bx.set_xticks(range(len(BUCKETS)))
    bx.set_xticklabels([f'{b} region{"" if b == "1" else "s"}\n{d["starter"][b]["tasks"]} tasks' for b in BUCKETS],
                       fontsize=7.8)
    bx.set_yticks([0, 20, 40, 60, 80, 100])
    bx.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    bx.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    bx.set_axisbelow(True)
    bx.spines[['top', 'right']].set_visible(False)
    bx.tick_params(labelsize=7.8, length=3)
    bx.set_ylabel('share of runs', fontsize=8.0)
    bx.set_xlabel('changed regions of the reference fix', fontsize=7.8)
    # the key, top right inside the plot
    kx, ky = 0.60, 0.95
    for key, label, color in series:
        bx.add_patch(Rectangle((kx, ky - 0.025), 0.03, 0.05, transform=bx.transAxes, fc=color, ec='none', zorder=6))
        bx.text(kx + 0.045, ky, label, transform=bx.transAxes, ha='left', va='center', fontsize=7.6, color=INK, zorder=6)
        ky -= 0.075
    bx.plot(kx + 0.015, ky, marker='D', ms=5.0, mfc='white', mec=INK, mew=1.0, transform=bx.transAxes, zorder=6)
    bx.text(kx + 0.045, ky, 'our runs as shipped', transform=bx.transAxes, ha='left', va='center',
            fontsize=7.6, color=INK, zorder=6)
    save(fig, page, out, 'fig_moves')


# ================================================================ fig_oracle
ARMS18 = (('N', 'control', PALE), ('ON', 'told every place by name', GREY),
          ('OF', 'told the functions with their line ranges', LIGHT), ('OA', 'told every place by file and lines', BLUE))
OUTCOMES = (('every', 'shown every\nchanged region'), ('overlap', 'final patch overlaps\na changed region'),
            ('resolved', 'resolved\n(the tests pass)'))
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


def fig_oracle(out, r22):
    seed2, reg18, seed3 = parse_oracle(r22)
    n = seed2['N']['runs']
    arms = [a for a in ARMS18 if a[0] in seed2 or (seed3 and a[0] in seed3)]
    TOP = 0.42
    KEY_H = 0.30 + (0.40 if seed3 else 0)
    PLOT_H, AX_H = 2.15, 0.52
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
    page.text(0.09, 0.07, 'Told where the fix is: names make the agent look, lines make its patch land', ha='left',
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
    for gi, (okey, _olabel) in enumerate(OUTCOMES):
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
    ax.set_xticklabels([lab for _k, lab in OUTCOMES], fontsize=8.2)
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
    w1 = max(len(r[0]) for r in PARSED)
    w2 = max(len(r[1]) for r in PARSED)
    w3 = max(len(r[2]) for r in PARSED)
    print('Parsed numbers (figure, quantity, value, file:line)')
    for figname, q, v, f, ln in PARSED:
        print(f'  {figname:<{w1}}  {q:<{w2}}  {v:<{w3}}  {f}:{ln}')
    print(f'fig_oracle: seed 3 (pre-registration 22) {"drawn" if with22 else "not drawn: no " + rel(R22)}')
    print(f'wrote fig_models, fig_asked_told, fig_graph, fig_moves and fig_oracle (.png at {DPI} dpi, .svg) in {out}')


if __name__ == '__main__':
    main()
