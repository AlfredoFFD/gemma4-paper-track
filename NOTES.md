# Claude Code notes

Claude Code's side of the project. LOG.md is the shared research log; this file is kept separate so two agents
never edit the same file at once.

## 2026-09-30

- Created the repo skeleton (README, BRIEF, LOG, docs, prereg, experiments, paper, data) in `~/dev/gemma4-paper-track`.
  It lives outside a synced folder, because git and multi-GB task data sync badly there.
- Facts in docs/competition.md come from Claude Code's own logged-in reads of the Kaggle Overview and Data tabs
  (Sep 27 and Sep 30). A separate agent is reading Rules, Discussion, Leaderboard, Code and Writeups.

### 2026-09-30 19:12 EDT: Phase-0 pointer audit, decision rule fixed before any number is computed

**Why.** The lead direction ("finding vs remembering") assumes the provided graph can act as a 32k-context agent's
working memory, with symbol names as pointers to the code the fix needs. `data/HARNESS_README.md` (section 6.3)
changes what that can mean:
- `get_code_neighbors` and `get_code_subgraph` already return names only, so names-only lookups are the default,
  not something we add.
- `search_similar_code` is the only graph tool that returns code, and it returns the code of *other* nodes
  ("computes cosine similarity across all other nodes"). No harness tool returns a node's own text, so the graph
  cannot re-fetch a function. Re-fetching goes through `read_file` or `run_command`, with or without the graph.
- Graph text is frozen at base_commit, so it goes stale once the agent edits.

What is left for the graph as memory is names and edges. This audit asks whether those can point at the code each fix
touches, and whether that code is big enough, against read_file's limits, for pointer-style memory to save context.

Definitions:
- **Gold unit:** the innermost function, method or class that encloses a line the gold patch removes (located in the
  base file) or adds (located in the patched file). An added line whose enclosing def exists only after the patch
  belongs to the nearest enclosing scope that already existed (a class, or the module). Import lines and blank lines
  are ignored. Other lines outside any def or class are "module-level". Created files are "new files". Non-Python
  files are counted separately.
- **Addressable:** the unit's graph-style name is a node id in that task's graph. The name is the module path (a
  leading `src/` or `docs_src/` dropped, `__init__` handled both ways) plus the class chain and the def name. Nested
  defs are tried both as `outer.inner` and flattened to the nearest class or module, as the graph appears to do.
- **Full read cost:** characters returned by `read_file` to read every gold file end to end (a call returns 150
  lines or 10,000 characters, whichever comes first).
- **Window cost:** characters returned by `read_file` calls that start at the unit's first line and continue until
  its last line is covered. This is what a plain agent pays to look at the function again.
- **Unit cost:** the characters of the unit's own source.

Decision rule for Option 2 as "the provided graph as the agent's working memory":
- **K1 addressability.** Among tasks with at least one pre-existing Python gold unit, the share whose units are all
  addressable. Under 50%: KILL. 50-75%: WEAKENED (we would need our own symbol index). 75% or more: PASS.
- **K2 leverage.** The median full read cost per task. 10,000 characters or less (one read_file call): KILL, since
  the fix-relevant code then fits in one call and there is little to save. Otherwise PASS.
- **K3 compression.** The median over tasks of total window cost / total unit cost. Under 2: KILL. 2-5: WEAKENED. 5
  or more: PASS.
- **Overall:** KILL if any criterion says KILL, otherwise WEAKENED if any says WEAKENED, otherwise PASS.

Descriptive only, no decision attached: the characters a default `search_similar_code` call (k=10) returns for each
addressable gold unit, and how many of those 10 hits share the query's module; graph text vs source fidelity; the
share of async units; the largest node texts.

Scope: this can kill or weaken the mechanism, not confirm it. A PASS says there is room for pointer memory, not that
memory helps. Only agent runs can say that. Every number from this audit is EXPLORATORY for the paper.

### 2026-09-30 19:21 EDT: Decoy-bite check, decision rule fixed before any number is computed

**Why.** The pointer audit came back WEAKENED (numbers in the next entry), and an adversarial prior-art pass found the
32k-overflow and graph-as-memory space more crowded than assumed. The lead is moving to Option 1 ("why doesn't the
graph help"). Its core instrument is the decoy test: scramble the graph and see whether the agent follows the decoys.
That only works where the provided graph carries task-relevant structure that a scramble can remove. If it almost
never does, the end-to-end decoy test measures noise.

Question: from the symbols a task's issue text names, does one graph call surface a gold unit that the issue does not
already name?

Definitions:
- **Issue text:** problem_statement plus hints_text (the agent sees both).
- **Mentioned node:** a node whose full id, or a dotted suffix of it, appears in the issue text, or whose short name
  (last dotted part, at least 4 characters, not a dunder) appears as an identifier and matches at most 5 nodes in
  that graph (more is too ambiguous to query).
- **Gold node:** the graph id of an addressable gold unit from the pointer audit (`results/units.csv`).
- **Named directly:** the gold node's short name or dotted id appears in the issue text. A grep finds those without
  the graph.
- **Graph bite (registered):** a gold node that is not named directly but is a 1-hop neighbor (in or out) of a
  mentioned node whose degree is at most 50 (`get_code_neighbors` returns up to 50 by default).
- **Embedding bite (descriptive):** the same, with the 10 hits of `search_similar_code` on a mentioned node in place
  of its neighbors.

Decision rule for Option 1's end-to-end decoy test, on the share of all 129 tasks with at least one graph bite:
under 10%: KILL the end-to-end decoy test as the core design (keep only forced-consultation probes). 10-25%:
WEAKENED (the decoy test is confined to a subset, and resolve rate cannot be its outcome). 25% or more: PASS.

Descriptive only: embedding bite, 2-hop bite, the share of tasks where some gold node is named directly, and the
share of gold nodes with no edges. EXPLORATORY for the paper.

### 2026-09-30 19:24 EDT: Results of both checks (EXPLORATORY)

**Why.** Both decision rules were fixed above before any number was computed. Below: the registered verdicts, then
descriptive numbers, then post-data readings, each labelled. Claude Science should re-derive the headline numbers
with its own code before anyone builds on them.

Code and outputs are in `experiments/00-pointer-audit/`. Script sha256: `pointer_audit.py` 120a581a..., and
`decoy_bite.py` 2fa2b46a.... Input `tasks.jsonl` sha256: e4b3fd60.... Output hashes are in each summary JSON. Runtimes:
94 s and 42 s on the laptop CPU, Python 3.11.9, no GPU.

**Pointer audit. Registered verdict: WEAKENED.**
- **K1 addressability: PASS.**
  - 103 of 122 tasks (84.4%) have every pre-existing Python gold unit in the graph (unit level: 466 of 523, 89.1%).
  - All 19 failures are fastapi (18 of 64) or httpx (1 of 1).
  - 55 of the 57 missing units are async functions. The graph holds 1 of the 56 async gold units.
- **K2 leverage: PASS.** Reading the gold files once costs a median of 36,262 characters.
- **K3 compression: WEAKENED.** The median over 122 tasks of window cost / unit cost is 2.57. A plain agent that
  re-reads a 150-line window at a function pays about 2.6x the function's own size.
- **Descriptive.**
  - The median gold unit is 22 lines and 902 characters.
  - Graph text matches the source, ignoring whitespace, for 75.1% of addressable units. Class nodes are skeletons.
  - A default `search_similar_code` call on a gold unit returns a median of 6,509 characters of code (90th percentile
    26,522). On average, 1.77 of its 10 hits come from the query's module.
  - 67 of 127 graphs hold at least one node over 35,000 characters. The largest is 383,734.
  - The median problem statement is 418 characters, and the median hints text is empty.
  - 7 tasks have no pre-existing Python gold unit, and 11 create files.
- **POST-DATA readings** (decided after a 3-graph dry run; they do not change the verdict):
  - K3 without class-level units: 2.88.
  - K3 at unit level: median 3.33, quartiles 1.52 and 9.27.
  - K1 on package source only (no docs_src, tests or scripts): 104 of 120 (86.7%).

**Decoy-bite check. Registered verdict: WEAKENED, one task above the kill line.**
- 13 of 129 tasks (10.1%) have a gold unit that the issue does not name but that is a 1-hop neighbor of a node it
  does name (degree 50 or less). The kill line was under 10%, i.e. 12 tasks or fewer.
- By repo: fastapi 8 of 67, rich 4 of 48, requests 0 of 13, httpx 1 of 1.
- **Descriptive.**
  - Without the degree cap: 11.6%. At 2 hops: 19.4%. Using the 10 search hits instead of neighbors: 10.1%.
  - The issue names a gold unit directly in 27.1% of tasks.
  - The issue names at least one graph node in 75.2% of tasks (median 2).
  - 6.7% of addressable gold nodes have no edges.
- **Hand check (fastapi_15745).** The issue names APIRouter and APIRoute. One hop reaches
  APIRoute.get_route_handler, APIRouter.add_api_route and other gold units that the issue does not name, all through
  real edges in the graph file.

**What this means.**
- **Option 2**, "the provided graph as working memory", is WEAKENED, not killed.
  - The graph can point at the fix site in 84% of tasks, but not in fastapi's async code.
  - No harness tool returns a node's own text.
  - Fetching the exact function instead of a 150-line window saves about 2.6x, and any agent can already get that with
    grep and a ranged read_file.
  - What is left for the graph is names and edges.
- **Option 1**'s end-to-end decoy test is WEAKENED.
  - Only about 10% of tasks have task-relevant structure within one hop, so scrambling the true graph cannot move the
    resolve rate measurably.
  - Planted decoys still measure reliance on every task where the agent consults the graph: a wrong edge from a
    mentioned symbol, scored against the rate of visiting that sibling under the true graph.
  - The low reach is itself a finding for "why doesn't the graph help".

### 2026-09-30 21:25 EDT: Reply to Claude Science's loophole review (LOG.md 19:34), checked against the data

**Why.** The review makes claims about the audit that the data can settle. All numbers below are POST-DATA, from
`experiments/00-pointer-audit/postdata_review.py` (sha256 dfebefe5...). None changes a registered verdict.

- **Point 1 (K3 doesn't involve the graph): agreed.** Both arms are line-addressed reads, so K3 bounds the gain per
  re-read; it is not evidence about graph memory. The 19:24 entry already says the graph's share is names and edges.
  The downgrade of Option 2 rests on the harness fact, which stands: no graph tool returns a node's own text.
- **Point 2 (no criterion measures the lever): agreed.** Context saved = re-reads x cost per re-read, and only
  trajectories give the first factor. The pilot should log the re-read share and what filled the context at overflow.
- **Point 3 (unit definition):** module-level lines never entered K1. The code counts only def and class units; module
  lines go to a separate counter (`modlevel_lines`). Declared interpretation I-1, stated after the fact. The class
  pull on K3 is real: 2.57 with classes, 2.88 without (already listed as POST-DATA).
- **Point 4 (a name match may hit the wrong node): not supported.** For 350 of 380 addressable function and method
  units (92.1%, 95% CI 89.0-94.4%), the graph text equals the source, ignoring whitespace. The other 30 are 0.85-0.95
  similar (median 0.95), so they are the same function with small differences, not other nodes. Class nodes never
  match (0 of 85) because the graph stores class skeletons.
- **Point 5 (no margin for noise): agreed, and it matters for one verdict.**
  - K1 pooled: 103/122 = 84.4%, 95% CI 77.0-89.8%. The PASS holds; the CI sits above the 75% line.
  - K1 per repo: rich 45/45 and requests 12/12 (100%), but fastapi 46/64 = 71.9% (CI 59.9-81.4%). The async gap is a
    fastapi problem.
  - Decoy-bite pooled: 13/129 = 10.1%, CI 6.0-16.5%. It straddles the 10% KILL line.
- **Degree fork (decoy-bite): it flips the label.** The audit counts unique neighbors. If the harness lists each stored
  edge direction separately, the 50-entry cap means about 25 unique neighbors, and the share drops to 11/129 = 8.5%
  (CI 4.8-14.6%), a KILL. So the end-to-end decoy test sits at the KILL/WEAKENED boundary until the harness source says
  how get_code_neighbors counts. Either way resolve rate cannot be its outcome. The planted-decoy readership design
  does not depend on the true graph's reach.
- **Point 8 (registration not verifiable yet): agreed.** The commit is waiting on the team's go.

### 2026-09-30 21:25 EDT: Jev engineering synthesis (PDF), read in full; what it changes

**Why.** The team shared a 12-page synthesis, "Jev Engineering for Coding Agents" (Sep 2026). A copy is in
`private/refs/jev-engineering-synthesis-2026-09.pdf`, sha256 de20f148..., identical to the team's Zotero copy.

- **What it is:** an unaffiliated synthesis of design notes by TypeSafe's founder, not a paper. It reports no
  experiments. Its token-share table (reading files 30-40%, search 10-18%, writing code 4-10%) is labelled an
  illustrative estimate. Its only measured numbers come secondhand from Microsoft's "fastcontext" project: reading and
  searching are 56.2% of tool-use turns and 46.5% of main-agent tokens in GPT-5.4 trajectories. Unverified.
- **Ideas that touch our design:**
  - **Query-blind vs query-aware compression.** Compaction summarizes before the next question is known. That is what
    the harness's ADK compaction does.
  - **A per-chunk "visibility ladder":** hidden, short summary, long summary or full, decided per query.
  - **Tiered disclosure:** a cheap map first, detail on demand.
  - **Sub-agents** that get a small, purpose-built context and return a compact answer.
- **It does not change the pick.** "Let the graph decide what gets read in full" is Option 2 with a new mechanism, and
  our data already bounds it:
  - one hop from the issue's symbols reaches fix code the issue doesn't name in only 8.5-10% of tasks
  - the shipped tools can't return code at all
  - two rival entries (G-HRR, GraphSWE-Gemma) already pitch graph-guided context selection for Gemma 4
  - 2607.09691 reportedly found file skeletons no better than deleting the rest (unverified)
- **What we take from it:**
  - **A measurement for the pilot.** Log Gemma's token split at 32k by bucket (reads, re-reads, search, command
    output, prompt, thinking, edits) and the contents at overflow. Compare with the synthesis's illustrative table.
  - **A fix arm for the "too costly to read" channel.** A read-only explorer sub-agent (the AgentTool pattern the
    harness guide recommends) shows names, then signatures, then bodies. Its candidates come either from the graph
    or from a graph-free outline of the files. The difference isolates what the graph adds. Our reach numbers predict
    little.
- **For Claude Science's prior-art pass:**
  - fastcontext (Microsoft, repo-exploration sub-agent; the source of the 56.2% / 46.5% figures)
  - ast-outline (hierarchical outline, "pick the subtree")
  - recursive language models (A. Zhang, 2025)
  - jevgrep (semantic code search for agents, reported 40% cost cut)
  - headroom and rtk (context and tool-output compressors)

### 2026-09-30 21:44 EDT: The earlier chat's architecture report; what I checked; where the plan moves

**Why.** The team relayed the earlier coordination chat's output: `private/refs/agent-architectures-2026-09-30.md`
(sha256 4357d3a1...). This entry records what I checked against the data or a primary source, and what follows.

**Handoff hygiene.**
- The earlier chat stayed in its lane. It wrote only in `private/refs/` (gitignored); every tracked change since HEAD
  is Claude Science's (LOG.md) or mine.
- Its report is stamped "about 22:10 ET", later than the file's 21:34 write time. That is a clock slip; only the
  content matters.

**Checked tonight by Claude Code.**
- **21.9% duplicate vectors: reproduced exactly.** 80,707 of the 367,985 node vectors in the 127 .npz files equal
  another node's vector (per graph 0 to 37.5%, median 22.5%).
- **The aghasalim audit is a paper-track draft** (github.com/aghasalim/gemma4-code-graph-localization, PAPER.md,
  Sep 30). It runs no model. On all 129 tasks it maps gold patches to graph-style names, then ranks code from the
  issue text alone:

  | Method | hit@5 |
  |---|---|
  | embeddings | 0.29 |
  | graph (seeds plus one-hop call neighbors) | 0.30 |
  | grep | 0.41 |
  | BM25 | 0.48 |
  | BM25 without test code | 0.64 |

  It also reports no async functions, calls-only edges, and 57 of 129 issues with no name that matches a node. Our
  pointer audit and decoy-bite check cover the same ground. They count as corroboration, not novelty, and we cite
  both GraphLoc and this draft.
- **The official instructions misdescribe the search tool.**
  - The harness's own prompt section calls `search_similar_code` a way to "Find semantically similar functions/classes
    by keyword" (HARNESS_README 5.2).
  - The sample system prompt says to use it "with keywords from the error message".
  - But the tool resolves only node names (HARNESS_README 6.3).
  - This fits Claude Science's trace count: 114 of 135 searches in GraphLoc's base runs returned nothing.
- **The 16,384-token prompt cap matches the sample config.** `max_output_tokens` is 16,384
  (`data/sample_submission/configs/sampling.yaml`) inside vLLM's `max_model_len` of 32,768.
- **The 2607.09691 conflict is resolved.** One paper reports both the skeleton result (equal to deletion, N=70,
  p=0.75) and the ~9% run-to-run flip rate. Both descriptions were right.

**Not checked by me** (left for Claude Science's task A):
- G-HRR's setup (the earlier chat confirmed only that the repo makes the claims)
- 2609.20804
- RepoAtlas's push-vs-pull numbers
- SWE-Gym's LoRA recipe
- the jevgrep and pi-jev-context figures

**Where the plan moves.** The direction stays Option 1, but its center moves.
- **The offline "why" is taken.** GraphLoc (localization, end to end) and aghasalim (offline audit) are both
  paper-track entries on this data.
- **What is left, and new, is behavior.** Measure it as a funnel, with causal tests at each stage:
  - **Query:** does the agent query in a form the tool understands? Mostly not: 114 of 135 searches came back empty,
    and the official instructions point it toward keywords.
  - **Uptake:** when a result comes back, does the next action use it?
  - **Reliance:** when the graph is wrong, does the agent follow it? Test this with planted decoys.
  - **One causal fix at the leakiest stage:** correct the tool description, or add a keyword-to-name lookup. Then
    measure the shift at every stage and in resolve rate. If graph use rises but resolve rate doesn't move, reach is
    the ceiling (8.5-10% of tasks). Either way the result is informative.
- **The "externalized memory" framing still fits.** The graph is a memory indexed by names, and the agent probes it
  with keywords. Retrieval fails when the cue doesn't match the index, which memory research calls encoding
  specificity (Tulving and Thomson, 1973).
- **Triage of the earlier chat's angles:**
  - **Keep:** "why the graph adds about one task". It is this funnel.
  - **Park:** the 2x2 of read policy x address scheme. The evidence predicts small effects at high cost:
    - re-reads are 10.3% of context characters
    - overflow ends 4.1% of GraphLoc's runs, because compaction does fire at 14,336
    - skeletons equal deletion (2607.09691)
    - reach is 8.5-10%

    It also overlaps G-HRR.
  - **Park as a possible second writeup:** the graph as pushed, write-back memory. It fits the framing best and sounds
    the most novel, but it needs a pre-step (a SequentialAgent with `output_key`) or a modified harness, and nothing
    yet shows it helps.
  - **Kill as a headline:** patch-loss accounting. Overflow is rare in the competition's configuration (26 of 636
    runs), and 2609.20804 already documents overflow at 32k.
- **The repaired-graph reach check I proposed at 21:25 drops in priority.** It answers a content question, which the
  funnel ranks below query and uptake, and the rivals already cover that ground. Revisit it if the interface fix
  raises graph use without moving resolve rate.

**Pending.**
- **Wheelhouse source** (Claude Science's request, LOG 21:34). The v28 wheels swegemma-0.2.7, adk_submission-0.2.12
  and adk_eval_core-0.1.0 total 273 KB. The download waits on the team's go. The Kaggle CLI has no version flag, so v25
  may need the website.
- **Before any local run:** confirm the graph tools are enabled when only the commit-named graph files exist (Claude
  Science's flag).
- **About the commit that follows this entry:** it freezes the record from now on. It cannot prove the 19:12 and 19:21
  rules came before their data; only file times speak to that, so those verdicts stay EXPLORATORY. From here, rules
  go into `prereg/` and are committed before their run.
