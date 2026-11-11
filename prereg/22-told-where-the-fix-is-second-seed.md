# Pre-registration 22: told where the fix is, a second seed, with the functions and the lines apart

Status: FROZEN on Nov 11, 2026, 2:33 AM EST, by the commit that adds this file, before any session of the run it
governs was started. It was written AFTER the result of pre-registration 18 (seed 2) was seen, and repeats that
design with another seed; what was seen is listed below. Before the freeze there was one plumbing check with a
scripted model (no GPU). Tags: [Claude Code] wrote it; [team] had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/make_oracle_22.py` `e7c2c6ad06a8fbce35bca97a7465d5ae`,
`analysis/oracle_22/manifest.json` `66d6c3c35c78984e5144ea5e91c5e1a5` (counts and the md5 of every note; the notes are
built from the competition data and are not tracked), `analysis/modal_h/wholerun22_runner.py`
`61ad061c5294f7d3de58e5e4bfbeea61`, `analysis/modal_h/wholerun22_modal.py` `f882877392898e44b7067cc40a25f9a3`,
`analysis/store_22.py` `55059fd7a765c7b9bbdcf0f3cef1de0c`, `analysis/analyze_22.py`
`b024c4b752493413de3f2271591e7c33`. Used unchanged: `analysis/analyze_18.py` `2b9e5c84e94ba656cd12d0b07b9488b3`,
`analysis/analyze_14.py` `ec13c46c322a270066d93355c7a26f87`, the task list `analysis/oracle_18/tasks_18.txt`
`4235306974c1252840bbec8c0bcd3d67`.

## What has been seen

Pre-registration 18, in full (seed 2, 40 tasks, arms N, ON, OA in one launch; registered script and an independent
one). Resolved: N 2, ON 5, OA 8 of 40; OA against N more (+15.0 points [5.0, 27.5]); ON against N and OA against ON
no detectable difference. Shown every changed region: N 8, ON 27, OA 25 by the registered script and 32 once reads
made in parallel are counted. And, without a rule, after the run: the final patch overlaps a changed region in N
19, ON 20, OA 33 of 40 runs (OA against ON: 17 against 4 discordant). By the number of changed regions the gain in
resolved tasks lies in fixes of one to three regions. The plumbing check of this experiment: three tasks, four
arms, seed 3, a scripted model; every session reached a test verdict, each arm's note stood once in the first user
message with the manifest's md5 and none in N, the harness equals that of 14. No session of seed 3 has run with
the model.

## Why

One seed and forty tasks carry the paper's only result at the end of a run, and the most surprising part of it
(told the functions, the agent sees all of the fix and its patch lands no closer; told the lines, it does) was
seen after the run, not registered. This run repeats the design with another seed and makes that observation a
rule. It also adds an arm, because OA differed from ON in two ways at once: its form (a file and lines against a
name) and its precision (the changed lines against a whole function).

## Design

- Tasks, order, budgets, model, server, wheels, sandbox, load per container: those of pre-registration 18. Seed 3.
  Two shards (the tasks at odd and at even positions of the order), each in its own container with at most 8
  sessions at a time; the four arms of a task run side by side.
- Arms: **N**, **ON** and **OA** as in 18, with the same notes byte for byte. New: **OF**, the functions with their
  lines: the same header, then one line per distinct name of the ON note, in its order: the file path, the line
  range of that function or class in the task's snapshot, and the name; for a name that is a module, the file path
  and the name without a line range. OF holds what ON holds and where each named definition is, and nothing about
  which lines inside it change. Of the 252 names, 174 get a line range and 78 are modules; some definitions are
  whole classes of thousands of lines, so OF is often close to ON by construction.
- Money decides the schedule: the first shard is launched now; the second when the credit allows. A shard takes
  about 90 minutes; no new session starts in it after 1.4 hours. If only one shard is run, no rule gets a verdict
  and the numbers are reported as they are.

## Outcomes

Those of 18, by the same functions. The registered script credits a step that holds several tool calls with the
result of its first call only (found in 18 by the independent script); "shown every changed region" is therefore
given twice in the paper, as the registered script prints it and with every call paired with its result, and the
rules below are read from the registered script.

## Rules

Each compares two runs of the same task and seed, on the tasks where both entered; bootstrap by task (2,000
resamples, seed 0); "more" if the interval lies above zero, "fewer" if below, else "no detectable difference"; a
verdict only with at least 34 such tasks; the exact McNemar p beside.

- **L1.** Resolved, OA against N. (U1 of 18.)
- **L2.** Resolved, ON against N. (U4 of 18.)
- **L3.** Final patch overlaps a changed region, OA against ON.
- **L4.** Final patch overlaps a changed region, ON against N.
- **L5.** Final patch overlaps a changed region, OF against ON; and OA against OF.
- **L6.** Resolved, OF against N; and OA against OF.
- **L7.** Shown every changed region, ON against N; and OF against ON.

Printed without a rule: every count of 18's description for the four arms; the same by the number of changed
regions; the mean share of a task's changed regions shown; and, pooled over seeds 2 and 3 for N, ON and OA, the
shares of task-runs resolved, shown every region and with a patch on a changed region, with a bootstrap by task.

## What we expect, written before any session

L1 more (5 to 10 against 1 to 4). L2 no detectable difference. L3 more. L4 no detectable difference. L5: OF
against ON no detectable difference, OA against OF more. L6: no detectable difference in either. L7: ON against N
more, OF against ON no detectable difference. If L1 or L3 is not met here, the paper reports the two seeds side by
side and the pooled description, and says that the first seed did not repeat.

## Not covered

The 62 tasks whose shipped run saw every region. One model, two repositories. The oracle is a bound, not a tool:
nothing that reads a repository can know which lines a fix will change.
