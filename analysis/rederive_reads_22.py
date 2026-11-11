"""Independent recount (EXPLORATORY): what the arms of experiment 22 (or 18) read, and where a run's first read of a
file of the note starts. Written blind from a brief, without the project's own scripts or outputs for these counts.
It reuses, by import, the trace pairing of analysis/rederive_cost_18.py (class Run18), the read parsing, CHANGED REGION
rule and result loader of analysis/rederive_read_starts.py, and the percentile of analysis/rederive_18.py.

Usage: py -I -X utf8 analysis/rederive_reads_22.py [--experiment 22|18] [--no-write]
Experiment 22 (default) prints the report and stores the same text in analysis/results/rederive_reads_22.txt (LF line
endings); --no-write prints only. Experiment 18 prints only.

Inputs
- Runs: analysis/results/22/<N|ON|OF|OA>/seed3 (experiment 22) or analysis/results/18/<N|ON|OA>/seed2 (experiment 18).
  A RUN is (task, arm) for a task of analysis/oracle_18/tasks_18.txt that has a line in the arm's task_results.jsonl
  (the last line of a task counts) and a stored trace.
- Notes: data/cache/oracle_22/<task>.json (keys ON, OF, OA: the note texts) and data/cache/oracle_18/<task>.json (ON,
  OA). The traces store the first user message only as a hash, so the note a run was given is checked by comparing the
  md5 of the cached note text with the note_md5 of the run's runner record (extra.jsonl).
- Reference patches: data/tasks.jsonl.

Definitions
- Tool calls and results: every tool call is paired with its own result; a step that holds several calls stores the
  first result in that step and the others in the following call-less steps, in order (Run18 of rederive_cost_18).
- READ: a read_file call whose paired result is a JSON object with status "ok". Its FILE is the filepath argument with
  a leading "/workspace/", "workspace/" or "./" removed. Its START is: none if the call gives no start_line argument
  (mangled argument names repaired as in rederive_read_starts.asked); otherwise the start_line the result returned
  (the asked start if the result returned none). Its LINES are the returned start_line..end_line. A call whose
  start_line argument name is mangled (e.g. 'start_line"') is answered by the harness from line 1, so its START is 1
  (TOP); the checks count these. The returned content is cut at 10,000 characters, so a few reads return fewer lines
  than their range; LINES READ uses the range and the checks count the shortfall.
- READS per run: the number of READs. LINES READ per run: the sum over READs of (returned end_line - start_line + 1);
  a READ without a numeric returned range adds 0 lines (counted in the checks). Printed for all READs and, as a second
  line, without READs of an OWN FILE (a file the run had written earlier with an ok write_file call; the rule of
  rederive_cost_18, for comparison with its output). Mean and median per run; the median of an even count is the mean
  of the two middle values.
- B: for each pair of arms, over the tasks with a run in both, the per-task difference (first arm minus second) in
  LINES READ and in READS; mean, and a 95% bootstrap interval: tasks resampled with replacement (randrange over the
  tasks in run-list order), 2,000 resamples, random.Random(0) started afresh for each difference, percentile interval
  with linear interpolation (rederive_18.percentile).
- NOTE FILES and RANGES: a note entry "- <file>, lines a-b (...)" gives the file and the range a..b; "- <file> (...)"
  (OF entries for a whole module) gives the file and no range. ON entries are dotted names and give no file. The NOTE
  FILES of a run: the files of the OF note for arm OF, of the OA note for arm OA, and of the OA note of the same task
  for arms N and ON (N has no note; ON names the same places without files). In experiment 18, which had no OF arm,
  the OF ranges of a task are taken from data/cache/oracle_22 (the OA notes of 18 and 22 are checked to be equal).
- C. FIRST READ of a NOTE FILE: the run's first READ of that file (one per run and file that has a READ). Classes:
  TOP if it gives no START or its START is <= 1; AT THE NOTE (k) if not TOP and its START lies in a range of the told
  note for that file (OF note for arm OF, OA note for arm OA) widened by k lines on each side, k = 0, 5, 20; OTHER (k)
  otherwise. N and ON: TOP and OTHER only. For every arm, the not-TOP first reads whose START lies inside the OF ranges
  and inside the OA ranges of the same task and file (k = 0, 5, 20) are counted too: for N and ON this is the rate at
  which a run lands there without being told. RUNS CONTRIBUTING: runs with at least one FIRST READ of a NOTE FILE.
- D. For arms OF and OA: every READ of a NOTE FILE whose START is > 1; how many START inside a range of the arm's own
  note (k = 0, 5, 20). N and ON against the OA and OF ranges are printed for comparison.
- E (a check against analysis/results/rederive_22.txt, whose rules differ; see the report). CHANGED REGION: per hunk
  of the reference patch, in a file the patch does not create, the old-file lines from the first to the last removed
  line, a pure insertion counting the two old lines around it (rederive_read_starts.changed_regions). SHOWN EVERY
  REGION: every CHANGED REGION is overlapped by the returned range of some READ of its file (read_file only, own-file
  reads included). PATCH OVERLAPS: a region of the stored final patch (patches/<task>.patch, same rule, old side)
  overlaps a CHANGED REGION of the same file. RESOLVED: the resolved field of the task_results line.
"""
import collections
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import rederive_read_starts as R  # noqa: E402
import rederive_cost_18 as C18  # noqa: E402
import rederive_18 as R18  # noqa: E402

OUT = HERE / "results" / "rederive_reads_22.txt"
KS = (0, 5, 20)
BOOT_RESAMPLES = 2000
BOOT_SEED = 0
CONFIG = {
    "22": dict(base=HERE / "results" / "22", seed="seed3", arms=["N", "ON", "OF", "OA"], notes="oracle_22"),
    "18": dict(base=HERE / "results" / "18", seed="seed2", arms=["N", "ON", "OA"], notes="oracle_18"),
}
ENTRY_LINES = re.compile(r"^- (\S+), lines (\d+)-(\d+) \(.*\)$")
ENTRY_FILE = re.compile(r"^- (\S+) \(.*\)$")
ENTRY_NAME = re.compile(r"^- [\w.]+$")
chk = collections.Counter()


def fmt(k, n):
    return R.fmt(k, n)


def mean(xs):
    return f"{sum(xs) / len(xs):.2f}" if xs else "n/a"


def median(xs):
    if not xs:
        return "n/a"
    s = sorted(xs)
    n = len(s)
    m = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return f"{m:g}"


def parse_note(text):
    """{file: [(a, b), ...]} in note order; a file named without lines maps to an empty list."""
    out = collections.OrderedDict()
    for line in text.split("\n")[1:]:
        m = ENTRY_LINES.match(line)
        if m:
            a, b = int(m.group(2)), int(m.group(3))
            if a > b:
                chk["note range with first > last (swapped)"] += 1
                a, b = b, a
            out.setdefault(R.norm_file(m.group(1)), []).append((a, b))
            continue
        m = ENTRY_FILE.match(line)
        if m:
            out.setdefault(R.norm_file(m.group(1)), [])
            continue
        if ENTRY_NAME.match(line):
            continue
        chk["note line of no known form"] += 1
    return out


def inside(x, ranges, k):
    return any(a - k <= x <= b + k for a, b in ranges)


def boot(diffs):
    n = len(diffs)
    if not n:
        return float("nan"), float("nan")
    rng = random.Random(BOOT_SEED)
    means = []
    for _ in range(BOOT_RESAMPLES):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return R18.percentile(means, 0.025), R18.percentile(means, 0.975)


def load_run(trace_path, arm, task):
    run = C18.Run18(str(trace_path), task.get("problem_statement") or "")
    # extra pairing check: a call-less step that carries a result should be a 'system' step
    d = json.load(open(trace_path, encoding="utf-8"))
    for s in d.get("steps", []):
        if not (s.get("tool_calls") or []) and s.get("observation") is not None and s.get("source") != "system":
            chk[f"call-less step with a result whose source is not 'system' ({arm})"] += 1
    written = {}
    reads = []
    n_read_calls = 0
    for c in run.calls:
        res = c["result"]
        if c["fname"] == "write_file":
            fp = R.norm_file(c["args"].get("filepath"))
            if fp and isinstance(res, dict) and res.get("status") == "ok":
                written.setdefault(fp, c["idx"])
            continue
        if c["fname"] != "read_file":
            continue
        n_read_calls += 1
        if not (isinstance(res, dict) and res.get("status") == "ok"):
            continue
        fp = R.norm_file(c["args"].get("filepath")) or ""
        rfp = R.norm_file(res.get("filepath"))
        if rfp is not None and rfp != fp:
            chk[f"read result names another file than its call ({arm})"] += 1
        s_asked, _e = R.asked(c["args"])
        rs, re_ = res.get("start_line"), res.get("end_line")
        if not (R.isnum(rs) and R.isnum(re_)):
            chk[f"ok read without a numeric returned range ({arm})"] += 1
            rs = re_ = None
        if s_asked is None:
            start = None
        else:
            start = rs if rs is not None else s_asked
            if rs is not None and rs != s_asked:
                mangled = any(R.clean_key(k) != k for k in c["args"])
                chk[f"asked start differs from returned start ({arm}; "
                    f"{'mangled argument name' if mangled else 'clean argument name'}; returned start {rs})"] += 1
        nlines = (re_ - rs + 1) if rs is not None and re_ >= rs else 0
        content = res.get("content")
        if isinstance(content, str) and rs is not None:
            cl = len(content.split("\n"))  # lines joined by newlines: an empty last line leaves a trailing newline
            if cl != nlines:
                chk[f"reads whose content holds {'fewer' if cl < nlines else 'more'} lines than the returned range "
                    f"({arm})"] += 1
                chk[f"lines by which those contents fall short of the range, summed ({arm})"] += nlines - cl
        reads.append(dict(idx=c["idx"], file=fp, start=start, rstart=rs, rend=re_, lines=nlines,
                          own=fp in written and written[fp] < c["idx"]))
    return run, reads, n_read_calls


def main(argv):
    exp = "22"
    args = argv[1:]
    write = "--no-write" not in args
    if "--experiment" in args:
        i = args.index("--experiment")
        exp = args[i + 1] if i + 1 < len(args) else ""
    if exp not in CONFIG:
        sys.stderr.write("usage: rederive_reads_22.py [--experiment 22|18] [--no-write]\n")
        return 2
    cfg = CONFIG[exp]
    arms = cfg["arms"]
    tasks = {}
    for line in (ROOT / "data" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["instance_id"]] = t
    tlist = [x.strip() for x in (HERE / "oracle_18" / "tasks_18.txt").read_text(encoding="utf-8").splitlines()
             if x.strip()]

    notes = {}
    for tid in tlist:
        raw = json.load(open(ROOT / "data" / "cache" / cfg["notes"] / f"{tid}.json", encoding="utf-8"))
        raw22 = json.load(open(ROOT / "data" / "cache" / "oracle_22" / f"{tid}.json", encoding="utf-8"))
        if raw22.get("OA") != raw.get("OA"):
            chk["OA note differs between oracle_18 and oracle_22"] += 1
        oa = parse_note(raw["OA"])
        of = parse_note(raw22["OF"])
        parse_note(raw["ON"])
        if set(of) != set(oa):
            chk["files of the OF note differ from the files of the OA note"] += 1
        notes[tid] = dict(raw=raw, OA=oa, OF=of)

    recs = {}
    harness = collections.defaultdict(collections.Counter)
    for arm in arms:
        sd = cfg["base"] / arm / cfg["seed"]
        results = R.ours_results(str(sd))
        extra = {}
        ep = sd / "extra.jsonl"
        if ep.exists():
            for line in ep.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    extra[r.get("task")] = r
        for tid in tlist:
            if tid not in results:
                continue
            tp = sd / "traces" / f"trace_{tid}.json"
            if not tp.exists():
                chk[f"result line without a trace ({arm})"] += 1
                continue
            task = tasks[tid]
            run, reads, n_read_calls = load_run(tp, arm, task)
            ex = extra.get(tid)
            if ex is None:
                chk[f"no runner record ({arm})"] += 1
            else:
                harness[arm][str(ex.get("harness"))] += 1
                if (ex.get("arm") or ex.get("condition")) != arm:
                    chk[f"runner record names another arm ({arm})"] += 1
                if arm == "N":
                    if ex.get("note_in_first_message") not in (0, None):
                        chk["N run with a note in its first message"] += 1
                else:
                    md5 = hashlib.md5(notes[tid]["raw"][arm].encode("utf-8")).hexdigest()
                    if ex.get("note_md5") != md5:
                        chk[f"runner note_md5 differs from the cached note ({arm})"] += 1
                    if ex.get("note_in_first_message") != 1:
                        chk[f"note not in the first message ({arm})"] += 1
                tr = ex.get("trace") or {}
                if R.isnum(tr.get("calls_read_file")) and tr["calls_read_file"] != n_read_calls:
                    chk[f"runner count of read_file calls differs from the trace ({arm})"] += 1
                if R.isnum(tr.get("calls")) and tr["calls"] != len(run.calls):
                    chk[f"runner count of tool calls differs from the trace ({arm})"] += 1
            # C: first reads of note files
            told = "OF" if arm == "OF" else "OA"
            nfiles = list(notes[tid][told]) if arm in ("OF", "OA") else list(notes[tid]["OA"])
            first = {}
            for r in reads:
                if r["file"] in nfiles and r["file"] not in first:
                    first[r["file"]] = r
                    if r["own"]:
                        chk[f"first read of a note file is of an OWN FILE ({arm})"] += 1
            # E
            regs = R.changed_regions(task["patch"], collections.Counter())
            shown = [any(r["file"] == f and r["rstart"] is not None and R.overlaps(a, b, r["rstart"], r["rend"])
                         for r in reads) for f, a, b in regs]
            pf = sd / "patches" / f"{tid}.patch"
            patch = pf.read_text(encoding="utf-8", errors="replace") if pf.exists() else ""
            fpr = R.changed_regions(patch, collections.Counter())
            overlap = any(ff == f and R.overlaps(a, b, fa, fb) for f, a, b in regs for ff, fa, fb in fpr)
            recs[(tid, arm)] = dict(
                reads=len(reads), lines=sum(r["lines"] for r in reads),
                reads_no=sum(1 for r in reads if not r["own"]), lines_no=sum(r["lines"] for r in reads if not r["own"]),
                own=sum(1 for r in reads if r["own"]), first=first, all_reads=[r for r in reads if r["file"] in nfiles],
                every=bool(regs) and all(shown), has_regs=bool(regs), overlap=overlap,
                resolved=R.is_true(results[tid].get("resolved")))

    L = []
    P = L.append
    P(f"INDEPENDENT RECOUNT (EXPLORATORY): what the arms of experiment {exp} read ({cfg['seed']}; arms "
      f"{', '.join(arms)})")
    P("=" * 100)
    runs_by_arm = {a: [t for t in tlist if (t, a) in recs] for a in arms}
    P("runs: " + "; ".join(f"{a} {len(runs_by_arm[a])}" for a in arms))
    common = [t for t in tlist if all((t, a) in recs for a in arms)]
    P(f"tasks with a run in every arm: {len(common)}")

    P("")
    P("A. READS and LINES READ per run (all READs; second line without READs of an OWN FILE)")
    for a in arms:
        rs = [recs[(t, a)] for t in runs_by_arm[a]]
        P(f"   {a:<3} runs {len(rs):>2}: READS mean {mean([r['reads'] for r in rs])}, median {median([r['reads'] for r in rs])}; "
          f"LINES READ mean {mean([r['lines'] for r in rs])}, median {median([r['lines'] for r in rs])}")
        P(f"       without OWN FILE (OWN-FILE READS {sum(r['own'] for r in rs)}): READS mean "
          f"{mean([r['reads_no'] for r in rs])}, median {median([r['reads_no'] for r in rs])}; LINES READ mean "
          f"{mean([r['lines_no'] for r in rs])}, median {median([r['lines_no'] for r in rs])}")

    P("")
    P("B. Paired by task, first arm minus second: mean difference [95% bootstrap interval over tasks, 2,000 resamples, "
      "seed 0]")
    pairs = [(x, y) for i, x in enumerate(arms) for y in arms[:i]]
    for x, y in pairs:
        ts = [t for t in tlist if (t, x) in recs and (t, y) in recs]
        parts = []
        for key, lab in (("lines", "LINES READ"), ("reads", "READS")):
            d = [recs[(t, x)][key] - recs[(t, y)][key] for t in ts]
            lo, hi = boot(d)
            parts.append(f"{lab} {mean(d)} [{lo:.2f}, {hi:.2f}]")
        P(f"   {x} minus {y} (tasks {len(ts)}): " + "; ".join(parts))

    P("")
    P("C. FIRST READ of each NOTE FILE (one per run and file read). AT THE NOTE (k): START inside a told range widened by "
      "k; N and ON have no told range.")
    if exp == "18":
        P("   (experiment 18 had no OF arm: the OF ranges are those of the OF notes of experiment 22 for the same task)")
    for a in arms:
        frs = [(t, f, r) for t in runs_by_arm[a] for f, r in recs[(t, a)]["first"].items()]
        n = len(frs)
        contrib = sum(1 for t in runs_by_arm[a] if recs[(t, a)]["first"])
        nfiles_total = sum(len(notes[t]["OF" if a == "OF" else "OA"]) for t in runs_by_arm[a])
        top = [x for x in frs if x[2]["start"] is None or x[2]["start"] <= 1]
        nt = [x for x in frs if not (x[2]["start"] is None or x[2]["start"] <= 1)]
        P(f"   {a:<3} runs contributing {contrib}/{len(runs_by_arm[a])}; note files over its runs {nfiles_total}, of them "
          f"with a READ (= FIRST READS) {n}; TOP {fmt(len(top), n)} (no start {sum(x[2]['start'] is None for x in top)});"
          f" not TOP {fmt(len(nt), n)}")
        if a in ("OF", "OA"):
            noR = sum(1 for t, f, r in nt if not notes[t][a][f])
            parts = []
            for k in KS:
                at = sum(1 for t, f, r in nt if inside(r["start"], notes[t][a][f], k))
                parts.append(f"k={k}: AT THE NOTE {fmt(at, n)}, OTHER {fmt(len(nt) - at, n)}")
            P("       " + "; ".join(parts))
            if noR:
                P(f"       (of the not-TOP first reads, {noR} are of a file whose {a} note gives no range: always OTHER)")
        else:
            P(f"       OTHER {fmt(len(nt), n)}")
        for src in ("OF", "OA"):
            parts = []
            for k in KS:
                hit = sum(1 for t, f, r in nt if inside(r["start"], notes[t][src].get(f, []), k))
                parts.append(f"k={k} {fmt(hit, n)}")
            P(f"       not-TOP first reads starting inside the {src} ranges of the task (share of all first reads): "
              + "; ".join(parts))

    P("")
    P("D. Every READ of a NOTE FILE with START > 1: how many START inside a range of the arm's own note "
      "(N and ON against the OA and OF ranges, for comparison)")
    for a in arms:
        rs = [(t, r) for t in runs_by_arm[a] for r in recs[(t, a)]["all_reads"] if r["start"] is not None and r["start"] > 1]
        srcs = [a] if a in ("OF", "OA") else ["OA", "OF"]
        for src in srcs:
            parts = [f"k={k} {fmt(sum(1 for t, r in rs if inside(r['start'], notes[t][src].get(r['file'], []), k)), len(rs))}"
                     for k in KS]
            lab = "own note" if src == a else f"{src} ranges"
            P(f"   {a:<3} reads past line 1: {len(rs)}; inside the {lab}: " + "; ".join(parts))

    P("")
    P("E. Check (rules differ from rederive_22.txt: read_file only, the CHANGED REGION rule of rederive_read_starts)")
    for a in arms:
        rs = [recs[(t, a)] for t in runs_by_arm[a]]
        P(f"   {a:<3} runs {len(rs)}: SHOWN EVERY REGION {fmt(sum(r['every'] for r in rs), len(rs))} "
          f"(tasks without a CHANGED REGION {sum(not r['has_regs'] for r in rs)}); PATCH OVERLAPS "
          f"{fmt(sum(r['overlap'] for r in rs), len(rs))}; RESOLVED {fmt(sum(r['resolved'] for r in rs), len(rs))}")

    P("")
    P("Harness of the runs (runner records): " + "; ".join(
        f"{a}: " + ", ".join(f"{h} ({n})" for h, n in sorted(harness[a].items())) for a in arms))
    allchk = collections.Counter(chk)
    allchk.update({f"pairing: {k}": v for k, v in C18.dg.items()})
    P("Checks: " + ("; ".join(f"{k}: {v}" for k, v in sorted(allchk.items())) or "none"))
    text = "\n".join(L) + "\n"
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(text)
    if write and exp == "22":
        with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
