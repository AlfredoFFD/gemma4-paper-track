#!/usr/bin/env python3
"""EXPLORATORY, written after all results were seen: how far the TASK decides whether a whole run is resolved.

Four whole-run arms ran the same 103 tasks, one run per task and arm: the agent as shipped (N) and with addresses in
the graph tools' answers (NAF) in pre-registration 14, seed 1; graph neighbors pushed into file reads with file and
line range (PE) and as names (PH) in pre-registration 23, seed 2. This script counts in how many of the four arms each
task is resolved, and the share of the variance in "resolved" that lies between tasks, against the same statistic
with the outcomes shuffled over runs.

Usage: py -I -X utf8 analysis/explore_task_agreement.py   (no arguments; prints the report)
Stored output: analysis/results/explore_task_agreement.txt is exactly this script's stdout (LF line ends).
Standard library only. Reads the tracked per-run tables analysis/results/14/runs_14.csv and
analysis/results/23/runs_23.csv (column `resolved`); the rows of arm N in the table of 23 repeat the N run of 14 and
are left out.
"""
import csv
import os
import random
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARMS = ("14 N", "14 NAF", "23 PE", "23 PH")


def load():
    res = {a: {} for a in ARMS}
    with open(os.path.join(ROOT, "analysis", "results", "14", "runs_14.csv"), encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h):
            res["14 " + r["condition"]][r["task"]] = int(r["resolved"] or 0)
    with open(os.path.join(ROOT, "analysis", "results", "23", "runs_23.csv"), encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h):
            if r["arm"] in ("PE", "PH"):
                res["23 " + r["arm"]][r["task"]] = int(r["resolved"] or 0)
    tasks = sorted(res[ARMS[0]])
    for a in ARMS:
        if sorted(res[a]) != tasks:
            raise SystemExit(f"stop: arm {a} does not have the tasks of {ARMS[0]}")
    return res, tasks


def icc1(groups, k):
    """One-way intraclass correlation for groups of k values each."""
    n = len(groups)
    allv = [v for g in groups for v in g]
    gm = sum(allv) / len(allv)
    ssb = sum(k * (sum(g) / k - gm) ** 2 for g in groups)
    sst = sum((v - gm) ** 2 for v in allv)
    msb = ssb / (n - 1)
    msw = (sst - ssb) / (n * (k - 1))
    return (msb - msw) / (msb + (k - 1) * msw), ssb / sst


def main():
    res, tasks = load()
    k = len(ARMS)
    print("EXPLORATORY: HOW FAR THE TASK DECIDES WHETHER A WHOLE RUN IS RESOLVED")
    print("EXPLORATORY, written after all results were seen; nothing here was registered. Four arms, one run per task")
    print("  and arm; the arms of 14 ran seed 1, those of 23 seed 2, in different launches.")
    print()
    print(f"1. Tasks: {len(tasks)}. Resolved per arm: " + ", ".join(f"{a} {sum(res[a].values())}" for a in ARMS))
    count = Counter(sum(res[a][t] for a in ARMS) for t in tasks)
    print("2. Tasks by the number of arms (of four) in which they are resolved: "
          + ", ".join(f"{i} arms: {count[i]}" for i in range(k + 1)))
    same = count[0] + count[k]
    print(f"3. Tasks with the same outcome in all four arms: {same} of {len(tasks)} ({count[0]} never resolved, "
          f"{count[k]} always); tasks on which the arms differ: {len(tasks) - same}")
    groups = [[res[a][t] for a in ARMS] for t in tasks]
    icc, eta = icc1(groups, k)
    print(f"4. Share of the variance in resolved that lies between tasks: {eta:.3f}; intraclass correlation "
          f"(one-way, four runs a task): {icc:.3f}")
    rng = random.Random(0)
    flat = [v for g in groups for v in g]
    null = []
    for _ in range(2000):
        sh = flat[:]
        rng.shuffle(sh)
        null.append(icc1([sh[i * k:(i + 1) * k] for i in range(len(tasks))], k)[0])
    null.sort()
    print(f"   the same correlation with the {len(flat)} outcomes shuffled over runs (2,000 shuffles, "
          f"random.Random(0)): median {null[1000]:.3f}, 97.5th percentile {null[1949]:.3f}")
    print()
    print(f"In plain words: the four arms give the same outcome on {same} of {len(tasks)} tasks; a comparison of the "
          f"arms in resolved tasks rests on the other {len(tasks) - same}.")


if __name__ == "__main__":
    main()
