# Notebooks

`table2_from_raw_outputs.ipynb` recomputes every row of the paper's Table 2 (the registered rules its argument rests on) from the raw per-replay and per-episode records under `analysis/results/`, and prints each next to the value that the registered analysis stored. It is committed with its outputs, so it can be read without running anything.

To run it again: `py -I -X utf8 notebooks/run_notebook.py` from the repository root (Python 3.10 or later, standard library only, no Jupyter kernel, about 20 seconds once the caches exist; `--check` compares a fresh run with the stored outputs and writes nothing), or open it in Jupyter and run all cells.

It reads the raw records as the runs wrote them, the stored reports, and the paused steps and task lists under `analysis/fork_states*/`, which `analysis/fork_states.py`, `make_states_d.py`, `make_population_k.py` and `make_population_g.py` built from public traces of the starter agent and the competition data; the first cell of the notebook lists each input, whether it is a file of the repository, and the script that makes it.

It also reads competition data, which is not redistributed here: the task snapshots (`data/snapshots/`) and, for the whole-run rows, `data/tasks.jsonl`. Download them as `data/README.md` says and run `py -I -X utf8 analysis/snapshot_index.py` once; the first run of the notebook then unpacks the Python files of each snapshot into `data/cache/`, which takes a while.

Without the competition data five rows still recompute (12 P2, 12 P3, 11 R1, 07 F2, 08 N1). Every other row prints which input is missing and is not approximated.
