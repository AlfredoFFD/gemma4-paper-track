# Prior-art check: arXiv 2610.33958 version 2 against our novelty claim (Nov 10, 2026)

[Claude Code] Done before submission because the draft's notes on 2610.33958 were written from version 1, and
version 2 (Nov 9) is effectively a new paper under a new title.

## (a) Coverage

- **v2: read in full.** All sections, every table (Tables 1 to 22), all four figure captions, Appendices A to I,
  and the reference list. Source: the arXiv HTML of 2610.33958v2, downloaded directly and converted to text (2,697
  lines); the abs page of v2. The figures are images, so only their captions were read, not the plotted values.
  The v2 PDF (20 pages) was opened to check that it matches the HTML. Its figure captions are 1 to 4, the same as
  the HTML. The abs-page comment "29 pages, 5 figures" is carried over from v1 and does not describe v2.
- **v1: read in part.** The abs page and the HTML abstract; the full table of contents; Section 5.7 (ForceTool) in
  full; the Section 7 paragraph "Implications for tool design"; the tool descriptions in Section 4.2; term greps
  over the whole HTML text (4,773 lines) for placebo, random entit, shuffle, permut, rewir, decoy, inject, expan,
  forc, signature. The v1 PDF (32 pages) was opened only to count figure captions (1 to 6).
- **Registration.** OSF API metadata for the registration that v2 names (title, date registered, public, not
  withdrawn). The registration's content was not read.
- **Code.** The GitHub repository v2 names returned HTTP 404 on Nov 10, so the released code could not be checked.

## (b) What changed from v1 to v2

| | v1 (25 Oct 2026) | v2 (9 Nov 2026) |
|---|---|---|
| Title | How Do Small Coding Agents Use Code Graphs and Embeddings? | How Much Do Structural Tools Help Small Coding Agents? A Pre-Registered Scale Study of Code Localization |
| Status | Exploratory | Confirmatory. v2 calls itself "the confirmatory successor of an exploratory preprint (Bellam, 2026)" (Section 1) and cites v1 as a separate reference under v1's title and the same arXiv id |
| Tasks | SWE-bench Verified: a depth-balanced 160-task split and all 500 | 500 SWE-bench test tasks outside Verified, held out (Verified becomes the development set and is never reported); 750 more for H3; 300 post-release tasks from SWE-bench-Live (S2) |
| Models | Ten: six Qwen3 sizes 0.6B to 32B, an FP8 control, three Gemma 4 sizes | Nine: Qwen3 0.6B to 32B, Gemma 4 E2B, E4B, 12B; plus a Qwen3-14B-FP8 control. No Gemma 4 model above 12B |
| Scale | 79k episodes; greedy decoding plus five decodings for the scale curve | 170,500 pre-registered episodes; 227,800 in all; T=0.7 with seeds 1 to 5 for every arm |
| Arms | G, E, T, ET | N, G, E, T, ET, and a new placebo arm PL; a shell harness SG/SET (S3) |
| Dropped | | Hop depth as a difficulty axis (now descriptive only); the linear probes (the "companion probing study" is withdrawn, Appendix H); ForceTool; the Budget and WeakEmb experiments; the trace analysis of expansion chaining |
| Added | | Placebo arm (random entities in the structural tools' output); Part 2 interventions GI, GIP, ETM (inject or mask the gold in tool output); activation patching and head ablation; thinking, FP8, prompt-paraphrase checks; post-release tasks; shell harness; cross-vendor rerun; 60-step run for Gemma 4 12B; repair check |
| Headline claims | Tool gain peaks at 17 to 21 points at 1.7 to 4B and falls to 4 to 5 at 32B; about half the gain from 8B up is submission form; graph gain is name lookup plus one expansion; agents chain expansions in 12 to 14% of episodes; the 14B to 32B fall is a fall in tool uptake | Tools raise canonical Acc@10 by +0.06 to +0.10 for small models, +0.03 at 32B (not supported after Holm), nothing for Gemma 4 12B; the placebo makes the gain causal; 4B with tools does not match 32B without (H3 fails); the embedding index, not the graph, carries the gain; the gain is mostly exposure; small models convert a shown answer less often (0.09, 0.24, 0.40 at 1.7B, 4B, 32B) |

**Two findings our draft cites are not in v2.** Forcing the graph call (v1 Section 5.7) and "agents expand once and
stop" (v1 Section 7) appear only in v1. v2 refers back to them only through its v1 citation: "small agents rarely
chain graph expansions (Bellam, 2026)" (v2 Section 7, "Embeddings, not graphs").

## (c) Our four claims against v2

Our sentence: "no work fixes one set of graph edges, varies only its encoding or rewires it, and scores the agent's
next action against a no-list base rate."

1. **Fixes one set of graph edges and varies only its encoding: still holds.** v2 holds the output format fixed
   across arms by design. The placebo uses "identical names, schemas and output format" (Section 3, Harness). Its
   discussion explicitly leaves format open: "This does not rule out graph interfaces that present structure
   differently" (Section 7, "Embeddings, not graphs"). The graph tool's format is fixed: "[hop h] u --relation--> v
   followed by the signature" (Appendix B, Tools). v2 studies format only on the submission side: "the tools print
   ids the model can copy" (Section 4.1), corrected by a metric repair (Appendix B).
2. **Rewires it: holds literally, but this clause is now the weakest.** v2 shows the agent corrupted structural
   output. In PL every entity the three structural tools show is "replaced by a definition drawn uniformly at random
   from the same repository" (Appendix B, Placebo and masking). In ETM, "every structural-tool line that shows a gold
   definition replaced by a random one" (Section 3, Checks). Neither is a degree-preserving rewiring of one
   function's fixed neighbor list. PL randomizes all entities from semantic_search, find_entity and
   graph_neighbors for whole episodes. ETM targets gold lines only. Neither is scored at the next step. A
   judge who reads only v2's abstract could still take "a placebo arm whose structural tools return random entities"
   as a corrupted-graph control, so our text has to state the difference.
3. **Scores the agent's next action: still holds, with one near case.** Every v2 behavioral outcome is end-of-episode
   localization (Acc@10, file Acc@5), with episodes of up to 30 turns. The nearest case is the head-ablation table:
   "Gold hit: the first action names the gold file or definition" (Appendix F, Table 20). That is a first-action
   score, but it comes from fresh episodes at turn 0 with ablated attention heads. It is compared with random-head
   ablations, not with a no-list base rate at a paused state.
4. **Against a no-list base rate: still holds, with one near case.** GI versus GIP is the closest design in v2. GI
   adds "one scripted grep whose ten output lines contain the definition lines of every gold definition" (Section 3),
   and GIP is the same draw "with the gold lines replaced by further distractors in the same slots" (Appendix B). This
   is a matched with-answer and without-answer contrast with decoy-like distractors. But it injects a grep line, not a
   graph neighbor list. It happens before the first turn of a new episode, not at a paused real state after a file
   open. And it is scored by final Acc@10, not the next call. It is also unregistered: "explanatory (Part 2, planned
   after the main results were read)" (Section 3, Pre-registration).

## (d) Specific checks

- **Manipulating how graph or tool output is written (formats, fields, line numbers, file paths): no.** Output format
  is held constant in every arm, by design. Line numbers appear only in the metric repair, which turns a submitted
  line number into its enclosing definition (Appendix B, Metric repair), and in grep's fixed `path:line: text`
  format. Output is truncated at 4,000 characters in every arm.
- **Replay or fork from saved agent states: no.** Every condition is a fresh episode. GI injects at the start
  ("before the agent's first turn", Section 3). Activation patching swaps the injected gold line for a distractor of
  equal token length on the GI first turn (Appendix F). That is a counterfactual on the input, but it is internal
  and at turn 0, not a behavioral replay from a mid-run state.
- **Corrupted, rewired or decoy graph content: yes, in a different form from ours.** PL (random entities in all
  structural-tool output, pre-registered as H4), ETM (gold lines replaced by random entities, explanatory) and
  GIP (distractors in place of gold lines in an injected grep, explanatory). No degree-preserving rewiring, and no
  single planted false edge with an otherwise true list. v2 reports that random output harms Qwen3-1.7B and
  Gemma 4 E2B (Table 5).
- **Multi-model or multi-step versions: yes for those designs.** PL runs on all nine models over full episodes of up
  to 30 turns. GI, GIP and ETM run on five models (Qwen3-1.7B, 4B, 32B; Gemma 4 E2B, E4B), seeds 1 to 3.
- **Pre-registration: what and where.** H1 to H4, the arms, metrics, tests, corrections, sample sizes and claim
  criteria were frozen in a tagged commit on 28 Oct 2026 and re-frozen on 31 Oct. Amendment 1 (S1 to S4) was
  committed on 1 Nov while the main block ran. The design was "registered on OSF on 3 November, after the main runs
  had finished" (Section 3), before any confirmatory output was opened. The registration is public at
  https://osf.io/h8zf4/ (OSF API: titled "A pre-registered scale study of tool benefit in coding agents", registered
  2026-11-03, not withdrawn). The parts nearest our design were not registered: Part 2 (GI, GIP, ETM, patching) is
  explanatory, its registration as amendment 2 was withdrawn on 6 Nov (Appendix H), and the revision analyses
  are post hoc. The paper says so itself (Limitations, Registration).

## (e) Verdict

**Our novelty sentence still holds against v2, but our related-work text is now wrong in two places and too weak in
one.** v2 never varies the encoding of a fixed edge set, never forks from a paused real state, never shows a
degree-preserving rewired list or a single false edge, and never scores the next call against a no-list base rate.
But v2 does have a placebo with random tool content, gold injection and masking, and a framing in which an answer
the agent was shown is not an answer it used ("A shown answer is not a used answer.", Section 7). That framing is
close to our bare-names result. A judge who knows v2 will ask how we differ, so the draft has to say it.
Confidence: high for v2 (read in full). The figures' plotted values and the registration's text were not read.

Changes the draft needs:

1. **Cite the versions separately.** v2 treats v1 as its own reference. The forcing and "expand once and stop"
   findings exist only in v1, so cite them as 2610.33958v1. Cite the current description as 2610.33958v2.
2. **Rewrite the description of the nearest study.** It is now a pre-registered, placebo-controlled scale study (nine
   models, Gemma 4 up to 12B, 500 held-out non-Verified SWE-bench tasks). "Measures how small coding agents use code
   graphs and embeddings" is the v1 framing.
3. **Name v2's placebo and injection designs and state the difference from ours.** PL replaces every structural-tool
   entity with a random one for whole episodes. GI and GIP inject a gold or distractor grep line at turn 0. Both are
   scored by final localization. Ours rewires one function's neighbor list with degree preserved, at a paused real
   state, and scores the next call.
4. **Optionally cite v2's convergent findings.** Small models convert a shown answer less often, and the embedding
   index, not the graph, carries the gain. Both agree with our bare-names result from a different design.
5. **Optionally tighten the novelty sentence.** For example: "no work fixes one function's graph neighbors at a
   paused agent state, varies only their encoding or rewires them with degree preserved, and scores the next action
   against a no-list base rate." This guards the "rewires" clause against v2's placebo.

Suggested replacement for the 2610.33958 sentences in Section 7 (about 35 words longer than the current text):

> The nearest study is a pre-registered, placebo-controlled scale study of how much code-graph and embedding tools
> help small agents localize code (2610.33958v2). Its graph tool already prints signatures and qualified paths, and
> its arms vary the tool set, not the encoding. Its placebo replaces every entity the structural tools return with a
> random one for whole episodes, and an injected grep line separates showing the answer from acting on it; both are
> scored by final localization. Its exploratory first version reports that forcing the graph call does not help and
> that agents expand once and stop (2610.33958v1). Our instruction arms agree from a different design.

Also outside the draft: `paper/references.md` should replace its single 2610.33958 entry with the two entries below.
Its note "v2 was not read" is now out of date.

**Not checked here.** v2 cites a paper that "inject[s] structure into grep output" (LARGER, arXiv 2605.16352). It has
turned up in the repo's searches but was never read. It is the one new lead from v2's reference list that touches
the encoding clause. RepoMirage (2605.26177) and Deterministic Anchoring (2606.26979), also cited by v2, are already
covered in `docs/lit/2026-10-27-delivery-lit-sprint.md` and `docs/prior-art.md`.

## (f) Reference entries

- Saurav Bellam. How Much Do Structural Tools Help Small Coding Agents? A Pre-Registered Scale Study of Code
  Localization. arXiv:2610.33958v2 [cs.SE], 2026. Single author (The University of Texas at Austin). v1 submitted
  25 Oct 2026 (00:16:32 UTC); v2 revised 9 Nov 2026 (13:25:12 UTC). https://arxiv.org/abs/2610.33958v2.
- Saurav Bellam. How Do Small Coding Agents Use Code Graphs and Embeddings? arXiv:2610.33958v1 [cs.SE], 25 Oct 2026.
  https://arxiv.org/abs/2610.33958v1. (Needed for the forcing and expansion findings, which v2 does not contain.)
