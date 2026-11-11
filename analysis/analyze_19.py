"""Experiment 19 (BUILD, not registered): the two one-call contrasts on models served by a hosted API, one table.

Usage:
    py -I -X utf8 analysis/analyze_19.py [root] [--no-write] [--run <design>:<run_dir>:<model id> ...]

root (default analysis/results/19) holds <design>/<model id with / replaced by __>/forks/results.jsonl, as
analysis/store_19.py stores the rows of analysis/modal_g/forks_19_modal.py; --run adds a run directory by hand (the
stand-in test on the stored rows of 10 and 17). Without --no-write the output also goes to <root>/analyze_19.txt.

Scoring is imported from the registered analyses, not copied:
  design 10  analysis/analyze_d.py: score(...)['any_true'], "the next call touches an unopened true neighbor" (the
             outcome of pre-registrations 02 to 05 and of M2 of pre-registration 10), arms H (bare names, note) and
             E (addresses, note); the 95% bootstrap by state of analyze_forks.diff_ci (2,000 resamples, seed 0), by
             task beside it; the first-read counts of analysis/explore_first_reads.py (a read_file on an unopened
             listed neighbor's file, and how many of those ask past line 1), on every usable replay of the arm.
  design 17  analysis/analyze_15.py: score(...) for Y1 (reads a hit file past line 1) and the reads of a hit file;
             S minus S0 on Y1 on the states complete for S and S0, and S0N minus S on Y1 on the states complete for
             all three arms; C (past line 1 among the reads of a hit file) by arm.
A replay is usable if the frozen interface-failure rule (gates_c.failure) accepts it; failures are counted by kind,
and the failures that were the API's (no reply after the retries) are counted apart from the others. A state is
complete if every arm compared returned a usable call for every seed that the run used (the registered analyses ask
for seeds 1 to 3; the full run of design 10 uses seeds 1 and 2).

Rules, one verdict per model:
  V1  design 10: the 95% interval of E minus H on the outcome lies above zero.
  V2  design 17: the 95% interval of S minus S0 on Y1 lies above zero.
  A model enters a rule only if at least 80% of its replays in that design hold a valid tool call (usable).
The floors of complete states of the registered analyses (200 for 10, 25 for 17) are printed beside the count; they
are not part of V1 or V2.
"""
import argparse
import collections
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_15 as Q  # noqa: E402
import analyze_d as D  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from explore_first_reads import read_stats  # noqa: E402
from gates_c import FAILURES, failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import opens_listed_file  # noqa: E402

VALID_MIN = 0.80
FLOOR = {'10': 200, '17': 25}
FAMILY = (('Qwen/', 'Qwen (Alibaba)'), ('openai/gpt-oss', 'gpt-oss (OpenAI)'), ('deepseek-ai/', 'DeepSeek'),
          ('zai-org/', 'GLM (Z.ai)'), ('MiniMaxAI/', 'MiniMax'), ('nvidia/', 'Nemotron (NVIDIA)'),
          ('google/gemma', 'Gemma (Google)'))


def family(model):
    return next((f for pre, f in FAMILY if model.startswith(pre)), 'unknown')


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def verdict(valid, n, d):
    if not n:
        return 'no rows'
    if valid / n < VALID_MIN:
        return f'excluded (valid {100 * valid / n:.0f}% < {100 * VALID_MIN:.0f}%)'
    if d[0] is None:
        return 'no estimate'
    return 'met' if d[1] > 0 else 'not met'


def fail_counts(rows, kind_of):
    """Counter of interface-failure kinds, with the API's own failures as their own kind."""
    c = collections.Counter()
    for r in rows:
        k = kind_of(r)
        if k:
            ek = (r.get('api') or {}).get('error_kind') if k == 'error' else None
            c['api error' if ek == 'api' else 'error after a reply (adapter)' if ek == 'adapter' else k] += 1
    return c


def analyze_10(run_dir, states, arms=('H', 'E')):
    rows = [r for r in load_rows(Path(run_dir) / 'results.jsonl') if r['arm'] in arms]
    seeds = sorted({r['seed'] for r in rows})
    usable = collections.defaultdict(dict)
    for r in rows:
        if not failure(r):
            usable[skey(r)][(r['arm'], r['seed'])] = r
    need = {(a, s) for a in arms for s in seeds}
    complete = sorted(k for k, v in usable.items() if need <= set(v))
    T = {a: {k: [D.score(states[k], usable[k][(a, s)])['any_true'] for s in seeds] for k in complete} for a in arms}
    by_task = {a: Q.by_task(T[a]) for a in arms}
    first = {}
    for a in arms:
        reads = ranged = 0
        for r in rows:
            if r['arm'] == a and not failure(r) and opens_listed_file(states[skey(r)], r['next_call']):
                reads += 1
                ranged += read_stats(states[skey(r)], r['next_call'])[0]
        first[a] = (reads, ranged)
    return {'design': '10', 'n': len(rows), 'valid': sum(not failure(r) for r in rows), 'seeds': seeds,
            'fails': fail_counts(rows, failure), 'complete': len(complete), 'states': len(states),
            'shares': {a: boot_ci(T[a]) for a in ('H', 'E')}, 'raw': {a: (sum(map(sum, T[a].values())), len(complete) * len(seeds)) for a in arms},
            'diff': diff_ci(T['E'], T['H']), 'diff_task': diff_ci(by_task['E'], by_task['H']), 'first_reads': first}


def analyze_17(run_dir, recs):
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs}
    states = {Q.state_key(r): r for r in recs if r['arm'] == 'S'}
    rows = []
    usable = collections.defaultdict(dict)
    for row in load_rows(Path(run_dir) / 'results.jsonl'):
        if row.get('skip'):
            continue
        rec = by_fork.get((row.get('task'), row.get('run'), row.get('fork')))
        if rec is None or row.get('arm') != Q.RUNNER_ARM[rec['arm']]:
            continue
        rows.append(row)
        if not failure(row):
            usable[Q.state_key(rec)][(rec['arm'], row['seed'])] = row
    seeds = sorted({r['seed'] for r in rows})

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in seeds))

    def y1(keys, a):
        out, reads, past = {}, 0, 0
        for k in keys:
            sc = [Q.score(states[k], usable[k][(a, s)]['next_call']) for s in seeds]
            out[k] = [int(x['reads_hit_file'] and x['past_line_1']) for x in sc]
            reads += sum(x['reads_hit_file'] for x in sc)
            past += sum(x['reads_hit_file'] and x['past_line_1'] for x in sc)
        return out, reads, past

    pair, full = complete(('S', 'S0')), complete(Q.ARMS)
    t = {a: y1(pair, a) for a in ('S', 'S0')}
    tf = {a: y1(full, a) for a in Q.ARMS}
    return {'design': '17', 'n': len(rows), 'valid': sum(not failure(r) for r in rows), 'seeds': seeds,
            'fails': fail_counts(rows, failure), 'complete': len(pair), 'complete_all': len(full), 'states': len(states),
            'shares': {a: boot_ci(t[a][0]) for a in ('S', 'S0')},
            'reads': {a: (tf[a][1], tf[a][2]) for a in Q.ARMS},
            'diff': diff_ci(t['S'][0], t['S0'][0]), 'diff_task': diff_ci(Q.by_task(t['S'][0]), Q.by_task(t['S0'][0])),
            'diff_s0n_s': diff_ci(tf['S0N'][0], tf['S'][0]), 'share_s0n': boot_ci(tf['S0N'][0])}


def discover(root):
    out = []
    for design in ('10', '17'):
        for d in sorted((Path(root) / design).glob('*')) if (Path(root) / design).is_dir() else []:
            run = d / 'forks' if (d / 'forks' / 'results.jsonl').exists() else d
            if (run / 'results.jsonl').exists():
                model = d.name.replace('__', '/', 1)
                v = run / 'versions.json'
                if v.exists():
                    model = json.load(open(v, encoding='utf-8')).get('api_model', model)
                out.append((design, run, model))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default=str(HERE / 'results' / '19'))
    ap.add_argument('--run', action='append', default=[], help='<design>:<run_dir>:<model id>')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--states-10', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    ap.add_argument('--states-17', default=str(HERE / 'fork_states_s' / 'states.jsonl'))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    runs = discover(args.root)
    for spec in args.run:
        design, run_dir, model = spec.split(':', 2)
        runs.append((design, Path(run_dir), model))
    if not runs:
        raise SystemExit(f'no run found under {args.root} and no --run given')
    states10 = load_states(args.states_10) if any(d == '10' for d, _r, _m in runs) else None
    recs17 = [json.loads(l) for l in open(args.states_17, encoding='utf-8')] if any(d == '17' for d, _r, _m in runs) else None

    buf = io.StringIO()

    def say(*a):
        print(*a)
        print(*a, file=buf)

    say('EXPERIMENT 19 (BUILD, not registered): the one-call contrasts of 10 and 15/17 on models served by a hosted API')
    say(f'V1: design 10, E minus H on "next call touches an unopened true neighbor"; V2: design 17, S minus S0 on Y1. '
        f'A model enters a rule only with at least {100 * VALID_MIN:.0f}% valid replays. 95% bootstrap by state.')
    say()
    head = (f'{"model":38s} {"family":18s} {"des":>3s} {"replays":>7s} {"valid":>6s} {"arm 1":>7s} {"arm 2":>7s} '
            f'{"arm 2 minus arm 1 [95%]":>26s}  verdict')
    say(head)
    say('-' * len(head))
    res = []
    for design, run_dir, model in runs:
        r = analyze_10(run_dir, states10) if design == '10' else analyze_17(run_dir, recs17)
        res.append((model, r))
        a1, a2 = ('H', 'E') if design == '10' else ('S0', 'S')
        rule = 'V1' if design == '10' else 'V2'
        say(f'{model[:38]:38s} {family(model):18s} {design:>3s} {r["n"]:7d} {100 * r["valid"] / max(1, r["n"]):5.1f}% '
            f'{a1:>2s} {pct(r["shares"][a1]):>4s} {a2:>2s} {pct(r["shares"][a2]):>4s} {dpt(r["diff"]):>26s}  '
            f'{rule} {verdict(r["valid"], r["n"], r["diff"])}')
    say()
    say('Per run, details')
    for model, r in res:
        say(f'  {model}, design {r["design"]}: seeds {r["seeds"]}; complete states {r["complete"]} of {r["states"]} '
            f'(floor of the registered analysis {FLOOR[r["design"]]}: '
            f'{"above" if r["complete"] >= FLOOR[r["design"]] else "BELOW"})')
        fails = ', '.join(f'{k} {v}' for k, v in sorted(r['fails'].items())) or 'none'
        say(f'    interface failures (excluded): {fails}; of them the API\'s own (no reply after retries): '
            f'{r["fails"].get("api error", 0)}')
        say(f'    difference by task: {dpt(r["diff_task"])}')
        if r['design'] == '10':
            say(f'    raw counts on complete states: H {r["raw"]["H"][0]}/{r["raw"]["H"][1]}, E {r["raw"]["E"][0]}/{r["raw"]["E"][1]}')
            say('    first reads of an unopened listed neighbor\'s file, asking past line 1: '
                + '; '.join(f'{a} {k} of {n}' for a, (n, k) in r['first_reads'].items()))
        else:
            say(f'    states complete for S, S0 and S0N: {r["complete_all"]}; Y1 under S0N {pct(r["share_s0n"])}; '
                f'S0N minus S on Y1: {dpt(r["diff_s0n_s"])}')
            say('    reads of a hit file asking past line 1 (on the states complete for all three arms): '
                + '; '.join(f'{a} {p} of {n}' for a, (n, p) in r['reads'].items()))
    if not args.no_write:
        out = Path(args.root) / 'analyze_19.txt'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(buf.getvalue(), encoding='utf-8')
        print(f'\nwritten: {out}')


if __name__ == '__main__':
    main()
