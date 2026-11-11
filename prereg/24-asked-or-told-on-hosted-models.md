# Pre-registration 24: asked or told, on models of other publishers through a hosted API

Status: FROZEN on Nov 11, 2026, 4:58 AM EST, by the commit that adds this file, before any replay of the full run it governs
was made. Before the freeze there was one plumbing check on the API (24 replays on one model); what was seen of it is
listed under "What has been seen". Tags: [Claude Code] wrote it; [team] had not read this text when it was frozen.

File hashes at freezing (md5): `analysis/modal_g/forks_24_runner.py` `7cdccc91d744794fd5cc9ff2dee4875b`,
`analysis/modal_g/forks_24_modal.py` `bc32725ff699d55645565c6081b4d4ae`, `analysis/analyze_24.py`
`d091c5aa49018aef13ad43576200c8ba`, `analysis/store_24.py` `82b497bc1b99c843d8d5204d38100743`. Used unchanged:
`analysis/analyze_20.py` `b92cfef7c0eaf48c730ed1b26cfacf60`, `analysis/analyze_19.py`
`cb3ec6aa469f6f5f55e2711d4d2a9339`, `analysis/analyze_15.py` `5dd2680966b40d7ed717c5387766ccf0`,
`analysis/modal_g/forks_20_modal.py` `379d7ed70142fc0ea5a95577cd50379c` (its order of the steps and its arm map),
the states file of pre-registration 20 `analysis/fork_states_t/states.jsonl` (not tracked; rebuilt by
`analysis/make_states_t.py`) `750b3e0952608bf023e69a338f26b030`, checked by md5 at launch on this machine and in the
container.

## Why

Pre-registration 20 showed on Gemma-4-31B that a line the agent is told, before it has searched, is used (USES THE
LINE 2.5% of replays with nothing added, 39.0% with the hits in a note), and less often than the same line in the
result of its own search (61.0%). Pre-registration 19 showed that the two earlier one-call contrasts hold on seven
models of other publishers. This experiment asks whether the first result, "a line the agent is told is used, and
less often than one it asked for", holds beyond Gemma-4-31B.

## Design

- Steps and arms: those of pre-registration 20, unchanged. The 53 paused steps (44 runs of 26 tasks, two
  repositories), each cut one call before the agent's own numbered search, built by `analysis/make_states_t.py`. Arms
  NONE (nothing added), TOLD (a note, "Matches in the repository:", with the hit lines the search was about to
  return), TOLDX (a note of the same form with the hits of another recorded search; on 26 steps) and ASKED (the
  recorded search call and its result). The records, histories and notes are 20's records, read from the same states
  file; each request is built by the same replay module and agent files as in 19 and 20.
- Harness: the replays run the competition's agent with the harness wheels of Sep 30 (v28: adk_eval_core 0.1.0,
  adk_submission 0.2.12, swegemma 0.2.7), the release of the replays of 15, 19 and 20. The histories are those of
  recorded Gemma-4-31B runs, so every other model continues a history that Gemma-4-31B wrote, as in 19.
- Models: the seven models of pre-registration 19, all of which passed its gate in both its designs:
  Qwen3-30B-A3B-Instruct-2507, Qwen3-235B-A22B-Instruct-2507, gpt-oss-120b, DeepSeek-V4.1-Flash-1017, GLM-5.3-Flash,
  MiniMax-M3.1-Flash, Nemotron-3-Super-120B, through the same provider.
- Replays: one model call each, seeds 1 to 3, per model 53 steps x 3 arms x 3 seeds + 26 steps x TOLDX x 3 seeds =
  555, so 3,885 in all. All seven models in one launch, each in its own CPU container.
- The API path is that of 19, with its limits, each recorded per call or per model: the chat template and the
  tool-call parsing are the provider's; no reasoning parameter is sent, so models that reason by default do; no stop
  string is sent and the output limit is the agent's own; the agent's temperature (0.2) and top-p (0.95) are sent and
  may be ignored by models that list no sampling parameters; seeds are sent but not guaranteed; prompts may be cached;
  the concurrency per model is the one 19 used (4 for the two Qwen3 models, 8 for the others). A row also keeps the
  raw reply (text, tool calls with their argument strings, the reasoning text if the API returns it apart); the scored
  call is the first tool call as the agent framework parsed it.
- Order and stops: the steps are taken in 20's fixed random order (`random.Random(20)`), each step's records NONE,
  TOLD, TOLDX, ASKED one after the other, so a run cut short is a random subset of steps. A cost stop per model: no new
  call starts once the model's token cost passes 3 dollars (in 19 the 549 replays of design 17 cost 0.40 to 1.36
  dollars per model). No new call starts after 5 hours; 10 API failures in a row stop the model. A model cut short
  keeps its verdicts if the floors below are met.

## Outcomes

Those of pre-registration 20, by its scorer (`analyze_20.py`, imported): USES THE LINE, the next call is a first read
of a file named in the note (for NONE and ASKED: in the step's own search result; for TOLDX: in its own note, among
the files that qualify it) that asks past line 1; SEARCHES, the next call is a search. A misspelled bound counts as
written. A reply without a usable tool call (an error, no call, an unknown tool, malformed arguments) is counted
apart, and a failure that was the API's (no reply after the retries) is counted apart from the others.

## Gate

A model enters the rules only if at least 80% of its rows hold a usable tool call, the share 19 allowed. A model below
it is reported with its counts and left out of every rule and of the reading across models.

## Rules, per model

Bootstrap by step, 2,000 resamples, seed 0, paired by step (`analyze_forks.diff_ci`, as in 20). A step enters a rule
only if both arms the rule compares have a usable replay for each of seeds 1 to 3. A step missing any of those six
rows, whether the API gave no reply after the retries, the cost stop or the time budget cut the run, or the reply had
no usable call, is left out of that rule only; it stays in every rule whose two arms it has complete. The number of
complete steps is printed beside each rule. A rule needs at least 40 complete steps (the floor of T1, T2 and T4 in
20); below it the numbers are printed without a verdict, and the rule counts as not met.

- **W1.** USES THE LINE, TOLD minus NONE: "used" if the interval lies above zero; otherwise not met.
- **W2.** USES THE LINE, ASKED minus TOLD: "used less than asked" if the interval lies above zero; "used more than
  asked" if it lies below zero; otherwise "no detectable difference". W2 is met only in the first case. ASKED is
  paused one call later than TOLD (after the search, not before it); the text says so wherever it gives this result,
  as in 20.
- **W3.** SEARCHES, TOLD minus NONE: "telling replaces the search" if the interval lies below zero; otherwise not met.

Printed without a rule: the ratio TOLD / ASKED on USES THE LINE with its interval (`analyze_15.ratio_ci`, as T2 of
20); TOLD minus TOLDX on USES THE LINE on the steps complete in both (TOLDX exists on 26 steps, so no floor and no
verdict); each interval again with tasks resampled in place of steps; the rates per arm; what the next call does under
each arm; replies with more than one tool call; reasoning lengths; cost and time. The rows of 20 (Gemma-4-31B) are
analyzed by the same script and printed as a reference row; they enter no rule and no count across models.

## Reading across models, fixed now

Let n be the number of models through the gate. If n is at least 5, a model counts if W1 and W2 are both met on it,
and the needed number is ceil(6n/7): 6 of 7, 6 of 6, 5 of 5.

- The sentence "a told line is used, and less often than an asked one, on models of other publishers" is written only
  if at least that many models count.
- If W1 is met on at least that many models and fewer count, the paper says the discount is not general and names the
  models on which W2 is not met.
- Any other outcome, and any outcome with fewer than 5 models through the gate, is reported as it falls, model by
  model, with no sentence across models.

No pooled test across models. W3 is reported in the same table, in how many models it is met.

## What we expect, written before any session of the full run

W1 met on all seven. W2 met on five or more. W3 met on all seven.

## What has been seen

The results of 19 and 20 in full. From the build: the analysis run on 20's stored rows reproduces 20's registered
numbers (USES THE LINE 2.5%, 39.0%, 61.0%, 26.9% under NONE, TOLD, ASKED, TOLDX; T1 +36.5, ratio 0.64, T4 -42.8), and
on synthetic copies of those rows (a model pushed below the gate, a model whose TOLD replies were replaced by its
ASKED replies) it applies the gate and the reading across models as written above; those numbers say nothing about
this experiment. The plumbing check, the one session on the API before the freeze: Qwen3-30B-A3B-Instruct-2507, the
first 2 steps of 20's order that have a TOLDX record, every arm, seeds 1 to 3; 24 replays, 24 API calls, no retry, no
failure, 24 replies with a parsed tool call, about 0.02 dollars, 27 seconds. The checker read the requests: per step
and seed, TOLD's messages are NONE's plus one user message equal to the note, TOLDX's the same with its own note,
ASKED's are NONE's plus an assistant message calling `run_command` with the recorded search command and a tool
message with its result, the tool declarations and sampling parameters are the same in every arm, the seed is sent,
and ASKED's prompt has the same number of tokens as 19's replay of the same step under arm S on the same model. It
printed the name of the tool of each next call (under NONE `search_similar_code` in 3 replays and `read_file` in 3;
`read_file` in all 18 replays under TOLD, TOLDX and ASKED); no outcome was computed on those rows, and they are not
stored. The two steps of the check are replayed again in the full run like every other step.

## Not covered

One scaffold, the competition's agent. Gemma-4-31B's histories: the other models continue steps they did not
produce. One provider, whose chat template and tool-call parsing stand between the history and the model. The note
as the one channel of telling: a user message after the last tool result, with no command in the history that its
hits would answer, which is the point of the comparison with ASKED and also its limit. Two repositories, 43 of the 53
steps from one of them. TOLDX on half of the steps.

## Notes added after the freeze

