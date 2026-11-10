"""Where a first read of a file starts in other teams' public runs, by what the agent had just been shown (EXPLORATORY).

Usage: py -I -X utf8 analysis/public_runs_address.py

Nothing here was pre-registered and no model is run. The script reads public traces of Gemma 4 agents on this
benchmark, written by the competition harness (ATIF JSON, one file per run), and prints counts.

Sources (local copies, not redistributed; see analysis/results/public/README.md for how each was obtained):
  data/graphloc/out/<notebook>/e2e/results/<arm>/w<k>/traces/trace_<task>.json
      the 636 traces published with the GraphLoc notebooks (Sep 2026): arm `base` is the starter agent, arm
      `skill` is the same agent with a graph-localization skill. Gemma-4-31B.
  data/public_traces/vanductan__gemma4-patchpool/traces/<run>/traces/trace_<task>.json
      a custom agent (Oct 2026); run names begin with the model (31b, 12b, e4b).
  data/public_traces/niraberman__gemma4-commit-anatomy-traces/arena_v2*/results_*/traces/trace_<task>.json
      another custom agent (Oct to Nov 2026). Gemma-4-31B.
  data/public_traces/petermugoya__what-the-agent-saw/data/main*_{calls,reads}.jsonl
      per-call and per-read tables of 1,329 runs of the starter agent (Oct 2026). They hold no tool output, so
      only the kind of the call just before a read is known; their `lo` is the first line the model asked for.

Rules (written before the counts below were looked at a second time; an independent script written from the same
text is analysis/rederive_public_address.py if present):
  READ            a `read_file` call. Its file is `filepath` without a leading `/workspace/` or `./`. Its asked
                  start and end are the arguments named `start_line` and `end_line` once quotes, backslashes and
                  whitespace are removed from the argument name (some calls carry a mangled name).
  FIRST READ      no earlier `read_file` on that file in the run, and no earlier `run_command` that names the file
                  and uses a viewer (cat, head, tail, sed, nl, less, more, awk).
  JUST BEFORE     the tool call that comes immediately before the read in the trace, with its result.
  ADDRESS         the result just before names the file together with a line number, in one of three ways:
                  (i) the file's path followed by `:<number>:` or `-<number>-`, as `grep -n` prints across files
                  (a directory prefix or `./` before the path is allowed); (ii) a traceback, the path followed by
                  `", line <number>`; (iii) the call just before is a `run_command` that names the file and runs
                  grep with the `-n` flag, `cat -n` or `nl`, and its output has lines that begin with a number
                  followed by `:`, `-` or a tab. The named lines are collected.
  GRAPH NAME      not ADDRESS; the call just before is one of the three graph tools and its result holds the
                  file's dotted module followed by a dot.
  PATH ONLY       not ADDRESS and not GRAPH NAME; the file's path appears in the result or in the command.
  OTHER           none of these.
  RANGED          the asked start is greater than 1.
  COVERS          RANGED, and a named line lies between the asked start and the smaller of the asked end and
                  start + 149 (start + 149 when no end was asked): the harness returns at most 150 lines.
The graph skill of the GraphLoc `skill` arm prints its candidates as `<rank> <score> <path>:<line> <name>`, with no
second delimiter after the line number, so rule (i) does not count it. It is reported apart (section 6).

Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analyze_forks.boot_ci, diff_ci).
"""
import collections
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import boot_ci, diff_ci  # noqa: E402

DATA = HERE.parent / 'data'
BOUNDS = ('start_line', 'end_line')
GRAPH_TOOLS = ('get_code_neighbors', 'get_code_subgraph', 'search_similar_code')
VIEWERS = ('cat', 'head', 'tail', 'sed', 'nl', 'less', 'more', 'awk')
STRIP = re.compile('[\\\\"\'\\s]')
NUMBERED = re.compile(r'^\s*(\d+)[:\-\t]', re.M)
PATHCH = r'A-Za-z0-9_.\-'
SKILL_LINE = re.compile(r'^\s*\d+\s+[\d.]+\s+(\S+?):(\d+)\s+(\S+)\s*$', re.M)
CLASSES = ('ADDRESS', 'PATH ONLY', 'GRAPH NAME', 'OTHER')


def clean(name):
    return STRIP.sub('', str(name))


def norm(path):
    p = str(path or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def is_read(call):
    return bool(call) and call.get('function_name') == 'read_file' and isinstance(call.get('arguments'), dict)


def asked(call):
    """(start, end) as the model wrote them; None where absent or not a number."""
    out = {}
    for k, v in call['arguments'].items():
        k = clean(k)
        if k in BOUNDS and k not in out:
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = None
    return out.get('start_line'), out.get('end_line')


def window(start, end):
    return start, (min(end, start + 149) if end is not None else start + 149)


def strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k != 'extra':
                strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            strings(v, out)


def result_of(step):
    """(text, parsed dict or None) of a step's tool result. ATIF stores the result as a JSON string in `content`."""
    obs = step.get('observation')
    content = obs.get('content') if isinstance(obs, dict) else obs
    if content is None and isinstance(obs, dict) and obs.get('results'):
        content = [r.get('content') for r in obs['results'] if isinstance(r, dict)]
    parsed = None
    out = []
    for item in (content if isinstance(content, list) else [content]):
        d = item
        if isinstance(item, str):
            try:
                d = json.loads(item)
            except ValueError:
                d = item
        if isinstance(d, dict) and isinstance(d.get('result'), str):  # the older harness wrapped a JSON string
            try:
                d = json.loads(d['result'])
            except ValueError:
                pass
        if isinstance(d, dict) and parsed is None:
            parsed = d
        strings(d, out)
    return '\n'.join(out), parsed


def calls_of(trace):
    """The run's tool calls in order: (call, result text, parsed result). A step's result goes to its last call."""
    out = []
    for step in trace.get('steps', []):
        tcs = step.get('tool_calls') or []
        if not tcs:
            continue
        text, parsed = result_of(step)
        for i, tc in enumerate(tcs):
            last = i == len(tcs) - 1
            out.append((tc, text if last else '', parsed if last else None))
    return out


def command_of(call):
    args = (call or {}).get('arguments')
    return str(args.get('command') or '') if isinstance(args, dict) else ''


def names_file(text, f):
    """True if the path f appears in text as a whole path (a directory prefix is allowed)."""
    return re.search(r'(?<![' + PATHCH + r'])' + re.escape(f) + r'(?![A-Za-z0-9_])', text) is not None or \
        re.search(r'/' + re.escape(f) + r'(?![A-Za-z0-9_])', text) is not None


def numbering_command(cmd):
    """True if a pipeline segment of cmd runs grep with -n, cat -n or nl."""
    for seg in re.split(r'[|;&\n()`]+', cmd):
        toks = seg.split()
        if not toks:
            continue
        head = toks[0]
        if head == 'git' and len(toks) > 1 and toks[1] == 'grep':
            head, toks = 'grep', toks[1:]
        flags = [t for t in toks[1:] if t.startswith('-') and not t.startswith('--')]
        if head in ('grep', 'egrep', 'fgrep', 'rg') and (any('n' in t for t in flags) or '--line-number' in toks):
            return True
        if head == 'cat' and any('n' in t for t in flags):
            return True
        if head == 'nl':
            return True
    return False


def classify(f, prev):
    """(class, way, named lines) for file f given the call just before and its result text."""
    if prev is None:
        return 'OTHER', None, set()
    call, text, _ = prev
    cmd = command_of(call)
    esc = re.escape(f)
    way_i = {int(m.group(1)) for m in re.finditer(r'(?:(?<![' + PATHCH + r'])|(?<=/))' + esc + r'[:\-](\d+)[:\-]', text)}
    way_ii = {int(m.group(1)) for m in re.finditer(esc + r'",? line (\d+)', text)}
    way_iii = set()
    if call.get('function_name') == 'run_command' and names_file(cmd, f) and numbering_command(cmd):
        way_iii = {int(m.group(1)) for m in NUMBERED.finditer(text)}
    lines = way_i | way_ii | way_iii
    if lines:
        return 'ADDRESS', ('i' if way_i else 'ii' if way_ii else 'iii'), lines
    if call.get('function_name') in GRAPH_TOOLS:
        mod = f[:-3].replace('/', '.') if f.endswith('.py') else None
        if mod and re.search(r'(?<![A-Za-z0-9_])' + re.escape(mod) + r'\.', text):
            return 'GRAPH NAME', None, set()
    if names_file(text, f) or names_file(cmd, f):
        return 'PATH ONLY', None, set()
    return 'OTHER', None, set()


def viewed_files(cmd):
    """Path-like tokens of a command that uses a viewer."""
    if not re.search(r'(?<![A-Za-z0-9_])(' + '|'.join(VIEWERS) + r')(?![A-Za-z0-9_])', cmd):
        return []
    return [norm(t) for t in re.findall(r'[\w./\-]+\.\w+', cmd)]


def sources():
    """(group label, model, list of trace paths)."""
    g = DATA / 'graphloc' / 'out'
    p = DATA / 'public_traces'
    van = p / 'vanductan__gemma4-patchpool' / 'traces'
    nir = p / 'niraberman__gemma4-commit-anatomy-traces'
    return [
        ('starter agent (GraphLoc base arm, Sep)', '31B', sorted(g.glob('*/e2e/results/base/w*/traces/trace_*.json'))),
        ('custom agent 1 (Oct)', '31B', sorted(van.glob('31b_*/traces/trace_*.json'))),
        ('custom agent 2 (Oct to Nov)', '31B', sorted(nir.glob('arena_v2*/results_*/traces/trace_*.json'))),
        ('custom agent 1 (Oct)', '12B', sorted(van.glob('12b_*/traces/trace_*.json'))),
        ('custom agent 1 (Oct)', 'E4B', sorted(van.glob('e4b_*/traces/trace_*.json'))),
        ('graph skill (GraphLoc skill arm, Sep)', '31B', sorted(g.glob('*/e2e/results/skill/w*/traces/trace_*.json'))),
    ]


def pct(m, n):
    return f'{m} of {n} ({100 * m / n:.1f}%)' if n else '0 of 0'


def ci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.1f}% [{100 * t[1]:.1f}, {100 * t[2]:.1f}]'


def dci(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.1f} points [{100 * t[1]:+.1f}, {100 * t[2]:+.1f}]'


def main():
    recs = []        # one dict per read
    files_read = collections.Counter()
    failed = collections.Counter()
    skill = collections.Counter()
    skill_runs = 0
    for label, model, paths in sources():
        key = f'{label}, {model}'
        for path in paths:
            try:
                trace = json.load(io.open(path, encoding='utf-8'))
            except (ValueError, OSError):
                failed[key] += 1
                continue
            files_read[key] += 1
            task = path.stem[len('trace_'):]
            calls = calls_of(trace)
            seen = set()
            had_skill = False
            for i, (call, text, parsed) in enumerate(calls):
                if is_read(call):
                    f = norm(call['arguments'].get('filepath'))
                    start, end = asked(call)
                    ranged = start is not None and start > 1
                    cls, way, lines = classify(f, calls[i - 1] if i else None)
                    prev_cmd = command_of(calls[i - 1][0]) if i else ''
                    prev_fn = calls[i - 1][0].get('function_name') if i else None
                    lo, hi = window(start, end) if ranged else (None, None)
                    rec = {'source': key, 'label': label, 'model': model, 'task': task, 'first': f not in seen, 'cls': cls,
                           'way': way, 'ranged': ranged, 'covers': bool(ranged and any(lo <= x <= hi for x in lines)),
                           'near': bool(ranged and any(0 <= x - start <= 30 for x in lines)),
                           'exact': bool(ranged and start in lines), 'prev_fn': prev_fn, 'prev_cmd': prev_cmd,
                           'chance': None}
                    total = parsed.get('total_lines') if isinstance(parsed, dict) else None
                    if rec['first'] and cls == 'ADDRESS' and ranged and isinstance(total, int) and total > 0:
                        length = min(hi - lo + 1, total)
                        starts = total - length + 1
                        named = [x for x in lines if 1 <= x <= total]
                        good = sum(1 for s0 in range(1, starts + 1) if any(s0 <= x <= s0 + length - 1 for x in named))
                        rec['chance'] = good / starts
                    recs.append(rec)
                    seen.add(f)
                elif call.get('function_name') == 'run_command':
                    seen.update(viewed_files(command_of(call)))
                # the graph skill's own answers (section 6)
                if call.get('function_name') == 'run_skill_script' and 'localize' in json.dumps(call.get('arguments')):
                    cands = [(norm(a), int(b)) for a, b, _ in SKILL_LINE.findall(text)]
                    if cands:
                        had_skill = True
                        skill['answers'] += 1
                        nxt = calls[i + 1][0] if i + 1 < len(calls) else None
                        if nxt is not None and is_read(nxt):
                            f2 = norm(nxt['arguments'].get('filepath'))
                            listed = [ln for pth, ln in cands if pth == f2]
                            if listed:
                                skill['reads a listed file'] += 1
                                skill['first read of that file'] += f2 not in seen
                                s2, e2 = asked(nxt)
                                if s2 is not None and s2 > 1:
                                    skill['asks past line 1'] += 1
                                    lo2, hi2 = window(s2, e2)
                                    skill['covers a listed line'] += any(lo2 <= ln <= hi2 for ln in listed)
            skill_runs += had_skill

    order = [f'{label}, {model}' for label, model, _ in sources()]
    main31 = [k for k in order if k.endswith('31B') and 'skill' not in k]

    print('PUBLIC RUNS: where a first read of a file starts, by what the result just before said about the file (EXPLORATORY)')
    print()
    print('0. Traces read')
    for k in order:
        print(f'   {k:<46} {files_read[k]:>4} traces, {failed[k]} unreadable')

    print()
    print('1. First reads, by source and class: reads, of which RANGED (asked start past line 1)')
    for k in order:
        for cls in CLASSES:
            sel = [r for r in recs if r['source'] == k and r['first'] and r['cls'] == cls]
            if sel:
                print(f'   {k:<46} {cls:<11} {pct(sum(r["ranged"] for r in sel), len(sel))}')

    print()
    print('2. Gemma-4-31B, the three sources whose addresses are grep -n output, tracebacks or numbered lines')
    first31 = [r for r in recs if r['source'] in main31 and r['first']]
    by = {cls: collections.defaultdict(list) for cls in CLASSES}
    for r in first31:
        by[r['cls']][r['task']].append(int(r['ranged']))
    for cls in CLASSES:
        sel = [r for r in first31 if r['cls'] == cls]
        print(f'   {cls:<11} {pct(sum(r["ranged"] for r in sel), len(sel)):<22} by task: {ci(boot_ci(by[cls]))}; '
              f'{len(by[cls])} tasks, mean of per-task shares '
              f'{100 * sum(sum(v) / len(v) for v in by[cls].values()) / max(1, len(by[cls])):.1f}%')
    print(f'   ADDRESS minus PATH ONLY, by task: {dci(diff_ci(by["ADDRESS"], by["PATH ONLY"]))}')

    print()
    print('3. The same first reads after an ADDRESS that are RANGED: do they go to a named line?')
    sel = [r for r in first31 if r['cls'] == 'ADDRESS' and r['ranged']]
    n = len(sel)
    print(f'   cover a named line:                         {pct(sum(r["covers"] for r in sel), n)}')
    print(f'   start 0 to 30 lines before a named line:    {pct(sum(r["near"] for r in sel), n)}')
    print(f'   start exactly on a named line:              {pct(sum(r["exact"] for r in sel), n)}')
    ch = [r for r in sel if r['chance'] is not None]
    if ch:
        print(f'   where the read\'s own result gives the file length ({len(ch)} reads): cover a named line '
              f'{100 * sum(r["covers"] for r in ch) / len(ch):.1f}%; a window of the same length placed uniformly at random in '
              f'the file would {100 * sum(r["chance"] for r in ch) / len(ch):.1f}% of the time')

    print()
    print('4. The same first reads after an ADDRESS, by way (the first that applies)')
    for way, name in (('i', 'path:<number>: across files'), ('ii', 'traceback'), ('iii', 'numbered lines of the named file')):
        sel = [r for r in first31 if r['cls'] == 'ADDRESS' and r['way'] == way]
        print(f'   ({way}) {name:<34} {pct(sum(r["ranged"] for r in sel), len(sel))}')

    print()
    print('5. Inside one stage: the call just before is a search (grep, rg, ag) in both rows')
    for group, test in (('a search', lambda c: re.search(r'(?<![A-Za-z0-9_])(grep|rg|ag)(?![A-Za-z0-9_])', c)),
                        ('a listing (find, ls, tree)', lambda c: re.search(r'(?<![A-Za-z0-9_])(find|ls|tree|fd)(?![A-Za-z0-9_])', c)
                         and not re.search(r'(?<![A-Za-z0-9_])(grep|rg|ag)(?![A-Za-z0-9_])', c))):
        for cls, word in (('ADDRESS', 'with a line number'), ('PATH ONLY', 'without a line number')):
            for scope, srcs in (('three 31B sources', main31), ('starter agent alone', main31[:1])):
                sel = [r for r in recs if r['source'] in srcs and r['first'] and r['cls'] == cls
                       and r['prev_fn'] == 'run_command' and test(r['prev_cmd'])]
                if sel:
                    print(f'   just before: {group:<27} its output names the file {word:<22} {scope:<20} '
                          f'{pct(sum(r["ranged"] for r in sel), len(sel))}')

    print()
    print('6. A public graph skill that prints `<rank> <score> <path>:<line> <name>` (GraphLoc skill arm, 318 runs)')
    print(f'   runs with at least one skill answer listing candidates: {skill_runs}')
    print(f'   skill answers listing candidates:                       {skill["answers"]}')
    print(f'   the next call reads a listed file:                      {pct(skill["reads a listed file"], skill["answers"])}')
    print(f'      of these, the first read of that file:               {skill["first read of that file"]}')
    print(f'      of these, RANGED:                                    {pct(skill["asks past line 1"], skill["reads a listed file"])}')
    print(f'      of these, the window covers a listed line:           {skill["covers a listed line"]}')
    print(f'   the next call lands on a listed line:                   {pct(skill["covers a listed line"], skill["answers"])}')

    print()
    print('7. Reads that are not the first read of the file, by source and class')
    for k in order:
        for cls in CLASSES:
            sel = [r for r in recs if r['source'] == k and not r['first'] and r['cls'] == cls]
            if sel:
                print(f'   {k:<46} {cls:<11} {pct(sum(r["ranged"] for r in sel), len(sel))}')

    tables = DATA / 'public_traces' / 'petermugoya__what-the-agent-saw' / 'data'
    print()
    print('8. Tables of 1,329 runs of the starter agent (no tool output published): first read_file reads by the kind')
    print('   of the call just before; RANGED = the first line asked for is past line 1')
    if not tables.exists():
        print('   (tables not found locally: skipped)')
    else:
        tot = collections.defaultdict(lambda: [0, 0])
        for name in ('main1', 'main2', 'main3'):
            kinds = {}
            for line in io.open(tables / f'{name}_calls.jsonl', encoding='utf-8'):
                c = json.loads(line)
                kinds[(c['cell'], c['instance_id'], c['call'])] = c
            for line in io.open(tables / f'{name}_reads.jsonl', encoding='utf-8'):
                r = json.loads(line)
                if r.get('via') != 'read_file' or not r.get('first_read'):
                    continue
                prev = kinds.get((r['cell'], r['instance_id'], r['call'] - 1))
                if prev is None:
                    kind = 'no call before'
                elif prev.get('kind') == 'graph':
                    kind = 'a graph tool, answer of 20 characters or more' if (prev.get('obs_chars') or 0) >= 20 \
                        else 'a graph tool, answer under 20 characters'
                else:
                    kind = str(prev.get('kind'))
                tot[kind][1] += 1
                tot[kind][0] += (r.get('lo') or 1) > 1
        for kind, (m, n) in sorted(tot.items(), key=lambda kv: -kv[1][1]):
            print(f'   just before: {kind:<46} {pct(m, n)}')


if __name__ == '__main__':
    main()
