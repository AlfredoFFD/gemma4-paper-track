"""Re-run every analysis of the paper on the raw replay outputs in this repository and compare with the stored outputs.

Usage (from the repo root; Python 3.11 or later, standard library only):
    py -I -X utf8 analysis/reproduce.py --help        this text, shortened
    py -I -X utf8 analysis/reproduce.py --list        every job: number, kind, label, and whether its inputs are here
    py -I -X utf8 analysis/reproduce.py               run every job; prints PASS, FAIL or SKIPPED per stored output
    py -I -X utf8 analysis/reproduce.py --job 12 --job "the reading rule"
                                                      run only the jobs whose number is 12 or whose label contains
                                                      the text (case ignored; a number matches a label only as a
                                                      whole word); --job may be given several times
    py -I -X utf8 analysis/reproduce.py --write       rewrite the stored outputs (maintainers only)
The last line is "PASS n, FAIL n, SKIPPED n". The exit status is 0 when no job failed, 1 otherwise.

Each job is one script whose report is compared, byte for byte after line endings, with a stored output under
analysis/results/. A job declares every input it reads that git does not track; a job with a missing input is not run
and is reported as SKIPPED with the first missing path.

What runs from a clone: the jobs whose inputs are all tracked (the raw replay outputs under analysis/results/ and the
tracked state files). Run --list to see them; in a clone without data/ they are the jobs marked "ready".
What needs more: most jobs also read the competition data (data/tasks.jsonl, data/snapshots/, data/graphs/,
data/embeddings/; join the competition on Kaggle, then kaggle competitions download -c gemma-4-developer-agent -p data/;
it is not redistributed here) or caches the scripts build from it under data/cache/ (analysis/snapshot_index.py,
analysis/make_oracle_18.py, analysis/make_oracle_22.py), state files that git ignores because they hold task text or
other teams' runs (rebuilt from the data by analysis/make_states_*.py and analysis/fork_states.py), other teams'
public runs (data/graphloc/, data/public_traces/; analysis/results/public/README.md says how to get them), or raw
output folders of our own runs that are not distributed (data/forks_*_modal/).

The registered scripts are frozen by their pre-registrations; the "independent" jobs are the second implementations
written without the first; the "exploratory" jobs carry no registered rule.

Two scripts behind numbers of the paper are not jobs here: analysis/public_runs_outside.py reads the four sets outside
the competition through a dataset viewer on the network (its output is analysis/results/public/outside.txt), and
analysis/make_spans_g.py rebuilds the spans of the graph nodes from the snapshots (it prints the share of nodes that
resolve, 95.6%, and stores no report). Scripts that write their report to a file take --no-write or --stdout here,
which prints the same report instead.
"""
import argparse
import re
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
    ('18 whole runs told where the fix is, as names or as addresses: U1 to U4', 'registered',
     ['analysis/analyze_18.py', '--no-write'], f'{R}/18/analyze_18.txt',
     [f'{R}/18/N/seed2/task_results.jsonl', f'{R}/18/ON/seed2/task_results.jsonl', f'{R}/18/OA/seed2/task_results.jsonl',
      f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl']),
    ('18 whole runs told where the fix is, independent', 'independent',
     ['analysis/rederive_18.py', '--no-write'], f'{R}/rederive_18.txt',
     [f'{R}/18/N/seed2/task_results.jsonl', f'{R}/18/ON/seed2/task_results.jsonl', f'{R}/18/OA/seed2/task_results.jsonl',
      'data/tasks.jsonl']),
    ('18 whole runs told where the fix is: endings by arm, and outcomes by ending', 'exploratory',
     ['analysis/explore_endings_18.py'], f'{R}/explore_endings_18.txt', [f'{R}/18/runs_18.csv']),
    ('18 whole runs told where the fix is: what each arm reads and when it first edits a changed region', 'exploratory',
     ['analysis/explore_cost_18.py'], f'{R}/explore_cost_18.txt',
     [f'{R}/18/N/seed2/task_results.jsonl', f'{R}/18/ON/seed2/task_results.jsonl', f'{R}/18/OA/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots']),
    ('18 whole runs told where the fix is: what each arm reads, independent', 'independent',
     ['analysis/rederive_cost_18.py', '--no-write'], f'{R}/rederive_cost_18.txt',
     [f'{R}/18/N/seed2/task_results.jsonl', f'{R}/18/ON/seed2/task_results.jsonl', f'{R}/18/OA/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots']),
    ('22 whole runs told where the fix is, second seed, the half that ran: L1 to L7', 'registered',
     ['analysis/analyze_22.py', '--no-write'], f'{R}/22/analyze_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl']),
    ('22 whole runs told where the fix is, second seed, independent', 'independent',
     ['analysis/rederive_22.py', '--no-write'], f'{R}/rederive_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl']),
    ('23 whole runs with the graph answers pushed, as names and with addresses: G0, A1 to A3', 'registered',
     ['analysis/analyze_23.py', '--no-write'], f'{R}/23/analyze_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl']),
    ('23 whole runs with the graph answers pushed, independent', 'independent',
     ['analysis/rederive_23.py', '--no-write'], f'{R}/rederive_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl']),
    ('23 beside a shipped run of the same seed: resolved on the 40 tasks that have one', 'exploratory',
     ['analysis/explore_same_seed_23.py'], f'{R}/23/explore_same_seed_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl']),
    ('23 against the stored shipped run of 14 with its lists replayed offline: uptake and first reads', 'exploratory',
     ['analysis/explore_push_baseline_23.py'], f'{R}/explore_push_baseline_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl', 'data/graphs']),
    ('14, 18, 22 and 23: the funnel of whole runs by arm (shown, patched, resolved), checked against the second scripts', 'exploratory',
     ['analysis/explore_funnel.py'], f'{R}/explore_funnel.txt',
     [f'{R}/14/runs_14.csv', f'{R}/18/runs_18.csv', f'{R}/22/runs_22.csv', f'{R}/23/runs_23.csv',
      f'{R}/14/N/seed1/task_results.jsonl', f'{R}/14/NAF/seed1/task_results.jsonl',
      f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', 'data/tasks.jsonl']),
    ('23: the one-call outcome of the replays, scored at the pushed lists of the whole runs', 'exploratory',
     ['analysis/explore_next_call_23.py'], f'{R}/explore_next_call_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl', 'data/graphs']),
    ('03 and 23: addresses against names by how far into its run the step is', 'exploratory',
     ['analysis/explore_step_position.py'], f'{R}/explore_step_position.txt',
     [f'{R}/c/forks/results.jsonl', f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl', 'data/graphs']),
    ('the replays: how often an unaltered replay repeats the recorded next call', 'exploratory',
     ['analysis/explore_replay_fidelity.py'], f'{R}/explore_replay_fidelity.txt',
     [f'{R}/c/forks/results.jsonl', f'{R}/w/forks/results.jsonl', f'{R}/15/forks/results.jsonl']),
    ('12: whether the next call opens the neighbor file at all, file and lines against the file alone', 'exploratory',
     ['analysis/explore_file_open_12.py'], f'{R}/explore_file_open_12.txt',
     [f'{R}/12/forks/results.jsonl', f'{R}/c/forks/results.jsonl', f'{R}/w/forks/results.jsonl', 'data/snapshots']),
    ('23: the call after a pushed list, by how much of the read stands before the list', 'exploratory',
     ['analysis/explore_list_position_23.py'], f'{R}/explore_list_position_23.txt',
     [f'{R}/23/PE/seed2/task_results.jsonl', f'{R}/23/PH/seed2/task_results.jsonl', f'{R}/14/N/seed1/task_results.jsonl', 'data/tasks.jsonl', 'data/graphs']),
    ('22 second seed: endings by arm, and outcomes by ending', 'exploratory',
     ['analysis/explore_endings_18.py', '--csv', f'{R}/22/runs_22.csv', '--launch', '22',
      '--manifest', 'analysis/oracle_18/manifest.json'],
     f'{R}/22/explore_endings_22.txt', [f'{R}/22/runs_22.csv']),
    ('22 second seed: what each arm reads and when it first edits a changed region', 'exploratory',
     ['analysis/explore_cost_18.py', '--experiment', '22'], f'{R}/22/explore_cost_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl'] + ['data/snapshots']),
    ('22 second seed: where each arm starts its reads and how it reaches the places of its note', 'exploratory',
     ['analysis/explore_reach_22.py'], f'{R}/explore_reach_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl'] + ['data/snapshots', 'data/cache/oracle_22']),
    ('18 and 22 together: lines read and where the first read of a file of the note starts', 'exploratory',
     ['analysis/explore_cost_pooled.py'], f'{R}/22/explore_cost_pooled.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots', 'data/cache/oracle_22']),
    ('22 second seed: what each arm reads, independent', 'independent',
     ['analysis/rederive_cost_22.py', '--no-write'], f'{R}/22/rederive_cost_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots', 'data/cache/oracle_22']),
    ('18 and 22: where the first read of a file of the note starts, independent', 'independent',
     ['analysis/rederive_first_reads_18_22.py', '--no-write'], f'{R}/rederive_first_reads_18_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots', 'data/cache/oracle_22']),
    ('22 second seed: reads, lines read and first reads of a file of the note, a third count', 'independent',
     ['analysis/rederive_reads_22.py', '--no-write'], f'{R}/rederive_reads_22.txt',
     [f'{R}/22/N/seed3/task_results.jsonl', f'{R}/22/OF/seed3/task_results.jsonl', f'{R}/18/N/seed2/task_results.jsonl', 'data/tasks.jsonl', 'data/snapshots', 'data/cache/oracle_22']),
    ('one-call contrasts of 03, 12, 15 and 20: intervals with tasks resampled instead of steps', 'exploratory',
     ['analysis/explore_cluster_bootstrap.py'], f'{R}/explore_cluster_bootstrap.txt',
     [f'{R}/v6/forks/results.jsonl', f'{R}/12/forks/results.jsonl', f'{R}/15/forks/results.jsonl',
      f'{R}/20/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl', 'analysis/fork_states_s/states.jsonl']),
    ('18 and 22 together: resolved, patch placement and regions shown with each task counted once', 'exploratory',
     ['analysis/explore_oracle_once.py'], f'{R}/22/explore_oracle_once.txt', [f'{R}/18/runs_18.csv', f'{R}/22/runs_22.csv']),
    ('18 and 22 together: each task counted once, independent', 'independent',
     ['analysis/rederive_oracle_once.py', '--no-write'], f'{R}/22/rederive_oracle_once.txt', [f'{R}/18/runs_18.csv', f'{R}/22/runs_22.csv']),
    ('the graphs: how many definitions a text search for the name of a neighbor returns', 'exploratory',
     ['analysis/explore_graph_ambiguity.py', '--no-write'], f'{R}/explore_graph_ambiguity.txt',
     ['data/graphs', 'data/snapshots', 'data/tasks.jsonl', f'{R}/c/forks/results.jsonl']),
    ('supplement to 15 and 20: the next call opens a hit or noted file at all, by condition', 'exploratory',
     ['analysis/explore_file_open_15_20.py'], f'{R}/explore_file_open_15_20.txt',
     [f'{R}/20/forks/results.jsonl', f'{R}/15/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl',
      'analysis/fork_states_s/states.jsonl', f'{R}/15/analyze_15.txt', f'{R}/20/analyze_20.txt']),
    ('the graphs: the share of nodes for which a file and a line range are found', 'exploratory',
     ['analysis/spans_share.py'], f'{R}/spans_share.txt', ['analysis/fork_states_g/spans_manifest.json']),
    ('20 asked or told, the same search hits: T1 to T4', 'registered',
     ['analysis/analyze_20.py', '--no-write'], f'{R}/20/analyze_20.txt',
     [f'{R}/20/forks/results.jsonl', f'{R}/15/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl',
      'analysis/fork_states_s/states.jsonl']),
    ('20 asked or told, independent', 'independent',
     ['analysis/rederive_20.py', '--no-write'], f'{R}/rederive_20.txt',
     [f'{R}/20/forks/results.jsonl', f'{R}/15/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl',
      'analysis/fork_states_s/states.jsonl', 'data/snapshots']),
    ('24 asked or told on seven hosted models: W1, W2, W3', 'registered',
     ['analysis/analyze_24.py', '--no-write'], f'{R}/24/analyze_24.txt',
     [f'{R}/24/zai-org__GLM-5.3-Flash/results.jsonl', f'{R}/20/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl', 'analysis/fork_states_s/states.jsonl']),
    ('24 asked or told on seven hosted models, independent', 'independent',
     ['analysis/rederive_24.py', '--no-write'], f'{R}/rederive_24.txt',
     [f'{R}/24/zai-org__GLM-5.3-Flash/results.jsonl', f'{R}/20/forks/results.jsonl', 'analysis/fork_states_t/states.jsonl', 'analysis/fork_states_s/states.jsonl']),
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
    ('whole runs of eight agents: where every argument of every call comes from; fix places the task names', 'exploratory',
     ['analysis/explore_arguments.py'], f'{R}/explore_arguments.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', 'data/graphs', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs of eight agents: the moves the agent makes against the call graph', 'exploratory',
     ['analysis/explore_graph_moves.py'], f'{R}/explore_graph_moves.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', 'data/graphs', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs of eight agents: where reads start, independent', 'independent',
     ['analysis/rederive_read_starts.py'], f'{R}/rederive_read_starts.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', 'data/graphs', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs of eight agents: where arguments come from, independent', 'independent',
     ['analysis/rederive_arguments.py'], f'{R}/rederive_arguments.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', 'data/graphs', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs of eight agents: moves against the call graph, independent', 'independent',
     ['analysis/rederive_graph_moves.py'], f'{R}/rederive_graph_moves.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', 'data/graphs', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs: are the regions of a fix shown independently, and fixes in one file against several', 'exploratory',
     ['analysis/explore_independence.py'], f'{R}/explore_independence.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', f'{R}/14/N/seed1/task_results.jsonl']),
    ('whole runs: regions shown independently, one file against several, independent', 'independent',
     ['analysis/rederive_independence.py'], f'{R}/rederive_independence.txt', PUBLIC + ['data/tasks.jsonl', 'data/snapshots', f'{R}/14/N/seed1/task_results.jsonl']),
    ('the code graphs read as text: what an edge is (edge types, both ways, name occurrence, search hits)', 'exploratory',
     ['analysis/explore_graph_names.py', '--no-write'], f'{R}/explore_graph_names.txt', ['data/graphs']),
    ('the shape of the reference fixes: hunks, files, repeats', 'exploratory',
     ['analysis/explore_fix_shape.py', '--no-write'], f'{R}/explore_fix_shape.txt',
     ['data/tasks.jsonl', f'{R}/14/runs_14.csv']),
    ('whole runs of eight agents: where every file read starts, and the changed regions by depth and count', 'exploratory',
     ['analysis/explore_read_starts.py'], f'{R}/explore_read_starts.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/snapshots', 'data/public_traces', f'{R}/14/N/seed1/task_results.jsonl']),
    ('public runs, whole runs: missed regions within reach of shown code by a call edge and by a search for a name', 'exploratory',
     ['analysis/public_runs_lexical_reach.py'], f'{R}/public/lexical_reach.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: missed regions within reach of shown code, recounted by a second script (two edge definitions)', 'exploratory',
     ['analysis/rederive_public_reach.py'], f'{R}/public/rederive_reach.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs of September: graph-tool calls and their answers, recounted by a second script', 'independent',
     ['analysis/rederive_public_graph_calls.py'], f'{R}/public/rederive_graph_calls.txt',
     PUBLIC),
    ('public runs, whole runs: missed regions within reach of shown code by a search for a name in both directions', 'exploratory',
     ['analysis/public_runs_lexical_reach_both.py'], f'{R}/public/lexical_reach_both.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
    ('public runs, whole runs: which same-named definition four rules pick on the ambiguous missed places', 'exploratory',
     ['analysis/explore_ambiguous_pick.py'], f'{R}/public/explore_ambiguous_pick.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots', 'data/wheelhouse/latest/swegemma-0.2.11-py3-none-any.whl']),
    ('public runs, whole runs: a search for a name in both directions against the call edge, independent', 'independent',
     ['analysis/rederive_public_reach_both.py'], f'{R}/public/rederive_reach_both.txt',
     PUBLIC + ['data/tasks.jsonl', 'data/graphs', 'data/snapshots']),
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


# Inputs that git does not track and that a job reads beyond the ones in its own entry above, keyed by label. Found by
# running every job in a clean export of the repository (no data/) and reading each failure, and by recording the
# files each job opens on a machine that holds every input. The snapshot texts are unpacked from data/snapshots/ into
# data/cache/snapshot_text/ on first use (analysis/nodes.py), so data/snapshots stands for both.
SNAP = 'data/snapshots'
SNAP_INDEX = 'data/cache/snapshot_files'   # built by analysis/snapshot_index.py from data/snapshots
ORACLE_18 = 'data/cache/oracle_18'         # built by analysis/make_oracle_18.py from the competition data
STATES_W = 'analysis/fork_states_w/first_call_states.jsonl'
DATA = {
    'public runs, whole runs: a search for a name in both directions against the call edge, independent': [SNAP_INDEX],
    'public runs, whole runs: missed regions within reach of shown code by a search for a name in both directions': [SNAP_INDEX],
    'public runs, whole runs: missed regions within reach of shown code, recounted by a second script (two edge definitions)': [SNAP_INDEX],
    'public runs, whole runs: missed regions within reach of shown code by a call edge and by a search for a name': [SNAP_INDEX],
    '24 asked or told on seven hosted models: W1, W2, W3': [SNAP],
    '24 asked or told on seven hosted models, independent': [SNAP],
    'one-call contrasts of 03, 12, 15 and 20: intervals with tasks resampled instead of steps': [SNAP],
    '02 one step: following, discrimination, channel': [SNAP],
    '03 one step: force, encoding, structure': [SNAP],
    '04 gates': [SNAP],
    '04 parts of an entry, false entry': [SNAP],
    '05 tool channel': [SNAP],
    '05 second model, 26B-A4B': [SNAP],
    '05 second model, E4B': [SNAP],
    '10 another model family, Qwen2.5-Coder-32B': [SNAP],
    '06 five calls': [SNAP],
    '06 five calls, supplement': [SNAP],
    '07 rendering': [SNAP],
    '08 and 09 fresh episodes: N1, A1, A2': [SNAP_INDEX],
    '08 and 09 fresh episodes, independent': [SNAP_INDEX],
    '04 independent': [SNAP],
    '05 tool channel, independent': [SNAP, 'data/forks_c_modal/out/results.jsonl'],
    '05 26B-A4B, independent': [SNAP],
    '05 E4B, independent': [SNAP],
    '10 Qwen2.5-Coder-32B, independent': [SNAP],
    '06 five calls, independent': [SNAP, 'data/tasks.jsonl'],
    '07 rendering, independent': [SNAP],
    'five calls, call by call': [SNAP],
    'supplement: task-clustered intervals, the false entry in detail, seed agreement, calls to the fix': [SNAP],
    'what a name without an address costs in calls': [SNAP],
    '12 a file without lines: P1 to P3': [SNAP],
    '13 the address written as a search hit: X1, X2': [SNAP],
    '18 whole runs told where the fix is, as names or as addresses: U1 to U4': [SNAP],
    '18 whole runs told where the fix is: what each arm reads and when it first edits a changed region': [ORACLE_18],
    '22 whole runs told where the fix is, second seed, the half that ran: L1 to L7': [SNAP],
    '22 second seed: what each arm reads and when it first edits a changed region': [ORACLE_18, 'data/cache/oracle_22'],
    '22 second seed: where each arm starts its reads and how it reaches the places of its note': [ORACLE_18],
    '18 and 22 together: lines read and where the first read of a file of the note starts': [ORACLE_18],
    '22 second seed: what each arm reads, independent': [ORACLE_18],
    '18 and 22: where the first read of a file of the note starts, independent': [ORACLE_18],
    '19 the two one-call contrasts on seven hosted models: V1, V2': [SNAP],
    '14 whole runs scored by tests: T1, T2, T3': [SNAP],
    'what the neighbor lists at the paused steps are made of, and which kind the next call reads':
        ['analysis/fork_states/fastapi_11194_r1_f0.json'],
    '02 and 03 one step: concentration, leave-one-out, matched entries, other outcomes':
        [SNAP, 'data/cache/rewired', SNAP_INDEX],
    '02 and 03 one step, independent: outcomes under its own scorer': [SNAP],
    '02 and 03 one step, independent: outcomes under its own scorer, recursive searches not counted': [SNAP],
    'mangled argument names: sensitivity': [SNAP],
    'where the first read lands': [SNAP],
    'public runs, whole runs: when the agent is first shown a line the fix changes': [SNAP],
    'public runs, whole runs: fix sites the agent never saw, against the code graph and rewired graphs': [SNAP_INDEX],
    'public runs, whole runs: from a fix site the run had seen to the ones it missed': [SNAP_INDEX],
    'public runs, whole runs: the graph against rewirings that keep locality': [SNAP_INDEX],
    'public runs, whole runs: which source would have held the fix sites a run never saw': [SNAP_INDEX],
    'whole runs of eight agents: where every argument of every call comes from; fix places the task names':
        [STATES_W, ORACLE_18],
    'whole runs of eight agents: the moves the agent makes against the call graph': [STATES_W, ORACLE_18, SNAP_INDEX],
    'whole runs of eight agents: where arguments come from, independent': [STATES_W],
    'whole runs of eight agents: moves against the call graph, independent': [STATES_W, SNAP_INDEX],
    'whole runs: are the regions of a fix shown independently, and fixes in one file against several': [ORACLE_18],
    'whole runs of eight agents: where every file read starts, and the changed regions by depth and count': [ORACLE_18],
    'public runs, whole runs: the kind of graph edge between a missed fix site and code the run saw': [SNAP_INDEX],
    'public runs, whole runs: fix sites the agent never saw, independent': [SNAP_INDEX],
    'public runs, whole runs: the kind of graph edge, independent': [SNAP_INDEX],
}

# Why an input is missing, by path prefix (the first that matches): (what the report says, where it comes from).
SOURCES = [
    ('data/graphloc', "other teams' public runs", 'analysis/results/public/README.md'),
    ('data/public_traces', "other teams' public runs", 'analysis/results/public/README.md'),
    ('data/forks_', 'raw output of one of our runs, not distributed', ''),
    ('data/cache/snapshot_files', 'the competition data', 'then py -I -X utf8 analysis/snapshot_index.py'),
    ('data/cache/oracle_18', 'the competition data', 'then py -I -X utf8 analysis/make_oracle_18.py'),
    ('data/cache/oracle_22', 'the competition data', 'then analysis/make_oracle_18.py and analysis/make_oracle_22.py'),
    ('data/cache/rewired', 'the competition data', 'then py -I -X utf8 analysis/fork_states.py'),
    ('data/', 'the competition data', ''),
    ('analysis/fork_states', 'a state file that git ignores, built from the data', 'analysis/make_states_*.py, '
                                                                                    'analysis/fork_states.py'),
]


def needs_of(job):
    """Every input of a job that is not under analysis/results/ (those are tracked), in the order they are checked."""
    label, _kind, _args, _stored, needs = job
    out = []
    for n in [*needs, *DATA.get(label, [])]:
        if n not in out:
            out.append(n)
    return out


def first_missing(job):
    return next((n for n in needs_of(job) if not (ROOT / n).exists()), None)


def why(path):
    what, where = next(((w, h) for p, w, h in SOURCES if path.startswith(p)), ('a file that is not tracked', ''))
    return f'needs {what} ({path}{"; " + where if where else ""})'


def run(args):
    tmp = str(Path(tempfile.gettempdir()) / 'reproduce_scratch_output.txt')  # for a script that always writes a file
    args = [tmp if a == '{TMP}' else a for a in args]
    p = subprocess.run([sys.executable, '-I', '-X', 'utf8', *args], cwd=ROOT, capture_output=True)
    return p.returncode, p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n'), p.stderr.decode('utf-8', 'replace')


def select(texts):
    """Indices of the jobs whose number (as --list prints it, from 1) equals one of the texts or whose label contains
    it (case ignored). A text of digits matches a label only as a whole word, so --job 1 is job 1 and not every label
    with a 1 in it, while --job 11 is job 11 and the jobs of pre-registration 11."""
    chosen = set()
    for t in texts:
        if t.isdigit():
            hits = [i for i, job in enumerate(JOBS) if int(t) == i + 1 or re.search(rf'\b{t}\b', job[0])]
        else:
            hits = [i for i, job in enumerate(JOBS) if t.lower() in job[0].lower()]
        if not hits:
            sys.exit(f'--job {t!r}: no job has this number or a label that contains it (see --list)')
        chosen.update(hits)
    return sorted(chosen)


def show_list():
    ready = 0
    for i, job in enumerate(JOBS):
        label, kind = job[0], job[1]
        miss = first_missing(job)
        ready += miss is None
        state = 'ready' if miss is None else why(miss)
        print(f'{i + 1:3d}  {kind:<11}  {label}\n       {state}')
    print(f'{len(JOBS)} jobs, {ready} with every input present')


def main():
    unknown = [k for k in DATA if k not in {job[0] for job in JOBS}]
    if unknown:
        sys.exit(f'reproduce.py: DATA names a label that is not a job: {unknown[0]!r}')
    ap = argparse.ArgumentParser(
        prog='analysis/reproduce.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Re-run the analyses behind the paper and compare each report with its stored output under\n'
                    'analysis/results/. Each job prints PASS (identical), FAIL (the script failed or its report\n'
                    'differs) or SKIPPED (an input that git does not track is missing: the competition data, a cache\n'
                    'built from it, a state file that git ignores, or other teams\' public runs). The last line is\n'
                    '"PASS n, FAIL n, SKIPPED n"; the exit status is 0 when no job failed, 1 otherwise.\n'
                    'From a clone without data/, the jobs that need only tracked files run; --list shows which.',
        epilog='Run from the repository root with py -I -X utf8 (or python3 -I -X utf8). The module docstring says\n'
               'where each kind of missing input comes from.')
    ap.add_argument('--list', action='store_true', help='list every job (number, kind, label) and whether its inputs '
                                                        'are present, then exit')
    ap.add_argument('--job', action='append', default=[], metavar='TEXT',
                    help='run only the jobs whose number equals TEXT or whose label contains TEXT (case ignored; a '
                         'number matches a label only as a whole word, so 11 also picks the jobs of '
                         'pre-registration 11); may be given several times')
    ap.add_argument('--write', action='store_true', help='rewrite the stored outputs instead of comparing '
                                                         '(maintainers only)')
    opts = ap.parse_args()
    if opts.list:
        show_list()
        return
    write = opts.write
    todo = select(opts.job) if opts.job else range(len(JOBS))
    counts = {'PASS': 0, 'FAIL': 0, 'SKIPPED': 0, 'WRITTEN': 0}
    for idx in todo:
        label, kind, args, stored, needs = JOBS[idx]
        n = idx + 1
        miss = first_missing(JOBS[idx])
        if miss:
            print(f'SKIPPED  {n:2d} [{kind}] {label}: {why(miss)}')
            counts['SKIPPED'] += 1
            continue
        code, out, err = run(args)
        path = ROOT / stored
        if code != 0:
            print(f'FAIL     {n:2d} [{kind}] {label}: the script exited with {code}: {err.strip().splitlines()[-1] if err.strip() else ""}')
            counts['FAIL'] += 1
        elif write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out, encoding='utf-8', newline='\n')
            print(f'WRITTEN  {n:2d} [{kind}] {label}: {stored}')
            counts['WRITTEN'] += 1
        elif not path.exists():
            print(f'FAIL     {n:2d} [{kind}] {label}: no stored output {stored}')
            counts['FAIL'] += 1
        else:
            old = path.read_text(encoding='utf-8').replace('\r\n', '\n')
            if old == out:
                print(f'PASS     {n:2d} [{kind}] {label}: identical to {stored} ({len(out.splitlines())} lines)')
                counts['PASS'] += 1
            else:
                a, b = old.splitlines(), out.splitlines()
                i = next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                print(f'FAIL     {n:2d} [{kind}] {label}: differs from {stored} at line {i + 1}')
                print(f'           stored: {a[i][:150] if i < len(a) else "<end>"}')
                print(f'           now:    {b[i][:150] if i < len(b) else "<end>"}')
                counts['FAIL'] += 1
    print(', '.join(f'{k} {v}' for k, v in counts.items() if k != 'WRITTEN' or write))
    sys.exit(1 if counts['FAIL'] else 0)


if __name__ == '__main__':
    main()
