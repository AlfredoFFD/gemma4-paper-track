"""Run a notebook's code cells in order and store what they print in the notebook.

Usage, from anywhere:
    py -I -X utf8 notebooks/run_notebook.py            run table2_from_raw_outputs.ipynb and store its outputs
    py -I -X utf8 notebooks/run_notebook.py --check    run it and compare with the stored outputs; nothing is written
    py -I -X utf8 notebooks/run_notebook.py <notebook> [--check]

No Jupyter kernel is needed and only the standard library is used. The code cells run in this process, in one
namespace, with the notebook's folder as the working directory, as Jupyter runs them. What a cell prints becomes its
output; if its last statement is an expression with a value, that value is shown too. The file stays ordinary notebook
JSON (nbformat 4), so it still opens and runs in Jupyter. If a cell raises, its traceback is printed and the notebook
is left as it was.
"""
import argparse
import ast
import contextlib
import io
import json
import linecache
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / 'table2_from_raw_outputs.ipynb'


class Captured(io.StringIO):
    """A text stream that also accepts reconfigure(), which some scripts call on sys.stdout."""

    def reconfigure(self, **settings):
        pass


def text_of(cell):
    source = cell.get('source', '')
    return ''.join(source) if isinstance(source, list) else source


def run_cell(code, namespace, label, count):
    """Execute one code cell and return its outputs in notebook form."""
    linecache.cache[label] = (len(code), None, code.splitlines(keepends=True), label)  # tracebacks can show the line
    tree = ast.parse(code, label)
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    out, err = Captured(), Captured()
    value = None
    # exec and eval run the notebook's own cells, which is what this script is for: the same trust as opening the
    # notebook in Jupyter and running it. Nothing else is evaluated.
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            exec(compile(tree, label, 'exec'), namespace)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), label, 'eval'), namespace)
    except BaseException:
        sys.stdout.write(out.getvalue())
        sys.stderr.write(err.getvalue())
        raise
    outputs = []
    for name, stream in (('stdout', out), ('stderr', err)):
        if stream.getvalue():
            outputs.append({'name': name, 'output_type': 'stream', 'text': stream.getvalue().splitlines(keepends=True)})
    if value is not None:
        outputs.append({'data': {'text/plain': repr(value).splitlines(keepends=True)}, 'execution_count': count,
                        'metadata': {}, 'output_type': 'execute_result'})
    return outputs


def plain(outputs):
    """Outputs as text that can be compared, however the JSON splits it into lines or stream pieces."""
    flat = []
    for o in outputs:
        kind = o.get('output_type')
        if kind == 'stream':
            item = (o.get('name'), ''.join(o.get('text', '')))
            if flat and flat[-1][0] == item[0]:
                item = (item[0], flat.pop()[1] + item[1])
        elif kind == 'execute_result':
            item = ('value', ''.join(o.get('data', {}).get('text/plain', '')))
        else:
            item = (kind, json.dumps(o, sort_keys=True))
        flat.append(item)
    return flat


def first_difference(old, new):
    a = [line for _, text in old for line in text.splitlines()]
    b = [line for _, text in new for line in text.splitlines()]
    i = next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return (a[i] if i < len(a) else '<no more output>'), (b[i] if i < len(b) else '<no more output>')


def main():
    ap = argparse.ArgumentParser(description='Run a notebook without a Jupyter kernel and store its outputs in it.')
    ap.add_argument('notebook', nargs='?', default=str(DEFAULT))
    ap.add_argument('--check', action='store_true', help='compare a fresh run with the stored outputs; write nothing')
    args = ap.parse_args()
    path = Path(args.notebook).resolve()
    nb = json.loads(path.read_text(encoding='utf-8'))
    namespace = {'__name__': '__main__'}
    differ = []
    count = 0
    back = os.getcwd()
    start = time.time()
    os.chdir(path.parent)
    try:
        for i, cell in enumerate(nb['cells']):
            code = text_of(cell)
            if cell.get('cell_type') != 'code' or not code.strip():
                continue
            count += 1
            name = cell.get('id', i)
            try:
                outputs = run_cell(code, namespace, f'<{path.name}, cell {name}>', count)
            except Exception:
                traceback.print_exc()
                sys.exit(f'{path.name}: the cell "{name}" raised; nothing was written')
            old, new = plain(cell.get('outputs', [])), plain(outputs)
            if old != new:
                differ.append((name, *first_difference(old, new)))
            cell['outputs'], cell['execution_count'] = outputs, count
    finally:
        os.chdir(back)
    seconds = time.time() - start
    if args.check:
        for name, was, now in differ:
            print(f'  the output of cell "{name}" differs from the stored one')
            print(f'    stored: {was[:150]}')
            print(f'    now:    {now[:150]}')
        verdict = f'{len(differ)} of {count} outputs differ from the stored ones' if differ else \
            f'all {count} outputs are identical to the stored ones'
        print(f'{path.name}: ran {count} code cells in {seconds:.1f} s; {verdict}; nothing written')
        sys.exit(1 if differ else 0)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(f'{path.name}: ran {count} code cells in {seconds:.1f} s; outputs stored '
          f'({len(differ)} changed, {count - len(differ)} as before)')


if __name__ == '__main__':
    main()
