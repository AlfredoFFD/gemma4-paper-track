"""Re-run every analysis of the paper on the raw replay outputs in this repository and compare with the stored outputs.

Usage (from the repo root):
    py -I -X utf8 analysis/reproduce.py            compare; prints PASS or FAIL per output
    py -I -X utf8 analysis/reproduce.py --write    rewrite the stored outputs (maintainers only)

Each job is one script run on tracked files only (analysis/results/<run>/forks/, the state files, the public traces
where a script needs them). A job whose input run is not in the repository is reported as SKIPPED.
The registered scripts are frozen by their pre-registrations; the "independent" jobs are the second implementations
written without the first; the "exploratory" jobs carry no registered rule.

Two scripts behind numbers of the paper are not jobs here: analysis/public_runs_outside.py reads the four sets outside
the competition through a dataset viewer on the network (its output is analysis/results/public/outside.txt), and
analysis/make_spans_g.py rebuilds the spans of the graph nodes from the snapshots (it prints the share of nodes that
resolve, 95.6%, and stores no report). Scripts that write their report to a file take --no-write or --stdout here,
which prints the same report instead.
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
    ('10 another model family, Qwen2.5-Coder-32B', 'registered',
     ['analysis/analyze_d.py', 'd2', f'{R}/qwen/forks'], f'{R}/qwen/analyze_d2_qwen.txt', [f'{R}/qwen/forks/results.jsonl']),
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
    ('10 Qwen2.5-Coder-32B, independent', 'independent',
     ['analysis/rederive_cd.py', 'd2', f'{R}/qwen/forks', '--tag', 'qwen', '--no-write'], f'{R}/rederive_d2_qwen.txt',
     [f'{R}/qwen/forks/results.jsonl']),
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
    ('13 the address written as a search hit: X1, X2', 'registered',
     ['analysis/analyze_13.py', f'{R}/13/forks'], f'{R}/13/analyze_13.txt',
     [f'{R}/13/forks/results.jsonl', f'{R}/c/forks/results.jsonl']),
    ('13 the address written as a search hit, independent', 'independent',
     ['analysis/rederive_13.py', f'{R}/13/forks', f'{R}/c/forks', '--no-write'], f'{R}/rederive_13.txt',
     [f'{R}/13/forks/results.jsonl', f'{R}/c/forks/results.jsonl', 'data/snapshots']),
    ('15 the own search of the agent with and without its line numbers: Q1, Q2, Q3', 'registered',
     ['analysis/analyze_15.py', f'{R}/15/forks'], f'{R}/15/analyze_15.txt',
     [f'{R}/15/forks/results.jsonl', 'analysis/fork_states_s/states.jsonl']),
    ('15 the own search of the agent, independent', 'independent',
     ['analysis/rederive_15.py', f'{R}/15/forks', '--no-write'], f'{R}/rederive_15.txt',
     [f'{R}/15/forks/results.jsonl', 'analysis/fork_states_s/states.jsonl', 'data/snapshots']),
    ('16 the task prompt and the first model call: W1, W2, W3', 'registered',
     ['analysis/analyze_16.py', f'{R}/16/forks'], f'{R}/16/analyze_16.txt',
     [f'{R}/16/forks/results_16.jsonl', 'analysis/fork_states_w/first_call_states.jsonl']),
    ('16 the task prompt and the first model call, independent', 'independent',
     ['analysis/rederive_16.py', f'{R}/16/forks', '--no-write'], f'{R}/rederive_16.txt',
     [f'{R}/16/forks/results_16.jsonl']),
    ('17 the own search of the agent on a model of another family: Q1, Q2, Q3', 'registered',
     ['analysis/analyze_17.py', f'{R}/17/forks'], f'{R}/17/analyze_17.txt',
     [f'{R}/17/forks/results.jsonl', 'analysis/fork_states_s/states.jsonl']),
    ('17 the own search of the agent on a model of another family, independent', 'independent',
     ['analysis/rederive_15.py', f'{R}/17/forks', '--no-write'], f'{R}/rederive_17.txt',
     [f'{R}/17/forks/results.jsonl', 'analysis/fork_states_s/states.jsonl', 'data/snapshots']),
    ('19 the two one-call contrasts on seven hosted models: V1, V2', 'registered',
     ['analysis/analyze_19.py', '--no-write'], f'{R}/19/analyze_19.txt',
     [f'{R}/19/10', f'{R}/19/17', 'analysis/fork_states_d/states.jsonl', 'analysis/fork_states_s/states.jsonl']),
    ('19 the two one-call contrasts on seven hosted models, independent', 'independent',
     ['analysis/rederive_19.py', '--no-write'], f'{R}/rederive_19.txt',
     [f'{R}/19/10', f'{R}/19/17', 'analysis/fork_states_d/states.jsonl', 'analysis/fork_states_s/states.jsonl',
      'data/snapshots']),
    ('14 whole runs scored by tests: T1, T2, T3', 'registered',
     ['analysis/analyze_14.py', f'{R}/14', '--csv'], f'{R}/14/analyze_14.txt',
     [f'{R}/14/N/seed1/task_results.jsonl', f'{R}/14/NAF/seed1/task_results.jsonl', 'data/tasks.jsonl']),
    ('14 whole runs scored by tests, independent', 'independent',
     ['analysis/rederive_14.py', f'{R}/14', '--no-write'], f'{R}/rederive_14.txt',
     [f'{R}/14/N/seed1/task_results.jsonl', f'{R}/14/NAF/seed1/task_results.jsonl', 'data/tasks.jsonl']),
    ('whole runs: runs shown every changed region against the others', 'exploratory',
     ['analysis/explore_every_region.py', '--no-write'], f'{R}/explore_every_region.txt', [f'{R}/14/runs_14.csv']),
    ('graph-tool calls by the agent itself under two wordings of the task prompt', 'exploratory',
     ['analysis/explore_graph_calls.py', '--no-write'], f'{R}/explore_graph_calls.txt',
     [f'{R}/09/forks/results_09.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'analysis/fork_states_g/fresh_states.jsonl',
      'data/forks_14_modal/out_14']),
    ('what the neighbor lists at the paused steps are made of, and which kind the next call reads', 'exploratory',
     ['analysis/explore_neighbor_kinds.py'], f'{R}/explore_neighbor_kinds.txt',
     [f'{R}/v6/forks/results.jsonl', f'{R}/12/forks/results.jsonl', 'data/snapshots', 'analysis/fork_states']),
    ('the kinds of neighbor at the paused steps, independent', 'independent',
     ['analysis/rederive_neighbor_kinds.py'], f'{R}/rederive_neighbor_kinds.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      f'{R}/12/forks/results.jsonl', f'{R}/c/forks/results.jsonl', 'data/snapshots',
      'analysis/fork_states/states.jsonl', 'analysis/fork_states_d/states.jsonl']),
    ('02 and 03 one step: concentration, leave-one-out, matched entries, other outcomes', 'exploratory',
     ['analysis/explore_b.py', '--stdout'], f'{R}/explore_b.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      'analysis/fork_states/states.jsonl']),
    ('02 and 03 one step, independent: failures and complete states', 'independent',
     ['analysis/recount_b.py', '--no-write'], f'{R}/recount_b.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      'analysis/fork_states/states.jsonl']),
    ('02 and 03 one step, independent: outcomes under its own scorer', 'independent',
     ['analysis/recount_b_outcomes.py', '--no-write'], f'{R}/recount_b_outcomes.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      'analysis/fork_states/states.jsonl', 'data/cache/snapshot_text']),
    ('02 and 03 one step, independent: outcomes under its own scorer, recursive searches not counted', 'independent',
     ['analysis/recount_b_outcomes.py', '--no-write', '--named-file-only'], f'{R}/recount_b_outcomes_named_file_only.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      'analysis/fork_states/states.jsonl', 'data/cache/snapshot_text']),
    ('02 and 03 one step, independent: the numbers of Sections 3 to 5 with the registered scorer', 'independent',
     ['analysis/rederive_s5.py', '--no-write'], f'{R}/rederive_s5.txt',
     [f'{R}/v5/forks/results.jsonl', f'{R}/v6/forks/results.jsonl', f'{R}/v8/forks/results.jsonl',
      'analysis/fork_states/states.jsonl', 'data/tasks.jsonl', 'data/snapshots']),
    ('pointer audit of Sep 30 (fix units that are graph nodes, reach from the issue text), independent', 'independent',
     ['analysis/rederive_audit.py', '--no-write'], f'{R}/rederive_audit.txt',
     ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
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
    ('public runs, whole runs: the graph against rewirings that keep locality', 'exploratory',
     ['analysis/public_runs_locality_null.py'], f'{R}/public/locality_null.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: which source would have held the fix sites a run never saw', 'exploratory',
     ['analysis/public_runs_sources.py'], f'{R}/public/sources.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots', 'data/embeddings']),
    ('whole runs of eight agents: where every file read starts, and the changed regions by depth and count', 'exploratory',
     ['analysis/explore_read_starts.py'], f'{R}/explore_read_starts.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', f'{R}/14/N/seed1/task_results.jsonl']),
    ('public runs, whole runs: the kind of graph edge between a missed fix site and code the run saw', 'exploratory',
     ['analysis/public_runs_missed_links.py'], f'{R}/public/missed_links.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: fix sites the agent never saw, independent', 'independent',
     ['analysis/rederive_public_missed_regions.py'], f'{R}/public/rederive_missed_regions.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: the kind of graph edge, independent', 'independent',
     ['analysis/rederive_public_missed_links.py'], f'{R}/public/rederive_missed_links.txt',
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
