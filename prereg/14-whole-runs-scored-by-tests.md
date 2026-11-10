# Pre-registration 14: whole runs scored by tests

Status: FROZEN on Nov 10, 2026, 6:28 PM EST, by the commit that adds this file, before any session of the run it
governs was started. Before the freeze there were a validation pass without a model, two plumbing checks with a
scripted model and one smoke test with the model (three tasks, both conditions); what was seen of them is listed
under "What has been seen". Tags: [Claude Code] wrote it after three blind readers of a draft each asked, as their
first request, for our two harness changes to be run from the start of a task to its end and scored by the tests;
[team] had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/modal_h/wholerun_modal.py` `fbff416834eaf0ee92fb0372cffff158`,
`analysis/modal_h/wholerun_runner.py` `dda4e525dbf01025d30e432502b3438b`, `analysis/analyze_14.py`
`ec13c46c322a270066d93355c7a26f87`, the task list `analysis/results/14/validate/tasks_ok.txt`
`fd0e67a9fcffff20c3d59c3fbdd76975`. Used unchanged: `analysis/modal_g/forks_09_runner.py`
`1cff77481df8a0b077e3b888ef4fe7e9` (the two changes; the runner refuses to start if its copies differ from it),
`analysis/public_runs_time_to_fix.py` `1a7f9cba4f94fe8ffe997eb2e3f0702d`, `analysis/public_runs_address.py`
`a86e30082d20caefc02fc9ec0fc3512a`, `analysis/mangled_sensitivity.py` `7f64709fa901e9b307525e7ffc6284fb`,
`analysis/make_population_k.py` `f84182fb2d545ca76a864dca36629a44`, `analysis/analyze_forks.py`
`8b22556e948c0df33f80cbeef8c11300`.

## Why

Pre-registrations 08 and 09 showed, in episodes that stop at the first edit or after eight calls, that the starter
agent is shown the lines of the fix sooner when the graph tools' answers carry a file and a line range and a
misspelled line-bound argument is honored. Nothing of ours ran past eight calls and nothing was scored by tests.
The only whole-run evidence was another team's runs of a different change on an earlier harness: found sooner, no
more tasks resolved. This run asks the same of our own two changes, on the current harness, with the harness's own
evaluator.

## Design

- Conditions, identical in everything else:
  - **N**, the harness as shipped: the wheels of Oct 12 (adk_submission 0.2.13, swegemma 0.2.11, adk_eval_core
    0.1.0), the base agent of every earlier run, nothing changed.
  - **NAF**, addressed and repaired: the same with the two changes of pre-registration 09, applied by the same
    functions: every entity in a graph tool's answer also carries its file and line range, and a misspelled
    line-bound argument name is restored before the read runs.
- Tasks: the public tasks that can be scored in our sandbox. A validation pass without any model ran the harness's
  test phase for each of the 129 public tasks twice, with the task's reference patch and with an empty patch
  (`analysis/results/14/validate/`). A task is in the run if the reference patch resolves it and the empty patch
  does not: 103 tasks (fastapi 60, rich 43). Left out: 19 that the reference patch does not resolve here and 7 that
  pass with an empty patch; together these are all 13 requests tasks, the one httpx task, 7 fastapi tasks and 5 rich
  tasks. The 103 are a subset of the 106 tasks of pre-registrations 08 and 09. Their order is fixed (sorted, then
  shuffled with `random.Random(0)`).
- Seed 1 for every task and condition. One seed: the credit left does not pay for a second pass, and this was
  settled before any session ran.
- A session is the harness's own evaluation of one task (`Evaluator.evaluate_task`, subprocess sandbox): the agent
  works until it submits a patch or a budget ends, then the patch is applied in a fresh sandbox and the task's tests
  run. Budgets are those printed in the task prompt of every public whole run and stored with the other team's runs:
  40 tool calls, 25 minutes, 60 turns, 120 seconds per command. The harness's verdict `resolved` is the outcome of
  the tests.
- Gemma-4-31B (QAT, 4-bit) served as in every earlier run, sampling as the base agent sets it. Two rented
  A100-80GB containers, each with half of the task list (`--shard 0/2`, `--shard 1/2`) and at most 8 sessions at a
  time; the two conditions of a task run side by side in the same container, so both see the same load. The time
  budget is wall-clock, so the number of sessions at a time is part of the design.
- What the runner adds to the harness (both conditions unless marked): its own task loop around
  `Evaluator.evaluate_task` (one process per session, resume, a stop time); the seed written into the compiled
  agent's configuration; the budgets above and the context settings of the harness's documentation; for NAF the two
  changes; a record per session of how it ended and of what the changes did (`extra.jsonl`; the trace keeps the
  arguments as the model wrote them). The image is that of pre-registration 09 plus git, patch, pytest and the
  packages the tasks' tests import; the subprocess sandbox installs nothing itself.

## Outcomes (per session; definitions are those of `analysis/public_runs_time_to_fix.py`, imported by
`analysis/analyze_14.py`)

1. Resolved: the harness's verdict from the tests.
2. Shown a line the fix changes within eight tool calls: the call index at which a read, or a shell view of one
   file, first returns a line of a changed region of the reference patch is at most 8.
3. The final patch overlaps a changed region of the reference patch.

Reported without a rule: shown such a line at any call, and within 3, 5, 10 and 20 calls; every changed region
shown; the final patch touches a file the reference patch changes; tool calls per session; how each session ended;
reads with a misspelled line bound by condition; graph-tool calls; `resolved` by repository.

A task enters the paired analysis if both conditions have a result for it and neither failed for a reason outside
the agent (the sandbox could not be set up, the model server failed, the tests could not be run for a reason other
than the patch), as `analysis/analyze_14.py` reads it from the harness's error text. A session with such a failure
is run once more (`--retry-infra`) before the analysis; if it fails again its task is left out and listed. A session
that ends on a budget, a context overflow or a malformed call is an outcome, not an exclusion: it counts as not
resolved.

## Rules

Each is "addressed and repaired minus as shipped", paired by task, with a 95% bootstrap interval over tasks (2,000
resamples, seed 0). They apply if at least 60 tasks enter the paired analysis.

**T1**, on outcome 1. "More tasks solved" if the lower bound is above 0; "fewer" if the upper bound is below 0;
otherwise "no detectable difference".

**T2**, on outcome 2. "Sooner" if the lower bound is above 0; otherwise "not detected".

**T3**, on outcome 3. "The final patch reaches the fix more often" if the lower bound is above 0; "less often" if the
upper bound is below 0; otherwise "no detectable difference".

## What we expect, said in advance

No detectable difference in T1. In the other team's public runs the agent is shown a line of the fix in 88% of runs
with or without their skill, so earlier sight can add at most about 3 points of resolved tasks by our own count,
and with 103 pairs the interval will be about 9 points wide on each side (their 315 pairs give about 5). A null in
T1 is the predicted result and will be reported as such, beside outcome 2. For T2 the fresh episodes gave +4.1
points within eight model calls; an effect of that size will most likely not be detected at this sample, and one the
size of the public skill's (+12 to +16 points) would be. T3 has no prediction.

## Stopping

No new session starts after five hours. The run is stopped by hand if the credit left on the account falls to 5
dollars. In either case the analysis uses the tasks finished in both conditions (the order is random) and says so.

## Stated limits

- One seed: 103 pairs. The run can detect a large change in solved tasks, not a small one.
- The two changes are tested together; this run cannot say which one matters.
- One model, one agent, one harness version; the tasks that can be scored here come from two repositories.
- The local evaluation is the harness's own, in a subprocess sandbox on a rented machine. It is not the
  competition's hidden test set, and local scores are known not to predict the leaderboard.
- Sessions share a model server, and the time budget is wall-clock: a session's speed depends on the load. Both
  conditions of a task run under the same load.

## What has been seen

Every earlier result of this repository, among them the fresh-episode results of pre-registrations 08, 09 and 11 and
the counts on the other team's whole runs. The analysis script was written before any whole run of ours existed and
was tested on the other team's public runs as a stand-in (their two arms in place of our two conditions; it
reproduces the stored counts of `analysis/results/public/time_to_fix.txt`) and then on the outputs of the plumbing
checks and of the smoke test, for their format. From the validation pass: which tasks the reference patch and the
empty patch resolve. From the smoke test with the model (fastapi_14430, fastapi_14583, rich_3905; both conditions;
six sessions): how each ended, its tool and model calls, minutes, patch size and test result (one of the three
tasks resolved, in both conditions), how often the changes fired (addresses in two answers of one session; no
restored bound), and the speed of the server. Those sessions are not part of the run; their three tasks are run
again with the others.

## What is reported regardless of outcome

The three rules with their intervals, whichever way they fall; every rate named above; failures outside the agent by
kind; the harness's result files, patches, test logs and traces of every session; the versions recorded by the run.

## Amendments

(none)
