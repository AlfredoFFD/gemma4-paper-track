# Pre-registration 26: the place of the list on seven hosted models (registration 25, replicated across model families)

Tags: [Claude Code] wrote it on the team's instruction to test, before the deadline, whether the registered place
result of 25 holds beyond Gemma-4-31B. FROZEN on Nov 12, 2026, 1:38 PM EST, before any replay of 26 has run on any
model. The status of 25 is known (its result is in `analysis/results/25/analyze_25.txt`); no row of 26 exists.

Inputs, by md5 (all as in 25): the records `analysis/fork_states_p/states.jsonl` `0422a706a3a4b57083ce6d61e2cd0cb3`
(not tracked; rebuilt by `analysis/make_states_25.py`), their manifest `analysis/fork_states_p/manifest.json`, the
paused steps `analysis/fork_states_d/states.jsonl` `d3105df0dc4aa43d7bb0afbdd6123b44`, `analysis/replay.py`
`446b85be41d90e0e8fdb7c32dd5ea2f1`, the agent files of the hosted runs of 19 and 24 (`agent.yaml`
`a19562f75e18e5c713310373cb4792a2`, `sampling.yaml` `4f06cb0c4b126ac9d12665ccf80f7df0`, `system.md`
`9917b5f1b3c37a76c55b0764e8c1c387`), the registered analysis of 25 `analysis/analyze_25.py`
`6b0b6c37336f9d588b6e8b3a2e922b27` and its blind second script `analysis/rederive_25.py`
`e1b92a253f606f359bc58021df67d86d`. Both scripts run unchanged.

## Why

25 found, on Gemma-4-31B and one seed, that the same addressed list is followed in 6.65% of steps as a note after a
file view and in 1.90% as the last key inside the view (K2 +4.75 [2.53, 7.28], "the place matters"). Whether that is a
property of Gemma or of how agents read tool results is the question a builder of tools needs answered. The hosted
models of 19 and 24 continue the same paused steps through the same harness with one changed message.

## Design

- **Models:** the seven hosted models of 19 and 24, all of them, chosen before this registration and none added or
  dropped after: `deepseek-ai/DeepSeek-V4.1-Flash-1017`, `MiniMaxAI/MiniMax-M3.1-Flash`,
  `nvidia/nemotron-3-super-120b-a12b`, `openai/gpt-oss-120b`, `Qwen/Qwen3-235B-A22B-Instruct-2507`,
  `Qwen/Qwen3-30B-A3B-Instruct-2507`, `zai-org/GLM-5.3-Flash`, through Nebius AI Studio's OpenAI-compatible API.
- **Steps, arms, outcome:** those of 25 unchanged: every record of the states file (322 steps, arms KH, KE, EL), one
  seed (seed 1), as 25's run had. KH and KE are replayed as they stand (runner arm A), EL with its note (runner arm
  EL); a row's fork is "<03's fork>:<record arm>:<seed>", as in 25's rows.
- **Runner:** `analysis/modal_g/forks_26_runner.py`, the hosted runner of 19 (`forks_19_runner.py`) with one design
  added (25's records, the mapping above); everything else as in 19: harness wheels of Oct 12 (`latest`), no
  reasoning parameter sent, the provider's default sampling apart from the agent's, retries recorded, a spending
  stop of 5 dollars per model. It runs on a local machine, not on Modal.
- **Analysis:** per model, `py -I -X utf8 analysis/analyze_25.py <run_dir>` and
  `py -I -X utf8 analysis/rederive_25.py --rows <run_dir>/results.jsonl --no-write`, unchanged; results under
  `analysis/results/26/<model>/forks/`. A cross-model table is printed by `analysis/analyze_26.py`, which only collects
  the two scripts' printed lines.

## Gate and rules, per model

- **Gate:** 25's part (a) only: at least 80% of the replays attempted in each arm hold a usable tool call, and at
  least 200 steps have a complete cell. 25's part (b) (EL's rate within Gemma's stored interval) is a check that
  Gemma reproduces its own earlier rate and has no counterpart for another model; `analyze_25.py` will print it as
  FAIL and label its lines exploratory. For 26 the rule is read from the intervals that script prints for K1 and K2
  when part (a) passes; part (b) is ignored.
- **K2, the place (the rule of 26):** EL minus KE, 95% bootstrap interval by step as `analyze_25.py` prints it. "The
  place matters on this model" if the interval lies above zero; otherwise "not detected".
- **K1, the address inside the view (reported per model, read as in 25):** KE minus KH; "the effect holds in the
  push's place" if the interval lies above zero; otherwise "not detected".
- If the two scripts disagree on a verdict for a model, both are reported and that model counts as "not detected".

## The reading fixed now (across the models through the gate)

- "The place effect generalizes": K2 met on at least 5 of the models through the gate, and at least 5 models pass it.
- "It holds on some models": K2 met on 2 to 4.
- "It is not shown beyond Gemma": K2 met on 0 or 1.
- Fewer than 5 models through the gate: no cross-model reading; per-model verdicts only.

## What we expect

Instructions are followed less inside a tool result than in a user message in most models tested [the papers cited
beside the place result in Section 9 of the writeup]; 24 found these models act on a noted line at 17.6% to 76.7% of
replays. Forecast: K2 met on 5 or 6 of 7; K1 met on 1 or 2.

## Cost and time expected

About 966 calls a model (322 steps x 3 arms); in 24, 555 calls cost 0.76 to 1.48 dollars and took 3 to 4 minutes
at concurrency 8. Expected: under 3 dollars and under 15 minutes a model, all seven within about 30 minutes run side
by side.

## Not covered

One seed; the same Gemma histories continued by other models (replications at the same steps, not independent
agents); whole runs with a note remain untested; the note differs from the key in wording and message role as well
as place (as in 25).

## Dated note after the run (Nov 12, 2026, 2:05 PM EST) [Claude Code]

- Run: about 1:40 to 2:00 PM EST on a local machine, harness wheels of Oct 12, Python 3.12.13, the seven models side
  by side. Five runners stopped at the wheel install before any replay (parallel installs into one environment
  collided); they were started again with their starts 25 seconds apart. No row was lost or repeated: every model has
  966 rows. The local folder path in warnings of three runner logs and in each versions.json was replaced by
  `<home>`. Cost: 10.61 dollars in all (0.72 to 2.50 a model).
- Gate (a) passed on all seven (313 to 322 steps with a complete cell). As registered, gate (b) is ignored and
  `analyze_25.py` labels its lines exploratory; the rule is read from the intervals it prints.
- K2 met ("the place matters") on 3 of 7: nvidia/nemotron-3-super-120b-a12b +5.03 [+2.83, +7.55],
  openai/gpt-oss-120b +7.99 [+4.79, +11.50], Qwen/Qwen3-235B-A22B-Instruct-2507 +9.38 [+5.94, +12.81]; not detected
  on the other four (point estimates +0.93 to +2.81; GLM-5.3-Flash's lower bound prints +0.00). The second script
  agrees on every interval. Registered reading: "it holds on some models". The forecast (5 or 6 of 7) was wrong.
- K1 met on 3 of 7 (DeepSeek-V4.1-Flash, Qwen3-30B, GLM-5.3-Flash), the three of the four without K2 met but
  MiniMax-M3.1-Flash. Printed without a rule (exploratory): EL minus KH, an addressed note against bare names inside
  the view, has an interval above zero on 6 of 7 (MiniMax's lower bound prints +0.00).
- Stored: `analysis/results/26/<model>/forks/` (results.jsonl, summary.json, versions.json, runner.log),
  `analysis/results/26/analyze_26.txt`; a reproduce job.
