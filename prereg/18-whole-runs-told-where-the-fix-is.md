# Pre-registration 18: whole runs told where the fix is, as names or as addresses

Status: FROZEN on Nov 11, 2026, 1:02 AM EST, by the commit that adds this file, before any session of the run it
governs was started. Before the freeze there was one plumbing check with a scripted model in place of the server (no
GPU); what was seen of it is listed under "What has been seen". Tags: [Claude Code] wrote it after four rounds of
blind readers named the same limit of the paper (no result at the end of a run) and after a count on the stored runs
of pre-registration 14, given below; [team] had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/make_oracle_18.py` `36e533947cdd31e8a6826e57f3a96eb5`, `analysis/modal_h/wholerun18_runner.py` `6f94e800469227af95d689f69903cf52`,
`analysis/modal_h/wholerun18_modal.py` `d09a3e20f513e8605799e510f8ec1364`, `analysis/store_18.py` `9b8cf1edf1d09225d3d65e1829c1e29e`,
`analysis/analyze_18.py` `2b9e5c84e94ba656cd12d0b07b9488b3`, the task list `analysis/oracle_18/tasks_18.txt` `4235306974c1252840bbec8c0bcd3d67`,
the manifest of the notes `analysis/oracle_18/manifest.json` `ce8eebc97423ff6c69bbbf41a6b00d3c` (counts and the md5 of every note; the notes
themselves are built from the competition data and are not tracked). Used unchanged: `analysis/analyze_14.py`
`ec13c46c322a270066d93355c7a26f87`. The runner is a copy of the runner of 14 (`dda4e525dbf01025d30e432502b3438b`) with the two
new arms; it refuses to start if the harness packages, budgets, context settings or agent files differ from those
recorded for the runs of 14.

## Why

The paper's third finding is an observation. In the whole runs of pre-registration 14, runs that were shown every
changed region of the reference patch resolved in 36 of 62 cases (N) and the others in 0 of 40. Seen after that
analysis, on the stored rows (`analysis/results/14/runs_14.csv`): on the 40 tasks whose N run was not shown every
changed region, the stored NAF run, an independent run, again was not shown every region in 34 and resolved 3. In
the public runs the six runs of a task agree on it in 75 of 105 tasks (`analysis/results/public/sources.txt`). So
whether a run sees all of the fix is largely a property of the task, and the observation cannot say whether seeing
all of it would have changed the outcome: those tasks may simply be hard. This run asks it causally. It also carries
the paper's contrast, a name against an address, to the end of a run with a list that is perfectly relevant: until
now that contrast was measured on the next call, and at the end of a run only with the graph tools' own answers,
which reached five runs.

Handing a system the gold locations is not new in kind. It is the oracle setting of repair benchmarks; one study
injects gold file and line spans into a pipeline system on another benchmark (arXiv 2603.29067), and another gives
ground-truth locations to a pipeline at the level of the line, the function and the file and finds a spread of three
points (arXiv 2604.00167; code pasted into the prompt, no agent loop). What is asked here is specific: this agent,
which navigates by itself, this harness, these tasks, and the same places written as names or as file-and-line
addresses. Nothing here is claimed as a first comparison of oracle formats.

## Design

- Tasks: the 40 tasks of pre-registration 14 whose stored N run (seed 1) entered the analysis, has a file to show,
  and was not shown every changed region (fastapi 22, rich 18). Listed in `analysis/oracle_18/tasks_18.txt` in run
  order (sorted ids, shuffled with `random.Random(18)`).
- Arms, identical in everything else, the harness as shipped (wheels of Oct 12, as N of pre-registration 14):
  - **N**, the control: nothing added.
  - **ON**, names: the task statement the agent receives ends with a note, "Note: the accepted fix for this issue
    changes code in these places:", then one line per distinct place name. A place is a changed region of a file the
    reference patch modifies, padded by 10 lines on each side and merged with neighbors within 5 lines; its name is
    the qualified name of the smallest function or class, by the file's own syntax tree, that contains its first
    changed line (async functions included; the competition's graph has no node for those), the module's dotted name
    when there is none, the file path when the file is not Python.
  - **OA**, addresses: the same note with one line per place: the file path, the place's line range in the task's
    snapshot, and the same name in parentheses. So OA holds everything ON holds, plus the address.
  - Files that the reference patch creates are in neither note.
  - The 40 tasks have 373 changed regions in 109 files, merged into 287 places with 252 distinct names; a task has
    3 places at the median (1 to 68). 27 places lie in an async function. 94 of the 287 places are named by their
    module only, because the place lies in no definition or because its first changed line is the line before an
    insertion between definitions; and some class names span thousands of lines. A name cannot say more than that,
    so a difference between OA and ON includes what a name cannot say.
- Seed 2 for every task and arm. The tasks were selected on the stored seed-1 run of N, so that run is biased toward
  failure on them by construction; every arm here, the control included, is a new run with another seed in the same
  launch.
- One session per task and arm; budgets, sampling, sandbox, model and server settings as in pre-registration 14
  (Gemma-4-31B, QAT, 4-bit; 40 tool calls, 25 minutes, 60 turns, 120 seconds per command). Two rented A100-80GB
  containers, each with half of the task list and at most 8 sessions at a time, as in 14; the three arms of a task
  run side by side in the same container. No new session starts in a container after 1.5 hours; the task order is
  random, so a run cut short is a random subset.
- The stored seed-1 runs of 14 (N and NAF) on the same tasks are printed for description only.

## Outcomes (per run, by the functions of `analysis/analyze_14.py`)

Resolved (the harness's verdict from the tests); shown every changed region (reads); shown a changed line; final
patch overlaps a changed region; new here: final patch touches every changed region. Interface failures and how the
session ended are counted apart, as in 14.

## Rules

Each rule compares two runs of the same task, on the tasks where both entered the analysis; the difference of the
two shares gets a bootstrap interval by task (2,000 resamples, seed 0). Verdict "more" if the interval lies above
zero, "fewer" if below, otherwise "no detectable difference". A rule gets a verdict only with at least 34 such
tasks. The exact McNemar p is printed beside each.

- **U1, does being told every place raise resolved tasks?** Resolved, OA against N.
- **U2, a name against an address, at the end of a run.** Resolved, OA against ON.
- **U3, does the agent then see all of the fix?** Shown every changed region, OA against N, and OA against ON.
- **U4.** Resolved, ON against N.

Everything else the analysis prints is description without a rule: the counts per arm from "shown a changed line"
through "shown every changed region" and "patch touches every changed region" to "resolved"; endings; tool calls;
by repository; resolved in OA by resolved in ON; the stored seed-1 runs.

## What we expect, written before any session

- U1: more. The third finding predicts it. Our guess is 6 to 15 of 40 against about 3 in the control. If the
  interval includes zero, the finding is a marker of hard tasks and not a cause, and the paper will say that.
- U2: no detectable difference. Within a run the agent can search for a name, and our replays say an address brings
  a read forward, not that it changes where the agent ends up. If OA resolves more than ON, the way the places are
  written matters to the end; either result is reported as it falls.
- U3: OA above 80% of runs against about 6 of 40 in the control; ON below OA.

Forty tasks resolve differences of about 20 points; smaller effects will read as "no detectable difference".

## What has been seen

Every stored run of pre-registration 14 and its analysis, including the counts above; the exploratory counts on the
public runs. The output of the plumbing check: three tasks, the three arms, seed 2, nine sessions with a scripted model: every session went through the harness to a test
verdict; the note stands once in the first user message of ON and OA, right after the problem statement, with the
md5 of the manifest, and nowhere in N; the harness packages, budgets, context settings and agent files equal those
of 14. No session of N, ON or OA with seed 2 has run with the
model.

## Not covered

The 62 tasks whose N run was shown every region are not run, so this says nothing about harm or gain there, and no
estimate for all 103 tasks follows from it. One seed. One model. Two repositories. The oracle is an upper bound on
what any tool that prints the fix's places could do, not a tool.

## Notes added after the freeze

- Nov 11, 2026, 1:21 AM EST, while the sessions are running and before any row of this run has been pulled or read:
  four descriptive cuts are added to what will be reported, none with a rule, each labelled exploratory. They follow
  from a count on other runs that arrived after the freeze (`analysis/results/explore_read_starts.txt`: tasks
  whose fix is one changed region are resolved in about half of the public runs at any depth in the file, tasks
  with 2 to 3, 4 to 9, and 10 or more regions in 22%, 12% and 0%). (a) Resolved and shown-every-region per arm,
  split by the number of changed regions of the task (1; 2 or 3; 4 to 9; 10 or more). (b) Per arm, the share of a
  task's changed regions that the run was shown, as a mean over tasks, beside the all-or-nothing count of U3.
  (c) Per arm, where the run's file reads start (the top of a file; where the run has read; a line that a result or
  the note printed; none of these), and for ON how a named place is reached (a search by the run, reading on, or a
  jump with no number). (d) Per arm, the number of tool calls before the last changed region is first shown, in the
  runs that are shown every region. The rules U1 to U4 and their tests are unchanged.

- Nov 11, 2026, 2:25 AM EST, after the run: both shards ran to the end; all 120 sessions entered the analysis (no
  infrastructure failure, no missing trace); the note stood once in the first user message of every ON and OA
  session and in none of N.
- Nov 11, 2026, 2:26 AM EST: the independent script (`analysis/rederive_18.py`, written blind) gives the same verdict on
  every rule and the same counts of resolved runs. It found that the registered script, through the loader of 14,
  credits a step that holds several tool calls with the result of its first call only, so reads made in parallel
  are lost: 2 results in N, 10 in ON, 48 in OA, where the agent often reads all the given addresses at once. With
  every call paired with its result, OA is shown every changed region in 32 of 40 runs, not 25 (N 8 and ON 27 are
  unchanged); U3 keeps both verdicts (OA against N +60.0 [45.0, 75.0]; OA against ON +12.5 [-2.5, 25.0]). The
  registered output is left as the script printed it; the paper gives the corrected count and says so.
