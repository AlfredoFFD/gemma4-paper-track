"""Independent re-derivation of the experiment B numbers (sections 3.1, 4, 5 of the draft) from the raw replay logs.

Usage: py -I analysis/rederive_s5.py
Writes analysis/results/rederive_s5.txt. Only the registered scorer (fork_states.touches / valid_call) and the file
reader (nodes.file_text, for exact character caps) are imported; every other definition is written here.
"""
import collections
import json
import math
import re
import shlex
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from fork_states import touches, valid_call  # noqa: E402  registered scorer
import nodes as N  # noqa: E402  file contents for the character caps

ARMS = ['A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE']
GRAPH = {'get_code_neighbors', 'get_code_subgraph', 'search_similar_code'}
KNOWN = GRAPH | {'run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch'}
VIEW = {'cat', 'head', 'tail', 'sed', 'grep', 'rg', 'less', 'more', 'awk', 'nl', 'egrep', 'fgrep'}
NB = 2000
OUT = []


def out(s=''):
    OUT.append(s)
    print(s)


def norm(p):
    if not isinstance(p, str):
        return p
    p = p.strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def toint(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- load
states = {}
for l in open(HERE / 'fork_states' / 'states.jsonl', encoding='utf-8'):
    s = json.loads(l)
    s.pop('steps', None)
    states[(s['task'], s['run'], s.get('fork', 0))] = s
rows = []
for v in ('v5', 'v6', 'v8'):
    rows += [json.loads(l) for l in open(HERE / 'results' / v / 'forks' / 'results.jsonl', encoding='utf-8')]
gold_files = {}
for l in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8'):
    t = json.loads(l)
    fs = set()
    for line in (t.get('patch') or '').splitlines():
        if line.startswith('+++ b/') or line.startswith('--- a/'):
            fs.add(norm(line[6:].split('\t')[0]))
    gold_files[t['instance_id']] = fs


def invalid_kind(r):
    c = r.get('next_call')
    if r.get('error'):
        return 'error'
    if not c:
        return 'no_call'
    if c.get('function_name') not in KNOWN:
        return 'unknown_tool'
    if not valid_call(c):
        return 'malformed'
    return None


inval = collections.Counter()
inval_kind = collections.Counter()
dup = 0
by_state = collections.defaultdict(dict)
for r in rows:
    k = invalid_kind(r)
    if k:
        inval[r['arm']] += 1
        inval_kind[(r['arm'], k)] += 1
        continue
    key = (r['task'], r['run'], r.get('fork', 0))
    if (r['arm'], r['seed']) in by_state[key]:
        dup += 1
    by_state[key][(r['arm'], r['seed'])] = r
seeds = sorted({r['seed'] for r in rows})
complete = {k: v for k, v in by_state.items() if len(v) == len(ARMS) * len(seeds) and k in states}

# ---------------------------------------------------------------- per-file line lengths (exact caps)
_ll = {}


def lengths(task, path):
    if (task, path) not in _ll:
        src = N.file_text(task, path)
        _ll[(task, path)] = [len(x) for x in src.splitlines()] if src else None
    return _ll[(task, path)]


def hit(call, span, nid, task):
    """Registered touch outcome: a read or edit (graph mentions do not count)."""
    if not span:
        return False
    v = touches(call, span, nid, line_lengths=lengths(task, span['path']))
    return bool(v) and v != 'graph'


def graph_names(call, nid):
    if call['function_name'] not in GRAPH:
        return False
    blob = json.dumps(call['arguments'])
    short = nid.rsplit('.', 1)[-1]
    return nid in blob or re.search(r'\b' + re.escape(short) + r'\b', blob) is not None


def shell_stages(cmd):
    st = []
    for part in re.split(r'\|\|?|&&|;', cmd):
        part = part.strip()
        if not part:
            continue
        try:
            toks = shlex.split(part)
        except ValueError:
            toks = part.split()
        st.append(toks)
    return st


def opens_file(call, path):
    """The call opens or views this file at any lines (read_file, edit_file, write_file, or a shell view of it)."""
    fn, a = call['function_name'], call['arguments']
    if fn in ('read_file', 'edit_file', 'write_file'):
        return norm(a.get('filepath')) == path
    if fn == 'run_command':
        for toks in shell_stages(str(a.get('command', ''))):
            if toks and toks[0] in VIEW and any(norm(t) == path for t in toks[1:]):
                return True
    return False


def followed(call, nid, span):
    if span and opens_file(call, span['path']):
        return True
    short = nid.rsplit('.', 1)[-1]
    if call['function_name'] == 'run_command':
        cmd = str(call['arguments'].get('command', ''))
        if re.search(r'\b' + re.escape(short) + r'\b', cmd) or (span and span['path'] in cmd):
            return True
    return graph_names(call, nid)


def mentions(text, nid):
    short = nid.rsplit('.', 1)[-1]
    if len(short) < 4:
        return False
    return re.search(r'(?<![A-Za-z0-9_])' + re.escape(short) + r'(?![A-Za-z0-9_])', text or '') is not None


def e_list(s, arm='E'):
    txt = s['arms'][arm]['user_text']
    return json.loads(txt.split('returned:\n', 1)[1])['neighbors']


# ---------------------------------------------------------------- per-replay records
recs = []
entry_rank = []     # (arm E) state key, rank, touched
entry_matched = []  # (arm, key, touched) for matched true entries
entry_rew = []      # (arm, key, touched) for rewired entries
hits_detail = collections.defaultdict(list)   # arm -> list of (call, listed spans)
n_unshown_total = n_matched_total = 0
states_with_matched = set()
for key, reps in complete.items():
    s = states[key]
    task = s['task']
    sp = s['neighbor_spans']
    unshown = [n for n in s['unshown_true_neighbors'] if sp.get(n)]
    gf = gold_files.get(task, set())
    gids = set(s.get('gold_ids', []))
    fresh = set(s.get('fresh_true_neighbors', []))
    matched = [n for n in unshown if n in fresh and n not in gids and sp[n]['path'] not in gf]
    n_unshown_total += len(unshown)
    n_matched_total += len(matched)
    if matched:
        states_with_matched.add(key)
    rsp = s.get('rewired_spans') or {}
    rew = [n for n in s.get('rewired_entries', []) if rsp.get(n)]
    unshown_files = {sp[n]['path'] for n in unshown}
    gold_new = {f for f in gf if f not in set(s['shown_files'])}
    nb_in_gold = any(sp[n]['path'] in gf for n in unshown)
    elist = [x['name'] for x in e_list(s)]
    rank = {n: i + 1 for i, n in enumerate(elist)}
    for (arm, seed), r in reps.items():
        c = r['next_call']
        th = {n: hit(c, sp[n], n, task) for n in unshown}
        s1 = any(th.values())
        rh = {n: hit(c, rsp[n], n, task) for n in rew}
        rec = dict(key=key, task=task, repo=s['repo'], fork=key[2], arm=arm, seed=seed,
                   s1=s1, swapped=th.get(s['swapped_out'], False),
                   decoy=hit(c, s.get('decoy_span'), s['decoy'], task),
                   rew=any(rh.values()),
                   opened=any(opens_file(c, f) for f in unshown_files),
                   follow=any(followed(c, n, sp[n]) for n in unshown),
                   th_true=any(mentions(r.get('thought'), n) for n in fresh),
                   th_decoy=mentions(r.get('thought'), s['decoy']),
                   matched=any(th[n] for n in matched),
                   gold=any(opens_file(c, f) for f in gold_new),
                   nb_in_gold=nb_in_gold, fill=s.get('rewired_fill', 0),
                   ptok=(r.get('usage') or {}).get('prompt_tokens') or 0)
        recs.append(rec)
        if arm == 'E':
            for n in unshown:
                entry_rank.append((key, rank.get(n), th[n]))
        for n in matched:
            entry_matched.append((arm, key, th[n]))
        for n in rew:
            entry_rew.append((arm, key, rh[n]))
        if arm in ('A', 'H', 'D', 'E') and s1:
            hits_detail[arm].append((c, [sp[n] for n in s['true_neighbors'] if sp.get(n)]))
        if arm == 'RE' and rec['rew']:
            hits_detail['RE'].append((c, [rsp[n] for n in rew]))
        if arm == 'RE' and s1:
            hits_detail['RE_true'].append((c, [sp[n] for n in s['true_neighbors'] if sp.get(n)]))

# ---------------------------------------------------------------- bootstrap (clusters resampled with replacement)


def _agg(pairs, cluster):
    """pairs: iterable of (cluster_id, value). Returns cluster ids, sums, counts."""
    S, C = collections.defaultdict(float), collections.defaultdict(int)
    for cid, v in pairs:
        S[cid] += v
        C[cid] += 1
    return S, C


def _idx(n_clusters, seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_clusters, size=(NB, n_clusters))


def _pct(b):
    b = np.sort(b)
    return b[int(0.025 * len(b))], b[int(0.975 * len(b)) - 1]


def rate_ci(pairs):
    S, C = _agg(pairs, None)
    cl = sorted(C)
    if not cl or sum(C.values()) == 0:
        return None
    s = np.array([S[c] for c in cl]); n = np.array([C[c] for c in cl])
    I = _idx(len(cl))
    bs, bn = s[I].sum(1), n[I].sum(1)
    b = np.where(bn > 0, bs / np.maximum(bn, 1), np.nan)
    b = b[~np.isnan(b)]
    lo, hi = _pct(b)
    return 100 * s.sum() / n.sum(), 100 * lo, 100 * hi, int(n.sum())


def diff_ci(pairs_a, pairs_b):
    Sa, Ca = _agg(pairs_a, None)
    Sb, Cb = _agg(pairs_b, None)
    cl = sorted(set(Ca) | set(Cb))
    sa = np.array([Sa[c] for c in cl]); na = np.array([Ca[c] for c in cl])
    sb = np.array([Sb[c] for c in cl]); nb = np.array([Cb[c] for c in cl])
    I = _idx(len(cl))
    b = sa[I].sum(1) / np.maximum(na[I].sum(1), 1) - sb[I].sum(1) / np.maximum(nb[I].sum(1), 1)
    lo, hi = _pct(b)
    return 100 * (sa.sum() / na.sum() - sb.sum() / nb.sum()), 100 * lo, 100 * hi


def P(arm, field, by='key', flt=None):
    return [(r[by], float(r[field])) for r in recs if r['arm'] == arm and (flt is None or flt(r))]


def fr(t):
    if t is None:
        return 'n/a'
    if len(t) == 4:
        return f'{t[0]:6.2f}% [{t[1]:.2f}, {t[2]:.2f}] (n={t[3]})'
    return f'{t[0]:+6.2f} [{t[1]:+.2f}, {t[2]:+.2f}]'


def contrast(label, a, fa, b, fb, by='key', flt=None):
    out(f'  {label}: {fr(diff_ci(P(a, fa, by, flt), P(b, fb, by, flt)))}')


# ---------------------------------------------------------------- S0
out('Independent re-derivation of experiment B (blind to explore_b / recount_b / draft / NOTES).')
out(f'Bootstrap: 95% percentile, {NB} resamples, numpy default_rng(0), clusters = states unless stated; rates are % of replays.')
out()
out('S0. Counts')
out(f'  rows read: {len(rows)}; states in states.jsonl: {len(states)}; seeds: {seeds}; duplicate (state,arm,seed) rows: {dup}')
ck = list(complete)
out(f'  complete states (all 30 (arm,seed) replays valid): {len(ck)}')
out(f'  distinct tasks: all states {len({k[0] for k in states})}, complete {len({k[0] for k in ck})}')
out(f'  distinct (task, run): all states {len({k[:2] for k in states})}, complete {len({k[:2] for k in ck})}')
out(f'  states per repo (all): {dict(collections.Counter(s["repo"] for s in states.values()))}')
out(f'  states per repo (complete): {dict(collections.Counter(states[k]["repo"] for k in ck))}')
out(f'  states per fork index (complete): {dict(sorted(collections.Counter(k[2] for k in ck).items()))}')
out(f'  replays per arm (complete states): {dict(collections.Counter(r["arm"] for r in recs))}')
out(f'  invalid replays per arm (all rows): {{{", ".join(f"{a}: {inval[a]}" for a in ARMS)}}} total {sum(inval.values())}')
out(f'  invalid by kind: {dict(inval_kind)}')
out()

# ---------------------------------------------------------------- S1
out('S1. Registered outcome (read or edit of the entry\'s lines by the first call; graph mentions excluded)')
out('  any unopened true neighbor touched, by arm:')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "s1")))}')
out('  swapped-out entry touched, by arm:')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "swapped")))}')
out('  decoy touched, by arm:')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "decoy")))}')
out('  any rewired entry touched, by arm:')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "rew")))}')
out('  contrasts (paired by state):')
contrast('D-H', 'D', 's1', 'H', 's1')
contrast('E-H', 'E', 's1', 'H', 's1')
contrast('E-A', 'E', 's1', 'A', 's1')
contrast('H-A', 'H', 's1', 'A', 's1')
contrast('D-A', 'D', 's1', 'A', 's1')
contrast('E-D', 'E', 's1', 'D', 's1')
contrast('D minus RD-rewired', 'D', 's1', 'RD', 'rew')
contrast('E minus RE-rewired', 'E', 's1', 'RE', 'rew')
targets = {'A': 2.15, 'H': 2.75, 'D': 4.30, 'E': 8.25}
chk = [(a, rate_ci(P(a, 's1'))[0], t) for a, t in targets.items()]
chk += [('RD rew', rate_ci(P('RD', 'rew'))[0], 0.52), ('RE rew', rate_ci(P('RE', 'rew'))[0], 1.03),
        ('E-H', diff_ci(P('E', 's1'), P('H', 's1'))[0], 5.50)]
out('  sanity check vs registered targets: ' + '; '.join(f'{a} {v:.2f} vs {t:.2f} {"OK" if abs(v - t) <= 0.1 else "OFF"}' for a, v, t in chk))
out()

# ---------------------------------------------------------------- S2
out('S2. Robustness of E-H and D-H (S1 outcome)')
contrast('E-H by task', 'E', 's1', 'H', 's1', by='task')
contrast('D-H by task', 'D', 's1', 'H', 's1', by='task')
for sd in seeds:
    contrast(f'E-H seed {sd}', 'E', 's1', 'H', 's1', flt=lambda r, sd=sd: r['seed'] == sd)
    contrast(f'D-H seed {sd}', 'D', 's1', 'H', 's1', flt=lambda r, sd=sd: r['seed'] == sd)
for f in sorted({k[2] for k in ck}):
    nf = sum(1 for k in ck if k[2] == f)
    contrast(f'E-H fork {f} ({nf} states)', 'E', 's1', 'H', 's1', flt=lambda r, f=f: r['fork'] == f)
    contrast(f'D-H fork {f} ({nf} states)', 'D', 's1', 'H', 's1', flt=lambda r, f=f: r['fork'] == f)
for rp in sorted({states[k]['repo'] for k in ck}):
    ns = sum(1 for k in ck if states[k]['repo'] != rp)
    contrast(f'E-H without {rp} ({ns} states)', 'E', 's1', 'H', 's1', flt=lambda r, rp=rp: r['repo'] != rp)
    contrast(f'D-H without {rp} ({ns} states)', 'D', 's1', 'H', 's1', flt=lambda r, rp=rp: r['repo'] != rp)
tasks = sorted({k[0] for k in ck})


def point(arm_a, fa, arm_b, fb, flt):
    a = [r[fa] for r in recs if r['arm'] == arm_a and flt(r)]
    b = [r[fb] for r in recs if r['arm'] == arm_b and flt(r)]
    return 100 * (sum(a) / len(a) - sum(b) / len(b))


loto = [(point('E', 's1', 'H', 's1', lambda r, t=t: r['task'] != t), t) for t in tasks]
out(f'  leave-one-task-out E-H: min {min(loto)[0]:+.2f} (without {min(loto)[1]}), max {max(loto)[0]:+.2f} (without {max(loto)[1]})')
loto_d = [point('D', 's1', 'H', 's1', lambda r, t=t: r['task'] != t) for t in tasks]
out(f'  leave-one-task-out D-H: min {min(loto_d):+.2f}, max {max(loto_d):+.2f}')
eh = collections.Counter(r['task'] for r in recs if r['arm'] == 'E' and r['s1'])
top5 = [t for t, _ in eh.most_common(5)]
out(f'  E hits per task, top 5: {eh.most_common(5)}; total E hits {sum(eh.values())}; tasks with any E hit {len(eh)}')
contrast('E-H without top-5 E-hit tasks', 'E', 's1', 'H', 's1', flt=lambda r: r['task'] not in top5)
ns5 = sum(1 for k in ck if k[0] not in top5)
out(f'    ({ns5} states remain)')
anyhit = collections.defaultdict(lambda: collections.defaultdict(bool))
for r in recs:
    if r['s1']:
        anyhit[r['arm']][r['key']] = True
e_s = sum(anyhit['E'][k] for k in ck); h_s = sum(anyhit['H'][k] for k in ck)
b = sum(anyhit['E'][k] and not anyhit['H'][k] for k in ck); c = sum(anyhit['H'][k] and not anyhit['E'][k] for k in ck)
both = sum(anyhit['E'][k] and anyhit['H'][k] for k in ck)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


out(f'  McNemar by state (any of 3 seeds hit), E vs H: E {e_s}, H {h_s}, both {both}, E-only {b}, H-only {c}, exact two-sided p = {mcnemar(b, c):.3g}')
d_s = sum(anyhit['D'][k] for k in ck)
bd = sum(anyhit['D'][k] and not anyhit['H'][k] for k in ck); cd = sum(anyhit['H'][k] and not anyhit['D'][k] for k in ck)
out(f'  McNemar by state, D vs H: D {d_s}, H {h_s}, D-only {bd}, H-only {cd}, p = {mcnemar(bd, cd):.3g}')
out()

# ---------------------------------------------------------------- S3
out('S3. File level: the first call opens (read_file any lines, edit/write, or shell view) the file of an unopened true neighbor')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "opened")))}')
contrast('H-A', 'H', 'opened', 'A', 'opened')
contrast('E-D', 'E', 'opened', 'D', 'opened')
contrast('E-H', 'E', 'opened', 'H', 'opened')
contrast('D-H', 'D', 'opened', 'H', 'opened')
contrast('E-A', 'E', 'opened', 'A', 'opened')
out('  P(S1 touch | such a file opened), by arm (bootstrap by state over the opening replays):')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "s1", flt=lambda r: r["opened"])))}')
out()

# ---------------------------------------------------------------- S4
out('S4. How the hits were made (S1 hits; RE: rewired-entry hits, listed = rewired spans; A: listed = true spans)')
for a in ('A', 'H', 'D', 'E', 'RE', 'RE_true'):
    L = hits_detail[a]
    kinds = collections.Counter(c['function_name'] for c, _ in L)
    rf = [(c, spans) for c, spans in L if c['function_name'] == 'read_file']
    top = exact = first = neither = 0
    for c, spans in rf:
        s0, e0 = toint(c['arguments'].get('start_line')), toint(c['arguments'].get('end_line'))
        t = s0 is None or s0 == 1
        x_ = any(s0 == x['start'] and e0 == x['end'] for x in spans)
        f_ = (not x_) and s0 is not None and any(s0 in (x['start'], x.get('def_line')) for x in spans)
        top += t; exact += x_; first += f_; neither += not (t or x_ or f_)
    out(f'  {a}: hits {len(L)}; by call {dict(kinds)}; read_file {len(rf)}: from the top (start 1 or none) {top}, '
        f'exact start-end of a listed entry {exact}, start at an entry\'s first line without its end {first}, none of these {neither}')
out('  ("from the top" can overlap with "exact"/"first line" when an entry starts at line 1)')
out()

# ---------------------------------------------------------------- S5
out('S5. Followed by any means (opens/views the file, names the short name or path in a shell command, or a graph call names it)')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "follow")))}')
contrast('H-A', 'H', 'follow', 'A', 'follow')
contrast('E-D', 'E', 'follow', 'D', 'follow')
contrast('E-H', 'E', 'follow', 'H', 'follow')
contrast('E-H by task', 'E', 'follow', 'H', 'follow', by='task')
contrast('D-H', 'D', 'follow', 'H', 'follow')
out()

# ---------------------------------------------------------------- S6
out('S6. Thought mentions (thought field only; word-boundary short name, names < 4 chars skipped)')
for a in ARMS:
    out(f'    {a:3s} fresh true: {fr(rate_ci(P(a, "th_true")))} | decoy: {fr(rate_ci(P(a, "th_decoy")))}')
contrast('E-H fresh true', 'E', 'th_true', 'H', 'th_true')
contrast('D-H fresh true', 'D', 'th_true', 'H', 'th_true')
contrast('H-A fresh true', 'H', 'th_true', 'A', 'th_true')
out()

# ---------------------------------------------------------------- S7
out('S7. List position under E (rank in the E note\'s neighbors array; per (replay, unopened entry) touch rate)')
buckets = collections.OrderedDict([('rank 1', lambda k: k == 1), ('ranks 2-3', lambda k: 2 <= k <= 3),
                                   ('ranks 4-7', lambda k: 4 <= k <= 7), ('rank 8+', lambda k: k >= 8)])
for lab, f in buckets.items():
    sel = [(key, float(t)) for key, rk, t in entry_rank if rk is not None and f(rk)]
    out(f'  {lab}: {fr(rate_ci(sel))}; touched entries {int(sum(v for _, v in sel))}')
tot_entry_hits = sum(t for _, _, t in entry_rank)
r1_hits = sum(t for _, rk, t in entry_rank if rk == 1)
out(f'  entry-level: {r1_hits} of {tot_entry_hits} touched (replay, entry) pairs are the rank-1 entry ({100 * r1_hits / max(tot_entry_hits, 1):.1f}%)')
# replay level: of E replays with an S1 hit, share whose touched set includes the rank-1 entry
rk1 = collections.defaultdict(lambda: False)
for key, reps in complete.items():
    s = states[key]
    first = e_list(s)[0]['name']
    sp = s['neighbor_spans']
    for (arm, seed), r in reps.items():
        if arm == 'E' and first in s['unshown_true_neighbors'] and sp.get(first):
            rk1[(key, seed)] = hit(r['next_call'], sp[first], first, s['task'])
e_hits = [r for r in recs if r['arm'] == 'E' and r['s1']]
on1 = sum(rk1[(r['key'], r['seed'])] for r in e_hits)
out(f'  replay-level: {on1} of {len(e_hits)} E hit replays touch the rank-1 entry ({100 * on1 / max(len(e_hits), 1):.1f}%)')
n_r1_unshown = sum(1 for k in ck if e_list(states[k])[0]['name'] in states[k]['unshown_true_neighbors'])
out(f'  states whose rank-1 entry is an unopened true neighbor: {n_r1_unshown} of {len(ck)}')
out()

# ---------------------------------------------------------------- S8
out('S8. Matched true entries (unopened, not in view before the pause [= fresh_true_neighbors], not a gold node, not in a gold-patch file)')
out(f'  unopened true entries: {n_unshown_total} total; matched: {n_matched_total}; states with >=1 matched entry: {len(states_with_matched)} of {len(ck)}')
in_m = lambda r: r['key'] in states_with_matched  # noqa: E731
for a in ('A', 'H', 'D', 'E', 'RD', 'RE'):
    out(f'    {a:3s} any matched true touched, all states: {fr(rate_ci(P(a, "matched")))} | matched-states only: {fr(rate_ci(P(a, "matched", flt=in_m)))}')
contrast('E-H matched (all states)', 'E', 'matched', 'H', 'matched')
contrast('E matched minus RE rewired (all states, by state)', 'E', 'matched', 'RE', 'rew')
contrast('E matched minus RE rewired (all states, by task)', 'E', 'matched', 'RE', 'rew', by='task')
contrast('D matched minus RD rewired (all states, by state)', 'D', 'matched', 'RD', 'rew')
contrast('D matched minus RD rewired (all states, by task)', 'D', 'matched', 'RD', 'rew', by='task')
contrast('E matched minus RE rewired (matched-states only)', 'E', 'matched', 'RE', 'rew', flt=in_m)
contrast('D matched minus RD rewired (matched-states only)', 'D', 'matched', 'RD', 'rew', flt=in_m)
em = [(k, float(t)) for a, k, t in entry_matched if a == 'E']
rr = [(k, float(t)) for a, k, t in entry_rew if a == 'RE']
dm = [(k, float(t)) for a, k, t in entry_matched if a == 'D']
rd = [(k, float(t)) for a, k, t in entry_rew if a == 'RD']
out(f'  per-entry touch rate: E matched {fr(rate_ci(em))} | RE rewired {fr(rate_ci(rr))}')
out(f'  per-entry touch rate: D matched {fr(rate_ci(dm))} | RD rewired {fr(rate_ci(rd))}')
out()

# ---------------------------------------------------------------- S9
out('S9. Padding of the rewired lists')
n_rew = sum(len(states[k].get('rewired_entries', [])) for k in ck)
n_fill = sum(states[k].get('rewired_fill', 0) for k in ck)
n0 = sum(1 for k in ck if states[k].get('rewired_fill', 0) == 0)
out(f'  rewired entries in complete states: {n_rew}; padded {n_fill}; truly rewired {n_rew - n_fill}; states with fill 0: {n0}; '
    f'states fully padded (no true rewired entry): {sum(1 for k in ck if states[k].get("rewired_fill", 0) == len(states[k].get("rewired_entries", [])))}')
f0 = lambda r: r['fill'] == 0  # noqa: E731
out(f'  fill==0: E true {fr(rate_ci(P("E", "s1", flt=f0)))} | RE rewired {fr(rate_ci(P("RE", "rew", flt=f0)))}')
contrast('fill==0: E true minus RE rewired', 'E', 's1', 'RE', 'rew', flt=f0)
out(f'  fill==0: D true {fr(rate_ci(P("D", "s1", flt=f0)))} | RD rewired {fr(rate_ci(P("RD", "rew", flt=f0)))}')
contrast('fill==0: D true minus RD rewired', 'D', 's1', 'RD', 'rew', flt=f0)
out()

# ---------------------------------------------------------------- S10
out('S10. Toward the fix: the first call reads, edits or views a gold-patch file not already opened')
for a in ARMS:
    out(f'    {a:3s} {fr(rate_ci(P(a, "gold")))}')
contrast('E-A', 'E', 'gold', 'A', 'gold')
contrast('D-A', 'D', 'gold', 'A', 'gold')
contrast('E-H', 'E', 'gold', 'H', 'gold')
contrast('E-RE', 'E', 'gold', 'RE', 'gold')
ng = sum(1 for k in ck if any(states[k]['neighbor_spans'][n]['path'] in gold_files.get(k[0], set())
                              for n in states[k]['unshown_true_neighbors'] if states[k]['neighbor_spans'].get(n)))
out(f'  states where an unopened true neighbor sits in a gold-patch file: {ng}')
ig = lambda r: r['nb_in_gold']  # noqa: E731
for a in ARMS:
    out(f'    {a:3s} (those states) {fr(rate_ci(P(a, "gold", flt=ig)))}')
contrast('E-A (those states)', 'E', 'gold', 'A', 'gold', flt=ig)
contrast('D-A (those states)', 'D', 'gold', 'A', 'gold', flt=ig)
contrast('E-H (those states)', 'E', 'gold', 'H', 'gold', flt=ig)
contrast('E-RE (those states)', 'E', 'gold', 'RE', 'gold', flt=ig)
out()

# ---------------------------------------------------------------- S11
out('S11. Drift and length')
contrast('RD true minus A true', 'RD', 's1', 'A', 's1')
contrast('RE true minus A true', 'RE', 's1', 'A', 's1')
for a in ARMS:
    v = [r['ptok'] for r in recs if r['arm'] == a]
    out(f'    {a:3s} mean prompt_tokens {sum(v) / len(v):.0f}')

out()
out('Notes on definitions')
out(f'  gold-patch files are read from data/tasks.jsonl diffs; the rewired eligibility used the pointer-audit units file. '
    f'Rewired entries (complete states) that sit in a gold-diff file: '
    f'{sum(1 for k in ck for n in states[k]["rewired_entries"] if (states[k]["rewired_spans"].get(n) or {}).get("path") in gold_files.get(k[0], set()))}')
out('  S5 short-name match is a word-boundary regex on run_command text and on graph-tool arguments; read/edit/write count by file path only.')
out('  S6 uses the thought field only (the frozen secondary used thought+text with a substring match).')

if '--no-write' not in sys.argv[1:]:  # reproduce.py passes --no-write and reads the report from stdout
    (HERE / 'results' / 'rederive_s5.txt').write_text('\n'.join(OUT) + '\n', encoding='utf-8')
