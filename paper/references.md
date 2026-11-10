# References

Verified reference list for `paper/draft.md` (Sections 1 and 7), built on Nov 10, 2026. Every arXiv record was
fetched today from the arXiv export API (`https://export.arxiv.org/api/query?id_list=<id>`) and compared with the
repo's reading notes (`docs/prior-art.md`, `docs/lit/`). The `verified:` line says exactly what was checked.
Entries are in the order the draft cites them. Open problems are listed at the end.

## Entries

[TalkLikeAGraph] Fatemi, Halcrow, Perozzi. Talk like a Graph: Encoding Graphs for Large Language Models. ICLR, 2024. arXiv:2310.04560. https://arxiv.org/abs/2310.04560.
verified: arXiv API (2310.04560): title and all three authors match `docs/prior-art.md` and `docs/lit/2026-10-27-delivery/refs.json`; ICLR 2024 virtual poster page (iclr.cc/virtual/2024/poster/18954): same title and authors, listed as an ICLR 2024 poster. The draft cites it without an id; the id comes from the repo's `refs.json` and was confirmed by the API today.

[2504.07087] Markowitz et al. KG-LLM-Bench: A Scalable Benchmark for Evaluating LLM Reasoning on Textualized Knowledge Graphs. arXiv:2504.07087, 2025. https://arxiv.org/abs/2504.07087.
verified: arXiv API: title and first author match `docs/prior-art.md` and `refs.json` (4 authors: Markowitz, Galiya, Ver Steeg, Galstyan). The arXiv comment says "To be presented at NAACL-HLT, KnowledgeNLP Workshop (2025)"; no Crossref or ACL Anthology record was found today, so the venue is given as arXiv.

[2610.33958] Bellam. How Much Do Structural Tools Help Small Coding Agents? A Pre-Registered Scale Study of Code Localization. arXiv:2610.33958, 2026. https://arxiv.org/abs/2610.33958.
verified: arXiv API and abs pages for v1 and v2: single author Bellam. TITLE MISMATCH WITH THE NOTES: the repo's notes (`docs/lit/2026-11-09-encoding-claim-prior-art.md:36`) give "How Do Small Coding Agents Use Code Graphs and Embeddings?", which is the v1 title (abs page of 2610.33958v1, 25 Oct 2026). The current version is v2 (updated 9 Nov 2026) with the title above. The notes were made from v1; v2 was not read. To cite the version read, use arXiv:2610.33958v1 with the v1 title.

[2503.09089] Chen et al. LocAgent: Graph-Guided LLM Agents for Code Localization. Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (ACL 2025, Volume 1: Long Papers), 2025. arXiv:2503.09089. https://doi.org/10.18653/v1/2025.acl-long.426.
verified: arXiv API: title and first author match `docs/prior-art.md` and `refs.json` (9 authors, current version v2); Crossref: same title, first authors Chen, Tang, Deng, container ACL 2025 Long Papers, DOI 10.18653/v1/2025.acl-long.426, matching "ACL 2025" in `docs/prior-art.md`.

[2609.08355] Chai et al. RepoNav: From Snippet Retrieval to File-Centered Repository Navigation for Code Agents. arXiv:2609.08355, 2026. https://arxiv.org/abs/2609.08355.
verified: arXiv API: record exists, v1, 8 Sep 2026; title begins "RepoNav", matching the name in the notes (the notes record no full title and no authors, so the authors were checked against arXiv only). This is the first successful API check of this id on record. The arXiv comment says "Accepted to EMNLP 2026"; not confirmed elsewhere, so the venue is given as arXiv.

[2611.07286] Sepidband et al. How Should Agents See Code? Rethinking Code Representations for Agentic Software Engineering. arXiv:2611.07286, 2026. https://arxiv.org/abs/2611.07286.
verified: arXiv API: title matches the notes ("How Should Agents See Code?", `docs/lit/2026-11-09-encoding-claim-prior-art.md:38`); authors (Sepidband, Shin, Wang, Hemmati) checked against arXiv only, the notes record none.

[2608.11386] Xu et al. The Devil Is in the Interface: Evaluating How Tool Architecture Shapes Coding Agent Behavior. arXiv:2608.11386, 2026. https://arxiv.org/abs/2608.11386.
verified: arXiv API: title matches the notes ("The Devil Is in the Interface", `docs/lit/2026-11-09-encoding-claim-prior-art.md:39`); authors (8, first Xu) checked against arXiv only, the notes record none.

[zenodo.23927441] Muhammad. AST-Compressed Code Graphs for Gemma 4 Agents: What a Small Local Model Gains from a Budgeted Repository Map. Zenodo (preprint), 2026. doi:10.5281/zenodo.23927441. https://doi.org/10.5281/zenodo.23927441.
verified: Zenodo API for records 23927441 and 23927442: both return the same record (conceptdoi 10.5281/zenodo.23927441, version DOI 10.5281/zenodo.23927442, version V1, published 2026-11-03, resource type preprint, one creator "Muhammad, Maroof"). The title matches the notes' short title; the record description's title line ends "(Gemma 4 Developer Agent Paper Track)", as the related-work check says. The notes record no author. 23927441 is the concept DOI (all versions); the version read is 23927442.

[2609.05587] Yang et al. Agents' Overreliance on Unreliable Tools. arXiv:2609.05587, 2026. https://arxiv.org/abs/2609.05587.
verified: arXiv API: title and all six authors, in order, match the reading note (`docs/lit/2026-10-27-delivery/notes/2609.05587.md`); current version v2 (26 Sep 2026), the version the note says was read.

[2605.09822] Kereopa-Yorke et al. Oracle Poisoning: Corrupting Knowledge Graphs to Weaponise AI Agent Reasoning. arXiv:2605.09822, 2026. https://arxiv.org/abs/2605.09822.
verified: arXiv API: title and all six authors, in order, match the reading note (`notes/2605.09822.md`); v1, 10 May 2026, the version read.

[2606.14476] Wang, Vemuri. When the Tool Decides: LLM Agents Defer Blindly to Graph Neural Network Tools, and Stronger Backbones Defer More. arXiv:2606.14476, 2026. https://arxiv.org/abs/2606.14476.
verified: arXiv API: title and both authors match the reading note (`notes/2606.14476.md`); v1, 12 Jun 2026, the version read. arXiv comment: "Under review at TMLR".

[2610.26836] Zhang et al. Same Simulation, Different Evidence: Where Retrieved Tool Output Costs LLM Agents Accuracy. arXiv:2610.26836, 2026. https://arxiv.org/abs/2610.26836.
verified: arXiv API: title and the set of five authors match the reading note (`notes/2610.26836.md`); first author Zhang in both. The note lists the authors grouped by affiliation; the arXiv order is Zhang, Chundur, Owusu, Abdolhosseini Qomi, Raissi. v1, 19 Oct 2026, the version read.

[2609.36526] Min et al. Adapting Context Compression for Long-Horizon Agents with Counterfactual Continuations. arXiv:2609.36526, 2026. https://arxiv.org/abs/2609.36526.
verified: arXiv API: title, first author and author order match the reading note (`docs/lit/2026-10-28-memory/notes/2609.36526.md`, which adds the name PAIR); v1, 29 Sep 2026, the version read. AUTHOR SPELLING MISMATCH: the note has "Minjia Shi", arXiv has "Mingjia Shi" (third author; does not affect the "et al." form).

[2610.31710] Sun et al. Compact-Bench: Measuring What Context Compaction Costs Long-Horizon Coding Agents. arXiv:2610.31710, 2026. https://arxiv.org/abs/2610.31710.
verified: arXiv API: title and all five authors, in order, match the reading note (`notes/2610.31710.md`). The note read v1 (22 Oct 2026); the current version is v2 (updated 28 Oct 2026), not read.

[GraphLoc] zzgtylors (Kaggle username; real name not recorded). Where Does the Graph Help? A Localization Audit of the Gemma 4 Developer Agent Code Graphs. Kaggle writeup, Gemma 4 Developer Agent Paper Track, 2026; public notebooks dated Sep 25-27, 2026, Apache-2.0. Notebooks: https://www.kaggle.com/code/zzgtylors/graphloc-auditing-gemma-4-agent-code-graphs, https://www.kaggle.com/code/zzgtylors/graphloc-can-gemma-4-pick-the-code-to-change, https://www.kaggle.com/code/zzgtylors/graphloc-end-to-end-gemma-4-agent-skill, https://www.kaggle.com/code/zzgtylors/graphloc-end-to-end-failure-analysis-resource.
verified: Kaggle CLI (`kernels list --user zzgtylors`) today: the four notebook refs above exist under zzgtylors, last run Sep 25-27, 2026. The writeup title and Apache-2.0 license are from the repo's notes only (`docs/competition.md:192-193`, `docs/prior-art.md:9-14`), not re-fetched. The writeup's own URL is not recorded in the repo.

[GraphAudit] Author not recorded. Title not recorded ("GraphAudit" is the name the repo's notes use). Kaggle writeup, Gemma 4 Developer Agent Paper Track, 2026; read in full on Oct 27, 2026.
verified: from the repo's reading notes only, not re-fetched (`docs/lit/2026-10-27-delivery-lit-sprint.md:152-155, 416-421`; `NOTES.md:443`). No URL, author, title or date of publication is recorded anywhere in the repo.

[Competition] Markowitz, Perozzi, Rózemberczki, Cameron, Hemmati, Li, Galkin, Farhadi, Holbrook, Oldacre. The Gemma 4 Developer Agent Paper Track. Kaggle, 2026. https://www.kaggle.com/competitions/gemma-4-developer-agent-paper.
verified: author surnames from the competition page's citation authors as recorded in `docs/competition.md:46` (read Sep 27-30); the repo records only the surnames, not the full citation text (first names, title wording, year). Today the overview page fetched without sign-in returned only its page title, "Google - The Gemma 4 Developer Agent Paper Track | Kaggle", and no citation section; the Kaggle CLI (`competitions list`) confirms the URL. The title above is from the page title and the year from the track's timeline (Sep 22 to Nov 12, 2026), not from the citation text.

## Problems found

1. 2610.33958: the title changed between v1 (read, "How Do Small Coding Agents Use Code Graphs and Embeddings?") and
   v2 (current, 9 Nov 2026). The draft's claims rest on v1; v2 was not read.
2. 2609.36526: third author "Minjia Shi" in the note vs "Mingjia Shi" on arXiv.
3. 2610.31710: now at v2 (28 Oct); the note read v1.
4. 2609.08355 (RepoNav): resolved by the arXiv API today, the first successful check on record. The repo's notes
   record no full title and no authors.
5. GraphAudit: no URL, author or title in the repo. `docs/lit/2026-10-27-delivery-lit-sprint.md:462` says the
   Kaggle writeups are "cited by URL in docs/competition.md and docs/prior-art.md", but neither file mentions
   GraphAudit. Submitted writeups are hidden until the track closes (`docs/competition.md:223-224`), so a reader may
   not be able to open it.
6. GraphLoc: the writeup URL is not recorded (only the notebook URLs).
7. Competition: the full citation text is not in the repo (surnames only), and it could not be fetched today without
   sign-in.
8. Venues not confirmed beyond arXiv comments: KG-LLM-Bench (KnowledgeNLP workshop at NAACL 2025) and RepoNav
   (EMNLP 2026). Both are given as arXiv.
9. 2611.07286 lists an author with the surname Hemmati, a surname also among the competition's citation authors.
   Whether it is the same person was not checked.
