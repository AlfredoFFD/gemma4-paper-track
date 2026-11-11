"""Figure 4: how often a first read of a file asks for lines past line 1, by what the agent was shown just before.

Usage: py -I -X utf8 paper/figures/make_fig_law.py [--out <dir>]

Every count is read from a stored report in this repository; the script fails if a line it needs is missing:
  analysis/results/public/address.txt        other teams' public runs of Gemma-4-31B on this benchmark
  analysis/results/public/outside.txt        public trajectories of other agents and models (its sections A to D;
                                             each row's model and agent are checked against its section)
  analysis/results/09/analyze_11.txt         our fresh episodes (pre-registration 11: thresholds fixed before the data)
  analysis/results/explore_depth.txt         the same first reads, split by whether the named line lies within the
                                             lines a read without a range returns
  analysis/results/explore_first_reads.txt   the one-step replays, restated as first reads of a listed neighbor's file
  analysis/results/15/analyze_15.txt         the agent's own search with its line numbers kept, stripped, and stripped
                                             and handed back in a note (pre-registration 15; registered report)
Optional, drawn when the report exists and skipped silently when it does not:
  analysis/results/13/analyze_13.txt         the same addresses written as search hits (pre-registration 13)

Three bars per row: the result just before the read showed no line number for the file; a line number within the
lines a read from the top returns (in sight); a line number past them (out of sight). Each pair of blue bars splits
one line of a report, and the script checks that the two parts add up to that line.
Panel (a) is observational (the agent chose to search or to list). Panel (b) is controlled: we chose what the graph's
answer prints, without and with line numbers, and every paused step and every task gets every condition, so nothing
is assigned at random (at paused steps the list is given to the agent; in fresh episodes it asked for it). Its last
three rows are the paused steps that follow the agent's own search (pre-registration 15): the result as recorded,
the same with its line numbers stripped, and stripped with the numbers handed back in a note. Their value is C of the
registered report, the share of the next call's reads of a hit file that ask past line 1, split by whether the file's
nearest hit lies past the window (the report's split); the grey bar of the stripped result is not split.
The public counts, the replay counts and the split by depth are exploratory; the fresh-episode row of panel (a) is
the registered test (its two blue bars together are the registered count).
The strings of the strip "What the agent is shown" are examples of the four ways of writing, not results: the first
neighbor of the paused step that Figure 1 shows.
"""
import argparse
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

FIG = Path(__file__).resolve().parent
RES = FIG.parents[1] / 'analysis' / 'results'
ADDRESS = RES / 'public' / 'address.txt'
OUTSIDE = RES / 'public' / 'outside.txt'
FRESH = RES / '09' / 'analyze_11.txt'
DEPTH = RES / 'explore_depth.txt'
REPLAYS = RES / 'explore_first_reads.txt'
HITS = RES / '13' / 'analyze_13.txt'      # optional
OWN = RES / '15' / 'analyze_15.txt'       # pre-registration 15, the registered report

INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
GREY, LIGHT, BLUE = '#8e8e8e', '#8fb5dc', '#1f6fb4'
GRID, BAND = '#ececec', '#f4f4f4'
MONO = 'DejaVu Sans Mono'
MONO_W = 0.60205          # advance of one DejaVu Sans Mono character, in em
WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven'}

# Public trajectories outside the competition, in the order of the rows. `section` is the block of outside.txt;
# `head` must stand in that block's first line and `token` in the name of every model the block lists, or the
# script stops: the row label is checked against the report. `agent` is the agent framework (the classic SWE-agent
# and the one with function calling count as one); `note` names the block's agent in the footnote.
OUTSIDE_SOURCES = (
    dict(section='A', model='Claude 3.7 Sonnet', agent='SWE-agent', family='Claude', token='claude-3-7-sonnet',
         head='SWE-agent with function calling', note='SWE-agent with function calling'),
    dict(section='D', model='GPT-4o', agent='OpenHands', family='GPT', token='gpt-4o',
         head='OpenHands with function calling', note='OpenHands'),
    dict(section='C', model='Qwen3-Coder-480B', agent='OpenHands', family='Qwen', token='qwen3-coder-480b',
         head='OpenHands with function calling', note='OpenHands', repositories=True),
    dict(section='B', model='Llama agents', agent='SWE-agent', family='Llama', token='llama',
         head='Classic SWE-agent', note='classic SWE-agent'),
)

# Examples of the ways of writing (not results)
EX_FILE, EX_LINE, EX_LINES, EX_DEF = 'fastapi/_compat.py', '272', '272-278', 'def copy_field_info('
EX_NAME = 'fastapi._compat.copy_field_info'

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK, 'xtick.major.width': 0.6, 'ytick.major.size': 0,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
})


def text_of(path):
    if not path.exists():
        raise SystemExit(f'make_fig_law: {path} is missing')
    return path.read_text(encoding='utf-8')


def need(pattern, text, what):
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit(f'make_fig_law: no line for {what}')
    return tuple(int(g) for g in m.groups())


def need_text(pattern, text, what):
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit(f'make_fig_law: no line for {what}')
    return m.group(1)


def and_join(items):
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def split_of(total, near, far, what):
    """The two blue bars must be the two parts of one line of a report."""
    if (near[0] + far[0], near[1] + far[1]) != tuple(total):
        raise SystemExit(f'make_fig_law: {what}: {near} and {far} do not add up to {total}')
    return near, far


def by_sight(text, label, what):
    """(k, n) in sight and out of sight for one table of explore_depth.txt."""
    k1, n1, k2, n2 = need(rf'^\s+{re.escape(label)}: first reads \d+\n\s+IN SIGHT\s+ask past line 1: (\d+) of (\d+).*\n'
                          r'\s+OUT OF SIGHT\s+ask past line 1: (\d+) of (\d+)', text, what)
    return (k1, n1), (k2, n2)


def public_rows():
    """Rows 1 to 3 of panel (a) and the number of lines a read from the top returns in this competition's harness."""
    a = text_of(ADDRESS)
    runs = re.findall(r'^\s+(.+?)\s+(\d+) traces, \d+ unreadable', a.split('\n1. ')[0], re.M)
    main = [(name, int(n)) for name, n in runs if name.endswith('31B') and 'skill' not in name]
    if len(main) not in WORDS:
        raise SystemExit(f'make_fig_law: {len(main)} sources of Gemma-4-31B in section 0 of address.txt')
    sec2 = a.split('\n2. ')[1].split('\n3. ')[0]
    none = need(r'^\s+PATH ONLY\s+(\d+) of (\d+)', sec2, 'public runs, PATH ONLY')
    total = need(r'^\s+ADDRESS\s+(\d+) of (\d+)', sec2, 'public runs, ADDRESS')
    w1, k1, n1, w2, k2, n2 = need(r'^\s+three 31B sources\s+within the first (\d+) lines (\d+) of (\d+) \([\d.]+%\)\s+'
                                  r'past line (\d+) (\d+) of (\d+)', a.split('\n9. ')[1], 'public runs, by depth')
    if w1 != w2:
        raise SystemExit('make_fig_law: section 9 of address.txt splits at two different lines')
    near, far = split_of(total, (k1, n1), (k2, n2), 'public runs')
    rows = [dict(main='Gemma-4-31B', sub=f'{sum(n for _s, n in main):,} public runs of {WORDS[len(main)]} teams',
                 none=none, near=near, far=far, family='Gemma', agent='the agents of this competition')]
    o = text_of(OUTSIDE)
    notes = {'whole': [], 'other': []}
    for src in OUTSIDE_SOURCES:
        main_label = f'{src["model"]} in {src["agent"]}'
        heads = [line for line in o.splitlines() if line.startswith(src['section'] + '. ')]
        if len(heads) != 1:
            raise SystemExit(f'make_fig_law: no section {src["section"]} in outside.txt')
        block = o.split(heads[0])[1].split('later reads')[0]
        models = need_text(r'models: (.+)$', block, f'{main_label}: models')
        if src['head'].lower() not in heads[0].lower() or not all(
                src['token'] in m.lower() for m in re.findall(r'([\w.\-]+) x\d+', models)):
            raise SystemExit(f'make_fig_law: section {src["section"]} of outside.txt is not {main_label}: {heads[0]}; '
                             f'{models}')
        traj, repos = need(r'trajectories (\d+), issues \d+, repositories (\d+)', block, f'{main_label}: trajectories')
        none = need(r'PATH ONLY\s+RANGED (\d+) of (\d+)', block, f'{main_label}: PATH ONLY')
        total = need(r'ADDRESS\s+RANGED (\d+) of (\d+)', block, f'{main_label}: ADDRESS')
        v1, k1, n1, v2, k2, n2 = need(r'ADDRESS by the smallest named line: within the first (\d+) lines RANGED '
                                      r'(\d+) of (\d+) \([\d.]+%\); past line (\d+) RANGED (\d+) of (\d+)', block,
                                      f'{main_label}: by depth')
        if v1 != v2:
            raise SystemExit(f'make_fig_law: {main_label}: split at two different lines')
        near, far = split_of(total, (k1, n1), (k2, n2), main_label)
        sub = f'{traj:,} public trajectories'
        if src.get('repositories'):
            sub += f', {repos:,} repositories'
        if v1 != w1:       # this agent's own window: the bars are split there, and the row says so
            sub += f', split at line {v1}'
            notes['other'].append((src['note'], v1, src['model']))
        elif 'shows the whole file' in block:
            notes['whole'].append(src['note'])
        rows.append(dict(main=main_label, sub=sub, none=none, near=near, far=far, family=src['family'],
                         agent=src['agent']))
    return rows, w1, notes


def fresh_rows(window):
    """Our fresh episodes: the registered row of panel (a) and the graph-answer row of panel (b)."""
    t = text_of(FRESH)
    d = text_of(DEPTH)
    (w,) = need(r'IN SIGHT: the line is within the first (\d+) lines', d, 'the window of explore_depth.txt')
    if w != window:
        raise SystemExit(f'make_fig_law: explore_depth.txt splits at line {w}, address.txt at line {window}')
    part1 = d.split('\n1. ')[1].split('\n2. ')[0]
    none = need(r'^\s+all arms\s+PATH ONLY\s+(\d+) of (\d+)', t, 'fresh episodes: PATH ONLY')
    total = need(r'^\s+all arms\s+ADDRESS\s+(\d+) of (\d+)', t, 'fresh episodes: ADDRESS')
    near, far = split_of(total, *by_sight(part1, 'after an ADDRESS, all conditions', 'fresh episodes by depth'),
                         'fresh episodes')
    g_none = need(r'^\s+arm N\s+GRAPH NAME\s+(\d+) of (\d+)', t, 'fresh episodes: GRAPH NAME')
    g_total = need(r'^\s+all arms\s+GRAPH ADDRESS\s+(\d+) of (\d+)', t, 'fresh episodes: GRAPH ADDRESS')
    g_near, g_far = split_of(g_total, *by_sight(part1, 'after a GRAPH ADDRESS, all conditions',
                                                'fresh episodes, graph answers by depth'),
                             'fresh episodes, graph answers')
    counts = re.findall(r'arm \w+: (\d+) episodes, (\d+) with an error', t)
    if not counts:
        raise SystemExit('make_fig_law: no episode counts in analyze_11.txt')
    episodes = sum(int(n) - int(e) for n, e in counts)
    return (dict(main=f'Our {episodes:,} fresh episodes', sub='thresholds registered before the data', none=none,
                 near=near, far=far, bold=True),
            dict(main='Fresh episodes: the graph tools\' own answers', grey='names only, as shipped', none=g_none,
                 near=g_near, far=g_far))


def replay_rows():
    """Paused steps: the neighbor list without and with line numbers, and (optional) written as search hits."""
    r = text_of(REPLAYS)
    d = text_of(DEPTH)
    pat = r'^\s+Gemma-4-31B\s+%s\s*: first reads (\d+), ask past line 1 (\d+)'
    n0, k0 = need(pat % 'without', r, 'paused steps, lists without line numbers')
    n1, k1 = need(pat % 'with', r, 'paused steps, lists with line numbers')
    near, far = split_of((k1, n1), *by_sight(d.split('\n2. ')[1], 'Gemma-4-31B, lists with line numbers',
                                             'paused steps by depth'), 'paused steps')
    rows = [dict(main='Paused steps: the neighbor list', grey='lists without line numbers', none=(k0, n0), near=near,
                 far=far)]
    if HITS.exists():
        n, k, _w, deep, deep_k = need(r'^\s+arm EG\s+first reads of a listed neighbor.s file: (\d+); ask past line 1 '
                                      r'(\d+); cover a listed neighbor \d+; out of the first (\d+) lines (\d+), of '
                                      r'which past line 1 (\d+)', HITS.read_text(encoding='utf-8'), 'search hits')
        rows.append(dict(main='Paused steps: the list as search hits',
                         sub='the same addresses, written file:line:definition', none=None,
                         near=(k - deep_k, n - deep), far=(deep_k, deep)))
    return rows


def own_search_rows(window):
    """Pre-registration 15: paused steps after the agent's own search. Per arm, C of the registered report (reads of
    a hit file that ask past line 1, on the states complete for every rule), split by the file's nearest hit."""
    t = text_of(OWN)
    (complete,) = need(r'^\s+on the (\d+) states complete for every rule\n\s+arm S ', t, 'own search: complete states')
    rates = t.split('\n2. ')[1].split('\n3. ')[0]
    descr = t.split('\n3. ')[1]
    out = {}
    for arm in ('S', 'S0', 'S0N'):
        total = need(rf'^\s+arm {arm}\s+Y1, .*; C, past line 1 among those reads: (\d+) of (\d+)', rates,
                     f'own search, arm {arm}: C')
        w1, k2, n2, w2, k1, n1 = need(rf'^\s+arm {arm}\s+Y1 by the nearest hit of the file read: past line (\d+), '
                                      r'(\d+) of (\d+) reads ask past line 1; within the first (\d+) lines, (\d+) of '
                                      r'(\d+)', descr, f'own search, arm {arm}: by the nearest hit')
        if not w1 == w2 == window:
            raise SystemExit(f'make_fig_law: analyze_15.txt splits at lines {w1} and {w2}, address.txt at {window}')
        out[arm] = (total, *split_of(total, (k1, n1), (k2, n2), f'own search, arm {arm}'))
    return [dict(label=f'After the agent\'s own search (pre-registration 15; {complete} paused steps)'),
            dict(main='Line numbers kept', sub='the search result as recorded', none=None, near=out['S'][1],
                 far=out['S'][2]),
            dict(main='Line numbers stripped', grey='the same result without them', none=out['S0'][0]),
            dict(main='Stripped, handed back in a note', sub='the numbers as a message after the result', none=None,
                 near=out['S0N'][1], far=out['S0N'][2])]


# ---------------------------------------------------------------- drawing
W_IN = 7.0
LEFT_IN, RIGHT_IN = 2.80, 0.10        # label column, right margin
ROW_H, HEAD_H, GAP_H = 0.375, 0.27, 0.10
LABEL_H = 0.21                        # a small label over a group of rows inside a panel
BAR_H, BAR_PITCH = 0.088, 0.100
TOP_H = 0.90                          # title and legend
AXIS_H, NOTE_LINE, STRIP_H = 0.30, 0.125, 1.11


def draw(panels, window, notes, out_dir):
    """panels: [(tag, title, what the panel covers or '', rows)]; a row {'label': text} is a small label over the
    rows that follow it."""
    def row_h(row):
        return LABEL_H if 'label' in row else ROW_H

    plot_h = sum(HEAD_H + sum(row_h(r) for r in rows) for *_t, rows in panels) + GAP_H * (len(panels) - 1)
    # what a read from the top returns, where an agent's own window differs
    note = [f'A read without a line range returns lines 1 to {window} in this competition\'s harness.']
    for agent, lines, model in notes['other']:
        note.append(f'{agent[0].upper() + agent[1:]} shows lines 1 to {lines}, so the bars of the {model} are split '
                    'there.')
    if notes['whole']:
        note.append(f'In {and_join(notes["whole"])} a view without a range shows the whole file.')
    note = textwrap.wrap(' '.join(note), 140)
    note_h = NOTE_LINE * len(note) + 0.07
    h_in = TOP_H + plot_h + AXIS_H + note_h + STRIP_H + 0.06
    fig = plt.figure(figsize=(W_IN, h_in))
    page = fig.add_axes([0, 0, 1, 1])              # the whole page, in inches from the top left
    page.set_xlim(0, W_IN)
    page.set_ylim(h_in, 0)
    page.axis('off')
    renderer = fig.canvas.get_renderer()

    def width_in(t):
        return t.get_window_extent(renderer).width / fig.dpi

    def swatch(x, y, w, colors, h=0.085):
        """A legend key centered on y: one color, or two side by side."""
        for i, color in enumerate(colors):
            page.add_patch(Rectangle((x + i * w / len(colors), y - h / 2), w / len(colors), h, fc=color, ec='none'))

    # title and the one legend
    page.text(0.09, 0.07, 'Share of first reads of a file that ask for lines past line 1', ha='left', va='top',
              fontsize=10.5, color=INK)
    page.text(0.09, 0.335, 'Just before the read, a tool result had shown, for that file:', ha='left', va='top',
              fontsize=7.8, color=INK2)
    keys = ((GREY, 'no line number shown'),
            (LIGHT, f'a line number within the first {window} lines (in sight from the top)'),
            (BLUE, f'a line number past line {window} (out of sight)'))
    for i, (color, label) in enumerate(keys):
        y = 0.545 + 0.137 * i
        swatch(0.11, y, 0.20, [color])
        page.text(0.39, y, label, ha='left', va='center', fontsize=7.8, color=INK)

    # the bars
    ax = fig.add_axes([LEFT_IN / W_IN, 1 - (TOP_H + plot_h) / h_in, (W_IN - LEFT_IN - RIGHT_IN) / W_IN, plot_h / h_in])
    ax.set_facecolor('none')           # the panel titles lie on the page under it
    ax.set_xlim(0, 119)
    ax.set_ylim(plot_h, 0)
    y = 0.0
    for tag, title, covers, rows in panels:
        page.text(0.09, TOP_H + y + 0.07, tag, ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
        page.text(0.36, TOP_H + y + 0.075, title, ha='left', va='top', fontsize=9.0, color=INK)
        if covers:
            page.text(W_IN - 0.10, TOP_H + y + 0.092, covers, ha='right', va='top', fontsize=7.6, color=INK2)
        y += HEAD_H
        # the grid and the zero line run through each stretch of bar rows, not through the labels
        stretches, yy, start = [], y, None
        for row in rows:
            if 'label' in row and start is not None:
                stretches.append((start, yy))
                start = None
            elif 'label' not in row and start is None:
                start = yy
            yy += row_h(row)
        if start is not None:
            stretches.append((start, yy))
        for top, bottom in stretches:
            for x in (25, 50, 75, 100):
                ax.plot([x, x], [top + 0.03, bottom - 0.03], color=GRID, lw=0.6, zorder=0)
            ax.plot([0, 0], [top + 0.03, bottom - 0.03], color=MUTED, lw=0.6, zorder=1)
        for row in rows:
            if 'label' in row:
                page.text(0.36, TOP_H + y + LABEL_H - 0.035, row['label'], ha='left', va='bottom', fontsize=7.9,
                          color=INK2, style='italic')
                y += LABEL_H
                continue
            yc = y + ROW_H / 2
            bars = [(row[key], color) for key, color in (('none', GREY), ('near', LIGHT), ('far', BLUE))
                    if row.get(key) is not None]
            for j, ((k, n), color) in enumerate(bars):
                yb = yc + (j - (len(bars) - 1) / 2) * BAR_PITCH
                if n:
                    share = 100 * k / n
                    ax.barh(yb, share, height=BAR_H, color=color, edgecolor=color, linewidth=0.7, zorder=2)
                    ax.text(share + 1.3, yb + 0.004, f'{k:,} of {n:,}', va='center', ha='left', fontsize=7.1, color=INK,
                            zorder=3)
                else:
                    ax.text(1.3, yb + 0.004, 'no such read', va='center', ha='left', fontsize=7.1, color=MUTED,
                            zorder=3)
            xl = LEFT_IN - 0.10
            page.text(xl, TOP_H + yc - 0.012, row['main'], ha='right', va='bottom', fontsize=8.4, color=INK,
                      fontweight='bold' if row.get('bold') else 'normal')
            if row.get('grey'):    # what the grey bar is in this row, behind its own key
                t = page.text(xl, TOP_H + yc + 0.012, row['grey'], ha='right', va='top', fontsize=7.3, color=INK2)
                swatch(xl - width_in(t) - 0.17, TOP_H + yc + 0.012 + 0.058, 0.11, [GREY], h=0.075)
            else:
                page.text(xl, TOP_H + yc + 0.012, row['sub'], ha='right', va='top', fontsize=7.3, color=INK2)
            y += ROW_H
        y += GAP_H
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.tick_params(axis='x', labelsize=8, length=3)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_bounds(0, 100)

    y0 = TOP_H + plot_h + AXIS_H
    for i, line in enumerate(note):
        page.text(0.09, y0 + 0.02 + NOTE_LINE * i, line, ha='left', va='top', fontsize=6.9, color=MUTED)

    # the strip: what the agent is shown, each way of writing behind the color of its bars
    y0 += note_h
    page.add_patch(FancyBboxPatch((0.07, y0), W_IN - 0.14, STRIP_H - 0.03, boxstyle='round,pad=0,rounding_size=0.05',
                                  fc=BAND, ec='none'))
    page.text(0.19, y0 + 0.085, 'What the agent is shown', ha='left', va='top', fontsize=8.6, fontweight='bold',
              color=INK)
    size = 8.2
    cw = MONO_W * size / 72
    plain, mark = (INK, 'normal'), (BLUE, 'bold')
    examples = (
        ('a file name', [GREY], [[(EX_FILE, *plain)]]),
        ('a search hit', [LIGHT, BLUE], [[(EX_FILE + ':', *plain), (EX_LINE, *mark), (':' + EX_DEF, *plain)]]),
        ('a graph answer as shipped', [GREY], [[(f'"{EX_NAME}"', *plain)]]),
        ('a graph answer with an address', [LIGHT, BLUE],
         [[(f'{{"name": "{EX_NAME}",', *plain)],
          [(f' "file": "{EX_FILE}", "lines": "', *plain), (EX_LINES, *mark), ('"}', *plain)]]),
    )
    y = y0 + 0.335
    for label, colors, lines in examples:
        swatch(0.21, y, 0.16, colors)
        page.text(0.46, y, label, ha='left', va='center', fontsize=8.0, color=INK)
        for pieces in lines:
            x = 2.42
            for text, ink, weight in pieces:
                page.text(x, y, text, ha='left', va='center', fontsize=size, family=MONO, color=ink, fontweight=weight)
                x += cw * len(text)
            y += 0.152
        y += 0.012

    for ext in ('png', 'svg'):
        fig.savefig(out_dir / f'fig_law.{ext}', dpi=300)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    observed, window, notes = public_rows()
    families = len({r['family'] for r in observed})
    frameworks = len({r['agent'] for r in observed})
    ours, graph = fresh_rows(window)
    observed.append(ours)
    controlled = ([dict(label='After a graph answer, as shipped and with line numbers added')] + replay_rows()
                  + [graph] + own_search_rows(window))
    panels = [('(a)', 'After the agent\'s own search or listing (observed: the agent chose)',
               f'{WORDS[families]} model families, {WORDS[frameworks]} agent frameworks', observed),
              ('(b)', 'Controlled: we chose whether the result shows line numbers', '', controlled)]
    draw(panels, window, notes, out)
    for _tag, title, _covers, rows in panels:
        print(title)
        for r in rows:
            if 'label' in r:
                print(f' {r["label"]}')
                continue
            cells = [f'{name} {r[key][0]:>4} of {r[key][1]:<5}' if r.get(key) is not None else f'{name}    -         '
                     for key, name in (('none', 'no line number'), ('near', 'in sight'), ('far', 'out of sight'))]
            print(f'  {r["main"] + (", " + r["sub"] if r.get("sub") else ""):<62} ' + '  '.join(cells))
    print(f'wrote fig_law.png and fig_law.svg in {out}')


if __name__ == '__main__':
    main()
