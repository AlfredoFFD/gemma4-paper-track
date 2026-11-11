"""Independent recount (EXPLORATORY): which regions of a fix a run is shown, by file, against independence.

Written from a brief's rules, blind to the project's own script and output for the same counts. It reuses the trace
loaders, the CHANGED REGION rule and the returned ranges of analysis/rederive_read_starts.py (an earlier independent
script), unchanged.

Rules as implemented:
- CHANGED REGION and SHOWN: as in rederive_read_starts.py (a region is SHOWN when the returned range of a read_file
  call with status ok on its file overlaps it).
- READ A FILE: a read_file call with status ok on that file returned a non-empty range (start_line <= end_line).
- First shown: the index of the first read whose returned range overlaps the region. The region shown first: smallest
  such index; ties go to the smaller (file path, start line).
- Classes by the number of CHANGED REGIONS: 1; 2 or 3; 4 to 9; 10 or more; 2 or more. Runs of tasks without a
  CHANGED REGION are left out.
- Independence: p1 = the set's share of runs of one-region fixes shown the region; expected runs shown every region
  in a class = sum over its runs of p1 ** (regions of the run's task).

Usage: py -I -X utf8 analysis/rederive_independence.py
It prints the report and stores the same text in analysis/results/rederive_independence.txt (LF line endings).
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
fmt = R.fmt
OUT = HERE / "results" / "rederive_independence.txt"
SETS = [("1. public starter agent, base arm", "public starter arm base"),
        ("2. public starter agent with the graph skill, skill arm", "public skill arm"),
        ("3. our whole runs of pre-registration 14, condition N", "ours N"),
        ("4. our whole runs of pre-registration 14, condition NAF", "ours NAF")]
CLASSES = [("1", lambda n: n == 1), ("2 or 3", lambda n: 2 <= n <= 3), ("4 to 9", lambda n: 4 <= n <= 9),
           ("10 or more", lambda n: n >= 10), ("2 or more", lambda n: n >= 2)]
MULTI = [c for c in CLASSES if c[0] != "1"]


def load_tasks():
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    return tasks


def run_record(path, task, regions):
    run = R.Run(path, task.get("problem_statement") or "")
    _, ranges = R.analyse_run(run)
    read_files = {f for f, rs in ranges.items() if any(s <= e for _, s, e in rs)}
    first = []
    for f, a, b in regions:
        hits = [i for i, s, e in ranges.get(f, []) if s <= b and a <= e]
        first.append(min(hits) if hits else None)
    shown = [x is not None for x in first]
    lead = None
    cands = [(first[i], regions[i][0], regions[i][1], i) for i in range(len(regions)) if shown[i]]
    if cands:
        lead = min(cands)[3]
    return dict(task=task["instance_id"], regions=regions, shown=shown, lead=lead, read=read_files,
                files=sorted({f for f, _, _ in regions}))


def report(label, runs):
    L = []
    P = L.append
    n1 = [r for r in runs if len(r["regions"]) == 1]
    p1 = sum(r["shown"][0] for r in n1) / len(n1) if n1 else 0.0
    P("")
    P(f"### {label}: runs {len(runs)} (of tasks with a CHANGED REGION); p1 = {sum(r['shown'][0] for r in n1)}/{len(n1)}"
      f" = {p1:.4f}")

    P("A. by the number of CHANGED REGIONS")
    for cl, f in CLASSES:
        rs = [r for r in runs if f(len(r["regions"]))]
        nreg = sum(len(r["regions"]) for r in rs)
        s = (f"   {cl:<10} tasks {len({r['task'] for r in rs}):>3}; runs {len(rs):>3}; "
             f"regions shown {fmt(sum(sum(r['shown']) for r in rs), nreg)}; "
             f"shown at least one {fmt(sum(any(r['shown']) for r in rs), len(rs))}; "
             f"shown every region {fmt(sum(all(r['shown']) for r in rs), len(rs))}")
        if cl != "1":
            s += f"; expected if independent {sum(p1 ** len(r['regions']) for r in rs):.1f}"
        P(s)

    P("B. runs shown at least one region: THE OTHERS (every region but the one shown first)")
    for cl, f in MULTI:
        rs = [r for r in runs if f(len(r["regions"])) and any(r["shown"])]
        o = same = other = o_sh = s_sh = d_sh = d_read = 0
        for r in rs:
            lf = r["regions"][r["lead"]][0]
            for i, (fl, _, _) in enumerate(r["regions"]):
                if i == r["lead"]:
                    continue
                o += 1
                o_sh += r["shown"][i]
                if fl == lf:
                    same += 1
                    s_sh += r["shown"][i]
                else:
                    other += 1
                    d_sh += r["shown"][i]
                    d_read += fl in r["read"]
        P(f"   {cl:<10} runs {len(rs):>3}; others shown {fmt(o_sh, o)}; in the file of the region shown first "
          f"{fmt(s_sh, same)}; in another file {fmt(d_sh, other)}, the run READ that file {fmt(d_read, other)}")

    P("C. by fix IN ONE FILE / IN SEVERAL FILES")
    for cl, f in MULTI:
        for lab, g in (("IN ONE FILE", lambda r: len(r["files"]) == 1), ("IN SEVERAL FILES", lambda r: len(r["files"]) > 1)):
            rs = [r for r in runs if f(len(r["regions"])) and g(r)]
            nreg = sum(len(r["regions"]) for r in rs)
            P(f"   {cl:<10} {lab:<16} tasks {len({r['task'] for r in rs}):>3}; runs {len(rs):>3}; "
              f"regions shown {fmt(sum(sum(r['shown']) for r in rs), nreg)}; "
              f"shown every region {fmt(sum(all(r['shown']) for r in rs), len(rs))}")

    P("D. fixes IN SEVERAL FILES")
    sev = [r for r in runs if len(r["files"]) > 1]

    def files_shown(r):
        return {r["regions"][i][0] for i in range(len(r["regions"])) if r["shown"][i]}

    nf = sum(len(r["files"]) for r in sev)
    P(f"   tasks {len({r['task'] for r in sev})}; runs {len(sev)}; FILES OF THE FIX {nf}; "
      f"files READ {fmt(sum(len(set(r['files']) & r['read']) for r in sev), nf)}; "
      f"files shown a region {fmt(sum(len(files_shown(r)) for r in sev), nf)}; "
      f"runs that READ every file {fmt(sum(set(r['files']) <= r['read'] for r in sev), len(sev))}")
    for lab, g in (("2 files", lambda k: k == 2), ("3 files", lambda k: k == 3), ("4 or more", lambda k: k >= 4)):
        rs = [r for r in sev if g(len(r["files"]))]
        nfs = sum(len(r["files"]) for r in rs)
        P(f"   {lab:<10} runs {len(rs):>3}; files READ {fmt(sum(len(set(r['files']) & r['read']) for r in rs), nfs)}; "
          f"runs that READ every file {fmt(sum(set(r['files']) <= r['read'] for r in rs), len(rs))}; "
          f"shown every region {fmt(sum(all(r['shown']) for r in rs), len(rs))}")

    P("E. fixes IN ONE FILE (any number of regions)")
    one = [r for r in runs if len(r["files"]) == 1]
    P(f"   tasks {len({r['task'] for r in one})}; runs {len(one)}; "
      f"runs that READ the file {fmt(sum(r['files'][0] in r['read'] for r in one), len(one))}; "
      f"shown every region {fmt(sum(all(r['shown']) for r in one), len(one))}")
    return L


def main():
    tasks = load_tasks()
    src = R.discover()
    regions_of = {}
    lines = ["INDEPENDENT RECOUNT (EXPLORATORY): regions of a fix shown to a run, by file, against independence",
             "=" * 100]
    left = collections.Counter()
    for label, key in SETS:
        runs = []
        for p in src[key]:
            tid = Path(p).stem[len("trace_"):]
            if tid not in tasks:
                tid = tid.replace("__", "/")
            if tid not in regions_of:
                regions_of[tid] = R.changed_regions(tasks[tid]["patch"], collections.Counter())
            if not regions_of[tid]:
                left[key] += 1
                continue
            runs.append(run_record(p, tasks[tid], regions_of[tid]))
        lines.extend(report(label, runs))
    lines.append("")
    lines.append("Runs left out (task without a CHANGED REGION): "
                 + "; ".join(f"{k} {left[k]}" for _, k in SETS))
    text = "\n".join(lines) + "\n"
    print(text, end="")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
