"""EXPLORATORY robustness analyses for the fork-and-replay arms (A, P, Pp, H, Hp, D, Dp, E, RD, RE).

EXPLORATORY: nothing in this file was pre-registered. The confirmatory numbers are the ones analyze_b.py prints.
This script uses the same replays, the same interface-failure exclusions and the same complete-state rule, imports
the frozen scorer (fork_states.touches) and checks its vectorised bootstrap against the frozen one
(analyze_forks.boot_ci / diff_ci). It asks whether the headline survives looser definitions of "following a listed
entry" (searches, file-level reads, graph calls), other clusterings, and the known asymmetries between the true list
and the rewired list.

Usage: py -I analysis/explore_b.py [--v5 DIR] [--v6 DIR] [--v8 DIR] [--states FILE] [--out FILE] [--limit N]
The report goes to analysis/results/explore_b.txt. It holds aggregate counts only: no commands and no code.
"""
import argparse
import collections
import json
import math
import posixpath
import random
import re
import shlex
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from analyze_forks import GRAPH_TOOLS, KNOWN_TOOLS, boot_ci, diff_ci  # noqa: E402
from fork_states import VIEW_CMDS, _int, load_gold, norm_path, shell_view_range, touches, valid_call  # noqa: E402

ARMS_ALL = ['A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE']
FILE_TOOLS = ('read_file', 'edit_file', 'write_file')
BOOTS = 2000
CLASSES = ['test file', 'same directory as the node', 'same top-level package', 'elsewhere']
FLAGS = ['a', 'b', 'cp', 'cn', 'cns', 'c', 'd', 'dx', 'U', 'Us', 'Unn', 'loc', 'gs', 'dr', 'X', 'file', 'fileL', 'ch',
         'ls']
FI = {f: i for i, f in enumerate(FLAGS)}
NF = len(FLAGS)
BINS = [('1', 1, 1), ('2-3', 2, 3), ('4-7', 4, 7), ('8+', 8, 10 ** 9)]
KINDS = ['read_file from the top of the file', 'read_file, start and end = a listed range',
         'read_file, start = a listed start line', 'read_file, start = a listed def line',
         'read_file, another start line', 'shell, search by the entry name in its file',
         'shell, line range at a listed start', 'shell, other view of the file', 'edit or write']
PUNCT = set('();<>|&')
NAN3 = (float('nan'),) * 3
_IDX = {}


def resample_idx(n):
    """BOOTS x n cluster indices, drawn exactly as [rng.choice(clusters) for _ in clusters] with Random(0)."""
    if n not in _IDX:
        rng = random.Random(0)
        r = range(n)
        _IDX[n] = np.array([[rng.choice(r) for _ in r] for _ in range(BOOTS)], dtype=np.int64).reshape(BOOTS, n)
    return _IDX[n]


class Design:
    """Maps per-state arrays onto bootstrap clusters. labels: one per state; None drops the state."""

    def __init__(self, labels, order='sorted'):
        keep = [i for i, lab in enumerate(labels) if lab is not None]
        labs = [labels[i] for i in keep]
        uniq = sorted(set(labs)) if order == 'sorted' else list(dict.fromkeys(labs))
        pos = {lab: j for j, lab in enumerate(uniq)}
        self.keep = np.array(keep, dtype=np.int64)
        self.cl = np.array([pos[lab] for lab in labs], dtype=np.int64)
        self.C = len(uniq)
        self.n = len(keep)

    def sums(self, v):
        v = np.asarray(v, dtype=float)
        return np.bincount(self.cl, weights=v[self.keep], minlength=self.C) if self.C else np.zeros(0)


def _boot(design, num, den):
    idx = resample_idx(design.C)
    nc, dc = design.sums(num), design.sums(den)
    return nc.sum(), dc.sum(), nc[idx].sum(axis=1), dc[idx].sum(axis=1)


def rate_ci(design, num, den):
    """Ratio of sums with a percentile interval (equals boot_ci when the clusters are states in file order)."""
    if design.C == 0:
        return NAN3
    n, d, nb, db = _boot(design, num, den)
    if not d:
        return NAN3
    ok = db > 0
    boots = np.sort(nb[ok] / db[ok])
    return n / d, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]


def lin_ci(design, terms, level=0.95):
    """Sum of w * rate over terms [(w, num, den)] on the same resamples (equals diff_ci for weights +1, -1)."""
    if design.C == 0:
        return NAN3
    point = 0.0
    boots = np.zeros(BOOTS)
    for w, num, den in terms:
        n, d, nb, db = _boot(design, num, den)
        point += w * (n / d if d else 0.0)
        boots += w * np.divide(nb, db, out=np.zeros_like(nb), where=db > 0)
    boots.sort()
    return point, boots[int((1 - level) / 2 * len(boots))], boots[int((1 - (1 - level) / 2) * len(boots)) - 1]


def mcnemar(x, y):
    """Discordant counts (x only, y only) and the exact two-sided p value."""
    x, y = np.asarray(x).astype(bool).ravel(), np.asarray(y).astype(bool).ravel()
    b, c = int((x & ~y).sum()), int((~x & y).sum())
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)
    return b, c, p


def load_rows(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh]


def is_test(path):
    return '/tests/' in '/' + path or path.rsplit('/', 1)[-1].startswith('test_')


def loc_class(path, node_path):
    if is_test(path):
        return 0
    if posixpath.dirname(path) == posixpath.dirname(node_path or ''):
        return 1
    return 2 if path.split('/')[0] == (node_path or '').split('/')[0] else 3


def specific(short):
    return len(short) >= 6 and not (short.startswith('__') and short.endswith('__'))


def pc(t):
    p, lo, hi = t
    return 'n/a' if p != p else f'{100 * p:5.2f}% [{100 * lo:5.2f}, {100 * hi:5.2f}]'


def pp(t):
    p, lo, hi = t
    return 'n/a' if p != p else f'{100 * p:+6.2f} [{100 * lo:+6.2f}, {100 * hi:+6.2f}]'


def is_punct(tok):
    return bool(tok) and all(ch in PUNCT for ch in tok)


def shell_parts(cmd):
    """Sub-commands of a chained command (split on ; && || & and line breaks), each rebuilt as one string."""
    line = cmd.strip()
    if '<<' in line:
        line = line.split('\n', 1)[0]
    line = re.sub(r'\s*\n\s*', ' ; ', line)
    try:
        lex = shlex.shlex(line, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = re.findall(r'&&|\|\||[;|&]|[^\s;|&]+', line)
    subs = [[]]
    for t in toks:
        if is_punct(t) and t != '|' and (';' in t or '&&' in t or '||' in t or t == '&'):
            subs.append([])
        else:
            subs[-1].append(t)
    subs = [x for x in subs if any(not is_punct(t) for t in x)]
    return [' '.join(t if is_punct(t) else shlex.quote(t) for t in x) for x in subs]


def call_context(call, snap):
    """What the call names: a file-tool path, shell path tokens and identifiers, viewed paths, guessed modules."""
    fn, args = call['function_name'], call['arguments']
    ctx = {'fn': fn, 'args': args, 'fpath': None, 'toks': frozenset(), 'words': frozenset(), 'ghosts': frozenset(),
           'viewpaths': frozenset(), 'lspaths': frozenset(), 'subcalls': [], 'chain': False, 'blob': ''}
    named = []
    if fn in FILE_TOOLS:
        raw = args.get('filepath')
        fp = norm_path(raw) if isinstance(raw, str) else None
        if fp:
            ctx['fpath'] = fp
            named.append(fp)
    elif fn == 'run_command':
        cmd = str(args.get('command', ''))
        toks = {norm_path(t).rstrip('./') for t in re.findall(r'[\w./-]+', cmd)}
        toks.discard('')
        ctx['toks'] = frozenset(toks)
        ctx['words'] = frozenset(re.findall(r'[A-Za-z0-9_]+', cmd))
        vp = set()  # the frozen source-stage rule: stages split on the raw '|', first token a view command
        for st in (x.strip() for x in cmd.split('|')):
            if not st:
                continue
            try:
                tk = shlex.split(st)
            except ValueError:
                tk = st.split()
            if tk and tk[0] in VIEW_CMDS:
                vp.update(norm_path(t) for t in tk[1:])
        ctx['viewpaths'] = frozenset(vp)
        subs = shell_parts(cmd)
        lp = set()  # paths named by an ls stage of any sub-command (a locate step, not a read)
        for st in (x.strip() for part in (subs or [cmd]) for x in part.split('|')):
            try:
                tk = shlex.split(st)
            except ValueError:
                tk = st.split()
            if tk and tk[0] == 'ls':
                lp.update(norm_path(t) for t in tk[1:])
        ctx['lspaths'] = frozenset(lp)
        if len(subs) > 1:
            ctx['chain'] = True
            ctx['subcalls'] = [{'function_name': 'run_command', 'arguments': {'command': sub}} for sub in subs]
        named.extend(t for t in toks if t.endswith('.py'))
    elif fn in GRAPH_TOOLS:
        ctx['blob'] = json.dumps(args)
    ghosts = set()
    for p in named:
        if p in snap:
            continue
        mod = p[:-3] if p.endswith('.py') else p
        if mod.endswith('/__init__'):
            mod = mod[:-len('/__init__')]
        mod = mod.strip('/').replace('/', '.')
        if mod.count('.') >= 1:
            ghosts.add(mod)
    ctx['ghosts'] = frozenset(ghosts)
    return ctx


def entry_flags(call, ctx, e):
    """One tuple of booleans per (call, listed entry), in the order of FLAGS."""
    v = touches(call, e['span'], e['id'], line_lengths=e['lens'])
    a, d = v in ('read', 'edit'), v == 'graph'
    path, toks = e['path'], ctx['toks']
    b = ctx['fpath'] == path
    cp = path in toks
    cn = e['short'] in ctx['words']
    cns = cn and e['spec']
    dx = bool(ctx['blob']) and e['id'] in ctx['blob']
    ds = dx or (d and e['spec'])
    loc = False
    if not b and not cp:
        fp = ctx['fpath'] or ''
        loc = bool(e['sufs'] & toks) or fp in e['sufs'] or fp.endswith('/' + path) \
            or any(t.endswith('/' + path) for t in toks)
    gs = bool(e['prefixes'] & ctx['ghosts'])
    dr = bool(e['dir']) and e['dir'] in toks
    view = path in ctx['viewpaths']
    ch = a or any(touches(sc, e['span'], e['id'], line_lengths=e['lens']) in ('read', 'edit')
                  for sc in ctx['subcalls'])
    c = cp or cn
    u = a or b or c or d
    return (a, b, cp, cn, cns, c, d, dx, u, a or b or cp or cns or ds, a or b or cp or d, loc, gs, dr,
            u or loc or gs, a or b or view, a or b or cp, ch, path in ctx['lspaths'])


def hit_kind(call, hits, listed):
    """How a frozen-scorer hit was made. hits: touched entries; listed: (start, end, def_line) in the same file."""
    fn, args = call['function_name'], call['arguments']
    if fn in ('edit_file', 'write_file'):
        return 8
    if fn == 'read_file':
        a, b = _int(args.get('start_line')), _int(args.get('end_line'))
        if not a or a <= 1:
            return 0
        if any(a == s and b == e for s, e, _ in listed):
            return 1
        if any(a == s for s, _, _ in listed):
            return 2
        return 3 if any(a == dl for _, _, dl in listed) else 4
    cmd = str(args.get('command', ''))
    views = [shell_view_range(cmd, e['path'], e['short'], None) for e in hits]
    if any(v and v[0] == 'named' for v in views):
        return 5
    starts = {s for s, _, _ in listed} | {dl for _, _, dl in listed}
    if any(v and v[0] == 'lines' and v[1] and v[1] > 1 and v[1] in starts for v in views):
        return 6
    return 7


def tool_class(fn):
    if fn == 'read_file':
        return 0
    if fn == 'run_command':
        return 1
    if fn in ('edit_file', 'write_file'):
        return 2
    return 3 if fn in GRAPH_TOOLS else 4


def main():
    ap = argparse.ArgumentParser()
    base = HERE / 'results'
    ap.add_argument('--v5', default=str(base / 'v5' / 'forks'))
    ap.add_argument('--v6', default=str(base / 'v6' / 'forks'))
    ap.add_argument('--v8', default=str(base / 'v8' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states' / 'states.jsonl'))
    ap.add_argument('--out', default=str(base / 'explore_b.txt'))
    ap.add_argument('--limit', type=int, default=0, help='development only: use the first N complete states')
    ap.add_argument('--stdout', action='store_true', help='print the report instead of writing it (for reproduce.py)')
    args = ap.parse_args()

    # ---- loading, exclusions and the complete-state rule: the same steps as analyze_b.py ----
    states = {(s['task'], s['run'], s.get('fork', 0)): s for s in load_rows(args.states)}
    rows, sessions = [], []
    for name, d in (('v5', args.v5), ('v6', args.v6), ('v8', args.v8)):
        part = load_rows(Path(d) / 'results.jsonl')
        sessions.append((name, len(part), sorted({r['arm'] for r in part}, key=ARMS_ALL.index)))
        rows += part
    n_states_seen = len({(r['task'], r['run'], r.get('fork', 0)) for r in rows})
    fail = collections.Counter()
    ok = []
    for r in rows:
        call = r.get('next_call')
        if r.get('error'):
            fail[(r['arm'], 'error')] += 1
        elif not call:
            fail[(r['arm'], 'no_call')] += 1
        elif call['function_name'] not in KNOWN_TOOLS:
            fail[(r['arm'], 'unknown_tool')] += 1
        elif not valid_call(call):
            fail[(r['arm'], 'malformed_args')] += 1
        else:
            ok.append(r)
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    seeds = sorted({r['seed'] for r in ok})
    arms = sorted({r['arm'] for r in ok}, key=ARMS_ALL.index)
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms) * len(seeds)}
    missing = [a for a in ('A', 'H', 'D', 'E', 'RD', 'RE') if a not in arms]
    if missing or not complete:
        sys.exit(f'cannot run: arms missing {missing}; complete states {len(complete)}')
    keys = list(complete)
    n_complete = len(keys)
    if args.limit:
        keys = keys[:args.limit]
    S, K, NA = len(keys), len(seeds), len(arms)
    AI = {a: i for i, a in enumerate(arms)}
    KI = {sd: i for i, sd in enumerate(seeds)}

    # ---- caches ----
    len_cache, snap_cache, rw_cache = {}, {}, {}

    def lengths(task, path):
        if (task, path) not in len_cache:
            src = N.file_text(task, path)
            len_cache[(task, path)] = [len(x) for x in src.splitlines()] if src else None
        return len_cache[(task, path)]

    def snapshot(task):
        if task not in snap_cache:
            snap_cache[task] = set(N.snapshot_files(task))
        return snap_cache[task]

    def rewired_real(s):
        """The node's neighbors in the rewired graph (list entries outside this set were padded); None if unknown."""
        g = s.get('graph')
        if g not in rw_cache:
            try:
                with open(HERE.parent / 'data' / 'cache' / 'rewired' / f'{g}.json', encoding='utf-8') as fh:
                    rw_cache[g] = json.load(fh)['neighbors']
            except (OSError, KeyError, ValueError):
                rw_cache[g] = None
        return None if rw_cache[g] is None else set(rw_cache[g].get(s['node'], []))

    try:
        gold_ids, gold_paths = load_gold()
        gold_note = 'gold patches loaded'
    except Exception as exc:  # noqa: BLE001  (the matched set then relies on the gold ids stored in the states)
        gold_ids, gold_paths = collections.defaultdict(set), collections.defaultdict(set)
        gold_note = f'gold patches NOT loaded ({type(exc).__name__}); the matched set uses the stored gold ids only'

    def make_entry(task, n, sp, node_path, true, rank=0):
        path = sp['path']
        parts, ids = path.split('/'), n.split('.')
        short = ids[-1]
        return {'id': n, 'span': sp, 'path': path, 'short': short, 'spec': specific(short), 'true': true, 'rank': rank,
                'sufs': frozenset('/'.join(parts[i:]) for i in range(1, len(parts))) - {'__init__.py'},
                'dir': posixpath.dirname(path), 'prefixes': frozenset('.'.join(ids[:i]) for i in range(2, len(ids) + 1)),
                'cls': loc_class(path, node_path), 'lens': lengths(task, path)}

    # ---- storage: per entry subset a count array (arm, state, seed, flag); per replay and per state arrays ----
    CNT = collections.defaultdict(lambda: np.zeros((NA, S, K, NF), dtype=np.int16))
    Z = collections.defaultdict(lambda: np.zeros(S, dtype=np.int64))
    shape = (NA, S, K)
    TOOL = np.zeros(shape, dtype=np.int8)
    CHAIN = np.zeros(shape, dtype=bool)
    THO = np.zeros(shape, dtype=bool)
    MEN = {k: np.zeros(shape, dtype=bool) for k in ('t', 'tw', 'r', 'rw')}
    SW = np.zeros(shape, dtype=bool)
    DEC = np.zeros(shape, dtype=bool)
    KIND = {k: np.full(shape, -1, dtype=np.int8) for k in 'TR'}
    MINR = np.zeros(shape, dtype=np.int32)
    PTOK = np.zeros(shape, dtype=float)
    FILL = np.zeros(S, dtype=np.int64)
    NFILES = {k: np.zeros(S, dtype=np.int64) for k in 'TR'}
    tasks, repos, forks = [], [], []
    pad_known = pad_mismatch = snap_seen = snap_found = 0

    # ---- the replay loop ----
    for si, key in enumerate(keys):
        s = states[key]
        task = s['task']
        spans, dspan = s['neighbor_spans'], s['decoy_span']
        unshown = set(s.get('unshown_true_neighbors', s['true_neighbors']))
        fresh = s.get('fresh_true_neighbors', list(unshown))
        fresh_set = set(fresh)
        rsp = s.get('rewired_spans', {})
        node_path = (s.get('node_span') or {}).get('path')
        gids = set(s.get('gold_ids', [])) | gold_ids[task]
        gpaths = gold_paths[task]
        snap = snapshot(task)
        real = rewired_real(s)
        entries = []
        listed = {'T': collections.defaultdict(list), 'R': collections.defaultdict(list)}
        for i, n in enumerate(s['true_neighbors']):
            sp = spans.get(n)
            if not sp:
                continue
            listed['T'][sp['path']].append((sp['start'], sp['end'], sp.get('def_line')))
            if n not in unshown:
                continue
            e = make_entry(task, n, sp, node_path, True, i + 1)
            e['subs'] = ['T', f'T:{e["cls"]}', 'Tt' if e['cls'] == 0 else 'Tnt', 'Tf' if n in fresh_set else 'Tv',
                         'Tg' if e['path'] in gpaths else 'Tng',
                         'Tr:' + next(lab for lab, lo, hi in BINS if lo <= i + 1 <= hi)]
            if n in fresh_set and n not in gids and e['path'] not in gpaths:
                e['subs'].append('Tm')
            entries.append(e)
        n_pad = 0
        for n in s.get('rewired_entries', []):
            sp = rsp.get(n)
            if not sp:
                continue
            listed['R'][sp['path']].append((sp['start'], sp['end'], sp.get('def_line')))
            e = make_entry(task, n, sp, node_path, False)
            e['subs'] = ['R', f'R:{e["cls"]}', 'Rt' if e['cls'] == 0 else 'Rnt']
            if real is not None:
                e['subs'].append('Rr' if n in real else 'Rp')
                n_pad += n not in real
            entries.append(e)
        if real is not None:
            pad_known += 1
            pad_mismatch += n_pad != s.get('rewired_fill', 0)
        for e in entries:
            for sub in e['subs']:
                Z[sub][si] += 1
        fresh_short = [n.rsplit('.', 1)[-1] for n in fresh]
        rew_short = [e['short'] for e in entries if not e['true']]
        fresh_spec = {x for x in fresh_short if specific(x)}
        rew_spec = {x for x in rew_short if specific(x)}

        for (arm, seed), r in complete[key].items():
            ai, ki = AI[arm], KI[seed]
            call = r['next_call']
            ctx = call_context(call, snap)
            acc = {}
            hits = {'T': [], 'R': []}
            for e in entries:
                fl = entry_flags(call, ctx, e)
                if not any(fl):
                    continue
                v = np.array(fl, dtype=np.int16)
                for sub in e['subs']:
                    acc[sub] = (acc[sub] + v) if sub in acc else v
                if fl[0]:
                    hits['T' if e['true'] else 'R'].append(e)
            for sub, v in acc.items():
                CNT[sub][ai, si, ki] = v
            TOOL[ai, si, ki] = tool_class(call['function_name'])
            CHAIN[ai, si, ki] = ctx['chain']
            THO[ai, si, ki] = bool(r.get('thought'))
            th = (r.get('thought') or '') + ' ' + (r.get('text') or '')
            words = set(re.findall(r'[A-Za-z0-9_]+', th))
            MEN['t'][ai, si, ki] = any(x in th for x in fresh_short)      # the frozen rule: substring match
            MEN['tw'][ai, si, ki] = bool(fresh_spec & words)              # whole identifier, specific names only
            MEN['r'][ai, si, ki] = any(x in th for x in rew_short)
            MEN['rw'][ai, si, ki] = bool(rew_spec & words)
            SW[ai, si, ki] = any(e['id'] == s.get('swapped_out') for e in hits['T'])
            if dspan:
                DEC[ai, si, ki] = touches(call, dspan, s['decoy'],
                                          line_lengths=lengths(task, dspan['path'])) in ('read', 'edit')
            for tag in 'TR':
                if hits[tag]:
                    lst = [x for p in {e['path'] for e in hits[tag]} for x in listed[tag].get(p, [])]
                    KIND[tag][ai, si, ki] = hit_kind(call, hits[tag], lst)
            MINR[ai, si, ki] = min((e['rank'] for e in hits['T']), default=0)
            PTOK[ai, si, ki] = (r.get('usage') or {}).get('prompt_tokens') or 0

        tasks.append(task)
        repos.append(str(s.get('repo', '')).split('/')[-1])
        forks.append(key[2])
        FILL[si] = s.get('rewired_fill', 0)
        NFILES['T'][si] = len({e['path'] for e in entries if e['true']})
        NFILES['R'][si] = len({e['path'] for e in entries if not e['true']})
        snap_seen += len(entries)
        snap_found += sum(e['path'] in snap for e in entries)

    # ---- accessors and bootstrap designs ----
    DEN = np.full(S, K, dtype=float)
    D_FIRST = Design(keys, 'first')      # clusters in file order, as boot_ci takes them
    D_SORT = Design(keys, 'sorted')      # clusters sorted, as diff_ci takes them
    D_TASK = Design(tasks, 'sorted')
    n_rep = S * K

    def anyn(sub, flag, arm):
        """Per state: the number of seeds in which any entry of the subset has the flag ('D+E' pools arms)."""
        return sum((CNT[sub][AI[a], :, :, FI[flag]] > 0).sum(axis=1) for a in arm.split('+'))

    def cntn(sub, flag, arm):
        """Per state: the number of (entry, seed) pairs with the flag."""
        return CNT[sub][AI[arm], :, :, FI[flag]].sum(axis=1)

    def den(arm):
        return DEN * len(arm.split('+'))

    def R1(sub, flag, arm, design=None):
        return rate_ci(design or D_FIRST, anyn(sub, flag, arm), den(arm))

    def DIFF(terms, design=None):
        """A linear contrast of any-level rates; terms are (weight, subset, flag, arm)."""
        return lin_ci(design or D_SORT, [(w, anyn(sub, flag, arm), den(arm)) for w, sub, flag, arm in terms])

    def PER(sub, flag, arm, design=None):
        """Per-entry rate: flagged (entry, seed) pairs over all (entry, seed) pairs of the subset."""
        return rate_ci(design or D_FIRST, cntn(sub, flag, arm), Z[sub] * K)

    def frozen_dict(sub, arm, labels=None):
        d = collections.defaultdict(list)
        hit = CNT[sub][AI[arm], :, :, 0] > 0
        for i, key in enumerate(keys):
            d[labels[i] if labels else key].extend(int(x) for x in hit[i])
        return d

    # ---- self-check of the fast bootstrap against the frozen functions ----
    EH = [(1, 'T', 'a', 'E'), (-1, 'T', 'a', 'H')]
    checks = [(boot_ci(frozen_dict('T', a)), R1('T', 'a', a)) for a in ('A', 'E')]
    checks.append((diff_ci(frozen_dict('T', 'E'), frozen_dict('T', 'H')), DIFF(EH)))
    checks.append((diff_ci(frozen_dict('T', 'E'), frozen_dict('R', 'RE')),
                   DIFF([(1, 'T', 'a', 'E'), (-1, 'R', 'a', 'RE')])))
    checks.append((diff_ci(frozen_dict('T', 'E', tasks), frozen_dict('T', 'H', tasks)), DIFF(EH, D_TASK)))
    dev = max(abs(x - y) for fz, mine in checks if fz[0] is not None for x, y in zip(fz, mine))
    assert dev < 1e-12, f'bootstrap self-check failed: max deviation {dev}'

    # ---- report ----
    L = []
    out = L.append

    def head(title):
        out('')
        out(f'== {title} ==')

    kinds = collections.Counter()
    for (_, kind), c in fail.items():
        kinds[kind] += c
    repo_n = collections.Counter(repos)
    out('EXPLORATORY robustness analyses of the fork-and-replay arms. Nothing in this file was pre-registered.')
    out('The confirmatory numbers are the ones the frozen analysis (analyze_b.py) prints; this file only probes them.')
    if args.limit:
        out('*** DEVELOPMENT RUN on a subset of the states (--limit): not for reporting ***')
    out('')
    out(f'Data: {len(rows)} replays over {n_states_seen} states. Sessions: '
        + '; '.join(f'{nm} ({c} replays, arms {" ".join(a)})' for nm, c, a in sessions) + '.')
    out(f'Interface failures excluded: {sum(fail.values())} ('
        + ', '.join(f'{k} {v}' for k, v in sorted(kinds.items())) + ').')
    out(f'Complete states (every arm x seed valid): {n_complete}. Used here: {S} states x {K} seeds = {n_rep} replays '
        f'per arm, from {len(set(tasks))} tasks; states per repo: '
        + ', '.join(f'{k} {v}' for k, v in sorted(repo_n.items())) + '.')
    out('Intervals: 95% percentile bootstrap, 2,000 resamples, seed 0, resampling states unless a line says tasks.')
    out('Rates are % of replays and differences are percentage points, unless a line says otherwise.')
    out('Sessions: v5 ran A P Pp H Hp, v6 ran D Dp E, v8 ran RD RE. No arm was repeated across sessions, so every')
    out('contrast between sessions (E - H, E - RE, D - RD) also carries any drift between sessions (see E7).')
    out(f'Self-check: the fast bootstrap reproduces the frozen boot_ci and diff_ci (max abs deviation {dev:.1e}).')
    out(f'Entry files found in the task snapshots: {snap_found} of {snap_seen}. Gold patches: {gold_note}.')
    out(f'Padded-entry marker derived for {pad_known} of {S} states; it disagrees with the stored fill count in '
        f'{pad_mismatch} states.')
    out('"true" = the scored true entries (unshown true neighbors with spans); "rewired" = the rewired list entries.')

    head('1. Raw counts per arm, frozen scorer (must equal the frozen analysis)')
    out(f'  count of {n_rep} replays, rate and interval')
    out(f'  {"arm":<5}{"any true neighbor":<29}{"any rewired entry":<29}{"swapped-out entry":<29}decoy')
    for a in arms:
        cols = (anyn('T', 'a', a), anyn('R', 'a', a), SW[AI[a]].sum(axis=1), DEC[AI[a]].sum(axis=1))
        out(f'  {a:<5}' + '   '.join(f'{int(v.sum()):>4} {pc(rate_ci(D_FIRST, v, DEN))}' for v in cols))
    out('  frozen contrasts: D - H ' + pp(DIFF([(1, 'T', 'a', 'D'), (-1, 'T', 'a', 'H')])) + ' | E - H ' + pp(DIFF(EH)))
    out('                    D true - RD rewired ' + pp(DIFF([(1, 'T', 'a', 'D'), (-1, 'R', 'a', 'RD')]))
        + ' | E true - RE rewired ' + pp(DIFF([(1, 'T', 'a', 'E'), (-1, 'R', 'a', 'RE')])))

    # ---- items 2 and 3: following by any means, and file-level following ----
    def con(flag):
        def T(w, arm):
            return (w, 'T', flag, arm)

        def R(w, arm):
            return (w, 'R', flag, arm)
        return [('H - A (true)', [T(1, 'H'), T(-1, 'A')]),
                ('D - H (true)', [T(1, 'D'), T(-1, 'H')]),
                ('E - H (true)', [T(1, 'E'), T(-1, 'H')]),
                ('E - D (true)', [T(1, 'E'), T(-1, 'D')]),
                ('D true - RD rewired', [T(1, 'D'), R(-1, 'RD')]),
                ('E true - RE rewired', [T(1, 'E'), R(-1, 'RE')]),
                ('(D, E) true - (RD, RE) rewired', [T(1, 'D+E'), R(-1, 'RD+RE')]),
                ('(D true - A true) - (RD rew - A rew)', [T(1, 'D'), T(-1, 'A'), R(-1, 'RD'), R(1, 'A')]),
                ('(E true - A true) - (RE rew - A rew)', [T(1, 'E'), T(-1, 'A'), R(-1, 'RE'), R(1, 'A')])]

    def contrast_table(flags, design=None):
        tabs = {f: con(f) for f in flags}
        out('  ' + f'{"contrast (points)":<40}' + ''.join(f'{f:<27}' for f in flags))
        for i, (lab, _) in enumerate(tabs[flags[0]]):
            out('  ' + f'{lab:<40}' + ''.join(f'{pp(DIFF(tabs[f][i][1], design)):<27}' for f in flags))

    COMP = ['a', 'b', 'cp', 'cn', 'cns', 'c', 'd', 'dx']
    UNI = ['a', 'U', 'Us', 'Unn']
    SUBS = (('T', 'TRUE entries'), ('R', 'REWIRED entries (shown only under RD and RE; in other arms a base rate)'))
    head('2. Following by ANY means (the next call), per arm')
    out('  Flags per (call, listed entry): a = touch by the frozen scorer; b = read_file / edit_file / write_file on')
    out("  the entry's file at any lines; cp = shell command naming the entry's file path; cn = shell command with the")
    out('  short name as a whole identifier; cns = cn with a specific name (6+ characters, not a dunder); c = cp or cn;')
    out('  d = graph-tool call naming the node (frozen rule); dx = graph-tool call with the full id in its arguments.')
    out('  U = a or b or c or d (the union asked for). Us = U with name matches kept only for specific names.')
    out('  Unn = a or b or cp or d (U without the shell name match). Counts = replays with any entry flagged.')
    out('  "U not a" = replays that follow by some other means but do not touch; "name only" = replays in U only')
    out('  through the shell name match (the search route the worry is about).')
    for sub, lab in SUBS:
        out('')
        out(f'  2{"a" if sub == "T" else "b"}. {lab}')
        out('  ' + f'{"arm":<5}' + ''.join(f'{f:>5}' for f in COMP) + f'{"U not a":>9}{"name only":>11}   '
            + ''.join(f'{f:<25}' for f in UNI))
        for a in arms:
            n = {f: int(anyn(sub, f, a).sum()) for f in COMP + UNI}
            out('  ' + f'{a:<5}' + ''.join(f'{n[f]:>5}' for f in COMP) + f'{n["U"] - n["a"]:>9}{n["U"] - n["Unn"]:>11}   '
                + ''.join(f'{pc(R1(sub, f, a)):<25}' for f in UNI))
    out('')
    out('  2c. Differences, for the touch (a) and for each union')
    contrast_table(UNI)
    out('')
    out('  2d. Wider nets (extras). loc = a loose path match (a path suffix of the entry file is named; generic file')
    out('  names inflate it); gs = a nonexistent path is named whose module form is a prefix of the entry id (a guessed')
    out("  path); dr = the entry's directory is named in a shell command (not in X); X = U or loc or gs;")
    out('  ch = chain-aware touch (the frozen scorer applied to each sub-command of a chained shell command).')
    for sub, lab in SUBS:
        out(f'  {lab}')
        out('  ' + f'{"arm":<5}' + ''.join(f'{f:>5}' for f in ('loc', 'gs', 'dr')) + '   '
            + ''.join(f'{f:<25}' for f in ('X', 'ch')))
        for a in arms:
            out('  ' + f'{a:<5}' + ''.join(f'{int(anyn(sub, f, a).sum()):>5}' for f in ('loc', 'gs', 'dr')) + '   '
                + ''.join(f'{pc(R1(sub, f, a)):<25}' for f in ('X', 'ch')))
    contrast_table(['X', 'ch'])

    head('3. File-level following (the entry file is opened or viewed at ANY line), per arm')
    out('  file = a or b or a shell view command (cat, sed, head, tail, grep, rg, less, more, awk) on the file;')
    out('  fileL = a or b or cp (any shell command naming the path). P(touch | file) = touch replays / file replays:')
    out('  given that the model opened a listed file, how often the lines it asked for overlap a listed entry.')
    out('  ls = replays in which an ls stage names an entry file (a locate step: counted in fileL and in U, not in')
    out('  file).')
    for sub, lab in SUBS:
        out('')
        out(f'  {lab}')
        out(f'  {"arm":<5}{"file":<30}{"fileL":<30}{"P(touch | file)":<25}ls')
        for a in arms:
            cond = rate_ci(D_FIRST, anyn(sub, 'a', a), anyn(sub, 'file', a))
            out(f'  {a:<5}' + ''.join(f'{int(anyn(sub, f, a).sum()):>4} {pc(R1(sub, f, a)):<25}' for f in ('file', 'fileL'))
                + f'{pc(cond):<25}{int(anyn(sub, "ls", a).sum()):>2}')
    out('')
    contrast_table(['file', 'fileL'])

    # ---- item 4: task clustering ----
    CA, CU = con('a'), con('U')
    ERE = CA[5][1]
    head('4. Primary outcome re-clustered by TASK')
    out(f'  The same point estimates with {D_TASK.C} tasks instead of {S} states as the bootstrap clusters.')
    out(f'  {"":<40}{"clusters = states":<27}clusters = tasks')
    for a in ('A', 'H', 'D', 'E'):
        out(f'  {"any true, arm " + a:<40}{pc(R1("T", "a", a)):<27}{pc(R1("T", "a", a, D_TASK))}')
    for a in ('RD', 'RE'):
        out(f'  {"any rewired, arm " + a:<40}{pc(R1("R", "a", a)):<27}{pc(R1("R", "a", a, D_TASK))}')
    for i in (1, 2, 3, 4, 5, 7, 8):
        lab, terms = CA[i]
        out(f'  {lab:<40}{pp(DIFF(terms)):<27}{pp(DIFF(terms, D_TASK))}')
    out('  the same for the any-means union U:')
    for i in (2, 5, 8):
        lab, terms = CU[i]
        out(f'  {lab:<40}{pp(DIFF(terms)):<27}{pp(DIFF(terms, D_TASK))}')

    # ---- item 5: repositories ----
    head('5. Per repository (frozen touch)')
    names = sorted(set(repos))
    out(f'  {"repo":<10}{"states":>7}{"replays":>8}   '
        + ''.join(f'{x:<25}' for x in ('A true', 'H true', 'D true', 'E true', 'RE rewired')))
    for rp in names:
        dz = Design([k if repos[i] == rp else None for i, k in enumerate(keys)], 'first')
        cells = [pc(R1('T', 'a', a, dz)) for a in ('A', 'H', 'D', 'E')] + [pc(R1('R', 'a', 'RE', dz))]
        out(f'  {rp:<10}{dz.n:>7}{dz.n * K:>8}   ' + ''.join(f'{c:<25}' for c in cells))
    out('  leave one repository out:')
    for rp in names:
        dz = Design([k if repos[i] != rp else None for i, k in enumerate(keys)], 'sorted')
        out(f'    without {rp:<10}({dz.n:>4} states)  E - H {pp(DIFF(EH, dz))}   E true - RE rewired {pp(DIFF(ERE, dz))}')
    tot = D_TASK.sums(DEN)

    def loo(num_x, num_y):
        x, y = D_TASK.sums(num_x), D_TASK.sums(num_y)
        v = ((x.sum() - x) - (y.sum() - y)) / (tot.sum() - tot)
        return f'{100 * v.min():+.2f} to {100 * v.max():+.2f}'

    out(f'  leave one task out ({D_TASK.C} tasks), range of the point estimate: E - H '
        + loo(anyn('T', 'a', 'E'), anyn('T', 'a', 'H')) + '; E true - RE rewired '
        + loo(anyn('T', 'a', 'E'), anyn('R', 'a', 'RE')))

    # ---- item 6: seeds and fork index ----
    head('6. Per seed and per fork index (frozen touch)')
    ONE = np.ones(S)
    cols6 = [('T', a) for a in ('A', 'H', 'D', 'E')] + [('R', 'RE')]
    out(f'  {"":<24}' + ''.join(f'{("true, " if sub == "T" else "rewired, ") + a:<25}' for sub, a in cols6) + 'E - H')
    for sd in seeds:
        cells = [pc(rate_ci(D_FIRST, CNT[sub][AI[a], :, KI[sd], 0] > 0, ONE)) for sub, a in cols6]
        dif = lin_ci(D_SORT, [(1, CNT['T'][AI['E'], :, KI[sd], 0] > 0, ONE), (-1, CNT['T'][AI['H'], :, KI[sd], 0] > 0, ONE)])
        out(f'  {"seed " + str(sd):<24}' + ''.join(f'{c:<25}' for c in cells) + pp(dif))
    for fk in sorted(set(forks)):
        dz = Design([k if forks[i] == fk else None for i, k in enumerate(keys)], 'first')
        out(f'  {"fork " + str(fk) + " (" + str(dz.n) + " states)":<24}'
            + ''.join(f'{pc(R1(sub, "a", a, dz)):<25}' for sub, a in cols6) + pp(DIFF(EH, dz)))

    # ---- item 7: paired tests ----
    head('7. Paired tests (exact two-sided McNemar)')
    out('  Pairs = the same state and seed under two arms. Seed pairing across different prompts is nominal and the')
    out('  three pairs of a state are not independent, so the state-level column (any of the 3 seeds) is the safer one.')
    out('  Each cell: hits under x vs hits under y, then the discordant counts (x only / y only) and p.')

    def hitm(sub, flag, arm):
        return CNT[sub][AI[arm], :, :, FI[flag]] > 0

    def mc_line(lab, x, y):
        cells = []
        for name, xx, yy in (('pairs', x, y), ('states', x.any(axis=1), y.any(axis=1))):
            b, c, p = mcnemar(xx, yy)
            cells.append(f'{name}: {int(xx.sum()):>3} vs {int(yy.sum()):>3}, {b:>3} / {c:>3}, p = {p:<8.2g}')
        out(f'  {lab:<40}' + ' | '.join(cells))

    for x, y in (('E', 'H'), ('E', 'A'), ('E', 'D'), ('D', 'H'), ('D', 'A'), ('H', 'A')):
        mc_line(f'{x} vs {y}: touch of a true entry', hitm('T', 'a', x), hitm('T', 'a', y))
    for x, y in (('E', 'H'), ('E', 'A'), ('D', 'H'), ('H', 'A')):
        mc_line(f'{x} vs {y}: any means (U), true entry', hitm('T', 'U', x), hitm('T', 'U', y))
    for x, y in (('E', 'RE'), ('D', 'RD')):
        mc_line(f'{x} true vs {y} rewired: touch', hitm('T', 'a', x), hitm('R', 'a', y))
        mc_line(f'{x} true vs {y} rewired: any means (U)', hitm('T', 'U', x), hitm('R', 'U', y))
    for x in ('RE', 'RD'):
        mc_line(f'{x} vs A: touch of a rewired entry', hitm('R', 'a', x), hitm('R', 'a', 'A'))
        mc_line(f'{x} vs A: any means (U), rewired entry', hitm('R', 'U', x), hitm('R', 'U', 'A'))
        mc_line(f'{x} vs A: touch of a true entry', hitm('T', 'a', x), hitm('T', 'a', 'A'))

    # ---- item 8: how the hits were made ----
    head('8. How the hits were made (frozen touch)')
    R4 = ('A', 'H', 'D', 'E')
    RF = [0, 1, 2, 3, 4]
    cols8 = [('T', a) for a in R4] + [('R', 'RD'), ('R', 'RE')]
    kc = {c: np.bincount(KIND[c[0]][AI[c[1]]][KIND[c[0]][AI[c[1]]] >= 0], minlength=len(KINDS)) for c in cols8}
    out('  Replays with a hit, by the kind of call that made it: true-entry hits under A, H, D, E and rewired-entry hits')
    out('  under RD, RE. "listed" = a line of the list as E (or RE) writes it: every list entry with a span in the file.')
    out(f'  {"kind of call":<46}' + ''.join(f'{("true " if t == "T" else "rew. ") + a:>9}' for t, a in cols8))
    for i, lab in enumerate(KINDS):
        out(f'  {lab:<46}' + ''.join(f'{int(kc[c][i]):>9}' for c in cols8))
    out(f'  {"all hits":<46}' + ''.join(f'{int(kc[c].sum()):>9}' for c in cols8))

    def share(c, idx):
        n = int(kc[c].sum())
        return f'{100 * kc[c][idx].sum() / n:.1f}%' if n else 'n/a'

    for lab, idx in (('share by read_file', RF), ('share by shell', [5, 6, 7]), ('share by edit or write', [8])):
        out(f'  {lab:<46}' + ''.join(f'{share(c, idx):>9}' for c in cols8))

    def kshare(c, num):
        k = KIND[c[0]][AI[c[1]]]
        return pc(rate_ci(D_FIRST, np.isin(k, num).sum(axis=1), np.isin(k, RF).sum(axis=1)))

    out('  Among read_file hits: the share whose start_line is a listed start line (with or without the listed end),')
    out('  the share that asks for exactly a listed range, and the share that reads from the top of the file:')
    for c in cols8:
        out(f'    {("true, " if c[0] == "T" else "rewired, ") + c[1]:<13}listed start {kshare(c, [1, 2]):<23}'
            f'exact range {kshare(c, [1]):<23}from the top {kshare(c, [0])}')
    out('')
    out('  Rank of the touched entry in the listed order (rank 1 = the first line of the list). "per entry" = touched')
    out('  (entry, seed) pairs over all (entry, seed) pairs of the rank bin; "lowest" = replays whose lowest touched')
    out('  rank falls in the bin.')
    out(f'  {"rank":<6}{"entries":>8}   ' + ''.join(f'{"per entry, " + a:<25}' for a in R4)
        + ''.join(f'{"lowest, " + a:>11}' for a in R4))
    for lab, lo, hi in BINS:
        sub = 'Tr:' + lab
        low = [int(((MINR[AI[a]] >= lo) & (MINR[AI[a]] <= hi)).sum()) for a in R4]
        out(f'  {lab:<6}{int(Z[sub].sum()):>8}   ' + ''.join(f'{pc(PER(sub, "a", a)):<25}' for a in R4)
            + ''.join(f'{x:>11}' for x in low))
    out('')
    out('  Any-true rate by the number of scored true entries of the state:')
    out(f'  {"entries":<9}{"states":>7}   ' + ''.join(f'{a:<25}' for a in R4) + 'E - H')
    for lab, lo, hi in BINS:
        dz = Design([k if lo <= Z['T'][i] <= hi else None for i, k in enumerate(keys)], 'first')
        out(f'  {lab:<9}{dz.n:>7}   ' + ''.join(f'{pc(R1("T", "a", a, dz)):<25}' for a in R4) + pp(DIFF(EH, dz)))

    # ---- item 9: mentions in the thought text ----
    head('9. Mentions of a listed entry in the thought text')
    out('  P(mention | thought text present). "frozen rule" = the short name of a fresh true entry is a substring of')
    out('  the thought and message text; "specific" = a specific short name (6+ characters, not a dunder) appears as a')
    out('  whole identifier. The rewired columns apply the same two rules to the rewired list (a base rate in the arms')
    out('  that do not show it; under RD and RE the true columns are the base rate).')
    MK = (('t', 'true, frozen rule'), ('tw', 'true, specific'), ('r', 'rewired, frozen rule'), ('rw', 'rewired, specific'))
    out(f'  {"arm":<5}{"thought present":<25}' + ''.join(f'{lab:<25}' for _, lab in MK))

    def men(k, a):
        th = THO[AI[a]]
        return (MEN[k][AI[a]] & th).sum(axis=1), th.sum(axis=1)

    for a in arms:
        out(f'  {a:<5}{pc(rate_ci(D_FIRST, THO[AI[a]].sum(axis=1), DEN)):<25}'
            + ''.join(f'{pc(rate_ci(D_FIRST, *men(k, a))):<25}' for k, _ in MK))
    for kt, kr, lab in (('t', 'r', 'frozen rule'), ('tw', 'rw', 'specific')):
        cells = [f'{x} true - {y} rewired ' + pp(lin_ci(D_SORT, [(1, *men(kt, x)), (-1, *men(kr, y))]))
                 for x, y in (('D', 'RD'), ('E', 'RE'))]
        cells.append('E - H (true) ' + pp(lin_ci(D_SORT, [(1, *men(kt, 'E')), (-1, *men(kt, 'H'))])))
        out(f'  {lab}: ' + ' | '.join(cells))

    # ---- item 10: padded vs truly rewired ----
    head('10. Rewired entries: padded from the directory vs truly rewired')
    out('  The states hold no per-entry marker, only a fill count per state. Derived marker: a rewired-list entry that')
    out("  is not a neighbor of the node in the cached rewired graph was padded from the node's own directory.")
    if not pad_known:
        out('  The rewiring cache could not be read here, so there is no split.')
    else:
        out(f'  Entries: {int(Z["Rr"].sum())} truly rewired and {int(Z["Rp"].sum())} padded; {int((FILL > 0).sum())} of {S} '
            f'states have padding ({int((Z["Rr"] > 0).sum())} states list a truly rewired entry, '
            f'{int((Z["Rp"] > 0).sum())} a padded one).')
        out('  The any-entry rates are over all replays (a state without such an entry cannot score), so the per-entry')
        out('  rates are the fair comparison between the two kinds.')
        out(f'  {"touch (count, rate)":<22}' + ''.join(f'{x:<29}' for x in ('truly rewired, any entry', 'padded, any entry'))
            + ''.join(f'{x:<25}' for x in ('truly rewired, per entry', 'padded, per entry')))
        for a in ('RE', 'RD', 'A', 'H', 'E'):
            out(f'  {"arm " + a:<22}'
                + ''.join(f'{int(anyn(sub, "a", a).sum()):>3} {pc(R1(sub, "a", a)):<25}' for sub in ('Rr', 'Rp'))
                + ''.join(f'{pc(PER(sub, "a", a)):<25}' for sub in ('Rr', 'Rp')))
        out('  any means (U): ' + ' | '.join(
            f'{a}: truly rewired {int(anyn("Rr", "U", a).sum())} ({pc(R1("Rr", "U", a))}), padded '
            f'{int(anyn("Rp", "U", a).sum())} ({pc(R1("Rp", "U", a))})' for a in ('RE', 'A')))
        for lab, cond in (('no padding', FILL == 0), ('some padding', FILL > 0)):
            dz = Design([k if cond[i] else None for i, k in enumerate(keys)], 'first')
            out(f'  states with {lab} ({dz.n}): RE rewired {pc(R1("R", "a", "RE", dz))}; RD rewired '
                f'{pc(R1("R", "a", "RD", dz))}; E true {pc(R1("T", "a", "E", dz))}; E true - RE rewired '
                f'{pp(DIFF(ERE, dz))}')

    # ---- extras (not asked for; each one tests an asymmetry between the true list and the rewired list) ----
    head('E1. Eligibility-matched true entries')
    out('  The rewired list was built only from entries whose name is not in view, that are not gold-patch nodes and')
    out('  whose file is unopened and not a gold-patch file. The scored true entries are in unopened files too, but')
    out('  they may have a name already in view, be gold-patch nodes or sit in a gold-patch file.')
    out('  "matched" = the scored true entries that pass the same filter. Rates are % of replays with any such entry')
    out('  touched; the right column keeps only the states that have a matched entry.')
    dm = Design([k if Z['Tm'][i] > 0 else None for i, k in enumerate(keys)], 'first')
    dms = Design([k if Z['Tm'][i] > 0 else None for i, k in enumerate(keys)], 'sorted')
    W = 58
    out(f'  Matched: {int(Z["Tm"].sum())} of {int(Z["T"].sum())} scored true entries, in {dm.n} of {S} states.')
    out(f'  {"":<{W}}{"all states":<27}states with a matched entry ({dm.n})')
    for a in R4:
        out(f'  {"matched true, touch, arm " + a:<{W}}{pc(R1("Tm", "a", a)):<27}{pc(R1("Tm", "a", a, dm))}')
    for a in ('RD', 'RE'):
        out(f'  {"rewired, touch, arm " + a:<{W}}{pc(R1("R", "a", a)):<27}{pc(R1("R", "a", a, dm))}')

    def mcon(flag):
        def T(w, arm):
            return (w, 'Tm', flag, arm)

        def R(w, arm):
            return (w, 'R', flag, arm)
        return [('E - H (matched true)', [T(1, 'E'), T(-1, 'H')]),
                ('D - H (matched true)', [T(1, 'D'), T(-1, 'H')]),
                ('D matched true - RD rewired', [T(1, 'D'), R(-1, 'RD')]),
                ('E matched true - RE rewired', [T(1, 'E'), R(-1, 'RE')]),
                ('(E - A) matched true - (RE - A) rewired', [T(1, 'E'), T(-1, 'A'), R(-1, 'RE'), R(1, 'A')])]

    for flag, lab2 in (('a', 'touch'), ('U', 'any means (U)')):
        for lab, terms in mcon(flag):
            out(f'  {lab + ", " + lab2:<{W}}{pp(DIFF(terms)):<27}{pp(DIFF(terms, dms))}')

    head('E2. True entries split by gold-patch file and by whether the name was already in view')
    out('  % of replays with any entry of the subset touched (all states in the denominator).')
    out(f'  {"subset":<30}{"entries":>8}{"states":>8}   ' + ''.join(f'{a:<25}' for a in R4) + 'E - H')
    for sub, lab in (('Tg', 'in a gold-patch file'), ('Tng', 'not in a gold-patch file'), ('Tf', 'name not in view (fresh)'),
                     ('Tv', 'name already in view'), ('Tm', 'matched (E1)'), ('T', 'all scored true entries')):
        out(f'  {lab:<30}{int(Z[sub].sum()):>8}{int((Z[sub] > 0).sum()):>8}   '
            + ''.join(f'{pc(R1(sub, "a", a)):<25}' for a in R4) + pp(DIFF([(1, sub, 'a', 'E'), (-1, sub, 'a', 'H')])))

    head('E3. Per-entry touch rates by where the entry lives')
    out('  Location relative to the node the state is about. Rate = touched (entry, seed) pairs over all (entry, seed)')
    out('  pairs of the class, in %.')
    RW = ('A', 'RD', 'RE')
    for tag, lab0, cols in (('T', 'TRUE entries', R4), ('R', 'REWIRED entries', RW)):
        out(f'  {lab0:<30}{"entries":>8}   ' + ''.join(f'{"per entry, " + a:<25}' for a in cols))
        for sub, lab in [(f'{tag}:{i}', x) for i, x in enumerate(CLASSES)] + [(tag + 'nt', 'all non-test'), (tag, 'all')]:
            out(f'  {lab:<30}{int(Z[sub].sum()):>8}   ' + ''.join(f'{pc(PER(sub, "a", a)):<25}' for a in cols))

    def per_diff(sx, ax, sy, ay):
        return pp(lin_ci(D_SORT, [(1, cntn(sx, 'a', ax), Z[sx] * K), (-1, cntn(sy, 'a', ay), Z[sy] * K)]))

    PAIRS = (('all', 'T', 'R'), ('test files', 'Tt', 'Rt'), ('non-test', 'Tnt', 'Rnt'), ('same directory', 'T:1', 'R:1'))
    out('  E true - RE rewired, per entry (points):')
    out('    ' + ' | '.join(f'{lab} {per_diff(sx, "E", sy, "RE")}' for lab, sx, sy in PAIRS))
    out('  E true - RE rewired, any entry of the class (points of replays):')
    out('    ' + ' | '.join(f'{lab} {pp(DIFF([(1, sx, "a", "E"), (-1, sy, "a", "RE")]))}' for lab, sx, sy in PAIRS))

    head('E4. List sizes')
    n_true = np.array([sum(1 for n in states[k]['true_neighbors'] if states[k]['neighbor_spans'].get(n)) for k in keys])
    out(f'  Entries with a span per state: true list mean {n_true.mean():.1f}, of which scored (unshown) mean '
        f'{Z["T"].mean():.1f}, median {np.median(Z["T"]):.0f}; rewired list mean {Z["R"].mean():.1f}, median '
        f'{np.median(Z["R"]):.0f} (all scored).')
    out(f'  Distinct files among the scored entries: true mean {NFILES["T"].mean():.1f}, rewired mean '
        f'{NFILES["R"].mean():.1f}.')
    out('  More scored entries and more files mean more chances of an accidental touch, so the any-entry rates do not')
    out('  favour the true list on this count; the per-entry rates are in E3.')

    head('E5. Concentration of the hits')
    out('  How many states and tasks the hit replays come from, and the share held by the tasks with the most hits.')
    for sub, a in cols6 + [('R', 'RD')]:
        e = anyn(sub, 'a', a)
        tk = np.sort(D_TASK.sums(e))[::-1]
        th = int(e.sum())
        out(f'  {("true, " if sub == "T" else "rewired, ") + a:<13}{th:>4} hit replays from {int((e > 0).sum()):>3} states '
            f'(all {K} seeds: {int((e == K).sum()):>2}) and {int((tk > 0).sum()):>2} of {D_TASK.C} tasks; top task '
            f'{100 * tk[:1].sum() / max(th, 1):.0f}%, top 5 tasks {100 * tk[:5].sum() / max(th, 1):.0f}%')
    e = anyn('T', 'a', 'E')
    tsum = collections.Counter()
    for i, t in enumerate(tasks):
        tsum[t] += int(e[i])
    top = {t for t, _ in tsum.most_common(5)}
    dz = Design([k if tasks[i] not in top else None for i, k in enumerate(keys)], 'sorted')
    out(f'  without the 5 tasks with the most E hits ({dz.n} states): E - H {pp(DIFF(EH, dz))}; E true - RE rewired '
        f'{pp(DIFF(ERE, dz))}')

    head('E6. Tool mix of the next call, and the touch rate within a tool')
    TN = ('read_file', 'shell', 'edit/write', 'graph tool', 'other')
    out('  Share of replays by the tool of the next call; then P(touch | tool) for the true entries and for the rewired')
    out('  entries (the rewired entries are shown only under RD and RE).')
    out(f'  {"arm":<5}' + ''.join(f'{x:>12}' for x in TN) + f'{"chained":>10}   '
        + ''.join(f'{x:<25}' for x in ('true | read_file', 'true | shell', 'rewired | read_file', 'rewired | shell')))
    for a in arms:
        t = TOOL[AI[a]]
        cells = [pc(rate_ci(D_FIRST, ((CNT[sub][AI[a], :, :, 0] > 0) & (t == i)).sum(axis=1), (t == i).sum(axis=1)))
                 for sub in 'TR' for i in (0, 1)]
        out(f'  {a:<5}' + ''.join(f'{100 * (t == i).mean():>11.1f}%' for i in range(5))
            + f'{100 * CHAIN[AI[a]].mean():>9.1f}%   ' + ''.join(f'{c:<25}' for c in cells))

    head('E7. Session drift and prompt length (indirect checks)')
    out('  No arm ran in two sessions, so drift between sessions cannot be measured directly. Indirect checks: the touch')
    out('  rate of TRUE entries in arms that do not show them (A in v5; RD and RE in v8), and the touch rate of REWIRED')
    out('  entries in arms that do not show them (the v5 and v6 arms). Differences near zero say the base rates held.')
    for lab, terms in (('true entries, RD - A', [(1, 'T', 'a', 'RD'), (-1, 'T', 'a', 'A')]),
                       ('true entries, RE - A', [(1, 'T', 'a', 'RE'), (-1, 'T', 'a', 'A')]),
                       ('true entries, RE - RD', [(1, 'T', 'a', 'RE'), (-1, 'T', 'a', 'RD')]),
                       ('rewired entries, E - A', [(1, 'R', 'a', 'E'), (-1, 'R', 'a', 'A')]),
                       ('rewired entries, D - H', [(1, 'R', 'a', 'D'), (-1, 'R', 'a', 'H')])):
        uni = [(w, sub, 'U', a) for w, sub, _, a in terms]
        out(f'  {lab:<26}touch {pp(DIFF(terms)):<27}any means (U) {pp(DIFF(uni))}')
    out('  mean prompt tokens per arm: ' + ', '.join(f'{a} {PTOK[AI[a]].mean():.0f}' for a in arms))

    head('E8. Matched true entries against rewired entries per entry, and shown-minus-unshown contrasts')
    out('  Per entry: touched (entry, seed) pairs over all (entry, seed) pairs, in %; the difference is in points.')
    for x, y in (('E', 'RE'), ('D', 'RD')):
        terms = [(1, cntn('Tm', 'a', x), Z['Tm'] * K), (-1, cntn('R', 'a', y), Z['R'] * K)]
        out(f'  per entry, {x} matched true {pc(PER("Tm", "a", x))} vs {y} rewired {pc(PER("R", "a", y))}: difference '
            f'{pp(lin_ci(D_SORT, terms))}; by tasks {pp(lin_ci(D_TASK, terms))}')
    out('  Shown minus unshown: each list in the arm that shows it, minus the same entries in the arm that shows the')
    out('  other list (any-entry rates, points of replays). Drift between sessions does not cancel in these.')
    for flag, lab2 in (('a', 'touch'), ('U', 'any means (U)')):
        for x, y in (('E', 'RE'), ('D', 'RD')):
            for sb, lab in (('T', 'true'), ('Tm', 'matched true')):
                terms = [(1, sb, flag, x), (-1, sb, flag, y), (-1, 'R', flag, y), (1, 'R', flag, x)]
                lab3 = f'({x} - {y}) {lab} - ({y} - {x}) rewired, {lab2}'
                out(f'  {lab3:<60}{pp(DIFF(terms)):<27}by tasks {pp(DIFF(terms, D_TASK))}')

    out('')
    out('End of the EXPLORATORY report.')
    if args.stdout:
        sys.stdout.buffer.write(('\n'.join(L) + '\n').encode('utf-8'))
        return
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L) + '\n')
    print(f'wrote {dest.name}: {len(L)} lines; bootstrap self-check deviation {dev:.1e}')


if __name__ == '__main__':
    main()
