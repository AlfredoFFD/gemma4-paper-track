# The replay tool

What it does: it takes a recorded run of an agent, paused at one step, changes the last thing the agent is shown,
and asks the competition harness's own compiled agent for its next call. Everything before the last message is
identical across conditions, so a difference in the next call is caused by that message.

Use it to test a change to what an agent sees (a tool's output format, a note, an instruction) in about two
GPU-hours, before paying for a full evaluation.

## Pieces

| File | What |
|---|---|
| `analysis/replay.py` | `build_agent` compiles a submission folder the way the harness does, with tools that never execute. `run_one_step(agent, state, condition, seed)` seeds a session with the state's history, delivers the condition's last message, makes one model call and returns the first function call with its arguments, the model's text and token counts. |
| `analysis/replay_k.py` | The same for several calls: `read_file` and read-only shell commands execute through the harness's own tool functions on a checkout of the task snapshot; the episode stops at the first edit, write or other command. |
| `analysis/fork_states.py` | Builds paused states from public traces of the starter agent (the rules for where to pause and which graph node to query are in its docstring), and holds the frozen scorer `touches`. |
| `analysis/make_states_d.py`, `analysis/make_states_f.py` | Add a condition to every state without touching the others (each checks that removing the new condition gives back the original bytes). |
| `analysis/modal_w/forks_w_runner.py` | The one-step runner: installs the competition wheelhouse and one of two harness versions, starts the model server as the competition's notebook does, replays every (state, condition, seed), and records versions. It resumes after an interruption. |
| `analysis/modal_g/forks_g_runner.py`, `forks_09_runner.py` | Several calls from a paused state, and fresh episodes from the task prompt with two optional harness changes. |
| `analysis/agents/base/` | The starter agent's prompt, tool list and sampling settings, as shipped. |

## A state

One JSON object per line. The fields a new experiment needs:

- `steps`: the recorded run up to the pause (task prompt, model calls, tool results).
- `arms`: one entry per condition. `{"user_text": "..."}` delivers a note as the last message;
  `{"call": {"name": ..., "args": ...}, "response": {...}}` inserts a tool call and delivers its result. The condition
  named `A` needs no entry: it replays the run's own last tool result.
- `task`, `repo`, `base_commit`, `run`, `fork`: where the state comes from.
- Fields used only for scoring the graph experiments (`true_neighbors`, `neighbor_spans`, `unshown_true_neighbors`).

To test a new last message, add an entry to `arms` and name it in the runner's `ARMS`.

## Check the plumbing without a GPU

```
python analysis/replay.py test <one state as a .json file> <condition> [<condition> ...]
```

A stand-in model records the request. The command prints the last messages of each condition exactly as the model
would receive them and checks that every condition shares the same prefix. It needs the harness source on
`PYTHONPATH` (the competition's wheelhouse) and `google-adk`.

## Run it

The runners read their settings from the environment (`WHEELHOUSE_DIR`, `INPUTS_DIR`, `MODEL_DIR`, `OUT_DIR`,
`STATES_FILE`, `ARMS`, `HARNESS_VARIANT`, `CONCURRENCY`, `TIME_BUDGET_S`). The files next to them
(`forks_w_modal.py` and the others) show one way to start them on a rented GPU; on a Kaggle session the same
runner works with the competition's model and wheelhouse datasets attached. One A100-80GB replays the 407 states
under one condition and three seeds in about an hour.

## Score it

Each experiment's analysis script reads the runner's `results.jsonl`. For a new question, write the outcome as a
function of the recorded call and the state, fix it before the run (`prereg/` has eleven examples), and cluster the
bootstrap by state or by task (`analysis/analyze_forks.py`: `boot_ci`, `diff_ci`).

## What it cannot tell you

One call, or a few, from a state the agent reached by itself. It measures what the agent does next, not whether
the task gets fixed. The states in this repository come from one model's runs on the public tasks, early in the
run.
