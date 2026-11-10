# Pre-registration 07: experiment F (how earlier tool results are rendered in the replayed history)

Status: FROZEN on Nov 10, 2026, 5:09 AM EST, by the commit that adds this file, before any replay of an arm ending in "w" ran on
any platform. It adds to pre-registrations 02 to 06 and changes none of their rules.
Tags: [Claude Code] wrote it; [team] asked for the additional runs and had not read this text when it was frozen.

## Why (found on Nov 10, EXPLORATORY, before this freeze)

1. In the replays, a `read_file` call often arrives with a line bound under a mangled argument name, for example
   `start_line"`. The agent framework drops an argument name it does not know, so the read returns the file from
   line 1 (`google/adk/tools/function_tool.py`, the filter on valid parameters). Share of first-call reads with a
   line bound that carry such a name, 31B model: 36% in arm A, 13% to 17% in arms P, H and D, 5% in arm E (hosted
   runs); 0 of 2,572 with the 26B-A4B model on the same platform. In the original runs, the model's own next call at
   the same states had it in 2 of 201 such reads (1.0%); over the 318 public base traces, in 42 of 2,012 (2.1%),
   each of which returned the file from line 1 (`analysis/mangled_args.py`).
2. The harness source shows one difference between the original runs and the replays. In the harness version
   closest to the original runs that we hold (v25, files dated Sep 27) every tool returns its JSON as a string,
   which the agent framework wraps as `{"result": "<string>"}`. In v28, which every replay uses, every tool returns
   a dictionary, and `analysis/replay.py` rebuilds each earlier tool result as a dictionary. The replayed prompt is
   smaller than the logged one in 24 of 24 fidelity states (median 1.66%).
3. Scoring the mangled reads as the model wrote them leaves the registered outcomes almost unchanged (E minus H:
   +5.50 becomes +5.58; PE minus P: +6.35 becomes +6.77; `analysis/mangled_sensitivity.py`), so no earlier result
   depends on this. Open: whether the rendering explains the size gap and the mangled names, and whether the
   encoding effect holds when the history is rendered as the original agent saw it.

## Arms

Same 407 states (`analysis/fork_states_d/states.jsonl`, md5 `d3105df0dc4aa43d7bb0afbdd6123b44`), seeds 1 to 3, and
the platform, model (Gemma-4-31B QAT W4A16), harness (v28) and settings of experiment D1.

| Arm | History | Last piece |
|---|---|---|
| A | as in every earlier replay: tool results rebuilt as dictionaries | the pause's own tool result |
| Aw | every tool result of the history, the last one included, delivered as `{"result": "<the logged JSON string>"}` | the same |
| Hw | as Aw | arm H's note, unchanged |
| Ew | as Aw | arm E's note, unchanged |

Implementation: `analysis/modal_w/forks_w_runner.py` (md5 `65372125c2e23b48f5ee0e829a5e4167`), the experiment C/D runner plus a wrapper
around `replay.arm_messages` for arms whose name ends in "w"; `analysis/replay.py` is unchanged.
`analysis/modal_w/forks_w_modal.py` (md5 `97b5807194093965b3307f7d0d8a3fc5`) starts it. The run records its versions.

## Rules

Analysis: `analysis/analyze_w.py` (md5 `3054cfd448425386a5aac3e141fcc60a`).

**F1, prompt size.** On the 24 fidelity states, the median absolute relative difference between arm Aw's prompt
size and the size the original run logged at the same step. "The rendering accounts for the size gap" if it is at
most 0.5%. Arm A's value in the same run is reported beside it.

**F2, mangled names.** Share of usable replays whose first call is a `read_file` with a mangled line-bound name
(a name that is not a plain identifier and reads `start_line` or `end_line` once quotes, backslashes and spaces
are removed), arm A minus arm Aw. "The v28 rendering raises mangled bound names" if the lower 95% bound is above 0;
otherwise no detectable difference. The shares among reads with a line bound and the original runs' own share at
the same states are reported beside it.

**F3, the encoding effect under the original rendering.** Ew minus Hw on any unopened true neighbor touched.
"Holds under the original runs' rendering" if the lower 95% bound is above 0; otherwise "not detected under the
original rendering". Reported with the interval either way.

Descriptive, no rule: Aw minus A, Ew minus Aw and Hw minus Aw on the registered outcome; the first call's tool by
arm; how often the first call names the same tool, and the same file, as the original run's own next call, under A
and under Aw.

## Common rules

Outcomes, exclusions, the scorer and the bootstrap as in pre-registrations 02 to 05: the first function call after
the pause; interface failures (error, no call, unknown tool, malformed arguments by the frozen `valid_call`)
excluded and reported by arm; 95% bootstrap intervals clustered by state, 2,000 resamples; complete states only (the
four arms and seeds 1 to 3 usable); a fixed shuffled state order, so a run cut short is a random subset; the rules
apply if at least 200 states are complete, below that everything is EXPLORATORY. Every contrast uses arms of this
run. Anything not listed here is EXPLORATORY.

## Stated limits

- "As the original runs' harness delivered them" is inferred from the v25 source and from the framework's wrapping
  of results that are not dictionaries; the public logs of the original runs do not record the harness version.
  F1 tests this inference.
- The "w" arms change only how earlier tool results are delivered. The tool declarations, the system prompt, the
  agent configuration and the server are those of v28.
- One model. The causes of the mangled names inside the model or the tool-call parser are not examined.

## Power, stated as assumptions

About 1,190 replays per arm. For F2, arm A's share was 17.7% of replays in the hosted run; a fall to the original
runs' level would be far outside any interval. For F3, the 31B difference was 5.5 points with a half-width of about
2.1 in the hosted runs and D1.

## What is reported regardless of outcome

Every arm's rates with intervals, the three rules, both fidelity files, the per-arm interface-failure counts, the
raw replay outputs, and the versions recorded by the run.
