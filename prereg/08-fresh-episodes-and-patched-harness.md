# Pre-registration 08: experiment G (fresh episodes, a patched harness against the stock one, the newest harness wheels)

Status: FROZEN on Nov 10, 2026, 1:29 PM EST, by the commit that adds this file, before any replay of this
experiment ran with a real model on any platform. It adds to pre-registrations 02 to 07 and changes none of their rules.
Tags: [Claude Code] wrote it after three blind readers of the draft asked for an experiment of this kind; [team] had
asked for whatever runs the paper still needs and had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/modal_g/forks_g_runner.py` `022f048f2927fcfd8a1b192192c97c64`,
`analysis/modal_g/forks_g_modal.py` `69a438104a24d0729a9b923ab530b22a`, `analysis/analyze_g.py`
`87cee4f91cc6d1a6bc8a591979d41a24`, `analysis/make_population_g.py` `920a7595fea5053f73a439086a084da4`,
`analysis/fork_states_g/fresh_states.jsonl` `2bb8662de0f614d8cbf3be1c9a244f36`,
`analysis/fork_states_g/population_g.json` `087d2e5f36cb85aff78b5a3fb2fc59ec`. Used unchanged: `analysis/replay.py`
`446b85be41d90e0e8fdb7c32dd5ea2f1`, `analysis/replay_k.py` `6d4e2f73274b9bc77b67eb86488c915d`,
`analysis/modal_w/forks_w_runner.py` `65372125c2e23b48f5ee0e829a5e4167`, `analysis/fork_states_k/population.json`
`036df3cef4d68a4a65ed29919a4cd18d`, `analysis/fork_states_d/states.jsonl` `d3105df0dc4aa43d7bb0afbdd6123b44`,
`analysis/analyze_k.py` `20294af5a37d5348f9bd0e20887b722b`. Code changes that the platform forces after this freeze are
recorded at the end of this file as dated amendments with the new hashes; the outcome definitions and the rules
cannot change.

## Why

What was known when this was written (all of it is in the stored outputs under `analysis/results/`):

1. The mangled line-bound names (`start_line"`) were measured only in replays of earlier histories. Whether a new
   episode shows them is open, and so is what they cost the agent.
2. In the five-call experiment (pre-registration 06) the registered contrast, legible list minus bare names, was not
   met (+3.86 [−1.05, 8.77]). Contrasts that were not registered there: legible list minus no list on being shown a
   changed line was +8.77 [1.75, 15.79] in R and +4.97 [1.46, 9.06] in U, and a rewired list gave +5.56 [1.46, 10.23]
   in U. In that run the no-list arm had the most mangled reads (41% of its ranged reads at the first call, 25% later,
   against 6% to 10% after a legible note). So a note may help by avoiding the defect and not by its content. G1 to
   G3 below separate the two.
3. Every earlier run installed the harness wheels of Sep 30 (adk_submission 0.2.12, swegemma 0.2.7). The competition
   wheelhouse we hold also has newer ones (adk_submission 0.2.13, swegemma 0.2.11, files dated Oct 12). By a file
   comparison the read tool and the handling of tool results are the same in both; no run has used the newer ones.
4. Three blind readers of the draft named the same gap: no consequence is shown beyond the next call, and neither
   proposed change was tested.

## Design

Platform, model (Gemma-4-31B QAT W4A16), server settings and replay code as in pre-registrations 05 to 07: a rented
A100-80GB per run, tensor-parallel size 1, Python 3.12, the harness's own compiled agent and tool functions. The
harness wheels are the newest ones, adk_submission 0.2.13 and swegemma 0.2.11 (with adk_eval_core 0.1.0). If the
platform checks fail with them, an amendment recorded before any full-run replay switches every part to the Sep 30
wheels. Each run records its versions.

**Part "fresh": new episodes.** For each of the 106 tasks with a public base trace, a new episode starts from
nothing: no history is seeded, and the task prompt that the original harness logged for that task is the first
message (`analysis/fork_states_g/fresh_states.jsonl`; the three original runs of a task logged the same prompt).
Arm N, seeds 1 to 3, 318 episodes. The agent makes up to 8 model calls. `read_file` and read-only shell commands
execute through the harness's tool functions on a checkout of the task's snapshot, and the episode stops before the
first call that is anything else, after the eighth model call, or on a response with no call (the rules of
pre-registration 06).

**Part "fix": a patched harness against the stock one, five model calls.** The states of R (74 states, seeds 11 to
15) and U (124 states, seeds 11 to 13) of pre-registration 06 (`analysis/fork_states_k/population.json`, unchanged),
with seeds that no earlier run used. Up to five model calls, tools executing as in pre-registration 06. Three arms:

| Arm | Argument names | Last piece |
|---|---|---|
| A | as the harness handles them: a name the tool does not know is dropped | the pause's own tool result (no list) |
| AF | before a `read_file` call runs, a name that is not a plain identifier and reads `start_line` or `end_line` once quotes, backslashes and spaces are removed is given that name (a well-formed name wins if both are present); nothing else changes, and the call the model wrote is recorded as written | the same |
| EF | as AF | arm E's note (each neighbor with name, file, line range and first definition line), unchanged |

2,226 replays. Outcomes as in pre-registration 06: Yline (the agent is shown a line the gold patch changes: an
executed `read_file` on a target file whose returned lines overlap a changed region, or a single-file shell view that
does) and Yfile; target files are the files the gold patch modifies that were not opened at the pause.

**Part "one step": the encoding contrast on the newest wheels.** Arms H (bare names) and E (legible) on the 407
states, seeds 1 to 3, one model call, no tool executes: the runner of pre-registration 07 unchanged, started with the
newest wheels and these two arms. It also repeats its two prompt-size passes on 24 states.

## Rules

Analysis: `analysis/analyze_g.py <run_dir> --onestep <onestep_run_dir>`.

**N1, the defect in fresh episodes.** Among executed `read_file` calls that carry a line bound (an argument name that
reads `start_line` or `end_line` once quotes, backslashes and spaces are removed), the share whose bound name is
mangled (not a plain identifier). 95% bootstrap interval clustered by task. "The defect occurs in fresh episodes" if
the lower bound is above 2.1%, the share in the 318 original traces (42 of 2,012); otherwise "not shown above the
original traces' share". Reported beside it: how many of the mangled reads returned the file from line 1, the share
at the first model call and at later calls, and the first prompt's size against the size the original run logged.

**G1, both changes together.** EF minus A on Yline, over all complete states of R and U together, seeds 11 to 13.
"The two changes together bring the agent to the fix's lines within five calls" if the lower 95% bound is above 0,
clustered by state; called robust only if the lower bound is also above 0 clustered by task. Otherwise "no detectable
gain from the two changes together".

**G2, the argument fix alone.** AF minus A on Yline, same states and seeds. "Honoring the bound alone raises reach
within five calls" if the lower 95% bound is above 0; otherwise "no detectable gain from the argument fix alone".

**G3, the list beyond the argument fix.** EF minus AF on Yline in R, seeds 11 to 15. "The legible list adds reach
beyond the argument fix" if the lower 95% bound is above 0; otherwise "no detectable gain from the list once the
bound is honored". Reported under both clusterings.

**S1, the encoding effect on the newest wheels.** E minus H on any unopened true neighbor touched (the outcome of
pre-registrations 02 to 05 and 07). "The encoding effect holds on the newest harness wheels" if the lower 95% bound
is above 0; otherwise "not detected on the newest harness wheels". It applies if at least 200 states are complete.

Descriptive, with no rule: every arm's rates with intervals; the contrasts by population (R and U) on Yline and
Yfile; the share shown a changed line by the end of each model call, by arm, and the mean number of calls to the
first changed line; EF minus A and AF minus A by call; the share of mangled ranged reads by arm, at the first call
and later; stop reasons and executed calls; interface failures by arm; the sensitivity that keeps replays which ended
in an error after a usable first response.

## Common rules

- Usable replay in parts "fix" and "one step": as in pre-registrations 06 and 07 (no error, and a first response
  with a call that the frozen interface-failure rule accepts). Interface failures are excluded and counted by arm.
  In part "fresh" an episode that ended in an error is excluded and counted; every other episode counts.
- Complete states only in parts "fix" and "one step": a state counts if every arm and every seed that ran for it
  gave a usable replay.
- 95% bootstrap intervals, 2,000 resamples, seed 0 (`analyze_forks.boot_ci`, `diff_ci`), clustered by state, and by
  task where stated. Part "fresh" clusters by task.
- Fixed shuffled order, so a run cut short is a random subset. Part "fresh" counts if at least 150 episodes finished;
  part "fix" counts if at least 100 states are complete, at least 40 of them in R; below that everything is
  EXPLORATORY.
- Every contrast uses arms of one run. Anything not listed here is EXPLORATORY.

## Stated limits

- A fresh episode here is the harness's compiled agent, its tools and the same model server, started from the task
  prompt. It is not the competition's full evaluation loop: the loop's plugins (display, retry, tool errors) and its
  compaction are not installed, the episode is read-only and ends at the first edit, write or other command, and no
  test runs. The task prompt is the one an earlier harness version logged, not one rebuilt by the newest wheels.
- AF and EF honor a mangled bound; they do not reject it. A harness that rejects the call would cost the agent one
  more call each time. Only the two line-bound names of `read_file` are restored.
- EF's note is pushed once, at the pause, by the replay. No harness feature that pushes such a note exists.
- G1 was written after the unregistered contrast of the five-call experiment was known (item 2 above). It is a
  confirmation on the same states with new seeds, not a new discovery.
- R was chosen by a fact about the gold patch (a listed neighbor lies in a file the fix modifies). R and U together
  are the states with a fix file not yet opened: 198 states from 42 tasks of three repositories.
- One model. The other models never mangled a name and are not run here.

## Power, stated as assumptions

- N1: the original runs made 348 ranged reads within their first eight model calls before the first other call. If
  new episodes behave alike and the share is anywhere near the replays' 14% to 36%, the lower bound is far above 2.1%.
- G1: with about 170 complete states and three seeds the half-width is assumed near 4 points; the unregistered
  contrast behind it was 5 to 9 points.
- G2 and G3: no earlier estimate. With about 57 complete states of R and five seeds the half-width of G3 is near 5
  points (K1's was), so a smaller real gain will usually read as "no detectable gain".
- S1: 5.5 points with a half-width near 2.1 in every earlier run.

## What is reported regardless of outcome

Every rule above with its interval, met or not; every arm's rates; the interface failures by arm; the checkout
fingerprints; the raw per-replay records; and the harness, server, model and sandbox versions recorded by each run.

## Amendment of Nov 10, 2026, 1:46 PM EST: graph tools execute in the part "fresh"; recorded before any full-run replay of the parts "fresh" and "fix"

- What the smoke test showed (3 fresh tasks and 3 states of R, the first two seeds of each; 24 replays, 0 errors):
  five of the six fresh episodes ended at a `search_similar_code` call after one or two model calls, so the part as
  frozen would have produced few ranged reads. The smoke test also printed, as plumbing checks, each fresh episode's
  first prompt size (67 tokens above the size the original run logged, in all six) and, for the part "fix", that the
  4 mangled reads of arm A returned the file from line 1 and the 4 of arm AF returned the lines the model wrote. No
  value of N1 and no outcome of G1 to G3 or S1 was computed or read.
- Change: in the part "fresh" only, the three graph tools (`get_code_neighbors`, `search_similar_code`,
  `get_code_subgraph`) execute as well, through the harness's own tool functions, on the competition's graph and
  embedding files staged on the platform. They read precomputed files and change nothing. Every other stopping rule
  is unchanged. The part "fix" keeps the rule of pre-registration 06: a graph tool ends the replay.
- N1, its threshold and every other rule are unchanged.
- The part "one step" was started at 1:40 PM with the frozen files; this amendment does not touch it.
- Platform record from the two smoke tests: the newest wheels install and run (adk_submission 0.2.13, swegemma
  0.2.11); sandbox locale C.UTF-8; git is absent from the image, so the baseline commit of the checkout is skipped,
  as in the amendment of pre-registration 06. With the history rendered as the original runs' harness delivered it,
  the rebuilt prompt is 67 tokens above the logged size in all six states checked (2 tokens below with the Sep 30
  wheels): the tool declarations of the newest wheels are longer.
- New md5: `analysis/modal_g/forks_g_runner.py` `db233368dbc98e1b972f1f93376e58a9`, `analysis/modal_g/forks_g_modal.py`
  `665d841ff93ddffe73f8b92183782f98`. No other file changed.
- 1:47 PM (commit 7166807), before the second smoke test: the runner's smoke mode also prints how many graph-tool calls executed and
  their result status (a print in smoke mode only; nothing else changed). New md5 of
  `analysis/modal_g/forks_g_runner.py`: `391894bd7fd7c2c14fcd2e83637ab169`.
