"""Pre-registration 27: one line in the system prompt. Registered analysis.

For each of the seven hosted models of 26, reads the rows of 27 (analysis/results/27/<model>/forks/results.jsonl: the
records of 25 under arms KH, KE, EL, seed 1, with the system prompt plus one added section) and the stored rows of 26
(analysis/results/26/<model>/forks/results.jsonl: the same records, arms and seed, without the line). Scoring is that of
25, imported unchanged: a row's record from its fork (analyze_25.record_of), interface failures excluded
(gates_c.failure), the outcome "reads a neighbor's code" (gates_c.any_true on the step of
analysis/fork_states_d/states.jsonl). The first row of a (step, arm) cell counts.

Rules (registration 27), per model, 95% bootstrap by step (analyze_forks.diff_ci, 2,000 resamples, seed 0):
  L1  KE with the line minus KE without it (26), on the steps whose KE replay is usable in both runs.
      "The line raises uptake inside the view" if the interval lies above zero; otherwise "not detected".
  L2  EL minus KE, both with the line, on the steps with all three arms usable in 27.
      "A gap remains with the line" if the interval lies above zero; otherwise "not detected".
Gate per model: at least 80% of 27's replays usable in each arm and at least 200 steps entering L1 and L2.
Reading across the models through the gate: "one line lifts uptake inside the view" if L1 is met on at least 5;
"on some models" if on 2 to 4; "not shown" if on 0 or 1; no reading if fewer than 5 models pass the gate.
Printed without a rule: KH and EL with the line minus without it; L1 and L2 on the three models where 26 met K2.

Usage: py -I -X utf8 analysis/analyze_27.py [--write]   (--write stores analysis/results/27/analyze_27.txt)
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import diff_ci  # noqa: E402
from analyze_25 import RUNNER_ARM, record_of  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states  # noqa: E402

MODELS = ['deepseek-ai/DeepSeek-V4.1-Flash-1017', 'MiniMaxAI/MiniMax-M3.1-Flash', 'nvidia/nemotron-3-super-120b-a12b',
          'openai/gpt-oss-120b', 'Qwen/Qwen3-235B-A22B-Instruct-2507', 'Qwen/Qwen3-30B-A3B-Instruct-2507',
          'zai-org/GLM-5.3-Flash']
K2_MET_IN_26 = {'nvidia/nemotron-3-super-120b-a12b', 'openai/gpt-oss-120b', 'Qwen/Qwen3-235B-A22B-Instruct-2507'}
ARMS = ('KH', 'KE', 'EL')
GATE_USABLE, MIN_STEPS = 0.80, 200


def cells(path):
    """{(step key, arm): row} for usable seed-1 rows; and per-arm counts (attempted, usable)."""
    usable, n, ok, seen = {}, collections.Counter(), collections.Counter(), set()
    for r in load_rows(path):
        if r.get('skip') or r.get('seed') != 1:
            continue
        rec = record_of(r)
        if rec is None or rec[1] not in ARMS or r['arm'] != RUNNER_ARM[rec[1]]:
            continue
        key = (r['task'], r['run'], rec[0])
        if (key, rec[1]) in seen:
            continue
        seen.add((key, rec[1]))
        n[rec[1]] += 1
        if not failure(r):
            ok[rec[1]] += 1
            usable[(key, rec[1])] = r
    return usable, n, ok


def fmt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    out = []
    p = out.append
    p('PRE-REGISTRATION 27: one line in the system prompt (arms of 25 on the seven hosted models of 26, seed 1)')
    p('model | usable % KH KE EL (27) | L1 KE line-noline [95%] (steps) | L2 EL-KE with line [95%] (steps) | '
      'no rule: KH line-noline | EL line-noline')
    met1, through = [], []
    for m in MODELS:
        d27 = HERE / 'results' / '27' / m.replace('/', '__') / 'forks' / 'results.jsonl'
        d26 = HERE / 'results' / '26' / m.replace('/', '__') / 'forks' / 'results.jsonl'
        if not d27.exists():
            p(f'{m} | no run')
            continue
        u27, n27, ok27 = cells(d27)
        u26, _n26, _ok26 = cells(d26)

        def score(u, k, a):
            return [any_true(states[k], u[(k, a)]['next_call'])]

        def paired(a):
            ks = sorted({k for (k, b) in u27 if b == a} & {k for (k, b) in u26 if b == a})
            return diff_ci({k: score(u27, k, a) for k in ks}, {k: score(u26, k, a) for k in ks}), len(ks)

        l1, n1 = paired('KE')
        full = sorted(k for k in {k for (k, _a) in u27} if all((k, a) in u27 for a in ARMS))
        l2 = diff_ci({k: score(u27, k, 'EL') for k in full}, {k: score(u27, k, 'KE') for k in full})
        kh, _ = paired('KH')
        el, _ = paired('EL')
        shares = [ok27[a] / n27[a] if n27[a] else 0 for a in ARMS]
        gate = all(s >= GATE_USABLE for s in shares) and n1 >= MIN_STEPS and len(full) >= MIN_STEPS
        v1 = ('the line raises uptake inside the view' if l1[1] is not None and l1[1] > 0 else 'not detected') \
            if gate else 'no verdict (gate)'
        v2 = ('a gap remains with the line' if l2[1] is not None and l2[1] > 0 else 'not detected') \
            if gate else 'no verdict (gate)'
        if gate:
            through.append(m)
            if l1[1] is not None and l1[1] > 0:
                met1.append(m)
        star = ' (K2 met in 26)' if m in K2_MET_IN_26 else ''
        p(f'{m}{star} | {" ".join(f"{100 * s:.1f}" for s in shares)} | {fmt(l1)} ({n1}): {v1} | '
          f'{fmt(l2)} ({len(full)}): {v2} | {fmt(kh)} | {fmt(el)}')
    p(f'models through the gate: {len(through)}; L1 met: {len(met1)} {met1}')
    if len(through) < 5:
        reading = 'fewer than 5 models through the gate: no cross-model reading'
    elif len(met1) >= 5:
        reading = 'one line lifts uptake inside the view'
    elif len(met1) >= 2:
        reading = 'on some models'
    else:
        reading = 'not shown'
    p(f'READING: {reading}')
    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if '--write' in sys.argv:
        (HERE / 'results' / '27' / 'analyze_27.txt').write_text(text, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
