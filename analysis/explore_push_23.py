"""EXPLORATORY (before experiment 23 runs): the exposure arm PE would give, counted on the stored N runs of
pre-registration 14 (seed 1, 103 tasks) as if their reads had been made under PE. The reads are those the runs made
(a push would change what a run does next, so this counts what the rule promises on unchanged reads, not what PE will
do). Every tool call is paired with its own result (analysis/rederive_18.load_calls_paired).

Also checks that the neighbor lists of analysis/modal_h/push_23.py equal those of analysis/fork_states.py
(graph_for, harness_neighbors) for every node of every task's graph; that arm PH's value (push_23.as_shown) is PE's
with every entry reduced to its name; and counts the population of rule A1 on these unchanged reads (first reads
of a file that holds a pushed entry, made after that push, the file not read before; and how many start past line 1).
Prints counts only. Usage: py -I -X utf8 analysis/explore_push_23.py
"""
import collections
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'modal_h'))
import fork_states as FS  # noqa: E402
import push_23 as P  # noqa: E402
from rederive_18 import load_calls_paired  # noqa: E402

TASKS = HERE / 'results' / '14' / 'validate' / 'tasks_ok.txt'
TRACES = HERE / 'results' / '14' / 'N' / 'seed1' / 'traces'
SPANS = ROOT / 'data' / 'cache' / 'fresh_spans'
GRAPHS = ROOT / 'data' / 'graphs'


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    order = [line.strip() for line in open(TASKS, encoding='utf-8') if line.strip()]
    meta = {json.loads(l)['instance_id']: json.loads(l) for l in open(ROOT / 'data' / 'tasks.jsonl', encoding='utf-8')}
    same = differ = 0
    per_run, entries, chars, sources, reads_ok, first_push_call = [], [], [], [], [], []
    ph_chars, a1_reads, a1_past = [], [], []
    same_but_fields = 0
    for task in order:
        t = meta[task]
        key = f"{t['repo'].split('/')[1]}_{t['base_commit']}"
        graph = json.load(open(GRAPHS / f'{key}.json', encoding='utf-8'))
        nbr = P.neighbor_sets(graph)
        ref = FS.graph_for(t)
        for n in ref['ids']:
            if P.harness_neighbors(nbr, n) == FS.harness_neighbors(ref, n):
                same += 1
            else:
                differ += 1
        spans = json.loads((SPANS / f'{task}.json').read_text(encoding='utf-8'))
        pusher = P.Pusher(nbr, spans)
        calls, _multi, _unparsed, _mism = load_calls_paired(TRACES / f'trace_{task}.json')
        n_push = n_ok = 0
        pushed_file_at, opened_at, start_of = {}, {}, {}
        for i, (name, args, result) in enumerate(calls, 1):
            if name != 'read_file':
                continue
            r = P.shown_range(result)
            if r is None:
                continue
            n_ok += 1
            f = P.norm(result.get('filepath') or args.get('filepath'))
            if f not in opened_at:
                opened_at[f] = i
                start_of[f] = first_start(args, result)
            value = pusher.on_read(result.get('filepath') or args.get('filepath'), *r)
            if value:
                n_push += 1
                if n_push == 1:
                    first_push_call.append(i)
                entries.append(sum(len(v['neighbors']) for v in value))
                sources.append(len(value))
                chars.append(len(json.dumps(value, ensure_ascii=False)))
                ph_chars.append(len(json.dumps(P.as_shown(value, 'PH'), ensure_ascii=False)))
                same_but_fields += P.as_shown(value, 'PH') == [
                    {'node': v['node'], 'neighbors': [{'name': n['name']} for n in v['neighbors']]} for v in value] \
                    and P.as_shown(value, 'PE') == value
                for v in value:
                    for n in v['neighbors']:
                        pushed_file_at.setdefault(P.norm(n['file']), i)
        per_run.append(n_push)
        reads_ok.append(n_ok)
        # A1's population on unchanged reads: a file holding a pushed entry whose first read comes after that push
        q = [start_of[f] for f, ip in pushed_file_at.items() if f in opened_at and opened_at[f] > ip]
        a1_reads.append(len(q))
        a1_past.append(sum(s is not None and s > 1 for s in q))
    n = len(per_run)
    with_push = sum(x > 0 for x in per_run)
    print(f'neighbor lists of push_23 against fork_states: {same} nodes equal, {differ} differ')
    print(f'{n} stored N runs of 14 (seed 1); reads of status ok per run: median {statistics.median(reads_ok)}, mean '
          f'{statistics.mean(reads_ok):.1f}')
    print(f'runs with at least one push: {with_push} of {n} ({100 * with_push / n:.1f}%)')
    print(f'reads that would get the key per run: median {statistics.median(per_run)}, mean {statistics.mean(per_run):.2f}, '
          f'max {max(per_run)}; distribution {dict(sorted(collections.Counter(per_run).items()))}')
    print(f'per push ({len(entries)} pushes): entries median {statistics.median(entries)}, mean {statistics.mean(entries):.2f}, '
          f'max {max(entries)}; source nodes with entries: {dict(sorted(collections.Counter(sources).items()))}; '
          f'characters median {statistics.median(chars)}, mean {statistics.mean(chars):.0f}, max {max(chars)}')
    run_chars = per_run_chars(per_run, chars)
    print(f'characters added per run: median {statistics.median(run_chars)}, max {max(run_chars)}')
    print(f'call index of the first push (runs with one): median {statistics.median(first_push_call)}, max {max(first_push_call)}')
    print(f'arm PH (names only): pushes whose PH value is the PE value with each entry reduced to its name, and PE the '
          f'value unchanged: {same_but_fields} of {len(chars)}; characters per push median {statistics.median(ph_chars)}, '
          f'mean {statistics.mean(ph_chars):.0f}; per run median {statistics.median(per_run_chars(per_run, ph_chars))}')
    runs_a1 = sum(x > 0 for x in a1_reads)
    print(f'rule A1\'s population on these unchanged reads (first read of a file that holds a pushed entry, after that push, '
          f'the file not read before): runs with at least one {runs_a1} of {n}; such reads {sum(a1_reads)} (per run with one: '
          f'median {statistics.median([x for x in a1_reads if x]) if runs_a1 else 0}); of them starting past line 1 '
          f'{sum(a1_past)} ({100 * sum(a1_past) / max(1, sum(a1_reads)):.1f}%)')


def first_start(args, result):
    """START of a read (analysis/rederive_reads_22.py): None without a start_line argument (any spelling), else the
    start_line the result returned (a mangled name is answered from line 1)."""
    import re
    asked = [v for k, v in (args or {}).items() if re.sub(r'[\\"\'\s]', '', str(k)) == 'start_line']
    if not asked:
        return None
    s = result.get('start_line')
    if isinstance(s, int):
        return s
    try:
        return int(asked[0])
    except (TypeError, ValueError):
        return None


def per_run_chars(per_run, chars):
    out, k = [], 0
    for x in per_run:
        out.append(sum(chars[k:k + x]))
        k += x
    return out


if __name__ == '__main__':
    main()
