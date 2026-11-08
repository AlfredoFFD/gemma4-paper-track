# Pre-registration 02: does Gemma follow a false code-graph edge as readily as a true one?

Status: FROZEN on Nov 8, 2026, 7:45 PM EST, with the team's approval delegated to Claude Code ("approve
everything you approve of"), while the replay run was in progress and before any of its output had been read.
Later edits may only add clarifications marked as such; anything computed outside this document is EXPLORATORY
and will be labeled so.

## Question

Gemma-4-31B rarely uses the competition's code graph on its own. When the graph's neighbor list for a function it
is already looking at is put in front of it, does its next read or edit follow a listed neighbor, and does it follow
a planted false neighbor as readily as a true one? Secondary: does it matter whether the list arrived as the result
of a tool call or as a note from the harness?

## Material

- States: GraphLoc's public base-arm traces (3 runs x 106 tasks, official `swegemma` harness, subprocess sandbox,
  4 x L4, temperature 0.2, thinking budget 4,096, 40 tool calls, dated Sep 25-28, 2026). Each run is cut right
  after the first tool result that shows file content, before any edit of repository code and before any
  compaction, with a logged prompt of at most 12,500 tokens at the next call. The cut rule, the in-view rule, the
  node-choice rule and the decoy rule are in `analysis/fork_states.py` (docstring) and were fixed before any
  replay. Up to three fork points per run (the first three content-showing steps). The export gives 525 states
  from 241 runs and 88 tasks.
- Replay: the history is reloaded into the harness's own ADK agent (the base agent: sample prompt, nine tools, no
  adapters, no sub-agent) and the model makes one call through vLLM. No tool executes. Code: `analysis/replay.py`,
  `analysis/kaggle/forks_pilot.py`. Harness wheels: the v28 copies (swegemma 0.2.7), the closest to the traces'
  era; the Kaggle run records every version in `versions.json`.
- Seeds: 1, 2, 3 per state and arm, passed to vLLM. Three seeds, five arms, 525 states = 7,875 replays. The
  states run in a fixed shuffled order with a 9-hour budget; if the session ends early, the analysis uses every
  state whose five arms and three seeds all finished, which is a random subset.

## Arms (the seeded history is identical; only the last piece differs)

| Arm | Last piece |
|---|---|
| A | the fork's own tool result (nothing added) |
| P | an inserted `get_code_neighbors(node)` call and its real result, in the tool's exact format |
| P' | as P, with one true neighbor (chosen by a seeded RNG) replaced by a decoy; list re-sorted alphabetically |
| H | the same result text as a user-role note with one fixed wording (`fork_states.H_WORDING`), no call |
| H' | as H, with the P' list |

The two compared entries both live in files the agent has not opened before the fork, so following either one takes
a new read. The swapped-out entry is a seeded random choice among such true neighbors (preferring one whose file
holds no other listed entry). The decoy is a real node in an unopened file that holds no listed entry, not a
neighbor, not a gold unit, not in view, not a test, drawn from the swapped-out entry's directory (else the queried
node's directory, else the package). Both list positions are logged. Rationale, found on the Nov 8 export before
any replay: most true neighbors sit in the file the agent just opened, so re-reading it would have counted as
following a true edge while no decoy could ever be reached that way.

## Outcomes

A replay's outcome is the model's first function call after the fork. "Touch" of a listed node follows the Sep 30
uptake definition, implemented in `fork_states.touches`: a `read_file` of the node's file whose line range overlaps
the node's span (no range = whole file), an `edit_file` or `write_file` of that file, or a shell view (`cat`, `sed`,
`grep`, ...) of that file overlapping the span or naming the node. Graph-tool calls that name the node count
separately as `graph`.

- Primary, discrimination: D = P(touch of the swapped-out true neighbor | arms P and H) minus P(touch of the decoy
  | arms P' and H'). The two entries occupy one list slot each, both in unopened files, matched by state and seed.
  Base rates for both come from arm A (the agent going there with nothing inserted).
- Per-entry rates: P(touch | listed true entry in an unopened file) over all such entries, P(touch | decoy), and
  the arm-A rates for the same nodes.
- Any-true following: P(any listed true neighbor in an unopened file touched | arm) for A, P, H. The same count
  including neighbors in already-opened files is reported as descriptive only, because re-reading the current file
  touches them without following anything.
- Channel: P(any unopened true touched | P) minus P(any unopened true touched | H), and the same for the decoy
  (P' vs H').
- H4, natural graph use: share of arm-A replays whose next call is a graph tool.
- Interface failures per arm: errors, no function call, malformed arguments, calls to tools that do not exist.
- Fidelity: on at least 12 states, arm A's prompt size from vLLM versus the logged prompt size at the same step.

## Decision rules

Confidence intervals are 95% bootstrap intervals clustered by state (2,000 resamples), computed by
`analysis/analyze_forks.py`. Replays with an interface failure are excluded from rates and reported.

- Fidelity gate: the median absolute relative difference between replayed and logged prompt size is at most 2%.
  If it fails, every result is reported as coming from approximate forks and the gap is stated.
- H1, following above base rate: the lower bound of the CI for [P(any unopened true | P and H) minus P(any
  unopened listed true | A)] is above 0.
- H2, the agent does not check (the headline claim if it holds): H1 holds, and the 90% CI for D lies within
  [-0.02, +0.02]. The agent checks: the lower 95% bound of D is above 0 and P(decoy touched) is below half of
  P(swapped-out touched). Anything else is reported as inconclusive with the interval.
- H3, channel (two-sided): the CI for [P(any true | P) minus P(any true | H)] excludes 0.
- H4 is descriptive.

## Power, stated as assumptions

With 525 states x 3 seeds = 1,575 replays per arm, D is estimated from 3,150 replays on each side. In the traces,
the agent's own next call touched the swapped-out entry in 11 of 525 states (2.1%) and any unopened true neighbor
in 34 (6.5%); those are the expected arm-A base rates. If showing the list lifts the swapped-out entry to 10%,
a decoy rate of 5% or below is distinguishable from it; a difference under about 3 points is not, and the
intervals will say so. If following stays near the base rate in every arm (H1 fails), the paper reports that as
the result and does not test H2.

## What is reported regardless of outcome

All of the rates above with intervals, the fidelity table, the per-arm failure counts, the decoy positions, and the
exact texts inserted. Raw replay outputs (`results.jsonl`) and the state bundle are released with the code.
