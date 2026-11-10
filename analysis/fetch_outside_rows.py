"""Save local copies of the public agent trajectories that analysis/public_runs_outside.py reads.

Usage: py -I -X utf8 analysis/fetch_outside_rows.py [--rows 800]

Reads rows 0 to N-1 of two public Hugging Face datasets through the dataset viewer and writes one JSON object per
line under data/public_traces/outside/ (gitignored; the copies are not redistributed):
  SWE-bench/SWE-smith-trajectories, split `tool` (MIT)         -> swe_smith_tool_rows_0_<N-1>.jsonl
      SWE-agent with function calling, Claude 3.7 Sonnet, tasks of the SWE-smith collection.
  nebius/SWE-agent-trajectories, split `train` (CC-BY-4.0)     -> nebius_swe_agent_rows_0_<N-1>.jsonl
      classic SWE-agent, Llama-based models (named swe-agent-llama-70b, -8b and -405b in the rows).
Prints each file's size, row count and SHA-256, so a later run can be checked against the stored report.
Needs network access. Nothing but these two files is written.
"""
import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'data' / 'public_traces' / 'outside'
SOURCES = (
    ('SWE-bench/SWE-smith-trajectories', 'tool', 'swe_smith_tool'),
    ('nebius/SWE-agent-trajectories', 'train', 'nebius_swe_agent'),
)


def fetch(dataset, split, offset, length, config='default'):
    """Rows [offset, offset + length) of a dataset split, as a list of dicts (at most 100 per request)."""
    query = urllib.parse.urlencode({'dataset': dataset, 'config': config, 'split': split, 'offset': offset, 'length': length})
    url = 'https://datasets-server.huggingface.co/rows?' + query
    last = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'public-runs-check'})
            with urllib.request.urlopen(req, timeout=180) as resp:
                return [item['row'] for item in json.load(resp)['rows']]
        except Exception as exc:  # the viewer sometimes answers 429 or 5xx
            last = exc
            time.sleep(4 + 6 * attempt)
    raise last


def rows_of(dataset, split, n):
    for offset in range(0, n, 100):
        yield from fetch(dataset, split, offset, min(100, n - offset))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', type=int, default=800)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for dataset, split, stem in SOURCES:
        path = OUT / f'{stem}_rows_0_{args.rows - 1}.jsonl'
        digest = hashlib.sha256()
        count = 0
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            for row in rows_of(dataset, split, args.rows):
                line = json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
                f.write(line)
                digest.update(line.encode('utf-8'))
                count += 1
        print(f'{path.name}: {count} rows, {path.stat().st_size} bytes, sha256 {digest.hexdigest()}')


if __name__ == '__main__':
    main()
