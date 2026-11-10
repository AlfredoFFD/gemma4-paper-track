# Prior-art check: the encoding claim (Nov 9, 2026)

[Claude Code] Adversarial check of the Experiment B headline before it enters the paper.

## Claim checked

At a paused navigation step, Gemma-4-31B does not act on the competition graph tool's bare neighbor names, but
follows the same neighbors about four times above its base rate when each entry carries file:line and a signature,
and does not follow a degree-preserving rewired list in the same encoding.

Components: C1 setting (competition harness, Gemma-4-31B, `get_code_neighbors`); C2 paused-run one-step forks
scored against a base rate; C3 encoding varied on the same neighbor set; C4 rewired graph shown to the agent;
C5 false edge under the legible encoding.

## Verdict

**Open in what we searched, with one part already known.** That the presentation of tool output changes what a
coding agent does is established (RepoNav; the tool-architecture study; the small-agent graph study). Do not claim
it. What none of the five works does: vary only the encoding of one fixed set of graph edges (C3), measure the
next action at a paused state against the no-list base rate (C2), or show the agent a rewired graph as a control
(C4) or a false edge (C5). Confidence: moderate. All reads below are partial; two papers were read at abstract
level only.

Consequences for the draft:
1. Cite 2610.33958 as the nearest work and say plainly that its graph tool already prints signatures and
   `path:QualifiedName` ids, so "legible output" is its default, not its manipulation.
2. Frame the contribution as the causal, step-level test (same edges, two encodings, rewired control), not as
   "format matters".
3. 2610.33958 reports that forcing the graph call does not help and that agents "expand once and stop"; our
   directive arms (D, D') and the base rate speak to the same point from a different design. Say so.

## Closest work

| Work | What it does | What it does not do (vs our claim) | Read |
|---|---|---|---|
| arXiv 2610.33958, How Do Small Coding Agents Use Code Graphs and Embeddings? | SWE-bench Verified, localization-only agent, own harness; Qwen3 0.6B-32B, Gemma 4 E2B/E4B; arms differ by tool set (grep / +embedding / +graph / both); trace analysis of which tool first reveals the gold; forced-tool, budget, repair, linear probes. Graph tool prints `[hop h] u --calls--> v signature`. | No Gemma-4-31B, not the competition graph or harness (C1). No forks or one-step replays (C2). Encoding is fixed, not varied (C3). No rewired or false graph shown to the agent; the only permutation control is for the probes (C4, C5). | partial |
| arXiv 2609.08355, RepoNav | Reorganizes retrieved snippets into a file-centered scaffold; ablations attribute the gain to organization, not volume (function Acc@5 32.6 to 47.0 to 52.1, as quoted in 2610.33958). | Search results, not graph edges; end-to-end localization, no step-level base rate (C2); no rewired or false structure (C4, C5). Nearest to C3 in spirit. | abstract + grep |
| arXiv 2611.07286, How Should Agents See Code? | Claude Code with Haiku 4.5; five on-demand repository views (AST, call graph, deps, docs, hybrid) over MCP; four benchmarks; success, tokens, time. | Compares which structure is exposed, not how one structure is encoded (C3); no forks, no perturbed graph (C2, C4, C5). | partial (abstract, method section) |
| arXiv 2608.11386, The Devil Is in the Interface | Six tool architectures with similar capabilities, three actors, 11,700 trajectories; architecture changes consistency, exploration, cost. | No code graph; trajectory-level outcomes; no perturbed tool content. | abstract + grep |
| Zenodo 10.5281/zenodo.23927441, AST-Compressed Code Graphs for Gemma 4 Agents (same paper track) | Gemma 4 E4B, SWE-bench Lite localization; a budgeted signature map in the prompt beats snippet RAG; adding call edges did not help (function accuracy 0.09 lower). | Prompt map, not the competition graph tools or harness; no forks; no perturbed graph. Agrees with us that signatures carry the value and bare call edges do not. | abstract |
| arXiv 2503.09089, LocAgent | Graph-guided localization with entity search, traversal and retrieval tools. | End-to-end; no encoding manipulation, no perturbed graph. | already in docs/prior-art.md |

## Coverage grid

| | 2610.33958 | 2609.08355 | 2611.07286 | 2608.11386 | Zenodo | LocAgent |
|---|---|---|---|---|---|---|
| C1 setting | x | x | x | x | ~ (track, other model and data) | x |
| C2 paused forks vs base rate | x | x | x | x | x | x |
| C3 encoding varied, same edges | ~ (legible by default) | ~ (search results) | x | ~ (tool layout) | ~ (map contents) | x |
| C4 rewired graph shown | x | x | x | x | x | x |
| C5 false edge | x | x | x | x | x | x |

## What would falsify "open"

A paper that shows an agent the same graph neighborhood in two encodings and scores its next action, or that feeds
an agent a shuffled or rewired code graph as a control. Not found by grep for shuffle, rewire, random graph,
corrupt, perturb, decoy, false edge, fork, replay in the four full texts on disk.

## Coverage lines

- 2610.33958: read lines 73-93, 419-437, 1310-1320, 1549-1552, 1860-1871 of 4,559 plus headings and term grep.
  Figures 0, tables 0, appendix no. checked: partial.
- 2611.07286: read lines 43-50, 168-262 of 1,566 plus headings and term grep. checked: partial.
- 2608.11386: abstract and term grep over 2,641 lines. checked: abstract.
- 2609.08355: abstract and term grep. checked: abstract.
- Zenodo 23927441: record description (abstract) only; PDF not downloaded. checked: abstract.

## Verification

`lit.py verify-file`, Nov 9: 2610.33958 OK, 2611.07286 OK, 2608.11386 OK, 2503.09089 OK. The Zenodo DOI returned
404 from the verifier; the record was confirmed directly from the Zenodo API (title, date 2026-11-03). 2609.08355
was found by search (Semantic Scholar) and its full text fetched; not run through verify-file.

## Not searched

Citation expansion on the seeds was not rerun for this claim. Other paper-track writeups on Kaggle were not
swept beyond the Zenodo entry. Paywalled venues, patents.
