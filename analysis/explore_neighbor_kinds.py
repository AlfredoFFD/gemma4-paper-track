"""What the neighbor lists at the paused steps are made of: class members, callees, callers (EXPLORATORY)

Usage: py -I -X utf8 analysis/explore_neighbor_kinds.py

Nothing here was pre-registered and no model is run. The graph files label every edge `calls`, store it in both
directions and also link a class to its members (Kaggle discussion 745731). At each paused step of the one-step
replays the agent is shown the neighbors of an entity it has just read, as `get_code_neighbors` prints them. This
script reads the state files (analysis/fork_states/*.json) and the task snapshots and says, entry by entry, what
kind of neighbor it is, with the rules of analysis/public_runs_missed_links.py:
  ENTRY         a neighbor in the list of the bare-names condition (arm P), which is the list the tool prints.
  CONTAINMENT   the entry and the entity lie in one file with the span of one inside the span of the other (a class
                and one of its members).
  NAMES         an entity names another if the last component of the other's dotted name stands, as a whole
                identifier, in the source lines of its span.
  CALLEE        not CONTAINMENT, and the entity just read NAMES the entry (its name stands in the code just read).
  CALLER        not CONTAINMENT, and the entry NAMES the entity just read.
  UNOPENED      the entry's file had not been opened by the run at the paused step (the state's
                `unshown_true_neighbors`). Only such entries can count for the outcome "reads a neighbor's code".
  TEST CODE     the entry's dotted name starts with `tests.` or `test.`, has a `.tests.` part, or ends in `test_*`.

Part 3 takes the replays of pre-registrations 02 and 03 (analysis/results/v5, v6 and v8), with the rows, the
exclusions and the outcome of analysis/analyze_b.py (imported functions, same states kept), and splits the registered
outcome "reads a neighbor's code" by the kind of the neighbor read. The split is post hoc: the kinds were defined
after the results were known. Differences are paired by paused step, as in the registered analysis.
"""
import collections
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402

STATES = HERE / 'fork_states'
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
KINDS = ('CONTAINMENT', 'CALLER only', 'CALLEE only', 'CALLER and CALLEE', 'neither named', 'no span')
_words = {}


def short(nid):
    return nid.rsplit('.', 1)[-1]


def is_test(nid):
    return nid.split('.')[0] in ('tests', 'test') or '.tests.' in nid or short(nid).startswith('test_')


def words_of(task, sp):
    key = (task, sp['path'], sp['start'], sp['end'])
    if key not in _words:
        text = N.file_text(task, sp['path']) or ''
        _words[key] = set(IDENT.findall('\n'.join(text.split('\n')[sp['start'] - 1:sp['end']])))
    return _words[key]


def contains(a, b):
    return a['path'] == b['path'] and (a['start'], a['end']) != (b['start'], b['end']) and (
        (a['start'] <= b['start'] and b['end'] <= a['end']) or (b['start'] <= a['start'] and a['end'] <= b['end']))


def kind_of(task, node, node_span, entry, span):
    if not span or span.get('end') is None or not node_span or node_span.get('end') is None:
        return 'no span'
    if contains(node_span, span):
        return 'CONTAINMENT'
    callee = short(entry) in words_of(task, node_span)
    caller = short(node) in words_of(task, span)
    return 'CALLER and CALLEE' if caller and callee else 'CALLER only' if caller else 'CALLEE only' if callee else 'neither named'


def pct(k, n):
    return f'{k} of {n} ({100 * k / n:.1f}%)' if n else f'{k} of {n}'


def main():
    rows, states = [], []
    for p in sorted(STATES.glob('*.json')):
        st = json.load(open(p, encoding='utf-8'))
        entries = st['arms']['P']['response']['neighbors']
        unopened = set(st['unshown_true_neighbors'])
        kinds = collections.Counter()
        for n in entries:
            k = kind_of(st['task'], st['node'], st['node_span'], n, st['neighbor_spans'].get(n))
            rows.append({'task': st['task'], 'kind': k, 'unopened': n in unopened, 'test': is_test(n)})
            kinds[k] += 1
            kinds[k + ', unopened'] += n in unopened
        states.append({'task': st['task'], 'n': len(entries), 'unopened': sum(1 for n in entries if n in unopened), 'kinds': kinds,
                       'same': set(entries) == set(st['true_neighbors'])})

    print('WHAT THE NEIGHBOR LISTS AT THE PAUSED STEPS ARE MADE OF (EXPLORATORY)')
    print()
    print('0. Paused steps and entries')
    ns = sorted(s['n'] for s in states)
    us = sorted(s['unopened'] for s in states)
    print(f'   paused steps {len(states)} in {len({s["task"] for s in states})} tasks; the printed list equals the state\'s true neighbors in '
          f'{sum(s["same"] for s in states)}; ENTRIES {len(rows)}, per step median {statistics.median(ns):.0f} (quartiles {ns[len(ns) // 4]} to {ns[(3 * len(ns)) // 4]})')
    print(f'   UNOPENED entries {sum(r["unopened"] for r in rows)}, per step median {statistics.median(us):.0f} '
          f'(quartiles {us[len(us) // 4]} to {us[(3 * len(us)) // 4]}); steps with none {sum(1 for s in states if not s["unopened"])}')
    print()
    print('1. Entries by kind')
    un = [r for r in rows if r['unopened']]
    op = [r for r in rows if not r['unopened']]
    for label, sel in (('all entries', rows), ('entries in files the run had opened', op), ('UNOPENED entries', un)):
        print(f'   {label}: {len(sel)}')
        for k in KINDS:
            ks = [r for r in sel if r['kind'] == k]
            if ks:
                print(f'      {k}: {pct(len(ks), len(sel))}; in TEST CODE {pct(sum(r["test"] for r in ks), len(ks))}')
        print(f'      in TEST CODE, any kind: {pct(sum(r["test"] for r in sel), len(sel))}')
    print()
    print('2. Paused steps by what their list holds')
    for k in KINDS:
        print(f'   steps with a {k} entry: {pct(sum(1 for s in states if s["kinds"][k]), len(states))}; '
              f'with an UNOPENED one: {pct(sum(1 for s in states if s["kinds"][k + ", unopened"]), len(states))}')
    only_callers = sum(1 for s in states if s['unopened'] and s['kinds']['CALLER only, unopened'] == s['unopened'])
    print(f'   steps whose UNOPENED entries are all CALLER only: {pct(only_callers, len(states))}')
    share = [s['kinds']['CONTAINMENT'] / s['n'] for s in states if s['n']]
    print(f'   share of a step\'s list that is CONTAINMENT: mean {100 * statistics.mean(share):.1f}%, median {100 * statistics.median(share):.1f}%')
    print()
    part3()
    part4()


GROUPS = ('CALLER only, TEST CODE', 'CALLER only, other code', 'CALLEE only', 'CALLER and CALLEE', 'CONTAINMENT or neither named')
_len = {}


def lengths(task, path):
    if (task, path) not in _len:
        src = N.file_text(task, path)
        _len[(task, path)] = [len(x) for x in src.splitlines()] if src else None
    return _len[(task, path)]


def tally_kinds(states, table):
    """table: {state key: {arm: [replay rows]}}. Returns (counts per arm, 0/1 lists per arm, outcome and state)."""
    from fork_states import touches
    arms = sorted({a for reps in table.values() for a in reps})
    tally = {a: collections.Counter() for a in arms}
    by = {a: {o: collections.defaultdict(list) for o in ('any', 'caller', 'callee', 'rest')} for a in arms}
    for key, reps in table.items():
        s = states[key]
        spans = s['neighbor_spans']
        unshown = [n for n in s['true_neighbors'] if spans.get(n) and n in set(s.get('unshown_true_neighbors', s['true_neighbors']))]
        group = {}
        for n in unshown:
            k = kind_of(s['task'], s['node'], s['node_span'], n, spans[n])
            group[n] = ('CALLER only, TEST CODE' if is_test(n) else 'CALLER only, other code') if k == 'CALLER only' else (
                k if k in ('CALLEE only', 'CALLER and CALLEE') else 'CONTAINMENT or neither named')
        for arm, rows in reps.items():
            for r in rows:
                hit = set()
                for n in unshown:
                    v = touches(r['next_call'], spans[n], n, line_lengths=lengths(s['task'], spans[n]['path']))
                    if v and v != 'graph':
                        hit.add(group[n])
                tally[arm]['replays'] += 1
                tally[arm]['any'] += bool(hit)
                for gname in hit:
                    tally[arm][gname] += 1
                tally[arm]['several kinds'] += len(hit) > 1
                by[arm]['any'][key].append(int(bool(hit)))
                by[arm]['caller'][key].append(int(bool(hit & {'CALLER only, TEST CODE', 'CALLER only, other code'})))
                by[arm]['callee'][key].append(int('CALLEE only' in hit))
                by[arm]['rest'][key].append(int(bool(hit & {'CALLER and CALLEE', 'CONTAINMENT or neither named'})))
    return tally, by


def show(tally, by, names, order, pairs):
    from analyze_forks import diff_ci
    for arm in order:
        if arm in tally:
            t = tally[arm]
            print(f'   {arm} ({names[arm]}): reads a neighbor\'s code {pct(t["any"], t["replays"])}; ' + '; '.join(f'{gname} {t[gname]}' for gname in GROUPS))
    print('   Differences in points, 95% bootstrap over paused steps (analysis/analyze_forks.diff_ci):')
    for a, b in pairs:
        if a in by and b in by:
            parts = []
            for o, label in (('any', 'a neighbor'), ('caller', 'a CALLER'), ('callee', 'a CALLEE'), ('rest', 'another kind')):
                d = diff_ci(by[a][o], by[b][o])
                parts.append(f'{label} n/a' if d[0] is None else f'{label} {100 * d[0]:+.2f} [{100 * d[1]:+.2f}, {100 * d[2]:+.2f}]')
            print(f'   {a} minus {b}: reads the code of ' + '; '.join(parts))


def part3():
    """Which kind of UNOPENED neighbor the next call reads, by condition, in the replays of pre-registrations 02 and 03.

    Rows, exclusions and the outcome are those of analysis/analyze_b.py as stored in analysis/results/analyze_b.txt
    (runs v5, v6 and v8; a state is kept if every arm and seed returned a well-formed call)."""
    from analyze_forks import KNOWN_TOOLS
    from fork_states import valid_call
    res = HERE / 'results'
    rows = []
    for run in ('v5', 'v6', 'v8'):
        rows += [json.loads(l) for l in open(res / run / 'forks' / 'results.jsonl', encoding='utf-8')]
    ok = [r for r in rows if not r.get('error') and r.get('next_call') and r['next_call']['function_name'] in KNOWN_TOOLS
          and valid_call(r['next_call'])]
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[(r['task'], r['run'], r.get('fork', 0))][(r['arm'], r['seed'])] = r
    arms = sorted({r['arm'] for r in ok})
    seeds = sorted({r['seed'] for r in ok})
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms) * len(seeds)}
    states = {(s['task'], s['run'], s.get('fork', 0)): s
              for s in (json.loads(l) for l in open(STATES / 'states.jsonl', encoding='utf-8'))}
    table = {k: {a: [v[(a, sd)] for sd in seeds] for a in arms} for k, v in complete.items()}
    tally, by = tally_kinds(states, table)
    names = {'A': 'no list', 'P': 'bare names, as the tool prints them', 'H': 'bare names, as a note', 'D': 'names with an instruction',
             'E': 'addresses', 'RD': 'rewired list, names with an instruction', 'RE': 'rewired list, addresses'}
    print('3. Which kind of UNOPENED neighbor the next call reads, by condition (replays of pre-registrations 02 and 03)')
    print(f'   states kept {len(complete)}; conditions {arms}; seeds {len(seeds)}; replays that read neighbors of more than one kind: '
          f'{sum(t["several kinds"] for t in tally.values())}')
    show(tally, by, names, ('A', 'P', 'H', 'D', 'E', 'RD', 'RE'), (('E', 'H'), ('E', 'D'), ('H', 'A'), ('RE', 'RD')))


def part4():
    """The same split in a second set of replays of the same 407 steps: pre-registrations 04 and 12.

    Rows and exclusions as in analysis/analyze_12.py: arm EPATH from analysis/results/12, arms H, EL and E from
    analysis/results/c; a state is kept if H, EL and EPATH are usable for seeds 1 to 3; arm E where it is usable."""
    from gates_c import failure, load_rows, load_states, skey
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    res = HERE / 'results'
    usable = collections.defaultdict(dict)
    for path, arms in ((res / '12' / 'forks' / 'results.jsonl', ('EPATH',)), (res / 'c' / 'forks' / 'results.jsonl', ('H', 'EL', 'E'))):
        for r in load_rows(path):
            if r['arm'] in arms and r['seed'] in (1, 2, 3) and not failure(r):
                usable[skey(r)][(r['arm'], r['seed'])] = r

    def rows_of(key, arm):
        return [usable[key][(arm, sd)] for sd in (1, 2, 3)] if all((arm, sd) in usable.get(key, {}) for sd in (1, 2, 3)) else None

    complete = sorted(k for k in states if all(rows_of(k, a) is not None for a in ('H', 'EL', 'EPATH')))
    table = {k: {a: rows_of(k, a) for a in ('H', 'EPATH', 'EL', 'E') if rows_of(k, a) is not None} for k in complete}
    tally, by = tally_kinds(states, table)
    names = {'H': 'bare names, as a note', 'EPATH': 'name and file, no lines', 'EL': 'name, file and line range',
             'E': 'the same with the first definition line'}
    print()
    print('4. The same split in a second set of replays of the same steps (pre-registrations 04 and 12)')
    print(f'   states kept {len(complete)} (arm E usable in {sum(1 for k in table if "E" in table[k])}); replays that read neighbors of more than one kind: '
          f'{sum(t["several kinds"] for t in tally.values())}')
    show(tally, by, names, ('H', 'EPATH', 'EL', 'E'), (('EL', 'H'), ('EL', 'EPATH'), ('EPATH', 'H')))


if __name__ == '__main__':
    main()
