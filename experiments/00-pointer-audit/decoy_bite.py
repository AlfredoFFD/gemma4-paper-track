"""Decoy-bite check (EXPLORATORY). Decision rule: NOTES.md, entry of 2026-09-30 19:21 EDT.

Question: from the symbols a task's issue text names, does one graph call surface a gold unit that the issue does not
already name? If almost never, a scrambled graph has nothing task-relevant to remove, and an end-to-end decoy test
measures noise.

Needs results/units.csv from pointer_audit.py. Reads data/ only. Run from the repo root:
    py experiments/00-pointer-audit/decoy_bite.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics as st
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RES = Path(__file__).resolve().parent / "results"

MAX_NEIGHBORS = 50  # get_code_neighbors default max_neighbors (HARNESS_README 6.3)
K_SEARCH = 10  # search_similar_code default k (HARNESS_README 6.3)
MAX_AMBIGUITY = 5  # a short name matching more nodes than this is not counted as mentioned
KILL, PASS = 0.10, 0.25  # decision thresholds, NOTES.md

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    t0 = time.time()
    tasks = {json.loads(l)["instance_id"]: json.loads(l) for l in open(DATA / "tasks.jsonl", encoding="utf-8")}
    gold = defaultdict(set)
    for u in csv.DictReader(open(RES / "units.csv", encoding="utf-8")):
        if u["addressable"] == "True":
            gold[u["instance_id"]].add(u["graph_id"])

    by_graph = defaultdict(list)
    for t in tasks.values():
        by_graph[f"{t['repo'].split('/')[1]}_{t['base_commit']}"].append(t)

    rows = []
    for gkey, gtasks in sorted(by_graph.items()):
        g = json.load(open(DATA / "graphs" / f"{gkey}.json", encoding="utf-8"))
        ids = [n["id"] for n in g["nodes"]]
        idset = set(ids)
        nbr = defaultdict(set)
        for e in g["edges"]:
            if e["source"] != e["target"]:
                nbr[e["source"]].add(e["target"])
                nbr[e["target"]].add(e["source"])
        by_short = defaultdict(list)
        for i in ids:
            by_short[i.rsplit(".", 1)[-1]].append(i)
        emb = np.load(DATA / "embeddings" / f"{gkey}.npz")
        keys = list(emb.files)
        mat = np.stack([emb[k] for k in keys]).astype(np.float32)
        mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
        kidx = {k: i for i, k in enumerate(keys)}

        def search(q):
            i = kidx.get(q)
            if i is None:
                return set()
            sims = mat @ mat[i]
            sims[i] = -np.inf
            return {keys[j] for j in np.argpartition(-sims, K_SEARCH)[:K_SEARCH]}

        for t in gtasks:
            text = t["problem_statement"] + "\n" + (t["hints_text"] or "")
            toks = set(IDENT.findall(text))
            dotted = {k for k in toks if "." in k}
            parts = {p for k in toks for p in k.split(".")}  # every identifier, including parts of a.b.c
            mentioned = set()
            for tok in dotted:
                mentioned.update(i for i in ids if i == tok or i.endswith("." + tok))
            for p in parts:
                if len(p) >= 4 and not p.startswith("__"):
                    cands = by_short.get(p, [])
                    if 0 < len(cands) <= MAX_AMBIGUITY:
                        mentioned.update(cands)
            gnodes = gold.get(t["instance_id"], set())
            named = {x for x in gnodes
                     if x.rsplit(".", 1)[-1] in parts or any(x == k or x.endswith("." + k) for k in dotted)}
            hidden = gnodes - named
            one_hop = {x for m in mentioned if len(nbr[m]) <= MAX_NEIGHBORS for x in nbr[m]}
            one_hop_any = {x for m in mentioned for x in nbr[m]}
            two_hop = one_hop_any | {y for x in one_hop_any for y in nbr[x]}
            emb_hits = {x for m in mentioned for x in search(m)}
            rows.append({
                "instance_id": t["instance_id"], "repo": t["repo"], "mentioned_nodes": len(mentioned),
                "gold_nodes": len(gnodes), "gold_named_directly": len(named),
                "gold_isolated": sum(len(nbr[x]) == 0 for x in gnodes),
                "graph_bite": len(hidden & one_hop), "graph_bite_uncapped": len(hidden & one_hop_any),
                "two_hop_bite": len(hidden & two_hop), "embedding_bite": len(hidden & emb_hits),
            })
        print(f"{gkey}: {len(gtasks)} task(s), {time.time() - t0:.0f}s", flush=True)

    n = len(rows)
    share = lambda k: round(sum(r[k] > 0 for r in rows) / n, 4)
    bite = share("graph_bite")
    verdict = "KILL" if bite < KILL else "WEAKENED" if bite < PASS else "PASS"
    gold_total = sum(r["gold_nodes"] for r in rows)
    summary = {
        "label": "EXPLORATORY; decision rule fixed in NOTES.md 2026-09-30 19:21 EDT before computing",
        "inputs": {"tasks.jsonl_sha256": sha256_file(DATA / "tasks.jsonl"),
                   "units.csv_sha256": sha256_file(RES / "units.csv"), "script_sha256": sha256_file(Path(__file__))},
        "n_tasks": n,
        "registered": {"tasks_with_graph_bite": sum(r["graph_bite"] > 0 for r in rows), "share": bite,
                       "verdict": verdict},
        "descriptive": {
            "share_graph_bite_uncapped": share("graph_bite_uncapped"),
            "share_two_hop_bite": share("two_hop_bite"),
            "share_embedding_bite": share("embedding_bite"),
            "share_any_gold_named_directly": share("gold_named_directly"),
            "share_tasks_with_mentioned_node": share("mentioned_nodes"),
            "mentioned_nodes_median": st.median(r["mentioned_nodes"] for r in rows),
            "gold_nodes_total": gold_total,
            "gold_nodes_isolated_share": round(sum(r["gold_isolated"] for r in rows) / max(1, gold_total), 4),
            "by_repo_graph_bite": {repo: f"{sum(r['graph_bite'] > 0 for r in rows if r['repo'] == repo)}/"
                                         f"{sum(r['repo'] == repo for r in rows)}"
                                   for repo in sorted({r["repo"] for r in rows})},
        },
        "runtime_seconds": round(time.time() - t0, 1),
    }
    with open(RES / "decoy_bite_per_task.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (RES / "decoy_bite_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
