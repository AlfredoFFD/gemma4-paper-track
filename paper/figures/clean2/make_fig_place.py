"""Figure 'where the list sits': for Gemma-4-31B (pre-registration 25) and the seven hosted models (26, 28), the share of
paused steps whose next call reads a listed neighbor's code when the same addressed list comes (i) as the last key of the
file view's result, (ii) as its first key (28; not run on Gemma), (iii) as a separate note after the view.

Rates are computed from the stored rows with the scoring of 25, imported unchanged (analyze_25.record_of, gates_c.failure,
gates_c.any_true), seed 1, on the steps where every arm drawn for that model is usable. The registered tests of these
contrasts are in Table 2 and Appendix K; this figure draws point rates only.

Usage: .venv/Scripts/python.exe -I -X utf8 paper/figures/clean/make_fig_place.py [--out <dir>]
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
A = ROOT / 'analysis'
sys.path.insert(0, str(A))
from analyze_25 import record_of  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states  # noqa: E402

# clean2 restyle (the paper's one color meaning): addresses royal blue (a tint for the last key, full for the first),
# a separate message green; light grey ticks, very light grid, baseline only.
INK, INK2, MUTED, TICK = '#1f1f1f', '#555555', '#8c8c8c', '#9a9a9a'
ROYAL, ROYAL_T, GREEN = '#1D3BE8', '#9AA8F5', '#14A37F'
PALE, GRID, BASE = '#dcdcdc', '#efefef', '#cfcfcf'
plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'], 'font.size': 9,
    'axes.edgecolor': BASE, 'axes.linewidth': 0.6, 'xtick.color': TICK, 'ytick.color': TICK,
    'xtick.labelcolor': TICK, 'xtick.major.size': 0, 'ytick.major.size': 0,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white',
})
LAST, FIRST, NOTE = 'last in the tool output', 'first in the tool output', 'as a separate message'
MODELS = [('Gemma-4-31B', None), ('Qwen3-235B', 'Qwen/Qwen3-235B-A22B-Instruct-2507'),
          ('gpt-oss-120b', 'openai/gpt-oss-120b'), ('Nemotron-3 Super', 'nvidia/nemotron-3-super-120b-a12b'),
          ('GLM-5.3-Flash', 'zai-org/GLM-5.3-Flash'), ('DeepSeek-V4.1-Flash', 'deepseek-ai/DeepSeek-V4.1-Flash-1017'),
          ('Qwen3-30B', 'Qwen/Qwen3-30B-A3B-Instruct-2507'), ('MiniMax-M3.1-Flash', 'MiniMaxAI/MiniMax-M3.1-Flash')]
K2_MET = {'Gemma-4-31B', 'Qwen3-235B', 'gpt-oss-120b', 'Nemotron-3 Super'}   # 25 and analysis/results/26/analyze_26.txt


def usable(path, arms):
    out, seen = {}, set()
    for r in load_rows(path):
        if r.get('skip') or r.get('seed') != 1:
            continue
        rec = record_of(r)
        if rec is None or rec[1] not in arms:
            continue
        key = ((r['task'], r['run'], rec[0]), rec[1])
        if key in seen:
            continue
        seen.add(key)
        if not failure(r):
            out[key] = r
    return out


def rates(states, rows):
    arms = sorted({a for (_k, a) in rows})
    steps = set.intersection(*[{k for (k, a) in rows if a == b} for b in arms])
    return {a: 100 * sum(any_true(states[k], rows[(k, a)]['next_call']) for k in steps) / len(steps) for a in arms}, len(steps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()
    states = load_states(A / 'fork_states_d' / 'states.jsonl')
    data = []
    for label, m in MODELS:
        if m is None:
            rows = usable(A / 'results' / '25' / 'forks' / 'results.jsonl', {'KE', 'EL'})
        else:
            d = m.replace('/', '__')
            rows = usable(A / 'results' / '26' / d / 'forks' / 'results.jsonl', {'KE', 'EL'})
            p28 = A / 'results' / '28' / d / 'forks' / 'results.jsonl'
            if p28.exists():
                rows.update(usable(p28, {'KF'}))
        r, n = rates(states, rows)
        data.append((label, r, n))
        print(f'{label}: ' + ', '.join(f'{a} {v:.2f}%' for a, v in sorted(r.items())) + f' ({n} steps)')

    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    ys = list(range(len(data)))[::-1]
    for y, (label, r, _n) in zip(ys, data):
        lo, hi = min(r.values()), max(r.values())
        ax.plot([lo, hi], [y, y], color=PALE, lw=1.6, zorder=1, solid_capstyle='round')
        ax.scatter(r['KE'], y, s=38, color=ROYAL_T, edgecolor='white', lw=0.8, zorder=3)
        if 'KF' in r:
            ax.scatter(r['KF'], y, s=38, color=ROYAL, edgecolor='white', lw=0.8, zorder=3)
        ax.scatter(r['EL'], y, s=38, color=GREEN, edgecolor='white', lw=0.8, zorder=4)
        ax.text(-0.6, y, label, ha='right', va='center', fontsize=8.2, color=INK)
        met = label in K2_MET
        ax.text(19.6, y, 'met' if met else 'not detected', ha='left', va='center', fontsize=7.8,
                color=GREEN if met else MUTED)
    ax.text(19.6, len(data) - 0.35, 'separate message > last', ha='left', va='bottom', fontsize=7.6, color=MUTED)
    ax.set_yticks([])
    ax.set_xlim(0, 19)
    ax.set_ylim(-0.7, len(data) - 0.3)
    ax.set_xlabel("share of paused steps whose next call reads a listed neighbor's code (%)", color=TICK, fontsize=8.0,
                  labelpad=6)
    ax.tick_params(axis='x', labelsize=7.8, length=0, pad=4)
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for sp in ('top', 'right', 'left'):
        ax.spines[sp].set_visible(False)
    from matplotlib.lines import Line2D
    keys = [Line2D([], [], ls='none', marker='o', ms=6, mfc=c, mec='white', mew=0.8, label=lab)
            for c, lab in ((ROYAL_T, LAST), (ROYAL, FIRST), (GREEN, NOTE))]
    fig.legend(handles=keys, loc='lower center', bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False, fontsize=7.8,
               handletextpad=0.2, columnspacing=1.8, labelcolor=INK2)
    fig.subplots_adjust(left=0.20, right=0.80, top=0.93, bottom=0.22)
    out = Path(args.out)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_place.{ext}', dpi=200)
    print('wrote', out / 'fig_place.png')


if __name__ == '__main__':
    main()
