# Pre-registration 25: the place of the list (the one-call list of 03, moved to where 23 pushed it)

Tags: [Claude Code] wrote it from a draft, with the design choices taken by [team]. No replay of arms KH or KE has
run on any platform, and arm EL has never run on the harness wheels of Oct 12. Inputs, by md5:
`analysis/fork_states_d/states.jsonl` `d3105df0dc4aa43d7bb0afbdd6123b44` (the 407 paused steps of 03), the records
`analysis/fork_states_p/states.jsonl` `0422a706a3a4b57083ce6d61e2cd0cb3` (not tracked; rebuilt by
`analysis/make_states_25.py`, which checks the input md5), their manifest `analysis/fork_states_p/manifest.json`,
`analysis/modal_h/push_23.py` `a87d121fdd063c17694ea82a9ec31bba`, the frozen one-step runner
`analysis/modal_w/forks_w_runner.py` `65372125c2e23b48f5ee0e829a5e4167`. The launcher is
`analysis/modal_g/forks_25_modal.py`, the analysis `analysis/analyze_25.py`, the reference interval of the gate
`analysis/explore_place_reference.py` (stored output `analysis/results/explore_place_reference.txt`).

## Why

The main one-call result of this repository (pre-registration 03, 388 complete paused steps, seeds 1 to 3, the
scorer of `analysis/analyze_b.py`): a list of graph neighbors given as names in a note is followed in 2.75% of 1,164
replays, the same list with each neighbor's file, line range and first definition line in 8.25%; E minus H +5.50
points [+3.44, +7.65] (`analysis/results/analyze_b.txt`, reproduced in `analysis/results/explore_place_reference.txt`).
The effect held inside the result of an inserted `get_code_neighbors` call (05: PE minus P +6.35 [+4.34, +8.52],
`analysis/results/d1/analyze_d1.txt`) and on the harness of Oct 12 (08, rule S1: +5.60 [+3.76, +7.77],
`analysis/results/g/analyze_g.txt`).

In whole runs (pre-registration 23) the list was pushed: the result of a `read_file` call ended with a key
`code_graph` listing neighbors of the code just shown, as names (PH) or with file and line range (PE). There the
one-call effect did not appear. Among lists with an entry in a file not opened before, the next call read a listed
neighbor's code after 13 of 425 lists with addresses (3.1%), after 9 of 396 lists of names (2.3%; 10 of 396, 2.5%,
with the next call counted by model step), and after 13 of 421 of the lists a run without lists would have been sent
(3.1%) (`analysis/results/explore_next_call_23.txt`). A split of 03's steps by how far into the run they lie is in
`analysis/results/explore_step_position.txt`. Two differences between the one-call design and the whole runs are left
untested: the task prompt (September's steps against the current runs) and the place of the list. No replay ever put
the list where 23 puts it, as a key at the end of a file view, after the file's content. This experiment moves the
list of 03 to that place and changes nothing else.

## Design

- **Steps.** The 407 paused steps of 03, restricted to those whose paused history ends with a `read_file` result of
  status ok: 322 steps in 76 tasks. The other 85 end with a `run_command` result (83 `grep`, 2 `cat`) and are left
  out. All 322 are kept. Per step the manifest flags whether 03's queried node overlaps the lines the last read showed
  (`push_23.shown_range`, the rule by which 23's push decides what a read showed): it does in 276 steps (76 tasks); in
  31 the node lies in the file read but outside the lines shown, in 15 not in that file at all (it was chosen from an
  earlier view or from the issue).
- **The last result as it is.** In all 322 steps the read result is a JSON object with the keys `status`,
  `filepath`, `content`, `start_line`, `end_line`, `total_lines`, `is_truncated`, in that order (checked by the
  builder on every step). The read tool of the Oct 12 wheels (swegemma 0.2.11, `swegemma/tools/workspace.py` and
  `base.py`) builds its result with these keys in this order, with the same code as swegemma 0.2.7 (the wheels of Sep
  30), so the push of 23 saw the same keys in the same order. The key `code_graph` is
  added after the last of them, as 23's runner adds it (`out = dict(tool_response); out["code_graph"] = shown`), so it
  follows the file's content and its line counts.
- **Harness, model, sampling.** The harness wheels of Oct 12 (`latest`: adk_eval_core 0.1.0, adk_submission 0.2.13,
  swegemma 0.2.11) and the one-step machinery of pre-registration 08 (`analysis/modal_g/forks_g_modal.py`, part "one
  step"): its image (vllm 0.19.1, litellm 1.82.4, google-adk 1.36.1), the frozen one-step runner
  `analysis/modal_w/forks_w_runner.py` (the vLLM server through the harness's own `VllmServer`, tool-call and
  reasoning parsers `gemma4`, thinking on, maximum length 32,768) with `analysis/replay.py` unchanged, the base
  agent's configuration and sampling files on the volume, 8 calls at once. Gemma-4-31B (QAT, 4-bit), one A100-80GB,
  tensor-parallel size 1. One model call per replay; no tool executes. The run records its versions: the runner's
  `versions.json`, and `versions_25.json` with the installed versions of the harness and the main packages after the
  run and whether the harness is the one registered.
- **Seeds.** 1 and 2. 322 steps x 3 arms x 2 seeds = 1,932 replays planned; the cap decides how many run (below).
- **How the records are built** (`analysis/make_states_25.py`). The one-step runner replays a history and can add a
  note; it cannot change the last result (pre-registration 15). So, as in 15, each (step, arm) is its own record: the
  KH and KE records carry the step's history with the last result changed and are replayed under the runner's arm A
  (nothing added); the EL record is the step unchanged, replayed under the runner's arm EL. The builder checks, on
  every record: KH and KE differ from the step's history in the last tool result only, and there only by the added
  last key; the key's text is byte for byte what `push_23.as_shown` gives for the same entries (the builder imports
  it), both as stored and as the agent framework renders a tool result to the model; KE's key and EL's note list the
  same names in the same order with the same file and line range.
- **Order and cap.** The steps in a fixed shuffled order (`random.Random(25)` over the step ids as the states file
  lists them; written in the manifest). The run is seed-major: pass 1 runs seed 1 over all steps in that order, the
  three arms of a step together; pass 2 runs seed 2 in the same order, until the cap. So every step is covered once
  before any step is covered twice, and what the cap cuts is a random subset of seed 2. Both passes run in one
  invocation of the runner (one server start-up): the launcher writes each (step, arm) record once per pass, its fork
  `<03's fork>:<arm>:<seed>`, the records of pass 1 before those of pass 2, and enters every other seed's cell as
  finished, so the runner meets the cells in that order. No new replay after 40 minutes of the runner's clock, both
  passes together, its start-up included; replays under way finish. The runner is stopped at 46 minutes; the
  container's own limit is 50 minutes. One container, one GPU, no retry: the full run refuses to start if its results
  file already holds a replay.
- **Smoke test.** The first 8 steps of the fixed order, every arm, seed 1: 24 replays. Only its usable share is read
  (rows, runner errors, rows with a call, by arm), from the launcher's summary of the smoke test's rows; its outcomes
  are not read.

## Arms

Identical in everything but the last piece. The entries are those of 03 for the step: the queried node's true
neighbors as `get_code_neighbors` lists them (sorted by name, the first 50), in the same order in all three arms.

| Arm | Last piece |
|---|---|
| KH | the file view that ends the paused history, with the last key `code_graph`: `[{"node": <03's queried node>, "neighbors": [{"name": <id>}, ...]}]` (`push_23.as_shown`, arm PH) |
| KE | the same key, each entry `{"name": <id>, "file": <path>, "lines": "<start>-<end>"}` (`push_23.as_shown`, arm PE; 23's PE entry, no definition line); a field arm E lacks stays missing |
| EL | arm EL of pre-registration 04 unchanged: the file view as recorded, then the note of 03 (`fork_states.E_WORDING`) with each entry reduced to name, file and lines (`fork_states.py`, `el_obs`) |

KE's entries and EL's are the same objects in the same order; only the place differs. On the 322 steps a list has 2
to 50 entries (median 9; 4,916 in all); 94 entries have no file (and so no line range). 23's push lists at most 8
(`push_23.MAX_ENTRIES`). The key adds a median of 534.5 characters to the last result under KH and 957 under KE; EL's
note has a median of 1,079 characters (`analysis/fork_states_p/manifest.json`, `counts`).

## Outcome

- **Registered:** reads a neighbor's code, exactly the outcome of 03: the next call reads, edits or shows lines of a
  listed true neighbor in a file not opened before (`gates_c.any_true`, the rule `analyze_b.py` applies, with
  `fork_states.touches` and the harness's caps). Every arm is scored on the same spans, those of the states file.
- **Beside it, no rule:** opens the neighbor's file: the next call is a `read_file` of a file that holds a listed true
  neighbor and that the agent had not opened, at any line (`mangled_sensitivity.opens_listed_file`).
- Interface failures (runner error, no call, unknown tool, malformed arguments; `gates_c.failure`) are excluded and
  counted by arm.
- A (step, seed) cell is complete if all three arms gave a usable replay at that seed. A step enters the analysis
  with the mean of its outcome over its complete cells, per arm, the same cells for every arm (one cell or two). The
  rules apply if at least 200 steps have at least one complete cell. The analysis prints how many steps have one
  complete cell and how many have two.

## Gate and rules

95% bootstrap intervals clustered by step, 2,000 resamples, seed 0 (`analyze_forks.boot_ci` and `diff_ci`, the steps
in sorted order), each step entering with its mean over its complete cells, with the interval clustered by task
printed beside each. Analysis: `analysis/analyze_25.py`; it refuses to print a rule's verdict if the gate fails or
fewer than 200 steps have a complete cell.

**Gate.** (a) At least 80% of the replays attempted in each arm hold a usable tool call. (b) EL's rate on the steps
with a complete cell lies within [3.81, 9.19] percent: the union of arm E's stored intervals at seeds 1 and 2 on the steps that end with a
file view, in the run of 03 (6.61% [4.03, 9.19], 310 steps) and the one-step run of 08 (6.03% [3.81, 8.41], 315
steps) (`analysis/results/explore_place_reference.txt`). EL has no stored run on the wheels of Oct 12; E's intervals
are used because EL differs from E only by the definition line (on the Sep 30 wheels, all complete steps: EL 7.71%
of 1,206 replays, E 8.60% of 1,197, `analysis/results/12/analyze_12.txt`). If the gate fails, no rule is read and the
result is reported as a failed replication.

**K1, the effect in the push's place.** KE minus KH. "The effect holds in the push's place" if the interval lies
above zero; otherwise "not detected".

**K2, the place.** EL minus KE. "The place matters" if the interval lies above zero; otherwise "not detected".

No equivalence band: two seeds cannot reach one (on these steps the stored E minus H at seeds 1 and 2 has intervals
about 4 to 5 points wide: 03 +5.00 [+2.74, +7.42], 08 +4.13 [+2.22, +6.19]).

No rule, reported: beside K1 and K2, the same contrasts on seed 1 alone (the steps with a complete seed-1 cell);
every arm's rates on both outcomes, also on seed 1 alone; EL minus KH; the contrasts on opening the file; all
estimates on the 276 steps whose queried node overlaps the lines the last read showed; interface failures by arm.

## What we expect

No direction is predicted for K2; for K1 the stored effect in a note and in a tool result suggests it will hold, and
the whole runs of 23 suggest it will not. A draft of this registration put the odds of "the place matters" near one
in three.

## The reading fixed now

- K1 not detected and K2 met: an address placed after a file's content is not acted on as it is in a note; the place
  of the list can explain why the whole runs of 23 showed no effect.
- K1 met: the address effect is there in the push's place, so the place of the list does not explain the null of 23
  (whatever K2 says; if K2 is also met, the place lowers the effect without removing it).
- K1 not detected and K2 not detected: undecided.

Nothing else is read into the result after the data.

## Cost and time expected

Estimates from stored runs of the same runner at 8 calls at once, not measured for this design:

- The one-step part of 08 (same wheels, same 407 states, prompts of arm E 8,295 tokens on average): 2,442 replays
  and 48 prompt-size replays in 5,913 s (`analysis/results/g_onestep/forks/summary.json`; its prompt-size checks hold
  24 rows each, `analysis/results/g/analyze_g.txt`). With a server start-up of 354 to 370 s (pre-registration 16: 354
  s in its smoke test; `analysis/results/16/forks/summary_16.json`: first call at 369.9 s), about 27 replays a minute.
- Pre-registration 15 (Sep 30 wheels): 549 replays in 1,323 s, start-up included
  (`analysis/results/15/forks/summary.json`), about 34 a minute after a start-up of that size.

Seed 1 is 966 replays: at 27 a minute, about 36 minutes of replays. The 40-minute cap counts the start-up (about 6
minutes), so about 34 minutes of replays fit: about 910 to 920 replays, about 305 of the 322 steps at seed 1, and no
replay at seed 2. At 34 a minute, about 1,150 replays: all of seed 1 and about 180 replays of seed 2 (about 60 steps
with two cells). Either way about 300 steps or more are expected to have a complete cell, above the floor of 200;
whether seed 2 is reached at all depends on the rate. The prefix shared by a step's replays is the same kind as in 08
(H and E of a step differed only in the last piece there too), so no gain over 08's rate is assumed. Pre-registration
16 gives about 1.8 dollars for a container of about 30 minutes; at that rate the full run (at most 50 minutes of
container time) costs about 3 dollars, the smoke test (at most 13 minutes) under 1 dollar.

## What has been seen

Every earlier result of this repository. The ones this design rests on are cited under "Why". Before the freeze:

- The builder's output (`analysis/make_states_25.py`, counts in `analysis/fork_states_p/manifest.json`): 322 steps
  in 76 tasks, 966 records, the entry counts and flags above; every check passed. No model was called.
- [Claude Code] also passed every record through `replay.arm_messages` and google-adk's own conversion of a request
  to chat messages (no model, no harness wheels; an untracked check): for KH and KE the messages are those of the
  unchanged step under arm A except the last tool message, which is the unchanged one with `, "code_graph": <value>`
  before its closing brace; for EL they are the unchanged step under arm EL.
- EXPLORATORY, `analysis/results/explore_place_reference.txt` (`analysis/explore_place_reference.py`, written before
  any replay of 25): on the complete steps that end with a file view, at seeds 1 and 2,
  - 03, 310 steps: E 6.61% [4.03, 9.19], H 1.61% [0.48, 2.90], E minus H +5.00 [+2.74, +7.42];
  - 08, 315 steps: E 6.03% [3.81, 8.41], H 1.90% [0.63, 3.33], E minus H +4.13 [+2.22, +6.19];
  - 04 (Sep 30 wheels, the only stored run with EL), 315 steps: EL 6.67% [4.29, 9.21], E 6.83% [4.44, 9.37], H 2.06%
    [0.79, 3.65], E minus EL +0.16 [-1.75, +1.90].
  At seeds 1 to 3 the same file gives 03: E 6.34%, H 1.72%, E minus H +4.62 [+2.47, +6.88]; 08: E 6.67%, H 2.12%,
  E minus H +4.55 [+2.65, +6.67]. A rate's interval depends on the order in which `boot_ci` resamples the steps; the
  file lists each run's steps as its stored analysis does and prints the other order beside it (03, sorted:
  [4.19, 9.19]; 08, by first usable row: [3.65, 8.41]). The gate uses the first.
- Nothing of arms KH or KE has been run on any platform.

## Not covered

- One model (Gemma-4-31B).
- September's steps and September's task prompt, replayed on the wheels of Oct 12. The task prompt of the current runs
  is not tested here; if the place does not explain 23, it remains untested.
- One sample per arm and step for most steps, two for those the cap lets pass 2 reach: intervals will be wider than
  those of 03 and 08, and an effect of the stored size (about 4 to 5 points) may go undetected.
- The entries are those of 03, not the push's own lists. 23's push leaves out nodes already shown and nodes listed by
  an earlier push, keeps at most 8 entries (4 per source) and can name two sources; 03's lists keep every true neighbor
  up to 50, including neighbors in files already opened (they are listed but not scored).
- A note and a key differ in more than place. The key sits inside a tool result the agent asked for, with no wording
  around it, as `[{"node", "neighbors"}]`; the note is a separate user-role message with 03's sentence before the list
  and the list inside `{"status", "node", "neighbors", "count"}`. EL minus KE is the effect of all of that together.
- Only steps that end with a file view; the 85 that end with a search are left out, and on the 310 complete ones that
  remain the stored effect is smaller than on all 388 (above).
- The 46 steps whose queried node is not in the lines the last read showed: the key then names a node that the file
  view above it does not show, which 23's push never does. They are kept (the entries must be 03's); the 276 others
  are reported apart, without a rule.

## Dated note, 2026-11-12 00:38 EST, before the full run (no outcome of 25 has been read)

- The smoke test ran: 24 replays, 8 rows per arm, no runner error, every row with a call; the harness as registered
  (adk_eval_core 0.1.0, adk_submission 0.2.13, swegemma 0.2.11). The platform preempted its container once during the
  installation and restarted it.
- Read beyond the registered usable share, and no outcome: the latency and the token counts of the smoke test's 24
  rows (not their calls). Mean latency 27.7 s a replay at 8 calls at once (four replays thought for 1,700 to 4,300
  tokens): about 17 replays a minute, not the 27 assumed under "Cost and time expected". At 17 a minute the cap of
  40 minutes would have ended the run at about 190 steps, under the floor of 200.
- Changed for that reason, in the launcher only (`analysis/modal_g/forks_25_modal.py`, committed with this note):
  the cap is 48 minutes in place of 40, counted from the first start (runner stopped at 54 minutes, container limit
  58). At 17 a minute that is about 720 replays, about 240 steps at seed 1; at 15 a minute about 640 and about 210.
  If the platform preempts the container and restarts the function, the run resumes on the cells not yet stored,
  under the clock of the first start, so the time a restart loses counts against the cap; a restart is recorded in
  `restarts.jsonl`; rows reach the volume every 2 minutes. "No retry" stays: a launch by hand after the cap runs no
  replay.
- Unchanged: steps, arms, order, seeds, outcome, gate, rules, readings, and both analysis scripts (committed before
  any outcome: `analysis/analyze_25.py` in f2f62c9, `analysis/rederive_25.py` in bdafb67).
- The smoke test and the full run together are now expected to cost about 3.8 dollars.
