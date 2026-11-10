"""Independent re-derivation of the registered results of pre-registration 09 (rules A1 and A2) and of rule N1 of
pre-registration 08 (evaluated on arm N of the same run), from the raw per-episode records.

Written from the texts of pre-registrations 06, 08 and 09 and from the raw records, without reading the analysis
script of this run, its stored outputs or the project's logs. It imports the frozen scorer (`fork_states.touches`)
and the resolver (`nodes.span`, `nodes.file_text`) and nothing else from the repository.

Usage: py -I -X utf8 analysis/rederive_09.py <run_dir> [--no-write] [--episodes <file>]

Reads <run_dir>/results_09.jsonl and analysis/fork_states_g/fresh_states.jsonl. Prints a report and, unless
--no-write is given, writes the same text to analysis/results/rederive_09.txt (LF line endings). --episodes also
writes one JSON line per counted episode with its outcomes to the given file, for an episode-by-episode comparison;
it does not change the report.
"""
import hashlib
import json
import math
import random
import re
import shlex
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from fork_states import touches  # noqa: E402  the frozen scorer
from nodes import file_text, span  # noqa: E402  the resolver and the snapshot's file contents

ARMS = ('N', 'NA', 'NAF')
SEEDS = (1, 2, 3)
HORIZON = 8
GRAPH_LIST = {'search_similar_code': 'results', 'get_code_neighbors': 'neighbors', 'get_code_subgraph': 'nodes'}
BOUNDS = ('start_line', 'end_line')
PLAIN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
NUMBER = re.compile(r'[+-]?\d+')
SED_PRINT = re.compile(r'\d+(,\d+)?p')
BOUND_IN_PATH = re.compile(r'start_line|end_line')
SHELL_PUNCT = set('();<>|&')
NO_NODE = '\x00'  # the files of the gold patch have no node: no grep stage can name this
RESAMPLES = 2000
BOOT_SEED = 20261110
OTHER_SEEDS = range(1, 21)  # for the line that shows how far a bound moves with the seed
N1_THRESHOLD = 2.1  # percent, as rule N1 states it
MIN_COMPLETE_TASKS = 60  # pre-registration 09, common rules
MIN_FRESH_EPISODES = 150  # pre-registration 08, common rules
STATES_MD5 = '2bb8662de0f614d8cbf3be1c9a244f36'  # fresh_states.jsonl as frozen in pre-registrations 08 and 09
STATES = ROOT / 'analysis' / 'fork_states_g' / 'fresh_states.jsonl'
OUT = ROOT / 'analysis' / 'results' / 'rederive_09.txt'
WIDTH = 118
USAGE = 'usage: py -I -X utf8 analysis/rederive_09.py <run_dir> [--no-write] [--episodes <file>]'


# ---------------------------------------------------------------- small helpers

def norm(path):
    """One spelling per file: a/b.py, ./a/b.py and /workspace/a/b.py are the same file to the harness."""
    if not isinstance(path, str):
        return None
    path = path.strip()
    while True:
        for prefix in ('/workspace/', './'):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        else:
            return path


def reads_as(name):
    """An argument name once quotes, backslashes and whitespace are removed."""
    if not isinstance(name, str):
        return None
    return ''.join(ch for ch in name if ch not in '"\'\\' and not ch.isspace())


def bound_names(args):
    """The argument names of a call that read start_line or end_line."""
    return [k for k in args if reads_as(k) in BOUNDS]


def mangled_names(args):
    """The line-bound names of a call that are not plain identifiers."""
    return [k for k in bound_names(args) if not PLAIN.fullmatch(k)]


def restored(call):
    """A read_file call as arm NAF executed it: a mangled line-bound name counts under its plain name, and a
    well-formed name wins if both are present. Any other call is returned as it is."""
    args = call.get('arguments')
    if call.get('function_name') != 'read_file' or not isinstance(args, dict):
        return call
    bad = mangled_names(args)
    if not bad:
        return call
    new = {k: v for k, v in args.items() if k not in bad}
    for k in bad:
        new.setdefault(reads_as(k), args[k])
    return {'function_name': 'read_file', 'arguments': new}


_LENGTHS = {}


def line_lengths(task, path):
    """Characters per line of a snapshot file, or None if the resolver has no text for it. The text is split at
    newlines and a final newline opens no further line."""
    key = (task, path)
    if key not in _LENGTHS:
        text = file_text(task, path)
        if text is None:
            _LENGTHS[key] = None
        else:
            lines = text.split('\n')
            if lines and lines[-1] == '':
                lines.pop()
            _LENGTHS[key] = [len(x) for x in lines]
    return _LENGTHS[key]


def ok_result(call):
    res = call.get('result')
    return bool(call.get('executed')) and isinstance(res, dict) and res.get('status') == 'ok'


def calls_of(step):
    calls = step.get('calls')
    return calls if isinstance(calls, list) else []


def errored(row):
    return row.get('error') is not None or row.get('stop') == 'error'


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def count(items):
    out = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def pct(num, den):
    return '%.2f%% (%d of %d)' % (100.0 * num / den, num, den) if den else 'no episodes (0 of 0)'


# ---------------------------------------------------------------- bootstrap (own implementation)

def percentile(sorted_values, q):
    """Linear interpolation between the two closest order statistics."""
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def boot_ci(clusters, stat, seed=BOOT_SEED):
    """95% percentile interval of stat over RESAMPLES resamples of the clusters (tasks), drawn with replacement,
    as many as there are clusters. Returns (low, high, resamples used)."""
    rng = random.Random(seed)
    k = len(clusters)
    values = []
    for _ in range(RESAMPLES):
        v = stat(rng.choices(clusters, k=k))
        if v is not None:
            values.append(v)
    values.sort()
    return percentile(values, 0.025), percentile(values, 0.975), len(values)


def ratio(sample):
    """Share in percent from per-task (numerator, denominator) pairs."""
    den = sum(d for _, d in sample)
    return 100.0 * sum(n for n, _ in sample) / den if den else None


def rate_diff(sample):
    """Difference of two rates in points from per-task (hits a, episodes a, hits b, episodes b)."""
    na, nb = sum(s[1] for s in sample), sum(s[3] for s in sample)
    if not na or not nb:
        return None
    return 100.0 * sum(s[0] for s in sample) / na - 100.0 * sum(s[2] for s in sample) / nb


# ---------------------------------------------------------------- outcomes

def entity_nodes(call):
    """The node names of the entities a graph answer returned, in the order returned. get_code_neighbors names its
    neighbors as <owner>/<repo>;<dotted name>: the dotted name is the node."""
    res = call.get('result')
    items = res.get(GRAPH_LIST[call['function_name']]) if isinstance(res, dict) else None
    out = []
    for e in items if isinstance(items, list) else []:
        if isinstance(e, dict):
            e = e.get('node_name', e.get('name'))
        if isinstance(e, str) and e:
            out.append(e.split(';', 1)[-1])
    return out


def next_call(row, i):
    """The first call of the model response after the i-th one (0-based), or None."""
    steps = row['steps'][:HORIZON]
    calls = calls_of(steps[i + 1]) if i is not None and i + 1 < len(steps) else []
    return calls[0] if calls else None


def ynext(row, first_only=False, any_entity=False, any_read=False, restore=True):
    """Ynext of pre-registration 09 for one episode: (has a qualifying graph answer, Ynext, index of that answer's
    model call).

    The qualifying answer is the first executed graph-tool answer that returns at least one entity the resolver
    locates (file and line range) in a file the episode has not read with read_file before that answer. Ynext is 1
    if the first call of the next model response touches one of those entities by the frozen scorer as a read or an
    edit. In arm NAF the call is scored with its line bounds restored, as it was executed.
    Other readings, for the sensitivity lines only: first_only looks at the episode's first graph answer and at no
    later one; any_entity lets the next call count on any located entity of the qualifying answer; any_read counts
    a file as read after any executed read_file on it, failed ones included; restore=False scores arm NAF as
    written.
    """
    task = row['task']
    read = set()
    for i, step in enumerate(row['steps'][:HORIZON]):
        for call in calls_of(step):
            name = call.get('function_name')
            args = call.get('arguments')
            if name in GRAPH_LIST and ok_result(call):
                located = [(node, sp) for node in entity_nodes(call) for sp in [span(task, node)] if sp is not None]
                unread = [(node, sp) for node, sp in located if sp['path'] not in read]
                if unread:
                    nxt = next_call(row, i)
                    if nxt is None:
                        return True, False, i
                    if row['arm'] == 'NAF' and restore:
                        nxt = restored(nxt)
                    hit = any(touches(nxt, sp, node, line_lengths=line_lengths(task, sp['path'])) in ('read', 'edit')
                              for node, sp in (located if any_entity else unread))
                    return True, hit, i
                if first_only:
                    return False, False, None
            if name == 'read_file' and call.get('executed') and isinstance(args, dict) \
                    and (any_read or ok_result(call)):
                read.add(norm(args.get('filepath')))
    return False, False, None


def single_file_operand(command):
    """The one file a shell command names, or None if it is not a single pipeline with exactly one file operand.

    A command with a second command (&&, ||, ;, &, a newline), a subshell, a substitution or a redirection is not a
    single-file view. Within the pipeline every word is a file operand unless it is the command word of its stage,
    an option (it starts with -), a number, or a sed print script (Np or N,Mp)."""
    if not isinstance(command, str) or '\n' in command.strip() or '`' in command or '$(' in command:
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return None
    operands = []
    command_word = True
    for w in words:
        if w and all(ch in SHELL_PUNCT for ch in w):
            if w != '|':
                return None
            command_word = True
        elif command_word:
            command_word = False
        elif not (w.startswith('-') or NUMBER.fullmatch(w) or SED_PRINT.fullmatch(w)):
            operands.append(norm(w))
    return operands[0] if len(operands) == 1 else None


def shows(call, task, path, first, last):
    """True if the frozen scorer reads this shell command as a view of lines first..last of the file (last None: of
    any line of it), its 5,000-character cap included."""
    target = {'path': path, 'start': first, 'end': last}
    return touches(call, target, NO_NODE, line_lengths=line_lengths(task, path)) == 'read'


def overlaps(first, last, regions):
    return any(first <= hi and last >= lo for lo, hi in regions)


def yline(row, gold, shell=True):
    """Yline of pre-registration 06 with every file the gold patch modifies as a target: (Yline, index of the first
    model call that shows a changed line, 'read_file' or 'shell').

    An executed read_file with status ok on a gold file whose returned start_line to end_line overlaps a changed
    region; or an executed single-file shell view with non-empty output whose line range by the frozen scorer
    overlaps a changed region."""
    task = row['task']
    for i, step in enumerate(row['steps'][:HORIZON]):
        for call in calls_of(step):
            args = call.get('arguments')
            if not ok_result(call) or not isinstance(args, dict):
                continue
            res = call['result']
            if call.get('function_name') == 'read_file':
                regions = gold.get(norm(args.get('filepath')))
                first, last = res.get('start_line'), res.get('end_line')
                if regions and isinstance(first, int) and isinstance(last, int) and overlaps(first, last, regions):
                    return True, i, 'read_file'
            elif call.get('function_name') == 'run_command' and shell and res.get('stdout'):
                path = single_file_operand(args.get('command'))
                if path in gold and any(shows(call, task, path, lo, hi) for lo, hi in gold[path]):
                    return True, i, 'shell'
    return False, None, None


def has_next(e):
    return e[1]


def has_line(e):
    return e[0]


# ---------------------------------------------------------------- report

def main():
    argv = sys.argv[1:]
    no_write = '--no-write' in argv
    episodes_out = None
    if '--episodes' in argv:
        at = argv.index('--episodes')
        if at + 1 >= len(argv):
            sys.exit(USAGE)
        episodes_out = argv[at + 1]
        del argv[at:at + 2]
    positional = [a for a in argv if a != '--no-write']
    if len(positional) != 1:
        sys.exit(USAGE)
    results = Path(positional[0]) / 'results_09.jsonl'
    if not results.exists() and (Path(positional[0]) / 'forks' / 'results_09.jsonl').exists():
        results = Path(positional[0]) / 'forks' / 'results_09.jsonl'

    with open(results, encoding='utf-8') as f:
        rows = [json.loads(line) for line in f if line.strip()]
    gold = {}
    with open(STATES, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                s = json.loads(line)
                gold[s['task']] = {norm(p): [(int(a), int(b)) for a, b in regions]
                                   for p, regions in s['gold_files'].items()}
    tasks = sorted(gold)

    out = []
    w = out.append

    def para(text, indent='  ', hang=None):
        out.extend(textwrap.wrap(text, width=WIDTH, initial_indent=indent,
                                 subsequent_indent=indent if hang is None else hang,
                                 break_long_words=False, break_on_hyphens=False))

    def item(letter, text):
        para('%s. %s' % (letter, text), indent='  ', hang='     ')

    # ---- the design
    cells, duplicates, outside = {}, 0, 0
    for r in rows:
        key = (r.get('task'), r.get('arm'), r.get('seed'))
        if key[0] not in gold or key[1] not in ARMS or key[2] not in SEEDS or r.get('population') != 'FRESH':
            outside += 1
        elif key in cells:
            duplicates += 1
        else:
            cells[key] = r
    design = [(a, s) for a in ARMS for s in SEEDS]
    present = [t for t in tasks if all((t, a, s) in cells for a, s in design)]
    complete = [t for t in present if not any(errored(cells[(t, a, s)]) for a, s in design)]
    complete_set = set(complete)
    counted = {a: [cells[(t, a, s)] for t in tasks for s in SEEDS
                   if (t, a, s) in cells and not errored(cells[(t, a, s)])] for a in ARMS}
    in_design = {a: sum(1 for k in cells if k[1] == a) for a in ARMS}
    errors = {a: in_design[a] - len(counted[a]) for a in ARMS}
    gold_tasks = [t for t in tasks if gold[t]]
    with_gold = [t for t in complete if gold[t]]
    with_gold_set = set(with_gold)

    w('Re-derivation of pre-registration 09 (rules A1 and A2) and of rule N1 of pre-registration 08 on arm N')
    para('An independent script, written from the texts of pre-registrations 06, 08 and 09 and the raw episode '
         'records, without reading the analysis script of the run or its stored outputs. It imports the frozen scorer '
         '(fork_states.touches) and the resolver (nodes.span, nodes.file_text) only.', indent='')
    w('')
    w('Inputs')
    w('  results_09.jsonl: %d episode records, md5 %s' % (len(rows), md5(results)))
    states_md5 = md5(STATES)
    w('  fresh_states.jsonl: %d tasks, md5 %s (%s)'
      % (len(tasks), states_md5, 'the hash frozen in pre-registrations 08 and 09' if states_md5 == STATES_MD5
         else 'NOT the frozen hash ' + STATES_MD5))
    para('Intervals: 95%% bootstrap clustered by task (tasks resampled with replacement), %s resamples, percentile '
         '(2.5th and 97.5th, linear interpolation between order statistics), seed %d. Own implementation.'
         % (format(RESAMPLES, ','), BOOT_SEED))
    w('')

    # ---- 1. episodes
    w('1. Episodes')
    w('  arm   in the design   ended in an error (excluded)   counted')
    for a in ARMS:
        w('  %-5s %-15d %-30d %d' % (a, in_design[a], errors[a], len(counted[a])))
    w('  %-5s %-15d %-30d %d'
      % ('all', sum(in_design.values()), sum(errors.values()), sum(len(v) for v in counted.values())))
    para('Records outside the design (unknown task, arm, seed or population): %d. Duplicates of a (task, arm, seed): '
         '%d.' % (outside, duplicates))
    para('Tasks: %d in the design, %d with all nine episodes, %d complete (all nine episodes without an error).'
         % (len(tasks), len(present), len(complete)))
    lost = ['%s (%s)' % (t, ' '.join('%s/%d' % (a, s) for a, s in design
                                     if (t, a, s) not in cells or errored(cells[(t, a, s)])))
            for t in tasks if t not in complete_set]
    para('Not complete (%d), with the arm/seed of each episode that ended in an error: %s.'
         % (len(lost), ', '.join(lost) or 'none'))
    kinds = count(str(cells[k].get('error')).split(':')[0] for k in sorted(cells) if errored(cells[k]))
    para('Errors by kind: %s. Records where the error field and the stop reason "error" disagree: %d.'
         % ('; '.join('%d %s' % (n, e) for e, n in sorted(kinds.items())) or 'none',
            sum(1 for r in cells.values() if (r.get('error') is not None) != (r.get('stop') == 'error'))))
    para('Complete tasks with at least one file the gold patch modifies: %d of %d (task without one: %s).'
         % (len(with_gold), len(complete), ', '.join(t for t in tasks if not gold[t]) or 'none'))
    para('At least %d complete tasks (pre-registration 09): %s, %d. At least %d finished fresh episodes of arm N '
         '(pre-registration 08): %s, %d.'
         % (MIN_COMPLETE_TASKS, 'met' if len(complete) >= MIN_COMPLETE_TASKS else 'NOT met', len(complete),
            MIN_FRESH_EPISODES, 'met' if len(counted['N']) >= MIN_FRESH_EPISODES else 'NOT met', len(counted['N'])))
    w('')

    # ---- 2. N1
    def n1(episodes):
        """Every executed read_file with a line bound as (task, index of the model call, mangled names, call), and
        the per-task (mangled, ranged) pairs of all tasks that have an episode here."""
        found = []
        per_task = {r['task']: [0, 0] for r in episodes}
        for r in episodes:
            for i, step in enumerate(r['steps']):
                for call in calls_of(step):
                    args = call.get('arguments')
                    if call.get('function_name') == 'read_file' and call.get('executed') and isinstance(args, dict) \
                            and bound_names(args):
                        bad = mangled_names(args)
                        found.append((r['task'], i, bad, call))
                        per_task[r['task']][1] += 1
                        per_task[r['task']][0] += bool(bad)
        return found, [tuple(per_task[t]) for t in sorted(per_task)]

    reads, n1_clusters = n1(counted['N'])
    bad_reads = [x for x in reads if x[2]]
    all_reads_n = sum(1 for r in counted['N'] for step in r['steps'] for c in calls_of(step)
                      if c.get('function_name') == 'read_file' and c.get('executed'))
    n1_lo, n1_hi, used = boot_ci(n1_clusters, ratio)
    n1_met = n1_lo > N1_THRESHOLD
    w('2. N1 (pre-registration 08), arm N, the %d counted episodes' % len(counted['N']))
    para('Executed read_file calls: %d. With a line bound (ranged reads): %d. With a mangled bound name: %d.'
         % (all_reads_n, len(reads), len(bad_reads)))
    para('Share of ranged reads with a mangled bound name: %s, 95%% interval [%.2f%%, %.2f%%] by task (%d tasks, %d '
         'of them with a ranged read and %d with a mangled one; %s resamples used).'
         % (pct(len(bad_reads), len(reads)), n1_lo, n1_hi, len(n1_clusters), sum(1 for c in n1_clusters if c[1]),
            sum(1 for c in n1_clusters if c[0]), format(used, ',')))
    para('Verdict: "%s" (the lower bound, %.2f%%, is %s %.1f%%, the share in the 318 original traces, 42 of 2,012).'
         % ('The defect occurs in fresh episodes' if n1_met else "not shown above the original traces' share", n1_lo,
            'above' if n1_met else 'not above', N1_THRESHOLD))
    names = count(k for x in reads for k in x[2])
    para('Mangled names: %s.' % ', '.join('%s in %d reads' % (k, n) for k, n in sorted(names.items())))
    from_one = [x for x in bad_reads if ok_result(x[3]) and x[3]['result'].get('start_line') == 1]
    asked_later = [x for x in from_one if any(reads_as(k) == 'start_line' and isinstance(x[3]['arguments'][k], int)
                                               and x[3]['arguments'][k] > 1 for k in x[2])]

    def how(x):
        if not ok_result(x[3]):
            return 'status %s' % (x[3].get('result') or {}).get('status')
        start = x[3]['result'].get('start_line')
        if 'start_line' in x[3]['arguments']:
            return 'status ok from line %s, where start_line is well-formed and only end_line is mangled' % start
        return 'status ok from line %s' % start

    not_one = count(how(x) for x in bad_reads if x not in from_one)
    para('Of the %d mangled reads, %d returned the file from line 1 (status ok, returned start_line 1); in %d of '
         'those the model had written a start past line 1 under the mangled name. The other %d: %s.'
         % (len(bad_reads), len(from_one), len(asked_later), len(bad_reads) - len(from_one),
            '; '.join('%d %s' % (n, k) for k, n in sorted(not_one.items())) or 'none'))
    first = [x for x in reads if x[1] == 0]
    later = [x for x in reads if x[1] > 0]
    para('At the first model call: %s. At later calls: %s.'
         % (pct(sum(1 for x in first if x[2]), len(first)), pct(sum(1 for x in later if x[2]), len(later))))
    w('')

    # ---- per-episode outcomes
    y = {}
    for a in ARMS:
        for r in counted[a]:
            y[(r['task'], a, r['seed'])] = {'next': ynext(r), 'line': yline(r, gold[r['task']])}

    def table(kind, pick, tasks_in):
        """Per arm over the counted episodes of tasks_in: (arm, episodes, episodes with the outcome, the values)."""
        keep = set(tasks_in)
        result = []
        for a in ARMS:
            eps = [y[(r['task'], a, r['seed'])][kind] for r in counted[a] if r['task'] in keep]
            result.append((a, len(eps), sum(1 for e in eps if pick(e)), eps))
        return result

    def clusters_of(kind, pick, arm_a, arm_b, tasks_in):
        """Per task: (hits arm_a, episodes arm_a, hits arm_b, episodes arm_b)."""
        result = []
        for t in tasks_in:
            ea = [pick(y[(t, arm_a, s)][kind]) for s in SEEDS if (t, arm_a, s) in y]
            eb = [pick(y[(t, arm_b, s)][kind]) for s in SEEDS if (t, arm_b, s) in y]
            result.append((sum(ea), len(ea), sum(eb), len(eb)))
        return result

    def contrast(kind, pick, arm_a, arm_b, tasks_in):
        """arm_a minus arm_b over the episodes of tasks_in, as text: points, counts, interval and the tasks' signs."""
        cl = clusters_of(kind, pick, arm_a, arm_b, tasks_in)
        low, high, _ = boot_ci(cl, rate_diff)
        ahead = sum(1 for c in cl if c[0] * c[3] > c[2] * c[1])
        behind = sum(1 for c in cl if c[0] * c[3] < c[2] * c[1])
        text = ('%+.2f points (%d of %d against %d of %d), 95%% interval [%+.2f, %+.2f] by task; tasks with %s ahead '
                '%d, with %s ahead %d, level %d'
                % (rate_diff(cl), sum(c[0] for c in cl), sum(c[1] for c in cl), sum(c[2] for c in cl),
                   sum(c[3] for c in cl), low, high, arm_a, ahead, arm_b, behind, len(cl) - ahead - behind))
        return text, low, '%+.2f [%+.2f, %+.2f]' % (rate_diff(cl), low, high)

    # ---- 3. A1
    w('3. A1 (pre-registration 09): Ynext, the first call after the qualifying graph answer reads a returned entity')
    for label, tasks_in in (('all counted episodes', tasks),
                            ('the episodes of the %d complete tasks' % len(complete), complete)):
        w('  Per arm, %s:' % label)
        w('    arm   episodes   qualifying answer      Ynext = 1   rate over episodes     '
          'rate among episodes with such an answer')
        for a, n, hits, eps in table('next', has_next, tasks_in):
            has = sum(1 for e in eps if e[0])
            w('    %-5s %-10d %-22s %-11d %-22s %s' % (a, n, pct(has, n), hits, pct(hits, n), pct(hits, has)))
    text, a1_lo, _ = contrast('next', has_next, 'NA', 'N', complete)
    para('NA minus N over all episodes of the %d complete tasks: %s.' % (len(complete), text))
    para('Verdict: "%s" (the lower bound, %+.2f, is %s 0).'
         % ("Addresses in the graph tools' own answers bring the next call to a returned entity's code" if a1_lo > 0
            else 'no detectable difference', a1_lo, 'above' if a1_lo > 0 else 'not above'))
    para('Beside it, no rule: NAF minus N %s.' % contrast('next', has_next, 'NAF', 'N', complete)[0])
    w('')

    # ---- 4. A2
    w('4. A2 (pre-registration 09): Yline, shown a line the gold patch changes within the eight calls')
    for label, tasks_in in (('all counted episodes of the %d tasks with a gold file' % len(gold_tasks), gold_tasks),
                            ('the episodes of the %d complete tasks with a gold file' % len(with_gold), with_gold)):
        w('  Per arm, %s:' % label)
        w('    arm   episodes   Yline = 1   rate                    first shown by read_file / by a shell view')
        for a, n, hits, eps in table('line', has_line, tasks_in):
            w('    %-5s %-10d %-11d %-23s %d / %d' % (a, n, hits, pct(hits, n),
                                                     sum(1 for e in eps if e[2] == 'read_file'),
                                                     sum(1 for e in eps if e[2] == 'shell')))
    text, a2_lo, _ = contrast('line', has_line, 'NAF', 'N', with_gold)
    para('NAF minus N over the %d complete tasks with at least one gold file: %s.' % (len(with_gold), text))
    para('Verdict: "%s" (the lower bound, %+.2f, is %s 0).'
         % ("The patched harness brings the agent to the fix's lines within eight calls of a fresh start" if a2_lo > 0
            else 'no detectable gain', a2_lo, 'above' if a2_lo > 0 else 'not above'))
    para('Beside it, no rule: NA minus N %s.' % contrast('line', has_line, 'NA', 'N', with_gold)[0])
    w('')

    # ---- 5. judgment calls, each with what it changes
    def per_arm(kind):
        return ', '.join('%s %d of %d' % (a, hits, n) for a, n, hits, _ in table(kind, has_next, complete))

    def qualifying(kind):
        return ', '.join('%s %d' % (a, sum(1 for e in eps if e[0])) for a, _, _, eps in table(kind, has_next, complete))

    def other_reading(**kw):
        for a in ARMS:
            for r in counted[a]:
                y[(r['task'], a, r['seed'])]['alt'] = ynext(r, **kw)
        return per_arm('alt'), qualifying('alt'), contrast('alt', has_next, 'NA', 'N', complete)[2]

    main_hits, main_qual = per_arm('next'), qualifying('next')
    b_hits, b_qual, b_diff = other_reading(first_only=True)
    e_hits, _, e_diff = other_reading(any_entity=True)
    r_hits, r_qual, r_diff = other_reading(any_read=True)

    def executed_calls(name):
        return [(r, c) for a in ARMS for r in counted[a] for step in r['steps'] for c in calls_of(step)
                if c.get('function_name') == name and c.get('executed') and isinstance(c.get('arguments'), dict)]

    graph_calls = [x for name in sorted(GRAPH_LIST) for x in executed_calls(name)]
    tools = count(c['function_name'] for _, c in graph_calls)
    printed = agree = located_n = unlocated = modules = 0
    for r, c in graph_calls:
        res = c.get('result') if isinstance(c.get('result'), dict) else {}
        items = res.get(GRAPH_LIST[c['function_name']])
        for e, node in zip(items if isinstance(items, list) else [], entity_nodes(c)):
            sp = span(r['task'], node)
            located_n += sp is not None
            unlocated += sp is None
            modules += sp is not None and sp['end'] is None
            if isinstance(e, dict) and ('file' in e or 'lines' in e):
                printed += 1
                agree += (sp is not None and e.get('file') == sp['path']
                          and e.get('lines') == '%s-%s' % (sp['start'], sp['end']))
    most_calls = max([len(calls_of(step)) for a in ARMS for r in counted[a] for step in r['steps']] or [0])

    read_calls = executed_calls('read_file')

    def path_of(c):
        return norm(c['arguments'].get('filepath'))

    arg_names = count(k for _, c in read_calls for k in c['arguments'])
    changed_paths = sum(1 for _, c in read_calls if path_of(c) != c['arguments'].get('filepath'))
    in_path = [(r, c) for r, c in read_calls if path_of(c) is not None and BOUND_IN_PATH.search(path_of(c))]
    cut = [(r, c) for r, c in read_calls if ok_result(c) and isinstance(c['result'].get('content_lines'), int)
           and c['result']['content_lines'] < c['result']['end_line'] - c['result']['start_line'] + 1]
    cut_gold = sum(1 for r, c in cut if path_of(c) in gold[r['task']])
    naf_mangled = [(r, c) for r, c in read_calls if r['arm'] == 'NAF' and mangled_names(c['arguments'])]
    naf_ok = [(r, c) for r, c in naf_mangled if ok_result(c)]
    naf_start = sum(1 for r, c in naf_ok
                    if c['result'].get('start_line') == (restored(c)['arguments'].get('start_line') or 1))
    stock_ok = [(r, c) for r, c in read_calls if r['arm'] != 'NAF' and ok_result(c)
                and any(reads_as(k) == 'start_line' for k in mangled_names(c['arguments']))]
    stock_one = sum(1 for r, c in stock_ok if c['result'].get('start_line') == 1)

    def mangled_after_answer(r):
        e = y[(r['task'], r['arm'], r['seed'])]['next']
        c = next_call(r, e[2]) if e[0] else None
        return bool(c and c.get('function_name') == 'read_file' and isinstance(c.get('arguments'), dict)
                    and mangled_names(c['arguments']))

    mangled_next = {a: sum(1 for r in counted[a] if mangled_after_answer(r)) for a in ARMS}
    naf_as_written = sum(1 for r in counted['NAF']
                         if ynext(r, restore=False)[1] != y[(r['task'], 'NAF', r['seed'])]['next'][1])
    known = [(r, c) for r, c in read_calls if ok_result(c) and isinstance(c['result'].get('total_lines'), int)
             and line_lengths(r['task'], path_of(c)) is not None]
    same_total = sum(1 for r, c in known if len(line_lengths(r['task'], path_of(c))) == c['result']['total_lines'])

    shell_calls = [(r, c) for r, c in executed_calls('run_command') if ok_result(c) and c['result'].get('stdout')]
    views = views_hit = beyond = beyond_hit = 0
    for r, c in shell_calls:
        one = single_file_operand(c['arguments'].get('command'))
        for path, regions in gold[r['task']].items():
            if not shows(c, r['task'], path, 1, None):
                continue
            hit = any(shows(c, r['task'], path, lo, hi) for lo, hi in regions)
            if path == one:
                views += 1
                views_hit += hit
            else:
                beyond += 1
                beyond_hit += hit
    shell_only = {a: sum(1 for r in counted[a] if r['task'] in with_gold_set and y[(r['task'], a, r['seed'])]['line'][0]
                         and not yline(r, gold[r['task']], shell=False)[0]) for a in ARMS}

    nc_reads, nc_clusters = n1([r for r in counted['N'] if r['task'] in complete_set])
    nc_lo, nc_hi, _ = boot_ci(nc_clusters, ratio)
    with_read = [cl for cl in n1_clusters if cl[1]]
    wr_lo, wr_hi, _ = boot_ci(with_read, ratio)

    a1_clusters = clusters_of('next', has_next, 'NA', 'N', complete)
    a2_clusters = clusters_of('line', has_line, 'NAF', 'N', with_gold)
    def over_seeds(clusters, stat, form):
        """How far the two bounds of an interval move over OTHER_SEEDS, as text."""
        bounds = [boot_ci(clusters, stat, seed) for seed in OTHER_SEEDS]
        lows, highs = [b[0] for b in bounds], [b[1] for b in bounds]
        return ('lower ' + form + ' to ' + form + ', upper ' + form + ' to ' + form) \
            % (min(lows), max(lows), min(highs), max(highs))

    seeds_n1 = over_seeds(n1_clusters, ratio, '%.2f%%')
    seeds_a1 = over_seeds(a1_clusters, rate_diff, '%+.2f')
    seeds_a2 = over_seeds(a2_clusters, rate_diff, '%+.2f')

    w('5. Judgment calls, where the pre-registrations left room, each with what it changes')
    item('a', 'Ynext, "a first graph answer that returns at least one entity ...": read as the first graph answer of '
              'the episode that returns such an entity; an earlier answer without one (an empty search, or entities '
              'only in files already read) does not close the episode. Complete tasks, Ynext = 1: %s; episodes with a '
              'qualifying answer: %s. Other reading, only the first graph answer of the episode can qualify: %s; with '
              'a qualifying answer: %s; NA minus N %s.' % (main_hits, main_qual, b_hits, b_qual, b_diff))
    item('b', 'Ynext, "reads that entity": the next call must touch an entity of that answer that lies in a file not '
              'yet read with read_file. If any located entity of the answer counted: %s; NA minus N %s.'
         % (e_hits, e_diff))
    item('c', 'Ynext, "a file the episode has not read with read_file": no executed read_file with status ok on that '
              'file before the answer; shell views do not count as reads. If failed reads counted too: %s; with a '
              'qualifying answer: %s; NA minus N %s.' % (r_hits, r_qual, r_diff))
    item('d', 'Ynext, "an entity with a line range": the resolver (nodes.span) applied to the returned name, in every '
              'arm, so that the outcome is defined alike with and without printed addresses. Executed graph-tool '
              'calls in counted episodes: %s; there is no get_code_subgraph call, so that path of this script is '
              'untested. Returned entities: %d located, %d not, %d located as a whole module without a line range. '
              'Addresses printed in the answers of NA and NAF that equal the resolver file and lines: %d of %d.'
         % (', '.join('%d %s' % (n, k) for k, n in sorted(tools.items())) or 'none', located_n, unlocated, modules,
            agree, printed))
    item('e', 'Ynext counts the frozen scorer answers "read" and "edit" on the first call of the next model response, '
              'executed or not (an edit ends the episode before it runs); "graph" does not count. The scorer is given '
              'the line lengths of the entity file, so its 150-line and 10,000-character caps of read_file and its '
              '5,000-character cap of shell output apply. The most calls in one model response of a counted episode: '
              '%d.' % most_calls)
    item('f', 'Scored as executed. Arms N and NA: the call goes to the scorer as written, and the scorer, like the '
              'stock harness, ignores a bound under a mangled name (records: of %d reads of N and NA with status ok '
              'and a mangled start_line name, %d returned from line 1). Arm NAF: mangled bound names are given their '
              'plain name first, a well-formed name winning (records: %d reads of NAF with a mangled name in counted '
              'episodes against %d restored calls logged by the run for them; the returned start_line equals the '
              'restored start in %d of the %d with status ok). In this run the clause decides nothing for Ynext: the '
              'first call after the qualifying answer carries a mangled bound name in %s episodes, and scoring arm '
              'NAF as written changes Ynext in %d.'
         % (len(stock_ok), stock_one, len(naf_mangled), sum(r.get('restored_calls') or 0 for r in counted['NAF']),
            naf_start, len(naf_ok), ', '.join('%s %d' % (a, mangled_next[a]) for a in ARMS), naf_as_written))
    item('g', 'N1 population: every arm-N episode without an error (pre-registration 08), not only those of complete '
              'tasks. On the complete tasks alone: %s, [%.2f%%, %.2f%%].'
         % (pct(sum(1 for x in nc_reads if x[2]), len(nc_reads)), nc_lo, nc_hi))
    item('h', 'N1 interval: the resampled clusters are all %d tasks with a counted arm-N episode, those without a '
              'ranged read included. Resampling only the %d tasks with a ranged read: [%.2f%%, %.2f%%].'
         % (len(n1_clusters), len(with_read), wr_lo, wr_hi))
    item('i', 'N1, mangled: a read counts once, and it is mangled if any of its bound names is not a plain '
              'identifier. Quotes are " and \'. Argument names of all executed read_file calls in counted episodes, '
              'all arms: %s.' % ', '.join('%s %d' % (k, n) for k, n in sorted(arg_names.items())))
    item('j', 'N1 counts argument names. A read whose filepath value swallowed the bounds (start_line or end_line '
              'inside the path) has no bound name and is not a ranged read: %s such reads; %d of them returned status '
              'ok.' % (', '.join('%s %d' % (a, sum(1 for r, _ in in_path if r['arm'] == a)) for a in ARMS),
                       sum(1 for _, c in in_path if ok_result(c))))
    item('k', 'N1 threshold: 2.1%% as the rule states it; the share behind it, 42 of 2,012, is %.4f%%.'
         % (100.0 * 42 / 2012))
    item('l', 'Yline, read_file: the range the harness returned, on the path the call names. In %d reads with status '
              'ok the 10,000-character cap returned fewer lines than that range; %d of them on a gold file.'
         % (len(cut), cut_gold))
    item('m', 'Yline, single-file shell view: one pipeline (no second command, subshell, substitution or redirection) '
              'whose only file operand is a gold file, executed with status ok and non-empty output; its lines are '
              'the frozen scorer range. Such views in counted episodes: %d, %d of them over a changed region. '
              'Commands that the scorer alone would read as a view of a gold file but that this rule leaves out: %d '
              '(%d over a changed region). Episodes of complete tasks whose Yline rests on a shell view alone: %s.'
         % (views, views_hit, beyond, beyond_hit, ', '.join('%s %d' % (a, shell_only[a]) for a in ARMS)))
    item('n', 'Paths: a leading ./ or /workspace/ is dropped. It changed %d of %d read_file paths.'
         % (changed_paths, len(read_calls)))
    item('o', 'Line lengths for the scorer caps: the snapshot text split at newlines, a final newline opening no '
              'further line. That line count equals the total_lines the harness returned in %d of %d reads with '
              'status ok of a file the resolver has text for.' % (same_total, len(known)))
    item('p', 'Rates per arm are given over all counted episodes and over the complete tasks; the contrasts use '
              'complete tasks only, with the three seeds of a task in one cluster.')
    item('q', 'Bootstrap seed. One episode is %.2f points of A1 and %.2f of A2, so a bound moves in such steps with '
              'the seed. The bounds over seeds %d to %d: N1 %s; A1 %s; A2 %s.'
         % (100.0 / max(sum(c[1] for c in a1_clusters), 1), 100.0 / max(sum(c[1] for c in a2_clusters), 1),
            OTHER_SEEDS[0], OTHER_SEEDS[-1], seeds_n1, seeds_a1, seeds_a2))

    text = '\n'.join(out) + '\n'
    sys.stdout.write(text)
    if not no_write:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    if episodes_out:
        with open(episodes_out, 'w', encoding='utf-8', newline='\n') as f:
            for a in ARMS:
                for r in counted[a]:
                    e = y[(r['task'], a, r['seed'])]
                    f.write(json.dumps({
                        'task': r['task'], 'arm': a, 'seed': r['seed'], 'complete_task': r['task'] in complete_set,
                        'qualifying_answer': e['next'][0], 'ynext': e['next'][1], 'answer_call': e['next'][2],
                        'yline': e['line'][0], 'yline_call': e['line'][1], 'yline_by': e['line'][2]}) + '\n')


if __name__ == '__main__':
    main()
