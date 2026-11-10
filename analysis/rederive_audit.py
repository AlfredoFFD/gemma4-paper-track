"""Blind re-derivation of two pointer-audit quantities: K1 (gold units addressable as graph nodes) and reach
(gold nodes one or two graph hops from a node the issue text mentions). Written from the Sep 30 definitions only.

Run: py -I -X utf8 analysis/rederive_audit.py  -> analysis/results/rederive_audit.txt (+ a per-task json)
"""
import ast
import json
import re
import sys
import tarfile
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CACHE_TXT = DATA / 'cache' / 'snapshot_text'
OUT_TXT = ROOT / 'analysis' / 'results' / 'rederive_audit.txt'
OUT_JSON = Path(sys.argv[1]) if len(sys.argv) > 1 else None  # optional per-task dump, kept outside the repo
CAP = 50
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
CHAIN = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+')


# ---------------------------------------------------------------- patch parsing
def parse_patch(patch):
    """[{old, new, hunks:[(old_start, old_len, new_start, new_len, [(tag, text)])]}]"""
    files, cur, lines, i = [], None, patch.split('\n'), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            old = ln[4:].split('\t')[0].strip()
            new = lines[i + 1][4:].split('\t')[0].strip()
            cur = {'old': None if old == '/dev/null' else re.sub(r'^a/', '', old),
                   'new': None if new == '/dev/null' else re.sub(r'^b/', '', new), 'hunks': []}
            files.append(cur)
            i += 2
            continue
        m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', ln)
        if m and cur is not None:
            os_, ol = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            ns, nl = int(m.group(3)), int(m.group(4) if m.group(4) is not None else 1)
            body, ro, rn = [], ol, nl
            i += 1
            while i < len(lines) and (ro > 0 or rn > 0):
                b = lines[i]
                if b.startswith('\\'):
                    i += 1
                    continue
                tag, text = (b[:1] or ' '), b[1:]
                if tag == ' ':
                    ro -= 1; rn -= 1
                elif tag == '-':
                    ro -= 1
                elif tag == '+':
                    rn -= 1
                else:
                    break
                body.append((tag, text))
                i += 1
            cur['hunks'].append((os_, ol, ns, nl, body))
            continue
        i += 1
    return files


def apply_hunks(base_lines, hunks):
    """Reconstruct the patched file; returns (new_lines, context_mismatches)."""
    out, pos, bad = [], 0, 0  # pos = 0-based index into base
    for os_, ol, ns, nl, body in hunks:
        start = os_ - 1 if ol > 0 else os_
        out.extend(base_lines[pos:start])
        pos = start
        for tag, text in body:
            if tag == ' ':
                if pos >= len(base_lines) or base_lines[pos] != text:
                    bad += 1
                out.append(text); pos += 1
            elif tag == '-':
                if pos >= len(base_lines) or base_lines[pos] != text:
                    bad += 1
                pos += 1
            else:
                out.append(text)
    out.extend(base_lines[pos:])
    return out, bad


def changed_lines(hunks):
    """(removed base line numbers, added new line numbers), 1-based."""
    rem, add = [], []
    for os_, ol, ns, nl, body in hunks:
        o, n = os_, ns
        for tag, _ in body:
            if tag == ' ':
                o += 1; n += 1
            elif tag == '-':
                rem.append(o); o += 1
            else:
                add.append(n); n += 1
    return rem, add


# ---------------------------------------------------------------- AST scopes
def scope_table(src):
    """Return (scopes, import_lines). scopes: list of (start, end, chain) where chain = [(name, kind)],
    kind in {'class','def','async'}; start includes decorators."""
    tree = ast.parse(src)
    scopes, imports = [], set()

    def walk(node, chain):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.Import, ast.ImportFrom)):
                imports.update(range(ch.lineno, ch.end_lineno + 1))
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = 'class' if isinstance(ch, ast.ClassDef) else ('async' if isinstance(ch, ast.AsyncFunctionDef) else 'def')
                c = chain + [(ch.name, kind)]
                start = min([d.lineno for d in ch.decorator_list] + [ch.lineno])
                scopes.append((start, ch.end_lineno, c))
                walk(ch, c)
            else:
                walk(ch, chain)

    walk(tree, [])
    return scopes, imports


def innermost(scopes, line):
    best = None
    for s, e, c in scopes:
        if s <= line <= e and (best is None or len(c) > len(best)):
            best = c
    return best


def qual(chain):
    return '.'.join(n for n, _ in chain)


# ---------------------------------------------------------------- naming
def module_variants(path):
    p = path[:-3]
    for pre in ('src/', 'docs_src/'):
        if p.startswith(pre):
            p = p[len(pre):]
            break
    parts = p.split('/')
    if parts[-1] == '__init__':
        return ['.'.join(parts[:-1]), '.'.join(parts)] if len(parts) > 1 else ['__init__']
    return ['.'.join(parts)]


def name_candidates(path, chain):
    tails = [qual(chain)]
    anc = chain[:-1]
    if any(k != 'class' for _, k in anc):  # nested inside a function: also flatten to nearest class/module
        ci = max([i for i, (_, k) in enumerate(anc) if k == 'class'], default=-1)
        flat = qual(anc[:ci + 1] + [chain[-1]])
        if flat not in tails:
            tails.append(flat)
    out = []
    for m in module_variants(path):
        for t in tails:
            out.append(f'{m}.{t}' if m else t)
    return out


# ---------------------------------------------------------------- file access
def cached_text(iid, path):
    for cand in ('./' + path, path):
        f = CACHE_TXT / iid / (cand.replace('/', '__') + '.txt')
        if f.exists():
            return f.read_text(encoding='utf-8')
    return None


def load_base_files(iid, paths):
    """Return {path: text or None}. Uses the full-text cache when complete, else one pass over the archive."""
    if (CACHE_TXT / iid / '.complete').exists():
        return {p: cached_text(iid, p) for p in paths}
    want = {p: None for p in paths}
    t0 = time.time()
    with tarfile.open(DATA / 'snapshots' / f'{iid}.tgz', 'r:gz') as tf:
        for m in tf:
            n = m.name[2:] if m.name.startswith('./') else m.name
            if m.isfile() and n in want:
                want[n] = tf.extractfile(m).read().decode('utf-8', 'replace')
                if all(v is not None for v in want.values()):
                    break
    print(f'    [archive pass {iid}: {time.time() - t0:.0f}s]', flush=True)
    return want


# ---------------------------------------------------------------- graph
def load_graph(repo, commit):
    f = DATA / 'graphs' / f'{repo.split("/")[1]}_{commit}.json'
    if not f.exists():
        return None
    g = json.loads(f.read_text(encoding='utf-8'))
    ids = [n['id'] for n in g['nodes']]
    nbr = defaultdict(set)
    for e in g['edges']:
        s, t = e['source'], e['target']
        if s != t:
            nbr[s].add(t); nbr[t].add(s)
    return {'ids': set(ids), 'nbr': nbr, 'short': Counter(i.split('.')[-1] for i in ids), 'file': f.name}


def text_index(text):
    idents = set(IDENT.findall(text))
    subchains = set()
    for ch in CHAIN.findall(text):
        parts = ch.split('.')
        for a in range(len(parts)):
            for b in range(a + 2, len(parts) + 1):
                subchains.add('.'.join(parts[a:b]))
    return idents, subchains


def dotted_hit(node_id, subchains):
    parts = node_id.split('.')
    return any('.'.join(parts[k:]) in subchains for k in range(len(parts) - 1))  # suffixes with >= 2 parts


def is_dunder(s):
    return s.startswith('__') and s.endswith('__')


def mentioned_nodes(G, idents, subchains):
    out = set()
    for nid in G['ids']:
        if '.' not in nid:
            if nid in idents:
                out.add(nid)
            continue
        if dotted_hit(nid, subchains):
            out.add(nid); continue
        sn = nid.split('.')[-1]
        if len(sn) >= 4 and not is_dunder(sn) and sn in idents and G['short'][sn] <= 5:
            out.add(nid)
    return out


def named_directly(nid, idents, subchains, min_len=0):
    sn = nid.split('.')[-1]
    return (sn in idents and len(sn) >= min_len) or dotted_hit(nid, subchains) or nid in idents


def bites(G, mentioned, golds, hops, cap):
    nbr = G['nbr']
    reach = set()
    for m in mentioned:
        if cap is not None and len(nbr[m]) > cap:
            continue
        frontier = set(nbr[m])
        reach |= frontier
        if hops == 2:
            for x in frontier:
                if cap is not None and len(nbr[x]) > cap:
                    continue
                reach |= nbr[x]
    return golds & reach


# ---------------------------------------------------------------- main
def main():
    tasks = [json.loads(l) for l in (DATA / 'tasks.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f'{len(tasks)} tasks', flush=True)
    graph_cache, rows = {}, []
    stats = Counter()
    for ti, t in enumerate(tasks, 1):
        iid, repo = t['instance_id'], t['repo'].split('/')[1]
        files = parse_patch(t['patch'])
        py_paths = sorted({f['old'] for f in files if f['old'] and f['old'].endswith('.py')})
        base = load_base_files(iid, py_paths) if py_paths else {}
        units = {}  # (path, qual) -> chain
        row = {'iid': iid, 'repo': repo, 'nonpy_files': 0, 'new_py_files': 0, 'missing_base': 0, 'ctx_mismatch': 0,
               'module_level_lines': 0, 'parse_fail': 0}
        for f in files:
            path = f['new'] or f['old']
            if not path.endswith('.py'):
                row['nonpy_files'] += 1; continue
            if f['old'] is None:
                row['new_py_files'] += 1; continue
            src = base.get(f['old'])
            if src is None:
                if all(h[1] == 0 for h in f['hunks']):  # "--- a/x" with "@@ -0,0": a created file
                    row['new_py_files'] += 1
                else:
                    row['missing_base'] += 1
                continue
            if f['new'] is None:
                # deleted file: only removed lines
                pass
            base_lines = src.split('\n')
            new_lines, bad = apply_hunks(base_lines, f['hunks'])
            row['ctx_mismatch'] += bad
            try:
                bscopes, bimp = scope_table(src)
                nscopes, nimp = scope_table('\n'.join(new_lines)) if f['new'] else ([], set())
            except SyntaxError:
                row['parse_fail'] += 1; continue
            bquals = {qual(c): c for _, _, c in bscopes}
            rem, add = changed_lines(f['hunks'])
            for ln in rem:
                text = base_lines[ln - 1] if ln - 1 < len(base_lines) else ''
                if not text.strip() or ln in bimp:
                    continue
                c = innermost(bscopes, ln)
                if c is None:
                    row['module_level_lines'] += 1; continue
                units[(f['old'], qual(c))] = c
            for ln in add:
                text = new_lines[ln - 1] if ln - 1 < len(new_lines) else ''
                if not text.strip() or ln in nimp:
                    continue
                c = innermost(nscopes, ln)
                while c and qual(c) not in bquals:
                    c = c[:-1]
                if not c:
                    row['module_level_lines'] += 1; continue
                units[(f['old'], qual(c))] = bquals[qual(c)]
        key = (repo, t['base_commit'])
        if key not in graph_cache:
            graph_cache[key] = load_graph(t['repo'], t['base_commit'])
        G = graph_cache[key]
        row['graph'] = G['file'] if G else None
        ulist = []
        for (p, q), c in sorted(units.items()):
            cands = name_candidates(p, c)
            hit = next((x for x in cands if G and x in G['ids']), None)
            ulist.append({'path': p, 'qual': q, 'kind': c[-1][1], 'node': hit, 'cands': cands})
        row['units'] = ulist
        issue = (t.get('problem_statement') or '') + '\n' + (t.get('hints_text') or '')
        idents, subchains = text_index(issue)
        golds = {u['node'] for u in ulist if u['node']}
        if G:
            men = mentioned_nodes(G, idents, subchains)
            direct = {g for g in golds if named_directly(g, idents, subchains)}
            direct4 = {g for g in golds if named_directly(g, idents, subchains, min_len=4)}
            nd = golds - direct
            nd4 = golds - direct4
            row.update(mentioned=len(men), direct=sorted(direct), direct_minlen4=sorted(direct4),
                       bite1=sorted(bites(G, men, nd, 1, CAP)), bite1_nocap=sorted(bites(G, men, nd, 1, None)),
                       bite2=sorted(bites(G, men, nd, 2, CAP)), bite2_nocap=sorted(bites(G, men, nd, 2, None)),
                       bite1_minlen4=sorted(bites(G, men, nd4, 1, CAP)),
                       bite2_minlen4=sorted(bites(G, men, nd4, 2, CAP)))
        else:
            row.update(mentioned=0, direct=[], direct_minlen4=[], bite1=[], bite1_nocap=[], bite2=[], bite2_nocap=[],
                       bite1_minlen4=[], bite2_minlen4=[])
        rows.append(row)
        print(f'{ti:3d}/{len(tasks)} {iid}: units={len(ulist)} addr={sum(1 for u in ulist if u["node"])} '
              f'men={row["mentioned"]} direct={len(row["direct"])} b1={len(row["bite1"])} b2={len(row["bite2"])}',
              flush=True)

    # ------------------------------------------------------------ aggregate
    N = len(rows)
    L = []
    pct = lambda a, b: f'{a}/{b} = {100 * a / b:.1f}%' if b else f'{a}/0'
    L.append('Blind re-derivation of the pointer audit (K1 and reach), from the Sep 30 definitions only.')
    L.append(f'Tasks: {N}. Graphs found for {sum(1 for r in rows if r["graph"])} tasks; '
             f'distinct graph files used: {len({r["graph"] for r in rows if r["graph"]})}.')
    nog = [r['iid'] for r in rows if not r['graph']]
    L.append(f'Tasks without a graph file: {nog}')
    L.append('')
    elig = [r for r in rows if r['units']]
    allad = [r for r in elig if all(u['node'] for u in r['units'])]
    nu = sum(len(r['units']) for r in elig)
    na = sum(1 for r in elig for u in r['units'] if u['node'])
    L.append('== K1: gold units addressable as graph nodes ==')
    L.append(f'Tasks with >=1 pre-existing Python gold unit: {len(elig)} of {N}')
    L.append(f'K1 (task level, all units addressable): {pct(len(allad), len(elig))}')
    L.append(f'Unit level: {pct(na, nu)}')
    L.append('Per repository (tasks all-addressable / eligible; units addressable / units):')
    for repo in sorted({r['repo'] for r in rows}):
        e = [r for r in elig if r['repo'] == repo]
        a = [r for r in e if all(u['node'] for u in r['units'])]
        u_ = sum(len(r['units']) for r in e)
        ua = sum(1 for r in e for u in r['units'] if u['node'])
        L.append(f'  {repo:8s} tasks {pct(len(a), len(e)):>18s}   units {pct(ua, u_):>18s}   (all tasks in repo: '
                 f'{sum(1 for r in rows if r["repo"] == repo)})')
    miss = [(r['iid'], u) for r in elig for u in r['units'] if not u['node']]
    L.append(f'Missing units: {len(miss)}; of which async functions: {sum(1 for _, u in miss if u["kind"] == "async")}; '
             f'kinds: {dict(Counter(u["kind"] for _, u in miss))}')
    L.append(f'Tasks with zero units: {N - len(elig)}; with non-Python files: {sum(1 for r in rows if r["nonpy_files"])}; '
             f'non-Python files total: {sum(r["nonpy_files"] for r in rows)}; new Python files total: '
             f'{sum(r["new_py_files"] for r in rows)}; base file missing from snapshot: '
             f'{sum(r["missing_base"] for r in rows)}; patch context mismatches: {sum(r["ctx_mismatch"] for r in rows)}; '
             f'parse failures: {sum(r["parse_fail"] for r in rows)}')
    L.append('Missing units (task, path::qualname, kind, first candidate tried):')
    for iid, u in miss:
        L.append(f'  {iid}  {u["path"]}::{u["qual"]}  {u["kind"]}  {u["cands"][0]}')
    L.append('')
    L.append('== Reach (denominator: all tasks) ==')
    cnt = lambda k: sum(1 for r in rows if r[k])
    L.append(f'Reach, 1 hop, cap {CAP}: {pct(cnt("bite1"), N)}')
    L.append(f'Reach, 1 hop, no cap: {pct(cnt("bite1_nocap"), N)}')
    L.append(f'Reach, 2 hops, cap {CAP} on each expanded node: {pct(cnt("bite2"), N)}')
    L.append(f'Reach, 2 hops, no cap: {pct(cnt("bite2_nocap"), N)}')
    L.append(f'Issue names a gold unit directly: {pct(cnt("direct"), N)}')
    L.append(f'Issue mentions >=1 graph node: {pct(sum(1 for r in rows if r["mentioned"] > 0), N)}')
    L.append('Sensitivity (EXPLORATORY): "named directly" short-name match requiring >=4 chars:')
    L.append(f'  direct {pct(cnt("direct_minlen4"), N)}; reach 1 hop cap {pct(cnt("bite1_minlen4"), N)}; '
             f'2 hops cap {pct(cnt("bite2_minlen4"), N)}')
    L.append('Per repository (tasks): bite1 / bite1_nocap / bite2 / direct / mentioned>=1 / n')
    for repo in sorted({r['repo'] for r in rows}):
        rr = [r for r in rows if r['repo'] == repo]
        L.append(f'  {repo:8s} ' + ' / '.join(str(sum(1 for r in rr if r[k])) for k in
                                              ('bite1', 'bite1_nocap', 'bite2', 'direct')) +
                 f' / {sum(1 for r in rr if r["mentioned"])} / {len(rr)}')
    L.append('Tasks with a 1-hop bite (cap): ' + ', '.join(f'{r["iid"]}{r["bite1"]}' for r in rows if r['bite1']))
    L.append('Tasks with a 2-hop bite (cap): ' + ', '.join(r['iid'] for r in rows if r['bite2']))
    L.append('Tasks naming a gold unit directly: ' + ', '.join(r['iid'] for r in rows if r['direct']))
    L.append('')
    L.append('== Interpretations made ==')
    L += [
        '1. Patch parsing: per file block (--- / +++), hunks read by their line counts; "/dev/null" old side = new file '
        '(no units), "/dev/null" new side = deleted file (removed lines only). A file is Python iff its path ends in .py.',
        '2. Patched file reconstructed by applying the hunks to the base text from the snapshot; context and removed '
        'lines checked against the base (mismatch count reported above).',
        '3. Scopes from ast on base and patched files: FunctionDef, AsyncFunctionDef, ClassDef; a scope spans its first '
        'decorator to end_lineno, so decorator lines belong to the def. Innermost = deepest scope containing the line.',
        '4. Ignored lines: blank (whitespace-only) and any line inside an Import/ImportFrom statement (multi-line '
        'imports included, inside defs too), judged in the file the line lives in. Comment lines count like code.',
        '5. Added line whose innermost patched scope is not a qualname in the base file: walk up its chain to the '
        'nearest qualname that exists in base; if none, module-level (not a unit). Units dedup by (file, qualname).',
        '6. Graph name: path minus .py, leading src/ or docs_src/ dropped, "/" -> "."; pkg/__init__.py tried as pkg and '
        'pkg.__init__; then the full class/def chain. If any ancestor is a function, also tried flattened to the nearest '
        'enclosing class (or the module). First candidate that is a node id wins.',
        '7. Graph: <repo short>_<base_commit>.json; neighbors = union of in and out edges over unique node ids, self '
        'loops dropped; the 50 cap is on that unique-neighbor count. Task with no graph: no units addressable, no mentions.',
        '8. "Appears in the issue text": the text is tokenized into identifiers [A-Za-z_][A-Za-z0-9_]* and into dotted '
        'chains of identifiers; a dotted id or dotted suffix (>=2 parts) appears iff it is a contiguous sub-chain of a '
        'chain in the text (i.e. whole-identifier boundaries, case-sensitive). A short name appears iff it is one of '
        'the identifier tokens (so "get" inside "get_x" does not count). A node id without dots is matched as a token.',
        '9. Mentioned: dotted suffix rule, or short name >=4 chars, not __dunder__, token present, and <=5 nodes in the '
        'graph share that short name.',
        '10. Named directly: gold node short name is a token (no length or ambiguity filter, as written), or its full '
        'id / a dotted suffix appears. A >=4-char variant is reported as sensitivity only.',
        '11. Graph bite: gold node, not named directly, in the 1-hop neighborhood of a mentioned node with <=50 unique '
        'neighbors. 2 hops: neighbors of such a mentioned node, plus neighbors of each of those that itself has <=50.',
        '12. Reach, direct naming and mention shares use all 129 tasks as denominator; K1 uses tasks with >=1 unit.',
    ]
    OUT_TXT.write_text('\n'.join(L) + '\n', encoding='utf-8')
    if OUT_JSON:
        OUT_JSON.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    print('\n'.join(L[:40]))


if __name__ == '__main__':
    main()
