# Prior art

Built from an adversarial sweep on Sep 27, 2026: three agents, each told to find the paper that kills one idea.
Most were opened by those agents; four were checked at the abstract level by Claude Code on Sep 30 (marked ✓).
**Re-verify every entry from the paper itself before citing it.** The 2026 entries are arXiv preprints.

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
