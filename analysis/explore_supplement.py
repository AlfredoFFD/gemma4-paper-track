"""Supplement to the stored analyses, asked for by two blind reviews of the draft (EXPLORATORY; changes no registered number).

Usage: py -I -X utf8 analysis/explore_supplement.py

Everything is recomputed from the raw replay outputs tracked under analysis/results/, with the frozen scorers and the
frozen bootstrap imported, not copied (analyze_forks.boot_ci and diff_ci; gates_c.failure, any_true and touch_map;
analyze_k.score and first_call_failure; analyze_w.norm; mangled_sensitivity.mangled; fork_states.load_gold).

1. Every registered contrast with its interval clustered by task, beside the state-clustered value recomputed here.
   Each recomputed state-clustered value is searched for, as text, in the stored registered output it comes from.
2. The false-entry contrast of pre-registration 04 in more detail.
3. Seed-to-seed agreement of the first call, as a ceiling for the agreement with the original run.
4. Five calls: legible minus rewired, the mean call of the first changed line, and stops at an edit or a write.
5. Lines copied from stored outputs (no recomputation).
Intervals: 95% bootstrap unless a line says 90%, 2,000 resamples, seed 0, clustered by state and, on the next line,
by task. Complete states only, by each experiment's own rule.
"""
import collections
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_k import ARMS as K_ARMS, first_call_failure, score as score_k, stop_group  # noqa: E402
from analyze_w import norm  # noqa: E402
from fork_states import load_gold  # noqa: E402
from gates_c import any_true, failure, load_rows, load_states, skey, touch_map  # noqa: E402
from mangled_sensitivity import mangled  # noqa: E402

RES = HERE / 'results'
SEEDS = (1, 2, 3)
_TEXT = {}


def stored(rel):
    if rel not in _TEXT:
        _TEXT[rel] = (RES / rel).read_text(encoding='utf-8').replace('\r\n', '\n')
    return _TEXT[rel]


def check(rel, text):
    if text in stored(rel):
        return f'equals the stored value ({rel})'
    return f'DIFFERS FROM THE STORED OUTPUT ({rel}): "{text}" is not in it'


def prop(t):
    return f'{t[0]:.4f} [{t[1]:.4f}, {t[2]:.4f}]'


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def raw(tab):
    vals = [v for vs in tab.values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


# ----------------------------------------------------------------------------- outcomes of one replay (frozen scorers)

def hit_true(state, r):
    return any_true(state, r['next_call'])


def hit_rewired(state, r):
    t = touch_map(state, r['next_call'], state.get('rewired_entries', []), state.get('rewired_spans', {}))
    return int(any(bool(v) and v != 'graph' for v in t.values()))


def hit_swapped(state, r):
    v = touch_map(state, r['next_call'], [state['swapped_out']], state['neighbor_spans']).get(state['swapped_out'])
    return int(bool(v) and v != 'graph')


def hit_decoy(state, r):
    if not state.get('decoy_span'):
        return 0
    v = touch_map(state, r['next_call'], [state['decoy']], {state['decoy']: state['decoy_span']}).get(state['decoy'])
    return int(bool(v) and v != 'graph')


def first_mangled(state, r):
    return int(mangled(r['next_call']))


class Run:
    """The complete states of one analysis: every arm and seed usable by the frozen interface-failure rule."""

    def __init__(self, run_dirs, arms, states, seeds=SEEDS):
        usable = collections.defaultdict(dict)
        for d in run_dirs:
            for r in load_rows(RES / d / 'forks' / 'results.jsonl'):
                if r['arm'] in arms and r['seed'] in seeds and not failure(r):
                    usable[skey(r)][(r['arm'], r['seed'])] = r
        need = {(a, s) for a in arms for s in seeds}
        self.rows = {k: v for k, v in usable.items() if need <= set(v)}  # file order, as the frozen scripts iterate
        self.keys = list(self.rows)
        self.states = states
        self.seeds = seeds
        self._cache = {}

    def value(self, k, arm, seed, outcome):
        ck = (k, arm, seed, outcome.__name__)
        if ck not in self._cache:
            self._cache[ck] = outcome(self.states[k], self.rows[k][(arm, seed)])
        return self._cache[ck]

    def tab(self, arms, outcome, by='state', keys=None):
        """{cluster: [values]}; several arms are pooled into one table."""
        t = collections.defaultdict(list)
        for k in (self.keys if keys is None else keys):
            c = k if by == 'state' else k[0]
            for a in (arms if isinstance(arms, tuple) else (arms,)):
                for s in self.seeds:
                    t[c].append(self.value(k, a, s, outcome))
        return t

    def size(self, keys=None):
        keys = self.keys if keys is None else keys
        return f'{len(keys)} states, {len({k[0] for k in keys})} tasks'


def contrast(run, label, a, b, checks=(), level=0.95, a_out=hit_true, b_out=None, keys=None):
    """Print a difference with its state- and task-clustered intervals; checks = [(stored file, text builder)]."""
    b_out = b_out or a_out
    name = lambda x: ' and '.join(x) if isinstance(x, tuple) else x  # noqa: E731
    sa, sb = run.tab(a, a_out, 'state', keys), run.tab(b, b_out, 'state', keys)
    ta, tb = run.tab(a, a_out, 'task', keys), run.tab(b, b_out, 'task', keys)
    ds, dt = diff_ci(sa, sb, level=level), diff_ci(ta, tb, level=level)
    lv = f'{round(100 * level)}%'
    notes = '; '.join(check(rel, build(ds)) for rel, build in checks)
    print(f'  {label}')
    print(f'      {lv} by state: {dpt(ds)} | {len(sa)} states | {name(a)} {raw(sa)}, {name(b)} {raw(sb)}'
          + (f' | {notes}' if notes else ''))
    print(f'      {lv} by task:  {dpt(dt)} | {len(ta)} tasks')
    return ds, dt


def rate_lines(run, label, arm, outcome, keys=None):
    s, t = run.tab(arm, outcome, 'state', keys), run.tab(arm, outcome, 'task', keys)
    print(f'  {label}: {raw(s)}')
    print(f'      by state: {pct(boot_ci(s))} | {len(s)} states')
    print(f'      by task:  {pct(boot_ci(t))} | {len(t)} tasks')


# ----------------------------------------------------------------------------- section 1

def section1(states_a, states_c, states_d):
    print('== 1. Registered contrasts: state-clustered (as registered, recomputed) and task-clustered ==')
    print('  Outcome unless a line says otherwise: the first call touches a true neighbor in an unopened file (points).')
    p4 = lambda label: (lambda d: f'{label}: {prop(d)}')    # noqa: E731  the 4-decimal format of analyze_forks/_b/_c
    pp = lambda label: (lambda d: f'{label}: {dpt(d)}')     # noqa: E731  the points format of gates_c, analyze_d, analyze_w

    print('\n  Pre-registration 02, hosted run 1 (v5), arms A, P, P\', H, H\'')
    v5 = Run(('v5',), ('A', 'P', 'Pp', 'H', 'Hp'), states_a)
    print(f'  complete: {v5.size()}')
    contrast(v5, 'Following: P and H pooled minus A', ('P', 'H'), 'A', [('analyze_a.txt', p4('H1 diff'))])
    contrast(v5, 'Channel: P minus H', 'P', 'H', [('analyze_a.txt', p4('channel true'))])

    print('\n  Pre-registration 03, hosted runs pooled (v5, v6, v8), ten arms')
    hosted = Run(('v5', 'v6', 'v8'), ('A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE'), states_a)
    print(f'  complete: {hosted.size()}')
    contrast(hosted, 'B1 force: D minus H', 'D', 'H', [('analyze_b.txt', p4('B1'))])
    contrast(hosted, 'B3 encoding: E minus H', 'E', 'H', [('analyze_b.txt', p4('B3'))])
    contrast(hosted, 'B4 structure: D (true entries) minus R_D (its rewired entries)', 'D', 'RD',
             [('analyze_b.txt', p4('D minus R_D'))], b_out=hit_rewired)
    contrast(hosted, 'B4 structure: E (true entries) minus R_E (its rewired entries)', 'E', 'RE',
             [('analyze_b.txt', p4('E minus R_E'))], b_out=hit_rewired)

    print('\n  Pre-registration 04, experiment C run, arms H, E, E\', EL, ES')
    c = Run(('c',), ('H', 'E', 'Ep', 'EL', 'ES'), states_c)
    print(f'  complete: {c.size()}')
    contrast(c, 'Gate G2: E minus H', 'E', 'H',
             [('c/gates_c.txt', pp('G2 replication (E minus H, any unopened true neighbor touched, points)')),
              ('c/analyze_c.txt', p4('E minus H (reference)'))])
    contrast(c, 'C2 location: EL minus H', 'EL', 'H', [('c/analyze_c.txt', p4('EL minus H'))])
    contrast(c, 'C2 definition line: ES minus H', 'ES', 'H', [('c/analyze_c.txt', p4('ES minus H'))])
    contrast(c, 'C2 sufficiency: E minus EL', 'E', 'EL', [('c/analyze_c.txt', p4('E minus EL'))])
    contrast(c, 'C2 sufficiency: E minus EL (the registered 90% interval; sufficient if within 2 points)', 'E', 'EL',
             [('c/analyze_c.txt', p4('E minus EL 90%'))], level=0.90)
    contrast(c, 'C1 false entry: swapped-out true entry under E minus decoy under E\'', 'E', 'Ep',
             [('c/analyze_c.txt', p4('D_E 95%'))], a_out=hit_swapped, b_out=hit_decoy)
    contrast(c, 'C1 false entry, 90%', 'E', 'Ep', [('c/analyze_c.txt', p4('D_E 90%'))], level=0.90,
             a_out=hit_swapped, b_out=hit_decoy)

    print('\n  Pre-registration 05, tool-channel run (D1), arms P, PE, E')
    d1 = Run(('d1',), ('P', 'PE', 'E'), states_d)
    print(f'  complete: {d1.size()}')
    contrast(d1, 'T1: PE minus P', 'PE', 'P', [('d1/analyze_d1.txt', pp('T1 PE - P 95%'))])
    contrast(d1, 'T2: PE minus E', 'PE', 'E', [('d1/analyze_d1.txt', pp('T2 PE - E 95%'))])
    contrast(d1, 'T2: PE minus E (the registered 90% interval; no channel difference if within 2 points)', 'PE', 'E',
             [('d1/analyze_d1.txt', pp('T2 PE - E 90%'))], level=0.90)
    for name, tag in (('Gemma 4 26B-A4B', 'd2_26b'), ('Gemma 4 E4B', 'd2_e4b')):
        print(f'\n  Pre-registration 05, second model {name}, arms A, H, E, R_E')
        d2 = Run((tag,), ('A', 'H', 'E', 'RE'), states_d)
        print(f'  complete: {d2.size()}')
        rel = f'{tag}/analyze_{tag}.txt'
        contrast(d2, 'M1: E minus H', 'E', 'H', [(rel, pp('M1 E - H 95%'))])
        contrast(d2, 'H minus A (promised by the pre-registration, no rule)', 'H', 'A', [(rel, pp('H - A 95% (no rule)'))])
        contrast(d2, 'E minus A (promised by the pre-registration, no rule)', 'E', 'A', [(rel, pp('E - A 95% (no rule)'))])

    print('\n  Pre-registration 07, rendering run, arms A, Aw, Hw, Ew')
    w = Run(('w',), ('A', 'Aw', 'Hw', 'Ew'), states_d)
    print(f'  complete: {w.size()}')
    contrast(w, 'F3: Ew minus Hw', 'Ew', 'Hw', [('w/analyze_w.txt', pp('F3 Ew - Hw'))])
    contrast(w, 'F2: first call is a read_file with a mangled line-bound name, A minus Aw', 'A', 'Aw',
             [('w/analyze_w.txt', pp('F2 A - Aw'))], a_out=first_mangled)
    contrast(w, 'Hw minus Aw (bare names against no list, original rendering; no rule)', 'Hw', 'Aw',
             [('w/analyze_w.txt', pp('Hw - Aw (no rule)'))])
    return c, w


# ----------------------------------------------------------------------------- section 2

def read_start(call):
    """The line a read_file starts at as the harness executes it: a bound under a mangled name is dropped."""
    args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
    try:
        return int(args['start_line']) if 'start_line' in args and args['start_line'] is not None else 1
    except (TypeError, ValueError):
        return 1


def rank_bin(rank):
    return '1' if rank == 1 else '2 to 3' if rank <= 3 else '4 to 7' if rank <= 7 else '8+'


def section2(c):
    """c: the experiment C run on its complete states (all five arms and three seeds usable)."""
    print('\n== 2. The false entry (pre-registration 04, experiment C run), in more detail ==')
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')  # same scoring fields as the file of the frozen analysis
    c.states = states
    c._cache.clear()
    print(f'  complete: {c.size()}; 3 replays per state and arm. E lists the swapped-out true entry; E\' (Ep) lists the')
    print('  decoy in its place; H lists the true entry as a bare name. Every entry of E and E\' has file, lines, first line.')

    print('\n  (a) The cells')
    rate_lines(c, 'swapped-out true entry touched, listed with its location (E)', 'E', hit_swapped)
    rate_lines(c, 'swapped-out true entry touched, not listed (E\': the decoy took its place)', 'Ep', hit_swapped)
    rate_lines(c, 'swapped-out true entry touched, listed as a bare name (H)', 'H', hit_swapped)
    rate_lines(c, 'decoy touched, listed with its location (E\')', 'Ep', hit_decoy)
    rate_lines(c, 'decoy touched, not listed (E)', 'E', hit_decoy)
    rate_lines(c, 'decoy touched, not listed (H)', 'H', hit_decoy)
    cells = [f'E: {prop(boot_ci(c.tab("E", hit_swapped)))} | {raw(c.tab("E", hit_swapped))} replays',
             f'Ep: {prop(boot_ci(c.tab("Ep", hit_swapped)))} | {raw(c.tab("Ep", hit_swapped))} replays',
             f'Ep: {prop(boot_ci(c.tab("Ep", hit_decoy)))} | {raw(c.tab("Ep", hit_decoy))} replays']
    found = sum(1 for x in cells if x in stored('c/analyze_c.txt'))
    print("  the three cells that the stored registered output prints (true entry under E, true entry under E', decoy "
          f"under E'): {found} of 3 found there as text with the same state-clustered interval (c/analyze_c.txt)")
    contrast(c, 'what listing adds for the true entry: listed (E) minus not listed (E\')', 'E', 'Ep', a_out=hit_swapped)
    contrast(c, 'what listing adds for the decoy: listed (E\') minus not listed (E)', 'Ep', 'E', a_out=hit_decoy)
    contrast(c, 'what the location adds for the true entry: E minus H', 'E', 'H', a_out=hit_swapped)

    print('\n  (b) D_E on states whose swapped-out true entry passes the decoy\'s own eligibility')
    print('  The decoy rule (analysis/fork_states.py, make_state): not a true neighbor, name not in view, not a gold')
    print('  node, not the queried node, has a span, file not a gold-patch file, file unopened, file holds no listed')
    print('  entry, not a test file, drawn from the swapped-out entry\'s directory if it can be (else the node\'s')
    print('  directory, else the package). Of these, the swapped-out true entry satisfies by construction: name not in')
    print('  view and file unopened. Applied here to the true entry: (1) not a gold node, (2) file not a gold-patch file,')
    print('  (3) not a test file, (4) its file holds no other listed entry.')
    _gold_ids, gold_paths = load_gold()

    def conds(k):
        s = states[k]
        sw = s['swapped_out']
        path = s['neighbor_spans'][sw]['path']
        return (sw not in set(s['gold_ids']), path not in gold_paths[s['task']], not s['swapped_out_is_test'],
                bool(s['swapped_out_alone_in_file']))

    names = ('(1) not a gold node', '(2) file not a gold-patch file', '(3) not a test file', '(4) alone in its file')
    for i, nm in enumerate(names):
        print(f'      {nm}: {sum(1 for k in c.keys if conds(k)[i])} of {len(c.keys)} states')
    dec_bad = collections.Counter()
    for k in c.keys:
        s = states[k]
        dsp = s['decoy_span']
        dec_bad['gold node'] += int(s['decoy'] in set(s['gold_ids']))
        dec_bad['gold-patch file'] += int(dsp['path'] in gold_paths[s['task']])
        dec_bad['file holding a listed entry'] += int(dsp['path'] in {v['path'] for v in s['neighbor_spans'].values() if v})
    print(f'      check of the decoys themselves: gold node {dec_bad["gold node"]}, in a gold-patch file '
          f'{dec_bad["gold-patch file"]}, in a file holding a listed entry {dec_bad["file holding a listed entry"]}')
    subsets = (('all four conditions', [k for k in c.keys if all(conds(k))]),
               ('conditions (1) and (2) only: outside the fix', [k for k in c.keys if conds(k)[0] and conds(k)[1]]),
               ('the rest: the true entry is a gold node or in a gold-patch file', [k for k in c.keys if not (conds(k)[0] and conds(k)[1])]),
               ('all four, and the decoy comes from the swapped-out entry\'s own directory',
                [k for k in c.keys if all(conds(k)) and states[k]['decoy_pool'] == 'swapped_dir']))
    for label, keys in subsets:
        if not keys:
            print(f'  {label}: no state')
            continue
        contrast(c, f'D_E, {label}', 'E', 'Ep', a_out=hit_swapped, b_out=hit_decoy, keys=keys)
        ne = c.tab('Ep', hit_swapped, 'state', keys)
        print(f'      on these states the true entry is touched when not listed (E\') in {raw(ne)} and as a bare name (H) in '
              f'{raw(c.tab("H", hit_swapped, "state", keys))}')

    print('\n  (c) How the swapped-out true entry is touched under E')
    kinds = collections.Counter()
    alone_hits = total = mang = 0
    hit_states = set()
    for k in c.keys:
        s = states[k]
        sp = s['neighbor_spans'][s['swapped_out']]
        for seed in c.seeds:
            if not c.value(k, 'E', seed, hit_swapped):
                continue
            total += 1
            hit_states.add(k)
            alone_hits += int(bool(s['swapped_out_alone_in_file']))
            call = c.rows[k][('E', seed)]['next_call']
            if call['function_name'] != 'read_file':
                kinds[f'not a read_file ({call["function_name"]})'] += 1
                continue
            mang += int(mangled(call))
            start = read_start(call)
            if start == sp['start']:
                kinds['read_file that starts at the entry\'s first listed line'] += 1
            elif sp['end'] is not None and sp['start'] < start <= sp['end']:
                kinds['read_file that starts inside the entry\'s span'] += 1
            elif start == 1:
                kinds['read_file from line 1 that reaches the entry'] += 1
            elif start < sp['start']:
                kinds['read_file that starts earlier (not at line 1) and overlaps the entry'] += 1
            else:
                kinds['read_file, other'] += 1
    print(f'      replays that touch it: {total}, from {len(hit_states)} states of {len({k[0] for k in hit_states})} tasks; in a file that '
          f'holds no other listed entry: {alone_hits}; with a mangled bound: {mang}')
    for kind, n in sorted(kinds.items(), key=lambda x: (-x[1], x[0])):
        print(f'      {kind}: {n}')

    print('\n  (d) List positions (rank in the note: 1 is the first entry; the tool sorts by name)')
    sw_rank = {k: states[k]['swapped_position'] + 1 for k in c.keys}
    dc_rank = {k: states[k]['decoy_position'] + 1 for k in c.keys}
    lens = [len(states[k]['true_neighbors']) for k in c.keys]
    print(f'      entries in the list: median {st.median(lens)}, range {min(lens)} to {max(lens)}; swapped-out entry: median rank '
          f'{st.median(sw_rank.values())}; decoy: median rank {st.median(dc_rank.values())}; same rank in {sum(1 for k in c.keys if sw_rank[k] == dc_rank[k])} '
          f'of {len(c.keys)} states')
    for b in ('1', '2 to 3', '4 to 7', '8+'):
        ks = [k for k in c.keys if rank_bin(sw_rank[k]) == b]
        kd = [k for k in c.keys if rank_bin(dc_rank[k]) == b]
        ts = raw(c.tab('E', hit_swapped, 'state', ks)) if ks else '0/0'
        td = raw(c.tab('Ep', hit_decoy, 'state', kd)) if kd else '0/0'
        th = raw(c.tab('H', hit_swapped, 'state', ks)) if ks else '0/0'
        print(f'      rank {b}: swapped-out entry there in {len(ks)} states, touched under E in {ts} replays (as a bare name under H in {th}); '
              f'decoy there in {len(kd)} states, touched under E\' in {td} replays')

    print('\n  (e) The registered secondary of pre-registration 04')
    per_entry_s, per_entry_t = collections.defaultdict(list), collections.defaultdict(list)
    for k in c.keys:
        s = states[k]
        unshown = set(s.get('unshown_true_neighbors', s['true_neighbors']))
        listed = [n for n in s['true_neighbors'] if n in unshown and n != s['swapped_out']]
        for seed in c.seeds:
            t = touch_map(s, c.rows[k][('Ep', seed)]['next_call'], listed, s['neighbor_spans'])
            vals = [int(bool(v) and v != 'graph') for v in t.values()]
            per_entry_s[k] += vals
            per_entry_t[k[0]] += vals
    print(f'  per listed true entry in the E\' notes (unopened true entries the note lists), touched: {raw(per_entry_s)}')
    print(f'      by state: {pct(boot_ci(per_entry_s))} | {len(per_entry_s)} states')
    print(f'      by task:  {pct(boot_ci(per_entry_t))} | {len(per_entry_t)} tasks')
    rate_lines(c, 'the decoy in the same notes, touched', 'Ep', hit_decoy)
    contrast(c, 'any unopened true neighbor touched: E\' minus E', 'Ep', 'E', [('c/analyze_c.txt', lambda d: f'Ep minus E: {prop(d)}')])


# ----------------------------------------------------------------------------- section 3

def section3(w):
    print('\n== 3. Seed-to-seed agreement of the first call (rendering run), beside the agreement with the original run ==')
    print(f'  complete: {w.size()}; three seeds per state and arm give three seed pairs per state.')
    pairs = ((1, 2), (1, 3), (2, 3))
    n_rep = len(w.keys) * len(w.seeds)
    for arm, label in (('A', 'A (tool results rendered as harness v28 delivers them)'),
                       ('Aw', 'Aw (tool results rendered as the original runs\' harness delivered them)')):
        same_s, same_t = collections.defaultdict(list), collections.defaultdict(list)
        both_read = same_file = 0
        o_same = o_both = o_file = 0
        for k in w.keys:
            calls = {s: w.rows[k][(arm, s)]['next_call'] for s in w.seeds}
            for i, j in pairs:
                a, b = calls[i], calls[j]
                same = int(a['function_name'] == b['function_name'])
                same_s[k].append(same)
                same_t[k[0]].append(same)
                if same and a['function_name'] == 'read_file':
                    both_read += 1
                    same_file += int(norm((a.get('arguments') or {}).get('filepath')) == norm((b.get('arguments') or {}).get('filepath')))
            oc = w.states[k].get('observed_next_call') or {}
            for s in w.seeds:
                call = calls[s]
                st_ = call['function_name'] == oc.get('function_name')
                o_same += int(st_)
                if st_ and call['function_name'] == 'read_file':
                    o_both += 1
                    o_file += int(norm((call.get('arguments') or {}).get('filepath')) == norm((oc.get('arguments') or {}).get('filepath')))
        print(f'  arm {label}')
        print(f'      two seeds name the same tool: {raw(same_s)} seed pairs')
        print(f'          by state: {pct(boot_ci(same_s))} | {len(same_s)} states')
        print(f'          by task:  {pct(boot_ci(same_t))} | {len(same_t)} tasks')
        print(f'      read_file in both seeds: {both_read} pairs; same file in {same_file} of them ({100 * same_file / both_read:.1f}%)')
        line = (f'{arm:2s}: same tool {100 * o_same / n_rep:.1f}% of replays; read_file in both {o_both}, '
                f'same file in {100 * o_file / o_both:.1f}% of those')
        print(f'      against the original run\'s own next call: same tool in {o_same} of {n_rep} replays ({100 * o_same / n_rep:.1f}%); '
              f'read_file in both {o_both}, same file in {o_file} ({100 * o_file / o_both:.1f}%) | {check("w/analyze_w.txt", line)}')


# ----------------------------------------------------------------------------- section 4

def section4(states_d):
    print('\n== 4. Five calls (pre-registration 06 run; usable and complete as analyze_k.py defines them) ==')
    pop = json.load(open(HERE / 'fork_states_k' / 'population.json', encoding='utf-8'))
    member = {tuple(g['key']): (p, g) for p in ('R', 'U') for g in pop[p]}
    rows = [json.loads(l) for l in open(RES / 'k' / 'forks' / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    usable = collections.defaultdict(dict)
    for r in rows:
        k = skey(r)
        if k in member and r['arm'] in K_ARMS and r['seed'] in member[k][1]['seeds'] and not first_call_failure(r):
            usable[k][(r['arm'], r['seed'])] = r
    complete = {p: sorted(k for k, (pp, g) in member.items() if pp == p
                          and {(a, s) for a in K_ARMS for s in g['seeds']} <= set(usable.get(k, {}))) for p in ('R', 'U')}
    scored = {(k, key): score_k(states_d[k], member[k][1], r) for p in ('R', 'U') for k in complete[p]
              for key, r in usable[k].items()}
    for p in ('R', 'U'):
        print(f'  complete in {p}: {len(complete[p])} states, {len({k[0] for k in complete[p]})} tasks, seeds {pop["seeds"][p]}')

    def tab(p, arm, fn, by):
        t = collections.defaultdict(list)
        for k in complete[p]:
            c = k if by == 'state' else k[0]
            for s in pop['seeds'][p]:
                t[c].append(fn(scored[(k, (arm, s))]))
        return t

    yline = lambda x: x['Yline']                                              # noqa: E731
    first = lambda x: x['first_Yline'] if x['first_Yline'] is not None else 6   # noqa: E731
    stops = lambda x: int(stop_group(x['stop']) in ('stop:edit_file', 'stop:write_file'))  # noqa: E731

    def diff(label, p, a, b, fn, unit):
        ds = diff_ci(tab(p, a, fn, 'state'), tab(p, b, fn, 'state'))
        dt = diff_ci(tab(p, a, fn, 'task'), tab(p, b, fn, 'task'))
        f = dpt if unit == 'points' else (lambda t: f'{t[0]:+.3f} [{t[1]:+.3f}, {t[2]:+.3f}]')
        print(f'  {label}')
        print(f'      by state: {f(ds)} {unit} | {len(tab(p, a, fn, "state"))} states')
        print(f'      by task:  {f(dt)} {unit} | {len(tab(p, a, fn, "task"))} tasks')

    print('\n  Shown a line the gold patch changes within five calls (Yline), population R')
    for a in K_ARMS:
        print(f'      {a:2s}: {pct(boot_ci(tab("R", a, yline, "state")))} | {raw(tab("R", a, yline, "state"))}')
    print('      stored counts (k/analyze_k.txt): '
          + check('k/analyze_k.txt', f'Yline E : {pct(boot_ci(tab("R", "E", yline, "state")))} | {raw(tab("R", "E", yline, "state"))}') + '; '
          + check('k/analyze_k.txt', f'Yline RE: {pct(boot_ci(tab("R", "RE", yline, "state")))} | {raw(tab("R", "RE", yline, "state"))}'))
    diff('legible true list minus legible rewired list: E minus R_E on Yline in R', 'R', 'E', 'RE', yline, 'points')
    diff('for comparison, the registered K1: E minus H on Yline in R', 'R', 'E', 'H', yline, 'points')
    diff('E minus R_E on Yline in U (neither list reaches the fix there)', 'U', 'E', 'RE', yline, 'points')

    for p in ('R', 'U'):
        print(f'\n  Model call at which a changed line is first shown, population {p} (a replay that never gets there counts as 6)')
        for a in K_ARMS:
            vals = [v for vs in tab(p, a, first, 'state').values() for v in vs]
            never = sum(1 for v in vals if v == 6)
            print(f'      {a:2s}: mean {st.mean(vals):.2f} | never {never} of {len(vals)}')
        diff(f'E minus H on that mean, {p}', p, 'E', 'H', first, 'calls')
        diff(f'E minus A on that mean, {p}', p, 'E', 'A', first, 'calls')
        diff(f'H minus A on that mean, {p}', p, 'H', 'A', first, 'calls')

    for p in ('R', 'U'):
        print(f'\n  Replays that end at an edit_file or write_file call (the replay stops there), population {p}')
        for a in K_ARMS:
            print(f'      {a:2s}: {pct(boot_ci(tab(p, a, stops, "state")))} | {raw(tab(p, a, stops, "state"))}')
        diff(f'E minus H, {p}', p, 'E', 'H', stops, 'points')
        diff(f'E minus A, {p}', p, 'E', 'A', stops, 'points')


# ----------------------------------------------------------------------------- section 5

def copy_lines(rel, picks):
    """Print stored lines verbatim. Each pick is a chain of line starts (leading spaces ignored): every item is
    searched for after the one before it, and the last one found is the line printed."""
    lines = stored(rel).split('\n')
    print(f'  from analysis/results/{rel}:')
    for chain in picks:
        i = -1
        for start in chain:
            i = next((j for j in range(i + 1, len(lines)) if lines[j].strip().startswith(start)), None)
            if i is None:
                print(f'      NOT FOUND: a line starting with "{start}"')
                break
        if i is not None:
            print(f'      line {i + 1}: {lines[i].rstrip()}')


def section5():
    print('\n== 5. Copied from stored outputs (no recomputation) ==')
    print('  The first hosted run, discarded because it failed the fidelity gate (it re-sent the agent\'s thoughts):')
    copy_lines('v4/analysis.txt', [('states with every arm and seed present',), ('H1 diff',), ('channel true',), ('Fidelity',)])
    print('  E minus H when an entry counts as followed by any means (union U), hosted runs; columns: by state | by task:')
    copy_lines('explore_b.txt', [('== 4. Primary outcome re-clustered by TASK ==', 'clusters = states'),
                                 ('== 4. Primary outcome re-clustered by TASK ==', 'the same for the any-means union U:', 'E - H (true)')])
    print('  E minus H on opening a listed entry\'s file at any line, hosted runs; columns: file | fileL:')
    copy_lines('explore_b.txt', [('== 3. File-level following', 'contrast (points)'),
                                 ('== 3. File-level following', 'contrast (points)', 'H - A (true)'),
                                 ('== 3. File-level following', 'contrast (points)', 'E - H (true)')])
    print('  Opening a listed file, by arm, experiment C run (no difference is stored there):')
    copy_lines('explore_mechanism.txt', [('Experiment C run', 'H  :'), ('Experiment C run', 'ES :'),
                                         ('Experiment C run', 'EL :'), ('Experiment C run', 'E  :')])


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
    print('EXPLORATORY supplement. No registered number changes; every state-clustered value of section 1 is checked')
    print('against the stored registered output as text.\n')
    states_a = load_states(HERE / 'fork_states' / 'states.jsonl')
    states_c = load_states(HERE / 'fork_states_c' / 'states.jsonl')
    states_d = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    c, w = section1(states_a, states_c, states_d)
    section2(c)
    section3(w)
    section4(states_d)
    section5()


if __name__ == '__main__':
    main()
