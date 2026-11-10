# Names get Gemma to the file, line ranges get it to the code

**Subtitle:** Pre-registered replays of paused agent runs show why the code graph goes unused, and what makes it used

<!-- DRAFT of Nov 10. Main text: Abstract to Reproducibility, at most 3,000 words (paper/wordcount.py). The host has
said that references do not count and that an appendix is supplementary. Remove this comment before submission. -->

## Abstract

A graph-localization skill barely changes what the competition's Gemma-4-31B agent resolves. We ask why, from inside the agent. We pause 205 real runs at 407 points right after the agent opens a file, show the model the code graph's neighbors of a function in that file, and replay its next step through the official harness: seven pre-registered experiments, about 40,000 replays. Bare names, as `get_code_neighbors` prints them, barely change the next call: 2.8% of replays reach a listed neighbor in an unopened file, against 2.2% with no list. The same neighbors with file and line range are followed three times as often (8.3%; +5.5 points, 95% interval 3.4 to 7.7). The gain holds inside the tool's own result (+6.4), on two other Gemma 4 models (+3.5, +3.1) and under the original harness's rendering (+5.2). The location carries all of it; the definition line adds nothing. A false neighbor written the same way is followed in 1 of 1,200 replays, the true one in 23. Five calls later the lead is +3.9 points [−1.1, 8.8]: the legible list gets the agent to the fix's lines sooner, not detectably more often. We also find that a harness change makes the 31B model mangle an argument name in a third of its ranged reads, which then silently return the top of the file. Both problems are cheap to fix.

## 1. The question

The competition [1] ships a precomputed code graph of each repository and three tools to query it. The closest public entry, GraphLoc [2], found that a graph-localization skill moves the baseline agent's resolve rate from 28.9% to 29.9% (interval −4.1 to +6.3 points). An end-to-end score cannot say why. The agent may never ask the graph, ignore the answer, be unable to act on it as printed, or follow it to the wrong place.

We separate these at one step: we pause real runs, show the model the graph's neighbor list in one of several forms, and score its next call against the rate at which it would have gone to the same code anyway (Figure 1). We vary the channel (tool result or harness note), the force (information or instruction) and the encoding (bare names, or names with file, line range and first line). Two controls test the edges: one true neighbor swapped for a plausible false one, and a list from a degree-preserving rewiring of the graph. We then test the main effect inside the tool's own result, on two other Gemma 4 models, under the original harness's rendering of tool results, and over five calls with tools executing.

## 2. What the public traces already show

In the 318 base-agent traces GraphLoc published (3 runs of 106 tasks), by our count, the agent calls a graph tool in 109 runs and gets a non-empty answer in 26; `get_code_neighbors` is called 8 times, `get_code_subgraph` never. After a non-empty answer the next read or edit lands on a returned node 27% of the time, against 23% for random nodes from the same files: traces cannot tell steering from the agent's own direction, forks can. The graph holds every function or class the fix edits in 84% of tasks, but one hop from a function the issue names reaches fix code the issue does not already name in 10% (15% to 19% at two hops).

## 3. Method

### 3.1 States

A state is the message history of one real run, cut right after the first, second or third tool result that shows file content, before any edit and before compaction, with a logged prompt of at most 12,500 tokens. The queried node is a function or class the agent has already seen, with 2 to 50 graph neighbors. The rules were fixed in code before any replay and give 407 states from 205 runs of 77 tasks.

### 3.2 Arms

Every arm seeds the same history; only the last piece differs (Figure 1).

- **A** adds nothing.
- **P** inserts a `get_code_neighbors(node)` call and its result as the tool prints it: bare names.
- **H** gives the same list as a user-role note from the harness.
- **D** adds an instruction to read the neighbors not yet opened.
- **E** is H with each neighbor as name, file, line range and first line of its definition. **EL** keeps name, file and lines; **ES** keeps name and first line. **PE** puts E's entries inside P's tool result.
- **Controls.** P′, H′, D′ and E′ swap one true neighbor for a decoy: a real function from the same directory that is not a neighbor, a fix location or a test. R_D and R_E carry D's and E's text with a list from a degree-preserving rewiring of the graph.

![](figures/fig_design.png)

**Figure 1.** The method, and the two list formats from one real state.

### 3.3 Replay

The history is loaded into the harness's own compiled agent as a session, and the arm's last piece is delivered as the new message. The agent makes one model call and stops; no tool executes. Each (state, arm) runs with seeds 1 to 3. In the five-call experiment, `read_file` and read-only shell commands execute through the harness's own tool functions on a checkout of the task snapshot, until any other call or the fifth model call.

**Fidelity.** Replays use harness v28, which hands tool results to the model as dictionaries; the original runs' harness handed them over as JSON strings [3]. Rebuilt the original way, the prompt is exactly 2 tokens below the logged size in 24 of 24 states, and the next call names the same tool as the real run in 83% of replays. Rebuilt as v28 renders it, the prompt is 1.7% smaller (median) and agreement is 76%. Every experiment uses v28's form unless stated.

### 3.4 Outcomes and rules

The outcome is the model's first function call. A listed node is touched when that call reads its file over a line range that overlaps the node (within the harness's caps of 150 lines and 10,000 characters per read), edits the file, or views it with a shell command that shows those lines or names the node. Only entries in unopened files are scored. Malformed calls are counted apart as interface failures. In the five-call experiment the outcome is whether the agent is shown a line the gold patch changes. Intervals are 95% bootstrap intervals clustered by state.

Seven pre-registrations (`prereg/02` to `07`) fixed every decision rule by a commit before its run; Table 1 lists each rule with its outcome, met or not. Every registered number was re-derived by a second script written without the first. Runs used hosted L4 GPUs or rented A100s; no contrast mixes runs.

## 4. Results

### 4.1 One step

Ten arms, 12,210 replays; 388 states are complete in all arms (Figure 2a).

**Bare names barely move the next call.** With nothing added, 2.15% of replays reach a listed neighbor. The bare list gives 3.01% as a tool result and 2.75% as a note: +0.8 points pooled [−0.1, 1.7], so the registered following test was not met and discrimination could not be tested. The channel makes no difference (P − H +0.25 [−0.7, 1.2]).

**An instruction helps a little.** D − H is +1.55 [0.60, 2.66], and not under a wider scoring of recursive searches (+0.77 [−0.52, 2.06]).

**A legible list is followed three times as often.** E reaches a listed neighbor in 8.25% of replays: E − H = +5.50 [3.44, 7.65]. E reaches one in 41 states and H in 14 (McNemar p = 5e-7). It holds in each seed, at each cut point, with either repository left out, clustered by task ([2.16, 9.15]) and under an independent recount. Hits are concentrated: without the five tasks with the most E hits it is +2.4 to +2.7.

**A rewired list is not followed.** Its entries are touched in 0.52% (R_D) and 1.03% (R_E) of replays. The registered structure rule is met (E − R_E +7.22 [4.64, 9.97]), with a qualification in Section 5.

![](figures/fig_results.png)

**Figure 2.** (a) Share of replays whose next call reaches a listed neighbor, by arm. (b) Opening a listed neighbor's file against reading its lines.

### 4.2 The same effect in other settings

**Inside the tool's own result.** With E's entries as the result of the `get_code_neighbors` call itself, the next call reaches a listed neighbor in 9.61% of replays against 3.26% for the bare result: PE − P = +6.35 [4.34, 8.52] (Figure 3a). Note and tool result do not differ detectably (PE − E +1.59 [−0.33, 3.43]).

**Other models.** Two other Gemma 4 models continued the same histories. 26B-A4B follows the legible note in 6.88% of replays against 3.36% for bare names (+3.53 [1.51, 5.54]); E4B in 8.20% against 5.14% (+3.06 [1.09, 5.03]).

**Another platform, another rendering.** On a rented GPU the hosted contrast repeats (+5.58 [3.67, 7.58]). With every earlier tool result rendered as the original runs' harness did, it is +5.17 [3.33, 7.17].

![](figures/fig_extensions.png)

**Figure 3.** (a) The legible list against bare names in six settings. (b) Parts of an entry, and a false entry. (c) Reaching the lines the fix changes, call by call.

### 4.3 Which part of an entry, and a false entry

**Location carries the effect.** In one run, the list with name, file and lines (EL) is followed in 7.75% of replays and the list with name and first definition line (ES) in 3.08%, against 3.00% for bare names and 8.58% for the full entry. EL − H is +4.75 [3.00, 6.58]; ES − H is +0.08 [−0.75, 0.92]. By the registered rule, location alone is sufficient for the full effect (E − EL +0.83, 90% interval [−0.17, 1.83]).

**A false entry is not followed.** In E′ a decoy takes the place of one true neighbor, written with its own file, lines and definition line. The true entry is followed in 23 of 1,200 replays and the decoy in 1 (+1.83 points [0.83, 3.17]). By the registered rule, the agent checks the edge.

### 4.4 Five calls later

2,968 replays continued for up to five model calls with reads executing. Where a listed neighbor lies in a file the fix changes (57 complete states), the agent is shown a line the gold patch changes in 69.8% of replays with the legible list, 66.0% with bare names and 61.1% with no list. The registered contrast, E − H, is +3.86 [−1.05, 8.77]: no detectable gain at five calls. Exploratory: the legible list gets there sooner (63.5% against 53.0% by the third call, +10.5 [2.1, 19.3]) and bare names catch up (Figure 3c).

Where the fix is elsewhere (114 states), the list does no harm: the fix's file is opened in 22.5% of replays with it and 14.0% without. A rewired list does the same (21.6%), so this gain is not the graph's content (Section 5).

![](figures/table_rules.png)

**Table 1.** Every pre-registered rule and its outcome.

## 5. What the encoding changes (exploratory)

**Bare names already move the agent to the files.** Count a listed entry as followed by any means (its file opened at any lines, or its name or path used in a command): A is 5.2%, H 9.9%, D 12.9% and E 12.4% (H − A +4.64 [2.66, 6.79]; E − D −0.52 [−2.58, 1.46]).

**The encoding changes where in the file the read lands.** Given that the agent opens a listed entry's file, the read covers the entity 37% to 49% of the time in every arm except E, where it is 70% [56, 82]. In A, H and D all but three of 107 hits are a `read_file` from the top of the file, so an entity is reached only if it sits in the first 150 lines. In E, 47 of 96 hits start at a listed line. The pattern repeats in the tool channel (44% for P, 68% for PE) and on 26B-A4B (49% and 72%); it is weaker on E4B (47% and 55%).

**List position matters.** Per entry, E minus A is +4.1 points at rank 1, +1.7 at ranks 2 to 3, +1.0 at ranks 4 to 7 and +0.4 after that. The tool sorts alphabetically [4].

**The structure effect is smaller on matched entries.** The rewired entries were filtered to unseen names outside fix-location files; the scored true entries were not. With the true entries filtered the same way, E − H is still +2.32 [1.12, 3.69], but true minus rewired is +1.46 [0.00, 3.01]: most of the registered gap comes from true neighbors the agent has its own reasons to visit. Models differ in what they do with a rewired list: 26B-A4B touches its entries in 0.34% of replays with or without it, E4B in 2.84% against 0.66% (+2.19 [0.87, 3.83]).

**An interface defect.** In the replays the 31B model often writes a line bound under a mangled name, `start_line"`. The agent framework drops an argument name it does not know, so the read silently returns lines 1 to 150. A pre-registered test traces this to the harness change of Sep 30 that turned tool results from JSON strings into dictionaries [3]: with no list, 36.1% of first-call reads that carry a line bound are mangled under the current rendering and 0.3% under the old one (18.3% against 0.2% of replays, +18.2 [14.8, 21.8]); the original runs had 1.0%. With tools executing, 14.4% of 4,655 ranged reads were mangled and 658 returned the file from line 1. The no-list arm is hit hardest (25% to 41% of its ranged reads, against 6% to 10% after a legible note), a likely reason any note helped in Section 4.4. The other two models never do it. Our registered outcomes do not depend on it (E − H +5.50 becomes +5.58 with the bound honored).

## 6. What it means

Where these agents decide where to look, the graph's failure is not a failure to attend or to tell a true edge from a false one. The tool prints names. A name gets the agent to a file, which it reads from line 1 under a 150-line cap. A file and a line range get it to the code: three times as often at the next call, ten points more often by the third, and no more often by the fifth. What a legible graph buys this agent is calls.

Three changes follow; none needs training:

1. `get_code_neighbors` should return each neighbor's file and line range. The definition line can be left out.
2. The harness should reject an unknown argument name instead of dropping it, or render tool results as it did before Sep 30. As it stands, a third of the 31B model's ranged reads after a file read return the wrong lines.
3. The list is alphabetical and following falls with rank. An order by relevance is untested.

Legible output did not make wrong edges actionable for the two larger models; the smallest one does follow a rewired list.

## 7. Related work

How a graph is written as text changes what a language model does with it on static graph tasks [5, 6]; we ask that question inside an agent's loop. The nearest study is a pre-registered, placebo-controlled scale study of how much code-graph and embedding tools help small agents localize code [7]. Its graph tool already prints signatures and paths, and its arms vary the tool set, not the encoding; its placebo replaces every returned entity with a random one for whole episodes, scored by final localization. Its first version reports that forcing the graph call does not help and that agents expand once and stop [8]. LocAgent compares six text formats of its graph tool's output [9]; LARGER appends callers and callees to grep output and never varies the encoding [10]; RepoNav attributes localization gains to how retrieved snippets are organized [11]; others compare repository views [12] and tool architectures [13]; a same-track entry finds that adding call edges to a signature map does not help [14]. That output format changes agent behavior is therefore known.

On trust: pushed corrupted search results are adopted more than tool-returned ones on this model [15]; a harness-inserted tool result is trusted like a real call [16]; small agents copy a graph-learning tool's often wrong labels [17]. Fork designs exist for tool results in scientific question answering [18] and after compaction [19, 20].

Within the competition, GraphLoc asks whether this graph helps localization and repair [2] and GraphAudit whether it helps retrieval, with the rewiring control we borrow [21]. Forum posts audit the graph tools [4] and compare three encodings of a file read on 30 fixed edit contexts [3], a small precedent for our method.

In what we searched (`docs/lit/`), no work fixes one function's graph neighbors at a paused agent state, varies only their encoding or rewires them with degree preserved, and scores the next action against a no-list base rate.

## 8. Limitations

We measure where the agent looks, not whether it fixes the task. No run here is scored by tests, and by the fifth call the legible list's lead is not detectable. The five-call replays are read-only and end at the first edit; 49 of them overflowed the context, which the real agent avoids by compaction. States come from the 31B agent's runs on two repositories, and the other models continue its histories, not their own. One harness version, in two renderings of tool results. The hosted arms ran in three sessions; arm E was rerun twice on another platform (8.0% and 8.6% against 8.25%). The instruction effect depends on how recursive searches are scored. The decoy is plausible, not adversarial. The interface defect is measured in replays of earlier histories under the current harness, not in fresh runs.

## Reproducibility

Code, the seven pre-registrations with their commit times, the raw outputs of all nine runs, the independent re-derivations and the figure code are released under Apache 2.0 at [repository URL]. `analysis/reproduce.py` re-runs every analysis from the raw outputs and compares it with the stored result. The competition data is not redistributed; the state bundle is rebuilt from it by the exporter. The appendix lists the rules as text, the runs, robustness checks and every deviation.

## References

[1] Markowitz, Perozzi, Rózemberczki, Cameron, Hemmati, Li, Galkin, Farhadi, Holbrook, Oldacre. Google - The Gemma 4 Developer Agent Paper Track. Kaggle, 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent-paper

[2] GraphLoc: Where Does the Graph Help? A Localization Audit of the Gemma 4 Developer Agent Code Graphs. Kaggle writeup and notebooks (user zzgtylors), same track, Sep 2026. https://www.kaggle.com/code/zzgtylors/graphloc-auditing-gemma-4-agent-code-graphs

[3] Tool results reach the model double-JSON-encoded. Discussion 744272 with replies, Gemma 4 Developer Agent Competition, Kaggle, Sep 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744272

[4] Notes on the graph tools from auditing all 127 graphs. Discussion 745731, Gemma 4 Developer Agent Competition, Kaggle, Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745731

[5] Fatemi, Halcrow, Perozzi. Talk like a Graph: Encoding Graphs for Large Language Models. ICLR, 2024. arXiv:2310.04560

[6] Markowitz et al. KG-LLM-Bench: A Scalable Benchmark for Evaluating LLM Reasoning on Textualized Knowledge Graphs. arXiv:2504.07087, 2025

[7] Bellam. How Much Do Structural Tools Help Small Coding Agents? A Pre-Registered Scale Study of Code Localization. arXiv:2610.33958v2, 2026

[8] Bellam. How Do Small Coding Agents Use Code Graphs and Embeddings? arXiv:2610.33958v1, 2026

[9] Chen et al. LocAgent: Graph-Guided LLM Agents for Code Localization. ACL, 2025. arXiv:2503.09089 (Appendix A.1.2)

[10] Hu, Su, Zhao, Zhu, Haque. LARGER: Lexically Anchored Repository Graph Exploration and Retrieval. arXiv:2605.16352, 2026

[11] Chai et al. RepoNav: From Snippet Retrieval to File-Centered Repository Navigation for Code Agents. arXiv:2609.08355, 2026

[12] Sepidband et al. How Should Agents See Code? Rethinking Code Representations for Agentic Software Engineering. arXiv:2611.07286, 2026

[13] Xu et al. The Devil Is in the Interface: Evaluating How Tool Architecture Shapes Coding Agent Behavior. arXiv:2608.11386, 2026

[14] Muhammad. AST-Compressed Code Graphs for Gemma 4 Agents: What a Small Local Model Gains from a Budgeted Repository Map. Zenodo, 2026. doi:10.5281/zenodo.23927441

[15] Yang et al. Agents' Overreliance on Unreliable Tools. arXiv:2609.05587, 2026

[16] Kereopa-Yorke et al. Oracle Poisoning: Corrupting Knowledge Graphs to Weaponise AI Agent Reasoning. arXiv:2605.09822, 2026

[17] Wang, Vemuri. When the Tool Decides: LLM Agents Defer Blindly to Graph Neural Network Tools, and Stronger Backbones Defer More. arXiv:2606.14476, 2026

[18] Zhang et al. Same Simulation, Different Evidence: Where Retrieved Tool Output Costs LLM Agents Accuracy. arXiv:2610.26836, 2026

[19] Min et al. Adapting Context Compression for Long-Horizon Agents with Counterfactual Continuations. arXiv:2609.36526, 2026

[20] Sun et al. Compact-Bench: Measuring What Context Compaction Costs Long-Horizon Coding Agents. arXiv:2610.31710, 2026

[21] GraphAudit. Kaggle writeup in the same track, read in full on Oct 27, 2026 (hidden since submission; author and URL not recorded).

## Appendix

[[APPENDIX]]
