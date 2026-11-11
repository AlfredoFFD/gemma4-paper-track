"""Independent re-derivation (EXPLORATORY, blind): a name search in both directions against the call edge, for the
places a public starter-agent run missed.

Written from a brief's definitions only, without reading the project's own scripts or outputs on this question.
Imports the populations and helpers of the earlier blind recount analysis/rederive_public_reach.py (and through it
analysis/rederive_public_missed_links.py, analysis/graphloc_traces.py, analysis/nodes.py) unchanged: MISSED PAIR,
NODE, TARGET, SHOWN NODE, the snapshot text of the SHOWN line ranges, the GRAPH WITHOUT CLASS-TO-MEMBER LINKS (its
second block) and EDGE REACH on it. Its main() is one function, so the population steps are re-run here line for line
from that file (the rewirings are not needed and are left out); the two check numbers (1,326 missed pairs; 267 edge
reach) are printed first.

Definitions as implemented (only for missed pairs whose TARGET exists and is not shown; every other pair counts no):
- short(x): the last dotted part of a node id.
- FORWARD: short(TARGET) is found in the snapshot text of the line ranges the run was shown (all shown files, .py or
  not; the ranges joined by newlines, as the earlier recount builds it).
- BACKWARD: short(S) is found in the TARGET's own text (the snapshot lines start..end of the TARGET's span, decorators
  included) for at least one SHOWN NODE S of the run, where S is not the TARGET and short(S) != short(TARGET).
- EITHER: FORWARD or BACKWARD.
Variants (applied to both directions alike):
 1. ALL: found = the name stands as a whole word, (?<!\\w)name(?!\\w), in the raw text.
 2. NO DUNDER: as 1, and names that start and end with '__' are left out (short(TARGET) for forward; the shown node's
    short name for backward).
 3. USE, NO DUNDER: as 2, but searched in a CLEANED text and only in a use position. CLEANED: each whole file is first
    scanned once from its first line: '#' comments (outside a string) and triple-quoted strings (''' or \"\"\", with
    backslash escapes) are replaced by spaces, newlines kept, so line numbers do not move; single-quoted strings are
    kept; a single-quoted string left open at the end of a line is closed there. The same scanner is used for every
    file (.py or not). Then the line ranges are cut from the cleaned file. A USE POSITION is one of:
      (a) call: the whole word followed by optional spaces or tabs and '(' -- (?<!\\w)name[ \\t]*\\( -- unless the text
          on the same line before the name ends with 'def' or 'class' followed by whitespace (async def included);
      (b) attribute: the whole word directly after a '.' -- \\.name(?!\\w);
      (c) import: the whole word anywhere on an import line. An import line is a cleaned line whose stripped text
          starts with 'import ' or matches 'from <dotted or dots> import'; the lines after it count as import lines
          while a '(' opened on the statement is not yet closed, or while the previous line ends with a backslash.
          Import lines are found on the whole cleaned file, then cut to the ranges.
- Intervals: 95% percentile bootstrap over tasks, 2,000 resamples, random.Random(0) fresh for each interval (the
  earlier recount's boot); a share is summed counts over summed denominator; EDGE minus EITHER is per task
  (edge - either) over the summed number of missed pairs.

Usage: py -I -X utf8 analysis/rederive_public_reach_both.py > analysis/results/public/rederive_reach_both.txt
"""
import collections
import functools
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graphloc_traces as gt  # noqa: E402
import nodes  # noqa: E402
import rederive_public_missed_links as ml  # noqa: E402
import rederive_public_reach as rp  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8', errors='replace', newline='\n')
DATA = HERE.parent / 'data'
WORD = re.compile(r'\w+')
CALL = re.compile(r'(?<!\w)(\w+)[ \t]*\(')
ATTR = re.compile(r'\.(\w+)(?!\w)')
DEFCLS = re.compile(r'(?:^|\W)(?:def|class)\s+$')
IMPORT = re.compile(r'^(?:import\s|from\s+[\w.]+\s+import\b)')


def short(nm):
    return nm.split('.')[-1]


def dunder(s):
    return s.startswith('__') and s.endswith('__')


# ---------------------------------------------------------------- cleaning
def clean(text):
    """Blank '#' comments and triple-quoted strings (newlines kept)."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ' '
            i = j
        elif c in '\'"':
            if text.startswith(c * 3, i):
                q = c * 3
                j = i + 3
                while j < n:
                    if text[j] == '\\':
                        j += 2
                        continue
                    if text.startswith(q, j):
                        j += 3
                        break
                    j += 1
                j = min(j, n)
                for k in range(i, j):
                    if out[k] != '\n':
                        out[k] = ' '
                i = j
            else:
                j = i + 1
                while j < n and text[j] != '\n':
                    if text[j] == '\\':
                        j += 2
                        continue
                    if text[j] == c:
                        j += 1
                        break
                    j += 1
                i = min(j, n)
        else:
            i += 1
    return ''.join(out)


def import_mask(lines):
    mask = [False] * len(lines)
    depth = 0
    cont = False
    for k, ln in enumerate(lines):
        st = ln.strip()
        if depth > 0 or cont or IMPORT.match(st):
            mask[k] = True
            depth = max(0, depth + ln.count('(') - ln.count(')'))
            cont = ln.rstrip().endswith('\\')
        else:
            depth = 0
            cont = False
    return mask


_CLEANED = {}


def cleaned(task, path, raw):
    """raw: the file's lines (the same snapshot lines whichever helper read them) -> (cleaned lines, import mask)."""
    key = (task, path)
    if key not in _CLEANED:
        cl = clean('\n'.join(raw)).split('\n')
        assert len(cl) == len(raw), (task, path)
        _CLEANED[key] = (cl, import_mask(cl))
    return _CLEANED[key]


def use_names(cl, mask, s, e):
    """Set of names in a use position in cleaned lines s..e (1-based, inclusive)."""
    seg = cl[max(s, 1) - 1:e]
    txt = '\n'.join(seg)
    found = set()
    for m in CALL.finditer(txt):
        ls = txt.rfind('\n', 0, m.start()) + 1
        if DEFCLS.search(txt[ls:m.start()]):
            continue
        found.add(m.group(1))
    for m in ATTR.finditer(txt):
        found.add(m.group(1))
    for k in range(max(s, 1) - 1, min(e, len(cl))):
        if mask[k]:
            found.update(WORD.findall(cl[k]))
    return found


def main():
    out = []
    P = out.append
    diag = collections.Counter()
    tasks = {}
    for line in (DATA / 'tasks.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t['instance_id']] = t
    runs = list(gt.iter_runs())
    run_tasks = sorted({r['task'] for r in runs})
    regions = {t: ml.changed_regions(tasks[t]['patch'], diag) for t in run_tasks}
    gkey = {t: f"{tasks[t]['repo'].split('/')[1]}_{tasks[t]['base_commit']}" for t in run_tasks}
    kept = [t for t in run_tasks if regions[t]]

    run_reads = []
    need_paths = collections.defaultdict(set)
    for r in runs:
        if not regions[r['task']]:
            continue
        reads = [(p, s, e) for p, s, e, _ in ml.read_results(gt.load(r['path']))]
        run_reads.append((r, reads))
        for p, s, e in reads:
            need_paths[r['task']].add(p)

    # ---- per task graph without class-to-member links (as the second block of the earlier recount)
    G = {}
    for t in kept:
        names, idx, edges, _ = ml.load_graph(gkey[t])
        by_path = collections.defaultdict(list)
        spans = {}
        is_class = set()
        for nm in names:
            i = idx[nm]
            sp = nodes.span(t, nm)
            if sp is None or sp.get('end') is None:
                continue
            p = nodes._norm(sp['path'])
            spans[i] = (p, sp['start'], sp['end'])
            by_path[p].append((sp['start'], sp['end'], nm, i))
            if sp['qualname'] in rp.class_quals(t, sp['path']):
                is_class.add(i)

        def in_class(c, x):
            return (c in is_class and x != c and x in spans and spans[x][0] == spans[c][0]
                    and spans[c][1] <= spans[x][1] and spans[x][2] <= spans[c][2])
        cm = {(u, v) for u, v in edges if in_class(u, v) or in_class(v, u)}
        edges2 = [e for e in edges if e not in cm]
        G[t] = {'names': names, 'by_path': by_path, 'spans': spans, 'adj2': rp.adjacency(len(names), edges2)}

    texts = {t: rp.snapshot_texts(t, need_paths[t]) for t in kept}

    @functools.lru_cache(maxsize=None)
    def file_lines(t, p):
        txt = nodes.file_text(t, p)
        return None if txt is None else tuple(txt.splitlines())

    recs = []
    for r, reads in run_reads:
        t = r['task']
        X = G[t]
        shown = collections.defaultdict(list)
        for p, s, e in reads:
            shown[p]
            if s <= e:
                shown[p].append((s, e))
        shown_nodes = set()
        for p, ivs in shown.items():
            for s, e, nm, i in X['by_path'].get(p, []):
                if ml.overlaps(ivs, s, e):
                    shown_nodes.add(i)
        parts = []
        use_fwd = set()
        for p, s, e in reads:
            lines = texts[t].get(p)
            if lines is None:
                continue
            parts.append('\n'.join(lines[max(s, 1) - 1:e]))
            cl, mask = cleaned(t, p, lines)
            use_fwd |= use_names(cl, mask, s, e)
        text = '\n'.join(parts)
        for f, s, e in regions[t]:
            if ml.overlaps(shown.get(f, []), s, e):
                continue
            rec = {'task': t, 'arm': r['arm'], 'ns': False, 'edge': False,
                   'fwd': [False] * 3, 'bwd': [False] * 3, 'nnames': [None] * 3}
            cands = sorted((ee - ss, nm, i) for ss, ee, nm, i in X['by_path'].get(f, []) if ss <= e and s <= ee)
            if cands:
                _, nm, ti = cands[0]
                if ti not in shown_nodes:
                    rec['ns'] = True
                    rec['edge'] = bool(X['adj2'][ti] & shown_nodes)
                    ts = short(nm)
                    # forward
                    fa = bool(re.search(r'(?<!\w)' + re.escape(ts) + r'(?!\w)', text))
                    rec['fwd'] = [fa, fa and not dunder(ts), (ts in use_fwd) and not dunder(ts)]
                    # backward
                    tp, tsa, tse = X['spans'][ti]
                    raw = file_lines(t, tp)
                    if raw is None:
                        diag['TARGET file text missing'] += 1
                        tw, tu = set(), set()
                    else:
                        tw = set(WORD.findall('\n'.join(raw[tsa - 1:tse])))
                        cl, mask = cleaned(t, tp, raw)
                        tu = use_names(cl, mask, tsa, tse)
                    sn_all = {short(X['names'][i]) for i in shown_nodes if i != ti} - {ts}
                    sn_nd = {x for x in sn_all if not dunder(x)}
                    rec['nnames'] = [len(sn_all), len(sn_nd), len(sn_nd)]
                    rec['bwd'] = [bool(sn_all & tw), bool(sn_nd & tw), bool(sn_nd & tu)]
            recs.append(rec)

    def per_task(num):
        d = collections.OrderedDict()
        for x in recs:
            d.setdefault(x['task'], [0, 0])
            d[x['task']][0] += num(x)
            d[x['task']][1] += 1
        return [tuple(v) for v in d.values()]

    n = len(recs)
    ns = [x for x in recs if x['ns']]
    ke = sum(x['edge'] for x in recs)
    P('RE-DERIVATION (EXPLORATORY, blind): a name search in both directions against the call edge, missed pairs of '
      'public starter-agent runs')
    P(f'runs kept: {len(run_reads)}; tasks kept: {len(kept)}; bootstrap: {rp.N_BOOT} resamples over tasks, seed 0')
    P('diagnostics: ' + ('; '.join(f'{k}: {v}' for k, v in sorted(diag.items())) or 'none'))
    P('')
    P('CHECK (from the earlier recount: 1326 missed pairs; edge reach without class-to-member links 267)')
    P(f'  missed pairs: {n}; TARGET exists and not shown: {len(ns)}')
    P(f'  EDGE REACH without class-to-member links: {rp.fmt(ke, n)} {rp.ci(per_task(lambda x: x["edge"]))}')
    P('')
    labels = ['1. ALL names', '2. NO DUNDER', '3. USE, NO DUNDER (cleaned text, use positions only)']
    for v, lab in enumerate(labels):
        P(lab)
        kf = sum(x['fwd'][v] for x in recs)
        kb = sum(x['bwd'][v] for x in recs)
        either = lambda x, v=v: x['fwd'][v] or x['bwd'][v]  # noqa: E731
        kx = sum(bool(either(x)) for x in recs)
        P(f'  FORWARD : {rp.fmt(kf, n)} {rp.ci(per_task(lambda x, v=v: x["fwd"][v]))}')
        P(f'  BACKWARD: {rp.fmt(kb, n)} {rp.ci(per_task(lambda x, v=v: x["bwd"][v]))}')
        P(f'  EITHER  : {rp.fmt(kx, n)} {rp.ci(per_task(lambda x: bool(either(x))))}')
        P(f'  EDGE - EITHER: {100 * (ke - kx) / n:+.1f} pts '
          f'{rp.ci(per_task(lambda x: int(x["edge"]) - int(bool(either(x)))), signed=True)}')
        er = [x for x in recs if x['edge']]
        c = collections.Counter((x['fwd'][v], x['bwd'][v]) for x in er)
        P(f'  of the {len(er)} pairs the EDGE reaches: forward only {c[(True, False)]}; backward only '
          f'{c[(False, True)]}; both {c[(True, True)]}; neither {c[(False, False)]}')
        cx = collections.Counter((x['edge'], bool(either(x))) for x in ns)
        P(f'  cross table, TARGET exists and not shown, n={len(ns)}')
        P('                   either yes  either no')
        P(f'    edge yes      {cx[(True, True)]:10d} {cx[(True, False)]:10d}')
        P(f'    edge no       {cx[(False, True)]:10d} {cx[(False, False)]:10d}')
        nn = [x['nnames'][v] for x in ns]
        P(f'  backward: distinct shown names searched per pair (n={len(nn)}): median {statistics.median(nn):g}; '
          f'pairs with none {sum(1 for k in nn if k == 0)}')
        P('')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
