# Pre-registration 15: the agent's own search, with and without its line numbers

Status: FROZEN on Nov 10, 2026, 8:33 PM EST, by the commit that adds this file, after the smoke test described under Gate and
before any replay of the full run. It adds a one-step experiment on new
states and changes no rule of pre-registrations 02 to 14. Tags: [Claude Code] wrote it after blind readers of a
draft asked that the observational half of the reading rule be manipulated.

File hashes at freezing (md5): `analysis/make_states_s.py` `3b2e4a5efc17e508d6781bd27a0cd17e`,
`analysis/fork_states_s/states.jsonl` `a90d2df2d7b6fc12591fffe2f1622a2b` (built by that script from the recorded
runs; not tracked; on the volume as `/inputs_g/states_s.jsonl`), `analysis/modal_g/forks_15_modal.py`
`31e898cf3b2a9a586375013209ee545b`, `analysis/analyze_15.py` `5dd2680966b40d7ed717c5387766ccf0`. Used unchanged:
the one-step runner `analysis/modal_w/forks_w_runner.py` `65372125c2e23b48f5ee0e829a5e4167`, `analysis/replay.py`
`446b85be41d90e0e8fdb7c32dd5ea2f1`, `analysis/fork_states.py` `7fc2e4bb40f50b64638a1243e6a636ba`,
`analysis/analyze_forks.py` `8b22556e948c0df33f80cbeef8c11300`, `analysis/gates_c.py`
`84f2af2d7d7f21813c930c6fd1d354ec`, `analysis/mangled_sensitivity.py` `7f64709fa901e9b307525e7ffc6284fb`,
`analysis/public_runs_address.py` `a86e30082d20caefc02fc9ec0fc3512a`.

## Why

The reading rule of the starter agent has two halves. A first read of a file asks for lines past line 1 only when
the tool result just before showed a line number for that file; otherwise it reads from the top (a read without a
range returns lines 1 to 150). The first half is randomized: after lists without line numbers, 0 of 856 first reads
ask past line 1 (`analysis/results/explore_first_reads.txt`), and 0 of 104 under the condition of pre-registration
12. The second half is a count: after the agent's own numbered search, 83 of 100 first reads ask past line 1 in
our fresh episodes (pre-registration 11). The agent runs a numbered search when it wants a line, so that count
cannot tell the line number from the intent. This run keeps the intent and removes the number: at paused steps
that follow the agent's own search, the result keeps its line numbers or loses them. A third arm hands the removed
numbers back in a note, to test whether a line number handed over is used like one in the agent's own result.

## Design

**States.** A candidate step is a step of a recorded base run (the starter agent, Gemma-4-31B, 318 public runs)
such that:

- its one call is `run_command`, the command line runs a search program (grep in every case found) and the result
  has status ok;
- the output has at least one hit line in a repository file that the agent has not opened earlier in the run. A hit
  line is `path:line:text`, or `line:text` when the command names exactly one repository file. A repository file is
  a Python file of the task's snapshot. Opened is what `fork_states.py` counts: a `read_file` that returned content,
  or a cat, sed, head, tail, grep, rg, awk, less or more command on the file that printed something;
- the step comes before any `edit_file`, `submit_patch`, `write_file` onto a repository file, parallel call or
  compaction, and the next model call was logged and not compacted (the conditions of `fork_states.py`, without its
  cap on the prompt size);
- the output has at most 40 hit lines and fewer than 5,000 characters (the harness cuts an output at 5,000).

At most the first two candidate steps of a run are kept. If more than 100 remained, the 100 with the smallest sha1
of `"<task>|<run>|<step index>"` would be the states. Counts: 965 search steps with output before any edit or
compaction; 449 with a numbered hit line; 370 of those have no hit in a repository file not opened earlier (the
agent mostly searches files it has already read), 6 are cut off, 2 are followed by a compaction; 71 candidate
steps; at most two per run: **61 steps in 47 runs of 29 tasks**. All 61 are the states (48 from one repository, 13
from the other; 14 runs give two states). The hit files of a state are the repository files with a hit line in its
last result that the agent had not opened: 114 in all. The 61 results hold 489 hit lines, 28 context lines (in one
state) and no other line. In 38 states the command names one file and the hits are written `line:text`. Every one
of the 442 hit lines that lie in a Python file of the snapshot equals that line of the snapshot.

**Arms.** The replayed history ends with that tool result. Nothing else is added, except in S0N.

- `S`: the result as recorded.
- `S0`: the same result with the line number removed from every hit line and every context line (`path:123:text`
  becomes `path:text`; `123:text` becomes `text`; `path-123-text` becomes `path-text`; `123-text` becomes `text`).
  Nothing else changes: same lines, same order, same text.
- `S0N`: S0, then a note in the channel of the earlier notes (a user message after the result, as in the
  full-address condition E), which reads `Line numbers of the matches above:` followed by one line per hit,
  `path:line`, in the order of the result (for a `line:text` hit, the path is the file as the command wrote it).

Example (a search of two files; the agent had opened the first):

    S     fastapi/applications.py:4560:    def on_event(
          fastapi/routing.py:4484:    def on_event(
    S0    fastapi/applications.py:    def on_event(
          fastapi/routing.py:    def on_event(
    S0N   the result of S0, then the note:
          Line numbers of the matches above:
          fastapi/applications.py:4560
          fastapi/routing.py:4484

In S0 and S0N the recorded search command is left as it was (it still asks for line numbers) and only the result
changes, so the history is slightly incoherent there. That is the one thing changed. The public-run classifier
(`public_runs_address.classify`) finds a line number for each of the 114 hit files in the result of S and for none
in the result of S0.

**Replays.** 61 states, three arms, seeds 1 to 3, one model call per replay, no tool executes: 549 replays.
Gemma-4-31B on one rented A100-80GB with the harness wheels of Sep 30 (v28) and the one-step runner of
pre-registration 07, unchanged: the platform of pre-registrations 04, 05, 12 and 13. The runner replays a history
and can add a message; it cannot alter the last result. So each (state, arm) is its own record with its own
history: records S and S0 are replayed under the runner's arm A (nothing added), record S0N under an arm that adds
the note. The runner replays every record under every arm it is given; the cells outside the design are entered in
its results file as finished before it starts, and removed afterwards. A check with a stand-in model on all 183
records: the requests of S and S0 differ in the last message only, and the request of S0N is that of S0 plus one
user message equal to the note.

**Order and budget.** S and S0 of every state run first, then S0N, so that a stop leaves Q1 and Q2 whole. No new
replay starts once 50 minutes of the runner's clock have passed (its start-up, five to six minutes, included). The
run is expected to take 25 to 35 minutes and to cost 1.5 to 2 dollars.

## Outcome of a replay (the next call)

- `reads_hit_file`: the call reads a hit file: a `read_file` on it, or a `run_command` whose pipeline starts from
  cat, head, tail or sed -n on it and shows a known range of lines.
- `past_line_1`: that read asks to start past line 1 (`start_line` above 1; for a shell view, a first line above 1).
  A `read_file` whose start line stands under a mangled argument name (the name is `start_line` once quotes,
  backslashes and blanks are removed) counts as asking, and is counted apart as well.
- `on_a_hit`: the lines asked for include a hit line of that file; for `read_file`, from the start to the end asked
  for, at most 150 lines, and 150 lines when no end is asked.
- `searches_again`: the call is another search command; whether it asks for line numbers.

Estimands. Y1: the share of replays with `reads_hit_file` and `past_line_1`. Y2: the share with `reads_hit_file`.
C: among replays with `reads_hit_file`, the share with `past_line_1`.

## Rules

Intervals: 95% bootstrap by state, 2,000 resamples, seed 0 (`analyze_forks.diff_ci`); every contrast also by task.

**Q1.** Y1 under S minus Y1 under S0. Met if the lower bound is above 0.

**Q2.** Under S0, at most 5% of the reads counted in `reads_hit_file` ask past line 1. It needs at least 20 such
reads, otherwise "not testable".

**Q3.** Y1 under S0N minus Y1 under S0. Met if the lower bound is above 0. And C under S0N minus C under S, by
state: "used less often than in the agent's own result" if the upper bound is below 0, "no detectable difference"
if the interval includes 0, "used more often" if the lower bound is above 0. And the ratio R = (Y1 under S0N minus
Y1 under S0) divided by (Y1 under S minus Y1 under S0): the note carries the line number about as well as the
agent's own result if R is at least two thirds (point estimate); the interval of R is reported (the same resamples
by state; a resample whose denominator is zero or negative is counted and left out of the interval, and the count
is printed).

A replay is usable if it is not an interface failure under the frozen rule (runner error, no call, unknown tool,
malformed call); failures are counted by arm and excluded. A state is complete for a rule if every arm the rule
compares returned a usable call for seeds 1 to 3: S and S0 for Q1 and Q2, all three arms for Q3. A rule needs at
least 40 complete states; otherwise it is reported as underpowered. (The floor was set when the number of
states, 61, was known and before any replay of the full run.)

Descriptive, printed after the rules: `on_a_hit` by arm; `searches_again` by arm; the next tool by arm; Y1 split
by whether the nearest hit of the file read (its hit closest to line 1) lies past line 150; the reads counted as
asking through a mangled argument name.

## Gate

A smoke test on 8 states (the first eight by sha1), every arm, seed 1: 24 replays. At least 80% usable calls in
every arm. Its outcomes are not read.

What it showed (Nov 10, 2026, ended 8:21 PM EST; one container, about seven minutes): usable calls 8 of 8 under S,
8 of 8 under S0 and 8 of 8 under S0N, no interface failure. The gate is passed. The prompt of S against the size
logged for the same step, on the 8 states: median difference −219 tokens, median absolute relative difference
2.33% (from 0.32% to 12.24%). That is above the 2% that the fidelity gate of the earlier runs allowed (1.68% there);
the cause is the one stated under limits. Between arms the prompt changes as it should: S0 is smaller than S by 4 to
190 tokens (median 20), S0N is larger than S0 by 25 to 556 (median 66). Nothing else of those rows was read: the
analysis script ran on them with its report discarded, and its scorer ran on the 24 calls without printing them.

## Stated limits

- 61 states from 47 runs of 29 tasks in two repositories, one model, one platform. States of one run and of one
  task are not independent; the by-task interval is printed beside each rule. The floor of 40 complete states
  leaves room for 21 incomplete states.
- The history before the last result is the same in every arm. In 6 states an earlier result had already shown a
  line number for a hit file, and it stays in S0.
- In S0 and S0N the command asks for line numbers and the result has none.
- The note of S0N is a message the agent did not ask for; in S the numbers sit in its own result. Q3 compares the
  two and cannot separate the channel from the position.
- The harness of the replays hands a tool result to the model as a dictionary; the recorded runs handed it as a
  string inside a dictionary, with its quotes, line ends and non-ASCII characters escaped once more. The prompt of S
  is smaller than the logged one for that reason, as in every one-step run before (here by 2.33% at the median of the
  smoke states). The three arms share the rendering.
- A hit in a file that is not a Python file of the snapshot keeps or loses its number like the others, and is not
  scored.

## Power, stated as assumptions

In the recorded runs, the call that followed these 61 results read a hit file in 43 and asked past line 1 in 36
(59% of the steps, 84% of those reads). If the replays of S behave alike and Y1 under S0 is near zero, the
difference of Q1 is near 55 points with a half-width near 13 by state: detected. A true difference under about 13
points would read as not met. Q2 needs 20 reads of a hit file under S0: at half the recorded rate of opening there
are about 60. In 28 states every hit file has its first hit past line 150, where a read from the top does not show
it.

## What has been seen

Every earlier result of this repository, and the recorded runs themselves, the next call after each of the 61
results among them (above). The analysis script was tested on stand-in rows built from call templates whose
scores are known by construction; its output repeats the tallies expected from the templates, the budget-stop
case and the underpowered case included. Of the conditions S0 and S0N nothing exists but the 16 smoke replays,
whose calls were not read.

## What is reported regardless of outcome

The three rules with their intervals, met or not; the ratio R with its interval; every rate; interface failures;
the raw per-replay records; the versions recorded by the run.

## Amendments

(none)
