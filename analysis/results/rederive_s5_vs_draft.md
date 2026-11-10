# Independent re-derivation vs the draft (abstract, 3.1, 4, 5)

My values are from `analysis/results/rederive_s5.txt` (blind phase, script `analysis/rederive_s5.py`), plus a few
phase-2 diagnostic runs that reuse the same functions (marked "diag"). Bootstrap: numpy RNG, seed 0, 2,000
resamples; the frozen analysis uses Python's `random.Random(0)`, so interval ends differ by bootstrap noise only.
MATCH = same value at the printed precision; CLOSE = within 0.3 points or bootstrap noise; MISMATCH = otherwise.

## Counts

| Claim | Draft | Mine | Verdict | Diagnosis |
|---|---|---|---|---|
| States (3.1) | 407 | 407 | MATCH | |
| Runs the states come from (3.1) | 241 runs | 205 distinct (task, run) = 205 distinct traces, all from the base agent | MISMATCH | No field in states.jsonl gives 241; 205 is what the states hold (388 complete states come from 199) |
| Tasks (3.1, abstract) | 77 | 77 (all and complete) | MATCH | |
| "two repositories supply all but one state" | | fastapi 216, rich 190, requests 1 | MATCH | |
| "We pause 407 real runs" (abstract) | 407 runs | 407 pause points in 205 runs | MISMATCH | Wording: up to 3 states per run; should be "407 points in 205 runs" |
| Replays | 12,210 | 12,210 | MATCH | |
| Interface failures | 34: 24 malformed, 10 no call, 0 to 7 per arm | 34: 24 malformed, 10 no call; per arm 0 (H) to 7 (A) | MATCH | |
| Complete states, replays per arm | 388, 1,164 | 388, 1,164 | MATCH | |
| Padded rewired entries (3.2) | 847 in 298 states | 847 in 298 of all 407 states; 826 in 286 of the 388 analysed | MATCH | Counted over all states; the analysed set has 826 / 286 |
| Fidelity, arm A vs logged prompt (v5) | median 1.7%, mean 3.0%, two at 9.5% and 25% | 1.66%, 3.01%, 9.5%, 25.2% (24 states) | MATCH | |
| Recount cells | 46,560 | 388 x 30 x 4 = 46,560 | MATCH (arithmetic) | Recount scores themselves not re-derived |

## Experiment A (section 4)

| Claim | Draft | Mine | Verdict | Diagnosis |
|---|---|---|---|---|
| P,H pooled minus A, five-arm states | +0.8 [-0.1, 1.7] | +0.81 [-0.04, 1.70] (393 five-arm complete states; diag) | MATCH | |
| Decoy followed | 0 of 2,442 | 0 of 2,358 (Pp+Hp in 393 complete states) | CLOSE | Count right; 2,442 is all Pp+Hp rows including 10 invalid ones, inconsistent with the 2,358 used for the swapped-out entry |
| Swapped-out true entry | 6 of 2,358 | 6 of 2,358 | MATCH | |
| Channel P - H | +0.25 [-0.7, 1.2] | +0.25 [-0.68, 1.19] | MATCH | |
| Graph tool as next call, P vs A | 3.2% vs 0.3% | 3.3% vs 0.3% (393 states) | CLOSE | |

## Experiment B (section 4, abstract)

| Claim | Draft | Mine | Verdict | Diagnosis |
|---|---|---|---|---|
| A any true | 2.15% [0.86, 3.61] (abstract 2.2%) | 2.15% [0.86, 3.69] | MATCH (point) / CLOSE (CI) | bootstrap RNG |
| P | 3.01% [1.55, 4.64] | 3.01% [1.55, 4.64] | MATCH | |
| H | 2.75% [1.37, 4.30] (abstract 2.8%) | 2.75% [1.37, 4.38] | CLOSE (CI) | bootstrap RNG |
| D | 4.30% [2.58, 6.10] | 4.30% [2.66, 6.19] | CLOSE (CI) | bootstrap RNG |
| E | 8.25% [5.76, 10.91] (abstract 8.3%) | 8.25% [5.84, 10.82] | CLOSE (CI) | bootstrap RNG |
| R_D true / rewired | 2.32% [1.03, 3.78] / 0.52% [0.00, 1.29] | 2.32% [1.03, 3.78] / 0.52% [0.00, 1.20] | CLOSE | |
| R_E true / rewired | 2.41% [1.12, 3.87] / 1.03% [0.34, 1.89] | 2.41% [1.12, 3.95] / 1.03% [0.34, 1.80] | CLOSE | |
| A rewired | 0 | 0.00% | MATCH | |
| B1 D - H | +1.55 [0.60, 2.66] | +1.55 [0.60, 2.66] | MATCH | |
| B2 swapped-out under D | 0.34% | 0.34% | MATCH | |
| B2 decoy under D' | 4 of 1,164 | 4 of 1,164 (0.34%) | MATCH | |
| B3 E - H | +5.50 [3.44, 7.65] (abstract 3.4 to 7.7) | +5.50 [3.52, 7.65] | CLOSE (CI) | bootstrap RNG |
| B4 D - R_D | +3.78 [2.15, 5.67] | +3.78 [2.15, 5.67] | MATCH | |
| B4 E - R_E | +7.22 [4.64, 9.97] | +7.22 [4.55, 9.97] | CLOSE (CI) | bootstrap RNG |
| E / A factor | 2.6 to 3.8 | 3.84 registered reading | MATCH (upper end) | lower end (2.6) uses the recount's wider reading, not re-derived |
| Recount: B1 +1.55 [0.43, 2.75], B3 +5.33, B4 +4.04 / +7.22; wide reading A 3.5%, E 9.1%, B3 +4.73, B1 +0.77 | | not computed | NOT VERIFIED | alternative scorer readings are outside this task |
| E - H by task | +5.50 [2.16, 9.15] | +5.50 [2.37, 9.28] | CLOSE | |
| E - R_E by task | +7.22 [2.97, 12.07] | +7.22 [3.09, 11.93] (diag) | CLOSE | |
| McNemar on states | E 41, H 14, 29 vs 2, p = 5e-7 | 41, 14, 29 vs 2, p = 4.6e-7 | MATCH | |
| E - H per seed | +4.6 to +7.0 | +4.64, +4.90, +6.96 | MATCH | |
| E - H at each cut point | positive | fork 0 +6.06, fork 1 +6.71, fork 2 +4.03, all CIs above 0 | MATCH | |
| E - H leaving out a repository | +3.1 / +7.7 | +3.06 (no fastapi) / +7.68 (no rich) | MATCH | |
| E - H leave one task out | +4.6 to +5.9 | +4.57 to +5.85 | MATCH | |
| E - H without the five top-E-hit tasks | +2.37 [0.85, 4.07] | +2.62 [1.12, 4.21] (356 states) | CLOSE | Tie at 8 E hits between two tasks for 5th place. The draft drops the one that leaves 352 states (+2.37, reproduced in diag); dropping the other gives +2.62; with all three possible top-5 sets the value runs from +2.37 to +2.74. Say "about +2.4 to +2.7" or state the tie-break |

## Section 5 (exploratory)

| Claim | Draft | Mine | Verdict | Diagnosis |
|---|---|---|---|---|
| Followed by any means: A, H, D, E | 5.2, 9.9, 12.9, 12.4 | 5.24, 9.88, 12.89, 12.37 | MATCH | |
| H - A (any means) | +4.64 [2.66, 6.79] | +4.64 [2.75, 6.70] | CLOSE (CI) | |
| E - D (any means) | -0.52 [-2.58, 1.46] | -0.52 [-2.66, 1.55] | CLOSE (CI) | |
| P(touch given file opened), E | 70% [56, 82] | 70.07% [56.74, 82.09] (n = 137) | MATCH | |
| Same, "37% to 47% in every arm except E" (also abstract) | 37-47% | A 47.2, H 36.8, D 38.5, but P 41.7, Pp 49.4, Hp 45.2, Dp 44.9, RD 47.4, RE 45.9 | MISMATCH (scope) | True for A, H, D (the draft source reports only those); across all non-E arms the range is 37% to 49% |
| "In A, H and D every hit is a read_file from the top of the file" | every hit | A 25/25; H 31/32; D 48/50 (the rest are shell name searches) | MISMATCH | 1 H hit and 2 D hits are grep-style shell views; say "all but three" |
| E: 34 of 96 hits read exactly a listed range, 13 more start at a listed first line | 34, 13 | 34, 13 (5 others, 44 from the top) | MATCH | |
| Thought mentions, H / D / E | 10.8 / 12.2 / 11.0% | 9.88 / 11.43 / 10.31% | CLOSE (definition) | Draft: substring of short name in thought+text, among replays with a thought. Mine: word-boundary match, names of 4+ chars, thought only, all replays. Same conclusion |
| E - H thought mentions | +0.21 [-1.00, 1.53] | +0.43 [-0.86, 1.72] | CLOSE (definition) | as above |
| List position under E: rank 1, 2-3, 4-7, 8+ | 5.2, 3.5, 1.3, 0.4% | 5.22, 3.47, 1.28, 0.40% (per entry-seed; n = 690, 807, 1,797, 7,818) | MATCH | |
| "The tool sorts alphabetically" | | true_neighbors sorted in all 407 states | MATCH | |
| Matched true entries | 3,292 of 3,704 | 3,292 of 3,704, in 363 of 388 states | MATCH | |
| E, matched true touched | 2.49% [1.20, 3.87] | 2.49% [1.20, 3.95] | CLOSE (CI) | |
| E - H, matched | +2.32 [1.12, 3.69] | +2.32 [1.03, 3.78] | CLOSE (CI) | |
| E matched minus R_E rewired | +1.46 [0.00, 3.01] | +1.46 [-0.09, 3.09]; by task [-0.73, 3.81] | CLOSE | Lower bound sits on zero under one RNG and below it under another, and well below by task: "somewhat more" is not established; call it not distinguishable from zero |
| D matched minus R_D rewired | +0.34 [-0.60, 1.29] | +0.34 [-0.52, 1.20] | CLOSE (CI) | |
| R_E: 5 of its 12 hits start at a listed first line | 5 of 12 | 5 of 12 (7 from the top) | MATCH | |
| Toward the fix: A, H, D, E | 6.0, 6.6, 8.8, 8.2% | 6.87, 7.22, 9.36, 8.51% (read, edit or shell view of a gold-diff file not yet opened) | MISMATCH (definition) | Draft numbers are reproduced (diag: 6.01, 6.62, 8.76, 8.16) only when counting read_file calls alone and taking gold files from the pointer-audit units file. Shell views (cat/sed/grep of the file) are excluded in the draft |
| Toward the fix: E - A | +2.15 [0.60, 3.95] | +1.63 [-0.26, 3.61] | MISMATCH | Under read-or-view the interval includes zero. read_file-only with diff files: +2.41 [0.69, 4.30]. The claim depends on excluding shell views; state the definition or soften |
| Toward the fix: E - R_E | +1.55 [-0.09, 3.35] | +1.03 [-0.69, 2.92] | MISMATCH (definition) | same cause; both readings include zero |
| R_D - A, true entries | +0.17 [-0.86, 1.29] | +0.17 [-0.95, 1.29] | CLOSE (CI) | |
| R_E - A, true entries | +0.26 [-0.60, 1.12] | +0.26 [-0.60, 1.12] | MATCH | |
| Prompt tokens, E vs H | 8,224 and 7,594 (about 630 longer) | 8,224 and 7,594 | MATCH | |
| "No arm ran in two sessions" | | v5: A P Pp H Hp; v6: D Dp E; v8: RD RE | MATCH | |

## Extra checks (not claimed in the draft)

- Rewired lists with no padding (102 states): E true 11.44% vs R_E rewired 1.63%, difference +9.80 [3.92, 16.34];
  D true minus R_D rewired +10.78. The B4 gap does not come from padding.
- D vs H McNemar on states: 25 vs 14, 13 vs 2 discordant, p = 0.0074.
- E - H on "followed by any means", by task: +2.49 [-0.25, 5.76] (by state +2.49 [0.52, 4.64]).
- 7 rewired entries sit in a file the gold diff touches: the rewired eligibility used the pointer-audit units
  file, which differs from the diff file list in 12 tasks. Negligible for the results.
