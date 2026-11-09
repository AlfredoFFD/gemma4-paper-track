# Pre-registration 03: does framing or encoding make Gemma follow the graph, and does it then check?

Status: FROZEN on Nov 9, 2026, about 12:20 PM EST (the first version of this line said 9:05 AM, a clock error
corrected at 12:55 PM), before any replay of these arms ran; the run (kernel v6) started at 12:50 PM. Written after the results of
pre-registration 02 (run v5) were read: following of the graph's neighbor list was near the base rate in every arm,
so the discrimination test there had no power. This extension changes only the last piece inserted at the fork;
the states, seeds, outcome definition, caps, exclusions and analysis code are those of pre-registration 02.

## Question

Two things could make the list matter: how it is framed (a note that merely reports the neighbors, versus an
instruction to look at them) and how it is written (bare dotted names, versus names with their file, lines and
signature, the question of *Talk like a Graph* asked inside an agent). If an instruction lifts following into a
measurable range, the pre-registration 02 question becomes testable: is a planted false neighbor followed as
readily as a true one?

## Arms (same 407 states and seeds 1, 2, 3; the history is identical; only the last user-role note differs)

| Arm | Last piece |
|---|---|
| D | the harness instructs the agent to look at the neighbors of the node and read the ones not yet opened, followed by the true list in the tool's JSON (`fork_states.D_WORDING`) |
| D' | the same instruction with the P' list (one true neighbor replaced by the decoy, re-sorted) |
| E | the pre-registration 02 note wording (`H_WORDING`), with each neighbor written as an object: name, file, line range, and the first line of its definition (`fork_states.E_WORDING`); true list only |

The instruction in D and D' names the queried node and the list as a whole, never a specific entry. E adds
information that the bare list lacks (where each neighbor lives); it is a richer encoding, not an information-matched
one, and is compared with H for that reason.

Comparison arms come from run v5: H and H' (note, bare names), P and P' (tool result), A (nothing added). The
model, server configuration, harness wheels and replay code are the same; the two runs are pooled by state and seed.

## Amendment of Nov 9, about 12:53 PM EST: the rewired-graph control (frozen before any output of v6 or v7 was read; the time was first written as 1:15 PM by a clock error and corrected at 1:00 PM)

Proposed by the team through a second session while v6 was running. Two more arms on the same states and seeds,
run as kernel v7:

| Arm | Last piece |
|---|---|
| R_D | the D instruction with a rewired list: the node's neighbors in a degree-preserving random rewiring of the repo graph (seeded double-edge swaps, 10 per edge; GraphAudit's control), minus gold, in-view and true neighbors, padded from the node's directory to the true count, sorted as the tool sorts |
| R_E | the E note with the same rewired list, each entry encoded with its file, lines and first definition line |

The rewired entries are, like the true entries, in unopened files and unseen names; they are scored exactly like
the true entries ("any rewired entry touched"). Construction fact, recorded at export (after a code review at
1:00 PM made the rewired entries meet the same eligibility as the scored true entries: unopened, non-gold file,
unseen name): the rewiring's own neighbors were often excluded, so 847 of the rewired entries across 298 states
were padded from the node's directory; 382 lists have exactly the true list's length and 25 are shorter because
the directory ran out of eligible nodes. A first version of these lists (kernel v7, cancelled before it ran) had
not excluded opened files.

- B4, structure versus vocabulary: at each dose (D versus R_D, E versus R_E), the difference between any-true
  following under the true list and any-rewired following under the rewired list. "Structure matters" if, in at
  least one dose, the true list beats the rewired list by at least 3 points with a 95% clustered interval
  excluding 0. "Vocabulary, not map" if, in every dose where the true list raised following above arm A, the
  difference lies within plus or minus 2 points. Otherwise inconclusive with the intervals.
- The fake-edge test (B2) and the other rules above are unchanged.

## Outcomes

As in pre-registration 02: the next call's touch of listed true neighbors in unopened files, of the swapped-out
entry and of the decoy, with the harness's caps; interface failures excluded and reported; 95% bootstrap intervals
clustered by state (2,000 resamples).

## Hypotheses and decision rules

- B1, framing: P(any unopened true neighbor touched | D) minus P(the same | H) has a lower 95% bound above 0.
- B2, discrimination under instruction (the test pre-registration 02 could not run): D_B = P(touch of the
  swapped-out entry | D) minus P(touch of the decoy | D'). The test is informative only if the swapped-out entry is
  touched in at least 5% of D replays; below that it is reported as underpowered. If informative: "does not check"
  when the 90% interval of D_B lies within plus or minus 2 points; "checks" when the lower 95% bound of D_B is above
  0 and the decoy rate is below half the swapped-out rate; otherwise inconclusive with the interval.
- B3, encoding (two-sided): P(any unopened true neighbor touched | E) minus P(the same | H); the 95% interval excludes 0.
- Secondary, listed in advance: graph-tool calls as the next action per arm; share of replays with thought text and
  median completion tokens; mentions of fresh true entries and of the decoy in the thought text; the next call's
  category mix.

## Power, stated as assumptions

1,221 replays per arm. If D lifts the swapped-out entry to 10% and D' puts the decoy at 10%, the interval of D_B
is about plus or minus 3 points, so "does not check" would need the two within 2 points of each other, which is a
demanding bar at these counts; the paper reports the interval either way. A difference of 5 points or more between
a 10% and a 5% rate is detectable.

## What is reported regardless of outcome

All rates with intervals for D, D', E beside the v5 arms, the inserted texts, the per-arm failure counts, the raw
replay outputs, and the harness, vLLM and model versions recorded by the run.
