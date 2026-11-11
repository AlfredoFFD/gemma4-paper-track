# A name is not an address, and an address is not enough

What a code-graph answer changes in what a coding agent does.

This repository holds the code, the pre-registrations, the raw replay outputs and the analyses behind a writeup for
Google DeepMind's Gemma 4 Developer Agent Paper Track on Kaggle
(https://www.kaggle.com/competitions/gemma-4-developer-agent-paper). The experiments pause recorded runs of the
competition's coding agent, change what the last tool answer says (a graph node's name, its file, its lines, a note),
replay the next model call through the competition harness, and score where that call goes. The replay tool is
described in [docs/replay-tool.md](docs/replay-tool.md).

## What runs from a clone

Python 3.11, standard library only, no data, GPU or key:

```
py -I -X utf8 analysis/reproduce.py --list      # every analysis job, and whether its inputs are here
py -I -X utf8 analysis/reproduce.py             # re-run them all and compare with the stored reports
py -I -X utf8 analysis/reproduce.py --job "reading rule"   # only the jobs whose label contains the text
```

(`python3` works in place of `py`.) Each job re-runs one analysis script on the raw outputs under
`analysis/results/` and prints `PASS` when its report is identical to the stored one, `FAIL` when it is not, or
`SKIPPED ...: needs the competition data (<path>)` when an input that git does not track is missing. The last line
is `PASS n, FAIL n, SKIPPED n`, and the exit status is 0 when nothing failed. From a clone, the jobs that need only
tracked files pass (for example the reading rule of pre-registration 11, the endings of the whole runs of 18 and 22,
and several exploratory counts); the rest are skipped, and none fails (when this was written: `PASS 12, FAIL 0,
SKIPPED 87`, in about 15 seconds). On Windows, clone with `git -c core.autocrlf=false clone ...`: one job prints
the md5 of a raw result file, and a checkout that rewrites line endings changes it.

## What needs the competition data

Most jobs also read the competition's tasks, repository snapshots or code graphs (about 21 GB). Join the main
competition on Kaggle (https://www.kaggle.com/competitions/gemma-4-developer-agent; joining accepts its rules),
save a Kaggle API token, then:

```
pip install kaggle
kaggle competitions download -c gemma-4-developer-agent -p data/
py -I -X utf8 analysis/snapshot_index.py        # the file lists of the snapshots, used by several jobs
```

The data is not redistributed here ([data/README.md](data/README.md) lists what it holds). Some jobs also read
caches built from it (the SKIPPED line names the script), state files that git ignores because they hold task text
or other teams' runs (rebuilt by `analysis/make_states_*.py` and `analysis/fork_states.py`), or other teams' public
runs ([analysis/results/public/README.md](analysis/results/public/README.md) says where to get them).

## What needs a GPU or an API key

- One-step and few-step replays on Gemma 4: a GPU serving the model, the harness wheels and `google-adk`
  (`analysis/modal_w/`, `analysis/modal_g/`). See [docs/replay-tool.md](docs/replay-tool.md).
- The same replays on a hosted OpenAI-compatible API (pre-registration 19): an API key, no GPU. See
  [docs/replay-tool.md](docs/replay-tool.md), "A hosted API instead of a GPU".
- Whole runs scored by the task tests (pre-registrations 14, 18, 22): a GPU, the harness and its sandbox
  (`analysis/modal_h/`).

## Map

| Path | What |
|---|---|
| [prereg/](prereg/) | The pre-registrations, each committed before the data it governs. [docs/prereg-times.md](docs/prereg-times.md) lists their freeze and commit times. |
| [analysis/](analysis/) | The replay tool, the state builders, the runners and every analysis script. `analysis/reproduce.py` re-runs the analyses. |
| [analysis/results/](analysis/results/) | Raw replay outputs (`results.jsonl` with versions and pip freezes) and the stored report of every analysis. |
| [paper/figures/](paper/figures/) | The figures of the writeup and the script that draws them. |
| [docs/](docs/) | The replay tool, the competition rules as read, prior work, how we work. |
| [LOG.md](LOG.md) | Research log: dated entries, each with a reason. Append-only. |
| [NOTES.md](NOTES.md) | Notes from checking claims against the data. |
| `data/` | The competition data, local only and never committed. |

## License

Apache 2.0 (see [LICENSE](LICENSE)). The competition data keeps its own terms and is not part of this repository.
