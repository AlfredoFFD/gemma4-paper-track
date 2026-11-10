# Trim proposal for `paper/draft.md`

Prepared Nov 10 against the draft at commit 2662c01. Nothing in `draft.md` was changed.

## Applied on Nov 10

The coordinator approved a subset; `paper/draft.md` was edited by a script that asserted each quoted text occurs exactly
once in both the original and the partly edited draft before replacing it. Nothing was committed. Each edit below is tagged
APPLIED, APPLIED MODIFIED, PARTLY APPLIED or NOT APPLIED.

- Count without the header note: 3,134 before, 3,009 after (Git Bash `wc -w`, which skips the standalone minus signs in
  "E − H"; counting every whitespace-separated token: 3,152 before, 3,028 after).
- The cuts saved more than this; the fixes for the ten problems below, the two figure references with captions and
  the results placeholder comment added words back.
- All ten problems were fixed in the draft, except the stale "One model" and "(the registered follow-up splits them)"
  in Section 8, the abstract's last sentence and the title, which wait for the Experiment C and D results.
  GraphLoc still has no link (none on disk).

## Counts

- Draft without the header note (title and headings included, `wc -w` style): **3,134 words**. Without the title line, which Kaggle may take as a separate field: 3,108. Markdown table pipes count as words under `wc -w`; ignoring them, 3,084.
- Room needed: about 250 words of new results, so the body must reach about 2,750 before they go in: cut about 385 (from 3,134) or 360 (if the title does not count).
- Word savings below are computed by script (`wc -w` style, old minus new), and every quoted current text was checked to occur exactly once in the draft.

| Package | Edits | Saves |
|---|---|---|
| Safe: tiers 1 and 2, figure-independent table tightening (28, 29a, 30a) | 34 | **263** |
| Safe + Section 6 rewrite + one Section 7 cut (31a, 32, 33) | 37 | **339** |
| Maximum: section 2 as prose (38), figure carries both tables (29b, 30b), Section 6 para 1 deleted (31b), 32, 33; edit 34 excluded | 34 | **525** |

Recommended: the middle package (339) plus 29b and 30b if Figures 1 and 2 print the prompt strings and the numbers with intervals as text. That is 440 words, enough for the new results with a margin. Fix problems 1 to 3 below before any of this; problem 1's fix costs about 16 words back.

Conflicts: pick one of 29a/29b, 30a/30b, 31a/31b. Edit 38 replaces 8, 25, 26 and the first half of 9 (keep 9's second half with it). Edit 27 assumes Section 2 keeps the one-hop 10%. Edits 6 and 37 touch the same sentence and apply cleanly together.

## Summary

| # | Section | Saves | Risk |
|---|---|---|---|
| 1 (APPLIED) | 5 (heading) | 4 | none |
| 2 (APPLIED) | 5 (attention paragraph) | 11 | none |
| 3 (APPLIED) | 1 (para 1) | 10 | none |
| 4 (APPLIED) | 1 (para 1) | 6 | none |
| 5 (APPLIED) | 3.3 + 4 (merge the fidelity result into the method) | 12 | none |
| 6 (APPLIED) | 4 (robustness) | 3 | none |
| 7 (APPLIED) | 4 (concentration) | 4 | none |
| 8 (NOT APPLIED) | 2 (intro) | 2 | none |
| 9 (PARTLY APPLIED) | 2 (last bullet) + 3.1 | 5 | none |
| 10 (APPLIED) | 3.2 (decoy) | 2 | none |
| 11 (APPLIED, MODIFIED) | 3.2 (rewired list) | 4 | none |
| 12 (APPLIED, MODIFIED) | 4 (sessions and interface failures) | 1 | none |
| 13 (APPLIED, MODIFIED) | 4 (Experiment A) | 4 | none |
| 14 (APPLIED) | 4 (independent recount) | 3 | none |
| 15 (APPLIED) | 5 (matched entries) | 22 | none |
| 16 (APPLIED) | 5 (toward the fix) | 5 | none |
| 17 (APPLIED, MODIFIED) | 8 | 4 | none |
| 18 (APPLIED, MODIFIED) | Reproducibility | 8 | none |
| 19 (APPLIED) | Abstract (sentence 3) | 5 | none |
| 20 (APPLIED) | Abstract (exploratory sentence) | 3 | none |
| 21 (APPLIED) | 5 (any-means paragraph) | 12 | none |
| 22 (APPLIED) | 4 (B2 bullet) | 0 | none |
| 23 (APPLIED) | 5 (attention paragraph) | 2 | loses a number |
| 24 (APPLIED) | 5 (cross-session checks) | 4 | loses a number |
| 25 (NOT APPLIED) | 2 (bullet 1) | 7 | loses a number |
| 26 (NOT APPLIED) | 2 (bullet 3) | 13 | loses a number |
| 27 (NOT APPLIED) | 8 | 12 | none if Section 2's bullet 3 stays |
| 28 (APPLIED) | 1 (para 2) | 27 | none if Figure 1 shows the pause-and-replay schematic |
| 29a (NOT APPLIED) | 3.2 (arms table, keep the table) | 23 | none |
| 29b (APPLIED, MODIFIED) | 3.2 (arms table, figure carries it) | 67 | verifiability: the exact prompt wording leaves the text and lives only in Figure 1 and the repo |
| 30a (NOT APPLIED) | 4 (results table, keep the table) | 14 | none |
| 30b (NOT APPLIED) | 4 (results table, figure carries it) | 71 | loses numbers from the text: every per-arm interval, and the true-neighbor rates of R_D and R_E |
| 31a (APPLIED, MODIFIED) | 6 (para 1, rewrite) | 16 | changes a claim's strength (weaker, now supported) |
| 32 (APPLIED, MODIFIED) | 6 (para 2) | 47 | loses a number; weakens one claim, corrects another |
| 33 (NOT APPLIED) | 7 | 13 | removes two citations |
| 34 (NOT APPLIED) | 4 (failed earlier run) | 20 | loses a caveat |
| 35 (APPLIED) | 3.1 | 6 | none |
| 36 (APPLIED) | 4 (independent recount) | 14 | loses a number |
| 37 (APPLIED) | 4 (robustness) | 6 | loses a number |
| 38 (APPLIED) | 2 (whole section as one paragraph) | 39 | loses a number |
| 31b (NOT APPLIED) | 6 (para 1, delete) | 96 | loses the conclusion paragraph |
| 39 (NOT APPLIED) | 8 | 5 | none once Experiment C's paragraph lands |

## Tier 1: wording only (no number, caveat or claim lost)

### 1. [APPLIED (with the results placeholder comment above the heading)] Section 5 (heading)

Current, exact text with the file's line breaks:

```text
## 5. What the encoding changes (exploratory)

Nothing in this section was pre-registered.
```

Replace with:

```text
## 5. What the encoding changes (exploratory, not pre-registered)
```

- Saves: **4** words
- Risk: none
- Note: The label moves into the heading.

### 2. [APPLIED] Section 5 (attention paragraph)

Current, exact text with the file's line breaks:

```text
The difference between arms is in the action,
not in attention.
```

Replace with: delete.

- Saves: **11** words
- Risk: none
- Note: The paragraph's bold lead and Section 6 already say it.

### 3. [APPLIED] Section 1 (para 1)

Current, exact text with the file's line breaks:

```text
The agent may never
ask the graph; it may ask and ignore the answer; it may be unable to act on the answer as printed; or it may
follow the answer to the wrong place.
```

Replace with:

```text
The agent may never ask the graph, ignore the answer, be unable to act on it as printed, or follow it to the wrong place.
```

- Saves: **10** words
- Risk: none

### 4. [APPLIED] Section 1 (para 1)

Current, exact text with the file's line breaks:

```text
moves the resolve rate by
about one task in a hundred (28.9% to 29.9%, interval −4.1 to +6.3 points).
```

Replace with:

```text
moves the resolve rate from 28.9% to 29.9% (interval −4.1 to +6.3 points).
```

- Saves: **6** words
- Risk: none
- Note: The numbers say it; the gloss repeats them.

### 5. [APPLIED (the 3.3 sentence also gained the platform clause, problem fix i)] Section 3.3 + 4 (merge the fidelity result into the method)

Current (piece 1 of 2), exact text with the file's line breaks:

```text
Fidelity is checked on 24 states by comparing arm A's prompt size with the size
logged at the same step of the original run.
```

Replace with (piece 1 of 2):

```text
Fidelity: on 24 states, arm A's prompt size differs from the size logged at the same step of the original run by 1.7% (median; mean 3.0%; two states at 9.5% and 25%).
```

Current (piece 2 of 2), exact text with the file's line breaks:

```text
**Fidelity.** Arm A's prompt differs from the logged prompt by 1.7% (median; mean 3.0%; two states at 9.5% and
25%).
```

Replace with (piece 2 of 2): delete.

- Saves: **12** words
- Risk: none
- Note: Two quoted pieces: replace the first, delete the second (the whole bold Fidelity paragraph in Section 4).

### 6. [APPLIED] Section 4 (robustness)

Current, exact text with the file's line breaks:

```text
in each repository (+3.1 without one, +7.7 without the other)
```

Replace with:

```text
with either repository left out (+3.1, +7.7)
```

- Saves: **3** words
- Risk: none
- Note: Also clearer: the old wording reads as if the numbers were per repository.

### 7. [APPLIED] Section 4 (concentration)

Current, exact text with the file's line breaks:

```text
E − H is between +2.4 and +2.7, depending on how a tie for fifth place is broken (+2.37 [0.85, 4.07] at the low end).
```

Replace with:

```text
E − H is +2.4 to +2.7, depending on a tie for fifth place (+2.37 [0.85, 4.07] at the low end).
```

- Saves: **4** words
- Risk: none

### 8. [NOT APPLIED (superseded by 38)] Section 2 (intro)

Current, exact text with the file's line breaks:

```text
GraphLoc published 636 traces (3 runs, 106 tasks, two agents) made with the competition harness and model. From
the base agent's 318 traces, with our own scripts:
```

Replace with:

```text
GraphLoc published 636 traces (3 runs of 106 tasks, two agents) with the competition harness and model. In the base agent's 318, by our count:
```

- Saves: **2** words
- Risk: none

### 9. [PARTLY APPLIED (second half only; the bullet went with 38)] Section 2 (last bullet) + 3.1

Current (piece 1 of 2), exact text with the file's line breaks:

```text
- Compaction fires in 68% of runs, so replays must start before it.
```

Replace with (piece 1 of 2): delete.

Current (piece 2 of 2), exact text with the file's line breaks:

```text
before any edit and before compaction,
```

Replace with (piece 2 of 2):

```text
before any edit and before compaction (which fires in 68% of the public runs),
```

- Saves: **5** words
- Risk: none
- Note: Two quoted pieces: delete the bullet, put its number where the rule is applied.

### 10. [APPLIED] Section 3.2 (decoy)

Current, exact text with the file's line breaks:

```text
The swapped-out neighbor and the decoy both live in unopened files and neither name has appeared in the prompt.
The decoy is a real non-neighbor function from the same directory, not a fix location and not a test.
```

Replace with:

```text
The swapped-out neighbor and the decoy are both in unopened files, with names not yet in the prompt; the decoy is a real non-neighbor function from the same directory, neither a fix location nor a test.
```

- Saves: **2** words
- Risk: none

### 11. [APPLIED, MODIFIED (keeps "padding" and says the 847 entries are same-directory padding, not rewired edges)] Section 3.2 (rewired list)

Current, exact text with the file's line breaks:

```text
The rewired
list comes from seeded double-edge swaps (ten per edge), which keep every node's degree; its entries are in
unopened files, with unseen names and outside fix-location files (the scored true entries need only an unopened
file; Section 5), and padded from
the node's directory where the rewired neighborhood is short (847 padded entries in 298 states).
```

Replace with:

```text
The rewired list comes from seeded double-edge swaps (ten per edge), which keep every node's degree. Its entries are in unopened files, with unseen names, outside fix-location files (true entries need only an unopened file; Section 5), and padded from the node's directory where the rewired neighborhood is short (847 entries in 298 states).
```

- Saves: **4** words
- Risk: none
- Note: The filter asymmetry stays here as a pointer; it is stated in full in Section 5 and Section 8.

### 12. [APPLIED, MODIFIED (names the arms of each session)] Section 4 (sessions and interface failures)

Current, exact text with the file's line breaks:

```text
Three sessions on four L4 GPUs produced 12,210 replays: five arms in 4.1 hours, three in 3.0, two in 2.3. There
were 34 interface failures (24 malformed calls, 10 with no call; between 0 and 7 per arm), counted apart.
```

Replace with:

```text
Three sessions on four L4 GPUs produced 12,210 replays: five arms in 4.1 hours, three in 3.0, two in 2.3. The 34 interface failures (24 malformed calls, 10 with no call; 0 to 7 per arm) are counted apart.
```

- Saves: **1** words
- Risk: none
- Note: Problem 6 proposes naming the arms of each session here, which costs about 8 words back.

### 13. [APPLIED, MODIFIED (names the following contrast and both denominators)] Section 4 (Experiment A)

Current, exact text with the file's line breaks:

```text
With five arms alone, the list moved following by +0.8 points [−0.1, 1.7], so the following
hypothesis failed and discrimination was not tested: the decoy was followed 0 times in 2,442 replays, the
swapped-out true entry 6 times in 2,358 (complete states). Channel made no difference (+0.25 [−0.7, 1.2]). The tool result did
make the agent call the graph again (3.2% of next calls, against 0.3% in A).
```

Replace with:

```text
The list moved following by +0.8 points [−0.1, 1.7], so the following hypothesis failed and discrimination was not tested (decoy followed 0 times in 2,442 replays, swapped-out true entry 6 times in 2,358, complete states). Channel made no difference (P − H +0.25 [−0.7, 1.2]), though the tool result made the next call a graph call in 3.2% of replays, against 0.3% in A.
```

- Saves: **4** words
- Risk: none
- Note: Names the channel contrast. See problem 7 on the two denominators and on which contrast the +0.8 is.

### 14. [APPLIED] Section 4 (independent recount)

Current, exact text with the file's line breaks:

```text
Under the reading of the grep rule closest to the registered text it differs in
28 cells
```

Replace with:

```text
Under the reading closest to the registered grep rule it differs in 28 cells
```

- Saves: **3** words
- Risk: none

### 15. [APPLIED] Section 5 (matched entries)

Current, exact text with the file's line breaks:

```text
**The structure effect is smaller on matched entries.** The rewired entries were filtered (unseen names, no
fix-location files); the scored true entries were not all (the pre-registration's text says both sets met one filter; the code applied it to the rewired entries only). Restricting the true entries to the same filter
(3,292 of 3,704), E falls to 2.49% [1.20, 3.87], E − H is still +2.32 [1.12, 3.69], but true minus rewired is
+1.46 [0.00, 3.01] under E (lower bound −0.09 in an independent bootstrap) and +0.34 [−0.60, 1.29] under D. Most of the B4 gap comes from true neighbors in
fix-location files and names already in view, which the agent has its own reasons to visit and the list makes
reachable. What survives matching is small and its interval touches zero: a preference for a legible true edge over a
legible rewired one is not established, and R_E shows that the agent does read rewired locations when given lines
(5 of its 12 hits start at a listed first line).
```

Replace with:

```text
**The structure effect is smaller on matched entries.** The rewired entries were filtered to unseen names outside fix-location files; the scored true entries were not (the pre-registration says both sets were; the code filtered only the rewired ones). With the true entries filtered the same way (3,292 of 3,704), E falls to 2.49% [1.20, 3.87] and E − H is still +2.32 [1.12, 3.69], but true minus rewired is +1.46 [0.00, 3.01] under E (lower bound −0.09 in an independent bootstrap) and +0.34 [−0.60, 1.29] under D. Most of the B4 gap comes from true neighbors in fix-location files or already named in view, which the agent has its own reasons to visit. A preference for a legible true edge over a legible rewired one is not established, and the agent does read rewired locations when given lines (5 of R_E's 12 hits start at a listed first line).
```

- Saves: **22** words
- Risk: none
- Note: Every number and both disclosures (deviation from the pre-registration text; interval touching zero) stay.

### 16. [APPLIED] Section 5 (toward the fix)

Current, exact text with the file's line breaks:

```text
Counting only `read_file` calls on a not-yet-opened file that holds a fix location, the next
call goes there in 6.0% of A replays, 6.6% of H, 8.8% of D and 8.2% of E (E − A +2.15 [0.60, 3.95]). Counting any
read, edit or shell view of a file the gold patch changes, the rates are 6.9%, 7.2%, 9.4% and 8.5%, and E − A is
+1.63 [−0.26, 3.61]. The direction is toward the fix; the size depends on the definition,
```

Replace with:

```text
Counting only `read_file` calls on an unopened file that holds a fix location, the next call goes there in 6.0% of A replays, 6.6% of H, 8.8% of D and 8.2% of E (E − A +2.15 [0.60, 3.95]); counting any read, edit or shell view of a file the gold patch changes, 6.9%, 7.2%, 9.4% and 8.5% (E − A +1.63 [−0.26, 3.61]). The direction is toward the fix, the size depends on the definition,
```

- Saves: **5** words
- Risk: none
- Note: Definition-dependence kept word for word.

### 17. [APPLIED, MODIFIED ("clean but indirect and cover two of the three sessions")] Section 8

Current, exact text with the file's line breaks:

```text
the indirect drift checks are clean but not a same-session comparison.
```

Replace with:

```text
the drift checks are clean but indirect.
```

- Saves: **4** words
- Risk: none

### 18. [APPLIED, MODIFIED (adds [repository URL])] Section Reproducibility

Current, exact text with the file's line breaks:

```text
Code under Apache 2.0: the state exporter, the replay runner, the Kaggle script, the frozen analysis, the
independent recount, the exploratory script and its blind re-derivation, with the three pre-registrations and their timestamps, the raw
per-replay outputs, and the harness, vLLM and model versions recorded by each run.
```

Replace with:

```text
Released under Apache 2.0: the state exporter, replay runner, Kaggle script, frozen analysis, independent recount, exploratory script and its blind re-derivation, the pre-registrations with their timestamps, the raw per-replay outputs, and the harness, vLLM and model versions each run recorded.
```

- Saves: **8** words
- Risk: none
- Note: Also drops "three", which is already stale (prereg 02 to 05 are frozen). Add the repository URL here (problem 9).

### 19. [APPLIED] Section Abstract (sentence 3)

Current, exact text with the file's line breaks:

```text
We pause real runs at 407 points (205 runs, 77 tasks) right after the agent opens a file, put the graph's neighbor list for a
function in that file in front of the model, and replay one step through the official harness in ten versions,
12,210 replays, with decision rules fixed in advance.
```

Replace with:

```text
We pause 205 real runs (77 tasks) at 407 points right after the agent opens a file, show the model the graph's neighbor list for a function in that file, and replay one step through the official harness in ten versions (12,210 replays, decision rules fixed in advance).
```

- Saves: **5** words
- Risk: none

### 20. [APPLIED] Section Abstract (exploratory sentence)

Current, exact text with the file's line breaks:

```text
Exploratory analysis says where the gain comes from:
```

Replace with:

```text
Exploratory analysis locates the gain:
```

- Saves: **3** words
- Risk: none

### 21. [APPLIED] Section 5 (any-means paragraph)

Current, exact text with the file's line breaks:

```text
"The agent ignores the
names" holds only for the registered entity-level outcome.
```

Replace with: delete.

- Saves: **12** words
- Risk: none
- Note: Slight loss: the explicit link back to Experiment A's failed following hypothesis. The bold lead carries the point.

### 22. [APPLIED] Section 4 (B2 bullet)

Current, exact text with the file's line breaks:

```text
B2: the swapped-out entry was touched in 0.34% of D replays, under the 5% floor; the decoy in 4 of 1,164 D′
  replays.
```

Replace with:

```text
B2: the swapped-out entry and the decoy were each touched in 4 of 1,164 replays (D and D′; 0.34%, under the 5% floor).
```

- Saves: **0** words
- Risk: none
- Note: Same facts (0.34% of 1,164 is 4); shows the two counts are equal, which the old wording hides.

## Tier 2: loses a minor number, or removes one copy of a repeated fact

### 23. [APPLIED] Section 5 (attention paragraph)

Current, exact text with the file's line breaks:

```text
(E − H +0.21 [−1.00, 1.53]; 9.9%, 11.4% and 10.3% under a stricter whole-word match)
```

Replace with:

```text
(E − H +0.21 [−1.00, 1.53]; the same pattern under a whole-word match)
```

- Saves: **2** words
- Risk: loses a number (the three whole-word rates; they stay in explore_b.txt)

### 24. [APPLIED] Section 5 (cross-session checks)

Current, exact text with the file's line breaks:

```text
E's
prompt is about 630 tokens longer than H's (means 8,224 and 7,594).
```

Replace with:

```text
E's prompt is about 630 tokens longer than H's.
```

- Saves: **4** words
- Risk: loses a number (the two means)

### 25. [NOT APPLIED (superseded by 38)] Section 2 (bullet 1)

Current, exact text with the file's line breaks:

```text
Of 135 `search_similar_code`
  calls, 114 return nothing.
```

Replace with: delete.

- Saves: **7** words
- Risk: loses a number (why non-empty answers are rare)

### 26. [NOT APPLIED (superseded by 38, which keeps the two-hop range)] Section 2 (bullet 3)

Current, exact text with the file's line breaks:

```text
(15% to 19% at two hops, with and
  without the tool's 50-neighbor cap)
```

Replace with: delete.

- Saves: **13** words
- Risk: loses a number (two-hop reach). The one-hop 10% stays.

### 27. [NOT APPLIED (removes a caveat from Section 8)] Section 8

Current, exact text with the file's line breaks:

```text
we do not show that reaching a neighbor resolves more tasks, and one hop reaches new fix
code in a tenth of tasks.
```

Replace with:

```text
we do not show that reaching a neighbor resolves more tasks.
```

- Saves: **12** words
- Risk: none if Section 2's bullet 3 stays (it holds the same 10%); loses a caveat if both 26 and a cut of bullet 3 are taken
- Note: Section 2 already gives the one-hop 10%. Take only if Section 2 keeps it.

### 35. [APPLIED] Section 3.1

Current, exact text with the file's line breaks:

```text
The rules were fixed in
`analysis/fork_states.py` before any replay and give 407 states from 205 runs and 77 tasks (two repositories
supply all but one state).
```

Replace with:

```text
The rules were fixed in `analysis/fork_states.py` before any replay and give the 407 states (two repositories supply all but one).
```

- Saves: **6** words
- Risk: none; 205 runs and 77 tasks stay in the abstract

### 36. [APPLIED] Section 4 (independent recount)

Current, exact text with the file's line breaks:

```text
E against A is a factor of 2.6 to 3.8 depending on the
reading.
```

Replace with: delete.

- Saves: **14** words
- Risk: loses a number (the E/A ratio range; Section 6 keeps the E/H "triples")

### 37. [APPLIED] Section 4 (robustness)

Current (piece 1 of 2), exact text with the file's line breaks:

```text
positive in each seed (+4.6 to +7.0), at each cut
```

Replace with (piece 1 of 2):

```text
positive in each seed, at each cut
```

Current (piece 2 of 2), exact text with the file's line breaks:

```text
with any single task left out (+4.6 to
+5.9).
```

Replace with (piece 2 of 2):

```text
with any single task left out.
```

- Saves: **6** words
- Risk: loses a number (the per-seed and leave-one-task-out ranges; the stronger checks, task-clustered intervals, McNemar and the top-five drop, stay)

### 38. [APPLIED] Section 2 (whole section as one paragraph)

Current, exact text with the file's line breaks:

```text
GraphLoc published 636 traces (3 runs, 106 tasks, two agents) made with the competition harness and model. From
the base agent's 318 traces, with our own scripts:

- The agent calls a graph tool in 109 runs and gets a non-empty answer in 26. Of 135 `search_similar_code`
  calls, 114 return nothing. `get_code_neighbors` is called 8 times; `get_code_subgraph` never.
- After a non-empty answer, the next read or edit lands on a returned node 27% of the time; random nodes from the
  same files score 23%. Traces cannot tell steering from the agent's own direction. Forks can.
- The graph holds every function or class the fix edits in 84% of tasks, but one hop from a function the issue
  names reaches fix code the issue does not already name in 10% of tasks (15% to 19% at two hops, with and
  without the tool's 50-neighbor cap).
- Compaction fires in 68% of runs, so replays must start before it.
```

Replace with:

```text
In the 318 base-agent traces GraphLoc published (3 runs of 106 tasks, competition harness and model), by our count, the agent calls a graph tool in 109 runs and gets a non-empty answer in 26; `get_code_neighbors` is called 8 times, `get_code_subgraph` never. After a non-empty answer the next read or edit lands on a returned node 27% of the time, against 23% for random nodes from the same files: traces cannot tell steering from the agent's own direction, forks can. The graph holds every function or class the fix edits in 84% of tasks, but one hop from a function the issue names reaches fix code the issue does not already name in 10% (15% to 19% at two hops).
```

- Saves: **39** words
- Risk: loses a number (636 traces in all, the 114 of 135 empty `search_similar_code` calls, the cap detail); compaction's 68% moves to 3.1 via the second half of edit 9
- Note: Alternative to edits 8, 25, 26 and the first half of 9 (take the second half of 9 with it). Do not add both.

### 39. [NOT APPLIED (still the only pointer to the split until Experiment C's paragraph lands)] Section 8

Current, exact text with the file's line breaks:

```text
(the registered follow-up splits them)
```

Replace with: delete.

- Saves: **5** words
- Risk: none once Experiment C's paragraph lands (it reports the split); until then it is the only pointer to it
- Note: Take together with the Experiment C paragraph.

## Tier 3: structural, depends on what the figures carry

### 28. [APPLIED] Section 1 (para 2)

Current, exact text with the file's line breaks:

```text
We separate these at one step. We pause real runs right after the agent opens a file, show the model the graph
neighbors of a function in that file, and score its next call against the rate at which it would have gone to the
same code anyway. We vary three things on the same states: the channel (tool result or harness note), the force
(information or instruction), and the encoding (bare names, or names with file, line range and first line). Two
controls say whether the edges themselves matter: one true neighbor swapped for a plausible false one, and a
whole list drawn from a degree-preserving rewiring of the graph.
```

Replace with:

```text
We separate these at one step, scoring the agent's next call against the rate at which it would have gone to the same code anyway (Figure 1). On the same paused states we vary the channel (tool result or harness note), the force (information or instruction) and the encoding (bare names, or with file, line range and first line). Two controls test the edges themselves: one true neighbor swapped for a plausible false one, and a list from a degree-preserving rewiring of the graph.
```

- Saves: **27** words
- Risk: none if Figure 1 shows the pause-and-replay schematic; the abstract and 3.1 to 3.3 hold the rest

### 29a. [NOT APPLIED (29b chosen)] Section 3.2 (arms table, keep the table)

Current, exact text with the file's line breaks:

```text
Every arm seeds the same history. Only the last piece differs.

| Arm | Last piece |
|---|---|
| A | the run's own tool result; nothing added |
| P, P′ | an inserted `get_code_neighbors(node)` call and its result in the tool's JSON; P′ swaps one true neighbor for a decoy |
| H, H′ | the same text as a user-role harness note: "Code graph note from the harness. get_code_neighbors(node=...) returned:" then the list; H′ uses the decoy list |
| D, D′ | "Instruction from the harness. Before you edit anything, look at the code graph neighbors of ... below and read the ones you have not opened yet." then the list; D′ uses the decoy list |
| E | H's wording, each neighbor as an object: name, file, line range, first line of its definition; true list only |
| R_D, R_E | D's instruction and E's note with a rewired list |
```

Replace with:

```text
Every arm seeds the same history; only the last piece differs.

| Arm | Last piece |
|---|---|
| A | nothing added |
| P, P′ | an inserted `get_code_neighbors(node)` call and its JSON result |
| H, H′ | the same list as a user-role note: "Code graph note from the harness. get_code_neighbors(node=...) returned:" |
| D, D′ | "Instruction from the harness. Before you edit anything, look at the code graph neighbors of ... below and read the ones you have not opened yet." then the list |
| E | H's note, each neighbor as name, file, line range and first line of its definition |
| R_D, R_E | D's and E's text on a rewired list |

Primed arms (P′, H′, D′) swap one true neighbor for a decoy.
```

- Saves: **23** words
- Risk: none; both verbatim prompt strings stay
- Note: Pick 29a or 29b, not both.

### 29b. [APPLIED, MODIFIED (both prompt strings kept verbatim in the prose, since Figure 1 does not print them; Figure 1 and caption added)] Section 3.2 (arms table, figure carries it)

Current, exact text with the file's line breaks:

```text
Every arm seeds the same history. Only the last piece differs.

| Arm | Last piece |
|---|---|
| A | the run's own tool result; nothing added |
| P, P′ | an inserted `get_code_neighbors(node)` call and its result in the tool's JSON; P′ swaps one true neighbor for a decoy |
| H, H′ | the same text as a user-role harness note: "Code graph note from the harness. get_code_neighbors(node=...) returned:" then the list; H′ uses the decoy list |
| D, D′ | "Instruction from the harness. Before you edit anything, look at the code graph neighbors of ... below and read the ones you have not opened yet." then the list; D′ uses the decoy list |
| E | H's wording, each neighbor as an object: name, file, line range, first line of its definition; true list only |
| R_D, R_E | D's instruction and E's note with a rewired list |
```

Replace with:

```text
Every arm seeds the same history; only the last piece differs (Figure 1 gives each verbatim). A adds nothing. P inserts a `get_code_neighbors(node)` call and its JSON result; H gives the same list as a user-role harness note; D prefixes it with an instruction to read the neighbors not yet opened; E is H with each neighbor as name, file, line range and first line of its definition. P′, H′ and D′ swap one true neighbor for a decoy; R_D and R_E use D's and E's text on a rewired list.
```

- Saves: **67** words
- Risk: verifiability: the exact prompt wording leaves the text and lives only in Figure 1 and the repo
- Note: Pick 29a or 29b, not both. Only if Figure 1 prints both prompt strings in full.

### 30a. [NOT APPLIED (results table kept as is)] Section 4 (results table, keep the table)

Current, exact text with the file's line breaks:

```text
| Arm | any true neighbor | any rewired entry |
|---|---|---|
| A, nothing | 2.15% [0.86, 3.61] | 0 |
| P, tool result | 3.01% [1.55, 4.64] | |
| H, note, names | 2.75% [1.37, 4.30] | |
| D, instruction, names | 4.30% [2.58, 6.10] | |
| E, note, names + file + lines + first line | 8.25% [5.76, 10.91] | |
| R_D, instruction, rewired | 2.32% [1.03, 3.78] | 0.52% [0.00, 1.29] |
| R_E, note with locations, rewired | 2.41% [1.12, 3.87] | 1.03% [0.34, 1.89] |
```

Replace with:

```text
| Arm | any true neighbor (any rewired entry) |
|---|---|
| A, nothing | 2.15% [0.86, 3.61] (0) |
| P, tool result | 3.01% [1.55, 4.64] |
| H, note, names | 2.75% [1.37, 4.30] |
| D, instruction, names | 4.30% [2.58, 6.10] |
| E, note with locations | 8.25% [5.76, 10.91] |
| R_D, instruction, rewired | 2.32% [1.03, 3.78] (0.52% [0.00, 1.29]) |
| R_E, note with locations, rewired | 2.41% [1.12, 3.87] (1.03% [0.34, 1.89]) |
```

- Saves: **14** words
- Risk: none; every number stays
- Note: Pick 30a or 30b. Most of the saving is empty-cell pipes, which wc -w counts as words. E's label must then be defined once in 3.2 as "note with locations" (29a/29b already describe it).

### 30b. [NOT APPLIED (results table kept as is)] Section 4 (results table, figure carries it)

Current, exact text with the file's line breaks:

```text
Experiment B.** Share of replays whose next call touches a listed entry:

| Arm | any true neighbor | any rewired entry |
|---|---|---|
| A, nothing | 2.15% [0.86, 3.61] | 0 |
| P, tool result | 3.01% [1.55, 4.64] | |
| H, note, names | 2.75% [1.37, 4.30] | |
| D, instruction, names | 4.30% [2.58, 6.10] | |
| E, note, names + file + lines + first line | 8.25% [5.76, 10.91] | |
| R_D, instruction, rewired | 2.32% [1.03, 3.78] | 0.52% [0.00, 1.29] |
| R_E, note with locations, rewired | 2.41% [1.12, 3.87] | 1.03% [0.34, 1.89] |
```

Replace with:

```text
Experiment B.** Figure 2 gives each arm's share of replays whose next call touches a listed entry, with intervals: A 2.15%, P 3.01%, H 2.75%, D 4.30%, E 8.25%; rewired entries 0.52% under R_D and 1.03% under R_E.
```

- Saves: **71** words
- Risk: loses numbers from the text: every per-arm interval, and the true-neighbor rates of R_D and R_E (2.32%, 2.41%) move to the figure only
- Note: Pick 30a or 30b. Only if Figure 2 prints the numbers and intervals as text, since judges and the word counter will read the writeup, and the R_D/R_E true-neighbor rates are the drift baselines Section 5 uses.

## Tier 4: changes a claim's strength or removes content

### 31a. [APPLIED, MODIFIED (author's wording kept; only the trust clause removed, "less than half" became "less than a third", and a sentence on what B2 does show added)] Section 6 (para 1, rewrite)

Current, exact text with the file's line breaks:

```text
For this agent, at the step where it decides where to look, the graph's failure is not a failure to attend and
not mainly a failure to trust. The tool prints names; a name gets the agent to a file, which it then reads from
line 1 under a 150-line cap. Printing the file, line range and first line with each neighbor triples the rate at
which the next call reaches graph-adjacent code, at about 630 prompt tokens. An instruction without locations
buys less than half of that and depends on how shell searches are scored.
```

Replace with:

```text
At the step where this agent decides where to look, the graph's output fails on addressability, not attention: a name gets the agent to a file, which it reads from line 1 under a 150-line cap. Printing each neighbor's file, line range and first line triples the rate at which the next call reaches graph-adjacent code, for about 630 prompt tokens; an instruction without locations adds less than a third as much, and only under one scoring of shell searches.
```

- Saves: **16** words
- Risk: changes a claim's strength: drops "not mainly a failure to trust", which B2 (underpowered) and the null Experiment A discrimination test cannot support; "less than half" becomes the exact "less than a third" (+1.55 against +5.50)
- Note: Pick 31a or 31b.

### 32. [APPLIED, MODIFIED ("our audit of the graph against the gold patches (Section 2) finds only 1 of the 56 async functions that the fixes edit")] Section 6 (para 2)

Current, exact text with the file's line breaks:

```text
For the organizers this is a cheap change to `get_code_neighbors`: return locations, and order neighbors by
something better than the alphabet, since the first entry draws over a third of the follows. Two cautions come with it.
The agent also reads rewired locations at a low rate, and under the legible encoding the swapped-out true entry
is followed in 1.8% of replays, enough for the first time to test whether a false edge is followed as readily.
That experiment is pre-registered (`prereg/04`) and not yet run. Until it is, more legible graph output also
makes the graph's errors more actionable; in our audit the graph holds 1 of 56 async functions.
```

Replace with:

```text
For the organizers this is a cheap change to `get_code_neighbors`: return locations, and consider an order better than the alphabet (Section 5). One caution comes with it: more legible output also makes the graph's errors more actionable. The agent reads rewired locations at a low rate, and in our audit the graph holds only 1 of the 56 async functions that gold patches edit.
```

- Saves: **47** words
- Risk: loses a number (1.8%, the swapped-out entry under E; it belongs in tomorrow's Experiment C paragraph, which also replaces the "not yet run" sentence); weakens the ordering advice (see problem 3); corrects the async claim (problem 2)

### 33. [NOT APPLIED] Section 7

Current, exact text with the file's line breaks:

```text
other work compares which repository views are exposed (2611.07286) and tool architectures
(2608.11386);
```

Replace with: delete.

- Saves: **13** words
- Risk: removes two citations (neither is one of the corrected statements); weakens the claim that the format question is already known only slightly, since RepoNav, LocAgent and the same-track entry carry it

### 34. [NOT APPLIED] Section 4 (failed earlier run)

Current, exact text with the file's line breaks:

```text
An earlier run re-sent the agent's past thoughts,
failed the fidelity gate (6.1%) and is reported only in the log.
```

Replace with: delete.

- Saves: **20** words
- Risk: loses a caveat (disclosure of an excluded run). Not recommended; listed only so the lead can see the cost.

### 31b. [NOT APPLIED] Section 6 (para 1, delete)

Current, exact text with the file's line breaks:

```text
For this agent, at the step where it decides where to look, the graph's failure is not a failure to attend and
not mainly a failure to trust. The tool prints names; a name gets the agent to a file, which it then reads from
line 1 under a 150-line cap. Printing the file, line range and first line with each neighbor triples the rate at
which the next call reaches graph-adjacent code, at about 630 prompt tokens. An instruction without locations
buys less than half of that and depends on how shell searches are scored.
```

Replace with: delete.

- Saves: **96** words
- Risk: loses the conclusion paragraph; its content survives in the abstract (rates, mechanism), Section 4 (B1 scorer-dependent) and Section 5 (630 tokens, the 150-line reads). Section 6 then opens on the organizers' paragraph
- Note: Pick 31a or 31b. Not recommended unless the new results paragraphs run long: judges read the abstract, then the meaning section.
## Problems found on a judge's read (separate from the cuts)

Ordered by how much a graph-ML judge would care. The first three should be fixed before anyone outside the team reads the draft.

1. **The abstract states the edge control without its caveat.** "A degree-preserving rewired list in the same two formats is followed 0.5% and 1.0% of the time" sits next to 4.3% and 8.3%, so a reader takes the true-minus-rewired gap as 4 to 7 points. Section 5 shows the sets are not like-for-like: with true entries filtered the same way, the gap is +1.46 [0.00, 3.01] under E and +0.34 [−0.60, 1.29] under D. For graph-ML judges this is the question that matters most (do the edges matter?), and the abstract answers it more strongly than the data does. Suggested replacement (about +16 words): "A degree-preserving rewired list in the same two formats is followed 0.5% and 1.0% of the time, but against true entries filtered the same way the gap is at most 1.5 points, with intervals touching zero." The title's "true, false and rewired edges" makes the same promise; it is fine only if Experiment C's false-edge result supports it.

2. **"in our audit the graph holds 1 of 56 async functions" (Section 6) misstates the audit.** The pointer audit in NOTES.md says the graph holds 1 of the 56 async *gold units*, the async functions that gold patches edit (55 of the 57 missing gold units are async, all in fastapi and httpx). As written it reads as a claim about every async function, and the paper never says what the audit is. Edit 32 corrects the wording. Better still, add one clause next to Section 2's 84%: the tasks the graph misses are fastapi's async code. That is a concrete graph-construction finding the organizers will want.

3. **The list-position result is confounded with list length, and the advice to reorder rests on it.** In `analysis/results/explore_b.txt` (rank table), arm A, which shows no list, has the same downward gradient per entry: 1.16%, 1.73%, 0.33% and 0.00% at ranks 1, 2 to 3, 4 to 7 and 8+. Entries at rank 8+ exist only in long lists, which have low base rates. E minus A by rank is still decreasing (+4.1, +1.7, +1.0, +0.4 points), so the claim probably survives, but the text should report it against A, or within list length. Section 6's "the first entry draws over a third of the follows" is supported (rank 1 is the lowest touched rank in 36 of 96 E hits) but never shown in Section 5; either show it there or drop it (edit 32 drops it).

4. **"not mainly a failure to trust" (Section 6) is not supported.** B2 is underpowered by its own rule, Experiment A's discrimination test was never run, and the abstract itself says following was too rare to tell whether the agent checks edges. Edit 31a removes the phrase. The same paragraph says the instruction "buys less than half" of E's gain; it is less than a third (+1.55 against +5.50).

5. **Abstract: "The list as the tool prints it, bare names, gives 2.8%."** 2.8% is arm H, the harness note. The tool-result arm P gives 3.0%. A reader who goes to the table finds the wrong row. Fix: "Bare names in a harness note give 2.8% (3.0% as a tool result)." "In the same two formats" then refers to D and E, which differ in force as well as format; "under D and E" is clearer.

6. **The cross-session check covers two sessions, not three.** Section 5 says true entries an arm does not show "are touched at the same rate in all three sessions", but both numbers compare session 3 (R_D, R_E) with session 1 (A). Session 2 (D, D′, E) has no check. Either add one (D′ hides the swapped-out entry, so its rate under D′ against A is a session-2 check) or say "in sessions 1 and 3". The draft also never says which arms ran in which session, which Sections 5 and 8 rely on. One clause in Section 4 fixes it: "A, P, P′, H, H′; then D, D′, E; then R_D, R_E" (about +8 words).

7. **Experiment A's paragraph is hard to check.** "+0.8 points" does not say which contrast it is (P and H pooled against A, or each against A). The two denominators differ (2,442 = 407 x 6 for the decoy; 2,358 = 393 x 6 for the swapped-out entry), and "(complete states)" attaches only to the second. Similarly, "all 46,560 (replay, entry-class) cells" in the recount is 11,640 complete-state replays x 4 entry classes, not all 12,210 replays; "all" invites the question.

8. **The rewired control is partly not rewired.** 847 entries in 298 of 407 states are padding from the node's directory: same-directory non-neighbors, much like the decoy, not rewired edges. Report what share of the R_D and R_E lists, and of R_E's 12 hits, is padding. Otherwise "a degree-preserving rewired list" overstates what the control is, and a graph-ML judge will ask.

9. **Missing references and text that goes stale tomorrow.**
   - GraphAudit is credited for the rewiring control but never cited. GraphLoc has no link.
   - The Reproducibility section has no repository URL.
   - "the three pre-registrations" is already wrong (02 to 05 are frozen); edit 18 drops the count.
   - These go stale when Experiments C and D land: the abstract's last sentence; Section 6's "pre-registered (`prereg/04`) and not yet run" (edit 32 removes it); Section 8's "One model" and "(the registered follow-up splits them)" (edit 39).
   - The new runs are on a single A100 (tensor-parallel size 1), not four L4s. Sections 3.3 and 4 need one platform sentence. Pre-registrations 04 and 05 already restrict contrasts to arms of the same run; say so in the text.

10. **Terminology.** Section 8 says E adds "a signature"; everywhere else it is "the first line of its definition". "Fidelity compares prompt sizes, not tokens" is unclear, since the sizes are token counts; "compares prompt sizes, not their token-by-token content" says what is meant.
