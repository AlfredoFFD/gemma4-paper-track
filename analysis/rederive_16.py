"""Independent re-derivation of the registered results of pre-registration 16 from the raw per-call records.

Written from the text of prereg/16-task-prompt-wording-and-graph-calls.md and the raw rows only, without sight of the
project's own analysis script for this experiment or its stored output. The one import from the repository is
fork_states.valid_call, the frozen rule for a malformed call.

Usage: py -I -X utf8 analysis/rederive_16.py <run_dir> [--no-write]
<run_dir> holds results_16.jsonl (analysis/results/16/forks). Prints the report and, unless --no-write is given,
writes the same text to analysis/results/rederive_16.txt (LF line endings).
"""
import collections
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fork_states import valid_call  # noqa: E402  (the frozen malformed-call rule)

ARMS = ('C', 'CS', 'S', 'SC')
SEEDS = (1, 2, 3)
GRAPH_TOOLS = ('get_code_neighbors', 'get_code_subgraph', 'search_similar_code')
DECLARED_TOOLS = ('run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
                  'get_code_neighbors', 'search_similar_code', 'get_code_subgraph')
SEARCH_CMDS = ('grep', 'egrep', 'fgrep', 'rg', 'find')
N_BOOT = 2000
BOOT_SEED = 16016  # this script's own seed (the registered analysis uses seed 0 in its own routine)
MIN_COMPLETE = 60
OUT_NAME = 'rederive_16.txt'


# ---------------------------------------------------------------- classification of one response

def calls_of(row):
    steps = row.get('steps') or []
    if not steps:
        return [], ''
    st = steps[0]
    return list(st.get('calls') or []), (st.get('text') or '')


def classify(row):
    """(kind, detail). kind is call, text, malformed or error; detail names the failure."""
    if row.get('error'):
        return 'error', 'error'
    calls, text = calls_of(row)
    if calls:
        for c in calls:
            name = c.get('function_name')
            if name not in DECLARED_TOOLS:
                return 'malformed', 'unknown tool'
            if not valid_call(c):
                return 'malformed', 'malformed arguments (%s)' % name
        return 'call', ''
    if text.strip():
        return 'text', ''
    return 'malformed', 'neither a call nor a text'


def graph_first(row):
    calls, _ = calls_of(row)
    return int(any(c.get('function_name') in GRAPH_TOOLS for c in calls))


SEP = re.compile(r'\|\||&&|[|;]')


def _words(segment):
    w = segment.strip().split()
    while w and (re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', w[0]) or w[0] in ('sudo', 'command', 'time')):
        w = w[1:]
    return w


def is_search_command(cmd, any_segment=False):
    """A run_command search: the command it runs is grep, rg or find (also egrep, fgrep, git grep).
    Default: the leading command, after leading cd segments; any_segment=True also counts a search later in a
    pipeline or chain (a sensitivity count)."""
    segs = [s for s in SEP.split(cmd or '') if s.strip()]
    heads = []
    for s in segs:
        w = _words(s)
        if not w:
            continue
        head = w[0].rsplit('/', 1)[-1]
        if head == 'git' and len(w) > 1 and w[1] == 'grep':
            head = 'grep'
        heads.append(head)
    if any_segment:
        return any(h in SEARCH_CMDS for h in heads)
    for h in heads:
        if h == 'cd':
            continue
        return h in SEARCH_CMDS
    return False


def first_call_kind(row, any_segment=False):
    calls, _ = calls_of(row)
    if not calls:
        return 'text answer (no call)'
    c = calls[0]
    name = c.get('function_name')
    if name == 'read_file':
        return 'read_file'
    if name == 'run_command' and is_search_command((c.get('arguments') or {}).get('command', ''), any_segment):
        return 'run_command search'
    if name in GRAPH_TOOLS:
        return 'graph tool'
    return 'something else'


# ---------------------------------------------------------------- statistics

def percentile(sorted_vals, q):
    """Linear interpolation between order statistics (q in [0, 100])."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def boot_ci(values, label):
    """Mean of per-task values with a 95% percentile interval over tasks (resampled with replacement).
    A fresh generator per interval, seeded by BOOT_SEED and the label, so each interval is reproducible alone."""
    n = len(values)
    if n == 0:
        return float('nan'), float('nan'), float('nan')
    seed = BOOT_SEED + int(hashlib.md5(label.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    means = []
    for _ in range(N_BOOT):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return sum(values) / n, percentile(means, 2.5), percentile(means, 97.5)


def pct(x):
    return '%.1f' % (100.0 * x)


# ---------------------------------------------------------------- report

def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    no_write = '--no-write' in argv[1:]
    if len(args) != 1:
        sys.stderr.write(__doc__)
        return 2
    run_dir = Path(args[0])
    path = run_dir / 'results_16.jsonl'
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]

    out = []
    p = out.append

    p('Re-derivation of pre-registration 16 from the raw per-call records (independent script)')
    p('input: results_16.jsonl, %d rows, md5 %s' % (len(rows), hashlib.md5(raw).hexdigest()))
    p('bootstrap: %d resamples of tasks with replacement, percentile 95%%, own generator (seed %d + label)'
      % (N_BOOT, BOOT_SEED))
    p('')

    # index rows; duplicates are reported and the first kept
    by_key = {}
    dups = 0
    for r in rows:
        key = (r.get('task'), r.get('arm'), int(r.get('seed')))
        if key in by_key:
            dups += 1
            continue
        by_key[key] = r
    tasks = sorted({k[0] for k in by_key})
    repo = {t: t.split('_')[0] for t in tasks}
    repos = sorted(set(repo.values()))
    kind = {k: classify(r) for k, r in by_key.items()}
    usable = {k: kind[k][0] in ('call', 'text') for k in by_key}

    # ------------------------------------------------------------ 1
    p('1. Rows, interface failures and usable responses, by arm')
    p('   expected per arm: %d tasks x %d seeds = %d rows; duplicate rows dropped: %d'
      % (len(tasks), len(SEEDS), len(tasks) * len(SEEDS), dups))
    for arm in ARMS:
        keys = [k for k in by_key if k[1] == arm]
        missing = len(tasks) * len(SEEDS) - len(keys)
        kinds = collections.Counter(kind[k][0] for k in keys)
        fails = collections.Counter(kind[k][1] for k in keys if kind[k][0] in ('malformed', 'error'))
        nus = sum(usable[k] for k in keys)
        p('   %-2s rows %d (missing %d); call %d, text answer %d, malformed %d, error %d; usable %d of %d (%s%%)'
          % (arm, len(keys), missing, kinds['call'], kinds['text'], kinds['malformed'], kinds['error'],
             nus, len(keys), pct(nus / len(keys)) if keys else 'n/a'))
        if fails:
            for d, n in sorted(fails.items()):
                p('      interface failure: %s: %d' % (d, n))
        else:
            p('      interface failures: none')
    inc_by_arm = {}
    for arm in ARMS:
        inc_by_arm[arm] = [t for t in tasks if not all(usable.get((t, arm, s), False) for s in SEEDS)]
    complete = [t for t in tasks if all(usable.get((t, a, s), False) for a in ARMS for s in SEEDS)]
    complete_ccs = [t for t in tasks if all(usable.get((t, a, s), False) for a in ('C', 'CS') for s in SEEDS)]
    p('   tasks in the rows: %d (%s)' % (len(tasks), ', '.join('%s %d' % (rp, sum(repo[t] == rp for t in tasks))
                                                            for rp in repos)))
    for arm in ARMS:
        ok = [t for t in tasks if t not in inc_by_arm[arm]]
        p('   %-2s complete for this arm (3 of 3 seeds usable): %d (%s); not: %s'
          % (arm, len(ok), ', '.join('%s %d' % (rp, sum(repo[t] == rp for t in ok)) for rp in repos),
             ', '.join(inc_by_arm[arm]) or 'none'))
    p('   complete tasks (every arm and seed usable): %d (%s); excluded: %s'
      % (len(complete), ', '.join('%s %d' % (rp, sum(repo[t] == rp for t in complete)) for rp in repos),
         ', '.join(t for t in tasks if t not in complete) or 'none'))
    p('')

    # budget-stop condition: S and SC incomplete (rows missing for S or SC)
    s_rows = sum(1 for k in by_key if k[1] in ('S', 'SC'))
    budget_stop = s_rows < len(tasks) * 2 * len(SEEDS)

    def task_share(t, arm):
        return sum(graph_first(by_key[(t, arm, s)]) for s in SEEDS) / len(SEEDS)

    # ------------------------------------------------------------ 2
    base = complete_ccs if budget_stop else complete
    p('2. Share of replays with graph_first, by arm, on the complete tasks (n = %d tasks)' % len(base))
    for arm in ARMS:
        if budget_stop and arm in ('S', 'SC'):
            p('   %-2s not run (budget stop left S and SC incomplete)' % arm)
            continue
        vals = [task_share(t, arm) for t in base]
        k = sum(graph_first(by_key[(t, arm, s)]) for t in base for s in SEEDS)
        m, lo, hi = boot_ci(vals, 'share:' + arm)
        p('   %-2s %d of %d replays = %s%% [%s, %s]; tasks with any graph_first: %d of %d'
          % (arm, k, len(base) * len(SEEDS), pct(m), pct(lo), pct(hi), sum(v > 0 for v in vals), len(base)))
        for rp in repos:
            tt = [t for t in base if repo[t] == rp]
            kk = sum(graph_first(by_key[(t, arm, s)]) for t in tt for s in SEEDS)
            p('      %s: %d of %d' % (rp, kk, len(tt) * len(SEEDS)))
    p('')

    # ------------------------------------------------------------ 3
    p('3. Registered rules (difference of shares, per-task paired, 95% bootstrap interval over tasks)')

    def contrast(a, b, tlist, label):
        diffs = [task_share(t, a) - task_share(t, b) for t in tlist]
        m, lo, hi = boot_ci(diffs, label)
        ka = sum(graph_first(by_key[(t, a, s)]) for t in tlist for s in SEEDS)
        kb = sum(graph_first(by_key[(t, b, s)]) for t in tlist for s in SEEDS)
        npos = sum(d > 0 for d in diffs)
        nneg = sum(d < 0 for d in diffs)
        return m, lo, hi, ka, kb, npos, nneg

    def line(name, a, b, tlist, label, verdict_fn):
        m, lo, hi, ka, kb, npos, nneg = contrast(a, b, tlist, label)
        if len(tlist) < MIN_COMPLETE:
            verdict = 'underpowered (fewer than %d complete tasks)' % MIN_COMPLETE
        else:
            verdict = verdict_fn(lo, hi)
        p('   %s  %s minus %s: %+.1f points [%+.1f, %+.1f]  (%s %d of %d, %s %d of %d; n = %d tasks; tasks %s>%s: %d, '
          '%s<%s: %d)'
          % (name, a, b, 100 * m, 100 * lo, 100 * hi, a, ka, len(tlist) * 3, b, kb, len(tlist) * 3, len(tlist),
             a, b, npos, a, b, nneg))
        p('        verdict: %s' % verdict)

    def met(lo, hi):
        return 'met' if lo > 0 else 'not met'

    def w3(lo, hi):
        if lo > 0:
            return 'more graph calls with the September listing'
        if hi < 0:
            return 'fewer'
        return 'no detectable difference'

    w1_tasks = complete_ccs if budget_stop else complete
    line('W1      ', 'CS', 'C', w1_tasks, 'W1', met)
    if budget_stop:
        p('   W2       not run (budget stop left S and SC incomplete)')
        p('   W3 (a)   not run')
        p('   W3 (b)   not run')
    else:
        line('W2      ', 'S', 'SC', complete, 'W2', met)
        line('W3 (a)  ', 'SC', 'C', complete, 'W3a', w3)
        line('W3 (b)  ', 'S', 'CS', complete, 'W3b', w3)
    p('')

    # ------------------------------------------------------------ 4
    p('4. Counts without a rule, by arm (usable responses on the complete tasks unless stated)')
    p('   share of graph_first on every usable response, complete or not:')
    for arm in ARMS:
        keys = [k for k in by_key if k[1] == arm and usable[k]]
        k = sum(graph_first(by_key[x]) for x in keys)
        p('      %-2s %d of %d (%s%%)' % (arm, k, len(keys), pct(k / len(keys)) if keys else 'n/a'))
    p('   the tool called first:')
    for arm in ARMS:
        keys = [(t, arm, s) for t in base for s in SEEDS if (t, arm, s) in by_key]
        c = collections.Counter()
        for x in keys:
            calls, _ = calls_of(by_key[x])
            c[calls[0].get('function_name') if calls else '(text answer)'] += 1
        p('      %-2s %s  (of %d)' % (arm, ', '.join('%s %d' % kv for kv in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))),
                                     len(keys)))
    p('   search_similar_code calls: phrase (query holds a blank) vs symbol-like (one token):')
    for arm in ARMS:
        keys = [(t, arm, s) for t in base for s in SEEDS if (t, arm, s) in by_key]
        ph = sy = 0
        for x in keys:
            calls, _ = calls_of(by_key[x])
            for cl in calls:
                if cl.get('function_name') == 'search_similar_code':
                    q = str((cl.get('arguments') or {}).get('query', '')).strip()
                    if re.search(r'\s', q):
                        ph += 1
                    else:
                        sy += 1
        tot = ph + sy
        p('      %-2s phrase %d, symbol-like %d (of %d calls%s)'
          % (arm, ph, sy, tot, '; phrase share %s%%' % pct(ph / tot) if tot else ''))
    p('   the kind of first call (run_command search = the leading command is grep, rg or find):')
    for arm in ARMS:
        keys = [(t, arm, s) for t in base for s in SEEDS if (t, arm, s) in by_key]
        c = collections.Counter(first_call_kind(by_key[x]) for x in keys)
        c2 = collections.Counter(first_call_kind(by_key[x], any_segment=True) for x in keys)
        order = ('read_file', 'run_command search', 'graph tool', 'something else', 'text answer (no call)')
        p('      %-2s %s  (of %d)' % (arm, ', '.join('%s %d (%s%%)' % (o, c[o], pct(c[o] / len(keys)))
                                                    for o in order if c[o] or o != 'text answer (no call)'), len(keys)))
        if c2 != c:
            p('         if a search anywhere in a pipeline counts: run_command search %d, something else %d'
              % (c2['run_command search'], c2['something else']))
    p('')

    # ------------------------------------------------------------ 5
    p('5. Judgment calls where the pre-registration left room')
    for j in JUDGMENTS:
        p('   - ' + j)

    text = '\n'.join(out) + '\n'
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode('utf-8'))
    sys.stdout.buffer.flush()
    if not no_write:
        (HERE / 'results' / OUT_NAME).write_bytes(text.encode('utf-8'))
    return 0


JUDGMENTS = [
    'Malformed call: fork_states.valid_call (the brief names it as the frozen rule; the pre-registration names '
    'gates_c.failure, which this script does not open), plus any tool outside the nine declared ones. A response '
    'with several calls is malformed if any one of them is.',
    'Error: a row whose error field is non-empty. Neither a call nor a non-blank text: malformed.',
    'graph_first counts a graph call anywhere in the response, not only its first call.',
    'Share per arm = mean over tasks of the per-task share of 3 seeds (equal to the pooled share on complete tasks); '
    'each rule is the mean of per-task paired differences, resampled over tasks.',
    'Verdict for W1 and W2 when the lower bound is not above 0: "not met". Underpowered applies when the rule is '
    'computed on fewer than 60 tasks; budget stop = fewer S and SC rows than tasks x 2 x 3.',
    'Bootstrap percentiles by linear interpolation; a fresh generator per interval (seed 16016 + an md5 of the '
    'rule label), not the registered seed 0 routine.',
    'Section 4 counts use the usable responses of the complete tasks; the graph_first share is also given on every '
    'usable response. Tool called first = the first call of the response.',
    'Phrase = the stripped query holds whitespace. run_command search = the leading command (after cd) is grep, '
    'egrep, fgrep, rg, find or git grep; the count with a search anywhere in a pipeline is shown where it differs.',
]


if __name__ == '__main__':
    sys.exit(main(sys.argv))
