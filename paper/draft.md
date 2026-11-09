# Does Gemma check the code graph? Paused-run replays with true and false edges

DRAFT, Nov 9 morning, with the confirmatory results. Budget 3,000 words. Run numbers come from
`analysis/results/v5/analysis.txt`; trace numbers from `analysis/trace_stats.py`; audit numbers from
`experiments/00-pointer-audit/`.

## Abstract

The competition's code graph barely changes what its Gemma-4-31B agent resolves. We ask why, from inside the agent. We cut 407 real runs (77 tasks, GraphLoc's public traces) right after the agent opens a file, put the graph's neighbor list for a function in that file in front of the model, and replay one step through the official harness, in five versions: nothing added, the list as the result of an inserted tool call, the same text as a harness note, and both again with one true neighbor replaced by a plausible false one. The rebuilt prompts match the logged ones within 1.7% (median). With nothing added, the agent's next read or edit reaches a listed neighbor in an unopened file 2.1% of the time; with the list, 2.8% to 3.3%, a change of 0.8 points [-0.1, 1.7]. The false neighbor was followed 0 times in 2,442 replays, the matched true one 6 times in 2,358. The channel changes behavior around the graph, not where the agent goes: a tool result makes it call the graph again (3.2% versus 0.3%), a note makes it think (median 185 versus 98 output tokens). At the navigation step, Gemma neither follows the graph nor checks it, which is why delivery alone cannot rescue it.

## 1. The question

The competition ships a precomputed code graph of each repository and three tools to query it. The most
careful public entry so far, GraphLoc, found that adding the graph tools moves the resolve rate by about one task
in a hundred (28.9% to 29.9%, interval −4.1 to +6.3 points). That result says the graph does not help much. It
does not say why. An end-to-end score cannot separate three different failures: the agent never asks the graph,
the agent asks and ignores the answer, or the agent follows the answer and the answer points at the wrong place.

We take the question inside the agent. We pause real Gemma-4-31B runs right after they open a file, put the
graph's neighbor list for a function in that file in front of the model, and replay one step. From the replay we
measure two things an end-to-end score cannot: whether the next read or edit follows a listed neighbor above the
rate at which the agent would have gone there anyway, and whether a planted false neighbor is followed as readily
as a true one. The second number is the one that matters for anyone who wants to ship a graph to an agent. An
agent that follows a wrong edge as often as a right one is not checking the graph. It is obeying it, and the
graph's gaps become the agent's errors.

## 2. What the public traces already show

GraphLoc published 636 full traces (3 runs, 106 tasks, two agents) made with the competition harness, the
competition model served with vLLM on four L4 GPUs, temperature 0.2, a thinking budget of 4,096 tokens and 40
tool calls per task. We re-derived the following from the base agent's 318 traces with our own scripts.

- The agent calls a graph tool in 109 of 318 runs and gets a non-empty answer in 26. Of 135 calls to
  `search_similar_code`, 114 return nothing: the prompt tells the agent to search "with keywords from the error
  message", and the tool resolves exact symbol names. `get_code_neighbors` is called 8 times in 318 runs and
  `get_code_subgraph` never.
- After one of the 26 non-empty answers, the agent's next read or edit lands on a returned node 7 times (27%).
  Random nodes drawn from the same files are "touched" 23% of the time by the same next calls, because a read of
  a file touches every node it shows. The traces cannot tell steering from the agent's own direction. Forks can.
- Offline, the graph contains a fix location in 84% of tasks, but one hop from a function the issue names reaches
  fix code the issue does not already name in 10% of tasks (19% at two hops). The graph's upside at this point of
  a run is bounded. A wrong edge's downside is not.
- Compaction (the harness summarizing old history when the prompt passes 14,336 tokens) fires in 68% of the base
  runs, so a replay must come from before it, where the history is still verbatim.

## 3. Method

### 3.1 States

A state is the message history of one real run, cut at a point where the next move is a navigation decision: right
after the first, second or third tool result that shows file content, before the agent has edited any repository
file and before any compaction, with a logged prompt of at most 12,500 tokens at the next call (the inserted
material must fit under the 16,384-token cap). The cut rule, the in-view rule and the node rule were fixed in
`analysis/fork_states.py` before any replay ran. They give 407 states from 241 runs and 77 tasks.

The queried node is a function or class defined inside a file range the agent has already seen, with 2 to 50
neighbors in the graph (the tool's cap). Its neighbor list is exactly what `get_code_neighbors` returns: callers
and callees, deduplicated, sorted alphabetically, self-loops included.

### 3.2 Arms

Every arm seeds the same history. Only the last piece differs.

| Arm | Last piece |
|---|---|
| A | the fork's own tool result; nothing added |
| P | an inserted `get_code_neighbors(node)` call and its real result, in the tool's exact JSON |
| P' | as P, with one true neighbor replaced by a decoy; the list re-sorted as the tool sorts |
| H | the same result text as a harness note (a user-role message with one fixed wording), no call |
| H' | as H, with the P' list |

The two compared entries, the swapped-out true neighbor and the decoy, both live in files the agent has not opened
and neither name has appeared in the prompt or any tool result, so following either one takes a new read and
neither is favored by familiarity. The decoy is a real function from the swapped-out entry's directory (else the
node's directory) that is not a neighbor, not a fix location and not a test. Its list position is logged. This
construction replaced a first version, before any replay, after we found that most true neighbors sit in the file
just opened: re-reading that file would have counted as following the graph.

### 3.3 Replay

The history is loaded into the harness's own compiled agent (the sample prompt, nine tools, no adapters, no
sub-agent) as an ADK session, event by event, with the model's recorded thoughts and tool calls and the recorded
tool results. The arm's last piece is delivered as the new message. The agent makes one model call through vLLM
and stops at the model's response; no tool ever executes. Each (state, arm) runs with three seeds. Fidelity is
checked directly: for 24 states, arm A's prompt size reported by vLLM is compared with the size logged at the
same step of the original run (Section 4).

### 3.4 Outcomes and pre-registered tests

The outcome of a replay is the model's first function call. A listed node is "touched" when that call reads its
file over a line range that overlaps the node (with the harness's caps: 150 lines and 10,000 characters per read,
5,000 characters per shell output), edits that file, or views it with a shell command that shows those lines or
names the node. Calls with malformed arguments are interface failures and never count.

- H1, following: the share of replays whose next call touches any listed true neighbor in an unopened file, in
  arms P and H minus arm A.
- H2, discrimination (primary): D = P(touch of the swapped-out entry | P, H) − P(touch of the decoy | P', H').
  The agent "does not check" if H1 holds and the 90% interval of D lies within ±2 points. It "checks" if the lower
  95% bound of D is above zero and the decoy is followed less than half as often as the swapped-out entry.
- H3, channel (two-sided): P(any true touched | P) − P(any true touched | H).
- H4, descriptive: how often arm A's next call is a graph tool at all.

Intervals are 95% bootstrap intervals clustered by state. The rules, thresholds and exclusions are in
`prereg/02-discrimination-forks.md`, frozen before the run with timestamped clarifications.

## 4. Results

The confirmatory run (v5) replayed all 407 states under five arms and three seeds, 6,105 replays, in 4.1 hours on
four L4 GPUs, with no model errors. 21 replays were interface failures (12 malformed arguments, 9 no call) and
are excluded from rates; 393 states have every arm and seed. A first run (v4) had re-sent the agent's earlier
thoughts and failed the fidelity gate (6.1%); its outcomes, read before the fix, pointed the same way and are
reported only in the log.

**Fidelity.** Across 24 states, arm A's prompt as counted by vLLM differs from the logged prompt at the same
step by 1.7% (median; mean 3.0%). Every replayed prompt is slightly smaller than the original, by about 150
tokens, consistent with small differences in the tool declarations between harness versions; two states differ
by 9.5% and 25% for reasons we could not trace. The arms differ only by their last piece: the note adds 178
tokens to arm A's prompt and the inserted call 181.

**Following (H1).** The next call touches a listed true neighbor in an unopened file in 2.1% of arm A replays
[0.9, 3.7], in 3.1% with the list as a tool result [1.5, 4.8], 3.3% with the decoy list as a tool result, 2.8%
as a note [1.4, 4.5] and 2.9% as a note with the decoy. Pooling the two true-list arms against A gives +0.8
points [-0.1, +1.7]: H1 is not supported. Per listed entry, the touch rate is 0.25% in A and 0.36% to 0.54%
with the list.

**Discrimination (H2).** Under the pre-registered rule, H2 is not tested when H1 fails; we report the quantities.
The swapped-out true entry was followed in 6 of 2,358 replays (0.25%) and the decoy in 0 of 2,442. D = 0.25
points [0.00, 0.76]. In arm A neither was ever touched.

**Channel (H3).** The tool result and the note move following by the same amount: +0.25 points [-0.7, +1.2].

**Natural use (H4).** With nothing added, the next call is a graph tool in 0.34% of replays [0.08, 0.68].

**What the channel does change (secondary, listed in advance).** After the inserted tool call, the next call is a
graph tool in 3.2% of replays [1.8, 4.8] (2.9% with the decoy list), against 0.3% in arm A and 0.6% after the
note; 27 of those 65 calls query a listed entry. The note restarts thinking: thought text appears in 99.6% of
note replays and the median completion is 185 tokens, against 58% and 98 tokens in arm A and 72% and 127 after
the tool result. In that thinking the agent names one of the fresh true entries in 10% of note replays and 5% of
tool-result replays, and the decoy in 2% and 1% (one decoy against two to four true entries per list). Named,
rarely followed: the words move more than the next call.

The next call's shape barely changes: `read_file` in 58% of arm A replays and 50% to 54% with the list, shell
views of files in 29% to 33%, writes and edits in 6% to 8%.

## 5. What it means for the organizers

Of the three readings we pre-registered, the data pick the third: at the moment the agent decides where to look
next, the graph's neighborhood neither steers it nor is checked by it. Pushing the graph into the context, which
other work found decisive for search results on this model, does not work here, and whether the agent asked for
it or was handed it makes no difference to where it goes. GraphLoc's end-to-end null is therefore not a delivery
failure that better prompting would fix at this step; the agent reads the issue, opens the file it names, and
keeps reading or running code regardless of the list.

Two effects do belong to the channel. A tool result makes the agent treat the graph as a thread to pull (one call
in thirty leads to another, usually on a listed entry), and a note makes it stop and think. If the organizers
want the graph used, the lever is the loop, not the text: a graph call that the harness answers early and keeps
answering, rather than a block of names. And because nothing was followed, nothing false was followed either;
the graph's gaps (it holds 1 of 56 async functions in our audit) are not yet the agent's errors, but they would
become so only once following rises, which is exactly when a false-edge test like this one should be run again.

## 6. Related work

Handed-over information is used more than fetched information for Gemma-4-31B on search content (+17 to +19
points) and less on the output of code it ran (2609.05587). Oracle Poisoning compares the same poisoned graph
data as prompt text and as a tool result and finds the channel decides trust, model by model; it also shows that a
tool result inserted by the harness is trusted exactly like a real call, which is what arm P relies on (2605.09822,
Table 7). Agents bring a planted solution into context in most runs and use it in few (2604.17609); decoy files
are the most damaging perturbation in RepoMirage (2605.26177); small agents agree with a graph tool that is wrong
on a third to two thirds of nodes (2606.14476). The nearest fork design pauses GPT-5.2 and varies only whether a
true tool result is inline or one read away, scored on final answers in scientific QA (2610.26836); PAIR and
Compact-Bench fork coding agents after compaction (2609.36526, 2610.31710). GraphLoc and GraphAudit, in this
competition, ask whether the graph helps end to end and in retrieval. None of these shows an agent a true and a
false edge at the same state and scores its next move against the rate it would have gone there anyway.

## 7. Limitations

One step per replay, not a resolved task. One model, one agent configuration, one harness version (recorded).
States come from the first three navigation points of a run; later points, after compaction, are not covered.
The decoy is plausible by construction, not adversarial. Three seeds per state pair the arms only loosely; the
analysis clusters by state. The fidelity check compares prompt sizes, not every token.

## Reproducibility

Code under Apache 2.0: the state exporter, the replay runner, the Kaggle script and the analysis, with the state
bundle, the raw replay outputs and the harness, vLLM and model versions recorded by the run.
