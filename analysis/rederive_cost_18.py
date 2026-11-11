"""Independent recount (EXPLORATORY) on the runs of experiment 18: what the runs read, when they first edit the fix,
and which regions of the fix they are shown and edit. Written from a brief's rules, blind to the project's own scripts
and outputs for the same counts. It reuses the READ classing, CHANGED REGION rule and result loaders of
analysis/rederive_read_starts.py (an earlier independent script).

Rules as implemented:
- Runs: analysis/results/18/<N|ON|OA>/seed2, one per task of analysis/oracle_18/tasks_18.txt and arm.
- Steps with several tool calls: the step's own observation is the result of its FIRST call; the results of the other
  calls are the observations of the steps that follow and hold no tool call, in order. Calls are numbered from 1 in
  trace order after this pairing.
- READ: a read_file call of status ok whose file the run had not written with an ok write_file call earlier. Its lines
  are its returned start_line..end_line. LINES READ: sum of the returned lengths; DISTINCT LINES: distinct
  (file, line) pairs.
- CHANGED REGION: per hunk of the reference patch, in a file the patch does not create, the old-file lines from the
  first to the last removed line, a pure insertion counting the two old lines around it.
- FIX EDIT: an edit_file call of status ok on a file with a CHANGED REGION whose returned diff, parsed by the same
  rule on its OLD side (the file as it stood at that call), has a region overlapping a CHANGED REGION of that file.
- EDITED: a region of the run's final patch (stored patch; same rule, old side, created files left out) overlaps the
  CHANGED REGION. SHOWN: the returned range of an ok read_file of the region's file overlaps it (own-file reads
  included, as in the earlier script).
- IN THE FIRST 150 LINES: region start <= 150; else BELOW LINE 150.
- Medians: the element at index n // 2 of the sorted list.
- How a run ended (context window) comes from the per-run table runs_18.csv (rows with launch 18); resolved from the
  per-task results of each run folder (cross-checked against the table).

Usage: py -I -X utf8 analysis/rederive_cost_18.py [--no-write]
It prints the report and stores the same text in analysis/results/rederive_cost_18.txt (LF line endings).
"""
import collections
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
fmt = R.fmt
BASE = HERE / "results" / "18"
OUT = HERE / "results" / "rederive_cost_18.txt"
ARMS = ["N", "ON", "OA"]
dg = collections.Counter()


class Run18(R.Run):
    """R.Run with the pairing of this experiment's traces: several calls in one step take the observations of the
    following call-less steps."""

    def __init__(self, path, task_text):
        d = json.load(open(path, encoding="utf-8"))
        self.calls = []
        pending = []
        for s in d.get("steps", []):
            tcs = s.get("tool_calls") or []
            if tcs:
                if pending:
                    dg["calls left without a result (next step had a call)"] += len(pending)
                pending = []
                if len(tcs) > 1:
                    dg["steps with several tool calls"] += 1
                for j, tc in enumerate(tcs):
                    args = tc.get("arguments") if isinstance(tc.get("arguments"), dict) else {}
                    c = dict(idx=len(self.calls) + 1, fname=tc.get("function_name"), args=args, result=None, text="")
                    self.calls.append(c)
                    if j == 0:
                        self._set(c, s.get("observation"))
                    else:
                        pending.append(c)
            elif s.get("observation") is not None:
                if pending:
                    self._set(pending.pop(0), s.get("observation"))
                else:
                    dg["observation with no call waiting (ignored)"] += 1
        if pending:
            dg["calls left without a result (end of trace)"] += len(pending)
        self.task_text = task_text
        self._named = {}

    @staticmethod
    def _set(c, obs):
        if obs is None:
            dg["call with no observation"] += 1
            return
        tn = (obs.get("extra") or {}).get("tool_name") if isinstance(obs, dict) else None
        if tn is not None and tn != c["fname"]:
            dg["paired observation names another tool"] += 1
        res = R.parse_result(obs)
        c["result"] = res
        c["text"] = "\n".join(R.strings_in(res)) if res is not None else ""


def median(xs):
    return sorted(xs)[len(xs) // 2] if xs else "n/a"


def mean(xs):
    return f"{sum(xs) / len(xs):.2f}" if xs else "n/a"


def overl(a, b, c, d):
    return a <= d and c <= b


def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    tlist = [x.strip() for x in (HERE / "oracle_18" / "tasks_18.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
    table = {}
    with open(BASE / "runs_18.csv", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("launch") == "18":
                table[(row["task"], row["arm"])] = row

    recs = {}
    for arm in ARMS:
        sd = BASE / arm / "seed2"
        results = R.ours_results(str(sd))
        for tid in tlist:
            task = tasks[tid]
            regs = R.changed_regions(task["patch"], collections.Counter())
            tp = sd / "traces" / f"trace_{tid.replace('/', '__')}.json"
            if not tp.exists():
                dg[f"missing trace ({arm})"] += 1
                continue
            run = Run18(str(tp), task.get("problem_statement") or "")
            reads, ranges = R.analyse_run(run)
            rd = [r for r in reads if r["ok"] and not r["own"] and r["rstart"] is not None]
            lines = sum(max(0, r["rend"] - r["rstart"] + 1) for r in rd)
            distinct = len({(r["file"], L) for r in rd for L in range(r["rstart"], r["rend"] + 1)})
            # fix edits
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
            # shown / edited
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
                dg[f"no row in runs_18.csv ({arm})"] += 1
            elif R.is_true(row.get("resolved")) != resolved:
                dg[f"resolved differs between task results and runs_18.csv ({arm})"] += 1
            ctx = bool(row) and row.get("ended") == "context window"
            recs[(tid, arm)] = dict(reads=len(rd), lines=lines, distinct=distinct, first_fix=first_fix,
                                    n_calls=len(run.calls), regs=regs, shown=shown, edited=edited,
                                    resolved=resolved, ctx=ctx)

    L = ["INDEPENDENT RECOUNT (EXPLORATORY): experiment 18, reading cost, first fix edit, regions shown and edited",
         "=" * 100, f"tasks {len(tlist)}; arms {', '.join(ARMS)}; runs found {len(recs)}"]
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
        parts = []
        for c in (5, 10, 15, 20, 30, 40, None):
            lab = "end" if c is None else str(c)
            nf = sum(1 for r in fx if c is None or r["first_fix"] <= c)
            nc = sum(1 for r in cw if c is None or r["n_calls"] <= c)
            parts.append(f"{lab}: first FIX EDIT {nf}, ended on the context window {nc}")
        P(f"C. by call (runs ended on the context window: {len(cw)}):")
        for x in parts:
            P("   " + x)
        lo = [(f, a, b, s, e) for r in rs for (f, a, b), s, e in zip(r["regs"], r["shown"], r["edited"])]
        for lab, sel in (("IN THE FIRST 150 LINES", lambda a: a <= 150), ("BELOW LINE 150", lambda a: a > 150)):
            sub = [x for x in lo if sel(x[1])]
            P(f"E. CHANGED REGIONS {lab}: {len(sub)}; SHOWN {fmt(sum(x[3] for x in sub), len(sub))}; "
              f"EDITED {fmt(sum(x[4] for x in sub), len(sub))}")

    P("")
    P("D. paired by task, mean difference over the tasks with a run in both arms")
    for a, b in (("ON", "N"), ("OA", "N"), ("OA", "ON")):
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
