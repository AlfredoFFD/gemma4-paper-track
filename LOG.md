# Research log

Append-only. Each entry: date and time (ET), author tag, what happened, and a "Why." line. Correct an old entry
with a new dated entry, never by editing it.

<!-- append new entries at the bottom -->

### 2026-09-30 ~15:00 ET [Claude Code] Project created

- Repo set up for the Gemma 4 Developer Agent Paper Track. Team of two.
- Starting point: the Sep 27 adversarial prior-art sweep. Of three candidate ideas, "does the agent read its code
  graph" survived best. The team's framing (Sep 29) is the code graph as externalized memory. The merged design is
  diagnose (Q1), measure (Q2), fix (Q3); see BRIEF.md.
- Nothing has been run. No data downloaded yet: it needs both of us to join the competition, plus a Kaggle API
  token.

**Why.** The deadline is Nov 12 (43 days away). A shared repo with the brief, prior art and
logging rules lets Claude Science start the literature map and pilot this week.

### 2026-09-30 ~17:00 ET [Claude Code] Kaggle read, data access, and a direct overlap

- Read the full Kaggle pages (details in docs/competition.md). Rules that bind us:
  - teams of up to 5, one team only, so the two team members must be one team
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
