"""Independent re-derivation of the registered results of pre-registration 13 (the address written as a search hit).

Written blind to the project's own analysis of this experiment: it reads only the raw replay rows of the new run
(arm EG) and of the reference run of pre-registration 04 (arms H, EL, E), the 407 fork states, and imports the frozen
scorer (fork_states.touches), the frozen malformed-call rule (fork_states.valid_call) and nodes.file_text.

Usage: py -I -X utf8 analysis/rederive_13.py <new_run_dir> <reference_run_dir> [--no-write]
"""
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'analysis'))

from fork_states import touches, valid_call  # noqa: E402  (frozen scorer and malformed-call rule)
from nodes import file_text  # noqa: E402

STATES = os.path.join(ROOT, 'analysis', 'fork_states_d', 'states.jsonl')
OUT = os.path.join(ROOT, 'analysis', 'results', 'rederive_13.txt')
TOOLS = {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
         'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
REF_ARMS = ('H', 'EL', 'E')
ARMS = ('H', 'EL', 'E', 'EG')
SEEDS = (1, 2, 3)
B = 2000
OUT_OF_SIGHT = 150
MIN_COMPLETE = 200
MIN_READS = 30
INT_RE = re.compile(r'^[+-]?\d+$')


# ---------------------------------------------------------------- loading

def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def skey(r):
    return (r['task'], r['run'], r['fork'])


# ---------------------------------------------------------------- per-replay classification

def failure_kind(row):
    """None if usable, else the first interface failure that applies: error, no call, unknown tool, malformed."""
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


def strip_prefix(p):
    """Remove leading '/workspace/', 'workspace/' or './' (repeatedly, until none is left)."""
    changed = True
    while changed:
        changed = False
        for pre in ('/workspace/', 'workspace/', './'):
            if p.startswith(pre):
                p = p[len(pre):]
                changed = True
    return p


def clean_key(k):
    return re.sub(r'[\s"\'\\]', '', str(k))


def as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and INT_RE.match(v.strip()):
        return int(v.strip())
    return None


def written_start(args):
    """The start line the model wrote: the first argument whose name, cleaned, is start_line; None if absent or
    not an integer."""
    for k, v in args.items():
        if clean_key(k) == 'start_line':
            return as_int(v), k != 'start_line', v
    return None, False, None


_LL = {}


def line_lengths(task, path):
    if (task, path) not in _LL:
        txt = file_text(task, path)
        _LL[(task, path)] = None if txt is None else [len(x) for x in txt.splitlines()]
    return _LL[(task, path)]


def score(row, state):
    """Outcome flags of one usable replay."""
    call = row['next_call']
    spans = state['neighbor_spans']
    targets = [n for n in state['unshown_true_neighbors'] if spans.get(n)]
    o1 = False
    for n in targets:
        sp = spans[n]
        t = touches(call, sp, n, line_lengths=line_lengths(state['task'], sp['path']))
        if t and t != 'graph':
            o1 = True
            break
    o2 = o3 = False
    oos = None
    mangled_key = False
    start = raw = None
    if call['function_name'] == 'read_file':
        fp = strip_prefix(call['arguments']['filepath'])
        in_file = [spans[n]['start'] for n in targets if spans[n]['path'] == fp]
        if in_file:
            o2 = True
            start, mangled_key, raw = written_start(call['arguments'])
            o3 = start is not None and start > 1
            oos = min(in_file) > OUT_OF_SIGHT
    return {'o1': o1, 'o2': o2, 'o3': o3, 'oos': oos, 'start': start, 'raw': raw, 'mangled_key': mangled_key}


# ---------------------------------------------------------------- bootstrap

def percentile(sorted_vals, q):
    n = len(sorted_vals)
    if n == 0:
        return float('nan')
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def boot(clusters, stat, seed):
    """95% percentile interval of stat(list of clusters) over B resamples of the clusters with replacement.
    Resamples where stat is undefined (None) are dropped; their number is returned."""
    rng = random.Random(seed)
    vals, dropped = [], 0
    n = len(clusters)
    for _ in range(B):
        sample = [clusters[rng.randrange(n)] for _ in range(n)]
        v = stat(sample)
        if v is None:
            dropped += 1
        else:
            vals.append(v)
    vals.sort()
    return percentile(vals, 0.025), percentile(vals, 0.975), dropped


def ratio(sample, num, den):
    a = sum(c[num] for c in sample)
    b = sum(c[den] for c in sample)
    return None if b == 0 else a / b


def pct(x):
    return f'{100 * x:.1f}'


def fmt_ci(ci):
    lo, hi, dropped = ci
    s = f'[{pct(lo)}, {pct(hi)}]'
    if dropped:
        s += f' ({dropped} resamples undefined, dropped)'
    return s


def verdict(ci, more, less):
    lo, hi, _ = ci
    if lo > 0:
        return more
    if hi < 0:
        return less
    return 'no detectable difference'


# ---------------------------------------------------------------- main

def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    no_write = '--no-write' in argv
    if len(args) != 2:
        sys.exit(__doc__)
    new_dir, ref_dir = args
    states = {skey(s): s for s in load_jsonl(STATES)}
    new_rows = load_jsonl(os.path.join(new_dir, 'results.jsonl'))
    ref_rows = load_jsonl(os.path.join(ref_dir, 'results.jsonl'))
    rows = [r for r in new_rows if r.get('arm') == 'EG' and r.get('seed') in SEEDS]
    rows += [r for r in ref_rows if r.get('arm') in REF_ARMS and r.get('seed') in SEEDS]
    lines = []
    p = lines.append

    p('Re-derivation of pre-registration 13 (the address written as a search hit), blind to the project analysis')
    def rel(d):
        return os.path.relpath(os.path.abspath(d), ROOT).replace(os.sep, '/')

    p(f'Inputs: new run {rel(new_dir)}/results.jsonl ({len(new_rows)} rows, EG seeds 1 to 3 used), '
      f'reference run {rel(ref_dir)}/results.jsonl ({len(ref_rows)} rows, H, EL and E seeds 1 to 3 used), '
      f'{len(states)} states')
    p('')

    # ---- 1. interface failures and usable replays
    rec = {}  # (state key, arm, seed) -> outcome dict, usable only
    dup = Counter()
    fails = {a: Counter() for a in ARMS}
    nrows = Counter()
    unknown_state = Counter()
    for r in rows:
        k = (skey(r), r['arm'], r['seed'])
        dup[k] += 1
        nrows[r['arm']] += 1
        if skey(r) not in states:
            unknown_state[r['arm']] += 1
            continue
        kind = failure_kind(r)
        if kind:
            fails[r['arm']][kind] += 1
            continue
        rec[k] = score(r, states[skey(r)])
    dups = sum(1 for v in dup.values() if v > 1)

    p('1. Rows, interface failures, usable replays (seeds 1 to 3)')
    for a in ARMS:
        f = fails[a]
        usable = sum(1 for k in rec if k[1] == a)
        nf = sum(f.values())
        flag = '  UNRELIABLE (>20% interface failures)' if nrows[a] and nf / nrows[a] > 0.20 else ''
        p(f'   {a:>2}: rows {nrows[a]}; failures {nf} (error {f["error"]}, no call {f["no call"]}, '
          f'unknown tool {f["unknown tool"]}, malformed {f["malformed"]}); usable {usable}{flag}')
    if dups or sum(unknown_state.values()):
        p(f'   duplicate (state, arm, seed) rows: {dups}; rows whose state is not in the states file: '
          f'{dict(unknown_state)}')

    def full(key, arm):
        return all((key, arm, s) in rec for s in SEEDS)

    complete = sorted(k for k in states if full(k, 'E') and full(k, 'EG'))
    tasks = Counter(k[0] for k in complete)
    p(f'   complete states (E and EG usable for seeds 1 to 3): {len(complete)} of {len(states)}, '
      f'in {len(tasks)} tasks (of {len({k[0] for k in states})})')
    lost = Counter(k[0] for k in states if k not in set(complete))
    if lost:
        p(f'   states not complete, by task: ' + ', '.join(f'{t} {n}' for t, n in sorted(lost.items())))
    p('   tasks of the complete states (states each): ' + ', '.join(f'{t} {n}' for t, n in sorted(tasks.items())))
    sub = {a: [k for k in complete if full(k, a)] for a in ARMS}
    p('   complete states where the arm is usable for all three seeds: '
      + ', '.join(f'{a} {len(sub[a])}' for a in ARMS))
    p('')

    # ---- per-state aggregates
    def agg(key, arm):
        c = Counter()
        for s in SEEDS:
            o = rec[(key, arm, s)]
            c['n'] += 1
            c['o1'] += o['o1']
            c['o2'] += o['o2']
            c['o3'] += o['o3']
            if o['o2'] and o['oos']:
                c['oos'] += 1
                c['oos3'] += o['o3']
        return c

    def clusters_by_state(keys, arms):
        out = []
        for k in keys:
            c = Counter({(a, f): v for a in arms for f, v in agg(k, a).items()})
            c['task'] = k[0]
            out.append(c)
        return out

    def by_task(cl):
        g = defaultdict(Counter)
        for c in cl:
            for f, v in c.items():
                if f != 'task':
                    g[c['task']][f] += v
        return [g[t] for t in sorted(g)]

    seed_base = 13013

    # ---- 2. rates per arm
    p('2. Rates on the complete states (replays pooled over seeds; 95% bootstrap by state, 2,000 resamples)')
    p('   outcome 1 = reads a listed neighbor; outcome 2 = opens a listed neighbor\'s file')
    for i, a in enumerate(ARMS):
        cl = clusters_by_state(sub[a], [a])
        tot = Counter()
        for c in cl:
            for f, v in c.items():
                if f != 'task':
                    tot[f] += v
        n = tot[(a, 'n')]
        r1 = boot(cl, lambda s, a=a: ratio(s, (a, 'o1'), (a, 'n')), seed_base + 10 * i + 1)
        r2 = boot(cl, lambda s, a=a: ratio(s, (a, 'o2'), (a, 'n')), seed_base + 10 * i + 2)
        p(f'   {a:>2} ({len(sub[a])} states, {n} replays): outcome 1 {pct(tot[(a, "o1")] / n)}% '
          f'({tot[(a, "o1")]}/{n}) {fmt_ci(r1)}; outcome 2 {pct(tot[(a, "o2")] / n)}% '
          f'({tot[(a, "o2")]}/{n}) {fmt_ci(r2)}')
    p('')

    def diff_stat(num, den, a1, a2):
        def f(s):
            x = ratio(s, (a1, num), (a1, den))
            y = ratio(s, (a2, num), (a2, den))
            return None if x is None or y is None else x - y
        return f

    def diff_line(keys, a1, a2, num, den, seed):
        cl = clusters_by_state(keys, [a1, a2])
        tot = Counter()
        for c in cl:
            for f, v in c.items():
                if f != 'task':
                    tot[f] += v
        x = tot[(a1, num)] / tot[(a1, den)] if tot[(a1, den)] else None
        y = tot[(a2, num)] / tot[(a2, den)] if tot[(a2, den)] else None
        d = None if x is None or y is None else x - y
        ci_s = boot(cl, diff_stat(num, den, a1, a2), seed)
        ci_t = boot(by_task(cl), diff_stat(num, den, a1, a2), seed + 5)
        return d, ci_s, ci_t, tot

    enough = len(complete) >= MIN_COMPLETE
    p(f'Rules apply if at least {MIN_COMPLETE} states are complete: {"yes" if enough else "NO"} ({len(complete)})')
    p('')

    # ---- 3. X1
    d, cs, ct, tot = diff_line(complete, 'EG', 'E', 'o1', 'n', seed_base + 101)
    p('3. X1 = EG minus E on outcome 1 (reads a listed neighbor)')
    p(f'   EG {tot[("EG", "o1")]}/{tot[("EG", "n")]}, E {tot[("E", "o1")]}/{tot[("E", "n")]}; '
      f'difference {pct(d)} points, 95% by state {fmt_ci(cs)}, by task {fmt_ci(ct)}')
    v1 = verdict(cs, 'Written as a search hit, the address is followed more', 'followed less') if enough \
        else 'rule does not apply (fewer than 200 complete states)'
    p(f'   verdict (by state): {v1}')
    p('')

    # ---- 4. X2
    d, cs, ct, tot = diff_line(complete, 'EG', 'E', 'o3', 'o2', seed_base + 201)
    p('4. X2 = EG minus E on outcome 3 (among outcome-2 reads, the start line written is past line 1)')
    for a in ('EG', 'E'):
        p(f'   {a:>2}: outcome-2 reads {tot[(a, "o2")]}, past line 1 {tot[(a, "o3")]}'
          + (f' ({pct(tot[(a, "o3")] / tot[(a, "o2")])}%)' if tot[(a, 'o2')] else ''))
    few = tot[('EG', 'o2')] < MIN_READS or tot[('E', 'o2')] < MIN_READS
    p(f'   difference of shares {pct(d) if d is not None else "n/a"} points, 95% by state {fmt_ci(cs)}, '
      f'by task {fmt_ci(ct)}')
    if not enough:
        v2 = 'rule does not apply (fewer than 200 complete states)'
    elif few:
        v2 = 'too few reads to test'
    else:
        v2 = verdict(cs, 'Written as a search hit, the line is asked for more often', 'less often')
    p(f'   verdict (by state): {v2}')
    p('')

    # ---- 5. without a rule
    p('5. Without a rule (EXPLORATORY in the sense of carrying no decision rule)')
    p(f'   a) outcome 3 restricted to OUT OF SIGHT reads (smallest start of a listed unshown neighbor in the read '
      f'file > {OUT_OF_SIGHT})')
    for a in ARMS:
        t = Counter()
        for k in sub[a]:
            t.update(agg(k, a))
        p(f'      {a:>2}: {t["oos3"]}/{t["oos"]} ask past line 1'
          + (f' ({pct(t["oos3"] / t["oos"])}%)' if t['oos'] else '')
          + f'; all outcome-2 reads {t["o3"]}/{t["o2"]}')
    d, cs, ct, tot = diff_line(complete, 'EG', 'E', 'oos3', 'oos', seed_base + 301)
    p(f'      EG minus E: {pct(d) if d is not None else "n/a"} points, by state {fmt_ci(cs)}, by task {fmt_ci(ct)}')
    for j, a in enumerate(('EL', 'H')):
        d, cs, ct, tot = diff_line(sub[a], 'EG', a, 'o1', 'n', seed_base + 401 + 10 * j)
        p(f'   b) EG minus {a} on outcome 1 ({len(sub[a])} states): EG {tot[("EG", "o1")]}/{tot[("EG", "n")]}, '
          f'{a} {tot[(a, "o1")]}/{tot[(a, "n")]}; {pct(d)} points, by state {fmt_ci(cs)}, by task {fmt_ci(ct)}')
    d, cs, ct, tot = diff_line(complete, 'EG', 'E', 'o2', 'n', seed_base + 501)
    p(f'   c) EG minus E on outcome 2: EG {tot[("EG", "o2")]}/{tot[("EG", "n")]}, E {tot[("E", "o2")]}/'
      f'{tot[("E", "n")]}; {pct(d)} points, by state {fmt_ci(cs)}, by task {fmt_ci(ct)}')
    p('')

    # ---- descriptive checks of the start-line argument
    p('Checks on the start line of outcome-2 reads (complete states)')
    for a in ARMS:
        mk = absent = nonint = rescued = low = 0
        for k in sub[a]:
            for s in SEEDS:
                o = rec[(k, a, s)]
                if not o['o2']:
                    continue
                mk += o['mangled_key']
                if o['raw'] is None:
                    absent += 1
                elif o['start'] is None:
                    nonint += 1
                    v = as_int(clean_key(o['raw']))
                    rescued += v is not None and v > 1
                elif o['start'] <= 1:
                    low += 1
        p(f'   {a:>2}: no start_line argument {absent}; not an integer {nonint} (of which past line 1 once quotes, '
          f'backslashes and whitespace are removed from the value: {rescued}); written as 1 or less {low}; '
          f'start_line found under a mangled argument name {mk}')
    p('')

    # ---- 6. judgment calls
    p('6. Judgment calls')
    for jc in JUDGMENT_CALLS:
        p('   - ' + jc)

    text = '\n'.join(lines) + '\n'
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode('utf-8'))  # LF line endings on every platform, same bytes as the file
    sys.stdout.buffer.flush()
    if not no_write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)


JUDGMENT_CALLS = [
    'Interface-failure kinds are assigned in the order error, no call, unknown tool, malformed (valid_call false); '
    'a row counts once, under the first kind that applies.',
    'Rates pool replays over seeds (successes over replays); every cluster (state or task) is resampled with all its '
    'replays, and the statistic is the pooled ratio within the resample.',
    'Differences (X1, X2, the unruled contrasts) pair the arms on the same states: each resample draws one set of '
    'states (or tasks) and computes both arms on it.',
    'Arms H and EL are reported, and contrasted with EG, on the complete states where they are usable for all three '
    'seeds (their own subset); X1 and X2 use all complete states.',
    'Clustered by task: tasks are resampled with replacement and carry all their complete states.',
    'Outcome 1 passes line_lengths (character count per line, from file_text(task, path).splitlines()) to touches '
    'for every neighbor; when file_text returns nothing, line_lengths is None and only line caps apply.',
    'Outcome 2: the read path has its leading /workspace/, workspace/ or ./ removed repeatedly until none is left; '
    'no other normalization (no whitespace strip). It is compared to the span paths of unshown true neighbors '
    'that have a span, not to shown_files.',
    'Outcome 3: the first argument whose name, after removing quotes, backslashes and whitespace, equals start_line; '
    'integers, integral floats and strings of an optional sign and digits (surrounding whitespace allowed) count as '
    'integers; booleans and anything else count as absent; absent means not past line 1. The value itself is not '
    'cleaned: a string such as 362 followed by a stray quote is not an integer (the checks above count how many '
    'such reads would pass line 1 if it were).',
    'X2 and the OUT OF SIGHT share: a state without such a read contributes nothing (shares are ratios of sums); '
    'resamples in which an arm has no such read would be dropped (the number dropped is printed when non-zero).',
    'OUT OF SIGHT is decided per read, over the unshown true neighbors whose span path equals the read path.',
    'Percentile interval: linear interpolation between order statistics at 2.5% and 97.5% of the 2,000 values; '
    'Python random.Random with fixed seeds per statistic (13013 plus an offset).',
    'Verdicts use the interval clustered by state; the interval by task is printed beside it.',
]


if __name__ == '__main__':
    main(sys.argv[1:])
