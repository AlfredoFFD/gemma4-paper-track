"""EXPLORATORY: replay fidelity. How often does an unaltered replay repeat what the recorded run did next at the same
paused step, and how often do two unaltered replays of the same step agree with each other (the ceiling)?

Usage: py -I -X utf8 analysis/explore_replay_fidelity.py > analysis/results/explore_replay_fidelity.txt
No arguments. Reads the stored replay rows and paused steps; reads the recorded traces under data/ as data only.

Written after all results were seen; nothing here was registered.

Populations
  B-A   experiment B (pre-registration 03), condition A (nothing added), run v5: the 388 steps complete in all ten
        arms of experiment B (v5, v6, v8), three seeds each, as in analyze_b.py / rederive_s5.py. Main population.
  F-A   experiment F (pre-registration 07), run w, arm A (nothing added, v28 rendering): states complete in all four
        arms of that run (A, Aw, Hw, Ew).
  F-Aw  the same run and states, arm Aw (nothing added; earlier tool results rendered as the original runs' harness
        rendered them).
  15-S  pre-registration 15, record S (the step as recorded) replayed under the runner's arm A: states with all three
        seeds usable. Experiment 20 reuses these rows as its arm ASKED (analyze_20.py), so it adds no new replays.

Definitions (each a judgment call, stated here)
  recorded next call: the first tool call of the agent step that follows the paused history in the recorded trace
        (fork_states.py stores it as observed_next_call). The replayed call is the first call of the replay
        (next_call). If either step made more than one call, only the first is compared; the counts are printed.
  usable replay: no error, a call, a known tool, arguments the harness could execute (fork_states.valid_call), as in
        analyze_b.py.
  level (a) same tool name.
  level (b) same tool and same kind: read_file of the same file (paths normalized as the harness does,
        fork_states.norm_path; start line ignored); edit_file / write_file of the same file; run_command: both
        a search (first word of the first non-cd stage is grep, rg, egrep, fgrep, ag, ack, or "git grep"), or
        otherwise the same first word; a graph tool or any other tool: the same tool name.
  level (c) same tool and the same arguments: every argument compared as a string with white space trimmed at both
        ends (so 151 and "151" agree), arguments with a null value dropped; nothing else normalized (./x vs x differ).
  bootstrap: 95% percentile, 2,000 resamples of steps with replacement, numpy default_rng(0); rates are over replays
        (or pairs of replays) pooled within the resampled steps.
"""
import collections
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from analyze_forks import GRAPH_TOOLS, KNOWN_TOOLS  # noqa: E402  registered tool sets
from fork_states import norm_path, touches, valid_call  # noqa: E402  registered scorer
import nodes as N  # noqa: E402  file contents for the registered scorer's character caps

ARMS_B = ['A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE']
SEEDS = (1, 2, 3)
NB = 2000
SEARCH = {'grep', 'rg', 'egrep', 'fgrep', 'ag', 'ack'}
VIEW = {'cat', 'head', 'tail', 'sed', 'less', 'more', 'nl', 'awk'}


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8')]


def usable(r):
    c = r.get('next_call')
    return not r.get('error') and bool(c) and c.get('function_name') in KNOWN_TOOLS and valid_call(c)


# ---------------------------------------------------------------- call kinds
def first_word(cmd):
    """First word of the first pipeline/list stage that is not a cd; ('git grep' counts as one word)."""
    for part in re.split(r'\|\|?|&&|;', cmd or ''):
        part = part.strip()
        if not part:
            continue
        try:
            toks = shlex.split(part)
        except ValueError:
            toks = part.split()
        if not toks or toks[0] == 'cd':
            continue
        if toks[0] == 'git' and len(toks) > 1 and toks[1] == 'grep':
            return 'git grep'
        return toks[0]
    return ''


def is_search(w):
    return w in SEARCH or w == 'git grep'


def kind_b(call):
    """The level-(b) kind of a call."""
    fn, a = call['function_name'], call.get('arguments') or {}
    if fn in ('read_file', 'edit_file', 'write_file'):
        return (fn, norm_path(a.get('filepath')))
    if fn == 'run_command':
        w = first_word(str(a.get('command', '')))
        return (fn, 'search' if is_search(w) else 'word:' + w)
    return (fn,)


def args_c(call):
    a = call.get('arguments') or {}
    return (call['function_name'], tuple(sorted((k, str(v).strip()) for k, v in a.items() if v is not None)))


def agree(x, y):
    """(a, b, c) agreement of two calls; a missing call agrees with nothing."""
    if not x or not y:
        return 0, 0, 0
    a = int(x['function_name'] == y['function_name'])
    b = int(a and kind_b(x) == kind_b(y))
    c = int(a and args_c(x) == args_c(y))
    return a, b, c


def coarse(call):
    """Kind for the distribution tables."""
    if not call:
        return 'no call'
    fn, a = call['function_name'], call.get('arguments') or {}
    if fn == 'read_file':
        return 'read_file, start line given' if a.get('start_line') is not None else 'read_file, no start line'
    if fn == 'run_command':
        w = first_word(str(a.get('command', '')))
        if is_search(w):
            return 'run_command, search (grep/rg/...)'
        if w in VIEW:
            return 'run_command, view (cat/head/tail/sed/...)'
        if w in ('find', 'ls', 'tree'):
            return 'run_command, list files (find/ls/tree)'
        if w in ('python', 'python3', 'pytest'):
            return 'run_command, python/pytest'
        return 'run_command, other'
    if fn in GRAPH_TOOLS:
        return 'graph tool: ' + fn
    return fn


def group(call):
    """Coarser group for the by-kind breakdown of agreement."""
    if not call:
        return 'no call'
    fn = call['function_name']
    if fn == 'run_command':
        return 'run_command, search' if is_search(first_word(str(call['arguments'].get('command', '')))) else 'run_command, other'
    if fn in ('edit_file', 'write_file'):
        return 'edit_file/write_file'
    if fn in GRAPH_TOOLS:
        return 'graph tool'
    return fn


# ---------------------------------------------------------------- bootstrap
def rate_ci(pairs):
    """pairs: (cluster, value). Pooled rate with a cluster bootstrap. Returns (rate%, lo%, hi%, n)."""
    S, C = collections.defaultdict(float), collections.defaultdict(int)
    for k, v in pairs:
        S[k] += v
        C[k] += 1
    cl = sorted(C)
    if not cl:
        return None
    s = np.array([S[k] for k in cl])
    n = np.array([C[k] for k in cl])
    idx = np.random.default_rng(0).integers(0, len(cl), size=(NB, len(cl)))
    b = np.sort(s[idx].sum(1) / n[idx].sum(1))
    return 100 * s.sum() / n.sum(), 100 * b[int(0.025 * NB)], 100 * b[int(0.975 * NB) - 1], int(n.sum())


def fr(t):
    return 'n/a' if t is None else f'{t[0]:6.2f}% [{t[1]:6.2f}, {t[2]:6.2f}] (n={t[3]})'


# ---------------------------------------------------------------- the analysis of one population
def fidelity(label, reps, recorded):
    """reps: step key -> {seed: row} (three usable seeds); recorded: step key -> recorded first call or None."""
    keys = sorted(reps)
    lv = {'a': [], 'b': [], 'c': []}
    pr = {'a': [], 'b': [], 'c': []}
    any_b = []
    by_group = collections.defaultdict(lambda: {'a': [], 'b': []})
    for k in keys:
        rec = recorded.get(k)
        calls = [reps[k][sd]['next_call'] for sd in SEEDS]
        hits_b = 0
        for c in calls:
            a, b, cc = agree(rec, c)
            lv['a'].append((k, a)); lv['b'].append((k, b)); lv['c'].append((k, cc))
            by_group[group(rec)]['a'].append((k, a)); by_group[group(rec)]['b'].append((k, b))
            hits_b += b
        any_b.append((k, int(hits_b > 0)))
        for i in range(3):
            for j in range(i + 1, 3):
                a, b, cc = agree(calls[i], calls[j])
                pr['a'].append((k, a)); pr['b'].append((k, b)); pr['c'].append((k, cc))
    print(f'{label}: {len(keys)} steps, {3 * len(keys)} replays, {3 * len(keys)} pairs of replays')
    print('  2. Replay vs the recorded next call (rate over replays)')
    print(f'     (a) same tool                     {fr(rate_ci(lv["a"]))}')
    print(f'     (b) same tool and kind            {fr(rate_ci(lv["b"]))}')
    print(f'     (c) same tool and arguments       {fr(rate_ci(lv["c"]))}')
    print(f'     steps where >= 1 of 3 replays agrees at (b): {fr(rate_ci(any_b))}')
    print('  3. Ceiling: two replays of the same step (rate over the 3 pairs per step)')
    print(f'     (a) same tool                     {fr(rate_ci(pr["a"]))}')
    print(f'     (b) same tool and kind            {fr(rate_ci(pr["b"]))}')
    print(f'     (c) same tool and arguments       {fr(rate_ci(pr["c"]))}')
    print('  Replay vs recorded, by the kind of the recorded call (steps; (a) and (b) over replays)')
    for g in sorted(by_group, key=lambda g: -len(by_group[g]['a'])):
        n = len(by_group[g]['a']) // 3
        pa = 100 * sum(v for _, v in by_group[g]['a']) / len(by_group[g]['a'])
        pb = 100 * sum(v for _, v in by_group[g]['b']) / len(by_group[g]['b'])
        print(f'     {g:<26} {n:4d} steps  (a) {pa:5.1f}%  (b) {pb:5.1f}%')
    return lv, pr


def complete_by_arm(rows, arms, key_of=lambda r: (r['task'], r['run'], r.get('fork', 0))):
    """step key -> arm -> seed -> usable row; only steps with every (arm, seed) usable are kept."""
    d = collections.defaultdict(lambda: collections.defaultdict(dict))
    for r in rows:
        if r.get('arm') in arms and r.get('seed') in SEEDS and usable(r):
            d[key_of(r)][r['arm']][r['seed']] = r
    return {k: v for k, v in d.items() if all(len(v[a]) == len(SEEDS) for a in arms)}


def main():
    print('EXPLORATORY, written after all results were seen; nothing here was registered.')
    print('Replay fidelity: unaltered replays of a paused step vs what the recorded run did next, and vs each other.')
    print(f'Bootstrap: 95% percentile, {NB} resamples of steps, numpy default_rng(0).')
    print()

    # ------------------------------------------------------------ 0. gate
    states = {}
    for l in open(HERE / 'fork_states' / 'states.jsonl', encoding='utf-8'):
        s = json.loads(l)
        s.pop('steps', None)
        states[(s['task'], s['run'], s.get('fork', 0))] = s
    rows_b = []
    for v in ('v5', 'v6', 'v8'):
        rows_b += load_jsonl(HERE / 'results' / v / 'forks' / 'results.jsonl')
    comp = {k: v for k, v in complete_by_arm(rows_b, ARMS_B).items() if k in states}
    reps_a = {k: v['A'] for k, v in comp.items()}
    hits = []
    for k, d in reps_a.items():
        s = states[k]
        sp = s['neighbor_spans']
        for sd in SEEDS:
            c = d[sd]['next_call']
            h = False
            for n in s['unshown_true_neighbors']:
                if not sp.get(n):
                    continue
                src = N.file_text(s['task'], sp[n]['path'])
                t = touches(c, sp[n], n, line_lengths=[len(x) for x in src.splitlines()] if src else None)
                h = h or (bool(t) and t != 'graph')
            hits.append(int(h))
    rate = 100 * sum(hits) / len(hits)
    ok = len(reps_a) == 388 and len(hits) == 1164 and round(rate, 2) == 2.15
    print('0. Gate: experiment B, condition A (run v5), complete steps across the ten arms of B, registered scorer')
    print(f'   steps {len(reps_a)} (expected 388); replays {len(hits)} (expected 1164); '
          f'reads a neighbor\'s code {sum(hits)} = {rate:.2f}% (expected 2.15%)')
    print('   ' + ('reproduced' if ok else f'NOT reproduced: steps {len(reps_a) - 388:+d}, replays {len(hits) - 1164:+d}, '
                                         f'rate {rate - 2.15:+.2f} points'))
    print()

    # ------------------------------------------------------------ 1. recorded next call
    recorded = {k: states[k].get('observed_next_call') for k in reps_a}
    n_par, n_mismatch, n_trace = 0, 0, 0
    dates = []
    cache = {}
    for k in reps_a:
        s = states[k]
        p = ROOT / s['trace'].replace('\\', '/')
        if p not in cache:
            cache[p] = json.load(open(p, encoding='utf-8')) if p.exists() else None
        d = cache[p]
        oc = recorded[k]
        if oc and (oc.get('extra') or {}).get('timestamp'):
            dates.append(datetime.fromtimestamp(oc['extra']['timestamp'], tz=timezone.utc).date())
        if d is None:
            continue
        n_trace += 1
        agent = [x for x in d['steps'] if x['source'] == 'agent']
        nxt = agent[s['fork_agent_step'] + 1]
        tcs = nxt.get('tool_calls') or []
        n_par += len(tcs) > 1
        first = tcs[0] if tcs else None
        if (first or {}).get('function_name') != (oc or {}).get('function_name') or \
                (first or {}).get('arguments') != (oc or {}).get('arguments'):
            n_mismatch += 1
    n_none = sum(1 for v in recorded.values() if not v)
    n_inval = sum(1 for k, v in recorded.items() if v and not states[k].get('observed_next_call_valid'))
    rep_multi = sum(1 for d in reps_a.values() for sd in SEEDS if len(d[sd].get('all_calls') or []) > 1)
    print('1. The recorded next call at the 388 steps (first tool call of the next recorded agent step)')
    print(f'   recorded traces opened: {n_trace} of {len(reps_a)} steps; stored observed_next_call differs from the '
          f'trace\'s first call: {n_mismatch}')
    print(f'   recorded next step with no tool call: {n_none}; recorded call malformed (valid_call false): {n_inval}; '
          f'recorded next step with more than one call: {n_par}; replays (of 1164) with more than one call: {rep_multi}')
    if dates:
        print(f'   recorded calls dated {min(dates)} to {max(dates)} (UTC, from the trace timestamps)')
    rc = collections.Counter(coarse(recorded[k]) for k in reps_a)
    pc = collections.Counter(coarse(d[sd]['next_call']) for d in reps_a.values() for sd in SEEDS)
    print(f'   {"kind":<44} {"recorded (steps)":>17} {"replays":>16}')
    for kd in sorted(set(rc) | set(pc), key=lambda x: (-rc[x], -pc[x], x)):
        print(f'   {kd:<44} {rc[kd]:5d} {100 * rc[kd] / len(reps_a):6.1f}%   {pc[kd]:5d} {100 * pc[kd] / (3 * len(reps_a)):6.1f}%')
    shell_words = collections.Counter(first_word(str(recorded[k]['arguments'].get('command', '')))
                                      for k in reps_a if recorded[k] and recorded[k]['function_name'] == 'run_command')
    print(f'   first word of the recorded shell commands: {dict(shell_words.most_common())}')
    std = {'filepath', 'start_line', 'end_line'}
    odd_r = sum(1 for k in reps_a if recorded[k] and recorded[k]['function_name'] == 'read_file'
                and set(recorded[k]['arguments']) - std)
    odd_p = sum(1 for d in reps_a.values() for sd in SEEDS if d[sd]['next_call']['function_name'] == 'read_file'
                and set(d[sd]['next_call']['arguments']) - std)
    print(f'   read_file calls with an argument name other than filepath, start_line, end_line (a mangled bound name '
          f'counts as "no start line" above): recorded {odd_r}, replays {odd_p}')
    print()

    # ------------------------------------------------------------ 2, 3 for B-A
    print('2-3. Agreement')
    fidelity('B-A (experiment B, condition A, run v5)', reps_a, recorded)
    print()

    # ------------------------------------------------------------ other unaltered conditions
    print('Other unaltered conditions, same definitions')
    rows_w = load_jsonl(HERE / 'results' / 'w' / 'forks' / 'results.jsonl')
    states_d = {}
    for l in open(HERE / 'fork_states_d' / 'states.jsonl', encoding='utf-8'):
        s = json.loads(l)
        states_d[(s['task'], s['run'], s.get('fork', 0))] = s.get('observed_next_call')
    comp_w = complete_by_arm(rows_w, ('A', 'Aw', 'Hw', 'Ew'))
    same_rec = sum(1 for k in comp_w if states_d.get(k) == states[k]['observed_next_call']) if all(k in states for k in comp_w) else 'n/a'
    print(f'  (experiment F states: fork_states_d; recorded next call identical to fork_states at {same_rec} of {len(comp_w)} steps)')
    fidelity('F-A (experiment F, arm A, v28 rendering)', {k: v['A'] for k, v in comp_w.items()}, states_d)
    fidelity('F-Aw (experiment F, arm Aw, the original runs\' rendering)', {k: v['Aw'] for k, v in comp_w.items()}, states_d)
    both = sorted(set(comp_w) & set(reps_a))
    if both:
        x = [(k, int(reps_a[k][sd]['next_call']['function_name'] == comp_w[k]['A'][sd]['next_call']['function_name']))
             for k in both for sd in SEEDS]
        y = [(k, int(kind_b(reps_a[k][sd]['next_call']) == kind_b(comp_w[k]['A'][sd]['next_call']))) for k in both for sd in SEEDS]
        print(f'  B-A seed s vs F-A seed s (two runs of the same unaltered replay, {len(both)} steps in both): '
              f'(a) {fr(rate_ci(x))}; (b) {fr(rate_ci(y))}')

    recs15 = load_jsonl(HERE / 'fork_states_s' / 'states.jsonl')
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs15}
    rows15 = []
    for r in load_jsonl(HERE / 'results' / '15' / 'forks' / 'results.jsonl'):
        rec = by_fork.get((r.get('task'), r.get('run'), r.get('fork')))
        if rec and rec['arm'] == 'S' and r.get('arm') == 'A':
            rows15.append(dict(r, arm='S'))
    comp15 = complete_by_arm(rows15, ('S',))
    rec15 = {(r['task'], r['run'], r['fork']): r.get('observed_next_call') for r in recs15 if r['arm'] == 'S'}
    print(f'  (pre-registration 15: {sum(1 for r in recs15 if r["arm"] == "S")} records S; {len(rows15)} rows of them)')
    fidelity('15-S (pre-registration 15, record S under arm A)', {k: v['S'] for k, v in comp15.items()}, rec15)
    print()

    # ------------------------------------------------------------ 4. harness releases
    print('4. Harness releases')
    log = HERE / 'results' / 'v5' / 'gemma-graph-forks-pilot.log'
    line = next((l for l in open(log, encoding='utf-8') if 'installing harness variant' in l), None)
    m = re.search(r'installing harness variant (\w+): (\[[^\]]*\])', line or '')
    print(f'  condition A of experiment B (run v5) installed: {m.group(1) + " " + m.group(2) if m else "not found in the run log"}')
    print('  (harness v28 = the wheels dated Sep 30: adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7; '
          'docs/replay-tool.md, NOTES.md)')
    print(f'  the recorded runs: the GraphLoc end-to-end notebooks, recorded calls dated {min(dates)} to {max(dates)}; '
          'they predate the harness change of Sep 30 (analysis/results/public/README.md),')
    print('  so the replay harness is not the recording harness. Known differences (NOTES.md): earlier tool results '
          'are rendered as dictionaries in v28 and as {"result": "<string>"} in the original runs')
    print('  (experiment F, arm Aw, restores the original rendering: see F-Aw above); replays do not re-send the '
          'recorded thoughts (versions.json: thoughts_in_history false).')
    vs = json.load(open(HERE / 'results' / 'g_onestep' / 'forks' / 'versions.json', encoding='utf-8'))
    arms_g = sorted({r['arm'] for r in load_jsonl(HERE / 'results' / 'g_onestep' / 'forks' / 'results.jsonl')})
    print(f'  pre-registration 08, rule S1 (run g_onestep, harness variant {vs.get("harness_variant")}, the wheels of '
          f'Oct 12): arms stored {arms_g}; no unaltered condition was run, so item 2 cannot be computed for it.')


if __name__ == '__main__':
    main()
