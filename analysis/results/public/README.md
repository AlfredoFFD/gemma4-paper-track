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
| `defect_split.txt` | `analysis/public_runs_defect_split.py` | the traces of `defect.txt`, the per-call and failed-read tables of `what-the-agent-saw`, and the per-call tables of `gemma4-agent-traces-graph-audit` |
| `time_to_fix.txt` | `analysis/public_runs_time_to_fix.py` | both arms of the GraphLoc end-to-end runs with their run records (resolved, final patch), the traces of the two custom agents with their run tables, the per-run and per-read tables of `what-the-agent-saw`, and the gold patches of `data/tasks.jsonl` |
| `graph_calls.txt` | `analysis/public_runs_graph_calls.py` | both arms of the GraphLoc end-to-end runs: how often the agent called a graph tool, when, and whether the tool returned anything |
| `missed_regions.txt` | `analysis/public_runs_missed_regions.py` | both arms of the GraphLoc end-to-end runs, the gold patches, the competition's code graphs and the task snapshots (through `analysis/nodes.py`): the changed regions a run never saw, and whether the graph, true or rewired with 20 seeds, links them to code the run had been shown |
| `coedit_sites.txt` | `analysis/public_runs_coedit_sites.py` | the same runs, graphs and snapshots: from a place of the fix that a run was shown, whether the neighbor list the harness would print for it, or a short list built from such lists, holds a place the run missed; true graph against 20 rewirings |

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
| `data/public_traces/petermugoya__what-the-agent-saw/` | Kaggle dataset `petermugoya/what-the-agent-saw`, "What the Agent Saw: Data and Code", Oct 2 to 5, 2026: per-run, per-call and per-read tables of 1,329 runs of the starter agent, Gemma-4-31B, with code, a pre-registration and the writeup | the same | Apache-2.0 (its `LICENSE` file and README; the license field of the dataset page says "unknown"); it releases no competition data |
| `data/public_traces/kmussa77__gemma4-agent-traces-graph-audit/` | Kaggle dataset `kmussa77/gemma4-agent-traces-graph-audit`, "Gemma 4 agent traces and graph audit", Oct 13, 2026: per-call tables of three runs of a two-agent bundle, Gemma-4-31B (argument texts are replaced by hashes), with the agent bundles and scripts | the same | code Apache-2.0 (its README); the license field of the dataset page says "unknown" |
| `data/public_traces/outside/` | rows 0 to 799 of `SWE-bench/SWE-smith-trajectories` (split `tool`) and of `nebius/SWE-agent-trajectories` (split `train`) on Hugging Face | `analysis/fetch_outside_rows.py` (dataset viewer) | MIT; CC BY 4.0 |

Harness versions as far as the sources state them: the tables of `what-the-agent-saw` name swegemma 0.2.7,
google-adk 1.36.1 and vLLM 0.19.1; the GraphLoc runs predate the harness change of Sep 30, 2026; the README of
`gemma4-agent-traces-graph-audit` names swegemma 0.2.7 for two of its runs and 0.2.11 for the third; the other two
trace sets do not state a version (their runs are dated Oct 14 to Nov 3, 2026).

`defect_split.txt` exists because the count of `what-the-agent-saw` covers every tool. On the traces we hold, the
same rule counts mostly `edit_file` calls (114 of 156 for the starter agent in September), so that count is a
ceiling for file reads, not a rate. The report gives a floor beside it, and counts apart a second malformation of
file reads: a path string that was not closed and swallowed the line bounds, which fails with an error.

## What these sources' own authors already report

- `what-the-agent-saw`: its writeup reports that when an observation names files and the agent next opens a new
  file, it is a named one 84% of the time. Its public analysis plan lists, among things known before the plan,
  that "some tool calls carry corrupted argument keys (e.g. `start_line"`)", and its per-run tables count such
  calls (`n_corrupted_arg_calls`), for all tools together. It does not analyse where reads start by what the
  observation held, nor what follows a corrupted key.
- `gemma4-agent-traces-graph-audit`: its trace script flags a call as malformed when it has a key the tool does not
  declare or when stray characters or a bound name sit inside the path, and counts loops that start from such a
  call; its reproduction notebook prints those counts per run (for example 1,083 malformed calls in 39 of 129 tasks
  and 16 loops started by one, in its first run). It does not separate the two kinds for file reads, and it does
  not look for a cause.
- Prompts: the starter agent's system prompt asks the agent to read only the specific files and lines it needs.
  The system prompt published with `gemma4-patchpool` adds a search command that prints line numbers. The traces
  of `gemma4-commit-anatomy-traces` omit their system prompts. So reading by line range is asked for in these
  agents; the counts in `address.txt` show when the agent does it.
- GraphLoc: its skill prints candidates as `<rank> <score> <path>:<line> <name>`; the writeup reports the
  end-to-end effect of the skill, not what the agent's next call does with those lines.
