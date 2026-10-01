# Experiments

One folder per experiment, each with its own README (how to run it), code, configs, and small result files. Large
outputs go to `data/` or cloud storage, recorded by path and sha256 in LOG.md. Every reported experiment has a
pre-registration in `../prereg/`, committed before its data.

| Folder | Question | Status |
|---|---|---|
| `00-pointer-audit/` | Can the graph point at the fix site, and does it carry task-relevant structure to corrupt? 129 tasks, no GPU | Done Sep 30 (EXPLORATORY): both WEAKENED; see NOTES.md |
| `q1-offline-map/` | When does structure help? Graph distance vs semantic-search rank of the gold symbols, 129 tasks, no GPU | Not started (needs the dataset) |
| `q2-counterfactual-arms/` | What does structure add over semantic retrieval? True / structure-scrambled / embeddings-scrambled / both / no tools | Not started (needs the harness pilot) |
| `q3-training/` | Can cheap training make Gemma use structure? Skill baseline, then LoRA on its own successful graph-using runs | Not started |
| `pilot-harness/` | Can we run the harness with Gemma 4? Cost per task, time per task, graph-tool call rate | Not started |
