# Does Gemma check the code graph? Paused-run replays with true and false edges

DRAFT skeleton, Nov 8. Word budget 3,000. Numbers marked [R] come from the Kaggle replay run and are filled in
after `analysis/analyze_forks.py` runs on `results.jsonl`; everything else is from the public traces and the
offline audit, re-derived by `analysis/trace_stats.py` and `experiments/00-pointer-audit/`.

## Abstract

[150 words, after results.]

## 1. The question

The competition ships a precomputed code graph and three graph tools, and the best-documented entry so far
(GraphLoc) found that they add about one resolved task in a hundred. We ask why, from inside the agent. We
pause real Gemma-4-31B runs right after they read a file, put the graph's neighbor list for a function in that
file in front of the model, and replay one step. Two things can be measured that end-to-end scores cannot:
whether the next read or edit follows a listed neighbor above the rate at which the agent goes there anyway, and
whether a planted false neighbor is followed as readily as a true one. The second number is the one we care
about. An agent that follows a wrong edge as often as a right one is not checking the graph; it is obeying it.

## 2. What the public traces already show (observational)

- 109 of 318 base-arm runs call a graph tool; 26 get a non-empty result. 114 of 135 `search_similar_code` calls
  return nothing: the prompt says "by keyword", the tool resolves node names. `get_code_neighbors` is called 8
  times; `get_code_subgraph` never.
- After a non-empty result, the next read or edit lands on a returned node in 13 of 26 events (50%), but random
  nodes from the same files are "touched" 36% of the time, because whole-file reads touch every node in a file.
  The traces cannot separate steering from the agent's own direction. Forks can.
- Offline, the graph holds a fix location in 84% of tasks but one hop from a function the issue names reaches
  unnamed fix code in only 10% of tasks (19% at two hops). The graph's upside is bounded; a wrong edge's downside
  is not.

## 3. Method

### 3.1 States
[525 states, 241 runs, 88 tasks; the cut rule; before any edit and before compaction; up to three per run.]

### 3.2 Arms
[Table: A, P, P', H, H'. The inserted text is the tool's exact JSON. The decoy rule and why both compared
entries live in unopened files.]

### 3.3 Replay
[The harness's own compiled agent, ADK session seeded from the trace, one model call through vLLM, no tool runs.
Fidelity: replayed vs logged prompt tokens [R].]

### 3.4 Pre-registered tests
[H1 following above base; H2 discrimination with the equivalence margin; H3 channel two-sided; H4 descriptive.
Clustered bootstrap by state. Link to prereg/02-discrimination-forks.md.]

## 4. Results

[R] Fidelity table.
[R] Table: per-arm rates with intervals (any unopened true touched; swapped-out entry; decoy; arm-A base).
[R] D with 95% and 90% intervals; the verdict under the pre-registered rule.
[R] Channel: P vs H, P' vs H'.
[R] Interface failures per arm. Decoy position effects (descriptive).

## 5. What it means for the organizers

[Three readings, one per outcome: it follows without checking (fix the graph's gaps before pushing it); it checks
(deliver the graph, it is safe); it ignores (delivery is not the bottleneck at this point of a run).]

## 6. Related work

[Push vs pull on Gemma (2609.05587); Oracle Poisoning's channel comparison and its Table 7 (an inserted call is
trusted like a real one); Agents Explore but Agents Ignore; RepoMirage decoys; When the Tool Decides; Same
Simulation, Different Evidence (the nearest fork design, true information only); PAIR and Compact-Bench (forks
after compaction); GraphLoc and GraphAudit (same competition). What none of them does: true vs false at the same
state, scored on the next move against a base rate, in the official harness.]

## 7. Limitations

[One step only; pilot scale; the 3-seed pairing; states come from one agent configuration; the decoy is
plausible by construction but not adversarially chosen; the harness version differs from the traces' (recorded);
single model.]

## Reproducibility

[Public notebook, dataset of states, code under Apache 2.0, harness versions in versions.json.]
