"""Pre-registration 16: how the task prompt describes the graph tools, and the agent's first model call.

Usage: py -I -X utf8 analysis/analyze_16.py <run_dir> [--states analysis/fork_states_w/first_call_states.jsonl]
                                             [--gate] [--rows <out.jsonl>]

<run_dir> holds results_16.jsonl of the run (analysis/modal_g/forks_16_runner.py): one row per model call, the first
call of a fresh episode whose only inputs are the system prompt and one task prompt. Nothing executed. Arms, same
tasks and seeds (1 to 3):
  C    the task prompt the current evaluator builds, as built
  CS   that prompt with its four lines on the graph tools replaced by the lines of the September prompt
  S    the task prompt the recorded runs of September logged, as logged
  SC   that prompt with its four lines on the graph tools replaced by the lines of the current prompt
So C and SC carry the current wording of the four lines, CS and S the September wording; C and CS carry the rest of
the current prompt (its listing of the workspace's files), S and SC the rest of the September prompt.

The kind of a response:
  call       it holds at least one call, and the frozen failure rule accepts every call it holds (gates_c.failure: the
             tool is one of the harness's nine and fork_states.valid_call accepts the arguments);
  text       it holds no call and its text is not empty;
  malformed  it holds a call that the frozen rule rejects (an unknown tool, malformed arguments), or it holds neither
             a call nor a text;
  error      the replay ended in an error or without a response.
A response is usable if it is a call or a text. Malformed responses and errors are interface failures: counted by arm
and left out.

Outcome of a usable response, graph_first: it holds at least one call of get_code_neighbors, get_code_subgraph or
search_similar_code (a text scores 0). Also derived: the tools it calls; for each search_similar_code call whether the
query holds a blank (a phrase) or not (one symbol-like token); for its first call whether it is a graph tool, a
read_file, a run_command that searches (a piece of the command line, cut at | ; & ( ) ` and newlines, begins with
grep, egrep, fgrep, rg or find, with `git grep`, or with xargs followed by one of them), or something else.

Rules (share of replays with graph_first; 95% bootstrap interval over tasks, 2,000 resamples, seed 0:
analyze_forks.diff_ci):
  W1  CS minus C: met if the lower bound is above 0.
  W2  S minus SC: met if the lower bound is above 0.
  W3  the rest of the prompt, the wording held fixed: SC minus C, and S minus CS; for each, "more graph calls with
      the September listing" if the lower bound is above 0, "fewer" if the upper bound is below 0, "no detectable
      difference" if the interval includes 0.
A task is complete if every arm and seed returned a usable response. With fewer than 60 complete tasks every rule is
reported as underpowered. If a budget stop left S and SC incomplete (the runner's summary reports a budget stop, or
is absent, and a planned call of S or SC has no row), W1 is computed on the tasks complete for C and CS, and W2 and
W3 are reported as not run.
After the rules, descriptive and with no rule: by arm, the share of graph_first, the tool of the first call, phrases
against symbol-like queries among the search_similar_code calls, and what the first calls are.

A call that was run again after an error has two rows; the row without an error is read. --gate prints the counts of
usable responses by arm and the prompt sizes, and nothing about what the responses were (the smoke test; it reads
smoke_16.jsonl when the folder has no results_16.jsonl). --rows writes one line per call with what was derived from
it (no text of a response).
"""
import argparse
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import GRAPH_TOOLS, boot_ci, diff_ci  # noqa: E402
from gates_c import failure  # noqa: E402

ARMS = ('C', 'CS', 'S', 'SC')
FIRST_PAIR, SECOND_PAIR = ('C', 'CS'), ('S', 'SC')     # the order of the run
SEEDS = (1, 2, 3)
MIN_COMPLETE = 60
GATE_USABLE = 0.80
KINDS = ('call', 'text', 'malformed', 'error')
SEARCHERS = ('grep', 'egrep', 'fgrep', 'rg', 'find')
CUT = re.compile(r'[|;&\n()`]+')
FIRST_CALL = ('a graph tool', 'read_file', 'run_command, a search', 'something else')
LISTING = {'more': 'more graph calls with the September listing', 'fewer': 'fewer', 'none': 'no detectable difference'}


def runs_search(cmd):
    """True if a piece of the command line starts a search program."""
    for piece in CUT.split(str(cmd)):
        toks = piece.split()
        if not toks:
            continue
        if toks[0] in SEARCHERS or toks[:2] == ['git', 'grep']:
            return True
        if toks[0] == 'xargs' and next((t for t in toks[1:] if not t.startswith('-')), None) in SEARCHERS:
            return True
    return False


def derive(row):
    """What is read from one row: the kind of the response, graph_first, the tools, the query shapes, the first call."""
    out = {'kind': 'error', 'graph_first': 0, 'tools': [], 'queries': [], 'first_call': None, 'first_tool': None,
           'why': None}
    steps = row.get('steps') or []
    if row.get('error') or not steps:
        out['why'] = 'error' if row.get('error') else 'no response'
        return out
    first = steps[0]
    calls = [{'function_name': c.get('function_name'), 'arguments': c.get('arguments')} for c in first.get('calls') or []]
    if not calls:
        text = (first.get('text') or '').strip()
        out['kind'] = 'text' if text else 'malformed'
        out['why'] = None if text else 'neither a call nor a text'
        return out
    out['tools'] = [str(c['function_name']) for c in calls]
    bad = [k for k in (failure({'error': None, 'next_call': c}) for c in calls) if k]
    if bad:
        out['kind'], out['why'] = 'malformed', bad[0]
        return out
    out['kind'] = 'call'
    out['graph_first'] = int(any(t in GRAPH_TOOLS for t in out['tools']))
    out['queries'] = ['phrase' if re.search(r'\s', str(c['arguments'].get('query')).strip()) else 'symbol-like'
                      for c in calls if c['function_name'] == 'search_similar_code']
    name, args = calls[0]['function_name'], calls[0]['arguments']
    out['first_tool'] = name
    out['first_call'] = ('a graph tool' if name in GRAPH_TOOLS else 'read_file' if name == 'read_file'
                         else 'run_command, a search' if name == 'run_command' and runs_search(args.get('command'))
                         else 'something else')
    return out


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def share(k, n):
    return f'{k} of {n}' + (f' ({100 * k / n:.1f}%)' if n else '')


def spread(d):
    return f'median {st.median(d):+.0f} tokens, from {min(d):+d} to {max(d):+d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--states', default=str(HERE / 'fork_states_w' / 'first_call_states.jsonl'))
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--rows')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run_dir = Path(args.run_dir)
    res = run_dir / 'results_16.jsonl'
    if args.gate and not res.exists():
        res = run_dir / 'smoke_16.jsonl'
    raw = [json.loads(l) for l in open(res, encoding='utf-8') if l.strip()]

    logged = {}
    if Path(args.states).exists():
        recs = [json.loads(l) for l in open(args.states, encoding='utf-8')]
        tasks = sorted({r['task'] for r in recs})
        logged = {(r['task'], r['arm']): r.get('logged_first_prompt_tokens') for r in recs}
        where = f'{len(tasks)} tasks, {len(recs)} records in the states file'
    else:
        tasks = sorted({r['task'] for r in raw})
        where = f'{len(tasks)} tasks in the rows (the states file with the prompts is not on this machine)'
    seeds = tuple(sorted({r['seed'] for r in raw if r.get('seed') in SEEDS})) if args.gate else SEEDS
    if args.gate:
        tasks = sorted({r['task'] for r in raw if r['task'] in set(tasks)})   # the smoke test runs a few tasks, one seed
    planned = {(t, a, s) for t in tasks for a in ARMS for s in seeds}

    cells, stray, replaced = {}, 0, 0
    for r in raw:
        key = (r.get('task'), r.get('arm'), r.get('seed'))
        if key not in planned:
            stray += 1
            continue
        if key in cells:
            replaced += 1
            if r.get('error') and not cells[key].get('error'):
                continue                                   # a row without an error is not replaced by one with an error
        cells[key] = r
    got = {key: derive(r) for key, r in cells.items()}

    print('PRE-REGISTRATION 16: how the task prompt describes the graph tools, and the first model call (arms C, CS, S, SC)')
    print()
    print(f'  {where}; calls planned {len(planned)} (seeds {", ".join(map(str, seeds))}); rows read {len(raw)} '
          f'(rows that match no planned call: {stray}; rows of a call that has another row: {replaced})')
    n_rows = {a: sum(1 for key in cells if key[1] == a) for a in ARMS}
    n_plan = {a: sum(1 for key in planned if key[1] == a) for a in ARMS}
    ok = {a: sum(1 for key, d in got.items() if key[1] == a and d['kind'] in ('call', 'text')) for a in ARMS}
    for a in ARMS:
        fails = collections.Counter(d['why'] for key, d in got.items() if key[1] == a and d['kind'] in ('malformed', 'error'))
        print(f'  arm {a:<2} planned {n_plan[a]}, with a row {n_rows[a]}; interface failures {sum(fails.values())} '
              f'{dict(sorted(fails.items()))} (excluded); usable {share(ok[a], n_rows[a])}')

    # prompt sizes: the same prompt for the three seeds of a task and arm; C and S against the size their source logged
    size, uneven = {}, 0
    for (t, a, s), r in sorted(cells.items()):
        steps = r.get('steps') or []
        tok = steps[0].get('prompt_tokens') if steps else None
        if tok:
            uneven += size.setdefault(t, {}).setdefault(a, tok) != tok
    for a in ARMS:
        v = [size[t][a] for t in size if a in size[t]]
        if v:
            print(f'  prompt size, arm {a:<2} median {st.median(v):.0f} tokens, from {min(v)} to {max(v)} ({len(v)} tasks)')
    for a, what in (('C', 'the size the whole run logged for its first model call'), ('S', 'the size the September run logged')):
        d = [size[t][a] - logged[(t, a)] for t in size if a in size[t] and logged.get((t, a))]
        if d:
            print(f'  prompt size, arm {a} minus {what} ({len(d)} tasks): {spread(d)}')
    for a, b in (('CS', 'C'), ('SC', 'S')):
        d = [size[t][a] - size[t][b] for t in size if a in size[t] and b in size[t]]
        if d:
            print(f'  prompt size, arm {a} minus arm {b} ({len(d)} tasks): {spread(d)}')
    if uneven:
        print(f'  WARNING: {uneven} calls have a prompt size that differs from another seed of the same task and arm')
    if args.gate:
        den = dict(n_plan)                                 # the calls the smoke test planned, by arm
        if (run_dir / 'smoke_summary_16.json').exists():
            by_arm = json.load(open(run_dir / 'smoke_summary_16.json', encoding='utf-8')).get('by_arm') or {}
            den = {a: max(n_plan[a], (by_arm.get(a) or {}).get('planned') or 0) for a in ARMS}
        gate = all(den[a] and ok[a] / den[a] >= GATE_USABLE for a in ARMS)
        print('  usable responses of the calls planned, by arm: ' + ', '.join(f'{a} {share(ok[a], den[a])}' for a in ARMS))
        print(f'  smoke gate (at least {100 * GATE_USABLE:.0f}% usable responses in every arm): {"PASS" if gate else "FAIL"}')
        return

    # did a budget stop leave the second pair of arms incomplete?
    summary = None
    if (run_dir / 'summary_16.json').exists():
        summary = json.load(open(run_dir / 'summary_16.json', encoding='utf-8'))
        print(f'  the runner\'s summary: a budget stop occurred: {summary.get("budget_stop")}; calls not started '
              f'{summary.get("calls_not_started")}; no new call after {summary.get("time_budget_s")} s; the last call started at '
              f'{summary.get("last_call_started_s")} s')
        late = sum(1 for r in cells.values() if r.get('started_s') is not None and summary.get('time_budget_s')
                   and r['started_s'] > summary['time_budget_s'])
        print(f'  calls that started after the time budget: {late}')
    missing = {a: n_plan[a] - n_rows[a] for a in ARMS}
    stopped = sum(missing[a] for a in SECOND_PAIR) > 0 and (summary is None or bool(summary.get('budget_stop')))
    print(f'  planned calls without a row: ' + ', '.join(f'{a} {missing[a]}' for a in ARMS)
          + ('; a budget stop left S and SC incomplete: W1 on the tasks complete for C and CS, W2 and W3 not run' if stopped
             else '; S and SC were not cut short by a budget stop'))

    def complete(arms):
        return sorted(t for t in tasks if all(got.get((t, a, s), {}).get('kind') in ('call', 'text') for a in arms for s in SEEDS))

    full, pair = complete(ARMS), complete(FIRST_PAIR)
    print(f'  tasks complete on every arm (a usable response for seeds 1 to 3): {len(full)} of {len(tasks)}')
    print(f'  tasks complete for C and CS: {len(pair)} of {len(tasks)}')
    keys, arms = (pair, FIRST_PAIR) if stopped else (full, ARMS)
    weak = len(keys) < MIN_COMPLETE
    tab = {a: {t: [got[(t, a, s)]['graph_first'] for s in SEEDS] for t in keys} for a in arms}

    def raw_share(a):
        vals = [v for vs in tab[a].values() for v in vs]
        return f'{sum(vals)}/{len(vals)}'

    def verdict(d, words, run=True):
        if not run:
            return 'not run (a budget stop left S and SC incomplete)'
        if weak:
            return f'underpowered ({len(keys)} complete tasks, fewer than {MIN_COMPLETE})'
        return 'no estimate' if d[0] is None else words(d)

    def met(d):
        return 'met (the lower bound is above 0)' if d[1] > 0 else 'not met (the lower bound is not above 0)'

    def listing(d):
        return LISTING['more'] if d[1] > 0 else LISTING['fewer'] if d[2] < 0 else LISTING['none']

    def contrast(a, b):
        return diff_ci(tab[a], tab[b]) if a in tab and b in tab else (None, None, None)

    print()
    print(f'1. Rules, on the {len(keys)} tasks complete ' + ('for C and CS' if stopped else 'on every arm')
          + ' (share of replays with graph_first, percent; 95% bootstrap over tasks)')
    for a in arms:
        print(f'  arm {a:<2} graph_first: {pct(boot_ci(tab[a]))} | {raw_share(a)}')
    w1 = contrast('CS', 'C')
    print(f'  W1, CS minus C (the September wording, on the current prompt): {dpt(w1)}')
    print('  W1 verdict: ' + verdict(w1, met))
    w2 = contrast('S', 'SC')
    print(f'  W2, S minus SC (the September wording, on the September prompt): {dpt(w2)}')
    print('  W2 verdict: ' + verdict(w2, met, run=not stopped))
    w3a = contrast('SC', 'C')
    print(f'  W3, SC minus C (the September listing, under the current wording): {dpt(w3a)}')
    print('  W3 verdict, under the current wording: ' + verdict(w3a, listing, run=not stopped))
    w3b = contrast('S', 'CS')
    print(f'  W3, S minus CS (the September listing, under the September wording): {dpt(w3b)}')
    print('  W3 verdict, under the September wording: ' + verdict(w3b, listing, run=not stopped))

    print()
    print(f'2. Descriptive, no rule (the same {len(keys)} tasks)')
    per = {a: [got[(t, a, s)] for t in keys for s in SEEDS] for a in arms}
    for a in arms:
        print(f'  arm {a:<2} graph_first: {pct(boot_ci(tab[a]))} | {raw_share(a)}; responses with a call '
              f'{sum(d["kind"] == "call" for d in per[a])}, text answers {sum(d["kind"] == "text" for d in per[a])}, '
              f'responses with more than one call {sum(len(d["tools"]) > 1 for d in per[a])}')
    for a in arms:
        firsts = collections.Counter(d['first_tool'] or 'no call (a text answer)' for d in per[a])
        print(f'  arm {a:<2} the tool called first: ' + ', '.join(f'{k} {v}' for k, v in sorted(firsts.items(), key=lambda kv: (-kv[1], kv[0]))))
    for a in arms:
        q = collections.Counter(x for d in per[a] for x in d['queries'])
        print(f'  arm {a:<2} search_similar_code calls: {sum(q.values())}; the query is a phrase {q["phrase"]}, '
              f'one symbol-like token {q["symbol-like"]}')
    for a in arms:
        c = collections.Counter(d['first_call'] for d in per[a] if d['first_call'])
        n = sum(c.values())
        print(f'  arm {a:<2} first calls {n}: ' + ', '.join(f'{k} {share(c[k], n)}' for k in FIRST_CALL))

    if args.rows:
        with open(args.rows, 'w', encoding='utf-8', newline='\n') as f:
            for (t, a, s), d in sorted(got.items()):
                f.write(json.dumps({'task': t, 'arm': a, 'seed': s, 'kind': d['kind'], 'why_not_usable': d['why'],
                                    'graph_first': d['graph_first'] if d['kind'] in ('call', 'text') else None,
                                    'tools': d['tools'], 'search_queries': d['queries'], 'first_call': d['first_call'],
                                    'in_the_rules': t in keys and a in arms}) + '\n')
        print(f'\nwrote {len(got)} lines to {args.rows}')


if __name__ == '__main__':
    main()
