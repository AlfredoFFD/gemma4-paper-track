"""Where the arguments of an agent's tool calls come from, and the places of the fix that the task names (EXPLORATORY).

Usage: py -I -X utf8 analysis/explore_arguments.py             the report
       py -I -X utf8 analysis/explore_arguments.py --sample    the report, then first uses of class NEITHER, to read
                                                               by hand

Nothing here was pre-registered and no model is run. The runs are the eight sets of whole runs of
analysis/explore_read_starts.py (other teams' public runs and our whole runs of pre-registration 14). The question
of part 1: when a call points at something (a file, a line, a word to search for, a graph node, the text an edit
replaces), had that string been given to the run, or did the run produce it? Part 2: are the places of the fix that
the task statement names shown more often than the others?

Rules.
  CONTEXT at a call  the text the run had been given before that call: its system prompt, its task prompt, and the
                     result of every earlier tool call. The agent's own messages and the arguments of its own
                     earlier calls are not CONTEXT. Our stored traces hold a checksum in place of each prompt; the
                     text is recovered by that checksum from a public trace (the system prompt is the same) and
                     from analysis/fork_states_w/first_call_states.jsonl (the task prompts). One other team's
                     traces hold a placeholder where the task text stood; the task statement of data/tasks.jsonl is
                     added there. The current task prompt lists the workspace's files to three levels; the
                     September prompt's list stops before the source files.
  FIRST USE          the first call of the run that uses a given value for a given kind of argument. A later use is
                     a REUSE and is counted apart.
  PATH               the `filepath` of a read_file or edit_file call, normalised as in public_runs_address.py. OWN
                     FILE: the run had written the file with write_file. Classes of a FIRST USE: IN CONTEXT, the
                     path stands in the CONTEXT as a whole path (a directory prefix before it is allowed); DOTTED
                     NAME, it does not, and the file's dotted module name does, as a whole dotted name; NEITHER.
                     Of the NEITHER, BASE NAME LISTED are those whose base name stands in the CONTEXT on its own,
                     not as part of a path (as `ls` of a directory prints it): the path was put together from a
                     listing.
                     WHERE an IN CONTEXT path first stood: the task statement, the rest of the prompt (the file
                     list), or the result of the earliest call that holds it: OWN SEARCH (a run_command that is a
                     search, explore_read_starts.is_search), COMMAND OUTPUT (another run_command), GRAPH TOOL,
                     READ (a read_file result), OTHER TOOL. WORKS: the call's result has status ok.
  SEARCH WORD        of a search: the longest identifier (a letter or underscore, then at least two letters, digits
                     or underscores; the first of equal length) in the pattern of a run_command search (the first
                     piece of the command line, cut at | ; & ( ), that begins with grep, egrep, fgrep, rg, ag, ack
                     or git grep: its first argument that is not an option, or the value of -e; for find, the value
                     of -name, -iname or -path) or in the query of search_similar_code. Classes of a FIRST
                     USE: IN CONTEXT, the word stands in the CONTEXT as a whole identifier; NEITHER. WORKS: the
                     search returned something (status ok and a stdout that is not blank; a count above 0).
  NODE               a node name given to get_code_neighbors or get_code_subgraph. IN CONTEXT: the whole name
                     stands in the CONTEXT; LAST PART: only its last dotted component does, as a whole identifier;
                     NEITHER. WORKS: an answer with a count above 0.
  EDIT TARGET        the `old_string` of an edit_file call on a file that is not an OWN FILE. VERBATIM: it stands in
                     the CONTEXT exactly; UP TO BLANKS: it does once every run of blanks, in both, is read as one
                     blank; ESCAPED COPY: it does once the two-character sequences backslash-n, backslash-t and
                     backslash-quote in it are read as a line break, a tab and a quote (the model wrote the
                     escapes out; the current harness repairs this, the September one did not); OWN TEXT: none of
                     these, and it stands (up to blanks, escapes read the same way) in a text the run itself wrote
                     earlier, the `new_string` of an edit or the `content` of a write_file; IN PIECES: none of
                     these, and each of its lines that is not blank stands, stripped, in the CONTEXT or in such a
                     text (two reads of a file are two pieces of the CONTEXT); NEITHER. WORKS: status ok.
  START LINE         the asked start of a READ past line 1 (classes of analysis/explore_read_starts.py), split by
                     whether the number itself had been given: EXACTLY A NAMED LINE; ONE PAST AN EARLIER READ (the
                     line after the end of an earlier RETURNED RANGE of the file); OTHER PAGING; NEAR A NAMED LINE
                     (class ADDRESSED and the start is not a NAMED LINE); OTHER (the remaining classes).
  PLACE NAME         of a CHANGED REGION: the simple name of the smallest function or class of the file's syntax
                     tree whose span holds the region's first line (analysis/nodes.py `scopes`); none for code
                     outside any definition.
  NAMED              the task statement holds the PLACE NAME as a whole identifier; a name that is one plain word
                     (no underscore, digit or inner capital, such as `get`) counts only where the statement writes
                     it as code: between backquotes, before `(` or after a dot. FILE NAMED: not NAMED, and the
                     statement holds the file's path, its dotted module name or its base name. UNNAMED: neither.
Intervals: 95% bootstrap over tasks, 2,000 resamples, seed 0 (analyze_forks.boot_ci, diff_ci).
"""
import argparse
import collections
import hashlib
import io
import json
import random
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_read_starts as E  # noqa: E402
import nodes as N  # noqa: E402
from analyze_forks import diff_ci  # noqa: E402
from graphloc_traces import iter_runs, load  # noqa: E402
from public_runs_address import DATA, GRAPH_TOOLS, calls_of, command_of, names_file, norm, pct  # noqa: E402
from public_runs_time_to_fix import gold_regions  # noqa: E402

OMITTED = re.compile(r'^\[omitted: \d+ characters, sha1 ([0-9a-f]{40})\]$')
WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')
PATH_CLASSES = ('IN CONTEXT', 'DOTTED NAME', 'NEITHER')
WHERE = ('TASK STATEMENT', 'REST OF THE PROMPT', 'OWN SEARCH', 'COMMAND OUTPUT', 'GRAPH TOOL', 'READ', 'OTHER TOOL')


VALUE_OPTS = {'-f', '-A', '-B', '-C', '-m', '-d', '-D', '-g', '-t', '-T', '--include', '--exclude', '--exclude-dir',
              '--max-count', '--after-context', '--before-context', '--context', '--glob', '--type'}


def search_pattern(cmd):
    """The pattern of the first search piece of a command line, or None."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars='|;&()')
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    pieces, cur = [], []
    for t in toks:
        if t and set(t) <= set('|;&()'):
            pieces.append(cur)
            cur = []
        else:
            cur.append(t)
    pieces.append(cur)
    for seg in pieces:
        if not seg:
            continue
        head = seg[0].rsplit('/', 1)[-1]
        if head == 'git' and len(seg) > 1 and seg[1] == 'grep':
            rest = seg[2:]
        elif head == 'find':
            for k, t in enumerate(seg[:-1]):
                if t in ('-name', '-iname', '-path', '-ipath', '-regex'):
                    return seg[k + 1].strip()
            continue
        elif head in E.SEARCHERS:
            rest = seg[1:]
        else:
            continue
        it = iter(rest)
        for t in it:
            if t in ('-e', '--regexp', '--'):
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


def sha1(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def stored_prompts():
    """{sha1: text} of the prompts whose text is on this machine."""
    out = {}
    first = next(iter_runs(arm='base'), None)
    if first is not None:
        for s in load(first['path']).get('steps', [])[:2]:
            if isinstance(s.get('message'), str):
                out[sha1(s['message'])] = s['message']
    path = HERE / 'fork_states_w' / 'first_call_states.jsonl'
    if path.exists():
        with io.open(path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    for s in json.loads(line).get('steps', []):
                        if isinstance(s.get('message'), str):
                            out[sha1(s['message'])] = s['message']
    return out


def prompts_of(trace, known):
    """(system prompt, task prompt, texts recovered, texts missing) of a run."""
    texts, got, missing = {'system': '', 'user': ''}, 0, 0
    for s in trace.get('steps', [])[:3]:
        src, m = s.get('source'), s.get('message')
        if src not in texts or texts[src] or not isinstance(m, str) or s.get('tool_calls'):
            continue
        mo = OMITTED.match(m.strip())
        if mo:
            if mo.group(1) in known:
                texts[src], got = known[mo.group(1)], got + 1
            else:
                missing += 1
        else:
            texts[src] = m
    return texts['system'], texts['user'], got, missing


def whole_word(word, text):
    return re.search(r'(?<![A-Za-z0-9_])' + re.escape(word) + r'(?![A-Za-z0-9_])', text) is not None


def dotted(path):
    p = path[:-3] if path.endswith('.py') else path
    if p.endswith('/__init__'):
        p = p[:-len('/__init__')]
    out = [p.replace('/', '.')]
    if p.startswith('src/'):
        out.append(p[len('src/'):].replace('/', '.'))
    return out


def dotted_in(path, text):
    return path.endswith('.py') and any(
        re.search(r'(?<![A-Za-z0-9_.])' + re.escape(d) + r'(?![A-Za-z0-9_])', text) is not None for d in dotted(path) if '.' in d)


def kind_of_call(call):
    name = call.get('function_name')
    if name == 'run_command':
        return 'OWN SEARCH' if E.is_search(command_of(call)) else 'COMMAND OUTPUT'
    if name in GRAPH_TOOLS:
        return 'GRAPH TOOL'
    return 'READ' if name == 'read_file' else 'OTHER TOOL'


def squeeze(text):
    return re.sub(r'\s+', ' ', text)


def unescape(text):
    return text.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")


def arguments(trace, statement, known):
    """One record per argument of the kinds above, and where each file's path first stood."""
    calls = calls_of(trace)
    system, user, got, missing = prompts_of(trace, known)
    stated = statement or ''
    if stated and stated[:200] not in user:        # a prompt stored without its task text: the statement is added
        user = user + '\n' + stated
    rest = system + '\n' + user                    # tested after the statement, so it stands for the rest of the prompt
    ctx = rest
    results = []                                   # (kind of call, result text) of earlier calls
    wrote, used = set(), collections.defaultdict(set)
    out, origin = [], {}
    own = ''                                       # the texts the run itself wrote into files
    for i, (call, text, parsed) in enumerate(calls, 1):
        name = call.get('function_name')
        args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
        ok = isinstance(parsed, dict) and parsed.get('status') == 'ok'
        if name in ('read_file', 'edit_file') and args.get('filepath'):
            f = norm(args.get('filepath'))
            rec = {'kind': 'PATH', 'tool': name, 'value': f, 'i': i, 'works': ok, 'where': None}
            if f in wrote:
                rec['cls'] = 'OWN FILE'
            elif f in used['PATH']:
                rec['cls'] = 'REUSE'
            else:
                if names_file(ctx, f):
                    rec['cls'] = 'IN CONTEXT'
                    if names_file(stated, f):
                        rec['where'] = 'TASK STATEMENT'
                    elif names_file(rest, f):
                        rec['where'] = 'REST OF THE PROMPT'
                    else:
                        rec['where'] = next((k for k, t in results if names_file(t, f)), 'OTHER TOOL')
                elif dotted_in(f, ctx):
                    rec['cls'] = 'DOTTED NAME'
                else:
                    rec['cls'] = 'NEITHER'
                    rec['listed'] = re.search(r'(?<![A-Za-z0-9_.\-/])' + re.escape(f.rsplit('/', 1)[-1]) + r'(?![A-Za-z0-9_])',
                                              ctx) is not None
                origin[f] = (rec['cls'], rec['where'])
            used['PATH'].add(f)
            out.append(rec)
        if name == 'edit_file' and isinstance(args.get('old_string'), str) and args.get('filepath'):
            f = norm(args.get('filepath'))
            old = args['old_string']
            if f not in wrote and old.strip():
                if old in ctx:
                    cls = 'VERBATIM'
                elif squeeze(old).strip() in squeeze(ctx):
                    cls = 'UP TO BLANKS'
                elif squeeze(unescape(old)).strip() in squeeze(ctx):
                    cls = 'ESCAPED COPY'
                elif squeeze(unescape(old)).strip() in squeeze(unescape(own)):
                    cls = 'OWN TEXT'
                elif all(ln.strip() in ctx or ln.strip() in own for ln in unescape(old).splitlines() if ln.strip()):
                    cls = 'IN PIECES'
                else:
                    cls = 'NEITHER'
                out.append({'kind': 'EDIT TARGET', 'value': old, 'i': i, 'works': ok, 'cls': cls, 'file': f})
        if name == 'edit_file' and isinstance(args.get('new_string'), str):
            own += '\n' + args['new_string']
        if name == 'write_file' and isinstance(args.get('content'), str):
            own += '\n' + args['content']
        word = None
        if name == 'run_command':
            pat = search_pattern(command_of(call))
            if pat:
                words = WORD.findall(pat)
                word = max(words, key=len) if words else ''
                works = ok and bool(str(parsed.get('stdout') or '').strip())
                tool = 'run_command'
        elif name == 'search_similar_code' and isinstance(args.get('query'), str):
            words = WORD.findall(args['query'])
            word = max(words, key=len) if words else ''
            works = ok and bool(parsed.get('count') or parsed.get('results'))
            tool = name
        if word is not None:
            rec = {'kind': 'SEARCH WORD', 'tool': tool, 'value': word, 'i': i, 'works': works}
            rec['cls'] = ('NO IDENTIFIER' if not word else 'REUSE' if word in used[tool] else
                          'IN CONTEXT' if whole_word(word, ctx) else 'NEITHER')
            used[tool].add(word)
            out.append(rec)
        if name in ('get_code_neighbors', 'get_code_subgraph'):
            given = args.get('node') if name == 'get_code_neighbors' else args.get('nodes')
            for node in ([given] if isinstance(given, str) else given if isinstance(given, list) else []):
                if not isinstance(node, str) or not node.strip():
                    continue
                node = node.strip()
                cls = ('REUSE' if node in used['NODE'] else
                       'IN CONTEXT' if re.search(r'(?<![A-Za-z0-9_.])' + re.escape(node) + r'(?![A-Za-z0-9_])', ctx) else
                       'LAST PART' if whole_word(node.split('.')[-1], ctx) else 'NEITHER')
                used['NODE'].add(node)
                out.append({'kind': 'NODE', 'tool': name, 'value': node, 'i': i, 'cls': cls,
                            'works': ok and bool(parsed.get('count') or parsed.get('neighbors') or parsed.get('edges'))})
        if name == 'write_file' and args.get('filepath'):
            wrote.add(norm(args.get('filepath')))
        results.append((kind_of_call(call), text or ''))
        ctx += '\n' + (text or '')
    return out, origin, got, missing


def place_names(task, g):
    """{(file, a, b): PLACE NAME or None} for the task's CHANGED REGIONS."""
    out = {}
    for f, regs in g.items():
        try:
            scopes = N.scopes(task, f) if f.endswith('.py') else {}
        except Exception:
            scopes = {}
        for a, b in regs:
            best = None
            for qual, (s, e, _d) in scopes.items():
                if s <= a <= e and (best is None or (e - s, -qual.count('.')) < best[0]):
                    best = ((e - s, -qual.count('.')), qual)
            out[(f, a, b)] = best[1].split('.')[-1] if best else None
    return out


def named_in(statement, name):
    if re.search(r'[_0-9]|[a-z][A-Z]', name):
        return whole_word(name, statement)
    esc = re.escape(name)
    return re.search(r'`' + esc + r'`|(?<![A-Za-z0-9_])' + esc + r'\(|\.' + esc + r'(?![A-Za-z0-9_])', statement) is not None


def naming(statement, f, name):
    if name and named_in(statement, name):
        return 'NAMED'
    base = f.rsplit('/', 1)[-1]
    if names_file(statement, f) or dotted_in(f, statement) or re.search(r'(?<![A-Za-z0-9_])' + re.escape(base) + r'(?![A-Za-z0-9_])', statement):
        return 'FILE NAMED'
    return 'UNNAMED'


def table(rows, classes, title):
    first = [r for r in rows if r['cls'] in classes]
    apart = collections.Counter(r['cls'] for r in rows if r['cls'] not in classes)
    print(f'   {title}: uses {len(rows)}' + ''.join(f', {k} {v}' for k, v in sorted(apart.items())) + f'; FIRST USES classed {len(first)}')
    for c in classes:
        sel = [r for r in first if r['cls'] == c]
        print(f'      {c:<14}{pct(len(sel), len(first)):<24} WORKS {pct(sum(r["works"] for r in sel), len(sel))}')
    return first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', action='store_true')
    args = ap.parse_args()
    gold = gold_regions()
    texts = E.task_texts()
    known = stored_prompts()
    srcs = collections.OrderedDict((k, v) for k, v in E.all_sources().items() if k not in E.ARMS_18.values())
    print('WHERE THE ARGUMENTS OF TOOL CALLS COME FROM, AND THE PLACES OF THE FIX THAT THE TASK NAMES (EXPLORATORY)')
    print()
    done = collections.OrderedDict()
    names = {}
    for label, runs in srcs.items():
        recs, regs, starts, kept, got, missing, no_prompt = [], [], [], [], 0, 0, 0
        for r in runs:
            trace = r['load']()
            task = r['task']
            g = gold.get(task, {})
            statement = texts.get(task, '')
            out, origin, a, b = arguments(trace, statement, known)
            got, missing = got + a, missing + b
            for x in out:
                x.update(task=task, key=r['key'])
            recs += out
            reads, rr, _fr, _more = E.analyse(trace, g, statement)
            for x in reads:
                if x['cls'] in E.CLASSES and x['cls'] != 'TOP':
                    starts.append({'task': task, 'cls': x['cls'], 'exact': x.get('exact', False), 'next1': x.get('next1', False)})
            if task not in names:
                names[task] = place_names(task, g)
            for x in rr:
                how = naming(statement, x['f'], names[task].get((x['f'], x['a'], x['b'])))
                regs.append({'task': task, 'key': r['key'], 'naming': how, 'seen': x['seen'], 'opened': x['opened'], 'how': x['how'],
                             'origin': origin.get(x['f'])})
            kept.append({'task': task, 'resolved': r['resolved'],
                         'naming': [naming(statement, x['f'], names[task].get((x['f'], x['a'], x['b']))) for x in rr]})
        done[label] = (recs, regs, starts, kept, got, missing)

    print('1. Where an argument comes from')
    for label, (recs, regs, starts, kept, got, missing) in done.items():
        print(f'{label}: runs {len(kept)}; prompts recovered by checksum {got}, not recovered {missing}')
        paths = table([r for r in recs if r['kind'] == 'PATH'], PATH_CLASSES, 'PATH of read_file and edit_file')
        nei = [r for r in paths if r['cls'] == 'NEITHER']
        lst = [r for r in nei if r.get('listed')]
        print(f'      of the NEITHER: BASE NAME LISTED {len(lst)}, WORKS {pct(sum(r["works"] for r in lst), len(lst))}; the other '
              f'{len(nei) - len(lst)}, WORKS {pct(sum(r["works"] for r in nei if not r.get("listed")), len(nei) - len(lst))}')
        inc = [r for r in paths if r['cls'] == 'IN CONTEXT']
        print('      WHERE an IN CONTEXT path first stood: ' + ', '.join(f'{k} {sum(r["where"] == k for r in inc)}' for k in WHERE))
        table([r for r in recs if r['kind'] == 'SEARCH WORD' and r['tool'] == 'run_command'], ('IN CONTEXT', 'NEITHER'),
              'SEARCH WORD of a shell search')
        table([r for r in recs if r['kind'] == 'SEARCH WORD' and r['tool'] == 'search_similar_code'], ('IN CONTEXT', 'NEITHER'),
              'SEARCH WORD of search_similar_code')
        table([r for r in recs if r['kind'] == 'NODE'], ('IN CONTEXT', 'LAST PART', 'NEITHER'), 'NODE of a graph tool')
        ed = [r for r in recs if r['kind'] == 'EDIT TARGET']
        print(f'   EDIT TARGET: edits {len(ed)}')
        for c in ('VERBATIM', 'UP TO BLANKS', 'ESCAPED COPY', 'OWN TEXT', 'IN PIECES', 'NEITHER'):
            sel = [r for r in ed if r['cls'] == c]
            print(f'      {c:<14}{pct(len(sel), len(ed)):<24} WORKS {pct(sum(r["works"] for r in sel), len(sel))}')
        n = len(starts)
        exact = sum(x['exact'] for x in starts)
        nxt = sum(x['next1'] and not x['exact'] for x in starts)
        pag = sum(x['cls'] == 'PAGING' and not x['exact'] and not x['next1'] for x in starts)
        near = sum(x['cls'] == 'ADDRESSED' and not x['exact'] and not x['next1'] for x in starts)
        print(f'   START LINE of a READ past line 1: {n}; EXACTLY A NAMED LINE {pct(exact, n)}; ONE PAST AN EARLIER READ {pct(nxt, n)}; '
              f'OTHER PAGING {pct(pag, n)}; NEAR A NAMED LINE {pct(near, n)}; OTHER {pct(n - exact - nxt - pag - near, n)}')

    print()
    print('2. The places of the fix that the task statement names')
    for label, (recs, regs, starts, kept, got, missing) in done.items():
        if not regs:
            continue
        print(f'{label}: CHANGED REGIONS in runs {len(regs)}')
        by = {}
        for c in ('NAMED', 'FILE NAMED', 'UNNAMED'):
            sel = [x for x in regs if x['naming'] == c]
            by[c] = collections.defaultdict(list)
            for x in sel:
                by[c][x['task']].append(int(x['seen']))
            print(f'   {c:<11} regions {len(sel)} in {len(by[c])} tasks; SHOWN {pct(sum(x["seen"] for x in sel), len(sel))}; in an OPENED FILE '
                  f'{pct(sum(x["opened"] for x in sel), len(sel))}; SHOWN of those in an OPENED FILE '
                  f'{pct(sum(x["seen"] for x in sel if x["opened"]), sum(x["opened"] for x in sel))}')
        d = diff_ci(by['NAMED'], by['UNNAMED'])
        if d[0] is not None:
            print(f'   SHOWN, NAMED minus UNNAMED, by task: {100 * d[0]:+.1f} points [{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]')
        un = [x for x in regs if x['naming'] == 'UNNAMED' and x['seen']]
        org = collections.Counter((x['origin'] or ('NO READ BY PATH', None)) for x in un)
        print(f'   the {len(un)} UNNAMED regions that were SHOWN: the path of their file, when the run first read it: '
              + ', '.join(f'{(k[0] + (", " + k[1] if k[1] else ""))} {v}' for k, v in org.most_common())
              + '; the READ that first showed the region: ' + ', '.join(f'{k} {v}' for k, v in collections.Counter(x['how'] for x in un).most_common()))
        scored = [k for k in kept if k['resolved'] is not None and k['naming']]
        if scored:
            for nm, test in (('1 region', lambda n: n == 1), ('2 or 3', lambda n: 2 <= n <= 3), ('4 or more', lambda n: n >= 4)):
                sel = [k for k in scored if test(len(k['naming']))]
                yes = [k for k in sel if all(x == 'NAMED' for x in k['naming'])]
                part = [k for k in sel if any(x == 'NAMED' for x in k['naming']) and not all(x == 'NAMED' for x in k['naming'])]
                no = [k for k in sel if not any(x == 'NAMED' for x in k['naming'])]
                print(f'   tasks with {nm}: every region NAMED, resolved {pct(sum(k["resolved"] for k in yes), len(yes))} '
                      f'({len({k["task"] for k in yes})} tasks); some, {pct(sum(k["resolved"] for k in part), len(part))} '
                      f'({len({k["task"] for k in part})}); none, {pct(sum(k["resolved"] for k in no), len(no))} ({len({k["task"] for k in no})})')

    if args.sample:
        rng = random.Random(0)
        for label, (recs, regs, starts, kept, got, missing) in done.items():
            for kind in ('PATH', 'SEARCH WORD'):
                sel = [r for r in recs if r['kind'] == kind and r['cls'] in ('NEITHER', 'DOTTED NAME')]
                print()
                print(f'SAMPLE, {label}, {kind}: {min(25, len(sel))} of {len(sel)} FIRST USES of class NEITHER or DOTTED NAME')
                for r in rng.sample(sel, min(25, len(sel))):
                    print(f'   {r["task"]} {r["key"]} call {r["i"]}: {r.get("tool")} {r["cls"]} {r["value"]!r} works={r["works"]}')


if __name__ == '__main__':
    main()
