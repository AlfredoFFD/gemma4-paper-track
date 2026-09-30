# Methods that transfer from our earlier work

An earlier project of ours (a pre-registered study of how answer formats change what vision-language models appear
able to do) is not about code. Its content does not transfer. Several of its methods do, and they target exactly the
criteria the judges score (novelty, verifiability, clarity).

1. **Check the interface before calling a model incapable.**
   - That project measured a capable model as incapable five times, each because the scorer and the model disagreed
     about what an answer looks like.
   - Here: count interface failures separately (an `edit_file` old_string that doesn't match, malformed or empty
     patches, tool-call schema errors) before attributing a failure to the model.
2. **The decoy test (readership).**
   - To know whether a model uses a cue, pit it against another cue and record which one it follows, normalized to
     chance.
   - Here: when a graph tool points to a plausible decoy, does the agent go there? That is Q2's core measurement.
3. **Congruent / neutral / incongruent.** True graph, no graph, scrambled graph. The classic conflict design gives
   three arms with a built-in ordering prediction.
4. **Pre-registration with a decision rule.**
   - Freeze the design, outcomes and decision rule before any data, and date any change as an amendment.
   - A pre-registered null is still a result. The judges score verifiability, and a frozen plan is the strongest
     verifiability signal we can give.
5. **A reproduction gate before any intervention.**
   - Reproduce the baseline first, and check determinism.
   - Agent runs are noisier than single forward passes (about 9% of outcomes flip between identical runs in one
     report), so use paired seeds and McNemar tests.
6. **Select on one set, test on another.** In that project, the best of 36 settings looked good on the tuning half
   and vanished on held-out data. Here: tune skills, prompts or LoRA on held-in repositories, test on a held-out
   repository and on the hidden leaderboard.
7. **Independent re-derivation.** A second agent recomputes every headline number from the raw per-trial logs with
   its own script before anything goes in the paper.
8. **Dated logging with reasons.** Every decision goes into LOG.md when it is made, with a "Why." line, so either
   of us can pick up the thread without the other in the room.
9. **An infrastructure lesson.** Long GPU jobs launched as background tasks from Claude Code can be killed when the
   machine runs low on memory. Run long jobs on cloud compute, or in their own window.

Claude Science has a skill for this workflow: `preregistered-experiment-protocol`.
