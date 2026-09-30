# Kickoff message for Claude Science

Paste this as the first message of a new Claude Science chat, with this folder granted:
`<repo>`.

---

New project: the **Gemma 4 Developer Agent Paper Track** on Kaggle (Google DeepMind), with my teammate.
The deadline is **Nov 12, 2026, 11:59 PM UTC**. The folder `<repo>` is a git repo (private
GitHub: AlfredoFFD/gemma4-paper-track).

**Read these in order before doing anything:**
1. `BRIEF.md`, including the Sep 30 update at the top
2. `private/origin-transcript.md`: how we got here (my messages and Claude Code's replies)
3. `docs/competition.md`: the full rules, harness facts, and the context-overflow bug
4. `docs/prior-art.md`: GraphLoc and the other nearest work
5. `docs/methods-we-bring.md`, `docs/how-we-work.md` and `LOG.md`

**Where we are:** another entrant (GraphLoc) already showed the provided code graph barely helps agents *find* bugs.
Two directions are open:
1. **"Finding vs remembering"** (Claude Code's pick): does the graph help a small-context agent *remember*, using
   symbol names as compact pointers and re-fetching exact functions instead of re-reading files? The setting is the
   32k-token scoring context, where overflows discard 12-33% of patches.
2. **"Why doesn't the graph help?"**: separate never consulted / consulted but ignored / wrong or missing content /
   the model can't read it.

**Your first tasks (no GPU or paid compute without asking me):**

- **A. Adversarial prior-art check, direction 1 first.**
  - Search for work on working memory or context management for coding agents under hard context limits:
    MemGPT-style memory, context folding and compaction, agent notes files, *Context Language Models* (arXiv
    2609.37725), and SWE-agent-style context management.
  - Search especially for any work that uses code graphs or symbol pointers as memory.
  - Then direction 2: corrupted-graph reliance tests, and fine-tuning for structural reliance.
  - Give each a verdict of KILLED, WEAKENED or OPEN, naming the nearest works.
  - Re-verify the citations in `docs/prior-art.md` from the papers themselves.
- **B. Phase-0 numbers without the agent harness.** Use `data/` (the Kaggle dataset, 20.4 GB, finishing today) and
  GraphLoc's public notebooks. Report:
  - how big the files and functions an agent reads are, compared with the 32k budget
  - how much of a task's context could go to re-reading code
  - what `HARNESS_README.md` says about compaction, budgets and the size of graph-tool outputs
- **C. Recommend a direction** with the evidence, and draft `prereg/01-<name>.md` for it. My teammate and I decide.

**Rules:**
- Log every step in `LOG.md`: date, a `[Claude Science]` tag, and a "Why." line.
- Don't edit `NOTES.md` (it's Claude Code's).
- Never commit `data/` or `private/`.
- Label anything that wasn't pre-registered EXPLORATORY.
- The `preregistered-experiment-protocol` skill fits this workflow.
