# 01 (DRAFT): Where the provided code graph's information is lost

**Status: DRAFT, not frozen.** Written by Claude Science on 2026-09-30 for the team's decision; nothing has been run
under it. The authors decide whether to pursue it, resolve the open items at the bottom, and commit the frozen version
to git before any data it governs exists. Rationale and prior art: `docs/claude-science-prior-art-check-2026-09-30.md`.

## Question

In the official harness at the competition setting, at which stage does the provided code graph's information fail to
reach the patch? And when the graph's structure points at a wrong but plausible symbol, does the agent follow it?

GraphLoc found that a graph skill adds about one task (+0.9 points, not significant). GraphLoc's public traces suggest
why (EXPLORATORY): in its base arm, 109 of 318 runs call a graph tool, 26 receive any non-empty result, and most
empty results come from multi-word queries to a tool that only looks up node names. This study replaces those
observations with interventions.

## Fixed setting

- **Model:** `gemma-4-31b-it-qat-w4a16-ct`, served by vLLM with `max_model_len` 32,768, as in the scoring setup.
- **Harness:** `swegemma` from `metric/gemma-4-developer-agent-wheelhouse`, one frozen version (O9), recorded with the
  sha256 of each wheel in every run's meta file.
- **Agent:** the sample-submission prompt and its sampling settings with all nine tools, plus only the changes each arm
  names. The per-task budget and `max_output_tokens` are open items (O2, O3); they are the same in every arm.
- **Graph data:** the provided graph and embedding files, except where an arm rewires one edge (arm C).

## Tasks

The public tasks whose reference patch passes Phase 2 in our sandbox (GraphLoc found 106; we re-verify and commit the
list with its hash before main runs). Stratum: the 13 decoy-bite tasks from the Phase-0 check (NOTES.md, 19:21 and
19:24 entries) vs the rest. A task enters the decoy analysis (H1) only if at least one issue-mentioned node has at
least one graph neighbor; the count of excluded tasks is reported.

## Arms (paired within task and seed)

- **A, pull, true graph:** the sample agent as is. It reproduces GraphLoc's base arm and anchors the funnel.
- **B, push, true graph:** before the agent's first turn, the names that `get_code_neighbors` returns for every
  issue-mentioned node are delivered into its context as a short block (definition of "mentioned node" as in the
  Phase-0 decoy-bite check). Implementation is open item O4.
- **C, push, decoy graph:** identical to B, except one delivered neighbor is replaced by a decoy sibling, and the
  served graph file is rewired consistently (the replaced edge removed, the decoy edge added, both directions), so the
  agent's own graph calls agree with the block.
- **D (optional, O8), tools removed:** no graph tools and no block, as the reference for "what the graph adds".

**Decoy sibling, fixed before data.** A node in the same module as the replaced neighbor (the same class if that
neighbor is a method), of the same kind, not gold, not mentioned in the issue, not a true neighbor of any mentioned
node, with node text length within 50% of the replaced neighbor's. It is drawn by a seeded generator whose seed string
is written here at freeze. The replaced neighbor is a gold node when one is delivered (the bite tasks), otherwise a
uniformly drawn delivered neighbor.

## Outcomes

**Visit indicator** (per episode and node): after the block is delivered, the trajectory contains a `read_file` call
whose returned line range overlaps the node's definition span, an edit inside that span, or a graph-tool call naming
the node. Spans come from the task snapshot by AST. Shell views (`cat`, `sed -n`, `grep -n`) count only in a
sensitivity reading.

- **H1, decoy following (primary).** Visit rate of the decoy node in arm C minus the visit rate of the same node in
  arm B, where it is not delivered. Exact two-sided McNemar on the (task, seed) pairs; effect with a task-cluster
  bootstrap 95% CI (10,000 resamples, fixed seed).
  - **FOLLOWS:** effect at least +10 points and p < 0.01.
  - **IGNORES:** the CI upper bound is below +5 points.
  - **INCONCLUSIVE:** otherwise.
- **H2, push raises uptake (primary).** Uptake = a visit to at least one graph-delivered or graph-returned node that
  the issue does not name. Arm B vs arm A, same test.
  - **PUSH-RAISES-UPTAKE:** effect at least +10 points and p < 0.01.
  - **NO-EFFECT:** the CI upper bound is below +5 points.
  - **INCONCLUSIVE:** otherwise.
- **Secondary, no decision attached:** resolve rate per arm (paired exact McNemar, A vs B and B vs C, overall and in
  the bite stratum); in bite tasks, the gold-visit rate in C vs B (does the decoy displace the gold node?); the funnel
  per arm (any graph call, any non-empty result, a result containing a gold node or one of its neighbors, uptake,
  resolved); overflow, lost patches and the context composition at overflow; tokens per episode.
- **Interface failures, counted separately from model failures:** `edit_file` mismatches, empty graph results, malformed
  tool calls, empty patches, context overflow.
- **Control for prior knowledge:** an issue-only prompt (no tools) asking the model to name the file and function to
  change, since models can often name the file from the issue alone (SWE-Bench Illusion). Descriptive.

## Sample size and power (planning calculation, not data)

106 tasks x 2 seeds = 212 pairs per comparison. Simulated with 2,000 datasets per cell, outcomes independent within a
pair (conservative), the H1 rule gives:

| Base visit rate | Decoy visit rate | IGNORES | INCONCLUSIVE | FOLLOWS |
|---|---|---|---|---|
| 2% | 2% | 0.95 | 0.05 | 0.00 |
| 2% | 10% | 0.00 | 0.83 | 0.17 |
| 2% | 15% | 0.00 | 0.15 | 0.85 |
| 2% | 20% | 0.00 | 0.00 | 1.00 |
| 5% | 5% | 0.66 | 0.34 | 0.00 |
| 5% | 15% | 0.00 | 0.50 | 0.50 |
| 5% | 20% | 0.00 | 0.07 | 0.94 |

So the design detects following of about 15 points or more above the base rate, and can call IGNORES when the base
rate is low and the true difference is near zero. The pilot estimates the base visit rate.

## Gate and pilot

- **Pilot (before freeze, EXPLORATORY, seed 0, never pooled with main runs):** 10 tasks (5 bite, 5 not), arms A and B
  only. It checks that the graph tools appear in the prompt, that the block is delivered and how long it is, that the
  visit indicator works on real traces, wall time and tokens per episode, overflow and what fills the context at
  overflow, and the base visit rate of decoy candidates. It has no decoy arm, so it cannot leak H1.
- **Gate (step 1 of the main runner):** arm A on all tasks with seed 1, with these checks:
  - graph tools present in every prompt;
  - complete per-episode records and traces;
  - the harness version equal to the frozen one.

  The resolve rate is reported next to GraphLoc's base runs (26.4-31.1%). What happens on a large deviation is open
  item O5.

## Compute

About 636 episodes for arms A-C (848 with D). GraphLoc ran 212 episodes per notebook run on 4xL4 with 12 concurrent
workers, so this is roughly three to four such runs. A guess, to be replaced by the pilot's measurement. No GPU or
paid compute runs without the team's go-ahead.

## Exploratory

Everything not named as H1 or H2 is EXPLORATORY, including any re-analysis of GraphLoc's public traces. Changes after
the freeze are dated amendments at the bottom of this file.

## Open items for the authors

- **O1. Compaction at scoring.** Match the scoring script exactly once its source is read (the README says a
  `token_threshold` of 14,336; a forum thread says 32,768; a rival entry says the CLI default is none).
- **O2. Budget.** GraphLoc's (40 tool calls, 25 minutes, 60 turns), which makes its traces a reference for arm A, or
  the scoring defaults (100 tool calls, 60 minutes).
- **O3. `max_output_tokens`.** Keep the sample's 16,384, which caps the prompt at 16,384 tokens, or lower it in every
  arm.
- **O4. Push mechanism.** A declarative SequentialAgent (a prefetch sub-agent with only `get_code_neighbors`, whose
  `output_key` fills the coder's instruction), which is a legal submission, or a research-harness prompt injection,
  which is deterministic.
- **O5. Gate failure.** What to do if arm A deviates strongly from GraphLoc's base resolve rate.
- **O6. Seeds.** Whether vLLM honors the sampling seed through the harness; if not, "seed" means a repeat index.
- **O7. Indicator details.** The span-overlap threshold for `read_file`, and whether shell views count in the primary.
- **O8. Arm D.** Include it or not.
- **O9. Wheelhouse version.** v28 is current (Sep 30); freeze one and stay on it.
