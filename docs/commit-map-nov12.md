# Commit hashes before and after the history rewrite of Nov 12, 2026

On Nov 12, 2026, before the repository was made public, its history was rewritten with `git filter-repo` to remove
private strings (personal names, a personal e-mail address as commit author, local folder paths, a Kaggle user
name, assistant trailers in commit messages) and four state files that held the competition's task statements
(`analysis/fork_states/states.jsonl`, `analysis/fork_states_c/states.jsonl`, `analysis/fork_states_d/states.jsonl`,
`analysis/fork_states_g/fresh_states.jsonl`; the competition data may not be redistributed). Author and committer
dates were kept, so the times of the pre-registrations are unchanged. No file under `prereg/`, `analysis/results/`
or `paper/` changed; every analysis script is unchanged.

A rewrite changes every commit hash. Files written before Nov 12 (the pre-registrations and their dated notes,
`NOTES.md`, `LOG.md`, stored reports) cite the old hashes; they were not edited, so that no registration carries a
change made after its run. Use this table to find the commit an old hash names. The four state files are rebuilt
from the competition data by the scripts named in the README; their md5 sums, cited in some registrations, are
those of the rebuilt files.

| Old | New | Author time | Subject |
|---|---|---|---|
| `41cb6cb` | `d2695cd` | 2026-09-30 16:16:20 -0400 | Project skeleton: brief, prior art, ideas, methods, working rules, competition facts |
| `e74bcc5` | `670c283` | 2026-09-30 16:45:54 -0400 | Full Kaggle read: rules, harness facts, GraphLoc overlap, context-overflow bottleneck; direction pending |
| `9570ed9` | `95d6c42` | 2026-09-30 18:45:45 -0400 | Claude Science kickoff message; keep private/ (origin transcript) out of git |
| `d6bc7dd` | `ede2b81` | 2026-09-30 18:49:41 -0400 | Remove personal names and attributions from repo content and issues |
| `ab00d3d` | `8ef0a2b` | 2026-09-30 18:55:21 -0400 | Shared agent instructions (CLAUDE.md), dataset verified, kickoff file-access check |
| `29a3b28` | `bc6c0eb` | 2026-09-30 19:06:03 -0400 | Names where they fit (team line); never attribute ideas to individuals |
| `bb48374` | `e21cdc5` | 2026-09-30 21:45:36 -0400 | Phase-0 offline checks, review replies, kickoff update, Claude Science log |
| `2b6fc90` | `9c48e13` | 2026-11-08 18:44:21 -0500 | Lit sprint, fork states, replay runner, pre-registration 02, Kaggle pilot |
| `9245c23` | `6e1e964` | 2026-11-08 19:03:04 -0500 | Fix review blockers: budget check inside the semaphore, content-only touch rule with head/tail ranges, malf... |
| `c17e008` | `21fef43` | 2026-11-08 19:11:54 -0500 | Review round 2 and audit: full argument validation, head/tail/sed ranges, fresh swapped-out entries, harnes... |
| `8a4ebb2` | `c4fa0ad` | 2026-11-08 19:21:21 -0500 | Review round 3: pipeline-aware shell view ranges, strict read-range validation, no estimate without eligibl... |
| `e3b0da1` | `9ac0803` | 2026-11-08 19:31:37 -0500 | Review round 4: harness read and stdout caps define what is shown and what a replay touches; 407 states |
| `cc04ce6` | `754784e` | 2026-11-08 19:42:06 -0500 | Review round 5: workspace path normalization, signed head/tail counts, parser control-flow fix with unit cases |
| `1022505` | `3f15d72` | 2026-11-08 19:48:36 -0500 | Paper draft: question, trace facts, method, related work; results pending |
| `50e0d05` | `1957f9e` | 2026-11-09 00:23:28 -0500 | Run v4 outputs and analysis (fidelity gate failed: re-sent thoughts); replay no longer re-sends thoughts; v... |
| `5ad5b6d` | `6e8e17f` | 2026-11-09 07:39:42 -0500 | Confirmatory run v5: outputs, analysis, notes (fidelity pass; following near base rate in every arm) |
| `03079a5` | `c4ab24f` | 2026-11-09 12:23:07 -0500 | Paper draft with the confirmatory results, implications and abstract |
| `55a9c1b` | `1815dad` | 2026-11-09 12:49:23 -0500 | Pre-registration 03 (directive and encoding arms): arms D, D', E in the states, replay generalized, Kaggle ... |
| `937205a` | `55004d1` | 2026-11-09 12:51:07 -0500 | Untrack the review hook's note; correct the freeze time in pre-registration 03 |
| `6137a23` | `f9a422b` | 2026-11-09 12:55:28 -0500 | Pre-registration 03 amendment: rewired-graph control arms R_D and R_E (degree-preserving rewiring, padded, ... |
| `22677df` | `d70e22e` | 2026-11-09 12:59:30 -0500 | Rewired control: entries held to the true-entry eligibility (unopened, non-gold files); states re-exported;... |
| `cef968b` | `2898e3a` | 2026-11-09 13:02:02 -0500 | NOTES: experiment B running, rewired control pushed, corrections |
| `f43edd3` | `da7063e` | 2026-11-09 21:21:26 -0500 | Pre-registration 04: experiment C (arms Ep, EL, ES), frozen before any replay of these arms; platform gates... |
| `9b5a95c` | `e52530d` | 2026-11-09 23:12:09 -0500 | Experiment B: v6 and v8 run outputs, independent recount, exploratory robustness tables, experiment C state... |
| `073e10f` | `072f809` | 2026-11-09 23:18:14 -0500 | Paper draft rewritten around experiment B (registered table recounted independently; exploratory section st... |
| `4e13a40` | `3298b1b` | 2026-11-09 23:36:54 -0500 | Blind re-derivation of sections 4 and 5 of the draft; draft corrected where it differed (run count, toward-... |
| `e847c40` | `875edc5` | 2026-11-09 23:51:29 -0500 | Draft: state the two eligibility filters and the gap to the pre-registration wording; correct the descripti... |
| `cec7488` | `d316669` | 2026-11-10 01:11:37 -0500 | Audit numbers re-derived blind; claims about other work checked and corrected in the draft (GraphLoc arm, L... |
| `962baa3` | `04ad1d5` | 2026-11-10 01:24:23 -0500 | Citation check of the draft: 28 claims about other work against reading notes and full texts |
| `2662c01` | `e67d259` | 2026-11-10 02:07:43 -0500 | Pre-registration 05: experiment D (arm PE, the legible list as the tool's own result; a second model), froz... |
| `cfb353a` | `c975499` | 2026-11-10 02:25:07 -0500 | Figures: method schematic with the two list formats; registered outcome by arm and file-level versus line-l... |
| `b5742d9` | `6a9046a` | 2026-11-10 02:29:41 -0500 | Draft: cuts and ten fixes from an editing pass (abstract caveat on the rewired rates, audit wording, list p... |
| `fc5245f` | `71c4af1` | 2026-11-10 02:41:28 -0500 | Modal runner used for experiment C: wrapper, runner derived from the hosted script, list of substitutions |
| `431b9c7` | `2f40fc6` | 2026-11-10 02:43:16 -0500 | Pre-registration 06: experiment E (navigation horizon of five model calls with read-only tools executing), ... |
| `15f9a03` | `09bf055` | 2026-11-10 02:47:46 -0500 | Pre-registration 05, amendment: the 12B model cannot be served by the pinned server (no replay ran); D2 run... |
| `bafbe85` | `b16fc37` | 2026-11-10 03:04:02 -0500 | Pre-registration 06, amendment before the full run: platform fidelity gate passed; 16 replays in flight, 4 ... |
| `e78690f` | `9e2b6ec` | 2026-11-10 04:52:09 -0500 | Experiment D1 (tool channel): raw replay outputs and the registered analysis output; supplement to the expe... |
| `98abc55` | `922ce01` | 2026-11-10 05:09:19 -0500 | Pre-registration 07: experiment F (earlier tool results rendered as the original runs' harness delivered th... |
| `aa89d67` | `c7ad516` | 2026-11-10 05:14:22 -0500 | Notes: D1 re-derived, second model 26B-A4B, mangled argument names, pre-registration 07, implementations of... |
| `9811ac2` | `48d7b63` | 2026-11-10 05:26:33 -0500 | Competition notes: paper-track pages read on Nov 10 (host rulings on word count, references, appendix, publ... |
| `572187b` | `27cb8f4` | 2026-11-10 05:34:59 -0500 | Prior art: competition forum threads read on Nov 10 (double-encoded tool results and their fix, a fixed-con... |
| `c93de5a` | `ff7c4d1` | 2026-11-10 05:35:12 -0500 | Prior art: dates of two forum threads stated as known |
| `e5fbf3c` | `006b913` | 2026-11-10 05:35:50 -0500 | References: competition citation as given on the overview page |
| `b45da79` | `f8f4d77` | 2026-11-10 05:49:07 -0500 | Second model E4B: raw outputs, registered analysis and independent re-derivation; figure code extended (for... |
| `e5281e5` | `888fd06` | 2026-11-10 05:49:34 -0500 | Notes: second model E4B, competition pages and forum threads, nearest paper's second version, reference lis... |
| `e18bd13` | `47c7bc5` | 2026-11-10 05:53:37 -0500 | Registered outputs of experiments A and B stored as text; exploratory script on where the first read lands ... |
| `3991a98` | `065b430` | 2026-11-10 11:11:47 -0500 | Experiment C, experiment F (rendering) and the five-call experiment: raw outputs, gates, registered analyse... |
| `c235eea` | `6bf5e67` | 2026-11-10 11:15:08 -0500 | Draft: appendix A to G (rules as text, runs, robustness, interface failures, the five-call experiment, devi... |
| `f368614` | `a1db30b` | 2026-11-10 11:17:15 -0500 | Draft: exact two-decimal values in the abstract, six pre-registrations (02 to 07), wording fixes; reproduce... |
| `3b429d3` | `bba9265` | 2026-11-10 11:23:25 -0500 | Figures: Figure 3 with all six settings, the parts of an entry and the false entry, and the five-call exper... |
| `ec96077` | `ebacb31` | 2026-11-10 11:31:19 -0500 | Draft after the number audit: rounding and count mismatches corrected, unsourced numbers removed or given a... |
| `d6e467e` | `abeee06` | 2026-11-10 11:35:42 -0500 | Stored output of the independent re-derivation of the rendering experiment rewritten from the script's own ... |
| `22ed2df` | `8b7440f` | 2026-11-10 13:29:14 -0500 | Pre-registration 08 frozen: experiment G (the argument defect in fresh episodes; a patched harness against ... |
| `d0cb5c0` | `50670a1` | 2026-11-10 13:46:47 -0500 | Pre-registration 08, amendment before any full-run replay of its parts fresh and fix: the three graph tools... |
| `7166807` | `c3790e3` | 2026-11-10 13:47:17 -0500 | Experiment G runner: smoke mode prints the result status of graph-tool calls (print only); hash recorded in... |
| `ff73b54` | `5c051b7` | 2026-11-10 13:47:29 -0500 | Pre-registration 08: the time of the last amendment line corrected to the commit's time (1:47 PM, was writt... |
| `88b412e` | `d108251` | 2026-11-10 13:48:45 -0500 | Exploratory: what a mangled line bound costs inside the five-call run (the next call re-reads the same file... |
| `e039df8` | `109181c` | 2026-11-10 13:55:05 -0500 | Pre-registration 08: second smoke test recorded; the wrapper takes an output folder so the parts fix and fr... |
| `7c268ed` | `2608aba` | 2026-11-10 14:04:37 -0500 | Pre-registration 09 frozen: fresh episodes on the newest harness wheels with the graph tools' answers as sh... |
| `ea863ab` | `1ba9aae` | 2026-11-10 14:05:31 -0500 | Exploratory supplement from the stored raw outputs: every registered contrast clustered by task, the false-... |
| `90a0190` | `278a21b` | 2026-11-10 14:13:43 -0500 | Notes: blind reviews, the harness-version fact, pre-registrations 08 and 09 with their smoke tests, the cos... |
| `2314bea` | `482d372` | 2026-11-10 14:14:31 -0500 | Pre-registration 09: smoke test recorded before the full run; nothing changed |
| `888aebc` | `7fd07cc` | 2026-11-10 14:14:54 -0500 | Pre-registration 09: two tool names restored in the smoke-test note (the shell had swallowed them when the ... |
| `04e3645` | `fff3c0f` | 2026-11-10 14:18:01 -0500 | Exploratory: the one-step replays restated as first reads of a listed neighbor's file (without line numbers... |
| `142cd3c` | `304da17` | 2026-11-10 14:28:32 -0500 | Exploratory: what a name without an address costs in the five-call records (with bare names 248 of 261 firs... |
| `9e69baa` | `8fa8399` | 2026-11-10 14:28:32 -0500 | Prepared, not run: a copy of the one-step runner whose model-server parser settings come from the environme... |
| `6444cc9` | `ca1cb4a` | 2026-11-10 14:35:04 -0500 | Pre-registration 10 frozen: the second-model design of pre-registration 05 on a model of another family (Qw... |
| `053b3cb` | `b480c10` | 2026-11-10 14:36:43 -0500 | Pre-registration 10, amendment before any replay: the smoke test writes its rows to the volume so the gate ... |
| `31a34ab` | `a168f0b` | 2026-11-10 14:45:58 -0500 | Pre-registration 10, amendment after the first smoke test and before any model answer: the server refused e... |
| `d200f45` | `09f9527` | 2026-11-10 14:46:11 -0500 | Pre-registration 10: correct the time written in the last amendment (it was ahead of the clock); nothing el... |
| `c167f65` | `4eaf71e` | 2026-11-10 15:03:26 -0500 | Exploratory: other teams' public runs counted (where a first read of a file starts, by what the result just... |
| `a5156db` | `827f037` | 2026-11-10 15:10:10 -0500 | Pre-registration 10, amendment before the third smoke test: the server now accepts the requests, but this m... |
| `5ce7678` | `b8eba7b` | 2026-11-10 15:19:20 -0500 | Pre-registration 10, amendment before the fourth smoke test: some answers of this model do not end even wit... |
| `23974ea` | `0f6a7fa` | 2026-11-10 15:20:56 -0500 | Pre-registration 08, one-step part on the newest harness wheels (adk_submission 0.2.13, swegemma 0.2.11): r... |
| `7dc17da` | `ff3c6ab` | 2026-11-10 15:29:47 -0500 | Pre-registration 10, the gate: the fourth smoke test passes (usable A 21, H 20, E 21, RE 21 of 24; every fa... |
| `2e75dc2` | `cf2db14` | 2026-11-10 15:32:13 -0500 | Exploratory: the first-reads count with the newest-wheels run added (without line numbers 0 of 856 first re... |
| `8dd1331` | `48927e1` | 2026-11-10 15:39:35 -0500 | Figure script: loaders and checks for the one-step run on the newest harness wheels and for the run on a mo... |
| `e9efe31` | `247e488` | 2026-11-10 15:47:06 -0500 | Pre-registration 11 frozen: the reading rule tested on the fresh episodes of pre-registration 09 (first rea... |
| `ae8cd20` | `734bd9f` | 2026-11-10 15:49:19 -0500 | Pre-registration 11: the analysis script and its hash, recorded before any row of the run is fetched for an... |
| `849064e` | `d7ee1d2` | 2026-11-10 15:49:32 -0500 | Pre-registration 11: the amendment's time corrected to the minute of its commit (3:49 PM); nothing else cha... |
| `5bf6210` | `682f24e` | 2026-11-10 15:51:17 -0500 | Exploratory, public runs: malformed file reads split by kind (the third-party count of corrupted argument k... |
| `d2b13f0` | `06d5d11` | 2026-11-10 15:51:56 -0500 | Figure script: conditions are named in words in the result figures (no list, bare names, addresses, rewired... |
| `e7c37b6` | `fb4a51b` | 2026-11-10 15:55:33 -0500 | Figure script: the method figure names its conditions in words; figure files not regenerated yet |
| `48012a3` | `bf69bd5` | 2026-11-10 15:56:41 -0500 | Exploratory: the second malformed file read (a path that swallowed the line bounds) counted in the one-step... |
| `8979dfd` | `c009fb3` | 2026-11-10 15:58:16 -0500 | Exploratory, public runs: an independent recount of the whole-run report (written from the rules without th... |
| `71e5dcf` | `8bf5443` | 2026-11-10 16:02:00 -0500 | Pre-registration 12 frozen: the one-step design with a list that gives each neighbor's file and no line ran... |
| `2543ad0` | `259835e` | 2026-11-10 16:09:08 -0500 | Pre-registration 12, the gate: the smoke test passes (24 of 24 replays with a call); the full run starts |
| `d391ec3` | `3bbbcac` | 2026-11-10 16:10:00 -0500 | Pre-registrations 08 (fresh part), 09 and 11: raw outputs of the fresh-episode run on the newest harness wh... |
| `e3c0c34` | `ec7fb04` | 2026-11-10 16:15:22 -0500 | Figure scripts: the first figure gains the fresh-episode rows (the registered test of the reading rule, and... |
| `20389ad` | `b98910b` | 2026-11-10 16:16:45 -0500 | Figure script for the run-level figure: fresh episodes call by call (pre-registration 09) beside public who... |
| `f195109` | `c0a8f0b` | 2026-11-10 16:21:29 -0500 | Notes: registered results on the newest wheels (S1, N1, A1, A2, R1, R2), pre-registrations 10 to 12, and th... |
| `b5ae947` | `a4bc345` | 2026-11-10 16:27:13 -0500 | Docs: how to use the replay tool (pieces, the shape of a paused state, a plumbing check without a GPU, runn... |
| `ef1323a` | `494b8ca` | 2026-11-10 16:39:26 -0500 | Independent re-derivation of pre-registration 11 with its stored output (same counts and verdicts; its head... |
| `40744f4` | `c89a68a` | 2026-11-10 16:40:23 -0500 | Independent re-derivation of the fresh-episode rules of pre-registrations 08 and 09, with its stored output... |
| `0f1f0ff` | `65a02be` | 2026-11-10 17:05:00 -0500 | Pre-registration 13 frozen: the address written as a search hit (one-step condition EG), with its states bu... |
| `7376794` | `0294c40` | 2026-11-10 17:08:51 -0500 | Exploratory, public runs: fix sites the agent never saw set against the code graph and degree-preserving re... |
| `eac8c06` | `6878c67` | 2026-11-10 17:15:00 -0500 | Pre-registration 13, amendment: the gate (smoke test) is passed; the full run starts |
| `763b099` | `20e8dcc` | 2026-11-10 17:16:44 -0500 | Runs of pre-registrations 08 (five calls) and 12 (a file without lines): raw outputs and the registered ana... |
| `92adee9` | `daaae11` | 2026-11-10 17:22:26 -0500 | Independent re-derivations with their stored outputs: pre-registration 08 (five calls and one step on the n... |
| `2dc3d55` | `9006c21` | 2026-11-10 17:34:59 -0500 | Exploratory, public runs: from a fix site the run had seen to the ones it missed, as a neighbor list would ... |
| `41a959d` | `ec4c41a` | 2026-11-10 17:36:17 -0500 | Exploratory: the call after a ranged read in the fresh episodes, by whether its line bound was mangled (scr... |
| `84b013d` | `d8d9361` | 2026-11-10 17:45:01 -0500 | Exploratory, public trajectories outside the competition: two more sources read through the dataset viewer ... |
| `6869be4` | `cb064ed` | 2026-11-10 17:57:21 -0500 | Exploratory, public runs: first reads after an answer of the public graph skill, split by whether the small... |
| `70684a1` | `0744db9` | 2026-11-10 18:15:16 -0500 | Exploratory, public runs: the kind of graph edge that joins a missed fix site to code the run had seen (cla... |
| `6ce3ac5` | `9e21775` | 2026-11-10 18:23:00 -0500 | Run of pre-registration 13 (the address written as a search hit): raw outputs and the registered analysis w... |
| `79346e3` | `1abc025` | 2026-11-10 18:28:00 -0500 | Pre-registration 14 frozen: whole runs scored by tests (the harness as shipped against the two changes of p... |
| `39df918` | `e9f7e6f` | 2026-11-10 18:30:04 -0500 | Independent re-derivations with their stored outputs: pre-registration 13 and the exploratory edge-kind cou... |
| `9066c68` | `2eac2e8` | 2026-11-10 18:34:22 -0500 | Exploratory: what the neighbor lists at the paused steps are made of (class members, callers, callees, test... |
| `397cfbe` | `5cafaf3` | 2026-11-10 18:38:24 -0500 | Search log for the reading rule, names against addresses and callers; exploratory whole-run report gains on... |
| `ee52866` | `9033fd8` | 2026-11-10 18:45:40 -0500 | Run of pre-registration 10 (a model of another family): raw outputs, the registered analysis and the indepe... |
| `6d88506` | `eb8517d` | 2026-11-10 18:50:00 -0500 | Notes: re-derivations, the results of pre-registrations 12, 08 (five calls), 13 and 10, the blind reviews o... |
| `b708e31` | `9a8f9ae` | 2026-11-10 18:54:22 -0500 | Exploratory edge-kind report: a section on links between entities that share a last name (earlier sections ... |
| `93bb254` | `6b4489b` | 2026-11-10 19:02:42 -0500 | Figures and tables redrawn from the stored reports: first reads by what the agent was shown (three bars per... |
| `5854aee` | `6940027` | 2026-11-10 19:18:23 -0500 | Stored outputs brought in line with what their scripts print now: the path-leak report includes the run of ... |
| `ed1ee5f` | `ec5b750` | 2026-11-10 20:17:28 -0500 | Run of pre-registration 14 (whole runs scored by tests): raw outputs without the task text, the registered ... |
| `4161535` | `7f5e881` | 2026-11-10 20:33:00 -0500 | Pre-registration 15 frozen: the agent's own search, with and without its line numbers (states maker, app, a... |
| `4cd4489` | `ff91ddd` | 2026-11-10 20:51:07 -0500 | Second scripts for the whole runs (pre-registration 14: same counts and verdicts) and for the split by kind... |
| `05696c5` | `be46721` | 2026-11-10 20:51:08 -0500 | Figures and tables for the rewritten text: a digest of the registered rules, Figure 5 by horizon with the w... |
| `7700e66` | `56ec45e` | 2026-11-10 21:18:00 -0500 | Pre-registration 16 frozen: how the task prompt describes the graph tools, and whether the agent asks (stat... |
| `97e8277` | `2bdfb30` | 2026-11-10 21:19:37 -0500 | Run of pre-registration 15 (the agent's own search, with and without its line numbers): raw outputs and the... |
| `e7f6816` | `0e4096c` | 2026-11-10 21:27:53 -0500 | Second script for pre-registration 15 (same counts and verdicts: Q1 met, Q2 not met, Q3 met); reproduce job... |
| `dc80da1` | `ec0ba35` | 2026-11-10 21:28:17 -0500 | Reproduce script: two job labels no longer break the file |
| `591f31c` | `a8d360b` | 2026-11-10 21:55:56 -0500 | Run of pre-registration 16 (the task prompt and the first model call): raw outputs and the registered analy... |
| `2b05555` | `2a390cf` | 2026-11-10 21:58:13 -0500 | Second script for pre-registration 16 (same counts and verdicts: W1 and W2 met, more graph calls with the S... |
| `06499db` | `1d276b2` | 2026-11-10 22:14:56 -0500 | Figures and tables with pre-registrations 15 and 16: three rows in the reading figure, five rows in the dig... |
| `964fe8c` | `1e8d6ee` | 2026-11-10 22:17:00 -0500 | Pre-registration 17 frozen: pre-registration 15 repeated on a model of another family (app, analysis wrappe... |
| `74fbefc` | `a45dde7` | 2026-11-10 22:38:08 -0500 | Run of pre-registration 17 (pre-registration 15 on a model of another family): raw outputs, the registered ... |
| `fc89514` | `443097e` | 2026-11-10 22:39:39 -0500 | Notes: the whole runs, pre-registrations 15, 16 and 17 with their second scripts, the second round of blind... |
| `dd354dc` | `631b68a` | 2026-11-10 22:46:45 -0500 | Tables with pre-registration 17: 45 rules in the full table, one more row in the digest and in the samples ... |
| `9a54136` | `ed64179` | 2026-11-10 22:47:20 -0500 | A table of every pre-registration's stated freeze time and commits, with the script that prints it from the... |
| `0c76d37` | `ee1fac6` | 2026-11-10 23:07:09 -0500 | Figure and table labels after a third round of blind reviews: what each variation is analyzed on, the title... |
| `dcd3538` | `68fc5b0` | 2026-11-10 23:13:58 -0500 | Exploratory count on the whole runs: runs shown every changed region against the others, with a stored outp... |
| `d012b88` | `d100f4a` | 2026-11-10 23:19:02 -0500 | Counts for a replay that was not run: steps where a recorded run first sees a fix site whose printed neighb... |
| `a44cd05` | `df2a22c` | 2026-11-10 23:37:12 -0500 | Exploratory: the code graph against rewirings that keep each edge's files or directories, for the fix sites... |
| `20f68b5` | `66ac75f` | 2026-11-11 00:42:48 -0500 | Exploratory: for the fix sites a public run never saw, which source would have held them (a file the run ha... |
| `bcc3c04` | `ed3fac5` | 2026-11-11 00:55:11 -0500 | Pre-registration 19, frozen before its full run: the two one-call contrasts (a name against an address; the... |
| `a2656c7` | `c82379c` | 2026-11-11 00:57:02 -0500 | Exploratory, the sources count: a section on the missed fix sites that no graph node covers, and how many o... |
| `6a4f782` | `afa06a1` | 2026-11-11 01:01:21 -0500 | Pre-registration 20, frozen before any replay with a model: the same search hits asked for by the agent or ... |
| `508e44c` | `565eb7f` | 2026-11-11 01:02:43 -0500 | Pre-registration 18, frozen before any session: whole runs on the 40 tasks whose shipped run was not shown ... |
| `cef6950` | `1a0d2d4` | 2026-11-11 01:02:43 -0500 | Exploratory: in the stored whole runs of 14, how many of the fix sites a run never saw lie in a file it had... |
| `26349a1` | `3a11324` | 2026-11-11 01:15:18 -0500 | Pre-registration 19: the stored rows of the seven hosted models, both designs, and the output of the regist... |
| `6721ded` | `0fb55cc` | 2026-11-11 01:19:44 -0500 | Pre-registration 19: both rules met in seven of seven hosted models (a name against an address, +2.0 to +10... |
| `823ce5a` | `a8523a3` | 2026-11-11 01:20:26 -0500 | The stored output of the independent script of 19 is now exactly what its reproduce job prints (two closing... |
| `a9b0041` | `53748c8` | 2026-11-11 01:21:37 -0500 | Exploratory: where every file read of eight sets of whole runs starts, and the changed regions by depth and... |
| `f56ff59` | `79d3225` | 2026-11-11 01:29:49 -0500 | Pre-registration 20: the stored rows (555 replays, every one usable) and the output of the registered analy... |
| `f40dec4` | `821025f` | 2026-11-11 01:34:07 -0500 | Pre-registration 20: told lines are used (+36.5 points), about two thirds as often as lines the agent searc... |
| `3c67a89` | `fd1b269` | 2026-11-11 02:06:29 -0500 | Exploratory, on the data alone: what an edge of the competition's code graphs is (edge types, pairs stored ... |
| `683ff2a` | `441e9f5` | 2026-11-11 02:25:40 -0500 | Pre-registration 18: the stored runs of the three arms (120 sessions, seed 2, prompts and the note replaced... |
| `966d515` | `42f5355` | 2026-11-11 02:26:29 -0500 | Pre-registration 18: told every changed place by file and lines the agent resolves 8 of 40 tasks against 2 ... |
| `7527b78` | `db04a1e` | 2026-11-11 02:33:12 -0500 | Pre-registration 22, frozen before any session and written after the result of 18 was seen: the same whole ... |
| `981dba6` | `75a1403` | 2026-11-11 02:44:55 -0500 | Five figures for the rebuilt paper, each number parsed from a stored output by the script: the two one-call... |
| `7bf2c16` | `a87af7a` | 2026-11-11 02:45:44 -0500 | Pre-registration 22: a dated note, added while the first shard runs and before any of its rows was read, na... |
| `0fa68b3` | `925c311` | 2026-11-11 02:50:29 -0500 | Exploratory counts on whole runs with their blind recounts (each re-run before this commit, identical outpu... |
| `d965cac` | `1c8bf21` | 2026-11-11 02:58:04 -0500 | Figures: the model figure shows every model the text counts (eleven for a name against an address, nine for... |
| `3401b98` | `488bcbd` | 2026-11-11 03:12:46 -0500 | Exploratory: in the runs of pre-registration 18, how each arm's runs end and what the runs that end on the ... |
| `25b9559` | `95a42b8` | 2026-11-11 03:17:23 -0500 | The table of registered rules for the rebuilt paper, drawn as an image with every estimate and verdict pars... |
| `04c8ea5` | `8391ad8` | 2026-11-11 03:19:46 -0500 | A table of the five populations of the rebuilt paper as an image, each size checked against a stored file |
| `611a436` | `f26bc54` | 2026-11-11 03:20:54 -0500 | Exploratory, with a blind recount: whether the changed regions of a fix are shown to a run independently of... |
| `5e9cfef` | `51c32b7` | 2026-11-11 03:23:21 -0500 | Figure: the second panel of the reads figure now compares fixes that lie in one file with fixes in several ... |
| `e29b2b2` | `36595f6` | 2026-11-11 03:26:51 -0500 | Dated notes on pre-registrations 18 and 20 (which harness release 20 ran on; which of the unread results in... |
| `7d50b75` | `2b54656` | 2026-11-11 03:27:13 -0500 | The table of freeze times, regenerated with pre-registrations 18 to 22 (the subject of the previous commit ... |
| `fdc4d3f` | `486017c` | 2026-11-11 04:41:11 -0500 | Pre-registration 22: the first of its two shards (20 of the 40 tasks, four arms) stored and analysed, no ru... |
| `3f65513` | `dda6228` | 2026-11-11 04:54:58 -0500 | Figures of the rebuilt paper: the oracle figure in three panels with both seeds on the same tasks; the rule... |
| `62fb391` | `5b51496` | 2026-11-11 04:58:37 -0500 | Pre-registration 24: asked or told on seven hosted models (the design of 20 through the API path of 19); ru... |
| `9e2d71c` | `39e9b38` | 2026-11-11 05:01:38 -0500 | The repository from a clean clone: reproduce.py lists and picks jobs and skips, with one line, a job whose ... |
| `a8194c9` | `dd885fb` | 2026-11-11 05:04:54 -0500 | Figures: the first-read count of the reads figure is the one a second script confirms (seven sets without t... |
| `eccc8f0` | `5115db1` | 2026-11-11 05:08:09 -0500 | Pre-registration 24: a dated note written after the sessions ended and before any row was pulled (what ASKE... |
| `825863f` | `30ff0fd` | 2026-11-11 05:15:35 -0500 | Pre-registration 24: the stored rows of the seven hosted models, the registered analysis, a second script w... |
| `18dacc8` | `38ddcb1` | 2026-11-11 05:15:49 -0500 | Pre-registration 24: a dated note on a stale first line of the registered script's report |
| `0de2362` | `72941a6` | 2026-11-11 05:17:15 -0500 | Exploratory, each re-run identical: the oracle runs with each task counted once over both seeds, with a rec... |
| `49ef2a3` | `a782413` | 2026-11-11 05:17:44 -0500 | Repair analysis/reproduce.py: the previous commit added a job label with an apostrophe inside a quoted stri... |
| `5c0fce4` | `cf59858` | 2026-11-11 05:18:27 -0500 | NOTES.md: the entry of Nov 11 (pre-registrations 18, 19, 20, 22 and 24, the exploratory counts, the rebuilt... |
| `48d1124` | `e16e521` | 2026-11-11 05:18:40 -0500 | Figures: pre-registration 24 in the asked-or-told figure (a panel with the seven hosted models) and in the ... |
| `dd77fbb` | `4b2fc45` | 2026-11-11 05:31:54 -0500 | The task-clustered bootstrap gains the three second-model runs of addresses against names and a line counti... |
| `96eae3b` | `247ba24` | 2026-11-11 05:34:11 -0500 | Figures: the sections of the populations table renumbered; the rules table gains the tool-result rule of 05... |
| `865efc4` | `6084063` | 2026-11-11 05:34:46 -0500 | Figures: the rules table gains the rule of 13 (the address written as a search hit) |
| `929aa2d` | `e77a80d` | 2026-11-11 15:05:51 -0500 | Pre-registration 23: whole runs in which the graph's own answers are pushed at the agent, as names or with ... |
| `f736fd1` | `3ddf480` | 2026-11-11 15:08:48 -0500 | Exploratory: how many of the regions a public run was never shown lie within reach of the code it was shown... |
| `f82e320` | `8c22330` | 2026-11-11 15:39:25 -0500 | Exploratory: a second script, written without sight of the first, recounts the regions a public run was nev... |
| `dd5c9a6` | `7e4fdf1` | 2026-11-11 15:42:46 -0500 | Pre-registration 23: a dated note (the launch waited for a free GPU of the registered type; when the two co... |
| `5e042fa` | `c12a149` | 2026-11-11 15:43:02 -0500 | Figures: the reach panel gains the name search without double-underscore names and in both directions, with... |
| `77c8ac3` | `7c8739d` | 2026-11-11 15:47:57 -0500 | Exploratory: a search for a name in both directions against the call edge, for the regions public runs were... |
| `21fdcc8` | `52fe475` | 2026-11-11 15:57:00 -0500 | Exploratory: the call edge and the name searches against a same-file stand-in for the missed function (a ne... |
| `d42a132` | `b8804e4` | 2026-11-11 16:03:11 -0500 | The second script of pre-registration 23, written from the registration without sight of the registered ana... |
| `3aa3f78` | `763a669` | 2026-11-11 16:21:16 -0500 | Figures: the rules table says what the whole-run test of 14 changed, reads the two-thirds rule as registere... |
| `c2ba710` | `b1ffde6` | 2026-11-11 17:05:00 -0500 | Pre-registration 23: a dated note, written before any stored row was pulled (one shard is slower and will s... |
| `06a10e0` | `493ce77` | 2026-11-11 17:08:21 -0500 | Figures: the rules table is ready for the three rules of pre-registration 23 (drawn only when its registere... |
| `df7150a` | `b6c19f7` | 2026-11-11 17:20:56 -0500 | Pre-registration 23: the stored runs of both arms (103 tasks each), the registered analysis, the second scr... |
| `c6e0a23` | `167b943` | 2026-11-11 17:24:40 -0500 | The table of registration commit times, regenerated (pre-registration 23 and its three dated notes) |
| `7b196d2` | `45c961f` | 2026-11-11 17:25:27 -0500 | NOTES: pre-registration 23, the recounts and counts on the public runs, the file-opening outcome, other ent... |
| `81b413a` | `36907a9` | 2026-11-11 17:33:54 -0500 | Exploratory: the two pushed arms of 23 beside the shipped run of the same seed on the 40 tasks that have on... |
| `ebbdae5` | `756b67d` | 2026-11-11 17:36:24 -0500 | Exploratory, written after the results of 23: the pushed arms beside the stored shipped run of 14 with its ... |
| `3b10833` | `d6ae9f3` | 2026-11-11 17:37:01 -0500 | Figures: the populations table gains the two other whole-run arms; the rules table puts the whole-run test ... |
| `c65b802` | `c2a39b0` | 2026-11-11 17:47:47 -0500 | Exploratory: the missed places behind an ambiguous short name, call edge against name search there (a new l... |
| `a8c836d` | `a8563de` | 2026-11-11 17:49:31 -0500 | Exploratory, written after the results of 23: the one-call outcome of the replays scored at the pushed list... |
| `b3c378f` | `a34f543` | 2026-11-11 17:52:35 -0500 | Exploratory: addresses against names in the replays and at the pushed lists of the whole runs, by how far i... |
| `a44535d` | `13f4bf8` | 2026-11-11 17:54:20 -0500 | Exploratory: how often an unaltered replay makes the recorded run's next call, beside how often two replays... |
| `c8d7a51` | `fcfccf2` | 2026-11-11 18:00:50 -0500 | Exploratory, written after the results of 23: the call after a pushed list, by how much of the read stands ... |
| `e92ab74` | `e975c1c` | 2026-11-11 18:03:29 -0500 | Exploratory: whether the next call opens the neighbor's file at all, file and lines against the file alone,... |
| `61df3f8` | `85af01f` | 2026-11-11 18:04:20 -0500 | NOTES: the exploratory counts made after 23 (same seed, offline baseline, the replays' outcome at whole-run... |
| `7922bee` | `aec6246` | 2026-11-11 18:36:25 -0500 | README: the writeup's title |
| `6ab6bc1` | `7659d80` | 2026-11-11 18:52:44 -0500 | Exploratory: which same-named definition a call edge, a random pick, the release's own rule and the nearest... |
| `fe184a1` | `4d184bf` | 2026-11-11 18:53:43 -0500 | NOTES: the oracle runs side by side in the text, a fifteenth round of blind reviews, which same-named defin... |
| `39c5e03` | `012ae69` | 2026-11-11 20:11:23 -0500 | Figures: the reach figure's title states its null as a null; the graph figure's label says what the async c... |
| `42579e6` | `a3f961a` | 2026-11-11 21:50:44 -0500 | Exploratory: the funnel of whole runs by arm (shown a changed region, shown every one, patch overlaps one, ... |
| `5268545` | `279437b` | 2026-11-11 21:51:38 -0500 | NOTES: a sixteenth round of blind reviews, a count by statement length kept out of the paper, a literature ... |
| `b7405ba` | `89b1e69` | 2026-11-11 22:16:42 -0500 | Exploratory: on how many tasks the four whole-run arms give the same outcome, and the share of the variance... |
| `f2f62c9` | `9282a5b` | 2026-11-12 00:18:35 -0500 | Pre-registration 25 (the place of the list): the registration, the builder and its manifest, the launcher, ... |
| `bdafb67` | `30e4a66` | 2026-11-12 00:26:09 -0500 | Pre-registration 25: the second script, written by another session from the frozen registration alone, comm... |
| `adf4b89` | `e5e4800` | 2026-11-12 00:38:20 -0500 | Pre-registration 25: a dated note before the full run (the cap raised after the smoke test's latencies; a r... |
| `bd73181` | `8435252` | 2026-11-12 01:39:24 -0500 | Pre-registration 25: the stored run, the outputs of both analyses, a dated note after the run, two reproduc... |
| `fa6aa24` | `a66548c` | 2026-11-12 01:39:25 -0500 | The table of pre-registration times, regenerated after the note on 25 |
| `320a058` | `1ddf3b8` | 2026-11-12 01:44:48 -0500 | Table 2: two rows for pre-registration 25, parsed from its registered report; the time stamp of the note af... |
| `a77fa4d` | `f971034` | 2026-11-12 01:44:49 -0500 | The table of pre-registration times, regenerated |
