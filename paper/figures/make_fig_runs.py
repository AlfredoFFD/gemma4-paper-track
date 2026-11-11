"""Figure 5: sooner, not more. When the agent is first shown a line the fix changes, call by call.

Usage: py -I -X utf8 paper/figures/make_fig_runs.py [--out <dir>]

Every number is read from a stored report in this repository; the script fails if a line it needs is missing:
  analysis/results/09/analyze_09.txt            our fresh episodes of up to eight model calls (pre-registration 09): the
                                                harness as shipped, and addressed and repaired (graph answers carry
                                                file and lines, and a misspelled line bound is honored); rule A2
  analysis/results/public/time_to_fix.txt       whole public runs of the starter agent with and without a skill that
                                                prints addresses (exploratory; another team's runs)
Optional. When both files exist, panel (a) shows our own whole runs scored by tests INSTEAD of the fresh episodes;
when either is missing, nothing of them is drawn:
  analysis/results/14/analyze_14.txt            pre-registration 14: rules T1 (resolved) and T2 (shown within 8 calls),
                                                the share ever shown
  analysis/results/14/runs_14.csv               one row per run (analysis/analyze_14.py --csv): the curves, from the
                                                runs that enter the paired analysis and have a line to score; the
                                                script checks them against the counts the report prints
Panel (a) is our experiment. Panel (b) is a public randomized comparison that we only counted.
"""
import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

FIG = Path(__file__).resolve().parent
RES = FIG.parents[1] / 'analysis' / 'results'
R09 = RES / '09' / 'analyze_09.txt'
PUBLIC = RES / 'public' / 'time_to_fix.txt'
R14 = RES / '14' / 'analyze_14.txt'        # optional, with CSV14
CSV14 = RES / '14' / 'runs_14.csv'

INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
GREY, BLUE = '#5f5f5f', '#1f6fb4'
MINUS = '−'
SHIPPED, REPAIRED = 'as shipped', 'addressed and repaired'

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


def fresh():
    t = text_of(R09)
    block = t.split('shown a changed line by the end of each model call')[1]
    curves = {}
    for arm in ('N', 'NAF'):
        m = need(rf'^\s+{arm}\s*: ((?:\d+: [\d.]+,? ?)+);', block, f'fresh episodes, condition {arm}')
        curves[arm] = [float(v) for _k, v in re.findall(r'(\d+): ([\d.]+)', m.group(1))]
        if len(curves[arm]) != 8:
            raise SystemExit(f'make_fig_runs: condition {arm} has {len(curves[arm])} calls, not 8')
    a2 = need(r'A2 NAF - N on Yline, clustered by task: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', t, 'A2').groups()
    n = need(r'Yline N\s*: [\d.]+ \[[\d.]+, [\d.]+\] \| \d+/(\d+)', t, 'episodes per condition').group(1)
    return dict(curves=curves, a2=a2, n=int(n))


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


def whole(n_calls):
    """Our whole runs scored by tests (pre-registration 14); None while the report or the per-run table is missing."""
    if not (R14.exists() and CSV14.exists()):
        return None
    t = R14.read_text(encoding='utf-8')
    with open(CSV14, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    first = {c: [math.inf if r['t_shown'] == 'inf' else int(r['t_shown']) for r in rows
                 if r['condition'] == c and r['entered'] == '1' and r['has_gold_file'] == '1'] for c in ('N', 'NAF')}
    n = len(first['N'])
    if not n or len(first['NAF']) != n:
        raise SystemExit(f'make_fig_runs: runs_14.csv has {n} and {len(first["NAF"])} scored runs in the two '
                         'conditions')
    out = dict(n=n, curves={}, ever={}, exploratory='EVERYTHING BELOW IS EXPLORATORY' in t)
    sec3 = t.split('\n3. ')[1]
    for c, block in (('N', sec3.split('\n   NAF: runs')[0]), ('NAF', sec3.split('\n   NAF: runs')[1])):
        # the per-run table must give the counts the report prints
        m = need(r'shown a changed line within k calls: (.*?); never: (\d+) of (\d+)', block,
                 f'whole runs, {c}: by call')
        printed = {int(k): (int(a), int(b)) for k, a, b in re.findall(r'(\d+): (\d+) of (\d+)', m.group(1))}
        printed[math.inf] = (n - int(m.group(2)), int(m.group(3)))
        for k, (shown, of) in printed.items():
            mine = sum(v <= k for v in first[c]) if k != math.inf else sum(v < math.inf for v in first[c])
            if (mine, n) != (shown, of):
                raise SystemExit(f'make_fig_runs: whole runs, {c}, within {k} calls: the table gives {mine} of {n}, '
                                 f'the report {shown} of {of}')
        out['curves'][c] = [100 * sum(v <= k for v in first[c]) / n for k in range(1, n_calls + 1)]
        out['ever'][c] = 100 * sum(v < math.inf for v in first[c]) / n
    m = need(r'T1 resolved: ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]; NAF (\d+) of (\d+) \([\d.]+%\), '
             r'N (\d+) of (\d+)', t, 'T1')
    out['d_resolved'] = m.groups()[:3]
    out['resolved'] = {'NAF': (int(m.group(4)), int(m.group(5))), 'N': (int(m.group(6)), int(m.group(7)))}
    m = need(r'T2 t_shown <= (\d+): ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\].*\n\s+verdict: (\w[\w ]*)', t,
             'T2')
    out['t2_k'], out['t2'], out['t2_met'] = int(m.group(1)), m.groups()[1:4], m.group(5).strip().startswith('sooner')
    return out


# ---------------------------------------------------------------- drawing
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
    """A legend drawn by hand in axes fractions, so that text can follow it: [(color, width, label)]."""
    for color, lw, label in entries:
        ax.plot([x, x + 0.075], [y, y], color=color, lw=lw, transform=ax.transAxes, solid_capstyle='butt', zorder=6)
        ax.text(x + 0.10, y, label, transform=ax.transAxes, ha='left', va='center', fontsize=7.4, color=INK, zorder=6)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pub = public()
    ours = whole(len(pub['curves']['base']))
    ep = None if ours else fresh()

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 3.3), gridspec_kw={'width_ratios': [1, 1.12], 'wspace': 0.2})
    fig.suptitle('Sooner, not more: when the agent is first shown a line the fix changes', x=0.012, y=0.985, ha='left',
                 fontsize=10.5, color=INK)

    top = 100.0
    if ours:      # our whole runs, scored by tests
        met = 'registered rule met' if ours['t2_met'] else 'registered rule not met'
        (k1, n1), (k0, n0) = ours['resolved']['NAF'], ours['resolved']['N']
        of = f'of {n0:,} each' if n0 == n1 else f'of {n0:,} and {n1:,}'
        style(a, len(ours['curves']['N']) + 0.5, f'tool calls ({ours["n"]:,} whole runs per condition)')
        top = max(top, whole_panel(
            a, dict(curves=[ours['curves']['N'], ours['curves']['NAF']], ever=ours['ever'], gap_k=ours['t2_k'],
                    gap_lines=[f'within {ours["t2_k"]} calls: {interval(ours["t2"])}', met]),
            (SHIPPED, REPAIRED), [f'resolved (tests pass), {of}:', f'{k0:,} {SHIPPED}, {k1:,} {REPAIRED}'],
            [f'difference {interval(ours["d_resolved"])}'], x=0.27))
        a.set_title('(a) Our whole runs, scored by tests' + (' (exploratory)' if ours['exploratory'] else ''),
                    fontsize=9, color=INK, loc='left', pad=6)
    else:         # our fresh episodes of up to eight model calls
        calls = list(range(1, 9))
        for arm, color, lw, label in (('N', GREY, 1.3, SHIPPED), ('NAF', BLUE, 2.0, REPAIRED)):
            a.plot(calls, ep['curves'][arm], color=color, lw=lw, marker='o', ms=3.6, mfc=color, mec='white', mew=0.5,
                   label=label, zorder=3 if arm == 'N' else 4)
        style(a, 8.5, f'model calls ({ep["n"]:,} fresh episodes per condition)')
        a.set_xticks(calls)
        a.legend(loc='upper left', bbox_to_anchor=(0.0, 1.0), frameon=False, fontsize=7.4, handlelength=1.8,
                 borderaxespad=0.2)
        lo = float(ep['a2'][1])
        met = 'not met' if lo <= 0 else 'met narrowly' if lo < 1 else 'met'
        ends = sorted((ep['curves']['N'][-1], ep['curves']['NAF'][-1]))
        a.plot([8.22, 8.22], ends, color=INK, lw=0.9, zorder=5)
        for v in ends:
            a.plot([8.12, 8.22], [v, v], color=INK, lw=0.9, zorder=5)
        a.text(8.4, ends[1] + 2.8, f'at call 8: {interval(ep["a2"])}\nregistered rule {met}', ha='right', va='bottom',
               fontsize=7.2, color=INK2, linespacing=1.3, zorder=6)
        a.set_title('(a) Our fresh episodes, up to eight model calls', fontsize=9, color=INK, loc='left', pad=6)
    a.set_ylabel('shown a line the fix changes', fontsize=8.2)

    n = pub['n']
    style(b, len(pub['curves']['base']) + 0.5, f'tool calls ({n:,} whole public runs per condition)')
    top = max(top, whole_panel(
        b, dict(curves=[pub['curves']['base'], pub['curves']['skill']], ever=pub['ever'], gap_k=5,
                gap_lines=[f'within 5 calls: {interval(pub["d5"])}']),
        ('without the skill', 'with a skill that prints addresses'),
        [f'resolved (tests pass), of {n:,} each:',
         f'{pub["resolved"]["base"]:,} without the skill, {pub["resolved"]["skill"]:,} with it'],
        ['another team\'s runs; the skill also', 'changes what is retrieved']))
    b.set_title('(b) A public experiment, whole runs', fontsize=9, color=INK, loc='left', pad=6)
    for ax in (a, b):       # the same scale in both panels, with room for the label of the dashed line
        ax.set_ylim(0, top)

    fig.subplots_adjust(left=0.085, right=0.988, top=0.84, bottom=0.135)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_runs.{ext}', dpi=300)
    plt.close(fig)
    if ours:
        print('our whole runs, percent shown a changed line by tool call 1, 5, 10, 20, 30:',
              {c: [round(v[k - 1], 1) for k in (1, 5, 10, 20, 30) if k <= len(v)] for c, v in ours['curves'].items()})
        print('T2:', ours['t2'], '| T1:', ours['d_resolved'], '| resolved:', ours['resolved'], '| ever shown:',
              ours['ever'])
    else:
        print('fresh episodes, percent shown a changed line by call:', ep['curves'])
        print('A2:', ep['a2'])
    print('public runs: within 5 calls', pub['d5'], '| resolved', pub['resolved'], 'of', n, pub['d_resolved'],
          '| ever shown', {k: round(v, 1) for k, v in pub['ever'].items()})
    print(f'wrote fig_runs.png and fig_runs.svg in {out}')


if __name__ == '__main__':
    main()
