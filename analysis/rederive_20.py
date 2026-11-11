"""Independent re-derivation of pre-registration 20 (asked or told: the same search hits, asked for or handed over).

Written blind: from the text of prereg/20-asked-or-told.md and prereg/15-own-search-without-line-numbers.md, the
states file analysis/fork_states_t/states.jsonl, the rows analysis/results/20/forks/results.jsonl, and, for the
description of ASKED against 15, analysis/fork_states_s/states.jsonl and analysis/results/15/forks/results.jsonl.
The scoring of one call (interface failures, a read of a file, its first line) is imported from the blind second
script of 15, analysis/rederive_15.py. The hit files are re-derived here from the recorded search result and the
note, and only compared with the ones the records store.

Usage: py -I -X utf8 analysis/rederive_20.py [--no-write]
Writes the report to analysis/results/rederive_20.txt (LF) unless --no-write is given.
"""
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rederive_15 as R  # noqa: E402

ROOT = HERE.parent
STATES = ROOT / 'analysis' / 'fork_states_t' / 'states.jsonl'
ROWS = ROOT / 'analysis' / 'results' / '20' / 'forks' / 'results.jsonl'
STATES_15 = ROOT / 'analysis' / 'fork_states_s' / 'states.jsonl'
ROWS_15 = ROOT / 'analysis' / 'results' / '15' / 'forks' / 'results.jsonl'
OUT = ROOT / 'analysis' / 'results' / 'rederive_20.txt'

ARMS = ('NONE', 'TOLD', 'TOLDX', 'ASKED')
SEEDS = (1, 2, 3)
B = 2000
SEED = 0
FLOOR = 40
FLOOR_T3 = 20
NOTE_HEAD = 'Matches in the repository:'


def rel(p):
    return R.norm(p)


def squash(cmd):
    """A command with quotes removed and blanks collapsed (for 'repeats the recorded search')."""
    return re.sub(r'\s+', ' ', re.sub(r'["\']', '', cmd or '')).strip()


def is_search(o):
    """SEARCHES: a run_command whose first program is a search program (the searches_again of rederive_15)."""
    return bool(o['searches_again'])


def parse_note(task, note):
    """Hit lines of a note: list of (repository file or None, line, text)."""
    lines = note.split('\n')
    assert lines[0] == NOTE_HEAD, lines[0]
    out = []
    for ln in lines[1:]:
        m = R.HIT_PATH.match(ln)
        assert m, ln
        out.append((R.repo_file(task, m['path']), int(m['line']), m['text']))
    return out


# ---------------------------------------------------------------- statistics

def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float('nan')
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def boot(steps, fn):
    """Point estimate, 95% percentile interval by step (2,000 resamples, random.Random(0)), number left out."""
    rng = random.Random(SEED)
    n = len(steps)
    pt = fn(steps)
    vals, left = [], 0
    for _ in range(B):
        v = fn([steps[rng.randrange(n)] for _ in range(n)]) if n else float('nan')
        if v is None or math.isnan(v):
            left += 1
        else:
            vals.append(v)
    return pt, pct(vals, 0.025), pct(vals, 0.975), left


def fp(x):
    return 'n/a' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{100 * x:.1f}'


def rate(k, n):
    return f'{k}/{n} ({fp(k / n if n else float("nan"))}%)'


# ---------------------------------------------------------------- main

def main(argv):
    no_write = '--no-write' in argv[1:]
    L = []
    p = L.append

    recs = [json.loads(x) for x in STATES.read_text(encoding='utf-8').splitlines() if x.strip()]
    by = defaultdict(dict)
    for r in recs:
        by[r['state_id']][r['arm']] = r
    sids = sorted(by)
    s15 = {}
    for x in STATES_15.read_text(encoding='utf-8').splitlines():
        if x.strip():
            r = json.loads(x)
            s15[(r['state_id'], r['arm'])] = r

    # ---- re-derive the files each arm is scored on
    info = {}
    checks = Counter()
    diffs = []
    for sid in sids:
        rs = by[sid]
        a = rs['ASKED']
        task = a['task']
        last = a['steps'][-1]
        cmd = last['tool_calls'][0]['arguments']['command']
        out = R.stdout_of(R.obs_of(last))
        hits, nctx, nother, one, _ = R.parse_result(task, cmd, out)
        opened = R.opened_before(task, a['steps'])
        files = R.snapshot(task)[0]
        own = defaultdict(list)
        for h in hits:
            if h['file'] in files and h['file'] not in opened:
                own[h['file']].append(h['line'])
        own = {f: sorted(set(v)) for f, v in own.items()}
        own_named = {h['file'] for h in hits}
        noted_own = defaultdict(list)
        for h in hits:
            if h['file'] in files:
                noted_own[h['file']].append(h['line'])
        told_note = NOTE_HEAD + ''.join(
            f"\n{h['raw_path'] if h['raw_path'] is not None else R.one_written(cmd, task)}:{h['line']}:{h['text']}"
            for h in hits)
        d = {'task': task, 'run': a['run'], 'repo': a.get('repo'), 'opened': opened, 'own_cmd': cmd,
             'hf': {'NONE': own, 'TOLD': own, 'ASKED': own}, 'noted': {a_: dict(noted_own) for a_ in ('NONE', 'TOLD', 'ASKED')},
             'fork15': a['state_of_15'], 'source': None}
        # checks against what the records store
        for arm in ('NONE', 'TOLD', 'ASKED'):
            stored = {f: sorted(v) for f, v in (rs[arm].get('hit_files') or {}).items()}
            if stored != own:
                diffs.append(f'{sid} {arm}: scored files mine {json.dumps(own, sort_keys=True)} vs stored '
                             f'{json.dumps(stored, sort_keys=True)}')
        stored_open = {rel(x) for x in a.get('opened_files') or []} & set(files)
        checks['opened files (repository) equal to the stored ones'] += stored_open == set(opened)
        checks['recorded search command equals own_search_call'] += \
            a['own_search_call']['arguments']['command'] == cmd == rs['NONE']['own_search_call']['arguments']['command']
        checks['TOLD note equals the note derived from the ASKED result'] += \
            (rs['TOLD'].get('arms') or {}).get('TOLD', {}).get('user_text') == told_note
        checks['NONE and TOLD histories equal ASKED history without its last step'] += \
            rs['NONE']['steps'] == a['steps'][:-1] == rs['TOLD']['steps']
        checks['NONE and ASKED carry no added message'] += not rs['NONE'].get('arms') and not a.get('arms')
        lastn = rs['NONE']['steps'][-1] if rs['NONE']['steps'] else None
        checks['NONE history ends on an agent step with one tool call and its result'] += bool(
            lastn and lastn.get('source') == 'agent' and len(lastn.get('tool_calls') or []) == 1
            and (lastn.get('observation') or {}).get('content') is not None)
        r15 = s15.get((sid, 'S'))
        checks['ASKED history equals the history of the S record of 15'] += bool(r15) and r15['steps'] == a['steps']
        checks['ASKED fork is the S record of 15'] += bool(r15) and r15['fork'] == a['state_of_15']
        if 'TOLDX' in rs:
            x = rs['TOLDX']
            note = (x.get('arms') or {}).get('TOLDX', {}).get('user_text')
            nh = parse_note(task, note)
            q = defaultdict(list)
            noted = defaultdict(list)
            for f, ln, _t in nh:
                if f is not None:
                    noted[f].append(ln)
                    if f not in opened:
                        q[f].append(ln)
            q = {f: sorted(set(v)) for f, v in q.items()}
            stored = {f: sorted(v) for f, v in (x.get('hit_files') or {}).items()}
            if stored != q:
                diffs.append(f'{sid} TOLDX: scored files mine {json.dumps(q, sort_keys=True)} vs stored '
                             f'{json.dumps(stored, sort_keys=True)}')
            d['hf']['TOLDX'] = q
            d['noted']['TOLDX'] = dict(noted)
            d['source'] = x.get('toldx_source')
            checks['TOLDX: note names an unopened repository file with a line number'] += bool(q)
            checks['TOLDX: note names no repository file of the own search result'] += \
                not ({f for f, *_ in nh if f} & {f for f in own_named if f in files})
            checks['TOLDX: history equals NONE history'] += x['steps'] == rs['NONE']['steps']
            checks['TOLDX: note text equals the stored note field'] += x.get('note') == note
            if x.get('toldx_source') == 'same run':
                checks['TOLDX same run: other search is a later step'] += (x.get('other_search_distance') or 0) > 0
        info[sid] = d
    n_x = sum(1 for s in sids if 'TOLDX' in by[s])

    p('Re-derivation of pre-registration 20 (independent script, written blind from the registration texts and raw files)')
    p('')
    p('0. STEPS')
    p(f'  steps {len(sids)}; runs {len({(info[s]["task"], info[s]["run"]) for s in sids})}; tasks '
      f'{len({info[s]["task"] for s in sids})}; by repository '
      + ', '.join(f'{k} {v}' for k, v in sorted(Counter(info[s]['repo'] for s in sids).items())))
    p(f'  records by arm: ' + ', '.join(f'{a} {sum(1 for s in sids if a in by[s])}' for a in ARMS)
      + f'; TOLDX source: ' + ', '.join(f'{k} {v}' for k, v in sorted(Counter(info[s]['source'] for s in sids
                                                                              if 'TOLDX' in by[s]).items())))
    p(f'  scored files: own search {sum(len(info[s]["hf"]["TOLD"]) for s in sids)} (in {len(sids)} steps); '
      f'TOLDX {sum(len(info[s]["hf"]["TOLDX"]) for s in sids if "TOLDX" in by[s])} (in {n_x} steps)')
    for k in sorted(checks):
        den = n_x if k.startswith('TOLDX:') else (
            sum(1 for s in sids if info[s]['source'] == 'same run') if k.startswith('TOLDX same') else len(sids))
        p(f'  check: {k}: {checks[k]} of {den}')
    p(f'  differences between the re-derived scored files and those stored in the records: {len(diffs)}')
    for dd in diffs:
        p('    ' + dd)
    p('')

    # ---- rows
    rows = [json.loads(x) for x in ROWS.read_text(encoding='utf-8').splitlines() if x.strip()]
    key2 = {}
    for sid, rs in by.items():
        for arm, r in rs.items():
            key2[(r['task'], r['run'], r['fork'])] = (sid, arm)
    cell, unmatched, dup = {}, 0, 0
    runner = Counter()
    multi = 0
    for r in rows:
        k = (r['task'], r['run'], r['fork'])
        if k not in key2:
            unmatched += 1
            continue
        sid, arm = key2[k]
        runner[(arm, r['arm'])] += 1
        if (sid, arm, r['seed']) in cell:
            dup += 1
        cell[(sid, arm, r['seed'])] = r
        multi += len(r.get('all_calls') or []) > 1
    expected = sum(len(by[s]) for s in sids) * len(SEEDS)
    p('1. REPLAYS BY ARM')
    p('  a row belongs to the record whose (task, run, fork) it carries; the fork id ends in the arm.')
    p('  runner arm by design arm: ' + ', '.join(f'{a} as {ra}: {n}' for (a, ra), n in sorted(runner.items())))
    p(f'  rows {len(rows)}; unmatched {unmatched}; duplicate cells {dup}; missing cells {expected - len(cell)};'
      f' rows with more than one call {multi}')

    def score_rows(cells, arm_of_hf):
        usable, fails = {}, defaultdict(Counter)
        for (sid, arm, seed), r in cells.items():
            f = R.interface_failure(r)
            if f:
                fails[arm][f] += 1
                continue
            hf = info[sid]['hf'][arm_of_hf(arm)]
            o = R.score(info[sid]['task'], r, hf)
            o['uses'] = bool(o['reads_hit_file'] and o['past_line_1'])
            o['search'] = is_search(o)
            o['cmd'] = (r['next_call'].get('arguments') or {}).get('command') if o['tool'] == 'run_command' else None
            noted = info[sid]['noted'].get(arm_of_hf(arm))
            if noted is not None:
                on = R.score(info[sid]['task'], r, {f: sorted(set(v)) for f, v in noted.items()})
                o['reads_noted'] = on['reads_hit_file']
                o['noted_past_1'] = on['past_line_1']
            usable[(sid, arm, seed)] = o
        return usable, fails

    U, F = score_rows(cell, lambda a: a)
    for arm in ARMS:
        n = sum(1 for k in cell if k[1] == arm)
        u = sum(1 for k in U if k[1] == arm)
        fl = ', '.join(f'{k} {v}' for k, v in sorted(F[arm].items())) or 'none'
        mg = sum(1 for k, o in U.items() if k[1] == arm and o['mangled_start'] and o['uses'])
        p(f'  {arm:5s} replays {n}; interface failures: {fl}; usable {rate(u, n)};'
          f' uses the line through a mangled start_line name {mg}')
    for k in sorted(cell):
        f = R.interface_failure(cell[k])
        if f:
            p(f'    failure: {k[0]} {k[1]} seed {k[2]}: {f}')

    def complete(arms, pool=None):
        pool = U if pool is None else pool
        return [s for s in sids if all((s, a, sd) in pool for a in arms for sd in SEEDS)]

    sets = {'T1': ('NONE', 'TOLD'), 'T2': ('TOLD', 'ASKED'), 'T3': ('TOLD', 'TOLDX'), 'T4': ('NONE', 'TOLD')}
    comp = {t: complete(a) for t, a in sets.items()}
    comp['R15'] = complete(('NONE', 'TOLD', 'ASKED'))
    for t in ('T1', 'T2', 'T3', 'T4'):
        p(f'  steps complete for {t} ({", ".join(sets[t])}): {len(comp[t])} of '
          f'{n_x if t == "T3" else len(sids)}; floor {FLOOR_T3 if t == "T3" else FLOOR}')
    p(f'  steps complete for NONE, TOLD and ASKED (the ratio of 15\'s form): {len(comp["R15"])}')
    p('')

    def share(arm, key):
        def f(steps):
            k = sum(U[(s, arm, sd)][key] for s in steps for sd in SEEDS)
            n = len(steps) * len(SEEDS)
            return k / n if n else float('nan')
        return f

    p('2. OUTCOMES PER ARM')
    p('  (a) all usable replays')
    for arm in ARMS:
        os_ = [o for k, o in U.items() if k[1] == arm]
        p(f'    {arm:5s} usable {len(os_)}; USES THE LINE {rate(sum(o["uses"] for o in os_), len(os_))};'
          f' SEARCHES {rate(sum(o["search"] for o in os_), len(os_))}')
    p('  (b) on the steps complete in all arms that step has (every arm, seeds 1 to 3)')
    for arm in ARMS:
        cs = complete(('NONE', 'TOLD', 'ASKED') + (('TOLDX',) if arm == 'TOLDX' else ()))
        cs = [s for s in cs if arm != 'TOLDX' or 'TOLDX' in by[s]]
        n = len(cs) * 3
        u = sum(U[(s, arm, sd)]['uses'] for s in cs for sd in SEEDS)
        se = sum(U[(s, arm, sd)]['search'] for s in cs for sd in SEEDS)
        p(f'    {arm:5s} steps {len(cs)}; USES THE LINE {rate(u, n)}; SEARCHES {rate(se, n)}')
    p('')

    p('3. RULES (95% percentile interval, bootstrap by step, 2,000 resamples, random.Random(0), on the steps complete'
      ' in the arms compared)')

    def diff(a1, a2, key):
        f1, f2 = share(a1, key), share(a2, key)
        return lambda st: f1(st) - f2(st)

    def line(name, steps, fn, unit='points'):
        pt, lo, hi, left = boot(steps, fn)
        ex = f'; {left} resamples left out' if left else ''
        if unit == 'points':
            p(f'  {name}: {fp(pt)} points [{fp(lo)}, {fp(hi)}] on {len(steps)} steps{ex}')
        else:
            p(f'  {name}: {pt:.3f} [{lo:.3f}, {hi:.3f}] on {len(steps)} steps{ex}')
        return pt, lo, hi

    cs = comp['T1']
    p(f'  T1  shares: TOLD {fp(share("TOLD", "uses")(cs))}%, NONE {fp(share("NONE", "uses")(cs))}%')
    pt, lo, hi = line('T1  USES THE LINE, TOLD - NONE', cs, diff('TOLD', 'NONE', 'uses'))
    if len(cs) < FLOOR:
        p(f'      verdict: none (below the floor: {len(cs)} complete steps)')
    else:
        p(f'      verdict: {"met" if lo > 0 else "not met"} (interval {"above" if lo > 0 else "not above"} zero)')

    cs = comp['T2']
    ft, fa = share('TOLD', 'uses'), share('ASKED', 'uses')

    def ratio_fn(st):
        den = fa(st)
        return ft(st) / den if den > 0 else float('nan')
    p(f'  T2  shares: TOLD {fp(ft(cs))}%, ASKED {fp(fa(cs))}%')
    pt, lo, hi = line('T2  USES THE LINE, ratio TOLD / ASKED', cs, ratio_fn, unit='ratio')
    if len(cs) < FLOOR:
        p(f'      verdict: none (below the floor: {len(cs)} complete steps)')
    else:
        v = 'used about as often' if pt >= 2 / 3 else 'telling does not replace asking'
        p(f'      verdict: {v} (point ratio {"at least" if pt >= 2 / 3 else "below"} two thirds)')

    cs = comp['T3']
    p(f'  T3  shares: TOLD {fp(share("TOLD", "uses")(cs))}%, TOLDX {fp(share("TOLDX", "uses")(cs))}%')
    pt, lo, hi = line('T3  USES THE LINE, TOLD - TOLDX', cs, diff('TOLD', 'TOLDX', 'uses'))
    if len(cs) < FLOOR_T3:
        p(f'      verdict: none (below the floor: {len(cs)} complete steps)')
    else:
        p(f'      verdict: {"met" if lo > 0 else "not met"} (interval {"above" if lo > 0 else "not above"} zero)')
    for src in ('same run', 'other run'):
        sub = [s for s in cs if info[s]['source'] == src]
        p(f'      source {src}: TOLD {fp(share("TOLD", "uses")(sub))}%, TOLDX {fp(share("TOLDX", "uses")(sub))}%')
        line(f'      T3 source {src} alone (no verdict)', sub, diff('TOLD', 'TOLDX', 'uses'))

    cs = comp['T4']
    p(f'  T4  shares: TOLD {fp(share("TOLD", "search")(cs))}%, NONE {fp(share("NONE", "search")(cs))}%')
    pt, lo, hi = line('T4  SEARCHES, TOLD - NONE', cs, diff('TOLD', 'NONE', 'search'))
    if len(cs) < FLOOR:
        p(f'      verdict: none (below the floor: {len(cs)} complete steps)')
    else:
        p(f'      verdict: {"met" if hi < 0 else "not met"} (interval {"below" if hi < 0 else "not below"} zero)')
    p('')

    p('4. PRINTED WITHOUT A RULE')
    cs = comp['R15']
    fn_, ft_, fa_ = share('NONE', 'uses'), share('TOLD', 'uses'), share('ASKED', 'uses')

    def r15(st):
        den = fa_(st) - fn_(st)
        return (ft_(st) - fn_(st)) / den if den > 0 else float('nan')
    line("  ratio of 15's form (TOLD - NONE) / (ASKED - NONE), USES THE LINE (a resample with a denominator not"
         " above 0 is left out)", cs, r15, unit='ratio')

    p('  (a) next call when it does not use the line (all usable replays; "noted file" = a repository file with a hit'
      ' line in the note)')
    for arm in ('TOLD', 'TOLDX'):
        os_ = [o for k, o in sorted(U.items(), key=lambda kv: kv[0]) if k[1] == arm and not o['uses']]
        c = Counter()
        other = Counter()
        for o in os_:
            if o.get('reads_noted') and not o.get('noted_past_1'):
                c['a read of a noted file from line 1'] += 1
            elif o.get('reads_noted'):
                c['a read of a noted file past line 1 (a file opened before: not a first read)'] += 1
            elif o['search']:
                c['a search'] += 1
            elif o['tool'] == 'edit_file':
                c['an edit (edit_file)'] += 1
            else:
                c['anything else'] += 1
                other[o['kind']] += 1
        p(f'    {arm}: {len(os_)} replays do not use the line: '
          + '; '.join(f'{k} {v}' for k, v in sorted(c.items(), key=lambda kv: -kv[1])))
        p(f'      anything else, by kind: ' + (', '.join(f'{k} {v}' for k, v in sorted(other.items(), key=lambda kv:
                                                                                         (-kv[1], kv[0]))) or 'none'))
    p('  (b) replays whose next call is a search, and how many repeat the recorded search (same command once quotes are'
      ' removed and blanks collapsed)')
    for arm in ('TOLD', 'NONE'):
        os_ = [(k, o) for k, o in U.items() if k[1] == arm and o['search']]
        rep = [(k, o) for k, o in os_ if squash(o['cmd']) == squash(info[k[0]]['own_cmd'])]
        p(f'    {arm}: searches {len(os_)}; repeat the recorded search {rate(len(rep), len(os_))};'
          f' in {len({k[0] for k, o in rep})} steps')
    p('  (c) ASKED against the stored rows of arm S of 15 on the same steps (scored here on the same files)')
    rows15 = [json.loads(x) for x in ROWS_15.read_text(encoding='utf-8').splitlines() if x.strip()]
    want = {(info[s]['task'], info[s]['run'], info[s]['fork15']): s for s in sids}
    c15 = {}
    for r in rows15:
        k = (r['task'], r['run'], r['fork'])
        if k in want:
            c15[(want[k], 'S15', r['seed'])] = r
    p(f'    rows of 15 found for the steps: {len(c15)} (expected {len(sids) * 3})')
    U15, F15 = score_rows(c15, lambda a: 'ASKED')
    p(f'    S of 15: interface failures: ' + (', '.join(f'{k} {v}' for k, v in sorted(F15['S15'].items())) or 'none')
      + f'; usable {len(U15)}')
    both = [s for s in sids if all((s, 'ASKED', sd) in U for sd in SEEDS) and all((s, 'S15', sd) in U15
                                                                                    for sd in SEEDS)]
    pool = dict(U)
    pool.update(U15)

    def sh(arm, key):
        def f(st):
            n = len(st) * 3
            return sum(pool[(s, arm, sd)][key] for s in st for sd in SEEDS) / n if n else float('nan')
        return f
    for key, lab in (('uses', 'USES THE LINE'), ('search', 'SEARCHES')):
        a_, b_ = sh('ASKED', key), sh('S15', key)
        n = len(both) * 3
        p(f'    {lab}: ASKED {rate(round(a_(both) * n), n)}, S of 15 {rate(round(b_(both) * n), n)} on {len(both)}'
          f' steps complete in both')
        line(f'      ASKED - S of 15, {lab}', both, lambda st, a_=a_, b_=b_: a_(st) - b_(st))
    same = sum(1 for s in both for sd in SEEDS
               if (U[(s, 'ASKED', sd)]['uses'], U[(s, 'ASKED', sd)]['search']) ==
               (U15[(s, 'S15', sd)]['uses'], U15[(s, 'S15', sd)]['search']))
    p(f'    same (USES THE LINE, SEARCHES) for the same step and seed: {rate(same, len(both) * 3)}')
    p('  (d) sensitivity of SEARCHES to what counts as a search (all usable replays)')
    for arm in ARMS:
        os_ = [o for k, o in U.items() if k[1] == arm]
        p(f'    {arm:5s} grep-family first program {sum(o["search"] for o in os_)}; plus find '
          f'{sum(o["kind"] == "run_command: find" for o in os_)}; plus search_similar_code '
          f'{sum(o["tool"] == "search_similar_code" for o in os_)}')
    p('  (e) USES THE LINE by the kind of read, and how far T2 is from its threshold')
    for arm in ARMS:
        os_ = [o for k, o in U.items() if k[1] == arm and o['uses']]
        p(f'    {arm:5s} uses {len(os_)}: read_file {sum(o["tool"] == "read_file" for o in os_)}, shell view '
          f'{sum(o["tool"] == "run_command" for o in os_)}, of which through a mangled start_line name '
          f'{sum(o["mangled_start"] for o in os_)}')
    cs = comp['T2']
    nt = sum(U[(s, 'TOLD', sd)]['uses'] for s in cs for sd in SEEDS)
    na = sum(U[(s, 'ASKED', sd)]['uses'] for s in cs for sd in SEEDS)
    need = math.ceil(2 * na / 3 - 1e-9)
    p(f'    T2: TOLD {nt} uses against ASKED {na}; "used about as often" needs TOLD at least {need} with ASKED as it is'
      f' ({need - nt} more), or ASKED at most {math.floor(3 * nt / 2 + 1e-9)} with TOLD as it is')
    reopen = sum(1 for k, o in U.items() if k[1] == 'TOLD' and k[0] in cs and not o['uses'] and o.get('reads_noted')
                 and o.get('noted_past_1'))
    reopen_a = sum(1 for k, o in U.items() if k[1] == 'ASKED' and k[0] in cs and not o['uses'] and o.get('reads_noted')
                   and o.get('noted_past_1'))
    p(f'    reads past line 1 of a noted file opened before (not first reads, so not counted): TOLD {reopen},'
      f' ASKED {reopen_a}; counted, the ratio would be {(nt + reopen) / (na + reopen_a):.3f}')
    mg_t = sum(1 for k, o in U.items() if k[1] == 'TOLD' and k[0] in cs and o['uses'] and o['mangled_start'])
    mg_a = sum(1 for k, o in U.items() if k[1] == 'ASKED' and k[0] in cs and o['uses'] and o['mangled_start'])
    p(f'    with a mangled start_line name not counted as asking, the ratio would be {(nt - mg_t) / (na - mg_a):.3f}')
    p('  (f) seeds: steps whose three seeds gave the same next call (function and arguments), by arm')
    for arm in ARMS:
        st_ = [s for s in sids if all((s, arm, sd) in cell for sd in SEEDS)]
        same3 = sum(1 for s in st_ if len({json.dumps(cell[(s, arm, sd)]['next_call'], sort_keys=True)
                                          for sd in SEEDS}) == 1)
        p(f'    {arm:5s} {same3} of {len(st_)}')
    cs = comp['T4']

    def wide(arm):
        def f(st):
            n = len(st) * 3
            return sum((U[(s, arm, sd)]['search'] or U[(s, arm, sd)]['tool'] == 'search_similar_code'
                        or U[(s, arm, sd)]['kind'] == 'run_command: find') for s in st for sd in SEEDS) / n
        return f
    line('(d, continued) T4 with find and search_similar_code counted as searches, TOLD - NONE (no verdict)', cs,
         lambda st: wide('TOLD')(st) - wide('NONE')(st))
    p('')
    p('5. JUDGMENT CALLS')
    for j in JUDGMENT:
        p('  - ' + j)
    text = '\n'.join(L) + '\n'
    sys.stdout.write(text)
    if not no_write:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return 0


JUDGMENT = [
    'Arm of a row: the suffix of the fork id of the record it names by (task, run, fork); NONE and ASKED both run as'
    ' the runner arm A.',
    'Scored files of NONE, TOLD and ASKED: re-derived from the last step of the ASKED record (the recorded search and'
    ' its result) with the parser and the "opened" rule of rederive_15: repository .py files with a hit line, not'
    ' opened earlier. TOLDX: parsed from its own note (path:line:text), repository files not opened earlier. Compared'
    ' with the stored hit_files; the re-derived ones are used for scoring.',
    'USES THE LINE: rederive_15.score on the scored files, reads_hit_file and past_line_1 (a read_file, or a shell'
    ' view by cat/head/tail/sed -n, of a scored file, starting past line 1). A scored file is unopened by'
    ' construction, so every such read is a first read. A start_line under a mangled name (equal to start_line once'
    ' quotes, backslashes and blanks are removed) counts as written.',
    'SEARCHES: a run_command whose first program is grep, egrep, fgrep, rg, ag, ack or git grep (find and'
    ' search_similar_code not counted; printed apart under 4d).',
    'Usable: not an interface failure under rederive_15 (runner error, no call, unknown tool, malformed call).'
    ' A step is complete for a rule if both arms compared have usable calls for seeds 1 to 3.',
    'Shares pool the replays of the steps (equal to the mean of per-step shares, since every complete step has three'
    ' replays per arm). Each rule draws its own 2,000 resamples of steps from a fresh random.Random(0); percentile'
    ' interval by linear interpolation at 2.5% and 97.5%.',
    'T2 is decided on the point ratio (at least two thirds); its interval is printed. A resample with ASKED at zero is'
    ' left out and counted. The ratio of 15\'s form leaves out a resample whose denominator is not above 0.',
    'Per-source T3 uses the steps complete for T3, split by the stored toldx_source.',
    'Next call when the line is not used: categories in this order: a read (as rederive_15 detects one) of any'
    ' repository file with a hit line in the note, from line 1; the same past line 1 (possible only for a noted file'
    ' opened before); a search; edit_file; anything else (write_file among it), with its kind.',
    'Repeat of the recorded search: the next search command equals the recorded search command once every single and'
    ' double quote is removed and runs of blanks are collapsed to one space (ends stripped).',
    'ASKED against 15: rows of 15 whose fork is the state_of_15 of the step (<step>:S), scored with the same files and'
    ' the same rules; compared on steps with three usable replays in both.',
]

if __name__ == '__main__':
    sys.exit(main(sys.argv))
