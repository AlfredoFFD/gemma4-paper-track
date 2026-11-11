"""Independent recount (EXPLORATORY) on the runs of experiment 22, extending analysis/rederive_cost_18.py: what the
runs read, when they first edit the fix, which regions of the fix they are shown and edit, and (new part G) where a run
first reads a file of its task's note. Written from a brief's rules, blind to the project's own scripts and outputs for
the same counts.

Rules: exactly those of analysis/rederive_cost_18.py (its docstring), whose step pairing, READ, CHANGED REGION, FIX EDIT
(diff parsed on its OLD side), EDITED and SHOWN this script imports unchanged. Differences:
- Runs: analysis/results/22/<N|ON|OF|OA>/seed3; tasks and endings from runs_22.csv, rows with seed 3.
- Part D: every pair of arms, the later minus the earlier in the order N, ON, OF, OA.
- Part G: the files of a task's note are the files of its PLACES (data/cache/oracle_18/<task>.json, "places"). For each
  run and each such file the run READ (read_file of status ok, not of a file the run wrote with an ok write_file
  earlier), its FIRST such read is classed by the start line it asked: AT LINE 1 (none asked, or 1 or less); AT A
  RANGE OF THE NOTE (within a range the run's note gave for that file, widened by 10 lines each side: arm OA, the
  PLACES with a start and an end; arm OF, the lines "- <file>, lines <a>-<b> (...)" of data/cache/oracle_22/<task>.json
  key "OF"; arms N and ON, none); AT ANOTHER LINE (any other start above 1).

Usage: py -I -X utf8 analysis/rederive_cost_22.py [--no-write]
It prints the report and stores the same text in analysis/results/22/rederive_cost_22.txt (LF line endings).
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402
import rederive_cost_18 as C18  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
fmt = R.fmt
BASE = HERE / "results" / "22"
OUT = BASE / "rederive_cost_22.txt"
ARMS = ["N", "ON", "OF", "OA"]
dg = C18.dg
median, mean, overl = C18.median, C18.mean, C18.overl
OF_LINE = re.compile(r"^\s*-\s*(.+?), lines (\d+)-(\d+)\b")


def note(tid):
    key = tid.replace("/", "__")
    d18 = json.loads((ROOT / "data" / "cache" / "oracle_18" / f"{key}.json").read_text(encoding="utf-8"))
    places = d18.get("places") or []
    files = {R.norm_file(p.get("file")) for p in places if isinstance(p.get("file"), str)}
    oa = collections.defaultdict(list)
    for p in places:
        if isinstance(p.get("file"), str) and R.isnum(p.get("start")) and R.isnum(p.get("end")):
            oa[R.norm_file(p["file"])].append((p["start"], p["end"]))
    of = collections.defaultdict(list)
    f22 = ROOT / "data" / "cache" / "oracle_22" / f"{key}.json"
    if f22.exists():
        txt = json.loads(f22.read_text(encoding="utf-8")).get("OF") or ""
        for line in txt.splitlines():
            m = OF_LINE.match(line)
            if m:
                of[R.norm_file(m.group(1).strip())].append((int(m.group(2)), int(m.group(3))))
    else:
        dg["no oracle_22 note file"] += 1
    return files, {"OA": oa, "OF": of}


def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    table = {}
    with open(BASE / "runs_22.csv", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("seed") == "3":
                table[(row["task"], row["arm"])] = row
    tlist = sorted({t for t, _ in table})

    recs = {}
    for arm in ARMS:
        sd = BASE / arm / "seed3"
        results = R.ours_results(str(sd))
        for tid in tlist:
            task = tasks[tid]
            regs = R.changed_regions(task["patch"], collections.Counter())
            if not regs:
                dg["task without a CHANGED REGION"] += 1
            tp = sd / "traces" / f"trace_{tid.replace('/', '__')}.json"
            if not tp.exists():
                dg[f"missing trace ({arm})"] += 1
                continue
            run = C18.Run18(str(tp), task.get("problem_statement") or "")
            reads, ranges = R.analyse_run(run)
            rd = [r for r in reads if r["ok"] and not r["own"] and r["rstart"] is not None]
            lines = sum(max(0, r["rend"] - r["rstart"] + 1) for r in rd)
            distinct = len({(r["file"], L) for r in rd for L in range(r["rstart"], r["rend"] + 1)})
            reg_files = {f for f, _, _ in regs}
            first_fix = None
            for c in run.calls:
                if c["fname"] != "edit_file" or not (isinstance(c["result"], dict) and c["result"].get("status") == "ok"):
                    continue
                fp = R.norm_file(c["result"].get("filepath")) or R.norm_file(c["args"].get("filepath"))
                d = c["result"].get("diff")
                if fp not in reg_files or not isinstance(d, str):
                    continue
                er = R.changed_regions(d, collections.Counter())
                if any(ef == f and overl(a, b, ea, eb) for f, a, b in regs for ef, ea, eb in er):
                    first_fix = c["idx"]
                    break
            shown = [any(overl(a, b, s, e) for _, s, e in ranges.get(f, [])) for f, a, b in regs]
            res = results.get(tid)
            if res is None:
                dg[f"no task result ({arm})"] += 1
            pf = sd / "patches" / f"{tid.replace('/', '__')}.patch"
            if pf.exists():
                patch = pf.read_text(encoding="utf-8", errors="replace")
            else:
                patch = (res or {}).get("agent_patch") or (res or {}).get("patch") or ""
                dg[f"final patch not in patches/ ({arm})"] += 1
            fpr = R.changed_regions(patch if isinstance(patch, str) else "", collections.Counter())
            edited = [any(ff == f and overl(a, b, fa, fb) for ff, fa, fb in fpr) for f, a, b in regs]
            resolved = R.is_true((res or {}).get("resolved"))
            row = table.get((tid, arm))
            if row is None:
                dg[f"no row in runs_22.csv ({arm})"] += 1
            elif R.is_true(row.get("resolved")) != resolved:
                dg[f"resolved differs between task results and runs_22.csv ({arm})"] += 1
            ctx = bool(row) and row.get("ended") == "context window"
            # part G
            nfiles, nranges = note(tid)
            g = collections.Counter()
            seen = set()
            for r in rd:  # in call order
                if r["file"] in seen:
                    continue
                seen.add(r["file"])
                if r["file"] not in nfiles:
                    continue
                g["first reads"] += 1
                s = r["start"]
                if s is None or s <= 1:
                    g["AT LINE 1"] += 1
                elif any(a - 10 <= s <= b + 10 for a, b in nranges.get(arm, {}).get(r["file"], [])):
                    g["AT A RANGE OF THE NOTE"] += 1
                else:
                    g["AT ANOTHER LINE"] += 1
            recs[(tid, arm)] = dict(reads=len(rd), lines=lines, distinct=distinct, first_fix=first_fix,
                                    n_calls=len(run.calls), regs=regs, shown=shown, edited=edited,
                                    resolved=resolved, ctx=ctx, g=g)

    L = ["INDEPENDENT RECOUNT (EXPLORATORY): experiment 22, reading cost, first fix edit, regions shown and edited, "
         "first reads of the note's files", "=" * 100,
         f"tasks {len(tlist)}; arms {', '.join(ARMS)}; runs found {len(recs)}"]
    P = L.append
    for arm in ARMS:
        rs = [recs[(t, arm)] for t in tlist if (t, arm) in recs]
        P("")
        P(f"### arm {arm}: runs {len(rs)}")
        P(f"A. reads per run mean {mean([r['reads'] for r in rs])}, median {median([r['reads'] for r in rs])}; "
          f"LINES READ per run mean {mean([r['lines'] for r in rs])}, median {median([r['lines'] for r in rs])}; "
          f"DISTINCT LINES per run mean {mean([r['distinct'] for r in rs])}, median {median([r['distinct'] for r in rs])}")
        fx = [r for r in rs if r["first_fix"] is not None]
        P(f"B. runs with a FIX EDIT {fmt(len(fx), len(rs))}; median call of the first FIX EDIT {median([r['first_fix'] for r in fx])}")
        cw = [r for r in rs if r["ctx"]]
        P(f"C. by call (runs ended on the context window: {len(cw)}):")
        for c in (5, 10, 15, 20, 30, 40, None):
            lab = "end" if c is None else str(c)
            nf = sum(1 for r in fx if c is None or r["first_fix"] <= c)
            nc = sum(1 for r in cw if c is None or r["n_calls"] <= c)
            P(f"   {lab}: first FIX EDIT {nf}, ended on the context window {nc}")
        lo = [(f, a, b, s, e) for r in rs for (f, a, b), s, e in zip(r["regs"], r["shown"], r["edited"])]
        for lab, sel in (("IN THE FIRST 150 LINES", lambda a: a <= 150), ("BELOW LINE 150", lambda a: a > 150)):
            sub = [x for x in lo if sel(x[1])]
            P(f"E. CHANGED REGIONS {lab}: {len(sub)}; SHOWN {fmt(sum(x[3] for x in sub), len(sub))}; "
              f"EDITED {fmt(sum(x[4] for x in sub), len(sub))}")
        g = collections.Counter()
        for r in rs:
            g.update(r["g"])
        n = g["first reads"]
        P(f"G. first reads of a file of the note {n}; AT LINE 1 {fmt(g['AT LINE 1'], n)}; "
          f"AT A RANGE OF THE NOTE {fmt(g['AT A RANGE OF THE NOTE'], n)}; AT ANOTHER LINE {fmt(g['AT ANOTHER LINE'], n)}")

    P("")
    P("D. paired by task, mean difference over the tasks with a run in both arms (later arm minus earlier)")
    for i, b in enumerate(ARMS):
        for a in ARMS[i + 1:]:
            ts = [t for t in tlist if (t, a) in recs and (t, b) in recs]
            dl = [recs[(t, a)]["lines"] - recs[(t, b)]["lines"] for t in ts]
            dr = [recs[(t, a)]["reads"] - recs[(t, b)]["reads"] for t in ts]
            P(f"   {a} minus {b} (tasks {len(ts)}): LINES READ {mean(dl)}; reads {mean(dr)}")

    P("")
    clean = [t for t in tlist if not any(recs.get((t, a), {}).get("ctx") for a in ARMS)]
    other = [t for t in tlist if t not in clean]
    P(f"F. tasks on which no arm's run ended on the context window: {len(clean)}; other tasks: {len(other)}")
    for lab, ts in (("no context-window ending", clean), ("other tasks", other)):
        P(f"   {lab}: " + "; ".join(
            f"{a} FIX EDIT {sum(recs[(t, a)]['first_fix'] is not None for t in ts if (t, a) in recs)}, "
            f"resolved {sum(recs[(t, a)]['resolved'] for t in ts if (t, a) in recs)}" for a in ARMS))
    P("")
    P("Diagnostics: " + ("; ".join(f"{k}: {v}" for k, v in sorted(dg.items())) or "none"))
    text = "\n".join(L) + "\n"
    print(text, end="")
    if "--no-write" in sys.argv[1:]:
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
