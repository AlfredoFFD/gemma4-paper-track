# Pre-registration 27: one line in the system prompt (can an instruction remove the place effect?)

Tags: [Claude Code] wrote it on the team's instruction. FROZEN on Nov 12, 2026, 3:15 PM EST, before any replay of 27
has run on any model. The result of 26 is known (`analysis/results/26/analyze_26.txt`); no row of 27 exists.

## Why

25 and 26 show that the same addressed list is followed more as a separate note than as the last key inside a file
view (registered on Gemma-4-31B and on 3 of 7 hosted models; the point estimate higher on all 8). Is that discount a
default the agent follows unless told otherwise, or a limit an instruction cannot lift? A builder controls the system
prompt; one added section is the cheapest possible fix.

## Design

- Everything as in 26 (records of 25, 322 steps, arms KH, KE, EL, seed 1, the seven hosted models, the runner
  `analysis/modal_g/forks_26_runner.py` unchanged, Nebius AI Studio, harness wheels of Oct 12, local machine), except
  the system prompt: `analysis/agents/line27/prompts/system.md` (md5 `4d9ff98de3d597032b78bedb81d6ed69`) is the
  prompt of 26 (`9917b5f1b3c37a76c55b0764e8c1c387`) with one section appended:

  > ## Leads in Tool Results
  > - A tool result may list related code as names with a file and line range (for example a `code_graph` key at the
  >   end of a file view). Treat these as leads: when one bears on the issue, read its lines with `read_file`.

- The comparison without the line is 26's stored rows (same records, arms, seed, models, harness; run about 90
  minutes earlier). Results under `analysis/results/27/<model>/forks/`.
- Analysis: `analysis/analyze_27.py` (scoring of 25 imported unchanged). A second script written from this
  registration alone, without reading `analyze_27.py` or any row of 27, recomputes L1 and L2.

## Rules, per model (95% bootstrap by step, 2,000 resamples, seed 0)

- **L1, the line inside the view:** KE with the line minus KE without it (26), on the steps whose KE replay is
  usable in both runs. "The line raises uptake inside the view" if the interval lies above zero; otherwise "not
  detected".
- **L2, the place with the line:** EL minus KE, both with the line, on the steps with all three arms usable in 27. "A
  gap remains with the line" if the interval lies above zero; otherwise "not detected".
- **Gate:** at least 80% of 27's replays usable in each arm, and at least 200 steps entering L1 and L2.
- If the two scripts disagree on a verdict, both are reported and that model counts as "not detected".

## The reading fixed now (across the models through the gate)

- "One line lifts uptake inside the view": L1 met on at least 5 models.
- "On some models": L1 met on 2 to 4.
- "Not shown": L1 met on 0 or 1.
- Fewer than 5 models through the gate: per-model verdicts only.
- Beside it, per model: L1 met and L2 not detected reads as "with the line, the place no longer detectably matters".

## What we expect

L1 met on 4 to 6 models; L2 still met on 1 or 2 of the three models where 26 met K2.

## Cost and time expected

966 calls a model, about 10 dollars and 20 minutes in all (26: 10.61 dollars).

## Not covered

One seed; the comparison is across two runs about 90 minutes apart (same seed, same harness; a provider-side change in
between cannot be excluded); the line names the `code_graph` key, as a builder who pushes that key would; it may also
raise reads of lines that do not bear on the issue (opening rates are printed by `analyze_25.py` on the rows of 27).

## Dated note after the run (Nov 12, 2026, 3:35 PM EST) [Claude Code]

- Run: about 3:17 to 3:28 PM EST, all seven models, 966 rows each, no runner error stopped a model; starts were
  staggered 20 seconds apart. The second script (`analysis/rederive_27.py`, md5 7312e662de8ca61c8c771ae56949ff7d) was
  committed at 15:19:56, before any outcome of 27 was read. The local folder path in two runner logs and in each
  versions.json was replaced by `<home>`.
- Gate passed on all seven. Both scripts agree on every estimate, interval and verdict.
- L1 met on 1 of 7 (Qwen3-235B, +2.17 [+0.31, +4.04]). Registered reading: "not shown". The forecast (4 to 6) was
  wrong.
- L2 ("a gap remains with the line") met on 5 of 7: Nemotron-3 Super +5.94, gpt-oss-120b +9.27, Qwen3-235B +8.39,
  Qwen3-30B +4.97, GLM-5.3-Flash +3.43; not detected on DeepSeek-V4.1-Flash (+1.55 [+0.00, +3.42]) and
  MiniMax-M3.1-Flash. No model reads "with the line, the place no longer detectably matters" except those two, where
  26 did not detect the place effect either.
