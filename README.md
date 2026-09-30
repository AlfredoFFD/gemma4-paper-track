# Gemma 4 Paper Track: the code graph as a coding agent's externalized memory

Team of two.

Target: Google DeepMind's **Gemma 4 Developer Agent Paper Track** on Kaggle
(https://www.kaggle.com/competitions/gemma-4-developer-agent-paper).
**Deadline: Nov 12, 2026, 11:59 PM UTC** (6:59 PM EST). The main competition
(https://www.kaggle.com/competitions/gemma-4-developer-agent) runs to Dec 2 and is optional for us.

**Status (Sep 30, 2026):** brainstorm moving to a pilot. Nothing has been run yet.

## The question in one paragraph

The competition gives every agent tools over a repository's call graph and node embeddings. Nobody has shown
cleanly **when explicit graph structure helps a small coding agent, what it supplies that plain semantic retrieval
does not, and whether cheap training can teach the model to use it**. We plan to answer that with a counterfactual
design: serve the agent the true graph, a graph with its structure scrambled, a graph with its embeddings scrambled,
or no graph. Then we measure what breaks and whether the agent follows the decoys. Details in [BRIEF.md](BRIEF.md).

## Map

| Path | What |
|---|---|
| [BRIEF.md](BRIEF.md) | The kickoff brief: goal, questions, plan, gates, constraints. Start here. |
| [LOG.md](LOG.md) | Research log. Dated entries, each with a reason. Append-only. |
| [NOTES.md](NOTES.md) | Claude Code's notes (kept separate so two agents never edit one file). |
| [docs/competition.md](docs/competition.md) | Rules and insights read from every part of the Kaggle pages. |
| [docs/prior-art.md](docs/prior-art.md) | Nearest published work and what it leaves open. |
| [docs/ideas.md](docs/ideas.md) | Brainstorm history: ideas considered, verdicts, the merged design. |
| [docs/methods-we-bring.md](docs/methods-we-bring.md) | Methods that transfer from our earlier work. |
| [docs/how-we-work.md](docs/how-we-work.md) | Branches, issues, pre-registration, logging, tools. |
| [prereg/](prereg/) | Pre-registrations, committed before any data they govern. |
| [experiments/](experiments/) | One folder per experiment: code, config, results. |
| [paper/](paper/) | The writeup (3,000 words maximum). |
| [data/](data/) | Local copy of the Kaggle dataset. Never committed. |

## Getting the data

Both of us must join the paper track and the main competition on Kaggle first (joining accepts the rules). Then
create a Kaggle API token (Kaggle settings, "Create New Token"), save it as `~/.kaggle/kaggle.json`, and run:

```
pip install kaggle
kaggle competitions download -c gemma-4-developer-agent -p data/
```

See [data/README.md](data/README.md) for what the dataset contains.

## License

To be decided once the competition rules on winner licensing are confirmed (see docs/competition.md). The
competition dataset is Apache 2.0.
