"""Re-run every analysis of the paper on the raw replay outputs in this repository and compare with the stored outputs.

Usage (from the repo root):
    py -I -X utf8 analysis/reproduce.py            compare; prints PASS or FAIL per output
    py -I -X utf8 analysis/reproduce.py --write    rewrite the stored outputs (maintainers only)

Each job is one script run on tracked files only (analysis/results/<run>/forks/, the state files, the public traces
where a script needs them). A job whose input run is not in the repository is reported as SKIPPED.
The registered scripts are frozen by their pre-registrations; the "independent" jobs are the second implementations
written without the first; the "exploratory" jobs carry no registered rule.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = 'analysis/results'
PUBLIC = ['data/graphloc/out', 'data/public_traces/vanductan__gemma4-patchpool',
          'data/public_traces/niraberman__gemma4-commit-anatomy-traces', 'data/public_traces/petermugoya__what-the-agent-saw']

# (label, kind, script and arguments, stored output, files that must exist)
JOBS = [
    ('02 one step: following, discrimination, channel', 'registered',
     ['analysis/analyze_forks.py', f'{R}/v5/forks'], f'{R}/analyze_a.txt', [f'{R}/v5/forks/results.jsonl']),
    ('03 one step: force, encoding, structure', 'registered',
     ['analysis/analyze_b.py', f'{R}/v6/forks', '--v5', f'{R}/v5/forks', '--rewired', f'{R}/v8/forks'],
     f'{R}/analyze_b.txt', [f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl']),
    ('04 gates', 'registered', ['analysis/gates_c.py', f'{R}/c/forks'], f'{R}/c/gates_c.txt', [f'{R}/c/forks/results.jsonl']),
    ('04 parts of an entry, false entry', 'registered',
     ['analysis/analyze_c.py', f'{R}/c/forks'], f'{R}/c/analyze_c.txt', [f'{R}/c/forks/results.jsonl']),
    ('05 tool channel', 'registered',
     ['analysis/analyze_d.py', 'd1', f'{R}/d1/forks', '--c', f'{R}/c/forks'], f'{R}/d1/analyze_d1.txt',
     [f'{R}/d1/forks/results.jsonl', f'{R}/c/forks/results.jsonl']),
    ('05 second model, 26B-A4B', 'registered',
     ['analysis/analyze_d.py', 'd2', f'{R}/d2_26b/forks'], f'{R}/d2_26b/analyze_d2_26b.txt', [f'{R}/d2_26b/forks/results.jsonl']),
    ('05 second model, E4B', 'registered',
     ['analysis/analyze_d.py', 'd2', f'{R}/d2_e4b/forks'], f'{R}/d2_e4b/analyze_d2_e4b.txt', [f'{R}/d2_e4b/forks/results.jsonl']),
    ('06 five calls', 'registered',
     ['analysis/analyze_k.py', f'{R}/k/forks'], f'{R}/k/analyze_k.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('06 five calls, supplement', 'registered',
     ['analysis/analyze_k_extra.py', f'{R}/k/forks'], f'{R}/k/analyze_k_extra.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('07 rendering', 'registered',
     ['analysis/analyze_w.py', f'{R}/w/forks'], f'{R}/w/analyze_w.txt', [f'{R}/w/forks/results.jsonl']),
    ('08 and 09 fresh episodes: N1, A1, A2', 'registered',
     ['analysis/analyze_09.py', f'{R}/09/forks'], f'{R}/09/analyze_09.txt',
     [f'{R}/09/forks/results_09.jsonl', 'data/snapshots']),
    ('11 the reading rule on the fresh episodes: R1, R2', 'registered',
     ['analysis/analyze_11.py', f'{R}/09/forks'], f'{R}/09/analyze_11.txt', [f'{R}/09/forks/results_09.jsonl']),
    ('08 and 09 fresh episodes, independent', 'independent',
     ['analysis/rederive_09.py', f'{R}/09/forks', '--no-write'], f'{R}/rederive_09.txt',
     [f'{R}/09/forks/results_09.jsonl', 'data/snapshots']),
    ('11 the reading rule, independent', 'independent',
     ['analysis/rederive_11.py', f'{R}/09/forks'], f'{R}/rederive_11.txt', [f'{R}/09/forks/results_09.jsonl']),
    ('04 independent', 'independent',
     ['analysis/rederive_cd.py', 'c', f'{R}/c/forks', '--no-write'], f'{R}/rederive_c.txt', [f'{R}/c/forks/results.jsonl']),
    ('05 tool channel, independent', 'independent',
     ['analysis/rederive_cd.py', 'd1', f'{R}/d1/forks', '--no-write'], f'{R}/rederive_d1.txt', [f'{R}/d1/forks/results.jsonl']),
    ('05 26B-A4B, independent', 'independent',
     ['analysis/rederive_cd.py', 'd2', f'{R}/d2_26b/forks', '--tag', '26b', '--no-write'], f'{R}/rederive_d2_26b.txt',
     [f'{R}/d2_26b/forks/results.jsonl']),
    ('05 E4B, independent', 'independent',
     ['analysis/rederive_cd.py', 'd2', f'{R}/d2_e4b/forks', '--tag', 'e4b', '--no-write'], f'{R}/rederive_d2_e4b.txt',
     [f'{R}/d2_e4b/forks/results.jsonl']),
    ('06 five calls, independent', 'independent',
     ['analysis/rederive_k.py', f'{R}/k/forks', '--out', '{TMP}'], f'{R}/rederive_k.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('07 rendering, independent', 'independent',
     ['analysis/rederive_w.py', f'{R}/w/forks', '--no-write'], f'{R}/rederive_w.txt', [f'{R}/w/forks/results.jsonl']),
    ('five calls, call by call', 'exploratory',
     ['analysis/explore_k.py'], f'{R}/k/explore_k.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('what a mangled read costs', 'exploratory',
     ['analysis/explore_defect_cost.py'], f'{R}/k/explore_defect_cost.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('supplement: task-clustered intervals, the false entry in detail, seed agreement, calls to the fix', 'exploratory',
     ['analysis/explore_supplement.py'], f'{R}/explore_supplement.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('what a name without an address costs in calls', 'exploratory',
     ['analysis/explore_name_cost.py'], f'{R}/k/explore_name_cost.txt', [f'{R}/k/forks/results_k.jsonl']),
    ('08 five calls with the bound honored, and one step on the newest wheels: G1 to G3, S1', 'registered',
     ['analysis/analyze_g.py', f'{R}/g/forks', '--onestep', f'{R}/g_onestep/forks'], f'{R}/g/analyze_g.txt',
     [f'{R}/g/forks/results_g.jsonl', f'{R}/g_onestep/forks/results.jsonl', 'data/snapshots']),
    ('08 five calls and one step on the newest wheels, independent', 'independent',
     ['analysis/rederive_g.py', f'{R}/g/forks', f'{R}/g_onestep/forks', '--no-write'], f'{R}/rederive_g.txt',
     [f'{R}/g/forks/results_g.jsonl', f'{R}/g_onestep/forks/results.jsonl', 'data/snapshots']),
    ('12 a file without lines: P1 to P3', 'registered',
     ['analysis/analyze_12.py', f'{R}/12/forks'], f'{R}/12/analyze_12.txt',
     [f'{R}/12/forks/results.jsonl', f'{R}/c/forks/results.jsonl']),
    ('12 a file without lines, independent', 'independent',
     ['analysis/rederive_12.py', f'{R}/12/forks', f'{R}/c/forks', '--no-write'], f'{R}/rederive_12.txt',
     [f'{R}/12/forks/results.jsonl', f'{R}/c/forks/results.jsonl', 'data/snapshots']),
    ('what follows a read whose line bound was dropped, fresh episodes', 'exploratory',
     ['analysis/explore_defect_fresh.py'], f'{R}/explore_defect_fresh.txt', [f'{R}/09/forks/results_09.jsonl']),
    ('is a line number used more when the line is out of sight', 'exploratory',
     ['analysis/explore_depth.py'], f'{R}/explore_depth.txt', [f'{R}/09/forks/results_09.jsonl', f'{R}/d1/forks/results.jsonl']),
    ('where a first read of a listed file starts', 'exploratory',
     ['analysis/explore_first_reads.py'], f'{R}/explore_first_reads.txt', [f'{R}/d1/forks/results.jsonl']),
    ('a path that swallowed the line bounds', 'exploratory',
     ['analysis/explore_path_leak.py'], f'{R}/explore_path_leak.txt', [f'{R}/d1/forks/results.jsonl']),
    ('mangled argument names: counts', 'exploratory',
     ['analysis/mangled_args.py', f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      f'{R}/d1/forks/results.jsonl', f'{R}/d2_26b/forks/results.jsonl', f'{R}/d2_e4b/forks/results.jsonl'],
     f'{R}/mangled_args_counts.txt', ['data/graphloc/out']),
    ('mangled argument names: sensitivity', 'exploratory',
     ['analysis/mangled_sensitivity.py'], f'{R}/mangled_sensitivity.txt', [f'{R}/d1/forks/results.jsonl']),
    ('where the first read lands', 'exploratory',
     ['analysis/explore_mechanism.py'], f'{R}/explore_mechanism.txt', [f'{R}/d1/forks/results.jsonl']),
    # Other teams' public runs: the data is not in this repository (analysis/results/public/README.md says how to get it).
    ('public runs: where a first read of a file starts', 'exploratory',
     ['analysis/public_runs_address.py'], f'{R}/public/address.txt', PUBLIC),
    ('public runs: where a first read of a file starts, independent', 'independent',
     ['analysis/rederive_public_address.py'], f'{R}/public/rederive_address.txt', PUBLIC),
    ('public runs: mangled argument names', 'exploratory',
     ['analysis/public_runs_defect.py'], f'{R}/public/defect.txt', PUBLIC),
    ('public runs: malformed file reads split by kind', 'exploratory',
     ['analysis/public_runs_defect_split.py'], f'{R}/public/defect_split.txt',
     PUBLIC + ['data/public_traces/kmussa77__gemma4-agent-traces-graph-audit']),
    ('public runs, whole runs: when the agent is first shown a line the fix changes', 'exploratory',
     ['analysis/public_runs_time_to_fix.py'], f'{R}/public/time_to_fix.txt', PUBLIC + ['data/tasks.jsonl']),
    ('public runs of September: graph-tool calls of the starter agent', 'exploratory',
     ['analysis/public_runs_graph_calls.py'], f'{R}/public/graph_calls.txt', PUBLIC),
    ('public runs, whole runs, independent', 'independent',
     ['analysis/rederive_public_time_to_fix.py'], f'{R}/public/rederive_time_to_fix.txt', PUBLIC + ['data/tasks.jsonl']),
    ('public runs, whole runs: fix sites the agent never saw, against the code graph and rewired graphs', 'exploratory',
     ['analysis/public_runs_missed_regions.py'], f'{R}/public/missed_regions.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: from a fix site the run had seen to the ones it missed', 'exploratory',
     ['analysis/public_runs_coedit_sites.py'], f'{R}/public/coedit_sites.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: fix sites the agent never saw, independent', 'independent',
     ['analysis/rederive_public_missed_regions.py'], f'{R}/public/rederive_missed_regions.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
]


def run(args):
    tmp = str(Path(tempfile.gettempdir()) / 'reproduce_scratch_output.txt')  # for a script that always writes a file
    args = [tmp if a == '{TMP}' else a for a in args]
    p = subprocess.run([sys.executable, '-I', '-X', 'utf8', *args], cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n'), p.stderr.decode('utf-8', 'replace')


def main():
    write = '--write' in sys.argv[1:]
    counts = {'PASS': 0, 'FAIL': 0, 'SKIPPED': 0, 'WRITTEN': 0}
    for label, kind, args, stored, needs in JOBS:
        missing = [n for n in needs if not (ROOT / n).exists()]
        if missing:
            print(f'SKIPPED  [{kind}] {label}: not in the repository: {missing[0]}')
            counts['SKIPPED'] += 1
            continue
        code, out, err = run(args)
        path = ROOT / stored
        if code != 0:
            print(f'FAIL     [{kind}] {label}: the script exited with {code}: {err.strip().splitlines()[-1] if err.strip() else ""}')
            counts['FAIL'] += 1
        elif write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out, encoding='utf-8', newline='\n')
            print(f'WRITTEN  [{kind}] {label}: {stored}')
            counts['WRITTEN'] += 1
        elif not path.exists():
            print(f'FAIL     [{kind}] {label}: no stored output {stored}')
            counts['FAIL'] += 1
        else:
            old = path.read_text(encoding='utf-8').replace('\r\n', '\n')
            if old == out:
                print(f'PASS     [{kind}] {label}: identical to {stored} ({len(out.splitlines())} lines)')
                counts['PASS'] += 1
            else:
                a, b = old.splitlines(), out.splitlines()
                i = next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                print(f'FAIL     [{kind}] {label}: differs from {stored} at line {i + 1}')
                print(f'           stored: {a[i][:150] if i < len(a) else "<end>"}')
                print(f'           now:    {b[i][:150] if i < len(b) else "<end>"}')
                counts['FAIL'] += 1
    print(', '.join(f'{k} {v}' for k, v in counts.items() if v))
    sys.exit(1 if counts['FAIL'] else 0)


if __name__ == '__main__':
    main()
