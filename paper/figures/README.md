# Figures

## Regenerate

From the repo root, with the repo's virtual environment (matplotlib 3.11.2 was installed into `.venv` for this):

```
.venv/Scripts/python.exe -I -X utf8 paper/figures/make_figures.py
```

It takes about a minute with all runs present and writes, here (PNG at 300 dpi, white background; SVG
text stays text):

- `fig_design.png/.svg`: Figure 1, the method
- `fig_results.png/.svg`: Figure 2, experiment B
- `fig_extensions.png/.svg`: Figure 3, replications and extensions
- `table_rules.png/.svg`: Table 1, the pre-registered rules, rendered from `rules_table.json`

Every later run has a default location, so the plain command draws everything that exists. A run whose directory
does not exist yet is skipped with a printed `not drawn: ...` line, and the figure is drawn without that row or
panel; rerun the script as the runs arrive.

| Tag | Run directory (raw rows) | States | Registered output checked against |
|---|---|---|---|
| B | `analysis/results/v5`, `v6`, `v8` | `analysis/fork_states/states.jsonl` | `analysis/results/rederive_s5.txt`, `explore_b.txt`, registered values |
| C | `analysis/results/c/forks/results.jsonl` | `analysis/fork_states_c/states.jsonl` | `analysis/results/c/analyze_c.txt`, `gates_c.txt` |
| D1 | `analysis/results/d1/forks/results.jsonl` | `analysis/fork_states_d/states.jsonl` | `analysis/results/d1/analyze_d1.txt` |
| D2a | `analysis/results/d2_26b/forks/results.jsonl` | same | `analysis/results/d2_26b/analyze_d2_26b.txt` |
| D2b | `analysis/results/d2_e4b/forks/results.jsonl` | same | `analysis/results/d2_e4b/analyze_d2_e4b.txt` |
| E | `analysis/results/k/forks/results_k.jsonl` | same, population `analysis/fork_states_k/population.json` | `analysis/results/k/analyze_k.txt`, `analyze_k_extra.txt`, `explore_k.txt` |
| F | `analysis/results/w/forks/results.jsonl` | same | `analysis/results/w/analyze_w.txt` |

Options: `--run TAG RUN_DIR` points one later run at another directory (the one its registered script is given;
the checks still read that tag's registered output file). This replaces the earlier `--run TAG STATES RUN_DIR`,
since the later arms no longer go into Figure 2. `--verbose` lists every checked value; `--table` names another
table data file; `--example task,run,fork` picks another state for the design figure (default: the first state in
`analysis/fork_states/states.jsonl`).

## Where the numbers come from

Nothing in the figures is typed in. Each value is computed from the raw per-replay rows with the registered code
path of its experiment:

- **B**: the outcome definitions (`hit`, `opens_file`, `invalid_kind`) are the functions of
  `analysis/rederive_s5.py`, which imports the registered scorer (`fork_states.touches`, `valid_call`).
  `rederive_s5.py` does all of its work at module level and rewrites its report when run, so the script parses its
  source and executes only its imports, constants and function definitions (`load_rederive_defs`). The loading
  block is the one piece copied (`load_source`).
- **C**: `analysis/analyze_c.py` keeps its logic in `main()`, so `exp_c` repeats it without printing: the same arms,
  the same failure checks in the same order (`gates_c.failure`), complete states across every arm and seed present,
  in order of first appearance among the usable rows, and the same scorer (`fork_states.touches` with the line
  lengths of `gates_c._ll`, which equal analyze_c's).
- **D1, D2a, D2b**: `analysis/analyze_d.py`'s `load_run` and `tables`, imported, with the complete-state rule of its
  `main()`.
- **E**: `analysis/analyze_k.py`'s `score` and `first_call_failure`, imported, with the usable-replay rule,
  per-population complete states and seeds of its `main()`. The call-by-call curves of Figure 3(c) are
  `analysis/explore_k.py` section 1 (exploratory): reached by call k means `first_Yline` is not None and at most k,
  on the same complete states. K1 clustered by task uses `analysis/analyze_k_extra.py`'s `table`.
- **F**: `analysis/analyze_w.py`'s arms and seeds, `gates_c.failure` and `gates_c.any_true`, as its `main()` uses
  them; F2 with its `mangled`; F1 from its `fidelity` (its printed line is swallowed).
- Gate G1 of the rented-GPU run is the median computed as `analysis/gates_c.py`'s `g1` computes it (that function only
  prints, so its three lines are repeated).

Rates use the frozen bootstrap `analysis/analyze_forks.py` `boot_ci` (Python's `random`, seed 0, 2,000 resamples,
clustered by state). It draws clusters in the order of its dict, so each table is built in the order its registered
script builds it (B: first appearance among the valid rows, read v5, v6, v8; D, E, F: sorted states; C: first
appearance among the usable rows). Differences use `diff_ci`, which sorts the clusters itself.

## What each figure shows

**fig_results (Figure 2).** Panel (a): share of replays whose next call reads or edits the lines of an unopened true
neighbor, for A, P, H, D and E, then the rewired controls R_D and R_E with their own rate (any rewired entry
touched). Bars are point estimates, whiskers the 95% interval clustered by state, also printed in grey after each
value; gray for nothing added and the bare-name arms, blue for the legible arm E, orange for the rewired lists.
Panel (b), the mechanism, for A, H, D, E: the light bar is the share whose next call opens a listed neighbor's file
at any lines (rederive_s5 section S3), the dark bar the share that reads the neighbor's own lines (section S1, the
registered outcome). Only experiment B is drawn here; the tool-channel arm moved to Figure 3.

**fig_extensions (Figure 3).** Runs are named in words, never by experiment letter. (a) Forest plot of the
legible encoding against bare names wherever both were run: Gemma-4-31B note in the hosted run (E − H) and on the
rented GPU (E − H in the parts-of-an-entry run), the tool result in the tool-channel run (PE − P), the original
rendering in the rendering run (Ew − Hw), and Gemma 4 26B-A4B and E4B in the second-model runs (E − H). Each row
prints the difference with its 95% interval and the two rates behind it; the gray line under each label names the
run and its complete states (a run under 200 complete states would be marked exploratory). (b) The rented-GPU run:
bare names (H), name + first line (ES), name + file + lines (EL), all three (E) on the registered outcome; then, set
apart, the swapped-out true entry under E beside the decoy written in its place under E′, with their raw counts.
(c) The five-call run: one curve per arm (A, H, R_E, E) of the share of replays shown a line the fix changes by the
end of model call 1 to 5, where the list reaches the fix (population R); the call-5 value is printed at the end of
each line; brackets mark E − H at call 3 (exploratory) and at call 5 (rule K1, not met). Beside it, where the fix is
elsewhere (population U), bars of opening a file the fix changes within five calls, per arm.

**table_rules (Table 1).** One row per pre-registered rule, from `rules_table.json` (experiment, pre-registration,
rule, estimate, outcome); the first column names experiments in words, with the pre-registration in gray below.
Cells are wrapped to the column width; the experiment name is shown on the first row of its group. The outcome's
verdict (the text before the first `:` or `;`) is styled: "met" and "passed" in the accent blue, "not met" in bold
dark neutral, "pending" in grey italics; the qualifier after it is set quietly below. A row may name the values its
cells report: `"check"` for the estimate cell, `"check_outcome"` for the outcome cell. Keys: B1, B3, B4_D, B4_E,
G1, G2, C1, C2_EL, C2_ES, E_EL_90, T1, T2_90, M1_D2a, M1_D2b, K1, K1_task, K2, F1, F2, F3. Each `[lo, hi]` in the
cell is compared in order with the next key, together with the last number written before it (if any); G1 and F1
are single values, compared with the first number in the cell. A mismatch stops the script; while a cell is still
`pending`, the script prints the computed value to copy in. Not computed and so not checked: the rows of
pre-registration 02, B2, the five-call gate (44 of 44), the token count in F1 and the two rates in F2's cell.

**fig_design (Figure 1).** The method as a flow: a real run (the issue and its tool calls, ending with the read that
opens a file) is paused; one piece is added per arm; the model makes one call; that call is scored against arm A.
Below, the two list formats from one real state (`fastapi_12942`, run 1, cut point 0, node `analyze_param`), cut
to two of its 14 entries. Display only: entries after the second are counted, the repeated `node` key is left out,
and lines are broken to fit; every value shown is read from the state's own arm texts.

## Checks run

- Before anything is saved, every plotted value of a run whose registered output exists is compared with the
  number printed there (to the printed precision), and a mismatch stops the script:
  - B: each rate and n against `rederive_s5.txt` (S1, S3); the registered rates and intervals of the paper's
    table; the four frozen contrasts (D − H, E − H, D − R_D, E − R_E) against `explore_b.txt` and the registered
    values.
  - C: rates, raw counts, the swapped-out and decoy rates, E − H, EL − H, ES − H, D_E and E − EL (90%) against
    `analyze_c.txt`; E − H, both rates and the G1 median against `gates_c.txt`.
  - D1, D2a, D2b: replays, complete states, each arm's rate, interval and raw count, T1, T2 (95% and 90%) or M1.
  - E: complete states per population, every Yline and Yfile rate and count, K1 and K2 against `analyze_k.txt`;
    K1 and K2 clustered by state and by task against `analyze_k_extra.txt`; every curve value of `explore_k.txt`
    section 1 (both populations, both outcomes, calls 1 to 5, each arm and E − H, E − A, to one decimal); and the
    curves at call 5 against the registered five-call rates.
  - F: complete states, the four rates and counts of the F3 block, F3, the F2 rates, counts and A − Aw, and the F1
    median.
  - A run that exists but has no registered output yet is drawn and reported as UNCHECKED.
- Nov 10, all runs present: 816 values match, none differ (B 77, C 57, D1 26, D2a 25, D2b 25, five-call run 507
  including 362 from `explore_k.txt`, rendering run 44, table cells 55); every interval is reproduced exactly.
  `--verbose` lists each.
- Before the runs arrived, the C, D2b, E and F code paths and their parsers were smoke-tested on scratch runs made by
  relabelling the D2a rows (not data, not kept): every value matched the registered scripts' output on them, and one
  altered printed number each in `analyze_c.txt` and `analyze_w.txt` stopped the script with no figure saved.
- All PNGs were inspected at full size for overlapping or clipped text.
- The palette (blue `#1f6fb4` for E, orange `#c47a3d` for the rewired lists and the decoy, grays for the rest)
  passes a colorblind-separation check (worst adjacent CVD delta E 21); identity never rests on color alone, since
  every bar is labelled in words.

## Note on the two bootstraps

`rederive_s5.txt` prints intervals from its own numpy bootstrap (for example E [5.84, 10.82]); the paper's table
and the figures use the frozen `boot_ci` (E [5.76, 10.91]). Point estimates agree.
