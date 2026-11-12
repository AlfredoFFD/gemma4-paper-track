"""[clean restyle of paper/figures/make_fig_funnel.py: same counts; no in-image title (the caption carries it), the
top band cropped, counts, ticks and footnote at 7.6 pt or more (9 pt at 800 px), bars spaced to match. Writes into
paper/figures/clean/.]

The funnel figure (EXPLORATORY): where whole runs are lost, stage by stage.

Usage (from the repo root):
    .venv/Scripts/python.exe -I -X utf8 paper/figures/make_fig_funnel.py

Writes, next to this script, fig_funnel.png (200 dpi) and fig_funnel.svg:
  (a) the four whole-run arms on 103 tasks (14: as shipped, graph answers with line ranges; 23: graph neighbors pushed
      with line ranges, as names only): runs that entered, were shown at least one changed region, were shown every
      changed region, whose final patch overlaps a changed region, and that were resolved; one horizontal bar per arm
  (b) the same five stages for experiment 18 (control, told the names, told the changed lines; 40 tasks)

Every number drawn comes from analysis/explore_funnel.py (its functions are imported and called; no count is typed
here). Before drawing, each drawn count is compared with the same count in the stored report
analysis/results/explore_funnel.txt; a difference stops the script. The style (fonts, sizes, palette, page helpers) is
imported from make_figures_v2.py.
"""
import re
import sys
from pathlib import Path

FIG = Path(__file__).resolve().parent
ROOT = FIG.parents[2]      # clean/ sits one level below paper/figures/
sys.path.insert(0, str(FIG))
sys.path.insert(0, str(ROOT / 'analysis'))
import make_figures_v3 as V  # noqa: E402  (style: rcParams, palette, page_of, axes_at, check_fits, text widths)
import explore_funnel as EF  # noqa: E402  (the counts)

import matplotlib  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

plt = V.plt
REPORT = ROOT / 'analysis' / 'results' / 'explore_funnel.txt'
NAME = 'fig_funnel'

STAGES = ('entered', 'shown_one', 'shown_every', 'overlaps', 'resolved')
STAGE_LABEL = {'entered': ['entered'],
               'shown_one': ['shown at least one', 'changed region'],
               'shown_every': ['shown every', 'changed region'],
               'overlaps': ['final patch overlaps', 'a changed region'],
               'resolved': ['resolved', '(the tests pass)']}
PANEL_A = (('14 N', 'as shipped (14)', V.PALE),
           ('14 NAF', 'graph answers with line ranges (14)', V.LIGHT),
           ('23 PH', 'neighbors pushed, names only (23)', V.GREY),
           ('23 PE', 'neighbors pushed, with line ranges (23)', V.BLUE))
COLORS18 = {k: c for k, _w, c in V.ARMS18}
WORDS18 = {k: w for k, w, _c in V.ARMS18}
PANEL_B = tuple(('18 ' + k, WORDS18[k], COLORS18[k]) for k in ('N', 'ON', 'OA'))
SAME_SPREAD = 10   # the title says "at the same stages" only if, at every drawn stage, the four arms differ by at most this


def stop(msg):
    raise SystemExit(f'make_fig_funnel: {msg}')


def stored_report():
    """{arm key: {stage letter: count}} from section 1 of explore_funnel.txt, and its section 5 lines."""
    text = REPORT.read_text(encoding='utf-8')
    if '\r' in text:
        stop(f'{REPORT.name} has CR line ends')
    lines = text.splitlines()
    try:
        s1 = lines.index('1. THE FUNNEL: runs reaching each stage (counts of runs; each stage on its own, not nested)')
        s2 = next(i for i, line in enumerate(lines) if line.startswith('2. THE SAME, NESTED'))
    except (ValueError, StopIteration):
        stop(f'{REPORT.name}: section 1 not found')
    letters = [letter for _k, letter, _w, _c in EF.STAGES]
    rows = {}
    for line in lines[s1:s2]:
        m = re.match(r'^  (\d\d [A-Z]+)\s+' + r'\s+'.join([r'(\d+)\*?'] * len(letters)) + r'\s*$', line)
        if m:
            rows[m.group(1)] = dict(zip(letters, (int(v) for v in m.groups()[1:])))
    return rows, lines


def check_against_report(counts, keys, stored_lines, extra):
    rows, lines = stored_report()
    for key in keys:
        if key not in rows:
            stop(f'{REPORT.name}: no row for arm {key} in section 1')
        for stage in STAGES:
            letter = EF.STAGE_LETTER[stage]
            if rows[key][letter] != counts[key][stage]:
                stop(f'{key} ({letter}): drawn {counts[key][stage]}, {REPORT.name} says {rows[key][letter]}')
    for key, letter, name, k in extra:      # the second scripts' counts named in the footnote
        rx = re.compile(r'^    %s\s+\(%s\) .*%s\s+%d/\d+' % (re.escape(key), letter, re.escape(name), k))
        if not any(rx.match(line) for line in lines):
            stop(f'{REPORT.name}: no section 5 line with {key} ({letter}) {name} {k}')


_MEASURE = {}


def text_w(s, size, **kw):
    """Width in inches of a text as the renderer draws it (make_figures_v2._text_w reads a little narrow)."""
    if 'fig' not in _MEASURE:
        _MEASURE['fig'], _MEASURE['page'] = V.page_of(1.0)
    t = _MEASURE['page'].text(0, 0.5, s, fontsize=size, **kw)
    w = V.width_in(_MEASURE['fig'], t)
    t.remove()
    return w


def wrap_in(text, width, size):
    """Lines of `text` no wider than `width` inches as drawn."""
    out, line = [], ''
    for word in text.split(' '):
        cand = f'{line} {word}' if line else word
        if line and text_w(cand, size) > width:
            out.append(line)
            line = word
        else:
            line = cand
    out.append(line)
    return out


def main():
    data, _facts = EF.load()
    counts = EF.funnel_counts(data)
    stored, _loader, _endings = EF.stored_counts()
    keys_a = [k for k, _l, _c in PANEL_A]
    keys_b = [k for k, _l, _c in PANEL_B]
    if tuple(keys_a) != tuple(sorted(EF.GROUPS[0][1], key=keys_a.index)) or set(keys_a) != set(EF.GROUPS[0][1]):
        stop('panel (a) arms differ from the first group of explore_funnel')
    if set(keys_b) != set(EF.GROUPS[1][1]):
        stop('panel (b) arms differ from the second group of explore_funnel')
    n_a = {len(data[k]['tasks']) for k in keys_a}
    n_b = {len(data[k]['tasks']) for k in keys_b}
    if len(n_a) != 1 or len(n_b) != 1:
        stop('the arms of a panel have different numbers of runs')
    n_a, n_b = n_a.pop(), n_b.pop()
    for key in keys_a + keys_b:
        if counts[key]['entered'] != len(data[key]['tasks']):
            stop(f'{key}: not every run entered')

    # the second scripts' counts of 'shown every changed region' where they differ from the drawn one (footnote)
    second = {}
    for key in keys_a + keys_b:
        for akey, stage, k, _n, name, _what in stored:
            if akey == key and stage == 'shown_every' and k != counts[key]['shown_every']:
                second[key] = (k, name)
    extra = [(key, 'c', name, k) for key, (k, name) in second.items()]
    check_against_report(counts, keys_a + keys_b, None, extra)

    # the title, from the numbers
    spread = max(max(counts[k][s] for k in keys_a) - min(counts[k][s] for k in keys_a) for s in STAGES)
    if spread > SAME_SPREAD:
        stop(f'the four arms differ by {spread} runs at some stage; the title "at the same stages" would not hold')
    best_b = max(counts[k]['resolved'] for k in keys_b)
    candidates = (f'The four whole-run arms lose runs at the same stages; told where the fix is, at most {best_b} of '
                  f'{n_b} runs are resolved',
                  f'The four whole-run arms lose runs at the same stages; told where the fix is, at most {best_b} of '
                  f'{n_b} resolve',
                  f'All four arms lose runs at the same stages; told where the fix is, at most {best_b} of {n_b} '
                  f'resolve')
    title_text = next((t for t in candidates if text_w(t, 10.5) <= V.W_IN - 0.18), None)
    if title_text is None:
        stop('no title fits on one line')

    # ---------------------------------------------------------------- layout (inches from the top left)
    FS_STAGE, FS_COUNT, FS_KEY, FS_FOOT = 7.8, 7.6, 7.8, 7.6
    BAR, PITCH, GAP = 0.105, 0.135, 0.16
    short = {k: re.sub(r' [(]\d+[)]$', '', l) for k, l, _c in PANEL_A + PANEL_B}   # without '(14)', '(23)'
    X_LABEL = 1.92              # stage labels end here (right-aligned)
    X0, X1 = 2.05, 6.55         # bar area
    texts = []

    def group_height(n_arms):
        return len(STAGES) * n_arms * PITCH + (len(STAGES) - 1) * GAP

    def key_rows(entries, x_start, width):
        """Rows of (label, color) that fit the width at FS_KEY."""
        rows, row, x = [], [], x_start
        for label, color in entries:
            w = 0.21 + text_w(label, FS_KEY) + 0.28
            if row and x + w - 0.28 > x_start + width:
                rows.append(row)
                row, x = [], x_start
            row.append((label, color))
            x += w
        rows.append(row)
        return rows

    foot = (f'Exploratory counts on stored runs; no registered rule. Panel a: as shipped and graph answers with line '
            f'ranges are experiment 14, seed 1; the two pushed arms are experiment 23, seed 2. Panel b: experiment '
            f'18, seed 2. Each bar counts the runs of an arm that reach that stage, one run per task. Shown every '
            f'changed region is the first script\'s count; the second script, which also credits the later calls of '
            f'a step and shell views, counts ' +
            ' and '.join(f'{k} for {short[key]}' for key, (k, _name) in second.items()) + '.')
    foot_lines = wrap_in(foot, V.W_IN - 0.25, FS_FOOT)

    rows_a = key_rows([(l, c) for _k, l, c in PANEL_A], X0, X1 - X0 + 0.3)
    rows_b = key_rows([(l, c) for _k, l, c in PANEL_B], X0, X1 - X0 + 0.3)

    y = 0.07 + 0.36                         # under the title
    layout = []
    for tag, head, keys, n, krows in (('(a)', f'Whole runs, {n_a} tasks: four arms', keys_a, n_a, rows_a),
                                      ('(b)', f'Told where the fix is, first seed (experiment 18), {n_b} tasks',
                                       keys_b, n_b, rows_b)):
        head_y = y
        key_y = head_y + 0.30
        plot_top = key_y + 0.155 * (len(krows) - 1) + 0.24
        plot_bot = plot_top + group_height(len(keys))
        layout.append((tag, head, keys, n, krows, head_y, key_y, plot_top, plot_bot))
        y = plot_bot + 0.62                 # room for the x axis and its label
    foot_y = y - 0.12
    h_in = foot_y + 0.13 * len(foot_lines) + 0.14

    fig, page = V.page_of(h_in)
    t = page.text(0.09, 0.07, title_text, ha='left', va='top', fontsize=10.5, color=V.INK)
    texts.append(t)
    axes = []
    for tag, head, keys, n, krows, head_y, key_y, plot_top, plot_bot in layout:
        texts.append(page.text(0.09, head_y, tag, ha='left', va='top', fontsize=8.8, fontweight='bold', color=V.INK))
        texts.append(page.text(0.35, head_y + 0.005, head, ha='left', va='top', fontsize=8.4, color=V.INK))
        colors = {k: c for k, _l, c in (PANEL_A if tag == '(a)' else PANEL_B)}
        for r, row in enumerate(krows):
            x = X0
            ky = key_y + 0.155 * r
            for label, color in row:
                page.add_patch(Rectangle((x, ky - 0.045), 0.16, 0.09, fc=color, ec='none'))
                kt = page.text(x + 0.21, ky, label, ha='left', va='center', fontsize=FS_KEY, color=V.INK)
                texts.append(kt)
                x += 0.21 + V.width_in(fig, kt) + 0.28
        ax = V.axes_at(fig, X0, X1, plot_top, plot_bot)
        axes.append(ax)
        height = plot_bot - plot_top
        ax.set_ylim(height, 0)
        xmax = n * 1.085
        ax.set_xlim(0, xmax)
        scale = (X1 - X0) / xmax
        yy = 0.0
        for s_i, stage in enumerate(STAGES):
            g_top = yy
            for key in keys:
                yc = yy + PITCH / 2
                v = counts[key][stage]
                ax.barh(yc, v, height=BAR, color=colors[key], edgecolor=colors[key], linewidth=0.6, zorder=2)
                ct = ax.text(v + 0.012 * xmax, yc, str(v), ha='left', va='center', fontsize=FS_COUNT, color=V.INK,
                             zorder=3)
                texts.append(ct)
                yy += PITCH
            g_mid = (g_top + yy) / 2
            for j, line in enumerate(STAGE_LABEL[stage]):
                off = (j - (len(STAGE_LABEL[stage]) - 1) / 2) * 0.135
                texts.append(page.text(X_LABEL, plot_top + g_mid + off, line, ha='right', va='center',
                                       fontsize=FS_STAGE, color=V.INK))
            yy += GAP
        step = 25 if n > 60 else 10
        ax.set_xticks(range(0, n + 1, step))
        ax.set_yticks([])
        ax.grid(axis='x', color='#eeeeee', lw=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.tick_params(axis='x', labelsize=7.6, length=3)
        ax.set_xlabel(f'runs (each arm has {n}, one per task)', fontsize=7.8)
        if scale * n > X1 - X0:
            stop(f'panel {tag}: the bars run past the plot area')
    for i, line in enumerate(foot_lines):
        texts.append(page.text(0.09, foot_y + 0.13 * i, line, ha='left', va='top', fontsize=FS_FOOT, color=V.MUTED))

    # no text runs past the page, no two texts overlap, no count runs into a bar
    V.check_fits(fig, page, NAME)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax in axes:
        texts += [t for t in ax.get_xticklabels() + [ax.xaxis.label] if t.get_text()]
    boxes = [(t, t.get_window_extent(renderer)) for t in texts]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][1].overlaps(boxes[j][1]):
                stop(f'"{boxes[i][0].get_text()[:30]}" overlaps "{boxes[j][0].get_text()[:30]}"')
    for ax in axes:
        bars = [p.get_window_extent(renderer) for p in ax.patches]
        for t in ax.texts:
            tb = t.get_window_extent(renderer)
            if tb.x1 > ax.get_window_extent(renderer).x1 + 0.5:
                stop(f'the count "{t.get_text()}" runs past its panel')
            hits = sum(1 for b in bars if tb.overlaps(b))
            if hits:
                stop(f'the count "{t.get_text()}" runs into a bar')
    box = V.drop_title(fig, page)
    for ext in ('png', 'svg'):
        fig.savefig(FIG / f'{NAME}.{ext}', dpi=V.DPI, bbox_inches=box)
    plt.close(fig)
    if "fig" in _MEASURE:
        plt.close(_MEASURE["fig"])
    print(f'{NAME}: title: {title_text}')
    print(f'{NAME}: {V.W_IN:.2f} x {h_in:.2f} in at {V.DPI} dpi ({round(V.W_IN * V.DPI)} x {round(h_in * V.DPI)} px)')
    for key in keys_a + keys_b:
        print(f'  {key:7s} ' + ', '.join(f'{s} {counts[key][s]}' for s in STAGES))
    print(f'  every drawn count equals {REPORT.relative_to(ROOT).as_posix()}')


if __name__ == '__main__':
    main()
