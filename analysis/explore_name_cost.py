"""What a name without an address costs in calls (EXPLORATORY; five-call records of pre-registration 06).

Usage: py -I -X utf8 analysis/explore_name_cost.py [<run_dir>]      (default: analysis/results/k/forks)

For every usable replay (the frozen rule of analyze_k.py) the script finds the first executed `read_file` of a file
that holds a listed neighbor and that the agent had not opened, neither before the pause nor earlier in the replay.
For that read it reports, by arm:
- whether it returned the file from line 1;
- whether the lines it returned include a listed neighbor of that file ("shows a neighbor at once");
- if not: whether the next model call is a search (grep, rg) that names the file or a listed neighbor of it, and how
  many more model calls pass until a listed neighbor of that file is shown (a `read_file` whose returned lines
  overlap it, or a shell command that the frozen scorer counts as a view of it), within the five-call window.
Counts only. Arms: A no list, H bare names, E name with file and lines, RE a rewired list in E's format; a listed
neighbor is a true neighbor in an unopened file whatever the arm shows, so A and RE are base rates.
"""
import collections
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_k import ARMS, first_call_failure  # noqa: E402
from fork_states import norm_path, touches  # noqa: E402
from gates_c import _ll, load_states, skey  # noqa: E402


def overlaps(a, b, span):
    return span['end'] is not None and not (b < span['start'] or a > span['end'])


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results' / 'k' / 'forks'
    states = load_states(HERE / 'fork_states_d' / 'states.jsonl')
    rows = [json.loads(l) for l in open(run_dir / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    print('EXPLORATORY. The first read of a listed neighbor\'s unopened file inside the five-call window, by arm.')
    for arm in ARMS:
        c = collections.Counter()
        waits = []
        for r in rows:
            if r['arm'] != arm or first_call_failure(r):
                continue
            c['usable'] += 1
            state = states[skey(r)]
            unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
            by_file = collections.defaultdict(dict)
            for n in unshown:
                sp = state['neighbor_spans'].get(n)
                if sp:
                    by_file[sp['path']][n] = sp
            opened = set(state.get('shown_files') or [])
            steps = r.get('steps') or []
            found = None
            for i, step in enumerate(steps):
                for call in step['calls']:
                    if call['function_name'] != 'read_file' or not call['executed']:
                        continue
                    res = call.get('result') or {}
                    path = norm_path(call['arguments'].get('filepath'))
                    if res.get('status') != 'ok':
                        continue
                    if path in by_file and path not in opened and found is None:
                        found = (i, path, res)
                    opened.add(path)
                if found is not None:
                    break
            if found is None:
                continue
            i, path, res = found
            spans = by_file[path]
            a, b = res.get('start_line'), res.get('end_line')
            c['first_reads'] += 1
            top = a == 1
            c['from_line_1'] += int(top)
            shows = isinstance(a, int) and isinstance(b, int) and any(overlaps(a, b, sp) for sp in spans.values())
            key = 'top' if top else 'ranged'
            c[f'{key}_shows'] += int(shows)
            if shows:
                continue
            c[f'{key}_misses'] += 1
            later = steps[i + 1:]
            if later and later[0]['calls']:
                c[f'{key}_misses_with_next'] += 1
                nxt = later[0]['calls'][0]
                cmd = str(nxt['arguments'].get('command', '')) if nxt['function_name'] == 'run_command' else ''
                is_search = any(w in cmd.split() or cmd.startswith(w) for w in ('grep', 'rg', 'egrep', 'fgrep')) or ' grep ' in f' {cmd} '
                names = any(n.split('.')[-1] in cmd for n in spans) or path in cmd
                c[f'{key}_next_is_search'] += int(bool(is_search and names))
            wait = None
            for j, step in enumerate(later, 1):
                for call in step['calls']:
                    if not call['executed']:
                        continue
                    res2 = call.get('result') or {}
                    if call['function_name'] == 'read_file' and res2.get('status') == 'ok' \
                            and norm_path(call['arguments'].get('filepath')) == path:
                        a2, b2 = res2.get('start_line'), res2.get('end_line')
                        if isinstance(a2, int) and isinstance(b2, int) and any(overlaps(a2, b2, sp) for sp in spans.values()):
                            wait = j
                    elif call['function_name'] == 'run_command':
                        view = {'function_name': 'run_command', 'arguments': call['arguments']}
                        if any(touches(view, sp, n, line_lengths=_ll(state['task'], path)) == 'read' for n, sp in spans.items()):
                            wait = j
                    if wait:
                        break
                if wait:
                    break
            if wait:
                c[f'{key}_shown_later'] += 1
                if top:
                    waits.append(wait)
            else:
                c[f'{key}_never'] += 1
        n = c['first_reads']
        print(f'\narm {arm}: usable replays {c["usable"]}; with such a first read {n}')
        if not n:
            continue
        print(f'  returned from line 1: {c["from_line_1"]} of {n}; of them a listed neighbor is shown at once in {c["top_shows"]} '
              f'({100 * c["top_shows"] / max(1, c["from_line_1"]):.1f}%)')
        m = c['top_misses']
        if m:
            print(f'  the {m} reads from line 1 that show none: the next model call is a search naming the file or a neighbor in '
                  f'{c["top_next_is_search"]} of {c["top_misses_with_next"]}; a neighbor of the file is shown later in the window in '
                  f'{c["top_shown_later"]} (median {st.median(waits) if waits else "n/a"} more model calls), never in {c["top_never"]}')
        rg = n - c['from_line_1']
        print(f'  returned from another line: {rg}; of them a listed neighbor is shown at once in {c["ranged_shows"]} '
              f'({100 * c["ranged_shows"] / max(1, rg):.1f}%)')


if __name__ == '__main__':
    main()
