"""Where a first read of a listed neighbor's file starts, by how the list was written (EXPLORATORY).

Usage: py -I -X utf8 analysis/explore_first_reads.py

One-step replays of every run in the repository. A replay counts here if it is usable by the frozen rule
(gates_c.failure) and its next call is a `read_file` on a file that holds a listed true neighbor and that the agent
had not opened (mangled_sensitivity.opens_listed_file). For those reads:
- "asks past line 1": the start line the model wrote is greater than 1 (a mangled bound name is read as written,
  that is, with quotes, backslashes and spaces removed from the argument name);
- "covers a neighbor": the lines asked for, capped at 150 lines from the start, overlap a listed neighbor in that
  file; "starts on one": the start line is the first line of a listed neighbor in that file.
Conditions are grouped by whether the list they show carries line numbers: without (no list, bare names in either
channel, the instruction, the definition line only, and the same under the original rendering) and with (name,
file and lines, with or without the definition line, in either channel and under either rendering).
Counts only; this restates the registered replays as reads and changes no registered number.
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gates_c import failure, load_rows, load_states, skey  # noqa: E402
from mangled_sensitivity import clean, opens_listed_file  # noqa: E402

RES = HERE / 'results'
WITHOUT = ('A', 'P', 'H', 'D', 'ES', 'Aw', 'Hw')
WITH = ('E', 'EL', 'PE', 'Ew')
RUNS = (
    ('Gemma-4-31B', 'hosted 1', 'v5', 'fork_states', ('A', 'P', 'H')),
    ('Gemma-4-31B', 'hosted 2', 'v6', 'fork_states', ('D', 'E')),
    ('Gemma-4-31B', 'parts and false entry', 'c', 'fork_states_d', ('H', 'ES', 'EL', 'E')),
    ('Gemma-4-31B', 'tool channel', 'd1', 'fork_states_d', ('P', 'PE', 'E')),
    ('Gemma-4-31B', 'rendering', 'w', 'fork_states_d', ('Aw', 'Hw', 'Ew')),
    ('Gemma-4-31B', 'newest wheels', 'g_onestep', 'fork_states_d', ('H', 'E')),
    ('Gemma 4 26B-A4B', 'second model', 'd2_26b', 'fork_states_d', ('A', 'H', 'E')),
    ('Gemma 4 E4B', 'second model', 'd2_e4b', 'fork_states_d', ('A', 'H', 'E')),
    ('Qwen2.5-Coder-32B', 'another family', 'qwen', 'fork_states_d', ('A', 'H', 'E')),
)
SEEDS = (1, 2, 3)


def norm(p):
    p = str(p or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def bounds(args):
    out = {}
    for k, v in args.items():
        c = clean(k)
        if c in ('start_line', 'end_line'):
            try:
                out.setdefault(c, int(v))
            except (TypeError, ValueError):
                pass
    return out.get('start_line'), out.get('end_line')


def read_stats(state, call):
    path = norm(call['arguments'].get('filepath'))
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    spans = [state['neighbor_spans'][n] for n in unshown
             if state['neighbor_spans'].get(n) and state['neighbor_spans'][n]['path'] == path]
    start, end = bounds(call['arguments'])
    ranged = start is not None and start > 1
    covers = on_first = False
    if ranged:
        last = min(end, start + 149) if end is not None else start + 149
        covers = any(sp['end'] is not None and not (last < sp['start'] or start > sp['end']) for sp in spans)
        on_first = any(sp['start'] == start for sp in spans)
    return ranged, covers, on_first


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('EXPLORATORY. First reads of a listed neighbor\'s unopened file in the one-step replays.')
    states_cache = {}
    pooled = collections.defaultdict(lambda: collections.Counter())
    print(f'\n{"model":16s} {"run":22s} {"arm":4s} {"usable":>7s} {"reads":>6s} {"past line 1":>12s} {"covers":>7s} {"starts on one":>14s}')
    for model, label, run, sdir, arms in RUNS:
        if sdir not in states_cache:
            states_cache[sdir] = load_states(HERE / sdir / 'states.jsonl')
        states = states_cache[sdir]
        rows = load_rows(RES / run / 'forks' / 'results.jsonl')
        for arm in arms:
            c = collections.Counter()
            for r in rows:
                if r['arm'] != arm or r['seed'] not in SEEDS or failure(r):
                    continue
                c['usable'] += 1
                call = r['next_call']
                st = states[skey(r)]
                if not opens_listed_file(st, call):
                    continue
                ranged, covers, on_first = read_stats(st, call)
                c['reads'] += 1
                c['ranged'] += int(ranged)
                c['covers'] += int(covers)
                c['on_first'] += int(on_first)
            share = f'{100 * c["ranged"] / c["reads"]:.1f}%' if c['reads'] else 'n/a'
            print(f'{model:16s} {label:22s} {arm:4s} {c["usable"]:7d} {c["reads"]:6d} {c["ranged"]:5d} {share:>6s} {c["covers"]:7d} {c["on_first"]:14d}')
            pooled[(model, 'with' if arm in WITH else 'without')].update(c)
    print('\nPooled by model: conditions without line numbers (A, P, H, D, ES, Aw, Hw) and with them (E, EL, PE, Ew)')
    for (model, kind), c in sorted(pooled.items()):
        share = f'{100 * c["ranged"] / c["reads"]:.1f}%' if c['reads'] else 'n/a'
        print(f'  {model:16s} {kind:8s}: first reads {c["reads"]}, ask past line 1 {c["ranged"]} ({share}), cover a listed neighbor '
              f'{c["covers"]}, start on a listed neighbor\'s first line {c["on_first"]}')


if __name__ == '__main__':
    main()
