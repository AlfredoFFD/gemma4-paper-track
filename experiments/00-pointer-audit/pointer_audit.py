"""Phase-0 pointer audit (EXPLORATORY). Decision rule: NOTES.md, entry of 2026-09-30 19:12 EDT.

Question: can the provided code graph address the code each gold patch edits, and is that code big enough, against
read_file's limits, for pointer-style memory to save context?

Reads data/ only (tasks.jsonl, graphs/, embeddings/, snapshots/). Writes results/ next to this file.
Run from the repo root:  py experiments/00-pointer-audit/pointer_audit.py
"""

from __future__ import annotations

import ast
import csv
import difflib
import hashlib
import json
import re
import statistics as st
import sys
import tarfile
import textwrap
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "results"

# Harness limits, from data/HARNESS_README.md
READ_LINES = 150  # read_file: 150 lines per call (6.2)
READ_CHARS = 10_000  # read_file: 10,000 characters per call (6.2)
K_SEARCH = 10  # search_similar_code default k (6.3)

# Decision thresholds, from NOTES.md (fixed before any number was computed)
K1_KILL, K1_PASS = 0.50, 0.75
K2_KILL_CHARS = 10_000
K3_KILL, K3_PASS = 2.0, 5.0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- patch parsing


def _strip(p: str) -> str | None:
    p = p.split("\t")[0].strip()
    if p == "/dev/null":
        return None
    return p[2:] if p[:2] in ("a/", "b/") else p


def parse_patch(patch: str) -> list[dict]:
    """Unified diff -> [{old, new, hunks: [{old_start, old_len, new_start, new_len, body}]}]."""
    files, cur = [], None
    lines = patch.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            cur = {"old": _strip(line[4:]), "new": _strip(lines[i + 1][4:]), "hunks": []}
            files.append(cur)
            i += 2
            continue
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if m and cur is not None:
            os_, ol = int(m[1]), int(m[2]) if m[2] is not None else 1
            ns, nl = int(m[3]), int(m[4]) if m[4] is not None else 1
            body, o_left, n_left = [], ol, nl
            i += 1
            while i < len(lines) and (o_left > 0 or n_left > 0):
                b = lines[i]
                if b.startswith("\\"):
                    i += 1
                    continue
                tag = b[:1] if b else " "
                if tag == " ":
                    o_left, n_left = o_left - 1, n_left - 1
                elif tag == "-":
                    o_left -= 1
                elif tag == "+":
                    n_left -= 1
                else:
                    break
                body.append((tag, b[1:]))
                i += 1
            cur["hunks"].append({"old_start": os_, "old_len": ol, "new_start": ns, "new_len": nl, "body": body})
            continue
        i += 1
    return files


def apply_hunks(old_lines: list[str], hunks: list[dict]) -> tuple[list[str], list[int], list[int], int]:
    """Returns (new_lines, removed_old_linenos, added_new_linenos, context_mismatches). Line numbers are 1-based."""
    new, removed, added, mism = [], [], [], 0
    pos = 0  # 0-based index into old_lines
    for h in hunks:
        upto = h["old_start"] - 1 if h["old_len"] > 0 else h["old_start"]
        new.extend(old_lines[pos:upto])
        pos = upto
        for tag, text in h["body"]:
            if tag == " ":
                if pos < len(old_lines) and old_lines[pos].rstrip() != text.rstrip():
                    mism += 1
                new.append(old_lines[pos] if pos < len(old_lines) else text)
                pos += 1
            elif tag == "-":
                if pos < len(old_lines) and old_lines[pos].rstrip() != text.rstrip():
                    mism += 1
                removed.append(pos + 1)
                pos += 1
            else:
                new.append(text)
                added.append(len(new))
    new.extend(old_lines[pos:])
    return new, removed, added, mism


# ---------------------------------------------------------------- AST scopes


def scopes(src: str):
    """All def/class scopes as (start, end, chain) where chain = ((name, kind), ...); plus import and blank lines."""
    tree = ast.parse(src)
    out = []
    def_line = {}

    def walk(node, chain):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = {ast.FunctionDef: "func", ast.AsyncFunctionDef: "async", ast.ClassDef: "class"}[type(child)]
                start = min([d.lineno for d in child.decorator_list] + [child.lineno])
                c = chain + ((child.name, kind),)
                out.append((start, child.end_lineno, c))
                def_line[c] = child.lineno
                walk(child, c)
            else:
                walk(child, chain)

    walk(tree, ())
    import_lines = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.update(range(node.lineno, node.end_lineno + 1))
    return out, import_lines, def_line


def enclosing(scope_list, line: int):
    best = None
    for start, end, chain in scope_list:
        if start <= line <= end and (best is None or start > best[0] or (start == best[0] and end < best[1])):
            best = (start, end, chain)
    return best


# ---------------------------------------------------------------- graph naming


def module_candidates(path: str) -> list[str]:
    p = path[:-3] if path.endswith(".py") else path
    parts = p.split("/")
    variants = [parts]
    if parts[0] in ("src", "docs_src") and len(parts) > 1:
        variants.append(parts[1:])
    out = []
    for v in variants:
        out.append(".".join(v))
        if v[-1] == "__init__" and len(v) > 1:
            out.append(".".join(v[:-1]))
    return list(dict.fromkeys(out))


def name_candidates(path: str, chain) -> list[str]:
    full = ".".join(n for n, _ in chain)
    flat = ".".join([n for n, k in chain[:-1] if k == "class"] + [chain[-1][0]])
    return [f"{m}.{nm}" for m in module_candidates(path) for nm in dict.fromkeys([full, flat])]


# ---------------------------------------------------------------- read_file cost model


def window_cost(lines: list[str], start: int, end: int) -> int:
    """Characters returned by read_file calls starting at `start` until line `end` is covered (1-based)."""
    total, cur = 0, start
    while cur <= end and cur <= len(lines):
        n_lines, chars = 0, 0
        while n_lines < READ_LINES and cur + n_lines <= len(lines):
            ln = len(lines[cur + n_lines - 1]) + 1
            if n_lines > 0 and chars + ln > READ_CHARS:
                break
            chars += ln
            n_lines += 1
        total += chars
        cur += n_lines
    return total


def text_chars(lines: list[str], start: int, end: int) -> int:
    return sum(len(x) + 1 for x in lines[start - 1 : end])


def norm(s: str) -> str:
    return "\n".join(x.rstrip() for x in textwrap.dedent(s).strip("\n").split("\n"))


def nows(s: str) -> str:
    return re.sub(r"\s+", "", s)


# ---------------------------------------------------------------- main


def load_snapshot_files(tgz: Path, wanted: set[str]) -> dict[str, str]:
    got = {}
    with tarfile.open(tgz, "r:gz") as tf:
        for m in tf:
            name = m.name[2:] if m.name.startswith("./") else m.name
            if name in wanted and m.isfile():
                got[name] = tf.extractfile(m).read().decode("utf-8", errors="replace")
                if len(got) == len(wanted):
                    break
    return got


def main():
    global OUT
    t0 = time.time()
    dry = "--dry-run" in sys.argv  # first 3 graphs only, written to results_dryrun/
    if dry:
        OUT = OUT.parent / "results_dryrun"
    OUT.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(line) for line in open(DATA / "tasks.jsonl", encoding="utf-8")]
    by_graph = defaultdict(list)
    for t in tasks:
        by_graph[f"{t['repo'].split('/')[1]}_{t['base_commit']}"].append(t)
    if dry:
        picks = sorted(by_graph)
        by_graph = {k: by_graph[k] for k in (picks[0], picks[-1], picks[len(picks) // 2])}

    task_rows, unit_rows, graph_rows, rand_payloads = [], [], [], []
    rng = np.random.default_rng(20260930)  # seed string: the audit date

    for gkey, gtasks in sorted(by_graph.items()):
        g = json.load(open(DATA / "graphs" / f"{gkey}.json", encoding="utf-8"))
        text = {n["id"]: (n.get("text") or "") for n in g["nodes"]}
        ids = set(text)
        emb = np.load(DATA / "embeddings" / f"{gkey}.npz")
        keys = list(emb.files)
        mat = np.stack([emb[k] for k in keys]).astype(np.float32)
        mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12
        kidx = {k: i for i, k in enumerate(keys)}
        tlen = np.array([len(text.get(k, "")) for k in keys])
        pkg = gtasks[0]["repo"].split("/")[1]

        def search(q: str):
            i = kidx.get(q)
            if i is None:
                return None
            sims = mat @ mat[i]
            sims[i] = -np.inf  # "across all other nodes"
            top = np.argpartition(-sims, K_SEARCH)[:K_SEARCH]
            return [keys[j] for j in top[np.argsort(-sims[top])]], float(np.mean(sims[top]))

        core = [k for k in keys if k.startswith(pkg + ".")]
        for k in rng.choice(core, size=min(50, len(core)), replace=False) if core else []:
            hits, _ = search(k)
            rand_payloads.append(int(sum(len(text.get(h, "")) for h in hits)))
        big = sorted(((len(v), k) for k, v in text.items()), reverse=True)[:3]
        graph_rows.append({
            "graph": gkey, "nodes": len(ids), "edges": len(g["edges"]), "npz_keys": len(keys),
            "npz_keys_not_in_graph": sum(k not in ids for k in keys),
            "nodes_over_35k_chars": sum(len(v) > 35_000 for v in text.values()),
            "largest_node_chars": big[0][0] if big else 0, "largest_node": big[0][1] if big else "",
        })

        for t in gtasks:
            files = parse_patch(t["patch"])
            wanted = {f["old"] for f in files if f["old"]}
            snap = load_snapshot_files(DATA / "snapshots" / f"{t['instance_id']}.tgz", wanted)
            row = Counter()
            notes = []
            units = {}  # (path, chain) -> dict
            modlevel_lines = 0
            full_read, full_read_py = 0, 0
            for f in files:
                path = f["old"] or f["new"]  # the graph is built at base_commit, so name units by the old path
                exists = f["old"] in snap if f["old"] else False
                is_new = (f["old"] is None) or (not exists and all(h["old_start"] == 0 for h in f["hunks"]))
                row["files"] += 1
                if is_new:
                    row["new_files"] += 1
                    continue
                if not exists:
                    notes.append(f"missing-in-snapshot:{f['old']}")
                    continue
                old_src = snap[f["old"]]
                old_lines = old_src.split("\n")
                full_read += len(old_src)
                if not path.endswith(".py"):
                    row["nonpy_files"] += 1
                    continue
                row["py_files"] += 1
                full_read_py += len(old_src)
                new_lines, removed, added, mism = apply_hunks(old_lines, f["hunks"])
                if mism:
                    notes.append(f"context-mismatch:{path}:{mism}")
                try:
                    old_scopes, old_imports, old_def_line = scopes(old_src)
                    new_scopes, new_imports, _ = scopes("\n".join(new_lines))
                except SyntaxError as e:
                    notes.append(f"parse-error:{path}:{e.lineno}")
                    row["parse_errors"] += 1
                    continue
                old_by_chain = {c: (s, e) for s, e, c in old_scopes}

                def touch(chain):
                    s, e = old_by_chain[chain]
                    units.setdefault((path, chain), {"path": path, "chain": chain, "start": s, "end": e,
                                                     "def_line": old_def_line[chain], "lines": old_lines})

                for ln in removed:
                    if ln in old_imports or not old_lines[ln - 1].strip():
                        continue
                    enc = enclosing(old_scopes, ln)
                    if enc:
                        touch(enc[2])
                    else:
                        modlevel_lines += 1
                for ln in added:
                    if ln in new_imports or not new_lines[ln - 1].strip():
                        continue
                    enc = enclosing(new_scopes, ln)
                    chain = enc[2] if enc else ()
                    while chain and chain not in old_by_chain:
                        chain = chain[:-1]
                    if chain:
                        touch(chain)
                    else:
                        modlevel_lines += 1

            n_addr, n_async, unit_c, win_c = 0, 0, 0, 0
            payloads, same_mod, fid_eq = [], [], []
            for (path, chain), u in units.items():
                cands = name_candidates(path, chain)
                hit = next((c for c in cands if c in ids), None)
                kind = chain[-1][1]
                uc = text_chars(u["lines"], u["start"], u["end"])
                wc = window_cost(u["lines"], u["start"], u["end"])
                unit_c += uc
                win_c += wc
                n_async += kind == "async"
                ur = {"instance_id": t["instance_id"], "path": path, "qualname": ".".join(n for n, _ in chain),
                      "kind": kind, "lines": u["end"] - u["start"] + 1, "unit_chars": uc, "window_chars": wc,
                      "addressable": hit is not None, "graph_id": hit or "", "parent_class_addressable": "",
                      "graph_text_chars": "", "text_equals_source": "", "text_similarity": "",
                      "search_payload_chars": "", "search_same_module": ""}
                if hit:
                    n_addr += 1
                    src = "\n".join(u["lines"][u["start"] - 1 : u["end"]])
                    src_nodec = "\n".join(u["lines"][u["def_line"] - 1 : u["end"]])
                    gt = text[hit]
                    eq = nows(gt) in (nows(src), nows(src_nodec))  # whitespace-insensitive
                    fid_eq.append(eq)
                    ur["graph_text_chars"], ur["text_equals_source"] = len(gt), eq
                    if len(src) < 20_000 and len(gt) < 20_000:
                        ur["text_similarity"] = round(difflib.SequenceMatcher(None, norm(gt), norm(src)).ratio(), 3)
                    res = search(hit)
                    if res:
                        hits, _ = res
                        mods = module_candidates(path)
                        p = int(sum(len(text.get(h, "")) for h in hits))
                        sm = sum(any(h.startswith(m + ".") for m in mods) for h in hits)
                        payloads.append(p)
                        same_mod.append(sm)
                        ur["search_payload_chars"], ur["search_same_module"] = p, sm
                else:
                    cls = [i for i, (_, k) in enumerate(chain) if k == "class"]
                    if cls:
                        pc = chain[: cls[-1] + 1]
                        ur["parent_class_addressable"] = any(c in ids for c in name_candidates(path, pc))
                unit_rows.append(ur)

            n_units = len(units)
            task_rows.append({
                "instance_id": t["instance_id"], "repo": t["repo"], "files": row["files"],
                "py_files": row["py_files"], "new_files": row["new_files"], "nonpy_files": row["nonpy_files"],
                "units": n_units, "units_addressable": n_addr,
                "all_addressable": (n_addr == n_units) if n_units else "",
                "async_units": n_async, "modlevel_lines": modlevel_lines,
                "full_read_chars": full_read, "full_read_py_chars": full_read_py,
                "unit_chars": unit_c, "window_chars": win_c,
                "window_unit_ratio": round(win_c / unit_c, 3) if unit_c else "",
                "full_unit_ratio": round(full_read_py / unit_c, 3) if unit_c else "",
                "search_payload_median": st.median(payloads) if payloads else "",
                "search_same_module_mean": round(st.mean(same_mod), 2) if same_mod else "",
                "graph_text_equals_source_share": round(sum(fid_eq) / len(fid_eq), 3) if fid_eq else "",
                "problem_chars": len(t["problem_statement"]), "hints_chars": len(t["hints_text"] or ""),
                "parse_errors": row["parse_errors"], "notes": ";".join(notes),
            })
        print(f"{gkey}: {len(gtasks)} task(s), {time.time() - t0:.0f}s", flush=True)

    # ------------------------------------------------------------ decision
    k1_pool = [r for r in task_rows if r["units"]]
    k1 = sum(r["all_addressable"] is True for r in k1_pool) / len(k1_pool)
    k2 = st.median(r["full_read_chars"] for r in task_rows)
    k3_pool = [r["window_unit_ratio"] for r in task_rows if r["window_unit_ratio"] != ""]
    k3 = st.median(k3_pool)
    v1 = "KILL" if k1 < K1_KILL else "WEAKENED" if k1 < K1_PASS else "PASS"
    v2 = "KILL" if k2 <= K2_KILL_CHARS else "PASS"
    v3 = "KILL" if k3 < K3_KILL else "WEAKENED" if k3 < K3_PASS else "PASS"
    verdicts = [v1, v2, v3]
    overall = "KILL" if "KILL" in verdicts else "WEAKENED" if "WEAKENED" in verdicts else "PASS"

    au = [u for u in unit_rows]
    pay = [u["search_payload_chars"] for u in au if u["search_payload_chars"] != ""]
    summary = {
        "label": "EXPLORATORY; decision rule fixed in NOTES.md 2026-09-30 19:12 EDT before computing",
        "inputs": {"tasks.jsonl_sha256": sha256_file(DATA / "tasks.jsonl"),
                   "script_sha256": sha256_file(Path(__file__))},
        "n_tasks": len(task_rows),
        "K1_addressability": {"pool_tasks_with_preexisting_py_units": len(k1_pool),
                              "tasks_all_units_addressable": sum(r["all_addressable"] is True for r in k1_pool),
                              "share": round(k1, 4), "verdict": v1},
        "K2_leverage": {"median_full_read_chars": k2, "verdict": v2},
        "K3_compression": {"pool_tasks": len(k3_pool), "median_window_over_unit": k3, "verdict": v3},
        "overall": overall,
        "descriptive": {
            "tasks_by_repo": dict(Counter(r["repo"] for r in task_rows)),
            "tasks_with_no_preexisting_py_unit": len(task_rows) - len(k1_pool),
            "tasks_with_new_files": sum(r["new_files"] > 0 for r in task_rows),
            "units_total": len(au), "units_addressable": sum(u["addressable"] for u in au),
            "units_by_kind": dict(Counter(u["kind"] for u in au)),
            "units_addressable_by_kind": dict(Counter(u["kind"] for u in au if u["addressable"])),
            "unaddressable_with_parent_class_in_graph": sum(u["parent_class_addressable"] is True for u in au),
            "unit_lines_median": st.median(u["lines"] for u in au) if au else None,
            "unit_chars_median": st.median(u["unit_chars"] for u in au) if au else None,
            "full_read_py_chars_median": st.median(r["full_read_py_chars"] for r in task_rows),
            "full_over_unit_median": st.median(r["full_unit_ratio"] for r in task_rows if r["full_unit_ratio"] != ""),
            "graph_text_equals_source_share": round(sum(u["text_equals_source"] is True for u in au if u["addressable"])
                                                    / max(1, sum(u["addressable"] for u in au)), 3),
            "search_payload_chars_gold_median": st.median(pay) if pay else None,
            "search_payload_chars_gold_p90": float(np.percentile(pay, 90)) if pay else None,
            "search_payload_chars_random_core_median": st.median(rand_payloads) if rand_payloads else None,
            "search_same_module_hits_of_10_mean": round(st.mean([u["search_same_module"] for u in au
                                                                 if u["search_same_module"] != ""]), 2) if pay else None,
            "graphs_with_node_over_35k_chars": sum(r["nodes_over_35k_chars"] > 0 for r in graph_rows),
            "largest_node_chars_max": max(r["largest_node_chars"] for r in graph_rows),
            "problem_chars_median": st.median(r["problem_chars"] for r in task_rows),
            "hints_chars_median": st.median(r["hints_chars"] for r in task_rows),
            "tasks_with_notes": sum(bool(r["notes"]) for r in task_rows),
        },
        "runtime_seconds": round(time.time() - t0, 1),
        "python": sys.version.split()[0],
    }
    # POST-DATA sensitivity readings: decided after the 3-graph dry run, not part of the registered verdict.
    nonpkg = ("docs_src/", "docs/", "tests/", "scripts/", "examples/", "benchmarks/", "tools/")
    per_task_units = defaultdict(list)
    for u in unit_rows:
        per_task_units[u["instance_id"]].append(u)
    k3_noclass, k1_pkg_pool, k1_pkg_ok = [], 0, 0
    for r in task_rows:
        us = per_task_units.get(r["instance_id"], [])
        fu = [u for u in us if u["kind"] != "class"]
        uc = sum(u["unit_chars"] for u in fu)
        if uc:
            k3_noclass.append(sum(u["window_chars"] for u in fu) / uc)
        pu = [u for u in us if not u["path"].startswith(nonpkg)]
        if pu:
            k1_pkg_pool += 1
            k1_pkg_ok += all(u["addressable"] for u in pu)
    summary["sensitivity_postdata"] = {
        "label": "POST-DATA (decided after a 3-graph dry run); does not change the registered verdict",
        "K3_excluding_class_units": {"pool_tasks": len(k3_noclass),
                                     "median_window_over_unit": round(st.median(k3_noclass), 3) if k3_noclass else None},
        "K1_package_source_only": {"pool_tasks": k1_pkg_pool, "tasks_all_addressable": k1_pkg_ok,
                                   "share": round(k1_pkg_ok / k1_pkg_pool, 4) if k1_pkg_pool else None},
        "K1_unit_level_share": round(sum(u["addressable"] for u in unit_rows) / max(1, len(unit_rows)), 4),
    }
    for name, rows in (("per_task.csv", task_rows), ("units.csv", unit_rows), ("graphs.csv", graph_rows)):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
