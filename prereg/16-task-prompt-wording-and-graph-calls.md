# Pre-registration 16: how the task prompt describes the graph tools, and whether the agent asks

Status: FROZEN on Nov 10, 2026, 9:18 PM EST, by the commit that adds this file, before any call of its full run ran on any
platform. It adds one experiment to pre-registrations 02 to 15 and
changes none of their rules. Tags: [Claude Code] wrote it, after the whole runs of pre-registration 14 showed that the agent had almost
stopped calling the graph tools.

File hashes at freezing (md5):
`analysis/make_states_w.py` `4da3142f4af9d069cfacd7a4b5eaac98`,
`analysis/fork_states_w/first_call_states.jsonl` `e5664dbf436c3c1d2555bb5a1148cc43` (built by that script; not
tracked: it holds the task prompts),
`analysis/modal_g/forks_16_runner.py` `b1bd7c324d7d6968371d581d32a3d323`,
`analysis/modal_g/forks_16_modal.py` `81eba60c23483d1c0d0d065fdbd69e36`,
`analysis/analyze_16.py` `9c6c8573233beffae1e6f9dbc74b23e5`.
Used unchanged:
`analysis/replay.py` `446b85be41d90e0e8fdb7c32dd5ea2f1`,
`analysis/replay_k.py` `6d4e2f73274b9bc77b67eb86488c915d`,
`analysis/analyze_forks.py` `8b22556e948c0df33f80cbeef8c11300`,
`analysis/gates_c.py` `84f2af2d7d7f21813c930c6fd1d354ec`,
`analysis/fork_states.py` `7fc2e4bb40f50b64638a1243e6a636ba`,
`analysis/fork_states_g/fresh_states.jsonl` `2bb8662de0f614d8cbf3be1c9a244f36`.

## Question

Two of our experiments start the competition's starter agent (Gemma-4-31B, harness wheels of Oct 12) from a task
prompt, and the agent behaves differently at its very first model call. Which of the two differences between the
two task prompts decides whether the agent opens with a graph-tool call?

## What was known before (the reason for this experiment)

- Fresh episodes (pre-registrations 08 and 09) use the task prompt that the recorded runs of September logged. The
  first model call is a graph-tool call in 73 of 316 episodes (condition N of pre-registration 09; 23.1%, by task
  [16.5, 30.4]).
- Whole runs (pre-registration 14) use the task prompt that the current evaluator builds. The first model call is a
  graph-tool call in 0 of 103 runs of condition N (0 of 102 when this experiment was designed; the last run had not
  been fetched) and in 0 of 103 runs of condition NAF.

Both counts are exploratory (`analysis/explore_graph_calls.py`). Model, wheels, system prompt and sampling settings
are the same in both settings. On the 103 tasks that have both prompts, the two task prompts differ in two places
and nowhere else (checked line by line by `analysis/make_states_w.py`: 103 of 103 tasks). The September prompt is
the one the harness built up to the wheels of Sep 30 (their source holds the September lines and the September
listing command); the wheels of Oct 12 changed both places.

1. Four lines that describe the graph tools, under the same heading. Each wording is the same in every task.
2. The listing of the workspace's files. The harness of September printed the first 150 entries of the sorted tree:
   the listing has 150 lines in every task and no entry under the package's source folder in any task. The wheels
   of Oct 12 print the tree level by level and leave out the contents of the folders for documentation, tests and
   examples: the listing has 100 lines at the median (91 to 156), with 58 entries under the package's source folder
   at the median (49 to 102). A median of 5% of the current listing's entries are also in the September listing.

## Design

**Tasks.** Every task that has both prompts and in which each prompt holds its four-line block exactly once: 103
tasks (fastapi 60, rich 43). 106 tasks have a September prompt (`analysis/fork_states_g/fresh_states.jsonl`), 103
have a current prompt (the whole-run traces of condition N), 103 have both, and none is dropped for its block.

**Arms.** The agent's only input is the system prompt, as the wheels build it, and one task prompt.

| Arm | Task prompt | Its four lines on the graph tools |
|---|---|---|
| C | the current prompt, as built | current |
| CS | the current prompt | replaced by the September lines; nothing else changes |
| S | the September prompt, as logged | September |
| SC | the September prompt | replaced by the current lines; nothing else changes |

The September lines:

```
This repository has pre-built code graph and embedding data. Use these tools for fast, targeted navigation:
- `search_similar_code(query)`: Find semantically similar functions/classes by keyword.
- `get_code_neighbors(node)`: Find callers, callees, and definitions related to a symbol.
- `get_code_subgraph(nodes)`: Get the induced subgraph for a set of symbols.
```

The current lines (wheels of Oct 12):

```
This repository has pre-built code graph and embedding data indexed by dotted symbol path (e.g. `pkg.module.Class.method`). Use these tools for fast, targeted navigation:
- `search_similar_code(query)`: Find functions/classes with similar precomputed embeddings given a symbol name (e.g. `pkg.module.Class.method`, `Class.method`, or `func_name`).
- `get_code_neighbors(node)`: Find callers and callees of a symbol node (e.g. `pkg.module.Class.method` or `Class.method`).
- `get_code_subgraph(nodes)`: Get the induced call subgraph connecting a list of symbol nodes.
```

`analysis/make_states_w.py` writes one record per task and arm and checks that C and CS, and S and SC, differ in
those four lines only.

**Replay.** One model call per task, arm and seed, seeds 1 to 3: 1,236 calls. The harness's own compiled agent on
the wheels of Oct 12 (adk_submission 0.2.13, swegemma 0.2.11), Gemma-4-31B on one rented A100-80GB, sampling as
shipped, the seed written into the generation config. The request is the one the fresh-episode runner of
pre-registration 09 makes at its first model call: nothing is seeded and the task prompt is the first message. The
runner is a copy of that runner with the horizon set to one model call; no tool executes (every call ends the replay
before it runs). A checkout of the task's snapshot is prepared as before, once per task and pair of arms.

**Order and budget.** Arms C and CS for every task and seed first, then arms S and SC, the tasks in a fixed shuffled
order, so that a budget stop leaves the first rule whole. For a task and a pair of arms, the two calls of seed 1 run
first and the calls of seeds 2 and 3 after them, so that the server holds their prompts in its prefix cache; no
request depends on this order. No new call starts after 30 minutes of the runner's clock (its start-up, about six
minutes, included).

## Outcome

The kind of a first response: a call (it holds at least one call, and the frozen interface-failure rule accepts
every call it holds: `gates_c.failure`), a text answer with no call, malformed (a call to an unknown tool or with
malformed arguments, or neither a call nor a text), or an error. A response is usable if it is a call or a text
answer.

`graph_first`: a usable response holds at least one call of `get_code_neighbors`, `get_code_subgraph` or
`search_similar_code`. A text answer scores 0.

Also recorded for each response: the tools it calls; for each `search_similar_code` call whether the query holds a
blank (a phrase) or not (one symbol-like token).

## Rules

Analysis: `py -I -X utf8 analysis/analyze_16.py <run dir>`. Each rule is a difference between two arms in the share
of replays with `graph_first`, with a 95% bootstrap interval over tasks (`analyze_forks.diff_ci`, 2,000 resamples,
seed 0).

**W1.** CS minus C. Met if the lower bound is above 0.

**W2.** S minus SC. Met if the lower bound is above 0.

**W3, the rest of the prompt, the wording held fixed.** SC minus C, and S minus CS. For each: "more graph calls with
the September listing" if the lower bound is above 0; "fewer" if the upper bound is below 0; "no detectable
difference" if the interval includes 0.

A task is complete if every arm and seed returned a usable response. A malformed response or an error is an
interface failure, counted by arm and excluded. With fewer than 60 complete tasks every rule is reported as
underpowered. If a budget stop left S and SC incomplete, W1 is computed on the tasks complete for C and CS, and W2
and W3 are reported as not run.

No rule, reported after the rules: by arm, the share of `graph_first`; the tool called first (counts); phrases
against symbol-like queries among the `search_similar_code` calls; the share of first calls that are a `read_file`,
a `run_command` search (grep, rg, find), a graph tool, or something else.

## Gate

A smoke test on 6 tasks, every arm, one seed (24 calls): at least 80% usable responses in every arm. Its outcomes
are not read.

## What the smoke test showed

It ran on Nov 10, 2026 and ended at 8:53 PM EST, before this text was frozen: the first 6 tasks of the run order (4
of fastapi, 2 of rich), every arm, seed 1, 24 calls on one A100-80GB with the wheels of Oct 12.

- Usable responses: C 6 of 6, CS 6 of 6, S 6 of 6, SC 6 of 6. No error and no malformed response. The gate is
  passed.
- Prompt sizes in tokens, median (smallest to largest): C 3,610 (3,533 to 4,416); CS 3,546 (3,469 to 4,352); S 4,791
  (3,816 to 5,396); SC 4,855 (3,880 to 5,460).
- Arm C has the size that the whole run of pre-registration 14 logged for its first model call, in all 6 tasks (a
  difference of 0 tokens). Arm S is 67 tokens above the size the September run logged, in all 6 tasks, as in the
  smoke test of pre-registration 09.
- CS minus C is -64 tokens in all 6 tasks, and SC minus S is +64 tokens in all 6 tasks: the swap changes the same
  64 tokens in both directions and nothing else.
- For the time estimate, the timing of the calls was read by pair of arms (start, duration, number of completion
  tokens), and the server's throughput lines.
- Nothing else of the rows was read: no tool name, no stop reason, no text. The runner prints none of them. The rows
  stay on the run's volume under `/out_16_smoke` and are not part of the full run.
- After the smoke test the runner changed in one place, and no request changed: the calls of seed 1 of a task and
  pair of arms now run before the calls of seeds 2 and 3, and up to 16 checkouts may be open at once instead of 8.
  The changed runner ran on the same platform with a scripted model in place of the server (72 calls, no error). It
  has not run on a GPU.

## Stated limits

- W3 compares two listings that differ in several ways at once (length, order, and which entries they hold). A
  difference there is the effect of the listing as a whole.
- One model call. The run says whether the agent opens with a graph call, not whether it calls a graph tool later.
- CS and SC are prompts that no evaluator built.
- The current prompt is the one our whole runs built on the rented platform. Its listing is sorted by the
  platform's locale (C.UTF-8), so a hosted evaluator may order or cut it differently.
- Arms S and SC replay a prompt that an earlier harness version logged, on the wheels of Oct 12, as
  pre-registrations 08 and 09 did.
- Three seeds of a task and arm share one prompt at temperature 0.2, so they are correlated. The intervals are over
  tasks.
- Interface failures are excluded by arm. If malformed graph calls are more frequent in one arm, the exclusion
  lowers that arm's share. The counts by arm are reported.
- One model, two repositories.

## Power, stated as assumptions

In the fresh episodes of pre-registration 09 the share is 23.1% with a half-width of 7 points by task, and it is 0 in
the whole runs. If one arm of a contrast is near 23% and the other near 0, the half-width of the paired difference
is assumed near 7 points: a difference of 10 points or more should be detected, and one under 5 points will mostly
read as "not met" or "no detectable difference".

## What has been seen

Every earlier result of this repository, among them the two counts above. From the smoke test: the counts of usable
responses by arm, the prompt sizes and the timing of the calls, and nothing else. The analysis script was tested on
rows written by a scripted model and on made-up rows. No other call of the four arms exists.

A start made by mistake. At 9:14 PM on Nov 10 the full run was started before the commit that freezes this file
existed (the command that writes this file had failed, and the commands after it ran all the same). The app was
stopped at 9:15:54 PM, during its start-up, which takes about six minutes before the first model call. It made
no call: its output folder holds the version and platform records and no result row. The run registered here
starts after the freeze, into the same folder.

## Budget

One rented A100-80GB. The full run: 1,236 calls, no new call after 30 minutes of the runner's clock (`--minutes 30`). Expected, from
the smoke test's timing: about 22 minutes (19 to 25), about 1.2 dollars, and at most about 1.8 dollars at the cap.
The margin under the cap is thin. In the smoke test the server needed 354 s to start, and 12 calls with prompts it
had not seen took 18 s; the estimate assumes that the calls of seeds 2 and 3 find their prompt in the server's
prefix cache. The smoke test: one container for about 7 minutes, about 0.40 dollars. Three plumbing runs without a
GPU, about 2 minutes each: about 0.06 dollars in all.

## What is reported regardless of outcome

Every rule with its interval, whichever way it falls; every arm's share; interface failures by arm; the raw
per-call records; the versions recorded by the run.

## Amendments

None.
