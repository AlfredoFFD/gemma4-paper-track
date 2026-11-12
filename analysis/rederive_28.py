"""Independent re-derivation of pre-registration 28 (the key first).

Written blind: from the frozen text of prereg/28-the-key-first.md (with the outcome it takes over from
prereg/25-the-place-of-the-list.md) alone, without sight of the registered analysis of 28 or of any row of 28. It reads
the replay rows of 28, record arm KF (analysis/results/28/<model>/forks/results.jsonl), those of 26, record arms KE and
EL (analysis/results/26/<model>/forks/results.jsonl), and the 407 paused steps of 03 (analysis/fork_states_d/states.jsonl,
whose spans every arm is scored on). Directory names replace "/" in a model's name with "__".

It imports, unchanged: the scorer gates_c.any_true ("reads a neighbor's code", the registered outcome of 25), the
interface-failure rule gates_c.failure, gates_c.load_rows / load_states, and the paired bootstrap analyze_forks.diff_ci
(2,000 resamples, seed 0), each step entering with its one outcome as a one-element list.

Rules, per model: P1 = KF (28) minus KE (26), on the steps whose KF and KE replays are both usable; P2 = EL (26) minus
KF (28), on the steps whose EL and KF replays are both usable. A rule is met if the 95% interval lies above zero
(lower bound strictly above 0). Gate: at least 80% of 28's replays usable, and at least 200 steps entering each rule.
Then the reading fixed in the registration, across the models through the gate.

Usage: py -I -X utf8 analysis/rederive_28.py [--no-write] [--kf-root <dir>] [--kf-arm <arm>]
Without options it prints the report and writes the same text to analysis/results/rederive_28.txt (LF).
--no-write prints only.
--kf-root reads the KF side from another root (<dir>/<model>/forks/results.jsonl); --kf-arm takes the rows of another
record arm there as KF, relabelled in memory. Check run: --kf-root analysis/results/26 --kf-arm KE, where P1 must be
exactly 0. Either option means nothing is written.
"""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from analyze_forks import diff_ci  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states  # noqa: E402

ROOT28 = HERE / 'results' / '28'
ROOT26 = HERE / 'results' / '26'
STATES = HERE / 'fork_states_d' / 'states.jsonl'
STATES_MD5 = 'd3105df0dc4aa43d7bb0afbdd6123b44'
OUT = HERE / 'results' / 'rederive_28.txt'

# The seven hosted models of 26 (the registration says "the seven hosted models of 26" without listing them; these are
# the seven model directories under analysis/results/26/).
MODELS = (
    'MiniMaxAI/MiniMax-M3.1-Flash',
    'Qwen/Qwen3-235B-A22B-Instruct-2507',
    'Qwen/Qwen3-30B-A3B-Instruct-2507',
    'deepseek-ai/DeepSeek-V4.1-Flash-1017',
    'nvidia/nemotron-3-super-120b-a12b',
    'openai/gpt-oss-120b',
    'zai-org/GLM-5.3-Flash',
)
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'KF': 'A', 'EL': 'EL'}
SEED = 1
PLANNED = 322
GATE_USABLE = 0.80
FLOOR = 200

L = []


def p(s=''):
    L.append(s)


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def rel(path):
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def fdiff(t):
    pt, lo, hi = t
    return 'n/a' if pt is None else f'{100 * pt:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]'


def above_zero(t):
    return t[1] is not None and t[1] > 0


def pct(u, n):
    return f'{100 * u / n:.2f}%' if n else 'n/a'


# ---------------------------------------------------------------- one file of one model

def read_run(path, states, wanted):
    """wanted: {record arm in the file: label used here}. Returns cells {(step, label): first row at seed 1},
    usable outcomes {(step, label): 0/1}, failure counts {(label, kind): n}, and counts of rows set aside."""
    rows = load_rows(path)
    cells = {}
    c = Counter()
    for r in rows:
        parts = str(r.get('fork')).split(':')
        if len(parts) != 3:
            c['bad_fork'] += 1
            continue
        f0, arm, sd = parts
        try:
            step = (r['task'], r['run'], int(f0))
            sd = int(sd)
        except (KeyError, ValueError):
            c['bad_fork'] += 1
            continue
        if arm not in wanted:
            c[f'other_arm_{arm}'] += 1
            continue
        if sd != SEED or r.get('seed') != SEED:
            if sd == SEED or r.get('seed') == SEED:
                c['seed_disagrees'] += 1
            else:
                c['other_seed'] += 1
            continue
        if step not in states:
            c['no_state'] += 1
            continue
        if r.get('arm') != RUNNER_ARM[arm]:
            c['runner_arm_mismatch'] += 1          # counted only; the row is kept
        k = (step, wanted[arm])
        if k in cells:
            c['repeat'] += 1                       # the first row of a cell counts
            continue
        cells[k] = r
    out, fails = {}, Counter()
    for k, r in cells.items():
        f = failure(r)
        if f:
            fails[(k[1], f)] += 1
            continue
        out[k] = any_true(states[k[0]], r['next_call'])
    c['rows'] = len(rows)
    return cells, out, fails, c


def share(cells, out, label):
    n = sum(1 for k in cells if k[1] == label)
    u = sum(1 for k in out if k[1] == label)
    return u, n


def steps_of(out, label):
    return {k[0] for k in out if k[1] == label}


# ---------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--kf-root', default=None, help='root of the KF rows (default analysis/results/28)')
    ap.add_argument('--kf-arm', default='KF', help='record arm read as KF from the KF root (default KF)')
    a = ap.parse_args(argv)
    root28 = Path(a.kf_root) if a.kf_root else ROOT28
    kf_arm = a.kf_arm
    check = a.kf_root is not None or kf_arm != 'KF'
    write = not a.no_write and not check

    p('Re-derivation of pre-registration 28, the key first (independent script, written blind from the frozen'
      ' registration text; imports gates_c.any_true / failure / load_rows / load_states and analyze_forks.diff_ci'
      ' unchanged)')
    h = md5(STATES)
    states = load_states(STATES)
    p(f'states analysis/fork_states_d/states.jsonl md5 {h} ({"as registered in 25" if h == STATES_MD5 else "DIFFERS from 25"});'
      f' {len(states)} paused steps')
    p(f'KF rows: {rel(root28)}/<model>/forks/results.jsonl, record arm {kf_arm}'
      + (' relabelled KF in memory' if kf_arm != 'KF' else '')
      + f'; KE and EL rows (26): {rel(ROOT26)}/<model>/forks/results.jsonl'
      + ('   [CHECK RUN: KF side redirected, nothing written]' if check else ''))
    p('per model, at seed 1: usable share of KF; P1 = KF(28) - KE(26) on the steps with KF and KE usable; P2 = EL(26) -'
      ' KF(28) on the steps with EL and KF usable; points, 95% bootstrap by step, 2,000 resamples, seed 0; met if the'
      ' lower bound is above 0; gate: KF usable share at least 80% and at least 200 steps in each rule')
    p('')

    res = {}
    details = []
    model_dirs = {m.replace('/', '__') for m in MODELS}
    extra_dirs = sorted(d.name for d in ROOT26.iterdir() if d.is_dir() and d.name not in model_dirs) \
        if ROOT26.is_dir() else []
    p('1. PER MODEL')
    for m in MODELS:
        d = m.replace('/', '__')
        f28 = root28 / d / 'forks' / 'results.jsonl'
        f26 = ROOT26 / d / 'forks' / 'results.jsonl'
        missing = [x for x in (f28, f26) if not x.exists()]
        if missing:
            p(f'  {m}: results file missing ({", ".join(rel(x) for x in missing)}); not through the gate')
            res[m] = {'gate': False, 'm1': False, 'm2': False, 'missing': True}
            continue
        c28, o28, x28, n28 = read_run(f28, states, {kf_arm: 'KF'})
        c26, o26, x26, n26 = read_run(f26, states, {'KE': 'KE', 'EL': 'EL'})
        skf = share(c28, o28, 'KF')
        ske, sel = share(c26, o26, 'KE'), share(c26, o26, 'EL')

        kf_steps, ke_steps, el_steps = steps_of(o28, 'KF'), steps_of(o26, 'KE'), steps_of(o26, 'EL')
        steps1 = sorted(kf_steps & ke_steps)
        steps2 = sorted(el_steps & kf_steps)
        p1 = diff_ci({s: [o28[(s, 'KF')]] for s in steps1}, {s: [o26[(s, 'KE')]] for s in steps1}) if steps1 else (None,) * 3
        p2 = diff_ci({s: [o26[(s, 'EL')]] for s in steps2}, {s: [o28[(s, 'KF')]] for s in steps2}) if steps2 else (None,) * 3

        usable_ok = skf[1] > 0 and skf[0] / skf[1] >= GATE_USABLE
        floor_ok = len(steps1) >= FLOOR and len(steps2) >= FLOOR
        gate = usable_ok and floor_ok
        why = []
        if not usable_ok:
            why.append('KF usable share under 80%')
        if len(steps1) < FLOOR:
            why.append('fewer than 200 steps in P1')
        if len(steps2) < FLOOR:
            why.append('fewer than 200 steps in P2')
        m1, m2 = above_zero(p1), above_zero(p2)
        if gate:
            v1 = 'the first place raises uptake' if m1 else 'not detected'
            v2 = 'the note still beats the first place' if m2 else 'not detected'
        else:
            v1 = v2 = 'no verdict (gate failed)'
        res[m] = {'gate': gate, 'm1': gate and m1, 'm2': gate and m2, 'missing': False}

        p(f'  {m}: KF usable {pct(*skf)} ({skf[0]} of {skf[1]});'
          f' P1 {fdiff(p1)} ({len(steps1)} steps) {v1}; P2 {fdiff(p2)} ({len(steps2)} steps) {v2};'
          f' gate {"passed" if gate else "FAILED: " + "; ".join(why)}')

        r1a = sum(o28[(s, 'KF')] for s in steps1)
        r1b = sum(o26[(s, 'KE')] for s in steps1)
        r2a = sum(o26[(s, 'EL')] for s in steps2)
        r2b = sum(o28[(s, 'KF')] for s in steps2)
        fk = lambda x: ', '.join(f'{arm} {kind} {n}' for (arm, kind), n in sorted(x.items())) or 'none'  # noqa: E731
        cnt = lambda n: ', '.join(f'{k} {v}' for k, v in sorted(n.items()) if k != 'rows') or 'none'  # noqa: E731
        details.append(
            f'  {m}:\n'
            f'    28 (KF side): {rel(f28)} md5 {md5(f28)}; rows {n28["rows"]}; KF cells {skf[1]}, usable {skf[0]};'
            f' failures: {fk(x28)}; rows set aside: {cnt(n28)}\n'
            f'    26: {rel(f26)} md5 {md5(f26)}; rows {n26["rows"]}; cells KE {ske[1]} EL {sel[1]};'
            f' usable KE {ske[0]} ({pct(*ske)}) EL {sel[0]} ({pct(*sel)}); failures: {fk(x26)};'
            f' rows set aside: {cnt(n26)}\n'
            f'    P1 steps {len(steps1)}: KF {r1a} ({pct(r1a, len(steps1))}), KE {r1b} ({pct(r1b, len(steps1))});'
            f' P2 steps {len(steps2)}: EL {r2a} ({pct(r2a, len(steps2))}), KF {r2b} ({pct(r2b, len(steps2))});'
            f' steps in both P1 and P2 {len(set(steps1) & set(steps2))}\n'
            f'    other reading: KF usable share of the {PLANNED} planned {pct(skf[0], PLANNED)}'
            f' ({"at least 80%" if skf[0] / PLANNED >= GATE_USABLE else "UNDER 80%"})')
    p('')

    # ---- the reading
    through = [m for m in MODELS if res[m]['gate']]
    met1 = [m for m in through if res[m]['m1']]
    met2 = [m for m in through if res[m]['m2']]
    n1, n2 = len(met1), len(met2)
    p('2. THE READING FIXED IN THE REGISTRATION (across the models through the gate; this script\'s verdicts alone, before'
      ' the two scripts are compared)')
    p(f'  models through the gate: {len(through)} of {len(MODELS)}'
      + (f' ({", ".join(through)})' if through else ''))
    p(f'  n1 (P1 met) = {n1}' + (f' ({", ".join(met1)})' if met1 else '')
      + f'; n2 (P2 met) = {n2}' + (f' ({", ".join(met2)})' if met2 else ''))
    if len(through) < 5:
        p('  Fewer than 5 models through the gate: per-model verdicts only.')
    elif n1 >= 4 and n2 <= 1:
        p('  "The first place recovers the note" (n1 >= 4 and n2 <= 1).')
    elif n1 >= 4 and n2 >= 2:
        p('  "The place within the result matters, and the separate note adds more" (n1 >= 4 and n2 >= 2).')
    elif n1 <= 1:
        p('  "Not the place within the result" (n1 <= 1).')
    else:
        p('  "Mixed" (none of the other readings applies).')
    p('')

    p('3. DETAILS (counts behind each line)')
    for x in details:
        p(x)
    if extra_dirs:
        p(f'  other directories under {rel(ROOT26)} (not models of 26): {", ".join(extra_dirs)}')
    p('')

    p('4. JUDGMENT CALLS')
    p('  - The seven models: the registration names "the seven hosted models of 26" without listing them; taken from the'
      ' seven model directories under analysis/results/26/ and fixed in the script.')
    p('  - Rows: seed 1 only (the fork id\'s seed and the row\'s seed field must both be 1); a row belongs to step (task,'
      ' run, int(03\'s fork)) and to its record arm from the fork id; KF is read from 28\'s file only, KE and EL from'
      ' 26\'s file only (KH and any other arm are set aside and counted); rows whose step is not in the states file are'
      ' set aside; the first row of a (step, record arm) in file order counts, before the failure check; the runner arm'
      ' (A for KF and KE, EL for EL) is only checked and counted.')
    p('  - Usable: gates_c.failure falsy; outcome gates_c.any_true(state, next_call), one 0/1 per step and arm, scored on'
      ' the spans of analysis/fork_states_d/states.jsonl for every arm.')
    p('  - Gate, usable share: "28\'s replays" read as the KF rows present (first row per cell at seed 1); usable KF rows'
      ' over those rows; replays never run do not count. The share of the 322 planned is printed under DETAILS.'
      ' 26\'s KE and EL shares are printed, not gated.')
    p('  - Gate, floor: P1 and P2 each need at least 200 steps; a model failing either part gets no verdict on either'
      ' rule.')
    p('  - P1\'s steps need KF and KE usable, P2\'s need EL and KF usable; no other arm is required (unlike 27, the'
      ' registration names only the two arms of each rule).')
    p('  - "Interval above zero": its lower bound strictly above 0. diff_ci sorts the steps itself; one call per rule and'
      ' model, each with seed 0.')
    p('  - The reading: "fewer than 5 models through the gate" is checked first and overrides the other readings; then'
      ' the three named readings in the registration\'s order; "mixed" otherwise. n1 and n2 count only models through'
      ' the gate.')
    p('  - A model whose gate fails, or whose 28 or 26 file is missing, gets no verdict and does not count toward the'
      ' reading. The rule that a disagreement between the two scripts counts as "not detected" is not applied here.')
    p('  - The states md5 is checked against the one registered in 25 and printed; a mismatch is reported, not fatal.')

    text = '\n'.join(L) + '\n'
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stdout.buffer.flush()
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
