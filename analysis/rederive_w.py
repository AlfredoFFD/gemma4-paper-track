"""Independent re-derivation of experiment F (pre-registration 07: how earlier tool results are rendered) from the
raw replay logs.

Usage (from the repo root):
    py -I -X utf8 analysis/rederive_w.py <run_dir> [--no-write]

Prints the report and, without --no-write, writes it to analysis/results/rederive_w.txt.

Only the registered scorer (fork_states.touches / valid_call) and the file reader (nodes.file_text, for exact
character caps) are imported. Loading, the interface-failure classes, complete states, the outcomes (any unopened
true neighbor touched, the mangled line-bound name), the clustered bootstrap, the fidelity summaries and the verdicts
are written here from the pre-registration texts (07, and 02 to 05 for the common rules), following the pattern of
analysis/rederive_s5.py and analysis/rederive_cd.py.
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

ARMS = ['A', 'Aw', 'Hw', 'Ew']
SEEDS = (1, 2, 3)
GRAPH = {'get_code_neighbors', 'get_code_subgraph', 'search_similar_code'}
KNOWN = GRAPH | {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch'}
KINDS = ('error', 'no_call', 'unknown_tool', 'malformed')
NB = 2000
MIN_COMPLETE = 200
F1_THRESHOLD = 0.5  # percent, inclusive
STATES = HERE / 'fork_states_d' / 'states.jsonl'
MD5_STATES = 'd3105df0dc4aa43d7bb0afbdd6123b44'
PREREG05_WHEELS = {'adk_eval_core': '0.1.0', 'adk_submission': '0.2.12', 'swegemma': '0.2.7'}
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
BOUND_NAMES = ('start_line', 'end_line')

AMBIGUITIES = [
    'Interface failures: one class per row, checked in this order: error (non-empty error field), no call '
    '(next_call missing or empty), unknown tool (name outside the nine declared tools), malformed (fork_states.'
    'valid_call is False). Counts are over all rows of the run; rates use usable replays of complete states only.',
    'Complete state: the state is in the states file and arms A, Aw, Hw and Ew each have a usable replay for seeds '
    '1, 2 and 3. A repeated (state, arm, seed) usable row would be counted and the first one kept.',
    '"Plain identifier" is the pattern [A-Za-z_][A-Za-z0-9_]* on the whole argument name.',
    '"Quotes, backslashes and spaces are removed": the characters double quote, single quote, backslash and the '
    'space character are deleted anywhere in the name (not only at the ends); the result must then EQUAL '
    'start_line or end_line (not merely contain it). Backticks, tabs and newlines are not removed. A sensitivity '
    'count under two looser readings (also removing backticks; any non-identifier name containing start_line or '
    'end_line) is printed in the data checks.',
    'F2 numerator: a usable replay whose first call is read_file and whose arguments hold at least one mangled '
    'line-bound name, whatever its value. A replay with two mangled names counts once.',
    'F2 "reads with a line bound": usable first-call read_file replays whose arguments hold start_line or end_line '
    'with a non-null value, or a mangled line-bound name with a non-null value. The share among them is clustered '
    'by state over the states that have at least one such read in the arm.',
    'F2 original runs: one observation per complete state (observed_next_call in the states file), scored with the '
    'same mangled-name rule, as a share of complete states and as a share of complete states whose observed call '
    'is a read with a line bound. The interval resamples states (each state is one cluster of size one). The '
    'observed call is used whatever its validity (all are valid in this states file).',
    'Rates are percent of usable replays on complete states (each replay weight 1); the bootstrap resamples states '
    'with replacement and takes the ratio of summed hits to summed replays. Contrasts are differences of these '
    'ratios on the same resampled states (paired by state).',
    'Bootstrap: numpy default_rng(0), 2,000 resamples; percentile bounds are order statistics b[int(0.025*n)] and '
    'b[int(0.975*n)-1] of the sorted resampled values. "Lower 95% bound above 0" is strict.',
    '"Any unopened true neighbor touched": a replay counts if fork_states.touches returns read or edit for at least '
    'one name in the state\'s unshown_true_neighbors that has a span in neighbor_spans, with the file\'s line '
    'lengths from nodes.file_text (exact character caps); graph returns do not count. A read under a mangled bound '
    'name is scored as the registered scorer reads it (the misnamed bound is ignored).',
    'F1: relative difference = (replayed - logged) / logged prompt tokens, computed here from the two token fields '
    '(the file\'s own diff field is not used); rows with an error or a missing or zero logged count are left out. '
    '"At most 0.5%" is inclusive. The mean and maximum are of the absolute relative differences.',
    'Descriptive tool mix: the first call\'s tool name over usable replays on complete states (interface failures '
    'are shown separately in S0). Same tool as the original: next_call function_name equals observed_next_call '
    'function_name, over usable replays on complete states. Same file: among replays where both calls are '
    'read_file, the filepath strings are equal after stripping whitespace and a leading "./", "/workspace/" or '
    '"workspace/".',
    'A partial run (fewer than 200 complete states) does not stop the script: the numbers are printed with an '
    'EXPLORATORY label.',
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


# ---------------------------------------------------------------- argument-name rules

def squeeze(name):
    """Remove quotes, backslashes and spaces from an argument name."""
    return re.sub(r'["\'\\ ]', '', str(name))


def is_mangled_bound(name):
    return not IDENT.match(str(name)) and squeeze(name) in BOUND_NAMES


def args_of(call):
    a = (call or {}).get('arguments')
    return a if isinstance(a, dict) else {}


def mangled_read(call):
    return (call or {}).get('function_name') == 'read_file' and any(is_mangled_bound(k) for k in args_of(call))


def bounded_read(call):
    if (call or {}).get('function_name') != 'read_file':
        return False
    for k, v in args_of(call).items():
        if v is None:
            continue
        if k in BOUND_NAMES or is_mangled_bound(k):
            return True
    return False


def norm_path(p):
    if not isinstance(p, str):
        return p
    p = p.strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


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


def classify(rows, states):
    info = dict(rows_per_arm=collections.Counter(), fails=collections.Counter(), dups=0,
                other_arms=collections.Counter(), other_seeds=0, unknown_states=set())
    usable = collections.defaultdict(dict)
    for r in rows:
        if r['arm'] not in ARMS:
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
    need = {(a, s) for a in ARMS for s in SEEDS}
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
    sp = s['neighbor_spans']
    unshown = [n for n in s['unshown_true_neighbors'] if sp.get(n)]
    obs = s.get('observed_next_call') or {}
    both_read = c.get('function_name') == 'read_file' and obs.get('function_name') == 'read_file'
    return dict(
        true_any=any(touched(c, sp[n], n, s['task']) for n in unshown),
        mangled=mangled_read(c),
        bounded=bounded_read(c),
        tool=c.get('function_name'),
        same_tool=c.get('function_name') == obs.get('function_name'),
        both_read=both_read,
        same_file=both_read and norm_path(args_of(c).get('filepath')) == norm_path(args_of(obs).get('filepath')),
    )


def score(usable, complete, states):
    recs = []
    for k in complete:
        s = states[k]
        for a in ARMS:
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


def _bounds(b):
    b = np.sort(b)
    n = len(b)
    return float(b[int(0.025 * n)]), float(b[int(0.975 * n) - 1])


def rate(pairs):
    d = _clusters(pairs)
    if not d:
        return None
    cl = sorted(d)
    s = np.array([d[c][0] for c in cl])
    n = np.array([d[c][1] for c in cl])
    idx = _draws(len(cl))
    b = 100 * s[idx].sum(1) / np.maximum(n[idx].sum(1), 1)
    return dict(est=100 * s.sum() / n.sum(), k=int(s.sum()), n=int(n.sum()), ci=_bounds(b), clusters=len(cl))


def diff(pairs_a, pairs_b):
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
    return dict(est=100 * (sa.sum() / na.sum() - sb.sum() / nb.sum()), ci=_bounds(b), clusters=len(cl))


def pairs(recs, arm, field, flt=None):
    return [(r['key'], float(r[field])) for r in recs if r['arm'] == arm and (flt is None or flt(r))]


def fmt_rate(t):
    if t is None:
        return 'n/a'
    lo, hi = t['ci']
    return f'{t["est"]:6.2f}% ({t["k"]}/{t["n"]}) 95% [{lo:.2f}, {hi:.2f}]'


def fmt_diff(t):
    if t is None:
        return 'n/a'
    lo, hi = t['ci']
    return f'{t["est"]:+.2f} points, 95% [{lo:+.2f}, {hi:+.2f}] ({t["clusters"]} states)'


def lower_above_zero(t):
    return t is not None and t['ci'][0] > 0


# ---------------------------------------------------------------- report sections

def header(out, run_dir, versions):
    out('Independent re-derivation of experiment F (pre-registration 07: how earlier tool results are rendered)')
    out('Script: analysis/rederive_w.py (imports only fork_states.touches, fork_states.valid_call and '
        'nodes.file_text; written without reading the registered analysis).')
    out(f'Run directory: {shown(run_dir)}')
    h = md5(STATES)
    out(f'States file: {shown(STATES)}, md5 {h} '
        f'({"matches" if h == MD5_STATES else "DIFFERS FROM"} the registered {MD5_STATES})')
    if versions:
        wheels = {}
        for w in versions.get('wheelhouse_files', []):
            name, _, rest = w.partition('-')
            if name in PREREG05_WHEELS or name in ('google_adk', 'vllm'):
                wheels[name] = rest.split('-')[0]
        model = str(versions.get('model_path') or '').split('models/', 1)[-1]  # the model id, without the mount point
        out(f'Run versions (versions.json): harness_variant {versions.get("harness_variant")}, wheels {wheels}, '
            f'model {model}, tensor_parallel_size {versions.get("tensor_parallel_size")}, platform '
            f'{versions.get("platform")}, gpu {versions.get("gpu")}, experiment field {versions.get("experiment")!r}, '
            f'arms field {versions.get("arms")}, thoughts_in_history {versions.get("thoughts_in_history")}')
        out(f'  wrapped_arms field: {versions.get("wrapped_arms")!r}')
    else:
        out('Run versions: no versions.json in the run directory.')
    out(f'Arms: {", ".join(ARMS)}; seeds 1-3. Bootstrap: clustered by state, {NB} resamples, numpy default_rng(0), '
        f'95% percentile intervals.')
    out()
    out('Ambiguities in the pre-registration texts and the readings taken here:')
    for i, a in enumerate(AMBIGUITIES, 1):
        out(f'  A{i}. {a}')
    out()


def counts_section(out, rows, usable, complete, info, states):
    out('S0. Counts')
    out(f'  rows read: {len(rows)}; rows per arm: {dict((a, info["rows_per_arm"][a]) for a in ARMS)}')
    if info['other_arms']:
        out(f'  rows of other arms (ignored): {dict(info["other_arms"])}')
    out(f'  rows with a seed outside 1-3: {info["other_seeds"]}; repeated (state, arm, seed) usable rows: '
        f'{info["dups"]}; row states not in the states file: {len(info["unknown_states"])}')
    out(f'  states with any usable row: {len(usable)}; states in the states file: {len(states)}')
    out('  interface failures per arm (all rows of the run):')
    for a in ARMS:
        tot = sum(info['fails'][(a, k)] for k in KINDS)
        n = info['rows_per_arm'][a]
        kinds = ', '.join(f'{k} {info["fails"][(a, k)]}' for k in KINDS)
        out(f'    {a:3s} {tot} of {n} ({100 * tot / n if n else 0:.2f}%): {kinds}')
    out(f'  complete states (arms {"/".join(ARMS)}, seeds 1-3 usable): {len(complete)}')
    ok = len(complete) >= MIN_COMPLETE
    out(f'  partial-run rule (at least {MIN_COMPLETE} complete states): '
        f'{"met, the rules apply" if ok else "NOT met, everything below is EXPLORATORY"}')
    out(f'  usable replays per arm on complete states: {len(complete) * len(SEEDS)}')
    out()
    return ok


def fidelity_numbers(fid):
    rel, tok, skipped = [], [], 0
    for f in fid:
        lg, rp = f.get('logged_prompt_tokens'), f.get('replayed_prompt_tokens')
        if f.get('error') or not lg or rp is None:
            skipped += 1
            continue
        rel.append((rp - lg) / lg)
        tok.append(rp - lg)
    return rel, tok, skipped


def fidelity_block(out, fid, label):
    if fid is None:
        out(f'  {label}: file missing')
        return None
    rel, tok, skipped = fidelity_numbers(fid)
    if not rel:
        out(f'  {label}: {len(fid)} rows, none usable')
        return None
    ab = [abs(x) for x in rel]
    med = 100 * statistics.median(ab)
    below = sum(1 for t in tok if t < 0)
    equal = sum(1 for t in tok if t == 0)
    above = sum(1 for t in tok if t > 0)
    out(f'  {label}: rows {len(fid)}, used {len(rel)}, left out (error or missing count) {skipped}, distinct states '
        f'{len({state_key(f) for f in fid})}')
    out(f'    |relative difference|: median {med:.3f}%, mean {100 * statistics.mean(ab):.3f}%, '
        f'max {100 * max(ab):.3f}%; signed median {100 * statistics.median(rel):+.3f}%')
    out(f'    replayed below logged {below}, equal {equal}, above {above}; largest |difference| in tokens '
        f'{max(abs(t) for t in tok)}; signed token differences from {min(tok)} to {max(tok)}')
    return med


def f1_section(out, run_dir, states):
    out('F1. Prompt size on the fidelity states (replayed versus logged prompt tokens)')
    fa = run_dir / 'fidelity.jsonl'
    fw = run_dir / 'fidelity_w.jsonl'
    fid_a = read_jsonl(fa) if fa.exists() else None
    fid_w = read_jsonl(fw) if fw.exists() else None
    med_a = fidelity_block(out, fid_a, 'arm A (fidelity.jsonl)')
    med_w = fidelity_block(out, fid_w, 'arm Aw (fidelity_w.jsonl)')
    if fid_a is not None and fid_w is not None:
        ka = {state_key(f) for f in fid_a}
        kw = {state_key(f) for f in fid_w}
        out(f'  same states in both files: {"yes" if ka == kw else "NO"} ({len(ka & kw)} shared)')
        lg_ok = sum(1 for f in fid_a + fid_w if state_key(f) in states and
                    f.get('logged_prompt_tokens') == states[state_key(f)].get('prompt_tokens_next_call_logged'))
        out(f'  logged counts equal to the states file\'s prompt_tokens_next_call_logged: {lg_ok} of '
            f'{len(fid_a) + len(fid_w)} rows')
    if med_w is None:
        out('  verdict (Aw): cannot be computed')
    elif med_w <= F1_THRESHOLD:
        out(f'  verdict (Aw, median {med_w:.3f}% <= {F1_THRESHOLD}%): the rendering accounts for the size gap.')
    else:
        out(f'  verdict (Aw, median {med_w:.3f}% > {F1_THRESHOLD}%): the rendering does not account for the size gap '
            f'(median above 0.5%).')
    if med_a is not None:
        out(f'  arm A beside it: median {med_a:.3f}%')
    out()


def f2_section(out, recs, complete, states, label):
    out(f'F2. Mangled line-bound names in the first call{label}')
    out('  share of usable replays whose first call is a read_file with a mangled line-bound name:')
    for a in ARMS:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "mangled")))}')
    out('  share among first-call reads with a line bound (correct or mangled):')
    for a in ARMS:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "mangled", lambda r: r["bounded"])))}')
    t = diff(pairs(recs, 'A', 'mangled'), pairs(recs, 'Aw', 'mangled'))
    out(f'  A minus Aw (share of usable replays, the registered contrast): {fmt_diff(t)}')
    if lower_above_zero(t):
        out('    verdict: the v28 rendering raises mangled bound names (lower 95% bound above 0).')
    else:
        out('    verdict: no detectable difference (lower 95% bound not above 0).')
    tb = diff(pairs(recs, 'A', 'mangled', lambda r: r['bounded']), pairs(recs, 'Aw', 'mangled', lambda r: r['bounded']))
    out(f'  A minus Aw among reads with a line bound (no rule): {fmt_diff(tb)}')
    # the original runs' own next call at the same complete states
    obs_all, obs_b = [], []
    for k in complete:
        c = states[k].get('observed_next_call')
        m = float(mangled_read(c))
        obs_all.append((k, m))
        if bounded_read(c):
            obs_b.append((k, m))
    n_valid = sum(1 for k in complete if states[k].get('observed_next_call_valid'))
    n_read = sum(1 for k in complete if (states[k].get('observed_next_call') or {}).get('function_name') == 'read_file')
    out(f'  original runs (observed_next_call, one per complete state; {n_valid} of {len(complete)} marked valid; '
        f'{n_read} are read_file):')
    out(f'    share of complete states: {fmt_rate(rate(obs_all))}')
    out(f'    share among observed reads with a line bound: {fmt_rate(rate(obs_b))}')
    out()


def f3_section(out, recs, label):
    out(f'F3. Any unopened true neighbor touched{label}')
    for a in ARMS:
        out(f'    {a:3s} {fmt_rate(rate(pairs(recs, a, "true_any")))}')
    t = diff(pairs(recs, 'Ew', 'true_any'), pairs(recs, 'Hw', 'true_any'))
    out(f'  Ew minus Hw (the registered contrast): {fmt_diff(t)}')
    if lower_above_zero(t):
        out('    verdict: holds under the original runs\' rendering (lower 95% bound above 0).')
    else:
        out('    verdict: not detected under the original rendering (lower 95% bound not above 0).')
    out('  descriptive, no rule:')
    for a, b in (('Aw', 'A'), ('Ew', 'Aw'), ('Hw', 'Aw')):
        out(f'    {a} minus {b}: {fmt_diff(diff(pairs(recs, a, "true_any"), pairs(recs, b, "true_any")))}')
    out()


def descriptive_section(out, recs, complete, states, label):
    out(f'S4. Descriptive, no rule: the first call\'s tool by arm (usable replays on complete states){label}')
    tools = sorted({r['tool'] for r in recs})
    for a in ARMS:
        cnt = collections.Counter(r['tool'] for r in recs if r['arm'] == a)
        n = sum(cnt.values())
        out(f'    {a:3s} ' + ', '.join(f'{t} {cnt[t]} ({100 * cnt[t] / n:.1f}%)' for t in tools if cnt[t]))
    obs = collections.Counter((states[k].get('observed_next_call') or {}).get('function_name') for k in complete)
    out(f'    original runs\' own next call on the {len(complete)} complete states: '
        + ', '.join(f'{t} {n}' for t, n in sorted(obs.items(), key=lambda x: str(x[0]))))
    out('  agreement with the original run\'s own next call (observed_next_call):')
    for a in ('A', 'Aw'):
        out(f'    {a:3s} same tool: {fmt_rate(rate(pairs(recs, a, "same_tool")))}')
        out(f'    {a:3s} same file, where both are read_file: '
            f'{fmt_rate(rate(pairs(recs, a, "same_file", lambda r: r["both_read"])))}')
    t = diff(pairs(recs, 'Aw', 'same_tool'), pairs(recs, 'A', 'same_tool'))
    out(f'    Aw minus A, same tool (no rule): {fmt_diff(t)}')
    out()


def data_checks(out, rows, states, recs, versions):
    out('S5. Data checks (descriptive; nothing here changes a number above)')
    no_all = sum(1 for r in rows if 'all_calls' not in r)
    mism = sum(1 for r in rows if r.get('all_calls') and r.get('next_call') != r['all_calls'][0])
    multi = collections.Counter(r['arm'] for r in rows if len(r.get('all_calls') or []) > 1)
    out(f'  rows without all_calls: {no_all}; rows whose next_call differs from all_calls[0]: {mism}; '
        f'rows with more than one call, by arm: {dict(multi)}')
    out(f'  rows with a non-null decoy field: {sum(1 for r in rows if r.get("decoy") is not None)}')
    node_mis = sum(1 for r in rows if state_key(r) in states and r.get('node') not in (None, states[state_key(r)]['node']))
    no_usage = sum(1 for r in rows if not r.get('usage'))
    out(f'  rows whose node differs from the state\'s node: {node_mis}; rows without usage: {no_usage}')
    odd = collections.Counter()
    for r in rows:
        c = r.get('next_call')
        for k in args_of(c):
            if not IDENT.match(str(k)):
                odd[(r['arm'], (c or {}).get('function_name'), k)] += 1
    out('  every non-identifier argument name in next_call over all rows (arm, tool, name): count')
    for (a, t, k), n in sorted(odd.items()):
        out(f'    {a:3s} {t} {k!r}: {n}  -> mangled line-bound name: {is_mangled_bound(k)}')
    # sensitivity of the mangled-name reading, over all rows
    loose1 = collections.Counter()
    loose2 = collections.Counter()
    strict = collections.Counter()
    for r in rows:
        c = r.get('next_call')
        if (c or {}).get('function_name') != 'read_file':
            continue
        ks = list(args_of(c))
        strict[r['arm']] += any(is_mangled_bound(k) for k in ks)
        loose1[r['arm']] += any(not IDENT.match(str(k)) and re.sub(r'["\'\\ `]', '', str(k)) in BOUND_NAMES for k in ks)
        loose2[r['arm']] += any(not IDENT.match(str(k)) and any(b in str(k) for b in BOUND_NAMES) for k in ks)
    out(f'  mangled reads over all rows, this reading: {dict((a, strict[a]) for a in ARMS)}; also removing '
        f'backticks: {dict((a, loose1[a]) for a in ARMS)}; any non-identifier name containing a bound name: '
        f'{dict((a, loose2[a]) for a in ARMS)}')
    n_m = collections.Counter(r['arm'] for r in recs if r['mangled'])
    n_mt = collections.Counter(r['arm'] for r in recs if r['mangled'] and r['true_any'])
    out(f'  on complete states, mangled reads by arm {dict((a, n_m[a]) for a in ARMS)}; of them counted as any '
        f'unopened true neighbor touched {dict((a, n_mt[a]) for a in ARMS)}')
    pt = collections.defaultdict(list)
    for r in rows:
        u = r.get('usage') or {}
        if u.get('prompt_tokens') is not None:
            pt[r['arm']].append(u['prompt_tokens'])
    out('  mean prompt tokens over all rows with a count: '
        + ', '.join(f'{a} {statistics.mean(pt[a]):.1f} (n={len(pt[a])})' for a in ARMS if pt[a]))
    by_tool = collections.Counter((r['arm'], (r.get('next_call') or {}).get('function_name')) for r in rows)
    for a in ARMS:
        out(f'  next-call tool mix over all rows (failures included), {a}: '
            f'{dict(sorted(((t or "none"), n) for (aa, t), n in by_tool.items() if aa == a))}')
    if versions:
        wheels = {}
        for w in versions.get('wheelhouse_files', []):
            name, _, rest = w.partition('-')
            if name in PREREG05_WHEELS:
                wheels[name] = rest.split('-')[0]
        diffs = {k: (wheels.get(k), v) for k, v in PREREG05_WHEELS.items() if wheels.get(k) != v}
        out(f'  harness wheels recorded versus those named in pre-registration 05 (recorded, named): '
            f'{diffs if diffs else "all equal"}')
    out(f'  files with no source text (line caps only, no character caps): {len(_missing_files)}')
    out()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dir')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    res = run_dir / 'results.jsonl'
    if not res.exists():
        sys.exit(f'No results.jsonl in {shown(run_dir)}: the run directory is missing or not downloaded yet.')
    rows = read_jsonl(res)
    ver = run_dir / 'versions.json'
    versions = json.loads(ver.read_text(encoding='utf-8')) if ver.exists() else None
    states = load_states(STATES)

    out = Report()
    header(out, run_dir, versions)
    usable, complete, info = classify(rows, states)
    enough = counts_section(out, rows, usable, complete, info, states)
    f1_section(out, run_dir, states)
    recs = score(usable, complete, states)
    label = '' if enough else ' [EXPLORATORY]'
    f2_section(out, recs, complete, states, label)
    f3_section(out, recs, label)
    descriptive_section(out, recs, complete, states, label)
    data_checks(out, rows, states, recs, versions)

    if args.no_write:
        print('\n(--no-write: nothing written; would have been analysis/results/rederive_w.txt)')
        return
    path = HERE / 'results' / 'rederive_w.txt'
    out.write(path)
    print(f'\nwrote {shown(path)}')


if __name__ == '__main__':
    main()
