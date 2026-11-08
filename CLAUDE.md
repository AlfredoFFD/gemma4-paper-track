# Instructions for AI assistants on this project (Claude Code, Claude Science)

## What this is

A research entry for Google DeepMind's **Gemma 4 Developer Agent Paper Track** on Kaggle.
- **Deadline:** Nov 12, 2026, 11:59 PM UTC.
- **Goal:** Overall Best Paper, in a writeup of at most 3,000 words.
- **Team:** two people. The humans decide the direction and own the paper.

## Read first, in order

BRIEF.md → docs/competition.md → docs/prior-art.md → docs/ideas.md → docs/methods-we-bring.md →
docs/how-we-work.md → LOG.md → NOTES.md. The dataset (about 20 GB) is in `data/`.

## The bar: think like the judges

- **Judge-first.** Every proposal states which of the five criteria it raises and how:
  - novelty
  - quality (how well it generalizes)
  - relevance to software engineering and agentic learning
  - verifiability
  - clarity

  The organizers are graph-ML researchers (their own work includes *Talk like a Graph* and *KG-LLM-Bench*). They
  built the code graphs, the embeddings and the graph tools, and they encourage papers that use them.
- **Novelty is checked, not assumed.**
  - Before calling anything new, run an adversarial prior-art search against the exact claim, in the field the claim
    belongs to.
  - Name the nearest work and what it does not cover.
  - GraphLoc (same competition, same data) is the baseline every judge will compare us against.
- **Pick a side and recommend.** Label guesses as guesses, and give honest odds.
- **Pre-register before any run we will report.** Fix the decision rule first, and label anything else EXPLORATORY.
- **Statistics:**
  - Reproduce the baseline before any intervention.
  - Use paired seeds and McNemar tests.
  - With about 106 tasks x 3 runs, effects under about 5 points are not detectable, so design for bigger effects or
    more power.
- **Count interface failures separately from model failures:** edit mismatches, context overflow, malformed patches.
- **Re-derive every headline number** from the raw per-trial logs with an independent script before it enters the
  paper.

## Division of labor

- **Claude Science:** literature, experimental design, reviewer passes, cloud compute for model runs. It writes
  `LOG.md`.
- **Claude Code:**
  - the repo, the local dataset, local scripts, git and GitHub, the Kaggle CLI (`.venv/Scripts/kaggle.exe`)
  - checking Claude Science's claims against the data
  - drafting prompts for Claude Science when a handoff is needed

  It writes `NOTES.md`.
- The two agents never edit the same file, and each reads the other's log before acting.

## Rules

- **No names and nothing private in tracked files.** No one's name, the team's included; the byline goes only on
  the Kaggle submission. No emails, schedules, exams, travel, local paths, or details of other projects. Never
  attribute ideas, quotes or framings to a person. Log tags are `[team]`, `[Claude Science]` and `[Claude Code]`.
- **Never commit** `data/`, `private/`, `CLAUDE.local.md`, tokens or `.env`. Never print a token.
- **Keep the repo open-sourceable:** winners must release code under Apache 2.0, with training and inference code.
- **Competition data** must not be redistributed outside participants.
- **LOG.md is append-only:** dated entries, each with a "Why." line.
- **Record the harness (wheelhouse) version for every run.** The harness changes mid-competition, and old
  submissions are not rescored.
