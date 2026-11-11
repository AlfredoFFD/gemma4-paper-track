"""Independent re-derivation of pre-registration 24 (asked or told, on models of other publishers through a hosted API).

Written blind: from the text of prereg/24-asked-or-told-on-hosted-models.md (with its dated note), the outcomes of
prereg/20-asked-or-told.md, the states file analysis/fork_states_t/states.jsonl and the stored rows
analysis/results/24/<model>/results.jsonl (and, for the reference row, analysis/results/20/forks/results.jsonl).
It does not import or read analyze_24.py, analyze_20.py, analyze_19.py, analyze_15.py or any output of theirs.
It reuses, by import, the blind second scripts of earlier designs: rederive_15.py (the scorer of one call: paths,
hit lines of a search result, reads of a file and their first line, searches) and rederive_19.py (the usable call
on the API path, with the nine tools the agent declares).

Usage: py -I -X utf8 analysis/rederive_24.py [--no-write]
Writes analysis/results/rederive_24.txt (LF), equal to its stdout, unless --no-write is given.
"""
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_15 as R  # noqa: E402  scorer of one call (design 17 / 20)
import rederive_19 as R19  # noqa: E402  usable call on the API path (nine tools)

STATES = HERE / 'fork_states_t' / 'states.jsonl'
STATES_MD5 = '750b3e0952608bf023e69a338f26b030'
RUNNER_MD5 = '7cdccc91d744794fd5cc9ff2dee4875b'
RES24 = HERE / 'results' / '24'
ROWS20 = HERE / 'results' / '20' / 'forks'
OUT = HERE / 'results' / 'rederive_24.txt'

ARMS = ('NONE', 'TOLD', 'ASKED', 'TOLDX')
SEEDS = (1, 2, 3)
B = 2000
BOOT_SEED = 0
GATE = 0.80
FLOOR = 40
SLACK = 10
NOTE_HEAD = 'Matches in the repository:'
# the seven models in the order of the registration; matched to the result folders by these names
MODELS = ['Qwen3-30B-A3B-Instruct-2507', 'Qwen3-235B-A22B-Instruct-2507', 'gpt-oss-120b', 'DeepSeek-V4.1-Flash-1017',
          'GLM-5.3-Flash', 'MiniMax-M3.1-Flash', 'nemotron-3-super-120b']
REF = 'Gemma-4-31B (rows of 20)'

L = []


def p(s=''):
    L.append(s)


# ---------------------------------------------------------------- states

def parse_note(task, note):
    lines = note.split('\n')
    assert lines[0] == NOTE_HEAD, lines[0]
    out = []
    for ln in lines[1:]:
        m = R.HIT_PATH.match(ln)
        assert m, ln
        out.append((R.repo_file(task, m['path']), int(m['line'])))
    return out


def load_states():
    recs = [json.loads(x) for x in STATES.read_text(encoding='utf-8').splitlines() if x.strip()]
    by = defaultdict(dict)
    for r in recs:
        by[r['state_id']][r['arm']] = r
    info, fork_to, diffs = {}, {}, []
    for sid in sorted(by):
        rs = by[sid]
        a = rs['ASKED']
        task = a['task']
        last = a['steps'][-1]
        cmd = last['tool_calls'][0]['arguments']['command']
        hits = R.parse_result(task, cmd, R.stdout_of(R.obs_of(last)))[0]
        opened = R.opened_before(task, a['steps'])
        files = R.snapshot(task)[0]
        own = defaultdict(list)
        for h in hits:
            if h['file'] in files and h['file'] not in opened:
                own[h['file']].append(h['line'])
        own = {f: sorted(set(v)) for f, v in own.items()}
        hf = {'NONE': own, 'TOLD': own, 'ASKED': own}
        source = None
        if 'TOLDX' in rs:
            x = rs['TOLDX']
            q = defaultdict(list)
            for f, ln in parse_note(task, x['arms']['TOLDX']['user_text']):
                if f is not None and f not in opened:
                    q[f].append(ln)
            hf['TOLDX'] = {f: sorted(set(v)) for f, v in q.items()}
            source = x.get('toldx_source')
        for arm, r in rs.items():
            stored = {f: sorted(v) for f, v in (r.get('hit_files') or {}).items()}
            if stored != hf[arm]:
                diffs.append(f'{sid} {arm}')
            fork_to[(r['task'], r['run'], r['fork'])] = (sid, arm)
        info[sid] = {'task': task, 'hf': hf, 'source': source, 'arms': set(rs)}
    return info, fork_to, diffs


# ---------------------------------------------------------------- one replay

def window(task, nc, hf):
    """(file, first, last) of a read of a scored file, the window as rederive_15.score takes it; else None."""
    fn, a = nc['function_name'], nc['arguments']
    if fn == 'read_file':
        f = R.repo_file(task, a.get('filepath'))
        if f not in hf:
            return None
        start = end = None
        for k, v in a.items():
            ck = R.clean_name(k)
            if ck == 'start_line':
                start = R.as_int(v)
            elif ck == 'end_line':
                end = R.as_int(v)
        s = start if (start is not None and start >= 1) else 1
        e = end if (end is not None and end >= s) else s + 149
        return f, s, min(e, s + 149)
    if fn == 'run_command':
        return R.shell_read(task, a.get('command') or '', hf)
    return None


def score(task, row, hf):
    o = R.score(task, row, hf)
    o['uses'] = bool(o['reads_hit_file'] and o['past_line_1'])
    o['search'] = bool(o['searches_again'])
    o['wide_search'] = o['search'] or o['tool'] == 'search_similar_code' or o['kind'] == 'run_command: find'
    w = window(task, row['next_call'], hf) if o['reads_hit_file'] else None
    near = bool(w) and any(w[1] - SLACK <= h <= w[2] + SLACK for h in hf[w[0]])
    o['covers'] = near
    o['strict'] = o['uses'] and near
    return o


# ---------------------------------------------------------------- statistics

def boot(steps, fn, info, by='step'):
    """Point estimate and 95% percentile interval (linear interpolation), 2,000 resamples from random.Random(0),
    of steps or of tasks (each drawn task brings all its steps of the set); resamples giving nan are left out."""
    rng = random.Random(BOOT_SEED)
    pt = fn(steps) if steps else float('nan')
    if not steps:
        return pt, float('nan'), float('nan'), B
    groups = defaultdict(list)
    for s in steps:
        groups[info[s]['task']].append(s)
    tasks = sorted(groups)
    vals, left = [], 0
    n = len(steps)
    for _ in range(B):
        if by == 'step':
            st = [steps[rng.randrange(n)] for _ in range(n)]
        else:
            st = [s for _ in range(len(tasks)) for s in groups[tasks[rng.randrange(len(tasks))]]]
        v = fn(st)
        if v is None or math.isnan(v):
            left += 1
        else:
            vals.append(v)
    return pt, R.pct(vals, 0.025), R.pct(vals, 0.975), left


def fpt(x):
    return 'n/a' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{100 * x:+.1f}'


def fsh(x):
    return 'n/a' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{100 * x:.1f}%'


def rate(k, n):
    return f'{k}/{n} ({fsh(k / n) if n else "n/a"})'


def fci(t):
    pt, lo, hi, left = t
    ex = f'; {left} resamples left out' if left else ''
    return f'{fpt(pt)} [{fpt(lo)}, {fpt(hi)}]{ex}'


def fratio(t):
    pt, lo, hi, left = t
    f = (lambda x: 'n/a' if math.isnan(x) else f'{x:.3f}')
    ex = f'; {left} resamples left out' if left else ''
    return f'{f(pt)} [{f(lo)}, {f(hi)}]{ex}'


# ---------------------------------------------------------------- one model

def find_dir(name):
    for d in sorted(RES24.iterdir()):
        if d.is_dir() and name.lower() in d.name.lower():
            return d
    return None


def analyze(label, run_dir, info, fork_to, is_ref=False):
    rows = [json.loads(x) for x in (run_dir / 'results.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    sids = sorted(info)
    cell, unmatched, dup, arm_mism, sid_mism = {}, 0, 0, 0, 0
    runner = Counter()
    api_fail = Counter()
    for r in rows:
        k = (r['task'], r['run'], r['fork'])
        if k not in fork_to:
            unmatched += 1
            continue
        sid, arm = fork_to[k]
        runner[(arm, r.get('arm'))] += 1
        if r.get('record_arm') not in (None, arm):
            arm_mism += 1
        if r.get('state_id') not in (None, sid):
            sid_mism += 1
        c = (sid, arm, r['seed'])
        if c in cell:
            dup += 1
            continue
        cell[c] = r
    expected = sum(len(info[s]['arms']) for s in sids) * len(SEEDS)
    U, fails = {}, defaultdict(Counter)
    for c, r in cell.items():
        if R19.is_api_failure(r):
            api_fail[c[1]] += 1
            continue
        f = R19.failure_17(r)
        if f:
            fails[c[1]][f] += 1
            continue
        U[c] = score(info[c[0]]['task'], r, info[c[0]]['hf'][c[1]])
    n_rows = len(rows)
    n_usable = len(U)
    gate_share = n_usable / n_rows if n_rows else 0.0
    gate_ok = n_rows > 0 and gate_share >= GATE

    p(f'MODEL {label}' + ('  (reference row: enters no rule and no count across models)' if is_ref else ''))
    p(f'  rows {R19.RC.shown(run_dir / "results.jsonl")}')
    # ---- facts of the run
    summ = run_dir / 'summary.json'
    s = json.loads(summ.read_text(encoding='utf-8')) if summ.exists() else {}
    st = s.get('stats') or {}
    ver = run_dir / 'versions.json'
    v = json.loads(ver.read_text(encoding='utf-8')) if ver.exists() else {}
    md = v.get('md5') or {}
    if not is_ref:
        p(f'  run: api model {v.get("api_model")}; harness {v.get("harness_variant")}, wheels '
          f'{", ".join(v.get("harness_wheels") or [])}; runner md5 {md.get("runner")} '
          f'({"as frozen" if md.get("runner") == RUNNER_MD5 else "DIFFERS"}); states md5 {md.get("states_file")} '
          f'({"as frozen" if md.get("states_file") == STATES_MD5 else "DIFFERS"})')
        rep = Counter((r.get('api') or {}).get('model_reported') for r in rows)
        fin = Counter((r.get('api') or {}).get('finish_reason') for r in rows)
        p(f'  reported model {dict(rep)}; finish reasons {dict(sorted(fin.items(), key=lambda kv: str(kv[0])))}')
        p(f'  cost {st.get("dollars")} dollars; elapsed {s.get("elapsed_s")} s; stopped_by {st.get("stopped_by")!r}; '
          f'API failures (summary) {st.get("api_failures")}; retries {st.get("retries")}')
        rc = [(r.get('api') or {}).get('reasoning_chars') or 0 for r in rows]
        p(f'  reasoning chars: median {statistics.median(rc) if rc else "n/a"}, mean '
          f'{(sum(rc) / len(rc)) if rc else 0:.0f}, replies with reasoning {sum(1 for x in rc if x)}/{len(rc)}')
    else:
        p(f'  run: elapsed {s.get("elapsed_s")} s (summary of 20)')
    multi_api = sum(1 for r in rows if ((r.get('api') or {}).get('n_tool_calls') or 0) > 1)
    multi_parsed = sum(1 for r in rows if len(r.get('all_calls') or []) > 1)
    no_all = sum(1 for r in rows if 'all_calls' not in r)
    nc_ne = sum(1 for r in rows if (r.get('all_calls') or []) and r.get('next_call') != r['all_calls'][0])
    p(f'  replies with more than one tool call: {multi_api} by the API count, {multi_parsed} as parsed (all_calls);'
      f' rows without all_calls {no_all}; rows whose next_call is not the first of all_calls {nc_ne}')
    p(f'  rows {n_rows} (expected {expected}); unmatched {unmatched}; repeated cells {dup}; missing cells '
      f'{expected - len(cell)}; record_arm differing from the fork id {arm_mism}; state_id differing {sid_mism}')
    p('  runner arm by design arm: ' + ', '.join(f'{a} as {ra}: {n}' for (a, ra), n in sorted(runner.items())))
    for arm in ARMS:
        n = sum(1 for c in cell if c[1] == arm)
        u = sum(1 for c in U if c[1] == arm)
        fl = ', '.join(f'{k} {v_}' for k, v_ in sorted(fails[arm].items())) or 'none'
        p(f'    {arm:5s} rows {n}; API failures {api_fail[arm]}; replies without a usable call: {fl}; usable {rate(u, n)}')
    p(f'  GATE: usable {rate(n_usable, n_rows)} of rows -> {"PASSED" if gate_ok else "FAILED"} (threshold 80%)')

    # ---- per-step counts
    def count(arm, key):
        return {s: sum(U[(s, arm, sd)][key] for sd in SEEDS) for s in sids if all((s, arm, sd) in U for sd in SEEDS)}
    K = {(arm, key): count(arm, key) for arm in ARMS for key in ('uses', 'search', 'strict', 'wide_search')}

    def share(arm, key):
        k = K[(arm, key)]
        return lambda st_: (sum(k[s] for s in st_) / (3 * len(st_))) if st_ else float('nan')

    def diff(a1, a2, key):
        f1, f2 = share(a1, key), share(a2, key)
        return lambda st_: f1(st_) - f2(st_)

    def complete(*arms):
        return [s for s in sids if all((s, a, sd) in U for a in arms for sd in SEEDS)]

    p('  OUTCOMES PER ARM (all usable replays)')
    for arm in ARMS:
        os_ = [o for c, o in U.items() if c[1] == arm]
        n = len(os_)
        p(f'    {arm:5s} usable {n}; USES THE LINE {rate(sum(o["uses"] for o in os_), n)}; SEARCHES '
          f'{rate(sum(o["search"] for o in os_), n)}; strict {rate(sum(o["strict"] for o in os_), n)}; '
          f'search with find and search_similar_code {rate(sum(o["wide_search"] for o in os_), n)}; '
          f'uses via a mangled start_line {sum(1 for o in os_ if o["uses"] and o["mangled_start"])}')
    p('  NEXT CALL PER ARM (all usable replays, by kind)')
    for arm in ARMS:
        kinds = Counter(o['kind'] for c, o in U.items() if c[1] == arm)
        p(f'    {arm:5s} ' + ', '.join(f'{k} {v_}' for k, v_ in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))))

    # ---- rules
    res = {'label': label, 'gate_ok': gate_ok, 'gate': gate_share, 'is_ref': is_ref}
    for arm in ARMS:
        os_ = [o for c, o in U.items() if c[1] == arm]
        res['uses_' + arm] = (sum(o['uses'] for o in os_), len(os_))
        res['search_' + arm] = (sum(o['search'] for o in os_), len(os_))
        res['strict_' + arm] = (sum(o['strict'] for o in os_), len(os_))
    p('  RULES (95% percentile interval, bootstrap by step, 2,000 resamples, random.Random(0), paired by step on the steps'
      ' complete in both arms; floor 40 complete steps)')
    spec = [('W1', 'USES THE LINE, TOLD - NONE', 'TOLD', 'NONE', 'uses'),
            ('W2', 'USES THE LINE, ASKED - TOLD', 'ASKED', 'TOLD', 'uses'),
            ('W3', 'SEARCHES, TOLD - NONE', 'TOLD', 'NONE', 'search')]
    for w, name, a1, a2, key in spec:
        cs = complete(a1, a2)
        t = boot(cs, diff(a1, a2, key), info)
        tt = boot(cs, diff(a1, a2, key), info, by='task')
        lo, hi = t[1], t[2]
        if not gate_ok:
            verdict, met = 'no verdict: gate', False
        elif len(cs) < FLOOR:
            verdict, met = f'no verdict: floor ({len(cs)} complete steps; counts as not met)', False
        elif w == 'W1':
            verdict, met = ('used', True) if lo > 0 else ('not met', False)
        elif w == 'W2':
            if lo > 0:
                verdict, met = 'used less than asked', True
            elif hi < 0:
                verdict, met = 'used more than asked', False
            else:
                verdict, met = 'no detectable difference', False
        else:
            verdict, met = ('telling replaces the search', True) if hi < 0 else ('not met', False)
        res[w] = {'n': len(cs), 't': t, 'tt': tt, 'verdict': verdict, 'met': met}
        p(f'    {w}  {name}: complete steps {len(cs)}; {a1} {fsh(share(a1, key)(cs))}, {a2} {fsh(share(a2, key)(cs))};'
          f' difference {fci(t)} points -> {verdict}')
        p(f'        tasks resampled in place of steps ({len({info[s]["task"] for s in cs})} tasks, no rule): {fci(tt)}')
        if w == 'W2':
            p('        (ASKED is paused one call later than TOLD: after the search, not before it.)')

    p('  PRINTED WITHOUT A RULE')
    cs = complete('TOLD', 'ASKED')
    ft, fa = share('TOLD', 'uses'), share('ASKED', 'uses')

    def ratio(st_):
        d = fa(st_)
        return ft(st_) / d if d > 0 else float('nan')
    tr, trt = boot(cs, ratio, info), boot(cs, ratio, info, by='task')
    res['ratio'] = tr
    p(f'    ratio TOLD / ASKED on USES THE LINE ({len(cs)} steps): {fratio(tr)}; tasks resampled {fratio(trt)}')
    csx = [s for s in complete('TOLD', 'TOLDX') if 'TOLDX' in info[s]['arms']]
    tx, txt = boot(csx, diff('TOLD', 'TOLDX', 'uses'), info), boot(csx, diff('TOLD', 'TOLDX', 'uses'), info, by='task')
    res['toldx'] = (len(csx), tx)
    p(f'    TOLD - TOLDX, USES THE LINE ({len(csx)} steps complete in both; no floor, no verdict): TOLD '
      f'{fsh(share("TOLD", "uses")(csx))}, TOLDX {fsh(share("TOLDX", "uses")(csx))}; {fci(tx)} points; tasks resampled '
      f'{fci(txt)}')

    # ---- cut (2) of the dated note
    p('  CUT (2) OF THE DATED NOTE (exploratory): W2 split by whether the model\'s own next call under NONE is a search'
      ' in at least two of the three seeds')
    res['cut2'] = {}
    for lab, key in (('search as SEARCHES counts it (grep family)', 'search'),
                     ('variant: find and search_similar_code also counted', 'wide_search')):
        srch = {s for s in sids if sum(1 for sd in SEEDS if (s, 'NONE', sd) in U and U[(s, 'NONE', sd)][key]) >= 2}
        cw2 = complete('TOLD', 'ASKED')
        a_ = [s for s in cw2 if s in srch]
        b_ = [s for s in cw2 if s not in srch]
        ta = boot(a_, diff('ASKED', 'TOLD', 'uses'), info)
        tb = boot(b_, diff('ASKED', 'TOLD', 'uses'), info)
        if key == 'search':
            res['cut2'] = {'a': (len(a_), ta), 'b': (len(b_), tb)}
        p(f'    {lab}:')
        p(f'      NONE searches in >= 2 of 3 seeds: {len(a_)} steps; ASKED {fsh(share("ASKED", "uses")(a_))}, TOLD '
          f'{fsh(share("TOLD", "uses")(a_))}; ASKED - TOLD {fci(ta)} points')
        p(f'      other steps:                       {len(b_)} steps; ASKED {fsh(share("ASKED", "uses")(b_))}, TOLD '
          f'{fsh(share("TOLD", "uses")(b_))}; ASKED - TOLD {fci(tb)} points')

    # ---- cut (3) of the dated note
    p(f'  CUT (3) OF THE DATED NOTE (exploratory): strict outcome = USES THE LINE and the window read covers a hit line'
      f' of the note, give or take {SLACK} lines')
    for arm in ARMS:
        os_ = [o for c, o in U.items() if c[1] == arm]
        n = len(os_)
        cov1 = sum(1 for o in os_ if o['covers'] and not o['past_line_1'])
        p(f'    {arm:5s} strict {rate(sum(o["strict"] for o in os_), n)} (USES THE LINE {sum(o["uses"] for o in os_)});'
          f' first reads from line 1 whose window covers a hit line (not counted) {cov1}')
    res['strict'] = {}
    for w, name, a1, a2 in (('W1', 'strict, TOLD - NONE', 'TOLD', 'NONE'), ('W2', 'strict, ASKED - TOLD', 'ASKED', 'TOLD')):
        cs = complete(a1, a2)
        t = boot(cs, diff(a1, a2, 'strict'), info)
        res['strict'][w] = (len(cs), t)
        p(f'    {w} on the strict outcome: {len(cs)} steps; {a1} {fsh(share(a1, "strict")(cs))}, {a2} '
          f'{fsh(share(a2, "strict")(cs))}; {fci(t)} points (no rule; interval '
          f'{"above" if t[1] > 0 else "below" if t[2] < 0 else "across"} zero)')
    p('')
    return res


# ---------------------------------------------------------------- main

def main(argv):
    no_write = '--no-write' in argv[1:]
    p('Re-derivation of pre-registration 24 (independent script, written blind from the registration texts and the raw rows)')
    p('Script: analysis/rederive_24.py; imports rederive_15.py (scorer of one call) and rederive_19.py (usable call).')
    h = hashlib.md5(STATES.read_bytes()).hexdigest()
    p(f'States file analysis/fork_states_t/states.jsonl md5 {h} ({"as frozen" if h == STATES_MD5 else "DIFFERS"})')
    info, fork_to, diffs = load_states()
    sids = sorted(info)
    p(f'  steps {len(sids)}; tasks {len({info[s]["task"] for s in sids})}; records by arm: '
      + ', '.join(f'{a} {sum(1 for s in sids if a in info[s]["arms"])}' for a in ARMS)
      + f'; scored files re-derived and differing from the stored hit_files: {len(diffs)}'
      + (' (' + ', '.join(diffs) + ')' if diffs else ''))
    p(f'Bootstrap: {B} resamples, random.Random({BOOT_SEED}), percentile 95% by linear interpolation; gate 80% of rows'
      f' with a usable tool call; floor {FLOOR} complete steps.')
    p('')
    results = []
    for m in MODELS:
        d = find_dir(m)
        if d is None or not (d / 'results.jsonl').exists():
            p(f'MODEL {m}: no rows')
            p('')
            continue
        results.append(analyze(m, d, info, fork_to))
    ref = analyze(REF, ROWS20, info, fork_to, is_ref=True)

    p('TABLE ACROSS MODELS (USES THE LINE per arm on all usable replays; W1, W2, W3 in points with the 95% bootstrap'
      ' interval by step, complete steps, verdict)')
    for r in results + [ref]:
        u = ' '.join(f'{a} {fsh(r["uses_" + a][0] / r["uses_" + a][1]) if r["uses_" + a][1] else "n/a"}' for a in ARMS)
        p(f'  {r["label"]}{" [reference]" if r["is_ref"] else ""}: gate {fsh(r["gate"])} '
          f'{"passed" if r["gate_ok"] else "FAILED"}; USES THE LINE {u}')
        for w in ('W1', 'W2', 'W3'):
            x = r[w]
            p(f'      {w} {fci(x["t"])} n={x["n"]} -> {x["verdict"]}{" (met)" if x["met"] else ""}')
        p(f'      ratio TOLD/ASKED {fratio(r["ratio"])}; TOLD - TOLDX {fci(r["toldx"][1])} n={r["toldx"][0]}')
    p('')
    p('READING ACROSS MODELS (the seven hosted models only)')
    through = [r for r in results if r['gate_ok']]
    n = len(through)
    p(f'  models through the gate: {n} of {len(results)}'
      + (' (left out: ' + ', '.join(r['label'] for r in results if not r['gate_ok']) + ')' if n < len(results) else ''))
    w1 = [r for r in through if r['W1']['met']]
    both = [r for r in through if r['W1']['met'] and r['W2']['met']]
    w3 = [r for r in through if r['W3']['met']]
    if n >= 5:
        need = math.ceil(6 * n / 7)
        p(f'  needed number ceil(6n/7) = {need}')
        p(f'  models that count (W1 and W2 both met): {len(both)} of {n}: ' + (', '.join(r['label'] for r in both) or 'none'))
        p(f'  W1 met on {len(w1)} of {n}: ' + (', '.join(r['label'] for r in w1) or 'none'))
        if len(both) >= need:
            p('  OUTCOME 1: the sentence is written, worded as the dated note asks: "a line in a note is used, and less'
              ' often than the same line in a search result" (on models of other publishers).')
        elif len(w1) >= need:
            p('  OUTCOME 2: W1 is met on at least the needed number and fewer models count: the discount is not general;'
              ' W2 not met on: ' + ', '.join(f'{r["label"]} ({r["W2"]["verdict"]})' for r in through
                                               if not r['W2']['met']))
        else:
            p('  OUTCOME 3: any other outcome: reported model by model, no sentence across models.')
    else:
        p('  OUTCOME 3: fewer than 5 models through the gate: reported model by model, no sentence across models.')
    p(f'  W3 met on {len(w3)} of {n}: ' + (', '.join(r['label'] for r in w3) or 'none'))
    p('  The seven models share one sample of 53 steps from 26 tasks: they are not seven independent tests.')
    p('')
    p('CUTS OF THE DATED NOTE ACROSS MODELS (exploratory)')
    for r in results + [ref]:
        a, b = r['cut2']['a'], r['cut2']['b']
        s1, s2 = r['strict']['W1'], r['strict']['W2']
        p(f'  {r["label"]}: (2) W2 where NONE searches {fci(a[1])} n={a[0]}; other steps {fci(b[1])} n={b[0]};'
          f' (3) strict W1 {fci(s1[1])}, strict W2 {fci(s2[1])}')
    p('')
    p('JUDGMENT CALLS (where the registration left room)')
    for j in JUDGMENT:
        p('  - ' + j)
    text = '\n'.join(L) + '\n'
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode('utf-8'))  # LF on every platform, byte-equal to the file
    sys.stdout.buffer.flush()
    if not no_write:
        with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
    return 0


JUDGMENT = [
    'Rows are mapped to steps and arms by (task, run, fork) against the states file; the fork id ends in the arm.'
    ' record_arm and state_id are only checked against it. A repeated (step, arm, seed) keeps the first row.',
    'API failure: api.error_kind "api". Usable call: rederive_19.failure_17 (the classes of rederive_15: runner error,'
    ' no call, unknown tool, malformed; with the nine tools the agent declares known, the graph tools judged by'
    ' fork_states.valid_call). A row with an error (an adapter JSON error) is a reply without a usable call.',
    'Gate: usable rows divided by all rows of the model (API failures in the denominator, as "of its rows" reads);'
    ' passed at 80% or more.',
    'Scored files: re-derived from the recorded search of the ASKED record (NONE, TOLD, ASKED) and from the TOLDX note,'
    ' repository .py files not opened earlier, as in rederive_20; compared with the stored hit_files.',
    'USES THE LINE: rederive_15.score reads_hit_file and past_line_1. SEARCHES: a run_command whose first program is'
    ' grep, egrep, fgrep, rg, ag, ack or git grep, as in rederive_20; find and search_similar_code are not searches'
    ' there, and a variant counting them is printed beside (it matters on models that call search_similar_code).',
    'Strict outcome (cut 3): USES THE LINE and the window read covers a hit line of the note (the scored lines of that'
    ' file) give or take 10 lines. Window: read_file from start_line (1 if absent) to end_line, at most 150 lines (the'
    ' window of rederive_15); a shell view by its known range. Taken as a subset of USES THE LINE ("strict twin");'
    ' first reads from line 1 whose window covers a hit line are counted and printed apart.',
    'Cut 2: a step is a NONE-search step if at least two of its three NONE replays are usable and a search; it is'
    ' computed on the steps complete for W2. A variant counts find and search_similar_code as searches.',
    'Shares pool the replays of complete steps (three per arm). Each interval draws its own 2,000 resamples from a'
    ' fresh random.Random(0). By task: the tasks of the complete steps are drawn with replacement, each with all its'
    ' complete steps. The ratio leaves out a resample with ASKED at zero.',
    'Verdicts: no verdict if the gate fails or fewer than 40 complete steps (then not met); W1 met if the lower bound'
    ' is above 0; W2 "used less than asked" if the lower bound is above 0, "used more than asked" if the upper bound'
    ' is below 0, else "no detectable difference"; W3 met if the upper bound is below 0.',
    'Reference row: the rows of 20 scored by the same code, printed in the table, not counted. Its rows carry no api'
    ' field, so no API failure can be detected there.',
]

if __name__ == '__main__':
    sys.exit(main(sys.argv))
