# Pre-registration 10: the second-model design on a model of another family

Status: FROZEN on Nov 10, 2026, 2:35 PM EST, by the commit that adds this file, before the model was fetched and
before any replay with it ran on any platform. It adds to pre-registrations 02 to 09 and changes none of their rules.
Tags: [Claude Code] wrote it on a proposal of a second session; [team] gave the go for the run and had not read this
text when it was frozen.

File hashes at freezing (md5): `analysis/modal_g/forks_10_runner.py` `5716f4c2819f4f42218278747d0e4750`,
`analysis/modal_g/forks_10_modal.py` `3b0279a5a848497de8c06dcf59d61b43`. Used unchanged: `analysis/analyze_d.py`
`844147a5ab612ee286c861a182d17d0b`, `analysis/rederive_cd.py` `2eaf4603028479bc3f09228ab275973b`,
`analysis/replay.py` `446b85be41d90e0e8fdb7c32dd5ea2f1`, `analysis/fork_states_d/states.jsonl`
`d3105df0dc4aa43d7bb0afbdd6123b44`. The runner is a copy of `analysis/modal_w/forks_w_runner.py`
(`65372125c2e23b48f5ee0e829a5e4167`) whose only change is that the model server's parser settings are read from the
environment. Code changes that the platform forces after this freeze are recorded at the end of this file as dated
amendments with the new hashes; the outcome definition and the rule cannot change.

## Why

Every causal result of this project is on Gemma 4 (31B, 26B-A4B, E4B). Blind readers of the draft cap its generality
there. Public runs of other model families show the same reading pattern, but only observationally (a second
session's exploratory counts, not yet re-derived in this repository). This run asks whether the registered one-step
contrast repeats on a model that is not a Gemma.

## Design

Exactly the second-model design of pre-registration 05 (D2), with another model:

- Model: `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ` (the publisher's 4-bit AWQ weights, Apache-2.0), fetched from Hugging
  Face into the run's volume. Served by the same server version (vLLM 0.19.1) with the tool-call parser `hermes`, no
  reasoning parser and no chat-template arguments; weight dtype `auto`. Everything else as for 26B-A4B and E4B: one
  rented A100-80GB, tensor-parallel size 1, the harness wheels of Sep 30 (v28), the starter agent's prompt, tools and
  configuration, the model reached under the agent's configured model name.
- States: the 407 states of `analysis/fork_states_d/states.jsonl`, that is, histories of the Gemma-4-31B agent,
  which this model continues.
- Arms A (no list), H (bare names, note), E (name, file, lines, definition line, note), RE (rewired list in E's
  format); seeds 1 to 3; one model call per replay; no tool executes. 4,884 replays.

## Gate before the full run

A smoke test on 8 states. The full run starts only if, in every arm, at least 80% of the smoke replays return a call
that the frozen interface-failure rule accepts (a call, to a known tool, with well-formed arguments). If the
tool-call format cannot be made to work through the harness within one hour, the experiment is dropped and reported
as not run. The smoke test prints counts of rows, errors and calls per arm; its outcomes are not read.

## Rule

Analysis: the frozen `analysis/analyze_d.py d2 <run_dir>` (it prints the contrast under the name M1, the name of
pre-registration 05's rule) and, independently, `analysis/rederive_cd.py d2 <run_dir>`.

**M2.** E minus H on any unopened true neighbor touched (the outcome of pre-registrations 02 to 05). "The encoding
effect replicates on a model of another family" if the lower 95% bound is above 0; otherwise "not detected on this
model". As in pre-registration 05: it applies if at least 200 states are complete (every arm and seeds 1 to 3
usable), and an arm with more than 20% interface failures is flagged as unreliable. 95% bootstrap intervals clustered
by state, 2,000 resamples; the interval clustered by task is reported beside it.

Descriptive, no rule: H minus A, E minus A, the rewired entries under RE and under A; of the next calls that are a
first read of a listed neighbor's file, how many ask for lines past line 1 in the arms without and with line numbers
(the count of `analysis/explore_first_reads.py`, extended by this run); interface failures by arm and kind.

## Stated limits

- The model continues another model's histories, in a harness built for Gemma 4. A failure here may be a failure of
  that fit and not of the effect.
- The agent's thinking settings have no counterpart in this model's server configuration; the model answers without
  a reasoning channel.
- 4-bit AWQ weights; one run; one model of one other family. The prompt-size passes of the runner compare token
  counts of different tokenizers and are not gates here.

## Power, stated as assumptions

The effect on the two smaller Gemma 4 models was 3.5 and 3.1 points with a half-width of about 2. With a similar
spread a true effect of 3 points or more is detected; a smaller one will usually read as "not detected".

## What is reported regardless of outcome

The rule with its interval, met or not; every arm's rates; interface failures by arm; the raw per-replay records;
the versions and server settings recorded by the run; and, if the gate fails, that the experiment was not run and
why.

## Amendments

- Nov 10, 2026, 2:36 PM EST, while the model was being fetched and before any replay: the wrapper's smoke test now
  writes its rows to the volume (`/vol/smoke_10`), so that the gate can be computed with the frozen
  interface-failure rule on the laptop; the frozen rule is not available inside the container. Nothing else changed.
  New md5 of `analysis/modal_g/forks_10_modal.py`: `955b7f0856b8e1511389e128a9f82d67`.
- Nov 10, 2026, 2:46 PM EST (the commit of this amendment is stamped 2:45:58 PM; its first version said 2:47 PM,
  ahead of the clock), after the first smoke test (started 2:38 PM) and before any replay returned a model answer: the model server refused all 96 smoke requests. The agent's configuration sends a thinking-token budget with
  every request, and the server accepts that field only if it was started with a reasoning configuration; for Gemma 4
  the harness supplies one by default, for another model it does not. Gate on this smoke test: 0 of 24 usable in every
  arm (failure kind: error); no model output exists. Change: the runner reads a reasoning configuration from the
  environment (`REASONING_CONFIG`) and the wrapper passes
  `{"reasoning_start_str": "<think>", "reasoning_end_str": "</think>"}`, delimiters this model is not trained to
  write. No reasoning parser is set, so nothing is removed from the model's answer, and the budget acts only on text
  between those delimiters. The requests, the agent's configuration, the prompt, the arms, the outcome and the rule
  are unchanged. Recorded from the server's log, not a change: for sampling parameters the agent does not send, the
  server uses the defaults of the model's own generation configuration (repetition penalty 1.05, top-k 20);
  temperature 0.2 and top-p 0.95 come from the agent's configuration, as in every other run. New md5:
  `analysis/modal_g/forks_10_runner.py` `dbcedd51640c45b869356c1d2f5450d8`, `analysis/modal_g/forks_10_modal.py`
  `85fab02719044af02c5219c99e421b42`. The one-hour limit of the gate counts from 2:38 PM.
- Nov 10, 2026, 3:10 PM EST, after the second smoke test was stopped by hand at 3:09 PM and before the third: with
  the reasoning configuration the server accepted the requests. 37 of the 96 smoke replays had returned when the
  test was stopped: all 37 with a call and no error (A 10, H 10, E 9, RE 8), median answer 156 tokens. The other
  requests were still generating after minutes. One returned answer showed why: 144 calls in a single answer, 7,590
  tokens, 215 seconds; 16 of the 37 answers held more than one call. This model can put many calls in one answer,
  up to the agent's limit of 16,384 output tokens, which the Gemma 4 models did not do; at that pace the full run
  would cost several times its budget. Only counts were read from these rows (errors, calls per answer, tokens,
  seconds); no call's content and no outcome. Change: the request carries a stop string, the closing tag of a call
  (`</tool_call>`), so the server ends the answer when its first call is complete. The registered outcome reads the
  first call of an answer and nothing after it, so the scored call is the one the model would have written first in
  any case; what is lost is the rest of the answer, which is not analyzed. The runner reads the stop strings from
  the environment (`STOP_SEQUENCES`; unset, nothing changes) and the wrapper passes `["</tool_call>"]`. The gate is
  applied to a third smoke test with this configuration. New md5: `analysis/modal_g/forks_10_runner.py`
  `ec3ffed6f6b56fa1c9f38b1a4ae8ad7e`, `analysis/modal_g/forks_10_modal.py` `c4e48c88cdd2fa070afc01e9549f9a1b`.
- Nov 10, 2026, 3:19 PM EST, after the third smoke test was stopped by hand at 3:18 PM and before the fourth: with
  the stop string set, four of the first six requests returned at once and two were still generating after more
  than three minutes, so some answers of this model do not end and contain no closing tag of a call. Nothing was read from
  that test but the server's load lines; it wrote no rows. A local check without a model confirmed that the stop
  string reaches the request. Change: the output limit for this model is 2,048 tokens instead of the agent's 16,384
  (13 times the median answer of the second smoke test, 156 tokens; the longest answer there that ended on its own
  with one call had 1,145). The runner reads the limit from the environment (`MAX_OUTPUT_TOKENS`; unset, nothing
  changes). An answer cut by the limit before its first call is complete has no call and counts as an interface
  failure under the frozen rule, apart from the outcome; if that pushes any arm under 80% usable in the fourth smoke
  test, the gate fails and the experiment is dropped. The smoke test skips the prompt-size pass, which is not a gate
  here. This is the last change: the one-hour limit runs out at 3:38 PM. New md5:
  `analysis/modal_g/forks_10_runner.py` `8b34d586f75214d1f6c7e0cd4762fb9a`, `analysis/modal_g/forks_10_modal.py`
  `1f1e617b613b858b8ca7a39ae6065ded`.
- Nov 10, 2026, 3:30 PM EST, the gate: the fourth smoke test ended at 3:29 PM with 96 replays and no error. Usable
  by the frozen interface-failure rule (`analysis/gates_c.py`): A 21 of 24 (88%), H 20 of 24 (83%), E 21 of 24
  (88%), RE 21 of 24 (88%); every failure is an answer without a call. Every arm is at or above 80%: the gate is
  passed, 51 minutes after the first smoke test started. Recorded with it, from counts only (no call's content and
  no outcome was read): 31 of the 96 answers reached the 2,048-token limit; the median answer had 436 tokens; 47
  answers held more than one call, up to 64, so the stop string did not end answers at the first call and the
  output limit is what bounds an answer (the stop string stays in the request; why it has no effect was not
  examined); in one of the eight states no answer held a call, and in six every answer did. The scored call is the
  first call of an answer, as registered. Expect about 13% interface failures and about three states in four
  complete in the full run. For the full run, two settings that do not change what the model is asked: 16 requests
  at a time (8 in the other runs), and no new replay after 3.25 hours, which holds the run near its budget; the
  runner takes states in a fixed shuffled order, so a run cut by the budget is a random subset of states, and the
  rule's threshold of 200 complete states decides whether it applies. New md5 of
  `analysis/modal_g/forks_10_modal.py`: `de186530152038b7ae0258b81ab28313`; the runner is unchanged
  (`8b34d586f75214d1f6c7e0cd4762fb9a`).
