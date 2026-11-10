# Claude Code notes

Claude Code's side of the project. LOG.md is the shared research log; this file is kept separate so two agents
never edit the same file at once.

## 2026-09-30

- Created the repo skeleton (README, BRIEF, LOG, docs, prereg, experiments, paper, data) in `~/dev/gemma4-paper-track`.
  It lives outside the cloud-synced folder, because git and multi-GB task data sync badly there.
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
`private/refs/jev-engineering-synthesis-2026-09.pdf`, sha256 de20f148..., identical to the team's copy.

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

### 2026-09-30 23:58 EDT: Harness source downloaded for Claude Science (v25 and v28); what it settles

**Why.** Claude Science asked for the harness source (LOG 21:34), and the team approved the download. The files are
the organizers' Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse`, three wheels per version.

**Paths** (gitignored). Each version's wheels are unzipped into `src/` next to them.

- `data/wheelhouse/v25/` (dataset version 25, files dated Sep 27 11:49 UTC; the closest to GraphLoc's runs):

  | Wheel | sha256 prefix |
  |---|---|
  | swegemma-0.2.7 | 2b74d402 |
  | adk_submission-0.2.11 | d14f7d31 |
  | adk_eval_core-0.1.0 | b1608c44 |

- `data/wheelhouse/v28/` (the latest, Sep 30 20:33 UTC):

  | Wheel | sha256 prefix |
  |---|---|
  | swegemma-0.2.7 | 27a2f60f |
  | adk_submission-0.2.12 | 077c438c |
  | adk_eval_core-0.1.0 | 194dd8f9 |

- Both swegemma wheels are labelled 0.2.7 but their code differs: graph tools, graph utilities, context, edit,
  execution and workspace tools. **Record the dataset version, not the package version.**
- To fetch a specific version with the CLI, write it as a third path segment:
  `kaggle datasets download metric/gemma-4-developer-agent-wheelhouse/25 -f <file>`.

**Read from the source.** I ran none of this; the package needs google-adk to import.
- **Neighbor lists, both versions:** de-duplicated, sorted alphabetically, then cut to `max_neighbors` (50)
  (`graph/graph_utils.py`, `get_neighbor`). This settles the degree fork in the decoy-bite check:
  - Unique neighbors were the right reading, so the 25-unique KILL reading does not apply.
  - For a node with more than 50 neighbors, the harness returns the alphabetically first 50. The true share
    therefore lies between the registered 10.1% and the uncapped 11.6%. WEAKENED stands.
- **v28 caps graph output** at `max_stdout_chars` (5,000 characters) per call. Search splits that budget across its
  hits (`_allocate_code_budgets`). My search-payload numbers (median 6,509, p90 26,522) and GraphLoc's 55k-character
  search overflow describe v25-era behavior, not v28.
- **v28 search excludes the query node** (`retrieval_utils.py`: `sims[target_index] = -np.inf`).
- **The agent-facing wording is unchanged in v28.** The prompt still says search finds code "by keyword"
  (`harness/agent_runner.py`, line 178).
- **Graph tools are offered when the commit-named files exist**, `<repo>_<base_commit>.json` and `.npz`, checked
  first. The logic is identical in v25 and v28, so our local data layout enables them.
- **Likely regression, to confirm by running:**
  - v25's `get_neighbor` resolved short names: exact, then suffix, then case-insensitive, then substring.
  - v28's version calls `graph.has_node` on the exact id only, and the tool passes the agent's string through
    unchanged.
  - If that's right, `get_code_neighbors("APIRoute")` returns an empty list in v28. Only a fully qualified id
    (`fastapi.routing.APIRoute`) works.
- **Compaction at scoring is not in these wheels.**
  - `swegemma/config.py` defaults `events_compaction_config` to None.
  - The 14,336 setting lives in the scoring script (`scripts/inference.py` per HARNESS_README), which this dataset
    does not ship.
  - GraphLoc passed it explicitly.

### 2026-10-01 00:05 EDT: Plan re-ranked on the team's stated goal (a bold, positive result), not on new evidence

**Why.** The team made the goal explicit: a novel, positive result that pushes a boundary, not a diagnosis of what
fails. The evidence has not changed since 21:44. What changed is how much risk we accept. On that goal, the option I
parked at 21:44, the graph as the agent's working memory, ranks first.

The plan is one paper in two acts.
- **Act 1 (cheap, mostly in hand): the graph fails as a search tool.**
  - Rivals cover the offline side (GraphLoc, aghasalim).
  - We add the behavioral side:
    - the agent is told to search "by keyword", while the tool takes exact names (114 of 135 searches empty)
    - neighbor lookups need fully qualified names in v28 (from code reading, not yet run)
    - one hop from the issue reaches unnamed fix code in about 10% of tasks
- **Act 2 (the bet): the graph as the agent's working memory.**
  - The agent carries no transcript. Each step's context is assembled from:
    - the task
    - a compact memory keyed by graph nodes (each entity the agent has touched, with a status such as suspect, ruled
      out, edited or verified, plus its graph relations)
    - the latest observation
  - Implemented declaratively: a LoopAgent whose worker runs with `include_contents: none`, reads the memory from
    session state through the instruction template, and writes it back through `output_key`.
  - Must be confirmed in a test before any design is frozen: ADK's semantics for `include_contents` and for optional
    template keys (google_adk 1.36.1 is in the wheelhouse).
  - Comparison arms: the standard transcript agent, a flat-notes memory, and the graph-keyed memory. An optional
    ablation varies how the memory graph is written out as text.
- **Why it can work at all.** In the scoring configuration the usable prompt is about 16k tokens, and compaction
  starts at 14,336.
  - In GraphLoc's base runs, compaction fired in 68% of runs (Claude Science, EXPLORATORY), while overflow crashes
    ended 4%.
  - So forgetting is the common failure. A loop that never accumulates a transcript avoids it by construction.
- **Nearest work, to attack first:** Context-Folding (2510.11967), SWE-MeM (2606.28434), AgentFold, MEM1, and Codex's
  experimental notes/new_context mode. All of these train the model, or are unevaluated. Ours is untrained,
  graph-keyed, at about 16k, in the official harness. Not yet checked adversarially.

**Kill check this week (no GPU):** GraphLoc's 636 public traces.
- Does compaction cost anything? Within the same task, compare runs where compaction fired with runs where it
  didn't:
  - the re-read share after compaction
  - repeated failed actions
  - resolve rate
- If compaction is harmless, Act 2 has nothing to fix. We drop it and Act 1 stands alone.
- Exact thresholds go into a `prereg/` file before the traces are recounted.

### 2026-10-27 15:40 EDT: Catch-up; lit sprint on delivery x truth; the plan changes

**Why.** The team resumed with 16 days left (deadline Thu Nov 12, 11:59 PM UTC). It asked for the
strongest question, a tie-in to an earlier multi-agent study (kept out of the repo), and a NotebookLM workflow. This entry records what the
reading found and what it changes, so Claude Science can revise its pre-registration draft.

**Lit sprint** (report: `docs/lit/2026-10-27-delivery-lit-sprint.md`):
- **Reading:** 18 papers read in full, plus the GraphAudit writeup. Notes are in `docs/lit/2026-10-27-delivery/notes/`, each with a coverage line. The last four finished at about 15:45. None changes the verdict.
  - 2610.26836 narrows it: a true fork from a saved GPT-5.2 state, varying only whether a true observation is inline or one read away, costs 9.4 points [-14.5, -4.6]. That is scientific QA with final answers.
  - So forking a state to vary delivery is not ours to claim. What stays open: code-graph structure, false edges vs base rates, next read or edit as the outcome, and the channel varied with the text fixed, on a small 4-bit model.
- **Searches:** 52 searches and 15 expansions on Oct 27, 14:49-14:56 EDT.
- **Citations:** `lit.py verify-file` gives 35/35 OK.
- **Verdict: open in what we searched, only as a combination.**
  - Pulled vs pushed delivery is partly done (2609.05587 includes Gemma-4-31B).
  - Planted decoys in repair are partly done (RepoMirage).
  - Forks from saved agent states are partly done (CRR, RippleCP, PAIR).
  - No one holds the state and the code-graph facts fixed while varying asked-for vs handed and true vs false edge, scoring the next read or edit against the same-state base rate.
- **The papers disagree on direction.**
  - Pushed content is adopted more for retrieval (Gemma-4-31B +17 to +19 points, 2609.05587).
  - It is adopted less for the output of code the agent ran (2609.05587). Oracle Poisoning (read in full at 15:40)
    shows the same for poisoned code-graph data: GPT-5.1 trusts it 0% as prompt prose vs 100% as a tool result, and
    Claude goes the other way. There the data is visible in every arm, so it is a channel and format effect on trust,
    not uptake. It does not contradict our plan, and its Table 7 (a harness-built tool result is trusted like a real
    call) supports the inserted-call arm.
  - Our forks separate uptake from trust given exposure. No paper does.

**What changes in the plan, and why** (new evidence, not new appetite):
- **Act 2 (the graph as working memory) moves to future work.** It is not disproven. Three reasons:
  - It needs full end-to-end runs, which are underpowered at 106 tasks.
  - Its upside is bounded: overflow ends 4% of GraphLoc's runs, and 2609.20804 finds context management mostly prevents overflow.
  - Memory-delivery prior art now covers the delivery half: 2607.20972, 2609.32590.
  - The Oct 1 kill check (does compaction cost anything) never ran.
- **Act 1 becomes the uptake-vs-trust fork experiment** (Part 2 of the report). Arms:
  - A, as shipped;
  - P, an inserted `get_code_neighbors` call plus its real result;
  - H, the same text as a harness note;
  - P' and H', one edge swapped for a plausible non-neighbor;
  - N, a neutral restatement;
  - R, optional, a degree-preserving random graph.
- **Primary outcome:** Claude Science's Sep 30 uptake definition, minus the same node's touch rate in arm A at the same state and seeds.
- **Why forks:** Claude Science's Oct 1 count (next action touches a returned node in 13 of 43 events vs 15.8% for random code in the same files) is observational. The agent asks only about code it is already heading toward, so it cannot separate steering from selection. Forks can.

**Checked or corrected for the record:**
- **RepoAtlas (2609.16936):** the requested views were *obtained* in 40.5% of instances. That is not the share of instances that requested them.
- **Don't Blindly Trust It (2606.21409), read in full.** It reruns one fixed loop (temperature 0, one seed) on QA with only the observation changed, and scores final answers only. These are reruns, not forks. Its "value inversion" may be abstention, since FEVER accuracy is below chance.
- **GraphAudit (Kaggle), read in full.** It is a retrieval study plus a one-shot file choice by a local 8B Gemma 4 in Q4, with degree-preserving random graphs as the null. It has no agent loop, shows no edges to the model and was not pre-registered. Real minus random file recall is 3.1 points [+0.7, +5.6]. It doesn't take our idea. We borrow its random-graph control.
- **G-HRR** stays out of all evidence (Oct 1: no model call in its code).
- **One statistic not to carry forward:** the K1 audit (84.4%) measures whether gold units are in the graph. It is not a rate of wrong edges. The graph's known gaps are missing async functions (it holds 1 of 56) and class skeletons. No natural wrong-edge rate has been measured.

### 2026-10-27 17:30 EDT: Novelty headline is discrimination (true vs false edge at the same state)

- **Proposal (the team decides at the Thu Oct 29 go/no-go):** lead the novelty claim with H2. At the same fork state, does Gemma follow a false edge as readily as a true one, scored on the next read or edit against arm A? The asked-vs-handed contrast (H3) stays as the hook and a secondary hypothesis.
- **Why.** In the sprint's own grid, the channel half has close neighbors. 2610.26836 forks a saved state to vary how true information is delivered. Oracle Poisoning compares tool result vs prompt text (§5.4) and harness-inserted vs model-initiated calls (Table 7). No paper we read compares true and false at the same state (report Part 1, "Shared assumptions", item 3). No new evidence came in; this is the grid re-read for the novelty criterion. It replaces the uptake-vs-trust split as the answer to risk 2 in report Part 2.
- **Edits:**
  - report Part 2: H2 marked as the proposed primary; risk 2 reworded;
  - Claude Science prompt: discrimination as primary, with an equivalence margin so "doesn't check" can be claimed;
  - teammate draft: one question, no papers or numbers.

### 2026-10-28 14:30 EDT: Hackathon-mode plan (three experiments); memory check result

**Why.** The team asked for the most ambitious plan that can win. It also asked whether memory should stay future work: pursue it if it's good, drop it if it's already done. A focused literature check settled the memory question.

- **Memory check** (`docs/lit/2026-10-28-memory-check.md`).
  - **What was read:** PAIR (2609.36526) and Compact-Bench (2610.31710) in full, 2610.20927 in part, and about 120 abstracts. The check verified 48 of 49 citations; one Zenodo DOI was flagged.
  - **Graph-keyed working memory as an architecture:** partly done. Compact state memories kept beside the transcript help coding agents with no training (Ledger 2608.00808, StateHarness 2610.17616; abstracts).
  - **Post-compaction forks:** done. Compact-Bench damaged 5–64% of 22 validated repairs across 14 summarizers; Claude Code checked this against the paper's text.
  - **Wrong summary entries carried out:** reported (2610.20927, partial read). Read it in full before citing it.
  - **Open in what we searched:** true vs false entries at the same state, scored against the no-note base rate, and whether compaction makes the agent more credulous.
- **Plan** (report Part 2, "The three experiments"):
  1. True vs fake link after the issue is read. This is the core and carries the novelty.
  2. The same test right after compaction (the credulity shift).
  3. The fix: full runs with the graph and a memory note pushed in, pre-registered on the tasks where one or two hops reach unnamed gold, with a harm check. This is an application, not a novelty claim.
- **What changed.**
  - Memory leaves "future work" in a narrower form: experiment 2, plus a component of experiment 3.
  - Full runs come back, focused where the graph can matter.
  - The Claude Science prompt now covers both experiments. Its compaction check measures evidence-to-edit loss first, since Compact-Bench found re-reads rare in code.
- **Risk (a guess):** PAIR's group publishes compaction papers roughly monthly, so a controlled-insertion follow-up before Nov 12 is plausible. Speed matters.

### 2026-11-08 18:40 EDT: Go; traces downloaded; fork states exported; replay runner built; pilot pushed to Kaggle

**Why.** The team said go on Nov 8 with four days left, as a solo pilot-scale run, and asked Claude Code to do all of it. Claude Science never received the Oct 27 prompt (its log still ends Oct 1), so its tasks were done here.

- **Traces.** GraphLoc's three end-to-end notebooks and their outputs (636 ATIF traces, about 92 MB) are in data/graphloc/ (gitignored). Loader: analysis/graphloc_traces.py. Counts match Claude Science's Oct 1 entry: 318 base and 318 skill runs; 8 get_code_neighbors calls in the base arm, each returning a sorted JSON list.
- **Harness facts that matter for the replay.** The traces are ATIF-v1.7 as written by adk_eval_core: one agent step per model call with thought text, tool calls, the tool result as JSON, and vLLM token usage. The system prompt is in the trace and is byte-identical to the sample prompt. The base agent is the sample prompt with the nine tools, no adapters and no sub-agent. Compaction is visible as a prompt-token drop. The Kaggle wheelhouse moved on Oct 12 to swegemma 0.2.11 and adk_submission 0.2.13 (local v28 is 0.2.7 and 0.2.12); only docstrings of the graph tools changed. ADK re-sends model thoughts as reasoning_content in the history, and Gemma 4 tool results go to a tool_responses role when the model name contains gemma4.
- **Fork states** (analysis/fork_states.py, rules in its docstring, EXPLORATORY): 525 states from 241 runs and 88 tasks, up to three per run. The node choice and decoy rules were changed twice before any replay: the first export chose hub classes named in every issue (FastAPI, 50 neighbors) and traceback tokens (File, line); the second showed that true neighbors mostly sit in the file just opened, so the compared entries now both live in unopened files. Observed base rates from the traces: the agent's own next call touches an unopened listed neighbor in 34 of 525 states and the swapped-out entry in 11.
- **Replay runner** (analysis/replay.py): the history is loaded into the harness's own compiled agent as ADK events; the arm's last piece is the new message; the run stops at the first model response; no tool executes. Local test with a fake model: the five arms share a byte-identical 17-message prefix; nine tool declarations; the system prompt renders from system.md.
- **Kaggle.** Private dataset gemma-graph-forks-inputs (states, replay.py, agent config, both harness wheel sets) and private script kernel gemma-graph-forks-pilot (analysis/kaggle/forks_pilot.py), version 1 pushed at about 18:35 EST, 4 x L4, no internet. It records versions.json, runs a 12-state fidelity check (replayed vs logged prompt tokens), then 525 states x 5 arms x 3 seeds with a 9-hour budget in a fixed shuffled order. Analysis script: analysis/analyze_forks.py. Pre-registration: prereg/02-discrimination-forks.md (DRAFT; the team approves it Mon Nov 9, 9 PM).
- **Schedule.** Nov 9 9 PM approve the pre-registration; Nov 11 7 PM edit the draft; Nov 12 noon submit.
- **Not done.** No commit (nothing was asked). Claude Science is out of the loop. The teammate has not replied.

### 2026-11-08 19:20 EDT: Independent re-derivation of the GraphLoc trace numbers (EXPLORATORY)

**Why.** The project rule: every headline number is re-derived from the raw logs with an independent script before it enters the paper. Script: analysis/trace_stats.py, output analysis/trace_stats.json.

- **Matches Claude Science's Oct 1 entry:** 109 of 318 base runs call a graph tool; 26 get a non-empty result; search_similar_code 135 calls, 114 empty; get_code_neighbors 8 calls; get_code_subgraph 0; compaction (a prompt drop of more than 30%) in 216 of 318 base runs (68%).
- **Uptake, different denominator and control.** This script counts 26 events (a non-empty graph result followed by a read or edit, base arm only) with 13 hits (50%); Claude Science reported 13 of 43 (30.2%), presumably counting both arms or events without a following read. The control here draws the same number of random nodes from the same files as the returned nodes and gets 36.4%, against Claude Science's 15.8% for size-matched random nodes; the same-files control is stricter because whole-file reads touch every node in a file. Reading: the next action lands on a returned node about as often as on any other node of the same files, so the traces alone cannot show steering. The forks are the test.
- **Later edits:** a returned node's file is edited later in 8 of 26 events, inside the node's span in 1 (Claude Science: 1 of 48).
- **Overflow:** not re-derived here (the ATIF traces do not carry the vLLM error; Claude Science read the run records).
- **Also seen:** search_similar_code results carry similarity 0.9999 for unrelated test functions (the duplicate-embedding problem from the Sep 30 audit), so even non-empty search results are mostly noise.

### 2026-11-08 21:35 EDT: Review rounds 3 and 4; truncation caps; 407 states

- **Codex round 3:** reversed or boolean read ranges passed validation; pipeline ranges (sed then head) were scored in file coordinates; a file named headers.py read as a head command; an empty run produced exact estimates. Fixed: strict range validation, a pipeline-aware shell view parser (stages split on the pipe, command word per stage, default head/tail of 10, single-line sed, grep counts only by name), no estimate without eligible pairs. Unit tests on the review's cases pass.
- **Codex round 4:** the harness caps read_file at 150 lines and 10,000 characters and shell output at 5,000 characters (swegemma/budget.py; every trace read without a range reports end_line 150), so "whole-file read" never meant the whole file. Fixed in both places: what counts as shown when a state is built uses the observation's real start and line count; replay scoring applies the harness's caps with the file's line lengths. Pre-registration clarified with the time.
- **Effect:** 407 states from 77 tasks (more nodes are now fresh). Observed base rates: the swapped-out entry touched by the agent's own next call in 1 of 407 states, any unopened listed neighbor in 12 (2.9%). Trace uptake re-derived with the caps: 7 of 26 (27%), same-files random control 23%.
- **Kaggle:** v4 could not start: the account's two batch GPU slots are held by v2 and v3, which keep running after a new push. Stopping them needs the Kaggle web UI (Chrome is not signed in to Kaggle).

### 2026-11-09 00:40 EST: Run v4 complete; fidelity gate failed and diagnosed; v5 pushed as the confirmatory run

**Why.** v4 (Nov 8, 8:32 PM to Nov 9, 12:16 AM; 3.7 h for 6,105 replays, 9 context-window errors) delivered the first numbers. Its fidelity gate failed, and the cause changes the replay construction but no rule.

- **Fidelity.** Median absolute relative difference between replayed and logged prompt sizes: 6.1% in arm A (gate 2%). The excess correlates 0.99 with the size of the earlier thoughts in the history, and the arms ending with a user note (H, H') match the logged sizes at 1.3%. So the original runs carried no earlier thoughts; vLLM renders re-sent reasoning only when the conversation ends with a tool result. v5 drops thoughts from the history (replay.INCLUDE_THOUGHTS = False) and samples 24 states for fidelity. The v4 confound also made P and H differ by the thoughts, not only by the channel.
- **v4 outcomes (EXPLORATORY, approximate forks; analysis/results/v4/analysis.txt).** Following is near zero everywhere. Any listed unopened true neighbor touched: A 2.2% [0.9, 3.6], P 4.0%, P' 3.9%, H 2.6%, H' 3.2%. H1 diff +1.1 points [0.4, 1.9]. The swapped-out true entry was followed in 0.2% of replays (5 of 2,376) and the decoy in 0 of 2,442; D = 0.2 points [0, 0.7]. Channel: P minus H +1.4 points [0.2, 2.9] for any-true; arm A's next call is a graph tool in 0.6% of replays. Arms ending with the note produced about 2.5 times more completion tokens (median 185 vs 71): a user note restarts thinking; a tool result does not.
- **Reading, pending v5.** At the navigation step, Gemma almost never follows the list it is given, true or false. The discrimination test is then uninformative by construction (5 events vs 0), which the pre-registration anticipated ("if following stays near the base rate in every arm, the paper reports that as the result"). The paper's headline becomes "handing Gemma the graph at the moment of choice barely moves its next step", with the channel and the thinking-restart as the texture.
- **Kaggle.** v3 (old states) still running; v4 outputs in analysis/results/v4/; v5 pushed about 00:40.

### 2026-11-09 07:50 EST: Confirmatory run v5 complete; fidelity gate passed; results

**Why.** v5 (Nov 9, 00:40 to 04:45 EST; 4.1 h; 6,105 replays; 0 errors) is the pre-registered run. Analysis in analysis/results/v5/analysis.txt, raw outputs in analysis/results/v5/forks/.

- **Fidelity: PASS.** 24 states, median absolute relative difference 1.66% (gate 2%), mean 3.0%. Every replayed prompt is a little smaller than the logged one (median about 150 tokens; plausibly the traces' era tool declarations). Two outliers at 9.5% and 25% (fastapi_15588 r3 f1, fastapi_14986 r2 f1) are reported; the cause is under check. The note arm now sits 178 tokens above arm A, the inserted call 181 above: the arms differ only by their last piece.
- **H1 (following above base), not supported.** Any listed true neighbor in an unopened file touched by the next call: A 2.1% [0.9, 3.7], P 3.1% [1.5, 4.8], P' 3.3%, H 2.8% [1.4, 4.5], H' 2.9%. Pooled P and H minus A: +0.8 points [-0.1, +1.7].
- **H2 (discrimination), not tested, per the pre-registration's rule when H1 fails.** Descriptively: the swapped-out true entry was followed in 0.25% of its replays (6 of 2,358) and the decoy in 0 of 2,442; D = 0.25 points [0, 0.76].
- **H3 (channel), no detectable effect on following:** P minus H +0.25 points [-0.7, +1.2].
- **H4:** arm A's next call is a graph tool in 0.34% of replays [0.08, 0.68].
- **Secondary (EXPLORATORY, pre-listed as secondary):** after an inserted graph call, the next call is a graph tool in 3.2% of replays (P) and 2.9% (P'), against 0.3% in A and 0.6% in H: a tool result begets another call, a note does not; 27 of those 65 calls query a listed entry. A note restarts thinking (thought text in 99.6% of replays, median 185 completion tokens) where a tool result does not (A 58%, 98 tokens; P 72%, 127). In its thinking, the agent names a fresh true entry in 10% of note replays and 5% of tool-result replays, and the decoy in 2% and 1%.
- **Reading.** At the navigation step, Gemma neither follows nor checks the graph: a list of its neighbors moves the next read or edit by at most about a point, true or false, asked for or handed. The visible effects are on behavior around the graph, not on where it goes: re-asking after a tool result, and re-thinking after a note.
- **Interface failures:** 21 of 6,105 (malformed arguments 12, no call 9), spread across arms.

### 2026-11-09 13:05 EST: Experiment B running (v6), rewired control pushed (v8); review and peer corrections

**Why.** After the v5 result (following near base in every arm), the team asked what would make the contribution strong enough and said go. Pre-registration 03 adds framing (an instruction instead of a report), encoding (names with file, lines and definition line) and, on a second session's proposal relayed by the team, a degree-preserving rewired-graph control (GraphAudit's) to separate structure from vocabulary.

- **v6 (D, D', E; 3,663 replays)** started 12:50 PM with states whose v5 arm texts are byte-identical to the confirmatory bundle; local plumbing test passed; review hook clean.
- **Rewired control.** The first construction let rewired entries sit in files the agent had already opened, while true entries are scored only in unopened files; the review hook caught it (126 of 407 states). Fixed: rewired entries meet the same eligibility (unopened, non-gold file, unseen name). The kernel carrying the first lists (v7) was cancelled in the Kaggle UI before it produced anything; the corrected run is v8 (R_D, R_E; 2,442 replays), queued at 1:01 PM. 847 of the rewired entries across 298 states are directory padding; 25 lists are shorter than the true list. Rule B4 and these facts are in prereg/03 with corrected times (two clock errors in my timestamps were fixed in place; the rules were written before the runs in every case).
- **Peer session.** Replied through the session messaging that the control runs as v8 after v6 and that this session owns the repo and runs.
- **Compute.** Kaggle's two-session limit and weekly quota are the constraints; the team offered Colab compute units (about 1,188) as a reserve, to be connected only if Kaggle blocks a run.

### 2026-11-09 19:05 EST: Experiment B pooled result (v5 + v6 + v8); Kaggle GPU quota spent; arms E', EL, ES in preparation

**Why.** The pooled result of pre-registration 03 existed only in a scratch output, and the compute constraint was nowhere in this log. Both must be durable before the next run is designed. [team] decided at 5:31 PM on one more run with three arms, then writing.

- **Runs.** v6 (D, D', E; 3,663 replays) and v8 (R_D, R_E; 2,442 replays) completed. The v8 log records the harness variant at install: v28 (adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7), the same as v5 and v6.
- **Pooled analysis (frozen `analysis/analyze_b.py`, run 4:01 PM):** 12,210 replays over 407 states; 388 states are complete across the 10 arms and 3 seeds, so every rate below is over 1,164 replays per arm. Intervals are 95%, clustered by state, 2,000 resamples.

| Arm | Any unopened true neighbor touched | Swapped-out entry touched | Decoy touched | Any entry of the rewired list touched |
|---|---|---|---|---|
| A | 2.15% [0.86, 3.61] | 0.17% | 0 | 0 |
| P | 3.01% [1.55, 4.64] | 0.17% | 0 | 0.17% |
| P' | 3.35% [1.80, 5.07] | 0.17% | 0 | 0.26% |
| H | 2.75% [1.37, 4.30] | 0.34% | 0 | 0.26% |
| H' | 2.84% [1.37, 4.38] | 0.26% | 0 | 0.43% |
| D | 4.30% [2.58, 6.10] | 0.34% [0, 0.95] | 0 | 0.34% |
| D' | 3.78% [2.23, 5.58] | 0.34% | 0.34% [0, 0.95] | 0.09% |
| E | 8.25% [5.76, 10.91] | 1.80% [0.69, 3.01] | 0 | 0 |
| R_D | 2.32% [1.03, 3.78] | 0 | 0 | 0.52% [0, 1.29] |
| R_E | 2.41% [1.12, 3.87] | 0.09% | 0 | 1.03% [0.34, 1.89] |

- **B1 (framing, D minus H): +1.55 points [0.60, 2.66]: confirmed.** An instruction to look at the neighbors lifts following, by a point and a half.
- **B2 (discrimination under instruction): underpowered by its own rule.** The swapped-out entry is touched in 0.34% of D replays, below the 5% floor. D_B = 0.00 [-0.77, 0.77] (95%), [-0.60, 0.69] (90%); reported, not interpreted.
- **B3 (encoding, E minus H): +5.50 points [3.44, 7.65]: confirmed.** Written with file, lines and first definition line, the same neighbors are followed three times as often as under bare names (8.25% against 2.75%) and 3.8 times the no-list base rate.
- **B4 (structure versus vocabulary): "structure matters".** D minus R_D: +3.78 points [2.15, 5.67]; E minus R_E: +7.22 points [4.64, 9.97]. Both doses pass the 3-point rule with intervals excluding 0.
- **Caveat on B4 (arithmetic from the table, no interval yet).** The pre-registered contrast does not subtract base rates: true neighbors are touched 2.15% of the time with no list at all, rewired entries 0%. Lift over arm A: E 6.10 points against R_E 1.03 (difference 5.07); D 2.15 against R_D 0.52 (difference 1.63). The gap survives at the E dose and is small at the D dose. The paper must report the adjusted contrast with intervals (exploratory script, pending) beside the pre-registered one.
- **Interface failures:** 34 of 12,210 (malformed arguments 24, no call 10; no errors, no unknown tools). By arm: A 7, P 4, P' 6, H 0, H' 4, D 1, D' 2, E 3, R_D 3, R_E 4.
- **Secondary outcomes (pre-listed).** Graph tool as the next call: A 0.34%, P 3.35%, P' 3.01%, H 0.60%, H' 0.69%, D 0.26%, D' 0.60%, E 0.17%, R_D 0.60%, R_E 0.26%. Thought text present: A 56.4%, P 71.4%, P' 71.6%, every note arm at least 99.6%. Median completion tokens: A 90, P 120, P' 121, H 182, H' 183, D 178, D' 180, E 189, R_D 186, R_E 198. Thought mentions a fresh true entry: A 3.7%, P 5.4%, P' 4.6%, H 10.7%, H' 8.9%, D 12.2%, D' 9.0%, E 11.0%, R_D 6.6%, R_E 7.3%. Thought mentions the decoy's short name: A 1.0%, P 1.3%, P' 0.7%, H 2.1%, H' 2.6%, D 2.4%, D' 3.4%, E 2.5%, R_D 2.2%, R_E 2.6% (the 1.0% in A is the string-match base rate of this metric). Share of `read_file` among next calls: A 59.4%, H 55.2%, D 64.3%, E 65.5%, R_D 57.0%, R_E 55.2%.
- **Reading (descriptive, to be tested by the any-means analysis).** The thought text names a fresh true neighbor about as often under bare names (H 10.7%) as under the legible encoding (E 11.0%), while the touch rate triples. The model notices the names under every wording; it acts on them mainly when they arrive with a location and a signature. Whether following under bare names goes through a search the touch metric does not count is open until the any-means table exists.
- **Not yet independently recounted.** Every number above comes from the frozen analysis script. The independent recount required before a number enters the paper was started and stalled without leaving output; it is being relaunched. A re-run of the frozen script at 5:39 PM produced a file of the same size as the 4:01 PM output (not diffed).
- **Kaggle GPU quota is spent until after the deadline.** Queried through the Kaggle API at 3:56 PM EST: "used 1 day, 15:53:14 | reserved 0:00:00 | allowed 1 day, 6:00:00 | refresh 2026-11-14 00:00:00". About 39.9 GPU-hours used against 30 allowed; the refresh is after the Nov 12 deadline. No further Kaggle GPU run is possible before submission; the Colab reserve is the only path for a new run and needs the team's go and their own token entry.
- **Docker image pin (not recorded before).** `analysis/kaggle/kernel-metadata.json` pins the kernel image by digest (`sha256:37c64f7d...`). On Nov 8 the default image had moved to Python 3.13 and rejected the wheelhouse's cp312 wheels ("is not a supported wheel on this platform"); v5, v6 and v8 ran on the pinned image. Any other platform needs Python 3.12.
- **Next run, decided by [team] at 5:31 PM:** three arms on the same 407 states and seeds. E' (key `Ep`): arm E's note with the swapped-out true neighbor replaced by the decoy in the same legible encoding, re-sorted. EL: name, file and lines, no signature. ES: name and signature, no location. E' asks whether a false edge is followed as readily as a true one now that following is measurable; EL and ES split the legible encoding into location and signature. Because the swapped-out entry's rate under E (1.80%) is below B2's 5% floor, E' gets its own pre-registered rule, written before any output exists. A run on other hardware must re-run E (and H) as same-platform references.
- **In progress, uncommitted:** the three arms and a separate state bundle (`analysis/fork_states_c/`), built additively so that the confirmatory bundle and the frozen scorer stay untouched; exploratory robustness tables (any-means following, base-rate-adjusted contrast, clustering by task, per-repo, McNemar); the adversarial prior-art search on the encoding claim (`docs/lit/2026-11-09-encoding-claim-prior-art.md`, written by the second session, citations to be verified before use).

### 2026-11-09 22:36 EST: Experiment B recounted independently; exploratory robustness tables; pre-registration 04 frozen

- **Count check (`analysis/recount_b.py`, output `analysis/results/recount_b.txt`).** 12,210 rows over 407 states, 1,221 per arm, no duplicate (state, arm, seed) rows, no row outside the state file. Interface failures 34 (no call 10, malformed arguments 24: `write_file` with a missing `filepath` 22, missing `content` 2; no errors, no unknown tools). By arm: A 7, P 4, Pp 6, H 0, Hp 4, D 1, Dp 2, E 3, RD 3, RE 4. Complete states 388 of 407, so 1,164 replays per arm. All of this equals the frozen analysis. This script stops there: it writes no rates.
- **Independent outcomes recount (second session; `analysis/recount_b_outcomes.py`, its own touch scorer written from the pre-registration text, no shared scoring code).** It agrees with the pooled scorer (`fork_states.touches`, the implementation named in pre-registration 02) on every `read_file`, `edit_file` and `write_file` call. The scorers differ only on grep, and always one way (pooled no, recount yes). Three readings:
  - pooled: a grep counts when the command names the node's file and the pattern contains the node's name;
  - recount, file: also a grep on the node's file whose matched lines fall inside the node's span (28 of 46,560 cells differ);
  - recount, wide: also a recursive grep over a directory that contains the node's file (217 cells differ, 194 of them recursive).

  | Any unopened true entry touched, % | pooled | recount, file | recount, wide |
  |---|---|---|---|
  | A | 2.15 | 2.32 | 3.52 |
  | H | 2.75 | 3.01 | 4.38 |
  | D | 4.30 | 4.55 | 5.15 |
  | D' | 3.78 | 3.78 | 4.73 |
  | E | 8.25 | 8.33 | 9.11 |
  | R_D | 2.32 | 2.32 | 4.12 |
  | R_E | 2.41 | 2.49 | 4.12 |

  | Contrast, points [95%, clustered by state] | pooled | recount, file | recount, wide |
  |---|---|---|---|
  | B1 D - H | +1.55 [0.60, 2.66] | +1.55 [0.43, 2.75] | +0.77 [-0.52, 2.06] |
  | B2 D_B | 0.00 [-0.77, 0.77] | +0.17 [-0.60, 0.95] | +0.26 [-0.60, 1.12] |
  | B3 E - H | +5.50 [3.44, 7.65] | +5.33 [3.35, 7.30] | +4.73 [2.75, 6.70] |
  | B4 D - R_D rewired | +3.78 [2.15, 5.67] | +4.04 [2.23, 6.01] | +4.47 [2.58, 6.53] |
  | B4 E - R_E rewired | +7.22 [4.64, 9.97] | +7.22 [4.55, 9.88] | +7.90 [5.24, 10.57] |

- **What the recount settles.** Under the reading closest to the pre-registered text ("a shell view of that file overlapping the span or naming the node") every decision B1 to B4 is unchanged and every rate is within 0.3 points. The pooled table stays the reported one. B3 and B4 hold under all three readings. **B1 (D versus H) fails under the wide reading**, because recursive greps add about 1.5 points to every arm and D gains less than H: report B1 as sensitive to how recursive greps are scored. E over A is 3.8 times (pooled), 3.6 (file), 2.6 (wide). An earlier version of the recount note (8 differing cells) came from a run that read no snapshot text; it is superseded. This replaces "not yet independently recounted" in the 19:05 entry.
- **Exploratory robustness tables (`analysis/explore_b.py`, output `analysis/results/explore_b.txt`). EXPLORATORY: nothing here was pre-registered.** Checked: its section 1 reproduces the frozen counts and its bootstrap reproduces the frozen intervals exactly; its gold-file row agrees with a separate script of the second session. Not checked: the script has had no code review and no independent re-derivation. Not read yet: sections 2, 7, 8, 9 and E3 to E6.
  - **File level.** Opening a listed entry's file: A 4.55%, H 7.47%, D 11.17%, E 11.77%. H - A +2.92 [1.46, 4.73], so bare names do move the agent toward listed files. E - D +0.60 [-1.29, 2.49]: the instruction reaches the same files as the legible entries. E's advantage on the touch outcome is precision: given the file was opened, the entry's lines were hit in 70.1% [56.4, 82.2] of E replays against 36.8% (H) and 38.5% (D).
  - **Clustered by task (77).** E - H +5.50 [2.16, 9.15]; D - H +1.55 [0.17, 3.54]; E true - R_E rewired +7.22 [2.97, 12.07].
  - **Per repository.** 203 states are from fastapi, 184 from rich, 1 from requests. E - H without fastapi +3.06 [1.08, 5.41]; without rich +7.68 [4.41, 11.44]. Leave one task out: E - H between +4.57 and +5.85.
  - **Per seed and fork.** E - H: seed 1 +6.96, seed 2 +4.64, seed 3 +4.90; fork 0 +6.06 [1.30, 11.69], fork 1 +6.71, fork 2 +4.03 [1.06, 7.22].
  - **Splits of the true entries.** In a gold-patch file (166 entries, 70 states): A 1.89, H 2.32, D 3.18, E 5.67; E - H +3.35 [1.80, 5.07]. Not in a gold file: E - H +2.15 [0.77, 3.61]. Fresh names: A 0.17, E 4.30; E - H +3.78 [2.15, 5.58]. Names already in view: E - H +1.72 [0.43, 3.18]. Arm A's base rate lives almost entirely in gold-file entries and names already in view.
  - **Padding of rewired lists.** 5,034 truly rewired entries, 826 padded, 286 of 388 states with padding. In the 102 states without padding: E true 11.44% against R_E rewired 1.63%, +9.80 [3.92, 16.01]. Padding does not explain the gap.
  - **Weakest cut.** With "followed by any means" as the outcome, E - H is +2.49 [0.60, 4.47] by states and [-0.34, 5.65] by tasks.
- **The rewired control is not like-for-like (correction to pre-registration 03's wording).** The amendment says the rewired entries meet the same eligibility as the scored true entries. In the code they do not: rewired entries exclude gold-patch nodes, gold-patch files and names already in view; the scored true entries only require an unopened file. Eligibility-matched true entries are 3,292 of 3,704, in 363 states. On those: A 0.00, H 0.17, D 0.86, E 2.49 [1.20, 3.87], against rewired R_D 0.52 and R_E 1.03. **E matched true - R_E rewired +1.46 [0.00, 3.01]** (by tasks [-0.80, 3.89]); D matched true - R_D rewired +0.34 [-0.60, 1.29]. Per entry: E 0.52% against R_E 0.11%, +0.41 [0.13, 0.73], by tasks [-0.01, 0.98]. So B4 returns "structure matters" by the frozen rule, but most of the gap comes from entries the rewired list cannot contain. The paper presents the rewired control as suggestive, not decisive.
- **Other caveats for the paper.** No arm ran in two sessions, so contrasts across sessions carry any drift (indirect checks on the touch outcome show none: true entries R_E - A +0.26 [-0.60, 1.12]). The legible encoding adds about 630 prompt tokens (mean 8,224 for E against 7,594 for H). Two repositories carry all but one state.
- **Pre-registration 04 (experiment C: arms E', EL, ES, with E and H re-run in the same run)** was written and committed by the second session at 21:21 EST (`f43edd3`), before any replay of those arms. This session did not write it and has read no experiment C output.
- **Process.** Two helper processes that started the recount and the robustness tables ended early on a usage limit; the recount was redone from scratch by the second session and the robustness script had already written its full report.

### 2026-11-09 23:05 EST: analyze_c.py aligned with pre-registration 04 (not run)

- **Who changed what.** The second session made `analysis/analyze_c.py` read arms E and H from the experiment C run itself and set the C1 floor to 1%, as pre-registration 04 requires. [Claude Code] then corrected the docstring and usage, added a stop when E or H is missing from the run, a line stating whether at least 200 states are complete (the partial-run rule), the 90% intervals of E minus EL and E minus ES, and a PASS/FAIL line for gate G2.
- **State.** The script compiles. It has not been run on any data, and no experiment C output exists or has been read.
- **Known limits.** Gates G1 (prompt-size fidelity) and G3 (drift against the hosted runs) are not computed by the script. The G2 line prints after the C1 and C2 blocks, so read it first. Completeness is counted over the arms present, not over a fixed list of five. The C1 and C2 reading labels are not printed; apply the rules of pre-registration 04 by hand.
- **Gaps seen in pre-registration 04, recorded here and not patched (the file is frozen).** It carries no correction of pre-registration 03's eligibility wording (see the entry above). It does not state that the three encodings differ in length (mean characters of the note: E 2,442, E' 2,437, EL 1,792, ES 1,658) or that 107 of 6,082 E entries have no span. Any-means and file-level outcomes are not listed, so they are EXPLORATORY for experiment C.
- **Draft.** `paper/draft.md` now holds the Experiment B draft written by the second session; this session checks its numbers against `analysis/results` before it is committed.

### 2026-11-09 23:36 EST: New lead session; sections 4 and 5 of the draft re-derived blind; draft corrected

- **Who writes this file now.** A new session took over the repository, this file and the draft at about 11:20 PM. The earlier owner session was stopped after its commit `9b5a95c`; it had been compacting every few minutes on a small context window. The second session keeps the experiment C run. The draft was committed unchanged as `073e10f` before any correction below.
- **Blind re-derivation** (`analysis/rederive_s5.py`, output `analysis/results/rederive_s5.txt`, comparison `analysis/results/rederive_s5_vs_draft.md`). A helper wrote its own script from written definitions and did not open `explore_b.py`, its output, the recount or the draft until its own numbers were on disk. It uses `fork_states.touches` for the registered outcome only. Every registered value reproduces exactly: A 2.15, H 2.75, D 4.30, E 8.25, R_D rewired 0.52, R_E rewired 1.03; E - H +5.50; D - H +1.55; D - R_D +3.78; E - R_E +7.22. Also reproduced: clustering by task, per seed, per fork index, leave-one-repository-out, leave-one-task-out, McNemar by state (41 against 14; 29 against 2 discordant), any-means following (5.2, 9.9, 12.9, 12.4), P(touch | file opened) under E (70.1%), the hit shapes under E (34 exact ranges and 13 at a listed first line, of 96), rank rates (5.22, 3.47, 1.28, 0.40), matched entries (3,292 of 3,704), the drift checks, prompt tokens, interface failures, padding, fidelity and experiment A. Interval ends differ by up to 0.1 point (another random generator).
- **Mismatches, and what changed in the draft.**
  - Runs: the 407 states come from **205 runs** (checked separately on `states.jsonl`; the 388 complete states from 199), not 241, a figure left from the first 525-state export. The abstract now says "407 points (205 runs, 77 tasks)".
  - Toward the fix: the rates in the draft (6.0, 6.6, 8.8, 8.2; E - A +2.15 [0.60, 3.95]) hold only when `read_file` calls alone are counted and the fix files come from the units file of the Sep 30 audit. Counting any read, edit or shell view of a file the gold patch changes: A 6.87, H 7.22, D 9.36, E 8.51; E - A +1.63 [-0.26, 3.61]; E - R_E +1.03 [-0.69, 2.92]. With `read_file` only and patch files: E - A +2.41 [0.69, 4.30]. The draft now gives both readings and says the size depends on the definition.
  - "Every hit from the top" in A, H and D: 104 of 107 (A 25 of 25, H 31 of 32, D 48 of 50); three are shell searches by name.
  - P(touch | file opened) outside E: 37% to 49% over all arms (A 47.2, H 36.8, D 38.5, P-prime 49.4, R_D 47.4), not 37% to 47%.
  - Without the five tasks with the most E hits: a tie for fifth place gives +2.37 to +2.74; now stated as a range.
  - Matched true minus rewired under E: +1.46, lower bound between -0.09 and 0.00 depending on the bootstrap draw; by tasks [-0.73, 3.81]. The draft now says a preference for a legible true edge over a legible rewired one is not established.
  - First list entry: 36 of the 96 E hit replays touch the rank-1 entry (37.5%; 30.5% of touched entries). The draft said "about half"; now "over a third".
  - Thought mentions depend on the matching rule: 10.8, 12.2, 11.0 (substring, among replays with a thought) against 9.9, 11.4, 10.3 (whole word, all replays). Same reading; both are in the draft.
- **Not covered by the re-derivation.** The two other grep readings of the recount, the session durations, the v4 fidelity figure, and the trace numbers of section 2. The Sep 30 audit numbers quoted in section 2 (84% of tasks; 10% and 19% reach) still have no independent re-derivation.
- **Not reviewed.** `rederive_s5.py` has had no second reader. Its exact agreement with the frozen table on every registered value is the evidence that its loader and complete-state rule are right; its name matching for any-means and mentions is its own choice.

### 2026-11-09 23:51 EST: Three corrections relayed from the earlier owner session; push

- **Source.** The earlier owner session's last message, relayed by the team, listed three corrections to the draft.
  1. "407 real runs" in the abstract and "241 runs" in section 3.1: already corrected at 23:36 (407 points, 205 runs).
  2. Section 3.2 said the rewired entries are held to the eligibility of the scored true entries. Checked in `analysis/fork_states.py`: the scored true entries are `unshown_true` (a known span in a file not yet opened, line 573); the rewired entries exclude the true neighbors, the names in view, the gold nodes, the node and the decoy (`banned_r`, line 632) and must pass `eligible_r`. Section 3.2 now states the two filters. Section 5 now says that the text of pre-registration 03 describes one filter for both sets while the code applied it to the rewired entries only.
  3. Section 4 described the wide grep reading as "recursive searches naming an entry". In `analysis/recount_b_outcomes.py` it is a recursive grep over a directory that contains the entry's file (`covers`, line 161). Reworded.
- **Push.** [team] said "yes push them" at about 11:50 PM. Commits `9b5a95c`, `073e10f`, `4e13a40` and the commit that carries this entry go to the private repository.
- **Word count.** After tonight's corrections the draft is over 3,000 words without its header note. About 200 words have to come out when experiment C is folded in.

### 2026-11-10 01:11 EST: Audit numbers re-derived blind; claims about other work checked; draft corrected

- **Sep 30 audit numbers (section 2 of the draft).** Blind re-derivation (`analysis/rederive_audit.py`, output `analysis/results/rederive_audit.txt`, comparison `analysis/results/rederive_audit_vs_original.md`), written from the registered definitions without opening `experiments/00-pointer-audit/`. K1: 103 of 122 tasks (84.4%), the same tasks. Reach at one hop: 13 of 129 (10.1%), the same 13 tasks. Also exact: 11.6% without the cap, direct naming 27.1%, at least one mentioned node 75.2%. Two differences. (1) Two hops is 19.4% only with no neighbor cap, which is how `decoy_bite.py` computed it; with the 50-neighbor cap applied to each expanded node it is 14.7%. The registered entry never defined two hops. (2) Unit level: 458 of 515 against 466 of 523; the eight units, in two tasks, are functions whose only change is an import added inside them. Wilson intervals: K1 [77.0, 89.8]; reach [6.0, 16.5]. The draft now says the graph "holds every function or class the fix edits in 84% of tasks" and gives two hops as "15% to 19%, with and without the tool's 50-neighbor cap".
- **Claims about other work** (`docs/lit/2026-11-10-related-work-check.md`; a helper checked 28 claims against the reading notes and the full texts on disk: 18 supported, 8 partly, 1 unsupported, 1 a judgment). Corrected in the draft:
  - GraphLoc's +0.9 points compares its base agent, which already has the nine tools with the graph tools among them, with the base agent plus its graph-localization skill. The draft said "adding the graph tools", and the first sentence of the abstract rested on the same reading. Both reworded.
  - LocAgent's appendix (A.1.2, Table 9) compares six text formats of its graph tool's output with an agent on 37 tasks; adding entity attributes to the row format lowered module-level accuracy. The draft cited LocAgent only as end-to-end. It now cites the format comparison, and the last sentence of related work is narrowed to what no work we read does: fix one edge set, vary only its encoding or rewire it, and score the next action against a no-list base rate.
  - The same-track Zenodo entry adds call edges to a signature map; it never tests bare call edges. Reworded.
  - 2609.05587 (corrupted search results; adoption), 2606.14476 (a GNN classifier as the tool; Qwen agents) and the GraphLoc and GraphAudit framing: reworded to what the notes support.
  - *Talk like a Graph* and KG-LLM-Bench were not cited at all; one sentence added at the start of related work.
  - "The most careful public entry" is now "the closest public entry".
- **Search log.** The Nov 9 queries behind the encoding claim existed only in a session scratch folder: copied (41 lines) (`docs/lit/2026-11-09-encoding/lit_search_log.jsonl`).
- **Depth of the citation check.** Four cited papers were checked from the reading notes only and three at abstract level; the helper's file lists the depth per work. GraphAudit's writeup is not on disk.
- **Length.** The draft is now about 3,152 words without its header note, over the 3,000 limit; the cut comes when experiment C is folded in.

### 2026-11-10 04:53 EST: Rented-GPU platform, pre-registrations 05 and 06, and the tool-channel result (D1)

- **Platform for experiments C, D and E.** Modal, one A100-80GB per run, tensor-parallel size 1 (pre-registration 04 names "a rented single A100" and no provider). Image `nvidia/cuda:12.8.0-devel-ubuntu22.04`, Python 3.12.1, with vllm 0.19.1, litellm 1.82.4, google-adk 1.36.1 and huggingface-hub 1.33.0 (below 2.0, which the server requires) plus the dependencies the harness wheels declare (docker, cachetools, networkx, python-dotenv, rich, pandas, accelerate, scikit-learn, pyyaml). The runner then reinstalls the 41 wheelhouse wheels and harness v28 without dependencies, as the hosted notebooks do. Wrapper and runner: `analysis/modal/` (commit `fc5245f`); `SUBSTITUTIONS.txt` lists every edit against the hosted script.
  - **Harness version, checked in the run's own freeze** (`analysis/results/d1/forks/pip_freeze.txt`): adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7, google-adk 1.36.1, google-genai 2.11.0, tokenizers 0.22.2, transformers 5.13.1, vllm 0.19.1. The `wheelhouse_files` list in `versions.json` names the newer wheels that sit in the wheelhouse directory (adk_submission 0.2.13, swegemma 0.2.11); the hosted runs' `versions.json` lists the same files, and in both cases the v28 wheels are installed over them.
  - **Differences from the hosted runs, to state in the paper.** One A100 instead of four L4, so tensor-parallel 1 instead of 4; torch 2.10.0 without the `+cu128` tag; Python 3.12.1 from the container. The model is served under the hosted path string, so the model name the agent and the client library see is identical.
  - **Fidelity.** On the six fidelity states of the smoke test the replayed prompt sizes equal the hosted ones token for token (5780, 5411, 7649, 12016, 11404, 8761). The gate of each run is on 24 states.
  - **A field to ignore.** `versions.json` reads `"experiment": "C"` in every run on this platform (hard-coded in the runner, which stayed byte-identical across runs). The `arms` field and the output directory identify the run.
  - **An attempt that produced nothing.** A hosted-notebook service was tried first for experiment C; it handed out a smaller GPU than selected and no replay ran there.
- **Pre-registration 05 (experiment D)**, frozen Nov 10, 2:07 AM (commit `2662c01`) before any replay of arm PE or of a second model. D1: arms P, PE, E on the 31B model; arm PE is arm P's inserted `get_code_neighbors` call with arm E's entries as its result (`analysis/make_states_d.py`, states file md5 `d3105df0dc4aa43d7bb0afbdd6123b44`). D2: arms A, H, E, RE on a second model.
  - **Amendment, 2:47 AM (commit `15f9a03`).** The model first named for D2 (`gemma-4-12b-it`) cannot be served by the pinned server: engine start fails on its architecture class with `ValueError: Expected hidden_size to be 3840, but found: 256`. No replay ran. D2 runs instead on `gemma-4-26b-a4b-it` (D2a) and `gemma-4-e4b-it` (D2b), chosen from their configuration files alone because they share the 31B model's architecture class; rules unchanged, both reported whichever way they fall.
- **Pre-registration 06 (experiment E, a navigation horizon of five model calls)**, frozen 2:43 AM (commit `431b9c7`) before any replay with a real model; amendment 3:04 AM (commit `bafbe85`) before the full run: the platform gate passed (44 of 44 re-executed `read_file` calls identical to the logged results; shell commands 36 identical, 18 same lines in another order, 13 different, of 67), 16 replays in flight, 4 states with a checkout at once, a 9-hour budget. The image has no git; the sandbox locale is C.UTF-8.
  - **Seen while the run was in progress (error messages and counts only, no outcome).** Some replays end in a context-window overflow after two to four model calls: the replay path has no compaction, and each executed read adds up to 10,000 characters. Under the frozen rule such a replay is not usable and its state is not complete. They are counted apart as interface failures.
  - **Supplement written before any full-run outcome was read** (`analysis/analyze_k_extra.py`, commit `e78690f`): interface failures by arm from the raw rows and K1 clustered by task (both promised by the pre-registration and not printed by `analyze_k.py`), the first-call indices and listed-entry touches, and one sensitivity labeled EXPLORATORY that keeps overflowed replays and scores the calls that executed. An arm-shuffled copy of a partial file was used to test the code, so no arm contrast could be read.
- **Runs.** Experiment C started 2:38 AM (6,105 replays). D1 started 2:50 AM after its smoke test (72 replays, 0 errors; mean prompt 9,095 tokens for PE against 9,092 for E on the same states, so the two differ by the channel only). E started 3:04 AM (2,968 replays). D2b started 3:07 AM and D2a 3:24 AM, each after a smoke test with 96 replays and 0 errors.
- **D1 result (registered analysis, `analysis/results/d1/analyze_d1.txt`; raw outputs in `analysis/results/d1/forks/`).** 3,663 replays, 0 errors, 1 h 52 min. Fidelity gate: median 1.66% on 24 states (rule: at most 2%), passed. Interface failures: P 6, PE 3, E 2 of 1,221 each. 399 of 407 states complete.
  - Any unopened true neighbor touched: P 3.26% [1.75, 5.01] (39 of 1,197); PE 9.61% [7.02, 12.28] (115); E 8.02% [5.76, 10.53] (96).
  - **T1, PE minus P: +6.35 points [+4.34, +8.52]. Passed:** the legible entries raise following inside the tool's own result.
  - **T2, PE minus E: +1.59 [-0.33, +3.43] at 95%, [0.00, +3.17] at 90%.** The 90% interval is not within plus or minus 2 points, so "no channel difference" is not claimed; the point estimate favors the tool result.
  - Secondary: the next call is a graph tool in 3.51% of P, 0.75% of PE and 0.08% of E replays; a thought is present in 72%, 73% and 100%; median completion tokens 123, 132 and 196.
  - Arm E on this platform (8.02%) is close to the hosted run (8.25% on 388 states); the paired drift against the experiment C run is computed when that run is in.
  - **Status.** These are the registered script's numbers. The independent re-derivation is being written; nothing enters the draft before it agrees.

### 2026-11-10 05:10 EST: D1 re-derived; second model 26B-A4B (D2a); mangled argument names; pre-registration 07

- **D1 re-derived blind.** `analysis/rederive_cd.py` (written by a helper that did not open the first implementation or its output; it imports only the registered scorer and the file reader) gives the same counts on the same 399 complete states: P 39, PE 115, E 96 of 1,197; failures 6, 3, 2; fidelity median 1.663%. T1 +6.35 [+4.09, +8.60] with its own bootstrap (registered script: [+4.34, +8.52]); T2 +1.59, 95% [-0.25, +3.43], 90% [+0.08, +3.17] (registered: [-0.33, +3.43] and [0.00, +3.17]). Same verdicts. Output: `analysis/results/rederive_d1.txt`.
- **D2a, Gemma 4 26B-A4B (registered analysis `analysis/results/d2_26b/analyze_d2_26b.txt`; raw outputs in `analysis/results/d2_26b/forks/`).** 4,884 replays, 0 errors, 1 h 36 min; harness v28 installed (pip freeze); A100-80GB. Interface failures A 3, H 4, E 8, RE 5 of 1,221 each. 397 of 407 states complete.
  - Any unopened true neighbor touched: A 2.27% [1.01, 3.78] (27 of 1,191); H 3.36% [2.02, 4.95] (40); E 6.88% [4.70, 9.15] (82); RE 1.51% [0.50, 2.77] (18), its rewired entries 0.34% [0.00, 0.84] (4).
  - **M1, E minus H: +3.53 [+1.51, +5.54]. Passed: replicates on the second model.** H minus A +1.09 [-0.17, +2.35]; E minus A +4.62 [+2.60, +6.80]; E true minus RE rewired +6.55 [+4.28, +8.82] (not like-for-like).
  - The next call is a graph tool more often than with the 31B model: A 1.85%, H 7.81%, E 5.21%, RE 5.88%.
  - Prompt-size check (no rule): median 1.42% below the 31B's logged sizes.
  - Re-derived blind with the same script: same counts; M1 +3.53 [+1.51, +5.71] (`analysis/results/rederive_d2_26b.txt`).
- **Mangled argument names (EXPLORATORY; `analysis/mangled_args.py`, `analysis/mangled_sensitivity.py`, output `analysis/results/mangled_args.txt`).** Both re-derivation helpers flagged `read_file` calls whose line bound arrives under a name with a stray quote (`start_line"`, `end_line"`). Checked:
  - The frozen `valid_call` accepts such a call and the scorer reads it without the bound (lines 1 to 150). That is what the harness does: the agent framework filters arguments to the tool's parameters (`function_tool.py`), so the unknown name is dropped silently. In the public traces all 42 base-arm reads with a mangled bound asked for another start line and got the file from line 1.
  - Rates, 31B model, share of first-call reads that carry a line bound: A 35.8% (211 of 589), P 17.3%, H 13.7%, D 14.4%, R_D 14.8%, E 4.9%, R_E 4.7% (hosted runs); D1: P 16.7%, PE 6.2%, E 4.4%. With the 26B-A4B model: 0 of 2,572.
  - In the original runs it is rare: 2 of the 201 bounded reads the model itself made next at the same 407 states (1.0%); 42 of 2,012 bounded reads over the 318 base traces (2.1%). The replay reproduces the original tool mix (arm A: read_file 58%, run_command 33%, write_file 6%; original next calls 61%, 32%, 6%) but not this rate.
  - **A difference between the original runs and the replays, read from the harness source.** In v25 (files dated Sep 27, the closest version to the original runs of Sep 25 to 27) every agent-facing tool returns its JSON as a string (`-> str`), which the agent framework wraps as `{'result': '<string>'}` (`functions.py`: "Specs requires the result to be a dict"). In v28 every tool returns a dictionary (`parse_tool_response`). `analysis/replay.py` rebuilds earlier tool results as dictionaries (`_parse`), which is v28's form. The two swegemma wheels carry the same version number, 0.2.7, and different contents (md5 a682db54... and 765b145d...). This would explain why the replayed prompt is smaller than the logged one in 24 of 24 fidelity states; it is untested until experiment F.
  - **The registered outcomes do not depend on it.** With the mangled bound honored, hosted E goes from 8.25% to 8.33% (one replay), every bare-name arm is unchanged, and E minus H goes from +5.50 to +5.58; in D1, PE 9.61% to 10.03% and PE minus P +6.35 to +6.77. Reads of a listed unopened file under bare names carry a mangled bound in 1 of 577 cases (arms A, P, P', H, H', D, D'), so "opens the file from the top" is the model's own choice there, not this defect.
- **Pre-registration 07 (experiment F)**, frozen 5:09 AM (commit `98abc55`) before any replay of a wrapped arm: arm A as before, and Aw, Hw, Ew with every earlier tool result delivered as `{'result': '<logged JSON string>'}`. F1: Aw's prompt size against the logged one (median at most 0.5%). F2: mangled bound names, A minus Aw. F3: Ew minus Hw. Runner `analysis/modal_w/forks_w_runner.py` (the experiment C/D runner plus a wrapper around `replay.arm_messages`; `replay.py` unchanged), analysis `analysis/analyze_w.py`.
- **Experiment E, implementations compared before any outcome is read.** `analysis/rederive_k.py` (independent; gold-patch regions re-derived from `data/tasks.jsonl` agree with `population.json` on all 198 states; the populations re-derive to R 74 and U 124) and the registered `analyze_k.py` give identical counts in every cell on an arm-shuffled copy of a partial file (993 replays).

### 2026-11-10 05:49 EST: Second model E4B (D2b); competition pages and forum threads; nearest paper's second version

- **D2b, Gemma 4 E4B (registered analysis `analysis/results/d2_e4b/analyze_d2_e4b.txt`; raw outputs in `analysis/results/d2_e4b/forks/`).** 4,884 replays, 0 errors, 2 h 40 min; harness v28 installed; A100-80GB. Interface failures A 80, H 78, E 80, RE 88 of 1,221 each (6.4% to 7.2%, below the 20% flag): all but a few are `edit_file` calls whose argument names are fragments of the code being edited (319 calls, concentrated in states that edit a regular expression). 305 of 407 states complete.
  - Any unopened true neighbor touched: A 2.95% [1.53, 4.59] (27 of 915); H 5.14% [3.28, 7.10] (47); E 8.20% [5.57, 10.82] (75); RE 3.61% [1.86, 5.57] (33), its rewired entries 2.84% [1.53, 4.48] (26).
  - **M1, E minus H: +3.06 [+1.09, +5.03]. Passed: replicates on this model too.** H minus A +2.19 [+0.77, +3.72]; E minus A +5.25 [+3.17, +7.21]; E true minus RE rewired +5.36 [+2.73, +7.98] (not like-for-like).
  - Re-derived blind: same counts; M1 +3.06 [+1.31, +5.03] (`analysis/results/rederive_d2_e4b.txt`).
  - **Read across the three models** (EXPLORATORY; different runs, so no contrast between models): the rewired legible list's entries are touched in 1.03% of replays by the 31B model (hosted), 0.34% by 26B-A4B and 2.84% by E4B; bare names move E4B (H minus A +2.19) and not detectably the other two (+0.60 [-0.26, 1.55] hosted 31B; +1.09 [-0.17, 2.35] 26B-A4B).
  - Neither second model writes a mangled line-bound name: 0 of 1,466 bounded first-call reads (E4B) and 0 of 2,572 (26B-A4B), against 4% to 36% for the 31B model. The three models ship different chat templates (16,934, 12,045 and 11,926 bytes).
- **Both D2 replications pass**, as the amendment to pre-registration 05 required to be reported together: 26B-A4B +3.53 [+1.51, +5.54], E4B +3.06 [+1.09, +5.03].
- **Experiment F, prompt sizes only (the outcome rules wait for the run to end).** Smoke test (8 states, 96 replays, 0 errors) and the 24 fidelity states of the full run: with earlier tool results delivered as `{'result': '<logged JSON string>'}` the replayed prompt is exactly 2 tokens below the logged size in 24 of 24 states; with dictionaries it is 9 to 2,268 tokens below (median 1.66%).
- **Competition pages read** (`docs/competition.md`, section of Nov 10): the host's statement that references do not count toward the 3,000 words and that an appendix is supplementary; a public repository is not a prior publication; derived labels may be published; 786 teams and 851 submissions, hidden until the close.
- **Forum threads read** (`docs/prior-art.md`, section of Nov 10): the double encoding of tool results and its fix in the Sep 30 wheelhouse (thread 744272), including a participant's fixed-context comparison of three encodings of a file read on 30 edit contexts; a participant's audit of the graph tools (thread 745731). Searches for a report of mangled line-bound names found none.
- **Nearest paper, second version** (`docs/lit/2026-11-10-bellam-v2-check.md`; read in full by a helper): 2610.33958v2 (Nov 9) is a pre-registered scale study with a random-entity placebo, a gold-injection contrast and a masking arm, all scored by final localization; its output format is held fixed, and it has no replay from saved states. The two findings the draft cites (forcing the graph call; one expansion and stop) are only in v1. The related-work text has to cite the versions separately and state the difference; the novelty sentence is tightened to "one function's graph neighbors at a paused agent state ... rewires them with degree preserved". A paper v2 cites, arXiv 2605.16352, is being read.
- **Reference list** (`paper/references.md`): 17 entries, each checked against the arXiv or Zenodo record on Nov 10. One writeup we cite from the same track has no recorded author, title or URL in the repository.
- **Figures** (`paper/figures/`): `fig_extensions` (the encoding effect across settings) and `table_rules` (every registered rule with its outcome), both generated from the raw outputs and checked against the registered outputs before saving.

### 2026-11-10 11:11 EST: Experiment C, experiment F (rendering) and the five-call experiment: registered results and re-derivations

All three runs finished on the rented platform between 6:17 and 7:55 AM. Raw outputs are in `analysis/results/c/forks/`, `analysis/results/w/forks/` and `analysis/results/k/forks/`; harness v28 as installed in each run's freeze (adk_submission 0.2.12, swegemma 0.2.7); A100-SXM4-80GB each. Total credit used for every run of Nov 10: 59.96 dollars.

- **Experiment C (pre-registration 04).** 6,105 replays, 0 errors. The container was preempted by the platform after 2,946 saved replays and restarted itself; the rest ran in the second container from the same fixed order (`versions.json`, `platform_actual.json` and `fidelity.jsonl` are the second container's; the fidelity values equal the first's). The side session that started the run stopped before the fetch; the lead fetched and analyzed.
  - **Gates, checked first (`analysis/results/c/gates_c.txt`).** G1 fidelity 1.66% median: passed. G2, E minus H in this run: +5.58 [+3.67, +7.58] (E 8.58%, H 3.00%): passed. G3 drift against the hosted runs on the same states and seeds: E +0.58 [-0.41, +1.57], H +0.25 [-0.33, +0.82]: no flag. Interface failures 1 to 5 per arm; 400 of 407 states complete.
  - **C2, which part (`analysis/results/c/analyze_c.txt`).** Any unopened true neighbor touched: H 3.00% (36 of 1,200), ES 3.08% (37), EL 7.75% (93), E 8.58% (103), E' 6.33% (76). EL minus H +4.75 [+3.00, +6.58]: location raises following. ES minus H +0.08 [-0.75, +0.92]: the definition line does not. Verdict by the registered rule: **location carries it**. E minus EL +0.83 [-0.33, +2.00], 90% [-0.17, +1.83]: within plus or minus 2 points, so **location is sufficient for the full effect**. E minus ES +5.50 [+3.50, +7.58].
  - **C1, the false entry.** Swapped-out true entry under E: 1.92% (23 of 1,200), above the 1% floor. Decoy under E': 0.08% (1 of 1,200). D_E +1.83 [+0.83, +3.17] (90% [+0.92, +2.83]); the decoy rate is below half the swapped-out rate. Verdict by the registered rule: **checks the edge**. Not listed, the same true entry is touched in 0.17% of E' replays and the decoy in 0 of 1,200 E replays, so listing raises the true entry by 1.75 points and the decoy by 0.08. Per listed true entry in the E' notes the touch rate is 1.03% (104 of 10,089). E' minus E on any true neighbor: -2.25 [-3.75, -0.83].
  - **Re-derived blind** (`analysis/results/rederive_c.txt`): identical counts in every cell, same gates and verdicts (D_E 95% [+0.83, +3.00]; E minus EL 90% [-0.17, +1.75]).
  - **Drift of arm E between the tool-channel run and this run** (descriptive): -0.58 [-1.56, +0.33] on 1,214 pairs (97 against 104 hits).
- **Experiment F (pre-registration 07; `analysis/results/w/analyze_w.txt`).** 4,884 replays, 0 errors, interface failures 1 to 4 per arm, 400 states complete.
  - **F1 met.** Arm Aw's prompt size against the logged size: median 0.03%, exactly 2 tokens below in 24 of 24 states. Arm A in the same run: 1.66%.
  - **F2 met.** First call is a `read_file` with a mangled line-bound name: A 18.33% of replays (220 of 1,200; 36.1% of its 610 reads with a line bound), Aw 0.17% (2; 0.3% of 595). A minus Aw +18.17 [+14.75, +21.75]. Hw 0.58%, Ew 0.08%. The original runs' own next calls at the same states: 2 of 199 reads with a line bound (1.0%).
  - **F3 met.** Any unopened true neighbor touched: Aw 2.33%, Hw 3.67%, Ew 8.83%; Ew minus Hw +5.17 [+3.33, +7.17]. Aw minus A +0.00 [-0.58, +0.58]; Hw minus Aw +1.33 [+0.50, +2.42]; Ew minus Aw +6.50 [+4.58, +8.67].
  - Descriptive: the replayed first call names the same tool as the original run's own next call in 76.2% of A replays and 83.1% of Aw replays; where both read a file it is the same file in 94.3% and 94.9%.
- **Five-call experiment (pre-registration 06; `analysis/results/k/analyze_k.txt`, `analyze_k_extra.txt`).** All 2,968 replays ran in 4 h 34 min (the 9-hour budget was not reached). 49 replays ended in a context-window overflow after two to four model calls (R: A 6, H 6, E 7, RE 9; U: A 2, H 6, E 7, RE 6) and two first calls were malformed; under the frozen rule their states are incomplete. Complete: 57 of 74 states of R (17 tasks), 114 of 124 of U (30 tasks). The checkout fingerprints are in `checkouts_k.jsonl`.
  - **K1 not met.** Shown a line the gold patch changes within five calls, R: A 61.05% (174 of 285), H 65.96% (188), E 69.82% (199), RE 64.56% (184). E minus H +3.86 [-1.05, +8.77] by state, [-0.80, +9.63] by task: no detectable gain. E minus A +8.77 [+1.75, +15.79]; H minus A +4.91 [-1.40, +11.58]; RE minus A +3.51 [-4.56, +11.58].
  - **K2: no harm.** Opens a file the gold patch changes, U: A 14.04% (48 of 342), H 17.25% (59), E 22.51% (77), RE 21.64% (74). E minus A +8.48 [+3.22, +14.04] (by task [+1.78, +16.24]). RE minus A +7.60 [+2.34, +13.16]: the rewired list does the same, so this is not the graph's content.
  - Sensitivity specified before the outcomes were read (overflowed replays kept, EXPLORATORY): 73 and 124 states; K1 +1.92 [-2.47, +6.58]; K2 +7.53 [+2.69, +12.90].
  - **Re-derived blind** (`analysis/results/rederive_k.txt`): identical counts in every cell and the same verdicts under three readings of "single-file shell view" (six shell views reach a changed line in all).
  - **By call (EXPLORATORY, `analysis/results/k/explore_k.txt`).** Shown a changed line by the end of call 1, 3 and 5 in R: E 33.0%, 63.5%, 69.8%; H 25.3%, 53.0%, 66.0%; A 24.6%, 48.8%, 61.1%. E minus H +7.7 [+0.7, +15.8] at call 1, +10.5 [+2.1, +19.3] at call 3, +3.9 at call 5. The legible list gets the agent there sooner and the bare list catches up.
  - **Mangled bound names with tools executing (EXPLORATORY).** 668 of 4,655 `read_file` calls with a line bound (14.4%) carry a mangled name; in 658 the model asked for another start line and the tool returned the file from line 1. Arm A: 40.6% at the first call and 25.1% at later calls; H 22.2% and 9.4%; E 6.3% and 9.6%; RE 9.0% and 6.9%. The no-list arm is hit hardest, which is a candidate cause of the U result above (any note, true or rewired, raises reaching the fix file).
- **Where the read lands in the later runs** (EXPLORATORY, `analysis/explore_mechanism.py`): of the first calls that open a listed file, the share that covers a listed neighbor is 44% for P and 68% for PE (tool channel), 49% for H and 72% for E on 26B-A4B, 47% and 55% on E4B. The rewired entries are touched by 26B-A4B in 0.34% of replays with or without the rewired list, and by E4B in 2.84% with it against 0.66% without (+2.19 [+0.87, +3.83]).
- **Experiment F re-derived blind** (`analysis/rederive_w.py`, `analysis/results/rederive_w.txt`): identical counts (220, 2, 7 and 1 mangled reads of 1,200; 28, 28, 44 and 106 hits), F1 0.028%, F2 +18.17 [+14.83, +21.75], F3 +5.17 [+3.17, +7.08], same verdicts. It also shows that under the original rendering the mangled names carry a backslash (`start_line\"`), the form found in the original runs, while under the current rendering they do not.
- **One command for every number.** `analysis/reproduce.py` re-runs each registered, independent and exploratory analysis on the tracked raw outputs and compares it with the stored output. All stored outputs were rewritten from the tracked files (so their first lines name tracked paths) and a second run compared identical: 18 of 18.

### 2026-11-10 14:13 EST: Blind reviews of the draft; pre-registrations 08 and 09; runs on the newest harness wheels; supplement from the stored outputs

- **Blind reviews of the draft at d6e467e.** Five fresh readers who saw only the rubric, the draft and its figures (three started by a second session, two by this one) scored it 6.4 to 7.2 of 10. They agree on what holds it down: no consequence shown beyond the next call (the outcome is where the agent looks, the registered five-call rule was not met, neither proposed change was tested); a narrow base (two repositories, early states, the 31B agent's histories); too many numbers and arm letters; and sentences that claim more than the evidence ("checks the edge", "barely change the next call", the 36% without its scope, "the current harness"). A sixth reader red-teamed the method against the pre-registrations and the stored outputs and found, among other things: the structure rule (B4) is met only as coded, not with the filter the registration describes; the first pre-registration was frozen while its run was in progress and its discarded first run had met two rules that the replacement run does not meet; several numbers the pre-registrations promised are missing from the draft. The rewrite addresses each point; the missing numbers are now computed (below).
- **A fact the draft had wrong.** "The current harness" is harness v28, wheels dated Sep 30 (adk_submission 0.2.12, swegemma 0.2.7), chosen in October as the closest to the recorded runs. The wheelhouse on disk also holds newer wheels dated Oct 12 (adk_submission 0.2.13, swegemma 0.2.11). By a file comparison the read tool (`tools/workspace.py`) and the handling of tool results (`tools/base.py`) are identical in both; the newer agent runner adds a plugin that turns tool exceptions into error results and sanitizes skill-tool arguments, and does not touch unknown argument names of other tools; the graph tools now accept name suffixes and their descriptions are longer.
- **Pre-registration 08** (frozen 1:29 PM, commit 22ed2df; dated amendments up to 2:04 PM). Newest wheels. (1) One step, bare names against the list with addresses, on the 407 states (rule S1). (2) Five calls on the R and U states of pre-registration 06 with new seeds (R 11 to 15, U 11 to 13), three arms: stock; a mangled line-bound name of `read_file` restored before the call runs; the same plus the note with addresses. Rules G1 (both changes against stock on being shown a line the gold patch changes, R and U together), G2 (the argument fix alone), G3 (the note beyond the fix, in R). (3) Fresh episodes from the task prompt for the 106 traced tasks (rule N1: the share of ranged reads with a mangled bound name, lower bound above the original traces' 2.1%).
- **Smoke tests on the newest wheels** (before any full-run replay; what they printed is recorded in the pre-registration). Everything installs and runs. A fresh episode's first prompt is exactly 67 tokens above the size the original run logged for the same task (with the Sep 30 wheels the rebuilt prompt was 2 tokens below). In the stock arm 4 of 4 mangled reads returned the file from line 1; in the patched arm 4 of 4 returned the lines the model asked for. Five of the first six fresh episodes ended at a `search_similar_code` call within two model calls, so an amendment lets the three graph tools execute in fresh episodes (they read precomputed files); with that, five of six episodes reached the eighth call.
- **Pre-registration 09** (frozen 2:04 PM, commit 7c268ed). Fresh episodes, newest wheels, 106 tasks, seeds 1 to 3, three arms with the same seeds: as shipped; the graph tools' answers with file and line range for every entity that resolves (`analysis/make_spans_g.py`: 316,564 of 330,998 graph nodes of the 106 tasks resolve to a line range, 95.6%; same resolver and entry format as arm EL); the same plus line bounds honored. Rules: A1 (addresses against shipped: after the first graph answer, does the next call read a returned entity's lines), A2 (patched against shipped: shown a line the gold patch changes within eight calls), and pre-registration 08's N1 on the shipped arm, which is the same arm.
- **Runs in progress** (rented A100-80GB each, newest wheels): one step since 1:40 PM (2,442 replays); five calls since 1:55 PM (2,226 replays); fresh episodes after their smoke test (954 episodes).
- **What a mangled bound costs** (EXPLORATORY, `analysis/explore_defect_cost.py`, five-call records of pre-registration 06): 96.0% of the 657 mangled reads with a known start asked to start past line 150 and 0.9% returned from the line asked for (well-formed: 99.9%). The next model call reads the same file again after 71.8% [67.3, 75.9] of mangled reads against 31.7% [27.7, 35.7] of well-formed ones (+40.1 [+35.2, +45.3]); 48.3% [41.0, 56.0] of those retries are mangled again. Mangled reads are 12.1% of the no-list arm's executed calls (4.7% bare names, 3.8% addresses, 2.9% rewired). By what the model saw just before: at the first call of the no-list arm, 53.3% after a read with no bound and 6.0% after a well-formed ranged read; at later calls, 48.6% right after a mangled read and 7% to 10% otherwise.
- **Supplement from the stored outputs** (EXPLORATORY, `analysis/explore_supplement.py`, written by a helper; all 25 state-clustered values it recomputes equal the stored registered ones).
  - Task-clustered intervals for every registered contrast. No verdict changes. E minus H: hosted [+2.16, +9.15], rented [+2.75, +8.75], tool channel [+2.48, +10.48], original rendering [+2.58, +8.12], 26B-A4B [+0.63, +6.35], E4B [+1.18, +5.43]. The following contrast of pre-registration 02 is +0.81 [-0.08, +1.65] by state (not met, as registered) and [+0.09, +1.66] by task.
  - Numbers pre-registration 05 promised: bare names minus no list and addresses minus no list are +1.09 [-0.17, +2.35] and +4.62 [+2.60, +6.80] on 26B-A4B, +2.19 [+0.77, +3.72] and +5.25 [+3.17, +7.21] on E4B.
  - The false entry (experiment C run). The swapped-out true entry is touched in 23 of 1,200 replays when listed with its address, in 2 when not listed (the decoy in its place) and in 5 as a bare name; the decoy in 1 when listed and 0 when not. Listing adds +1.75 [+0.67, +3.08] for the true entry and +0.08 [+0.00, +0.25] for the decoy. Restricted to the 140 states whose true entry passes the decoy's own filter (not a gold node, not in a gold-patch file, not a test file, alone in its file): 8 of 420 against 0 of 420, +1.90 [+0.24, +4.29] (by task [+0.00, +5.51]). Outside the fix only: 9 of 1,104 against 0. In the 32 states where the true entry is a gold node or in a gold-patch file: 14 of 96 against 1 of 96. Of the 23 reads, 21 start at the entry's first listed line. The decoy is at rank 1 in 148 states (1 of 444 replays), the true entry in 86 (15 of 258).
  - Seed-to-seed agreement of the first call (rendering run): two seeds name the same tool in 83.1% of pairs under the v28 rendering and 82.7% under the original one. The original rendering's agreement with the recorded run (83.1%) is therefore at that ceiling; the v28 rendering's (76.2%) is below it.
  - Five calls: mean model call at which a changed line is first shown in R, with never counted as 6: no list 3.72, bare names 3.49, addresses 3.16, rewired 3.62. Addresses minus bare names -0.32 calls [-0.54, -0.11] by state, [-0.68, +0.00] by task. Addresses minus rewired on being shown a changed line in R: +5.26 [-2.11, +12.98]. Replays with addresses end at an edit or a write more often than with bare names in R (28.4% against 22.5%, +5.96 [+0.00, +11.93]).
  - The discarded first hosted run (it re-sent the agent's thoughts and failed the fidelity gate at 6.1%; `analysis/results/v4/analysis.txt`): following +1.13 [+0.38, +1.93] and channel +1.42 [+0.17, +2.93], both of which meet their rules; the replacement run's values are +0.81 [-0.08, +1.65] and +0.25 [-0.68, +1.19].
- **Other teams' public runs.** A second session downloaded several public trace datasets of Gemma 4 agents on this benchmark (kept outside the repository) and made a first, exploratory count: a first read of a file asks for lines past line 1 far more often when the observation just before named the file with a line number than when it named only the file, and mangled line-bound names occur in other teams' fresh runs. Nothing of this is in the repository yet; it will be re-derived here with tracked scripts before any number is used.
- **History inventory for a public copy** (read-only scan of all 53 commits): 7 commits carry a personal mail address as author, 7 an assistant trailer, and 23 paths hold a name, a handle, an address or a local path in some version. No decision taken.

### 2026-11-10 16:21 EST: Registered results on the newest wheels (S1, N1, A1, A2, R1, R2); pre-registrations 10 to 12; other teams' public runs in the repository

- **S1 (pre-registration 08, one step on the wheels of Oct 12): met.** 2,442 replays, arms H and E, 399 complete states of 407, 4 interface failures per arm. Bare names 2.92% [1.50, 4.59] (35 of 1,197), addresses 8.52% [6.18, 11.19] (102 of 1,197), E minus H +5.60 [+3.76, +7.77]. The run recorded adk_submission 0.2.13 and swegemma 0.2.11 in its `pip_freeze.txt`. Raw files in `analysis/results/g_onestep/forks`; the stored output of `analyze_g.py` follows with the five-call part. Not yet re-derived by an independent script.
- **Fresh episodes (pre-registrations 08 and 09; 954 episodes, 9 ended in a context overflow; `analysis/results/09/analyze_09.txt`).** All three registered rules are met.
  - N1: of the executed ranged reads of the shipped arm, 13.17% [9.19, 17.17] carry a mangled line-bound name (66 of 501, in 226 episodes of 88 tasks); the threshold was a lower bound above 2.1%. 65 of the 66 returned the file from line 1; 53 of 316 episodes have at least one; none at the first model call (0 of 6).
  - A1: the call after the first qualifying graph answer reads a returned entity in 4.04% of episodes as shipped (12 of 297) and 7.74% with addresses in the answers (23 of 297): +3.70 [+1.35, +6.73] by task, 99 complete tasks. Among episodes with a qualifying answer: 12 of 74 against 23 of 71.
  - A2: shown a line the gold patch changes within eight calls in 65.65% of episodes as shipped (193 of 294) and 69.73% with addresses and line bounds honored (205 of 294): +4.08 [+0.68, +7.48]. Descriptive: addresses alone +2.38 [-1.02, +6.12]; honoring the bounds on top +1.70 [-0.68, +4.42].
  - Descriptive: the shipped arm calls a graph tool in 89 of 297 episodes, the first at model call 1 (median), nearly always `search_similar_code`. With bounds honored the share of ranged reads with a mangled name is 21.3% (88 of 414), and none of them returns from line 1. The addresses printed in the answers equal the resolver's in 1,385 of 1,385 cases.
- **Pre-registration 11 (the reading rule on the same episodes): both rules met.** Frozen at 3:47 PM (e9efe31) while the run was in progress and before any of its rows was read; thresholds from the public-run counts; analysis script hashed at 3:49 PM and tested only on the tracked rows of the five-call run of pre-registration 06. `analysis/results/09/analyze_11.txt`: after a result that names the file with a line number, 83 of 100 first reads ask past line 1 (by task [66.7, 97.6]); after a file name alone, 0 of 708; difference +83.0 [+66.0, +97.8]. In the shipped arm alone 26 of 35 against 0 of 233. R2: after a graph answer as shipped, 0 of 33. No rule: after a graph answer that gives file and lines, 20 of 78 first reads ask past line 1 and 19 of the 20 cover the listed range; ranged first reads after an address cover a named line in 78 of 83 cases.
- **Pre-registration 10 (a model of another family, Qwen2.5-Coder-32B-Instruct, 4-bit AWQ).** Frozen at 2:35 PM. Four smoke tests, each amendment recorded before the test it governs: the server refused the agent's thinking-token budget until it was started with a reasoning configuration (first test: 0 of 24 usable in every arm); the model can put dozens of calls in one answer and runs to the output limit, so a stop string was added (it turned out not to end the answers) and then the output limit was set to 2,048 tokens. Gate on the fourth test: usable A 21, H 20, E 21, RE 21 of 24. Recorded with it: 31 of 96 answers reach the limit, 13 hold no call, one state of eight never yields a call; the scored call is the first of an answer. The full run (4,884 replays, 16 requests at a time, no new replay after 3.25 hours) started at 3:30 PM.
- **Pre-registration 12 (a file without lines).** Frozen at 4:02 PM after a blind reader asked for the missing condition: the note of the name-file-lines condition with the line range removed (`analysis/make_states_f.py`; 6,082 entries, 5,975 with a file). Rules P1 (file and lines minus file alone on reading a neighbor), P2 (file alone minus bare names on opening its file), P3 (at most 5% of those reads past line 1). The references are the conditions of pre-registration 04's run on the same platform, wheels, states and seeds. Smoke test 24 of 24 usable; the full run (1,221 replays) started at 4:09 PM.
- **Other teams' public runs, now in the repository** (EXPLORATORY; scripts written by a second session, re-run here before each commit; the data stays outside the repository and `analysis/results/public/README.md` lists sources and licenses).
  - Where a first read starts (`public_runs_address.py`, and `rederive_public_address.py`, a second implementation written from the rules without the first): Gemma-4-31B, three sources: after a file with a line number 213 of 254 ask past line 1, after a file alone 3 of 450 (3 of 454 in the second implementation: four reads fall between two classes), after a graph name 0 of 10; 212 of the 213 ranged reads cover a named line. Other models through a dataset viewer (`public_runs_outside.py`): Claude 3.7 Sonnet 66 of 75 against 6 of 923; Llama-based agents 42 of 47 against 50 of 883.
  - The mangled name (`public_runs_defect.py`, `public_runs_defect_split.py`): starter agent in September 42 of 2,012 bounded reads; two custom agents 25 of 1,376; none on 12B and E4B. A third team's count of corrupted argument keys covers every tool and is mostly edit calls, so it bounds file reads from above (between 4 and 10 per 100); an unclosed path string that swallows the bounds is a second malformation, counted apart. In our own one-step replays that second kind is 12 of 21,529 `read_file` calls (`explore_path_leak.py`).
  - Whole runs (`public_runs_time_to_fix.py` and its independent recount, which agrees on every count): in the two public arms of the GraphLoc end-to-end runs (315 pairs), a skill that prints `path:line name` shows the agent a changed line within five calls in 224 runs against 173 (+16.2 [+8.9, +23.5] by task), 1.95 calls sooner, level by call 20, and resolves 95 against 92. In either arm 278 of 315 runs are shown a changed line; every changed region is shown in 372 of 630.
- **First reads in the replays, updated** (`explore_first_reads.py` with the newest-wheels run): without line numbers 0 of 856 first reads of a listed neighbor's file ask past line 1; with them 375 of 1,000, all on a listed neighbor, 337 on its first line.
- **Figures and Table 1.** The figure scripts name every condition in words; `make_fig_law.py` and `make_fig_runs.py` draw two new figures from stored reports; `rules_table.json` is rewritten in plain words for the main text. The figure files are not regenerated yet.
- **In progress.** Blind re-derivations of pre-registrations 09 and 11 by two helpers; the five-call run of pre-registration 08; the runs of pre-registrations 10 and 12. `analysis/reproduce.py` has 31 jobs; the outputs of the new registered analyses are not yet among them.

### 2026-11-10 18:50 EST: Re-derivations; results of pre-registrations 12, 08 (five calls), 13 and 10; blind reviews of the merged draft; pre-registration 14 running; exploratory counts on the graph

- **Blind re-derivations of pre-registrations 09 and 11** (`analysis/rederive_09.py`, `rederive_11.py`, stored outputs): same counts and verdicts as the registered analyses for N1, A1, A2, R1 and R2; intervals by their own bootstraps. Both second analysts saw one commit subject line that stated headline numbers; their headers say so. Since then results stay out of commit subjects until a second script exists.
- **Pre-registration 12 (a file without lines): P1 met, P2 not met, P3 met** (`analysis/results/12/analyze_12.txt`; 1,221 replays, 6 interface failures, 402 complete states with H and EL of the run of pre-registration 04). Reads a listed neighbor: bare names 2.99% (36 of 1,206), file only 3.15% (38), file and lines 7.71% (93), full address 8.60% (103 of 1,197). Opens a listed neighbor's file: 7.30%, 8.62%, 10.78%, 11.53%. P1, file and lines minus file only on reading: +4.56 [+2.74, +6.63], by task [+1.85, +7.67]. P2, file only minus bare names on opening: +1.33 [-0.08, +2.82]. P3: 0 of 104 first reads ask past line 1. Re-derived blind (`analysis/rederive_12.py`): same counts and verdicts.
- **Pre-registration 08, five calls on the wheels of Oct 12: G1 met (also by task), G2 met, G3 not met** (`analysis/results/g/analyze_g.txt`; 2,226 replays; 170 complete states of 198, 39 tasks; 47 interface failures, 43 of them context overflows after a usable first call). Shown a line the gold patch changes within five calls: as shipped 28.24% (144 of 510), mangled bound honored 33.73% (172), honored with the address note 37.45% (191). G1 +9.22 [+5.29, +13.92], by task [+4.13, +14.63]; G2 +5.49 [+2.35, +8.82]; G3 (address note on top of the honored bound, where a listed neighbor lies in a gold file) +0.00 [-5.86, +5.52]. Ranged reads with a mangled bound as shipped: 366 of 1,124 (32.6%), every one returned from line 1. Re-derived blind with S1 (`analysis/rederive_g.py`): same counts and verdicts.
- **Three blind reviews of the merged draft** (a three-minute reader, a skeptic, an organizer persona; the draft of 4:32 PM without the runs then in progress): 3.6, 3.4 and 3.5 of 5. Common requests: run the two harness changes to the end and score them by tests; the opening rule is false as an absolute and half of it holds for any agent; the paper learns little about the graph itself; a dozen sample sizes are unexplained. Each is acted on below.
- **Is a line number used more when the line is out of sight?** (EXPLORATORY, `analysis/explore_depth.py`.) A read without a range returns lines 1 to 150. Fresh episodes, first reads after a search hit: 22 of 38 ask past line 1 when the named line is within the first 150 lines, 61 of 62 when it is past them; after an addressed graph answer 4 of 36 and 16 of 42. Paused steps, lists with line numbers: 80 of 439 and 295 of 561. Other teams' public runs show the same split after a search hit (`public_runs_address.py` section 9, `public_runs_outside.py`: Gemma-4-31B 106 of 144 and 107 of 110; Claude 3.7 Sonnet 23 of 31 and 43 of 44; GPT-4o 32 of 47 and 68 of 73; Qwen3-Coder 178 of 242 and 257 of 272; Llama agents 7 of 12 and 35 of 35). Two public sets (GPT-4o and Qwen3-Coder in OpenHands) were added to the outside counts; after a path alone 1 of 660 and 90 of 1,786 first reads ask past line 1.
- **Pre-registration 13 (the address written as a search hit): no detectable difference in following; the line is asked for less often, narrowly** (frozen 5:05 PM, commit 0f1f0ff; `analysis/results/13/analyze_13.txt`; 1,221 replays, 1 interface failure, 402 complete states with E of the run of pre-registration 04). Reads a listed neighbor: search hits 7.55% (91 of 1,206), full address as JSON 8.62% (104); X1 -1.08 [-2.74, +0.58]. First reads of a listed neighbor's file that ask past line 1: 37 of 133 against 53 of 139; X2 -10.31 [-19.87, -0.43], by task [-22.51, +0.31]. Re-derived blind (`analysis/rederive_13.py`): same counts and verdicts; over 50 bootstrap seeds X2's upper bound is below 0 in 46.
- **Pre-registration 10 (Qwen2.5-Coder-32B-Instruct, 4-bit AWQ): M2 met** (`analysis/results/qwen/analyze_d2_qwen.txt`; 4,884 replays; 256 interface failures, no call or a tool that does not exist; 297 complete states). Bare names 3.25% (29 of 891), no list 3.25%, addresses 7.41% (66): E minus H +4.15 [+1.91, +6.62]. The independent script gives +4.15 [+2.02, +6.51]. Descriptive: without line numbers in the list this model asks past line 1 in 54 of 133 first reads of a listed neighbor's file, always from line 100 or line 590; with them in 64 of 85, 62 on a listed neighbor's first line.
- **What follows a read whose line bound was dropped** (EXPLORATORY, `analysis/explore_defect_fresh.py`): on the harness as shipped the next call reads the same file again after 59 of 66 mangled reads (55 ask for the same lines) and after 119 of 308 well-formed ranged reads.
- **The graph and the fix sites a run never saw** (EXPLORATORY; other teams' public whole runs; scripts by a second session, re-run here before each commit; `analysis/public_runs_missed_regions.py`, `public_runs_coedit_sites.py`, `public_runs_missed_links.py`). Of 1,326 changed regions that 258 runs never read, 859 lie inside a graph entity the run had seen no part of; 375 of those are one hop from an entity it had been shown (43.7% [35.2, 55.1]; 20.2% on degree-preserving rewirings). The graph files label every edge `calls`, store it in both directions and link a class to its members; 108 of the 375 are class-member links only. On call edges alone: 267 of 859 (31.1% [18.6, 38.4]) against 17.5% rewired, +13.6 [+3.1, +19.7]; over all missed regions 20.1% against 11.3%. In 212 of the 267 the missed place names the code the run had read (a caller), in 19 the reverse, in 35 both. Two blind recounts (`rederive_public_missed_regions.py`, `rederive_public_missed_links.py`) agree on every count of the second; the first differed by reading a changed region as a whole hunk, which the docstrings now exclude.
- **What the neighbor lists at the paused steps are made of** (EXPLORATORY, post hoc; `analysis/explore_neighbor_kinds.py`): of the 3,805 listed neighbors in unopened files, 85.5% are callers of the entity just read, 8.0% callees, 56.8% test code; class members are 8. Next call reads a caller's code: bare names 6 of 1,164 replays, addresses 49; a callee's: 14 and 26. In the replays of pre-registrations 04 and 12: callers 7 and 47, callees 17 and 24.
- **Pre-registration 14 (whole runs scored by tests): frozen 6:28 PM (commit 79346e3) and running.** The harness as shipped against the two changes of pre-registration 09, the harness's own evaluator with the subprocess sandbox, budgets of the public whole runs (40 tool calls, 25 minutes, 60 turns), seed 1, two rented A100-80GB with eight sessions at a time each. Task list from a validation pass without a model (`analysis/results/14/validate/`): the reference patch resolves 110 of the 129 public tasks in this sandbox and an empty patch resolves 7 of those; the other 103 are the run (fastapi 60, rich 43). Rules T1 (resolved), T2 (shown a changed line within eight tool calls), T3 (final patch overlaps a changed region). The analysis script was written before any run and reproduces the stored public counts on the other team's runs as a stand-in.
- **Harness versions recorded by these runs:** pre-registrations 12, 13 and 10 installed adk_submission 0.2.12 and swegemma 0.2.7 (the wheels of Sep 30); the five-call run of 08 and the whole runs of 14 installed adk_submission 0.2.13 and swegemma 0.2.11 (Oct 12). Each run stores its `pip_freeze`.
- **`analysis/reproduce.py`** has 52 jobs; not re-run in full since the afternoon.
