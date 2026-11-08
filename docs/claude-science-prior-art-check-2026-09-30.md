# Prior-art check and direction recommendation

Claude Science, 2026-09-30 (evening ET). Read-only literature work; no GPU or paid compute. Five Claude Science
sub-agents read the papers below from their full text (arXiv HTML or PDF, version recorded); this session re-checked
the numbers that carry a decision. Their per-paper reports, which name rival entrants, are in
`private/claude-science/2026-09-30/` (gitignored). Numbers marked EXPLORATORY come from public data that existed
before any plan of ours.

## Bottom line

**Direction 1 ("finding vs remembering") is WEAKENED, and two of its four sub-claims are already published.** Overflow
at a 32k window is the measured outcome of a September 2026 harness study ([2609.20804](https://arxiv.org/abs/2609.20804)),
where unmanaged agents overflow in 78.7% of SWE-Bench Verified runs and plain elision of stale tool outputs removes
overflow. Symbol-addressed retrieval as a token saver is established (CODESTRUCT, AutoCodeRover, Agentless, LocAgent's
fetch-by-ID, Aider's repo map). Graph-structured memory for coding agents exists without a hard window (StateTape,
Prometheus, CodeNib, ContextSniper). Only the comparison against a notes file is open, and it is a control, not a
headline. GraphLoc's public traces add a practical objection: in its setting, overflow is triggered by one large tool
output arriving under a 16,384-token prompt cap that the sample config's 16,384-token output reservation imposes, and
re-reading already-seen code is only about 10% of what enters the context (EXPLORATORY). A judge will ask why the
agent did not simply lower `max_output_tokens` or cap tool outputs. I recommend against Direction 1 as the lead.

**Direction 2 ("why doesn't the graph help?") is also WEAKENED, but what survives is larger and better aimed at these
judges.** Every ingredient has a precedent: knowledge-graph perturbation tests of reliance
([Raman et al. 2021](https://arxiv.org/abs/2010.12872); [Huang et al. 2024](https://arxiv.org/abs/2309.16595)), corrupted
tool returns for 14 models including Gemma-4-31B with LoRA reliance tests ([2609.05587](https://arxiv.org/abs/2609.05587)),
planted look-alikes in SWE-bench repositories ([2605.26177](https://arxiv.org/abs/2605.26177)), and failure taxonomies
([2607.04686](https://arxiv.org/abs/2607.04686)). No verified work estimates where a provided code graph's information
is lost, stage by stage and by intervention, inside end-to-end repair on the graph's own tools. GraphLoc's traces show
the funnel is real and steep: in its base arm, 109 of 318 runs call a graph tool, only 26 ever receive a non-empty
result, and 114 of 135 `search_similar_code` calls return nothing. Across both arms, 128 of the 148 empty results came
from multi-word queries sent to a tool that only looks up node names, and every non-empty result came from a single
identifier (EXPLORATORY). **I recommend Direction 2, reframed as "why the organizers' graph
adds about one task"**, with push vs pull delivery and planted decoys as the two interventions. The pushed-memory idea
from the agent-architectures notes fits there as the delivery factor, not as a memory headline.

**Honest odds, all guesses.** If the paper presents itself as moving perturbation-based reliance tests into
tool-mediated code navigation, and cites the graph-ML precedents first, a careful judge rates the method novel for this
setting perhaps 50-60% of the time; pitched as a new kind of test, perhaps 20%. Overall Best Paper: perhaps 10-15% if
executed cleanly and early, against a field in which several visible entries report simulated results. Direction 1 as
the lead: lower, perhaps 5-10%.

## 1. Verdicts

| Claim | Verdict | Nearest works | What survives |
|---|---|---|---|
| **D1** graph as working memory under ~32k | **WEAKENED** | [2609.20804](https://arxiv.org/abs/2609.20804); StateTape [2609.36319](https://arxiv.org/abs/2609.36319); CodeNib [2607.25431](https://arxiv.org/abs/2607.25431); Prometheus [2507.19942](https://arxiv.org/abs/2507.19942); ContextSniper [2607.01916](https://arxiv.org/abs/2607.01916); SWE-MeM [2606.28434](https://arxiv.org/abs/2606.28434) | A controlled test with the organizers' names-only graph, a 4-bit open 31B model and patch loss at overflow, against elision and notes-file arms, a length-matched truncation control and an auto-submit control |
| 1a graph or symbol memory under a hard limit | WEAKENED | StateTape; Prometheus; CodeNib; ContextSniper; Codebase-Memory [2603.27277](https://arxiv.org/abs/2603.27277) | Code-graph memory for SWE repair under a hard small window where overflow is fatal |
| 1b overflow or lost work as the outcome | **KILLED** as novelty | 2609.20804; SWE-MeM; Context-Folding [2510.11967](https://arxiv.org/abs/2510.11967); CodeNib; one rival entry that tracks overflow in this harness | Usable as an outcome, with citation |
| 1c symbol pointers and exact re-fetch as a token saver | **KILLED** as novelty | CODESTRUCT [2604.05407](https://arxiv.org/abs/2604.05407); AutoCodeRover [2404.05427](https://arxiv.org/abs/2404.05427); Agentless [2407.01489](https://arxiv.org/abs/2407.01489); LocAgent [2503.09089](https://arxiv.org/abs/2503.09089); Aider repo map; LSP study [2608.13568](https://arxiv.org/abs/2608.13568) | Only re-fetch as a memory policy under a hard window; the provided tools cannot do it |
| 1d comparison with a notes file | OPEN (a control) | MOOSEDev [2608.13662](https://arxiv.org/abs/2608.13662); CAMG-RL [2609.34422](https://arxiv.org/abs/2609.34422); Delivery, Not Storage [2607.20972](https://arxiv.org/abs/2607.20972) | The none / notes / graph comparison |
| Graph as pushed, write-back memory | WEAKENED | StateTape (graph updated per write); Delivery, Not Storage (harness-delivered memory; 0 voluntary memory operations in 114 turns); RepoAtlas [2609.16936](https://arxiv.org/abs/2609.16936) vs SeeRepo [2606.14061](https://arxiv.org/abs/2606.14061); 2609.20804's recall tool | Push vs pull on the organizers' graph at 32k with a 31B open model; best used as a factor inside D2 |
| Patch-loss accounting | OPEN, but harness-specific | SWE-agent auto-submits on budget exhaustion [2405.15793](https://arxiv.org/abs/2405.15793); 2609.20804 does not say whether overflowed edits are scored | An EXPLORATORY side count, not a headline |
| **D2** why the graph does not help | **WEAKENED** | [2609.05587](https://arxiv.org/abs/2609.05587); [2010.12872](https://arxiv.org/abs/2010.12872); [2309.16595](https://arxiv.org/abs/2309.16595); Oracle Poisoning [2605.09822](https://arxiv.org/abs/2605.09822); Don't Blindly Trust It [2606.21409](https://arxiv.org/abs/2606.21409); GraphLoc; codegraph-loc | The integrated, intervention-based account on the organizers' own tools in end-to-end repair at the scoring setting |
| 2a corrupted-graph reliance test | WEAKENED | 2010.12872; 2609.05587; 2605.09822; 2606.21409; OKGQA-P [2410.08085](https://arxiv.org/abs/2410.08085); RepoMirage [2605.26177](https://arxiv.org/abs/2605.26177) | Decoy following scored against the true-graph base rate of visiting the same sibling, in multi-turn repair |
| 2b structure vs embeddings | WEAKENED | GNN is a Counter? [2110.03192](https://arxiv.org/abs/2110.03192); 2309.16595; LocAgent's tool ablation; competition audits (codegraph-loc, aghasalim, GraphLoc) | A causal factorial inside the agent; note that 21.9% of the provided vectors are exact duplicates (one audit), so an embedding permutation must be checked for effect |
| 2c four-way decomposition | WEAKENED | ToolFailBench [2607.04686](https://arxiv.org/abs/2607.04686); RAG failure points [2401.05856](https://arxiv.org/abs/2401.05856); ContextBench [2602.05892](https://arxiv.org/abs/2602.05892); Agents Explore but Agents Ignore [2604.17609](https://arxiv.org/abs/2604.17609); CodeCompass [2602.20048](https://arxiv.org/abs/2602.20048) | Each cell estimated by an intervention in one agent, rather than by labelling traces |
| 2d fine-tuning for reliance | WEAKENED | 2609.05587 (LoRA SFT changed Gemma-4-31B's adoption of corrupted search results by -6.1 points, interval -11.3 to -0.7); KAFT [2211.05110](https://arxiv.org/abs/2211.05110); RAMP [2603.14937](https://arxiv.org/abs/2603.14937); LocAgent | LoRA judged by whether the scramble-induced drop grows; expect a small effect of uncertain sign |
| "The graph misses async code and some fix sites" | KILLED as novelty | two public audits in this competition (async 0 of 45,593; 67 of 49,126, all name collisions) | Report the team's K1 as an independent replication |

## 2. What GraphLoc's public traces show (EXPLORATORY)

GraphLoc's end-to-end notebooks publish one trace per run: 3 runs x 2 agents x 106 tasks = 636 runs of
`gemma-4-31b-it-qat-w4a16-ct` in the official harness (subprocess sandbox on 4xL4; T=0.2; `max_output_tokens` 16,384;
thinking budget 4,096; compaction passed explicitly with `token_threshold` 14,336; 40 tool calls, 25 minutes, 60 turns
per task; wheelhouse version not recorded, runs dated Sep 25-28). The base agent is the sample-submission prompt with
all nine tools. I re-analyzed them with my own script (`analysis/graphloc_traces.py`, saved as a Claude Science
artifact; the hash is in LOG.md).

| Quantity | Base | Skill |
|---|---|---|
| Runs ending in `ContextWindowExceededError` | 14 / 318 | 12 / 318 |
| Runs calling any graph tool | 109 / 318 | 34 / 318 |
| Runs receiving any non-empty graph result | 26 / 318 | 16 / 318 |
| `search_similar_code` calls returning zero results | 114 / 135 | 34 / 38 |
| Re-read share of `read_file` characters | 27.0% | 28.7% |
| Re-read share of all characters entering the context | 10.3% | 11.0% |

Four things follow.
- **The prompt cap is 16,384 tokens, not 32,768.** vLLM's error reads that the prompt had at least 16,385 tokens while
  16,384 output tokens were requested. With the sample config, every request reserves half the window for output.
- **Overflow is spiky, not cumulative.** All 26 overflowed runs end with an empty patch (8 had already edited files).
  In 23 of them the last call is a `run_command` or `read_file` output of about 4-13k characters arriving at a prompt
  of 9.8k-14.2k tokens. The other 3 are one task (fastapi_14258) in every base run: the first call is
  `search_similar_code`, which returns 55,164 characters. The wheelhouse moved to v27 on Sep 30 with a "graph output
  cap", which should remove that case.
- **Compaction fires inside a single invocation in this setting.** 326 prompt drops of more than 30% occur in the base
  runs, while the harness sent only 7 continuation nudges in total; I read these drops as compaction (an inference).
  Whether the scoring script passes the compaction config at all is still open (one rival entry reports that the CLI
  default is `None`).
- **The graph is barely reached.** 92% of base runs never receive any graph content. The interface explains most of
  the gap: the prompt advertises `search_similar_code` as finding similar code "by keyword", the tool resolves only
  node names, and a miss returns status "ok" with zero results.

Also: GraphLoc's end-to-end summary over-counts tool calls (each count equals the true calls plus the share of traces
using the tool; for example `search_similar_code` 0.61 per task reported, 0.33 true, run 1 base). Its failure
taxonomy crosses edit location with failure reason and does not separate "never called the graph" from "called it but
ignored it" for the graph tools. For its own skill it records whether the skill ran and whether the patch edits a
listed candidate (38.5%), an observational version of the split.

## 3. The kickoff's named items

| Item | Status | What the paper or repo shows |
|---|---|---|
| [2609.20804](https://arxiv.org/abs/2609.20804), harness design | confirmed, one correction | Four open models, 32k-128k, SWE-Bench Verified and Terminal-Bench 2.1. Unmanaged overflow 78.7% at 32k. The store-and-recall arm is **rarely** used, not unused: 36 of 64 recall-enabled settings never call it; 0.540 calls per task at 32k; no accuracy gain over elision (-0.36 points). |
| SWE-MeM, [2606.28434](https://arxiv.org/abs/2606.28434) | confirmed | Learned span compression at a 32,768-token limit throughout; Qwen3-Coder-30B-A3B 60.2% and Qwen3-4B 43.4% on SWE-Bench Verified. |
| Codebase-Memory, [2603.27277](https://arxiv.org/abs/2603.27277) | corrected | A Tree-Sitter knowledge graph served over MCP, evaluated on structural questions (not bug fixing) with Claude Opus 4.6 and no context limit; about 1,000 vs 10,000 tokens per question at quality 0.83 vs 0.92, graded by the first author. |
| Code Isn't Memory, [2606.22417](https://arxiv.org/abs/2606.22417) | confirmed, one correction | Claude Opus 4.7, index / no index / agentic grep, 91 instances, three seeds: resolve 50.4% vs 41.9% (p=0.003). BRIEF.md's "mostly on multi-file tasks" holds for localization only, and only as an exploratory split; the resolve gain is largest on 1-file tasks. |
| [2608.13568](https://arxiv.org/abs/2608.13568), language-server study | corrected | Full title "Does a Language Server Save Tokens for Coding Agents? A Measurement Methodology and Preliminary Study"; single author; a tool-surface ablation with forced arms, so more than usage counts. 0-6% LSP use during localization is confirmed. No context cap. Location-only results cost 15.2 file reads per episode vs 3.2 with inline lines. |
| Don't Blindly Trust It, [2606.21409](https://arxiv.org/abs/2606.21409) | confirmed, one correction | Faithful / misleading / absent observations in a fixed ReAct loop; misleading is worse than none on every model. Besides HotpotQA and FEVER there is a GSM8K calculator pilot. Still no code. |
| Oracle Poisoning, [2605.09822](https://arxiv.org/abs/2605.09822) | corrected | 270 trials with one timeout: all 269 valid trials accepted the fabricated sanitiser, counting "Mixed" answers as trust (Claude Sonnet 4.6 strictly 80%). Open-ended prompts lower trust. A contradicting source-code tool cuts trust to 0-25% (N=10). |
| CodeCompass, [2602.20048](https://arxiv.org/abs/2602.20048) | confirmed, setting corrected | 51 of 88 graph-arm trials (58.0%) made zero graph calls despite an explicit instruction. The tasks are 30 hand-built tasks on one FastAPI example app, not SWE-bench; the agent is Claude Code (Sonnet 4.5). The listing and body titles differ. |
| Deterministic Anchoring, [2606.26979](https://arxiv.org/abs/2606.26979) | corrected | Interventional, not observational (tags present or absent, granularities, repeated runs, a repair test); accepted to ISSTA 2026 per its arXiv comment. The link-following rate is confirmed; there is no wrong-tag arm. |
| [2607.09691](https://arxiv.org/abs/2607.09691) | both descriptions right | An oracle-localization study (Claude Sonnet 4.6, single-shot, 70 multi-file instances, pre-registered). The ~9% flip rate is a side measurement from one re-run of one arm (6 of 70). Cite it as single-shot API inference; for this harness, cite GraphLoc's run-to-run spread (between-run SD about 3.4 points). |
| GraphLoc failure taxonomy | does not split | See section 2. |
| G-HRR | no experiments | Every number comes from code that never calls a model (random draws with hard-coded pass probabilities); its own CSV does not reproduce its paper's numbers. Do not cite as evidence. |
| GraphSWE-Gemma | no experiments | Template patches on 3 mock tasks; claims a "Gemma 4 9B" model that the competition does not offer. No Kaggle account under the given name was found. |
| codegraph-loc | real, different setting | Localization only, SWE-bench Lite, Gemma 4 E4B and 12B, graph on/off, paired bootstrap CIs. Its agents use the graph as a symbol index: 9 `callers` calls in 444 graph-arm episodes and no `callees` calls. It pre-empts the descriptive half of D2. |

Other entries found: one tracks `context_overflow` in this harness on a 12B proxy and plans a paper ("context is the
binding constraint"), which weakens 1b inside the competition; two publish CPU audits of the graph (async coverage,
duplicate vectors, unresolvable issue names); one claims sub-agent isolation gains from hard-coded numbers.

## 4. Section 5 of the agent-architectures notes

| Claim | Status | Evidence |
|---|---|---|
| 78.7% unmanaged overflow at 32k (2609.20804) | confirmed | Model-averaged, SWE-Bench Verified; elision lifts Nemotron-3 30B 9.4% to 20.6% and Mistral-Medium-3.5 12.6% to 64.4% (Table 3) |
| Recall tool unused in 56.3% of settings | confirmed, as settings | 36 of 64 recall-enabled settings never call it; per task it is called 0.540 times at 32k |
| RepoAtlas +2.3-4.4 and LocAgent +0.7-1.4 over mini-SWE-agent, LocAgent at 1.6-1.9x RepoAtlas's tokens | confirmed | Table 2: RepoAtlas 63.1 / 68.0 / 72.4 vs mini-SWE-agent 60.8 / 65.4 / 68.0; LocAgent 61.5 / 66.1 / 69.4 at 1,570.6K / 1,219.4K / 984.7K input tokens vs RepoAtlas's 909.3K / 647.0K / 630.3K (ratios 1.56-1.88) |
| "Push beats pull" | weakly supported | RepoAtlas and LocAgent differ in selection, budgets and modality, and the paper reports no CIs. The cleaner contrast is SeeRepo's on-demand views (requested in 40.5% of instances) vs RepoAtlas: +2.3, +1.1, +3.8. Delivery, Not Storage adds 0 voluntary memory operations in 114 turns despite a pre-seeded store, in a single-task study |
| Context-Folding at 32K: the ReAct baseline scores 43.6%, the summary agent 48.8%, and the folding agent 49.2% without RL and 58.0% with FoldGRPO (ReAct at 327K: 55.2%) | confirmed (corrected 2026-10-01: 43.6% is the ReAct baseline, not the folding agent) | Table 1, Seed-OSS-36B on SWE-Bench Verified |
| SWE-agent ablations (100-line viewer 18.0 vs full file 12.7; summarized search 18.0, iterative 12.0, none 15.7; linting +3.0; 90.5% to 57.2% after a failed edit) | confirmed | SWE-agent Table 3 and its editing analysis |
| Planning +11.6 points for Nemotron-3 30B; predefined tools +15.0 over bash-only | confirmed, with scope | Both measured under T4 at 128k, not at 32k |
| 68.6% of no-planning runs ended with no edit | not found | Not in the text I searched; check the figure before citing |
| "ADK compacts every N invocations, so a single scoring invocation never triggers it" | contradicted in GraphLoc's setting | See section 2; the scoring configuration still needs the harness source |
| "thinking_budget is never enforced" | mostly not, in GraphLoc's runs | 0.52% of base-arm agent steps exceed 4,096 completion tokens; one reaches 16,384. Thinking does not trigger the overflows there |
| Cheap LoRA SFT recipes (SWE-Gym, SWE-smith, LoRA Without Regret) | not checked | Verify before citing; for reliance, 2609.05587 is the nearest LoRA result on Gemma-4-31B |

## 5. Recommendation

**Lead with Direction 2, reframed as "why the organizers' code graph adds about one task".** The paper would estimate,
stage by stage, where the graph's information is lost between the tool and the patch: whether it is consulted, whether
the query resolves, whether the result carries fix-relevant structure, whether the agent acts on it, and what it costs
in context. Each stage gets an intervention rather than a label. Push vs pull delivery tests consultation and the
interface; a planted decoy edge tests whether the agent follows structure or ignores it, scored against the rate at
which it visits the same sibling under the true graph; the 13 decoy-bite tasks test content; the context accounting
tests cost.

Why this side, criterion by criterion:
- **Relevance.** It answers the organizers' own question about their own tools, and every stage is actionable for
  them (the interface mismatch, output caps, missing async nodes).
- **Novelty.** The pieces exist in KG QA, web tools and repository perturbation; the integrated, intervention-based
  account inside end-to-end repair on the provided graph does not. Related work should open with Raman et al. 2021,
  Wang et al. 2022, Huang et al. 2024 and 2609.05587.
- **Verifiability.** The observational funnel can be recomputed by anyone from GraphLoc's public traces, and the decoy
  test is pre-registered with per-episode outcomes, which have far more power than resolve rate at about 106 tasks.
- **Quality.** The funnel and the push/decoy design transfer to any agent tool.

**What to fold in from Direction 1:** the cost stage (the 16k prompt cap, spiky outputs, the graph output that
overflowed a task three times out of three) and an EXPLORATORY patch-loss count. **What to drop:** graph-as-memory as
the headline, and the LoRA unless the main runs finish early; 2609.05587 already reports LoRA reliance effects on
Gemma-4-31B, small and of mixed sign across models.

**Where the evidence is weak.** The funnel numbers come from GraphLoc's setting (40 calls, 25 minutes, 12 concurrent
workers, an older wheelhouse), not from scoring. A decoy test may find near-zero following; a pre-registered null is
still a result, but a less exciting one. Anyone can recompute the funnel from GraphLoc's traces, so speed matters. The
organizers may fix the tool description or the interface, which would date that finding but also confirm it.

## 6. Corrections for tracked files

For Claude Code or the team to apply; I have not edited these files.
1. **docs/prior-art.md, Talk like a Graph:** "Choosing the text encoding changed PaLM 62B accuracy on synthetic graph
   tasks by 4.8 to 61.8 points (best vs worst encoder), depending on task and prompt."
2. **FLAME:** student C programs; 62.7% top-1 when the pipeline returns the code with faulty lines tagged inline vs
   15.8% when the same pipeline outputs line numbers.
3. **The Position Curse:** the failure is backward and relative indexing; forward indexing approaches ceiling.
4. **LocAgent:** "comparable" accuracy (not "matches") at about 86% lower estimated cost ($0.09 vs $0.66 per example);
   the format study says 37 tasks but its percentages imply 34, Claude-3.5 only. It already returns entity IDs for
   large result sets and fetches code by ID, and LoRA-tunes on successful trajectories partly its own.
5. **RepoAtlas:** a pushed, budgeted view plus a textual index of exact symbols and locations, not only images; the
   text index matters more than the image (-3.9 vs -1.9 points).
6. **Context Language Models (2609.37725):** first author Rulin Shao, last author Pang Wei Koh; cite as Shao et al.
   2026.
7. **2608.13568:** full title as above; "usage, not reliance" undersells its forced arms.
8. **Oracle Poisoning, CodeCompass, Deterministic Anchoring, Don't Blindly Trust It, 2607.09691:** as in section 3.
9. **SWE-Bench Illusion:** ICSE-SEIP 2026 per CrossRef. Add an issue-only localization baseline to any reliance test,
   since models can name the file from the issue alone.
10. **KG-LLM-Bench** is a NAACL 2025 KnowledgeNLP workshop paper; GraphToken needs no "to verify".
11. **BRIEF.md:** "mostly on multi-file tasks" (Code Isn't Memory) and "the bottleneck nobody has studied here" are
    both out of date.
12. **docs/competition.md:** the wheelhouse is at v28 (Sep 30), not v25; v27 added a graph output cap.
13. **docs/claude-science-kickoff.md:** of the five "memory under a hard context limit" items, only 2609.20804 and
    SWE-MeM impose a hard cap; Codebase-Memory, Code Isn't Memory and the LSP study do not.

## 7. Open items

- **Harness source** (v28 and v25) from Claude Code: the scoring compaction config, the output reservation, graph-tool
  caps and de-duplication. Requested in LOG.md.
- **Graph tools in local runs:** confirm they appear in the prompt when only commit-named graph files exist.
- **Registration hygiene:** commit NOTES.md and `experiments/00-pointer-audit/`; future rules go in `prereg/` and are
  committed before their run.
- **Decision:** the team picks the direction. A draft pre-registration for the recommended one is in
  `prereg/01-graph-uptake-draft.md`; nothing in it is frozen.
