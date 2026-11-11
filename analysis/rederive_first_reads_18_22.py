"""Independent recount (EXPLORATORY): where runs first read a file of their task's note, experiments 18 and 22, under
two rules. Written from a brief's rules, blind to the project's own scripts and outputs for the same counts. It imports
the step pairing, READ and note parsing of analysis/rederive_cost_18.py and analysis/rederive_cost_22.py unchanged.

- Files of the note: the files of the task's PLACES (data/cache/oracle_18/<task>.json, "places"), for every arm.
- For each run and each such file the run READ (read_file of status ok, not of a file the run wrote with an ok
  write_file earlier), its FIRST such read is classed by the start line s and end line asked:
  RULE S: AT LINE 1 (no start asked, or 1 or less); START INSIDE A RANGE OF THE NOTE (s within a range of the run's
  note for that file widened by 10 lines on each side); AT ANOTHER LINE.
  RULE W: AT LINE 1; WINDOW AT A RANGE OF THE NOTE (some line of a range lies within s - 10 .. w + 10, where w is the
  end asked if asked and not before s, at most s + 149, and s + 149 when none was asked); AT ANOTHER LINE.
- Ranges of the note: arm OA, the PLACES with a start and an end; arm OF (experiment 22), the "- <file>, lines a-b"
  lines of data/cache/oracle_22/<task>.json key "OF"; arms N and ON, none.
- Experiment 18: analysis/results/18/<N|ON|OA>/seed2, tasks of analysis/oracle_18/tasks_18.txt. Experiment 22:
  analysis/results/22/<N|ON|OF|OA>/seed3, tasks of runs_22.csv rows with seed 3.

Usage: py -I -X utf8 analysis/rederive_first_reads_18_22.py [--no-write]
It prints the report and stores the same text in analysis/results/rederive_first_reads_18_22.txt (LF line endings).
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
import rederive_cost_18 as C18  # noqa: E402
import rederive_cost_22 as C22  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
fmt = R.fmt
OUT = HERE / "results" / "rederive_first_reads_18_22.txt"


def experiments():
    t18 = [x.strip() for x in (HERE / "oracle_18" / "tasks_18.txt").read_text(encoding="utf-8").splitlines() if x.strip()]
    with open(HERE / "results" / "22" / "runs_22.csv", encoding="utf-8", newline="") as fh:
        t22 = sorted({row["task"] for row in csv.DictReader(fh) if row.get("seed") == "3"})
    return [("experiment 18", HERE / "results" / "18", "seed2", ["N", "ON", "OA"], t18),
            ("experiment 22", HERE / "results" / "22", "seed3", ["N", "ON", "OF", "OA"], t22)]


def main():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    L = ["INDEPENDENT RECOUNT (EXPLORATORY): first reads of a file of the note, rules S and W", "=" * 100]
    P = L.append
    for label, base, seed, arms, tlist in experiments():
        P("")
        P(f"### {label}: tasks {len(tlist)}")
        for arm in arms:
            S = collections.Counter()
            W = collections.Counter()
            nruns = 0
            for tid in tlist:
                tp = base / arm / seed / "traces" / f"trace_{tid.replace('/', '__')}.json"
                if not tp.exists():
                    C18.dg[f"missing trace ({label}, {arm})"] += 1
                    continue
                nruns += 1
                run = C18.Run18(str(tp), tasks[tid].get("problem_statement") or "")
                reads, _ = R.analyse_run(run)
                rd = [r for r in reads if r["ok"] and not r["own"] and r["rstart"] is not None]
                nfiles, nranges = C22.note(tid)
                rngs = nranges.get(arm, {})
                seen = set()
                for r in rd:
                    if r["file"] in seen:
                        continue
                    seen.add(r["file"])
                    if r["file"] not in nfiles:
                        continue
                    S["n"] += 1
                    W["n"] += 1
                    s, e = r["start"], r["end"]
                    if s is None or s <= 1:
                        S["AT LINE 1"] += 1
                        W["AT LINE 1"] += 1
                        continue
                    fr = rngs.get(r["file"], [])
                    S["IN" if any(a - 10 <= s <= b + 10 for a, b in fr) else "OTHER"] += 1
                    ws, we = R.window(s, e)
                    W["IN" if any(a <= we + 10 and b >= ws - 10 for a, b in fr) else "OTHER"] += 1
            n = S["n"]
            P(f"   arm {arm:<3} runs {nruns:>2}; first reads of a file of the note {n}")
            P(f"      RULE S: AT LINE 1 {fmt(S['AT LINE 1'], n)}; START INSIDE A RANGE OF THE NOTE {fmt(S['IN'], n)}; "
              f"AT ANOTHER LINE {fmt(S['OTHER'], n)}")
            P(f"      RULE W: AT LINE 1 {fmt(W['AT LINE 1'], n)}; WINDOW AT A RANGE OF THE NOTE {fmt(W['IN'], n)}; "
              f"AT ANOTHER LINE {fmt(W['OTHER'], n)}")
    P("")
    P("Diagnostics: " + ("; ".join(f"{k}: {v}" for k, v in sorted(C18.dg.items())) or "none"))
    text = "\n".join(L) + "\n"
    print(text, end="")
    if "--no-write" in sys.argv[1:]:
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
