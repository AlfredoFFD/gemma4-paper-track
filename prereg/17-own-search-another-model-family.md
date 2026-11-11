# Pre-registration 17: the agent's own search, with and without its line numbers, on a model of another family

Status: FROZEN on Nov 10, 2026, 10:17 PM EST, by the commit that adds this file, after the smoke test described below and before any replay of the full run.

It changes no rule of pre-registrations 02 to 16. Tags: [Claude Code] wrote it.

## What changes

Everything is as in pre-registration 15 (the 61 states and 183 records, arms S, S0 and S0N, seeds 1 to 3, 549
one-step replays, outcome, estimands, rules, intervals, completeness rule, frozen interface-failure rule, S and S0
first), except:

- **Model and serving**, as in the full run of pre-registration 10: `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ` (4-bit) on
  vLLM 0.19.1; tool-call parser `hermes`, no reasoning parser, no chat-template arguments, dtype `auto`; reasoning
  configuration with delimiters `<think>`, `</think>`; stop string `</tool_call>`; output limit 2,048 tokens; 16
  requests at a time; one A100-80GB, harness wheels v28. The runner is that of 10, unchanged (the runner of 15 with
  the server settings read from the environment).
- **Floor**: 25 complete states for each rule (40 in 15). In the full run of 10, 5.2% of replays were interface
  failures (222 without a call, 34 to an unknown tool, of 4,884). At that rate a state is complete for Q1 (six
  replays) with probability about 0.73 and for Q3 (nine) about 0.62: about 45 and 38 of 61.
- **Budget**: no new replay after 45 minutes of the runner's clock (50 in 15).

Analysis: `analysis/analyze_17.py <run dir>` sets the floor and calls `analyze_15`; on the rows of 15 it repeats
`analyze_15.txt`.

## What was known before

- Pre-registration 15 on Gemma-4-31B (`analysis/results/15/analyze_15.txt`): "Q1, Y1 under S minus Y1 under S0:
  +56.67 [+45.00, +69.44]", met; "Q2, under S0, reads of a hit file that ask past line 1: 9 of 108 (8.3%)", not met;
  "Q3, Y1 under S0N minus Y1 under S0: +45.56 [+34.44, +56.67]", met; C difference +2.46 [-5.68, +11.52], no
  detectable difference; R 0.80 [0.65, 0.99].
- Public runs of other families (EXPLORATORY, `analysis/results/public/outside.txt`), first reads asking for a range
  after a file with a line number against the file alone: Claude 3.7 Sonnet 66 of 75 against 6 of 923; Llama-based
  agents 42 of 47 against 50 of 883; Qwen3-Coder-480B 435 of 514 against 90 of 1,786; GPT-4o 100 of 120 against 1 of
  660.
- This model in the replays of 10 (EXPLORATORY, `analysis/results/explore_first_reads.txt`): first reads of a listed
  neighbor's file ask past line 1 in 64 of 85 with line numbers and 54 of 133 without (Gemma 4 without: 0 of 856, 2
  of 147, 0 of 183). If that carries over, Q2 will likely not be met. A guess.

## Rules (as in 15)

- **Q1.** Y1 under S minus Y1 under S0; met if the lower 95% bound is above 0.
- **Q2.** Under S0, at most 5% of reads of a hit file ask past line 1; at least 20 such reads.
- **Q3.** Y1 under S0N minus under S0, met if the lower bound is above 0; C under S0N minus under S, less, no
  difference or more; R at least two thirds: the note carries the number about as well.

## Gate

Smoke test: the first eight states by sha1, every arm, seed 1, 24 replays; at least 80% usable in every arm. What it
showed (Nov 10, 2026, 10:06 to 10:11 PM EST; one container, about five minutes, about a quarter of a dollar): usable
8 of 8 under S, S0 and S0N; no interface failure. Passed. Nothing else of those rows was read but prompt sizes; the
analysis ran on them with its report discarded.

## Stated limits

- The model continues the Gemma-4-31B agent's history, that agent's own search included, as in 10; only the next
  call is this model's.
- One model of one other family, 4-bit, one platform, one run; no counterpart to the thinking settings. An answer cut
  at 2,048 tokens before its first call counts as an interface failure.
- 61 states from 47 runs of 29 tasks in two repositories. The limits of 15 stand.

## File hashes (md5)

`analysis/modal_g/forks_17_modal.py` `dd7cda0977a5b4a270cbc70f7720adaa`, `analysis/analyze_17.py`
`b85f13aeb26af3c6101657b6f3c2d24e`. Unchanged: `analysis/modal_g/forks_10_runner.py`
`8b34d586f75214d1f6c7e0cd4762fb9a`, `analysis/fork_states_s/states.jsonl`
`a90d2df2d7b6fc12591fffe2f1622a2b` (not tracked; both volume copies match), `analysis/make_states_s.py`
`3b2e4a5efc17e508d6781bd27a0cd17e`, `analysis/analyze_15.py` `5dd2680966b40d7ed717c5387766ccf0`,
`analysis/replay.py` `446b85be41d90e0e8fdb7c32dd5ea2f1`, `analysis/fork_states.py`
`7fc2e4bb40f50b64638a1243e6a636ba`, `analysis/analyze_forks.py` `8b22556e948c0df33f80cbeef8c11300`,
`analysis/gates_c.py` `84f2af2d7d7f21813c930c6fd1d354ec`, `analysis/mangled_sensitivity.py`
`7f64709fa901e9b307525e7ffc6284fb`, `analysis/public_runs_address.py` `a86e30082d20caefc02fc9ec0fc3512a`.

## Amendments

(none)
