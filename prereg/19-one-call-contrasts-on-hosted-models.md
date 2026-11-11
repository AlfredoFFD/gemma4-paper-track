# Pre-registration 19: the two one-call contrasts on models of other publishers, through a hosted API

Status: FROZEN on Nov 11, 2026, 12:55 AM EST, by the commit that adds this file, before any replay of the full run it
governs was made. Before the freeze there was a smoke test on the API (12 replays per model and design); what was
seen of it is listed under "What has been seen". Tags: [Claude Code] wrote it; [team] had not read this text when
it was frozen.

File hashes at freezing (md5): `analysis/modal_g/forks_19_runner.py` `b0e0a0c1680f89bfd9343a041847933b`,
`analysis/modal_g/forks_19_modal.py` `3bbd60224348dc90ea040827495720b8`, `analysis/analyze_19.py`
`cb3ec6aa469f6f5f55e2711d4d2a9339`, `analysis/store_19.py` `6c8b9b1c8116a68f90aaca0745ccf20a`. Used unchanged:
`analysis/analyze_15.py` `5dd2680966b40d7ed717c5387766ccf0`, the states files of pre-registrations 10 and 15 (checked
by md5 at launch).

## Why

The paper's two causal one-call results rest on Gemma 4 models and one model of another publisher
(Qwen2.5-Coder-32B). Blind readers asked how far they generalize. A hosted inference API serves tool-calling models
of several other publishers, so the same recorded histories can be replayed on them without a GPU.

## Design

- **Design 10**, a name against an address: the 407 paused steps of pre-registration 10, arms H (a note with the
  bare names of the graph neighbors) and E (the same note with each neighbor's file, line range and definition
  line), 2 replays per step (seeds 1 and 2).
- **Design 17**, the agent's own search with and without its line numbers: the 61 paused steps of pre-registration
  15, arms S (the search result as recorded), S0 (line numbers stripped), S0N (stripped, handed back in a note), 3
  replays per step.
- Models, each replayed on the same recorded histories (the histories are Gemma-4-31B's): Qwen3-30B-A3B-Instruct,
  Qwen3-235B-A22B-Instruct, gpt-oss-120b, DeepSeek-V4.1-Flash, GLM-5.3-Flash, MiniMax-M3.1-Flash,
  Nemotron-3-Super-120B. The two Qwen3 models are a later generation of a publisher already covered; the other five
  come from publishers not yet covered. Gemma-3-27B was a candidate and cannot take the recorded history (the
  provider rejects it: roles must alternate); it is not run.
- The replay is that of pre-registrations 10 and 17 (same harness wheels, agent files, tool declarations, added
  messages, row format) with the model call sent to the API. What differs from the rented-GPU runs and cannot be
  controlled: the chat template and the tool-call parsing are the provider's; no reasoning parameter is sent, so
  models that reason by default do; no stop string is sent and the output limit is the agent's own; the quantization
  is what the API reports per model; seeds are sent but not guaranteed; prompts may be cached; three of the models
  list no supported sampling parameters, so the agent's temperature and top-p may be ignored for them. Each of these
  is recorded per call or per model.
- A guard stops a model's design when its token cost passes 6 dollars. Design 10 takes its steps in a fixed random
  order, so a run cut short is a random subset and keeps its verdict if the floor below is met. Design 17 takes its
  steps in the order of their hashed ids; a model whose design 17 is cut gets no verdict for it.

## Outcomes

As in pre-registrations 10 and 15, by their scorers: design 10, the next call reads a neighbor's code; design 17,
Y1, the next call reads a file named in the search result past line 1; and, of the next calls that read such a
file, the share that ask past line 1. A reply without a valid tool call is counted apart; an API failure is counted
apart from both.

## Rules, one verdict per model

Bootstrap by step, 2,000 resamples, seed 0, on the steps complete in the arms and seeds run.

- **V1.** Design 10: the share of replays whose next call reads a neighbor's code, E minus H. Met if the interval
  lies above zero. Needs at least 200 complete steps.
- **V2.** Design 17: Y1, S minus S0. Met if the interval lies above zero. Needs at least 25 complete steps.
- A model enters a rule only if at least 80% of its replays in that design hold a valid tool call. The script
  applies this gate itself; it prints the floor of complete steps beside each count, and a verdict it prints for a
  model below the floor is not read.
- No pooled test across models. The paper reports in how many models each rule is met, not met, or without a
  verdict, and gives the table.

Printed without a rule: under S0, how often a read of a hit file asks past line 1 (a line the model was not shown);
S0N against S; first-read counts in design 10; valid-call shares; reasoning lengths.

## What we expect, written before the full run

V2 met in every model that enters it. V1 met in most. How often a model asks past line 1 without having been shown a
line (design 17, arm S0) should differ by model: 8% for Gemma-4-31B, 58% for Qwen2.5-Coder-32B in the earlier runs.

## What has been seen

The smoke test: per model and design 12 replays (4 or 6 steps, one seed), of which the builder read the number of
valid tool calls, errors, token counts, cost and latency; while debugging the model that was dropped, the counts of
next-tool names per model in the design-17 smoke rows. No outcome of either design was computed on smoke rows. On
the stored Qwen2.5-Coder rows of 10 and 17 the analysis reproduces the registered numbers of those runs.

## Not covered

The histories were written by Gemma-4-31B; another model replays a step it did not produce (as in 10 and 17). One
provider. Two repositories. Models that reason before calling a tool are scored on the tool call alone.

## Notes added after the freeze

- Nov 11, 2026, 1:15 AM EST, after the run: all seven models ran both designs to the end and no guard stopped a design
  (1,628 replays of design 10 and 549 of design 17 per model; no API failure). The first line of the analysis output
  reads "BUILD, not registered": the script was written before the freeze and was not changed after it (hash above).
