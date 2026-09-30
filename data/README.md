# Data (never committed)

Everything in this folder except this README is gitignored.

Download after joining the competition and saving a Kaggle API token to `~/.kaggle/kaggle.json`:

```
kaggle competitions download -c gemma-4-developer-agent -p data/
```

Contents (from the Kaggle Data tab):
- `tasks.jsonl`: 129 public tasks (fastapi, rich, requests, httpx) with gold patch and test patch
- `snapshots/`: repositories at base_commit
- `graphs/`: NetworkX AST call and dependency graphs (JSON)
- `embeddings/`: 256-d vectors per graph node (.npz)
- `wheels/`: offline dependencies
- `docker/`: sandbox image specs
- `sandbox/setup.py`
- `sample_submission/`: a baseline ADK agent
- `HARNESS_README.md`: harness libraries and local evaluation

Record the download date and the sha256 of the archive in LOG.md, so every result can be traced to a dataset version.
