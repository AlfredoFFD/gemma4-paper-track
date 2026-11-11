"""Independent re-derivation of experiments C and D (pre-registrations 04 and 05) from the raw replay logs.

Usage (from the repo root):
    py -I -X utf8 analysis/rederive_cd.py d1 <run_dir>
    py -I -X utf8 analysis/rederive_cd.py d2 <run_dir> --tag <name>
    py -I -X utf8 analysis/rederive_cd.py c <run_dir>

Writes analysis/results/rederive_d1.txt, analysis/results/rederive_d2_<name>.txt or analysis/results/rederive_c.txt.
Options for plumbing tests only: --arms A,H restricts the arms of a mode; --no-write prints without writing a file.

Only the registered scorer (fork_states.touches / valid_call) and the file reader (nodes.file_text, for exact
character caps) are imported. Loading, the interface-failure classes, complete states, outcomes, aggregation, the
clustered bootstrap, the gates and the verdicts are written here from the pre-registration texts, following the
pattern of analysis/rederive_s5.py.
"""
import argparse
import collections
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from fork_states import touches, valid_call  # noqa: E402  registered scorer
import nodes as N  # noqa: E402  file contents for the character caps

GRAPH = {'get_code_neighbors', 'get_code_subgraph', 'search_similar_code'}
KNOWN = GRAPH | {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch'}
KINDS = ('error', 'no_call', 'unknown_tool', 'malformed')
SEEDS = (1, 2, 3)
NB = 2000
MIN_COMPLETE = 200
STATES_D = HERE / 'fork_states_d' / 'states.jsonl'
STATES_C = HERE / 'fork_states_c' / 'states.jsonl'
MD5_D = 'd3105df0dc4aa43d7bb0afbdd6123b44'
MD5_C_PREFIX = '9d7ad4bbd8f4'
HOSTED_H = HERE / 'results' / 'v5' / 'forks'
HOSTED_E = HERE / 'results' / 'v6' / 'forks'
C_RUN_DEFAULT = ROOT / 'data' / 'forks_c_modal' / 'out'
REGISTERED_WHEELS = {'adk_eval_core': '0.1.0', 'adk_submission': '0.2.12', 'swegemma': '0.2.7'}
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

AMBIGUITIES = [
    'Interface failures: each row gets one class, checked in this order: error (non-empty error field), no call '
    '(next_call missing or empty), unknown tool (name outside the nine declared tools), malformed (fork_states.'
    'valid_call is False). Graph-tool calls with valid arguments are usable replays and never a touch.',
    'Failure counts are over all rows of the run (every state); rates use usable replays of complete states only.',
    'Complete state: the state is in the states file and every arm of the mode has a usable replay for seeds 1, 2 '
    'and 3. A repeated (state, arm, seed) row is counted and the first one is kept.',
    'Rates are percent of usable replays on complete states (each replay weight 1); the bootstrap resamples states '
    'with replacement and takes the ratio of summed hits to summed replays. Contrasts are differences of these '
    'ratios on the same resampled states (paired by state).',
    'Bootstrap: numpy default_rng(0), 2,000 resamples; percentile bounds are order statistics b[int(a*n)] and '
    'b[int((1-a)*n)-1] of the sorted resampled values (a = 0.025 for 95%, 0.05 for 90%), as in rederive_s5.py. '
    'The 90% interval uses the same resamples as the 95% one.',
    '"Any unopened true neighbor touched": a replay counts if fork_states.touches returns read or edit for at least '
    'one name in the state\'s unshown_true_neighbors, with its span from neighbor_spans and the file\'s line lengths '
    'from nodes.file_text (exact character caps); graph returns do not count.',
    '"Lower bound above 0" is strict. "Interval lies within plus or minus X points" is closed: both bounds in '
    '[-X, +X].',
    'Fidelity: relative difference = (replayed - logged) / logged prompt tokens; rows with an error or a missing '
    'count are left out; the gate passes if the median of the absolute values is at most 2% (inclusive).',
    'Thought text present: the thought field is a string that is non-empty after stripping whitespace. Completion '
    'and prompt tokens come from the usage field; replays without the count are left out of that line.',
    'A failed gate or fewer than 200 complete states does not stop the script: the numbers are printed with an '
    'EXPLORATORY / NOT ANALYZED label so they can be compared.',
    'D2 20% flag: interface failures of an arm divided by all rows of that arm in the run; flagged if strictly '
    'above 20%.',
    'D2 "E true minus RE rewired": per replay, any unopened true neighbor touched under E minus any rewired entry '
    '(rewired_entries with rewired_spans) touched under RE, paired by state.',
    'C, arm Ep: scored on all unopened true neighbors from the states file, including the swapped-out entry that '
    'the Ep note does not list ("every arm is scored with the same spans, whatever the note showed"). The variant '
    'that leaves the swapped-out entry out is printed beside it, labeled.',
    'C secondary per-entry rate: pooled over (Ep replay, entry) pairs for the unopened true entries the Ep note '
    'lists (unshown true neighbors minus the swapped-out entry), clustered by state.',
    'C1 and the decoy-versus-half rule use point estimates on the same complete states; the 1% floor is inclusive '
    '(swapped-out rate under E >= 1%).',
    'C2 when G2 fails: no "only the full entry" verdict is given (the rule names it only while G2 holds); every C2 '
    'line is then EXPLORATORY.',
    'G3: hosted H from results/v5, hosted E from results/v6, scored with the same states file; pairs are '
    '(state, seed) with a usable replay in both runs, on this run\'s complete states; difference = this run minus '
    'hosted, clustered by state. "Above 3 points" is read on the absolute point estimate.',
]


class Report:
    def __init__(self):
        self.lines = []

    def __call__(self, s=''):
        self.lines.append(s)
        print(s)

    def write(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(self.lines) + '\n', encoding='utf-8')


def shown(p):
    """A path for the report: relative to the repo root when possible, never absolute."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def state_key(d):
    return (d['task'], d['run'], d.get('fork', 0))


def load_states(path):
    states = {}
    for s in read_jsonl(path):
        s.pop('steps', None)
        states[state_key(s)] = s
    return states


def installed_wheels(run_dir, names):
    """Versions of the named wheels as the run installed them, from the run folder's pip_freeze.txt. The wheelhouse
    list in versions.json names every wheel the folder held (always the newest), not the ones installed."""
    f = Path(run_dir) / 'pip_freeze.txt'
    if not f.exists():
        return 'not recorded in the run folder'
    found = {}
    for line in f.read_text(encoding='utf-8').splitlines():
        if ' @ ' in line:
            name, ver = line.split(' @ ', 1)[0].strip(), line.rsplit('/', 1)[-1].split('-')[1]
        elif '==' in line:
            name, ver = line.split('==', 1)
        else:
            continue
        key = name.strip().replace('-', '_').lower()
        if key in names:
            found[key] = ver.strip()
    return {k: found.get(k, 'not recorded in the run folder') for k in names}


def load_run(run_dir):
    run_dir = Path(run_dir)
    res = run_dir / 'results.jsonl'
    if not res.exists():
        sys.exit(f'No results.jsonl in {shown(run_dir)}: the run directory is missing or not downloaded yet.')
    fid = run_dir / 'fidelity.jsonl'
    ver = run_dir / 'versions.json'
    return (read_jsonl(res), read_jsonl(fid) if fid.exists() else None,
            json.loads(ver.read_text(encoding='utf-8')) if ver.exists() else None)


# ---------------------------------------------------------------- classification

def failure_kind(row):
    if row.get('error'):
        return 'error'
    call = row.get('next_call')
    if not call:
        return 'no_call'
    if call.get('function_name') not in KNOWN:
        return 'unknown_tool'
    if not valid_call(call):
        return 'malformed'
    return None


def classify(rows, arms, states):
    info = dict(rows_per_arm=collections.Counter(), fails=collections.Counter(), dups=0, other_arms=collections.Counter(),
                other_seeds=0, unknown_states=set())
    usable = collections.defaultdict(dict)
    for r in rows:
        if r['arm'] not in arms:
            info['other_arms'][r['arm']] += 1
            continue
        info['rows_per_arm'][r['arm']] += 1
        if r['seed'] not in SEEDS:
            info['other_seeds'] += 1
        k = state_key(r)
        if k not in states:
            info['unknown_states'].add(k)
        kind = failure_kind(r)
        if kind:
            info['fails'][(r['arm'], kind)] += 1
            continue
        slot = (r['arm'], r['seed'])
        if slot in usable[k]:
            info['dups'] += 1
            continue
        usable[k][slot] = r
    need = {(a, s) for a in arms for s in SEEDS}
    complete = sorted(k for k, v in usable.items() if k in states and need <= set(v))
    return usable, complete, info


# ---------------------------------------------------------------- scoring

_lengths = {}
_missing_files = set()


def line_lengths(task, path):
    if (task, path) not in _lengths:
        src = N.file_text(task, path)
        if src is None:
            _missing_files.add((task, path))
        _lengths[(task, path)] = [len(x) for x in src.splitlines()] if src is not None else None
    return _lengths[(task, path)]


def touched(call, span, nid, task):
    if not span:
        return False
    v = touches(call, span, nid, line_lengths=line_lengths(task, span['path']))
    return v in ('read', 'edit')


def score_row(r, s):
    c = r['next_call']
    task = s['task']
    sp = s['neighbor_spans']
    unshown = [n for n in s['unshown_true_neighbors'] if sp.get(n)]
    th = {n: touched(c, sp[n], n, task) for n in unshown}
    rsp = s.get('rewired_spans') or {}
    rew = [n for n in s.get('rewired_entries', []) if rsp.get(n)]
    usage = r.get('usage') or {}
    thought = r.get('thought')
    listed_ep = [n for n in unshown if n != s['swapped_out']]
    return dict(
        true_any=any(th.values()),
        true_any_no_swapped=any(th[n] for n in listed_ep),
        swapped=th.get(s['swapped_out'], False) if s['swapped_out'] in th else touched(
            c, sp.get(s['swapped_out']), s['swapped_out'], task),
        decoy=touched(c, s.get('decoy_span'), s['decoy'], task),
        rew=any(touched(c, rsp[n], n, task) for n in rew),
        graph=c.get('function_name') in GRAPH,
        thought=isinstance(thought, str) and bool(thought.strip()),
        ctok=usage.get('completion_tokens'),
        ptok=usage.get('prompt_tokens'),
        ep_entries=[th[n] for n in listed_ep],
        oddkey=any(not IDENT.match(str(k)) for k in (c.get('arguments') or {})),
    )


def score(usable, complete, states, arms):
    recs = []
    for k in complete:
        s = states[k]
        for a in arms:
            for sd in SEEDS:
                rec = score_row(usable[k][(a, sd)], s)
                rec.update(key=k, arm=a, seed=sd)
                recs.append(rec)
    return recs


# ---------------------------------------------------------------- clustered bootstrap

def _clusters(pairs):
    d = {}
    for cid, v in pairs:
        t = d.setdefault(cid, [0.0, 0])
        t[0] += v
        t[1] += 1
    return d


def _draws(m):
    return np.random.default_rng(0).integers(0, m, size=(NB, m))


def _bounds(b, level):
    b = np.sort(b)
    a = (1 - level) / 2
    n = len(b)
    return float(b[int(a * n)]), float(b[int((1 - a) * n) - 1])


def rate(pairs, levels=(0.95,)):
    d = _clusters(pairs)
    if not d:
        return None
    cl = sorted(d)
    s = np.array([d[c][0] for c in cl])
    n = np.array([d[c][1] for c in cl])
    idx = _draws(len(cl))
    b = 100 * s[idx].sum(1) / n[idx].sum(1)
    return dict(est=100 * s.sum() / n.sum(), k=int(s.sum()), n=int(n.sum()), ci={lv: _bounds(b, lv) for lv in levels})


def diff(pairs_a, pairs_b, levels=(0.95,)):
    da, db = _clusters(pairs_a), _clusters(pairs_b)
    if not da or not db:
        return None
    cl = sorted(set(da) | set(db))
    sa = np.array([da.get(c, [0, 0])[0] for c in cl], dtype=float)
    na = np.array([da.get(c, [0, 0])[1] for c in cl], dtype=float)
    sb = np.array([db.get(c, [0, 0])[0] for c in cl], dtype=float)
    nb = np.array([db.get(c, [0, 0])[1] for c in cl], dtype=float)
    idx = _draws(len(cl))
    b = 100 * (sa[idx].sum(1) / np.maximum(na[idx].sum(1), 1) - sb[idx].sum(1) / np.maximum(nb[idx].sum(1), 1))
    return dict(est=100 * (sa.sum() / na.sum() - sb.sum() / nb.sum()), ci={lv: _bounds(b, lv) for lv in levels},
                clusters=len(cl))


def pairs(recs, arm, field):
    return [(r['key'], float(r[field])) for r in recs if r['arm'] == arm]


def fmt_rate(t):
    if t is None:
        return 'n/a'
    lo, hi = t['ci'][0.95]
    return f'{t["est"]:6.2f}% ({t["k"]}/{t["n"]}) 95% [{lo:.2f}, {hi:.2f}]'


def fmt_diff(t, levels=(0.95,)):
    if t is None:
        return 'n/a'
    parts = [f'{t["est"]:+.2f} points']
    for lv in levels:
        lo, hi = t['ci'][lv]
        parts.append(f'{int(lv * 100)}% [{lo:+.2f}, {hi:+.2f}]')
    return ', '.join(parts)


def lower_above_zero(t):
    return t is not None and t['ci'][0.95][0] > 0


def within(t, level, x):
    if t is None:
        return False
    lo, hi = t['ci'][level]
    return -x <= lo and hi <= x


# ---------------------------------------------------------------- shared report pieces

def header(out, title, run_dir, states_path, versions, mode_note):
    out(title)
    out('Script: analysis/rederive_cd.py (independent re-derivation; imports only fork_states.touches, '
        'fork_states.valid_call and nodes.file_text).')
    out(f'Run directory: {shown(run_dir)}')
    h = md5(states_path)
    out(f'States file: {shown(states_path)}, md5 {h}')
    if versions:
        wheels = installed_wheels(run_dir, REGISTERED_WHEELS)
        model = str(versions.get('model_path') or '').split('models/', 1)[-1]  # the model id, without the mount point
        out(f'Run versions (versions.json; wheels as installed, from pip_freeze.txt): harness_variant '
            f'{versions.get("harness_variant")}, wheels {wheels}, model {model}, tensor_parallel_size '
            f'{versions.get("tensor_parallel_size")}, platform {versions.get("platform")}, '
            f'experiment field {versions.get("experiment")!r}, arms field {versions.get("arms")}')
    else:
        out('Run versions: no versions.json in the run directory.')
    out(mode_note)
    out(f'Bootstrap: clustered by state, {NB} resamples, numpy default_rng(0), percentile intervals.')
    out()
    out('Ambiguities in the pre-registration texts and the readings taken here:')
    for i, a in enumerate(AMBIGUITIES, 1):
        out(f'  A{i}. {a}')
    out()


def counts_section(out, rows, arms, usable, complete, info, states):
    out('S0. Counts')
    out(f'  rows read: {len(rows)}; rows per arm: {dict(sorted(info["rows_per_arm"].items()))}')
    if info['other_arms']:
        out(f'  rows of arms outside this mode (ignored): {dict(info["other_arms"])}')
    out(f'  rows with a seed outside 1-3: {info["other_seeds"]}; repeated (state, arm, seed) usable rows: {info["dups"]}; '
        f'row states not in the states file: {len(info["unknown_states"])}')
    out(f'  states with any usable row: {len(usable)}; states in the states file: {len(states)}')
    out('  interface failures per arm (all rows of the run):')
    for a in arms:
        tot = sum(info['fails'][(a, k)] for k in KINDS)
        n = info['rows_per_arm'][a]
        kinds = ', '.join(f'{k} {info["fails"][(a, k)]}' for k in KINDS)
        out(f'    {a:3s} {tot} of {n} ({100 * tot / n if n else 0:.2f}%): {kinds}')
    out(f'  complete states (every arm {"/".join(arms)}, seeds 1-3 usable): {len(complete)}')
    ok = len(complete) >= MIN_COMPLETE
    out(f'  partial-run rule (at least {MIN_COMPLETE} complete states): '
        f'{"met, the rules apply" if ok else "NOT met, everything below is EXPLORATORY"}')
    out()
    return ok


def fidelity_summary(fid):
    vals, signed, skipped = [], [], 0
    for f in fid:
        lg, rp = f.get('logged_prompt_tokens'), f.get('replayed_prompt_tokens')
        if f.get('error') or not lg or rp is None:
            skipped += 1
            continue
        d = (rp - lg) / lg
        signed.append(d)
        vals.append(abs(d))
    return vals, signed, skipped


def fidelity_gate(out, fid, label):
    out(f'{label}. Fidelity gate (median absolute relative difference between replayed and logged prompt tokens, '
        f'rule: at most 2%)')
    if fid is None:
        out('  no fidelity.jsonl in the run directory: gate cannot be checked (FAILED for the purpose of the rule)')
        out()
        return False
    vals, signed, skipped = fidelity_summary(fid)
    if not vals:
        out(f'  {len(fid)} rows, none usable: gate cannot be checked')
        out()
        return False
    med = 100 * statistics.median(vals)
    passed = med <= 2.0
    out(f'  rows {len(fid)}, used {len(vals)}, left out (error or missing count) {skipped}; distinct states '
        f'{len({state_key(f) for f in fid})}')
    out(f'  median |relative difference| {med:.3f}%; median signed {100 * statistics.median(signed):+.3f}%; '
        f'max |relative difference| {100 * max(vals):.3f}%; replayed below logged in '
        f'{sum(1 for d in signed if d < 0)} of {len(signed)}')
    out(f'  gate: {"PASSED" if passed else "FAILED"}')
    out()
    return passed


def per_arm_lines(out, recs, arms, extra=True, rewired_arms=()):
    out('  any unopened true neighbor touched:')
    for a in arms:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "true_any")))}')
    out('  swapped-out entry touched:')
    for a in arms:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "swapped")))}')
    for a in rewired_arms:
        out(f'  any rewired entry touched, {a}: {fmt_rate(rate(pairs(recs, a, "rew")))}')
    if not extra:
        return
    out('  next call is a graph tool:')
    for a in arms:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "graph")))}')
    out('  thought text present:')
    for a in arms:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "thought")))}')
    out('  tokens:')
    for a in arms:
        ct = [r['ctok'] for r in recs if r['arm'] == a and r['ctok'] is not None]
        pt = [r['ptok'] for r in recs if r['arm'] == a and r['ptok'] is not None]
        nr = sum(1 for r in recs if r['arm'] == a)
        out(f'    {a:3s} median completion tokens {statistics.median(ct) if ct else float("nan"):.1f} (n={len(ct)}); '
            f'mean prompt tokens {sum(pt) / len(pt) if pt else float("nan"):.1f} (n={len(pt)}); replays {nr}')


def data_checks(out, rows, states, label, recs=None):
    out(f'{label}. Data checks (descriptive; nothing here changes a number above)')
    no_all = sum(1 for r in rows if 'all_calls' not in r)
    mism = sum(1 for r in rows if r.get('all_calls') and r.get('next_call') != r['all_calls'][0])
    multi = collections.Counter(r['arm'] for r in rows if len(r.get('all_calls') or []) > 1)
    out(f'  rows without all_calls: {no_all}; rows whose next_call differs from all_calls[0]: {mism}; '
        f'rows with more than one call, by arm: {dict(multi)}')
    odd = collections.Counter()
    odd_names = collections.Counter()
    for r in rows:
        c = r.get('next_call')
        if c and isinstance(c.get('arguments'), dict):
            bad = [k for k in c['arguments'] if not IDENT.match(str(k))]
            if bad:
                odd[r['arm']] += 1
                for k in bad:
                    odd_names[(c.get('function_name'), k)] += 1
    out(f'  next calls with an argument name that is not a plain identifier, by arm: {dict(odd)}')
    if odd_names:
        out(f'    (tool, argument name): {dict(odd_names.most_common(10))}')
        out('    valid_call accepts these calls and touches reads them without the misnamed bound (a read with no '
            'start line shows lines 1-150).')
    if recs is not None:
        n_odd = collections.Counter(r['arm'] for r in recs if r['oddkey'])
        n_hit = collections.Counter(r['arm'] for r in recs if r['oddkey'] and r['true_any'])
        n_sw = collections.Counter(r['arm'] for r in recs if r['oddkey'] and r['swapped'])
        out(f'    on complete states: such replays by arm {dict(n_odd)}; of them counted as any unopened true '
            f'neighbor touched {dict(n_hit)}; as swapped-out touched {dict(n_sw)}')
    node_mis = sum(1 for r in rows if state_key(r) in states and r.get('node') not in (None, states[state_key(r)]['node']))
    no_usage = sum(1 for r in rows if not r.get('usage'))
    out(f'  rows whose node differs from the state\'s node: {node_mis}; rows without usage: {no_usage}')
    by_tool = collections.Counter((r['arm'], (r.get('next_call') or {}).get('function_name')) for r in rows)
    arms = sorted({r['arm'] for r in rows})
    for a in arms:
        out(f'  next-call tool mix, {a}: {dict(sorted(((t or "none"), n) for (aa, t), n in by_tool.items() if aa == a))}')
    out(f'  files with no source text (line caps only, no character caps): {len(_missing_files)}')
    out()


def check_states_file(out, path, mode):
    h = md5(path)
    if mode == 'd' and h != MD5_D:
        out(f'  WARNING: states file md5 {h} differs from the registered {MD5_D}')
    if mode == 'c' and not h.startswith(MD5_C_PREFIX):
        out(f'  WARNING: states file md5 {h} does not begin with the registered {MD5_C_PREFIX}')


def drift_vs(out, recs, arm, other_rows, states, complete, label):
    """This run's arm against another run's same arm, paired by (state, seed), clustered by state."""
    other = {}
    for r in other_rows:
        if r['arm'] != arm or failure_kind(r):
            continue
        other.setdefault((state_key(r), r['seed']), r)
    cset = set(complete)
    mine, theirs = [], []
    for r in recs:
        if r['arm'] != arm or r['key'] not in cset:
            continue
        o = other.get((r['key'], r['seed']))
        if o is None:
            continue
        mine.append((r['key'], float(r['true_any'])))
        theirs.append((r['key'], float(score_row(o, states[r['key']])['true_any'])))
    if not mine:
        out(f'  {label}: no paired replays')
        return None
    t = diff(mine, theirs)
    out(f'  {label}: this run {fmt_rate(rate(mine))} | other run {fmt_rate(rate(theirs))}; '
        f'difference {fmt_diff(t)} ({len(mine)} paired replays, {t["clusters"]} states)')
    return t


def finish(out, args, name):
    if args.no_write:
        print(f'\n(--no-write: nothing written; would have been analysis/results/{name})')
        return
    path = HERE / 'results' / name
    out.write(path)
    print(f'\nwrote {shown(path)}')


# ---------------------------------------------------------------- D1

def mode_d1(args):
    arms = args.arms or ['P', 'PE', 'E']
    rows, fid, versions = load_run(args.run_dir)
    states = load_states(STATES_D)
    out = Report()
    header(out, 'Independent re-derivation of experiment D1 (pre-registration 05: the tool channel)',
           args.run_dir, STATES_D, versions, f'Arms: {", ".join(arms)}; seeds 1-3.')
    check_states_file(out, STATES_D, 'd')
    usable, complete, info = classify(rows, arms, states)
    enough = counts_section(out, rows, arms, usable, complete, info, states)
    passed = fidelity_gate(out, fid, 'S1')
    if not passed:
        out('  The rule says the run is not analyzed: every number below is EXPLORATORY.')
        out()
    recs = score(usable, complete, states, arms)
    label = '' if (passed and enough) else ' [EXPLORATORY]'
    out(f'S2. Per arm, usable replays on the {len(complete)} complete states{label}')
    per_arm_lines(out, recs, arms)
    out()
    out(f'S3. Contrasts on any unopened true neighbor touched (paired by state){label}')
    if {'P', 'PE', 'E'} <= set(arms):
        t1 = diff(pairs(recs, 'PE', 'true_any'), pairs(recs, 'P', 'true_any'))
        out(f'  T1 = PE minus P: {fmt_diff(t1)}')
        out('    verdict: ' + ('The legible entries raise following in the tool channel (lower 95% bound above 0).'
                               if lower_above_zero(t1) else
                               'The legible entries do not raise following in the tool channel (lower 95% bound not '
                               'above 0); reported with the interval.'))
        t2 = diff(pairs(recs, 'PE', 'true_any'), pairs(recs, 'E', 'true_any'), levels=(0.95, 0.90))
        out(f'  T2 = PE minus E: {fmt_diff(t2, (0.95, 0.90))}')
        out('    verdict: ' + ('No channel difference (the 90% interval lies within plus or minus 2 points).'
                               if within(t2, 0.90, 2.0) else
                               'Not "no channel difference": the 90% interval does not lie within plus or minus 2 '
                               'points; the difference is reported with its intervals.'))
    else:
        out('  skipped: the mode was restricted to arms without P, PE and E')
    out()
    out('S4. Drift of arm E against the experiment C run (descriptive, changes no rule; paired by state and seed)')
    c_res = C_RUN_DEFAULT / 'results.jsonl'
    if 'E' in arms and c_res.exists():
        drift_vs(out, recs, 'E', read_jsonl(c_res), states, complete, 'E, this run minus the C run')
    else:
        out(f'  skipped: {shown(C_RUN_DEFAULT)} has no results.jsonl yet')
    out()
    data_checks(out, rows, states, 'S5', recs)
    finish(out, args, 'rederive_d1.txt')


# ---------------------------------------------------------------- D2

def mode_d2(args):
    if not args.tag:
        sys.exit('d2 needs --tag <name> (for example 26b or e4b).')
    arms = args.arms or ['A', 'H', 'E', 'RE']
    rows, fid, versions = load_run(args.run_dir)
    states = load_states(STATES_D)
    out = Report()
    header(out, f'Independent re-derivation of experiment D2, tag {args.tag} (pre-registration 05: a second model, '
                f'and its amendment)', args.run_dir, STATES_D, versions, f'Arms: {", ".join(arms)}; seeds 1-3.')
    check_states_file(out, STATES_D, 'd')
    usable, complete, info = classify(rows, arms, states)
    enough = counts_section(out, rows, arms, usable, complete, info, states)
    out('S1. Interface-failure flag (an arm with more than 20% interface failures is reported as unreliable)')
    unreliable = set()
    for a in arms:
        n = info['rows_per_arm'][a]
        f = sum(info['fails'][(a, k)] for k in KINDS)
        share = 100 * f / n if n else 0.0
        flag = share > 20.0
        if flag:
            unreliable.add(a)
        out(f'  {a:3s} {share:.2f}% -> {"UNRELIABLE" if flag else "below the flag"}')
    out()
    recs = score(usable, complete, states, arms)
    label = '' if enough else ' [EXPLORATORY]'
    out(f'S2. Per arm, usable replays on the {len(complete)} complete states{label}')
    per_arm_lines(out, recs, arms, rewired_arms=[a for a in arms if a == 'RE'])
    if unreliable:
        out(f'  arms reported as unreliable (over 20% interface failures): {", ".join(sorted(unreliable))}')
    out()
    out(f'S3. Contrasts (paired by state){label}')
    if {'E', 'H'} <= set(arms):
        m1 = diff(pairs(recs, 'E', 'true_any'), pairs(recs, 'H', 'true_any'))
        out(f'  M1 = E minus H, any unopened true neighbor touched: {fmt_diff(m1)}')
        out('    verdict: ' + ('replicates on the second model (lower 95% bound above 0).' if lower_above_zero(m1)
                               else 'does not replicate on the second model (lower 95% bound not above 0).'))
    if {'H', 'A'} <= set(arms):
        out(f'  H minus A (no rule): {fmt_diff(diff(pairs(recs, "H", "true_any"), pairs(recs, "A", "true_any")))}')
    if {'E', 'A'} <= set(arms):
        out(f'  E minus A (no rule): {fmt_diff(diff(pairs(recs, "E", "true_any"), pairs(recs, "A", "true_any")))}')
    if {'E', 'RE'} <= set(arms):
        out(f'  E true minus RE rewired (no rule; not like-for-like): '
            f'{fmt_diff(diff(pairs(recs, "E", "true_any"), pairs(recs, "RE", "rew")))}')
    missing = [x for x in ('M1', 'H-A', 'E-A', 'E-RE') if not {
        'M1': {'E', 'H'}, 'H-A': {'H', 'A'}, 'E-A': {'E', 'A'}, 'E-RE': {'E', 'RE'}}[x] <= set(arms)]
    if missing:
        out(f'  skipped for lack of arms: {", ".join(missing)}')
    out()
    out('S4. Prompt-size check from fidelity.jsonl (a plumbing check with no rule; the logged sizes come from the '
        'first model\'s traces)')
    if fid is None:
        out('  no fidelity.jsonl in the run directory')
    else:
        vals, signed, skipped = fidelity_summary(fid)
        if vals:
            out(f'  rows {len(fid)}, used {len(vals)}, left out {skipped}; median |relative difference| '
                f'{100 * statistics.median(vals):.3f}%; median signed {100 * statistics.median(signed):+.3f}%; '
                f'range {100 * min(signed):+.3f}% to {100 * max(signed):+.3f}%')
        else:
            out(f'  rows {len(fid)}, none usable')
    out()
    data_checks(out, rows, states, 'S5', recs)
    finish(out, args, f'rederive_d2_{args.tag}.txt')


# ---------------------------------------------------------------- C

def mode_c(args):
    arms = args.arms or ['Ep', 'EL', 'ES', 'E', 'H']
    rows, fid, versions = load_run(args.run_dir)
    states = load_states(STATES_C)
    out = Report()
    header(out, 'Independent re-derivation of experiment C (pre-registration 04)', args.run_dir, STATES_C, versions,
           f'Arms: {", ".join(arms)}; seeds 1-3.')
    check_states_file(out, STATES_C, 'c')
    usable, complete, info = classify(rows, arms, states)
    enough = counts_section(out, rows, arms, usable, complete, info, states)
    recs = score(usable, complete, states, arms)
    have = set(arms)

    g1 = fidelity_gate(out, fid, 'G1')
    if not g1:
        out('  G1 failed: the rule says the run is not analyzed. Every number below is EXPLORATORY.')
        out()
    out('G2. Replication of B3 on this platform: E minus H, any unopened true neighbor touched (lower 95% bound '
        'above 0)')
    g2 = None
    if {'E', 'H'} <= have:
        t = diff(pairs(recs, 'E', 'true_any'), pairs(recs, 'H', 'true_any'))
        g2 = lower_above_zero(t)
        out(f'  E minus H: {fmt_diff(t)} -> G2 {"HOLDS" if g2 else "FAILS"}')
        if not g2:
            out('  G2 failed: that failure is the reported result; C1 and C2 are reported as EXPLORATORY.')
    else:
        out('  skipped: arms E and H are not both in this mode')
    out()
    out('G3. Platform drift (descriptive): this run against the hosted runs on the same states and seeds; a '
        'difference above 3 points with a 95% interval excluding 0 is reported as a platform difference')
    for arm, hdir in (('E', HOSTED_E), ('H', HOSTED_H)):
        if arm not in have:
            continue
        hres = hdir / 'results.jsonl'
        if not hres.exists():
            out(f'  {arm}: hosted run {shown(hdir)} not found')
            continue
        t = drift_vs(out, recs, arm, read_jsonl(hres), states, complete, f'{arm}, this run minus hosted {shown(hdir)}')
        if t is not None:
            lo, hi = t['ci'][0.95]
            pdiff = abs(t['est']) > 3.0 and (lo > 0 or hi < 0)
            out(f'    -> {"PLATFORM DIFFERENCE" if pdiff else "not reported as a platform difference"}')
    out()

    base = '' if (g1 and enough) else ' [EXPLORATORY]'
    out(f'S1. All arms, usable replays on the {len(complete)} complete states{base}')
    per_arm_lines(out, recs, arms, extra=False)
    out('  decoy touched:')
    for a in arms:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "decoy")))}')
    if 'Ep' in have:
        out(f'  Ep, any unopened true neighbor touched without the swapped-out entry (alternative reading, see '
            f'ambiguities): {fmt_rate(rate(pairs(recs, "Ep", "true_any_no_swapped")))}')
    out()

    cl = '' if (g1 and enough and g2) else ' [EXPLORATORY]'
    out(f'C1. The false edge under the legible encoding: D_E = P(swapped-out touched | E) minus P(decoy touched | Ep)'
        f'{cl}')
    if {'E', 'Ep'} <= have:
        sw = rate(pairs(recs, 'E', 'swapped'))
        dc = rate(pairs(recs, 'Ep', 'decoy'))
        de = diff(pairs(recs, 'E', 'swapped'), pairs(recs, 'Ep', 'decoy'), levels=(0.95, 0.90))
        out(f'  swapped-out under E: {fmt_rate(sw)}')
        out(f'  decoy under Ep:      {fmt_rate(dc)}')
        out(f'  D_E: {fmt_diff(de, (0.95, 0.90))}')
        if sw['est'] < 1.0:
            v = 'underpowered: the swapped-out entry is touched in fewer than 1% of arm E replays; reported with the interval.'
        elif lower_above_zero(de) and dc['est'] < sw['est'] / 2:
            v = 'checks the edge (lower 95% bound above 0 and decoy rate below half the swapped-out rate).'
        elif within(de, 0.90, 1.5) and dc['est'] >= sw['est'] / 2:
            v = ('follows a false edge as readily (90% interval within plus or minus 1.5 points and decoy rate at '
                 'least half the swapped-out rate).')
        else:
            v = 'inconclusive, reported with the interval.'
        out(f'  floor (swapped-out under E at least 1%): {"met" if sw["est"] >= 1.0 else "NOT met"}')
        out(f'  verdict: {v}')
        out('  secondary, descriptive:')
        out(f'    any unopened true neighbor touched, Ep minus E: '
            f'{fmt_diff(diff(pairs(recs, "Ep", "true_any"), pairs(recs, "E", "true_any")))}')
        out(f'    (alternative reading, swapped-out entry left out in both arms: '
            f'{fmt_diff(diff(pairs(recs, "Ep", "true_any_no_swapped"), pairs(recs, "E", "true_any_no_swapped")))})')
        ent = [(r['key'], float(x)) for r in recs if r['arm'] == 'Ep' for x in r['ep_entries']]
        out(f'    decoy touch rate under Ep: {fmt_rate(dc)}')
        out(f'    per-entry touch rate of the unopened true entries in the Ep notes: {fmt_rate(rate(ent))}')
    else:
        out('  skipped: arms E and Ep are not both in this mode')
    out()

    out(f'C2. Which part of the entry is followed (any unopened true neighbor touched){cl}')
    if {'E', 'EL', 'ES', 'H'} <= have:
        el = diff(pairs(recs, 'EL', 'true_any'), pairs(recs, 'H', 'true_any'))
        es = diff(pairs(recs, 'ES', 'true_any'), pairs(recs, 'H', 'true_any'))
        r_el, r_es = lower_above_zero(el), lower_above_zero(es)
        out(f'  EL minus H (location): {fmt_diff(el)} -> {"raises following" if r_el else "does not raise following"}')
        out(f'  ES minus H (definition line): {fmt_diff(es)} -> '
            f'{"raises following" if r_es else "does not raise following"}')
        if r_el and not r_es:
            v = 'Location carries it.'
        elif r_es and not r_el:
            v = 'Definition line carries it.'
        elif r_el and r_es:
            v = 'Either part is enough.'
        elif g2:
            v = 'Only the full entry (neither part raises following while G2 holds).'
        else:
            v = 'Neither part raises following, and G2 does not hold: no registered verdict.'
        out(f'  verdict: {v}')
        for arm in ('EL', 'ES'):
            t = diff(pairs(recs, 'E', 'true_any'), pairs(recs, arm, 'true_any'), levels=(0.95, 0.90))
            suff = within(t, 0.90, 2.0)
            out(f'  E minus {arm}: {fmt_diff(t, (0.95, 0.90))} -> '
                f'{"sufficient for the full effect" if suff else "not called sufficient for the full effect"} '
                f'(90% interval within plus or minus 2 points: {"yes" if suff else "no"})')
    else:
        out('  skipped: arms E, EL, ES and H are not all in this mode')
    out()
    data_checks(out, rows, states, 'S2', recs)
    finish(out, args, 'rederive_c.txt')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['d1', 'd2', 'c'])
    ap.add_argument('run_dir')
    ap.add_argument('--tag')
    ap.add_argument('--arms', type=lambda s: [x for x in s.split(',') if x], help='plumbing tests only')
    ap.add_argument('--no-write', action='store_true', help='plumbing tests only')
    args = ap.parse_args()
    if not Path(args.run_dir).is_dir():
        sys.exit(f'Run directory {shown(args.run_dir)} does not exist (not downloaded yet?). Nothing computed.')
    {'d1': mode_d1, 'd2': mode_d2, 'c': mode_c}[args.mode](args)


if __name__ == '__main__':
    main()
