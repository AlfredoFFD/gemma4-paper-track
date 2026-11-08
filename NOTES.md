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
- **Kaggle.** Private dataset <kaggle-user>/gemma-graph-forks-inputs (states, replay.py, agent config, both harness wheel sets) and private script kernel <kaggle-user>/gemma-graph-forks-pilot (analysis/kaggle/forks_pilot.py), version 1 pushed at about 18:35 EST, 4 x L4, no internet. It records versions.json, runs a 12-state fidelity check (replayed vs logged prompt tokens), then 525 states x 5 arms x 3 seeds with a 9-hour budget in a fixed shuffled order. Analysis script: analysis/analyze_forks.py. Pre-registration: prereg/02-discrimination-forks.md (DRAFT; the team approves it Mon Nov 9, 9 PM).
- **Schedule.** Nov 9 9 PM approve the pre-registration; Nov 11 7 PM edit the draft; Nov 12 noon submit.
- **Not done.** No commit (nothing was asked). Claude Science is out of the loop. The teammate has not replied.

### 2026-11-08 19:20 EDT: Independent re-derivation of the GraphLoc trace numbers (EXPLORATORY)

**Why.** The project rule: every headline number is re-derived from the raw logs with an independent script before it enters the paper. Script: analysis/trace_stats.py, output analysis/trace_stats.json.

- **Matches Claude Science's Oct 1 entry:** 109 of 318 base runs call a graph tool; 26 get a non-empty result; search_similar_code 135 calls, 114 empty; get_code_neighbors 8 calls; get_code_subgraph 0; compaction (a prompt drop of more than 30%) in 216 of 318 base runs (68%).
- **Uptake, different denominator and control.** This script counts 26 events (a non-empty graph result followed by a read or edit, base arm only) with 13 hits (50%); Claude Science reported 13 of 43 (30.2%), presumably counting both arms or events without a following read. The control here draws the same number of random nodes from the same files as the returned nodes and gets 36.4%, against Claude Science's 15.8% for size-matched random nodes; the same-files control is stricter because whole-file reads touch every node in a file. Reading: the next action lands on a returned node about as often as on any other node of the same files, so the traces alone cannot show steering. The forks are the test.
- **Later edits:** a returned node's file is edited later in 8 of 26 events, inside the node's span in 1 (Claude Science: 1 of 48).
- **Overflow:** not re-derived here (the ATIF traces do not carry the vLLM error; Claude Science read the run records).
- **Also seen:** search_similar_code results carry similarity 0.9999 for unrelated test functions (the duplicate-embedding problem from the Sep 30 audit), so even non-empty search results are mostly noise.
