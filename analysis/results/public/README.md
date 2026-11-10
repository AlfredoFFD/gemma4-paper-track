# Public runs: sources and stored reports

Everything in this folder is EXPLORATORY: no rule was pre-registered, and no model was run. The reports count what
other teams' published agent runs did. The data itself is not in this repository and is not redistributed.

## Stored reports

| File | Script | Reads |
|---|---|---|
| `address.txt` | `analysis/public_runs_address.py` | traces and tables under `data/graphloc/` and `data/public_traces/` |
| `defect.txt` | `analysis/public_runs_defect.py` | the same |
| `outside.txt` | `analysis/public_runs_outside.py` | rows 0 to 799 of two Hugging Face datasets (its first lines say whether the rows came from local copies or from the dataset viewer) |
| `rederive_address.txt` | `analysis/rederive_public_address.py` | the same traces as `address.txt` (not the tables) |

Each script prints its report; the stored file is that output with LF line endings. `analysis/reproduce.py` re-runs
the first, second and fourth when the data is present and reports them as SKIPPED when it is not; the third needs
the network and is not part of it.

`rederive_address.txt` is a second implementation of the main counts of `address.txt`, written from the rules in the
first script's docstring without its code. On the three Gemma-4-31B sources it agrees on every count the paper uses:
after an ADDRESS 213 of 254 first reads ask for a start past line 1, 212 of those 213 cover a named line (a random
window of the same length would 18.7% of the time), after a GRAPH NAME 0 of 10, the same counts by way, and the same
ADDRESS counts in every source and model. The two differ on a few reads that fall between PATH ONLY and OTHER: four
first reads of the starter agent that ask for no range (first script: PATH ONLY 3 of 450, OTHER 73 of 580; second:
3 of 454 and 73 of 576), and three first reads of the graph-skill arm, which is not pooled (143 of 423 and 99 of 376
against 144 of 426 and 98 of 373).

## Sources, how each was obtained, and its license as stated on its page

| Local path | Source | Obtained | License stated |
|---|---|---|---|
| `data/graphloc/out/` | outputs of the three end-to-end notebooks of the GraphLoc writeup (Kaggle user zzgtylors), Sep 25 to 27, 2026: 318 traces of the starter agent and 318 with a graph skill, Gemma-4-31B | Kaggle CLI, `kaggle kernels output` | Apache-2.0 (notebooks) |
| `data/public_traces/vanductan__gemma4-patchpool/` | Kaggle dataset `vanductan/gemma4-patchpool`, "PatchPool: Gemma 4 agent patches and labels", Oct 2026: 40 traces per run of a custom agent (two runs of 31B, one of 12B, two of E4B) | Kaggle CLI, `kaggle datasets download`, Nov 10, 2026 | CC BY 4.0 |
| `data/public_traces/niraberman__gemma4-commit-anatomy-traces/` | Kaggle dataset `niraberman/gemma4-commit-anatomy-traces`, Oct 31 to Nov 3, 2026: 120 traces of a custom agent, Gemma-4-31B, 20 tasks of one repository | the same | CC BY-SA 4.0 |
| `data/public_traces/petermugoya__what-the-agent-saw/` | Kaggle dataset `petermugoya/what-the-agent-saw`, "What the Agent Saw: Data and Code", Oct 2 to 5, 2026: per-run, per-call and per-read tables of 1,329 runs of the starter agent, Gemma-4-31B, with code, a pre-registration and the writeup | the same | not stated on the dataset page ("unknown"); its README releases no competition data |
| `data/public_traces/outside/` | rows 0 to 799 of `SWE-bench/SWE-smith-trajectories` (split `tool`) and of `nebius/SWE-agent-trajectories` (split `train`) on Hugging Face | `analysis/fetch_outside_rows.py` (dataset viewer) | MIT; CC BY 4.0 |

Harness versions as far as the sources state them: the tables of `what-the-agent-saw` name swegemma 0.2.7,
google-adk 1.36.1 and vLLM 0.19.1; the GraphLoc runs predate the harness change of Sep 30, 2026; the other two
trace sets do not state a version (their runs are dated Oct 14 to Nov 3, 2026).

## What these sources' own authors already report

- `what-the-agent-saw`: its writeup reports that when an observation names files and the agent next opens a new
  file, it is a named one 84% of the time. Its public analysis plan lists, among things known before the plan,
  that "some tool calls carry corrupted argument keys (e.g. `start_line"`)", and its per-run tables count such
  calls (`n_corrupted_arg_calls`). It does not analyse where reads start by what the observation held, nor what
  follows a corrupted key.
- GraphLoc: its skill prints candidates as `<rank> <score> <path>:<line> <name>`; the writeup reports the
  end-to-end effect of the skill, not what the agent's next call does with those lines.
