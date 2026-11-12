# A name is not an address, and an address is not enough

**Subtitle:** What a coding agent does with a code graph's answers, and why they have not helped

## Abstract

The Gemma 4 developer agent comes with a code graph and tools that query it, yet no public test we know of shows the graph raising the number of solved tasks. We ask why, testing the same change to a tool's answer at paused steps of real runs, replayed with one message changed, and in whole runs. The graph's answers seldom arrive: the current task prompt cut the agent's first calls to a graph tool from 29% to under 1% (registered). When an answer does arrive, the agent follows it three times as often with a line range as with a bare name (8.25% against 2.75% of replays; registered, and replicated on other models). But with the graph's answers attached to file reads in whole runs, line ranges changed nothing we could detect (38 against 35 of 103 tasks resolved; registered). A registered replay can explain why: the same list is followed in 1.90% of steps inside a file view, 6.65% as a separate note after it. As its tools present it, the graph is no detectably better guide to code a run missed than a rewiring that keeps each edge's two files, and the tool's unstated choice among same-named definitions does no better than a random pick (exploratory). Location is not enough either: told the lines a fix changes, the agent still fails most tasks. We release the replay suite, with its pre-registrations and blind second scripts: any tool answer, at paused steps, on any model behind an API, for a few dollars.

## 1. The question

The competition [1] gives every agent a code graph of the repository and three tools to query it. In the public runs of GraphLoc [2], the starter agent resolved 95 of 315 scored runs with a skill that ranks locations from the graph and 92 of 315 without. Other entries find that expanding along its edges retrieves code no better than matching words [3–6], that appending the nodes nearest the issue leaves resolved tasks unchanged [7], and that the graph tools change nothing detectable [8].

How a graph is written as text changes what a language model *answers* about it [9–11]. We ask what it changes in what an agent *does*. We measure one change, a line range in the graph's answers, at replayed steps, where an effect is cheap to find, and in whole runs, where it counts. We found no earlier test of a tool's output format at both levels, and a registered replay finds a reason the two can differ (Section 4). We find five reasons the graph has not helped, each with a change for tool builders.

## 2. Method

**Replay.** A paused step is the history of a recorded run up to one of its tool results. Our replay suite loads it into the harness's compiled agent, adds or changes one message, and lets the agent make one model call; no tool runs (Figure 1; after [12–14]; a concurrent track entry probes paused runs the same way [15]). Each condition is sampled three times at the starter agent's settings. The paused steps come from September's public runs (harness release of Sep 30); whole runs use the release of Oct 12.

**Populations.** fastapi and rich hold 103 of the 106 tasks the public runs cover (of 129 public tasks), and all our runs (Table 1). A contrast uses the steps complete in all its arms (Appendix B).

![](figures/table_populations.png)

**Table 1.** The populations.

**Outcomes.** At one call, the agent *reads a neighbor's code* when its next call reads, views, searches or edits lines of a listed neighbor in a file it has not opened (registered). That outcome, like "reads a file past line 1" in the search experiments, favors answers with line numbers (a read without a range returns the first 150 lines), so we report beside each whether the agent *opens the file* at all (exploratory). In whole runs, a run is *shown* a *changed region* (a hunk of the reference patch) when a file read returns one of its lines; the task's tests decide *resolved*.

**Rules.** Before each experiment we committed its decision rules (*registered*; exceptions: Appendix F). A rule is *met* when the 95% bootstrap interval of its difference lies on the registered side of zero; otherwise we write *not met*, or *no detectable difference* where no side was registered. Either may mean only that the test could not decide. Every registered result, but for the first registration's, was recomputed by a second script written blind to the first. Table 2 lists the rules reported here and Appendix A all of them; everything else is marked exploratory.

![](figures/fig_design.png)

**Figure 1.** A paused step, the one message that differs between conditions, and the outcome.

## 3. The graph's answers seldom reach the agent

**Called, and answered (exploratory).** In September's public runs without the skill, the agent called a graph tool in 109 of 318 runs (34%), nearly always `search_similar_code` first, which returned nothing for 114 of its 135 calls (also [16, 17]); a non-empty answer from any graph tool reached 26 of the 318 runs. The October release repaired this [18].

**The current prompt (registered).** At the first model call of 100 tasks, 29% of calls go to a graph tool under September's task prompt and under 1% under the current one. Its file listing and its wording of the tool lines each matter (Table 2).

**When answers do arrive.** Another entry [16] repaired the tools and prompted the agent to ask the graph first: first answers with results rose from 4% to 85% of runs, and resolved tasks did not change detectably (+4.2 points [−2.8, 11.3]; 71 tasks).

**Handed over instead (registered).** At 53 steps paused just before the agent searches for code, we handed it, in a note (a separate message), the hits that search was about to return (Figure 2). Its next call reads a noted file past line 1 in 2.5% of replays with nothing added, in 39% when handed them (met), and in 61% one call later, when it had searched itself; it opens a noted file at all in 6%, 59% and 77%. Handed hits are used 0.64 times as often as searched ones [0.47, 0.82] (registered mark of two thirds: not met; undecided).

![](figures/fig_asked_told.png)

**Figure 2.** The same search hits, searched for or handed over.

## 4. The answers are names, and the agent acts on line numbers

`get_code_neighbors` answers with dotted names. We replayed 388 steps with no list, with the names, and with *addresses*: each name followed by its file, line range and definition line. The next call reads a neighbor's code in 2.15%, 2.75% and 8.25% of 1,164 replays each; addresses against names is met (+5.50 points [3.44, 7.65]; on the October release, +5.6 [3.8, 7.8], met). The neighbor's file is opened at all in 4.6%, 7.5% and 11.8% (exploratory; +4.3 points [2.3, 6.4]).

**The line range does it, not the format (registered).** At the same steps, file and range alone give 7.7% of replays and the file alone 3.2% (+4.6 points [2.7, 6.6]; met). Neither the definition line nor the format adds anything detectable (Table 2).

A swapped-in non-neighbor with its own address is seldom read (met), and a rewired list is not detectably read less than a true one (not met; Table 2).

**The agent's own search behaves alike.** At 60 steps it has just searched, and the result names an unopened file with line numbers: its next call reads that file past line 1 in 62% of replays, and in 5% with the numbers stripped (met). Stripped, it still opens the file (60% against 76%), but from the top (99 of 108 reads; exploratory): the name gets the file opened, the number gets the line read.

Both contrasts hold when other models continue the same steps (Figure 3): addresses against names on ten (+2.0 to +10.3 points; with tasks resampled, on nine), the search on eight (+23.5 to +54.1).

![](figures/fig_models.png)

**Figure 3.** Names against addresses in a graph answer (left); a search result with and without line numbers (right).

**In whole runs (registered).** Addresses in the tools' own answers resolved 37 of 103 tasks against 36 as shipped (+1.0 points [−5.8, 7.8]): uninformative, since the agent seldom calls a graph tool (8 of 103 shipped runs). So we *pushed* the answers: a file read's result carried, as its last key, up to eight graph neighbors of the code just shown, as names or with file and line range (one seed). The two forms did not detectably differ: 38 tasks resolved with addresses, 35 with names (+2.9 points [−4.9, 9.7]), nor in where first reads of a listed file start (not met; Table 2). Scored as in the replays (exploratory), the call after a list reads a listed neighbor's code after 3.1% of lists with addresses and 2.5% with names (+0.6 points [−0.8, 2.0]). And 4% of the pushed entries point at a place the fix changes. The four whole-run arms lose runs at the same stages (Figure 7a; exploratory): 59 to 63 of 103 are shown every changed region, 35 to 38 resolve, and 80 tasks have the same outcome in all four.

**The place of the list (registered).** We then replayed where the list sits: at 316 steps that end with a file view, the same entries came as the last key inside the view (as names or with addresses) or as a note after it (one seed). The next call reads a neighbor's code in 1.58%, 1.90% and 6.65% of steps: in the key the address adds nothing detectable (+0.32 points [−0.63, 1.27]); as a note the same addressed list is followed 3.5 times as often (+4.75 [2.53, 7.28]; met). The list's place can explain the whole-run null; whole runs with a note are untested.

## 5. The graph's edges are mostly names, and its tools hide how a name was resolved (exploratory)

The competition's 127 graphs hold one type of edge, `calls`, stored in both directions [19, 20] (Figure 4); a quarter of the edges link a class to its own members, and we found no node for an `async def` function (also [19]). For 98.5% of the 449,902 neighbor pairs one function's text contains the other's name. What a search cannot tell is which definition a name means: for 31% of pairs other nodes share the neighbor's short name. An edge could tell them apart (Section 6), but the tools do not pass that on: since October `get_code_neighbors` accepts a short name and resolves it, without saying so, to the same-named node with the fewest dotted parts, and answers with names only: no file, no line, no direction.

![](figures/fig_graph.png)

**Figure 4.** What an edge of the code graph is.

## 6. Runs miss parts of a fix, and call edges are no detectably better guide to them than file pairs (exploratory)

In the public runs without the skill, a fix inside one file is shown to the agent whole in 74% of runs, one across files in 20% (Figure 5a).

In both arms of the public runs, a run missed a changed region 1,326 times. In 267 of them (20%), the missed place is one call edge from code the run was shown. That is more than in a rewired graph that keeps only each node's degree (11%), and not detectably more than in one that keeps each edge in its directory (15%) or between its two files (18%). We cannot show that an edge tells more about the missed place than its file does.

For 32% of the missed places, the missed function uses the name of something the run was shown, or the reverse (names such as `__init__` not counted): 11.9 points more than the edge [5.9, 17.4], with 256 of the edge's 267 among them (Figure 5b). Of 227 missed places whose short name is shared by other definitions and appears in code the run was shown, a call edge from that code points at 70, a random pick among the same-named definitions at about 30 and the release's own rule at 29 (edge over random +17.5 points [4.8, 45.0]). Without names such as `__init__`: edge 22 of 70, random pick about 25.

![](figures/fig_moves.png)

**Figure 5.** (a) Fixes in one file against fixes in several. (b) Regions a run was never shown: within reach of code it was shown.

## 7. Told where the fix is, the agent still fails most tasks

We told the agent where the fix is, as others have [21–24], in a note ending the task statement, on the 40 tasks where our shipped run had missed part of it. *Names* lists every function, class or module the accepted fix changes; *ranges* adds file and line range; *lines* gives each changed place as a file and about twenty lines; the *control* has no note.

![](figures/fig_oracle.png)

**Figure 6.** Told where the fix is: tasks resolved, first reads, lines read.

**Registered, first seed.** Resolved (control, names, lines): 2, 5 and 8 of 40. Lines against the control is met (+15 points [5.0, 27.5]; exact McNemar p = 0.03, uncorrected); the other two contrasts show no detectable difference.

**Second seed, half a run.** A second registered seed added ranges; every second task of a shuffled list ran (20 of 40), under the registered floor of 34 for a verdict. Resolved: control 4, names 7, ranges 5, lines 6: the first seed's lead of lines was not repeated.

**What the form changes (exploratory).** Given names, the agent opens a named file at line 1 in 31 of 36 first reads (second seed); given ranges or lines, most first reads go to a noted line (Figure 6b). The final patch overlaps a changed region in 19, 20 and 33 of 40 runs in the first seed (control, names, lines; Figure 7b) and in 8, 11, 13 and 13 of 20 in the second (control, names, ranges, lines), which had registered lines against names (no verdict). Names and lines differ in grain as well as form.

![](figures/fig_funnel.png)

**Figure 7.** Where whole runs are lost, by arm.

## 8. What to change

One change per reason; none is shown to resolve more tasks.

1. Restore the prompt wording under which the agent asks the graph (Table 2), without expecting that alone to resolve more tasks [16].
2. Print the file and line range of every entity, for example `{"name": "pkg.mod.f", "file": "pkg/mod.py", "lines": "120-148"}` (Appendix D). Push a list as a note after a tool's result, not as a key inside it.
3. Say which same-named definition a short name was resolved to, or return them all with their addresses: today's unstated rule does no better than a random pick.
4. Aim at the parts of a fix a run misses: call edges are no detectably better guide to them than file pairs.
5. Do not expect location alone to solve most tasks: told the changed lines, the agent resolved 8 of 40 and 6 of 20 (2 and 4 with no note).

![](figures/table_rules_v2.png)

**Table 2.** Registered rules of the experiments above, with estimates and outcomes (reasons 1 to 5: Sections 3 to 7).

## 9. Related work

Most of our single findings have close precedents. That an agent's next file is one its last tool output names is an argument of interface design [25], reported observationally [26] and in this track [16]; our replays vary the output, as [27] did once. That a code graph's edges add little for a small agent beyond an index of its nodes is a secondary analysis of a pre-registered study [28] and the result of a track entry [29] (see also [17, 19, 20, 30–37]). Call links written into the code an agent reads gain about two points of localization [38], and context files pushed at commercial agents did not detectably change their pass rate [39]. Instructions are followed less inside a tool result than in a user message in most models tested [40–42]; our place result is akin, for code locations after a file's content. Exact locations help a strong agent little [24], and the title alone keeps our model 10 of 83 solves [43]. Nearest to our design, [28] measures one injected search line at an episode's first step and in whole runs. We found no other test of a tool's output format at both levels, no note set against the agent's own search with the content held fixed (nearest: [40, 44]), and no rewiring that keeps each edge's directory or its two files ([45] has a degree-preserving null).

## 10. Limitations

One agent scaffold and two repositories. The paused steps are file views of Gemma-4-31B's September runs; other models continue those histories: replications at the same steps, not independent agents. The one-call effect did not appear in whole runs, akin to the replay gap [46]; the list's place can explain it (one seed); whole runs with a note are untested. The registered intervals resample steps; with tasks resampled most are wider (up to 1.9 times; Appendix C) and two verdicts change (addresses against names on one hosted model; names against no list in an earlier run). The whole-run test of pushed lists has one seed and no arm without lists; its interval rules out a gain above 10 points in resolved tasks, not the few points reported for location aids [24]. No correction is made for the number of rules.

## The replay suite

The suite is released under Apache 2.0 at https://github.com/AlfredoFFD/gemma4-paper-track: the builder of the paused steps, a runner that puts one changed message through the harness's own agent on a GPU or any OpenAI-compatible API, the scorers, the registrations with commit times, raw outputs and second scripts. An unaltered replay makes the same kind of call as the recorded run made next in 70% of cases, where two replays of one step agree in 78% (exploratory; cf. [47]). `docs/replay-tool.md` shows how to test a new tool answer; `analysis/reproduce.py` re-runs over 100 analyses.

## References

[1] Markowitz, Perozzi, Rózemberczki, Cameron, Hemmati, Li, Galkin, Farhadi, Holbrook, Oldacre. Google - The Gemma 4 Developer Agent Paper Track. Kaggle, 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent-paper

[2] GraphLoc: Where Does the Graph Help? A Localization Audit of the Gemma 4 Developer Agent Code Graphs. Kaggle writeup and notebooks (user zzgtylors), same track, Sep 2026. https://www.kaggle.com/code/zzgtylors/graphloc-auditing-gemma-4-agent-code-graphs

[3] g4 Paper Graph Benchmark. Kaggle notebook (user narisettichaitanya), same track, Nov 2026. https://www.kaggle.com/code/narisettichaitanya/g4-paper-graph-benchmark

[4] What Limits a Small-Model SWE Agent? Reproduction. Kaggle notebook (user bsw0610), same track, Nov 2026. https://www.kaggle.com/code/bsw0610/what-limits-a-small-model-swe-agent-reproduction

[5] Anchor Diffusion Writeup. Kaggle notebook (user keykavus), same track, Nov 2026. https://www.kaggle.com/code/keykavus/anchor-diffusion-writeup

[6] Retrieval or Selection: Reproduce Tables. Kaggle notebook (user mstege), same track, Nov 2026. https://www.kaggle.com/code/mstege/retrieval-or-selection-reproduce-tables

[7] Does Retrieval Help the Gemma 4 Agent? Paired A/B. Kaggle notebook (user mohammedqattan), same track, Nov 2026. https://www.kaggle.com/code/mohammedqattan/does-retrieval-help-the-gemma-4-agent-paired-a-b

[8] Audit: 61 of 129 public tasks can't tell agents apart. Kaggle discussion 756400, Gemma 4 Developer Agent competition, Nov 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/756400

[9] Fatemi, Halcrow, Perozzi. Talk like a Graph: Encoding Graphs for Large Language Models. ICLR, 2024. arXiv:2310.04560

[10] Markowitz et al. KG-LLM-Bench: A Scalable Benchmark for Evaluating LLM Reasoning on Textualized Knowledge Graphs. arXiv:2504.07087, 2025

[11] Can Gemma 4 read the code graph its tools return? Kaggle writeup, same track, with code, stored replies and the paper text (user alepacheco), Nov 2026. https://www.kaggle.com/datasets/alepacheco/graphread-gemma4

[12] Zhang et al. Same Simulation, Different Evidence: Where Retrieved Tool Output Costs LLM Agents Accuracy. arXiv:2610.26836, 2026

[13] Min et al. Adapting Context Compression for Long-Horizon Agents with Counterfactual Continuations. arXiv:2609.36526, 2026

[14] Sun et al. Compact-Bench: Measuring What Context Compaction Costs Long-Horizon Coding Agents. arXiv:2610.31710, 2026

[15] Instructions lose to interfaces: what steers Gemma 4 31B as a coding agent. Kaggle notebook and dataset (user hassantavakoli), same track, Nov 2026. https://www.kaggle.com/code/hassantavakoli/instructions-lose-to-interfaces-reproduce-tables

[16] What the Agent Saw: Cue-Driven Navigation and the Limits of Behavioral Prediction in a Coding Agent. Kaggle writeup, same track, with data, code and pre-registration (user petermugoya), Oct 2026. https://www.kaggle.com/datasets/petermugoya/what-the-agent-saw

[17] Silent Failures in Code-Graph Tools: Why a Local Gemma 4 Agent Ignores the Map. Kaggle writeup, same track, with data and a reproduction notebook (user kmussa77), Oct 2026. https://www.kaggle.com/datasets/kmussa77/gemma4-agent-traces-graph-audit

[18] Silent failures in the Gemma 4 Developer Agent code-graph toolkit. Kaggle notebook and dataset (user chengren01), same track, Nov 2026. https://www.kaggle.com/code/chengren01/code-graph-toolkit-audit-rerun-on-official-data

[19] Notes on the graph tools from auditing all 127 graphs. Discussion 745731, Gemma 4 Developer Agent Competition, Kaggle, Oct 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745731

[20] BugDial: how far is the bug (reproduction). Kaggle notebook (user godswillidolor), same track, Nov 2026. https://www.kaggle.com/code/godswillidolor/bugdial-how-far-is-the-bug-reproduction

[21] Zhao, Yang, Le, Liu, Tian. Beyond Localization: Recoverable Headroom and Residual Frontier in Repository-Level RAG-APR. arXiv:2603.29067, 2026.

[22] Townsend, Pravin, Ngan, Parizy. A Study on the Impact of Fault localization Granularity for Repository-Scale Code Repair Tasks. arXiv:2604.00167, 2026.

[23] Li, Jin, Zhu, Huang, Wu, Zhang, Zhang, Jin, Huang, Nallipogu, Zhang, Kang, Rajmohan, Lin, Lee, Zhang. ORACLE-SWE: Quantifying the Contribution of Oracle Information Signals on SWE Agents. arXiv:2604.07789, 2026.

[24] Shi, Yang, Chen. From Finding to Fixing: How Useful is Fault Localization for Agentic Program Repair? arXiv:2610.25826, 2026. https://arxiv.org/abs/2610.25826

[25] Yang, Jimenez, Wettig, Lieret, Yao, Narasimhan, Press. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS, 2024. arXiv:2405.15793

[26] J. He et al. What Process Evaluation of Coding Agents Actually Measures: Action, Task, and Step Are Three Different Levels. arXiv:2608.22960, 2026. https://arxiv.org/abs/2608.22960

[27] Tool results reach the model double-JSON-encoded. Discussion 744272 with replies, Gemma 4 Developer Agent Competition, Kaggle, Sep 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744272

[28] Bellam. How Much Do Structural Tools Help Small Coding Agents? A Pre-Registered Scale Study of Code Localization. arXiv:2610.33958v2, 2026 (v1: How Do Small Coding Agents Use Code Graphs and Embeddings?)

[29] Nodes or Edges? What a Code Graph Actually Contributes to a Small Coding Agent. Kaggle notebook (user lizhang20252026), same track, Nov 2026. https://www.kaggle.com/code/lizhang20252026/nodes-or-edges-tool-ablation-notebook

[30] Chen et al. LocAgent: Graph-Guided LLM Agents for Code Localization. ACL, 2025. arXiv:2503.09089 (Appendix A.1.2)

[31] Hu, Su, Zhao, Zhu, Haque. LARGER: Lexically Anchored Repository Graph Exploration and Retrieval. arXiv:2605.16352, 2026

[32] Chai et al. RepoNav: From Snippet Retrieval to File-Centered Repository Navigation for Code Agents. arXiv:2609.08355, 2026

[33] Sepidband et al. How Should Agents See Code? Rethinking Code Representations for Agentic Software Engineering. arXiv:2611.07286, 2026

[34] Xu et al. The Devil Is in the Interface: Evaluating How Tool Architecture Shapes Coding Agent Behavior. arXiv:2608.11386, 2026

[35] Muhammad. AST-Compressed Code Graphs for Gemma 4 Agents: What a Small Local Model Gains from a Budgeted Repository Map. Zenodo, 2026. doi:10.5281/zenodo.23927441

[36] Chen, Yang, Cao, Lin. CodeGrep: An RL-Trained Retrieval Agent for LLM Coding Agents. arXiv:2608.05886, 2026.

[37] Seddik, Seddik, Esmaeili, Sadatbenis, Fard. ARISE: A Repository-level Graph Representation and Toolset for Agentic Program Repair and Fault Localization. arXiv:2605.03117, 2026.

[38] Lin, Zhou, Yang, Li. How Much Static Structure Do Code Agents Need? A Study of Deterministic Anchoring. ISSTA 2026. arXiv:2606.26979

[39] P. Khatri. Do Context Files Help Coding Agents? A Two-Agent Ablation Study on Real Repositories. arXiv:2607.27250, 2026. https://arxiv.org/abs/2607.27250

[40] Syed, Yasaei. Same Payload, Different Channel: Measuring Trust Asymmetry in Tool-Using Language Models. arXiv:2606.00566, 2026.

[41] Woo, Conde, Reviriego. Same Error, Different Recovery: How Delivery Changes LLM Agent Behavior. arXiv:2611.11581, 2026. https://arxiv.org/abs/2611.11581

[42] Laddha, Pradhan, Srivastava. Position, Role or Label? A Controlled Study of Instruction Conflicts in LLM Agents. arXiv:2610.33201, 2026. https://arxiv.org/abs/2610.33201

[43] Khatib, Mathews, Nagappan, Nie, Zimmermann. What Makes a Good Bug Report for an AI Agent? arXiv:2607.07593, 2026. https://arxiv.org/abs/2607.07593

[44] Saha. Delivery, Not Storage: Cue-Anchored Working Memory as a Harness Property for Coding Agents. arXiv:2607.20972, 2026.

[45] GraphAudit: Measuring Help and Harm in Code-Graph Retrieval. Kaggle writeup, same track, with companion notebook "GraphAudit - Code Graph Intervention Benchmark" (user tejasgluth), Oct 2026. https://www.kaggle.com/code/tejasgluth/graphaudit-code-graph-intervention-benchmark

[46] A. Gonuguntla. The Replay Gap: Static Evaluation of Model Switching in LLM Agents Scores the Wrong World. arXiv:2608.08239, 2026. https://arxiv.org/abs/2608.08239

[47] E. Pakhomov, E. Nijkamp. Attributing Agent Failures to Their History Needs an Executed Counterfactual: Toward a Reporting Standard. arXiv:2611.05650, 2026. https://arxiv.org/abs/2611.05650

[48] PatchPool: Gemma 4 agent patches and labels. Kaggle dataset with traces (user vanductan), Oct 2026. https://www.kaggle.com/datasets/vanductan/gemma4-patchpool

[49] gemma4-commit-anatomy-traces. Kaggle dataset (user niraberman), Nov 2026. https://www.kaggle.com/datasets/niraberman/gemma4-commit-anatomy-traces

[50] Yang, Lieret, Jimenez, Wettig, Khandpur, Zhang, Hui, Press, Schmidt, Yang. SWE-smith: Scaling Data for Software Engineering Agents. arXiv:2504.21798, 2025. Trajectories: https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories (split `tool`, rows 0 to 799)

[51] Nebius. SWE-agent-trajectories. Hugging Face dataset, 2024. https://huggingface.co/datasets/nebius/SWE-agent-trajectories (split `train`, rows 0 to 799)

[52] Trofimova, Shevtsov, Badertdinov, Pyaev, Karasik, Golubev. OpenHands Trajectories with Qwen3-Coder-480B-A35B-Instruct. Nebius blog, 2025. Dataset: https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories (split `train`, rows 0 to 799)

[53] Pan, Wang, Neubig, Jaitly, Ji, Suhr, Zhang. Training Software Engineering Agents and Verifiers with SWE-Gym. ICML 2025. arXiv:2412.21139. Trajectories: https://huggingface.co/datasets/SWE-Gym/OpenHands-Sampled-Trajectories (split `train.raw`, rows 0 to 799)

[54] Gemma and the Unclosed Quotation; Gemma and the Fifty-Eight Silences. Kaggle notebooks (user prvsiyan), Nov 2026. https://www.kaggle.com/code/prvsiyan/gemma-and-the-unclosed-quotation and https://www.kaggle.com/code/prvsiyan/gemma-and-the-fifty-eight-silences. With: joe_qrq, "Tool-call serialization issue: edit_file repeatedly emitted without old_string", discussion 756051 of the main competition, Nov 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/756051

## Statement on AI assistance

I was assisted by Claude Code, an AI coding assistant, in building and running the experiments and in preparing this writeup. The research direction and the judgments in this writeup are mine. The second scripts were written by separate sessions of the assistant (F.14, F.19), and the "blind readers" this appendix cites are sessions of AI models as well.

## Appendices

In [appendix.md](appendix.md).
