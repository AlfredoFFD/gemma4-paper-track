"""Pre-registration 28: the key first. Registered analysis.

For each of the seven hosted models of 26, reads the rows of 28 (analysis/results/28/<model>/forks/results.jsonl:
record arm KF, the list as the FIRST key of the file view's result, seed 1, the system prompt of 26) and the stored rows
of 26 (record arms KE, the list as the LAST key, and EL, the list as a note after the view). Scoring is that of 25,
imported unchanged (analyze_25.record_of; gates_c.failure excludes interface failures; gates_c.any_true on the step of
analysis/fork_states_d/states.jsonl). Seed 1; the first row of a (step, record arm) cell counts.

Rules (registration 28), per model, 95% bootstrap by step (analyze_forks.diff_ci, 2,000 resamples, seed 0):
  P1  KF minus KE, on the steps whose KF and KE replays are both usable. "The first place raises uptake" if the
      interval lies above zero; otherwise "not detected".
  P2  EL minus KF, on the steps whose EL and KF replays are both usable. "The note still beats the first place" if the
      interval lies above zero; otherwise "not detected".
Gate per model: at least 80% of 28's replays usable and at least 200 steps entering each rule.
Reading across the models through the gate (n1 = models with P1 met, n2 = models with P2 met):
  n1 >= 4 and n2 <= 1: "the first place recovers the note"; n1 >= 4 and n2 >= 2: "the place within the result matters,
  and the separate note adds more"; n1 <= 1: "not the place within the result"; otherwise "mixed". Fewer than 5 models
  through the gate: per-model verdicts only.

Usage: py -I -X utf8 analysis/analyze_28.py [--write]   (--write stores analysis/results/28/analyze_28.txt)
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import diff_ci  # noqa: E402
from analyze_25 import record_of  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states  # noqa: E402

MODELS = ['deepseek-ai/DeepSeek-V4.1-Flash-1017', 'MiniMaxAI/MiniMax-M3.1-Flash', 'nvidia/nemotron-3-super-120b-a12b',
          'openai/gpt-oss-120b', 'Qwen/Qwen3-235B-A22B-Instruct-2507', 'Qwen/Qwen3-30B-A3B-Instruct-2507',
          'zai-org/GLM-5.3-Flash']
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL', 'KF': 'A'}
GATE_USABLE, MIN_STEPS = 0.80, 200


def cells(path, arms):
    usable, n, ok, seen = {}, collections.Counter(), collections.Counter(), set()
    for r in load_rows(path):
        if r.get('skip') or r.get('seed') != 1:
            continue
        rec = record_of(r)
        if rec is None or rec[1] not in arms or r['arm'] != RUNNER_ARM[rec[1]]:
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
    p('PRE-REGISTRATION 28: the key first (arm KF on the seven hosted models of 26, seed 1; KE and EL from 26)')
    p('model | usable % KF | KF% KE% EL% (paired steps) | P1 KF-KE [95%] (steps) | P2 EL-KF [95%] (steps)')
    n1, n2, through = [], [], []
    for m in MODELS:
        d = m.replace('/', '__')
        p28 = HERE / 'results' / '28' / d / 'forks' / 'results.jsonl'
        p26 = HERE / 'results' / '26' / d / 'forks' / 'results.jsonl'
        if not p28.exists():
            p(f'{m} | no run')
            continue
        u28, n28, ok28 = cells(p28, {'KF'})
        u26, _n, _o = cells(p26, {'KE', 'EL'})

        def sc(u, k, a):
            return [any_true(states[k], u[(k, a)]['next_call'])]

        kf = {k for (k, a) in u28}
        ke = {k for (k, a) in u26 if a == 'KE'}
        el = {k for (k, a) in u26 if a == 'EL'}
        s1, s2 = sorted(kf & ke), sorted(kf & el)
        r1 = diff_ci({k: sc(u28, k, 'KF') for k in s1}, {k: sc(u26, k, 'KE') for k in s1})
        r2 = diff_ci({k: sc(u26, k, 'EL') for k in s2}, {k: sc(u28, k, 'KF') for k in s2})
        share = ok28['KF'] / n28['KF'] if n28['KF'] else 0
        gate = share >= GATE_USABLE and len(s1) >= MIN_STEPS and len(s2) >= MIN_STEPS
        m1 = gate and r1[1] is not None and r1[1] > 0
        m2 = gate and r2[1] is not None and r2[1] > 0
        if gate:
            through.append(m)
            n1 += [m] if m1 else []
            n2 += [m] if m2 else []
        rate = lambda u, ks, a: 100 * sum(sc(u, k, a)[0] for k in ks) / len(ks) if ks else float('nan')
        v1 = ('the first place raises uptake' if m1 else 'not detected') if gate else 'no verdict (gate)'
        v2 = ('the note still beats the first place' if m2 else 'not detected') if gate else 'no verdict (gate)'
        p(f'{m} | {100 * share:.1f} | {rate(u28, s1, "KF"):.2f} {rate(u26, s1, "KE"):.2f} {rate(u26, s2, "EL"):.2f} | '
          f'{fmt(r1)} ({len(s1)}): {v1} | {fmt(r2)} ({len(s2)}): {v2}')
    p(f'models through the gate: {len(through)}; P1 met: {len(n1)} {n1}; P2 met: {len(n2)} {n2}')
    if len(through) < 5:
        reading = 'fewer than 5 models through the gate: per-model verdicts only'
    elif len(n1) >= 4 and len(n2) <= 1:
        reading = 'the first place recovers the note'
    elif len(n1) >= 4:
        reading = 'the place within the result matters, and the separate note adds more'
    elif len(n1) <= 1:
        reading = 'not the place within the result'
    else:
        reading = 'mixed'
    p(f'READING: {reading}')
    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if '--write' in sys.argv:
        (HERE / 'results' / '28' / 'analyze_28.txt').write_text(text, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
