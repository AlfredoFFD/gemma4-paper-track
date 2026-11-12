# Pre-registration 28: the key first (is the place effect about position inside the result, or the channel?)

Tags: [Claude Code] wrote it on the team's instruction. FROZEN on Nov 12, 2026, 3:53 PM EST, before any replay of 28
has run on any model. The results of 25, 26 and 27 are known; no row of 28 exists.

## Why

In 25 to 27 the addressed list is followed more as a separate note after a file view (EL) than as the last key of the
view's result (KE). The two differ in channel (a message of its own against part of the tool's output) and in
position (the key comes after up to 150 lines of file content; the note is the last thing in the context). Instructions
are known to be followed more when they come first within a message (the papers cited for the place result in Section
9 of the writeup). If moving the key to the front of the result recovers the note's uptake, the fix for a tool builder is
to put the list first; if not, the channel itself matters.

## Design

- Everything as in 26 (322 steps of 25, seed 1, the seven hosted models of 26, Nebius AI Studio, harness wheels of
  Oct 12, the system prompt of 26 `9917b5f1b3c37a76c55b0764e8c1c387`, local machine) with one new record arm:
- **KF:** record KE with the key `code_graph` moved from the last place of the file view's result to the first, before
  `status` and the file's content; the value byte for byte KE's (`analysis/make_states_28.py`, which asserts it; records
  `analysis/fork_states_p/states_28.jsonl`, md5 `f048214e5cfc9ca7c0c870822ae44fe8`, not tracked, rebuilt by the
  script). Runner `analysis/modal_g/forks_28_runner.py`: the runner of 26 with record arm KF (runner arm A) added.
- KE and EL come from 26's stored rows (same records, seed, models, harness; run about two hours earlier).
  Results of 28 under `analysis/results/28/<model>/forks/`.
- Analysis: `analysis/analyze_28.py` (scoring of 25 imported unchanged). A second script written from this
  registration alone, without reading `analyze_28.py` or any row of 28, recomputes P1 and P2.

## Rules, per model (95% bootstrap by step, 2,000 resamples, seed 0)

- **P1, the first place:** KF minus KE, on the steps whose KF and KE replays are both usable. "The first place raises
  uptake" if the interval lies above zero; otherwise "not detected".
- **P2, the channel:** EL minus KF, on the steps whose EL and KF replays are both usable. "The note still beats the
  first place" if the interval lies above zero; otherwise "not detected".
- **Gate:** at least 80% of 28's replays usable, and at least 200 steps entering each rule.
- If the two scripts disagree on a verdict, both are reported and that model counts as "not detected".

## The reading fixed now (n1, n2 = models through the gate with P1, P2 met)

- n1 >= 4 and n2 <= 1: "the first place recovers the note".
- n1 >= 4 and n2 >= 2: "the place within the result matters, and the separate note adds more".
- n1 <= 1: "not the place within the result".
- Otherwise: "mixed". Fewer than 5 models through the gate: per-model verdicts only.

## What we expect

P1 met on 2 to 4 models; P2 met on 2 or 3 (the three where 26 met K2): a reading of "mixed" or "the place within the
result matters, and the separate note adds more".

## Cost and time expected

322 calls a model, about 4 dollars and 10 minutes in all.

## Not covered

One seed; the comparison is across two runs about two hours apart; a key at the front moves the file's content later in
the result, so P1 compares positions of the list, not the list alone; whole runs remain untested.
