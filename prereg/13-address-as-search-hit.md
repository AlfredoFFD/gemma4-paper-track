# Pre-registration 13: the address written as a search hit

Status: FROZEN on Nov 10, 2026, 5:05 PM EST, by the commit that adds this file, before any replay of its condition
ran on any platform. It adds one condition to the one-step design of pre-registrations 02 to 05 and 12 and changes
none of their rules. Tags: [Claude Code] wrote it after three blind readers of a draft set two of our own counts
side by side (after its own search the agent asks for the named line in 83 of 100 first reads; after a list that
carries line ranges it does so in 20 of 78 first reads in fresh episodes and in 375 of 1,000 at paused steps) and one
of them asked for the list printed the way a numbered search prints its hits; [team] had not read this text when it
was frozen.

File hashes at freezing (md5): `analysis/make_states_h.py` `0a7a1678437e0be6ffbdd0a3cee79e8b`,
`analysis/fork_states_h/states.jsonl` `921fbbab3c74df1f340d60e0a465209e` (built by that script from
`analysis/fork_states_d/states.jsonl`, `d3105df0dc4aa43d7bb0afbdd6123b44`; not tracked),
`analysis/modal_g/forks_13_modal.py` `eb08cb3c668b6894b9452894fca1f006`, `analysis/analyze_13.py`
`9cf7088b5faaded49fbd775864619bcd`. Used unchanged: the one-step runner `analysis/modal_w/forks_w_runner.py`
`65372125c2e23b48f5ee0e829a5e4167`, `analysis/gates_c.py` `84f2af2d7d7f21813c930c6fd1d354ec`,
`analysis/mangled_sensitivity.py` `7f64709fa901e9b307525e7ffc6284fb`, `analysis/explore_first_reads.py`
`cff4ab21af1f58244a0df872af1d46ba`.

## Why

A list that gives each neighbor's file and line range is followed about three times as often as bare names
(pre-registrations 03 to 08). Yet the agent uses the line range in a minority of the files it opens from such a
list, and far less often than it uses the line of a search hit. The lists so far were JSON objects with a `lines`
field ("272-278"). A numbered search prints `file:line:text`. This run asks whether the same address, written the
way a search writes it, is followed more.

## Design

- Condition EG: under the same first line as every other list condition, one neighbor per line, in the order of
  the full-address condition (E): `<file>:<first line of its range>:<its first definition line>`. Example:
  `fastapi/_compat.py:272:def copy_field_info(*, field_info: FieldInfo, annotation: Any) -> FieldInfo:`.
  A neighbor without an address keeps its name alone on its line. 6,082 entries in 407 states: 5,975 written as
  hits, 107 as names. The note is shorter than E's (mean 984 characters against 2,442).
- The 407 states, seeds 1 to 3, one model call per replay, no tool executes: 1,221 replays. Gemma-4-31B on one
  rented A100-80GB with the harness wheels of Sep 30 (v28): the platform, wheels, states and seeds of the run of
  pre-registration 04.
- Reference conditions are not re-run. The full address as JSON (E), name with file and lines (EL) and bare names (H)
  come from the run of pre-registration 04 (`analysis/results/c/forks`).

## Outcomes

1. Reads a listed neighbor: the registered outcome of pre-registrations 02 to 05 (`gates_c.any_true`).
2. Opens a listed neighbor's file: the next call is a `read_file` of a file that holds a listed neighbor and that
   the agent had not opened (`mangled_sensitivity.opens_listed_file`), at any line.
3. Among those reads: whether the start line the model wrote is past line 1 (`explore_first_reads.read_stats`).

A state is complete if E and EG are usable for seeds 1 to 3 under the frozen interface-failure rule. Intervals: 95%
bootstrap clustered by state, 2,000 resamples; clustered by task beside them.

## Rules

They apply if at least 200 states are complete.

**X1.** EG minus E on outcome 1. "Written as a search hit, the address is followed more" if the lower bound is above
0; "followed less" if the upper bound is below 0; otherwise "no detectable difference".

**X2.** EG minus E on outcome 3 (the share of first reads of a listed neighbor's file that ask past line 1; states
that have such a read in either condition). "Written as a search hit, the line is asked for more often" if the lower
bound is above 0; "less often" if the upper bound is below 0; otherwise "no detectable difference". Tested only if
each condition has at least 30 such reads.

No rule, reported: outcome 3 restricted to reads of a file in which no listed neighbor starts within the first 150
lines (a read from line 1 shows 150 lines); EG minus EL and EG minus H on outcome 1; EG minus E on outcome 2; every
condition's rates; interface failures.

## Gate

A smoke test on 8 states: at least 80% of its replays usable under the frozen interface-failure rule, read from the
runner's own summary (rows, errors, rows with a call). Its outcomes are not read.

## Stated limits

- The new condition and its references come from two runs. Between two earlier runs of one condition the paired
  difference was +0.58 [−0.41, 1.57] (full entries, hosted against rented) and +0.25 [−0.33, 0.82] (bare names).
- EG differs from E by more than its layout: it has no JSON wrapper, no last line of the range and no qualified
  name, and it is 60% shorter. A difference in either direction is the effect of the writing as a whole.
- The list still arrives as a note the agent did not ask for. The run tests the writing, not who asked.
- One model, one run, the same 407 states as every earlier one-step result.

## Power, stated as assumptions

E reads a listed neighbor in 8.6% of the reference run's replays. A rise of 3 points or more would be detected
(half-width of a paired difference near 2); a rise under 2 points will read as "no detectable difference". For X2,
E asks past line 1 in 53 of 139 first reads; with about as many reads under EG, a difference above about 12 points
is detected.

## What has been seen

Every earlier result of this repository. Among them, from today and exploratory: in the reference run's E
condition, of the first reads of a file in which no listed neighbor starts within the first 150 lines, 41 of 75 ask
past line 1; in the fresh episodes of pre-registration 09, 61 of 62 first reads after a search hit ask past line 1
when the smallest named line is past line 150, against 16 of 42 after a graph answer with line ranges. The analysis
script was tested on a stand-in file in which the published rows of the name-file-lines condition of
pre-registration 04 were relabeled EG; its output repeats known numbers. Nothing of the EG condition exists.

## What is reported regardless of outcome

Both rules with their intervals, whichever way they fall; every rate; interface failures; the raw per-replay
records; the versions recorded by the run.

## Amendments

(none)
