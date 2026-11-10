"""Figure 1: where a first read of a file starts, in public runs and in the replays.

Usage: py -I -X utf8 paper/figures/make_fig_law.py [--out <dir>]

Every count is read from a stored report in this repository; the script fails if a line it needs is missing:
  analysis/results/public/address.txt        other teams' public runs of Gemma 4 agents on this benchmark
  analysis/results/public/outside.txt        public trajectories of other agents and models
  analysis/results/09/analyze_11.txt         our fresh episodes (pre-registration 11: thresholds fixed before the data)
  analysis/results/explore_first_reads.txt   the one-step replays, restated as first reads of a listed neighbor's file
The public counts and the replay counts are exploratory (no rule was registered for them); the fresh-episode row is
the registered test. Panel (a) is observational; panel (b) is the experiment: the graph's answer, written without
and with line numbers (in the replays the list is given to the agent; in the fresh episodes it asked for it).
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
GREY, BLUE = '#8e8e8e', '#1f6fb4'

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9, 'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'axes.labelcolor': INK2,
    'xtick.color': INK2, 'ytick.color': INK, 'xtick.major.width': 0.6, 'ytick.major.size': 0,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white', 'axes.facecolor': 'white',
})


def need(pattern, text, what):
    m = re.search(pattern, text, re.M)
    if not m:
        raise SystemExit(f'make_fig_law: no line for {what}')
    return tuple(int(g) for g in m.groups())


def public_rows():
    """[(label, (k, n) without a line number, (k, n) with one)] from the two public-run reports."""
    a = (RES / 'public' / 'address.txt').read_text(encoding='utf-8')
    o = (RES / 'public' / 'outside.txt').read_text(encoding='utf-8')
    rows = []
    for label, source in (('Gemma-4-31B, starter agent\n318 runs', r'starter agent \(GraphLoc base arm, Sep\), 31B'),
                          ('Gemma-4-31B, a custom agent\n80 runs', r'custom agent 1 \(Oct\), 31B'),
                          ('Gemma-4-31B, another custom agent\n120 runs', r'custom agent 2 \(Oct to Nov\), 31B'),
                          ('Gemma-4-12B, a custom agent\n40 runs', r'custom agent 1 \(Oct\), 12B')):
        first = a.split('\n2. ')[0]  # section 1: first reads by source and class
        with_n = need(rf'^\s+{source}\s+ADDRESS\s+(\d+) of (\d+)', first, f'{label}: ADDRESS')
        without = need(rf'^\s+{source}\s+PATH ONLY\s+(\d+) of (\d+)', first, f'{label}: PATH ONLY')
        rows.append((label, without, with_n))
    for label, head in (('Claude 3.7 Sonnet, SWE-agent\n800 trajectories', 'A. SWE-agent with function calling'),
                        ('Llama 70B, 8B, 405B, SWE-agent\n800 trajectories', 'B. Classic SWE-agent')):
        block = o.split(head)[1].split('later reads')[0]
        with_n = need(r'ADDRESS\s+RANGED (\d+) of (\d+)', block, f'{label}: ADDRESS')
        without = need(r'PATH ONLY\s+RANGED (\d+) of (\d+)', block, f'{label}: PATH ONLY')
        rows.append((label, without, with_n))
    return rows


def fresh_rows():
    """Our fresh episodes (pre-registration 11): the row for panel (a) and the graph-answer row for panel (b)."""
    t = (RES / '09' / 'analyze_11.txt').read_text(encoding='utf-8')
    with_n = need(r'^\s+all arms\s+ADDRESS\s+(\d+) of (\d+)', t, 'fresh episodes: ADDRESS')
    without = need(r'^\s+all arms\s+PATH ONLY\s+(\d+) of (\d+)', t, 'fresh episodes: PATH ONLY')
    g_name = need(r'^\s+arm N\s+GRAPH NAME\s+(\d+) of (\d+)', t, 'fresh episodes: GRAPH NAME')
    g_addr = need(r'^\s+all arms\s+GRAPH ADDRESS\s+(\d+) of (\d+)', t, 'fresh episodes: GRAPH ADDRESS')
    episodes = sum(int(n) - int(e) for n, e in re.findall(r'arm \w+: (\d+) episodes, (\d+) with an error', t))
    return ((f'Our {episodes} fresh episodes, 31B\nthresholds fixed in advance', without, with_n),
            ('fresh episodes, Gemma-4-31B:\nthe graph tools\' own answers', g_name, g_addr))


def replay_rows():
    """[(label, (k, n) without line numbers, (k, n) with them)] from the replay report's pooled lines."""
    t = (RES / 'explore_first_reads.txt').read_text(encoding='utf-8')
    rows = []
    for label, model in (('paused steps, Gemma-4-31B', 'Gemma-4-31B'), ('paused steps, Gemma 4 26B-A4B', 'Gemma 4 26B-A4B'),
                         ('paused steps, Gemma 4 E4B', 'Gemma 4 E4B'), ('paused steps, Qwen2.5-Coder-32B', 'Qwen2.5-Coder-32B')):
        pat = rf'^\s+{re.escape(model)}\s+%s\s*: first reads (\d+), ask past line 1 (\d+)'
        if not re.search(pat % 'with', t, re.M):
            if model.startswith('Qwen'):
                continue  # drawn only once that run is in the report
            raise SystemExit(f'make_fig_law: no pooled line for {model}')
        n1, k1 = need(pat % 'with', t, f'{model}: with')
        n0, k0 = need(pat % 'without', t, f'{model}: without')
        rows.append((label, (k0, n0), (k1, n1)))
    return rows


def panel(ax, rows, title, legend, n_slots, bold=()):
    h = 0.34
    ys = []
    for i, (label, without, with_n) in enumerate(rows):
        y = -i
        ys.append(y)
        for (k, n), dy, color in ((without, +h / 2, GREY), (with_n, -h / 2, BLUE)):
            share = 100 * k / n
            ax.barh(y + dy, share, height=h, color=color, edgecolor='none', zorder=2)
            ax.text(share + 1.2, y + dy, f'{k:,} of {n:,}', va='center', ha='left', fontsize=8, color=INK, zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    for i, t in enumerate(ax.get_yticklabels()):
        if i in bold:
            t.set_fontweight('bold')
    ax.set_ylim(-n_slots + 0.45, 0.6)  # the same row height in both panels
    ax.spines['bottom'].set_position(('data', -len(rows) + 0.45))
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.tick_params(axis='x', labelsize=8.5, length=3)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.set_title(title, fontsize=9, color=INK, loc='left', pad=8)
    handles = [plt.Rectangle((0, 0), 1, 1, color=GREY), plt.Rectangle((0, 0), 1, 1, color=BLUE)]
    yb = (0.6 - (-len(rows) + 0.45)) / (0.6 - (-n_slots + 0.45))  # the panel's bottom spine, in axes fractions from the top
    ax.legend(handles, legend, loc='upper center', bbox_to_anchor=(0.5, 1 - yb - 0.09), ncol=2, frameon=False,
              fontsize=8.5, handlelength=1.4, columnspacing=1.6)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=str(FIG))
    args = ap.parse_args()
    pub, rep = public_rows(), replay_rows()
    ours, graph = fresh_rows()
    pub.append(ours)
    rep.append(graph)
    n_slots = max(len(pub), len(rep))
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.4, 0.62 * n_slots + 0.95),
                               gridspec_kw={'width_ratios': [1.2, 1], 'wspace': 0.66})
    panel(a, pub, '(a) Observed: by what the result just before named', ['a file', 'a file with a line number'], n_slots,
          bold=(len(pub) - 1,))
    panel(b, rep, '(b) Tested: the graph\'s answer, by how it is written',
          ['names only', 'names with file and line range'], n_slots)
    fig.suptitle('First reads of a file that ask for lines past line 1', fontsize=10.5, color=INK, x=0.5, y=0.985)
    fig.subplots_adjust(left=0.2, right=0.985, top=0.86, bottom=0.14)
    # the two things an agent is shown, in the free corner under panel (b)
    x0, y0 = 0.60, 0.215
    fig.text(x0, y0, 'What the agent is shown', fontsize=8.8, color=INK, ha='left', va='top')
    for i, (name, text, color) in enumerate((('a numbered search', 'fastapi/_compat.py:272:def copy_field_info(', BLUE),
                                             ('the graph tools', '"fastapi._compat.copy_field_info"', INK2))):
        y = y0 - 0.052 - i * 0.072
        fig.text(x0, y, name, fontsize=8.2, color=INK2, ha='left', va='top')
        fig.text(x0 + 0.105, y, text, fontsize=7.8, color=color, family='DejaVu Sans Mono', ha='left', va='top')
    out = Path(args.out)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_law.{ext}', dpi=300)
    plt.close(fig)
    for label, without, with_n in pub + rep:
        print(f'{label.splitlines()[0]:<36} without {without[0]:>4} of {without[1]:<5} with {with_n[0]:>4} of {with_n[1]}')
    print(f'wrote fig_law.png and fig_law.svg in {out}')


if __name__ == '__main__':
    main()
