"""Map code-graph node names to files and line spans inside a task's repository snapshot.

A node id is a dotted path such as `fastapi.dependencies.utils.analyze_param`. Its module is the longest
prefix that names a .py file in the snapshot (`a/b/c.py` or `a/b/c/__init__.py`); the remainder is the
qualified name inside that file, located with `ast`. Spans are 1-based inclusive, decorators included.
Snapshot file lists come from analysis/snapshot_index.py; file texts are extracted on demand and cached.
"""
import ast
import functools
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CACHE = DATA / 'cache'


def _norm(path: str) -> str:
    """Snapshot archives list files as ./a/b.py; the agent and the gold tables use a/b.py."""
    return path[2:] if path.startswith('./') else path


@functools.lru_cache(maxsize=None)
def snapshot_files(instance_id: str) -> tuple[str, ...]:
    p = CACHE / 'snapshot_files' / f'{instance_id}.json'
    return tuple(_norm(f) for f in json.loads(p.read_text()))


@functools.lru_cache(maxsize=None)
def _module_table(instance_id: str) -> dict[str, str]:
    """dotted module name -> path, for every .py file in the snapshot (both `pkg.mod` and bare `mod` forms)."""
    table: dict[str, str] = {}
    for f in snapshot_files(instance_id):
        parts = f[:-3].split('/')
        if parts[-1] == '__init__':
            parts = parts[:-1]
        if not parts:
            continue
        for i in range(len(parts)):
            key = '.'.join(parts[i:])
            table.setdefault(key, f)
    return table


def resolve(instance_id: str, node_id: str) -> tuple[str, str] | None:
    """Return (path, qualname_in_file) for a node id, or None if no module prefix matches."""
    table = _module_table(instance_id)
    parts = node_id.split('.')
    for cut in range(len(parts), 0, -1):
        mod = '.'.join(parts[:cut])
        if mod in table:
            return table[mod], '.'.join(parts[cut:])
    return None


def _extract_all_py(instance_id: str) -> Path:
    """Unpack every .py file of a snapshot once (one pass over the archive) into the cache."""
    cdir = CACHE / 'snapshot_text' / instance_id
    marker = cdir / '.complete'
    if marker.exists():
        return cdir
    cdir.mkdir(parents=True, exist_ok=True)
    tgz = DATA / 'snapshots' / f'{instance_id}.tgz'
    with tarfile.open(tgz, 'r:gz') as tf:
        for m in tf:
            if m.isfile() and m.name.endswith('.py'):
                data = tf.extractfile(m).read().decode('utf-8', 'replace')
                (cdir / (m.name.replace('/', '__') + '.txt')).write_text(data, encoding='utf-8')
    marker.write_text('ok')
    return cdir


@functools.lru_cache(maxsize=None)
def file_text(instance_id: str, path: str) -> str | None:
    cdir = _extract_all_py(instance_id)
    for candidate in (_norm(path), './' + _norm(path)):
        cfile = cdir / (candidate.replace('/', '__') + '.txt')
        if cfile.exists():
            return cfile.read_text(encoding='utf-8')
    return None


@functools.lru_cache(maxsize=None)
def scopes(instance_id: str, path: str) -> dict[str, tuple[int, int, int]]:
    """qualname -> (start_line, end_line, def_line) for every function, method and class in the file."""
    src = file_text(instance_id, path)
    out: dict[str, tuple[int, int, int]] = {}
    if src is None:
        return out
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out

    def walk(node, chain):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                c = chain + [child.name]
                start = min([d.lineno for d in child.decorator_list] + [child.lineno])
                out.setdefault('.'.join(c), (start, child.end_lineno, child.lineno))
                walk(child, c)
            else:
                walk(child, chain)

    walk(tree, [])
    return out


def span(instance_id: str, node_id: str) -> dict | None:
    """{'path', 'qualname', 'start', 'end', 'def_line'} for a node, or None if it cannot be located."""
    r = resolve(instance_id, node_id)
    if r is None:
        return None
    path, qual = r
    if qual == '':
        return {'path': path, 'qualname': '', 'start': 1, 'end': None, 'def_line': 1}
    sc = scopes(instance_id, path)
    if qual in sc:
        s, e, d = sc[qual]
        return {'path': path, 'qualname': qual, 'start': s, 'end': e, 'def_line': d}
    return None


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    inst, node = sys.argv[1], sys.argv[2]
    print(resolve(inst, node)); print(span(inst, node))
