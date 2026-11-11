# Pre-registration 23: whole runs in which the graph's own answers are pushed at the agent, as names or with addresses

Status: FROZEN on Nov 11, 2026, 3:05 PM EST, by the commit that adds this file, before any session of the run it
governs was started. It was written AFTER the results of pre-registrations 14, 18 and 22 (first shard) and of the
one-call replays were seen; what was seen is listed below. Before the freeze there were two plumbing checks with a
scripted model (no GPU) and offline counts on the stored runs of 14. Tags: [Claude Code] wrote it; [team] had not read
this text when it was frozen.

File hashes at freezing (md5): `analysis/modal_h/push_23.py` `a87d121fdd063c17694ea82a9ec31bba`,
`analysis/modal_h/wholerun23_runner.py` `efd66463f99dbfe1dd99d6fa2923370a`, `analysis/modal_h/wholerun23_modal.py`
`be650db1b4baffa5cf5d0449e6fac290`, `analysis/store_23.py` `5626771b7f7bd67fb75e8aee542665d1`, `analysis/analyze_23.py`
`4334362e5c8e5f13ceecec9cfd76e5a0`, `analysis/explore_push_23.py` `cfe49b4a09a2adef6c7dc9b7b52703b1`. The runner and
`push_23.py` on the volume (`/inputs_23/`) are these files; they are uploaded again after any change. Used unchanged: `analysis/analyze_14.py` `ec13c46c322a270066d93355c7a26f87`,
`analysis/analyze_18.py` `2b9e5c84e94ba656cd12d0b07b9488b3`, `analysis/fork_states.py`
`7fc2e4bb40f50b64638a1243e6a636ba` (the neighbor lists;
`push_23.py` gives the same list for all 322,683 nodes of the 103 tasks' graphs), `analysis/public_runs_address.py`
`a86e30082d20caefc02fc9ec0fc3512a`, `analysis/public_runs_time_to_fix.py` `47ce4ac9ee8e31b530ed2c0df132ccd8`,
`analysis/analyze_forks.py` `8b22556e948c0df33f80cbeef8c11300`, `analysis/rederive_18.py`
`5037f9137d2387b54d3dc008e5cf0b93`, the task list `analysis/results/14/validate/tasks_ok.txt`
`fd0e67a9fcffff20c3d59c3fbdd76975`.

## Why

The paper's claim is that a name is not an address: at one call, a neighbor list with files and line ranges changes
what the agent does next, and a list of names hardly does. Blind readers asked for the whole-run test in which the
graph's own answers actually reach the agent, and for the contrast that isolates the address: the same answers
pushed as names against pushed with addresses. Pre-registration 14 could not test this: the agent called a graph
tool in 8 of 103 runs, and addressed answers reached 5. Here the answers are not left to the agent's choice: they
are appended to what it reads.

## Design

- Tasks, order, budgets, model, server, wheels, sandbox: those of pre-registrations 14 and 22. The 103 validated
  tasks of 14 (fastapi 60, rich 43) in 14's order; 40 tool calls, 25 minutes, 60 turns, 120 seconds per command;
  Gemma-4-31B (QAT, 4-bit) served by vLLM as before; the wheels of Oct 12 (adk_submission 0.2.13, swegemma 0.2.11,
  adk_eval_core 0.1.0), compared at start with the versions of 14 (the run stops if one differs).
- One seed, 2, for every task and arm. Two shards (the tasks at odd and at even positions of the order), each in its
  own container with at most 8 sessions at a time; the three arms of a task run side by side, so they see the same
  load.
- Arms, identical in everything else:
  - **N**: the harness as shipped, nothing added (a fresh control).
    THIS LAUNCH RUNS PH AND PE ONLY: the compute credit at hand covers two arms. N is not run, so P1, P2 and H1
    have no verdict; they are printed against the stored N run of pre-registration 14 (seed 1, the same wheels and
    platform), marked as another launch, as the rules below provide.
  - **PE**, pushed with addresses: after a read, the result the agent receives may end with a key `code_graph`
    listing graph neighbors of the code just shown, each with its file and line range.
  - **PH**, pushed names: exactly the push of PE (same reads, same source nodes, same neighbors, same order, same
    caps), but each listed neighbor carries only its name, the graph's id as `get_code_neighbors` returns it.

### The push, in words, as built (`analysis/modal_h/push_23.py`)

1. It acts on every `read_file` call whose result has status ok, after the tool has run and before the agent sees the
   result (the harness's after-tool callback, where the address change of 14 acted). The SHOWN LINES are the
   returned start_line to end_line; a read cut by the character limit ends where its content ends.
2. A SHOWN NODE is a node of the task's code graph whose line range (the address table used for 14's addressed
   answers) lies in the file read and overlaps the shown lines.
3. SOURCES: the shown nodes of this read not yet used as a source in the session, largest overlap first (ties by
   name), at most 2.
4. For each source, its neighbors as `get_code_neighbors` lists them (both directions, sorted by name, the first 50),
   without nodes shown by an earlier read or by this one, without nodes already listed by an earlier push of the
   session, and without nodes that have no line range; the first 8 in that order are kept, 4 per source when there
   are two. A source with nothing left is left out of the value and still counts as used.
5. The key's value: `[{"node": <source>, "neighbors": [<entry>, ...]}, ...]`. PE entry: `{"name": <id>, "file":
   <path>, "lines": "<start>-<end>"}`. PH entry: `{"name": <id>}`. A read with nothing to list gets no key.
6. At most 10 reads per session get the key (the first 10 that qualify).
7. The key is the last key of the result object; the saved trace records the result as the agent received it.
   `extra.jsonl` records per session the reads that got the key, the sources, every pushed entry with its file, line
   range and call index (for PH too, though its agent does not see them), and the characters the agent received.

## Outcomes and definitions (`analysis/analyze_23.py`)

Every tool call is paired with its own result (a step with several calls stores the others' results in the
following system steps; the pairing of `analysis/rederive_18.py`). A READ is a `read_file` call whose result has
status ok; its FILE is the result's path without a leading `/workspace/`, `workspace/` or `./`. Its START: none if the
call gives no start_line argument (under any spelling); otherwise the start_line the result returned (a misspelled
argument name is answered from line 1, so its START is 1). LINES READ per run: the sum over READs of the returned
range's length, repetitions counted (as `analysis/rederive_reads_22.py`). A PUSHED LIST is a READ whose result in the
trace carries the key; its entries' files and ranges come from `extra.jsonl`, checked by name against the trace. An
A1 READ: the run's first READ of a file that holds an entry of a pushed list, made after that push, when the run had
made no READ of that file before it (only `read_file` counts as opening a file). Resolved, the final patch, the
context-window ending and the rest: those of 14 and 18, by the same functions.

## Gate and rules

Each rule compares two runs of the same task, on the tasks where both runs entered (no failure outside the agent,
as 14 reads it); 95% bootstrap by task (2,000 resamples, seed 0); a verdict only with at least 80 such tasks; the
exact McNemar p beside where the outcome is binary. A rule whose two arms did not both run in this launch has no
verdict.

- **G0**, gate, no verdict: the share of entered PE runs, and of entered PH runs, with at least one pushed list. The
  rules below are read only if both shares are at least 80%.
- **A1**, the address at the first read: per run, the share of its A1 READs that start past line 1; per task, PE
  minus PH, on the tasks where both runs have at least one A1 READ (and at least 20 such tasks): "an address moves
  the read" if the interval lies above zero, else "not detected".
- **A2**, reading: LINES READ per run, PE minus PH: "an address saves reading" if the interval lies below zero, else
  "not detected".
- **A3**, resolved, PE against PH: "more" if the interval lies above zero, "fewer" if below, else "no detectable
  difference".
- **P1**, resolved, PE against N; **P2**, resolved, PH against N: the same three words.
- **H1**, harm: runs that end on the context window, PE minus N and PH minus N: "harm" if an interval lies above
  zero, else "no detectable harm".

If N is not run, P1, P2 and H1 have no verdict and are printed against the stored N run of 14 (seed 1), marked as
another launch.

Printed without a rule: uptake (pushed entries whose file is READ within the three calls after the push, all and
those in another file than the read that got the push; whether that READ starts inside the pushed range; whether
that range holds a changed region); A1 READs and their starts per arm; shown every changed region; shown a changed
line within eight calls; the final patch overlaps a changed region, and touches every one; tool calls, reads, LINES
READ, graph-tool calls; pushed lists, entries and characters per run; how runs ended; everything by repository.

## What we expect, written before any session

A1 met: with addresses the agent's first read of a pushed file starts at the listed lines, with names it starts at
the top as unprompted reads do (about 13% of such reads start past line 1 on the stored runs of 14). A2 met: PE reads
fewer lines than PH. A3, P1, P2: no detectable difference. H1: no harm in either arm.

## The reading fixed now

"Pushed with addresses, the graph's own answers change what a run reads, and not detectably what it resolves" is
written only if A1 or A2 is met and A3 is not. Every other outcome is reported as it falls, with its interval: a
resolved difference in A3 or P1 is reported as found; a gate not met is reported as "the push did not reach enough
runs", and the rules are not read; harm in H1 is reported beside the rule it qualifies.

## If only one shard runs

A shard holds 51 or 52 tasks, fewer than the 80 a verdict needs. One shard is reported without verdicts: the script
prints every number and the paper calls it half a run, as for 22. If the second shard runs later, the same script
analyses all 103 tasks unchanged.

## Cost and time expected

The first shard of 22 ran 80 sessions in about 90 minutes; 14 ran 104 sessions per container in about 1.6 hours at
8 at a time (mean 7 to 8 minutes of wall time per session). A shard of all three arms is about 155 sessions, about
2.5 hours of sessions, longer than the 1.9 hours after which no new session starts; the shard is then launched again
and resumes (finished sessions are not run twice). At about 3.3 to 3.8 dollars per container hour (the bills of Nov
10), all three arms cost about 18 to 22 dollars; PH and PE alone (about 103 sessions per shard, the load of 14) about
12 to 14 dollars. These are estimates, not measurements.

## What has been seen

- Pre-registration 14 in full (seed 1): N resolved 36, addressed and repaired 37 of 103; no detectable difference;
  graph tools called in 8 of 103 N runs. Pre-registrations 18 (seed 2, 40 tasks) and the first shard of 22 (seed
  3, 20 tasks), in which the agent is told every place the fix changes: told as files and lines, the runs read fewer
  lines than told as names (18: 324.5 fewer per run [138.7, 524.8], 40 tasks; 22: 279.5 fewer [65.7, 483.8], 20
  tasks, exploratory recounts), and the first read of a told file starts past line 1 in 55% (lines) and 63%
  (functions with lines) of such reads against 13% to 14% with names or nothing (22, 20 tasks).
- The one-call replays of the paper: a neighbor list with addresses changes the next call more than names do; the
  neighbor's file is opened in 11.8% of replays with addresses, 7.5% with names, 4.6% with no list (exploratory).
- Offline, on the reads of the stored N runs of 14 as if they had been made under the push (`explore_push_23.py`; a
  push changes what a run does next, so this is the promise of the rule, not what PE or PH will do): 101 of 103 runs
  would get at least one pushed list; a median of 4 pushed reads per run (max 10); 3.75 entries per push on average;
  a median of 2,038 characters per run with addresses and 1,297 as names; the first push at a median call of 2. The PH value of
  every one of the 485 pushes is the PE value with each entry reduced to its name. A1 READs on these unchanged reads:
  71 in 49 runs, 9 of them (12.7%) past line 1.
- The registered script on a stand-in (the stored runs of 14: N and PH both the N run, PE the addressed run, the
  pushes replayed offline): every rule prints; G0 98% and 96%; A1 rests on 38 tasks with an A1 READ in both runs.
- Plumbing check 1 (launch `20261111T080317Z_check`; arms N and PE, three tasks, a scripted model that reads a
  function with neighbors twice): passed, as its builder reported (every session reached a test verdict; the key in
  PE's first qualifying read and not repeated for the same source; none in N; the harness equal to that of 14).
  Plumbing check 2 (launch `20261111T103120Z_check`; arms N, PH and PE, the same three tasks and script): all nine
  sessions reached a test verdict (resolved, as the reference patch is applied); N got no key; PH and PE pushed at the
  same reads (2, 1 and 2 pushes), the same sources, neighbors, order and ranges, and differ only in the entry fields
  the agent received (PE name, file, lines; PH name); the trace records the key as received; the analysis functions
  read every push from the trace with its file and range from `extra.jsonl`, and the offline replay of the push
  matches the trace; the harness equals that of 14.
- Nothing of seed 2 under PE or PH has been run with the model. Seed 2 was the seed of 18, whose N arm ran 40 of these
  103 tasks.

## Not covered

- One seed and 103 tasks: a difference in resolved tasks smaller than about 9 points cannot be detected.
- The names of PH are the graph's ids (dotted module paths such as `app02.main.get_settings`), as the graph tool
  returns them; they hint at the file without naming it, so PH is a name as the tools give it, not a bare function
  name.
- The push lists neighbors of what the agent has just read, not where the fix is; whether the graph's answers help
  depends on the graph reaching the fix, which this run measures (uptake, ranges holding a changed region) but does
  not control.
- Only `read_file` counts as opening a file for A1; a file viewed through the shell first is not excluded.
- One model, one agent, one harness version, two repositories.

## Notes added after the freeze

(none yet)
