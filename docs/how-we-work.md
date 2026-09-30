# How we work

## Repository

- Private GitHub repo with both of us as collaborators. It becomes public only when we both agree
  (before submission, if we attach a public notebook or code).
- `main` stays runnable. Work on a branch per idea or experiment (`q1-offline-map`, `q2-counterfactual-arms`,
  `q3-lora`, ...) and merge through pull requests. Small commits with clear messages.
- **Never commit data, model weights, adapters, or secrets.** `data/` is gitignored except its README. Keys go in
  `.env` (gitignored).

## Brainstorming and tasks

- Ideas, questions and tasks live in **GitHub Issues** (labels: `idea`, `experiment`, `infra`, `paper`, `question`).
  Anyone opens one; the discussion stays in the issue so we both see it.
- Decisions that change the plan go into BRIEF.md (via a pull request) and into LOG.md.

## Pre-registration

- Before any run whose result we will report, write `prereg/NN-name.md`: the question, arms, outcomes, sample,
  analysis, and the decision rule. Commit it **before** the data exists.
- Changes after that are dated amendments at the bottom of the same file, never silent edits.
- Anything not pre-registered is labelled EXPLORATORY in the results and the paper.

## Logs

- `LOG.md` is the research log. Claude Science writes it during its sessions; we append by pull request.
  - Every entry has a date, an author tag (`[team]`, `[Claude Science]`, `[Claude Code]`), and a "Why." line.
  - It is append-only: correct old entries with a new dated entry, not an edit.
- `NOTES.md` is Claude Code's, kept separate so two agents never edit one file at once.

## Experiments

- One folder per experiment in `experiments/`: code, configs, a README with how to run it, and results
  (small files only; large outputs go to `data/` or cloud storage, recorded by path and sha256).
- A second agent independently re-derives every headline number from the raw per-trial logs before it enters the
  paper.

## Tools

- **Claude Science:** execution on cloud compute, literature work, reviewer passes. It gets this folder, nothing
  else.
- **Claude Code:** repo setup, local tooling, review, re-derivation.
- Colab Pro+ for jobs that need no Docker: offline analysis, LoRA training.
- Anything produced elsewhere (our own tools, notebooks) comes back into this repo with a log entry.

## Kaggle

- Both of us join the paper track and the main competition, then form a team as the rules allow (see
  docs/competition.md for team rules).
- The paper is a Kaggle Writeup (3,000 words maximum). Draft it in `paper/` first, then paste it in.
