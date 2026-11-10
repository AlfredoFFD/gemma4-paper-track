# Pre-registration 12: a file without lines

Status: FROZEN on Nov 10, 2026, 4:02 PM EST, by the commit that adds this file, before any replay of its condition
ran on any platform. It adds one condition to the one-step design of pre-registrations 02 to 05 and changes none of
their rules. Tags: [Claude Code] wrote it after a blind reader of a draft asked for the condition; [team] had not
read this text when it was frozen.

File hashes at freezing (md5): `analysis/make_states_f.py` `510c56d26aa6b049f11ba451167e6e9e`,
`analysis/fork_states_f/states.jsonl` `9619d4d158245e34e853c5c3dd25b9b7` (built by that script from
`analysis/fork_states_d/states.jsonl`, `d3105df0dc4aa43d7bb0afbdd6123b44`; not tracked, 25 MB),
`analysis/modal_g/forks_12_modal.py` `f6383d7ffaa6261802449a0921ab8a55`, `analysis/analyze_12.py`
`9d36f00047b1b2e7b7f3345daba853c1`. Used unchanged: the one-step runner `analysis/modal_w/forks_w_runner.py`
`65372125c2e23b48f5ee0e829a5e4167`, `analysis/gates_c.py` `84f2af2d7d7f21813c930c6fd1d354ec`,
`analysis/mangled_sensitivity.py` `7f64709fa901e9b307525e7ffc6284fb`, `analysis/explore_first_reads.py`
`cff4ab21af1f58244a0df872af1d46ba`.

## Why

Pre-registration 04 showed that a neighbor's file and line range together carry the effect of the list with
addresses (name, file and lines against bare names: +4.75 [3.00, 6.58]) and that the definition line adds nothing.
It had no condition with the file and without the lines, so the path and the line range are confounded. In other
teams' public runs a first read after a result that names only a file starts at line 1 (3 of 450 ask past it), but
that is a count, not an experiment. This run adds the missing condition.

## Design

- Condition EPATH: the note of the name-file-lines condition (EL) with the line range removed from every entry.
  Each neighbor keeps its name and its file: `{"name": "pkg.mod.fn", "file": "pkg/mod.py"}`. 6,082 entries in 407
  states, 5,975 with a file.
- The 407 states, seeds 1 to 3, one model call per replay, no tool executes: 1,221 replays. Gemma-4-31B on one
  rented A100-80GB with the harness wheels of Sep 30 (v28): the platform, wheels, states and seeds of the run of
  pre-registration 04.
- Reference conditions are not re-run. Bare names (H), name with file and lines (EL) and the full entry (E) come
  from the run of pre-registration 04 (`analysis/results/c/forks`).

## Outcomes

1. Reads a listed neighbor: the registered outcome of pre-registrations 02 to 05 (`gates_c.any_true`).
2. Opens a listed neighbor's file: the next call is a `read_file` of a file that holds a listed neighbor and that
   the agent had not opened (`mangled_sensitivity.opens_listed_file`), at any line.
3. Among those reads: whether the start line the model wrote is past line 1 (`explore_first_reads.read_stats`).

A state is complete if H, EL and EPATH are usable for seeds 1 to 3 under the frozen interface-failure rule.
Intervals: 95% bootstrap clustered by state, 2,000 resamples; clustered by task beside them.

## Rules

They apply if at least 200 states are complete.

**P1.** EL minus EPATH on outcome 1. "The line range, not the path, gets the agent to the code" if the lower bound
is above 0.

**P2.** EPATH minus H on outcome 2. "A path alone gets the agent to the file" if the lower bound is above 0.

**P3.** Under EPATH, at most 5% of the first reads of a listed neighbor's file ask past line 1: "without a line
number the file is read from the top". Tested only if there are at least 30 such reads.

No rule, reported: EPATH minus H on outcome 1; EL minus EPATH on outcome 2; every condition's rates; interface
failures.

## Gate

A smoke test on 8 states: at least 80% of its replays usable under the frozen interface-failure rule, read from the
runner's own summary (rows, errors, rows with a call). Its outcomes are not read.

## Stated limits

- The new condition and its references come from two runs. Between two earlier runs of one condition the paired
  difference was +0.58 [−0.41, 1.57] (full entries, hosted against rented) and +0.25 [−0.33, 0.82] (bare names).
  A difference of that size between runs would not change P1 at the size pre-registration 04 leads us to expect
  (about 4 points) and could matter for P2.
- One model, one run, the same 407 states as every earlier one-step result.

## Power, stated as assumptions

If EPATH behaves like bare names on outcome 1 (about 3%) and EL gives 7.75% as before, P1 has a difference of
about 4.7 points with a half-width near 2: detected. If a path opens the file about as often as the full entry
(11.5% against 7.3% for bare names), P2 is detected; a rise under 2 points will read as "not detected".

## What has been seen

Every earlier result of this repository, among them the public-run counts and the first-read counts of the replays.
The analysis script was tested on a stand-in file in which the published rows of the name-and-definition-line
condition of pre-registration 04 were relabeled EPATH; its output repeats known numbers. Nothing of the EPATH
condition exists.

## What is reported regardless of outcome

The three rules with their intervals, met or not; every rate; interface failures; the raw per-replay records; the
versions recorded by the run.

## Amendments
