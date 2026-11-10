# Pre-registration 04: experiment C (the false edge under the legible encoding, and which part of an entry is followed)

Status: FROZEN on Nov 9, 2026, 9:21 PM EST, by the commit that adds this file, before any replay of arms Ep, EL or ES ran on
any platform and before any output of them existed. It amends pre-registration 03 and changes none of its rules.
Tags: [Claude Code] wrote it; the plan was approved by [team].

## Why

Pre-registration 03 found that a note listing true neighbors with file, lines and first definition line (arm E) is
followed about three times as often as the same list as bare names (arm H): 8.25% against 2.75% of replays, pooled
over runs v5, v6 and v8. Two questions it cannot answer:

1. Does the model follow a false entry when it is written in the same legible form? The fake-edge test of
   pre-registration 03 (B2) ran under arm D, where the swapped-out entry was touched in 0.34% of replays, far below
   its 5% floor, so it was underpowered.
2. Which part of an arm E entry carries the effect: the location (file and lines) or the definition line?

## Arms

All three are user-role notes with arm H's wording, delivered after arm A's messages, on the same 407 states and
seeds 1 to 3. Entries are written exactly as arm E writes them (same keys, same order, a missing field stays missing).

| Arm | Last piece |
|---|---|
| Ep | arm E's note on the decoy list: the swapped-out true neighbor is replaced by the decoy of pre-registration 02, written with the decoy's own file, lines and definition line; the list is re-sorted as the tool sorts |
| EL | the true list, each entry with name, file and lines only |
| ES | the true list, each entry with name and first definition line only |
| E, H | re-run unchanged in the same run, as same-platform references |

States file: `analysis/fork_states_c/states.jsonl`, md5 beginning `9d7ad4bbd8f4`, built before this freeze.

## Platform change, stated in advance

The hosted GPU quota used for v5, v6 and v8 is spent until after the deadline. Experiment C runs on a rented
single A100 (tensor-parallel size 1 in place of 4 across four L4s), Python 3.12, with the same model weights
(Gemma-4-31B QAT W4A16), the same harness wheels (v28: adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7)
and the same replay code. The run records its versions. A second model, if one is run, gets its own amendment.

Because the platform differs, every contrast below uses only arms of this run. The pooled v5, v6 and v8 numbers
are never mixed into an experiment C contrast; they appear beside it for comparison only.

Gates, checked before any outcome of Ep, EL or ES is read:

- G1, fidelity (as in pre-registration 02): on 24 states under arm A, the median absolute relative difference
  between the replayed and the logged prompt size is at most 2%. If it fails, the run is not analyzed.
- G2, replication of B3 on this platform: P(any unopened true neighbor touched | E) minus P(the same | H), this
  run, has a lower 95% bound above 0. If it fails, that failure is the reported result, and C1 and C2 are
  reported as EXPLORATORY.
- G3, platform drift (descriptive, changes no rule): this run's E and H rates against the hosted runs' on the same
  states and seeds, with paired 95% intervals. A difference above 3 points with an interval excluding 0 is
  reported as a platform difference.

## Outcomes

As in pre-registration 02 and 03: the first function call after the fork; a touch of a listed node by a read,
edit, write or content-showing shell view, with the harness's caps; "any unopened true neighbor touched" over the
true neighbors in unopened files; the swapped-out entry; the decoy. Every arm is scored with the same spans from
the states file, whatever the note showed. Interface failures (error, no call, unknown tool, malformed arguments)
are excluded and reported by arm. Analysis uses states complete across the five arms and three seeds of this run.
95% bootstrap intervals clustered by state, 2,000 resamples; 90% where stated.

## Hypotheses and decision rules

**C1, the false edge under the legible encoding.** D_E = P(swapped-out entry touched | E) minus P(decoy touched |
Ep). The decoy takes the swapped-out entry's place in an otherwise identical note, so D_E is how much more often
a true entry is followed than a false one written the same way.

- Floor. The 5% floor of B2 cannot be met: the swapped-out entry was touched in 1.80% of arm E replays in the
  hosted runs. The floor here is 1%: the test is informative only if the swapped-out entry is touched in at
  least 1% of this run's arm E replays. Below that it is reported as underpowered, with the interval.
- "Checks the edge": the lower 95% bound of D_E is above 0 and the decoy rate is below half the swapped-out rate.
- "Follows a false edge as readily": the 90% interval of D_E lies within plus or minus 1.5 points and the decoy
  rate is at least half the swapped-out rate.
- Otherwise inconclusive, reported with the interval.
- Secondary, descriptive: P(any unopened true neighbor touched | Ep) minus the same under E (does one false entry
  change following of the true ones); the decoy's touch rate under Ep beside the mean per-entry touch rate of the
  unopened true entries in the same notes.

**C2, which part of the entry is followed.** On any unopened true neighbor touched, this run:

- A part "raises following" if its arm minus H has a lower 95% bound above 0 (EL for location, ES for the
  definition line).
- "Location carries it": EL raises following and ES does not. "Definition line carries it": the reverse.
  "Either part is enough": both do. "Only the full entry": neither does while G2 holds.
- A part is called "sufficient for the full effect" only if the 90% interval of E minus that arm lies within
  plus or minus 2 points. E minus EL and E minus ES are reported with intervals in every case.

## Power, stated as assumptions

About 1,160 replays per arm if all states complete. At the hosted rates, the 95% interval of a 1.8% rate is about
plus or minus 1.2 points. If the decoy is never touched under Ep (as in every hosted arm but one), D_E is about
1.8 with a lower bound near 0.7: "checks the edge". If the decoy is touched as often as the swapped-out entry, the
90% interval of D_E is about plus or minus 1.3 points, so "as readily" is reachable but not certain. For C2, the
hosted E minus H difference was 5.5 points with a half-width of about 2.1; a part that carries half of it (about
2.7 points) is near the detection limit, so "does not raise" for one part is weak evidence and is reported with
its interval, not as a zero.

## Partial runs

States are processed in a fixed shuffled order, so a run cut short is a random subset. The rules apply if at least
200 states are complete; below that everything is EXPLORATORY.

## What is reported regardless of outcome

All five arms' rates with intervals, the three gates, the inserted texts, the per-arm failure counts, the raw
replay outputs, and the harness, server and model versions recorded by the run. Anything not listed here is
labeled EXPLORATORY.
