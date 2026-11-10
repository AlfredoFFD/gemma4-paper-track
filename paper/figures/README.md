# Figures

## Regenerate

From the repo root, with the repo's virtual environment (matplotlib 3.11.2 was installed into `.venv` for this):

```
.venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py
```

It takes about 15 seconds and writes `fig_results.png`, `fig_results.svg`, `fig_design.png` and `fig_design.svg`
here (PNG at 300 dpi, white background; SVG text stays text).

Later runs are added without changing the figure code. Each one is passed with its tag, its states file and its run
directories (the directory holding `results.jsonl` or `forks/results.jsonl`):

```
.venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py \
    --run C  analysis/fork_states_c/states.jsonl <experiment C run dir> \
    --run D1 analysis/fork_states_d/states.jsonl <experiment D1 run dir>
```

`ARM_SPECS` in the script already lists Ep, EL, ES (tag `C`) and PE (tag `D1`) with their labels; an arm is drawn
only when its run is given. Each run is scored on its own states file and its own complete states (every arm of
that run and every seed valid) and is never pooled with experiment B. Its bars get their own section with a header
naming the run. `--example task,run,fork` picks another state for the design figure (default: the first state in
`analysis/fork_states/states.jsonl`).

## Where the numbers come from

Nothing is typed in. The script computes every value from the raw replay logs (`analysis/results/v5`, `v6`, `v8`)
and `analysis/fork_states/states.jsonl`:

- The outcome definitions (`hit`, `opens_file`, `invalid_kind`) are the functions of `analysis/rederive_s5.py`,
  which imports the registered scorer (`fork_states.touches`, `valid_call`).
- The intervals come from the frozen bootstrap of the paper's table, `analysis/analyze_forks.py` `boot_ci`
  (Python's `random`, seed 0, 2,000 resamples, clustered by state). It draws clusters in the order of its dict, so
  the per-state lists are built in the order `analysis/analyze_b.py` builds them: states in order of first
  appearance among the valid rows, read v5, v6, v8.
- `rederive_s5.py` does all of its work at module level and rewrites `analysis/results/rederive_s5.txt` when run,
  so it is neither imported nor run. The script parses its source and executes only its imports, constants and
  function definitions (`load_rederive_defs`). The loading block (states, valid replays, complete states) is the
  one piece copied, generalized to take a states file and run directories (`load_source`); the per-replay loop
  (`score`) keeps only the three outcomes the figures use.

## What each figure shows

**fig_results.** Panel (a): share of replays whose next call reads or edits the lines of an unopened true neighbor,
for A, P, H, D and E, then the rewired controls R_D and R_E with their own rate (any rewired entry touched). Bars
are point estimates, whiskers the 95% interval clustered by state, also printed in grey after each value; gray for nothing added and the bare-name arms,
blue for the legible arm E, orange for the rewired lists. Panel (b), the mechanism, for A, H, D, E: the light bar
is the share whose next call opens a listed neighbor's file at any lines (rederive_s5 section S3), the dark bar the
share that reads the neighbor's own lines (section S1, the registered outcome). Bare names already raise the first
(4.55% to 7.47% and 11.17%) without raising the second much; only E's line ranges carry the read to the code.

**fig_design.** The method as a flow: a real run (the issue and its tool calls, ending with the read that opens a
file) is paused; one piece is added per arm; the model makes one call; that call is scored against arm A. Below,
the two list formats from one real state (`fastapi_12942`, run 1, cut point 0, node `analyze_param`), cut to two
of its 14 entries: the bare-name JSON as `get_code_neighbors` prints it (arm P; H and D carry the same JSON) and
arm E's note with name, file, line range and first definition line. Display only: entries after the second are
counted, the repeated `node` key is left out, and lines are broken to fit; every value shown is read from the
state's own arm texts. The tool-call history shows the first two calls, a count, and the last call.

## Checks run

- Before anything is saved, every experiment B value the figures use is checked, and a mismatch stops the script:
  each rate and n against `analysis/results/rederive_s5.txt` (sections S1 and S3); the registered rates A 2.15,
  P 3.01, H 2.75, D 4.30, E 8.25 (any unopened true neighbor touched) and R_D 0.52, R_E 1.03 (any rewired entry
  touched); and the registered intervals A [0.86, 3.61], P [1.55, 4.64], H [1.37, 4.30], D [2.58, 6.10],
  E [5.76, 10.91], R_D [0.00, 1.29], R_E [0.34, 1.89] (to the printed two decimals). All passed: `boot_ci`
  reproduces each registered interval exactly (388 complete states, 1,164 replays per arm). Panel (b)'s
  file-level whiskers use the same `boot_ci`; they have no registered values to check against.
- The `--run` path was smoke-tested on a scratch copy of the v6 rows with the arm labels renamed (not data, not
  kept); the extra section drew without overlap.
- Both PNGs were inspected at full size for overlapping or clipped text.
- The palette (blue `#1f6fb4` for E, orange `#c47a3d` for the rewired lists, grays for the rest) passes a
  colorblind-separation check (worst adjacent CVD delta E 21); identity never rests on color alone, since every
  bar is labelled in words.

## Note on the two bootstraps

`rederive_s5.txt` prints intervals from its own numpy bootstrap (for example E [5.84, 10.82]); the paper's table
and the figure use the frozen `boot_ci` (E [5.76, 10.91]). Point estimates agree.
