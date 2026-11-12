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

INK, INK2, MUTED = '#222222', '#555555', '#8a8a8a'
PALE, BLUE, LIGHT, GRID = '#b9b9b9', '#1f6fb4', '#8fb5dc', '#ececec'
plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'], 'font.size': 9,
    'axes.edgecolor': MUTED, 'axes.linewidth': 0.6, 'xtick.color': INK2, 'ytick.color': INK2,
    'svg.fonttype': 'none', 'savefig.facecolor': 'white', 'figure.facecolor': 'white',
})
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

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ys = list(range(len(data)))[::-1]
    for y, (label, r, _n) in zip(ys, data):
        lo, hi = min(r.values()), max(r.values())
        ax.plot([lo, hi], [y, y], color=PALE, lw=1.2, zorder=1)
        ax.scatter(r['KE'], y, s=34, color=MUTED, zorder=3, label='inside the tool output, last' if y == ys[0] else None)
        if 'KF' in r:
            ax.scatter(r['KF'], y, s=34, facecolor='white', edgecolor=BLUE, lw=1.3, zorder=3,
                       label='inside the tool output, first' if label == data[1][0] else None)
        ax.scatter(r['EL'], y, s=40, color=BLUE, zorder=4, label='as a separate note' if y == ys[0] else None)
        ax.text(-0.6, y, label, ha='right', va='center', fontsize=9, color=INK,
                fontweight='bold' if label == 'Gemma-4-31B' else 'normal')
        ax.text(19.6, y, 'note > last: met' if label in K2_MET else 'not detected', ha='left', va='center',
                fontsize=7.8, color=BLUE if label in K2_MET else MUTED)
    ax.set_yticks([])
    ax.set_xlim(0, 19)
    ax.set_ylim(-0.7, len(data) - 0.3)
    ax.set_xlabel("share of paused steps whose next call reads a listed neighbor's code (%)", color=INK2, fontsize=8.5)
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=8.2, handletextpad=0.3,
              columnspacing=1.4)
    fig.subplots_adjust(left=0.24, right=0.83, top=0.88, bottom=0.14)
    out = Path(args.out)
    for ext in ('png', 'svg'):
        fig.savefig(out / f'fig_place.{ext}', dpi=200)
    print('wrote', out / 'fig_place.png')


if __name__ == '__main__':
    main()
