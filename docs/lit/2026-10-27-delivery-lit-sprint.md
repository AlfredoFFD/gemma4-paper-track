# Lit sprint, Oct 27 2026: does Gemma use a code graph it can see, and does a wrong edge steer it?

Written by Claude Code on Tue Oct 27, 2026. Sources:
- 18 papers read in full, every line, figure and table, with notes in `2026-10-27-delivery/notes/`;
- one rival Kaggle writeup read in full (GraphAudit);
- five more papers known by abstract only, marked ABSTRACT below.

Everything about our own data is EXPLORATORY unless it says otherwise.

- **Part 1:** the verdict and the literature (what is done, what is open, where the papers disagree).
- **Part 2: The plan.** The question, the experiment, the gates and the odds (one screen).
- **Part 3:** reading notes, verified references, search log.

---

## Part 1. Verdict

**Open in what we searched, but only as a combination. Each piece is partly done somewhere.**
- **Pulled vs pushed, same content:**
  - 2609.05587, which includes Gemma-4-31B;
  - 2604.17609;
  - 2610.26836, the closest on method. It forks one saved GPT-5.2 state and varies only whether a tool result is inline or one read away: −9.4 points [−14.5, −4.6]. That is scientific QA, all information true, final answers only.
- **Planted decoys:**
  - in repair: RepoMirage;
  - agents following wrong graph-tool output: 2606.14476;
  - a fabricated call chain in a code knowledge graph, accepted in 269 of 269 valid directed yes/no trials (Oracle Poisoning, Table 4).
- **Forks from saved agent states:** CRR, RippleCP, 2610.26836, PAIR (ABSTRACT), Causal Agent Replay (ABSTRACT).
- **Rerunning one agent loop with only the observation changed:** 2606.21409.

**No one has done the combination.** Nobody has held a coding agent's state and the delivered code-graph facts fixed, varied (a) whether the agent asked for those facts or was handed them and (b) whether one edge is true or false, and scored where the agent reads or edits next against the base rate for that same target. Nor has anyone done it on a small 4-bit model under a ~16k prompt cap.

**The papers also disagree on the direction of the delivery effect.** That disagreement is our opening.
- **Handed-over content gets used more:**
  - Gemma-4-31B adopts the same corrupted search content 17 to 19 points more when it is pushed into the prompt (2609.05587);
  - a solution in the prompt beats the same solution as a findable file, 76.25 vs 55.88 pass@1 (2604.17609).
- **Content arriving as a tool result is trusted more:**
  - for code the agent ran itself, pushing lowers adoption by 36 to 38 points pooled (2609.05587);
  - with poisoned code-graph data visible in every arm, GPT-5.1 trusts it 0% as prompt prose but 100% as a tool result (Oracle Poisoning §5.4). Claude goes the other way.
  - Both comparisons also change the format. In Oracle Poisoning, a name prefix alone flips inline trust from 0% to 100% for three models (Table 16).

Our design separates the two quantities these papers mix: **uptake** (does the graph ever reach the agent's context) and **trust given exposure** (once it is there, does the agent act on it, true or false). It holds the text fixed and varies only the channel. Oracle Poisoning also supports the method: a tool result inserted by the harness was trusted exactly like a real, model-initiated call for all three models tested (Table 7). So an inserted call is a fair stand-in for a real pull.

**Confidence:** medium.
- **Not searched:** paywalled venues, non-English work, patents.
- **Kaggle writeups:** only the ones we know of were checked.
- **Read in full:** 18 papers. The last four (Oracle Poisoning, CodeCompass, 2607.09691, 2610.26836) were finished at about 15:45 on Oct 27. None changes the verdict. 2610.26836 narrows it: forking a saved state to vary only how a true observation is delivered is done, outside code. What stays open is code-graph structure, false edges scored against base rates, the next read or edit as the outcome, and the channel varied with the text fixed, on a small 4-bit model.

### Closest prior work

| Paper | What it does | What it does not do, relative to us | Where |
|---|---|---|---|
| Agents' Overreliance on Unreliable Tools (2609.05587) | Same corrupted content pulled by the agent's call vs pushed into the prompt, six models including Gemma-4-31B. Search: push raises Gemma's adoption, +17.3 [+12.2, +22.4] as a user message and +19.1 [+13.9, +24.4] as a RAG block (pooled over models: +1.6 n.s. and +6.8). Code executor: push lowers it (Gemma −18.8 / −9.8; pooled −38.4 / −36.4). Claude Code re-checked these against Table 27 on Oct 27. No prompt policy lowers Gemma's adoption. | QA, summaries and arithmetic, not repair; no code graph; delivery is confounded with tool access, query provenance and repetitions (the paper says so); outcome is the final answer; no forks; bf16, 200k budget | §4.4; Tables 3, 8, 26, 27, 29, 32 |
| Oracle Poisoning (2605.09822) | Poisons a code knowledge graph that agents query by tool. 9 large closed models; a fabricated call chain is accepted in 269/269 valid directed trials; 3–55% under open-ended prompts. Channel comparison: GPT-5.1 trusts the data 0% as prompt prose vs 100% as a tool result; Claude the reverse. A harness-built tool result equals a real call (Table 7). | One yes/no security question per fresh session: no repair, no navigation outcome. The data is visible in every arm, so this is a channel and format comparison, not queryable vs visible. Information match not shown. No base rate on true data; no forks | §4, §5.4; Tables 4, 7, 16, 18 |
| Agents Explore but Agents Ignore (2604.17609) | Coding agents bring a planted solution into context with their own commands in 53–100% of runs but touch it in 0.3–50%; the solution in the prompt gives 76.25 pass@1 vs 55.88 as a findable file vs 44.50 with none | Unpaired; incidental discovery, not a queried tool; true information only (50 wrong variants planted once, following never measured); no forks; 111B–355B models; no graph | Fig. 2; Tables 4, 5 (App. A.2), 10 |
| RepoMirage (2605.26177) | Decoy files beside the real target are its most damaging perturbation (−6.8 to −11.8); pushing structural knowledge raises success a lot (GPT-5 Proxy 11.11 → 81.94) | No graph; the pushed hint carries generator rules no tool could return (not information-matched); no rate of following the decoy, no base rate; no forks | §3.1, §5.2–5.3; Table 3; Fig. 3 |
| When the Tool Decides (2606.14476) | Small open agents agree with a GNN tool 97.6–99.2% of the time although it is wrong on 29–70% of nodes (so they follow wrong outputs at least ~96% of the time, the note's bound); calls are compliance, not judgment; its §9 names "tool output dominating the context" as untested | Node classification, not code; pull only; nothing planted; no base rate; no forks | Table 1; §3, §4, §9 |
| Same Simulation, Different Evidence (2610.26836) | The same simulator report either inline or behind a section index. GPT-5.1 −11.3 [−18.0, −4.9]; GPT-5.2 −7.9 (fails Holm correction); Claude and GPT-5.4 show no detectable cost (GPT-5.4's null hides about 10 points of evidence-use loss). A true fork from a saved GPT-5.2 state, varying only the pending observation, gives −9.4 [−14.5, −4.6]. Agents answer from evidence they already hold ("evidence substitution"); naming the authoritative output restores use. | Geochemistry QA, not code; all information true; final answer only; unseeded sampling, 3 continuations per arm; no channel-with-fixed-text contrast | §2.2, §4; Fig. 3; Tables 1, 3–5, 10 (App. D) |
| Method neighbors: CRR (2609.33875), RippleCP (2610.09088), Don't Blindly Trust It (2606.21409), PAIR (2609.36526, ABSTRACT) | Forks or matched reruns from one state. CRR forks the action, keeping ~57% of the signal at 2 steps; RippleCP restores branches; 2606.21409 reruns one fixed loop with the observation changed (temp 0, one seed); PAIR compares execution from the same state with vs without compression | None varies a code-graph observation; none measures the next read or edit against a base rate. We borrow the method and do not claim it | CRR §3, Fig. 3c; RippleCP §3; 2606.21409 §2 |

### Coverage grid

Components:
- **C1 setting:** a coding agent with code-graph tools doing end-to-end repair, on a small 4-bit open model under a ~16k prompt cap.
- **C2 delivery:** the same graph facts pulled vs pushed; presentation.
- **C3 truth:** a planted wrong edge, with following scored against the same target's base rate.
- **C4 method:** paired forks from one saved state; next read or edit.
- **C5 claim:** visible beats queryable; tool calls and stated beliefs are not use.

Key: ✓ covered · ~ partly · ✗ not · ? pending a full read.

| | 05587 Overreliance | 17609 Explore/Ignore | 26177 RepoMirage | 16936 RepoAtlas | 20972 Delivery≠Storage | 14476 Tool Decides | 24873 One-Pixel | 23254 Ignored≠Refused | 06191 Judged Useless | 17444 Belief–Action | 33875 CRR | 09088 RippleCP | 21409 Don't Blindly Trust | 32590 Retrieved≠Delivered | GraphLoc (Kaggle) | GraphAudit (Kaggle) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | ~ | ~ | ~ | ~ | ~ | ~ | ✗ | ~ | ~ | ✗ | ~ | ~ | ~ | ~ | ✓ | ~ |
| C2 | ~ | ~ | ~ | ~ | ~ | ✗ | ✗ | ✗ | ~ | ✗ | ✗ | ✗ | ✗ | ~ | ✗ | ✗ |
| C3 | ~ | ~ | ~ | ✗ | ✗ | ~ | ~ | ~ | ✗ | ~ | ✗ | ✗ | ~ | ~ | ✗ | ~ |
| C4 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ✗ | ✗ | ✗ |
| C5 | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ~ | ✗ | ~ | ~ | ~ | ~ | ✗ |

**Read in full after the main grid was drawn:**

| | 09822 Oracle Poisoning | 20048 CodeCompass | 09691 What Context | 26836 Same Simulation |
|---|---|---|---|---|
| C1 | ~ | ~ | ~ | ✗ |
| C2 | ~ (channel and format; data visible in all arms) | ~ (weak; different information pushed vs pulled) | ~ (presentation only, all pushed) | ~ (inline vs one read away, information-matched) |
| C3 | ~ (verbal verdict; no base rate) | ✗ | ✗ | ✗ (all true) |
| C4 | ✗ | ✗ | ~ (paired by instance; noise floor) | ~ (true fork, one model, unseeded, final answer) |
| C5 | ~ | ~ (queryable goes unqueried) | ✗ | ~ (evidence substitution) |

**What the grid shows:**
- Only GraphLoc (same competition, same harness) covers C1 fully, and it tests none of C2 to C4.

### Cross-paper map

#### Where the papers agree

1. **What the agent could fetch mostly goes unfetched, and what it fetched mostly goes unused.**
   - **Planted solution:** found in 53–100% of runs but touched in only 0.3–50% (17609).
   - **Memory store:** 0 voluntary memory-tool calls in 114 turns until something was pushed (20972).
   - **Requested repository views:** obtained in 40.5% of instances (16936).
   - **GNN tool:** 83% of 7B queries make one call and never fetch the anomaly signal (14476).
   - **This competition (GraphLoc's traces):** 109 of 318 runs call a graph tool, 26 get a non-empty result, and the final patch edits a returned node in 1 of 48 events.
   - **A dependency-graph tool over MCP:** Claude Code made zero graph calls in 51 of 88 trials, and in 0 of 30 structural-task trials, despite a prompt telling it to call the tool first (CodeCompass §5.3).
   - The metrics differ, but the direction is the same from 7B to frontier models.
2. **Text in view steers the action, even against instructions.**
   - **Transplanted reasoning:** it sets the action (0.598–0.673 probability), and telling the model to ignore it restores the prompt's action in 1.0% of cases (17444).
   - **One sentence:** a single added sentence flips verdicts, and a neutral restatement alone flips 17–28% (24873).
   - **A framing block:** it swings execution of tool-output instructions from 0.22% to 43.05% (23254).
   - **Graph tool output:** small agents agree with the GNN tool 97.6–99.2% of the time (14476).
3. **Calls and words are not use.**
   - **Calls:** tool-call ratios rise up to 18x under corruption while adoption stays high (05587).
   - **Stated doubts:** thinking models flag the conflict in 87.9–96.0% of runs and adopt anyway (05587).
   - **Judgments:** 98.4–99.9% accurate, yet actions ignore them (06191).
   - **Recognized, then executed:** 28.9% / 16.9% (23254).
   - **Correct state reports:** in 66 of 161 suboptimal switches, every report stayed correct (17444).
4. **Wrong structure near the target hurts.**
   - **Decoy files:** RepoMirage's are its worst perturbation.
   - **A missing runtime edge:** it kept the agent from the gold file in 8 of 8 runs (RepoAtlas sympy-17630, anecdotal).
   - **A costly decoy-like artifact:** pass@1 fell below the no-injection baseline, 37.92 vs 44.50 (17609).
   - **Wrong dates:** worse than no dates, −5.67 (32590).

#### Where they disagree

1. **Does handing content over raise or lower its influence?**
   - **Push wins:**
     - Gemma-4-31B search content (05587);
     - prompt vs findable file (17609);
     - inline vs retrieved tool output: GPT-5.1 loses 11.3 points under retrieval and GPT-5.2 loses 9.4 in a true fork, while Claude models lose nothing detectable (2610.26836);
     - memory notes (20972);
     - RepoAtlas, though its +1.1 to +3.8 is within noise.
   - **The tool channel wins:**
     - code-executor output, where pushing lowers adoption by 36–38 points (05587);
     - Oracle Poisoning's channel result for GPT-5.1 and others (Claude reversed). The data was visible in every arm, so this is trust given exposure, not uptake.
   - **Candidate explanations (ours, untested):**
     - **(a) Provenance (who started the fetch).** Oracle Poisoning's Table 7 argues against this for three large models: a tool result the harness inserted was trusted exactly like one the model asked for.
     - **(b) Channel and format.** A tool result vs prompt text, JSON vs prose. Oracle Poisoning shows format alone can flip trust (a name prefix: 0% → 100%).
     - **(c) Two different quantities.** Pushing wins on uptake, because pulled content often never arrives. The tool channel may win on trust once exposure is fixed.
   - **No paper separates these, because none fixes the text and the exposure together.** Our forks do. "Asked for" (P) and "handed" (H) deliver identical text into identical states and differ only in channel. "As shipped" (A) vs P measures uptake.
2. **Does visible content carry behavior at all?**
   - **06191 says no:** a running count written into the context each step did not make 7–8B agents stop on useless results. Δ stayed negative (−0.14 to −0.24), where acting on the count would make it positive. Only the harness enforcing the rule worked (Δ +0.33 to +0.37). Everyone else says yes.
   - **Reconciliation (guess):**
     - visible content that supplies the next step of the default loop, like a file to open, gets followed;
     - visible content that asks the agent to break the loop (stop, switch tools) does not.
   - **A pushed graph neighborhood is the first kind.** We scope C5 to it and, if cheap, add one "deviation" arm ("X is not the bug").
3. **Does code structure help?**
   - **Yes:**
     - a structural index gives a localization gain and a separated resolve gain for Opus 4.7 (2606.22417, ABSTRACT);
     - CodeCompass reports 99.4% vs 76.2% on hidden-dependency tasks. That is mean file coverage (every gold file read or edited), not task completion, on a hand-built 30-task benchmark, with a prompt that orders reading every returned neighbor. No tests are run.
   - **No:**
     - GraphLoc: +0.9 points, CI −4.1 to +6.3;
     - RepoAtlas's names-only image scores below no graph (59.2 vs 60.8);
     - with the files to edit given by an oracle, showing the rest as UML skeletons + signatures resolves 23 of 70 vs 25 of 70 with it deleted. Discordant pairs 4 vs 6, p = 0.754, pre-registered (2607.09691, Tables 3–4). Its byte-identical rerun flipped 6 of 70 outcomes (8.6%).
   - **GraphAudit:**
     - real-graph fusion raises official-task file recall from 63.4% to 73.7%;
     - a degree-preserving random graph gets to 70.1%, so most of the gain is "what lands in the context", not topology;
     - the real-minus-random contrast is 3.1 points [+0.7, +5.6].
   - **The differences:** who controls delivery, the stage (finding vs acting), and the task type. In our tasks, the issue already names a gold unit in 27.1% of tasks, and one hop reaches unnamed fix code in only 10.1%.

#### Shared assumptions no one tests

1. **Exposure is inferred from the call.**
   - Almost every paper infers what the agent saw from what it called; 05587's App. F.2 is the exception.
   - Nobody holds exposure fixed while varying who started it.
2. **The outcome is the final answer or pass/fail.**
   - Only RepoAtlas (first gold-file open, one case study), 17609 (interaction@k) and GraphLoc's re-analysis measure process.
   - None scores the next read or edit against the base rate at the same state.
3. **Nobody measures discrimination.**
   - Papers test following wrong content, or using right content.
   - None compares following a true edge with following a false edge at the same state. That difference is what tells you whether the agent checks anything.
4. **Framing varies with delivery.**
   - Push arms arrive as system text, "RAG context" or a "hint", while pull arms arrive as tool results.
   - 23254 shows framing alone can swing compliance about 200-fold. We hold the wording fixed and vary only provenance.
5. **Budgets are generous.**
   - Most run at 65k–200k+. Only 06191 (8,192) and 14476 (5,000) run tight.
   - Nobody tests delivery under a binding ~16k cap, where pushed text displaces other context.

#### Mechanism chains: untested claims that two results imply together

1. **Following plus the graph's own gaps.** 05587 §4.4 (Gemma adopts pushed content) + 14476 Table 1 (agents follow wrong graph outputs) + our audit (the graph holds 1 of 56 async gold units; 18 of 64 fastapi tasks lack a gold unit) imply this: pushing the organizers' graph would steer Gemma away from the fix where the graph is silent or wrong. The quantity to estimate is P(follow | false edge), measured.
2. **Handing begets asking.** 20972 §5.2 (the agent queried the store only after content was pushed) + GraphLoc's traces (graph calls rare, mostly empty because the agent searches by keyword and the tool resolves names) imply that a handed neighborhood raises later graph-tool calls, since the agent learns exact node names it can query. Testable in the same forks: tool calls after the fork.
3. **Following peaks at uncertain steps.** 17444 (susceptibility falls from 100% to 62.5% as confidence rises) + CRR Table 23 (high-entropy steps first-touch the gold file 41% vs 13% at random steps) imply that a wrong edge is followed most at uncertain navigation steps. Choose fork points by entropy and pre-register commitment as a covariate.
4. **Salience alone.** 24873 (neutral restatement flips 17–28%) + 23254 (framing) + GraphAudit (random graphs recover most of the retrieval gain) imply that any push effect could be salience, not information. Hence the neutral-restatement arm, the random-graph arm and fixed wording.
5. **Position.** 32590's position effect (wrong picks go to the first-listed item) + the v28 tool's alphabetized neighbor lists imply that list position could masquerade as following. Log the decoy's position, balance it across states, and use it as a covariate.

#### Metric drift (same word, different measure)

- **"Adoption"** (05587): the final answer equals the corrupted value.
- **"Trust"** (Oracle Poisoning): the model accepts a fabricated claim.
- **"Interaction"** (17609): a command string-matches the solution.
- **"Agreement"** (14476): the prediction equals the tool output.
- **"Uptake"** (Claude Science, Sep 30): the next read or edit overlaps a returned node's span or distinctive line.
- **Ours, "following":** the uptake definition, minus the touch rate for that same node in the no-insertion arm, at the same state with the same seeds.
- **"Push"** has five meanings across these papers: system prompt, RAG block, task prompt, harness view and hook injection. Ours is the identical tool-result text placed as a harness note.

### Gap and falsifier

**Gap.** No study we found holds a coding agent's state and the delivered code-graph facts fixed while varying (a) the channel with the text fixed (tool result vs harness note) and (b) true vs false edge, and scores the next read or edit against the same-state base rate. It is untested on the organizers' graph, Gemma-4-31B in 4-bit, the official harness, and a ~16k cap.

The nearest design is 2610.26836: a true fork varying only how a true observation is delivered (inline vs one read away), scored on final answers in scientific QA. We borrow its fork design and add truth, navigation outcomes, the channel contrast and the setting.

**What would show it is not new:**
- Causal Agent Replay's interventions (abstract only) applied to observation content in a coding agent;
- a Kaggle entry we haven't seen.
- Already checked and cleared: Oracle Poisoning (full read: channel and format comparison, data visible in every arm, verbal verdicts only); GraphAudit (retrieval only).

**What would show it doesn't work:**
1. Next actions after an inserted graph block don't follow even true neighbors above base rate. That is still a result, but a duller one.
2. Fork states can't be rebuilt faithfully, so the forks don't reproduce the agent.
3. Base rates for listed neighbors are already high, meaning the agent was going there anyway. Then we stratify to unnamed nodes, which leaves fewer events.

---

## Part 2. The plan

**The question, in plain words.** When Gemma has the code graph in front of it while fixing a bug, can it tell a
right link from a wrong one, or does it just go wherever the graph points? Two side questions use the same runs: does
it matter whether Gemma asked for the graph or was handed the same text, and how often does it bring the graph into
view on its own? (Updated Oct 28: the true-vs-fake test leads; see the proposed primary under Hypotheses.)

**Why this question.**
- **No paper we read tests it.** None shows an agent a true and a fake link at the same moment and checks where it goes next (Part 1, "Shared assumptions", item 3).
- **Nobody has asked it.** Every audit so far (GraphLoc, GraphAudit, aghasalim, ours) asks whether the graph helps. None asks why not, inside the agent.
- **The papers disagree** on whether agents trust information more as a tool result or handed over in the prompt (2609.05587, Oracle Poisoning). None separates that from whether the information arrives at all.
- **It tells the organizers what to build next.** Better delivery, if the agent ignores what it must ask for. A more accurate graph, if it follows whatever it sees.
- **Every outcome teaches something.**

**What we already know (EXPLORATORY, Claude Science, Oct 1).**
- When a graph tool returns something in GraphLoc's traces, Gemma's next read or edit touches a returned node 30.2% of the time (13 of 43; CI 18.6–45.1), against 15.8% for size-matched random code in the same files.
- But the agent only asks about things it is already heading toward, so these traces can't separate steering from selection. Forks can.

**The three experiments (Oct 28, hackathon mode).** Experiment 1 is the core and is designed in detail below. Experiments 2 and 3 reuse its machinery.

| # | What | Answers | Cost (guess) |
|---|---|---|---|
| 1. True vs fake link | Forks right after the issue is read (arms below), on Gemma-4-31B; repeated on a second open model if time allows | Does Gemma act on graph facts, and can it tell a true edge from a false one? | A few GPU-hours |
| 2. The same test after compaction | Forks right after the harness compacts: the same true and false edges, plus a graph-shaped memory note with true entries or one false entry | Does losing the transcript make Gemma more credulous (worse discrimination after compaction than before)? | A few GPU-hours; needs post-compaction states that can be rebuilt |
| 3. The fix | Full repair runs: the graph neighborhood pushed when the issue is read and a memory note pushed after each compaction, vs the plain harness. Pre-registered on the tasks where one or two hops reach unnamed fix code (about 25 of 129), with a harm check on the rest | Does it fix more bugs where the graph can matter? | Tens of GPU-hours. The schedule risk; needs a second Kaggle quota |

- **Experiment 2 after the memory check** (`2026-10-28-memory-check.md`).
  - Already done: forks after compaction (PAIR 2609.36526; Compact-Bench 2610.31710, read in full), and wrong summary entries being carried out (2610.20927, partial read).
  - Open in what we searched: true vs false at the same state against the no-note base rate, and whether compaction raises credulity.
  - So "the note reduces re-reads" and "the note restores progress" would repeat PAIR and are not headlines.
- **Experiment 3 is an application, not a novelty claim.**
  - Compact state memories kept beside the transcript already help coding agents without training (Ledger 2608.00808, StateHarness 2610.17616; abstracts). Its job is the end-to-end gain.
  - The graph reaches unnamed fix code in only about 10–20% of tasks, so the overall gain is capped at a few points. That's why the test is focused on those tasks.
- **The leaderboard can't verify any of this.** Re-running one agent reproduces the spread of the whole board (`docs/competition.md`).

**Design: forks from real Gemma states.**
- **States:** saved from real Gemma-4-31B repair runs on the official harness, taken after the issue is read, before the first edit, and before compaction.
- **Source of states:** GraphLoc's 636 public traces if a state can be rebuilt exactly; otherwise about 30 of our own runs.
- **Arms:** at each state, continue under arms that differ only in what is inserted.

| Arm | What is inserted at the fork |
|---|---|
| A, as shipped | nothing (base rate and natural uptake) |
| P, asked for | a `get_code_neighbors` call on a node already in view, plus its real v28 result |
| H, handed | the same result text as a harness note, with no call |
| P′ and H′, one edge false | as P and H, with one neighbor swapped for a plausible non-neighbor (same file or module); list length and format fixed. The v28 tool returns names sorted alphabetically, so the decoy sits where that order puts it; its position is logged and balanced across states |
| N, salience control | a harness note that restates only names already in view |
| R, random graph (optional) | the same node's neighborhood in a degree-preserving rewired graph (GraphAudit's control) |
| E, encoding (optional, cheap) | H's note with each name written as signature + file:line instead of a bare name. This is the judges' own question (*Talk like a Graph*) asked inside an agent; RepoAtlas hints that bare names alone can hurt (59.2 vs 60.8 with no graph) |

**Outcomes.**
- **Primary:** Claude Science's Sep 30 uptake definition applied to each fork: does the next read or edit touch a given node? Effect = touch rate when the node is shown, minus that node's touch rate in arm A, at the same state with the same seeds.
- **Secondary:**
  - graph-tool calls after the fork (does handing beget asking?);
  - gold touched within 10 calls (subset, read-only tools run on a checkout);
  - interface failures per arm (malformed calls, overflow, edit mismatches).

**Hypotheses.** Claude Science freezes the thresholds; these are the directions.
- **H1:** shown true neighbors are followed above base rate.
- **H2:** a false edge is followed at least half as often as a true one; the agent doesn't check.
- **H3, two-sided (the disagreement in the literature):** with the text fixed, the channel (tool result after an inserted call, P, vs harness note, H) changes following.
- **H4, descriptive:** in arm A the agent rarely brings the graph into view on its own.
- **Proposed primary (added Oct 27, 17:30): H2, discrimination.**
  - It is the one piece no paper we read measures (Part 1, "Shared assumptions", item 3).
  - The asked-vs-handed contrast (H3) has close neighbors: 2610.26836 forks a saved state to vary delivery, and Oracle Poisoning compares channels (§5.4, Table 7).
  - The pre-registration needs an equivalence margin, so that "doesn't check" can be claimed as a finding, not only as a failure to find a difference.
  - Our guess is that Gemma doesn't check. Outside code, small agents agree with a GNN tool 97.6–99.2% of the time although it is wrong on 29–70% of nodes (2606.14476).

**Controls borrowed from the reading:**
- the same wording in every arm (23254);
- neutral-restatement and random-graph arms (24873, GraphAudit);
- decoy position logged and balanced across states (32590). It can't be shuffled, because the real tool sorts names alphabetically;
- commitment at the fork as a covariate (17444);
- fork points chosen by entropy (CRR);
- the arms of a pair run in the same vLLM batch configuration (06191);
- K = 1 rates reported, not best-of-K (24873);
- interface failures counted per arm (project rule).

**Why it is cheap.**
- The main readout is one model step per fork: pure inference with prefix caching, no sandbox.
- About 200 states × 6 arms × 4 seeds ≈ 4,800 generations. A guess of 2 to 4 hours on one free Kaggle 4xL4 session until the pilot measures it.
- The unit is the fork state, with many per task, so the 106-task power limit does not bind. Tasks are clustered in the analysis.

**What we could claim.** One of these three, translated into this competition's terms:
- "Gemma follows what it sees and doesn't check it";
- "it checks";
- "it trusts what it asked for and ignores what it's handed".

The translation: the graph can only steer toward unnamed fix code in about 10% of tasks at one hop (19% at two). Where the graph is silent (1 of 56 async gold units held), a pushed graph would steer the agent somewhere else.

**Kill checks, in order.**
1. **Fork fidelity, no GPU (Claude Science, which holds the traces).** Can a GraphLoc trace be rebuilt into the exact prompt at step t: system prompt, tool schemas, message history, and how thinking is kept? If not, we run our own baseline episodes to save states (about +2 days).
2. **Pilot.** Arm A from a logged state produces next actions like the logged ones, and an inserted block arrives intact under the 16k cap.
3. **Base rates.** If listed neighbors are near-certain visits anyway, restrict the analysis to unnamed nodes.

**Timeline and gates.**

| When | Who | What | Gate |
|---|---|---|---|
| Oct 27–28 | agents | Finish this sprint. Claude Science: pre-registration v2 + fork-fidelity check. Claude Code: fork builder + pilot notebook. | - |
| Thu Oct 29 | team, 30 min | Go or no-go; the teammate's yes or no; Kaggle team | No-go → stop, or the no-run fallback |
| Oct 30 – Nov 1 | agents | Pilot: 20 states × all arms × 2 seeds; fidelity, cost per generation, base rates | **Sun Nov 1:** no valid pilot → no-run fallback |
| Mon Nov 2 | team, 20 min | Approve the frozen pre-registration | - |
| Nov 2–6 | agents | Main runs on free Kaggle sessions; independent re-derivation of every number; the 10-call subset if budget allows | Incomplete by Fri Nov 6 → report what finished, labeled |
| Nov 6–9 | agents draft; team edits ~3 h | 3,000-word writeup + public notebook | - |
| Tue Nov 10 | team, 30 min | Submit (two days of buffer) | - |

**No-run fallback** if the pilot fails: "Where the provided graph's information is lost", built from what exists.
- GraphLoc's traces: queries that return nothing, uptake of 30% vs 16%, and 1 of 48 patches editing a returned node.
- Our offline reach numbers: 10.1% at one hop, 19.4% at two, 27.1% named directly.
- The harness facts: the "keyword" instruction vs a name-only tool.
- It is a smaller paper: about 3 hours of team time, with lower odds.

**The teammate.**
- **If he's in:** Kaggle sessions on his own GPU quota (that doubles the free compute) and the related-work section.
- **Training is out.** A LoRA doesn't fit in 16 days, and 2609.05587 already reports reliance effects of fine-tuning on Gemma-4-31B.

**Odds (guesses).**
- About 10% for Overall Best Paper if the main runs land clean; about 3–5% for the fallback.
- **Biggest risks:**
  1. fork fidelity or the pilot slips (nothing has run yet);
  2. a judge reads it as an application of known tool-reliance tests. The answer leads with the true-vs-false comparison at the same state, which no paper we read makes, then the uptake-vs-trust split and the official harness and graph. (Changed Oct 27, 17:30; see the proposed primary under Hypotheses.)
  3. Gemma ignores even handed content. That is a result, but a duller one.

**What changed since the Oct 1 plan, and why.**
- **Memory comes back in a narrower form (Oct 28).**
  - The memory check found the architecture partly done (Ledger, StateHarness) and post-compaction forks done (PAIR, Compact-Bench).
  - Memory returns as experiment 2 (the true-vs-fake test after compaction) and as part of experiment 3's fix.
  - The new-agent version stays out, for the reasons below.
- **Act 2 moves to future work.** Act 2 was the graph as the agent's working memory. Nothing disproved it. Three things moved it:
  - It needs full end-to-end runs, where effects under about 5 points are undetectable at 106 tasks.
  - Its upside is bounded here. In GraphLoc's runs overflow ends 4% of runs, and 2609.20804 (ABSTRACT) finds context management mostly prevents overflow.
  - Memory-delivery prior art now covers the "delivery" half: 2607.20972, 2609.32590.
- **The Oct 1 kill check never ran.** That was the check of whether compaction costs anything in GraphLoc's traces.
- **Act 1 changes from "the graph fails as a search tool" to the uptake-vs-trust test above.** The reading showed that the delivery question is live and contested. 16 days only fits one experiment.

---

## Part 3. Reading notes, references, search log

### Reading notes (one block per paper; full notes in `2026-10-27-delivery/notes/`)

- **2609.05587, Agents' Overreliance on Unreliable Tools (Yang, Song et al., v2).**
  - **What it shows:** the closest test of pull vs push, with Gemma-4-31B. The direction flips by tool (Search vs Code).
  - **Calls are not use:** call ratios up to 18x under corruption.
  - **Prompts don't help:** no prompt policy lowers Gemma's adoption.
  - **Limits:** delivery is confounded by the paper's own admission; outcomes are final answers.
  - `read: lines 1-6809 of 6809 (reference list skipped per rule) · figures 4/4 · tables 40/40 · appendix yes` · checked: full-text
- **2604.17609, Agents Explore but Agents Ignore (Engländer et al., v1).**
  - **What it shows:** found is not used, in coding agents. Pushing the solution into the prompt gives 76.25 pass@1, vs 55.88 when it is only findable.
  - **Holding things fixed:** tool set and prompt wording both move behavior, so hold both fixed.
  - **Limits:** unpaired comparisons and no CIs. Several numbers disagree across its tables.
  - `read: lines 1-1994 of 1994 · figures 12/12 · tables 12/12 · appendix yes` · checked: full-text
- **2605.26177, RepoMirage (Li, Zhang et al., v1).**
  - **What it shows:** decoy files are the most damaging perturbation in end-to-end repair, and pushed structural hints help a lot.
  - **Limits:** the hints carry extra information. Following of the decoy is never counted.
  - `read: lines 1-1030 of 1030 · figures 13/13 · tables 3/3 · appendix yes` · checked: full-text
- **2609.16936, RepoAtlas (Zhang et al.).**
  - **What it shows:** a pushed graph view. The image of node names alone scores below no graph (59.2 vs 60.8); index rows with signature and file:line score 61.2; both together 63.1.
  - **Pull uptake:** requested views were obtained in 40.5% of instances.
  - **Limits:** the push-minus-pull difference (+1.1 to +3.8) has no uncertainty reported.
  - `read: lines 1-1077 of 1077 · figures 3/3 · tables 4/4 · appendix n/a` · checked: full-text
- **2607.20972, Delivery, Not Storage (Saha).**
  - **What it shows:** memory notes the agent could query got 0 voluntary calls in 114 turns. Pushed notes were used at once, and pushing begets pulling.
  - **Limits:** one task, n = 1–3 runs, frontier models.
  - `read: lines 1-1205 of 1205 · figures 1/1 · tables 5/5 · appendix n/a` · checked: full-text
- **2606.14476, When the Tool Decides (Wang, Vemuri).**
  - **What it shows:** small agents defer to a GNN tool that is often wrong, and calls are compliance.
  - **Open question it names:** §9 says tool output dominating the context is untested. That is our C5.
  - `read: lines 1-766 of 766 · figures 2/2 · tables 4/4 · appendix yes` · checked: full-text
- **2610.24873, The One-Pixel of Reasoning (Hu et al.).**
  - **What it shows:** one true, relation-targeted sentence flips single-shot verdicts, and a neutral restatement flips 17–28%.
  - **What we borrow:** its random-warrant and neutral controls, and its K = 1 reporting.
  - `read: lines 1-3002 of 3002 · figures 6/6 · tables 16/16 · appendix yes` · checked: full-text
- **2610.23254, Ignored, Not Refused (Zarif et al.).**
  - **What it shows:** framing swings compliance from 0.22% to 43.05%. Gemma-4 E4B and 12B act on tool-output instructions once licensed.
  - **Quantization:** NF4 raises invalid outputs, so count interface failures.
  - `read: lines 1-1763 of 1763 · figures 3/3 · tables 11/11 · appendix yes` · checked: full-text
- **2610.06191, Judged Useless, Queried Anyway (Zhang et al.).**
  - **What it shows:** judgments don't become stop decisions, and a visible running count doesn't help. Only harness removal works.
  - **Why it matters to us:** it is the main counterexample to "visible carries behavior". It also warns that vLLM batching shifts outputs.
  - `read: lines 1-6102 of 6102 · figures 6/6 · tables 28/28 · appendix yes` · checked: full-text
- **2610.17444, The Belief–Action Gap (Okcu et al.).**
  - **What it shows:** in a grid world, reportable state isn't acted on, and visible reasoning sets the action. An injected claim flips 62.5–100% of decisions depending on confidence.
  - **What we borrow:** the counter / neutral / supportive triplet.
  - `read: lines 1-1747 of 1747 · figures 10/10 · tables 8/8 · appendix yes` · checked: full-text
- **2609.33875, Counterfactual Rollout Replay (Li et al., v3).**
  - **What it does:** snapshot and restore of an SWE agent, with action forks used as training credit. Two-step continuations keep ~57% of the signal.
  - **Caveat:** its Fig. 2 and Tables 15–17 disagree by 2–3 points.
  - **What we borrow:** its determinism controls.
  - `read: lines 1-2766 of 2766 (reference list skipped per rule) · figures 5/5 · tables 23/23 · appendix yes` · checked: full-text
- **2610.09088, RippleCP (Akewar, Ranjan).**
  - **What it does:** paired restore-and-continue branches without seed control. Paired noise SD is 24.1 s, and 5 of 24 cells flipped sign.
  - **Why it matters to us:** an argument for seed control.
  - `read: lines 1-1087 of 1087 · figures 5/5 · tables 8/8 · appendix yes` · checked: full-text
- **2606.21409, Don't Blindly Trust It (Zhang et al.).**
  - **What it does:** reruns one fixed loop (temperature 0, one seed) with only the observation changed. QA tasks; final answers only.
  - **Caveat:** its "value inversion" may be abstention or step exhaustion rather than adoption, since FEVER accuracy falls below chance.
  - `read: lines 1-824 of 824 · figures 3/3 · tables 6/6 · appendix yes` · checked: full-text
- **2609.32590, Retrieved but Not Delivered (Jiang et al.).**
  - **What it shows:** delivery, not retrieval, carries the gain: pixels delivered vs withheld +13.87 at 8B, while perfect vs actual retrieval gives +2.31 (not significant). The gap shrinks at 30–32B.
  - **Wrong attributes:** wrong dates score below no dates.
  - **For our design:** wrong picks go to the first-listed item, so randomize position.
  - `read: lines 1-2917 of 2917 (reference list skipped except cited entries) · figures 6/6 · tables 21/21 · appendix yes` · checked: full-text
- **GraphAudit (Kaggle writeup, same competition, read in full on Oct 27).**
  - **What it is:** a retrieval study (BM25 plus graph fusion, with degree-preserving random graphs as the null) and a one-shot file choice by a local 8B Gemma 4 in Q4.
  - **Not covered:** no agent loop, no graph edges shown to the model, no delivery factor, no next-action measure. It states it was not pre-registered.
  - **What we borrow:** the random-graph control.
  - It cites two more entries: codegraph-loc and a "Code-Graph Bug Localization Benchmark" notebook.
  - checked: full-text (the published writeup; its code archive was not opened)
- **2602.20048, CodeCompass (Paipuru).**
  - **What it shows:** the clearest published case of a coding agent not querying a code graph it has. Claude Code with a file-level dependency graph over MCP made zero graph calls in 51 of 88 trials, and 0 of 30 on structural tasks, despite being told to call the tool first.
  - **Caveats:**
    - Its "99.4% task completion" is file coverage, inflated by a read-every-neighbor instruction.
    - The repo is a FastAPI example app, not fastapi/fastapi. Its arXiv comment says SWE-bench Lite; the body says otherwise.
    - Several numbers come from a pre-revision run.
  - **Lessons for us:** identical instructions, tool menus and instruction position across arms.
  - `read: lines 1-1130 of 1130 · figures 7/7 · tables 5/5 · appendix yes` · checked: full-text
- **2607.09691, What Context Does a Coding Agent Actually Need to Act? (Sam-Bodden).**
  - **What it shows:** a pre-registered, single-shot repair study with oracle localization (Claude Sonnet 4.6). Signatures and skeletons for the rest of a file resolve no more than deleting it: 23 vs 25 of 70, p = 0.754.
  - **Noise floor:** a byte-identical rerun flips 8.6% of outcomes.
  - **What it means for us:** a boundary condition, not overlap. Structure carries little at the edit stage, so our presentation arm must be scored on navigation (the next target), not on resolution.
  - **Caveat:** it claims a "powered null" without a power analysis; the reader's simulation gives about 11% power for 5 points.
  - `read: lines 1-727 of 727 · figures 4/4 · tables 4/4 · appendix yes` · checked: full-text
- **2605.09822, Oracle Poisoning (Kereopa-Yorke et al.).**
  - **What it shows:** the closest code-graph evidence for C3. A plausible fabricated call chain in a code knowledge graph is accepted in 269 of 269 valid directed yes/no trials.
  - **Its "delivery mode" result** changes channel and format (prompt prose vs a JSON tool result) with the data visible in every arm. GPT-5.1 trusts it 0% as prose vs 100% as a tool result; Claude goes the other way.
  - **Format alone matters:** a name prefix flips inline trust 0% → 100% (Table 16).
  - **For our design:** a harness-built tool result is trusted like a real call (Table 7). That supports our inserted-call arm. It also means push and pull should share one format and fixed naming, with no directed yes/no framing.
  - **Not covered:** no navigation outcome, no base rate on true data, no forks.
  - `read: lines 1-1962 of 1962 (reference list not analysed; leaned-on references looked up) · figures 3/3 · tables 19/19 · appendix yes` · checked: full-text
- **2610.26836, Same Simulation, Different Evidence (Zhang et al.).**
  - **What it shows:** the closest precedent for our method, in another domain. The same simulator output is inline or one read away behind a section index. A true fork from a saved GPT-5.2 state, varying only the pending observation, costs 9.4 points [−14.5, −4.6].
  - **Where the loss comes from:** what agents read and use, not what they compute. They answer from evidence already in hand ("evidence substitution").
  - **Model dependence:** Claude models show no detectable cost.
  - **Lessons for us:**
    - seed the sampling, which they did not;
    - expect model dependence;
    - a pointer naming the authoritative item restores use.
  - `read: lines 1-1618 of 1618 · figures 4/4 · tables 11/11 · appendix yes` · checked: full-text
- **ABSTRACT only, not scheduled:**
  - 2606.08275 Causal Agent Replay;
  - 2609.36526 PAIR (counterfactual continuations for compression);
  - 2609.20804 Harness design study;
  - 2606.22417 Code Isn't Memory;
  - 2603.24631 Coherence Collapse.

### Verified references

`refs.json` holds every paper cited here. `lit.py verify-file refs.json` on Oct 27 after adding 2609.36526: **35/35 OK**
(output in `verify_out.txt`; Crossref flags no retractions). Kaggle writeups (GraphLoc, GraphAudit) are not in `refs.json` because they have no
DOI or arXiv id; they are cited by URL in `docs/competition.md` and `docs/prior-art.md`.

### Search log

Oct 27, 14:49–14:56 EDT, `lit.py`:
- **Searches:** 8 phrasings × 3 sources × 2 windows (last 6 months, all years): 52 searches. That is 20 arXiv, 16 OpenAlex and 16 Semantic Scholar (S2), with S2 throttled; OpenAlex carried those queries.
- **Expansions:** 15 (references, citing papers and recommendations) on the 5 seeds 2609.05587, 2609.33875, 2609.16936, 2605.26177 and 2610.24873.
- **Abstract look-ups:** done later through the arXiv API, for the ABSTRACT papers.
- **Raw log:** `2026-10-27-delivery/lit_search_log.jsonl`.

| # | Phrasing | arXiv 6mo / all | OpenAlex 6mo / all | S2 6mo / all |
|---|---|---|---|---|
| p1 | misleading tool output coding agent | 2 / 5 | 15 / 15 | 0 / 15 |
| p2 | code graph context injection repository agent | 2 / 2 | 15 / 15 | 15 / 0 |
| p3 | counterfactual resampling agent trajectory | 1 / 2 | 15 / 15 | 0 / 15 |
| p4 | corrupted code graph decoy agent | 0 / 0 | 15 / 15 | 7 / 15 |
| p5 | agents ignore retrieved information | 13 / 15 | 15 / 15 | 15 / 0 |
| p6 | anchoring language model agents visible context | 3 / 4 | 15 / 15 | 0 / 0 |
| p7 | push pull memory delivery LLM agent | 0 / 0 | 15 / 15 | 0 / 0 |
| p8 | tool reliance language model agents | 15 / 15 | 15 / 15 | 0 / 0 |

Earlier sweeps this builds on: `docs/prior-art.md` (Sep 30) and `docs/claude-science-prior-art-check-2026-09-30.md`.
Claude Science's Sep 30 check had already listed Oracle Poisoning and Don't Blindly Trust It as threats to the "why
doesn't the graph help" direction.
