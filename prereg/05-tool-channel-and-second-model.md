# Pre-registration 05: experiment D (the legible encoding inside the tool's own result, and a second model)

Status: FROZEN on Nov 10, 2026, 2:07 AM EST, by the commit that adds this file, before any replay of arm PE ran on any
platform and before any replay of the second model existed. It amends pre-registrations 02 to 04 and changes none
of their rules.
Tags: [Claude Code] wrote it; [team] asked for the additional runs and had not read this text when it was frozen.

## Why

1. The practical recommendation concerns the tool's own output: write each neighbor with its file, lines and first
   definition line. But the legible encoding (arm E) was tested only as a harness note with arm H's wording, never
   as the result of a `get_code_neighbors` call. Experiment D1 tests it in the tool channel.
2. Every result so far is one model (Gemma-4-31B). Experiment D2 asks whether the main effect, E minus H, holds on
   a second model.

## D1: the tool channel

Same platform and settings as experiment C: a rented single A100, tensor-parallel size 1, Python 3.12, harness v28
(adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma 0.2.7), the same model weights (Gemma-4-31B QAT W4A16) and the
same replay code. The run records its versions.

| Arm | Last piece |
|---|---|
| P | an inserted `get_code_neighbors` call on the queried node; its result lists the true neighbors as bare names (pre-registration 02) |
| PE | the same call; its result is arm P's with the list replaced by arm E's entries (name, file, lines, first definition line), in arm E's order; every other field is arm P's |
| E | arm E's harness note, unchanged (pre-registration 03) |

Same 407 states, seeds 1 to 3. States file: `analysis/fork_states_d/states.jsonl`, md5 `d3105df0dc4aa43d7bb0afbdd6123b44`,
built by `analysis/make_states_d.py` from `analysis/fork_states_c/states.jsonl` (md5 beginning `9d7ad4bbd8f4`) by
adding arm PE and changing nothing else.

Gate: fidelity as G1 of pre-registration 04. On 24 states under arm A, the median absolute relative difference
between the replayed and the logged prompt size is at most 2%. If it fails, the run is not analyzed.

**T1, the encoding inside the tool result.** PE minus P, on any unopened true neighbor touched. "The legible
entries raise following in the tool channel" if the lower 95% bound is above 0; otherwise not, reported with the
interval.

**T2, the channel.** PE minus E, on the same outcome, with 95% and 90% intervals. "No channel difference" only if
the 90% interval lies within plus or minus 2 points. Otherwise the difference is reported with its intervals.

Secondary, descriptive: graph tool as the next call, thought text present, completion tokens, prompt tokens, by arm.
The drift of arm E against the experiment C run (same states and seeds, paired by state and seed) is descriptive
and changes no rule.

## D2: a second model

`gemma-4-12b-it` (Kaggle `google/gemma-4`, Transformers, version 2, unquantized), with the same harness, agent
configuration, system prompt and tool declarations as every run so far, served by the same server version with
the same tool-call and reasoning parsers, temperature and thinking budget, on the platform of D1. Arms A, H, E and RE (pre-registrations 02
and 03, unchanged texts) on the same 407 states and seeds 1 to 3, from the same states file.

Stated limits:

- The histories are the 31B agent's own runs. The second model continues another model's trajectory from the fork,
  so D2 tests whether it follows the note in a context it did not produce, not how it would behave on its own runs.
- No logged prompt sizes exist for this model, so the prompt-size comparison is a plumbing check with no rule: it
  is reported and can stop nothing.
- The second model is a smaller member of the same family, served unquantized, while the first is served with
  4-bit weights. D2 is a replication within one model family, not across families.

**M1, replication.** E minus H, on any unopened true neighbor touched. A lower 95% bound above 0 means "replicates
on the second model"; otherwise "does not replicate on the second model". It is reported either way.

Reported with intervals, with no rule: E true minus RE rewired (the rewired list is not like-for-like, as recorded
in NOTES.md on Nov 9: its entries exclude gold-patch nodes and files and names in view, the scored true entries do
not); H minus A; E minus A.

Interface failures: if more than 20% of an arm's replays are interface failures, that arm's rates are reported as
unreliable.

## Common to D1 and D2

- Outcomes and exclusions as in pre-registrations 02 to 04: the first function call after the fork; a touch of a
  listed node by a read, edit, write or content-showing shell view, with the harness's caps; "any unopened true
  neighbor touched" over the true neighbors in unopened files. Every arm is scored with the same spans from the
  states file. Interface failures (error, no call, unknown tool, malformed arguments) are excluded and reported by arm.
- 95% bootstrap intervals clustered by state, 2,000 resamples; 90% where stated.
- Complete states only: a state counts if every arm of that experiment and all three seeds gave a usable replay.
- States are processed in a fixed shuffled order, so a run cut short is a random subset. The rules apply if at
  least 200 states are complete; below that everything is EXPLORATORY.
- Every contrast uses arms of one run. Hosted runs and the experiment C run appear beside a result for comparison
  only and are never pooled into a contrast.
- Analysis: `analysis/analyze_d.py d1 <run>` and `analysis/analyze_d.py d2 <run>`; the D1 fidelity gate with the G1
  code of `analysis/gates_c.py`.
- Anything not listed here is EXPLORATORY.

## Power, stated as assumptions

About 1,160 replays per arm if all states complete. At the hosted rates, P is about 3% and E about 8%, with a
half-width near 2 points for a difference between them. So a PE rate of about 6% or more separates from P (T1); a
PE rate near P's would not. For T2, the 90% interval of PE minus E has a half-width of roughly 1.7 points (the
hosted 95% half-width scaled to 90%), so "no channel difference" needs a point estimate within about 0.3 points of
zero: a demanding bar, which close channels can miss by chance. For M1, the 31B
difference was 5.5 points with a half-width of about 2.1; a second model with half that effect is near the
detection limit, so "does not replicate" is weak evidence of no effect and is reported with its interval.

## What is reported regardless of outcome

All rates of every arm with intervals, the fidelity gate (D1) and the prompt-size check (D2), the inserted texts and
tool results, the per-arm interface-failure counts, the raw replay outputs, and the harness, server and model
versions recorded by each run. Anything not listed here is labeled EXPLORATORY.

## Amendment of Nov 10, 2026, 2:47 AM EST: the second model (frozen before any replay of a second model existed)

The model named for D2, `gemma-4-12b-it`, could not be served. The pinned server (vLLM 0.19.1 with transformers
5.13.1) fails at engine start on its architecture (`Gemma4UnifiedForConditionalGeneration`): `ValueError: Expected
hidden_size to be 3840, but found: 256`, in the smoke test started at 2:41 AM EST. No replay ran and no outcome
exists for it.

D2 is run instead on two models of the first model's architecture class (`Gemma4ForConditionalGeneration`), both
from Kaggle `google/gemma-4`, Transformers, version 1, unquantized, chosen from their configuration files alone:

- D2a: `gemma-4-26b-a4b-it`
- D2b: `gemma-4-e4b-it`

Arms (A, H, E, RE), states, seeds, outcomes, limits and rule M1 are unchanged and apply to each model separately.
Stated in advance: two replications are two chances, so the paper reports both, whichever way each falls, and
does not present one without the other. If one of them cannot be served either, that is reported and the other
stands alone.
