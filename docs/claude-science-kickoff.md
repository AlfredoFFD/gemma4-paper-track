# Kickoff message for Claude Science

Paste this as the first message of a new Claude Science chat, with this repo's folder granted.

---

New project: the **Gemma 4 Developer Agent Paper Track** on Kaggle (Google DeepMind), with my teammate.
The deadline is **Nov 12, 2026, 11:59 PM UTC**. This folder is a git repo (a
private GitHub repo).

**Read these in order before doing anything:**
1. `CLAUDE.md`: the bar we hold (judge-first, checked novelty, pre-registration, statistics) and who writes which file
2. `BRIEF.md`. Its Sep 30 update box recommends "finding vs remembering". Item 5 supersedes that recommendation;
   we haven't decided yet.
3. `private/origin-transcript.md`: how we got here (my messages and Claude Code's replies)
4. `docs/competition.md`: the full rules, harness facts, and the context-overflow bug
5. `NOTES.md`, the Sep 30 evening entries: two pre-registered Phase-0 checks by Claude Code, and why its pick changed
6. `docs/prior-art.md`, `docs/methods-we-bring.md`, `docs/how-we-work.md` and `LOG.md`

**Where we are:** another entrant (GraphLoc) already showed the provided code graph barely helps agents *find* bugs.
Two directions are open:
1. **"Finding vs remembering":** does the graph help a small-context agent *remember* inside the 32k-token scoring
   context? Symbol names would act as compact pointers, and the agent would re-fetch exact functions instead of
   re-reading files.
2. **"Why doesn't the graph help?":** separate four failures: never consulted, consulted but ignored, wrong or missing
   content, and the model can't read it.

Claude Code's pick moved from 1 to 2 on Sep 30 evening, on three pieces of evidence (details in NOTES.md):
- No harness tool returns a node's own text, so the graph can hold names and edges, not code.
- On the 129 tasks:
  - fetching the exact function instead of a 150-line window saves only about 2.6x
  - the graph holds 1 of the 56 async gold functions
- A quick adversarial pass found close work on memory under a 32k window, and a rival entry in this competition. All
  of it is unverified (task A).

Its reframed version of 2: audit the code graph as the agent's external memory, with four ways it fails (not consulted,
ignored, missing content, too costly to read). Measure offline where possible, and with planted decoys in agent runs.
The same checks found only 13 of 129 tasks where one graph hop from the issue's symbols reaches fix code the issue
doesn't name, so resolve rate can't be the decoy test's outcome.

**Your first tasks (no GPU or paid compute without asking me):**

- **0. Confirm file access first.**
  - List the folder and open, in full, BRIEF.md, docs/competition.md, private/origin-transcript.md, NOTES.md and
    data/HARNESS_README.md. Report their line counts, so we know you read files directly and not excerpts.
  - Check that you can read data/tasks.jsonl (129 lines) and one graph file.
  - Tell me about anything you can't open.
  - Data layout: graphs and embeddings are keyed by commit (`<repo>_<base_commit>.json` / `.npz`; 127 each). Match
    them to tasks through `repo` and `base_commit` in tasks.jsonl. The snapshots are 21 GB of .tgz files: don't copy
    them. If a heavy pass over the local data is slow for you, ask Claude Code to run it on the laptop.

- **A. Verify the prior-art pass; don't redo it.** Open each item yourself and confirm or correct what it does:
  - Memory under a hard context limit:
    - a harness-design study, arXiv 2609.20804 (overflow at 32k; a store-and-recall arm reportedly unused)
    - SWE-MeM, 2606.28434
    - Codebase-Memory, 2603.27277
    - Code Isn't Memory, 2606.22417
    - Does a Language Server Save Tokens?, 2608.13568
  - Reliance tests: Don't Blindly Trust It (2606.21409), Oracle Poisoning (2605.09822), CodeCompass (2602.20048),
    Deterministic Anchoring (2606.26979).
  - **2607.09691:** docs/prior-art.md cites it for run-to-run variance, but the new pass describes it as an
    oracle-localization study. Which is right?
  - **GraphLoc's end-to-end and failure-analysis notebooks:** does its failure taxonomy already split "never called
    the graph" from "called it but ignored it"?
  - **Rival entries in this competition:** G-HRR (github Tarekswd/g-hrr-gemma4), GraphSWE-Gemma (nazarcoder123) and
    codegraph-loc (Benadict-Git). What do they claim, and does any of them overlap either direction?
  - Give each direction a verdict (KILLED, WEAKENED or OPEN) and name the nearest works.

- **B. Re-derive Claude Code's Phase-0 numbers independently.**
  - Write your own code from the definitions in NOTES.md. Don't open `experiments/00-pointer-audit/` until you have
    your numbers.
  - Recompute K1-K3 and the decoy-bite share, and report every discrepancy.
  - From the harness source, resolve one conflict: data/HARNESS_README.md says scoring compacts at `token_threshold =
    14,336`, while docs/competition.md (thread #744692) says the scorer's threshold is 32,768.
  - Also check the tool behavior the audit assumed:
    - `search_similar_code` excludes the query node
    - graph tools have no output cap
    - `get_code_neighbors` returns names only
  - The source is in the Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse`. If you can't fetch it, ask
    Claude Code.

- **C. Design the harness pilot; don't run it.**
  - Scope: 8 to 10 tasks, mixing the 13 "decoy-bite" tasks (`experiments/00-pointer-audit/results/`) with tasks
    that have no bite.
  - Two arms: the sample agent, and a forced-consultation variant that must query the graph on the issue's symbols
    before it reads files.
  - Measure per task:
    - the graph-tool call rate
    - overflows and what filled the context when they happened
    - edit_file and patch failures, counted separately from model failures
    - time and cost
  - Give exact commands, expected runtime and memory, a cost estimate, and stop conditions. Record the wheelhouse
    version.

- **D. Recommend a direction** with the evidence, and draft `prereg/01-<name>.md` for it. My teammate and I decide.

**Rules:**
- Log every step in `LOG.md`: date and time, a `[Claude Science]` tag, and a "Why." line. Append at the bottom and
  keep the file's existing header format; the skill's "append above this line" marker isn't used here.
- Don't edit `NOTES.md` (it's Claude Code's). Claude Code doesn't edit `LOG.md`.
- Never commit `data/` or `private/`.
- Label anything that wasn't pre-registered EXPLORATORY.
- The `preregistered-experiment-protocol` skill fits this workflow.
