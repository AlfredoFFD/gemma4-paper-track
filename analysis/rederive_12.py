"""Independent re-derivation of the registered results of pre-registration 12 (a file without lines).

Written blind: from the pre-registration text, the raw per-replay rows and the states file only, without the
project's own analysis code or stored outputs for this experiment. Imports only fork_states.touches,
fork_states.valid_call and nodes.file_text.

Usage (from the repository root):
    py -I -X utf8 analysis/rederive_12.py <new_run_dir> <reference_run_dir> [--no-write]

Prints the report; unless --no-write, also writes the same text to analysis/results/rederive_12.txt (LF endings).
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fork_states import touches, valid_call  # noqa: E402
from nodes import file_text  # noqa: E402

STATES = HERE / 'fork_states_d' / 'states.jsonl'
OUT = HERE / 'results' / 'rederive_12.txt'

TOOLS = {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
         'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
SEEDS = (1, 2, 3)
REF_ARMS = ('H', 'EL', 'E')
NEW_ARM = 'EPATH'
ARMS = ('H', 'EPATH', 'EL', 'E')
N_BOOT = 2000
BOOT_SEED = 120012
MIN_COMPLETE = 200
P3_MIN_READS = 30
P3_MAX_SHARE = 0.05
FAILURE_KINDS = ('error', 'no call', 'unknown tool', 'malformed')


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def failure_kind(row):
    """None if the replay is usable, else the first failure kind that applies (in FAILURE_KINDS order)."""
    if row.get('error'):
        return 'error'
    call = row.get('next_call')
    if not call or not call.get('function_name'):
        return 'no call'
    if call.get('function_name') not in TOOLS:
        return 'unknown tool'
    if not valid_call(call):
        return 'malformed'
    return None


_LL = {}


def line_lengths(task, path):
    """Characters per line of a snapshot file (newline excluded), or None if the snapshot lacks the file."""
    key = (task, path)
    if key not in _LL:
        text = file_text(task, path)
        if text is None:
            COUNT['no_text'] += 1
            _LL[key] = None
        else:
            lines = text.split('\n')
            if text.endswith('\n'):
                lines = lines[:-1]
            _LL[key] = [len(x) for x in lines]
    return _LL[key]


def outcome1(call, state, use_lengths=True):
    spans = state['neighbor_spans']
    for n in state['unshown_true_neighbors']:
        sp = spans.get(n)
        if not sp:
            continue
        ll = line_lengths(state['task'], sp['path']) if use_lengths else None
        t = touches(call, sp, n, line_lengths=ll)
        if t and t != 'graph':
            return True
    return False


COUNT = {'prefixed': 0, 'no_text': 0, 'multi_start': 0}


def strip_path(p):
    if p.startswith(('/workspace/', 'workspace/', './')):
        COUNT['prefixed'] += 1
    changed = True
    while changed:
        changed = False
        for pre in ('/workspace/', 'workspace/', './'):
            if p.startswith(pre):
                p = p[len(pre):]
                changed = True
    return p


def outcome2(call, state):
    if call.get('function_name') != 'read_file':
        return False
    fp = (call.get('arguments') or {}).get('filepath')
    if not isinstance(fp, str):
        return False
    fp = strip_path(fp)
    spans = state['neighbor_spans']
    paths = {spans[n]['path'] for n in state['unshown_true_neighbors'] if spans.get(n)}
    return fp in paths


def norm_name(k):
    return ''.join(ch for ch in k if ch not in '"\'\\' and not ch.isspace())


def start_line(call):
    """The start line the model wrote, or None if absent or not an integer."""
    args = call.get('arguments') or {}
    vals = [v for k, v in args.items() if isinstance(k, str) and norm_name(k) == 'start_line']
    if not vals:
        return None
    if len(vals) > 1:
        COUNT['multi_start'] += 1
    v = vals[0]
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if s and (s.isdigit() or (s[0] in '+-' and s[1:].isdigit())):
            return int(s)
    return None


def pct(x):
    return f'{100 * x:.2f}'


def interval(vals):
    v = sorted(vals)
    lo = v[int(0.025 * len(v))]
    hi = v[int(0.975 * len(v)) - 1]
    return lo, hi


def make_resamples(units, seed):
    rng = random.Random(seed)
    k = len(units)
    return [[units[rng.randrange(k)] for _ in range(k)] for _ in range(N_BOOT)]


def main(argv):
    args = [a for a in argv if a != '--no-write']
    write = '--no-write' not in argv
    if len(args) != 2:
        sys.stderr.write(__doc__)
        return 2
    new_dir, ref_dir = Path(args[0]), Path(args[1])

    states = {(s['task'], s['run'], s['fork']): s for s in load_jsonl(STATES)}
    new_rows = load_jsonl(new_dir / 'results.jsonl')
    ref_rows_all = load_jsonl(ref_dir / 'results.jsonl')

    rows = {a: [] for a in ARMS}
    other_new = 0
    for r in new_rows:
        if r.get('arm') == NEW_ARM and r.get('seed') in SEEDS:
            rows[NEW_ARM].append(r)
        else:
            other_new += 1
    for r in ref_rows_all:
        if r.get('arm') in REF_ARMS and r.get('seed') in SEEDS:
            rows[r['arm']].append(r)

    out = []
    w = out.append
    w('Re-derivation of pre-registration 12 (a file without lines), written blind from raw outputs.')
    w(f'New run: {new_dir.as_posix()}/results.jsonl ({len(new_rows)} rows; {other_new} rows not {NEW_ARM} seeds 1-3, ignored).')
    w(f'Reference run: {ref_dir.as_posix()}/results.jsonl ({len(ref_rows_all)} rows; arms H, EL, E seeds 1-3 used).')
    w(f'States: analysis/fork_states_d/states.jsonl ({len(states)} states).')
    w('')

    # ---- 1. interface failures, usable replays, complete states
    usable = {a: {} for a in ARMS}  # arm -> (key, seed) -> row
    unknown_keys = 0
    dup = 0
    w('1. Interface failures and usable replays (rows of seeds 1-3)')
    w(f'   {"arm":<6}{"rows":>6}{"error":>7}{"no call":>9}{"unknown tool":>14}{"malformed":>11}{"usable":>8}')
    for a in ARMS:
        kinds = {k: 0 for k in FAILURE_KINDS}
        for r in rows[a]:
            key = (r['task'], r['run'], r['fork'])
            if key not in states:
                unknown_keys += 1
                continue
            fk = failure_kind(r)
            if fk:
                kinds[fk] += 1
                continue
            if (key, r['seed']) in usable[a]:
                dup += 1
                continue
            usable[a][(key, r['seed'])] = r
        w(f'   {a:<6}{len(rows[a]):>6}{kinds["error"]:>7}{kinds["no call"]:>9}{kinds["unknown tool"]:>14}'
          f'{kinds["malformed"]:>11}{len(usable[a]):>8}')
    if unknown_keys or dup:
        w(f'   rows whose state is not in the states file: {unknown_keys}; duplicate (state, arm, seed) rows dropped: {dup}')

    def full(a, key):
        return all((key, s) in usable[a] for s in SEEDS)

    complete = sorted(k for k in states if full('H', k) and full('EL', k) and full(NEW_ARM, k))
    complete_e = [k for k in complete if full('E', k)]
    n_tasks = len({k[0] for k in complete})
    w(f'   complete states (H, EL and EPATH usable for seeds 1-3): {len(complete)} of {len(states)}, in {n_tasks} tasks')
    w(f'   of these, E usable for seeds 1-3: {len(complete_e)}')
    w(f'   rules apply (at least {MIN_COMPLETE} complete states): {"yes" if len(complete) >= MIN_COMPLETE else "NO"}')
    w('')

    # ---- per-state hit counts
    hits1 = {a: {} for a in ARMS}
    hits2 = {a: {} for a in ARMS}
    nolen_diff = 0
    for a in ARMS:
        keys = complete_e if a == 'E' else complete
        for k in keys:
            h1 = h2 = 0
            for s in SEEDS:
                call = usable[a][(k, s)]['next_call']
                o1 = outcome1(call, states[k])
                if o1 != outcome1(call, states[k], use_lengths=False):
                    nolen_diff += 1
                h1 += o1
                h2 += outcome2(call, states[k])
            hits1[a][k] = h1
            hits2[a][k] = h2

    # bootstrap resamples: states, and tasks (each task brings its states)
    def boot_sets(keys, seed):
        st_res = make_resamples(list(keys), seed)
        by_task = {}
        for k in keys:
            by_task.setdefault(k[0], []).append(k)
        tasks = sorted(by_task)
        tk_res = [[k for t in res for k in by_task[t]] for res in make_resamples(tasks, seed + 1)]
        return st_res, tk_res

    boots = {'all': boot_sets(complete, BOOT_SEED), 'E': boot_sets(complete_e, BOOT_SEED + 10)}

    def rate_ci(h, keys, which, cluster):
        res = boots[which][0 if cluster == 'state' else 1]
        vals = [sum(h[k] for k in r) / (3 * len(r)) for r in res]
        return interval(vals)

    def diff_ci(ha, hb, which, cluster):
        res = boots[which][0 if cluster == 'state' else 1]
        vals = [(sum(ha[k] for k in r) - sum(hb[k] for k in r)) / (3 * len(r)) for r in res]
        return interval(vals)

    # ---- 2. rates
    w('2. Rates on the complete states, 95% bootstrap interval clustered by state (2,000 resamples, percentile)')
    for label, hits in (('Outcome 1, reads a listed neighbor', hits1), ('Outcome 2, opens a listed neighbor\'s file', hits2)):
        w(f'   {label}:')
        for a in ARMS:
            which = 'E' if a == 'E' else 'all'
            keys = complete_e if a == 'E' else complete
            n = 3 * len(keys)
            x = sum(hits[a][k] for k in keys)
            lo, hi = rate_ci(hits[a], keys, which, 'state')
            note = f'  (on the {len(keys)} complete states where E is usable for seeds 1-3)' if a == 'E' else ''
            w(f'     {a:<6}{x:>4} / {n:<5} = {pct(x / n):>6}%  [{pct(lo)}, {pct(hi)}]{note}')
    w('')

    def diff_line(name, ha, hb, keys):
        n = 3 * len(keys)
        xa, xb = sum(ha[k] for k in keys), sum(hb[k] for k in keys)
        d = (xa - xb) / n
        s_lo, s_hi = diff_ci(ha, hb, 'all', 'state')
        t_lo, t_hi = diff_ci(ha, hb, 'all', 'task')
        w(f'   {name}: {xa}/{n} - {xb}/{n} = {100 * d:+.2f} points; by state [{100 * s_lo:+.2f}, {100 * s_hi:+.2f}]; '
          f'by task [{100 * t_lo:+.2f}, {100 * t_hi:+.2f}]')
        return s_lo

    # ---- 3. rules
    w('3. Registered rules (verdict from the state-clustered interval; task-clustered interval beside it)')
    applies = len(complete) >= MIN_COMPLETE
    lo1 = diff_line('P1, EL minus EPATH on outcome 1', hits1['EL'], hits1[NEW_ARM], complete)
    v1 = 'The line range, not the path, gets the agent to the code'
    if not applies:
        w('      verdict: rules do not apply (fewer than 200 complete states)')
    elif lo1 > 0:
        w(f'      verdict: met (lower bound above 0): "{v1}".')
    else:
        w(f'      verdict: not met (lower bound not above 0): "{v1}" is not supported.')
    lo2 = diff_line('P2, EPATH minus H on outcome 2', hits2[NEW_ARM], hits2['H'], complete)
    w(f'      exact state-clustered lower bound: {lo2!r} (a difference of '
      f'{round(lo2 * 3 * len(complete))} hits in that resample)')
    alt = []
    for i in range(20):
        res = make_resamples(list(complete), BOOT_SEED + 1000 + i)
        vals = [(sum(hits2[NEW_ARM][k] for k in r) - sum(hits2['H'][k] for k in r)) / (3 * len(r)) for r in res]
        alt.append(interval(vals)[0])
    w(f'      sensitivity, not the verdict: over 20 other bootstrap seeds the state-clustered lower bound is above 0 '
      f'in {sum(x > 0 for x in alt)}, exactly 0 in {sum(x == 0 for x in alt)}, below 0 in {sum(x < 0 for x in alt)} '
      f'(min {100 * min(alt):+.2f}, max {100 * max(alt):+.2f})')
    v2 = 'A path alone gets the agent to the file'
    if not applies:
        w('      verdict: rules do not apply (fewer than 200 complete states)')
    elif lo2 > 0:
        w(f'      verdict: met (lower bound above 0): "{v2}".')
    else:
        w(f'      verdict: not met (lower bound not above 0): "{v2}" is not supported.')

    reads = past = absent = 0
    hist = {}
    for k in complete:
        for s in SEEDS:
            call = usable[NEW_ARM][(k, s)]['next_call']
            if outcome2(call, states[k]):
                reads += 1
                sl = start_line(call)
                if sl is None:
                    absent += 1
                    bucket = 'absent or not an integer'
                elif sl > 1:
                    past += 1
                    bucket = 'past line 1'
                else:
                    bucket = 'at line 1 or below'
                hist[bucket] = hist.get(bucket, 0) + 1
    share = past / reads if reads else 0.0
    w(f'   P3, EPATH outcome-2 reads on the complete states: {reads}; asking past line 1: {past} '
      f'({pct(share)}% of {reads}); start line absent or not an integer: {absent}')
    v3 = 'without a line number the file is read from the top'
    if not applies:
        w('      verdict: rules do not apply (fewer than 200 complete states)')
    elif reads < P3_MIN_READS:
        w(f'      verdict: too few reads to test ({reads} < {P3_MIN_READS})')
    elif share <= P3_MAX_SHARE:
        w(f'      verdict: met ({past}/{reads} = {pct(share)}% <= 5%): "{v3}".')
    else:
        w(f'      verdict: not met ({past}/{reads} = {pct(share)}% > 5%): "{v3}" is not supported.')
    w('')

    # ---- 4. unregistered contrasts
    w('4. Reported without a rule')
    diff_line('EPATH minus H on outcome 1', hits1[NEW_ARM], hits1['H'], complete)
    diff_line('EL minus EPATH on outcome 2', hits2['EL'], hits2[NEW_ARM], complete)
    w('')

    # ---- 5. judgment calls
    w('5. Judgment calls where the pre-registration left room')
    calls = [
        'Interface-failure kinds are assigned in the order error, no call, unknown tool, malformed (valid_call false); '
        'a replay counts once, under the first kind that applies.',
        'Rates pool replays (states x 3 seeds); the clustered bootstrap resamples whole states (or whole tasks, each '
        'bringing all its complete states) with replacement and divides hits by replays in the resample. One fixed '
        'set of 2,000 state resamples and one of task resamples (Python random, seeds 120012/120013; 120022/120023 '
        'for the E subset) is shared by every statistic on the same set of states. Percentile interval: the 51st and '
        '1,950th of the 2,000 sorted values.',
        'Differences are paired: both arms on the same complete states and seeds.',
        'Outcome 1 calls touches with the line lengths of the target file from nodes.file_text (text split on LF, '
        'newline excluded, a final empty piece after a trailing newline dropped); if the snapshot lacked the file, '
        f'touches runs without lengths (target files missing from the snapshot here: {COUNT["no_text"]}). Calling '
        f'touches without line lengths changes outcome 1 in {nolen_diff} replay(s) across the four arms on the '
        f'complete states.',
        'Outcome 2 strips the prefixes /workspace/, workspace/ and ./ repeatedly until none leads; a non-string '
        f'filepath never matches. read_file paths that carried such a prefix: {COUNT["prefixed"]}.',
        'Outcome 3: an argument whose name normalizes to start_line; ints (not bools), integral floats and strings '
        'of digits with an optional sign count as integers; anything else (e.g. a string with a stray quote) counts '
        'as absent, and an absent start line is not past line 1. If several names normalize to start_line the first '
        f'is used (calls where that happened: {COUNT["multi_start"]}).',
        'The P2 sensitivity line (20 other bootstrap seeds) is added by this script, written after the first run '
        'showed a lower bound at 0, and is not part of the registered rule.',
        'P3 counts replays on the complete states (each next call is a first read after the fork); its 5% bar is '
        'applied to the point share, with no interval.',
        'Verdicts of P1 and P2 use the state-clustered interval, the registered one; the task-clustered interval is '
        'reported beside it only.',
        'Arm E is restricted to the complete states where E is usable for all three seeds, so its rates are on a '
        'subset and E is not differenced against the other arms.',
    ]
    for i, c in enumerate(calls, 1):
        w(f'   {i}. {c}')

    text = '\n'.join(out) + '\n'
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stdout.buffer.flush()
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
