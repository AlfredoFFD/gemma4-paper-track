"""The share of graph nodes for which a file and a line range are found (EXPLORATORY; a count, no rule).

Reads the tracked manifest that analysis/make_spans_g.py writes (analysis/fork_states_g/spans_manifest.json: per task
of the fresh population, the number of distinct node names of the task's code graph, the number that resolve to a
file of the task's snapshot, and the number that also get a line range) and prints the totals that script prints when
it builds the address tables. Nothing is rebuilt here; the manifest's own md5 is printed so that a change shows.

Usage: py -I -X utf8 analysis/spans_share.py > analysis/results/spans_share.txt
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'fork_states_g' / 'spans_manifest.json'


def main():
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    tot = {k: sum(m[k] for m in manifest.values()) for k in ('graph_nodes', 'with_file', 'with_lines')}
    print('GRAPH NODES WITH AN ADDRESS (EXPLORATORY): from the manifest of analysis/make_spans_g.py')
    print(f'{len(manifest)} tasks; graph nodes {tot["graph_nodes"]}, with a file {tot["with_file"]} '
          f'({100 * tot["with_file"] / tot["graph_nodes"]:.1f}%), with a line range {tot["with_lines"]} '
          f'({100 * tot["with_lines"] / tot["graph_nodes"]:.1f}%)')
    shares = sorted(100 * m['with_lines'] / m['graph_nodes'] for m in manifest.values())
    print(f'per task, with a line range: lowest {shares[0]:.1f}%, median {shares[len(shares) // 2]:.1f}%, '
          f'highest {shares[-1]:.1f}%')
    print(f'manifest md5 {hashlib.md5(MANIFEST.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
