"""Independent re-derivation of an exploratory split: which kind of listed neighbor a replay reads.

EXPLORATORY: the split reported here was not pre-registered. The outcome it splits, "reads a neighbor's code", is
the registered one.

Written blind, from a written list of definitions and the raw files only (the two states files, the per-replay
rows, the task snapshots), without the project's own script for this split or its stored output. Starting point:
analysis/rederive_12.py and analysis/rederive_cd.py (loading, the failure classes, the registered outcome, the
bootstrap over steps). Imports only fork_states.touches, fork_states.valid_call and nodes.file_text; everything
else is the standard library.

Usage (from the repository root):
    py -I -X utf8 analysis/rederive_neighbor_kinds.py

Prints the report (UTF-8, LF line ends) and writes nothing. The stored output,
analysis/results/rederive_neighbor_kinds.txt, is this report redirected to a file.

The definitions, as implemented here:
  paused step       a record of the states file; its entity just read is `node`, with the span `node_span`
  entry             a name in arms.P.response.neighbors of the step (the list as the tool prints it)
  unopened entry    an entry that is in the step's unshown_true_neighbors
  kind of an entry  the first that applies: NO SPAN; CONTAINMENT (same file, different spans, one span inside the
                    other); CALLER AND CALLEE (each names the other); CALLER ONLY (the entry names the entity just
                    read and is not named by it); CALLEE ONLY (the entity just read names the entry and is not
                    named by it); NEITHER
  names             X names Y if the last component of Y's dotted name stands, as a whole identifier, in the
                    source lines of X's span
  test code         first component of the dotted name is tests or test, or the name contains .tests., or its
                    last component starts with test_
  usable replay     a row with no error and a next call to one of the nine tools whose arguments pass valid_call
  reads a neighbor's code   the next call touches (read or edit, not a graph call) an unopened entry with a span
"""
import collections
import hashlib
import json
import random
import re
import statistics
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fork_states import touches, valid_call  # noqa: E402  the registered scorer
from nodes import file_text  # noqa: E402  the text of a file in a task's snapshot

STATES_1 = HERE / 'fork_states' / 'states.jsonl'
STATES_2 = HERE / 'fork_states_d' / 'states.jsonl'
RUNS_1 = ('v5', 'v6', 'v8')
RUN_C, ARMS_C = 'c', ('H', 'EL', 'E')
RUN_12, ARMS_12 = '12', ('EPATH',)

TOOLS = {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
         'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
ARM_ORDER = ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'EPATH', 'EL', 'E', 'RD', 'RE')
DIFFS_1 = (('E', 'H'), ('E', 'D'), ('H', 'A'), ('RE', 'RD'))
DIFFS_2 = (('EL', 'H'), ('EL', 'EPATH'), ('EPATH', 'H'))
ARMS_2 = ('H', 'EPATH', 'EL', 'E')
SEEDS_2 = (1, 2, 3)
N_BOOT = 2000
BOOT_SEED_1, BOOT_SEED_2 = 731953, 731954        # resamples of steps, first and second set
TASK_SEED_1, TASK_SEED_2 = 831953, 831954        # resamples of tasks (beside the definitions)
N_OTHER_SEEDS = 20                               # other seeds for the resamples of steps: seed + 1000 * i

NO_SPAN, CONTAIN, BOTH, CALLER, CALLEE, NEITHER = (
    'NO SPAN', 'CONTAINMENT', 'CALLER AND CALLEE', 'CALLER ONLY', 'CALLEE ONLY', 'NEITHER')
KINDS = (NO_SPAN, CONTAIN, BOTH, CALLER, CALLEE, NEITHER)
OUTCOMES = (('reads', "reads a neighbor's code"), ('caller', 'reads a caller'), ('callee', 'reads a callee'),
            ('another', 'another kind'))
USED_FIELDS = ('task', 'run', 'fork', 'node', 'node_span', 'true_neighbors', 'unshown_true_neighbors',
               'neighbor_spans')

COUNT = collections.Counter()
TOUCH_VALUES = collections.Counter()


# ---------------------------------------------------------------- loading

def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def results_path(run):
    return HERE / 'results' / run / 'forks' / 'results.jsonl'


def input_line(path):
    data = Path(path).read_bytes()
    rows = sum(1 for line in data.split(b'\n') if line.strip())
    return f'   {hashlib.md5(data).hexdigest()}  analysis/{Path(path).relative_to(HERE).as_posix()} ({rows} rows)'


def step_key(d):
    return (d['task'], d['run'], d['fork'])


def printed_list(state):
    """The neighbors as the tool prints them at the step: arms.P.response.neighbors (None if absent)."""
    resp = ((state.get('arms') or {}).get('P') or {}).get('response')
    nb = resp.get('neighbors') if isinstance(resp, dict) else None
    return nb if isinstance(nb, list) else None


def load_states(path):
    states = {}
    for s in load_jsonl(path):
        s.pop('steps', None)
        states[step_key(s)] = s
    return states


def used_view(state):
    return json.dumps([state.get(f) for f in USED_FIELDS] + [printed_list(state)], sort_keys=True)


# ---------------------------------------------------------------- file texts, spans, names

_LINES = {}


def file_lines(task, path):
    """The lines of a snapshot file (split on LF, newline excluded), or None if the snapshot lacks the file."""
    key = (task, path)
    if key not in _LINES:
        text = file_text(task, path)
        if text is None:
            COUNT['files missing'] += 1
            _LINES[key] = None
        else:
            lines = text.split('\n')
            if text.endswith('\n'):
                lines = lines[:-1]
            if lines != text.splitlines():
                COUNT['split differs'] += 1
            _LINES[key] = lines
    return _LINES[key]


_LENGTHS = {}


def line_lengths(task, path):
    key = (task, path)
    if key not in _LENGTHS:
        lines = file_lines(task, path)
        _LENGTHS[key] = None if lines is None else [len(x) for x in lines]
    return _LENGTHS[key]


def full_span(span):
    """(path, start, end) of a span record that has an end, else None (NO SPAN)."""
    if not span or span.get('end') is None:
        return None
    if span.get('start') is None or not span.get('path'):
        return None
    return (span['path'], span['start'], span['end'])


RUN_ASCII = re.compile(r'[A-Za-z0-9_]+')
RUN_UNICODE = re.compile(r'\w+')
NAIVE_ASCII = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_IDENTS = {}


def identifiers(task, span, mode='ascii'):
    """The identifiers that stand in the source lines of a span (lines 1-based, both ends included).

    ascii (the reading used): maximal runs of ASCII letters, digits and underscores that start with a letter or
    an underscore. unicode: the same with every letter and digit Python's regular expressions know. naive: a
    letter or underscore followed by letters, digits and underscores, even in the middle of a run that starts
    with a digit (0x1F gives x1F). The last two are computed for the sensitivity line only.
    """
    key = (task, span, mode)
    if key not in _IDENTS:
        lines = file_lines(task, span[0])
        found = set()
        if lines is not None:
            if mode == 'ascii' and (span[2] > len(lines) or span[1] < 1):
                COUNT['span outside file'] += 1
            for line in lines[max(span[1], 1) - 1:span[2]]:
                if mode == 'naive':
                    found.update(NAIVE_ASCII.findall(line))
                elif mode == 'unicode':
                    found.update(r for r in RUN_UNICODE.findall(line) if r[0] == '_' or r[0].isalpha())
                else:
                    found.update(r for r in RUN_ASCII.findall(line) if not r[0].isdigit())
        _IDENTS[key] = frozenset(found)
    return _IDENTS[key]


def last_part(name):
    return name.rsplit('.', 1)[-1]


def kind_of(state, entry, mode='ascii'):
    node_span = full_span(state.get('node_span'))
    span = full_span((state.get('neighbor_spans') or {}).get(entry))
    if node_span is None or span is None:
        return NO_SPAN
    if span[0] == node_span[0] and span[1:] != node_span[1:]:
        (a, b), (c, d) = span[1:], node_span[1:]
        if (c <= a and b <= d) or (a <= c and d <= b):
            return CONTAIN
    task = state['task']
    entry_names_node = last_part(state['node']) in identifiers(task, span, mode)
    node_names_entry = last_part(entry) in identifiers(task, node_span, mode)
    if entry_names_node and node_names_entry:
        return BOTH
    if entry_names_node:
        return CALLER
    if node_names_entry:
        return CALLEE
    return NEITHER


def is_test(name):
    parts = name.split('.')
    return parts[0] in ('tests', 'test') or '.tests.' in name or parts[-1].startswith('test_')


def path_looks_like_test(path):
    parts = path.replace('\\', '/').split('/')
    return (any(p in ('tests', 'test') for p in parts[:-1]) or parts[-1].startswith('test_')
            or parts[-1].endswith('_test.py') or parts[-1] == 'conftest.py')


def build_steps(states):
    """Per paused step: the entries, the unopened ones, and the kind and test flag of every entry."""
    steps = {}
    for key in sorted(states):
        s = states[key]
        entries = printed_list(s)
        if entries is None:
            COUNT['steps without a printed list'] += 1
            entries = []
        unshown = set(s.get('unshown_true_neighbors') or [])
        unopened = [e for e in entries if e in unshown]
        names = list(dict.fromkeys(entries))
        steps[key] = dict(
            key=key, task=s['task'], node=s['node'], entries=entries, unopened=unopened,
            unopened_names=list(dict.fromkeys(unopened)), spans=s.get('neighbor_spans') or {},
            kind={e: kind_of(s, e) for e in names}, test={e: is_test(e) for e in names},
            same_list=entries == s.get('true_neighbors'),
            same_set=sorted(entries) == sorted(s.get('true_neighbors') or []),
            repeats=len(entries) - len(names), unshown_outside=len(unshown - set(entries)))
    return steps


# ---------------------------------------------------------------- replays

def failure_kind(row):
    """None if the replay is usable, else the first failure class that applies."""
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


def classify(rows, steps):
    """arm -> {(step, seed): row} of usable replays, and the counts of rows and failures per arm."""
    usable = collections.defaultdict(dict)
    info = collections.defaultdict(collections.Counter)
    for r in rows:
        arm = r['arm']
        info[arm]['rows'] += 1
        key = step_key(r)
        if key not in steps:
            info[arm]['step not in the states file'] += 1
            continue
        kind = failure_kind(r)
        if kind:
            info[arm][kind] += 1
            continue
        if (key, r['seed']) in usable[arm]:
            info[arm]['repeated'] += 1
            continue
        usable[arm][(key, r['seed'])] = r
        info[arm]['usable'] += 1
    return usable, info


FLAGS = ('reads', 'caller', 'callee', 'another', 'caller_test', 'caller_other', 'both', 'rest', 'contain',
         'neither', 'nospan', 'multi6', 'multi5', 'multi3', 'multi_entry')


def score(call, step):
    """What one replay's next call touches among the unopened entries of its step."""
    touched = []
    for e in step['unopened_names']:
        span = step['spans'].get(e)
        if not span:
            continue
        t = touches(call, span, e, line_lengths=line_lengths(step['task'], span['path']))
        TOUCH_VALUES[repr(t)] += 1
        if t is not None and t != 'graph':
            touched.append(e)
    kinds = {step['kind'][e] for e in touched}
    cols = set()
    for e in touched:
        k = step['kind'][e]
        if k == CALLER:
            cols.add('caller_test' if step['test'][e] else 'caller_other')
        elif k in (CALLEE, BOTH):
            cols.add(k)
        else:
            cols.add('rest')
    another = kinds - {CALLER, CALLEE}
    return dict(
        reads=bool(touched), caller=CALLER in kinds, callee=CALLEE in kinds, another=bool(another),
        caller_test='caller_test' in cols, caller_other='caller_other' in cols, both=BOTH in kinds,
        rest='rest' in cols, contain=CONTAIN in kinds, neither=NEITHER in kinds, nospan=NO_SPAN in kinds,
        multi6=len(kinds) > 1, multi5=len(cols) > 1,
        multi3=(CALLER in kinds) + (CALLEE in kinds) + bool(another) > 1, multi_entry=len(touched) > 1)


def hits_per_step(usable_arm, keys, seeds, steps):
    """step -> flag -> number of the step's replays (one per seed) with that flag."""
    hits = {}
    for k in keys:
        h = dict.fromkeys(FLAGS, 0)
        for sd in seeds:
            sc = score(usable_arm[(k, sd)]['next_call'], steps[k])
            for f in FLAGS:
                h[f] += sc[f]
        hits[k] = h
    return hits


# ---------------------------------------------------------------- bootstrap

def interval(values):
    v = sorted(values)
    return v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]


def step_bounds(vectors, n, denom, seed):
    """95% percentile bounds, in points, of each vector's summed difference over one set of step resamples."""
    rng = random.Random(seed)
    cells = {name: [(i, v) for i, v in enumerate(vec) if v] for name, vec in vectors.items()}
    sums = {name: [] for name in vectors}
    population = range(n)
    for _ in range(N_BOOT):
        times = collections.Counter(rng.choices(population, k=n))
        for name, cc in cells.items():
            sums[name].append(sum(times[i] * v for i, v in cc))
    return {name: interval([100 * s / denom for s in vals]) for name, vals in sums.items()}


def task_bounds(vectors, kept, n_seeds, seed):
    """The same with whole tasks resampled; each task brings all its kept steps."""
    tasks = sorted({k[0] for k in kept})
    where = {t: j for j, t in enumerate(tasks)}
    size = [0] * len(tasks)
    for k in kept:
        size[where[k[0]]] += 1
    per_task = {}
    for name, vec in vectors.items():
        tot = [0] * len(tasks)
        for k, v in zip(kept, vec):
            tot[where[k[0]]] += v
        per_task[name] = tot
    rng = random.Random(seed)
    vals = {name: [] for name in vectors}
    population = range(len(tasks))
    for _ in range(N_BOOT):
        times = collections.Counter(rng.choices(population, k=len(tasks)))
        replays = n_seeds * sum(c * size[j] for j, c in times.items())
        for name, tot in per_task.items():
            vals[name].append(100 * sum(c * tot[j] for j, c in times.items()) / replays)
    return {name: interval(v) for name, v in vals.items()}, len(tasks)


# ---------------------------------------------------------------- report pieces

def pc(x, n):
    return f'{x} ({100 * x / n:.2f}%)' if n else f'{x} (n/a)'


def num(x):
    return f'{x:g}'


def quart(values):
    q1, q2, q3 = statistics.quantiles(values, n=4, method='inclusive')
    return f'median {num(q2)}, quartiles {num(q1)} and {num(q3)} (least {min(values)}, most {max(values)})'


def arm_sort(arms):
    return sorted(arms, key=lambda a: (ARM_ORDER.index(a) if a in ARM_ORDER else len(ARM_ORDER), a))


def sections_0_to_2(w, steps):
    keys = sorted(steps)
    n_steps = len(keys)
    per_step = [len(steps[k]['entries']) for k in keys]
    un_per_step = [len(steps[k]['unopened']) for k in keys]
    n_entries, n_un = sum(per_step), sum(un_per_step)
    w('0. Paused steps and entries')
    w(f'   paused steps: {n_steps}, in {len({k[0] for k in keys})} tasks')
    w(f'   steps whose printed list (arms.P.response.neighbors) equals true_neighbors, same names in the same order: '
      f'{sum(steps[k]["same_list"] for k in keys)} of {n_steps}')
    w(f'   (same names in any order: {sum(steps[k]["same_set"] for k in keys)} of {n_steps})')
    w(f'   ENTRIES: {n_entries}; per step: {quart(per_step)}')
    w(f'   UNOPENED ENTRIES: {pc(n_un, n_entries)} of the entries; per step: {quart(un_per_step)}')
    w(f'   steps with no UNOPENED ENTRY: {pc(sum(1 for x in un_per_step if x == 0), n_steps)} of the steps')
    w('')

    pops = ('all entries', 'not UNOPENED', 'UNOPENED')
    tally = {p: collections.Counter() for p in pops}
    tests = {p: collections.Counter() for p in pops}
    for k in keys:
        s = steps[k]
        un = set(s['unopened'])
        for e in s['entries']:
            for p in ('all entries', 'UNOPENED' if e in un else 'not UNOPENED'):
                tally[p][s['kind'][e]] += 1
                tests[p][s['kind'][e]] += s['test'][e]
    w('1. ENTRIES by KIND: entries (share of the column) and, in square brackets, how many of them are TEST CODE')
    w(f'   {"kind":<19}' + ''.join(f'{p:>30}' for p in pops))
    for kd in KINDS:
        cells = [f'{pc(tally[p][kd], sum(tally[p].values()))} [{tests[p][kd]}]' for p in pops]
        w(f'   {kd:<19}' + ''.join(f'{c:>30}' for c in cells))
    cells = [f'{sum(tally[p].values())} (100.00%) [{sum(tests[p].values())}]' for p in pops]
    w(f'   {"all kinds":<19}' + ''.join(f'{c:>30}' for c in cells))
    w('')

    w(f'2. Steps (of {n_steps}) with at least one entry of each KIND, and with at least one UNOPENED entry of it')
    w(f'   {"kind":<19}{"an entry":>20}{"an UNOPENED entry":>24}')
    for kd in KINDS:
        any_e = sum(1 for k in keys if any(steps[k]['kind'][e] == kd for e in steps[k]['entries']))
        any_u = sum(1 for k in keys if any(steps[k]['kind'][e] == kd for e in steps[k]['unopened']))
        w(f'   {kd:<19}{pc(any_e, n_steps):>20}{pc(any_u, n_steps):>24}')
    with_un = [k for k in keys if steps[k]['unopened']]
    all_caller = sum(1 for k in with_un if all(steps[k]['kind'][e] == CALLER for e in steps[k]['unopened']))
    line = (f'   steps whose UNOPENED ENTRIES are all CALLER ONLY: {pc(all_caller, len(with_un))} of the '
            f'{len(with_un)} steps that have an UNOPENED ENTRY')
    if len(with_un) != n_steps:
        line += f' ({100 * all_caller / n_steps:.2f}% of all {n_steps} steps)'
    w(line)
    w('')


def failures_table(w, info, arms):
    w(f'   {"arm":<7}{"rows":>6}{"error":>7}{"no call":>9}{"unknown tool":>14}{"malformed":>11}{"usable":>8}')
    for a in arms:
        c = info[a]
        w(f'   {a:<7}{c["rows"]:>6}{c["error"]:>7}{c["no call"]:>9}{c["unknown tool"]:>14}{c["malformed"]:>11}'
          f'{c["usable"]:>8}')
    odd = sum(info[a]['step not in the states file'] + info[a]['repeated'] for a in arms)
    w(f'   rows whose step is not in the states file, or that repeat a (step, arm, seed): {odd}')


def kept_line(w, steps, kept, what):
    tally = collections.Counter(steps[k]['kind'][e] for k in kept for e in steps[k]['unopened'])
    n_test = sum(steps[k]['test'][e] for k in kept for e in steps[k]['unopened']
                 if steps[k]['kind'][e] == CALLER)
    w(f'   UNOPENED ENTRIES on {what}: {sum(tally.values())}')
    w('      by KIND: ' + '; '.join(
        f'{kd} {tally[kd]}' + (f' ({n_test} in TEST CODE)' if kd == CALLER else '') for kd in KINDS))


def arm_tables(w, hits, arms, keys_of, n_seeds, notes=None):
    notes = notes or {}
    tot = {a: {f: sum(hits[a][k][f] for k in keys_of[a]) for f in FLAGS} for a in arms}
    n = {a: n_seeds * len(keys_of[a]) for a in arms}
    w("   (a) Replays that READ A NEIGHBOR'S CODE (share of the arm's replays) and, among them, how many touch an "
      'UNOPENED ENTRY of')
    w('       each kind (share of those reads; a replay that touches entries of several kinds is counted under '
      'each;')
    w('       "the rest" is CONTAINMENT, NEITHER and NO SPAN)')
    w(f'   {"arm":<6}{"replays":>8}{"reads":>15}{"CALLER ONLY,":>17}{"CALLER ONLY,":>17}{"CALLEE ONLY":>17}'
      f'{"CALLER AND":>17}{"the rest":>17}')
    w(f'   {"":<6}{"":>8}{"":>15}{"TEST CODE":>17}{"other code":>17}{"":>17}{"CALLEE":>17}')
    for a in arms:
        t, r = tot[a], tot[a]['reads']
        w(f'   {a:<6}{n[a]:>8}{pc(r, n[a]):>15}{pc(t["caller_test"], r):>17}{pc(t["caller_other"], r):>17}'
          f'{pc(t["callee"], r):>17}{pc(t["both"], r):>17}{pc(t["rest"], r):>17}' + notes.get(a, ''))
    w('   (b) "The rest" by KIND; replays that touch more than one UNOPENED ENTRY; replays that touch entries of '
      'more than one kind,')
    w('       counted three ways (the six KINDS; the five columns of table (a); the three outcomes caller, callee, '
      'another kind)')
    w(f'   {"arm":<6}{"CONTAINMENT":>12}{"NEITHER":>9}{"NO SPAN":>9}{">1 entry":>10}{">1 of six KINDS":>17}'
      f'{">1 of five columns":>20}{">1 of three outcomes":>22}')
    for a in arms:
        t = tot[a]
        w(f'   {a:<6}{t["contain"]:>12}{t["neither"]:>9}{t["nospan"]:>9}{t["multi_entry"]:>10}{t["multi6"]:>17}'
          f'{t["multi5"]:>20}{t["multi3"]:>22}')
    w("   (c) The four outcomes: replays (share of the arm's replays)")
    w(f'   {"arm":<6}{"replays":>8}' + ''.join(f'{label:>26}' for _, label in OUTCOMES))
    for a in arms:
        w(f'   {a:<6}{n[a]:>8}' + ''.join(f'{pc(tot[a][f], n[a]):>26}' for f, _ in OUTCOMES) + notes.get(a, ''))


def differences(w, hits, pairs, kept, n_seeds, seed, task_seed):
    n, denom = len(kept), n_seeds * len(kept)
    vectors, counts = {}, {}
    for a, b in pairs:
        if a in hits and b in hits:
            for f, _ in OUTCOMES:
                vectors[(a, b, f)] = [hits[a][k][f] - hits[b][k][f] for k in kept]
                counts[(a, b, f)] = (sum(hits[a][k][f] for k in kept), sum(hits[b][k][f] for k in kept))
    main = step_bounds(vectors, n, denom, seed)
    w(f'   (d) DIFFERENCES in points on the {n} steps kept ({denom} replays an arm), with the 95% percentile '
      f'bootstrap interval over steps')
    for a, b in pairs:
        if (a, b, 'reads') not in vectors:
            w(f'   {a} minus {b}: skipped, an arm is missing')
            continue
        w(f'   {a} minus {b}')
        for f, label in OUTCOMES:
            xa, xb = counts[(a, b, f)]
            lo, hi = main[(a, b, f)]
            w(f'      {label:<24}{xa:>4}/{denom} ({100 * xa / denom:5.2f}%) - {xb:>4}/{denom} '
              f'({100 * xb / denom:5.2f}%) = {100 * (xa - xb) / denom:+6.2f}  [{lo:+.2f}, {hi:+.2f}]')
    return vectors, main, (n, denom, seed, task_seed)


def beside(w, hits, arms, keys_of, pairs, kept, n_seeds, vectors, setup):
    n, denom, seed, task_seed = setup
    w('   (e) Beside the definitions, not asked for: steps (and tasks) with at least one such replay')
    w(f'   {"arm":<6}' + ''.join(f'{label:>26}' for _, label in OUTCOMES))
    for a in arms:
        cells = []
        for f, _ in OUTCOMES:
            ks = [k for k in keys_of[a] if hits[a][k][f]]
            cells.append(f'{len(ks)} ({len({k[0] for k in ks})})')
        w(f'   {a:<6}' + ''.join(f'{c:>26}' for c in cells))
    others = [step_bounds(vectors, n, denom, seed + 1000 * i) for i in range(1, N_OTHER_SEEDS + 1)]
    by_task, n_tasks = task_bounds(vectors, kept, n_seeds, task_seed)
    w(f'   (f) Beside the definitions, not asked for: the bounds of (d) under {N_OTHER_SEEDS} other bootstrap seeds '
      f'(least and greatest of each')
    w(f'       bound), and the 95% interval when whole tasks are resampled instead of steps ({N_BOOT} resamples of '
      f'the {n_tasks} tasks,')
    w('       each bringing its kept steps)')
    for a, b in pairs:
        if (a, b, 'reads') not in vectors:
            continue
        w(f'   {a} minus {b}')
        for f, label in OUTCOMES:
            los = [o[(a, b, f)][0] for o in others]
            his = [o[(a, b, f)][1] for o in others]
            t_lo, t_hi = by_task[(a, b, f)]
            w(f'      {label:<24}lower {min(los):+.2f} to {max(los):+.2f}, upper {min(his):+.2f} to {max(his):+.2f}; '
              f'tasks resampled [{t_lo:+.2f}, {t_hi:+.2f}]')


# ---------------------------------------------------------------- main

def main():
    out = []
    w = out.append

    states1, states2 = load_states(STATES_1), load_states(STATES_2)
    steps1, steps2 = build_steps(states1), build_steps(states2)
    same_keys = sorted(states1) == sorted(states2)
    differing = sum(1 for k in states1 if k in states2 and used_view(states1[k]) != used_view(states2[k]))
    same = same_keys and not differing

    w('EXPLORATORY: the split reported here was not pre-registered (the outcome it splits, "reads a neighbor\'s '
      'code", is the registered one).')
    w("Independent re-derivation of the split of that outcome by the kind of the neighbor read. Written blind from "
      'a written list of')
    w("definitions and the raw files, without the project's own script for this split or its output.")
    w('Script: analysis/rederive_neighbor_kinds.py (imports only fork_states.touches, fork_states.valid_call and '
      'nodes.file_text).')
    w(f'States: analysis/fork_states/states.jsonl ({len(states1)} steps) for the first set of replays; '
      f'analysis/fork_states_d/states.jsonl ({len(states2)} steps)')
    w('for the second.')
    w(f'The two states files hold the same steps: {"yes" if same_keys else "NO"}. Steps where a field used here '
      f'differs between them: {differing}')
    w('(fields: task, run, fork, node, node_span, true_neighbors, unshown_true_neighbors, neighbor_spans, '
      'arms.P.response.neighbors).')
    w('Sections 0 to 2 are therefore the same for both files and are printed once.' if same
      else 'Sections 0 to 2 are printed for each file.')
    w('Raw input (md5 of the file, path, rows):')
    for path in [STATES_1, STATES_2] + [results_path(run) for run in RUNS_1 + (RUN_C, RUN_12)]:
        w(input_line(path))
    w('')

    sections_0_to_2(w, steps1)
    if not same:
        w('Sections 0 to 2 again, for analysis/fork_states_d/states.jsonl')
        sections_0_to_2(w, steps2)

    # ---- 3. first set
    rows1 = []
    where = collections.defaultdict(set)
    for run in RUNS_1:
        for r in load_jsonl(results_path(run)):
            rows1.append(r)
            where[r['arm']].add(run)
    arms1 = arm_sort({r['arm'] for r in rows1})
    seeds1 = sorted({r['seed'] for r in rows1})
    usable1, info1 = classify(rows1, steps1)

    def kept_for(arms):
        return [k for k in sorted(steps1) if all((k, sd) in usable1[a] for a in arms for sd in seeds1)]

    kept1 = kept_for(arms1)
    in_a_difference = arm_sort({a for pair in DIFFS_1 for a in pair if a in arms1})
    w('3. First set of replays (analysis/results/v5, v6 and v8, forks/results.jsonl)')
    w('   arms present: ' + '; '.join(f'{a} ({", ".join(sorted(where[a]))})' for a in arms1)
      + f'. Seeds present: {", ".join(str(s) for s in seeds1)}.')
    failures_table(w, info1, arms1)
    w(f'   STEPS KEPT (every arm usable for every seed): {len(kept1)} of {len(steps1)}, in '
      f'{len({k[0] for k in kept1})} tasks; {len(seeds1) * len(kept1)} replays an arm')
    kept_line(w, steps1, kept1, 'the steps kept')
    hits1 = {a: hits_per_step(usable1[a], kept1, seeds1, steps1) for a in arms1}
    keys_of1 = {a: kept1 for a in arms1}
    arm_tables(w, hits1, arms1, keys_of1, len(seeds1))
    vectors1, _, setup1 = differences(w, hits1, DIFFS_1, kept1, len(seeds1), BOOT_SEED_1, TASK_SEED_1)
    beside(w, hits1, arms1, keys_of1, DIFFS_1, kept1, len(seeds1), vectors1, setup1)
    w('')

    # ---- 4. second set
    rows_c = load_jsonl(results_path(RUN_C))
    rows_12 = load_jsonl(results_path(RUN_12))
    rows2 = ([r for r in rows_c if r['arm'] in ARMS_C and r['seed'] in SEEDS_2]
             + [r for r in rows_12 if r['arm'] in ARMS_12 and r['seed'] in SEEDS_2])
    ignored = len(rows_c) + len(rows_12) - len(rows2)
    usable2, info2 = classify(rows2, steps2)

    def full(a, k):
        return all((k, sd) in usable2[a] for sd in SEEDS_2)

    kept2 = [k for k in sorted(steps2) if full('H', k) and full('EL', k) and full('EPATH', k)]
    kept2_e = [k for k in kept2 if full('E', k)]
    w('4. Second set of replays (analysis/results/c: arms H, EL and E; analysis/results/12: arm EPATH; '
      'forks/results.jsonl)')
    w(f'   seeds 1, 2 and 3; rows of other arms or seeds in the two files, ignored: {ignored}')
    failures_table(w, info2, ARMS_2)
    w(f'   STEPS KEPT (H, EL and EPATH usable for seeds 1, 2 and 3): {len(kept2)} of {len(steps2)}, in '
      f'{len({k[0] for k in kept2})} tasks; {3 * len(kept2)} replays an arm')
    w(f'   of these, steps where E too is usable for the three seeds: {len(kept2_e)} ({3 * len(kept2_e)} replays); '
      f'arm E is counted on these')
    kept_line(w, steps2, kept2, 'the steps kept')
    if len(kept2_e) != len(kept2):
        kept_line(w, steps2, kept2_e, 'the steps kept where E is usable')
    keys_of2 = {a: (kept2_e if a == 'E' else kept2) for a in ARMS_2}
    hits2 = {a: hits_per_step(usable2[a], keys_of2[a], SEEDS_2, steps2) for a in ARMS_2}
    note = {'E': f'   (on {len(kept2_e)} steps)'} if len(kept2_e) != len(kept2) else {}
    arm_tables(w, hits2, ARMS_2, keys_of2, 3, note)
    vectors2, _, setup2 = differences(w, hits2, DIFFS_2, kept2, 3, BOOT_SEED_2, TASK_SEED_2)
    beside(w, hits2, ARMS_2, keys_of2, DIFFS_2, kept2, 3, vectors2, setup2)
    w('')

    # ---- 5. judgment calls, with the counts that show how much each one matters
    all_entries = [(k, e) for k in sorted(steps1) for e in steps1[k]['entries']]
    un_of = {k: set(steps1[k]['unopened']) for k in steps1}

    def kinds_text(pairs):
        tally = collections.Counter(steps1[k]['kind'][e] for k, e in pairs)
        return ', '.join(f'{kd} {tally[kd]}' for kd in KINDS if tally[kd]) or 'none'

    def unopened(pairs):
        return [(k, e) for k, e in pairs if e in un_of[k]]

    selves = [(k, e) for k, e in all_entries if e == steps1[k]['node']]
    same_last = [(k, e) for k, e in all_entries
                 if e != steps1[k]['node'] and last_part(e) == last_part(steps1[k]['node'])]
    changes = {mode: [(k, e) for k, e in all_entries if kind_of(states1[k], e, mode) != steps1[k]['kind'][e]]
               for mode in ('unicode', 'naive')}
    with_path = [(k, e) for k, e in all_entries if steps1[k]['spans'].get(e)]
    path_only = [(k, e) for k, e in with_path
                 if not steps1[k]['test'][e] and path_looks_like_test(steps1[k]['spans'][e]['path'])]
    name_only = [(k, e) for k, e in with_path
                 if steps1[k]['test'][e] and not path_looks_like_test(steps1[k]['spans'][e]['path'])]
    same_span, partial, node_file = [], [], []
    for k, e in all_entries:
        sp, ns = full_span(steps1[k]['spans'].get(e)), full_span(states1[k].get('node_span'))
        if not sp or not ns or sp[0] != ns[0]:
            continue
        node_file.append((k, e))
        if sp == ns:
            same_span.append((k, e))
        elif steps1[k]['kind'][e] != CONTAIN and not (sp[2] < ns[1] or ns[2] < sp[1]):
            partial.append((k, e))
    no_node_span = sum(1 for k in steps1 if full_span(states1[k].get('node_span')) is None)
    half_spans = sum(1 for k, e in all_entries
                     if steps1[k]['spans'].get(e) and full_span(steps1[k]['spans'][e]) is None)
    un_nospan = [(k, e) for k, e in unopened(all_entries) if steps1[k]['kind'][e] == NO_SPAN]
    node_file_un = unopened(node_file)

    calls = [
        'Sections 0 to 2 cover every paused step of the states file, kept or not. Sections 3 and 4 cover the steps '
        'kept of each set and print, for reference, the UNOPENED ENTRIES by KIND on those steps.',

        f'An ENTRY is one position of the printed list (steps without a printed list: '
        f'{COUNT["steps without a printed list"]}; names repeated within a list: '
        f'{sum(steps1[k]["repeats"] for k in steps1)}). Names in unshown_true_neighbors that are not in the '
        f'printed list: {sum(steps1[k]["unshown_outside"] for k in steps1)}; so the UNOPENED ENTRIES are exactly '
        'unshown_true_neighbors, the set the registered outcome is scored on.',

        'Quartiles: statistics.quantiles with method inclusive (linear interpolation between closest ranks).',

        f'NO SPAN: no span record for the entry, or a record without an end ({half_spans} entries have a record '
        f'that lacks an end, a start or a path), or a step whose node_span is missing or has no end '
        f'({no_node_span} steps). For the registered outcome, "has a span" is read as in the starting scripts: '
        f'neighbor_spans holds a record for the entry. UNOPENED ENTRIES of KIND NO SPAN: {len(un_nospan)}, so the '
        'two readings cannot differ on these data.',

        'CONTAINMENT: same path, (start, end) not equal, and one span inside the other, bounds allowed to '
        f'coincide. Entries in the file of the entity just read whose span overlaps its span without containment: '
        f'{len(partial)}. Entries with exactly the span of the entity just read: {len(same_span)}; entries that '
        f'are the entity just read itself (it is in its own list): {len(selves)}, of them UNOPENED: '
        f'{len(unopened(selves))}. Such an entry is not CONTAINMENT (the spans do not differ) and goes on to the '
        f'naming rules, where an entity names itself on its own definition line; their KINDS: '
        f'{kinds_text(selves)}.',

        'UNOPENED ENTRIES that lie in the file of the entity just read are kept and scored like any other: '
        f'{len(node_file_un)} ({kinds_text(node_file_un)}), in {len({k for k, _ in node_file_un})} steps, the '
        'steps where the run had not opened that file. Every UNOPENED ENTRY of KIND CONTAINMENT is among them, so '
        'a replay that opens the code of the entity just read can count there as reading a neighbor (the class '
        'around it, or its own method).',

        'NAMES is read on the text of the span as it stands, lines start to end inclusive: decorators, the '
        'definition line, comments, strings and docstrings all count, and nothing is parsed. So an entry whose '
        'last name component equals that of the entity just read names it, and is named by it, through the two '
        f'definition lines alone. Entries other than the entity itself that share its last component: '
        f'{len(same_last)} ({kinds_text(same_last)}), of them UNOPENED: {len(unopened(same_last))} '
        f'({kinds_text(unopened(same_last))}).',

        'Identifier: a maximal run of ASCII letters, digits and underscores that starts with a letter or an '
        'underscore (a run that starts with a digit holds no identifier). Entries whose KIND changes if letters '
        f'and digits are any Unicode ones: {len(changes["unicode"])} ({len(unopened(changes["unicode"]))} '
        f'UNOPENED); if an identifier may start inside a run that begins with a digit: {len(changes["naive"])} '
        f'({len(unopened(changes["naive"]))} UNOPENED).',

        'File lines: the text from nodes.file_text split on LF, newline excluded, a final empty piece after a '
        'trailing newline dropped (as in rederive_12.py; rederive_cd.py uses splitlines). Files where the two '
        f'ways differ: {COUNT["split differs"]}; files of a span missing from the snapshot: '
        f'{COUNT["files missing"]}; spans that reach outside their file: {COUNT["span outside file"]}.',

        'TEST CODE is decided by the dotted name alone, as written (a component test or tests that is not the '
        'first counts only in the form .tests.). Entries that are not TEST CODE by the name but whose file path '
        f'has a directory test or tests, or a file named test_*.py, *_test.py or conftest.py: {len(path_only)} '
        f'({len(unopened(path_only))} UNOPENED); entries that are TEST CODE by the name with no such path: '
        f'{len(name_only)}.',

        'USABLE REPLAY: failure classes in the order error, no call (no next call, or one without a function '
        'name), unknown tool (not one of the nine tools), malformed (valid_call false); a replay counts once. A '
        'valid call to a graph tool is usable and is never a read. A repeated (step, arm, seed) row would keep '
        'the first; a row whose step is not in the states file is left out.',

        f'STEPS KEPT, first set: all {len(arms1)} arms present in the three files ({", ".join(arms1)}) must be '
        f'usable for seeds {", ".join(str(s) for s in seeds1)}, not only the {len(in_a_difference)} arms that '
        f'enter a DIFFERENCE (with only {", ".join(in_a_difference)} the steps kept would be '
        f'{len(kept_for(in_a_difference))}). Every arm is scored on the UNOPENED ENTRIES of the true list, '
        'whatever the arm itself showed the model.',

        "READS A NEIGHBOR'S CODE: touches returns something other than None and 'graph' for at least one "
        "UNOPENED ENTRY, called with the line lengths of the entry's file. Values returned over all the calls "
        'scored in sections 3 and 4: ' + ', '.join(f'{v} {TOUCH_VALUES[v]}' for v in sorted(TOUCH_VALUES)) + '.',

        'One call can touch several UNOPENED ENTRIES. The split counts a replay under every kind it touches, so '
        'the kind columns may add to more than the reads, and "reads a caller", "reads a callee" and "another '
        'kind" are not exclusive by construction. "Another kind" is CALLER AND CALLEE, CONTAINMENT, NEITHER or '
        'NO SPAN. "Reads a caller" takes CALLER ONLY entries in TEST CODE and in other code together. "More '
        'than one kind" is given three ways because the text does not say which.',

        'Shares pool replays: replays with the outcome over all replays of the arm on the steps kept (steps '
        'times seeds; a step kept has one replay per seed in every arm). A DIFFERENCE is paired: both arms on the '
        'same steps and seeds.',

        f'Bootstrap: random.Random(seed).choices over the steps kept, sorted by task, run and fork; seed '
        f'{BOOT_SEED_1} for the first set and {BOOT_SEED_2} for the second; {N_BOOT} resamples, one set of '
        'resamples per set of replays, shared by every DIFFERENCE and outcome; each resample divides its summed '
        'difference in hits by its replays. Percentile bounds are the 51st and the 1,950th of the 2,000 sorted '
        f'values, as in the starting scripts. One hit is {100 / (len(seeds1) * len(kept1)):.2f} points in the '
        f'first set and {100 / (3 * len(kept2)):.2f} in the second, and a bound that sits one hit from zero can '
        'land on zero under another seed (table f gives the range of each bound).',

        'Tables (e) and (f) are additions of this script: counts of steps and tasks behind each outcome, the '
        f'bounds under {N_OTHER_SEEDS} other seeds (seed + 1000, + 2000, ...) as a rough guide to the Monte Carlo '
        f'error, and intervals with whole tasks resampled (seeds {TASK_SEED_1} and {TASK_SEED_2}; a resample '
        'divides by its own number of replays), since the steps of a task are not independent.',

        'Second set: arm E is restricted to the steps kept where E too is usable for the three seeds, so its '
        'shares are on fewer steps; E enters no DIFFERENCE there.',
    ]
    w('5. Judgment calls where the definitions left room (counts are over all paused steps unless said otherwise)')
    for i, c in enumerate(calls, 1):
        head = f'   {i}. '
        w(textwrap.fill(c, width=118, initial_indent=head, subsequent_indent=' ' * len(head),
                        break_long_words=False, break_on_hyphens=False))

    sys.stdout.buffer.write(('\n'.join(out) + '\n').encode('utf-8'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
