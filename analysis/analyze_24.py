"""Experiment 24 (BUILD, not registered): the design of pre-registration 20 ("asked or told") on the hosted models of
pre-registration 19, one verdict per model on each rule, and a table across models at the top.

Usage:
    py -I -X utf8 analysis/analyze_24.py [root] [--no-write] [--run <run_dir>:<label> ...] [--no-reference]

root (default analysis/results/24) holds <model id with / replaced by __>/results.jsonl, as analysis/store_24.py stores
the rows of analysis/modal_g/forks_24_modal.py (one row per model, step, arm and seed; the arm is the runner arm of
20, A, TOLD or TOLDX, and the record is found by task, run and fork, as in 20). --run adds a run directory by hand (a
stand-in test); with --run the report is never written. Without --no-write the report also goes to
<root>/analyze_24.txt, and that file holds exactly what --no-write prints.

The rows of pre-registration 20 (Gemma-4-31B, analysis/results/20/forks) are analyzed by the same code and printed as a
reference row, marked as such; they enter no rule and no count across models (--no-reference leaves them out).

Everything that scores or tests is imported from analysis/analyze_20.py (and through it from analyze_15, analyze_forks
and gates_c), not copied: the row loader (load_cells), the interface-failure rule (failure), the scorer (score: USES
THE LINE is `reads_hit_file and past_line_1` on the record's hit_files; SEARCHES is `searches_again`), the next-call
categories (category), the bootstrap by step (diff_ci, boot_ci; 2,000 resamples, seed 0), the ratio (ratio_ci) and the
grouping by task (by_task). The gate and the failure counts by kind are those of analysis/analyze_19.py.

Per model:
  gate   the model enters the rules only if at least 80% of its rows hold a usable call (gates_c.failure: no runner
         or API error, a call, a known tool, valid arguments), the rule of 19. A model below it is reported and left
         out of every rule and of the reading across models.
  steps  a step enters a rule if both arms the rule compares have a usable replay for each of seeds 1 to 3; a step
         missing any of those six rows (an API failure after the retries, a cut by the cost stop or the time budget,
         an interface failure) is left out of that rule only. The number of complete steps is printed beside each
         rule; below 40 complete steps (the floor of T1, T2 and T4 in 20) a rule gets no verdict.
  W1     USES THE LINE, TOLD minus NONE: "used" if the 95% interval lies above zero, else "not met".
  W2     USES THE LINE, ASKED minus TOLD: "used less than asked" if the interval lies above zero; "used more than
         asked" if it lies below zero; else "no detectable difference". W2 is met only in the first case.
  W3     SEARCHES, TOLD minus NONE: "telling replaces the search" if the interval lies below zero, else "not met".
  Printed without a rule: the ratio TOLD / ASKED on USES THE LINE with its interval; TOLD minus TOLDX on USES THE
  LINE, on the steps complete in both (TOLDX exists on 26 steps; TOLDX is scored on the files of its own note); every
  interval again with tasks resampled in place of steps; rates per arm; the next call by arm; replies with more than
  one tool call; reasoning lengths; cost and time from summary.json.
Across models (fixed in the registration): with n models through the gate, n at least 5, a model counts if W1 and W2
are both met on it; the sentence "a told line is used, and less often than an asked one, on models of other
publishers" is written only if at least ceil(6n/7) models count (6 of 7, 6 of 6, 5 of 5); if W1 is met on at least
ceil(6n/7) and fewer count, the discount is not general and the models without it are named; any other outcome, or
fewer than 5 models through the gate, is reported as it falls. Gate failures and rules without a verdict are not met.
"""
import argparse
import collections
import json
import math
import statistics as st
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_19 as A19  # noqa: E402
import analyze_20 as T  # noqa: E402

ROOT = HERE.parent
ARMS = T.ARMS                                     # NONE, TOLD, TOLDX, ASKED
FLOOR = 40                                        # complete steps for W1, W2 and W3 (20's floor of T1, T2 and T4)
VALID_MIN = A19.VALID_MIN                         # 0.80, the gate of 19
SEEDS = T.SEEDS
PLANNED = 555                                     # 53 steps x NONE, TOLD, ASKED x 3 seeds + 26 x TOLDX x 3
REF_DIR = HERE / 'results' / '20' / 'forks'
REF_LABEL = 'Gemma-4-31B (pre-registration 20; reference, not counted)'
ASKED15 = HERE / 'results' / '15' / 'forks'        # read by analyze_20.load_cells; its ASKED15 cells are dropped here


def analyze(run_dir, recs):
    """Every number of one model (or of the reference rows)."""
    rec_of = {(T.state_key(r), r['arm']): r for r in recs}
    states = sorted({T.state_key(r) for r in recs})
    has_x = {k for k in states if (k, 'TOLDX') in rec_of}
    cells, skipped, stray = T.load_cells(SimpleNamespace(run_dir=str(run_dir), asked=str(ASKED15), standin=False), recs)
    cells = [c for c in cells if c[1] != 'ASKED15']
    n, usable = collections.Counter(), collections.defaultdict(dict)
    for k, arm, seed, row in cells:
        n[arm] += 1
        if not T.failure(row):
            usable[k][(arm, seed)] = row
    rows = [c[3] for c in cells]
    fails = A19.fail_counts(rows, T.failure)
    valid = len(rows) - sum(fails.values())

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    def table(keys, a, what):
        def one(row):
            x = T.score(rec_of[(k, a)], row['next_call'])
            return int(x['reads_hit_file'] and x['past_line_1']) if what == 'uses' else int(x['searches_again'])
        out = {}
        for k in keys:
            out[k] = [one(usable[k][(a, s)]) for s in SEEDS]
        return out

    def pair(a, b, what):
        keys = complete((a, b))
        ta, tb = table(keys, a, what), table(keys, b, what)
        return {'steps': len(keys), 'd': T.diff_ci(ta, tb), 'd_task': T.diff_ci(T.by_task(ta), T.by_task(tb))}

    r = {'rows': len(rows), 'n': dict(n), 'valid': valid, 'fails': fails, 'skipped': skipped, 'stray': stray,
         'states': len(states), 'has_x': len(has_x)}
    r['W1'] = pair('TOLD', 'NONE', 'uses')
    r['W2'] = pair('ASKED', 'TOLD', 'uses')
    r['W3'] = pair('TOLD', 'NONE', 'search')
    r['X'] = pair('TOLD', 'TOLDX', 'uses')
    k2 = complete(('TOLD', 'ASKED'))
    tt, ta = table(k2, 'TOLD', 'uses'), table(k2, 'ASKED', 'uses')
    r['ratio'] = T.ratio_ci(tt, {}, ta, {})
    r['ratio_task'] = T.ratio_ci(T.by_task(tt), {}, T.by_task(ta), {})
    r['rates'] = {}
    for a in ARMS:
        keys = complete((a,))
        u, s_ = table(keys, a, 'uses'), table(keys, a, 'search')
        r['rates'][a] = {'steps': len(keys), 'uses': T.boot_ci(u), 'uses_n': sum(map(sum, u.values())),
                         'search': T.boot_ci(s_), 'search_n': sum(map(sum, s_.values())), 'replays': 3 * len(keys)}
    cat = {a: collections.Counter() for a in ARMS}
    for k, d in usable.items():
        for (a, _s), row in d.items():
            cat[a][T.category(T.score(rec_of[(k, a)], row['next_call']), row['next_call'])] += 1
    r['categories'] = cat
    r['multi_call'] = sum(((row.get('api') or {}).get('n_tool_calls') or 0) > 1 for row in rows)
    rc = [(row.get('api') or {}).get('reasoning_chars') for row in rows if (row.get('api') or {}).get('reasoning_chars')]
    r['reasoning'] = (len(rc), st.median(rc) if rc else None)
    sp = Path(run_dir) / 'summary.json'
    r['summary'] = json.load(open(sp, encoding='utf-8')) if sp.exists() else {}
    return r


def gate(r):
    if not r['rows']:
        return False, 'no rows'
    share = r['valid'] / r['rows']
    if share < VALID_MIN:
        return False, f'OUT (usable {100 * share:.1f}% < {100 * VALID_MIN:.0f}%)'
    return True, f'in ({100 * share:.1f}% usable)'


def verdicts(r):
    """{rule: (met, text)} for W1, W2 and W3 (met is False without a verdict)."""
    out = {}
    for w in ('W1', 'W2', 'W3'):
        x = r[w]
        d = x['d']
        if x['steps'] < FLOOR:
            out[w] = (False, f'no verdict (below the floor: {x["steps"]} complete steps < {FLOOR})')
        elif d[0] is None:
            out[w] = (False, 'no estimate')
        elif w == 'W1':
            out[w] = (True, 'used') if d[1] > 0 else (False, 'not met')
        elif w == 'W2':
            out[w] = (True, 'used less than asked') if d[1] > 0 else \
                (False, 'used more than asked') if d[2] < 0 else (False, 'no detectable difference')
        else:
            out[w] = (True, 'telling replaces the search') if d[2] < 0 else (False, 'not met')
    return out


def short(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def rate(t):
    return '  n/a' if t[0] is None else f'{100 * t[0]:5.1f}'


def discover(root):
    out = []
    for d in sorted(Path(root).glob('*'), key=lambda x: x.name.lower()) if Path(root).is_dir() else []:
        if (d / 'results.jsonl').exists():
            model = d.name.replace('__', '/', 1)
            v = d / 'versions.json'
            if v.exists():
                model = json.load(open(v, encoding='utf-8')).get('api_model', model)
            out.append((d, model))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default=str(HERE / 'results' / '24'))
    ap.add_argument('--run', action='append', default=[], help='<run_dir>:<label>')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--no-reference', action='store_true')
    ap.add_argument('--states', default=str(HERE / 'fork_states_t' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')   # stdout = the stored file, byte for byte
    runs = discover(args.root)
    for spec in args.run:
        run_dir, label = spec.rsplit(':', 1) if ':' in spec[2:] else (spec, spec)
        runs.append((Path(run_dir), label))
    recs = [json.loads(l) for l in open(args.states, encoding='utf-8')]
    lines = []

    def say(s=''):
        lines.append(s)
        print(s)

    say('EXPERIMENT 24 (BUILD, not registered): asked or told (the design of pre-registration 20) on the hosted models '
        'of pre-registration 19')
    if args.run:
        say('  STAND-IN: rows given with --run are analyzed below; this report is not written')
    say(f'  W1: USES THE LINE, TOLD minus NONE (met: "used", interval above 0). W2: USES THE LINE, ASKED minus TOLD (met: '
        f'"used less than asked", interval above 0). W3: SEARCHES, TOLD minus NONE (met: "telling replaces the search", '
        f'interval below 0). 95% bootstrap by step, 2,000 resamples, seed 0, on the steps complete in the two arms '
        f'(seeds 1 to 3 usable in both); floor {FLOOR} complete steps. Gate: at least {100 * VALID_MIN:.0f}% usable rows.')
    say()
    res = [(label, analyze(d, recs)) for d, label in runs]
    ref = None
    if not args.no_reference and (REF_DIR / 'results.jsonl').exists():
        ref = (REF_LABEL, analyze(REF_DIR, recs))
    if not res and ref is None:
        raise SystemExit(f'no run found under {args.root} and no --run given')

    head1 = (f'{"model":38s} {"family":18s} {"rows":>5s} {"gate":>24s} | USES THE LINE, % of replays: '
             f'{"NONE":>5s} {"TOLD":>5s} {"ASKED":>5s} {"TOLDX":>5s} | SEARCHES: {"NONE":>5s} {"TOLD":>5s}')
    say('1. Rates by arm (each arm on the steps complete in it)')
    say(head1)
    say('-' * len(head1))
    for label, r in res + ([ref] if ref else []):
        g = gate(r)[1]
        rt = r['rates']
        say(f'{label[:38]:38s} {A19.family(label if label != REF_LABEL else "google/gemma"):18s} {r["rows"]:5d} {g:>24s} | '
            f'{"":29s}{rate(rt["NONE"]["uses"])} {rate(rt["TOLD"]["uses"])} {rate(rt["ASKED"]["uses"])} '
            f'{rate(rt["TOLDX"]["uses"])} | {"":10s}{rate(rt["NONE"]["search"])} {rate(rt["TOLD"]["search"])}')
    say()
    say('2. Rules, one verdict per model (difference in points [95% interval by step]; complete steps)')
    head2 = f'{"model":38s} {"W1 TOLD - NONE":>34s} {"W2 ASKED - TOLD":>34s} {"W3 SEARCHES TOLD - NONE":>34s}  ratio TOLD/ASKED'
    say(head2)
    say('-' * len(head2))
    counted = []
    for label, r in res + ([ref] if ref else []):
        ok, _g = gate(r)
        v = verdicts(r)
        cells = []
        for w in ('W1', 'W2', 'W3'):
            cells.append(f'{short(r[w]["d"])} ({r[w]["steps"]})')
        ratio = T.rat(r['ratio'])
        say(f'{label[:38]:38s} {cells[0]:>34s} {cells[1]:>34s} {cells[2]:>34s}  {ratio}')
        if not ok:
            say(f'{"":38s} left out by the gate: {gate(r)[1]}')
        else:
            say(f'{"":38s} {"W1 " + v["W1"][1]:>34s} {"W2 " + v["W2"][1]:>34s} {"W3 " + v["W3"][1]:>34s}')
        if label != REF_LABEL:
            counted.append((label, ok, v))

    say()
    say('3. Reading across models (the hosted models only; the reference row is not counted)')
    passed = [(m, v) for m, ok, v in counted if ok]
    npass = len(passed)
    say(f'  models analyzed {len(counted)}; through the gate {npass}: {[m for m, _v in passed]}')
    say(f'  left out by the gate: {[m for m, ok, _v in counted if not ok]}')
    w1 = [m for m, v in passed if v['W1'][0]]
    both = [m for m, v in passed if v['W1'][0] and v['W2'][0]]
    w3 = [m for m, v in passed if v['W3'][0]]
    say(f'  W1 met on {len(w1)}; W1 and W2 both met on {len(both)}; W3 met on {len(w3)} (of {npass} through the gate)')
    if npass < 5:
        say('  fewer than 5 models through the gate: no sentence across models; reported as it falls')
    else:
        need = math.ceil(6 * npass / 7)
        say(f'  needed: {need} of {npass} (ceil(6n/7))')
        if len(both) >= need:
            say('  READING: "a told line is used, and less often than an asked one, on models of other publishers" '
                '(W1 and W2 both met on enough models)')
        elif len(w1) >= need:
            say('  READING: the discount is not general: W1 is met on enough models and W2 is not; models without W2 met: '
                + str([m for m, v in passed if v['W1'][0] and not v['W2'][0]]))
        else:
            say('  READING: neither case of the registration; reported as it falls')

    say()
    say('4. Per model, details (printed without a rule except where a rule is named)')
    for label, r in res + ([ref] if ref else []):
        say(f'  {label}:')
        fails = ', '.join(f'{k} {v}' for k, v in sorted(r['fails'].items())) or 'none'
        say(f'    rows {r["rows"]} (planned {PLANNED}); by arm {dict(sorted(r["n"].items()))}; rows that match no record '
            f'{r["stray"]}; cells entered as finished and not run {r["skipped"]}')
        say(f'    interface failures (excluded): {fails}; of them the API\'s own (no reply after the retries): '
            f'{r["fails"].get("api error", 0)}')
        for w, name in (('W1', 'W1'), ('W2', 'W2'), ('W3', 'W3'), ('X', 'TOLD minus TOLDX, USES THE LINE, no rule')):
            x = r[w]
            say(f'    {name}: {T.dpt(x["d"])} on {x["steps"]} complete steps; by task {T.span(x["d_task"])}')
        say(f'    ratio TOLD / ASKED on USES THE LINE, no rule: {T.rat(r["ratio"])}, resamples left out {r["ratio"][3]} '
            f'of 2000; by task ' + ('[n/a]' if r['ratio_task'][1] is None else
                                    f'[{r["ratio_task"][1]:.2f}, {r["ratio_task"][2]:.2f}]')
            + f', left out {r["ratio_task"][3]}')
        for a in ARMS:
            x = r['rates'][a]
            say(f'    arm {a:<5} {x["steps"]} complete steps; USES THE LINE {T.pct(x["uses"])} | {x["uses_n"]}/{x["replays"]}; '
                f'SEARCHES {T.pct(x["search"])} | {x["search_n"]}/{x["replays"]}')
        for a in ARMS:
            c = r['categories'][a]
            tot = sum(c.values())
            parts = ', '.join(f'{nm} {T.share(c[nm], tot)}' for nm in (
                'reads a noted file past line 1', 'reads a noted file from line 1', 'a search', 'an edit', 'something else'))
            say(f'    next call, arm {a:<5} {parts}')
        s = r['summary']
        stt = s.get('stats') or {}
        say(f'    replies with more than one tool call (the first is scored): {r["multi_call"]}; replies with reasoning '
            f'returned apart: {r["reasoning"][0]}, median {r["reasoning"][1]} characters')
        if stt:
            say(f'    API:{stt.get("calls_started")} calls, {stt.get("retries")} retries, {stt.get("rate_limited")} rate '
                f'limits, {s.get("dollars_this_session")} dollars in the last session, {s.get("wall_s_replays")} s of '
                f'replays; stopped by: {stt.get("stopped_by")}; reported model other than asked: '
                f'{s.get("reported_model_other_than_asked") or "none"}')

    if not args.no_write and not args.run:
        out = Path(args.root) / 'analyze_24.txt'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        print(f'(written to {out})', file=sys.stderr)


if __name__ == '__main__':
    main()
