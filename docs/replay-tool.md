# The replay tool

What it does: it takes a recorded run of an agent, paused at one step, changes the last thing the agent is shown,
and asks the competition harness's own compiled agent for its next call. Everything before the last message is
identical across conditions, so a difference in the next call is caused by that message.

Use it to test a change to what an agent sees (a tool's output format, a note, an instruction) in about two
GPU-hours, before paying for a full evaluation.

## What you need

| To do this | You need |
|---|---|
| Re-run the analyses of the stored replays | A clone and Python 3.11: `py -I -X utf8 analysis/reproduce.py --list` shows which jobs are ready. The others name the missing input. |
| Re-run the analyses that read tasks, snapshots or graphs | The competition data in `data/` (about 21 GB; join the competition on Kaggle, then `kaggle competitions download -c gemma-4-developer-agent -p data/`; it is not redistributed here), then `py -I -X utf8 analysis/snapshot_index.py` once. |
| Rebuild the paused steps that git ignores | The competition data and, for most sets, other teams' public runs (`analysis/results/public/README.md`). See "Where the paused steps come from". |
| Check the plumbing of a new last message | `google-adk` 1.36.1 and the harness wheels (below). No GPU, no key. |
| Replay on Gemma 4 | The above plus a GPU serving the competition's model (an A100-80GB in our runs), `vllm` 0.19.1 and `litellm` 1.82.4. |
| Replay on another model | The above without the GPU, plus a key for a hosted OpenAI-compatible API. See "A hosted API instead of a GPU". |

The harness wheels come from the competition's wheelhouse dataset on Kaggle (`metric/gemma-4-developer-agent-wheelhouse`).

## Pieces

| File | What |
|---|---|
| `analysis/replay.py` | `build_agent` compiles a submission folder the way the harness does, with tools that never execute. `run_one_step(agent, state, condition, seed)` seeds a session with the state's history, delivers the condition's last message, makes one model call and returns the first function call with its arguments, the model's text and token counts. |
| `analysis/replay_k.py` | The same for several calls: `read_file` and read-only shell commands execute through the harness's own tool functions on a checkout of the task snapshot; the episode stops at the first edit, write or other command. |
| `analysis/fork_states.py` | Builds paused states from public traces of the starter agent (the rules for where to pause and which graph node to query are in its docstring), and holds the frozen scorer `touches`. |
| `analysis/make_states_*.py`, `analysis/make_population_*.py` | Build the other sets of paused steps. `make_states_d.py` and `make_states_f.py` add a condition to every state and check that removing it gives back the original bytes. |
| `analysis/modal_w/forks_w_runner.py` | The one-step runner: installs the competition wheelhouse and one of two harness versions, starts the model server as the competition's notebook does, replays every (state, condition, seed), and records versions. It resumes after an interruption. |
| `analysis/modal_g/forks_g_runner.py`, `forks_09_runner.py` | Several calls from a paused state, and fresh episodes from the task prompt with two optional harness changes. |
| `analysis/modal_g/forks_19_runner.py` | The one-step replays with the model call sent to a hosted API. |
| `analysis/agents/base/` | The starter agent's prompt, tool list and sampling settings, as shipped. |

## Where the paused steps come from

A paused step holds the recorded run up to the pause: the task prompt (the issue text) and the tool results the
agent saw (repository code). Every set is built from the competition data or from other teams' public runs, by
the script below, run from the repository root with `py -I -X utf8`. Some sets are tracked; the sets marked
"ignored" are not shipped and have to be rebuilt.

| Folder | Designs | Built by | Reads | In git |
|---|---|---|---|---|
| `analysis/fork_states/` | 02, 03 | `analysis/fork_states.py` | GraphLoc's public base traces (`data/graphloc/out`), `data/tasks.jsonl`, `data/graphs`, the snapshots | `states.jsonl` tracked; the per-state `*.json` ignored |
| `analysis/fork_states_c/` | 04 | `analysis/fork_states.py analysis/fork_states_c` | the same | `states.jsonl` tracked |
| `analysis/fork_states_d/` | 05, 07, 10, 19 (design 10) | `analysis/make_states_d.py` | `fork_states_c` (md5 checked) | tracked |
| `analysis/fork_states_k/` | 06 | `analysis/make_population_k.py` | `fork_states_d`, `data/tasks.jsonl` | `population.json` tracked |
| `analysis/fork_states_g/` | 08, 09 | `analysis/make_population_g.py` | GraphLoc's public base traces, `data/tasks.jsonl`, `fork_states_k` | tracked |
| `analysis/fork_states_f/` | 12 | `analysis/make_states_f.py` | `fork_states_d` (md5 checked) | ignored |
| `analysis/fork_states_h/` | 13 | `analysis/make_states_h.py` | `fork_states_d` (md5 checked) | `states.jsonl` ignored |
| `analysis/fork_states_s/` | 15, 17, 19 (design 17) | `analysis/make_states_s.py` | `data/graphloc/out` | ignored |
| `analysis/fork_states_t/` | 20 | `analysis/make_states_t.py` | `data/graphloc/out` | `states.jsonl` ignored; `manifest.json` (md5, counts) tracked |
| `analysis/fork_states_w/` | 16 | `analysis/make_states_w.py` | `fork_states_g` and the traces of our run 14 (`data/forks_14_modal/out_14`, not distributed) | ignored |

## A state

One JSON object per line of a `states.jsonl`.

| Field | Meaning |
|---|---|
| `task`, `repo`, `base_commit` | The task and its repository snapshot. |
| `run`, `fork` | Which recorded run, and which pause in it (`fork` defaults to 0). |
| `node` | The graph node the conditions are about. Required: the result row copies it. |
| `steps` | The recorded run up to the pause, in the harness's trace format (below). The history must end on a tool result. |
| `arms` | One entry per condition. `{"user_text": "..."}` delivers a note as the last message; `{"call": {"name": ..., "args": ...}, "response": {...}}` inserts a tool call and delivers its result. The condition named `A` needs no entry: it replays the run's own last tool result. |
| `true_neighbors`, `unshown_true_neighbors`, `neighbor_spans`, `file_lines`, ... | Inputs of the scoring of the graph designs (written by `analysis/fork_states.py`). |

One element of `steps`:

| Field | Meaning |
|---|---|
| `source` | `system`, `user` or `agent`. |
| `extra.event_type` | Steps of type `system_instruction` are skipped (the agent renders its own). The `task_prompt` step becomes the session's problem description. |
| `message` | The text: the prompt of a user step, the model's text of an agent step. |
| `tool_calls[]` | `{"function_name", "arguments"}` per call. Only the first call's result is replayed. |
| `observation.content` | The tool result as JSON text, parsed back into a dictionary. |

## A result row

One JSON object per line of a runner's `results.jsonl`.

| Field | Meaning |
|---|---|
| `task`, `run`, `fork`, `arm`, `seed`, `node` | The cell. |
| `next_call` | `{"function_name", "arguments"}` of the first call of the response, or null. |
| `all_calls` | Every call of that response. |
| `thought`, `text` | The model's reasoning text and its plain text. |
| `usage` | `prompt_tokens`, `completion_tokens`, `total_tokens`. |
| `error`, `latency_s` | The exception text if the call failed, and the seconds it took. |
| `decoy` | The one-step runner: the decoy node for conditions `Pp` and `Hp`, else null. |
| `api` | Hosted runs only: the model id the API reported, tokens, finish reason, attempts and their errors. |

Next to it each run stores `versions.json` (harness release, wheel files, settings), `pip_freeze.txt` and
`summary.json`.

## How the outcome is scored

Each experiment fixes its outcome before the run, in its pre-registration (`prereg/`, one file each). The shared pieces:

- `analysis/gates_c.py`, `failure(row)`: `error`, `no_call`, `unknown_tool` or `malformed_args`, or None when the
  row is usable. These are the interface failures, counted apart from the model's choices.
- `analysis/fork_states.py`, `valid_call(call)`: False for arguments the harness could not have executed.
- `analysis/fork_states.py`, `touches(call, target, node_id, ...)`: `read`, `edit`, `graph` or None. A read counts
  only for the lines the harness would return: `read_file` is capped at 150 lines and 10,000 characters from its
  start line, a shell view at 5,000 characters of output. Malformed calls never count.
- Intervals: a bootstrap clustered by state or by task (`analysis/analyze_forks.py`: `boot_ci`, `diff_ci`).

## Test another way of writing a graph answer

Add a condition to one state and check what the model would receive, with a stand-in model (no GPU, no key):

```
py -I -X utf8 -c "import json; s = json.loads(open('analysis/fork_states_d/states.jsonl', encoding='utf-8').readline()); s['arms']['MINE'] = {'user_text': 'your note'}; json.dump(s, open('mine.json', 'w', encoding='utf-8'))"
PYTHONPATH="<wheels>/adk_eval_core-0.1.0-py3-none-any.whl:<wheels>/adk_submission-0.2.12-py3-none-any.whl:<wheels>/swegemma-0.2.7-py3-none-any.whl" python -X utf8 analysis/replay.py test mine.json MINE
```

(On Windows the `PYTHONPATH` separator is `;`.) For a graph answer written as a tool result, use
`{"call": {"name": "get_code_neighbors", "args": {"node": ...}}, "response": {...}}` as the condition instead.
The command prints the last messages of each condition exactly as the model would receive them and checks that
every condition shares the same prefix and that a note is the one added message. To replay it on the model, add
the condition's name to the runner's `ARMS`.

## Run it on Gemma 4 (GPU)

The runners read their settings from the environment (`WHEELHOUSE_DIR`, `INPUTS_DIR`, `COMP_DIR`, `MODEL_DIR`,
`AGENT_DIR`, `OUT_DIR`, `STATES_FILE`, `STATES_N`, `ARMS`, `HARNESS_VARIANT`, `CONCURRENCY`, `TP_SIZE`,
`TIME_BUDGET_S`). The files next to them (`forks_w_modal.py` and the others) show one way to start them on a
rented GPU (Modal, A100-80GB); on a Kaggle session the same runner works with the competition's model and
wheelhouse datasets attached. One A100-80GB replays the 407 states under one condition and three seeds in about an
hour.

## A hosted API instead of a GPU

`analysis/modal_g/forks_19_runner.py` sends the model call to any OpenAI-compatible API and keeps everything else
(harness wheels, `replay.py`, agent files, states, seeds). It handles designs 10 (`fork_states_d`, conditions H and E,
2 seeds) and 17 (`fork_states_s`, records S, S0 and S0N, 3 seeds). It reads `INPUTS_DIR`, `COMP_DIR`, `OUT_DIR`,
`AGENT_DIR`, `HARNESS_VARIANT`, `DESIGN`, `STATES_FILE`, `ARMS`, `SEEDS`, `STATES_N`, `CONCURRENCY`, `API_BASE`,
`API_MODEL`, `NEBIUS_API_KEY` (the key, whatever the provider), `MAX_DOLLARS`, `MAX_OUTPUT_TOKENS`, `MAX_RETRIES`,
`REQUEST_TIMEOUT_S`, `TIME_BUDGET_S`, `PREFLIGHT`, `PRICE_IN_PER_M` and `PRICE_OUT_PER_M`. Before any call it
checks that the API's model list names the model and that a price is known, and it starts no new call once the
spending passes `MAX_DOLLARS`. Design 20 has its own hosted runner and launcher, `analysis/modal_g/forks_24_runner.py`
and `forks_24_modal.py` (pre-registration 24).

The launcher `analysis/modal_g/forks_19_modal.py` runs it on Modal with 4 CPUs and no GPU
(`modal run analysis/modal_g/forks_19_modal.py --design 10,17 --model <id>[,<id>...] --max-dollars <d>`; its
docstring has the smoke test). It reads the key from the local environment and hands it to the container as an
ephemeral secret. It expects a Modal volume that already holds the wheels, the agent files and the states files
(checked by md5), at a volume root set in the file.

Cost and time per model in our runs, from the stored `analysis/results/19/<design>/<model>/forks/summary.json`
(`dollars_this_session`, `elapsed_s`), seven models, concurrency 4 or 8:

| Design | Calls per model | Cost per model | Time per model |
|---|---|---|---|
| 10 | 1,628 | $1.19 to $4.20 | 4 to 15 minutes |
| 17 | 549 | $0.40 to $1.36 | 1.5 to 4.5 minutes |

## Versions

- Harness wheels, `VARIANTS` in every runner: `v28` is adk_eval_core 0.1.0, adk_submission 0.2.12, swegemma
  0.2.7; `latest` is adk_eval_core 0.1.0, adk_submission 0.2.13, swegemma 0.2.11.
- The wheels a run used are in its `pip_freeze.txt` with their sha256 (for example
  `analysis/results/c/forks/pip_freeze.txt`: swegemma 0.2.7, sha256 beginning 27a2f60f). The version number alone
  is not enough: the swegemma wheels of two harness releases both say 0.2.7 and differ (NOTES.md), so record the
  wheelhouse dataset version as well.
- Libraries: google-adk 1.36.1, litellm 1.82.4, vllm 0.19.1 (`analysis/modal_w/forks_w_modal.py`), google-genai
  2.11.0 (`analysis/modal_g/forks_19_modal.py`).

## What was only run by us

Every replay, rebuild of states and hosted run was run by us, on our machines, Modal and Kaggle, with the competition
data and the public runs in place. None of it has been run from a clean machine. Tested from a clean copy of the
repository (no `data/`): `analysis/reproduce.py --help`, `--list` and the full list of jobs, which prints PASS or
SKIPPED and no FAIL. The plumbing test above ran in a clean copy without `data/`, on a CPU, but in our own Python
environment (google-adk 1.36.1 with newer google-genai and litellm than the pins, the v28 wheels on `PYTHONPATH`);
a fresh environment has not been tried. The hosted runner has only run inside the
Modal launcher, not with its variables set by hand.

## What it cannot tell you

One call, or a few, from a state the agent reached by itself. It measures what the agent does next, not whether
the task gets fixed. The states in this repository come from one model's runs on the public tasks, early in the
run.
