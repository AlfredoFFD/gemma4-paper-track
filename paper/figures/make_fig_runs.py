"""Figure: beyond the next call. When the agent is first shown a line the fix changes, call by call.

Usage: py -I -X utf8 paper/figures/make_fig_runs.py [--out <dir>]

Every number is read from a stored report in this repository; the script fails if a line it needs is missing:
  analysis/results/09/analyze_09.txt            our fresh episodes of up to eight calls (pre-registration 09): the
                                                harness as shipped, the graph tools' answers with file and lines, and
                                                the same with mangled line bounds honored; rule A2 with its interval
  analysis/results/public/time_to_fix.txt       whole public runs of the starter agent with and without a skill that
                                                prints `path:line name` (exploratory; another team's runs)
Panel (a) is our experiment. Panel (b) is a public randomized comparison that we only counted.
"""
import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

FIG = Path(__file__).resolve().parent
RES = FIG.parents[1] / 'analysis' / 'results'
INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
GREY, BLUE, LIGHT = '#5f5f5f', '#1f6fb4', '#8fb5dc'
MINUS = '−'

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK2, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
})


def need(pattern, text, what):
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit(f'make_fig_runs: no line for {what}')
    return m


def num(s):
    return s.replace('-', MINUS)


def fresh():
    t = (RES / '09' / 'analyze_09.txt').read_text(encoding='utf-8')
    block = t.split('shown a changed line by the end of each model call')[1]
    curves = {}
    for arm in ('N', 'NA', 'NAF'):
        m = need(rf'^\s+{arm}\s*: ((?:\d+: [\d.]+,? ?)+);', block, f'fresh episodes, arm {arm}')
        curves[arm] = [float(v) for _k, v in re.findall(r'(\d+): ([\d.]+)', m.group(1))]
        if len(curves[arm]) != 8:
            raise SystemExit(f'make_fig_runs: arm {arm} has {len(curves[arm])} calls, not 8')
    a2 = need(r'A2 NAF - N on Yline, clustered by task: ([+-][\d.]+) \[([+-][\d.]+), ([+-][\d.]+)\]', t, 'A2').groups()
    n = need(r'Yline N\s*: [\d.]+ \[[\d.]+, [\d.]+\] \| \d+/(\d+)', t, 'episodes per arm').group(1)
    return curves, a2, int(n)


def public():
    t = (RES / 'public' / 'time_to_fix.txt').read_text(encoding='utf-8')
    block = t.split('4. Runs shown a changed line by call k')[1]
    total = int(need(r'counts of (\d+) runs per arm', t, 'runs per arm').group(1))
    out = {}
    for arm in ('base', 'skill'):
        m = need(rf'^\s+{arm}:\s+((?:\d+\s*)+)$', block, f'public runs, arm {arm}')
        out[arm] = [100 * int(v) / total for v in m.group(1).split()]
    d5 = need(r'shown a changed line within 5 calls ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]', t, 'within 5').groups()
    res = need(r'^\s+resolved ([+-][\d.]+) points \[([+-][\d.]+), ([+-][\d.]+)\]', t, 'resolved').groups()
    return out, d5, res, total


def style(ax, xmax, xlabel):
    ax.set_ylim(0, 100)
    ax.set_xlim(0.6, xmax)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.grid(axis='y', color='#eeeeee', lw=0.6, zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=8, length=3)
    ax.set_xlabel(xlabel, fontsize=8.2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    curves, a2, n_fresh = fresh()
    pub, d5, res, n_pub = public()

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={'width_ratios': [1, 1.25], 'wspace': 0.3})
    calls = list(range(1, 9))
    for arm, color, ls, lw, label in (('N', GREY, '-', 1.3, 'harness as shipped'),
                                      ('NA', LIGHT, '-', 1.3, 'graph answers with file and lines'),
                                      ('NAF', BLUE, '-', 2.0, 'and mangled line bounds honored')):
        a.plot(calls, curves[arm], color=color, ls=ls, lw=lw, marker='o', ms=3.6, mfc=color, mec='white', mew=0.5,
               label=label, zorder=3)
    style(a, 8.4, f'model call (fresh episodes, {n_fresh} per condition)')
    a.set_xticks(calls)
    a.set_ylabel('shown a line the fix changes by that call', fontsize=8.2)
    a.legend(loc='upper left', bbox_to_anchor=(0.0, 1.0), frameon=False, fontsize=7.2, handlelength=1.8, borderaxespad=0.2)
    a.text(8.3, 30, f'at call 8: {num(a2[0])} points\n[{num(a2[1].lstrip("+"))}, {num(a2[2].lstrip("+"))}], rule met',
           ha='right', va='center', fontsize=7.2, color=INK2, linespacing=1.25)
    a.set_title('(a) Our fresh episodes', fontsize=9, color=INK, loc='left', pad=6)

    ks = list(range(1, len(pub['base']) + 1))
    b.plot(ks, pub['base'], color=GREY, lw=1.3, label='starter agent', zorder=3)
    b.plot(ks, pub['skill'], color=BLUE, lw=2.0, label='with a skill that prints path:line', zorder=3)
    style(b, len(ks) + 0.5, f'tool call (public runs of another team, {n_pub} per arm)')
    b.set_xticks([1, 5, 10, 15, 20, 25, 30])
    b.legend(loc='lower right', bbox_to_anchor=(1.0, 0.02), frameon=False, fontsize=7.2, handlelength=1.8, borderaxespad=0.2)
    b.annotate('', xy=(5, pub['skill'][4]), xytext=(5, pub['base'][4]),
               arrowprops=dict(arrowstyle='<->', color=INK, lw=0.8, shrinkA=0, shrinkB=0))
    b.text(5.6, (pub['skill'][4] + pub['base'][4]) / 2 - 3,
           f'within 5 calls: {num(d5[0])} points\n[{num(d5[1].lstrip("+"))}, {num(d5[2].lstrip("+"))}]', ha='left',
           va='center', fontsize=7.2, color=INK2, linespacing=1.25)
    b.text(30.3, 100, f'tasks resolved: {num(res[0])} points [{num(res[1])}, {num(res[2].lstrip("+"))}]', ha='right',
           va='top', fontsize=7.2, color=INK2)
    b.set_title('(b) Whole runs, public', fontsize=9, color=INK, loc='left', pad=6)

    fig.subplots_adjust(left=0.085, right=0.985, top=0.9, bottom=0.16)
    out = Path(args.out)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_runs.{ext}', dpi=300)
    plt.close(fig)
    print('fresh episodes, percent shown a changed line by call:', curves)
    print('A2:', a2, '| public within 5 calls:', d5, '| resolved:', res)
    print(f'wrote fig_runs.png and fig_runs.svg in {out}')


if __name__ == '__main__':
    main()
