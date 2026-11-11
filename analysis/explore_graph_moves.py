"""Does the agent make the code graph's moves by itself? (EXPLORATORY)

Usage: py -I -X utf8 analysis/explore_graph_moves.py

Nothing here was pre-registered and no model is run. The runs are the eight sets of whole runs of
analysis/explore_read_starts.py. Two questions. Part 1: what do the agent's own searches look for: a name the task
gave it, the name of a definition it has been shown (the search that returns that definition's callers), a name in
code it has read, or something else? Part 2: when a read shows the run a definition it had not been shown, is that
definition one call edge from one it had been shown, and how did the run get there?

Rules.
  SEARCH, SEARCH WORD   as in analysis/explore_arguments.py (a run_command with a search piece; the longest
                        identifier of its pattern). Searches without an identifier are counted apart.
  DEFINITION SHOWN      a function or class of a file's syntax tree (analysis/nodes.py `scopes`, so async functions
                        count) whose `def` or `class` line a READ of status ok had returned before the call.
  Class of a SEARCH, the first that applies: TASK, the word stands in the task statement as a whole identifier;
                        DEFINITION SHOWN, the word is the simple name of one; CODE SHOWN, the word stands as a
                        whole identifier in the content some earlier READ returned; OTHER RESULT, it stands in
                        another earlier result; NEW, none of these. (TASK and DEFINITION SHOWN are also counted
                        each on its own.) A SEARCH HITS if its status is ok and its stdout is not blank.
  ENTITY                a node of the task's code graph whose file and lines analysis/nodes.py resolves; SHOWN
                        once a READ of status ok (not of a file the run wrote) has returned one of its lines.
  CALL EDGE             an edge of the graph between two ENTITIES that is not a CONTAINMENT edge (a class and one
                        of its members), read without direction (analysis/public_runs_missed_links.call_graph).
  MOVE                  a READ that makes at least one ENTITY SHOWN for the first time, at a call where some
                        ENTITY was SHOWN already. Its NEW ENTITIES are those.
  ALONG A CALL EDGE     a NEW ENTITY of the MOVE is one CALL EDGE from an ENTITY SHOWN before it. BY CHANCE: the
                        share of the task's ENTITIES not yet SHOWN that are one CALL EDGE from a SHOWN one at that
                        call; its mean over MOVES is the share expected if the new entity were drawn at random.
  How a MOVE was made   READING ON: the READ's class in explore_read_starts.py is PAGING. OWN SEARCH: its class is
                        ADDRESSED with a NAMED LINE from the run's OWN SEARCH near its WINDOW, or it is the first
                        READ of its file and the file's path first stood in the result of an OWN SEARCH
                        (explore_arguments.py). TOP OF A LISTED FILE: the first READ of a file whose path stood
                        in the prompt or the task statement. OTHER: the rest.
  NAMED BY SHOWN CODE   the simple name of a NEW ENTITY stood, as a whole identifier, in content an earlier READ
                        had returned (the callee side). NAMES A SHOWN ENTITY: the source of a NEW ENTITY holds the
                        simple name of an ENTITY SHOWN before (the caller side).
Intervals: none; these are counts.
"""
import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_arguments as X  # noqa: E402
import explore_read_starts as E  # noqa: E402
import nodes as N  # noqa: E402
import public_runs_missed_regions as M  # noqa: E402
from fork_states import graph_for, load_tasks  # noqa: E402
from public_runs_address import calls_of, command_of, is_read, norm, pct  # noqa: E402
from public_runs_missed_links import call_graph, entities, short, words_of  # noqa: E402
from public_runs_time_to_fix import gold_regions  # noqa: E402

IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
SEARCH_CLASSES = ('TASK', 'DEFINITION SHOWN', 'CODE SHOWN', 'OTHER RESULT', 'NEW')
HOW = ('READING ON', 'OWN SEARCH', 'TOP OF A LISTED FILE', 'OTHER')
_defs = {}


def def_lines(task, f):
    """{line of a def or class: simple name} for a Python file of the task's snapshot."""
    key = (task, f)
    if key not in _defs:
        out = {}
        if f.endswith('.py'):
            try:
                for qual, (_s, _e, d) in N.scopes(task, f).items():
                    out[d] = qual.split('.')[-1]
            except Exception:
                pass
        _defs[key] = out
    return _defs[key]


def one_run(trace, task, tasks, statement, gold, known):
    calls = calls_of(trace)
    reads, _regs, _files, _more = E.analyse(trace, gold.get(task, {}), statement)
    by_call = {x['i']: x for x in reads}
    _recs, origin, _a, _b = X.arguments(trace, statement, known)
    g = graph_for(tasks[task]) if task in tasks else None
    ent = entities(task, g) if g else {}
    cg = call_graph(task, g)[0]['nbr'] if g else {}
    shown, shown_names = set(), set()        # ENTITIES shown; simple names of DEFINITIONS SHOWN
    screen, other_text = set(), ''           # identifiers in content read; text of the other results
    files_read = set()
    searches, moves = [], []
    for i, (call, text, parsed) in enumerate(calls, 1):
        name = call.get('function_name')
        ok = isinstance(parsed, dict) and parsed.get('status') == 'ok'
        if name == 'run_command':
            pat = X.search_pattern(command_of(call))
            if pat:
                words = X.WORD.findall(pat)
                word = max(words, key=len) if words else ''
                rec = {'word': word, 'hits': ok and bool(str(parsed.get('stdout') or '').strip()),
                       'task': bool(word) and X.whole_word(word, statement), 'defn': word in shown_names}
                rec['cls'] = ('NO IDENTIFIER' if not word else 'TASK' if rec['task'] else 'DEFINITION SHOWN' if rec['defn'] else
                              'CODE SHOWN' if word in screen else 'OTHER RESULT' if X.whole_word(word, other_text) else 'NEW')
                searches.append(rec)
        x = by_call.get(i)
        if x is not None and x['cls'] in E.CLASSES and 'range' in x:
            f, (rs, re_) = x['f'], x['range']
            here = {nid for s0, e0, nid in (M.nodes_of_file(task, g, f) if g else ()) if not (e0 < rs or s0 > re_)}
            new = here - shown
            if new and shown:
                frontier = set()
                for s in shown:
                    frontier |= cg.get(s, set())
                frontier = {n for n in frontier if n in ent} - shown
                rest = len(ent) - len(shown)
                org = origin.get(f) or (None, None)
                first_of_file = f not in files_read
                if x['cls'] == 'PAGING':
                    how = 'READING ON'
                elif (x['cls'] == 'ADDRESSED' and 'OWN SEARCH' in x['kinds']) or (first_of_file and org[1] == 'OWN SEARCH'):
                    how = 'OWN SEARCH'
                elif first_of_file and org[1] in ('TASK STATEMENT', 'REST OF THE PROMPT'):
                    how = 'TOP OF A LISTED FILE'
                else:
                    how = 'OTHER'
                moves.append({'edge': bool(new & frontier), 'chance': len(frontier) / rest if rest else 0.0, 'how': how,
                              'new_file': first_of_file,
                              'callee': any(short(n) in screen for n in new),
                              'caller': any(words_of(task, ent, n) & {short(s) for s in shown} for n in new)})
            shown |= here
            files_read.add(f)
            for d, nm in def_lines(task, f).items():
                if rs <= d <= re_:
                    shown_names.add(nm)
            screen.update(IDENT.findall(str(parsed.get('content') or '')))
        elif not is_read(call):
            other_text += '\n' + (text or '')
    return searches, moves


def main():
    gold = gold_regions()
    texts = E.task_texts()
    known = X.stored_prompts()
    tasks = load_tasks()
    srcs = collections.OrderedDict((k, v) for k, v in E.all_sources().items() if k not in E.ARMS_18.values())
    print('DOES THE AGENT MAKE THE CODE GRAPH\'S MOVES BY ITSELF? (EXPLORATORY)')
    print()
    done = collections.OrderedDict()
    for label, runs in srcs.items():
        ss, mm, with_caller = [], [], 0
        for r in runs:
            s, m = one_run(r['load'](), r['task'], tasks, texts.get(r['task'], ''), gold, known)
            ss += s
            mm += m
            with_caller += any(x['defn'] for x in s)
        done[label] = (ss, mm, len(runs), with_caller)
    print('1. What the agent\'s own searches look for')
    for label, (ss, mm, n_runs, with_caller) in done.items():
        sel = [x for x in ss if x['cls'] != 'NO IDENTIFIER']
        print(f'{label}: runs {n_runs}; SEARCHES {len(ss)}, without an identifier {len(ss) - len(sel)}')
        print('   class of the ' + str(len(sel)) + ' others: '
              + '; '.join(f'{c} {pct(sum(x["cls"] == c for x in sel), len(sel))}' for c in SEARCH_CLASSES))
        dfn = [x for x in sel if x['defn']]
        print(f'   the word is in the task statement: {pct(sum(x["task"] for x in sel), len(sel))}; it is the name of a DEFINITION SHOWN: '
              f'{pct(len(dfn), len(sel))} (in {with_caller} runs), of which also in the task statement {sum(x["task"] for x in dfn)}; '
              f'such a search HITS in {pct(sum(x["hits"] for x in dfn), len(dfn))}')
    print()
    print('2. Moves to a definition not shown before')
    for label, (ss, mm, n_runs, with_caller) in done.items():
        if not mm:
            continue
        edge = [x for x in mm if x['edge']]
        nf = [x for x in mm if x['new_file']]
        print(f'{label}: MOVES {len(mm)}; ALONG A CALL EDGE {pct(len(edge), len(mm))}, BY CHANCE {100 * sum(x["chance"] for x in mm) / len(mm):.1f}%; '
              f'to a file not read before {len(nf)}, ALONG A CALL EDGE {pct(sum(x["edge"] for x in nf), len(nf))}, '
              f'BY CHANCE {100 * sum(x["chance"] for x in nf) / max(len(nf), 1):.1f}%')
        print('   how a MOVE was made: ' + '; '.join(f'{h} {pct(sum(x["how"] == h for x in mm), len(mm))}' for h in HOW))
        print('   how the MOVES ALONG A CALL EDGE were made: ' + '; '.join(f'{h} {pct(sum(x["how"] == h for x in edge), len(edge))}' for h in HOW))
        print('   ALONG A CALL EDGE, by how the MOVE was made: '
              + '; '.join(f'{h} {pct(sum(x["edge"] for x in mm if x["how"] == h), sum(x["how"] == h for x in mm))}' for h in HOW))
        print(f'   a NEW ENTITY is NAMED BY SHOWN CODE {pct(sum(x["callee"] for x in mm), len(mm))}; NAMES A SHOWN ENTITY '
              f'{pct(sum(x["caller"] for x in mm), len(mm))}; either {pct(sum(x["callee"] or x["caller"] for x in mm), len(mm))}; '
              f'among MOVES ALONG A CALL EDGE: {pct(sum(x["callee"] for x in edge), len(edge))} and {pct(sum(x["caller"] for x in edge), len(edge))}')


if __name__ == '__main__':
    main()
