"""Experiment 20 ("asked or told"): the same search hits, asked for by the agent or handed to it (arms NONE, TOLD,
TOLDX and ASKED, all replayed in one launch; the stored rows of arm S of pre-registration 15 printed beside ASKED).

Usage: py -I -X utf8 analysis/analyze_20.py [<run_dir>] [--states analysis/fork_states_t/states.jsonl]
                                            [--asked analysis/results/15/forks] [--no-write] [--gate] [--standin]
<run_dir> (default analysis/results/20/forks) holds results.jsonl of the run: one row per replay, written by the
one-step runner. The states file (analysis/make_states_t.py) has one record per (state, arm); a row belongs to the
record with its task, run and fork. The runner replays records NONE and ASKED under its arm A (nothing added) and
records TOLD and TOLDX under the arms of the same names (the note). A row that carries `skip` is a cell entered as
finished before the run; it is not a replay and is not read. ASKED is the history of arm S of pre-registration 15,
replayed in this launch. For description only, the stored rows of 15's arm S (record `<step>:S` in
<asked>/results.jsonl, the runner's arm A; a state of 15 is the same state here: task, run, step) are read as ASKED15.

Outcomes of a replay (the next call), with the definitions of pre-registration 15 (analyze_15.score, unchanged):
  USES THE LINE  the call is a first read of a file named in the note (for NONE and ASKED: a file of the state's own
                 search result) that asks past line 1: `reads_hit_file` and `past_line_1` of 15, scored on the
                 record's `hit_files` (for TOLDX: the files of its own note); a start line under a mangled argument
                 name counts as written, as in 15;
  SEARCHES       the call is a search (`searches_again` of 15: a run_command that runs a search program).
Rules (95% bootstrap interval by state, 2,000 resamples, seed 0: analyze_forks.diff_ci; by task beside it), each on
the states complete in the arms it compares (every arm usable for seeds 1 to 3):
  T1  told lines are used: USES THE LINE under TOLD minus under NONE; met if the lower bound is above 0.
  T2  asked against told: the ratio TOLD / ASKED on USES THE LINE (analyze_15.ratio_ci: the same resamples by state,
      a resample whose denominator is zero or negative counted and left out); "used about as often" if the point
      estimate is at least two thirds, otherwise "telling does not replace asking".
  T3  wanted against unwanted: USES THE LINE under TOLD minus under TOLDX; met if the lower bound is above 0. Also
      printed, without a rule, on the states whose TOLDX comes from the same run (source a) and from another run of
      the task (source b), each alone.
  T4  telling saves the search: SEARCHES under TOLD minus under NONE; met if the upper bound is below 0.
  Floors: T1, T2 and T4 need at least 40 complete states, T3 at least 20; below the floor the numbers are printed and
  no verdict.
A replay is usable if it is not an interface failure (gates_c.failure: runner error, no call, unknown tool, malformed
arguments); failures are counted by arm and left out.

Also printed, no rule: what the next call does under each arm (a noted file read past line 1, a noted file read from
line 1, a search, an edit, something else), interface failures apart, by repository; under TOLD and NONE, of the
replays whose next call is a search, how many repeat the recorded search (the search call the state of 15 ends with):
the same command once quotes are removed and blanks collapsed, and, looser, the same search pattern with any other
arguments; ASKED of this launch against the stored rows of 15's arm S (how well a re-run reproduces them).

--no-write prints the report only; otherwise it is written to analysis/results/20/analyze_20.txt as well.
--gate prints the counts of usable calls by arm and the prompt sizes, and nothing about what the calls were.
--standin runs the whole analysis on the stored rows of pre-registration 15 in place of a run of 20 (S0N as TOLD, S0
as NONE and as TOLDX, S as ASKED and as ASKED15; the records of 20 for the files scored), to prove the script before data exist. It
never writes the report file.
"""
import argparse
import collections
import json
import re
import shlex
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_15 import by_task, dpt, pct, rat, ratio_ci, score, share, span  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from gates_c import failure, load_rows  # noqa: E402
from make_states_s import CUT, SEARCH_PROGRAMS  # noqa: E402

ROOT = HERE.parent
ARMS = ('NONE', 'TOLD', 'TOLDX', 'ASKED')
ALL_ARMS = ARMS + ('ASKED15',)                   # ASKED15: the stored rows of 15's arm S
RUNNER_ARM = {'NONE': 'A', 'TOLD': 'TOLD', 'TOLDX': 'TOLDX', 'ASKED': 'A'}
SEEDS = (1, 2, 3)
FLOOR = {'T1': 40, 'T2': 40, 'T3': 20, 'T4': 40}
R_MIN = 2 / 3
GATE_USABLE = 0.80
OUT = HERE / 'results' / '20' / 'analyze_20.txt'
EDITS = ('edit_file', 'write_file', 'submit_patch')
VALUE_OPTS = {'-f', '-A', '-B', '-C', '-m', '-d', '-D', '-g', '-t', '-T', '--include', '--exclude', '--exclude-dir',
              '--glob', '--type', '--type-not', '--max-count', '--context', '--after-context', '--before-context',
              '--file', '--max-depth', '--color', '--colour'}
QUOTES = re.compile(r'[\'"]')


def state_key(rec):
    return (rec['task'], rec['run'], rec['fork_agent_step'])


# ---------------------------------------------------------------- the recorded search, repeated or not

def _segments(cmd):
    """The pieces of a command line, each as its words (quotes honored), cut at | ; & ( ) and newlines."""
    try:
        lex = shlex.shlex(str(cmd), posix=True, punctuation_chars='|;&()')
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return [seg.split() for seg in CUT.split(str(cmd))]
    out, cur = [], []
    for t in toks:
        if t and set(t) <= set('|;&()'):
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    out.append(cur)
    return [s for s in out if s]


def search_pattern(cmd):
    """The search pattern of the first search piece of a command line (grep, rg, ... as make_states_s counts them),
    quotes removed and blanks around it stripped; None if there is none."""
    for toks in _segments(cmd):
        if toks[0] == 'git' and len(toks) > 1 and toks[1] == 'grep':
            args = toks[2:]
        elif toks[0] == 'xargs':
            rest = [t for t in toks[1:] if not t.startswith('-')]
            if not rest or rest[0] not in SEARCH_PROGRAMS:
                continue
            args = toks[toks.index(rest[0]) + 1:]
        elif toks[0] in SEARCH_PROGRAMS:
            args = toks[1:]
        else:
            continue
        it = iter(args)
        for t in it:
            if t == '--':
                nxt = next(it, None)
                return None if nxt is None else nxt.strip()
            if t in ('-e', '--regexp'):
                nxt = next(it, None)
                return None if nxt is None else nxt.strip()
            if t.startswith('--regexp='):
                return t.split('=', 1)[1].strip()
            if t.startswith('-') and len(t) > 1:
                if t in VALUE_OPTS:
                    next(it, None)
                continue
            return t.strip()
    return None


def same_command(a, b):
    def norm(c):
        return ' '.join(QUOTES.sub('', str(c)).split())
    return norm(a) == norm(b)


def repeat_kind(rec, call):
    """'same search', 'same pattern, other arguments' or None, for a next call that is a run_command search."""
    rcmd = rec['own_search_call']['arguments'].get('command', '')
    cmd = call['arguments'].get('command', '')
    if same_command(cmd, rcmd):
        return 'same search'
    p, rp = search_pattern(cmd), search_pattern(rcmd)
    if p is not None and p == rp:
        return 'same pattern, other arguments'
    return None


def category(x, call):
    if x['reads_hit_file']:
        return 'reads a noted file past line 1' if x['past_line_1'] else 'reads a noted file from line 1'
    if x['searches_again']:
        return 'a search'
    if call['function_name'] in EDITS:
        return 'an edit'
    return 'something else'


# ---------------------------------------------------------------- rows

def load_cells(args, recs):
    """[(state key, arm, seed, row)] of every replay read, and the counts of rows not read."""
    by_fork = {(r['task'], r['run'], r['fork']): r for r in recs}
    cells, skipped, stray = [], 0, 0
    asked_rows = load_rows(Path(args.asked) / 'results.jsonl')
    if args.standin:                             # every arm from the rows of 15
        keys = {state_key(r) for r in recs}
        want = {'S': ('ASKED', 'ASKED15'), 'S0': ('NONE', 'TOLDX'), 'S0N': ('TOLD',)}
        for row in asked_rows:
            step, arm15 = str(row.get('fork')).split(':')
            k = (row['task'], row['run'], int(step))
            if row.get('skip') or k not in keys or row.get('seed') not in SEEDS \
                    or row.get('arm') != ('S0N' if arm15 == 'S0N' else 'A'):
                stray += 1
                continue
            cells += [(k, a, row['seed'], row) for a in want[arm15]]
        return cells, skipped, stray
    for row in load_rows(Path(args.run_dir) / 'results.jsonl'):
        if row.get('skip'):
            skipped += 1
            continue
        rec = by_fork.get((row.get('task'), row.get('run'), row.get('fork')))
        if rec is None or row.get('arm') != RUNNER_ARM[rec['arm']] or row.get('seed') not in SEEDS:
            stray += 1
            continue
        cells.append((state_key(rec), rec['arm'], row['seed'], row))
    keys = {state_key(r) for r in recs}
    for row in asked_rows:                       # ASKED15: record <step>:S of 15 under the runner's arm A
        step, arm15 = str(row.get('fork')).split(':')
        k = (row['task'], row['run'], int(step))
        if arm15 == 'S' and row.get('arm') == 'A' and not row.get('skip') and k in keys and row.get('seed') in SEEDS:
            cells.append((k, 'ASKED15', row['seed'], row))
    return cells, skipped, stray


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir', nargs='?', default=str(HERE / 'results' / '20' / 'forks'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_t' / 'states.jsonl'))
    ap.add_argument('--asked', default=str(HERE / 'results' / '15' / 'forks'))
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--gate', action='store_true')
    ap.add_argument('--standin', action='store_true')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    lines = []

    def out(s=''):
        lines.append(s)
        print(s)

    recs = [json.loads(l) for l in open(args.states, encoding='utf-8')]
    rec_of = {(state_key(r), r['arm']): r for r in recs}
    rec_of.update({(state_key(r), 'ASKED15'): r for r in recs if r['arm'] == 'ASKED'})   # scored as ASKED
    states = sorted({state_key(r) for r in recs})
    repo = {state_key(r): r['repo'] for r in recs}
    has_x = {k for k in states if (k, 'TOLDX') in rec_of}

    cells, skipped, stray = load_cells(args, recs)
    n, fail = collections.Counter(), collections.Counter()
    usable = collections.defaultdict(dict)
    for k, arm, seed, row in cells:
        if arm == 'TOLDX' and k not in has_x:    # the stand-in only: S0 rows of a state without a TOLDX record
            continue
        n[arm] += 1
        kind = failure(row)
        if kind:
            fail[(arm, kind)] += 1
        else:
            usable[k][(arm, seed)] = row

    out('EXPERIMENT 20: the same search hits, asked for by the agent or handed to it (arms NONE, TOLD, TOLDX, ASKED; '
        'ASKED15, the stored rows of arm S of pre-registration 15, for description)')
    if args.standin:
        out('  STAND-IN: every row below is a row of pre-registration 15 (S0N as TOLD, S0 as NONE and TOLDX, S as '
            'ASKED and as ASKED15); the numbers prove the script, they are not results of experiment 20')
    out()
    out(f'  {len(states)} states, {len(recs)} records ({len(has_x)} states with a TOLDX record); rows of replays read: '
        f'{sum(n.values())} (cells entered as finished beforehand and not run: {skipped}; rows that match no record: '
        f'{stray})')
    ok = {a: sum(1 for d in usable.values() for (arm, _s) in d if arm == a) for a in ALL_ARMS}
    for a in ALL_ARMS:
        kinds = {kk: v for (arm, kk), v in sorted(fail.items()) if arm == a}
        out(f'  arm {a:<5} {n[a]} rows; interface failures {sum(kinds.values())} {kinds} (excluded); usable '
            + share(ok[a], n[a]))

    size = {a: {} for a in ALL_ARMS}
    for k, d in usable.items():
        for (arm, _seed), row in sorted(d.items()):
            got = (row.get('usage') or {}).get('prompt_tokens')
            if got:
                size[arm].setdefault(k, got)
    for arm, what in (('NONE', 'the search call'), ('ASKED', 'the call after the search')):
        logged = {state_key(r): r['prompt_tokens_next_call_logged'] for r in recs if r['arm'] == arm}
        if size[arm]:
            diffs = [size[arm][k] - logged[k] for k in size[arm]]
            rel = [abs(x) / logged[k] for x, k in zip(diffs, size[arm])]
            out(f'  prompt size, arm {arm} against the size logged for {what}, the call it replays ({len(diffs)} states): '
                f'median difference {st.median(diffs):+.0f} tokens, median absolute relative difference '
                f'{100 * st.median(rel):.2f}%, largest {100 * max(rel):.2f}%')
    for a, b in (('TOLD', 'NONE'), ('TOLDX', 'NONE'), ('ASKED', 'NONE'), ('ASKED', 'ASKED15')):
        d = [size[a][k] - size[b][k] for k in size[a] if k in size[b]]
        if d:
            out(f'  prompt size, {a} minus {b} ({len(d)} states): median {st.median(d):+.0f} tokens, from {min(d):+d} '
                f'to {max(d):+d}')
    if args.gate:
        gate = all(n[a] and ok[a] / n[a] >= GATE_USABLE for a in ARMS)
        out(f'  smoke gate (at least {100 * GATE_USABLE:.0f}% usable calls in NONE, TOLD, TOLDX and ASKED): '
            f'{"PASS" if gate else "FAIL"}')
        return

    def complete(arms):
        return sorted(k for k in states if all((a, s) in usable.get(k, {}) for a in arms for s in SEEDS))

    def scores(k, a):
        return [score(rec_of[(k, a)], usable[k][(a, s)]['next_call']) for s in SEEDS]

    def table(keys, a, what):
        if what == 'uses':
            return {k: [int(x['reads_hit_file'] and x['past_line_1']) for x in scores(k, a)] for k in keys}
        return {k: [int(x['searches_again']) for x in scores(k, a)] for k in keys}

    comp = {'T1': complete(('TOLD', 'NONE')), 'T2': complete(('TOLD', 'ASKED')), 'T3': complete(('TOLD', 'TOLDX')),
            'T4': complete(('TOLD', 'NONE'))}
    out()
    out('1. Rules (95% bootstrap by state; by task beside it)')
    for t, arms in (('T1', 'TOLD and NONE'), ('T2', 'TOLD and ASKED'), ('T3', 'TOLD and TOLDX'), ('T4', 'TOLD and NONE')):
        out(f'  states complete for {t} ({arms} usable for seeds 1 to 3): {len(comp[t])} of '
            f'{len(has_x) if t == "T3" else len(states)} (floor {FLOOR[t]})')

    def verdict(t, text):
        if len(comp[t]) < FLOOR[t]:
            return f'no verdict: below the floor ({len(comp[t])} complete states, fewer than {FLOOR[t]})'
        return text

    k1 = comp['T1']
    d1 = diff_ci(table(k1, 'TOLD', 'uses'), table(k1, 'NONE', 'uses'))
    d1t = diff_ci(by_task(table(k1, 'TOLD', 'uses')), by_task(table(k1, 'NONE', 'uses')))
    out(f'  T1, USES THE LINE under TOLD minus under NONE: {dpt(d1)}; by task {span(d1t)}')
    out('  T1 verdict: ' + verdict('T1', 'no estimate' if d1[0] is None else
                                   'met: told lines are used (the lower bound is above 0)' if d1[1] > 0
                                   else 'not met (the lower bound is not above 0)'))
    k2 = comp['T2']
    r = ratio_ci(table(k2, 'TOLD', 'uses'), {}, table(k2, 'ASKED', 'uses'), {})
    rt = ratio_ci(by_task(table(k2, 'TOLD', 'uses')), {}, by_task(table(k2, 'ASKED', 'uses')), {})
    out(f'  T2, the ratio TOLD / ASKED on USES THE LINE: {rat(r)}; resamples left out because the denominator was zero '
        f'or negative: {r[3]} of 2000; by task ' + ('[n/a]' if rt[1] is None else f'[{rt[1]:.2f}, {rt[2]:.2f}]')
        + f', left out {rt[3]}')
    out('  T2 verdict: ' + verdict('T2', 'no estimate' if r[0] is None else
                                   'used about as often (the ratio is at least two thirds)' if r[0] >= R_MIN
                                   else 'telling does not replace asking (the ratio is below two thirds)'))
    k3 = comp['T3']
    d3 = diff_ci(table(k3, 'TOLD', 'uses'), table(k3, 'TOLDX', 'uses'))
    d3t = diff_ci(by_task(table(k3, 'TOLD', 'uses')), by_task(table(k3, 'TOLDX', 'uses')))
    out(f'  T3, USES THE LINE under TOLD minus under TOLDX (TOLDX scored on the files of its own note): {dpt(d3)}; '
        f'by task {span(d3t)}')
    out('  T3 verdict: ' + verdict('T3', 'no estimate' if d3[0] is None else
                                   'met: wanted lines are used more than unwanted ones (the lower bound is above 0)'
                                   if d3[1] > 0 else 'not met (the lower bound is not above 0)'))
    for src, label in (('same run', 'source a, the same run'), ('other run', 'source b, another run of the task')):
        ks = [k for k in k3 if rec_of[(k, 'TOLDX')]['toldx_source'] == src]
        dd = diff_ci(table(ks, 'TOLD', 'uses'), table(ks, 'TOLDX', 'uses'))
        out(f'  T3 on the {len(ks)} complete states whose TOLDX comes from {label}, printed without a rule: {dpt(dd)}')
    k4 = comp['T4']
    d4 = diff_ci(table(k4, 'TOLD', 'search'), table(k4, 'NONE', 'search'))
    d4t = diff_ci(by_task(table(k4, 'TOLD', 'search')), by_task(table(k4, 'NONE', 'search')))
    out(f'  T4, SEARCHES under TOLD minus under NONE: {dpt(d4)}; by task {span(d4t)}')
    out('  T4 verdict: ' + verdict('T4', 'no estimate' if d4[0] is None else
                                   'met: telling saves the search (the upper bound is below 0)' if d4[2] < 0
                                   else 'not met (the upper bound is not below 0)'))

    out()
    out('2. Rates (percent of replays, 95% interval by state | replays counted), each arm on its states complete in it')
    for a in ALL_ARMS:
        keys = complete((a,))
        u, s_ = table(keys, a, 'uses'), table(keys, a, 'search')
        out(f'  arm {a:<5} {len(keys)} states; USES THE LINE {pct(boot_ci(u))} | {sum(map(sum, u.values()))}/'
            f'{3 * len(keys)}; SEARCHES {pct(boot_ci(s_))} | {sum(map(sum, s_.values()))}/{3 * len(keys)}')
    kr = complete(('TOLD', 'NONE', 'ASKED'))
    rr = ratio_ci(table(kr, 'TOLD', 'uses'), table(kr, 'NONE', 'uses'), table(kr, 'ASKED', 'uses'), table(kr, 'NONE', 'uses'))
    out(f'  printed, no rule: (TOLD minus NONE) / (ASKED minus NONE) on USES THE LINE, the form of 15\'s ratio, on the '
        f'{len(kr)} states complete in the three arms: {rat(rr)}; left out {rr[3]} of 2000')
    ka = complete(('ASKED', 'ASKED15'))
    for what, name in (('uses', 'USES THE LINE'), ('search', 'SEARCHES')):
        dd = diff_ci(table(ka, 'ASKED', what), table(ka, 'ASKED15', what))
        out(f'  printed, no rule: a re-run of 15\'s arm S, {name} under ASKED (this launch) minus under the stored rows of '
            f'15 (ASKED15), on the {len(ka)} states complete in both: {dpt(dd)}')
    same = sum(score(rec_of[(k, 'ASKED')], usable[k][('ASKED', s)]['next_call'])['reads_hit_file'] ==
               score(rec_of[(k, 'ASKED15')], usable[k][('ASKED15', s)]['next_call'])['reads_hit_file'] for k in ka for s in SEEDS)
    out(f'  printed, no rule: ASKED and ASKED15 agree on whether the next call reads a hit file in {share(same, 3 * len(ka))} '
        f'(state, seed) pairs; the same tool and arguments in '
        + share(sum(usable[k][('ASKED', s)]['next_call'] == usable[k][('ASKED15', s)]['next_call'] for k in ka for s in SEEDS),
                3 * len(ka)))

    out()
    out('3. Descriptive, no rule')
    out('  the next call, by arm (usable replays; interface failures apart), all states and then by repository:')
    for label, keep in [('all', lambda k: True)] + [(rp, (lambda rp: lambda k: repo[k] == rp)(rp))
                                                   for rp in sorted(set(repo.values()))]:
        out(f'  {label}:')
        for a in ALL_ARMS:
            c = collections.Counter()
            for k, d in usable.items():
                if not keep(k):
                    continue
                for (arm, _s), row in d.items():
                    if arm == a:
                        c[category(score(rec_of[(k, a)], row['next_call']), row['next_call'])] += 1
            nf = sum(v for (arm, _kind), v in fail.items() if arm == a) if label == 'all' else \
                sum(1 for k, arm, _s, row in cells if arm == a and keep(k) and failure(row)
                    and (arm != 'TOLDX' or k in has_x))
            tot = sum(c.values())
            parts = ', '.join(f'{name} {share(c[name], tot)}' for name in (
                'reads a noted file past line 1', 'reads a noted file from line 1', 'a search', 'an edit',
                'something else'))
            out(f'    arm {a:<5} {parts}; interface failures {nf}')
    out('  repeats of the recorded search (the search call the state of 15 ends with):')
    for a in ('TOLD', 'NONE'):
        c, nsearch = collections.Counter(), 0
        for k, d in usable.items():
            for (arm, _s), row in d.items():
                if arm != a:
                    continue
                x = score(rec_of[(k, a)], row['next_call'])
                if x['searches_again']:
                    nsearch += 1
                    c[repeat_kind(rec_of[(k, a)], row['next_call'])] += 1
        out(f'    arm {a:<5} of the {nsearch} replays whose next call is a search, {c["same search"]} repeat the recorded '
            f'search (the same command, quotes removed and blanks collapsed); {c["same search"] + c["same pattern, other arguments"]} '
            f'have the same search pattern with any other arguments')

    if not args.no_write and not args.standin:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        print(f'(written to {OUT.relative_to(ROOT).as_posix()})')


if __name__ == '__main__':
    main()
