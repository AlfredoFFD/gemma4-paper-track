# Kickoff brief (Sep 30, 2026)

> **Update Sep 30, evening: read this first. The direction is pending a decision.**
>
> - **Our Q1 is already done by another entrant.** GraphLoc (see docs/prior-art.md) audited when the graph helps
>   localization on this exact data. It found the graph about equal to plain keyword search (BM25), and a graph
>   skill adding +0.9 points end to end (not significant). Its labels and code are Apache-2.0, so we build on them
>   rather than redo them.
> - **The provided graph and embeddings are weak:**
>   - The graph has calls-only edges, no async functions and many isolated nodes.
>   - The embeddings are near-collapsed, and the search tool is a lookup by node name, not text search.
>
>   So "does the graph help?" is partly "is this graph any good?".
> - **✓ Context is the bottleneck nobody has studied here.** At the scoring setting, compaction cannot fire, and a
>   context overflow throws away the patch: 12-33% of runs, per a participant's evidence (thread #744692).
> - **Two directions are on the table:**
>   - **Option 1, "Why doesn't the graph help?":** separate the four ways an external memory can fail. The agent
>     never consults it; it consults it but ignores it; the content is wrong or missing; the model can't read it.
>     Methods: the decoy test with scrambled graphs, a graph-quality dose-response (repaired, provided, scrambled),
>     and a LoRA. Solid, but close to GraphLoc.
>   - **Option 2, "Finding vs remembering":** GraphLoc shows the graph doesn't help agents *find* the bug. The new
>     hypothesis is that it helps a small-context agent *remember*: symbol names as compact pointers, names-only
>     neighbor lookups, and re-fetching exact functions instead of re-reading big files. The test is context
>     pressure (tokens used, overflow rate, lost patches, resolve rate) with graph-anchored working memory vs plain
>     vs notes-file memory. This is new relative to GraphLoc, fits the "externalized memory" framing, and targets
>     a verified bottleneck.
> - **Claude Code's recommendation: Option 2 as the lead hypothesis, with Option 1's decoy test as the method for
>   the "finding" half.** Gate it with a fast prior-art check on working memory for SWE agents, plus Phase 0 numbers
>   (how much context goes to re-reading code, and what causes overflows). The sections below still describe the
>   original design and will be rewritten once the team decides.

For the team and for Claude Science, which will do most of the execution. Everything under
"Decided" was agreed in the brainstorm. Everything under "Open" is still a hypothesis. Facts about the
competition come from the Kaggle pages (read Sep 27-30); see [docs/competition.md](docs/competition.md).

## Goal

Write a paper-track submission with a real chance at **Overall Best Paper ($15k)**. We need a clean, verifiable
result that the organizers care about. Resource or application prizes ($10k each) are fallbacks, not targets.
Winning papers are shown at a Google expo during NeurIPS 2026.

## What the judges score (equal weights, 0 to 5 each)

- **Novelty:** new insights, or important properties of existing methods.
- **Quality:** how general the approach is beyond the competition.
- **Relevance:** impact on software engineering and agentic learning.
- **Verifiability:** enough detail to see how data was obtained, analyzed and interpreted.
- **Clarity.**

Format: a Kaggle Writeup, at most 3,000 words, original and unpublished. Non-archival. A public notebook is optional
but helps verifiability. Required parts: title and subtitle, abstract, introduction, methods and experiments,
related work and citations.

## Why this topic (the judge fit)

- The organizers built code graphs and node embeddings for every task, plus three graph tools
  (`get_code_neighbors`, `get_code_subgraph`, `search_similar_code`). They write that submissions using this dataset
  are "highly encouraged".
- Organizer Bryan Perozzi co-wrote *Talk like a Graph* (ICLR 2024): how a graph is encoded as text swings LLM
  accuracy by 4.8% to 61.8%.
- Judge Elan Markowitz wrote *KG-LLM-Bench* (arXiv 2504.07087) on how knowledge-graph textualization affects LLM
  reasoning.
- So "when does your graph help, what does it add, and can the model learn to use it" is their question. Our
  framing names it: **the code graph as the agent's externalized memory**.

## Decided

- Paper track, team of two.
- Topic: code graph as externalized memory for a small coding agent, organized as diagnose, measure, fix (below).
- Model: `gemma-4-31b-it-qat-w4a16-ct`, the only variant the competition supports.
- Tasks: the 129 public development tasks (fastapi, rich, requests, httpx) with gold patches and tests.
- Pre-register every experiment we will report, before its data exists ([prereg/](prereg/)).
- Hold out repositories for anything tuned. The hidden leaderboard (private repositories) is our external test.

## The three questions (Open: all hypotheses)

1. **When does structure help? (diagnose, offline, no GPU)**
   - For each task, compute two things:
     - the call-graph distance from the symbols the issue names to the symbols the gold patch edits
     - the rank of those gold symbols under plain semantic search
   - Where the gold symbol is close in the graph but ranked poorly by search, the graph should add value. If almost
     no task looks like that, the whole paper needs rethinking. This is the cheapest early warning we have.
2. **What does structure add over semantic retrieval? (measure, agent runs)** Serve the harness's own tools in five
   counterfactual arms:
   - (a) true graph and embeddings
   - (b) structure scrambled: edges rewired to plausible sibling symbols, embeddings intact
   - (c) embeddings scrambled: node vectors permuted among plausible siblings, edges intact
   - (d) both scrambled
   - (e) graph tools removed

   Outcomes:
   - localization (did the agent read or edit the gold symbol)
   - resolve rate (tests pass)
   - **readership**: when a tool points to a decoy, how often the agent follows it, compared with the decoy-visit
     rate under the true graph

   Each trial is classified as "never called the tool", "called it but ignored it" or "followed it over the code".
3. **Can cheap training make the model use structure? (fix)**
   - A no-training baseline first: a skill or prompt that makes the agent trace the graph before editing.
   - Then a LoRA trained on Gemma's own successful, graph-using trajectories (rejection sampling), with the
     repository held out.
   - The key measurement is not just a higher score but **more reliance on structure**: a bigger drop under arm (b)
     after training.
   - Then submit the fixed agent to the main leaderboard for a private-repository number.

## Plan and gates

| Phase | Dates | Work | Go only if |
|---|---|---|---|
| 0. Pilot | Sep 30 to Oct 9 | Literature map attacking Q2 and Q3 novelty; Q1 offline map; harness pilot (run Gemma 4 on a few tasks, cost per task, how often it calls the graph tools) | No published paper already does Q2; a meaningful share of tasks favors structure (threshold set in the pre-registration, e.g. at least 20%); cost per task is affordable |
| 1. Measure | Oct 10 to Oct 31 | Pre-registered Q2 runs; Q3 baseline skill and LoRA | Registered decision rules decide, not us |
| 2. Write | Nov 1 to Nov 10 | Leaderboard submission of the fix; 3,000-word writeup; public notebook | Submit by Nov 10, leaving two days of buffer |

## Constraints and known facts

- **Compute:** the harness runs in Docker containers, so Colab cannot run agent episodes (no Docker). Options:
  - Claude Science's cloud compute (Modal)
  - a rented GPU VM
  - Colab Pro+ (available to us) for things that need no Docker: the offline analysis and LoRA training

  Real RL is out of budget; stay with cheap, clever training.
- **Scale:** the full Q2 design at about 129 tasks x 5 arms x 2 seeds is roughly 1,300 agent episodes. That's an
  estimate; the pilot measures real cost and may force a subset.
- **Harness:** tools are `run_command`, `read_file` (line slicing), `edit_file` (string replace),
  `write_file`, `submit_patch`, `get_status`, plus the three graph tools. The agent has 12 hours for all tasks on
  the leaderboard. Submissions are ADK agent configs (prompts, sub-agents, skills, LoRA adapters).
- **Data:** graphs are NetworkX JSON (node id = fully qualified symbol path, with source text; edges such as calls);
  embeddings are 256-dimensional vectors per node. Counterfactual arms (b) and (c) can reuse these files: rewire
  edges, permute node-to-vector assignments. No re-embedding is needed as long as we do not change node text.
- **Known risk:** agents may rarely call graph tools (another study saw 58% of graph-arm runs make zero graph
  calls). Pre-register an intention-to-treat analysis, and consider an arm that forces one graph call.
- **Nondeterminism:** identical runs at temperature 0 reportedly flip about 9% of outcomes. Use paired seeds and
  McNemar tests.

## Nearest prior work (details in [docs/prior-art.md](docs/prior-art.md))

- *Code Isn't Memory* (arXiv 2606.22417): a structural index helps Claude Opus 4.7 localize and resolve, mostly on
  multi-file tasks. On/off arms only, one frontier model.
- *LocAgent* (arXiv 2503.09089): graph-guided localization; fine-tuned Qwen2.5-Coder-32B matches proprietary models
  on localization. It measures accuracy, not reliance on structure.
- *Oracle Poisoning* (2605.09822), *Deterministic Anchoring* (2606.26979), *CodeCompass* (2602.20048), *Don't
  Blindly Trust It* (2606.21409): pieces of our design, but none inside end-to-end SWE bug-fixing.

## Roles (to split between the two of us)

- **Team:** experimental design and pre-registrations (Q1, Q2); the training fix (Q3); the memory framing and its
  related work; analysis and writing.
- **Claude Science:** execution on cloud compute, literature map, reviewer passes, research log.
- **Claude Code:** repo, local tooling, independent re-derivation of every headline number.

## First tasks for Claude Science

1. **Literature map.** Re-verify every citation in docs/prior-art.md from the paper itself. Search hard for any
   paper that already scrambles code-graph structure versus embeddings to measure reliance (Q2), or that measures
   whether fine-tuning increases reliance on structure (Q3). Report KILLED, WEAKENED or OPEN for each, with the
   nearest work.
2. **Q1 offline map** from the dataset in `data/`.
   Include the distribution plot and the share of structure-favoring tasks.
3. **Harness pilot.** Run the sample submission on 3 to 5 tasks with Gemma 4. Record cost per task, time per task,
   and the graph-tool call rate.

Write everything in LOG.md with dates and reasons.
