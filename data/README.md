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

## Downloaded copy (2026-09-30)

- Zip: 21,929,289,087 bytes, sha256 `06cec82cc9c9090edea659a31ce5ff92a6e96133c1fc152c06300e869a2e7421`; unzipped with no errors.
- Counts: tasks.jsonl 129 lines; snapshots 129 (.tgz, 21 GB); graphs 127; embeddings 127; wheels 124.
- The task-named duplicates of graphs and embeddings are not in the zip. Map a task to its files through `repo` and
  `base_commit`: `graphs/<repo_short>_<base_commit>.json` and `embeddings/<repo_short>_<base_commit>.npz`.
