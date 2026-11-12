"""Pre-registration 26: the cross-model table. Runs the registered analysis of 25 (analysis/analyze_25.py <run_dir>)
and its blind second script (analysis/rederive_25.py --rows <run_dir>/results.jsonl --no-write) on each model's run
under analysis/results/26/<model>/forks, unchanged, and collects their printed lines: gate (a), the steps with a
complete cell, the three rates, K1 and K2 with their intervals. A rule is met if its interval lies above zero in the
output of analyze_25.py and the second script agrees (registration 26: on disagreement the model counts as "not
detected"). Gate (b) of 25 is ignored (registration 26). Prints the reading fixed in the registration.

Usage: py -I -X utf8 analysis/analyze_26.py [--write]   (--write stores analysis/results/26/analyze_26.txt)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'analysis' / 'results' / '26'
MODELS = ['deepseek-ai/DeepSeek-V4.1-Flash-1017', 'MiniMaxAI/MiniMax-M3.1-Flash', 'nvidia/nemotron-3-super-120b-a12b',
          'openai/gpt-oss-120b', 'Qwen/Qwen3-235B-A22B-Instruct-2507', 'Qwen/Qwen3-30B-A3B-Instruct-2507',
          'zai-org/GLM-5.3-Flash']
NUM = r'([+-]?\d+\.\d+)'
IV = NUM + r' \[' + NUM + r', ' + NUM + r'\]'


def run(args):
    p = subprocess.run([sys.executable, '-I', '-X', 'utf8', *args], cwd=ROOT, capture_output=True)
    return p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n')


def grab(text, pattern):
    m = re.search(pattern, text)
    return m.groups() if m else None


def main():
    out = []
    p = out.append
    p('PRE-REGISTRATION 26: the place of the list (25) on seven hosted models; analyze_25.py and rederive_25.py, unchanged')
    p('model | gate (a) | steps | KH% KE% EL% | K1 KE-KH [95%] | K2 EL-KE [95%] | second script K2 | K2 verdict')
    met, through = [], []
    for m in MODELS:
        d = BASE / m.replace('/', '__') / 'forks'
        if not (d / 'results.jsonl').exists():
            p(f'{m} | no run')
            continue
        a = run(['analysis/analyze_25.py', str(d.relative_to(ROOT))])
        b = run(['analysis/rederive_25.py', '--rows', str((d / 'results.jsonl').relative_to(ROOT)), '--no-write'])
        gate_a = grab(a, r'\(a\)[^\n]*: (PASS|FAIL)') or grab(a, r'gate \(a\)[^\n]*(PASS|FAIL)')
        steps = grab(a, r'steps with at least one complete cell: (\d+)')
        rates = [grab(a, rf'\n\s+{arm}: {NUM}') for arm in ('KH', 'KE', 'EL')]
        k1 = grab(a, r'K1, [^\n]*?: ' + IV)
        k2 = grab(a, r'K2, [^\n]*?: ' + IV)
        k2b = grab(b, r'K2 [^\n]*?: ' + IV)
        ok = bool(gate_a and gate_a[0] == 'PASS' and steps and int(steps[0]) >= 200)
        k2a_met = bool(k2 and float(k2[1]) > 0)
        k2b_met = bool(k2b and float(k2b[1]) > 0)
        verdict = ('the place matters' if (k2a_met and k2b_met) else 'not detected') if ok else 'no verdict (gate)'
        if ok:
            through.append(m)
            if k2a_met and k2b_met:
                met.append(m)
        r = ' '.join(x[0] if x else '?' for x in rates)
        p(f'{m} | {gate_a[0] if gate_a else "?"} | {steps[0] if steps else "?"} | {r} | '
          f'{k1[0] + " [" + k1[1] + ", " + k1[2] + "]" if k1 else "?"} | '
          f'{k2[0] + " [" + k2[1] + ", " + k2[2] + "]" if k2 else "?"} | '
          f'{k2b[0] + " [" + k2b[1] + ", " + k2b[2] + "]" if k2b else "?"} | {verdict}')
    p(f'models through the gate: {len(through)}; K2 met: {len(met)} {met}')
    if len(through) < 5:
        reading = 'fewer than 5 models through the gate: no cross-model reading'
    elif len(met) >= 5:
        reading = 'the place effect generalizes'
    elif len(met) >= 2:
        reading = 'it holds on some models'
    else:
        reading = 'it is not shown beyond Gemma'
    p(f'READING: {reading}')
    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if '--write' in sys.argv:
        (BASE / 'analyze_26.txt').write_text(text, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
