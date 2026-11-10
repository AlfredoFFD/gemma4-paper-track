"""Independent re-derivation of the registered results of pre-registration 08, parts "fix" (G1 to G3) and "one step" (S1).

Written blind: from the raw per-replay outputs, the frozen state and population files and the two pre-registration
texts (08, and 06 for the outcome definitions), without reading the project's own analysis of this experiment.
Imports only the frozen scorer `fork_states.touches`, the frozen malformed-call rule `fork_states.valid_call`, and
`nodes.file_text` (snapshot file contents, for the line lengths that make the scorer's character caps exact).

Usage: py -I -X utf8 analysis/rederive_g.py <fix_run_dir> <onestep_run_dir> [--no-write]
Each run dir may be the folder holding the results file or its parent (a `forks/` subfolder is searched).
Writes analysis/results/rederive_g.txt (LF) unless --no-write; prints the same text either way.
"""
import json
import random
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from fork_states import touches, valid_call  # noqa: E402
from nodes import file_text  # noqa: E402

STATES = ROOT / 'analysis' / 'fork_states_d' / 'states.jsonl'
POPULATION = ROOT / 'analysis' / 'fork_states_k' / 'population.json'
OUT = ROOT / 'analysis' / 'results' / 'rederive_g.txt'

KNOWN_TOOLS = {'read_file', 'edit_file', 'write_file', 'run_command', 'get_status', 'submit_patch',
               'get_code_neighbors', 'search_similar_code', 'get_code_subgraph'}
FIX_ARMS = ('A', 'AF', 'EF')
FIX_SEEDS = {'R': (11, 12, 13, 14, 15), 'U': (11, 12, 13)}
ONESTEP_ARMS = ('H', 'E')
ONESTEP_SEEDS = (1, 2, 3)
B = 2000
BOOT_SEED = 80808  # this script's own seed, not the project's
NO_NODE = '\x00no-node\x00'  # a node name no command can contain: a grep stage never counts (target files have no node)


# ---------------------------------------------------------------- helpers

def npath(p):
    """Harness path equivalence: a/b.py, ./a/b.py and /workspace/a/b.py are one file."""
    if not isinstance(p, str):
        return p
    p = p.strip()
    changed = True
    while changed:
        changed = False
        for pre in ('/workspace/', 'workspace/', './'):
            if p.startswith(pre):
                p = p[len(pre):]
                changed = True
    return p


_LL = {}


def line_lengths(task, path):
    """Characters per line (newline excluded) of a snapshot file, or None if the file text is not available."""
    k = (task, path)
    if k not in _LL:
        txt = file_text(task, path)
        if txt is None:
            _LL[k] = None
        else:
            lines = txt.split('\n')
            if lines and lines[-1] == '':
                lines = lines[:-1]
            _LL[k] = [len(x) for x in lines]
    return _LL[k]


PATHLIKE = re.compile(r'[/*?\[]|\.\w+$')


def single_file(cmd):
    """True if no stage of the pipeline names more than one file operand and only one file is named overall.

    A file operand is a non-option token that looks like a path (has a slash, a glob character or an extension).
    Recursive flags (-r, -R, --recursive) or a glob make the command multi-file.
    """
    files = set()
    for st in cmd.split('|'):
        st = st.strip()
        if not st:
            continue
        try:
            toks = shlex.split(st)
        except ValueError:
            toks = st.split()
        if not toks:
            continue
        for t in toks[1:]:
            if t in ('-r', '-R', '--recursive') or (t.startswith('-') and not t.startswith('--')
                                                     and ('r' in t[1:] or 'R' in t[1:]) and toks[0] in ('grep', 'rg')):
                return False
            if t.startswith('-'):
                continue
            if any(ch in t for ch in '*?['):
                return False
            if PATHLIKE.search(t) and not re.fullmatch(r"\d+(,\d+)?p", t):
                files.add(npath(t))
    return len(files) == 1


def stdout_of(res):
    if not isinstance(res, dict):
        return ''
    out = res.get('stdout')
    if out is None and isinstance(res.get('details'), dict):
        out = res['details'].get('stdout')
    return out or ''


def pct(k, n):
    return f'{100.0 * k / n:5.1f}% ({k}/{n})' if n else '   n/a (0/0)'


def boot_diff(clusters, seed=BOOT_SEED, b=B):
    """clusters: list of (sum_x, sum_y, n). Percentile 95% interval of sum(x)/sum(n) - sum(y)/sum(n) over
    resamples of clusters with replacement. Returns (point, lo, hi) in percentage points."""
    sx = sum(c[0] for c in clusters)
    sy = sum(c[1] for c in clusters)
    sn = sum(c[2] for c in clusters)
    point = 100.0 * (sx - sy) / sn
    rng = random.Random(seed)
    m = len(clusters)
    ds = []
    for _ in range(b):
        ax = ay = an = 0
        for _ in range(m):
            c = clusters[rng.randrange(m)]
            ax += c[0]
            ay += c[1]
            an += c[2]
        ds.append(100.0 * (ax - ay) / an)
    ds.sort()
    return point, ds[int(0.025 * b)], ds[int(0.975 * b) - 1]


def fmt_ci(t):
    return f'{t[0]:+6.2f} [{t[1]:+6.2f}, {t[2]:+6.2f}]'


def find_file(run_dir, name):
    d = Path(run_dir)
    for cand in (d / name, d / 'forks' / name):
        if cand.exists():
            return cand
    raise SystemExit(f'{name} not found under {run_dir}')


def wheels(run_dir, name):
    try:
        v = json.loads(find_file(run_dir, name).read_text(encoding='utf-8'))
    except SystemExit:
        return 'versions file not found'
    w = [x for x in v.get('wheelhouse_files', []) if x.startswith(('adk_submission', 'swegemma', 'adk_eval_core'))]
    return f"harness_variant={v.get('harness_variant')}; " + ', '.join(sorted(w))


# ---------------------------------------------------------------- part "fix"

def iface_fix(r):
    if r.get('error'):
        return 'error'
    steps = r.get('steps') or []
    if not steps or not steps[0].get('calls'):
        return 'no call in first response'
    c = steps[0]['calls'][0]
    if c.get('function_name') not in KNOWN_TOOLS:
        return 'unknown tool'
    if not valid_call({'function_name': c.get('function_name'), 'arguments': c.get('arguments')}):
        return 'malformed arguments'
    return None


IFACE_KINDS = ('error', 'no call in first response', 'unknown tool', 'malformed arguments')


def outcomes_fix(r, member, notes):
    """(Yline, Yfile) of one replay within its horizon, by the definitions of pre-registration 06."""
    task = r['task']
    targets = [npath(p) for p in member['unopened_gold_files']]
    regions = {npath(p): [tuple(x) for x in v] for p, v in member['gold_files'].items()}
    yline = yfile = 0
    for s in r.get('steps') or []:
        for c in s.get('calls') or []:
            fn = c.get('function_name')
            res = c.get('result')
            call = {'function_name': fn, 'arguments': c.get('arguments')}
            if c.get('executed'):
                if fn == 'read_file' and isinstance(res, dict) and res.get('status') == 'ok':
                    p = npath(res.get('filepath') or (c.get('arguments') or {}).get('filepath'))
                    if p in targets:
                        yfile = 1
                        a, b = res.get('start_line'), res.get('end_line')
                        if any(a <= hi and b >= lo for lo, hi in regions.get(p, [])):
                            yline = 1
                elif fn == 'run_command':
                    out = stdout_of(res)
                    cmd = str((c.get('arguments') or {}).get('command', ''))
                    for tf in targets:
                        ll = line_lengths(task, tf)
                        whole = touches(call, {'path': tf, 'start': 1, 'end': None}, NO_NODE, line_lengths=ll)
                        if whole != 'read':
                            continue
                        if not out:
                            notes['shell view of a target file with empty output (not counted)'] += 1
                            continue
                        yfile = 1
                        notes['shell views of a target file counted for Yfile'] += 1
                        hit = any(touches(call, {'path': tf, 'start': lo, 'end': hi}, NO_NODE, line_lengths=ll) == 'read'
                                  for lo, hi in regions.get(tf, []))
                        if hit:
                            if single_file(cmd):
                                yline = 1
                                notes['shell views counted for Yline'] += 1
                            else:
                                notes['multi-file shell views overlapping a changed region (Yfile only)'] += 1
            else:
                if fn in ('edit_file', 'write_file'):
                    for tf in targets:
                        if touches(call, {'path': tf, 'start': 1, 'end': None}, NO_NODE) == 'edit':
                            yfile = 1
                            notes['stopping edit/write on a target file counted for Yfile'] += 1
    return yline, yfile


def part_fix(fix_dir, L):
    import collections
    rows = [json.loads(x) for x in find_file(fix_dir, 'results_g.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    pop = json.loads(POPULATION.read_text(encoding='utf-8'))
    member = {}
    for p in ('R', 'U'):
        for m in pop[p]:
            member[tuple(m['key'])] = (p, m)
    notes = collections.Counter()

    L.append('PART "fix" (pre-registration 08, rules G1 to G3)')
    L.append(f'  raw file: {len(rows)} replay rows; ' + wheels(fix_dir, 'versions_g.json'))
    variants = collections.Counter(r.get('harness_variant') for r in rows)
    L.append(f'  harness_variant per row: {dict(sorted(variants.items()))}; fake_model rows: '
             f'{sum(1 for r in rows if r.get("fake_model"))}')

    # per replay
    rec = {}  # (state, arm, seed) -> dict
    dup = 0
    popmismatch = 0
    for r in rows:
        key = (r['task'], r['run'], r['fork'])
        p, m = member[key]
        if r.get('population') != p:
            popmismatch += 1
        k = (key, r['arm'], r['seed'])
        if k in rec:
            dup += 1
        f = iface_fix(r)
        yl, yf = outcomes_fix(r, m, notes) if f is None else (None, None)
        rec[k] = {'pop': p, 'iface': f, 'yline': yl, 'yfile': yf, 'task': r['task'],
                  'restored': r.get('restored_calls') or 0}
    L.append(f'  duplicate (state, arm, seed) rows: {dup}; rows whose population field disagrees with population.json: '
             f'{popmismatch}')

    # design and seeds that ran
    ran = collections.defaultdict(set)
    for (key, arm, seed), v in rec.items():
        ran[v['pop']].add(seed)
    L.append('  seeds that ran: ' + '; '.join(f'{p} {sorted(ran[p])}' for p in ('R', 'U')))

    L.append('')
    L.append('  Interface failures and usable replays (design = states x arms x seeds of the population)')
    L.append('    pop arm  design  error  no-call  unknown-tool  malformed  usable')
    for p in ('R', 'U'):
        states_p = [tuple(m['key']) for m in pop[p]]
        for arm in FIX_ARMS:
            design = len(states_p) * len(FIX_SEEDS[p])
            cnt = collections.Counter()
            present = 0
            for st in states_p:
                for sd in FIX_SEEDS[p]:
                    v = rec.get((st, arm, sd))
                    if v is None:
                        cnt['missing'] += 1
                        continue
                    present += 1
                    cnt[v['iface'] or 'usable'] += 1
            miss = f'  (missing rows {cnt["missing"]})' if cnt['missing'] else ''
            L.append(f'    {p}   {arm:<3}  {design:6d}  {cnt["error"]:5d}  {cnt["no call in first response"]:7d}  '
                     f'{cnt["unknown tool"]:12d}  {cnt["malformed arguments"]:9d}  {cnt["usable"]:6d}{miss}')

    # complete states
    complete = {}
    for p in ('R', 'U'):
        complete[p] = []
        for m in pop[p]:
            st = tuple(m['key'])
            ok = all(rec.get((st, arm, sd)) is not None and rec[(st, arm, sd)]['iface'] is None
                     for arm in FIX_ARMS for sd in FIX_SEEDS[p])
            if ok:
                complete[p].append(st)
    nR, nU = len(complete['R']), len(complete['U'])
    tasks_R = len({s[0] for s in complete['R']})
    tasks_U = len({s[0] for s in complete['U']})
    tasks_RU = len({s[0] for s in complete['R'] + complete['U']})
    L.append('')
    L.append(f'  Complete states (all 3 arms x every seed of the population usable): R {nR} of {len(pop["R"])} '
             f'({tasks_R} tasks), U {nU} of {len(pop["U"])} ({tasks_U} tasks), together {nR + nU} ({tasks_RU} tasks)')
    applies = (nR + nU) >= 100 and nR >= 40
    L.append(f'  Partial-run rule (>= 100 complete states, >= 40 in R): '
             f'{"met, the rules apply" if applies else "NOT met, everything is EXPLORATORY"}')

    # rates on complete states
    L.append('')
    L.append('  Rates on complete states (each population with all its seeds)')
    L.append('    pop arm  Yline                 Yfile')
    for p in ('R', 'U'):
        for arm in FIX_ARMS:
            vs = [rec[(st, arm, sd)] for st in complete[p] for sd in FIX_SEEDS[p]]
            n = len(vs)
            L.append(f'    {p}   {arm:<3}  {pct(sum(v["yline"] for v in vs), n):<20}  {pct(sum(v["yfile"] for v in vs), n)}')
    L.append('  Rates on complete states of R and U together, seeds 11 to 13')
    for arm in FIX_ARMS:
        vs = [rec[(st, arm, sd)] for p in ('R', 'U') for st in complete[p] for sd in (11, 12, 13)]
        n = len(vs)
        L.append(f'    R+U {arm:<3}  {pct(sum(v["yline"] for v in vs), n):<20}  {pct(sum(v["yfile"] for v in vs), n)}')

    def contrast(states, seeds, x, y, outcome='yline'):
        by_state, by_task = [], {}
        nx = ny = 0
        for st in states:
            sx = sum(rec[(st, x, sd)][outcome] for sd in seeds)
            sy = sum(rec[(st, y, sd)][outcome] for sd in seeds)
            n = len(seeds)
            nx += sx
            ny += sy
            by_state.append((sx, sy, n))
            t = by_task.setdefault(st[0], [0, 0, 0])
            t[0] += sx
            t[1] += sy
            t[2] += n
        tasks = [tuple(by_task[k]) for k in sorted(by_task)]
        return (nx, ny, len(states) * len(seeds), len(states), len(tasks),
                boot_diff(by_state), boot_diff(tasks))

    L.append('')
    L.append(f'  Contrasts on Yline (difference in points; 95% percentile bootstrap, {B} resamples, seed {BOOT_SEED})')
    rules = []
    allRU = sorted(complete['R']) + sorted(complete['U'])
    g1 = contrast(allRU, (11, 12, 13), 'EF', 'A')
    g2 = contrast(allRU, (11, 12, 13), 'AF', 'A')
    g3 = contrast(sorted(complete['R']), FIX_SEEDS['R'], 'EF', 'AF')
    for name, desc, c in (('G1', 'EF - A, R+U, seeds 11-13', g1),
                          ('G2', 'AF - A, R+U, seeds 11-13', g2),
                          ('G3', 'EF - AF, R, seeds 11-15', g3)):
        xk, yk, n, ns, nt, cs, ct = c
        L.append(f'    {name} {desc}: {xk}/{n} vs {yk}/{n}  ({ns} states, {nt} tasks)')
        L.append(f'       clustered by state: {fmt_ci(cs)}')
        L.append(f'       clustered by task:  {fmt_ci(ct)}')
        rules.append((name, cs, ct))
    L.append('')
    L.append('  Verdicts (in the pre-registration\'s words' + ('' if applies else '; EXPLORATORY, partial-run rule not met') + ')')
    _, cs, ct = rules[0]
    if cs[1] > 0:
        rob = 'robust (task-clustered lower bound also above 0)' if ct[1] > 0 else \
            'not called robust (task-clustered lower bound not above 0)'
        L.append(f'    G1: "The two changes together bring the agent to the fix\'s lines within five calls"; {rob}')
    else:
        L.append('    G1: "no detectable gain from the two changes together"')
    _, cs, ct = rules[1]
    L.append('    G2: ' + ('"Honoring the bound alone raises reach within five calls"' if cs[1] > 0
                            else '"no detectable gain from the argument fix alone"'))
    _, cs, ct = rules[2]
    L.append('    G3: ' + ('"The legible list adds reach beyond the argument fix"' if cs[1] > 0
                            else '"no detectable gain from the list once the bound is honored"')
             + f' (state clustering; by task the lower bound is {ct[1]:+.2f})')

    L.append('')
    L.append('  Scoring notes (counts over usable replays of every state, complete or not)')
    for k in sorted(notes):
        L.append(f'    {k}: {notes[k]}')
    restored = collections.Counter()
    for (key, arm, seed), v in rec.items():
        restored[arm] += v['restored']
    L.append('    restored_calls field summed by arm (all rows): ' + ', '.join(f'{a} {restored[a]}' for a in FIX_ARMS))
    nopy = sorted({(st[0], tf) for p in ('R', 'U') for m in pop[p] for st in [tuple(m['key'])]
                   for tf in m['unopened_gold_files'] if line_lengths(st[0], npath(tf)) is None})
    L.append(f'    target files without snapshot text (line caps only, no character cap): {len(nopy)}')
    return applies


# ---------------------------------------------------------------- part "one step"

def iface_onestep(r):
    if r.get('error'):
        return 'error'
    c = r.get('next_call')
    if not c or not c.get('function_name'):
        return 'no call in first response'
    if c.get('function_name') not in KNOWN_TOOLS:
        return 'unknown tool'
    if not valid_call({'function_name': c.get('function_name'), 'arguments': c.get('arguments')}):
        return 'malformed arguments'
    return None


def part_onestep(os_dir, L):
    import collections
    rows = [json.loads(x) for x in find_file(os_dir, 'results.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    states = {}
    for x in STATES.read_text(encoding='utf-8').splitlines():
        if x.strip():
            s = json.loads(x)
            states[(s['task'], s['run'], s['fork'])] = s
    L.append('PART "one step" (pre-registration 08, rule S1)')
    L.append(f'  raw file: {len(rows)} replay rows; ' + wheels(os_dir, 'versions.json'))
    L.append(f'  arms in the file: {dict(sorted(collections.Counter(r["arm"] for r in rows).items()))}')

    rec = {}
    dup = 0
    fallback = 0
    for r in rows:
        key = (r['task'], r['run'], r['fork'])
        s = states[key]
        k = (key, r['arm'], r['seed'])
        if k in rec:
            dup += 1
        f = iface_onestep(r)
        y = None
        if f is None:
            call = {'function_name': r['next_call']['function_name'], 'arguments': r['next_call']['arguments']}
            y = 0
            for n in s['unshown_true_neighbors']:
                sp = s['neighbor_spans'][n]
                ll = line_lengths(s['task'], sp['path'])
                if ll is None:
                    fallback += 1
                    t = touches(call, sp, n, file_lines=(s.get('file_lines') or {}).get(n))
                else:
                    t = touches(call, sp, n, line_lengths=ll)
                if t and t != 'graph':
                    y = 1
                    break
        rec[k] = {'iface': f, 'y': y, 'task': r['task']}
    L.append(f'  duplicate (state, arm, seed) rows: {dup}; neighbor checks scored without snapshot text: {fallback}')

    L.append('')
    L.append('  Interface failures and usable replays by arm (design = 407 states x seeds 1 to 3)')
    L.append('    arm  design  error  no-call  unknown-tool  malformed  usable')
    for arm in ONESTEP_ARMS:
        cnt = collections.Counter()
        for st in states:
            for sd in ONESTEP_SEEDS:
                v = rec.get((st, arm, sd))
                cnt['missing' if v is None else (v['iface'] or 'usable')] += 1
        miss = f'  (missing rows {cnt["missing"]})' if cnt['missing'] else ''
        L.append(f'    {arm:<3}  {len(states) * 3:6d}  {cnt["error"]:5d}  {cnt["no call in first response"]:7d}  '
                 f'{cnt["unknown tool"]:12d}  {cnt["malformed arguments"]:9d}  {cnt["usable"]:6d}{miss}')

    complete = sorted(st for st in states
                      if all(rec.get((st, a, sd)) is not None and rec[(st, a, sd)]['iface'] is None
                             for a in ONESTEP_ARMS for sd in ONESTEP_SEEDS))
    ntask = len({s[0] for s in complete})
    applies = len(complete) >= 200
    L.append('')
    L.append(f'  Complete states (both arms, seeds 1 to 3 usable): {len(complete)} of {len(states)} ({ntask} tasks); '
             f'S1 applies (>= 200): {"yes" if applies else "NO, EXPLORATORY"}')
    L.append('  Share whose next call touches an unopened true neighbor (complete states)')
    sums = {}
    for arm in ONESTEP_ARMS:
        vs = [rec[(st, arm, sd)]['y'] for st in complete for sd in ONESTEP_SEEDS]
        sums[arm] = sum(vs)
        L.append(f'    {arm}: {pct(sum(vs), len(vs))}')
    L.append('  Same share over all usable replays (complete or not, descriptive)')
    for arm in ONESTEP_ARMS:
        vs = [v['y'] for (st, a, sd), v in sorted(rec.items()) if a == arm and v['iface'] is None]
        L.append(f'    {arm}: {pct(sum(vs), len(vs))}')

    by_state, by_task = [], {}
    for st in complete:
        sx = sum(rec[(st, 'E', sd)]['y'] for sd in ONESTEP_SEEDS)
        sy = sum(rec[(st, 'H', sd)]['y'] for sd in ONESTEP_SEEDS)
        by_state.append((sx, sy, 3))
        t = by_task.setdefault(st[0], [0, 0, 0])
        t[0] += sx
        t[1] += sy
        t[2] += 3
    cs = boot_diff(by_state)
    ct = boot_diff([tuple(by_task[k]) for k in sorted(by_task)])
    L.append('')
    L.append(f'  S1 E - H ({B} resamples, seed {BOOT_SEED}):')
    L.append(f'       clustered by state: {fmt_ci(cs)}')
    L.append(f'       clustered by task:  {fmt_ci(ct)}')
    L.append('  Verdict: ' + ('"The encoding effect holds on the newest harness wheels"' if cs[1] > 0
                              else '"not detected on the newest harness wheels"')
             + ('' if applies else ' (EXPLORATORY: fewer than 200 complete states)'))


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 2:
        raise SystemExit(__doc__)
    no_write = '--no-write' in argv
    L = ['Independent re-derivation of pre-registration 08, parts "fix" and "one step" (analysis/rederive_g.py)',
         'Interface failures: error; no call in the first response; unknown tool; malformed arguments by the frozen',
         'valid_call on the first call of the first response (checked in that order, one kind per replay).',
         '']
    part_fix(args[0], L)
    L.append('')
    part_onestep(args[1], L)
    text = '\n'.join(L) + '\n'
    try:
        sys.stdout.reconfigure(newline='\n')
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(text)
    sys.stdout.flush()
    if not no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)


if __name__ == '__main__':
    main(sys.argv[1:])
