# The competition: rules and facts

Read from the Kaggle pages by Claude Code on Sep 27-30, 2026, while logged in. Quotes are exact. The sections
below were read directly; a full read of the Rules, Discussion, Leaderboard, Code and Writeups tabs is added in
the next section once it lands.

## Paper track (https://www.kaggle.com/competitions/gemma-4-developer-agent-paper)

- **Scope:** "Submit a Research Paper advancing the state-of-the-art for agentic software engineering."
  "Participation in the main competition isn't required to submit to the Paper Track." "Submissions can include
  any related research, as long as it is unpublished."
- **Timeline:** start Sep 22, 2026; **final submission deadline Nov 12, 2026**. "All deadlines are at 11:59 PM UTC
  on the corresponding day unless otherwise noted." (11:59 PM UTC on Nov 12 is 6:59 PM EST.)
- **Evaluation:** five criteria, scored 0 to 5, final score = average:
  - **Novelty:** "Does the work provide new insights, deepen understanding, or highlight important properties of
    existing methods?"
  - **Quality:** "How general and universal is the Submission approach beyond the competition? ... How well does
    your method generalize?"
  - **Relevance:** "Is there significance and/or potential impact of the research on the field of software
    engineering and agentic learning?"
  - **Verifiability:** "Does the paper include sufficient information to understand how an innovation works; to
    understand how data was obtained, analyzed, and interpreted?"
  - **Clarity:** "Is the paper clearly presented and written?"
  - Ties go to the paper "entered first to the Competition". The rubric evaluation is not shared with entrants.
- **Submission:**
  - A Kaggle Writeup with a title and subtitle, abstract, introduction, research description (methods and
    experiments), and related work and citations.
  - "Scope: 3,000 words maximum, reporting original, unpublished research." "Non-Archival: Submission to this
    competition does not prevent submission to other conferences or venues."
  - Optional public notebook in Project Links (a private Kaggle notebook becomes public after the deadline), or an
    arXiv-ready PDF via the Public Project Link.
  - "Any un-submitted or draft Writeups by the competition deadline will not be considered."
- **Suggested topics:**
  - Tuning & Optimization (PEFT and RL for SWE agents)
  - Code Comprehension (code-graph generation, parsing, embedding)
  - Tasks & Benchmarks ("new tasks, evaluation datasets, or resources targeting code structure, graphs, and
    structured code generation")
  - Graph Reasoning (LLM reasoning over large-scale graphs)
- **Prizes ($35,000):**
  - Overall Best Paper $15,000 (the highest average score)
  - Best New Resource $10,000 ("a new dataset, tool, or software")
  - Best New Application $10,000 ("a new use-case", e.g. "using code-graphs for writing TPU kernels")
  - Top submissions "highlighted at a Google hosted expo during NeurIPS 2026". The track does not award points or
    medals.
- **People:**
  - Judge listed: Elan Markowitz (Machine Learning Engineer, Google).
  - Citation authors: Markowitz, Perozzi, Rózemberczki, Cameron, Hemmati, Li, Galkin, Farhadi, Holbrook, Oldacre.
- **Participation on Sep 27:** 1,849 entrants, 56 teams, 57 submissions.

## Main competition (https://www.kaggle.com/competitions/gemma-4-developer-agent)

- **Task:** "post-train Gemma 4 to build autonomous software engineering agents". Scored like SWE-bench:
  - the agent's patch is applied and the issue's validation tests run
  - score = share of tasks whose tests pass
  - "a limit of 12 hours to submit patches for all tasks, inclusive of sandbox setup time"
- **Submission:** `submission.zip` with `agent.yaml` at the root (Google ADK Agent Config), plus optional prompts,
  sub-agents, skills (sandboxed scripts and resources), and PEFT LoRA adapters in `.safetensors`.
- **Model:** "At present, we only support the gemma-4-31b-it-qat-w4a16-ct Gemma 4 model variant. You must choose
  this model for every agent and subagent." Adapters may differ per agent.
- **Tools:** agents may only use harness tools or custom sub-agents:
  - `run_command(command)`
  - `submit_patch()`
  - `get_status()`
  - `read_file(filepath, start_line, end_line)`, 1-indexed
  - `edit_file(filepath, old_string, new_string, allow_multiple)`
  - `write_file(filepath, content)`
  - `get_code_neighbors(node, edge_type, max_neighbors)`
  - `search_similar_code(query, k)`, cosine similarity over the precomputed embeddings
  - `get_code_subgraph(nodes)`
- **Timeline:** start Sep 23; entry and team-merger deadline Nov 25; final submission Dec 2 (all 11:59 PM UTC).
- **Prizes:** $65,000 ($37k / $18k / $10k). It awards points and medals.
- **Participation on Sep 27:** 5,220 entrants, 687 teams, 1,479 submissions.

## Data (competition Data tab)

- **tasks.jsonl:** 129 public development tasks from fastapi/fastapi, Textualize/rich, psf/requests and
  encode/httpx. Each has an instance_id, repo, base_commit, problem_statement, hints_text, gold `patch`,
  `test_patch` and created_at.
- **snapshots/:** git working trees at base_commit (future history removed).
- **graphs/:** NetworkX AST call and dependency graphs in JSON, directed multigraphs.
  - Node `id` is the fully qualified symbol path (e.g. `fastapi.routing._prepare_response_content`).
  - Node `text` is the full source of the definition.
  - Edges have a `type` such as `calls`.
- **embeddings/:** per-node float32 vectors of length 256 (.npz), powering `search_similar_code`.
- **wheels/:** offline dependency wheels. **docker/:** sandbox image specs. **sandbox/setup.py:** editable install
  and a clean baseline commit.
- **Harness and samples:** `sample_submission/` (a baseline ADK agent) and `HARNESS_README.md` (the libraries
  swegemma, adk-submission and adk-eval-core; the two-container sandbox lifecycle; local CLI evaluation).
- **Test set:** "about 120 tasks ... evenly divided between the public and private splits"; "curated from a set of
  private repositories"; each test task checked so "a larger frontier model can pass the case or get within a
  single test case of passing".
- **License:** Apache 2.0.

## Full read of Rules, Discussion, Leaderboard, Code (Sep 30)

Read by an agent on Sep 30. Its browser profile was logged out, so the paper-track Writeups tab and the data file
previews were not visible to it. Items marked ✓ were re-checked by Claude Code from the primary source (the Kaggle
CLI, or the notebook itself). Everything else is the agent's reading and gets checked before it goes in the paper.

### Rules that bind us (paper track)

- **Teams:**
  - "The maximum Team size is five (5)." "You may join or form only one Team."
  - The paper track does not require joining the main competition.
  - Both rulebooks forbid sharing code across teams "unless a Team merger occurs", so **the two team members are one team
    in any competition either of them enters.**
- **Submissions:** 5 per day and up to 2 final. The host (Sep 29): "A team can submit at most two write-ups. There
  is only one submission track, and the judges will determine the eligibility for each prize." One writeup can be
  considered for several prizes but wins at most one.
- **"Unpublished"** is not defined. The host says "Parallel submission to ArXiv is also allowed and encouraged".
- **Winner obligations:**
  - "WINNER LICENSE TYPE: Open Source Apache 2.0" for the code used to generate the submission.
  - Winners also deliver "training code, inference code, and a description of the required computational
    environment." **So keep the repo clean enough to open-source.**
- **Competition data:**
  - Participants must not "publish, redistribute or otherwise provide or make available the Competition Data to any
    party not participating in the Competition."
  - On publishing regenerated graphs, the host said "I believe that should be acceptable with citation and with
    linking to the Kaggle dataset... I will double check." Still unresolved.
- **External models and data:**
  - Allowed if publicly available at no cost, or if they pass a "Reasonableness" cost test.
  - Distilling from proprietary models is allowed within those models' license terms (Kaggle staff, Sep 29).
  - The host: "Training on gemma-4-31b itself is fine."
- **AI assistance:** not addressed. The rules only warrant that "your Submission is your own original work."
- **Eligibility:** 18+; not in a sanctioned country. Prize money is split evenly by default.

### Main competition facts that matter for experiments

- **Scoring machine:** 4x NVIDIA L4, vLLM, a 32,768-token context. All ~120 hidden tasks run sequentially in one
  pass, and exceeding 12 hours fails the whole submission.
- **Submissions:** 1 per day, 2 final. Entry and team-merger deadline Nov 25; final deadline Dec 2.
- **LoRA only.**
  - The whole submission must be under 3 GiB unpacked, with rank at most 128 and up to 8 adapters.
  - The model variant is marked not fine-tunable, so we would train on the unquantized base and check that the
    adapter actually changes outputs.
- **Known serving bugs** (host fixes are in progress):
  - LoRA adapters silently wiped in vLLM 0.19.1 (fixed in wheelhouse v23).
  - With LoRA on, the KV cache shrinks to about 7.6k tokens and longer requests hang.
  - Thinking-mode content dropped between tool calls.
  - Tool results double-JSON-encoded: escaping caused 39 of 62 failed edit_file calls in one team's logs.

  Old submissions are not rescored, so **record the harness version in the paper.**

### Harness and data

- **Tool limits:** 300 s per command; 5,000 characters of output; read_file capped at 150 lines or 10,000
  characters. The graph tools are always available, but their prompt description is only added when graph and
  embedding files exist.
- **Budgets:** eval_config.yaml sets timeout_seconds, max_tool_calls, max_time_minutes and max_turns. "The default is
  no limit." The official sample ships 10 tool calls and 1 minute per task.
- **✓ Context overflow discards the patch** (thread #744692, Sep 30, with local evidence on the official wheels):
  - At the scoring threshold of 32,768 tokens, compaction cannot fire before vLLM rejects the request.
  - The resulting error skips the fallback git-diff capture: "44 of 44 overflowed sessions had an empty patch, 14 of
    them after successful edits".
  - Overflow rate: "about 12% of sessions ... at a threshold of 14,336, and 17-33% at 32,768".
  - The scorer's actual threshold is unconfirmed.
- **Sandboxes:** two containers per task (the agent's, then a fresh one for the patch and hidden tests). Offline,
  4 GiB RAM, 2 vCPU.
- **Local evaluation:**
  - The organizers publish the harness as the Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` (v25 on
    Sep 30).
  - The official starter runs `Evaluator(EvalConfig(..., graph_dir=..., embeddings_dir=..., sandbox='subprocess'))`
    on a Kaggle 4xL4 session. **So Docker is not strictly required; the subprocess sandbox exists.**
  - The public setup is missing some test dependencies: in one team's setup the reference fix passed only 18 of 40
    tasks. The hidden test set is said to be filtered so reference fixes pass.
- **Graph quality** (participant audits, including GraphLoc):
  - Every edge is of type `calls`: no import or containment edges, no module nodes.
  - **Async functions are missing entirely.** The host: "I don't have an ETA".
  - One audit found 68.7% of FastAPI nodes isolated, and every edge paired with its reverse.
- **Embeddings:**
  - The embedding model is undisclosed.
  - `search_similar_code` "only accepts an existing node name" and returns that node's stored neighbors. No model
    embeds a text query.
  - The vectors are nearly collapsed: two random nodes average 0.78-0.90 cosine similarity.
  - Each hit returns full source with no size cap, and a single call can overflow the context.
- **Serving modified graphs:**
  - Locally this is easy: graph_dir and embeddings_dir are plain folders.
  - Caveat: task-named files are hard-linked to commit-named twins, and the zip download loses the links (one side
    becomes a zero-byte file).
  - In the scoring environment you cannot supply graph data; only a skill that rebuilds its own graph from source
    could change it.

### Current state (Sep 30)

- **Paper track:** 84 teams, 86 submissions.
- **Leaderboard:** 1,132 teams; the top score is 0.17 (about 10 of 58 public tasks).
  - Ranks 7-32 all score 0.13.
  - Re-running one agent reproduces the spread of the whole board, so **the leaderboard is mostly noise at this
    sample size.**
  - Local development scores (0.18-0.32) don't predict the leaderboard.
- **Compute used by participants:** free Kaggle 4xL4 sessions, often queued 8-13 hours; a scoring run takes 12-14.5
  hours.
- **✓ Direct overlap: "GraphLoc".** A paper-track writeup, *"Where Does the Graph Help? A Localization Audit of the
  Gemma 4 Developer Agent Code Graphs"*, by zzgtylors, with five public notebooks (Sep 25-27) under Apache-2.0.
  - Content (confirmed from the notebooks):
    - GraphLoc-129 function- and file-level gold labels
    - an audit of the graph's structure
    - embedding probes
    - BM25 vs tool-faithful simulations of the graph tools vs personalized PageRank on the provided graph and a
      repaired graph
    - transfer to SWE-bench Lite (300 tasks)
    - a `graph-localize` skill
    - end-to-end runs with a failure taxonomy and run-to-run variance
  - Headline numbers, as read by the agent from the rendered pages:
    - top-5 localization: BM25 0.467, embeddings 0.246, PageRank 0.434; no significant differences
    - end to end: base 28.9% vs graph skill 29.9%, +0.9 points, 95% CI −4.1 to +6.3
    - tasks resolve 57% of the time when the patch touches a gold function, 6% otherwise
  - No corrupted-graph experiment and no training, as far as the agent read.
- Other visible drafts: "Declarative Agents for Autonomous Software Engineering" (about 12%, loose numbers);
  "CORTEX-SWE" (theory only).

### Open questions worth asking the host

- Does the 3,000-word cap apply to the PDF route?
- May we publish a dataset of regenerated graphs?
- What `token_threshold` does the scorer use?
