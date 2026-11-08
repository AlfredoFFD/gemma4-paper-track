# Research log

Append-only. Each entry: date and time (ET), author tag, what happened, and a "Why." line. Correct an old entry
with a new dated entry, never by editing it.

<!-- append new entries at the bottom -->

### 2026-09-30 ~15:00 ET [Claude Code] Project created

- Repo set up for the Gemma 4 Developer Agent Paper Track. Team of two.
- Starting point: the Sep 27 adversarial prior-art sweep. Of three candidate ideas, "does the agent read its code
  graph" survived best. The framing (Sep 29) is the code graph as externalized memory. The merged design is
  diagnose (Q1), measure (Q2), fix (Q3); see BRIEF.md.
- Nothing has been run. No data downloaded yet: it needs both of us to join the competition, plus a Kaggle API
  token.

**Why.** The deadline is Nov 12 (43 days away). A shared repo with the brief, prior art and
logging rules lets Claude Science start the literature map and pilot this week.

### 2026-09-30 ~17:00 ET [Claude Code] Kaggle read, data access, and a direct overlap

- Read the full Kaggle pages (details in docs/competition.md). Rules that bind us:
  - teams of up to 5, one team only, so the two of us must be one team
  - up to 2 writeups per team
  - arXiv allowed
  - winners license their code Apache 2.0 and deliver training and inference code
- Joined both competitions. The Kaggle CLI works; the dataset download is running (more than 11.7 GB).
- **Overlap:** GraphLoc (zzgtylors) is a paper-track writeup that already audits when the graph helps localization
  on this data (graph about equal to BM25; +0.9 points end to end, not significant). Our Q1 is covered. Its
  labels and code are Apache-2.0.
- **Verified bottleneck (thread #744692):** at the scoring setting, context compaction cannot fire, and an overflow
  discards the patch (44/44 overflowed sessions scored 0; 12-33% of runs overflow).
- Direction now pending between Option 1 ("why doesn't the graph help") and Option 2 ("finding vs remembering").
  Recommendation recorded in BRIEF.md.

**Why.** Starting Q1 would have duplicated a public writeup. The decision has to happen before any compute is
spent.

### 2026-09-30 ~19:10 ET [Claude Code] Names removed from repo content

- At the team's request, personal names and idea attributions were removed from every tracked file (README, BRIEF,
  LOG, docs) and from issues #1 and #7. Log author tags are now `[team]`, `[Claude Science]` and `[Claude Code]`.
  Earlier entries above were edited only to remove names; nothing else about them changed.

**Why.** The repo is shared, and it may be open-sourced if we win (the rules require Apache 2.0 code release). Its
content should stand on its own, without personal attribution.

### 2026-09-30 ~19:30 ET [Claude Code] Dataset downloaded and verified; project instructions added

- Kaggle dataset downloaded (21,929,289,087 bytes; zip sha256 `06cec82c...7421`) and unzipped into `data/` with no
  errors. Counts: 129 tasks, 129 snapshots (21 GB), 127 graphs, 127 embeddings, 124 wheels. Graphs and embeddings
  are keyed by commit; match them to tasks through `repo` + `base_commit` (details in data/README.md).
- Added `CLAUDE.md` (shared instructions for AI assistants: judge-first thinking, novelty checks, division of
  labor, rules). A local-only instructions file stays out of git.
- The Claude Science kickoff now starts with a file-access check.

**Why.** Both agents need the same bar and the same map of the data before any analysis starts. A file-access check
up front catches a partial-read problem before it can silently weaken the literature map or the numbers.

### 2026-09-30 ~19:45 ET [Claude Code] Names rule refined

- Names now appear only where they fit: authors or team, repo owner, the paper's byline. No attributing ideas,
  quotes or framings to a person. The README team line names the repo owner.

**Why.** The earlier removal overcorrected. The point was to avoid crediting ideas to individuals in the docs, not to
hide who is on the team.

### 2026-09-30 19:34 ET [Claude Science] Step 0: file access confirmed; the kickoff changed mid-session

- Read in full, directly from disk (bytes / lines / sha256 prefix):
  - BRIEF.md: 10,976 / 162 / febf0420228e
  - docs/competition.md: 14,487 / 215 / bd6826bf26ea
  - private/origin-transcript.md: 41,339 / 464 / ea3773e8ae87
  - data/HARNESS_README.md: 49,356 / 671 / 3d6e57a13234
  - also CLAUDE.md (63 lines), LOG.md (66), README.md (52), docs/prior-art.md (81), docs/ideas.md (37),
    docs/methods-we-bring.md (36), docs/how-we-work.md (51).
- NOTES.md: read in full at session start, when it held 6,465 bytes (the 19:12 and 19:21 entries). It has since grown
  to 10,472 bytes / 146 lines. I read the rest only after logging the rule review below.
- docs/claude-science-kickoff.md changed while this session ran. First read: 3,769 bytes (tasks A-C). Re-read at
  19:27: 6,610 bytes / 104 lines (tasks A-D, with an independent re-derivation as B and a pilot design as C). The
  team's chat instruction for this session follows the first version: don't redo the Phase-0 numbers, review K1-K3
  instead, and put the main effort into the prior-art check. I follow the chat instruction and record the conflict.
- data/tasks.jsonl: 129 lines, 129 records (fastapi 67, rich 48, requests 13, httpx 1). There are 127 distinct
  (repo, base_commit) pairs; two commits are shared by two tasks each (rich 4d6d631a, requests 7a13c041). Every task
  matches one graph and one embedding file by `<repo short name>_<base_commit>`. No file is zero bytes. Graph files are
  0.59-5.18 MB (median 3.79).
- One graph opened in full (fastapi_15661): a directed multigraph with 4,263 nodes and 2,430 edges, all of type
  `calls`. Node attributes are only `id`, `name` and `text`: no file path, no line numbers. 71.8% of nodes have no
  edge, and every edge's reverse is also present. The .npz holds one float32[256] vector per node (4,263 keys, equal to
  the node ids). The largest node text is 383,734 characters.
- Not opened, on purpose: experiments/00-pointer-audit/, so that an independent re-derivation stays possible. Nothing I
  tried to open failed.
- git: the last commit is 29a3b28 (19:06). NOTES.md is modified but uncommitted, and experiments/00-pointer-audit/ is
  untracked.

**Why.** The kickoff asks for proof of direct reads before any claim. Because the kickoff changed under this session,
the log has to say which version each later step follows.

### 2026-09-30 19:34 ET [Claude Science] Loophole review of the pointer-audit rule (K1-K3), before reading its numbers

What I knew when writing this: the 19:21 NOTES entry says the audit came back WEAKENED (so K2 did not KILL, and at
least one of K1 and K3 is WEAKENED). The revised kickoff reports two results: an exact-function re-fetch saves about
2.6x over a 150-line window, and 13 of 129 tasks have a graph bite. I had not seen K1 or K2, NOTES.md past 19:21, or
anything in experiments/00-pointer-audit/. So this review is not blind, and every change it suggests is POST-DATA.

Loopholes, most consequential first:
1. **K3 does not involve the graph.** Both arms are line-addressed read_file calls. The treatment (fetch exactly the
   unit) can't go through the graph tools: they return names (neighbors, subgraph) or the code of *other* nodes
   (search_similar_code), never a requested node's own text, and in the graph I opened nodes carry no line numbers.
   It can be done without the graph: read_file takes an end_line, and run_command can print one function (grep -n,
   sed, or Python's ast). So a K3 KILL would have killed function-granular re-reading, not graph memory, and a K3 PASS
   would not have supported graph memory either.
2. **No criterion measures the lever.** Context saved by memory = (number of re-reads) x (cost per re-read). K1-K3
   measure only the second factor, and only on gold files. What decides the direction is the share of context, in
   real 32k trajectories, spent re-showing code the agent has already seen, next to thinking tokens, test and command
   output, and the fixed prompt. A 2.6x cut on a large re-read share could matter; a 10x cut on a small one would not.
   K3's thresholds (2 and 5) aren't derived from that link.
3. **The unit definition pulls K3 toward 1 and can pull K1 down.** When a patch adds a def, the unit is the innermost
   scope that already existed, often a whole class or the module. Those units are large, so window/unit nears 1. The
   graph has no module nodes, so if module-level units count toward K1's "all units addressable", every task with a
   module-level edit fails K1 by construction. The rule doesn't say whether they count.
4. **Addressable isn't the same as correct.** A name match (src/ and docs_src/ dropped, __init__ both ways, nested defs
   flattened) can hit a different node with the same name, and K1 has no check that the node's text is the unit's
   source. The harness also resolves names by exact, then suffix, then case-insensitive, then substring match
   (HARNESS_README 6.3), so a short pointer can silently land on another node.
5. **No margin for noise.** The thresholds carry no interval. With about 100-120 tasks, a 95% interval on a share is
   about ±8-10 points. 67 of the 129 tasks are fastapi and 48 are rich, and the two shared commits aren't independent
   graphs. Per-repo values should sit next to the pooled one.
6. **Characters aren't tokens.** K2 compares characters with a 32,768-token window. Tool results reach the model as
   JSON (reportedly double-encoded), so escaping raises a read's token cost above characters/4. K3 is less affected,
   since both arms are escaped alike.
7. **K2 can barely fail here.** It counts only gold files, not the exploration reads that fill most of a trajectory,
   and core modules in these repos are large (a guess; I haven't measured). Its PASS carries little information.
8. **The registration isn't verifiable yet.** Both rules exist only in uncommitted NOTES.md, the audit folder is
   untracked, and the last commit (19:06) predates both rules. File times (script 19:17, run log 19:18; decoy script
   19:22:03, its log 19:22:46) fit the stated order, but they are not proof. The decoy-bite rule (19:21) was written
   after the pointer-audit outputs existed and takes them as input (results/units.csv). That's allowed, but it should
   be declared.

Decoy-bite rule (outside the requested scope, but it now drives the direction): 13 of 129 is 10.08%, one task above the
10% KILL line, so a single task decides KILL vs WEAKENED. One fork should be settled from the harness source before
the value is quoted: "degree at most 50". In the graph I opened every edge is stored with its reverse, so an edge count
doubles the unique-neighbor count. Whether get_code_neighbors de-duplicates, and which 50 it returns, decides which
nodes pass the filter.

What follows:
- The registered labels stand as computed; nothing above can change them.
- In the direction decision, read K3 as a bound on the gain per re-read, not as evidence against memory. The solid
  findings are K1 and the harness facts (names only, no async functions, no line anchors).
- POST-DATA readings worth computing, labelled as such: K3 on function and method units only; K1 with a text-fidelity
  check; K1 per repo with Wilson intervals; the decoy-bite share under both degree definitions.
- The decisive quantity (the re-read share at overflow) needs trajectories, so the pilot should log it.
- Commit NOTES.md and the audit folder now, and commit future rules to prereg/ before their run.

**Why.** The team asked for a loophole review before the results land. They had partly landed, so this entry records
what I knew when I wrote it, and the review can be weighed accordingly.

### 2026-09-30 21:34 ET [Claude Science] GraphLoc's public notebooks verified; its traces re-analyzed (EXPLORATORY)

- Pulled GraphLoc's four listed notebooks, plus the three they depend on (two repeat runs and a test-deps notebook),
  through Kaggle's public API (kernels/pull and kernels/output), read-only. Its outputs include one trace per run:
  3 runs x 2 agents x 106 tasks = 636 traces (84.7 MB). They stay in the Claude Science workspace, not in the repo.
- Confirmed from its printed outputs:
  - base resolves 92/318 (28.9%) and skill 95/318 (29.9%): +0.9 points, 95% CI -4.1 to +6.3 (paired task bootstrap
    pooled over 3 runs);
  - in the base arm, runs resolve 82/143 when the patch touches a gold function and 10/175 otherwise.
- Its setting: official swegemma; subprocess sandbox on 4xL4; vLLM at 32,768; T=0.2; max_output_tokens 16,384;
  thinking budget 4,096; compaction passed explicitly (token_threshold 14,336); 40 tool calls, 25 minutes, 60 turns
  per task. The wheelhouse version is not recorded (runs dated Sep 25-28).
- Its failure taxonomy (analyze_e2e.py) crosses where the patch edits (no patch, wrong file, gold file, gold function)
  with why the run failed (time, tool or turn budget; error; patch did not apply; tests could not run; target tests
  fail; only other tests fail). It does **not** split "never called the graph" from "called it but ignored it" for the
  harness's graph tools. For its own skill, it records whether the skill ran and whether the patch edits a listed
  candidate (38.5%). That is an observational version of the split, for the skill only.
- A reporting bug: its end-to-end summary's tool counts per task equal the true calls plus the share of traces that
  use the tool (observation records are counted as calls). Example: search_similar_code 0.61 reported vs 0.33 true per
  task (run 1, base). The identity holds exactly for all 6 tools I checked.
- EXPLORATORY numbers from the 636 traces (my script analysis/graphloc_traces.py, sha256 69e16f87814d...; per-run table
  sha256 2d7ddea816f4...):
  - **Overflow:** 26 of 636 runs (base 14, skill 12; 15 distinct tasks) end in ContextWindowExceededError. vLLM's
    message says the prompt had at least 16,385 tokens while 16,384 output tokens were requested. So under the sample
    sampling config, the prompt cap is 16,384 tokens, not 32,768. All 26 have an empty patch and none resolved; 8 had
    already edited files.
  - **What triggers it:** in 23 of the 26, the last call is a large run_command or read_file output (about 4-13k
    characters) arriving at a prompt of about 13-14k tokens. The other 3 are one task (fastapi_14258, base arm, every
    run): the first call is search_similar_code, which returns 55,164 characters.
  - **Graph use (base arm: all nine tools, sample prompt):** 109 of 318 runs call a graph tool, but only 26 ever get a
    non-empty result. 114 of 135 search_similar_code calls return zero results with status "ok": the agent sends
    natural-language queries to a tool that only looks up node names. get_code_neighbors is called 8 times and
    get_code_subgraph never.
  - **Re-reading:** 27.0% of read_file characters (base) re-show lines already shown in the same session from an
    unedited file. That is 10.3% of all characters entering the context. Per run: median 18%, 90th percentile 43%.
  - **Compaction:** 68% of base runs show a prompt falling below 70% of the previous step's, so compaction did fire at
    14,336 in this setting. Peak prompt: median 14.5k tokens.
- Caveats: GraphLoc's budget and its 12 concurrent workers differ from scoring, and 132 base runs hit its 25-minute
  limit. Shares are in characters, not tokens. The re-read measure covers read_file only; shell views (cat, sed, grep)
  add another 1.56M characters in the base arm.

**Why.** GraphLoc is the baseline every judge will compare against, and the kickoff asks whether its taxonomy already
covers our split. Its public traces also answer, without any GPU, the question my K1-K3 review called decisive: what
fills the context when a run overflows.

### 2026-09-30 21:34 ET [Claude Science] The harness changed on Sep 30; source needed from Claude Code

- The wheelhouse dataset (metric/gemma-4-developer-agent-wheelhouse) is at **v28** (2026-09-30 20:33 UTC).
  docs/competition.md still says v25. Two other versions came out on Sep 30: v26 (19:08 UTC) and v27 (19:40 UTC),
  whose notes read "Rebuild adk-submission and swegemma wheels (scheduler_reserve_full_isl and graph output cap)".
  A graph output cap would remove the 55k-character search_similar_code output seen in GraphLoc's traces, so "the graph
  tools have no output cap" is now version-dependent.
- I couldn't fetch the wheels: the download redirects to a path-style storage.googleapis.com URL, which the sandbox
  always blocks.
- **Request for Claude Code:**
  - Download v28 and v25 (v25 is the closest to GraphLoc's runs) with the Kaggle CLI into data/wheelhouse/vNN/.
  - Unzip the swegemma, adk-submission and adk-eval-core wheels there, and note the paths in NOTES.md.
  - I will then read scripts/inference.py (the compaction config at scoring), swegemma/config.py (the CLI default),
    swegemma/tools/graph.py (neighbor de-duplication, the output cap, whether the query node is excluded) and the
    request path (the max_output_tokens reservation).
- **Check before any local run:** whether the graph tools appear in the agent's prompt when only the commit-named
  graph files exist. One rival entry reports that they are silently disabled for the zip download; another reports
  the opposite.

**Why.** The pilot depends on three facts: compaction at scoring, the prompt cap, and the graph-tool caps. They have
changed or are disputed, and only the source settles them.

### 2026-09-30 21:57 ET [Claude Science] Prior-art check (task A): verdicts, corrections, and the agent-architectures notes

- **Method.** Five Claude Science sub-agents, each reading from full text with the version recorded:
  - the eight memory items named in the kickoff;
  - an open search against Direction 1 (about 60 papers read from full text);
  - the reliance items plus an open search against Direction 2;
  - the rival entries;
  - the other citations in docs/prior-art.md.

  I re-checked the decision-carrying numbers myself (RepoAtlas Table 2, Context-Folding Table 1, SWE-agent Table 3,
  2609.20804, Delivery, Not Storage, StateTape).
- **Files.**
  - The five reports are copied to private/claude-science/2026-09-30/ (gitignored, because they name entrants). sha256
    prefixes: memory items 596efdfa83a4, memory search 619c31693a16,
    reliance f7eeadd26fa8, rivals c9a049332fd9, citations 725ab92d5ee7.
  - The consolidated report is docs/claude-science-prior-art-check-2026-09-30.md (sha256 9f808b56ca38...).
- **Direction 1: WEAKENED.**
  - 1b (overflow as the outcome) and 1c (symbol pointers as a token saver) are KILLED as novelty claims.
  - 1a (graph memory under a hard limit) is WEAKENED.
  - 1d (vs a notes file) is OPEN, as a control.
  - Nearest works: 2609.20804, StateTape 2609.36319, CodeNib 2607.25431, Prometheus 2507.19942, ContextSniper
    2607.01916, SWE-MeM 2606.28434, CODESTRUCT 2604.05407. One rival entry tracks overflow in this harness.
- **Direction 2: WEAKENED, with all of 2a-2d WEAKENED.** Nearest works: 2609.05587 (corrupted tool returns for 14
  models including Gemma-4-31B, with LoRA reliance tests), Raman et al. 2021 (2010.12872), Huang et al. 2024
  (2309.16595), Oracle Poisoning 2605.09822, Don't Blindly Trust It 2606.21409, RepoMirage 2605.26177, and
  codegraph-loc (agents use the graph as a symbol index). What survives is the integrated, intervention-based account
  on the organizers' own tools in end-to-end repair.
- **Other angles.**
  - Pushed write-back memory: WEAKENED (StateTape; Delivery, Not Storage 2607.20972; RepoAtlas vs SeeRepo).
  - Patch-loss accounting: OPEN but specific to this harness.
- **Kickoff items.**
  - 2609.20804's recall arm is rarely used, not unused (36 of 64 settings never call it).
  - Codebase-Memory, Code Isn't Memory and the language-server study run under no hard context cap.
  - Code Isn't Memory's resolve gain is largest on 1-file tasks, not multi-file ones.
  - Oracle Poisoning had 270 trials with one timeout, so 269 valid trials, all accepted.
  - CodeCompass used 30 hand-built tasks, not SWE-bench.
  - Deterministic Anchoring is interventional.
  - 2607.09691 is an oracle-localization study, and its ~9% flip rate is a single-shot side measurement (6 of 70).
  - The G-HRR and GraphSWE-Gemma entries ran no experiments.
- **Section 5 of private/refs/agent-architectures-2026-09-30.md, checked.**
  - Confirmed: 78.7% unmanaged overflow; the recall figure, which is 56% of *settings*; the Context-Folding and
    SWE-agent figures; planning and predefined-tool gains, measured at 128k, not 32k.
  - RepoAtlas +2.3-4.4 and LocAgent +0.7-1.4 points over mini-SWE-agent, with LocAgent at 1.56-1.88x RepoAtlas's input
    tokens, are confirmed from Table 2. My chat reply at about 21:40 ET said these numbers did not match; that was
    wrong, because I had compared them against SeeRepo.
  - "Push beats pull" is only weakly supported, since the systems differ.
  - "68.6% of runs ended with no edit" was not found.
  - The claim that ADK never compacts inside one invocation is contradicted in GraphLoc's setting.
  - Thinking budgets were exceeded in 0.52% of base-arm steps.
- **POST-DATA note on the decoy-bite rule.** In GraphLoc's traces, get_code_neighbors returns de-duplicated names (28
  calls, no duplicates, at most 14 names). The "degree at most 50" filter can therefore only have removed bites, so
  13/129 is a lower bound (11.6% without the cap, per NOTES). That fork cannot flip WEAKENED to KILL.
- **Limits carried from the sub-agents.**
  - Main texts were read in full, most appendices were not, and figure images were not viewed.
  - OpenReview is blocked, so some venues come from secondary listings.
  - About 50 further candidates were triaged at the abstract level only, so every "not found" is provisional.
  - No Kaggle writeup or discussion thread was read; their pages render client-side.

**Why.** The team asked for an adversarial check of both directions before choosing one. The verdicts, and the place
each claim came from, need to be on record before any experiment is designed around them.

### 2026-09-30 21:57 ET [Claude Science] Recommendation: Direction 2, reframed; draft pre-registration written (not frozen)

- **Recommendation.** Lead with Direction 2, reframed as "why the organizers' code graph adds about one task": estimate
  stage by stage, by intervention, where the graph's information is lost. The stages are consultation, query
  resolution, fix-relevant content, uptake and context cost. The two interventions are push vs pull delivery of graph
  neighbors and a planted decoy edge scored against the true-graph base rate.
  - Fold in from Direction 1: the cost stage and an EXPLORATORY patch-loss count.
  - Drop graph-as-memory as the headline.
  - Keep the LoRA optional; 2609.05587 already reports LoRA reliance effects on Gemma-4-31B.
- **Honest odds (guesses).**
  - A careful judge rates the method novel for this setting: perhaps 50-60% if it is framed as a transfer of
    perturbation-based reliance tests, about 20% if pitched as new.
  - Overall Best Paper: perhaps 10-15% if executed cleanly and early.
  - Direction 1 as the lead: perhaps 5-10%.
- **Weak spots.**
  - The funnel numbers come from GraphLoc's setting, not scoring.
  - Decoy following may be near zero.
  - Anyone can recompute the funnel from GraphLoc's public traces.
  - The organizers may fix the tool interface.
- **Draft pre-registration:** prereg/01-graph-uptake-draft.md (sha256 e342a790fc14...), marked DRAFT.
  - Arms: A pull/true, B push/true, C push/decoy, and an optional D with the tools removed.
  - Primary hypotheses: H1, decoy following (C vs B); H2, push raises uptake (B vs A). Both use exact McNemar on (task,
    seed) pairs, with FOLLOWS / IGNORES / INCONCLUSIVE-style labels.
  - A simulated power table, assuming outcomes are independent within pairs: following of about 15 points or more
    above the base rate is detected at 212 pairs.
  - A pilot and a gate, plus nine open items for the authors. Nothing in it is frozen, and no data exists under it.
- **Not done, and why.**
  - The revised kickoff's task B (an independent re-derivation of K1-K3 and the decoy-bite share): skipped per the
    team's chat instruction. It is still owed before any of those numbers enter the paper.
  - Task C's exact pilot commands, runtime and cost: blocked until the harness source is available (see the request
    above).

**Why.** The kickoff asks for a recommendation with evidence and a draft pre-registration. The team decides, so the
draft is written to be frozen or discarded, not run.

### 2026-09-30 21:58 ET [Claude Science] Corrections to tonight's entries and to two sub-agent reports

- **21:34 entry ("The harness changed on Sep 30"):** only v27's notes mention the graph output cap ("Rebuild
  adk-submission and swegemma wheels (scheduler_reserve_full_isl and graph output cap)"). v26's notes read only
  "Update 2026-09-30". The sentence was ambiguous; the request to Claude Code stands.
- **Reliance report** (private/claude-science/2026-09-30/prior_art_reliance.md): its limits section says the Part 2
  appendices were keyword-scanned, while its submitted deviations say they were mostly unread. Treat them as unread or
  keyword-scanned only, which is how the 21:57 entry describes them.
- **Rivals report** (rival_entries.md): its screening counts do not add up (35 candidate repos besides the 3 named
  rivals, but 27 screened by README only plus 9 with no README makes 36). No rival verdict depends on that count.

**Why.** LOG.md is append-only, so errors are corrected by a new entry, and the copies in private/ are what Claude
Code will read.

### 2026-09-30 23:53 ET [Claude Science] Uptake in GraphLoc's traces: definition fixed before computing (EXPLORATORY)

The team asked: after a non-empty graph result, does the next read or edit touch a returned node? GraphLoc's data
already exist, so any answer is EXPLORATORY. The definition is fixed here before the number exists.

- **Event:** a graph-tool call with a non-empty result: `search_similar_code` with at least one result, or
  `get_code_neighbors` with a count of at least 1 (`get_code_subgraph` was never called).
- **Returned nodes:** the result's node names (search) or neighbor names, excluding the queried node itself.
- **Location:** each returned node maps to a file and line span in the task's base snapshot by AST, using GraphLoc's
  Apache-2.0 module naming (graphloc.py), with nested defs folded into their parent. Unmapped nodes are counted.
- **Touch, for a read:** a `read_file` result touches a node if its returned lines overlap the node's span (only while
  that file has not been edited), or if its content contains one of the node's distinctive lines. A distinctive line is
  at least 20 non-space characters long and occurs exactly once in the base file.
- **Touch, for an edit:** an edit touches a node if its diff's removed or context lines include a distinctive line of
  the node. A write_file call to the node's file counts as a touch.
- **Primary:** the share of events whose next `read_file` or edit touches at least one returned node.
- **Secondary:**
  - any later read or edit in the run touches a returned node;
  - the same, restricted to new nodes (not named in the issue, and not touched before the event);
  - the final patch edits a returned node;
  - a shell-view reading: `run_command` text containing a returned node's short name of at least 4 characters.
- **Comparator:** the same indicators for size-matched random nodes from the same files (200 seeded draws per event),
  to separate node-level targeting from merely reading the same file.
- **Reported as:** counts with Wilson 95% intervals, by tool and arm. Units are events, plus runs with at least one
  event.

**Why.** With about 50 events, the definition is the main forking path, so it is on record before the counts exist.

### 2026-10-01 00:18 ET [Claude Science] Uptake of graph results in GraphLoc's traces: results (EXPLORATORY)

The definition is the one logged at 2026-09-30 23:53, unchanged. Script `analysis/graphloc_uptake.py` (sha256
a4fd6e71957a...), per-event table `graphloc_uptake_events.csv` (sha256 e5b992269a32...), both saved as Claude
Science artifacts. Data: GraphLoc's public traces, base and skill arms, 3 runs, 636 runs in all. I did not determine
which wheelhouse version GraphLoc's runs used.

- **Events:** 48 non-empty graph results in 42 runs and 28 tasks.
  - base: 21 search, 8 neighbors; skill: 4 search, 15 neighbors.
  - 352 of 357 returned nodes mapped to a span in the base snapshot.
- **Primary:** 43 events are followed by a read or an edit. The next one touches a returned node in 13 of 43 (30.2%,
  Wilson 95% CI 18.6-45.1). Size-matched random nodes from the same files would give 6.8 (15.8%).
  - By tool: neighbors 7 of 21, search 6 of 22.
- **Secondary:**
  - new nodes only (not named in the issue, not touched before): 8 of 43
  - any later read or edit touches a returned node: 30 of 48; new nodes only: 22 of 48
  - the final patch edits a returned node: 1 of 48 events (31 of the 42 runs have a non-empty patch; 9 resolved)
  - a later shell command names a returned node: 8 of 48
- **Post-hoc** (not in the 23:53 definition):
  - a returned set contains a symbol the gold patch edits in 4 of 48 events (3 neighbors, 1 search)
  - 29.5% of returned nodes are in test files and 9.4% in docs or scripts
- **Reading:** when the graph returns something, the next read or edit goes to it about twice as often as to random
  code in the same files. But the content rarely holds the fix, and the final patch almost never edits a returned node.
  The query stage leaks most and content second, so a query-stage fix alone predicts more graph use and little change
  in resolve rate.
- **Caveats:**
  - Search results already include code, so a read is not needed to use them; read-based uptake undercounts search use.
  - A touch is a location overlap, not proof of use.
  - Events are pooled over arms and runs and are not independent (42 runs, 28 tasks).
  - I checked eight printed events against their traces (four touches, four non-touches); all matched the definition.

**Why.** The team asked whether the agent acts on graph results. The answer bounds what an interface fix can buy, and it
fixes the uptake indicator for the pre-registered pilot.

### 2026-10-01 00:18 ET [Claude Science] G-HRR setup verified from its repo: no model was run

Source: github.com/Tarekswd/g-hrr-gemma4 at commit 4becfb7904704c7a5752dfa2ae029ca707bf3a8d. I read paper/paper.md and
src/experiments/experiment_runner.py in full and grep-scanned the other 27 Python files. Full note (it names a rival
entry, so it stays private): `private/claude-science/2026-10-01/ghrr_verification.md`, sha256 90cc01c11355...

- **Claimed:** 100 SWE-bench Lite and Verified tasks with Gemma 4 31B served via vLLM (paper.md sections 4.1 and 4.3).
- **The code contains no model, vLLM, ADK or swegemma call.**
  - Tasks come from a template with a random repo (experiment_runner.py:30).
  - Outcomes are `passed = random.random() < prob`, using hard-coded per-system probabilities (experiment_runner.py:106).
  - The control, localization and ablation results are literals (red_team_control.py:28-49, localization_experiment.py:28-43,
    ablation_runner.py:23-72).
  - The test runner is never called.
- **Arithmetic:**
  - Table 1's easy, medium and hard columns equal those probabilities for all 8 systems.
  - 7 of 8 medium cells are impossible as shares of 45 tasks.
  - The raw CSV gives a different pass rate for every system (G-HRR 48% vs the paper's 44.0%).
- **Verdict:** G-HRR's numbers are not evidence and must not be cited as results. It remains a pitch-level overlap.

**Why.** The team asked for this check (NOTES.md 21:44 left it to Claude Science). A rival's numbers can enter our paper
only if they come from runs.

### 2026-10-01 00:18 ET [Claude Science] Correction to my 2026-09-30 21:57 note on the degree cap

I wrote that de-duplicated neighbor output makes 13/129 a lower bound. That is too strong.
- **What the traces show:** none of the 28 neighbor calls returns a duplicate name, and six return exactly one name.
  Every stored edge has a reverse, so the tool does not print each direction separately.
- **What they can't show:** the largest output has 14 names, so the traces cannot tell whether the 50-entry cap applies
  before or after de-duplication.
- Claude Code's fork (NOTES.md 21:25: 11/129, a KILL, if the cap counts both directions) stays open until the harness
  source is read. GraphLoc's harness may also predate v27, which added a "graph output cap".

**Why.** The decoy test's KILL/WEAKENED label depends on this; the earlier note closed the question on evidence that
cannot close it.

### 2026-10-01 00:18 ET [Claude Science] Advice on a combined frontier-style architecture (team question, chat)

The team asked whether combining ideas from Claude Code, Codex and Jev into a new architecture for Gemma could be the
paper. My recommendation: not as the headline. Instead, use them as two arms of the funnel, each aimed at a measured
leak:
1. **Interface fix:**
   - an accurate tool description
   - a keyword-to-node-name lookup as a sandboxed skill
   - file, line and signature in the tool output
   - a test-file filter

   Comparator: the same lexical front-end without the graph, so that BM25 is not what gets measured.
2. **Presentation, with content fixed:**
   - pull vs push
   - bare names vs names with signature and location

   Nearest work: Talk like a Graph (static graph QA, not agents).

Two constraints, both checked:
- Jev cannot run inside a submission. The sandbox has `network_mode="none"` (HARNESS_README:249), and one model serves
  every agent and sub-agent (docs/competition.md:57-58).
- Sending repo code to its API would give competition data to a third party (docs/competition.md:115-116).

**Why.** A bundle of known components reads as a port. With GraphLoc's precision (95% CI about 10 points wide) we
couldn't say which part helped.

### 2026-10-01 00:19 ET [Claude Science] Correction to the prior-art report: Context-Folding row

A background review flagged it. `docs/claude-science-prior-art-check-2026-09-30.md` said "Context-Folding at 32K: 43.6%
to 49.2% without RL". The 43.6% belongs to the ReAct baseline, not the folding agent. I re-read Table 1 of 2510.11967 in
the PDF (page 7, SWE-Bench Verified, Seed-OSS-36B):
- ReAct at 32K: 0.436
- summary agent: 0.488
- folding agent: 0.492 without RL, 0.580 with FoldGRPO
- ReAct at 327K: 0.552

The row now gives each system its own number. New sha256 20b01268cf60... (was 9f808b56ca38...). The file is not
yet committed.

Also worth noting: without RL, folding (0.492) is level with summarization (0.488) and below the long-context ReAct
agent. Only the RL-trained folding beats it.

**Why.** Crediting the paper's method with its baseline's score would misstate the nearest prior work on 32K context
management.
