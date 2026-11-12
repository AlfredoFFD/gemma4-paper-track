"""Independent re-derivation of pre-registration 27 (one line in the system prompt).

Written blind: from the frozen text of prereg/27-one-line-in-the-system-prompt.md (with the outcome it takes over from
prereg/25-the-place-of-the-list.md) alone, without sight of the registered analysis of 27 or of any row of 27. It reads
the replay rows of 27 (analysis/results/27/<model>/forks/results.jsonl), those of 26, the run without the line
(analysis/results/26/<model>/forks/results.jsonl), and the 407 paused steps of 03 (analysis/fork_states_d/states.jsonl,
whose spans every arm is scored on). Directory names replace "/" in a model's name with "__".

It imports, unchanged: the scorer gates_c.any_true ("reads a neighbor's code", the registered outcome of 25), the
interface-failure rule gates_c.failure, gates_c.load_rows / load_states, and the paired bootstrap analyze_forks.diff_ci
(2,000 resamples, seed 0), each step entering with its one outcome as a one-element list.

Rules, per model: L1 = KE with the line (27) minus KE without it (26), on the steps whose KE replay is usable in both
runs; L2 = EL minus KE, both in 27, on the steps with all three arms usable in 27. A rule is met if the 95% interval
lies above zero. Gate: at least 80% of 27's replays usable in each arm, and at least 200 steps entering L1 and L2.
Then the reading fixed in the registration, across the models through the gate.

Usage: py -I -X utf8 analysis/rederive_27.py [--root27 <dir>] [--no-write]
Without options it prints the report and writes the same text to analysis/results/rederive_27.txt (LF).
--root27 reads the rows "with the line" from another root (e.g. analysis/results/26 for a check where L1 must be
exactly 0) and never writes the stored file; --no-write prints only.
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

ROOT27 = HERE / 'results' / '27'
ROOT26 = HERE / 'results' / '26'
STATES = HERE / 'fork_states_d' / 'states.jsonl'
STATES_MD5 = 'd3105df0dc4aa43d7bb0afbdd6123b44'
OUT = HERE / 'results' / 'rederive_27.txt'

# The seven hosted models of 26 (the registration says "the seven hosted models" of 26 without listing them; these are
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
ARMS = ('KH', 'KE', 'EL')
RUNNER_ARM = {'KH': 'A', 'KE': 'A', 'EL': 'EL'}
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


# ---------------------------------------------------------------- one run of one model

def read_run(path, states):
    """Cells {(step, arm): first row at seed 1}, usable outcomes {(step, arm): 0/1}, and counts."""
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
        if arm not in ARMS:
            c['other_arm'] += 1
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
        k = (step, arm)
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


def shares(cells, out):
    s = {}
    for a in ARMS:
        n = sum(1 for k in cells if k[1] == a)
        u = sum(1 for k in out if k[1] == a)
        s[a] = (u, n)
    return s


def pct(u, n):
    return f'{100 * u / n:.2f}%' if n else 'n/a'


# ---------------------------------------------------------------- main

def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--root27', default=None)
    ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args(argv)
    root27 = Path(a.root27) if a.root27 else ROOT27
    write = not a.no_write and a.root27 is None

    p('Re-derivation of pre-registration 27, one line in the system prompt (independent script, written blind from the')
    p('frozen registration text; imports gates_c.any_true / failure / load_rows / load_states and analyze_forks.diff_ci')
    p('unchanged)')
    h = md5(STATES)
    states = load_states(STATES)
    p(f'states analysis/fork_states_d/states.jsonl md5 {h} ({"as registered in 25" if h == STATES_MD5 else "DIFFERS from 25"});'
      f' {len(states)} paused steps')
    p(f'rows with the line: {rel(root27)}/<model>/forks/results.jsonl; without it (26): {rel(ROOT26)}/<model>/forks/results.jsonl'
      + ('' if a.root27 is None else '   [CHECK RUN: --root27 given, nothing written]'))
    p('per model, at seed 1: usable share per arm in 27 (and KE in 26); L1 = KE(27) - KE(26) on the steps with KE usable in'
      ' both; L2 = EL(27) - KE(27) on the steps with all three arms usable in 27; points, 95% bootstrap by step, 2,000'
      ' resamples, seed 0; met if the lower bound is above 0')
    p('')

    res = {}
    details = []
    extra_dirs = sorted(d.name for d in ROOT26.iterdir() if d.is_dir() and d.name not in {m.replace('/', '__') for m in MODELS}) \
        if ROOT26.is_dir() else []
    p('1. PER MODEL')
    for m in MODELS:
        d = m.replace('/', '__')
        f27 = root27 / d / 'forks' / 'results.jsonl'
        f26 = ROOT26 / d / 'forks' / 'results.jsonl'
        missing = [x for x in (f27, f26) if not x.exists()]
        if missing:
            p(f'  {m}: results file missing ({", ".join(rel(x) for x in missing)}); not through the gate')
            res[m] = {'gate': False, 'missing': True}
            continue
        c27, o27, x27, n27 = read_run(f27, states)
        c26, o26, x26, n26 = read_run(f26, states)
        s27, s26 = shares(c27, o27), shares(c26, o26)

        steps1 = sorted({k[0] for k in o27 if k[1] == 'KE'} & {k[0] for k in o26 if k[1] == 'KE'})
        steps2 = sorted({k[0] for k in o27 if k[1] == 'KE'} & {k[0] for k in o27 if k[1] == 'EL'}
                        & {k[0] for k in o27 if k[1] == 'KH'})
        l1 = diff_ci({s: [o27[(s, 'KE')]] for s in steps1}, {s: [o26[(s, 'KE')]] for s in steps1}) if steps1 else (None,) * 3
        l2 = diff_ci({s: [o27[(s, 'EL')]] for s in steps2}, {s: [o27[(s, 'KE')]] for s in steps2}) if steps2 else (None,) * 3

        usable_ok = all(s27[x][1] > 0 and s27[x][0] / s27[x][1] >= GATE_USABLE for x in ARMS)
        floor_ok = len(steps1) >= FLOOR and len(steps2) >= FLOOR
        gate = usable_ok and floor_ok
        why = []
        if not usable_ok:
            why.append('usable share under 80% in an arm')
        if not floor_ok:
            why.append('fewer than 200 steps in L1 or L2')
        m1, m2 = above_zero(l1), above_zero(l2)
        if gate:
            v1 = 'the line raises uptake inside the view' if m1 else 'not detected'
            v2 = 'a gap remains with the line' if m2 else 'not detected'
        else:
            v1 = v2 = 'no verdict (gate failed)'
        res[m] = {'gate': gate, 'm1': gate and m1, 'm2': gate and m2, 'missing': False}

        p(f'  {m}: usable 27 KH {pct(*s27["KH"])} KE {pct(*s27["KE"])} EL {pct(*s27["EL"])}, 26 KE {pct(*s26["KE"])};'
          f' L1 {fdiff(l1)} ({len(steps1)} steps) {v1}; L2 {fdiff(l2)} ({len(steps2)} steps) {v2};'
          f' gate {"passed" if gate else "FAILED: " + "; ".join(why)}')

        r1a = sum(o27[(s, 'KE')] for s in steps1)
        r1b = sum(o26[(s, 'KE')] for s in steps1)
        r2a = sum(o27[(s, 'EL')] for s in steps2)
        r2b = sum(o27[(s, 'KE')] for s in steps2)
        inter = len(set(steps1) & set(steps2))
        fk = lambda x: ', '.join(f'{arm} {kind} {n}' for (arm, kind), n in sorted(x.items())) or 'none'  # noqa: E731
        cnt = lambda n: ', '.join(f'{k} {v}' for k, v in sorted(n.items()) if k != 'rows') or 'none'  # noqa: E731
        details.append(
            f'  {m}:\n'
            f'    27: {rel(f27)} md5 {md5(f27)}; rows {n27["rows"]}; cells KH {s27["KH"][1]} KE {s27["KE"][1]}'
            f' EL {s27["EL"][1]}; usable KH {s27["KH"][0]} KE {s27["KE"][0]} EL {s27["EL"][0]}; failures: {fk(x27)};'
            f' rows set aside: {cnt(n27)}\n'
            f'    26: {rel(f26)} md5 {md5(f26)}; rows {n26["rows"]}; cells KH {s26["KH"][1]} KE {s26["KE"][1]}'
            f' EL {s26["EL"][1]}; usable KH {s26["KH"][0]} KE {s26["KE"][0]} EL {s26["EL"][0]}; failures: {fk(x26)};'
            f' rows set aside: {cnt(n26)}\n'
            f'    L1 steps {len(steps1)}: KE(27) {r1a} ({pct(r1a, len(steps1))}), KE(26) {r1b} ({pct(r1b, len(steps1))});'
            f' L2 steps {len(steps2)}: EL(27) {r2a} ({pct(r2a, len(steps2))}), KE(27) {r2b} ({pct(r2b, len(steps2))});'
            f' steps in both L1 and L2 {inter}\n'
            f'    other readings: usable share of the {PLANNED} planned per arm in 27: '
            + ', '.join(f'{x} {pct(s27[x][0], PLANNED)}' for x in ARMS)
            + f' ({"all at least 80%" if all(s27[x][0] / PLANNED >= GATE_USABLE for x in ARMS) else "NOT all at least 80%"});'
            f' floor on the steps in both L1 and L2: {"met" if inter >= FLOOR else "NOT met"}')
    p('')

    # ---- the reading
    through = [m for m in MODELS if res[m]['gate']]
    met1 = [m for m in through if res[m]['m1']]
    p('2. THE READING FIXED IN THE REGISTRATION (across the models through the gate; this script\'s verdicts alone, before'
      ' the two scripts are compared)')
    p(f'  models through the gate: {len(through)} of {len(MODELS)}; L1 met on {len(met1)}'
      + (f' ({", ".join(met1)})' if met1 else ''))
    if len(through) < 5:
        p('  Fewer than 5 models through the gate: per-model verdicts only.')
    elif len(met1) >= 5:
        p('  "One line lifts uptake inside the view" (L1 met on at least 5 models).')
    elif len(met1) >= 2:
        p('  "On some models" (L1 met on 2 to 4).')
    else:
        p('  "Not shown" (L1 met on 0 or 1).')
    beside = [m for m in through if res[m]['m1'] and not res[m]['m2']]
    p('  Beside it, per model, L1 met and L2 not detected ("with the line, the place no longer detectably matters"): '
      + (', '.join(beside) if beside else 'none'))
    p('')

    p('3. DETAILS (counts behind each line)')
    for x in details:
        p(x)
    if extra_dirs:
        p(f'  other directories under {rel(ROOT26)} (not models of 27): {", ".join(extra_dirs)}')
    p('')

    p('4. JUDGMENT CALLS')
    p('  - The seven models: the registration names "the seven hosted models" of 26 without listing them; taken from the'
      ' seven model directories under analysis/results/26/ and fixed in the script.')
    p('  - Rows: seed 1 only (the fork id\'s seed and the row\'s seed field must both be 1); a row belongs to step (task,'
      ' run, int(03\'s fork)) and record arm KH, KE or EL from its fork id; rows whose step is not in the states file are'
      ' set aside; the first row of a (step, record arm) in file order counts, before the failure check; the runner arm'
      ' (A for KH and KE, EL for EL) is only checked and counted.')
    p('  - Usable: gates_c.failure falsy; outcome gates_c.any_true(state, next_call), one 0/1 per step and arm.')
    p('  - Gate, usable share: usable rows over the rows present (first row per cell) in each of KH, KE and EL of 27;'
      ' replays never run do not count. The share of the 322 planned is printed under DETAILS. 26\'s shares are printed,'
      ' not gated.')
    p('  - Gate, floor: L1 and L2 each need at least 200 steps; the floor on the steps entering both is printed under'
      ' DETAILS.')
    p('  - L2\'s steps need all three arms usable in 27, KH included, as registered, though KH is not in the contrast.')
    p('  - "Interval above zero": its lower bound strictly above 0. diff_ci sorts the steps itself; one call per rule and'
      ' model, each with seed 0.')
    p('  - A model whose gate fails, or whose 27 or 26 file is missing, gets no verdict and does not count toward the'
      ' reading. The rule that a disagreement between the two scripts counts as "not detected" is not applied here.')
    p('  - The "beside it" line lists only models through the gate.')

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
