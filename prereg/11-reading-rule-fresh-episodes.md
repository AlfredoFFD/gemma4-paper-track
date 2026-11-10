# Pre-registration 11: the reading rule, tested on our own fresh episodes

Status: FROZEN on Nov 10, 2026, 3:47 PM EST, by the commit that adds this file, while the fresh-episode run of
pre-registration 09 was in progress and before any row of that run was read. It adds a rule to that run and changes
nothing in pre-registrations 02 to 10. Tags: [Claude Code] wrote it on a proposal of a second session; [team] had not
read this text when it was frozen.

## Why

In other teams' public runs a first read of a file asks for lines past line 1 after 84% of results that named the
file with a line number and after under 1% of results that named only the file
(`analysis/results/public/address.txt`; exploratory, counted after the fact). The fresh episodes of pre-registration
09 are new runs of the starter agent on the newest harness wheels, made by us for another purpose. They give the
rule a test whose thresholds are fixed before the data is seen.

## What has been seen

- The public-run counts above and the first-read counts of the one-step replays
  (`analysis/results/explore_first_reads.txt`). The thresholds below come from the public counts.
- Of the full run of pre-registration 09: its progress, three times (125, 214 and 384 episodes done), from the run's
  log lines and from the number of lines of the results file. A partial copy of that file was downloaded twice to
  count its lines and was not opened. No row's content has been read by anyone.
- The smoke test of pre-registration 09 (18 episodes, not part of the full run): rows, errors, graph-tool calls
  executed, answers that received addresses, one sample answer, and the three mangled reads of the patched arm.

## Data and definitions

Rows: `results_09.jsonl` of the run of pre-registration 09 (106 tasks, arms N, NA and NAF, seeds 1 to 3, up to eight
calls per episode), episodes without an error. The definitions are those of `analysis/public_runs_address.py`
(md5 `c2293f0441a781e2c9b54a43652a786b`), whose functions the analysis imports:

- A read is an executed `read_file` call. It is a first read if no earlier executed `read_file` of the episode read
  that file and no earlier executed shell command named it with a viewer.
- The call just before is the executed call that precedes the read in the episode. The first call of an episode has
  none and is classed OTHER.
- ADDRESS, PATH ONLY, GRAPH NAME and OTHER as `classify` returns them from the call just before and its result.
- One class is added, for arms NA and NAF only, where graph answers carry lines: GRAPH ADDRESS, when the call just
  before is a graph tool whose answer lists the read's file with a line range. It is checked first.
- A read asks past line 1 if the start line the model wrote is greater than 1 (a mangled bound name is read as
  written).

The rows of this run keep the result of a `read_file` call without the file's text. A first read that follows
another read is therefore classed from that call alone and is OTHER. In the public traces a few such reads are
PATH ONLY or ADDRESS, because the text of the file just read names the next file. This is the one difference.

## Rules

Intervals: 95% bootstrap over tasks, 2,000 resamples (`analyze_forks.boot_ci` and `diff_ci`, as in the public-run
script).

**R1, shell output.** All three arms together; the class of a read depends only on the call just before. "The
reading rule holds in our fresh episodes" if all three are true: (a) at least 65% of first reads after an ADDRESS ask
past line 1; (b) at most 5% of first reads after a PATH ONLY do; (c) the difference has a lower bound above 50
points. It is tested only if each class has at least 30 first reads; otherwise the result is "too few reads to test"
and the counts are reported. Arm N alone (the harness as shipped) is reported beside it with the same three checks
and the same floor of 30; if the two disagree, both are stated and the claim is the weaker one.

**R2, the graph tools as shipped.** Arm N only. "A graph answer is read from the top" if at most 10% of first reads
classed GRAPH NAME ask past line 1. Tested only if there are at least 20 such reads.

No rule, reported: first reads after a GRAPH ADDRESS in arms NA and NAF (how many ask past line 1 and how many of
those cover the listed range); the registered rule for those answers is A1 of pre-registration 09. Also: every class
by arm, the ways of an ADDRESS, ranged reads that cover a named line, and first reads at the first call of an
episode.

## Stated limits

- Episodes have at most eight calls, so every first read here comes from the start of a run.
- The thresholds are looser than the public estimates (83.9% [77.1, 89.6] against 0.7% [0.0, 1.8]; starter agent
  alone 57 of 69 against 0 of 390): the harness wheels, the episode length and the tools that execute differ.
- The test confirms an association in new data. It is not an experiment: the agent runs a numbered search when it
  wants a line. The experiment is the replays.

## Analysis script

`analysis/analyze_11.py`, written after this freeze and before any row of the full run is read. It is tested on the
18 smoke-test episodes only. Its md5 is recorded here by a dated amendment before the run's rows are fetched for
analysis.

## What is reported regardless of outcome

Every count above, each rule with its verdict or "too few reads to test", and the arm-N-alone version of R1.

## Amendments

- Nov 10, 2026, 3:49 PM EST, before any row of the full run was fetched for analysis: the analysis script is
  written, md5 of `analysis/analyze_11.py` `9545a6db7ed9699412fcb3aebf46ae94`. The smoke-test rows of
  pre-registration 09 were not kept (that test wrote inside its container), so the script was tested instead on the
  tracked rows of the five-call run of pre-registration 06, which have the same format
  (`analyze_11.py analysis/results/k/forks --rows results_k.jsonl --arms A,H,E,RE`). Those replays start from paused
  runs, so their "first reads" are first only within the replay and the test says nothing about the rule; its
  output was seen (after an ADDRESS 597 of 620 ask past line 1, after a PATH ONLY 36 of 604). No threshold was
  changed.
- Nov 10, 2026, 4:10 PM EST, for the record: the run of pre-registration 09 ended at 4:07 PM; its rows were fetched
  then and analyzed in this order: `analyze_09.py` (the rules of pre-registrations 08 and 09), then `analyze_11.py`
  with the hash above. Stored outputs: `analysis/results/09/analyze_09.txt` and `analysis/results/09/analyze_11.txt`.
