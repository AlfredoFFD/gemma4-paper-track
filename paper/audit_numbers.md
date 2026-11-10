# Number audit of `paper/draft.md` (Nov 10, 2026)

**Status, Nov 10, 2026, after this audit.** The audit below was run on the draft as it stood before the corrections. All 36 items were then handled in `paper/draft.md`: the rounding and count mismatches are corrected (two-decimal values in the abstract, six pre-registrations, +0.9 at ranks 4 to 7, 199 original-run reads); the unsourced numbers are either removed (the read_file-only reading of "toward the fix", the total duration of the preempted run) or now have a stored source (`analysis/results/k/fidelity_gate.txt`, `analysis/results/c/restart_log_excerpt.txt`, the updated `paper/references.md`); the wording items are reworded (subtitle, the definition line, "sooner" marked exploratory, the scope of the mangled-name rate, re-derivation limited to pre-registrations 03 to 07, hosted sessions, 393 states, "no detectable difference", "rarely" and "almost never" followed, the confound of list position, Qwen agents, the third repository, padding counts, the arms behind 1 of 577). The item numbers below refer to the draft before these changes.

[Claude Code] Checker only. Every quantitative claim in the draft (title to Appendix G) was traced to a stored
output under `analysis/results/`, a raw run file (`forks/summary*.json`, `versions*.json`, `pip_freeze*.txt`,
`fidelity*.jsonl`, `checkouts_k.jsonl`), `analysis/trace_stats.json`, a pre-registration, or a repo document for
cited work. NOTES.md was used only to find where a number came from. Line numbers below are of the cited file.
Rates from raw counts were recomputed where the draft rounds a printed two-decimal value a second time.

## Verdict

The draft is in good shape: every registered estimate, interval and verdict in Sections 4.1 to 4.4 and in
Appendix A matches the stored analysis outputs, the replay total (39,598) and the nine-run table add up, and the
Section 5 mechanism numbers all trace to `explore_b.txt`, `explore_mechanism.txt`, `explore_k.txt` and
`mangled_*.txt`. The problems are of three kinds. (1) Seven small numeric errors, four of them in the abstract,
mostly from rounding an already rounded value (2.2%, 2.8%, 8.3%, +6.4 should be 2.1%, 2.7%, 8.2%, +6.3), plus
"seven pre-registrations" (there are six documents, 02 to 07, governing seven experiments), "201" reads (stored
output says 199) and "+1.0" at ranks 4 to 7 (+0.9). (2) Five claims rest on no stored output: the read_file-only
"toward the fix" rates and interval, the five-call platform gate (44 of 44; 36/18/13 of 67), the 3.6-hour duration
and the 2,946-replay preemption point of experiment C, and three references absent from `paper/references.md`.
(3) About two dozen wording issues, the most exposed being: "not followed" for the rewired list and the false
entry when the 31B model does touch rewired entries above base (12 vs 0, McNemar p = 0.00049); "no contrast mixes
runs" when every hosted contrast pairs arms from different sessions; "the channel makes no difference" for a
failed two-sided test; "a third of its ranged reads", true only for the no-list arm's first call; and "no more
often by the fifth" for a contrast whose interval reaches +8.8. None of these changes a registered verdict.

## Items that are not MATCH or ROUNDING

| # | Section | Draft phrase | Source (file:line) | Status | Suggested correction |
|---|---|---|---|---|---|
| 1 | Abstract | "barely change the next call: 2.8% of replays" | `explore_b.txt:20,22` (P 35/1164, H 32/1164) | MISMATCH | H is 32/1164 = 2.749%, which rounds to 2.7%; P is 3.0%; pooled P and H is 2.9%. The phrase "as `get_code_neighbors` prints them" also points at P while 2.8 is H's printed 2.75. Write "2.7% as a note and 3.0% as the tool's result". |
| 2 | Abstract | "against 2.2% with no list" | `explore_b.txt:19` (25/1164) | MISMATCH | 25/1164 = 2.148%: "2.1%" (or "2.15%" as in 4.1). |
| 3 | Abstract | "three times as often (8.3%;" | `explore_b.txt:26` (96/1164) | MISMATCH | 96/1164 = 8.247%: "8.2%" (or "8.25%" as in 4.1 and Section 8). |
| 4 | Abstract | "holds inside the tool's own result (+6.4)" | `d1/analyze_d1.txt:10,15,27` (115/1197 minus 39/1197) | MISMATCH | 76/1197 = 6.349 points: "+6.3" (4.2 and Appendix A print +6.35). |
| 5 | 3.4; Reproducibility | "Seven pre-registrations (`prereg/02` to `07`)"; "the seven pre-registrations" | `prereg/` holds 02, 03, 04, 05, 06, 07; 01 is "DRAFT, not frozen" (`prereg/01-graph-uptake-draft.md:3`) | MISMATCH | "Six pre-registrations (`prereg/02` to `07`) fixed the rules of seven experiments". The abstract's "seven pre-registered experiments" is correct (A, B, C, D1, D2, the five-call run, F). |
| 6 | 5 | "+1.0 at ranks 4 to 7" | `explore_b.txt:261`; `rederive_s5.txt:173` (E 23/1797, A 6/1797) | MISMATCH | 17/1797 = 0.95 points before rounding (0.946): "+0.9". The other ranks match (+4.1, +1.7, +0.4). |
| 7 | App. D | "Original runs, their own next call at the same states \| 201 \| 2 (1.0%)" | `w/analyze_w.txt:20` and `rederive_w.txt:65`: 2 of 199 | MISMATCH | "199". The 201 appears only in the exploratory "Why" of `prereg/07-tool-result-rendering.md:13`, from an earlier count over a different state set. |
| 8 | App. C | "only `read_file` calls ... 6.0% of A replays, 6.6% of H, 8.8% of D and 8.2% of E (E − A +2.15 [0.60, 3.95])" | No script output prints these. `rederive_s5_vs_draft.md:84-85` reproduces the four rates only in an unstored diagnostic run and gets +2.41 [0.69, 4.30] for read_file-only with patch files; the interval +2.15 [0.60, 3.95] appears only in NOTES.md:624 | UNSOURCED | Add the read_file-only reading to `explore_b.py` or `rederive_s5.py` and store its output, or drop the read_file-only sentence and keep the sourced reading (6.9, 7.2, 9.4, 8.5%; +1.63 [−0.26, 3.61], `rederive_s5.txt:205-215`). |
| 9 | App. A row 06; App. E | "44 of 44"; "of 67 logged shell results, 36 were identical, 18 ... 13 differed" | Only in the amendment text `prereg/06-navigation-horizon.md` (Amendment of Nov 10, 3:04 AM) and NOTES.md:667; no gate output under `analysis/results/k/` | UNSOURCED | Store the fidelity-mode output of the five-call runner (or say "recorded in the pre-registration's amendment"). |
| 10 | App. B | "31B, one A100-80GB, 3.6 h in two containers" | `c/forks/summary.json`: elapsed_s 6159 (1.7 h), the second container only; the first container's time is not stored | UNSOURCED | Store the first container's time, or write "1.7 h in the second container after a restart". |
| 11 | App. F item 6 | "preempted by the platform after 2,946 saved replays" | NOTES.md:717 only; `c/forks/results.jsonl` rows carry no timestamps or container id | UNSOURCED | Keep the fact but cite the run log, or drop the count. |
| 12 | References | [3] discussion 744272, [4] discussion 745731, [10] LARGER | Not in `paper/references.md`. Supported by `docs/prior-art.md:89-111` ([3], [4]) and `docs/lit/2026-11-10-larger-check.md:132` ([10], authors, title, id) | UNSOURCED (in references.md) | Add the three entries to `paper/references.md`; also update its Bellam entry, which still says "v2 was not read" (`docs/lit/2026-11-10-bellam-v2-check.md` read v2 in full) and lists one entry where the draft has [7] v2 and [8] v1. |
| 13 | Abstract | "The location carries all of it; the definition line adds nothing." | `c/analyze_c.txt:32,37`; `prereg/04-experiment-c-amendment.md` (Power: "does not raise" for one part "is reported with its interval, not as a zero") | WORDING | "Location alone is enough (E − EL +0.83, 90% interval within 2 points); the definition line adds no detectable following (+0.08 [−0.75, 0.92])." |
| 14 | Abstract | "the legible list gets the agent to the fix's lines sooner" | `k/explore_k.txt:4-8` (EXPLORATORY; E − H excludes 0 at calls 1 and 3 only) | WORDING | Mark it: "in an exploratory call-by-call view, the legible list gets the agent there sooner". |
| 15 | Abstract; 6 | "mangle an argument name in a third of its ranged reads"; "a third of the 31B model's ranged reads after a file read" | `mangled_args_counts.txt:13-28` (A 35.8%; notes 4.4% to 17.3%); `w/analyze_w.txt:15`; `k/explore_k.txt:28-36` (no list 40.6% first call, 25.1% later; all arms and calls 14.4%) | WORDING | "in a third of its ranged reads when no note is added (14% over all arms and calls with tools executing)". |
| 16 | Subtitle; Abstract | "show why the code graph goes unused"; "Both problems are cheap to fix" | Section 5 is EXPLORATORY; no run tested rejecting unknown argument names | WORDING | Keep "why" tied to the registered encoding result, and say "both have cheap fixes, one tested (PE) and one not". |
| 17 | 2 | "holds every function or class the fix edits in 84% of tasks" | `rederive_audit_vs_original.md:10` (103/122 eligible tasks); the 10% and 15% to 19% use 129 tasks (`:14,17`) | WORDING | "in 84% of the 122 tasks whose fix edits a function or class". |
| 18 | 3.2 | "a real function from the same directory that is not a neighbor, a fix location or a test" | `prereg/02-discrimination-forks.md` (Arms): a node (function or class) in an unopened file with no listed entry, not in view, from the swapped-out entry's directory, else the node's directory, else the package | WORDING | "a real function or class, usually from the same directory, in an unopened file, that is not a neighbor, a fix location, a test or already in view". |
| 19 | 3.2 | "a list from a degree-preserving rewiring of the graph" | `explore_b.txt:293` (826 of 5,860 rewired entries in the 388 states are directory padding, 286 states) | WORDING | Add "padded from the node's directory where the rewiring ran short (Appendix C)". |
| 20 | 3.4 | "Every registered number was re-derived by a second script written without the first." | Pre-registration 02's H1 (+0.81) and H3 (+0.25) on 393 states appear in `rederive_s5_vs_draft.md:28,31` only from diagnostic runs, not in `rederive_s5.txt`; the five-call gate has no stored re-derivation | WORDING | "Every registered estimate of pre-registrations 03 to 07 was re-derived ...; those of 02 were checked in a diagnostic run." Or store the diag output. |
| 21 | 3.4 | "no contrast mixes runs" | `explore_b.txt:4,9-10`: v5 ran A P P′ H H′, v6 D D′ E, v8 R_D R_E; "every contrast between sessions (E - H, E - RE, D - RD) also carries any drift between sessions" | WORDING | "no contrast mixes platforms or models; the hosted contrasts pair arms from three sessions of one platform (Appendix C)". |
| 22 | 4.1 | "+0.8 points pooled [−0.1, 1.7]" next to "2.15% ... 3.01% ... 2.75%" | `analyze_a.txt:3,23` (393 states complete over five arms); the rates are on 388 states, where the pooled difference is (3.01 + 2.75)/2 − 2.15 = +0.73 | WORDING | Add "(registered analysis on the 393 states complete in that run)". |
| 23 | 4.1; App. A row 02 | "The channel makes no difference (P − H +0.25 [−0.7, 1.2])"; outcome "no difference" | `prereg/02-discrimination-forks.md` H3: "the CI ... excludes 0" (two-sided); `analyze_a.txt:28`. The draft applies the stricter equivalence reading to T2 ("not shown") | WORDING | "No channel difference was detected (P − H +0.25 [−0.7, 1.2])"; Appendix A outcome "not met (interval includes 0)". |
| 24 | 4.1; 6 | "A rewired list is not followed."; "Legible output did not make wrong edges actionable for the two larger models" | `explore_b.txt:222` (R_E vs A, rewired entries: 12 vs 0 replays, p = 0.00049; 9 vs 0 states, p = 0.0039); `analyze_b.txt:55` (1.03% [0.34, 1.89]); 26B: `explore_mechanism.txt:20-24` (0.34% with and without) | WORDING | "A rewired list is rarely followed (1.03% under R_E against 0% with no list)"; in 6, "made wrong edges barely actionable for the 31B model and not at all for 26B-A4B". |
| 25 | 4.3 | "A false entry is not followed." | `c/analyze_c.txt:23` (1 of 1,200) | WORDING | "A false entry is almost never followed." |
| 26 | 5 | "List position matters." | `explore_b.txt:255-262` (EXPLORATORY); rank is confounded with alphabetical order and list length | WORDING | "Entries lower in the list are followed less." |
| 27 | 5 | "A pre-registered test traces this to the harness change of Sep 30" | `prereg/07-tool-result-rendering.md` (Stated limits: the original rendering "is inferred from the v25 source"); the date comes from forum thread 744272 (`docs/prior-art.md:89-100`) | WORDING | "A pre-registered test traces this to the rendering of tool results as dictionaries, which the forum dates to the harness of Sep 30 [3]". |
| 28 | 5 | "a likely reason any note helped in Section 4.4" | `k/analyze_k.txt:36` (U, Yfile H − A +3.22 [−1.75, 8.48]); only E − A and R_E − A exclude 0 (`:35,37`) | WORDING | "a likely reason the legible and rewired notes helped in Section 4.4". |
| 29 | 6 | "the graph's failure is not a failure ... to tell a true edge from a false one" | `explore_b.txt:323` (matched true minus rewired +1.46 [0.00, 3.01]); `rederive_s5.txt:188-189` (lower −0.09; by task [−0.73, 3.81]); Section 5's own qualification | WORDING | Restrict it to the registered false-entry test: "a planted false entry is almost never followed (Section 4.3)", and drop the rewired list from this sentence. |
| 30 | 6 | "ten points more often by the third, and no more often by the fifth" | `k/explore_k.txt:6` (EXPLORATORY); `k/analyze_k.txt:8` (K1 +3.86 [−1.05, 8.77], "no detectable gain") | WORDING | "ten points more often by the third (exploratory), and not detectably more often by the fifth". |
| 31 | 6, item 2 | "As it stands, a third of the 31B model's ranged reads after a file read return the wrong lines." | Section 8: measured "in replays of earlier histories ..., not in fresh runs"; a third holds only for the no-list first call (item 15) | WORDING | "In our replays under the current harness, a third of the no-list first reads with a line bound return the wrong lines." |
| 32 | 7 | "small agents copy a graph-learning tool's often wrong labels [17]" | `docs/lit/2026-11-10-related-work-check.md:42` row 21 (Qwen2.5-7B agrees 0.976 to 0.992; Mistral-7B 0.53, OLMo-2-7B 0.60) | WORDING | "small Qwen agents copy a GNN tool's often wrong labels [17]". |
| 33 | 4.1; 8; App. C | "with either repository left out"; "States come from the 31B agent's runs on two repositories" | `rederive_s5.txt:9-10` and `explore_b.txt:6`: fastapi 203, rich 184, requests 1 of the 388 states (216, 190, 1 of 407) | WORDING | "on two repositories (one more state comes from a third)"; "with either main repository left out". |
| 34 | App. B | "each run's `versions.json` also lists the newer wheels ..., and its `pip_freeze.txt` shows what was installed" | `pip_freeze*.txt` exists for the six rented runs only (all show adk_submission 0.2.12, swegemma 0.2.7); hosted v5 and v8 show the installed 0.2.12 and 0.2.7 wheels in `gemma-graph-forks-pilot.log`; v6 has no stored install record | WORDING | "the rented runs' `pip_freeze.txt` and the hosted runs' logs show what was installed (no install record is stored for hosted run 2)". |
| 35 | App. C | "847 rewired entries in 298 states are same-directory padding" | `explore_b.txt:293`, `rederive_s5.txt:198`: 826 in 286 of the 388 analysed states; 847 in 298 is over all 407 (`prereg/03-directive-and-encoding.md`, amendment; `rederive_s5_vs_draft.md:20`) | WORDING | "826 rewired entries in 286 of the 388 states (847 in 298 of all 407)". |
| 36 | App. D | "Reads of a listed unopened file under bare names carry a mangled bound in 1 of 577 cases" | `mangled_sensitivity.txt:4-10`: 577 = A 51 + P 80 + P′ 76 + H 80 + H′ 70 + D 124 + D′ 96; the bare-name arms alone give 526 (1 mangled, in D) | WORDING | "with no list or under bare names ... 1 of 577" or "under bare names ... 1 of 526". |

## Full list of checked items

Status counts are at the end. "printed" means the two-decimal value in the stored output.

### Title, subtitle, abstract

- [MATCH] 205 runs, 407 points: `rederive_s5.txt:5,8`; `explore_b.txt:4`.
- [MATCH] seven pre-registered experiments: A, B, C, D1, D2, five calls, F (six documents, see item 5).
- [ROUNDING] about 40,000 replays: 39,598 (sum of Appendix B rows).
- [MISMATCH] 2.8% with bare names: item 1.
- [MISMATCH] 2.2% with no list: item 2.
- [MATCH] three times as often: 96/32 = 3.0 (`explore_b.txt:22,26`).
- [MISMATCH] 8.3%: item 3.
- [ROUNDING] +5.5 points [3.4, 7.7]: printed +5.50 [3.44, 7.65] (`analyze_b.txt:44`).
- [MISMATCH] +6.4 in the tool result: item 4.
- [MATCH] +3.5, +3.1 on two other models: 42/1191 = 3.53, 28/915 = 3.06 (`d2_26b/analyze_d2_26b.txt:34`; `d2_e4b/analyze_d2_e4b.txt:34`).
- [MATCH] +5.2 under the original rendering: 62/1200 = 5.17 (`w/analyze_w.txt:27`).
- [WORDING] location carries all of it; definition line adds nothing: item 13.
- [MATCH] false neighbor 1 of 1,200, true 23: `c/analyze_c.txt:20,23`.
- [MATCH] five calls +3.9 [−1.1, 8.8]: 11/285 = 3.86 (`k/analyze_k.txt:8`).
- [WORDING] gets to the fix's lines sooner (exploratory, unlabeled): item 14.
- [WORDING] a third of its ranged reads: item 15.
- [WORDING] subtitle "why"; "both problems are cheap to fix": item 16.

### 1. The question

- [MATCH] GraphLoc 28.9% to 29.9%, interval −4.1 to +6.3: `docs/competition.md:205`; LOG.md:164-165 per `docs/lit/2026-11-10-related-work-check.md` row 4. The arm is now described correctly ("a graph-localization skill").
- [MATCH] three tools to query the graph: `docs/competition.md:66-68`.

### 2. What the public traces already show

- [MATCH] 318 traces, 3 runs of 106 tasks: `analysis/trace_stats.json` ("runs": 318).
- [MATCH] graph tool in 109 runs, non-empty answer in 26: `trace_stats.json`.
- [MATCH] `get_code_neighbors` 8 times, `get_code_subgraph` never: `trace_stats.json` ("calls").
- [MATCH] 27% against 23%: `trace_stats.json` (uptake_rate 0.2692, control_rate_mean 0.2267; 7 of 26 events).
- [WORDING] 84% of tasks: item 17 (103/122, `rederive_audit_vs_original.md:10`).
- [MATCH] 10% at one hop: 13/129 (`rederive_audit_vs_original.md:14`).
- [ROUNDING] 15% to 19% at two hops: 14.7% capped, 19.4% uncapped (`rederive_audit_vs_original.md:17`).

### 3. Method

- [MATCH] cut after the first, second or third content-showing result; prompt at most 12,500 tokens: `prereg/02-discrimination-forks.md` (Material).
- [MATCH] queried node with 2 to 50 neighbors: `analysis/fork_states.py:18,55`.
- [MATCH] 407 states, 205 runs, 77 tasks: `rederive_s5.txt:5,7,8`.
- [WORDING] decoy description: item 18.
- [WORDING] rewired list without the padding caveat: item 19.
- [MATCH] seeds 1 to 3: every `versions.json` ("seeds": [1, 2, 3]); five-call R uses 1 to 5, stated in Appendix B.
- [MATCH] v28 hands results as dictionaries, the original harness as JSON strings [3]: `prereg/07-tool-result-rendering.md` (Why, item 2); `docs/prior-art.md:89-94`.
- [MATCH] original rendering exactly 2 tokens below logged in 24 of 24: `rederive_w.txt:41-43`.
- [MATCH] same tool as the real run in 83%: `w/analyze_w.txt:39` (83.1%).
- [MATCH] v28 rendering 1.7% smaller (median): `w/analyze_w.txt:2` (1.66%).
- [MATCH] agreement 76%: `w/analyze_w.txt:38` (76.2%).
- [MATCH] caps of 150 lines and 10,000 characters per read: `prereg/02` (Outcomes, second clarification); `fork_states.py:58`.
- [MISMATCH] seven pre-registrations (`prereg/02` to `07`): item 5.
- [WORDING] every registered number re-derived: item 20.
- [WORDING] no contrast mixes runs: item 21.

### 4.1 One step

- [MATCH] ten arms, 12,210 replays, 388 complete states: `analyze_b.txt:1,3`.
- [MATCH] A 2.15%: `explore_b.txt:19`.
- [MATCH] P 3.01%, H 2.75%: `explore_b.txt:20,22`.
- [WORDING] +0.8 pooled [−0.1, 1.7] on another state set: item 22 (value matches `analyze_a.txt:23`).
- [MATCH] following test not met, discrimination not tested: `prereg/02` (Power: "does not test H2" if H1 fails).
- [WORDING] channel makes no difference: item 23 (value +0.25 [−0.7, 1.2] matches `analyze_a.txt:28`).
- [MATCH] D − H +1.55 [0.60, 2.66]: `analyze_b.txt:39`.
- [MATCH] wider scoring +0.77 [−0.52, 2.06]: `recount_b_outcomes_diff.txt:28`.
- [MATCH] E 8.25%; E − H +5.50 [3.44, 7.65]: `analyze_b.txt:13,44`.
- [ROUNDING] 41 vs 14 states, p = 5e-7: printed p = 4.6e-07 (`explore_b.txt:208`; `rederive_s5.txt:98`).
- [MATCH] each seed, each cut point, either repository out, by task [2.16, 9.15], independent recount: `explore_b.txt:173,190-202`; `recount_b_outcomes_diff.txt:30`.
- [ROUNDING] +2.4 to +2.7 without the five top tasks: stored outputs give +2.37 (`explore_b.txt:377`) and +2.62 (`rederive_s5.txt:96`); the upper end +2.74 is from a diagnostic run reported in `rederive_s5_vs_draft.md:61`.
- [MATCH] R_D 0.52%, R_E 1.03% of their own entries: `analyze_b.txt:54-55`.
- [WORDING] "A rewired list is not followed": item 24.
- [MATCH] E − R_E +7.22 [4.64, 9.97], rule met: `analyze_b.txt:58`; `prereg/03` (B4: at least 3 points, interval excluding 0, one dose).

### 4.2 Other settings

- [MATCH] PE 9.61%, P 3.26%, PE − P +6.35 [4.34, 8.52]: `d1/analyze_d1.txt:10,15,27`.
- [MATCH] PE − E +1.59 [−0.33, 3.43]: `d1/analyze_d1.txt:28`.
- [MATCH] 26B-A4B 6.88% vs 3.36%, +3.53 [1.51, 5.54]: `d2_26b/analyze_d2_26b.txt:16,21,34`.
- [MATCH] E4B 8.20% vs 5.14%, +3.06 [1.09, 5.03]: `d2_e4b/analyze_d2_e4b.txt:16,21,34`.
- [MATCH] rented GPU +5.58 [3.67, 7.58]: `c/gates_c.txt:9`.
- [MATCH] original rendering +5.17 [3.33, 7.17]: `w/analyze_w.txt:27`.
- [MATCH] Figure 3a, six settings: `paper/figures/make_figures.py:832-839` (FOREST, six rows).

### 4.3 Parts of an entry, false entry

- [MATCH] EL 7.75%, ES 3.08%, H 3.00%, E 8.58%: `c/analyze_c.txt:14-18`.
- [MATCH] EL − H +4.75 [3.00, 6.58]; ES − H +0.08 [−0.75, 0.92]: `c/analyze_c.txt:31-32`.
- [MATCH] E − EL +0.83, 90% [−0.17, 1.83], sufficient: `c/analyze_c.txt:37`; rule `prereg/04` (C2).
- [MATCH] true entry 23 of 1,200, decoy 1, +1.83 [0.83, 3.17]; "checks the edge" by rule (1% floor met, 1.92%): `c/analyze_c.txt:20,23,26`; `rederive_c.txt:81`.
- [WORDING] "A false entry is not followed": item 25.

### 4.4 Five calls

- [MATCH] 2,968 replays: `k/analyze_k_extra.txt:1`.
- [MATCH] 57 complete states of R: `k/analyze_k.txt:1`.
- [MATCH] 69.8%, 66.0%, 61.1%: `k/analyze_k.txt:4-6`.
- [MATCH] K1 +3.86 [−1.05, 8.77], no detectable gain: `k/analyze_k.txt:8`; `k/analyze_k_extra.txt:19,23`.
- [MATCH] 63.5% vs 53.0% by call 3, +10.5 [2.1, 19.3]: `k/explore_k.txt:6`.
- [MATCH] 114 states; changed file opened 22.5% vs 14.0%; no harm by K2: `k/analyze_k.txt:30,32,35`; `k/analyze_k_extra.txt:24`.
- [MATCH] rewired list 21.6%: `k/analyze_k.txt:33`.

### 5. What the encoding changes (exploratory)

- [MATCH] any means A 5.2%, H 9.9%, D 12.9%, E 12.4%; H − A +4.64 [2.66, 6.79]; E − D −0.52 [−2.58, 1.46]: `explore_b.txt:44-51,70,73`.
- [MATCH] read covers the entity 37% to 49% in every arm but E; E 70% [56, 82]: `explore_b.txt:128-137`.
- [MATCH] all but three of 107 hits in A, H, D are a `read_file` from the top: `explore_b.txt:233,242` (104 of 107).
- [MATCH] 47 of 96 E hits start at a listed line: `explore_b.txt:234-235` (34 + 13).
- [MATCH] tool channel 44% and 68%; 26B-A4B 49% and 72%; E4B 47% and 55%: `explore_mechanism.txt:4-5,17-18,28-29`.
- [MATCH] rank 1 +4.1, ranks 2 to 3 +1.7, rank 8+ +0.4: `explore_b.txt:259-262`.
- [MISMATCH] ranks 4 to 7 +1.0: item 6.
- [WORDING] "List position matters": item 26.
- [MATCH] the tool sorts alphabetically [4]: `docs/prior-art.md:101-104`; `rederive_s5_vs_draft.md:77`.
- [MATCH] matched E − H +2.32 [1.12, 3.69]; true minus rewired +1.46 [0.00, 3.01]: `explore_b.txt:320,323`.
- [MATCH] 26B-A4B 0.34% with or without the rewired list; E4B 2.84% vs 0.66%, +2.19 [0.87, 3.83]: `explore_mechanism.txt:20,23,31,34-35`.
- [MATCH] `start_line"` and the dropped argument: `rederive_w.txt:97-99`; `prereg/07` (Why, item 1).
- [WORDING] "traces this to the harness change of Sep 30": item 27.
- [MATCH] 36.1% vs 0.3% of bounded first reads; 18.3% vs 0.2% of replays; +18.2 [14.8, 21.8]; original runs 1.0%: `w/analyze_w.txt:15-20`.
- [MATCH] 14.4% of 4,655 ranged reads; 658 from line 1: `k/explore_k.txt:36`.
- [MATCH] no-list arm 25% to 41%; legible note 6% to 10%: `k/explore_k.txt:28,30,32,34`.
- [WORDING] "any note helped in Section 4.4": item 28.
- [MATCH] the other two models never do it: `mangled_args_counts.txt:30-38` (0 of 2,572 and 0 of 1,466).
- [MATCH] E − H +5.50 becomes +5.58 with the bound honored: `mangled_sensitivity.txt:14`.

### 6. What it means

- [WORDING] "not a failure ... to tell a true edge from a false one": item 29.
- [MATCH] three times as often at the next call: item above (96/32).
- [WORDING] "ten points more often by the third, and no more often by the fifth": item 30.
- [MATCH] recommendation 1, definition line can be left out: C2 sufficiency (`c/analyze_c.txt:37`).
- [WORDING] "As it stands, a third ... return the wrong lines": item 31.
- [MATCH] the list is alphabetical and following falls with rank: `explore_b.txt:259-262`.
- [WORDING] "did not make wrong edges actionable for the two larger models": item 24.
- [MATCH] the smallest model follows a rewired list: `explore_mechanism.txt:35`.

### 7. Related work (claims checked against `docs/lit/` and `docs/prior-art.md`)

- [MATCH] [5, 6] encoding changes LLM behavior on static graph tasks: `docs/prior-art.md:54-57`.
- [MATCH] [7] v2: pre-registered, placebo-controlled scale study; prints signatures and paths; arms vary the tool set; placebo replaces every entity for whole episodes, scored by final localization: `docs/lit/2026-11-10-bellam-v2-check.md` (b), (c) items 1 and 2.
- [MATCH] [8] v1: forcing the graph call does not help; agents expand once and stop (v1 only): `bellam-v2-check.md` (b); `related-work-check.md` rows 10-11 (forcing tested at 4B and 8B).
- [MATCH] [9] LocAgent compares six text formats (App. A.1.2): `related-work-check.md` row 17.
- [MATCH] [10] LARGER appends callers and callees to grep output, one format: `docs/lit/2026-11-10-larger-check.md` (b), and its claim 3.
- [MATCH] [11] RepoNav, [12] repository views, [13] tool architectures: `related-work-check.md` rows 13-15.
- [MATCH] [14] adding call edges to a signature map does not help: `related-work-check.md` row 16 (the suggested wording is used).
- [MATCH] [15] pushed corrupted search results adopted more than tool-returned ones on this model: row 19 (suggested wording used).
- [MATCH] [16] harness-inserted tool result trusted like a real call: row 20.
- [WORDING] [17] "small agents copy a graph-learning tool's often wrong labels": item 32.
- [MATCH] [18] fork designs in scientific QA; [19, 20] after compaction: rows 22-24.
- [MATCH] [2] GraphLoc asks about localization and repair; [21] GraphAudit retrieval with the rewiring control: rows 25-26.
- [MATCH] [4] forum posts audit the graph tools; [3] three encodings on 30 fixed edit contexts: `docs/prior-art.md:95-104`.
- [MATCH] novelty sentence: the form recommended in `bellam-v2-check.md` (e) item 5 and `larger-check.md`.

### 8. Limitations and Reproducibility

- [MATCH] 49 overflowed five-call replays: `k/analyze_k_extra.txt:4-11` (28 in R, 21 in U); `rederive_k.txt` S1 (ContextWindowExceededError 49).
- [WORDING] "two repositories": item 33.
- [MATCH] arm E rerun twice, 8.0% and 8.6% against 8.25%: `d1/analyze_d1.txt:20` (96/1197); `c/analyze_c.txt:15` (103/1200).
- [MATCH] hosted arms in three sessions: `explore_b.txt:4`.
- [MISMATCH] seven pre-registrations (Reproducibility): item 5.
- [MATCH] nine runs: Appendix B rows; nine `forks/` directories with results (v5, v6, v8, c, d1, d2_26b, d2_e4b, k, w).

### References against `paper/references.md`

- [MATCH] [1] competition citation, ten authors: `references.md:58`.
- [MATCH] [2] GraphLoc: title and user match `references.md:52` (the draft adds a "GraphLoc:" prefix and dates it Sep 2026; notebooks Sep 25 to 27).
- [UNSOURCED] [3], [4], [10] absent from references.md: item 12.
- [MATCH] [5] Talk like a Graph; [6] KG-LLM-Bench: `references.md:10,13`.
- [MATCH] [7] Bellam v2 title, [8] v1 title: `references.md:16-17` (the entry names both titles; see item 12 for the stale note).
- [MATCH] [9] LocAgent, ACL 2025, arXiv 2503.09089: `references.md:19`.
- [MATCH] [11] to [20]: authors, titles, ids and years match `references.md:22-50`.
- [MATCH] [14] concept DOI 10.5281/zenodo.23927441 is valid; the version read is 23927442 (`references.md:31-32`).
- [MATCH] [21] GraphAudit, author and URL not recorded: `references.md:55-56`.

### Appendix A

- [MATCH] 02 following +0.8 [−0.1, 1.7], not met: `analyze_a.txt:23`.
- [MATCH] 02 discrimination not tested: `prereg/02` (Power).
- [WORDING] 02 channel outcome "no difference": item 23.
- [MATCH] 03 B1 +1.55 [0.60, 2.66], met; wider scoring +0.77 [−0.52, 2.06]: `analyze_b.txt:39`; `recount_b_outcomes_diff.txt:28`.
- [MATCH] 03 B2 0.34%, underpowered (5% floor): `analyze_b.txt:40`; `prereg/03` (B2).
- [MATCH] 03 B3 +5.50 [3.44, 7.65], met: `analyze_b.txt:44`.
- [MATCH] 03 B4 +3.78 [2.15, 5.67] and +7.22 [4.64, 9.97], met; matched +1.46 [0.00, 3.01]: `analyze_b.txt:57-58`; `explore_b.txt:323`.
- [MATCH] 04 G1 1.66%, passed: `c/gates_c.txt:1`.
- [MATCH] 04 G2 +5.58 [3.67, 7.58], passed: `c/gates_c.txt:9`.
- [MATCH] 04 C1 rule and result: `prereg/04` (C1); `c/analyze_c.txt:26`.
- [MATCH] 04 C2 rule and results: `prereg/04` (C2); `c/analyze_c.txt:31-37`.
- [MATCH] 05 T1 +6.35 [4.34, 8.52], met: `d1/analyze_d1.txt:27`.
- [MATCH] 05 T2 +1.59, 90% [0.00, 3.17], not shown: `d1/analyze_d1.txt:29`.
- [MATCH] 05 M1 26B-A4B +3.53 [1.51, 5.54]; E4B +3.06 [1.09, 5.03]: as in 4.2.
- [UNSOURCED] 06 gate 44 of 44: item 9.
- [MATCH] 06 K1 +3.86 [−1.05, 8.77], by task [−0.80, 9.63], not met; rule "robust only if also by task": `k/analyze_k_extra.txt:19-20`; `prereg/06` (K1).
- [MATCH] 06 K2 +8.48 [3.22, 14.04], no harm: `k/analyze_k.txt:35`.
- [MATCH] 07 F1 0.03% (2 tokens in 24 of 24), met: `w/analyze_w.txt:3`; `rederive_w.txt:43`.
- [MATCH] 07 F2 +18.17 [14.75, 21.75], met: `w/analyze_w.txt:19`.
- [MATCH] 07 F3 +5.17 [3.33, 7.17], met: `w/analyze_w.txt:27`.

### Appendix B

- [MATCH] hosted 1: 6,105 replays, four L4, 4.1 h: `v5/forks/summary.json` (rows 6105, elapsed 14,677 s); `v5/forks/versions.json` (gpu).
- [MATCH] hosted 2: 3,663, 3.0 h: `v6/forks/summary.json` (10,856 s).
- [MATCH] hosted 3: 2,442, 2.3 h: `v8/forks/summary.json` (8,215 s).
- [MATCH] 388 complete; 34 failures (24 malformed, 10 no call): `explore_b.txt:5-6`.
- [MATCH] parts and false entry: 6,105 replays, 400 complete, 12 failures: `c/analyze_c.txt:1-9`.
- [UNSOURCED] 3.6 h in two containers: item 10.
- [MATCH] tool channel: 3,663, 1.9 h, 399, 11: `d1/forks/summary.json` (6,725 s); `d1/analyze_d1.txt:2-6`.
- [MATCH] 26B-A4B: 4,884, 1.6 h, 397, 20: `d2_26b/forks/summary.json` (5,750 s); `d2_26b/analyze_d2_26b.txt:2-7`.
- [MATCH] E4B: 4,884, 2.7 h, 305, 326: `d2_e4b/forks/summary.json` (9,614 s); `d2_e4b/analyze_d2_e4b.txt:2-7`.
- [MATCH] E4B failures nearly all malformed `edit_file` calls: indirect; 319 of 326 are malformed (`d2_e4b/analyze_d2_e4b.txt:3-6`) and every one of the ten most frequent bad argument names is on `edit_file` (`rederive_d2_e4b.txt:87`); no per-tool split of the 319 is printed.
- [MATCH] five calls: 2,968, 4.6 h, 57 of 74 and 114 of 124, 49 overflows, 2 malformed: `k/forks/summary_k.json` (16,435 s); `k/analyze_k_extra.txt:4-16`.
- [MATCH] rendering: 4,884, 2.6 h, 400, 10: `w/forks/summary.json` (9,298 s); `w/analyze_w.txt:8-12`.
- [MATCH] 39,598 replays in all: sum of the nine rows.
- [MATCH] seeds 1 to 3, 1 to 5 in R: `versions*.json`; `rederive_k.txt` S0.
- [MATCH] v28 with adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7, google-adk 1.36.1, vLLM 0.19.1: rented `pip_freeze*.txt`; hosted v5 and v8 logs.
- [WORDING] pip_freeze for every run: item 34.
- [MATCH] Modal, Python 3.12.1, tensor-parallel 1, torch 2.10.0; hosted tensor-parallel 4, torch 2.10.0+cu128: `c/forks/versions.json`; `v5/forks/versions.json`; `analysis/kaggle/forks_pilot.py:101`.
- [MATCH] token-for-token prompt sizes on the 24 fidelity states: replayed tokens in `c`, `d1` and `w` `fidelity.jsonl` equal `v5/forks/fidelity.jsonl` in 24 of 24 (computed for this audit).
- [MATCH] second models unquantized: `prereg/05` (amendment).

### Appendix C

- [MATCH] recount of 46,560 cells; 28 differ, all shell searches; B1 +1.55 [0.43, 2.75], B3 +5.33 [3.35, 7.30], B4 +4.04 and +7.22: `recount_b_outcomes_diff.txt:28-32,44-45`.
- [MATCH] wide reading: A 3.5%, E 9.1%; +4.73 [2.75, 6.70]; +4.47, +7.90; B1 +0.77 [−0.52, 2.06]: `recount_b_outcomes.txt:6,13`; `recount_b_outcomes_diff.txt:28-32`.
- [MATCH] by task E − H +5.50 [2.16, 9.15], E − R_E +7.22 [2.97, 12.07]: `explore_b.txt:173,176`.
- [ROUNDING] McNemar 41 and 14 states, 29 vs 2, p = 5e-7: `explore_b.txt:208` (4.6e-07).
- [MATCH] positive in each seed, each cut point, repositories left out (+3.1, +7.7), any task left out: `explore_b.txt:190-202`.
- [MATCH] without the five top tasks +2.37 [0.85, 4.07] at the low end: `explore_b.txt:377`.
- [MATCH] R_D − A +0.17 [−0.86, 1.29]; R_E − A +0.26 [−0.60, 1.12]: `explore_b.txt:398-399`.
- [MATCH] rented E 8.02% and 8.58%; drift +0.58 [−0.41, 1.57] and +0.25 [−0.33, 0.82]: `d1/analyze_d1.txt:20`; `c/gates_c.txt:10-11`.
- [MATCH] matched entries 3,292 of 3,704; E 2.49% [1.20, 3.87]; E − H +2.32 [1.12, 3.69]; +1.46 [0.00, 3.01], −0.09 independently; +0.34 [−0.60, 1.29] under D: `explore_b.txt:312-323`; `rederive_s5.txt:188`.
- [MATCH] five of R_E's 12 hits start at a listed first line: `rederive_s5.txt:134`.
- [WORDING] 847 padded entries in 298 states: item 35.
- [MATCH] thoughts 10.8%, 12.2%, 11.0%; E − H +0.21 [−1.00, 1.53]: `explore_b.txt:280,282,284,287`.
- [UNSOURCED] toward the fix, read_file only: item 8.
- [MATCH] toward the fix, any read, edit or view: 6.9%, 7.2%, 9.4%, 8.5%; E − A +1.63 [−0.26, 3.61]: `rederive_s5.txt:205-215`.
- [MATCH] prompt cost about 620, 400 and 270 tokens: `c/analyze_c.txt:48-52` (8,207 − 7,586 = 621; 7,983 − 7,586 = 397; 7,857 − 7,586 = 271).

### Appendix D

- [MATCH] mangled-name definition and the ADK filter: `prereg/07` (F2); `rederive_w.txt:13`.
- [MATCH] hosted first-call rows (A 589/211 35.8%, P 481/83 17.3%, H 504/69 13.7%, D 571/82 14.4%, E 634/31 4.9%, R_D 522/77 14.8%, R_E 508/24 4.7%): `mangled_args_counts.txt:13-24`.
- [MATCH] tool-channel rows (P 460/77, PE 585/36, E 636/28): `mangled_args_counts.txt:26-28`.
- [MATCH] rendering-run rows (A 610/220 36.1%, Aw 595/2 0.3%, Hw 501/7 1.4%, Ew 631/1 0.2%): `w/analyze_w.txt:15-18`.
- [MATCH] 26B-A4B 2,572 and E4B 1,466 bounded reads, 0 mangled: `mangled_args_counts.txt:30-38`.
- [MISMATCH] original runs at the same states, 201: item 7.
- [MATCH] all 318 base traces: 2,012 bounded reads, 42 mangled (2.1%), each from line 1: `mangled_args_counts.txt:2-5`.
- [MATCH] five calls: 4,655, 668 (14.4%), 658 from line 1: `k/explore_k.txt:36`.
- [MATCH] `start_line"` now, a backslash form under the original rendering: `rederive_w.txt:97-104`.
- [MATCH] per-arm five-call rates 40.6/25.1, 22.2/9.4, 6.3/9.6, 9.0/6.9: `k/explore_k.txt:28-35`.
- [MATCH] bound honored: E 8.25% to 8.33%, bare-name arms unchanged, E − H +5.58, PE − P +6.77: `mangled_sensitivity.txt:4-14,23`.
- [WORDING] 1 of 577 under bare names: item 36.

### Appendix E

- [MATCH] R 74 states, 20 tasks, seeds 1 to 5; U 124 states, 30 tasks, seeds 1 to 3: `prereg/06` (Populations); `rederive_k.txt` S0.
- [MATCH] allowed calls: `prereg/06` (Design).
- [MATCH] all 198 checkouts unchanged: `k/forks/checkouts_k.jsonl` (198 rows, checkout_unchanged true in all).
- [UNSOURCED] 44 of 44 reads; 36, 18, 13 of 67 shell results: item 9.
- [MATCH] table, calls 1 to 5, A, H, E, R_E and E − H with intervals: `k/explore_k.txt:4-8`.
- [MATCH] U: file opened 14.0, 17.3, 22.5, 21.6%; line shown 10.2, 13.2, 15.2, 15.8%: `k/analyze_k.txt:22-25,30-33`.
- [ROUNDING] stop reasons: two thirds reach call 5 (65.2% to 66.7%), edit 11% to 13% (10.5% to 12.9%), write 11% to 13% (11.2% to 12.6%), shell 7% (6.5% to 7.3%), graph 2% to 4% (1.9% to 4.0%): `k/analyze_k.txt:40-43`.
- [MATCH] sensitivity K1 +1.92 [−2.47, 6.58], K2 +7.53 [2.69, 12.90]: `k/analyze_k_extra.txt:66,70`.

### Appendix F

- [MATCH] item 3, failed fidelity gate 6.1%: `prereg/02` (Run record).
- [MATCH] item 5, 16 in flight, 9-hour budget, finished in 4.6 h: `prereg/06` (amendment); `k/forks/summary_k.json`.
- [UNSOURCED] item 6, 2,946 saved replays: item 11.

## Status counts

| Status | Count |
|---|---|
| MATCH | 161 |
| ROUNDING | 7 |
| MISMATCH | 8 |
| UNSOURCED | 6 |
| WORDING | 26 |

(The counts are of the lines in the full list; several lines group a few numbers from one source. MISMATCH
counts item 5 twice (Section 3 and Reproducibility), UNSOURCED counts item 9 twice (Appendix A and E), and WORDING
counts items 23 and 24 twice, where the same phrase appears in two sections. Distinct problems: 7 MISMATCH, 5
UNSOURCED, 24 WORDING, listed as items 1 to 36 in the table above.)
