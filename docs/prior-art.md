# Prior art

Built from an adversarial sweep on Sep 27, 2026: three agents, each told to find the paper that kills one idea.
Most were opened by those agents; four were checked at the abstract level by Claude Code on Sep 30 (marked ✓).
**Re-verify every entry from the paper itself before citing it.** The 2026 entries are arXiv preprints.

## ⚠️ Nearest work, same competition and same data: GraphLoc (found Sep 30)

**✓ zzgtylors, *"Where Does the Graph Help? A Localization Audit of the Gemma 4 Developer Agent Code Graphs"*.**
A paper-track writeup, with public notebooks under Apache-2.0:
- [audit](https://www.kaggle.com/code/zzgtylors/graphloc-auditing-gemma-4-agent-code-graphs)
- [can Gemma pick the code](https://www.kaggle.com/code/zzgtylors/graphloc-can-gemma-4-pick-the-code-to-change)
- [end to end](https://www.kaggle.com/code/zzgtylors/graphloc-end-to-end-gemma-4-agent-skill)
- [failure analysis and resource](https://www.kaggle.com/code/zzgtylors/graphloc-end-to-end-failure-analysis-resource)

What it covers (confirmed from the notebooks):
- GraphLoc-129 gold labels at function and file level
- an audit of the graph's structure
- embedding probes
- BM25 vs simulations of the graph tools vs personalized PageRank, on the provided graph and a repaired one
- transfer to SWE-bench Lite
- a `graph-localize` skill
- end-to-end runs with a failure taxonomy and run-to-run variance

Its reported results (read from the rendered pages by an agent; re-check before citing):
- the graph does about as well as BM25 at localization
- the provided embeddings do worse and encode graph position more than code text
- the graph skill adds +0.9 points end to end, 95% CI −4.1 to +6.3

**It covers our old Q1 ("when does structure help localization").** It has no corrupted-graph test of reliance,
no training, and nothing on the graph as memory under context limits. Its labels and library are Apache-2.0, so we
can build on them with citation instead of rebuilding them.

## Closest to our topic (code graphs for agents; reliance on tools)

| Work | What it does | What it leaves open for us |
|---|---|---|
| ✓ *Code Isn't Memory: A Structural Codebase Index Inside a Coding Agent*, arXiv [2606.22417](https://arxiv.org/abs/2606.22417) (Jun 2026) | Claude Opus 4.7, three arms (index / no index / agentic grep) on SWE-PolyBench Verified and SWE-bench Pro. Large localization gain, a resolve gain, value depends on multi-file work. | One frontier model; on/off arms; no separation of structure vs semantic retrieval; no reliance test. |
| ✓ *LocAgent*, ACL 2025, arXiv [2503.09089](https://arxiv.org/abs/2503.09089) | Heterogeneous code graph plus traversal tools for localization. Fine-tuned Qwen2.5-Coder-32B matches proprietary models at about 86% lower cost. Appendix compares six graph text formats (37 tasks). | Accuracy, not reliance; small format study, one model, no patch outcome. |
| *Oracle Poisoning*, arXiv [2605.09822](https://arxiv.org/abs/2605.09822) | Poisoned MCP code knowledge graph accepted in 269/270 directed-query trials; a source-code tool cuts trust. | Security scenarios, rater-coded trust; no bug-fixing, no removed-tool arm, no chance baseline. |
| *Deterministic Anchoring*, arXiv [2606.26979](https://arxiv.org/abs/2606.26979) | Call/inheritance tags on SWE-bench; "link following rate". | Observational only; no corrupted graphs. |
| *CodeCompass*, arXiv [2602.20048](https://arxiv.org/abs/2602.20048) | 58% of graph-arm trials made zero graph calls despite instructions. | Usage counts, not causal reliance. |
| *Does a Language Server Save Tokens?*, arXiv [2608.13568](https://arxiv.org/abs/2608.13568) | 0-6% language-server use during localization. | Usage, not reliance. |
| *Don't Blindly Trust It*, arXiv [2606.21409](https://arxiv.org/abs/2606.21409) | Our exact faithful / misleading / absent observation design for tools; misleading tools do worse than no tool. | HotpotQA and FEVER only, not code. |
| *When Retrieval Hurts Code Completion*, arXiv [2605.14478](https://arxiv.org/abs/2605.14478) | Current / stale / none repository context on httpx, requests, rich, click, flask. | Single-turn completion, no tools, no agent. |
| *CodeCrash*, NeurIPS 2025, arXiv [2504.14119](https://arxiv.org/abs/2504.14119) | Comments that contradict code mislead models. | Single-turn. |
| *RepoGraph*, arXiv [2410.14684](https://arxiv.org/abs/2410.14684); *RepoAtlas*, arXiv [2609.16936](https://arxiv.org/abs/2609.16936) | Graph context for SWE agents (flattening depth; rendered graph images). | Help-or-not, not why. |

Also: ClashEval and "Adaptive Chameleon or Stubborn Sloth" (knowledge conflicts in retrieval QA). One entrant
posts graph on/off ablations: github.com/Benadict-Git/codegraph-loc.

## The judges' own line of work

| Work | Relevance |
|---|---|
| ✓ Fatemi, Halcrow, Perozzi, *Talk like a Graph: Encoding Graphs for Large Language Models*, ICLR 2024 ([poster](https://iclr.cc/virtual/2024/poster/18954), [blog](https://research.google/blog/talk-like-a-graph-encoding-graphs-for-large-language-models/)) | Graph text encodings swing LLM accuracy by 4.8% to 61.8%. |
| ✓ Markowitz et al., *KG-LLM-Bench*, arXiv [2504.07087](https://arxiv.org/abs/2504.07087) | Textualization strategies for knowledge graphs change LLM reasoning. |
| Markowitz et al., *Tree-of-Traversals* (ACL 2024) | Zero-shot LLM reasoning over knowledge graphs. |
| Perozzi et al., *Let Your Graph Do the Talking* (GraphToken, 2024) | Learned graph encoder as soft tokens. To verify. |

## Memory framing

- Lambert and colleagues, *Context Language Models*, arXiv [2609.37725](https://arxiv.org/abs/2609.37725): models
  edit their own context for long-horizon memory. Self-managed context, a contrast with external structured memory.

## Addressing conventions (idea B, dropped as a headline)

- *FLAME*, ASE 2025, arXiv [2509.25676](https://arxiv.org/abs/2509.25676): asking for line numbers gives 15.8% top-1
  localization, marking lines in the code gives 62.7%, with the same faults.
- *To Diff or Not to Diff?*, arXiv [2604.27296](https://arxiv.org/abs/2604.27296): line-addressed diffs underperform
  anchored or AST formats.
- *The Position Curse*, arXiv [2605.07127](https://arxiv.org/abs/2605.07127): position-based retrieval fails.

## Probing agent internals (idea C, dropped)

- LLMAO (ICSE 2024, [2310.01726](https://arxiv.org/abs/2310.01726)); BAP ([2502.13966](https://arxiv.org/abs/2502.13966)).
- *Latent Programming Horizons in Coding Agents* ([2607.05188](https://arxiv.org/abs/2607.05188)).
- *SWE-Pruner Pro* ([2607.18213](https://arxiv.org/abs/2607.18213)).
- *TACT* ([2605.05980](https://arxiv.org/abs/2605.05980)): steering Gemma-4-26B coding agents.
- *SWE-Bench Illusion* ([2506.12286](https://arxiv.org/abs/2506.12286)): models name buggy files from issue text alone.
- Run-to-run variance: identical runs at T=0 flip about 9% of outcomes ([2607.09691](https://arxiv.org/abs/2607.09691)).

## Competition forum threads read on Nov 10, 2026 (main competition and paper track)

Read by Claude Code in a signed-in browser; searched in the main competition's discussion for `start_line`, `argument`,
`tool call parser`, `silently`, `read_file` and `get_code_neighbors`. Thread numbers are the ids in the URL
`kaggle.com/competitions/gemma-4-developer-agent/discussion/<id>`.

- **744272, "Tool results reach the model double-JSON-encoded" (about Oct 1).** The swegemma tools returned a JSON
  string, the agent framework wrapped it as `{"result": <string>}`, the client library serialized that again, and the
  chat template put the string verbatim into the tool response. The post proposed returning a dictionary. Kaggle
  staff answered that the fix is in the Sep 30 wheelhouse: tool results now reach the model as one level of JSON, and
  `edit_file` retries a match with escapes removed.
  - **A fixed-context test in the same thread:** a participant held 30 real edit contexts fixed, varied only how the
    `read_file` observation was encoded, and sampled the next call three times per condition: failed `edit_file`
    calls were 22% with the double encoding, 62% with one level of JSON and 0% with raw text; "a call that loses an
    argument because a string was closed with a backtick" stayed (4 of 45 with the double encoding, 7 of 40 with one
    level).
  - **What this means for us.** (1) It is the public source for the rendering difference that experiment F tests,
    and it dates the change (Sep 30, harness v28). (2) It is a small precedent for our method: fixed real contexts,
    one observation re-encoded, the next call sampled. Cite it. (3) It reports failed edits and one kind of lost
    argument under one level of JSON. It does not report mangled line-bound names in `read_file`, their silent
    removal by the agent framework, or rates on reads.
- **745731, "Notes on the graph tools from auditing all 127 graphs" (about Oct 9).** `get_code_neighbors` matches
  exact ids only; the neighbor list does not say which way an edge goes, is sorted alphabetically and cut at 50;
  edges are stored in both directions and classes are linked to their members; no graph has an async def and calls
  through `self` are missing; the released graphs hold 14% to 21% of recorded call pairs in three repositories; the
  embeddings follow graph distance more than code text. It names earlier reports of the missing async defs (thread
  742911) and of exact-name matching (745220). No agent behavior is measured. Cite it for the tool facts we use
  (alphabetical order, missing async defs).
- **755291, "Where 76% of a 300-second agent budget actually goes" (Nov 3).** Notes that `read_file` truncates at
  150 lines: a 754-line file "was read 6 times, still never fully seen", and 1,152 lines were fetched twice in four
  runs. It attributes this to the cap and prompt habits. Consistent with our reading that ranged reads return the
  top of the file when the bound's name is mangled; the post does not identify that cause.
- **Tool-call parser reports** (745138, 746336, 753521, 753973): hangs and dropped calls in the server's Gemma 4
  parser. None describes argument names with a stray quote.
- **Paper track, "CodeGraphQA (how Gemma 4 reads code graphs)" (Nov 4):** a pre-registration hash only; the document
  is not public. By its title it is question answering over the graphs.
- **Not found in these searches:** any report that a line-bound argument arrives under a mangled name and is
  dropped, or any test of the neighbor list's encoding inside an agent run.
