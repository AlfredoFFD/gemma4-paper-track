"""Where every file read of a run starts, and whether the run held a line number for that place (EXPLORATORY).

Usage: py -I -X utf8 analysis/explore_read_starts.py             the report
       py -I -X utf8 analysis/explore_read_starts.py --sample    the report, then 20 reads of the last class per
                                                                 source with the calls before them, to read by hand

Nothing here was pre-registered and no model is run. The script reads whole runs of Gemma 4 agents on this
benchmark and asks two things. Part 1: for every file read, where its start line could have come from. Part 2: for
every place the reference fix changes, whether the run held a line number for it, and whether the run was shown it.

Sources:
  data/graphloc/out/...                      other teams' public runs: the starter agent (arm base) and the same
                                             agent with a graph skill (arm skill), September 2026, Gemma-4-31B
  data/public_traces/...                     two other teams' custom agents (as in public_runs_address.sources())
  analysis/results/14/                       our whole runs of pre-registration 14, conditions N and NAF
The public data is not in this repository and is not redistributed.

Rules. READ, its file and its asked start and end are those of analysis/public_runs_address.py (a bound written
under a mangled argument name counts as written). Only READS whose result has status ok are classed.
  RETURNED RANGE  start_line..end_line of the result of a READ.
  OWN FILE        a file the run had written with write_file before the read. Its reads are counted apart.
  TOP             the asked start is absent, not a number, or at most 1.
  WINDOW          of a READ with an asked start s above 1: s to the smaller of the asked end and s + 149 (the harness
                  returns at most 150 lines).
  NAMED LINE      a line number that an earlier tool result of the run printed for the file under the ADDRESS rule
                  of public_runs_address.py (ways i to iii: `<path>:<n>:`, a traceback, a numbering command on the
                  file), applied to every earlier call that is not a READ; and, in the task text (the problem
                  statement of data/tasks.jsonl), ways (i) and (ii) and a link to a line of the file as GitHub writes
                  it, `<path>#L<n>` or `<path>#L<a>-L<b>`.
  ADDRESSED       a NAMED LINE lies in the WINDOW or within 10 lines of it. STRICT: in the WINDOW.
  SOURCE          of a NAMED LINE: TASK TEXT; OWN SEARCH, a run_command that runs grep with -n, cat -n or nl
                  (public_runs_address.numbering_command); COMMAND OUTPUT, any other run_command (a traceback, a
                  test report); OTHER TOOL, a result of any other tool.
  PAGING          the WINDOW touches what the run had read of the file: its start lies inside an earlier RETURNED
                  RANGE (INSIDE), or at most 10 lines after the end of one (NEXT), or its start lies before an earlier
                  RETURNED RANGE and the WINDOW reaches that range or ends at most 10 lines before it (BACK).
  OTHER NUMBER    a line of the WINDOW, or within 10 lines of it, was numbered for the file by an earlier result in a
                  way the ADDRESS rule does not count: a hunk header of a diff of that file (edit_file returns the
                  diff of its edit; the hunk's lines in the new file), or a line `<rank> <score> <path>:<line> <name>`
                  as the graph skill of the GraphLoc skill arm prints.
  SHELL VIEW      an earlier run_command named the file and used a viewer (cat, head, tail, sed, nl, less, more, awk).
  Class of a READ, the first that applies: TOP, PAGING, ADDRESSED, OTHER NUMBER, SHELL VIEW, NO NUMBER.
  NO NUMBER       so: a start past line 1 at a place for which the run held no line number and next to nothing it
                  had read. A JUMP is a READ of class ADDRESSED, OTHER NUMBER, SHELL VIEW or NO NUMBER.
  HIT             a READ of a file the fix changes whose RETURNED RANGE overlaps a CHANGED REGION.
  BY CHANCE       for a READ past line 1 of a file with no earlier SHELL VIEW: the share of the file's possible starts
                  (line 2 to its last line, same WINDOW length) that would have been classed PAGING, ADDRESSED or
                  OTHER NUMBER at that point of the run. One minus its mean is the share of NO NUMBER expected if
                  starts were placed at random in the file.

  CHANGED REGION, SHOWN, OPENED FILE   as in analysis/public_runs_sources.py (READS of status ok only).
  DEEP            a CHANGED REGION that starts below line 150; the others are IN THE FIRST 150 LINES.
  HELD A NUMBER   a NAMED LINE within 10 lines of the region was printed before the region was first SHOWN (before
                  the end of the run if it never was). WIDER adds the lines of OTHER NUMBER.
  HOW             for a region that was SHOWN: the class of the READ that first showed it.
  READS TO REACH  for a region that was SHOWN: the READS of status ok of its file up to and including the one that
                  first showed it.
  STRETCH FROM THE TOP  for a file whose first READ was a TOP read that returned from line 1: the lines reachable
                  from line 1 through RETURNED RANGES of the run without a gap of more than 10 lines. The run JUMPED
                  in the file if a RETURNED RANGE starts more than 10 lines past the end of that stretch.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analyze_forks.boot_ci, diff_ci).
"""
import argparse
import collections
import io
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_14 as A  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import (DATA, SKILL_LINE, asked, calls_of, classify, command_of, is_read, norm,  # noqa: E402
                                 numbering_command, pct, sources, viewed_files)
from public_runs_time_to_fix import gold_regions, graphloc_records, truth  # noqa: E402

NEAR = 10
CAP = 150
INF = float('inf')
HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', re.M)
CLASSES = ('TOP', 'PAGING', 'ADDRESSED', 'OTHER NUMBER', 'SHELL VIEW', 'NO NUMBER')
KINDS = ('OWN SEARCH', 'COMMAND OUTPUT', 'TASK TEXT', 'OTHER TOOL')


def task_texts():
    out = {}
    with io.open(DATA / 'tasks.jsonl', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                t = json.loads(line)
                out[t['instance_id']] = t.get('problem_statement') or ''
    return out


def link_lines(f, text):
    """Lines of f that a link `<path>#L<n>` or `<path>#L<a>-L<b>` in text points to."""
    out = set()
    for m in re.finditer(re.escape(f) + r'#L(\d+)(?:-L(\d+))?', text):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        out.update(range(a, min(b, a + 400) + 1))
    return out


def diff_lines(f, text):
    """Lines of f, in new-file numbers, that the hunks of a diff of f in text cover."""
    out = set()
    for m in re.finditer(r'^\+\+\+ (?:b/)?' + re.escape(f) + r'[ \t]*$', text, re.M):
        rest = text[m.end():]
        stop = re.search(r'^(?:diff --git |--- (?:a/|/dev/null))', rest, re.M)
        for h in HUNK.finditer(rest[:stop.start()] if stop else rest):
            c = int(h.group(1))
            d = int(h.group(2)) if h.group(2) is not None else 1
            out.update(range(c, c + max(d, 1)))
    return out


def skill_lines(f, text):
    return {int(m.group(2)) for m in SKILL_LINE.finditer(text) if norm(m.group(1)) == f}


def union(pairs, limit):
    out = set()
    for j, lines in pairs:
        if j < limit:
            out |= lines
    return out


def measure(intervals, lo, hi):
    """Number of integers of [lo, hi] covered by the closed intervals."""
    total, end = 0, lo - 1
    for a, b in sorted(intervals):
        a, b = max(a, lo, end + 1), min(b, hi)
        if b >= a:
            total += b - a + 1
            end = b
    return total


def messages_of(trace):
    out = []
    for step in trace.get('steps', []):
        tcs = step.get('tool_calls') or []
        out += [str(step.get('message') or step.get('reasoning_content') or '')] * len(tcs)
    return out


def analyse(trace, g, prompt):
    """(reads, regions, files read from the top) of one run. g: the task's CHANGED REGIONS by file; prompt: the task text."""
    calls = calls_of(trace)
    files = set(g)
    for call, _t, parsed in calls:
        if is_read(call):
            ok = isinstance(parsed, dict) and parsed.get('status') == 'ok'
            files.add(norm((parsed.get('filepath') if ok else None) or call['arguments'].get('filepath')))
    files.discard('')
    named = collections.defaultdict(list)     # file -> [(call index, lines)]; index 0 is the task text
    kinds = collections.defaultdict(list)     # file -> [(call index, lines, source of the lines)]
    other = collections.defaultdict(list)
    views = collections.defaultdict(list)
    wrote = {}
    for f in files:
        if f in prompt:
            ln = classify(f, ({'function_name': 'task'}, prompt, None))[2] | link_lines(f, prompt)
            if ln:
                named[f].append((0, ln))
                kinds[f].append((0, ln, 'TASK TEXT'))
    for i, (call, text, parsed) in enumerate(calls, 1):
        name = call.get('function_name')
        cmd = command_of(call)
        if name == 'write_file' and isinstance(call.get('arguments'), dict):
            wrote.setdefault(norm(call['arguments'].get('filepath')), i)
        if name == 'run_command':
            for f in viewed_files(cmd):
                views[f].append(i)
        if is_read(call):
            continue
        for f in files:
            if f not in text and f not in cmd:
                continue
            ln = classify(f, (call, text, parsed))[2]
            if ln:
                named[f].append((i, ln))
                kinds[f].append((i, ln, 'OTHER TOOL' if name != 'run_command' else
                                 'OWN SEARCH' if numbering_command(cmd) else 'COMMAND OUTPUT'))
            ex = diff_lines(f, text) | skill_lines(f, text)
            if ex:
                other[f].append((i, ex))
    shown = collections.defaultdict(list)     # file -> [(call index, start, end)]
    reads, cls_at = [], {}
    for i, (call, _text, parsed) in enumerate(calls, 1):
        if not is_read(call):
            continue
        ok = isinstance(parsed, dict) and parsed.get('status') == 'ok'
        f = norm((parsed.get('filepath') if ok else None) or call['arguments'].get('filepath'))
        s, e = asked(call)
        rec = {'i': i, 'f': f, 's': s, 'e': e, 'first': not shown[f], 'chance': None, 'sub': None,
               'paging': False, 'near': False, 'strict': False, 'total': None, 'hit': None, 'tail': False,
               'held_kinds': {k for j, _ln, k in kinds[f] if j < i}, 'kinds': set()}
        if not ok:
            rec['cls'] = 'FAILED'
            reads.append(rec)
            continue
        rec['total'] = parsed.get('total_lines')
        if f in wrote and wrote[f] < i:
            rec['cls'] = 'OWN FILE'
        elif s is None or s <= 1:
            rec['cls'] = 'TOP'
        else:
            w = min(e, s + CAP - 1) if (e is not None and e >= s) else s + CAP - 1
            earlier = [(a, b) for _j, a, b in shown[f]]
            inside = any(a <= s <= b for a, b in earlier)
            nxt = any(b < s <= b + NEAR for a, b in earlier)
            back = any(s < a <= w + NEAR for a, b in earlier)
            lines = union(named[f], i)
            ex = union(other[f], i)
            rec['strict'] = any(s <= n <= w for n in lines)
            rec['near'] = any(s - NEAR <= n <= w + NEAR for n in lines)
            rec['kinds'] = {k for j, ln, k in kinds[f] if j < i and any(s - NEAR <= n <= w + NEAR for n in ln)}
            near_ex = any(s - NEAR <= n <= w + NEAR for n in ex)
            shell = any(j < i for j in views.get(f, ()))
            rec['paging'] = inside or nxt or back
            rec['sub'] = 'INSIDE' if inside else 'NEXT' if nxt else 'BACK' if back else None
            rec['cls'] = ('PAGING' if rec['paging'] else 'ADDRESSED' if rec['near'] else 'OTHER NUMBER' if near_ex
                          else 'SHELL VIEW' if shell else 'NO NUMBER')
            t = rec['total']
            if isinstance(t, int) and t >= 2 and not shell:
                n_w = w - s + 1
                iv = [(a - n_w - NEAR + 1, b + NEAR) for a, b in earlier] + [(n - n_w - NEAR + 1, n + NEAR) for n in lines | ex]
                rec['chance'] = measure(iv, 2, t) / (t - 1)
        cls_at[i] = rec
        rs, re_ = parsed.get('start_line'), parsed.get('end_line')
        if isinstance(rs, int) and isinstance(re_, int):
            if f in g:
                rec['hit'] = any(not (re_ < a or rs > b) for a, b in g[f])
            rec['tail'] = isinstance(rec['total'], int) and re_ >= rec['total']
            shown[f].append((i, rs, re_))
        reads.append(rec)
    regions = []
    for f, rr in g.items():
        for a, b in rr:
            seen_at = min((i for i, x, y in shown.get(f, []) if not (y < a or x > b)), default=INF)
            how = cls_at[seen_at] if seen_at < INF else None
            held = any(a - NEAR <= n <= b + NEAR for n in union(named[f], seen_at))
            wider = held or any(a - NEAR <= n <= b + NEAR for n in union(other[f], seen_at))
            end = any(a - NEAR <= n <= b + NEAR for n in union(named[f], INF))
            regions.append({'f': f, 'a': a, 'deep': a > CAP, 'opened': bool(shown.get(f)), 'seen': seen_at < INF,
                            'held': held, 'wider': wider, 'held_end': end,
                            'how': (how['cls'] if how else None), 'sub': (how['sub'] if how else None),
                            'how_near': bool(how and how['near']), 'how_paging': bool(how and how['paging']),
                            'reads_to': sum(1 for i, _x, _y in shown.get(f, []) if i <= seen_at) if seen_at < INF else None})
    files_read = []
    for f, rr in shown.items():
        if not rr:
            continue
        first = cls_at[rr[0][0]]
        total = next((cls_at[i]['total'] for i, _a, _b in rr if isinstance(cls_at[i]['total'], int)), None)
        if first['cls'] != 'TOP' or rr[0][1] != 1 or total is None:
            continue
        reach = rr[0][2]
        grew = True
        while grew:
            grew = False
            for _i, a, b in rr:
                if a <= reach + NEAR + 1 and b > reach:
                    reach, grew = b, True
        lines = set()
        for _i, a, b in rr:
            lines.update(range(a, min(b, total) + 1))
        files_read.append({'f': f, 'total': total, 'reach': min(reach, total), 'reads': len(rr),
                           'jumped': any(a > reach + NEAR + 1 for _i, a, _b in rr), 'share': len(lines) / max(total, 1)})
    return reads, regions, files_read


def all_sources():
    """(label, [run dicts]): run = {'task', 'key', 'load', 'resolved' (None when not known)}."""
    out = collections.OrderedDict()
    rec = graphloc_records()
    labels = {'base': 'starter agent, public runs of September (GraphLoc base arm)',
              'skill': 'the same agent with a graph skill, public runs (GraphLoc skill arm)'}
    for r in iter_runs():
        if r['arm'] in labels:
            out.setdefault(labels[r['arm']], []).append(
                {'task': r['task'], 'key': f'run {r["run"]}', 'load': (lambda p=r['path']: load(p)),
                 'resolved': rec.get((r['run'], r['arm'], r['task']), (None, ''))[0]})
    for label, model, paths in sources():
        if 'GraphLoc' in label:
            continue
        for p in paths:
            out.setdefault(f'{label}, Gemma-4-{model}, other team', []).append(
                {'task': p.stem[len('trace_'):], 'key': p.parts[-3], 'load': (lambda p=p: json.load(io.open(p, encoding='utf-8'))),
                 'resolved': None})
    loaded = A.load_root(HERE / 'results' / '14')
    ours = loaded[0] if isinstance(loaded, tuple) else loaded
    for (task, cond, seed), r in sorted(ours.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
        if r[0] is not None:
            out.setdefault(f'our whole runs of pre-registration 14, condition {cond}', []).append(
                {'task': task, 'key': f'seed {seed}', 'load': (lambda t=r[0]: t), 'resolved': truth(r[1].get('resolved'))})
    return out


def rate(by):
    t = boot_ci(by)
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def part1(label, rows):
    ok = [r for r in rows if r['cls'] in CLASSES]
    print(f'   READS {len(rows)}: not of status ok {sum(r["cls"] == "FAILED" for r in rows)} (left out), of an OWN FILE '
          f'{sum(r["cls"] == "OWN FILE" for r in rows)} (apart); classed {len(ok)}, of which the first READ of its file '
          f'{sum(r["first"] for r in ok)}')
    print(f'      {"class":<14}{"all reads":<24}{"first read of the file":<26}later reads')
    first = [r for r in ok if r['first']]
    later = [r for r in ok if not r['first']]
    for c in CLASSES:
        cells = [pct(sum(r['cls'] == c for r in sel), len(sel)) for sel in (ok, first, later)]
        print(f'      {c:<14}{cells[0]:<24}{cells[1]:<26}{cells[2]}')
    past = [r for r in ok if r['cls'] != 'TOP']
    pg = [r for r in past if r['cls'] == 'PAGING']
    print(f'      PAGING by kind: ' + ', '.join(f'{k} {sum(r["sub"] == k for r in pg)}' for k in ('INSIDE', 'NEXT', 'BACK'))
          + f'; PAGING and also ADDRESSED {sum(r["near"] for r in pg)}; ADDRESSED, STRICT '
          f'{pct(sum(r["strict"] for r in past if r["cls"] == "ADDRESSED"), sum(r["cls"] == "ADDRESSED" for r in past))}')
    jumps = [r for r in past if r['cls'] != 'PAGING']
    blind = [r for r in past if r['cls'] == 'NO NUMBER']
    addr = [r for r in past if r['cls'] == 'ADDRESSED']
    print(f'      JUMPS {len(jumps)}: ' + ', '.join(f'{c} {pct(sum(r["cls"] == c for r in jumps), len(jumps))}' for c in CLASSES[2:])
          + f'; runs with a READ of class NO NUMBER {len({(r["task"], r["key"]) for r in blind})}')
    print(f'      a start that is a multiple of 100: NO NUMBER {pct(sum(r["s"] % 100 == 0 for r in blind), len(blind))}, ADDRESSED '
          f'{pct(sum(r["s"] % 100 == 0 for r in addr), len(addr))}; the RETURNED RANGE reaches the last line of the file: NO NUMBER '
          f'{pct(sum(r["tail"] for r in blind), len(blind))}, ADDRESSED {pct(sum(r["tail"] for r in addr), len(addr))}')
    print(f'      ADDRESSED READS by the SOURCE of a NAMED LINE near the WINDOW (a READ can count under several): '
          + ', '.join(f'{k} {sum(k in r["kinds"] for r in addr)}' for k in KINDS) + f'; OWN SEARCH and nothing else '
          f'{pct(sum(r["kinds"] == {"OWN SEARCH"} for r in addr), len(addr))}')
    held = [r for r in first if r['held_kinds']]
    cells = []
    for nm, test in (('from its OWN SEARCH', lambda k: 'OWN SEARCH' in k),
                     ('from COMMAND OUTPUT and no OWN SEARCH', lambda k: 'COMMAND OUTPUT' in k and 'OWN SEARCH' not in k),
                     ('from the TASK TEXT only', lambda k: k == {'TASK TEXT'})):
        sel = [r for r in held if test(r['held_kinds'])]
        cells.append(f'{nm}: starts at a NAMED LINE {pct(sum(r["cls"] == "ADDRESSED" for r in sel), len(sel))}')
    print(f'      first READ of a file for which the run held a NAMED LINE ({len(held)}): ' + '; '.join(cells))
    gold_reads = [r for r in ok if r['hit'] is not None]
    print(f'      READS of a file the fix changes {len(gold_reads)}; HIT, by class: '
          + ', '.join(f'{c} {pct(sum(r["hit"] for r in gold_reads if r["cls"] == c), sum(r["cls"] == c for r in gold_reads))}'
                      for c in CLASSES if any(r['cls'] == c for r in gold_reads)))
    by = collections.defaultdict(list)
    for r in past:
        by[r['task']].append(int(r['cls'] == 'NO NUMBER'))
    ch = [r for r in past if r['chance'] is not None]
    print(f'      of {len(past)} READS past line 1: NO NUMBER {sum(r["cls"] == "NO NUMBER" for r in past)}, by task {rate(by)}')
    if ch:
        exp = 1 - sum(r['chance'] for r in ch) / len(ch)
        print(f'      of the {len(ch)} with no earlier SHELL VIEW and a known file length: NO NUMBER '
              f'{pct(sum(r["cls"] == "NO NUMBER" for r in ch), len(ch))}; expected if starts were placed at random {100 * exp:.1f}%')


def median(v):
    return sorted(v)[len(v) // 2] if v else float('nan')


def part1b(label, files):
    long = [x for x in files if x['total'] > CAP]
    print(f'   files whose first READ was from the top: {len(files)}; longer than 150 lines {len(long)}')
    if not long:
        return
    one = [x for x in long if x['reach'] <= CAP + NEAR]
    b2 = [x for x in long if CAP + NEAR < x['reach'] <= 2 * CAP + NEAR and x['reach'] < x['total']]
    b3 = [x for x in long if 2 * CAP + NEAR < x['reach'] <= 3 * CAP + NEAR and x['reach'] < x['total']]
    more = [x for x in long if x['reach'] > 3 * CAP + NEAR and x['reach'] < x['total']]
    end = [x for x in long if x['reach'] > CAP + NEAR and x['reach'] >= x['total']]
    print(f'      the STRETCH FROM THE TOP ends: in the first 150 lines {pct(len(one), len(long))}; in lines 151 to 300 {len(b2)}; '
          f'in lines 301 to 450 {len(b3)}; further, short of the end {len(more)}; at the end of the file {len(end)}')
    print(f'      of those {len(one)} that end in the first 150 lines: the run JUMPED in the file {sum(x["jumped"] for x in one)}, '
          f'read nothing else of it {sum(not x["jumped"] for x in one)}; of all {len(long)}: JUMPED {pct(sum(x["jumped"] for x in long), len(long))}')
    big = [x for x in long if x['total'] > 600]
    print(f'      share of a file the run was shown: median {100 * median([x["share"] for x in long]):.0f}%; files longer than 600 lines '
          f'({len(big)}): median {100 * median([x["share"] for x in big]):.0f}%, STRETCH FROM THE TOP ends in the first 150 lines '
          f'{pct(sum(x["reach"] <= CAP + NEAR for x in big), len(big))}')


def part2(label, regs, runs):
    deep = [x for x in regs if x['deep']]
    top = [x for x in regs if not x['deep']]
    print(f'   CHANGED REGIONS {len(regs)} in {len(runs)} runs: IN THE FIRST 150 LINES {len(top)}, DEEP {len(deep)}')
    for name, sel in (('in an OPENED FILE', [x for x in regs if x['opened']]),):
        t = [x for x in sel if not x['deep']]
        d = [x for x in sel if x['deep']]
        h = [x for x in d if x['held']]
        n = [x for x in d if not x['held']]
        print(f'   {name}: {len(sel)}')
        print(f'      IN THE FIRST 150 LINES: SHOWN {pct(sum(x["seen"] for x in t), len(t))}')
        bh, bn = collections.defaultdict(list), collections.defaultdict(list)
        for x in h:
            bh[x['task']].append(int(x['seen']))
        for x in n:
            bn[x['task']].append(int(x['seen']))
        print(f'      DEEP, HELD A NUMBER:    SHOWN {pct(sum(x["seen"] for x in h), len(h))}, by task {rate(bh)}')
        print(f'      DEEP, no number held:   SHOWN {pct(sum(x["seen"] for x in n), len(n))}, by task {rate(bn)}')
        dd = diff_ci(bh, bn)
        if dd[0] is not None:
            print(f'      difference, by task: {100 * dd[0]:+.1f} points [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}]')
        he = [x for x in d if x['held_end']]
        ne = [x for x in d if not x['held_end']]
        print(f'      (a NAMED LINE within 10 lines by the end of the run, before or after the region was shown: SHOWN '
              f'{pct(sum(x["seen"] for x in he), len(he))}; none by the end: SHOWN {pct(sum(x["seen"] for x in ne), len(ne))})')
        sn = [x for x in n if x['seen']]
        hows = collections.Counter(x['how'] for x in sn)
        subs = collections.Counter(x['sub'] for x in sn if x['how'] == 'PAGING')
        print(f'      HOW the {len(sn)} SHOWN with no number held were first shown: '
              + ', '.join(f'{c} {v}' for c, v in hows.most_common())
              + (f' (PAGING: ' + ', '.join(f'{k} {v}' for k, v in subs.most_common()) + ')' if subs else ''))
        hs = [x for x in h if x['seen']]
        hows = collections.Counter(x['how'] for x in hs)
        print(f'      HOW the {len(hs)} SHOWN that HELD A NUMBER were first shown: ' + ', '.join(f'{c} {v}' for c, v in hows.most_common()))
        print(f'      the READ that first showed a DEEP region ({len(sn) + len(hs)}): continued or overlapped an earlier read and no '
              f'NAMED LINE near its WINDOW {sum(x["how_paging"] and not x["how_near"] for x in sn + hs)}; both '
              f'{sum(x["how_paging"] and x["how_near"] for x in sn + hs)}; a NAMED LINE near its WINDOW only '
              f'{sum(x["how_near"] and not x["how_paging"] for x in sn + hs)}; neither {sum(not x["how_near"] and not x["how_paging"] for x in sn + hs)}')
        buckets = (('151 to 300', 151, 300), ('301 to 450', 301, 450), ('451 to 900', 451, 900), ('past 900', 901, INF))
        for nm, grp in (('HELD A NUMBER', h), ('no number held', n)):
            print(f'      {nm}, SHOWN by the line the region starts at: '
                  + '; '.join(f'{bn}: {pct(sum(x["seen"] for x in grp if lo <= x["a"] <= hi), sum(lo <= x["a"] <= hi for x in grp))}'
                              for bn, lo, hi in buckets))
        both = sn + hs
        for nm, grp in (('continued or overlapped an earlier read, no NAMED LINE near', [x for x in both if x['how_paging'] and not x['how_near']]),
                        ('a NAMED LINE near its WINDOW', [x for x in both if x['how_near']])):
            print(f'      READS TO REACH, mean, when the first showing READ {nm}: '
                  + '; '.join(f'{bn}: {sum(x["reads_to"] for x in grp if lo <= x["a"] <= hi) / max(1, sum(lo <= x["a"] <= hi for x in grp)):.1f} '
                              f'({sum(lo <= x["a"] <= hi for x in grp)})' for bn, lo, hi in buckets))
        w = [x for x in n if x['wider']]
        print(f'      of the DEEP with no number held, WIDER holds one for {len(w)}, SHOWN {pct(sum(x["seen"] for x in w), len(w))}')
    un = [x for x in regs if not x['opened']]
    print(f'   in a file the run never opened: {len(un)} (DEEP {sum(x["deep"] for x in un)}); HELD A NUMBER by the end of the run '
          f'{pct(sum(x["held_end"] for x in un), len(un))}')
    nh = [x for x in deep if not x['seen']]
    print(f'   DEEP and never SHOWN: {len(nh)}; in an OPENED FILE {pct(sum(x["opened"] for x in nh), len(nh))}; HELD A NUMBER by the end '
          f'of the run {pct(sum(x["held_end"] for x in nh), len(nh))}')
    scored = [r for r in runs if r['resolved'] is not None and r['regs']]
    if scored:
        for name, test in (('every DEEP region HELD A NUMBER by the end of the run (runs of tasks with a DEEP region)',
                            lambda r: (None if not any(x['deep'] for x in r['regs']) else all(x['held_end'] for x in r['regs'] if x['deep']))),
                           ('every region is IN THE FIRST 150 LINES of an OPENED FILE or HELD A NUMBER by the end of the run',
                            lambda r: all((not x['deep'] and x['opened']) or x['held_end'] for x in r['regs'])),
                           ('every region SHOWN', lambda r: all(x['seen'] for x in r['regs']))):
            yes = [r for r in scored if test(r) is True]
            no = [r for r in scored if test(r) is False]
            print(f'   {name}: yes, resolved {pct(sum(r["resolved"] for r in yes), len(yes))}; no, resolved {pct(sum(r["resolved"] for r in no), len(no))}')


def part3(label, runs):
    """Per task: where the fix lies, against whether the task's runs were shown all of it."""
    runs = [r for r in runs if r['regs']]
    if not runs:
        return
    geo = {}
    for r in runs:
        regs = r['regs']
        geo[r['task']] = (max(x['a'] for x in regs), len(regs), len({x['f'] for x in regs}))
    print(f'{label}: runs of tasks with a CHANGED REGION {len(runs)}, tasks {len(geo)}')

    def line(name, test):
        sel = [r for r in runs if test(geo[r['task']])]
        tasks = len({r['task'] for r in sel})
        every = sum(all(x['seen'] for x in r['regs']) for r in sel)
        res = [r for r in sel if r['resolved'] is not None]
        tail = f'; resolved {pct(sum(r["resolved"] for r in res), len(res))}' if res else ''
        print(f'      {name}: tasks {tasks}; runs shown every region {pct(every, len(sel))}{tail}')

    print('   by the line at which the deepest CHANGED REGION of the task starts')
    line('in the first 150 lines', lambda t: t[0] <= CAP)
    line('151 to 450', lambda t: CAP < t[0] <= 450)
    line('451 to 900', lambda t: 450 < t[0] <= 900)
    line('past 900', lambda t: t[0] > 900)
    print('   by the number of CHANGED REGIONS of the task')
    line('1', lambda t: t[1] == 1)
    line('2 or 3', lambda t: 2 <= t[1] <= 3)
    line('4 to 9', lambda t: 4 <= t[1] <= 9)
    line('10 or more', lambda t: t[1] >= 10)
    print('   by the number of files the fix changes')
    line('1', lambda t: t[2] == 1)
    line('2', lambda t: t[2] == 2)
    line('3 or more', lambda t: t[2] >= 3)
    print('   tasks with one CHANGED REGION, by the line at which it starts')
    line('in the first 150 lines', lambda t: t[1] == 1 and t[0] <= CAP)
    line('151 to 450', lambda t: t[1] == 1 and CAP < t[0] <= 450)
    line('451 to 900', lambda t: t[1] == 1 and 450 < t[0] <= 900)
    line('past 900', lambda t: t[1] == 1 and t[0] > 900)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', action='store_true')
    args = ap.parse_args()
    gold = gold_regions()
    texts = task_texts()
    srcs = all_sources()
    print('WHERE EVERY FILE READ STARTS, AND THE PLACES OF THE FIX BY WHETHER THE RUN HELD A LINE NUMBER FOR THEM (EXPLORATORY)')
    print()
    samples = {}
    done = {}
    for label, runs in srcs.items():
        rows, regs, kept, files_all = [], [], [], []
        for r in runs:
            trace = r['load']()
            g = gold.get(r['task'], {})
            reads, rr, fr = analyse(trace, g, texts.get(r['task'], ''))
            files_all += fr
            for x in reads:
                x.update(task=r['task'], key=r['key'])
            for x in rr:
                x.update(task=r['task'], key=r['key'])
            rows += reads
            regs += rr
            kept.append({'task': r['task'], 'resolved': r['resolved'], 'regs': rr})
            if args.sample:
                for x in reads:
                    if x['cls'] == 'NO NUMBER':
                        samples.setdefault(label, []).append((r, x))
        done[label] = (rows, regs, kept, files_all)
    print('1. Where a READ starts')
    for label, (rows, regs, kept, files_all) in done.items():
        print(f'{label}: runs {len(kept)}, tasks {len({k["task"] for k in kept})}')
        part1(label, rows)
        part1b(label, files_all)
    print()
    print('2. The places of the fix')
    for label, (rows, regs, kept, files_all) in done.items():
        if not regs:
            continue
        print(f'{label}')
        part2(label, regs, kept)
    print()
    print('3. Where the fix lies, by task, and whether a run was shown all of it')
    for label, (rows, regs, kept, files_all) in done.items():
        part3(label, kept)
    if args.sample:
        rng = random.Random(0)
        for label, items in samples.items():
            print()
            print(f'SAMPLE, {label}: {min(20, len(items))} of {len(items)} READS of class NO NUMBER')
            for r, x in rng.sample(items, min(20, len(items))):
                trace = r['load']()
                calls = calls_of(trace)
                msgs = messages_of(trace)
                i = x['i']
                print(f'--- {r["task"]} {r["key"]} call {i}: {x["f"]} asked {x["s"]}..{x["e"]} of {x["total"]} lines; first read of the file: {x["first"]}')
                if i - 1 < len(msgs) and msgs[i - 1]:
                    print('    said: ' + msgs[i - 1][:400].replace('\n', ' '))
                for j in range(max(0, i - 4), i - 1):
                    call, text, _p = calls[j]
                    print(f'    [{j + 1}] {call.get("function_name")} {json.dumps(call.get("arguments"), ensure_ascii=False)[:200]}')
                    print('         -> ' + (text or '')[:260].replace('\n', ' | '))


if __name__ == '__main__':
    main()
