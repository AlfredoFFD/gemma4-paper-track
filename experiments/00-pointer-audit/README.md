# 00: Pointer audit and decoy-bite check (Phase 0, EXPLORATORY)

Two offline checks on the 129 public tasks, with no GPU and no agent runs. Both decision rules were fixed in NOTES.md
(Sep 30, 19:12 and 19:21 EDT) before any number was computed. Results and verdicts: NOTES.md, Sep 30, 19:24 EDT.

- `pointer_audit.py` asks whether the provided graph can address the code each gold patch edits, and whether that
  code is big enough, against read_file's limits, for pointer-style memory to save context. It tests Option 2,
  "finding vs remembering".
- `decoy_bite.py` asks, starting from the symbols the issue names, whether one graph call surfaces a gold unit the
  issue does not name. It tests whether Option 1's decoy test has anything to bite on.

## Run

From the repo root, with `data/` unzipped (numpy needed):

```
py experiments/00-pointer-audit/pointer_audit.py            # about 95 s; writes results/
py experiments/00-pointer-audit/decoy_bite.py               # about 45 s; needs results/units.csv
py experiments/00-pointer-audit/pointer_audit.py --dry-run  # 3 graphs only, into results_dryrun/
```

## Outputs (results/)

| File | What |
|---|---|
| `summary.json` | Pointer audit: the registered K1-K3 verdicts, descriptive numbers, post-data readings, input hashes |
| `per_task.csv` | One row per task: gold files, units, addressability, read costs, search payloads |
| `units.csv` | One row per gold unit: kind, size, window cost, graph id, fidelity, search payload |
| `graphs.csv` | One row per graph: size, largest node, nodes over 35,000 characters |
| `decoy_bite_summary.json` | Decoy-bite: the registered verdict and descriptive shares |
| `decoy_bite_per_task.csv` | One row per task: mentioned nodes, gold named directly, 1-hop, 2-hop and embedding bites |

The files hold derived counts, sizes and symbol names only. They contain no code text from the dataset.

## Known limits

- Gold units come from the gold patch. Real agents read more than the gold code, so these are lower bounds on reading.
- "Mentioned" symbols are matched by name from the issue text. An agent may query other names.
- The tool behavior modelled here (names-only neighbors, search excluding the query node, the read_file caps) comes
  from `data/HARNESS_README.md`, not from the harness source. Verify it against the wheelhouse before citing it.
