# Ideas and verdicts

A brainstorm record. Nothing here is a commitment until it is in [BRIEF.md](../BRIEF.md) under "Decided" or in a
pre-registration.

## Sep 27: three candidates, each attacked by an adversarial prior-art agent

| Idea | One line | Verdict | Why |
|---|---|---|---|
| A | Does the agent read its code graph? Serve true / missing / subtly wrong graphs and see whether it follows the decoys. | WEAKENED, best of three | Nobody has done it inside end-to-end bug-fixing with behavioral outcomes, but every ingredient exists (Oracle Poisoning, CodeCompass, Don't Blindly Trust It). |
| B | Line numbers vs symbol names as the way the model addresses code, holding the target fixed. | WEAKENED, core published | FLAME (ASE 2025) already shows the line-number penalty. Code-graph encoding comparisons already appear in LocAgent's appendix. |
| C | Knows vs acts: probe hidden states for the bug location vs where the agent actually looks. | WEAKENED, crowded | 2026 probes on 22.7k SWE trajectories, a probe-guided pruner, steering of Gemma-4-26B agents. It also risks being trivially true. |

## Sep 29-30: inputs

- **Team discussion (Sep 29):** real RL or post-training is hard to resource, so the approach has to be clever. The code-graph part could be a paper on **"externalizing memory" in agent systems**.
- **A shared screenshot** (an AI assistant's answer, not a person's): the paper track could produce something more
  interesting than the winning agent. It suggests a clean result on *when explicit code-graph structure helps an LLM,
  what it supplies that semantic retrieval does not, and whether the model can be trained to exploit it*. The
  organizers' emphasis on graphs suggests they want exactly that.

## The merged design (current)

Diagnose, measure, fix. See BRIEF.md for the full version.

1. **When does structure help?** An offline map: graph distance vs semantic-search rank of the gold symbols.
2. **What does it add over semantic retrieval?** Counterfactual tool arms that scramble structure, embeddings, both,
   or remove the tools; readership measured as how often the agent follows the decoys.
3. **Can cheap training make the model use structure?** A no-training skill baseline, then a LoRA on Gemma's own
   successful graph-using runs. Measure reliance, not just score, and check on the hidden leaderboard.

## Parked

- **Graph encodings as soft tokens** (GraphToken for code): high judge appeal, but the harness only accepts prompts,
  tools, skills and LoRA adapters, and it is too heavy for the time we have.
- **Readout failure accounting:** how much of Gemma's failure is interface or format failure (edit_file mismatches,
  malformed patches) rather than inability. Useful as a diagnostic inside Q2, not a paper on its own.
