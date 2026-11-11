"""Pre-registration 15: the agent's own search, with and without its line numbers (arms S, S0, S0N).

Usage: py -I -X utf8 analysis/analyze_15.py <run_dir> [--states analysis/fork_states_s/states.jsonl] [--gate]

<run_dir> holds results.jsonl of the run: one row per replay, written by the one-step runner. The states file
(analysis/make_states_s.py) has one record per (state, arm), each with its own history; a row belongs to the record
with its task, run and fork. The runner replays records S and S0 under its arm A (nothing added) and record S0N
under its arm S0N (the note). A row that carries `skip` is a cell entered as finished before the run so that the
runner leaves it out; it is not a replay and is not read.

The last result of a state is the output of the agent's own search. Its hit files are the repository files with a
hit line in that output that the agent had not opened. For the next call of a replay:
  reads_hit_file  the call reads a hit file: a `read_file` on it, or a `run_command` whose pipeline starts from cat,
                  head, tail or sed -n on it and shows a known range of lines (fork_states.shell_view_range);
  past_line_1     that read asks to start past line 1: `start_line` above 1; for a shell view, a first line above 1.
                  A `read_file` whose start line stands under a mangled argument name (the name is start_line once
                  quotes, backslashes and blanks are removed) counts as asking, as the model wrote it, and is
                  counted apart as well;
  on_a_hit        the lines asked for include a hit line of that file; for `read_file`, the lines from the start to
                  the end asked for, at most 150 lines (the harness returns no more), 150 lines when no end is asked;
  searches_again  the call is a `run_command` that runs a search program; whether it asks for line numbers.
Estimands: Y1, the share of replays with reads_hit_file and past_line_1; Y2, the share with reads_hit_file; C, among
replays with reads_hit_file, the share with past_line_1.

Rules (95% bootstrap interval by state, 2,000 resamples, seed 0: analyze_forks.diff_ci; by task beside it):
  Q1  Y1 under S minus Y1 under S0: met if the lower bound is above 0.
  Q2  under S0, at most 5% of the reads of a hit file ask past line 1; at least 20 such reads, otherwise not testable.
  Q3  Y1 under S0N minus Y1 under S0: met if the lower bound is above 0. And C under S0N minus C under S: "used less
      often than in the agent's own result" if the upper bound is below 0, "no detectable difference" if the interval
      includes 0, "used more often" if the lower bound is above 0. And the ratio R = (Y1 under S0N minus Y1 under S0) /
      (Y1 under S minus Y1 under S0): "the note carries the line number about as well as the agent's own result" if R
      is at least two thirds (point estimate); its interval is reported (the same resamples by state; a resample whose
      denominator is zero or negative is counted and left out of the interval).
A replay is usable if it is not an interface failure (the frozen rule, gates_c.failure: runner error, no call, unknown
tool, malformed arguments); failures are counted by arm and left out. A state is complete for a rule if every arm the
rule compares returned a usable call for seeds 1 to 3 (Q1 and Q2: S and S0; Q3: S, S0 and S0N). A rule with fewer
than 40 complete states is reported as underpowered.

--gate prints the counts of usable calls by arm and the prompt-size check of arm S, and nothing about what the calls
were (the smoke test).
"""
import argparse
import collections
import json
import random
import re
import shlex
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import public_runs_address as P  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from fork_states import VIEW_CMDS, norm_path, shell_view_range  # noqa: E402
from gates_c import failure, load_rows  # noqa: E402
from make_states_s import asks_line_numbers, repo_path, search_segments  # noqa: E402
from mangled_sensitivity import intended  # noqa: E402

ARMS = ('S', 'S0', 'S0N')
RUNNER_ARM = {'S': 'A', 'S0': 'A', 'S0N': 'S0N'}       # the runner's arm for each record
SEEDS = (1, 2, 3)
MIN_COMPLETE, MIN_READS, Q2_MAX, WINDOW = 40, 20, 0.05, 150
R_MIN = 2 / 3                                          # Q3: the ratio at which the note counts as carrying the line number
GATE_USABLE, GATE_PROMPT = 0.80, 0.02
VIEWERS = ('cat', 'head', 'tail', 'sed')               # shell commands that count as reading a file
SANDBOX_DIR = re.compile(r'/tmp/swegemma_sandbox_[^/\s]+/workspace/')
NO_NAME = '\x00'                                       # no command holds it: a grep stage then never counts as a view


def state_key(rec):
    return (rec['task'], rec['run'], rec['fork_agent_step'])


def bounds_asked(call):
    """(start, end, start under a mangled name) of a read_file call, as the model wrote them."""
    fixed = intended(call)['arguments']                 # mangled bound names restored; a well-formed name wins

    def num(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return num(fixed.get('start_line')), num(fixed.get('end_line')), \
        'start_line' not in call['arguments'] and 'start_line' in fixed


def shell_view(cmd, path, file_lines):
    """(first line, last line or None for the end of the file) that a shell command shows of `path`, or None.

    The pipeline must start from cat, head, tail or sed on the file; the lines are those that
    fork_states.shell_view_range works out, so a later grep or any other filter makes it no view.
    """
    cmd = SANDBOX_DIR.sub('', cmd)                      # paths under the sandbox's working directory, as repository paths
    for stage in (s.strip() for s in cmd.split('|')):
        try:
            toks = shlex.split(stage)
        except ValueError:
            toks = stage.split()
        if toks and toks[0] in VIEW_CMDS and any(norm_path(t) == path for t in toks[1:]):
            if toks[0] not in VIEWERS:
                return None
            view = shell_view_range(cmd, path, NO_NAME, file_lines)
            return (view[1], view[2]) if view and view[0] == 'lines' else None
    return None


def score(rec, call):
    """What a usable next call does with the hit files of the state's last result."""
    name, args = call['function_name'], call['arguments']
    hits = rec['hit_files']
    out = {'reads_hit_file': False, 'past_line_1': False, 'mangled_start': False, 'on_a_hit': False, 'far': None,
           'searches_again': False, 'with_numbers': False, 'tool': name}
    if name == 'read_file':
        f = repo_path(args.get('filepath'))
        if f in hits:
            start, end, mangled = bounds_asked(call)
            lo, hi = P.window(start if start is not None else 1, end)
            past = start is not None and start > 1
            out.update(reads_hit_file=True, past_line_1=past, mangled_start=bool(mangled and past),
                       on_a_hit=any(lo <= h <= hi for h in hits[f]), far=min(hits[f]) > WINDOW, tool='read_file, a hit file')
        else:
            out['tool'] = 'read_file, another file'
    elif name == 'run_command':
        cmd = str(args.get('command', ''))
        for f in hits:
            view = shell_view(cmd, f, rec['file_lines'].get(f))
            if view:
                a, b = view
                out.update(reads_hit_file=True, past_line_1=a > 1, far=min(hits[f]) > WINDOW,
                           on_a_hit=any(a <= h and (b is None or h <= b) for h in hits[f]),
                           tool='run_command, a view of a hit file')
                break
        if search_segments(cmd):
            out.update(searches_again=True, with_numbers=asks_line_numbers(cmd))
        if not out['reads_hit_file']:
            out['tool'] = 'run_command, a search' if out['searches_again'] else 'run_command, another command'
    return out


def ratio_ci(num_a, num_b, den_a, den_b, n=2000, seed=0):
    """(point, low, high, resamples left out) of (mean(num_a) - mean(num_b)) / (mean(den_a) - mean(den_b)).

    The tables are {state: [0/1 per replay]}. States are resampled as analyze_forks.diff_ci resamples them (the same
    generator, seed and order of states), so the resamples are those of the differences on the same states. A resample
    whose denominator is zero or negative is counted and left out of the interval; the point estimate is None when
    the denominator of the data itself is zero or negative.
    """
    clusters = sorted(set(num_a) | set(num_b) | set(den_a) | set(den_b))
    if not clusters:
        return None, None, None, 0

    def m(d, cl):
        vals = [v for c in cl for v in d.get(c, [])]
        return st.mean(vals) if vals else 0.0

    den = m(den_a, clusters) - m(den_b, clusters)
    point = (m(num_a, clusters) - m(num_b, clusters)) / den if den > 0 else None
    rng = random.Random(seed)
    boots, left_out = [], 0
    for _ in range(n):
        sample = [rng.choice(clusters) for _ in clusters]
        d = m(den_a, sample) - m(den_b, sample)
        if d <= 0:
            left_out += 1
            continue
        boots.append((m(num_a, sample) - m(num_b, sample)) / d)
    boots.sort()
    if not boots:
        return point, None, None, left_out
    return point, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1], left_out


def rat(t):
    point = 'no estimate (the denominator is zero or negative)' if t[0] is None else f'{t[0]:.2f}'
    return point + (' [n/a]' if t[1] is None else f' [{t[1]:.2f}, {t[2]:.2f}]')


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def span(t):
    return 'n/a' if t[0] is None else f'[{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def share(k, n):
    return f'{k} of {n}' + (f' ({100 * k / n:.1f}%)' if n else '')


def by_task(table):
    out = collections.defaultdict(list)
    for key, vals in table.items():
        out[key[0]] += vals
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--states', default=str(HERE / 'fork_states_s' / 'states.jsonl'))
    ap.add_argument('--gate', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    recs = [json.loads(l) for l in open(args.states, encoding='utf-8')]
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs}
    states = {state_key(r): r for r in recs if r['arm'] == 'S'}   # the scored fields are the same in a state's three records

    n, fail = collections.Counter(), collections.Counter()
    usable = collections.defaultdict(dict)                         # state -> (arm, seed) -> row
    skipped = stray = 0
    for row in load_rows(Path(args.run_dir) / 'results.jsonl'):
        if row.get('skip'):
            skipped += 1
            continue
        rec = by_fork.get((row.get('task'), row.get('run'), row.get('fork')))
        if rec is None or row.get('arm') != RUNNER_ARM[rec['arm']] or row.get('seed') not in SEEDS:
            stray += 1
            continue
        n[rec['arm']] += 1
        kind = failure(row)
        if kind:
            fail[(rec['arm'], kind)] += 1
        else:
            usable[state_key(rec)][(rec['arm'], row['seed'])] = row

    print('PRE-REGISTRATION 15: the agent\'s own search, with and without its line numbers (arms S, S0, S0N)')
    print()
    print(f'  {len(states)} states, {len(recs)} records; rows of replays read: {sum(n.values())} (cells entered as finished '
          f'beforehand and not run: {skipped}; rows that match no record: {stray})')
    ok = {a: sum(1 for d in usable.values() for (arm, _s) in d if arm == a) for a in ARMS}
    for a in ARMS:
        kinds = {k: v for (arm, k), v in sorted(fail.items()) if arm == a}
        print(f'  arm {a:<4} {n[a]} rows; interface failures {sum(kinds.values())} {kinds} (excluded); usable '
              + share(ok[a], n[a]))

    # prompt size: arm S is the recorded history, so its prompt is compared with the size logged for the same step
    size = {a: {} for a in ARMS}
    for key, d in usable.items():
        for (arm, _seed), row in sorted(d.items()):
            got = (row.get('usage') or {}).get('prompt_tokens')
            if got:
                size[arm].setdefault(key, got)
    diffs = [size['S'][k] - states[k]['prompt_tokens_next_call_logged'] for k in size['S']]
    rel = [abs(size['S'][k] - states[k]['prompt_tokens_next_call_logged']) / states[k]['prompt_tokens_next_call_logged']
           for k in size['S']]
    if diffs:
        print(f'  prompt size, arm S against the size logged for the same step ({len(diffs)} states): median difference '
              f'{st.median(diffs):+.0f} tokens (replayed minus logged), median absolute relative difference '
              f'{100 * st.median(rel):.2f}%, largest {100 * max(rel):.2f}%: '
              f'{"within" if st.median(rel) <= GATE_PROMPT else "above"} the {100 * GATE_PROMPT:.0f}% that the fidelity gate '
              f'of the other runs allowed')
    else:
        print('  prompt size, arm S: no usable row with a prompt size')
    for a, b in (('S0', 'S'), ('S0N', 'S0')):
        d = [size[a][k] - size[b][k] for k in size[a] if k in size[b]]
        if d:
            print(f'  prompt size, {a} minus {b} ({len(d)} states): median {st.median(d):+.0f} tokens, from {min(d):+d} to {max(d):+d}')
    if args.gate:
        gate = all(n[a] and ok[a] / n[a] >= GATE_USABLE for a in ARMS)
        print(f'  smoke gate (at least {100 * GATE_USABLE:.0f}% usable calls in every arm): {"PASS" if gate else "FAIL"}')
        return

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    pair, full = complete(('S', 'S0')), complete(ARMS)
    print(f'  states complete for Q1 and Q2 (S and S0 usable for seeds 1 to 3): {len(pair)} of {len(states)}')
    print(f'  states complete for Q3 (S, S0 and S0N usable for seeds 1 to 3): {len(full)} of {len(states)}')

    def tables(keys, arms):
        """Per arm: Y1 and Y2 as {state: [0/1 per replay]}, C as {state: [0/1 per read of a hit file]}, and tallies."""
        t = {a: {'y1': {}, 'y2': {}, 'c': {}, 'n': collections.Counter(), 'tool': collections.Counter()} for a in arms}
        for k in keys:
            for a in arms:
                scores = [score(states[k], usable[k][(a, s)]['next_call']) for s in SEEDS]
                d = t[a]
                d['y1'][k] = [int(x['reads_hit_file'] and x['past_line_1']) for x in scores]
                d['y2'][k] = [int(x['reads_hit_file']) for x in scores]
                reads = [x for x in scores if x['reads_hit_file']]
                if reads:
                    d['c'][k] = [int(x['past_line_1']) for x in reads]
                for x in scores:
                    c = d['n']
                    c['replays'] += 1
                    c['reads'] += x['reads_hit_file']
                    c['past'] += x['reads_hit_file'] and x['past_line_1']
                    c['mangled'] += x['mangled_start']
                    c['on_a_hit'] += x['on_a_hit']
                    c['search'] += x['searches_again']
                    c['search_n'] += x['with_numbers']
                    if x['reads_hit_file']:
                        where = 'far' if x['far'] else 'near'
                        c[where] += 1
                        c[where + '_past'] += x['past_line_1']
                    d['tool'][x['tool']] += 1
        return t

    tp, tf = tables(pair, ('S', 'S0')), tables(full, ARMS)
    blocks = [] if pair == full else [(f'the {len(pair)} states complete for Q1 and Q2', tp, ('S', 'S0'))]
    blocks.append((f'the {len(full)} states complete for ' + ('every rule' if pair == full else 'Q3'), tf, ARMS))

    print()
    print('1. Rules (95% bootstrap by state; by task beside it)')
    weak_pair = len(pair) < MIN_COMPLETE
    weak_full = len(full) < MIN_COMPLETE

    def low(k):
        return f'underpowered ({k} complete states, fewer than {MIN_COMPLETE})'

    d1 = diff_ci(tp['S']['y1'], tp['S0']['y1'])
    d1t = diff_ci(by_task(tp['S']['y1']), by_task(tp['S0']['y1']))
    print(f'  Q1, Y1 under S minus Y1 under S0: {dpt(d1)}; by task {span(d1t)}')
    print('  Q1 verdict: ' + (low(len(pair)) if weak_pair else 'no estimate' if d1[0] is None
                              else 'met (the lower bound is above 0)' if d1[1] > 0
                              else 'not met (the lower bound is not above 0)'))
    c0 = tp['S0']['n']
    print(f'  Q2, under S0, reads of a hit file that ask past line 1: {share(c0["past"], c0["reads"])}')
    print('  Q2 verdict: ' + (low(len(pair)) if weak_pair
                              else f'not testable (fewer than {MIN_READS} reads of a hit file under S0)' if c0['reads'] < MIN_READS
                              else f'met (at most {100 * Q2_MAX:.0f}%)' if c0['past'] / c0['reads'] <= Q2_MAX
                              else f'not met (more than {100 * Q2_MAX:.0f}%)'))
    d3 = diff_ci(tf['S0N']['y1'], tf['S0']['y1'])
    d3t = diff_ci(by_task(tf['S0N']['y1']), by_task(tf['S0']['y1']))
    print(f'  Q3, Y1 under S0N minus Y1 under S0: {dpt(d3)}; by task {span(d3t)}')
    print('  Q3 verdict, first part: ' + (low(len(full)) if weak_full else 'no estimate' if d3[0] is None
                                          else 'met (the lower bound is above 0)' if d3[1] > 0
                                          else 'not met (the lower bound is not above 0)'))
    d4 = diff_ci(tf['S0N']['c'], tf['S']['c'])
    d4t = diff_ci(by_task(tf['S0N']['c']), by_task(tf['S']['c']))
    cn, cs = tf['S0N']['n'], tf['S']['n']
    print(f'  Q3, C under S0N minus C under S (past line 1 among reads of a hit file: S0N {share(cn["past"], cn["reads"])}, '
          f'S {share(cs["past"], cs["reads"])}): {dpt(d4)}; by task {span(d4t)}')
    print('  Q3 verdict, second part: ' + (low(len(full)) if weak_full else 'no estimate' if d4[0] is None
                                           else 'used less often than in the agent\'s own result' if d4[2] < 0
                                           else 'used more often' if d4[1] > 0 else 'no detectable difference'))
    r = ratio_ci(tf['S0N']['y1'], tf['S0']['y1'], tf['S']['y1'], tf['S0']['y1'])
    rt = ratio_ci(by_task(tf['S0N']['y1']), by_task(tf['S0']['y1']), by_task(tf['S']['y1']), by_task(tf['S0']['y1']))
    print(f'  Q3, R = (Y1 under S0N minus Y1 under S0) / (Y1 under S minus Y1 under S0): {rat(r)}; resamples left out '
          f'because the denominator was zero or negative: {r[3]} of 2000; by task '
          + ('[n/a]' if rt[1] is None else f'[{rt[1]:.2f}, {rt[2]:.2f}]') + f', left out {rt[3]}')
    print('  Q3 verdict, the ratio: ' + (low(len(full)) if weak_full else 'no estimate' if r[0] is None
                                         else 'the note carries the line number about as well as the agent\'s own result '
                                              '(R is at least two thirds)' if r[0] >= R_MIN
                                         else 'R is below two thirds: the note is not shown to carry the line number about '
                                              'as well as the agent\'s own result'))

    print()
    print('2. Rates (percent of replays, 95% interval by state | replays counted)')
    for label, t, arms in blocks:
        print(f'  on {label}')
        for a in arms:
            c = t[a]['n']
            print(f'    arm {a:<4} Y1, reads a hit file past line 1: {pct(boot_ci(t[a]["y1"]))} | {c["past"]}/{c["replays"]}; '
                  f'Y2, reads a hit file: {pct(boot_ci(t[a]["y2"]))} | {c["reads"]}/{c["replays"]}; '
                  f'C, past line 1 among those reads: {share(c["past"], c["reads"])}')

    print()
    print('3. Descriptive, no rule')
    for label, t, arms in blocks:
        print(f'  on {label}')
        for a in arms:
            c = t[a]['n']
            print(f'    arm {a:<4} on_a_hit, reads of a hit file whose lines include a hit of that file: '
                  f'{share(c["on_a_hit"], c["reads"])}')
        for a in arms:
            c = t[a]['n']
            print(f'    arm {a:<4} searches_again: {share(c["search"], c["replays"])} of the replays; asking for line numbers '
                  f'{c["search_n"]}')
        for a in arms:
            tools = ', '.join(f'{k} {v}' for k, v in sorted(t[a]['tool'].items(), key=lambda kv: (-kv[1], kv[0])))
            print(f'    arm {a:<4} the next tool: {tools}')
        for a in arms:
            c = t[a]['n']
            print(f'    arm {a:<4} Y1 by the nearest hit of the file read: past line {WINDOW}, {c["far_past"]} of {c["far"]} reads '
                  f'ask past line 1; within the first {WINDOW} lines, {c["near_past"]} of {c["near"]}; '
                  f'of {c["replays"]} replays')
        for a in arms:
            c = t[a]['n']
            print(f'    arm {a:<4} reads counted as asking past line 1 whose start line stands under a mangled argument '
                  f'name: {c["mangled"]} of {c["past"]}')


if __name__ == '__main__':
    main()
