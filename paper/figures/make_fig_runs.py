"""Figure 5: sooner, with no detectable gain in solved tasks. What the two changes buy at each horizon, and a public experiment on whole runs.

Usage: py -I -X utf8 paper/figures/make_fig_runs.py [--out <dir>]

Every number is read from a stored report in this repository; the script fails if a line it needs is missing:
  analysis/results/analyze_b.txt            pre-registration 03, rule B3: addresses against bare names at paused steps
  analysis/results/k/analyze_k.txt          pre-registration 06, rule K1: five-call replays
  analysis/results/g/analyze_g.txt          pre-registration 08, rules G2 and G3: five-call replays with the repair
  analysis/results/09/analyze_09.txt        pre-registration 09, rules A1 and A2 and one contrast that it reports
                                            without a rule: fresh episodes of up to eight model calls
  analysis/results/public/time_to_fix.txt   whole public runs of the starter agent with and without GraphLoc's
                                            skill (exploratory; another entry's runs)
Optional. Its two rows are drawn when the report exists; until then their group says "whole runs: pending":
  analysis/results/14/analyze_14.txt        pre-registration 14, rules T2 and T1: our whole runs scored by tests

Panel (a) is a forest by horizon: one row per contrast, the difference in percentage points with its 95% interval as
the report prints it, from the next call to five calls, eight calls and whole runs. A marker is filled when the
registered rule of its row is met, and hollow when it is not met or when the contrast has no registered rule (the
row then says so). Nothing about a rule is typed: it is met when the lower bound that the report prints is above 0
(rule B3: when the interval excludes 0), and for the whole runs the script takes the verdict that the report prints.
Panel (b) is a public experiment that we only counted: the same tasks were run with and without the skill.
The title of the figure is the constant TITLE below.
"""
import argparse
import re
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

TITLE = 'Sooner, with no detectable gain in solved tasks'      # the title above both panels

FIG = Path(__file__).resolve().parent
RES = FIG.parents[1] / 'analysis' / 'results'
R03 = RES / 'analyze_b.txt'
R06 = RES / 'k' / 'analyze_k.txt'
R08 = RES / 'g' / 'analyze_g.txt'
R09 = RES / '09' / 'analyze_09.txt'
PUBLIC = RES / 'public' / 'time_to_fix.txt'
R14 = RES / '14' / 'analyze_14.txt'        # optional

INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
GREY, BLUE = '#5f5f5f', '#1f6fb4'
GRID, HAIR = '#ececec', '#e4e4e4'
MINUS = '−'

# Panel (a), the rows that are always drawn, by group: (label, report, the pattern whose three groups are the
# estimate and the bounds of its interval, the factor that turns them into percentage points, the registered rule:
# 'above 0', 'excludes 0', or None for a contrast that its report gives without a rule).
NUM3 = r'([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]'
GROUPS = (
    ('Addresses', (
        ('Next call: reads a neighbor\'s code (paused steps)', R03,
         r'^  B3: (-?[\d.]+) \[(-?[\d.]+), (-?[\d.]+)\]', 100, 'excludes 0'),
        ('Next call: reads a returned function (fresh episodes, the agent asked)', R09,
         r'^  A1 NA - N on Ynext, clustered by task \(\d+ tasks\): ' + NUM3, 1, 'above 0'),
        ('Five calls: shown the fix', R06, r'^  Yline E - H: ' + NUM3 + r'\s+\(K1\)', 1, 'above 0'),
        ('Five calls: shown the fix, on top of the repair', R08,
         r'^  G3 EF - AF on Yline in R, seeds 11 to 15, clustered by state \(\d+ clusters\): ' + NUM3, 1, 'above 0'),
        ('Eight calls: shown the fix (fresh episodes)', R09, r'^\s+descriptive Yline: NA - N ' + NUM3, 1, None),
    )),
    ('Repair of the misspelled line bound', (
        ('Five calls: shown the fix', R08,
         r'^  G2 AF - A on Yline, clustered by state \(\d+ clusters\): ' + NUM3, 1, 'above 0'),
        ('Eight calls: shown the fix, both changes (fresh episodes)', R09,
         r'^\s+A2 NAF - N on Yline, clustered by task: ' + NUM3, 1, 'above 0'),
    )),
)
# The last group, our whole runs: (label, the rule's line in the report of pre-registration 14, the verdict the
# report prints when the rule is met).
WHOLE_GROUP = 'Both changes, whole runs'
WHOLE = (('Shown the fix within eight tool calls', r'T2 t_shown <= 8', 'sooner'),
         ('Resolved by the tests', r'T1 resolved', 'more tasks solved'))

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK2, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
})


def text_of(path):
    if not path.exists():
        raise SystemExit(f'make_fig_runs: {path} is missing')
    return path.read_text(encoding='utf-8')


def need(pattern, text, what, flags=re.M):
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit(f'make_fig_runs: no line for {what}')
    return m


def num(s):
    return s.replace('-', MINUS)


def interval(d):
    """'+4.08 points [0.68, 7.48]' from the three strings a report prints."""
    return f'{num(d[0])} points [{num(d[1].lstrip("+"))}, {num(d[2].lstrip("+"))}]'


def contrast(label, printed, factor=1, rule=None, met=None):
    """One row of panel (a) from the three strings a report prints (estimate, lower bound, upper bound). A factor of
    100 turns the fractions of an early report into percentage points, exactly and with two decimals. met: given
    for a rule whose verdict the report prints; otherwise worked out from the printed bounds."""
    if factor != 1:
        printed = [f'{Decimal(g) * factor:.2f}' for g in printed]
    val, lo, hi = (float(g) for g in printed)
    if met is None:
        met = {'above 0': lo > 0, 'excludes 0': lo > 0 or hi < 0, None: False}[rule]
    if rule is None:        # a contrast that its report gives without a rule: the row says so
        label = label[:-1] + '; not a registered rule)' if label.endswith(')') else label + ' (not a registered rule)'
    point = printed[0] if printed[0][0] in '+-' else '+' + printed[0]
    text = f'{num(point)} [{num(printed[1].lstrip("+"))}, {num(printed[2].lstrip("+"))}]'
    return dict(label=label, val=val, lo=lo, hi=hi, text=text, met=met, registered=rule is not None)


def forest_groups():
    """[(group label, rows)] of panel (a) for the reports that are always there."""
    out = []
    for group, rows in GROUPS:
        out.append((group, [contrast(label, need(pattern, text_of(path), f'{group}, {label}').groups(), factor, rule)
                            for label, path, pattern, factor, rule in rows]))
    return out


def whole_rows():
    """(rows, exploratory) for rules T2 and T1 of pre-registration 14; None while the report does not exist. The
    report prints one decimal, and its verdict, not the printed bound, says whether a rule is met. Exploratory: fewer
    tasks entered than the pre-registration asks for, so that no rule applies."""
    if not R14.exists():
        return None
    t = R14.read_text(encoding='utf-8')
    rows = []
    for label, line, said in WHOLE:
        m = need(rf'^   {line}: ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\].*\n\s+verdict: (.+)$', t,
                 f'whole runs, {line}')
        rows.append(contrast(label, m.groups()[:3], rule='verdict', met=m.group(4).strip() == said))
    return rows, 'EVERYTHING BELOW IS EXPLORATORY' in t


def public():
    t = text_of(PUBLIC)
    total = int(need(r'counts of (\d+) runs per arm', t, 'runs per condition').group(1))
    block = t.split('4. Runs shown a changed line by call k')[1]
    out = dict(n=total, curves={}, resolved={}, ever={})
    for arm in ('base', 'skill'):
        m = need(rf'^\s+{arm}:\s+((?:\d+\s*)+)$', block, f'public runs, condition {arm}')
        out['curves'][arm] = [100 * int(v) / total for v in m.group(1).split()]
        m = need(rf'^\s+{arm}: runs (\d+); resolved (\d+) of (\d+) \([\d.]+%\); tool calls per run [\d.]+; ever shown '
                 r'a changed line (\d+) of (\d+)', t, f'public runs, condition {arm}: resolved and ever shown')
        runs, k_res, n_res, k_ever, n_ever = (int(g) for g in m.groups())
        if not runs == n_res == n_ever == total:
            raise SystemExit(f'make_fig_runs: public runs, condition {arm}: {runs}, {n_res}, {n_ever} runs, not '
                             f'{total}')
        out['resolved'][arm] = k_res
        out['ever'][arm] = 100 * k_ever / total
    out['d5'] = need(r'shown a changed line within 5 calls ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]', t,
                     'within 5 calls').groups()
    out['d_resolved'] = need(r'^\s+resolved ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]', t, 'resolved').groups()
    return out


# ---------------------------------------------------------------- drawing
W_IN = 7.0
TOP_H, HEAD_H = 0.40, 0.30               # the title of the figure; the title line of a panel
GROUP_H, ROW_H, GROUP_GAP = 0.225, 0.215, 0.05
AXIS_H, GAP_H = 0.46, 0.16               # ticks and label under the forest; space before panel (b)
B_H, B_AXIS_H = 2.0, 0.44                # panel (b): its plot and what lies under it
X_GROUP, X_HORIZON, X_WHAT = 0.10, 0.24, 1.00      # inches from the left: group label, horizon, what is counted
AX_L, AX_R, X_NUM = 4.08, 5.80, 5.90               # the axis of the forest, and where the numbers begin
B_L, B_R = 0.60, 6.91                              # panel (b)


def style(ax, xmax, xlabel):
    ax.set_ylim(0, 100)
    ax.set_xlim(0.6, xmax)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=8, length=3)
    ax.set_xlabel(xlabel, fontsize=8.2)


def gap(ax, k, low, high, lines, x_text=None, y_text=None, ha='left'):
    """A double arrow between two curves at call k, and what it measures just under it."""
    ax.annotate('', xy=(k, high), xytext=(k, low), arrowprops=dict(arrowstyle='<->', color=INK, lw=0.8, shrinkA=0,
                                                                   shrinkB=0), zorder=5)
    ax.text(k + 0.5 if x_text is None else x_text, low - 3 if y_text is None else y_text, '\n'.join(lines), ha=ha,
            va='top', fontsize=7.2, color=INK2, linespacing=1.3, zorder=6)


def key(ax, y, entries, x=0.33, step=0.075):
    """A legend drawn by hand in axes fractions, so that text can follow it: [(color, width, label)]. The sample of
    a line and the space after it have a fixed length on the page, however wide the panel is."""
    width_in = ax.get_position().width * ax.figure.get_figwidth()
    sample, space = 0.23 / width_in, 0.075 / width_in
    for color, lw, label in entries:
        ax.plot([x, x + sample], [y, y], color=color, lw=lw, transform=ax.transAxes, solid_capstyle='butt', zorder=6)
        ax.text(x + sample + space, y, label, transform=ax.transAxes, ha='left', va='center', fontsize=7.4, color=INK,
                zorder=6)
        y -= step
    return y


def ever_line(ax, ever, names, xmax):
    """The share ever shown a line the fix changes: one dashed line when the two conditions agree, else two."""
    a, b = ever.values()
    if round(a) == round(b) and abs(a - b) < 0.5:
        ax.axhline((a + b) / 2, color=INK2, lw=0.8, ls=(0, (4, 2.5)), zorder=2)
        label = f'ever shown in the run: {a:.0f}% in either condition'
    else:
        for v, color in ((a, GREY), (b, BLUE)):
            ax.axhline(v, color=color, lw=0.8, ls=(0, (4, 2.5)), zorder=2)
        label = f'ever shown in the run:\n{a:.0f}% {names[0]}, {b:.0f}% {names[1]}'
    ax.text(xmax - 0.2, max(a, b) + 1.6, label, ha='right', va='bottom', fontsize=7.2, color=INK2, linespacing=1.25,
            zorder=6)
    return max(a, b) + 1.6 + 5.8 * (1 + label.count('\n'))      # the height the label needs, in percent


def whole_panel(ax, d, names, resolved, extra=(), x=0.33):
    """Curves of whole runs by tool call, the share ever shown, the gap at one call and the resolved counts.
    Returns the height the panel needs (above 100 when the label of the dashed line would leave the frame)."""
    ks = list(range(1, len(d['curves'][0]) + 1))
    ax.plot(ks, d['curves'][0], color=GREY, lw=1.3, zorder=3)
    ax.plot(ks, d['curves'][1], color=BLUE, lw=2.0, zorder=4)
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30])
    top = ever_line(ax, d['ever'], names, len(ks) + 0.5)
    k = d['gap_k']
    low, high = sorted((d['curves'][0][k - 1], d['curves'][1][k - 1]))
    gap(ax, k, low, high, d['gap_lines'], x_text=k + 0.6)
    y = key(ax, 0.405, [(GREY, 1.3, names[0]), (BLUE, 2.0, names[1])], x=x, step=0.066) - 0.016
    for line in resolved:
        ax.text(x, y, line, transform=ax.transAxes, ha='left', va='center', fontsize=7.4, color=INK, zorder=6)
        y -= 0.063
    y -= 0.012
    for line in extra:
        ax.text(x, y, line, transform=ax.transAxes, ha='left', va='center', fontsize=6.8, color=MUTED, zorder=6)
        y -= 0.056
    return top


def forest_height(groups, pending):
    """The height of the rows of panel (a), in inches."""
    n_rows = sum(len(rows) for _g, rows in groups) + (1 if pending else 0)
    n_groups = len(groups) + (1 if pending else 0)
    return n_groups * GROUP_H + (n_groups - 1) * GROUP_GAP + n_rows * ROW_H + 0.03


def draw_forest(fig, page, top, groups, pending):
    """Panel (a) below `top` (inches from the top of the page): groups of rows, each row a horizon in bold, what is
    counted, the interval with its marker, and the estimate and interval as text. pending: a last group label under
    which one grey line stands for rows still to come."""
    renderer = fig.canvas.get_renderer()
    h_in = fig.get_figheight()

    def width_in(t):
        return t.get_window_extent(renderer).width / fig.dpi

    block_h = forest_height(groups, pending)
    ax = fig.add_axes([AX_L / W_IN, 1 - (top + block_h) / h_in, (AX_R - AX_L) / W_IN, block_h / h_in])
    ax.set_facecolor('none')
    every = [r for _g, rows in groups for r in rows]
    ax.set_xlim(min(r['lo'] for r in every) - 1.5, max(r['hi'] for r in every) + 1.5)
    ax.set_ylim(block_h, 0)
    span = ax.get_xlim()[1] - ax.get_xlim()[0]
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5 if span <= 22 else 10))
    ticks = [v for v in ax.get_xticks() if ax.get_xlim()[0] <= v <= ax.get_xlim()[1]]
    last = groups[-1][1][-1] if not pending else None      # no hairline between the last row and the axis
    for v in ticks:
        ax.plot([v, v], [0.02, block_h], color=MUTED if v == 0 else GRID, lw=0.8 if v == 0 else 0.6, zorder=1)
    y = 0.0
    for i, (group, rows) in enumerate(list(groups) + ([(pending, None)] if pending else [])):
        y += GROUP_GAP if i else 0
        page.text(X_GROUP, top + y + GROUP_H / 2 + 0.01, group, ha='left', va='center', fontsize=8.4,
                  fontweight='bold', color=INK)
        y += GROUP_H
        if rows is None:        # rows still to come
            page.text(X_HORIZON, top + y + ROW_H / 2, 'whole runs: pending', ha='left', va='center', fontsize=8.0,
                      color=MUTED, style='italic')
            y += ROW_H
            continue
        for r in rows:
            yc = y + ROW_H / 2
            horizon, colon, what = r['label'].partition(': ')
            if not colon:       # a row without a horizon of its own: its group names it
                horizon, what = '', r['label']
            what, paren, aside = what.partition(' (')
            page.text(X_HORIZON, top + yc, horizon, ha='left', va='center', fontsize=8.0, fontweight='bold', color=INK)
            x_what = X_WHAT if horizon else X_HORIZON
            t = page.text(x_what, top + yc, what, ha='left', va='center', fontsize=8.0, color=INK)
            end = x_what + width_in(t)
            if paren:
                t = page.text(end + 0.035, top + yc, '(' + aside, ha='left', va='center', fontsize=8.0, color=INK2)
                end += 0.035 + width_in(t)
            if end > AX_L - 0.06:
                raise SystemExit(f'make_fig_runs: the label "{r["label"]}" runs into the axis of panel (a)')
            ax.plot([r['lo'], r['hi']], [yc, yc], color=INK, lw=1.2, solid_capstyle='butt', zorder=2)
            for v in (r['lo'], r['hi']):
                ax.plot([v, v], [yc - 0.04, yc + 0.04], color=INK, lw=0.9, zorder=2)
            ax.plot(r['val'], yc, marker='s', ms=5.6, mfc=BLUE if r['met'] else 'white',
                    mec='white' if r['met'] else BLUE, mew=0.5 if r['met'] else 1.2, zorder=3)
            page.text(X_NUM, top + yc, r['text'], ha='left', va='center', fontsize=7.8, color=INK)
            if r is not last:
                page.plot([X_HORIZON, W_IN - 0.10], [top + y + ROW_H] * 2, color=HAIR, lw=0.5, zorder=0)
            y += ROW_H
    ax.set_yticks([])
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.tick_params(axis='x', labelsize=8, length=3)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: '0' if abs(v) < 1e-9 else num(f'{v:+.0f}')))
    ax.set_xlabel('difference in percentage points, 95% interval', fontsize=8.0)


def marker_key(fig, page, y):
    """What the two markers of panel (a) mean, set from the right edge on the panel's title line."""
    renderer = fig.canvas.get_renderer()
    x = W_IN - 0.10
    for label, filled in (('not met, or not a registered rule', False), ('registered rule met', True)):
        t = page.text(x, y, label, ha='right', va='center', fontsize=7.4, color=INK2)
        x -= t.get_window_extent(renderer).width / fig.dpi + 0.10
        page.plot(x, y, marker='s', ms=5.2, mfc=BLUE if filled else 'white', mec='white' if filled else BLUE,
                  mew=0.5 if filled else 1.1, zorder=3)
        x -= 0.26


def panel_title(page, y, tag, title):
    page.text(0.09, y, tag, ha='left', va='top', fontsize=9.4, fontweight='bold', color=INK)
    page.text(0.36, y + 0.005, title, ha='left', va='top', fontsize=9.0, color=INK)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    groups = forest_groups()
    ours = whole_rows()
    pending = None
    if ours:
        rows, exploratory = ours
        groups.append((WHOLE_GROUP + (' (exploratory: too few tasks for the rules to apply)' if exploratory else ''),
                       rows))
    else:
        pending = WHOLE_GROUP
    pub = public()

    block_h = forest_height(groups, pending)
    h_in = TOP_H + HEAD_H + block_h + AXIS_H + GAP_H + HEAD_H + B_H + B_AXIS_H
    fig = plt.figure(figsize=(W_IN, h_in))
    page = fig.add_axes([0, 0, 1, 1])              # the whole page, in inches from the top left
    page.set_xlim(0, W_IN)
    page.set_ylim(h_in, 0)
    page.axis('off')
    page.text(0.09, 0.07, TITLE, ha='left', va='top', fontsize=10.5, color=INK)

    panel_title(page, TOP_H, '(a)', 'What the two changes buy, by horizon')
    marker_key(fig, page, TOP_H + 0.085)
    draw_forest(fig, page, TOP_H + HEAD_H, groups, pending)

    top_b = TOP_H + HEAD_H + block_h + AXIS_H + GAP_H
    panel_title(page, top_b, '(b)', 'Another entry\'s public runs, whole runs')
    b = fig.add_axes([B_L / W_IN, 1 - (top_b + HEAD_H + B_H) / h_in, (B_R - B_L) / W_IN, B_H / h_in])
    n = pub['n']
    style(b, len(pub['curves']['base']) + 0.5, f'tool calls ({n:,} whole public runs per condition)')
    top = whole_panel(
        b, dict(curves=[pub['curves']['base'], pub['curves']['skill']], ever=pub['ever'], gap_k=5,
                gap_lines=[f'within 5 calls: {interval(pub["d5"])}']),
        ('without the skill', 'with GraphLoc\'s skill (prints path:line name; also changes what is retrieved)'),
        [f'resolved (tests pass), of {n:,} each:',
         f'{pub["resolved"]["base"]:,} without the skill, {pub["resolved"]["skill"]:,} with it'])
    b.set_ylim(0, max(100.0, top))       # room for the label of the dashed line
    b.set_ylabel('shown a line the fix changes', fontsize=8.2)

    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_runs.{ext}', dpi=300)
    plt.close(fig)
    print('panel (a), difference in percentage points [95% interval]:')
    for group, rows in groups:
        print(f'  {group}')
        for r in rows:
            state = 'met' if r['met'] else 'not met' if r['registered'] else 'no registered rule'
            print(f'    {r["label"]:<82} {r["text"].replace(MINUS, "-"):<22} {state}')
    if pending:
        print(f'  {pending}\n    whole runs: pending ({R14.relative_to(FIG.parents[1]).as_posix()} does not exist yet)')
    print('panel (b), public runs: within 5 calls', pub['d5'], '| resolved', pub['resolved'], 'of', n,
          pub['d_resolved'], '| ever shown', {k: round(v, 1) for k, v in pub['ever'].items()})
    print(f'wrote fig_runs.png and fig_runs.svg in {out}')


if __name__ == '__main__':
    main()
