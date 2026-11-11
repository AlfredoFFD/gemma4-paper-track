"""States file for pre-registration 16 (how the task prompt describes the graph tools, and the first model call).

Usage: py -I -X utf8 analysis/make_states_w.py [--current <folder of whole-run traces>]

Two task prompts exist for a task:
  September  the prompt that the recorded runs of September logged: the message of the step with source `user` in
             analysis/fork_states_g/fresh_states.jsonl (the first message of the fresh episodes of pre-registrations
             08 and 09);
  current    the prompt that the current evaluator builds (harness wheels of Oct 12): the message of the step with
             source `user` in the whole-run trace of condition N of pre-registration 14
             (data/forks_14_modal/out_14/N/seed1/traces/trace_<task>.json; the traces with their prompts are not
             tracked).
Each prompt describes the graph tools in four lines that stand one after another: a line that begins "This repository
has pre-built code graph and embedding data", then one line for each of `search_similar_code`, `get_code_neighbors`
and `get_code_subgraph`. The wording of the four lines differs between the two prompts. This script holds only the
beginnings of those lines; it reads the lines themselves from the prompts.

A task is kept if it has both prompts and each of the two holds its four-line block exactly once: one place where the
four lines stand one after another, and no other line that begins like one of the four.

Arms, one record per (task, arm) in analysis/fork_states_w/first_call_states.jsonl (not tracked: the prompts are
competition data; the folder's .gitignore is written here if it is missing):
  C    the current prompt as built
  CS   the current prompt with its four lines replaced by the four lines of the task's September prompt
  S    the September prompt as logged
  SC   the September prompt with its four lines replaced by the four lines of the task's current prompt
Nothing else changes in CS and SC: the script checks that C and CS, and S and SC, differ in those four lines only,
that the block of CS equals the block of S and the block of SC equals the block of C, and that putting the block back
gives the prompt it came from.

A record: task, arm, run (0), fork (0), repo, base_commit, prompt_from, block_from, steps (one step: the task prompt,
in the form analysis/replay.py reads), prompt_chars, prompt_md5, logged_first_prompt_tokens (arm C: the prompt size
of the first model call in the whole-run trace; arm S: the size the September run logged; CS and SC: null).

Printed: how many tasks have each prompt, how many have both, how many are kept and why the others are not; how many
distinct wordings of the block each source has; in how many kept tasks the two prompts are the same outside the block
and the listing of the workspace's files (the lines between the last two code fences); sizes by arm; the md5 of the
file.
"""
import argparse
import collections
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEPTEMBER = HERE / 'fork_states_g' / 'fresh_states.jsonl'
CURRENT = ROOT / 'data' / 'forks_14_modal' / 'out_14' / 'N' / 'seed1' / 'traces'
OUT = HERE / 'fork_states_w' / 'first_call_states.jsonl'
ARMS = ('C', 'CS', 'S', 'SC')                      # arm -> (the prompt it starts from, the block it carries)
ARM_PARTS = {'C': ('current', 'current'), 'CS': ('current', 'september'),
             'S': ('september', 'september'), 'SC': ('september', 'current')}
# The beginnings of the four lines (the same in both wordings), and the line that opens and closes the listing.
BLOCK_HEAD = 'This repository has pre-built code graph and embedding data'
BLOCK_TOOLS = ('- `search_similar_code(query)`:', '- `get_code_neighbors(node)`:', '- `get_code_subgraph(nodes)`:')
MARKERS = (BLOCK_HEAD,) + BLOCK_TOOLS
FENCE = '```'
IGNORE = '# built by analysis/make_states_w.py from the competition\'s task prompts: never committed\n' \
         'first_call_states.jsonl\n'


def md5(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def user_message(steps):
    """The message of the one step with source `user`, or None if there is not exactly one."""
    users = [s for s in steps if s.get('source') == 'user']
    return (users[0].get('message') or '') if len(users) == 1 else None


def block_at(lines):
    """Where the four-line block starts, or None unless the prompt holds it exactly once."""
    starts = [i for i in range(len(lines) - len(MARKERS) + 1)
              if all(lines[i + j].startswith(m) for j, m in enumerate(MARKERS))]
    if len(starts) != 1:
        return None
    i = starts[0]
    others = [k for k, line in enumerate(lines) if not i <= k < i + len(MARKERS) and line.startswith(MARKERS)]
    return None if others else i


def with_block(lines, i, block):
    return lines[:i] + list(block) + lines[i + len(MARKERS):]


def outside(lines, i):
    """The prompt without its block and without its listing (the lines between the last two code fences)."""
    rest = lines[:i] + lines[i + len(MARKERS):]
    fences = [k for k, line in enumerate(rest) if line.strip() == FENCE]
    if len(fences) < 2:
        return None, None
    return rest[:fences[-2] + 1] + rest[fences[-1]:], fences[-1] - fences[-2] - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--current', default=str(CURRENT), help='folder with trace_<task>.json of the whole runs, condition N')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    sept, meta = {}, {}
    for line in open(SEPTEMBER, encoding='utf-8'):
        s = json.loads(line)
        text = user_message(s['steps'])
        if text is not None:
            sept[s['task']] = text
        meta[s['task']] = {'repo': s['repo'], 'base_commit': s['base_commit'], 'logged': s.get('logged_first_prompt_tokens')}
    cur, cur_logged = {}, {}
    files = sorted(Path(args.current).glob('trace_*.json'))
    for f in files:
        task = f.stem[len('trace_'):]
        steps = json.loads(f.read_text(encoding='utf-8')).get('steps') or []
        text = user_message(steps)
        if text is not None:
            cur[task] = text
        first = next((s for s in steps if s.get('source') == 'agent'), None)   # the first model call of the whole run
        cur_logged[task] = ((first or {}).get('metrics') or {}).get('prompt_tokens')

    both = sorted(set(sept) & set(cur))
    print(f'tasks with a September prompt (fresh_states.jsonl): {len(sept)}')
    print(f'tasks with a current prompt ({len(files)} whole-run traces of condition N): {len(cur)}')
    print(f'tasks with both prompts: {len(both)}; only September: {sorted(set(sept) - set(cur))}; '
          f'only current: {sorted(set(cur) - set(sept))}')

    kept, why = [], collections.Counter()
    wording = {'september': collections.Counter(), 'current': collections.Counter()}
    same_outside, listing = 0, {'september': [], 'current': []}
    recs = []
    for task in both:
        a, b = sept[task].split('\n'), cur[task].split('\n')
        ia, ib = block_at(a), block_at(b)
        if ia is None or ib is None:
            why['the September prompt does not hold its block exactly once' if ia is None
                else 'the current prompt does not hold its block exactly once'] += 1
            continue
        if task not in meta:
            why['no repository and commit on record'] += 1
            continue
        kept.append(task)
        block = {'september': a[ia:ia + len(MARKERS)], 'current': b[ib:ib + len(MARKERS)]}
        for name in block:
            wording[name]['\n'.join(block[name])] += 1
        base = {'september': (a, ia), 'current': (b, ib)}
        out_a, n_a = outside(a, ia)
        out_b, n_b = outside(b, ib)
        same_outside += out_a is not None and out_a == out_b
        if n_a is not None and n_b is not None:
            listing['september'].append(n_a)
            listing['current'].append(n_b)
        texts = {}
        for arm in ARMS:
            src, blk = ARM_PARTS[arm]
            lines, i = base[src]
            texts[arm] = '\n'.join(with_block(lines, i, block[blk]))
        # the checks: an arm as built or logged is the source text itself; a swapped arm differs in the four lines only
        assert texts['C'] == cur[task] and texts['S'] == sept[task]
        for plain, swapped, other in (('C', 'CS', 'S'), ('S', 'SC', 'C')):
            p, q = texts[plain].split('\n'), texts[swapped].split('\n')
            i = block_at(q)
            assert i == block_at(p) and len(p) == len(q)
            assert all(i <= k < i + len(MARKERS) for k in range(len(p)) if p[k] != q[k]), (task, swapped)
            j = block_at(texts[other].split('\n'))
            assert q[i:i + len(MARKERS)] == texts[other].split('\n')[j:j + len(MARKERS)]
            assert '\n'.join(with_block(q, i, p[i:i + len(MARKERS)])) == texts[plain]
        for arm in ARMS:
            src, blk = ARM_PARTS[arm]
            recs.append({
                'task': task, 'arm': arm, 'run': 0, 'fork': 0, 'repo': meta[task]['repo'],
                'base_commit': meta[task]['base_commit'], 'prompt_from': src, 'block_from': blk,
                'steps': [{'step_id': 1, 'source': 'user', 'message': texts[arm], 'extra': {'event_type': 'task_prompt'}}],
                'prompt_chars': len(texts[arm]), 'prompt_md5': md5(texts[arm]),
                'logged_first_prompt_tokens': cur_logged.get(task) if arm == 'C' else meta[task]['logged'] if arm == 'S' else None})

    print(f'tasks kept (both prompts, each with its four-line block exactly once): {len(kept)}')
    for reason, n in sorted(why.items()):
        print(f'  not kept, {reason}: {n}')
    repos = collections.Counter(meta[t]['repo'] for t in kept)
    print('  by repository: ' + ', '.join(f'{r} {n}' for r, n in sorted(repos.items())))
    for name in ('september', 'current'):
        print(f'  wordings of the block in the {name} prompts: {len(wording[name])} '
              f'(md5 of the four lines, tasks: ' + ', '.join(f'{md5(k)} {v}' for k, v in wording[name].most_common()) + ')')
    print(f'  kept tasks whose two prompts are the same outside the block and the listing of files: {same_outside} of {len(kept)}')
    if listing['current']:
        longer = sum(x > y for x, y in zip(listing['september'], listing['current']))
        print('  lines of the listing: ' + '; '.join(
            f'{name} median {st.median(v):.0f}, from {min(v)} to {max(v)}' for name, v in listing.items())
            + f'; the September listing is the longer one in {longer} of {len(listing["current"])} tasks')
    if not kept:
        print('no task kept: nothing written')
        return
    for arm in ARMS:
        chars = [r['prompt_chars'] for r in recs if r['arm'] == arm]
        logged = [r['logged_first_prompt_tokens'] for r in recs if r['arm'] == arm and r['logged_first_prompt_tokens']]
        print(f'  arm {arm:<2} {len(chars)} records; characters median {st.median(chars):.0f}, from {min(chars)} to {max(chars)}'
              + (f'; logged size of the first model call, tokens: median {st.median(logged):.0f} ({len(logged)} tasks)' if logged else ''))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ignore = OUT.parent / '.gitignore'
    if not ignore.exists():
        ignore.write_text(IGNORE, encoding='utf-8', newline='\n')
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        for r in recs:
            f.write(json.dumps(r) + '\n')
    print(f'wrote {OUT.relative_to(ROOT).as_posix()}: {len(recs)} records ({len(kept)} tasks x {len(ARMS)} arms), '
          f'md5 {hashlib.md5(OUT.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
