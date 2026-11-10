"""Mangled argument names in tool calls (EXPLORATORY; an interface count, not a model outcome).

Some calls arrive with an argument name that carries a stray quote or backslash, for example {"filepath": ...,
'start_line"': 600}. This script counts them
  1. in the public end-to-end traces (every tool call of every base-arm and skill-arm run), with what the tool
     returned, and
  2. in the first calls of the replay runs given on the command line, by arm.
A name is mangled if it is not a plain identifier. Its intended name is the name with quotes, backslashes and spaces
removed, when that is a declared parameter of the tool.

Usage: py -I -X utf8 analysis/mangled_args.py [<results.jsonl> ...]
Writes nothing; prints a report.
"""
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graphloc_traces import iter_runs, load  # noqa: E402

BOUNDS = ('start_line', 'end_line')


def clean(name):
    return re.sub(r'[\\"\'\s]', '', str(name))


def shape(args):
    """(has a well-formed bound, has a mangled bound, other mangled names) of a read_file call."""
    if not isinstance(args, dict):
        return False, False, True
    good = any(k in BOUNDS for k in args)
    bad = any((not str(k).isidentifier()) and clean(k) in BOUNDS for k in args)
    other = any((not str(k).isidentifier()) and clean(k) not in BOUNDS for k in args)
    return good, bad, other


def obs_dict(step):
    ob = step.get('observation')
    content = ob.get('content') if isinstance(ob, dict) else ob
    if isinstance(content, list):
        content = content[0] if content else None
    if isinstance(content, dict):
        content = content.get('content', content)
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return None
    return content if isinstance(content, dict) else None


def traces():
    print('1. Public end-to-end traces, every tool call')
    by_arm = collections.defaultdict(collections.Counter)
    returned = collections.defaultdict(collections.Counter)
    runs = collections.Counter()
    runs_with = collections.Counter()
    for run in iter_runs():
        t = load(run['path'])
        steps = t.get('steps') if isinstance(t, dict) else t
        arm = run['arm']
        runs[arm] += 1
        seen = False
        for st in steps or []:
            calls = st.get('tool_calls') or []
            for tc in calls:
                fn = tc.get('function_name')
                args = tc.get('arguments') or {}
                c = by_arm[arm]
                c['calls'] += 1
                names = [k for k in args if not str(k).isidentifier()] if isinstance(args, dict) else []
                if names:
                    c['calls with a mangled name'] += 1
                    c[f'mangled:{fn}'] += 1
                if fn != 'read_file':
                    continue
                c['read_file'] += 1
                good, bad, _other = shape(args)
                if good or bad:
                    c['read_file with a line bound'] += 1
                if bad:
                    c['read_file with a mangled bound'] += 1
                    seen = True
                    o = obs_dict(st) if len(calls) == 1 else None
                    if isinstance(o, dict):
                        asked = None
                        for k, v in args.items():
                            if clean(k) == 'start_line' and not str(k).isidentifier():
                                asked = v
                        got = o.get('start_line')
                        if o.get('status') != 'ok':
                            returned[arm]['tool returned an error'] += 1
                        elif asked is not None and got == 1 and asked != 1:
                            returned[arm]['asked for another start line, got the file from line 1'] += 1
                        elif asked is not None and got == asked:
                            returned[arm]['got the start line asked for'] += 1
                        else:
                            returned[arm]['other (only the end bound mangled, or start line 1 asked)'] += 1
                    else:
                        returned[arm]['result not readable here'] += 1
        runs_with[arm] += int(seen)
    for arm in sorted(by_arm):
        c = by_arm[arm]
        print(f'  arm {arm}: {runs[arm]} runs, {c["calls"]} tool calls, {c["read_file"]} read_file calls, '
              f'{c["read_file with a line bound"]} of them with a line bound')
        b = c['read_file with a line bound']
        m = c['read_file with a mangled bound']
        print(f'    read_file calls with a mangled bound name: {m}' + (f' = {100 * m / b:.1f}% of the bounded reads' if b else '')
              + f'; runs with at least one: {runs_with[arm]} of {runs[arm]}')
        print(f'    calls of any tool with a mangled name: {c["calls with a mangled name"]} ('
              + ', '.join(f'{k.split(":", 1)[1]} {v}' for k, v in sorted(c.items()) if k.startswith('mangled:')) + ')')
        for k, v in returned[arm].most_common():
            print(f'    result of a read with a mangled bound: {k}: {v}')


def replays(path):
    rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
    n = collections.Counter()
    c = collections.defaultdict(collections.Counter)
    for r in rows:
        a = r['arm']
        n[a] += 1
        call = r.get('next_call') or {}
        if call.get('function_name') != 'read_file':
            continue
        good, bad, _other = shape(call.get('arguments'))
        c[a]['read_file'] += 1
        c[a]['bounded'] += int(good or bad)
        c[a]['mangled'] += int(bad)
    print(f'  {path}')
    for a in sorted(n):
        b, m = c[a]['bounded'], c[a]['mangled']
        print(f'    {a:3s}: {n[a]} replays, first call read_file {c[a]["read_file"]}, with a line bound {b}, '
              f'mangled bound {m}' + (f' = {100 * m / b:.1f}% of bounded reads, {100 * m / n[a]:.1f}% of replays' if b else ''))


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    traces()
    if sys.argv[1:]:
        print('\n2. First calls of the replay runs')
        for p in sys.argv[1:]:
            replays(p)


if __name__ == '__main__':
    main()
