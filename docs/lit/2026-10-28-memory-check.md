# Memory check, Oct 28 2026: is graph-shaped agent memory already done?

Written by Claude Code on Wed Oct 28, 2026, for the Oct 29 decision on whether a "memory" experiment joins the paper. This is the "already done?" half only. Whether compaction hurts the agent in our traces is a separate check, not attempted here.

Sources:
- **Read in full** (every line, figure and table; notes in `2026-10-28-memory/notes/`): PAIR (2609.36526) and Compact-Bench (2610.31710).
- **Read in part:** Source-Judged Compaction (2610.20927). Found late in PAIR's citation trail; the targeted sections and a keyword check are noted, and it should be read in full before the paper cites it.
- **Abstract only:** everything else below, marked ABSTRACT.

## Verdicts

**Claim A (architecture), partly done; nearly done as a mechanism.** Confidence: medium-high.
- **The claim:** a compact working memory keyed by code-graph nodes (suspect / ruled out / edited / verified), kept instead of or beside the raw transcript, beats standard compaction under a small cap, with no training.
- **Coding agents with a compact, status-bearing execution memory beside the transcript, no training, beat the same agent:**
  - Ledger (2608.00808, ABSTRACT): observed / modified / attempted. SWE-bench Verified 56.2 → 64.2 with GPT-5 mini.
  - StateHarness (2610.17616, ABSTRACT): hypothesis, findings, repository relationships, unfinished work.
- **Memory keyed by code entities replacing raw history under a constrained context:**
  - MemTrace (2610.04838, ABSTRACT): files, symbols and tests in a trace graph.
  - StateTape (2609.36319, ABSTRACT; already in the team's Sep 30 check): a symbol-level code graph decides which context records a write has falsified.
- **Status-labelled hypothesis memory, outside code:** SLEUTH (2607.12267, ABSTRACT).
- **Structured Done / In progress / Blocked checkpoints under 2–4K budgets, no training:** ACON and PAIR (PAIR read in full).
- **What is left is a setting, not a mechanism:** the organizers' names-only graph, a 4-bit 31B open model, and the harness's own ~14.3k-token compaction. A judge would read our version as an application of Ledger or MemTrace to the competition graph.

**Claim B (paused-run mechanism), partly done; the true-vs-false contrast is open in what we searched.** Confidence: medium.
- **The claim:** fork a saved post-compaction state with vs without an inserted graph-shaped note, same seeds. The note changes the next read or edit, and a note with one wrong entry is followed as readily as a true one.
- **Done: same-state forks at a compaction boundary, with vs without (part of) the memory.**
  - PAIR (full text) and its predecessor 2608.06503 (ABSTRACT).
  - RECAP (2610.22897, ABSTRACT), with matched rollout seeds.
  - In SWE-bench repairs: Compact-Bench (full text).
- **Done: agents act on wrong or unsupported memory entries.**
  - SJC (partial read): 29 of 35 failed runs carry out a specific summary entry, 22 of them unsupported by any environment output.
  - Compaction Laundering (2610.29869, ABSTRACT): forged entries survive compaction in five coding harnesses and steer plans away from a designated file.
  - Memory Trust Gap (2609.01852, ABSTRACT): Qwen3 0.6–8B answer with a stale stored value 92–100% of the time when the note is their only source.
  - PAIR Case A (full text): a wrong "settled" result in a summary is followed into failure.
- **Done: re-reading as the cost of lost state.** PAIR's interaction burden and its Case B.
- **Not found anywhere:** a planted wrong entry compared with a true one at the same state, scored on the next read or edit against a no-insertion base rate. SJC's "the agent cannot tell the two apart" is inferred from failure attribution, not measured (from the sections read and a keyword check of its full text).

**What would make Claim B a straight application of PAIR:** reporting "a note at the compaction boundary reduces re-reads or restores progress". That is PAIR's interaction burden (Case B) and Compact-Bench's fork, moved to Gemma. The only defensible headline is discrimination: true vs one-false entry at the same state, against the base rate.

**What could weaken Claim B further:**
- **Re-reads may not be where the effect is in code.** In Compact-Bench's damaged repairs, repeated `read_file` calls were at most one per condition. The loss was the step from evidence to edit (App. J, §4.4), so "fewer re-reads" is a weak outcome to pre-register. Use the next read or edit target, as the main experiment does.
- **It is structurally the main experiment run at a second fork point.** A real list plus one fake link, scored against a no-insertion base rate. Its added value is the compaction contrast (O2 below), not the memory framing, which is the crowded part.
- **The closest group publishes monthly.** PAIR's authors (Min et al.) posted on Aug 6, Sep 29 and Oct 14. A controlled-insertion follow-up before Nov 12 is plausible (a guess).

## Closest prior work

| Paper | Read | What it does | What it leaves open (A / B) | Where |
|---|---|---|---|---|
| **PAIR**, Min et al. (2609.36526) | full-text | Forks from a restored state at each compaction boundary: PRE (full context) vs POST (summary), compression off afterwards. Outcome hazard is the success drop, interaction burden the extra steps; 197 AppWorld boundaries, m = 9. Burden is common, severe harm rare (11 of 197 cut success by > 0.5). Uses this to rewrite a structured OpenClaw compression prompt, agent frozen. Case A: a summary recording "Use total 1676 as the answer" is followed (PRE 3/3 vs POST 1/3; 0/3 on recompression). Case B: specs reduced to prose force re-reading (+5 steps) | A: structured, status-bearing checkpoints under 2–4K budgets without training are done, but not keyed by code-graph nodes and not in code. B: no note inserted on top of a summary; no controlled wrong entry; no true vs false; terminal outcomes, not the next action; GPT-5.6 Luna and MiniMax-M3 only, unseeded | §3.2–3.3; Fig. 2; Tables 1, 8, 9; App. D.10 |
| **Compact-Bench**, Sun et al. (2610.31710) | full-text | The same fork in coding: 22 validated SWE-bench repairs, cached history and repository snapshot, full history vs summary only, 8-step continuation, FAIL_TO_PASS tests. Damage 5–64% across 14 summarizers. Summaries keep the target file and most gold-patch tokens yet fail; repeated `read_file` ≤ 1 per condition in the four inspected failures | A: no structured memory is tested on task outcome (the 79.1% mechanical extractor is scored only on retention). B: the method in code is done. No inserted note, no wrong entries, no base rate, unseeded, Kimi-K3 only. Tool outputs are cut to 200 characters before summarizing, and POST adds an extra wrapper message | §3.1, Fig. 1; Tables 2, 5, 15; App. D, I, J |
| **Source-Judged Compaction**, Min & Chen (2610.20927) | partial | Agents act on compressor-written summary entries: 29 of 35 failed runs carry out a specific entry, 22 unsupported and 3 contradicted. Pruning unsupported entries raises Pass^3 by 2.1–8.9 on AppWorld and OfficeBench. Provenance does not predict correctness (92.2% vs 90.6% correct) | B: the strongest support that wrong memory entries get followed after compaction. No forks, no planted entry, no true-vs-false contrast (keyword check of the full text); not code | §3.2, §5.5, Limitations, App. D, G |
| **Compaction Laundering**, Dabirsiaghi (2610.29869) | ABSTRACT | A forged "user turn" survives compaction as memory in 87–100% of runs in five flattening coding harnesses (0% in four role-typed ones). It drives execution (~50% vs 0% in a paired clean arm) and steers an agent's plan away from a designated file | B: wrong memory steers file choice in coding agents, but as a security exploit through harness flattening: instruction-shaped, no true-entry comparison, no base rate | abstract |
| **RECAP / When to Forget**, Chen et al. (2610.22897) | ABSTRACT | Keep, compress or remove the same history block at matched environment states and rollout seeds; measures continuation success and prompt cost across five backbones | B: seeded same-state forks over memory content are done. It edits existing history (no inserted note, no false content), and the domain is not stated in the abstract | abstract |
| **The Memory Trust Gap**, Hu & Ramachandran (2609.01852) | ABSTRACT | Small models (Qwen3 0.6–8B) answer with a stale stored value 0.92–1.00 of the time. A 2×2×2×2 factorial shows which note features (label, recency, authority, position) trigger over-trust | B: small-model over-trust of a wrong note is shown, with action-scored suites, but not in code, not after compaction, no forks, no true-vs-false at the same state | abstract |
| **Ledger**, Wang et al. (2608.00808) | ABSTRACT | A deterministic runtime layer keeps an explicit execution state (observed, modified, attempted), injects a compact view each step, and returns still-valid earlier results instead of re-executing (flagging likely repeats). SWE-bench Verified 56.2 → 64.2 (GPT-5 mini), 75.8 → 81.0 (MiniMax M2.5); Codex +3.4. No LM calls | A: nearly the architecture, keyed by files and commands rather than graph nodes, with no small cap or compaction comparison stated. B: not a fork study | abstract |
| **StateHarness**, Zou et al. (2610.17616) | ABSTRACT | Agent-maintained project state (current problem and hypothesis, findings, repository relationships, unfinished work) as a compact brief; no parameter updates; gains on RefactorBench, LHTB and ChainSWE, with more pass-to-pass regressions | A: hypothesis-and-relationship memory in coding is done; not graph-node keyed; no small-cap comparison stated | abstract |
| **MemTrace**, Xu et al. (2610.04838) | ABSTRACT | Memory traces anchored to files, symbols and tests in a trace graph. Under constrained context only compact anchors stay in working memory; validity is checked against the repository before reuse. DeepSWE +21.2, SWE-EVO +4.4 (Codex CLI) | A: entity-keyed memory replacing raw history under a constrained context is done. Not the organizers' graph, not a small open model; training status not stated | abstract |
| **StateTape**, Yu et al. (2609.36319) | ABSTRACT (team-known) | Models the repository as a symbol-level code graph; a per-write tape marks context records a write may have falsified. Its stated alternative is history-based masking and summarizing; it reports a higher resolve rate in all experiments (six coding agents, three edit-heavy benchmarks) | A: code-graph-keyed context maintenance vs standard maintenance is done. A small manager model is used; the cap and training status are not stated | abstract |
| **SLEUTH / Track, Rank, Crack**, Liu (2607.12267) | ABSTRACT | Structured epistemic working memory (confirmed facts, ranked active hypotheses, open questions) drives the next action; +5 to +11 points on multi-hop QA; training-free | A: status-labelled hypothesis memory is done, outside code | abstract |

**Also relevant, ABSTRACT only:**
- **Same-state compaction checks:**
  - TRACE predecessor 2608.06503 (paired continuations from the same environment state, Aug 6);
  - Slipstream 2605.08580 (judges a summary against the agent's own continuation from the same state; SWE-bench Verified).
- **Constraint and state loss under compaction:**
  - COMPINT 2608.11242: 17% of side constraints retained; 30/100 inbox sessions violated a constraint after compaction;
  - Benchmarks Are Surprisingly Compaction-Friendly 2610.31778.
- **Wrong memory followed:**
  - When Stale Constraints Go Unchecked 2608.25553: stale-consistent decisions in 74–77% of episodes; provenance inspected about 1 in 5;
  - Reclaim Evaluation 2606.25449: a lossy memory worse than none;
  - MemDev-Bench 2610.27524: code agents reuse memory without reassessing it;
  - The Working Set of a Coding Agent 2608.16630: "a stale convention file costs more than no file".
- **Small models under small windows, no training:**
  - Bud ContextCompact 2.0 2610.25516: a 27B model on a 49K window, +12.3 on long SWE-bench sessions;
  - transparent-compact 2610.20116 (local lightweight models);
  - Spine 2610.37224 (Qwen 3.8 27B);
  - ARC 2607.25066 (Qwen3-8B, 16k).
- **Other structured or graph context managers:** ContextWeaver 2604.23069, CWL 2606.11213, FlowState 2609.34565, MAGE 2606.06090, ReCAP context graphs 2609.40118, PROJECTMEM 2606.12329 ("decided, tried, ruled out"), EA-Graph 2608.04278, Stratum 2610.36153, ACON 2510.00615, Complexity Trap 2508.21433.
- **Trained alternatives** (they modify the model): AutoCompact 2610.02163, SWE-Compressor 2512.22087, LOHA/ACD 2609.31430, plus the team-known Context-Folding 2510.11967 and SWE-MeM 2606.28434.
- **Already known to the team, not re-reported:** 2607.20972, 2609.32590, 2609.20804, CodeNib 2607.25431, Prometheus 2507.19942.
- **FLAGGED:** The Hypothesis Graph (Zenodo 10.5281/zenodo.21939860), a preprint whose nodes are testable claims and whose edges are refutations, for coding agents. `verify-file` could not resolve its DataCite DOI (HTTP 404). The record exists in OpenAlex; it is not peer-reviewed and was seen as a truncated abstract only. Do not cite without checking.

## What is still open (in what we searched)

Claim B components against the closest papers:

Key: ✓ done · ~ partly · ✗ not found.

| | PAIR | Compact-Bench | SJC | Laundering | RECAP | Trust Gap |
|---|---|---|---|---|---|---|
| B1 Same-state fork at a compaction boundary | ✓ | ✓ (code) | ✗ | ~ (paired clean arm) | ✓ | ✗ |
| B2 A note inserted on top of the summary | ✗ | ✗ | ✗ | ~ (forged turn) | ✗ | ✗ |
| B3 A wrong entry gets followed | ~ (Case A) | ✗ | ✓ (attribution) | ✓ | ✗ | ✓ |
| B4 True vs one-false entry at the same state | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| B5 Next read or edit against the no-insertion base rate | ✗ | ~ (one trace) | ✗ | ~ | ✗ | ✗ |
| B6 Seeded paired continuations | ✗ | ✗ | ✗ | ? | ✓ | n/a |
| B7 Code graph, small 4-bit open model, official harness | ✗ | ✗ | ✗ | ✗ | ✗ | ~ (small, not code) |

**Open items:**
1. **O1, discrimination (B4 + B5).** At the same saved post-compaction state, with the same seeds, does Gemma follow a false link in an inserted, node-keyed note as often as a true one, relative to the base rate for that node? No paper we found measures it. This is the part worth keeping.
2. **O2, does losing the transcript raise credulity?** Fork the same task before and after compaction, and test whether following of the fake link rises once the agent's own record is gone. This is the compaction × truth interaction. We found no test of it. It is our inference that this is what a memory arm adds beyond the main experiment.
3. **O3, Claim A in this setting.** Memory keyed by the organizers' graph nodes vs the harness's own compaction under its ~16k cap with a 4-bit 31B model. Open only as a setting (see the verdict above).
4. **Not open:** forks at compaction boundaries, the claim that summaries lose progress, the claim that wrong summary entries get followed, seeded matched-state forks (RECAP), and re-reads as the measured cost (PAIR).

**Context for the separate compaction check** (literature only, not our traces):
- Summary-only continuation damages 5–64% of short SWE-bench repairs (Compact-Bench).
- Compaction helped a 27B model on a 49K window (Bud ContextCompact 2.0, ABSTRACT).
- Context management mostly prevents overflow (2609.20804, ABSTRACT, team-known).
- The literature points both ways, so our own traces have to decide.

**Not searched:** paywalled venues, non-English work, patents, and Kaggle writeups from this competition.

## Search log

Wed Oct 28, 2026, 13:54–14:04 local time, `lit.py search` (each phrasing over three sources × two windows) and `lit.py expand`. The raw log is `2026-10-28-memory/lit_search_log.jsonl`; result tables are in `searches/` and `trails/`.

| # | Phrasing | arXiv 6mo / all | OpenAlex 6mo / all | S2 6mo / all |
|---|---|---|---|---|
| p1 | code graph agent memory | 15 / 15 | 15 / 15 | 15 / 0 |
| p2 | structured working memory coding agent | 15 / 15 | 15 / 15 | 15 / 0 |
| p3 | context compaction coding agent | 15 / 15 | 15 / 15 | 0 / 0 |
| p4 | context compression long-horizon agent | 15 / 15 | 15 / 15 | 0 / 15 |
| p5 | agent memory stale wrong notes | 0 / 0 (fallback with 4 terms, "memory agent stale wrong": 9 / 10) | 15 / 15 | 0 / 0 |
| p6 | repository graph memory software agent | 7 / 13 | 15 / 15 | 0 / 0 |
| p7 | counterfactual continuation context compression | 1 / 1 | 15 / 15 | 0 / 0 |
| p8 | observation masking summarization agent | 3 / 4 | 15 / 15 | 0 / 0 |
| p9 | memory poisoning coding agent | 15 / 15 | 15 / 15 | 0 / 0 |
| p10 | agent state fork intervention replay | 1 / 1 | 15 / 15 | 0 / 0 |
| p11 | hypothesis tracking debugging agent | 0 / 0 | 15 / 15 | 0 / 15 |
| p12 | summary injection agent behavior | 5 / 7 | 15 / 15 | 0 / 0 |
| p13 | small context window coding agent | 10 / 15 | 15 / 15 | 15 / 0 |
| p14 | graph memory compaction | 15 / 15 | 15 / 15 | 0 / 0 |

**Notes on the counts:**
- Hits are capped at 15 per source.
- S2 throttled often (0 = no response, not "nothing exists"); OpenAlex carried those queries.
- arXiv needs every term to match, so it returns newest-first noise that was filtered by hand.

**Trails** (Semantic Scholar, refs + cites + recs, 25 each): PAIR (25 / 1 / 25; the one citing paper is SJC), Compact-Bench (25 / 0 / 25) and MemTrace (25 / 0 / 25).

**Abstract look-ups:** about 120 arXiv records through the arXiv API (full abstracts), plus 7 non-arXiv records through `lit.py get`.

**Full texts:** 2 read in full and 1 read in part, kept outside the repo.

**Verified references:** `2026-10-28-memory/refs.json` holds every paper cited here. `lit.py verify-file` on Oct 28 gives **48/49 OK**; every OK has a title match ≥ 0.95 and the author confirmed. The one failure is the flagged Zenodo DOI above. Output in `2026-10-28-memory/verify_out.txt`.
