# Pre-registration 06: experiment E (a navigation horizon of five model calls)

Status: FROZEN on Nov 10, 2026, 2:43 AM EST, by the commit that adds this file, before any replay of this experiment ran
with a real model. It adds to pre-registrations 02 to 05 and changes none of their rules.
Tags: [Claude Code] wrote it; [team] asked for the additional runs and had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/replay_k.py` `6d4e2f73274b9bc77b67eb86488c915d`, `analysis/analyze_k.py` `20294af5a37d5348f9bd0e20887b722b`,
`analysis/make_population_k.py` `f84182fb2d545ca76a864dca36629a44`, `analysis/fork_states_k/population.json` `036df3cef4d68a4a65ed29919a4cd18d`,
`analysis/modal_k/forks_k_runner.py` `4173cc97ab077b9a44f17c07b375e9b0`, `analysis/modal_k/forks_k_modal.py` `f1886fdb58fb5fd4b066b7d4304dcbe6`.
Code changes that the platform forces after this freeze are recorded at the end of this file as dated amendments
with the new hashes; the outcome definitions and the rules cannot change.

## Why

Every result so far is one step: the first call after the pause. A list that changes the next call may still not
bring the agent to the code it has to fix, and a list that does not change the next call may still do so two or
three calls later. Experiment E asks whether the legible list (arm E) brings the agent to the code the fix changes
within five model calls, and whether a list that points elsewhere delays it.

## Design

- Replays continue for up to five model calls after the pause, through the harness's own compiled agent (harness
  v28: adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7) and the same model weights (Gemma-4-31B QAT
  W4A16), server settings and replay code as experiment D, on a rented single A100-80GB, tensor-parallel size 1,
  Python 3.12. The run records its versions, the sandbox locale and whether git was present.
- `read_file` and read-only shell commands execute for real, through the harness's unchanged tool functions (their
  caps and result formats), on a checkout of the task's snapshot prepared the way the harness prepares its subprocess
  sandbox (snapshot extracted, git exclude rules, pytest.ini and conftest.py, baseline commit), plus the files the
  history's own `write_file` calls created. Read-only shell commands: cat, head, tail, `sed -n` with a print script,
  grep, rg, ls, find (without -exec, -delete or -fprint), wc, pipelines made only of these, xargs feeding one of them,
  cd, and redirections to /dev/null. All replays of a state share one checkout, which is fingerprinted before and
  after and must be unchanged.
- A replay stops before executing the first call that is anything else (edit_file, write_file, submit_patch,
  get_status, any graph tool, any other shell command), after the fifth model call, or on a response with no call. A
  response with several calls executes its allowed calls in order up to the first disallowed one. Every call, a
  summary of its result, per-call prompt tokens and the stop reason are recorded.
- Arms A, H, E and RE, texts unchanged, from `analysis/fork_states_d/states.jsonl` (md5
  `d3105df0dc4aa43d7bb0afbdd6123b44`).
- Gold files and changed regions come from the gold patch in `data/tasks.jsonl` (md5
  `b3d40066102b495a9f5b0bcfe494a65e`). A file is created by the patch when every hunk of it has the old range -0,0;
  otherwise it is modified. The changed region of a hunk, in old-file lines, runs from its first removed line to its
  last; an insertion not directly after a removed line adds the two old-file lines around its insertion point, so a
  pure-insertion hunk spans those two lines.
- Populations, from pre-treatment facts only, over all 407 states (`analysis/make_population_k.py`):
  - R ("the list reaches the fix"): an entry of `unshown_true_neighbors` lies in a file the gold patch modifies.
    74 states from 20 tasks; seeds 1 to 5.
  - U ("the fix is elsewhere"): not in R, and a file the gold patch modifies was not opened at the pause
    (`shown_files`). 124 states from 30 tasks; seeds 1 to 3.
  - The other 209 states are not run. Of the 388 states complete in the pooled analysis, 70 are in R and 121 in U.
  - 742 replays per arm, 2,968 in all, at most 14,840 model calls.
- Target files of a state: the files the gold patch modifies that were not opened at the pause.
- Outcomes per replay, within the horizon:
  - Yfile: an executed `read_file` with status ok on a target file; an executed shell command with non-empty output
    that the frozen scorer (`fork_states.touches`, i.e. `shell_view_range` with the 5,000-character cap) treats as a
    view of a target file; or the stopping call, if it is an edit_file or write_file on a target file.
  - Yline: an executed `read_file` with status ok on a target file whose returned start_line to end_line overlaps a
    changed region; or an executed single-file shell view whose frozen-scorer range overlaps a changed region.
    Recursive and multi-file commands count for Yfile only, and only where the frozen scorer treats them as a view
    of that file. The frozen scorer counts a grep stage only when it names the queried node; target files have no
    node, so a grep never counts as a view for either outcome.
  - Recorded as well: the index of the first model call with Yfile and with Yline, the number of executed calls, the
    stop reason, per-call prompt tokens, and whether each call touched a listed entry (true or rewired) by the frozen
    `touches`.

## Gate

Before the run starts, the fidelity mode re-executes the logged read-only calls of one state per task on the
platform's checkout. The run starts only if at least 95% of the re-executed `read_file` calls return exactly the
logged result. Agreement of shell commands is reported and gates nothing (directory order, see the limits).

## Rules

**K1, reaching the fix.** E minus H on Yline, in R. "The legible list brings the agent to fix code within five
calls" if the lower 95% bound is above 0; otherwise "no detectable gain". Reported with the interval either way.
The same contrast clustered by task (20 tasks in R) is reported beside it, and K1 is called robust only if its
lower 95% bound is above 0 under both clusterings.

**K2, harm.** E minus A on Yfile, in U. "The list delays reaching the fix" if the upper 95% bound is below 0;
otherwise no harm is claimed. Reported with the interval either way.

Descriptive, with no rule: every other contrast (E - A, H - A, RE - A on Yline and Yfile in R and in U; E - H on
Yfile in R; the U contrasts on Yline), stop-reason shares, mean executed calls, first-call indices and the
listed-entry touches.

## Common rules

- Usable replay: no error, and the first model response has a call that the frozen interface-failure rule accepts
  (no call, an unknown tool or malformed arguments in the first call are interface failures, as in
  pre-registrations 02 to 05). Later calls are scored as they are: a later malformed call is executed and returns
  the tool's error, a later text answer is a stop. Interface failures are excluded and counted apart (`analyze_k.py` prints the outputs listed under Rules and the complete-state counts; the count by arm is
  taken from the raw rows and reported).
- Complete states only: a state counts if every arm and every seed of its population gave a usable replay.
- 95% bootstrap intervals clustered by state, 2,000 resamples, seed 0 (`analyze_forks.boot_ci`, `diff_ci`).
- States run in a fixed shuffled order, so a run cut short is a random subset. A partial run counts if at least 40
  states of R are complete; below that everything is EXPLORATORY.
- Analysis: `analysis/analyze_k.py <run_dir>`. Anything not listed here is EXPLORATORY.

## Stated limits

- The continuation is read-only: tests, python and every edit end the replay, so the horizon measures where the agent
  looks, not whether it fixes anything.
- Directory order may differ from the original runs for recursive commands (grep -r, find, ls). A local check found
  27 of 70 logged shell results in another order, 11 of them with different lines kept under a head or the
  5,000-character cap. All arms of a state share one checkout, so the comparison between arms is unaffected.
- Files that earlier python runs created (`__pycache__`) and heredoc writes are not reproduced. The sandbox locale is
  en_US.UTF-8 if available, else C.UTF-8, recorded per run; it changes `ls` order only.
- The populations are a subset of states chosen by facts about the gold patch, and R has only 20 tasks: the
  intervals cluster by state, and states of one task are not independent.
- One model, one platform.

## Power, stated as assumptions

R gives 370 replays per arm (74 states x 5 seeds), U 372 (124 x 3). With about 70 complete states of R the 95%
half-width of a paired difference is near 9 points, so K1 detects a gain of roughly 10 points or more and a smaller
real gain will usually read as "no detectable gain". For K2 the half-width with about 120 states of U is near 7
points (an assumption from the same per-state spread), so only a sizeable delay can be claimed.

## What is reported regardless of outcome

All rates of every arm in R and U with intervals, every contrast listed above, stop-reason shares, the checkout
fingerprints, the local and on-platform fidelity counts, the raw per-replay records,
and the harness, server, model and sandbox versions recorded by the run.

## Amendment of Nov 10, 2026, 3:04 AM EST: run settings, before the full run started

Recorded after the platform checks and before any full-run replay. No outcome of the smoke test was read: it
printed stop reasons and call counts only (32 replays, 0 errors).

- Gate: on the platform, 44 of 44 re-executed `read_file` calls returned exactly the logged result (passed). Shell
  commands: 36 exact, 18 same lines in another order, 13 different, of 67. Sandbox locale C.UTF-8; git is absent
  from the image, so the baseline commit of the checkout is skipped (the snapshot's own `.git` directory is present).
- Throughput and cost: the smoke test ran at about 0.06 replays per second, which would put the full run near 14
  hours. The wrapper now keeps 16 replays in flight (was 8) and 4 states with a checkout at once (was 3), and the
  time budget is 9 hours (was 19). If the budget ends the run early, the partial-run rule above applies.
- New md5 of `analysis/modal_k/forks_k_modal.py`: `1aff7f58aa7466f12b8c5fc10fedcf08`. No other file changed. No rule, outcome, population
  or seed changes.
