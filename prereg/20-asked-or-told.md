# Pre-registration 20: asked or told (the same search hits, asked for by the agent or handed to it)

Status: FROZEN on Nov 11, 2026, 1:01 AM EST, by the commit that adds this file, before any replay of the run it
governs was made with a model. Before the freeze the states were built and two plumbing checks ran with a scripted
model in place of the server (no GPU); what was seen is listed under "What has been seen". Tags: [Claude Code]
wrote it; [team] had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/make_states_t.py` `5a79e3a4bea1d6281c090c343f4d0c13`,
`analysis/modal_g/forks_20_modal.py` `379d7ed70142fc0ea5a95577cd50379c`, `analysis/modal_g/forks_20_check.py`
`f2599623134ccfea54758146d1c7c611`, `analysis/analyze_20.py` `b92cfef7c0eaf48c730ed1b26cfacf60`,
`analysis/store_20.py` `1f056303c5a22499233c27e5e7079f48`, the states file `analysis/fork_states_t/states.jsonl`
(not tracked; rebuilt by the builder) `750b3e0952608bf023e69a338f26b030`, its manifest
`analysis/fork_states_t/manifest.json` `cbe13b34bb272a69c3d86447c987e2ac`. Used unchanged:
`analysis/make_states_s.py` `3b2e4a5efc17e508d6781bd27a0cd17e`, `analysis/analyze_15.py`
`5dd2680966b40d7ed717c5387766ccf0`.

## Why

Pre-registrations 15 and 17 showed that the agent's next call uses the line numbers of its own search result, that
without them it reads from the top, and that line numbers handed back in a note are used like those in the result
itself. In every arm of those experiments the agent had just asked. So one sentence of the paper is still a reading:
that a line is used when it answers the agent's own question, which would explain why a graph neighbor's line, which
the agent did not ask for, is taken up less often. This experiment tests the sentence: the same hits, handed to the
agent before it has searched; and the hits of a search it was not about to make.

Parts of this exist and are not claimed. Rebuilding a saved state and varying only the pending tool result is an
earlier design (arXiv 2610.26836). The same content through different channels has been compared for adversarial
instructions (arXiv 2606.00566), and pushed against pulled for memory (arXiv 2607.20972: voluntary use near zero,
injection delivers). A bounded search found no test that holds benign search evidence fixed and varies whether the
agent asked for it; that is the one thing asked here.

## Design

- Steps: the 61 paused steps of pre-registration 15. Each ends with the agent's own search, whose result names an
  unopened file with a line number. Here each step is also cut one call earlier: the history as it stood just before
  that search. 8 steps are dropped from every arm because the search was the agent's first call (the shortened
  history ends on the task prompt, not on a tool result). 53 steps remain (44 runs of 26 tasks).
- Arms, one model call each, three seeds, the model and settings of 15 (Gemma-4-31B, the current harness), all in
  one launch:
  - **NONE**: the shortened history, nothing added.
  - **TOLD**: the shortened history and a note, "Matches in the repository:", followed by the hit lines of the
    recorded search result as the agent saw them (file, line number, text). No command, no instruction, no mention of
    a search. The note is attached the way arm S0N of 15 attaches its note.
  - **TOLDX**: the shortened history and a note of the same form holding the hits of another recorded search: first
    choice, the nearest search at another step of the same run whose result is not in the shortened history; if the
    run has none, the search nearest in step index in another recorded run of the same task. Either must name, with
    a line number, a file that the run had not opened at the paused step, and must name no file of the step's own
    search result. 26 steps have such a search (15 from the same run, always a later step; 11 from another run); the
    other 27 have no TOLDX arm.
  - **ASKED**: the step as recorded, the search made by the agent, its result with line numbers (arm S of 15),
    replayed again in this launch. The stored rows of 15 for the same steps are printed beside it for description.
- Steps are taken in a fixed random order (`random.Random(20)`); no new replay starts after 30 minutes of the
  runner's clock, so a run cut short is a random subset.

## Outcomes (per replay, definitions of 15)

USES THE LINE: the next call is a first read of a file named in the note (for NONE and ASKED: in the step's own
search result; for TOLDX: in its own note, among the files that qualify it) that asks past line 1. SEARCHES: the next
call is a search. A misspelled bound counts as written. Malformed calls are counted apart.

## Rules

Bootstrap by step, 2,000 resamples, seed 0, on the steps complete in the arms compared.

- **T1, told lines are used.** USES THE LINE, TOLD minus NONE: met if the interval lies above zero.
- **T2, asked against told.** The ratio TOLD / ASKED on USES THE LINE: "used about as often" if it is at least two
  thirds, otherwise "telling does not replace asking". The two arms are one call apart (ASKED is paused after the
  search, TOLD before it); the text will say so wherever it gives this result.
- **T3, wanted against unwanted.** USES THE LINE, TOLD minus TOLDX: met if the interval lies above zero.
- **T4, telling saves the search.** SEARCHES, TOLD minus NONE: met if the interval lies below zero.

Floors: T1, T2 and T4 need at least 40 complete steps; T3 at least 20. The floor of T3 was 30 in the plan and was
set to 20 after the builder showed that only 26 steps have another search to take hits from, before any replay with
a model. Below a floor the numbers are printed without a verdict.

Printed without a rule: T3 for each source of the other search alone; the ratio of 15's form, (TOLD − NONE) /
(ASKED − NONE); under TOLD and TOLDX, what the next call is when it does not use the line; of the replays under TOLD
and under NONE whose next call is a search, how many repeat the search the agent made in the recorded run (told and
re-checked, against told and trusted); ASKED against the stored rows of 15.

## What we expect, written before any replay

We do not know, which is why it is run. If TOLD is near ASKED and well above TOLDX, what counts is whether the line
answers the question the agent has at that moment, not who made the search. If TOLD is far below ASKED, the agent
uses what it asks for and discounts what it is handed. Our guess: T1 met; T2 "used about as often" by a small
margin; T3 met; T4 met.

## What has been seen

The results of 15 and 17, in full. From the builder: the counts above; the notes hold a median of 2 hit lines; every
hit line in a Python file equals that line of the task's snapshot; three records read by hand. From the plumbing
checks (scripted model, 8 steps): each arm's request is what the design says (NONE is ASKED without the search call
and its result; TOLD and TOLDX add one note), and the analysis scores scripted calls as scripted. The analysis was
run on a stand-in (rows of 15 relabelled); those numbers say nothing about this experiment. No replay of any arm has
been made with a model in this launch.

## Not covered

One model here; other publishers' models may be replayed through a hosted API, under their own registration, if
that run is made. The steps come from two repositories, 43 of the 53 from one of them. TOLDX exists for half of the
steps, and for 11 of them its hits come from another run of the task. ASKED differs from TOLD by one call of history
(the search call itself), which is the point of the comparison and also its limit: TOLD has no command in the
history that the hits would answer.

## Notes added after the freeze

- Nov 11, 2026, 3:26 AM EST, after the run: the Design above says "the current harness". That is wrong. The run, like
  that of pre-registration 15 whose settings it takes, used the harness wheels of Sep 30 (v28), as the frozen launcher
  states and as the stored `versions.json` records. The run was as frozen; the sentence was not.
- Nov 11, 2026, 3:26 AM EST: all 555 replays ran and were usable (53 steps, three seeds; TOLDX on 26 steps).
