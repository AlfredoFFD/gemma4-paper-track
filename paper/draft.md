# Names get Gemma to the file, line ranges get it to the code: paused-run replays of the code graph with true, false and rewired edges

DRAFT, Nov 9 night, built around experiment B (the earlier null-result draft is in git history). Budget 3,000 words.
Pre-registered numbers come from the frozen `analysis/analyze_b.py` on the pooled runs v5 + v6 + v8; the
independent recount is `analysis/recount_b_outcomes.py`; everything in Section 5 comes from
`analysis/results/explore_b.txt` and is EXPLORATORY. Trace numbers: `analysis/trace_stats.py`. Sections 4 and 5 were re-derived blind by `analysis/rederive_s5.py` (comparison: `analysis/results/rederive_s5_vs_draft.md`). Harness packages
as installed (run logs of v5 and v8, variant v28): adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7.

## Abstract

The competition's code graph barely changes what its Gemma-4-31B agent resolves. We ask why, from inside the
agent. We pause real runs at 407 points (205 runs, 77 tasks) right after the agent opens a file, put the graph's neighbor list for a
function in that file in front of the model, and replay one step through the official harness in ten versions,
12,210 replays, with decision rules fixed in advance. With nothing added, the next call reaches a listed neighbor
in an unopened file in 2.2% of replays. The list as the tool prints it, bare names, gives 2.8%. An instruction to
read the neighbors gives 4.3%. The same neighbors printed with file, line range and first line of definition give
8.3% (+5.5 points over bare names, 95% interval 3.4 to 7.7). A degree-preserving rewired list in the same two
formats is followed 0.5% and 1.0% of the time. Exploratory analysis says where the gain comes from: bare names
already send the agent to the listed files, but it opens them from the top and misses the entity; with line
ranges, 70% of opened files are read at the listed code, against 37% to 49%. The graph's content is used once it
is addressable. A planted false neighbor was almost never followed, but following was too rare under bare names
to say the agent checks edges.

## 1. The question

The competition ships a precomputed code graph of each repository and three tools to query it. The most careful
public entry so far, GraphLoc, found that adding the graph tools moves the resolve rate by about one task in a
hundred (28.9% to 29.9%, interval −4.1 to +6.3 points). An end-to-end score cannot say why. The agent may never
ask the graph; it may ask and ignore the answer; it may be unable to act on the answer as printed; or it may
follow the answer to the wrong place.

We separate these at one step. We pause real runs right after the agent opens a file, show the model the graph
neighbors of a function in that file, and score its next call against the rate at which it would have gone to the
same code anyway. We vary three things on the same states: the channel (tool result or harness note), the force
(information or instruction), and the encoding (bare names, or names with file, line range and first line). Two
controls say whether the edges themselves matter: one true neighbor swapped for a plausible false one, and a
whole list drawn from a degree-preserving rewiring of the graph.

## 2. What the public traces already show

GraphLoc published 636 traces (3 runs, 106 tasks, two agents) made with the competition harness and model. From
the base agent's 318 traces, with our own scripts:

- The agent calls a graph tool in 109 runs and gets a non-empty answer in 26. Of 135 `search_similar_code`
  calls, 114 return nothing. `get_code_neighbors` is called 8 times; `get_code_subgraph` never.
- After a non-empty answer, the next read or edit lands on a returned node 27% of the time; random nodes from the
  same files score 23%. Traces cannot tell steering from the agent's own direction. Forks can.
- The graph contains a fix location in 84% of tasks, but one hop from a function the issue names reaches fix code
  the issue does not already name in 10% of tasks (19% at two hops).
- Compaction fires in 68% of runs, so replays must start before it.

## 3. Method

### 3.1 States

A state is the message history of one real run, cut right after the first, second or third tool result that shows
file content, before any edit and before compaction, with a logged prompt of at most 12,500 tokens. The queried
node is a function or class the agent has already seen, with 2 to 50 graph neighbors. The rules were fixed in
`analysis/fork_states.py` before any replay and give 407 states from 205 runs and 77 tasks (two repositories
supply all but one state).

### 3.2 Arms

Every arm seeds the same history. Only the last piece differs.

| Arm | Last piece |
|---|---|
| A | the run's own tool result; nothing added |
| P, P′ | an inserted `get_code_neighbors(node)` call and its result in the tool's JSON; P′ swaps one true neighbor for a decoy |
| H, H′ | the same text as a user-role harness note: "Code graph note from the harness. get_code_neighbors(node=...) returned:" then the list; H′ uses the decoy list |
| D, D′ | "Instruction from the harness. Before you edit anything, look at the code graph neighbors of ... below and read the ones you have not opened yet." then the list; D′ uses the decoy list |
| E | H's wording, each neighbor as an object: name, file, line range, first line of its definition; true list only |
| R_D, R_E | D's instruction and E's note with a rewired list |

The swapped-out neighbor and the decoy both live in unopened files and neither name has appeared in the prompt.
The decoy is a real non-neighbor function from the same directory, not a fix location and not a test. The rewired
list comes from seeded double-edge swaps (ten per edge), which keep every node's degree; its entries are in
unopened files, with unseen names and outside fix-location files (the scored true entries need only an unopened
file; Section 5), and padded from
the node's directory where the rewired neighborhood is short (847 padded entries in 298 states).

### 3.3 Replay

The history is loaded into the harness's own compiled agent as a session, event by event, and the arm's last
piece is delivered as the new message. The agent makes one model call and stops; no tool executes. Each (state,
arm) runs with seeds 1 to 3. Fidelity is checked on 24 states by comparing arm A's prompt size with the size
logged at the same step of the original run.

### 3.4 Outcomes and pre-registered rules

The outcome is the model's first function call. A listed node is touched when that call reads its file over a
line range that overlaps the node (within the harness's caps of 150 lines and 10,000 characters per read), edits
the file, or views it with a shell command that shows those lines or names the node. Only entries in unopened
files are scored. Malformed calls are interface failures and never count. Intervals are 95% bootstrap intervals
clustered by state.

Experiment A (`prereg/02`): following, P and H against A; discrimination, the swapped-out entry against the
decoy; channel, P against H. Experiment B (`prereg/03`, frozen before its runs):

- B1, force: D − H, lower bound above zero.
- B2, discrimination under force: swapped-out under D minus decoy under D′; informative only if the swapped-out
  entry is touched in at least 5% of D replays.
- B3, encoding: E − H, two-sided.
- B4, structure: in at least one format, the true list beats the rewired list by 3 points or more with an
  interval excluding zero.

## 4. Results

Three sessions on four L4 GPUs produced 12,210 replays: five arms in 4.1 hours, three in 3.0, two in 2.3. There
were 34 interface failures (24 malformed calls, 10 with no call; between 0 and 7 per arm), counted apart. 388
states are complete in all ten arms, 1,164 replays per arm. An earlier run re-sent the agent's past thoughts,
failed the fidelity gate (6.1%) and is reported only in the log.

**Fidelity.** Arm A's prompt differs from the logged prompt by 1.7% (median; mean 3.0%; two states at 9.5% and
25%).

**Experiment A.** With five arms alone, the list moved following by +0.8 points [−0.1, 1.7], so the following
hypothesis failed and discrimination was not tested: the decoy was followed 0 times in 2,442 replays, the
swapped-out true entry 6 times in 2,358 (complete states). Channel made no difference (+0.25 [−0.7, 1.2]). The tool result did
make the agent call the graph again (3.2% of next calls, against 0.3% in A).

**Experiment B.** Share of replays whose next call touches a listed entry:

| Arm | any true neighbor | any rewired entry |
|---|---|---|
| A, nothing | 2.15% [0.86, 3.61] | 0 |
| P, tool result | 3.01% [1.55, 4.64] | |
| H, note, names | 2.75% [1.37, 4.30] | |
| D, instruction, names | 4.30% [2.58, 6.10] | |
| E, note, names + file + lines + first line | 8.25% [5.76, 10.91] | |
| R_D, instruction, rewired | 2.32% [1.03, 3.78] | 0.52% [0.00, 1.29] |
| R_E, note with locations, rewired | 2.41% [1.12, 3.87] | 1.03% [0.34, 1.89] |

- B1: D − H = +1.55 [0.60, 2.66]. Confirmed.
- B2: the swapped-out entry was touched in 0.34% of D replays, under the 5% floor; the decoy in 4 of 1,164 D′
  replays. Underpowered, as pre-registered.
- B3: E − H = +5.50 [3.44, 7.65]. Confirmed.
- B4: D − R_D = +3.78 [2.15, 5.67]; E − R_E = +7.22 [4.64, 9.97]. "Structure matters" by the registered rule;
  Section 5 qualifies it.

**Independent recount.** A second script, written without the first, rescored all 46,560 (replay, entry-class)
cells from the raw replay logs. Under the reading of the grep rule closest to the registered text it differs in
28 cells, all shell searches, and every decision stands (B1 +1.55 [0.43, 2.75], B3 +5.33 [3.35, 7.30], B4 +4.04
and +7.22). Under a wider reading that also credits recursive searches over a directory that contains an entry's file, base rates rise (A 3.5%,
E 9.1%), B3 and B4 stand (+4.73 [2.75, 6.70]; +4.47, +7.90) and B1 does not (+0.77 [−0.52, 2.06]). We therefore
rest the paper on B3 and B4 and call B1 scorer-dependent. E against A is a factor of 2.6 to 3.8 depending on the
reading.

**Clustering and concentration.** Clustered by task instead of state, E − H is +5.50 [2.16, 9.15] and E − R_E
+7.22 [2.97, 12.07]. By McNemar's test on states (any of three seeds), E reaches a listed neighbor in 41 states
and H in 14 (29 against 2 discordant, p = 5e-7). E − H is positive in each seed (+4.6 to +7.0), at each cut
point, in each repository (+3.1 without one, +7.7 without the other) and with any single task left out (+4.6 to
+5.9). Hits are concentrated: without the five tasks with the most E hits, E − H is between +2.4 and +2.7, depending on how a tie for fifth place is broken (+2.37 [0.85, 4.07] at the low end).

## 5. What the encoding changes (exploratory)

Nothing in this section was pre-registered.

**Bare names already move the agent to the files.** Count a listed entry as followed by any means: its file
opened or viewed at any lines, or its name or path used in a shell command or graph call. Then A is 5.2%, H 9.9%,
D 12.9% and E 12.4%; H − A is +4.64 [2.66, 6.79], and E − D is −0.52 [−2.58, 1.46]. "The agent ignores the
names" holds only for the registered entity-level outcome.

**The encoding changes where in the file the read lands.** Given that the agent opens a listed entry's file, the
read covers the entity 37% to 49% of the time in every arm except E, where it is 70% [56, 82]. In A, H and D
all but three of 107 hits are a `read_file` from the top of the file, so an entity is reached only if it sits in the first 150
lines. In E, 34 of 96 hits read exactly a listed line range and 13 more start at a listed first line.

**The model notices the names equally.** A fresh true neighbor is named in the model's thoughts in 10.8% of H
replays, 12.2% of D and 11.0% of E (E − H +0.21 [−1.00, 1.53]; 9.9%, 11.4% and 10.3% under a stricter whole-word match). The difference between arms is in the action,
not in attention.

**List position matters.** Under E, an entry at rank 1 is touched in 5.2% of replays, ranks 2 to 3 in 3.5%,
ranks 4 to 7 in 1.3%, rank 8 or later in 0.4%. The tool sorts alphabetically.

**The structure effect is smaller on matched entries.** The rewired entries were filtered (unseen names, no
fix-location files); the scored true entries were not all (the pre-registration's text says both sets met one filter; the code applied it to the rewired entries only). Restricting the true entries to the same filter
(3,292 of 3,704), E falls to 2.49% [1.20, 3.87], E − H is still +2.32 [1.12, 3.69], but true minus rewired is
+1.46 [0.00, 3.01] under E (lower bound −0.09 in an independent bootstrap) and +0.34 [−0.60, 1.29] under D. Most of the B4 gap comes from true neighbors in
fix-location files and names already in view, which the agent has its own reasons to visit and the list makes
reachable. What survives matching is small and its interval touches zero: a preference for a legible true edge over a
legible rewired one is not established, and R_E shows that the agent does read rewired locations when given lines
(5 of its 12 hits start at a listed first line).

**Toward the fix.** Counting only `read_file` calls on a not-yet-opened file that holds a fix location, the next
call goes there in 6.0% of A replays, 6.6% of H, 8.8% of D and 8.2% of E (E − A +2.15 [0.60, 3.95]). Counting any
read, edit or shell view of a file the gold patch changes, the rates are 6.9%, 7.2%, 9.4% and 8.5%, and E − A is
+1.63 [−0.26, 3.61]. The direction is toward the fix; the size depends on the definition, and neither reading
separates E from the rewired list (+1.55 [−0.09, 3.35]; +1.03 [−0.69, 2.92]).

**Checks on the cross-session contrasts.** No arm ran in two sessions. True entries that an arm does not show are
touched at the same rate in all three sessions (R_D − A +0.17 [−0.86, 1.29]; R_E − A +0.26 [−0.60, 1.12]). E's
prompt is about 630 tokens longer than H's (means 8,224 and 7,594).

## 6. What it means

For this agent, at the step where it decides where to look, the graph's failure is not a failure to attend and
not mainly a failure to trust. The tool prints names; a name gets the agent to a file, which it then reads from
line 1 under a 150-line cap. Printing the file, line range and first line with each neighbor triples the rate at
which the next call reaches graph-adjacent code, at about 630 prompt tokens. An instruction without locations
buys less than half of that and depends on how shell searches are scored.

For the organizers this is a cheap change to `get_code_neighbors`: return locations, and order neighbors by
something better than the alphabet, since the first entry draws over a third of the follows. Two cautions come with it.
The agent also reads rewired locations at a low rate, and under the legible encoding the swapped-out true entry
is followed in 1.8% of replays, enough for the first time to test whether a false edge is followed as readily.
That experiment is pre-registered (`prereg/04`) and not yet run. Until it is, more legible graph output also
makes the graph's errors more actionable; in our audit the graph holds 1 of 56 async functions.

## 7. Related work

The nearest study measures how small coding agents use code graphs and embeddings in a localization harness; its
graph tool already prints signatures and qualified paths, it varies the tool set rather than the encoding, and it
reports that forcing the graph call does not help and that agents expand once and stop (2610.33958). Our
instruction arms agree from a different design. RepoNav attributes localization gains to how retrieved snippets
are organized (2609.08355); other work compares which repository views are exposed (2611.07286) and tool
architectures (2608.11386); a same-track entry finds that signatures carry the value and bare call edges do not
(Zenodo 10.5281/zenodo.23927441); LocAgent builds graph-guided localization end to end (2503.09089). That tool
output format changes agent behavior is therefore known. On channel and trust: handed-over search content is used
more than fetched content on this model (2609.05587); a harness-inserted tool result is trusted like a real call
(2605.09822); small agents agree with a wrong graph tool (2606.14476); fork designs exist for tool results in
scientific QA (2610.26836) and after compaction (2609.36526, 2610.31710). GraphLoc and GraphAudit ask whether
this graph helps end to end and in retrieval; the rewiring control is GraphAudit's. In what we searched (queries
and dates in `docs/lit/`), no work shows an agent one fixed set of graph edges in two encodings, or a rewired
graph, and scores its next action against a no-list base rate.

## 8. Limitations

One step per replay: we do not show that reaching a neighbor resolves more tasks, and one hop reaches new fix
code in a tenth of tasks. One model, one agent configuration, one harness version (v28: adk_submission 0.2.12, swegemma 0.2.7), two repositories. E is not
information-matched to H: it adds a file path, lines and a signature at once, and we cannot say which carries
the effect (the registered follow-up splits them). E, D and the rewired arms ran in different sessions from H
and A; the indirect drift checks are clean but not a same-session comparison. B1 depends on the scoring of
recursive searches. The registered structure contrast compares unequal entry sets; the matched contrast is
small and its interval touches zero. Hits are concentrated in a minority of states and tasks. The decoy is
plausible, not adversarial. Fidelity compares prompt sizes, not tokens.

## Reproducibility

Code under Apache 2.0: the state exporter, the replay runner, the Kaggle script, the frozen analysis, the
independent recount, the exploratory script and its blind re-derivation, with the three pre-registrations and their timestamps, the raw
per-replay outputs, and the harness, vLLM and model versions recorded by each run. The competition data is not
redistributed; the state bundle is rebuilt from it by the exporter.
