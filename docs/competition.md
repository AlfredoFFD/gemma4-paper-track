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

## Full read of Rules, Discussion, Leaderboard, Code, Writeups

Pending (agent reading the pages on Sep 30).
