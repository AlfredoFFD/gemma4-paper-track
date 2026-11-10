# Prior-art check: LARGER (arXiv 2605.16352) against our novelty claim (Nov 10, 2026)

[Claude Code] Done before submission because 2610.33958v2 describes this paper as injecting structure into grep
output, which touches our encoding and channel clauses. It had turned up in the repo's searches but had never been read.

## (a) Coverage

- **Read in full.** The arXiv HTML of 2605.16352v1, downloaded directly and converted to text (about 2,060 lines):
  the abstract; Sections 1 to 6; Algorithm 1; Theorems 1 and 2, Proposition 1, Corollary 1; Tables 1 to 11; all
  figure captions; Appendices A (proofs), B (full results, efficiency, token and cost breakdowns), C (datasets),
  D (alignment cost, hyperparameter sweep) and E (graph construction, edge confidences, sidecar storage, both
  system prompts, the injected format); and the reference list.
- **PDF.** The 21-page PDF was converted to text and checked against the HTML. One sentence the HTML conversion
  cut off (the confidence filter in Appendix E.1) was read from the PDF. Nothing else differs.
- **Figures.** Figures 1a and 1b (Recall@5 and runtime with and without LARGER) were viewed as images and their
  values read. Figures 1c, 2, 3 and 4 were read by caption only. Figures 3 and 4 do not render in the HTML.
- **Versions.** Only v1 exists. The URL for v2 returned 404 on Nov 10, and the abs page lists a single submission
  (v1, 8 May 2026).
- **Not checked.** No code repository is named in the paper, so no released code was read.
- **Repo notes before this check.** `docs/prior-art.md` does not mention it. `docs/lit/2026-11-10-bellam-v2-check.md`
  lists it as an unread lead. Two search tables in the Oct 27 lit-sprint delivery list it (first author spelled
  "Yun-Tong Hu" there, from Semantic Scholar; arXiv spells it Yuntong Hu).

## (b) What the paper does

- **Task.** File-level code localization: given a GitHub issue, the agent outputs a JSON list of 1 to 10 files to
  modify. Transfer is tested on two downstream tasks: test writing and codebase question answering (SWE-Atlas).
- **System.** A code graph (directories, files, classes, functions; edges for containment, imports, calls,
  inheritance, test, documentation and configuration links) is built once per repository with tree-sitter style
  parsing and stored as per-file JSON sidecars (capped at 20 neighbors per file). Each edge type has a fixed
  confidence (1.0 same-file down to 0.5 fuzzy name match; Table 11). Files get Leiden community labels.
- **What is injected, where.** Whenever the agent runs grep, the matched files are aligned to graph nodes, and up to
  k = 10 neighbors per anchor with confidence of at least 0.5 are appended to that same grep result. No new tool is
  added. The channel is the existing tool result.
- **Format** (Appendix E.4). A block headed "[Related files from dependency graph]" lists, per related file: its
  path and cluster label; callers and callees written as `path:function_name` with a bracketed confidence; and an
  execution-flow name with a step index. **File paths: yes. Function names: yes. Call edges: yes, typed as callers
  and callees, with confidence. Line numbers or line ranges: no. Signatures or definition lines: no.** The block is
  generated deterministically from the sidecar index.
- **Prompt.** The graph agent's system prompt differs from the baseline's only in the step-3 guidance. The added
  lines tell the agent to read the appended block, to treat high-confidence callers and callees as strong
  candidates, and to treat same-cluster files as likely co-changes (Appendix E.4). So the "on" condition adds both
  information in the tool result and an instruction in the system prompt.
- **Agents and models.** An in-house CLI agent on GPT-5.2 for all main results. The with/without comparison
  (Figure 1) also uses GPT-4.1. Baselines: BM25, Agentless, SWE-agent, OpenHands, Codex, mini-swe-agent, CoSIL and
  LocAgent on GPT-5.2; Claude Code on Claude Opus 4.6 (flagged as not directly comparable). No open-weight models.
- **Comparisons.** (1) LARGER against those baselines (Table 1). (2) The same agent with and without LARGER
  (Figure 1). LocBench Recall@5 goes from 69.0 to 76.6 (GPT-4.1) and from 82.0 to 90.1 (GPT-5.2). MuLocBench goes
  from 51.9 to 57.9 and from 63.2 to 68.6. Runtime falls in all four cells. (3) Component ablations on MuLocBench
  (Table 3): removing graph expansion drops Acc@5 from 55.7 to 48.2; removing confidence scoring, to 53.1; removing
  community labels, to 53.4; removing all modules, to 46.8.
- **Scoring.** End of episode only: file-level Acc@K, Recall@K, Hit@K, MAP and MRR on the final file list
  (Tables 1, 4, 5); mutation and rubric-judge scores for SWE-Atlas (Table 2); wall-clock time, tokens and cost
  (Tables 6 to 9). Section 5.1 says each method's score is the mean of three independent runs. No intervals or
  significance tests are reported. Efficiency telemetry covers 374 of 560 LocBench instances (Appendix B.1 says the
  rest failed with API authentication errors).
- **Scale.** LocBench (560 issues, 5 repositories), MuLocBench (1,100 issues, 46 repositories), SWE-Atlas Test
  Writing (90 tasks) and Codebase QA (124 questions) over 11 repositories in Python, Go, TypeScript and C. Episodes
  average 13 to 14.5 model calls (Table 8).
- **Theory.** Section 4.3 and Appendix A prove that, for a fixed policy and a fixed query stream, adding neighbors
  can only raise recall at each step (a superset argument). Appendix A also argues that in real runs the richer
  observations lead the agent to issue more targeted next queries. The paper asserts this but never measures it.

## (c) Our novelty sentence, clause by clause

Our sentence: "no work fixes one function's graph neighbors at a paused agent state, varies only their encoding or
rewires them with degree preserved, and scores the next action against a no-list base rate."

1. **Fixes one function's graph neighbors: not done.** LARGER's neighbor set is recomputed at every grep from
   whatever matched: top-k per anchor after the confidence filter (Section 4.2, Eq. 13), read from file-level
   sidecars (Appendix E.3). The unit is the file. The set changes with each query and is never held fixed across
   conditions.
2. **At a paused agent state: not done.** Every condition is a full episode that starts from the issue
   (Algorithm 1, Section 4.4). No states are saved, forked or replayed.
3. **Varies only their encoding: not done.** One rendering is used throughout (Appendix E.4). The ablations
   (Section 5.3, Table 3) remove graph expansion, confidence scoring or community labels. These change which
   neighbors are chosen and which fields carry signal. None holds the neighbor set fixed while changing how it is
   written, and the paper does not say how the rendered block changes in those arms.
4. **Or rewires them with degree preserved: not done.** The paper has no random, shuffled, decoy or corrupted graph
   condition. The only degraded conditions remove components.
5. **Scores the next action against a no-list base rate: not done.** All outcomes are end-of-episode (Tables 1 to 9,
   Figure 1). A no-graph condition exists (Figure 1; Table 3, without graph expansion and without all modules), but
   only at episode level. The next action appears only in the formal model (Section 4.1, Eq. 8) and in the unmeasured
   claim about more targeted queries (Appendix A, remark after Proposition 1, and A.8).

## (d) Specific checks

- **Comparison of encodings of the same structural content: no.** One format throughout.
- **No-injection base rate: yes, at episode level only.** Figure 1 compares the same agent with and without
  LARGER on two models. But the "with" condition also adds system-prompt guidance. So information in the tool
  result and instruction in the prompt are switched on together and never separated. Our channel and force axes
  separate exactly these.
- **Corrupted, rewired or decoy structure: no.**
- **Replay from saved agent states: no.**
- **Multi-step: yes, inherently.** Every condition is a full episode of about 13 calls, longer than our five-call
  continuation. But it is not a continuation from a fixed state.
- **Multi-model: partly.** The with/without comparison runs on GPT-4.1 and GPT-5.2. Everything else uses GPT-5.2.
  No Gemma models and no open-weight models.

## (e) Verdict

**Our novelty sentence holds against LARGER on all five clauses. We should cite it. It is the nearest example of
graph neighbors delivered inside an existing tool's result, not through a separate graph tool.** It supports our
related-work framing that how a tool's output is written and placed changes agent behavior. Its own analysis
argues that graph delivery inside the search loop beats separate graph tools (Section 5.2, CoSIL and LocAgent
against LARGER). But it tests one format, scores only whole episodes, has no corrupted-structure control, and
switches on prompt instructions together with the injected data. Its central mechanism claim, that richer grep
output makes the next query more targeted, is asserted and not measured. Our one-step test measures that kind of
claim directly. Confidence: high (read in full; Figures 1c, 2, 3 and 4 by caption only).

Points of contact the draft could use (our inference, not the paper's claims):

- LARGER's format names a function together with its file path (`path:function`) and gives no line range. Our
  encoding axis sits on either side of that format: bare names below it, names with file, line range and
  definition line above it. LARGER scores file-level localization only, so a line range would not have shown up
  in its metric.
- LARGER's injection is our "legible encoding inside the tool's own result" condition at episode scale, with an
  instruction added. If a judge asks whether our tool-result arm is just LARGER, the answer is: same channel,
  but we hold the edge set fixed, vary only the encoding, keep information and instruction separate, and score
  the next call.

Suggested related-work sentence (24 words):

> LARGER appends confidence-scored callers and callees to grep output and improves end-of-episode file localization
> for GPT-4.1 and GPT-5.2 agents; it never varies the encoding.

Optional second clause if space allows: its on condition also adds prompt guidance, and its claim that the next
query becomes more targeted is not measured.

## (f) Reference entry

- Yuntong Hu, Tongli Su, Liang Zhao, Bowen Zhu, Hasibul Haque. LARGER: Lexically Anchored Repository Graph
  Exploration and Retrieval. arXiv:2605.16352v1 [cs.IR], submitted 8 May 2026 (05:03:46 UTC). Only one version
  exists as of Nov 10, 2026. Affiliations: Emory University; CausalDynamics.com. Also listed under cs.AI and
  cs.LG. https://arxiv.org/abs/2605.16352v1.
