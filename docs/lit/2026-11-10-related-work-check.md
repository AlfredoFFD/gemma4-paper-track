# Citation check: claims about other work in `paper/draft.md` (Nov 10, 2026)

[Claude Code] Sentence-by-sentence check of every clause in the draft (version at commit e847c40) that attributes
a finding, design or number to someone else's work, against what is on disk. Nothing in the draft was edited.

## Verdict

28 claims checked. 18 SUPPORTED, 8 PARTLY, 1 UNSUPPORTED, 1 NOT CHECKED (a judgment, not a fact).

Fix before submission, in order of risk:

1. **Section 1, GraphLoc's arm is misdescribed (UNSUPPORTED).** "adding the graph tools moves the resolve rate"
   is wrong. GraphLoc's base arm already has all nine tools, the graph tools included. Its +0.9 points is base vs
   base plus its own `graph-localize` skill. The draft's own Section 2 says the base agent calls graph tools in
   109 runs, so a judge can catch this from the draft alone. The abstract's first sentence rests on the same
   comparison (row 1).
2. **The novelty sentence in Section 7 is open to a direct counterexample (PARTLY).** LocAgent's Appendix A.1.2
   (Table 9) shows an agent its graph tool's output in six text encodings and scores localization: 37 hard
   SWE-Bench-Lite tasks, Claude-3.5. Read alone, "no work shows an agent one fixed set of graph edges in two
   encodings" is false. The draft cites LocAgent only as "end to end". LocAgent also finds that adding entity
   attributes to each node *lowers* accuracy ("row (w/ entity attributes)" vs "row"), the opposite direction from
   our E arm. A judge who knows LocAgent will ask about it.
3. **Zenodo entry (PARTLY).** It never tests bare call edges. It adds callee lists to a signature map (function
   accuracy 0.09 lower), and it partly blames budget displacement and its own name-only resolver.
4. **2609.05587, 2606.14476, the GraphLoc and GraphAudit framing (PARTLY):** wording drifts beyond the evidence.
   Replacements are in the table.
5. **Omission.** *Talk like a Graph* (Fatemi, Halcrow, Perozzi, ICLR 2024), the organizers' own paper on how a
   graph's text encoding changes LLM accuracy, is not cited. `paper/README.md:20` plans it, `docs/prior-art.md:56`
   has it, and LocAgent cites it for exactly this motivation (LocAgent App. A.1.2). It costs one clause.

## Claims

Line numbers refer to `paper/draft.md`. Full texts are local copies outside the repo (arXiv HTML text, not
redistributed), cited below as `FT/<id>.txt:line`. LocAgent was fetched in this session with `lit.py fulltext`
(cited as `LA:line`).

| # | Draft wording (line) | Work | Evidence (location) | Verdict | Replacement (same length or shorter) |
|---|---|---|---|---|---|
| 1 | "The competition's code graph barely changes what its Gemma-4-31B agent resolves" (L11) | GraphLoc | The only end-to-end comparison is base vs base + graph skill (`docs/competition.md:201,205`; `LOG.md:164`). No arm without the graph tools exists. | PARTLY: no graph-vs-no-graph comparison exists | "A graph skill barely changes what the competition's Gemma-4-31B agent resolves." |
| 2 | "The most careful public entry so far, GraphLoc" (L26-27) | GraphLoc | No basis on disk for ranking care. GraphAudit, also read in full, is public too. "Closest" is supported: GraphLoc is the only work that fully covers our setting (`docs/lit/2026-10-27-delivery-lit-sprint.md:90`). | NOT CHECKED: a judgment | "The closest public entry, GraphLoc," |
| 3 | "found that adding the graph tools moves the resolve rate by about one task in a hundred" (L27-28) | GraphLoc | Base arm = "all nine tools" (`LOG.md:187`; `NOTES.md` Nov 8 18:40 entry: "the sample prompt with the nine tools"); comparison = "base 28.9% vs graph skill 29.9%" (`docs/competition.md:201,205`); "a graph skill adds about one task" (`prereg/01-graph-uptake-draft.md:12`); the draft's own L44 (base agent calls graph tools in 109 runs). | UNSUPPORTED: wrong arm | "found that adding its graph-localization skill moves the resolve rate by about one task in a hundred" |
| 4 | "(28.9% to 29.9%, interval −4.1 to +6.3 points)" (L28) | GraphLoc | "base resolves 92/318 (28.9%) and skill 95/318 (29.9%): +0.9 points, 95% CI -4.1 to +6.3 (paired task bootstrap pooled over 3 runs)" (`LOG.md:164-165`, verified from GraphLoc's printed notebook outputs). | SUPPORTED. The difference is +0.9, not 1.0, from rounded endpoints. | - |
| 5 | "GraphLoc published 636 traces (3 runs, 106 tasks, two agents) made with the competition harness and model" (L41) | GraphLoc | 3 x 2 x 106 = 636 traces from public notebooks (`LOG.md:160-162`); official swegemma (`LOG.md:167`); the trace files carry `gemma-4-31b-it-qat-w4a16-ct` (grep over `data/graphloc/out`, this session). | SUPPORTED | - |
| 6 | Section 2 bullets (L44-50): counts in GraphLoc's traces | own analysis | Not a citation. Cross-check only: 109 / 26 / 135 / 114 / 8 / 0 and 68% match `LOG.md:187-193` and `NOTES.md` (Nov 8 19:20); 27% vs 23% matches `NOTES.md` (Nov 8 21:35). 84% / 10% / 19% not checked. | SUPPORTED (as far as checked) | - |
| 7 | "The nearest study measures how small coding agents use code graphs and embeddings in a localization harness" (L212) | 2610.33958 | Title; localization-only agent in its own harness (`FT/2610.33958.txt:403`); Qwen3 0.6B-32B and Gemma 4 E4B (`:479`). | SUPPORTED | - |
| 8 | "its graph tool already prints signatures and qualified paths" (L213) | 2610.33958 | `find_entity`: "one line per hit with its signature" (`:427`); `graph_neighbors`: "[hop h] u --calls--> v signature" (`:431`); node id = `path/to/mod.py:Class.method` (`:112`). | SUPPORTED | - |
| 9 | "it varies the tool set rather than the encoding" (L213) | 2610.33958 | "arms differ only in their tool set: G, E, T, ET" (`:37`); tool output fixed as lines (`:407`); its own related work says its T arm "presents structure in the plainest way" (`:85`). | SUPPORTED | - |
| 10 | "reports that forcing the graph call does not help" (L214) | 2610.33958 | §5.7: forcing find_entity then graph_neighbors moves T from 23.7 to 21.8% (Qwen3-8B, p=0.61) and 30.8 to 29.5% (Qwen3-4B, p=0.80) (`:1551`). | SUPPORTED (4B and 8B only) | - |
| 11 | "and that agents expand once and stop" (L214) | 2610.33958 | Stated in §7: "Since agents expand once and stop" (`:1862`); measured in §5.3: Qwen3-32B asks for two hops in 0 of 263 graph_neighbors calls and chains expansions in 0.7% of episodes (`:1138`). | SUPPORTED | - |
| 12 | "Our instruction arms agree from a different design." (L214-215) | 2610.33958 | Interpretation. ForceTool forces the call and scores final localization; our D arm instructs reading the neighbors and scores the next call. Both find that forcing or instructing adds little. | SUPPORTED (as interpretation) | - |
| 13 | "RepoNav attributes localization gains to how retrieved snippets are organized" (L215-216) | 2609.08355 | Abstract: "gains come from structured evidence organization rather than simply exposing additional file structure" (`FT/2609.08355.txt:41`); §4.3 RQ2: only presentation differs, function Acc@5 32.61 → 46.96 → 52.13 (GPT-OSS-120B, 560 LocBench tasks) (`:497-540`). | SUPPORTED | - |
| 14 | "other work compares which repository views are exposed (2611.07286)" (L216) | 2611.07286 | Abstract: five code-representation workflows (AST, call graph, module deps, docs, hybrid), Claude Code with Haiku 4.5, four benchmarks (`FT/2611.07286.txt`, Abstract). | SUPPORTED | - |
| 15 | "and tool architectures (2608.11386)" (L216-217) | 2608.11386 | Abstract: "comparing six tool architectures ... across three actors and a total of 11,700 trajectories" (`FT/2608.11386.txt`, Abstract). | SUPPORTED | - |
| 16 | "a same-track entry finds that signatures carry the value and bare call edges do not" (L217-218) | Zenodo 10.5281/zenodo.23927441 | Record description: title ends "(Gemma 4 Developer Agent Paper Track)"; signature map File@1 0.527 vs snippet RAG 0.380; the variant that *adds* callee lists and control-flow counts is 0.04 lower on File@1 (n.s.) and 0.09 lower on Func@1 (p Holm 0.002); "every callee list pushes another symbol out of the map"; "edges hurt result applies to this resolver and serialization"; at function level snippet RAG equals the signature map (0.227 vs 0.235). Source: the Zenodo API record (`record.json`, local copy outside the repo). | PARTLY: bare call edges never tested; edges were added on top of signatures; the paper scopes the result to its resolver and budget | "a same-track entry finds a signature map beats snippet RAG and adding call edges to it does not help" |
| 17 | "LocAgent builds graph-guided localization end to end (2503.09089)" (L218) | 2503.09089 | True as far as it goes (`LA:72`, §3). But App. A.1.2 and Table 9 compare six text formats of the TraverseGraph output (row, row with entity attributes, incident, Graphviz DOT, JSON, tree) on 37 hard SWE-Bench-Lite tasks with Claude-3.5. Tree and JSON do best; adding entity attributes to "row" lowers module Acc@5 from 61.8 to 50.0 (`LA:1251-1362`). | PARTLY: omits its graph-encoding comparison, the closest prior result to our E arm | "LocAgent builds graph-guided localization and compares six text formats of its graph output (2503.09089, App. A.1.2)" |
| 18 | "That tool output format changes agent behavior is therefore known." (L218-219) | 13-17 | RepoNav RQ2; 2608.11386 abstract; LocAgent Table 9. | SUPPORTED, more strongly once LocAgent's Table 9 is cited | - |
| 19 | "handed-over search content is used more than fetched content on this model (2609.05587)" (L219-220) | 2609.05587 | Note: for Gemma-4-31B, the same *corrupted* search content pushed into the prompt is adopted more than when the agent's own tool call returns it: +17.3 (User) and +19.1 (RAG) points (Table 3, §4.4; `docs/lit/2026-10-27-delivery/notes/2609.05587.md:199-204`). The note says this is confounded with tool access, query provenance and repetitions, as the paper itself states (`:357`, `:366`). Code-executor content reverses (`:205-206`). | PARTLY: the content is corrupted, the measure is adoption, and the contrast is confounded | "pushed corrupted search results are adopted more than tool-returned ones on this model (2609.05587)" |
| 20 | "a harness-inserted tool result is trusted like a real call (2605.09822)" (L220-221) | 2605.09822 | Table 7: the "simulated" mode (the harness writes a role-tool message) equals real SDK tool use for all three models tested (GPT-5.1 100/100, Claude Sonnet 4.6 100/100, GPT-4o 100/100; N = 30 per cell); trust = a verbal verdict (note `2605.09822.md:146-148`, `:355`, `:385`). | SUPPORTED (three API models, N = 30, verbal trust) | optional: "...trusted like a real call by three API models (2605.09822)" |
| 21 | "small agents agree with a wrong graph tool (2606.14476)" (L221) | 2606.14476 | The tool is a frozen GNN node classifier on ogbn-arxiv and WikiCS, not a code graph. Qwen2.5-7B agrees with it on 0.976-0.992 of nodes (Table 1) while the GNN is wrong on 29-70% of them. Agreement is never conditioned on the GNN being wrong (the ≥96% bound is the note's arithmetic). Mistral-7B and OLMo-2-7B agree only 0.53 and 0.60 (§9) (note `2606.14476.md:14-20`, `:199`, `:219`). | PARTLY: "graph tool" reads as a code-graph tool; the effect is Qwen-specific in size | "small Qwen agents copy a GNN tool's often-wrong labels (2606.14476)" |
| 22 | "fork designs exist for tool results in scientific QA (2610.26836)" (L221-222) | 2610.26836 | Paired fork from a saved GPT-5.2 state that varies only the pending observation; geochemistry (PHREEQC) MCQ: −9.4 pp [−14.5, −4.6] (App. D, Table 10; note `2610.26836.md:12-17`, `:470`). | SUPPORTED | - |
| 23 | "and after compaction (2609.36526" (L222) | 2609.36526 | PAIR forks from the same restored state at each compression boundary, PRE vs POST context (§3.2; note `2609.36526.md:12`). | SUPPORTED | - |
| 24 | "2610.31710)" (L222) | 2610.31710 | Compact-Bench: PRE (full history) vs POST (summary) continuations from the same restored snapshot in SWE-bench repairs (§3.1, Fig. 1; note `2610.31710.md:13-14`). | SUPPORTED | - |
| 25 | "GraphLoc and GraphAudit ask whether this graph helps end to end and in retrieval" (L222-223) | GraphLoc, GraphAudit | GraphLoc is titled "A Localization Audit": gold labels, BM25 vs embeddings vs PageRank, SWE-bench Lite transfer, plus end-to-end runs (`docs/competition.md:192-202`). GraphAudit is a retrieval study plus a one-shot file choice by Gemma 4 8B Q4 (`docs/lit/2026-10-27-delivery-lit-sprint.md:416-421`; `NOTES.md:443`). | PARTLY: GraphLoc's main question is localization, not only end to end | "GraphLoc asks whether this graph helps localization and repair, GraphAudit whether it helps retrieval" |
| 26 | "the rewiring control is GraphAudit's" (L223) | GraphAudit | "degree-preserving random graphs as the null"; real minus random file recall +3.1 points [+0.7, +5.6] (`docs/lit/2026-10-27-delivery-lit-sprint.md:152-155, 417`; `NOTES.md:443`). | SUPPORTED (note level; writeup not on disk) | - |
| 27 | "In what we searched (queries and dates in `docs/lit/`)" (L223-224) | own | Query logs for Oct 27 and Oct 28 are in `docs/lit/2026-10-27-delivery/lit_search_log.jsonl` and `docs/lit/2026-10-28-memory/lit_search_log.jsonl`. The Nov 9 encoding search (the one behind this sentence) has its log (`lit_search_log.jsonl`, entries from 2026-11-09T17:33) only in a local scratch folder outside the repo. | PARTLY: the Nov 9 queries are not in the repo | copy the Nov 9 log to `docs/lit/2026-11-09-encoding/` (no wording change needed) |
| 28 | "no work shows an agent one fixed set of graph edges in two encodings, or a rewired graph, and scores its next action against a no-list base rate" (L224-225) | novelty claim | Holds if read as "(two encodings or rewired) AND next action vs base rate". Its first clause read alone is contradicted by LocAgent Table 9 (row 17): six encodings of graph tool output shown to an agent, though as whole runs with the agent's own traversals, not one fixed edge set, and scored on final localization. No paper on disk shows an agent a rewired graph (`docs/lit/2026-11-09-encoding-claim-prior-art.md:53-57`; GraphAudit's rewiring is never shown to a model, `NOTES.md:443`). | PARTLY: true only under the narrow reading | "no work fixes one set of graph edges, varies only its encoding or rewires it, and scores the agent's next action against a no-list base rate" |

## Existence checks (`lit.py verify <id> --title <title>`, Nov 10)

Two rounds on Nov 10 (the second spaced 30 s apart). The arXiv API timed out or returned HTTP 429 for most ids,
so the table also gives the most recent earlier result and the arXiv header line of any full text fetched from
arXiv.

| id | Nov 10 | Earlier `lit.py` result | arXiv header of fetched full text | Standing |
|---|---|---|---|---|
| 2610.33958 | ERROR_RETRY x2 (timeout) | OK, Nov 9 verify-file (`2026-11-09-encoding-claim-prior-art.md:70`) | v1 [cs.SE] 25 Oct 2026 | exists |
| 2609.08355 | ERROR_RETRY x2 (429, timeout) | never verified (found by search, Nov 9 report :71) | v1 [cs.SE] 08 Sep 2026 | exists (arXiv HTML fetched); no verify pass on record |
| 2611.07286 | OK, title match 1.0 | OK, Nov 9 | v1 [cs.SE] 05 Nov 2026 | OK |
| 2608.11386 | OK, title match 1.0 (round 2) | OK, Nov 9 | v1 [cs.SE] 11 Aug 2026 | OK |
| 2503.09089 | OK, title match 1.0 (round 2) | OK, Oct 27 and Nov 9 | v2 [cs.SE] 29 Apr 2025 | OK |
| 2609.05587 | ERROR_RETRY x2 (timeout) | OK, Oct 27 (`2026-10-27-delivery/verify_out.txt`) | not fetched | OK on Oct 27 |
| 2605.09822 | ERROR_RETRY x2 (timeout) | OK, Oct 27 | not fetched | OK on Oct 27 |
| 2606.14476 | ERROR_RETRY x2 (timeout, 429) | OK, Oct 27 | not fetched | OK on Oct 27 |
| 2610.26836 | ERROR_RETRY x2 (timeout) | OK, Oct 27 | not fetched | OK on Oct 27 |
| 2609.36526 | ERROR_RETRY x2 (timeout) | OK, Oct 27/28 | not fetched | OK on Oct 28 |
| 2610.31710 | ERROR_RETRY x2 (timeout) | OK, Oct 28 (`2026-10-28-memory/verify_out.txt`) | not fetched | OK on Oct 28 |

No id failed on a title mismatch or a missing record. Every failure was a network error. Before submission, run
`lit.py verify 2609.08355` once more: it is the only id cited in the draft with no verify pass on record.

The Zenodo id 10.5281/zenodo.23927441 is the concept DOI (all versions). The v1 record is
10.5281/zenodo.23927442 (`record.json`: `conceptdoi` 23927441, `doi` 23927442, published 2026-11-03). The verifier
returned 404 on the concept DOI on Nov 9 (`docs/lit/2026-11-09-encoding-claim-prior-art.md:70`). Citing the
concept DOI is valid. Citing 23927442 pins the version that was read.

## Depth of reading behind each verdict

| Work | What was read for this check | Depth |
|---|---|---|
| 2610.33958 | Full text on disk (4,559 lines): abstract, §1 (L37, L53), related work L83-85, §3.1 L112, §4.1-4.2 L403-431, §5.3 L1138, §5.7 L1549-1551, §7 L1850-1862, all headings; term greps (forc, expand, signature, qualified, format). | sections |
| 2609.08355 RepoNav | Full text on disk: abstract and §4.3 (RQ2) text with table and figure captions; table cells not read. | abstract + one section |
| 2611.07286 | Full text on disk: abstract and the first part of §I. | abstract |
| 2608.11386 | Full text on disk: abstract only. | abstract |
| 2503.09089 LocAgent | Fetched this session (`lit.py fulltext`): headings, §3.2 L303-304, App. A.1.1-A.1.2 and Table 9 in full. Figures not viewed; main results not re-read. | sections |
| Zenodo 23927441 | Record description from `record.json` (a long abstract with results tables and limitations). PDF not downloaded. | abstract (extended) |
| 2609.05587 | Reading note only (the note says full text, Oct 27): Table 3 rows, coverage grid. | note only |
| 2605.09822 | Reading note only (full text per note, Oct 27): Table 7 rows, critique. | note only |
| 2606.14476 | Reading note only (full text per note, Oct 27). | note only |
| 2610.26836 | Reading note only (full text per note, Oct 27). | note only |
| 2609.36526 PAIR | Reading note only (full text per note, Oct 28). | note only |
| 2610.31710 Compact-Bench | Reading note only (full text per note, Oct 28). | note only |
| GraphLoc | `LOG.md:158-201` (notebooks verified by the other agent), `docs/competition.md:192-207`, `prereg/01:12`; model string grepped in `data/graphloc/out`. The writeup itself was not re-read. | log and notes |
| GraphAudit | `docs/lit/2026-10-27-delivery-lit-sprint.md:152-155, 416-421`; `NOTES.md:443`. The writeup is not on disk in the repo. | notes only |

## Cited with no primary source on disk

- **GraphAudit:** only secondary notes; no copy of the writeup in the repo and no URL in the draft. Its numbers
  (+3.1 [+0.7, +5.6]) cannot be re-checked locally.
- **GraphLoc's writeup:** its numbers are checked against its notebook outputs (`LOG.md`), not the writeup's text.
  The trace files are in `data/graphloc/` (gitignored).
- **Not cited but expected by these judges:** *Talk like a Graph* (ICLR 2024; `docs/prior-art.md:56`) and
  KG-LLM-Bench (`paper/README.md:20`).

## Not done

No claim in Sections 3-6 about our own runs was checked. The four note-only papers were not re-opened, because
`private/lit/` is off limits and their full texts are not in the scratch copies. Their verdicts rest on notes that
say they come from full reads.
