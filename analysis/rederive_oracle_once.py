"""Independent recount (EXPLORATORY), from a brief's rules: arms N, ON and OA of experiments 18 and 22 pooled so that
every task weighs the same.

Inputs: analysis/results/18/runs_18.csv (rows with launch 18) and analysis/results/22/runs_22.csv (rows with experiment
22), rows with entered = 1, arms N, ON, OA (arm OF of experiment 22 is not used). Columns resolved, patch_overlaps,
every_region (0 or 1).
Rule: a task's outcome in an arm is the mean over its runs in that arm across the two tables.
Per column: the sum over tasks of the task means per arm; for ON - N, OA - N, OA - ON the mean over tasks of the
per-task difference in points (x100) with a 95% bootstrap interval over tasks (2,000 resamples of the tasks with
replacement, random.Random(20261111); the same resampled task lists serve every column and pair of one task set;
interval = the 51st and the 1,950th of the 2,000 sorted resampled means, i.e. sorted[50] and sorted[1949]), and the
number of tasks where the first arm is higher and where it is lower. The same on the tasks with one run and on the
tasks with two runs. Also the plain pooled counts per arm over all runs.

Usage: py -I -X utf8 analysis/rederive_oracle_once.py
It prints the report and stores the same text in analysis/results/22/rederive_oracle_once.txt (LF line endings).
"""
import collections
import csv
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = HERE / "results" / "22" / "rederive_oracle_once.txt"
ARMS = ["N", "ON", "OA"]
COLS = ["resolved", "patch_overlaps", "every_region"]
PAIRS = [("ON", "N"), ("OA", "N"), ("OA", "ON")]
B = 2000
SEED = 20261111


def val(x):
    x = (x or "").strip().lower()
    if x in ("1", "1.0", "true"):
        return 1
    if x in ("0", "0.0", "false"):
        return 0
    raise ValueError(f"unexpected value {x!r}")


def load():
    rows = []
    skipped = collections.Counter()
    with open(HERE / "results" / "18" / "runs_18.csv", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("launch") == "18":
                rows.append(("18", r))
    with open(HERE / "results" / "22" / "runs_22.csv", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("experiment") == "22":
                rows.append(("22", r))
    kept = []
    for exp, r in rows:
        if r["arm"] not in ARMS:
            skipped[f"experiment {exp} arm {r['arm']} (not used)"] += 1
            continue
        if val(r.get("entered")) != 1:
            skipped[f"experiment {exp} not entered"] += 1
            continue
        kept.append((exp, r))
    return kept, skipped


def main():
    kept, skipped = load()
    runs = collections.defaultdict(list)  # (task, arm) -> rows
    for exp, r in kept:
        runs[(r["task"], r["arm"])].append(r)
    tasks = sorted({t for t, _ in runs})
    nrun = {t: len(runs.get((t, "N"), [])) for t in tasks}
    for t in tasks:
        if len({len(runs.get((t, a), [])) for a in ARMS}) != 1:
            skipped["task whose arms have different run counts"] += 1

    def mean_of(t, a, col):
        rs = runs.get((t, a), [])
        return sum(val(r[col]) for r in rs) / len(rs) if rs else None

    L = ["INDEPENDENT RECOUNT (EXPLORATORY): arms N, ON, OA over experiments 18 and 22, each task weighing the same",
         "=" * 100,
         f"tasks {len(tasks)}; with one run per arm {sum(nrun[t] == 1 for t in tasks)}; with two "
         f"{sum(nrun[t] == 2 for t in tasks)}; bootstrap {B} resamples of tasks, random.Random({SEED}), "
         f"interval sorted[50]..sorted[1949]"]
    P = L.append
    rng = random.Random(SEED)
    subsets = [("all tasks", tasks), ("tasks with one run", [t for t in tasks if nrun[t] == 1]),
               ("tasks with two runs", [t for t in tasks if nrun[t] == 2])]
    draws = {}
    for lab, ts in subsets:
        n = len(ts)
        draws[lab] = [[rng.randrange(n) for _ in range(n)] for _ in range(B)]
    for col in COLS:
        P("")
        P(f"### {col}")
        for lab, ts in subsets:
            m = {(t, a): mean_of(t, a, col) for t in ts for a in ARMS}
            P(f"  [{lab}: {len(ts)} tasks] sum of task means: "
              + "; ".join(f"{a} {sum(m[(t, a)] for t in ts):.2f}" for a in ARMS))
            for a, b in PAIRS:
                d = [m[(t, a)] - m[(t, b)] for t in ts]
                est = 100 * sum(d) / len(d)
                bs = sorted(100 * sum(d[i] for i in idx) / len(idx) for idx in draws[lab])
                P(f"     {a} minus {b}: {est:+.2f} points [{bs[50]:+.2f}, {bs[1949]:+.2f}]; "
                  f"{a} higher on {sum(x > 0 for x in d)} tasks, lower on {sum(x < 0 for x in d)}")
    P("")
    P("Plain pooled counts over all runs (experiment 18 and 22 together):")
    for a in ARMS:
        rs = [r for (t, arm), v in runs.items() if arm == a for r in v]
        P(f"   {a}: runs {len(rs)}; " + "; ".join(f"{c} {sum(val(r[c]) for r in rs)}" for c in COLS))
    P("")
    P("Rows not used: " + ("; ".join(f"{k} {v}" for k, v in sorted(skipped.items())) or "none"))
    text = "\n".join(L) + "\n"
    print(text, end="")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
