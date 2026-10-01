"""POST-DATA readings answering Claude Science's loophole review (LOG.md, 2026-09-30 19:34 ET).

None of this changes a registered verdict. It reads the registered outputs in results/ (and data/ for the degree-cap
reading) and prints: Wilson intervals for K1 and the decoy-bite share, per repo; name-match fidelity for function and
method units; and the decoy-bite share if get_code_neighbors counts each stored edge direction separately.
Run from the repo root:  py experiments/00-pointer-audit/postdata_review.py
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RES = Path(__file__).resolve().parent / "results"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


def wilson(k: int, n: int, z: float = 1.96) -> str:
    if n == 0:
        return "n/a"
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{k}/{n} = {p:.1%} [{c - h:.1%}, {c + h:.1%}]"


def main():
    tasks = [r for r in csv.DictReader(open(RES / "per_task.csv", encoding="utf-8"))]
    units = [r for r in csv.DictReader(open(RES / "units.csv", encoding="utf-8"))]
    bite = [r for r in csv.DictReader(open(RES / "decoy_bite_per_task.csv", encoding="utf-8"))]

    print("POST-DATA. K1 (all pre-existing Python units addressable), Wilson 95%:")
    pool = [r for r in tasks if r["units"] != "0"]
    print("  pooled ", wilson(sum(r["all_addressable"] == "True" for r in pool), len(pool)))
    for repo in sorted({r["repo"] for r in pool}):
        p = [r for r in pool if r["repo"] == repo]
        print(f"  {repo:18}", wilson(sum(r["all_addressable"] == "True" for r in p), len(p)))

    print("POST-DATA. Decoy-bite share (registered definition), Wilson 95%:")
    print("  pooled ", wilson(sum(int(r["graph_bite"]) > 0 for r in bite), len(bite)))
    for repo in sorted({r["repo"] for r in bite}):
        p = [r for r in bite if r["repo"] == repo]
        print(f"  {repo:18}", wilson(sum(int(r["graph_bite"]) > 0 for r in p), len(p)))

    print("POST-DATA. Name-match fidelity: addressable units whose graph text equals their source (whitespace-insensitive):")
    for kind in ("func", "class"):
        a = [u for u in units if u["addressable"] == "True" and u["kind"] == kind]
        print(f"  {kind:6}", wilson(sum(u["text_equals_source"] == "True" for u in a), len(a)))
    bad = [u for u in units if u["addressable"] == "True" and u["kind"] == "func" and u["text_equals_source"] != "True"]
    sims = sorted(float(u["text_similarity"]) for u in bad if u["text_similarity"])
    print(f"  func mismatches: {len(bad)}; their similarity to source, min/median: "
          f"{sims[0] if sims else 'n/a'} / {sims[len(sims) // 2] if sims else 'n/a'}")

    # Degree-cap fork: if each stored direction counts as a separate neighbor entry, a 50-entry cap is ~25 unique.
    tmap = {json.loads(l)["instance_id"]: json.loads(l) for l in open(DATA / "tasks.jsonl", encoding="utf-8")}
    gold = defaultdict(set)
    for u in units:
        if u["addressable"] == "True":
            gold[u["instance_id"]].add(u["graph_id"])
    by_graph = defaultdict(list)
    for t in tmap.values():
        by_graph[f"{t['repo'].split('/')[1]}_{t['base_commit']}"].append(t)
    hits = {25: 0, 50: 0}
    for gkey, gtasks in by_graph.items():
        g = json.load(open(DATA / "graphs" / f"{gkey}.json", encoding="utf-8"))
        ids = [n["id"] for n in g["nodes"]]
        nbr = defaultdict(set)
        for e in g["edges"]:
            if e["source"] != e["target"]:
                nbr[e["source"]].add(e["target"])
                nbr[e["target"]].add(e["source"])
        by_short = defaultdict(list)
        for i in ids:
            by_short[i.rsplit(".", 1)[-1]].append(i)
        for t in gtasks:
            toks = set(IDENT.findall(t["problem_statement"] + "\n" + (t["hints_text"] or "")))
            dotted = {k for k in toks if "." in k}
            parts = {p for k in toks for p in k.split(".")}
            mentioned = set()
            for tok in dotted:
                mentioned.update(i for i in ids if i == tok or i.endswith("." + tok))
            for p in parts:
                if len(p) >= 4 and not p.startswith("__") and 0 < len(by_short.get(p, [])) <= 5:
                    mentioned.update(by_short[p])
            gn = gold.get(t["instance_id"], set())
            hidden = {x for x in gn if x.rsplit(".", 1)[-1] not in parts
                      and not any(x == k or x.endswith("." + k) for k in dotted)}
            for cap in hits:
                reach = {x for m in mentioned if len(nbr[m]) <= cap for x in nbr[m]}
                hits[cap] += bool(hidden & reach)
    n = len(tmap)
    print("POST-DATA. Decoy-bite share by degree cap (unique neighbors):")
    for cap, k in sorted(hits.items()):
        print(f"  cap {cap:2} unique:", wilson(k, n))


if __name__ == "__main__":
    main()
