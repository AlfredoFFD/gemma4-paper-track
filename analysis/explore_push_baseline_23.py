#!/usr/bin/env python3
"""EXPLORATORY baseline for the uptake and A1 numbers of pre-registration 23, written after its results were seen.

How often does a run that received NO pushed list READ the file of a would-be entry within three calls, and how often
does its first READ of such a file start past line 1? The control is the stored N run of pre-registration 14 (another
launch, seed 1), with the push of analysis/modal_h/push_23.py replayed offline on its reads (the method of
analysis/explore_push_23.py). Its lists were seen by no agent.

Usage: py -I -X utf8 analysis/explore_push_baseline_23.py   (no arguments; prints the report)
Stored output: analysis/results/explore_push_baseline_23.txt is exactly this script's stdout (LF line ends).

Reused by import: rederive_23.load_dir (READs, pushed lists, A1 READs, uptake of the real arms), rederive_23.boot
(bootstrap), rederive_18.load_calls_paired, push_23 (Pusher, neighbor_sets, shown_range, norm), explore_push_23
.first_start (the START of the offline count). The A1 and uptake rules are re-stated here as functions (load_dir has
them inline) and checked to give load_dir's own results on every real run before they are applied to the control.
Standard library only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "modal_h"))
import rederive_14 as r14  # noqa: E402
import rederive_18 as r18  # noqa: E402
import rederive_23 as R  # noqa: E402
import push_23 as P  # noqa: E402
import explore_push_23 as E  # noqa: E402

CTL = R.CONTROL
SPANS = os.path.join(ROOT, "data", "cache", "fresh_spans")
GRAPHS = os.path.join(ROOT, "data", "graphs")
UP = R.UPTAKE_CALLS
SEARCH_CMD = re.compile(r"(^|[\s|;&(`])(grep|egrep|fgrep|rg|git\s+grep)(\s|$)")
SEARCH_TOOLS = ("search_similar_code",)


def wrap(text, first="", rest="  "):
    return R.wrap(text, first, rest)


def pct(a, b):
    return "%d/%d (%.1f%%)" % (a, b, 100.0 * a / b) if b else "%d/0" % a


# ------------------------------------------------------------------ the two rules as functions (as load_dir has them)

def a1_of(reads, pushes):
    listed_at = {}
    for push in pushes:
        for entry in push["entries"]:
            if entry["file"]:
                listed_at.setdefault(entry["file"], push["idx"])
    first_read = {}
    for read in reads:
        first_read.setdefault(read["file"], read)
    out = [first_read[f] for f, i in listed_at.items() if f in first_read and first_read[f]["idx"] > i]
    out.sort(key=lambda r: r["idx"])
    return out


def uptake_of(reads, pushes):
    out = []
    for push in pushes:
        for entry in push["entries"]:
            hit = None
            for read in reads:
                if push["idx"] < read["idx"] <= push["idx"] + UP and read["file"] == entry["file"]:
                    hit = read
                    break
            rng = entry["range"]
            out.append({"other_file": entry["file"] != push["file"], "taken": hit is not None,
                        "inside": (hit is not None and rng is not None and hit["start"] is not None
                                   and rng[0] <= hit["start"] <= rng[1])})
    return out


def past1(read):
    return read["start"] is not None and read["start"] > 1


# ------------------------------------------------------------------ the offline replay on the control

def replay(task, meta, trace_path):
    """(would-be pushes in load_dir's shape, explore_push_23's own A1 count (reads, past line 1), calls)."""
    t = meta[task]
    key = "%s_%s" % (t["repo"].split("/")[1], t["base_commit"])
    with open(os.path.join(GRAPHS, key + ".json"), encoding="utf-8") as h:
        graph = json.load(h)
    with open(os.path.join(SPANS, task + ".json"), encoding="utf-8") as h:
        spans = json.load(h)
    pusher = P.Pusher(P.neighbor_sets(graph), spans)
    calls, _m, _u, _x = r18.load_calls_paired(trace_path)
    pushes = []
    pushed_file_at, opened_at, start_of = {}, {}, {}
    for i, (name, args, result) in enumerate(calls, 1):
        if name != "read_file":
            continue
        rng = P.shown_range(result)
        if rng is None:
            continue
        raw = result.get("filepath") or args.get("filepath")
        f = P.norm(raw)
        if f not in opened_at:
            opened_at[f] = i
            start_of[f] = E.first_start(args, result)
        value = pusher.on_read(raw, *rng)
        if not value:
            continue
        entries = []
        for v in value:
            for n in v["neighbors"]:
                pushed_file_at.setdefault(P.norm(n["file"]), i)
                entries.append({"name": n["name"], "file": r14.norm_path(str(n["file"] or "")),
                                "range": R.parse_range(n["lines"])})
        path = result.get("filepath")
        if not isinstance(path, str):
            path = args.get("filepath")
        pushes.append({"idx": i, "file": r14.norm_path(path) if isinstance(path, str) else "", "entries": entries})
    q = [start_of[f] for f, ip in pushed_file_at.items() if f in opened_at and opened_at[f] > ip]
    return pushes, (len(q), sum(s is not None and s > 1 for s in q)), calls


# ------------------------------------------------------------------ part 3 helper

def searched_before(calls, read, window=UP):
    """True if one of the `window` calls before the READ is a search whose output names the READ's file."""
    f = read["file"]
    if not f:
        return False
    for j in range(max(1, read["idx"] - window), read["idx"]):
        name, args, result = calls[j - 1]
        if name == "run_command":
            if not SEARCH_CMD.search(str(args.get("command") or "")):
                continue
            text = str(result.get("stdout") or "") + "\n" + str(result.get("stderr") or "")
        elif name in SEARCH_TOOLS:
            text = json.dumps(result, ensure_ascii=False)
        else:
            continue
        if f in text:
            return True
    return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    with open(R.TASK_LIST, encoding="utf-8") as h:
        run_list = [line.strip() for line in h if line.strip()]
    meta = {}
    for row in r14.read_jsonl(os.path.join(ROOT, "data", "tasks.jsonl")):
        meta[row["instance_id"]] = row
    gold = {t: r14.changed_regions(meta[t]["patch"])[0] for t in run_list}
    checks = []
    data = {lab: R.load_dir(R.DEFAULTS[lab], lab, run_list, gold, checks) for lab in R.ARMS + (CTL,)}
    entered = {lab: [t for t in run_list if t in data[lab] and data[lab][t]["infra"] is None] for lab in data}

    # the control as if pushed
    calls_of = {}
    exp_a1 = {}
    for t in run_list:
        if t not in data[CTL]:
            continue
        pushes, exp_a1[t], calls_of[t] = replay(t, meta, os.path.join(R.DEFAULTS[CTL], "traces", "trace_%s.json" % t))
        run = data[CTL][t]
        run["pushes"] = pushes
        run["a1"] = a1_of(run["reads"], pushes)
        run["uptake"] = uptake_of(run["reads"], pushes)
    for lab in R.ARMS:
        for t in data[lab]:
            path = os.path.join(R.DEFAULTS[lab], "traces", "trace_%s.json" % t)
            calls_of[(lab, t)] = r18.load_calls_paired(path)[0] if os.path.exists(path) else []

    out = []
    add = out.append
    add("EXPLORATORY: A BASELINE FOR THE UPTAKE AND A1 NUMBERS OF PRE-REGISTRATION 23")
    add(wrap("EXPLORATORY. Written after the results of 23 were seen; nothing here was registered. The control is the"
             " stored N run of pre-registration 14: another launch and another seed (seed 1; PE and PH ran seed 2). Its"
             " pushed lists are replayed offline (analysis/modal_h/push_23.py on the reads that run made) and were seen"
             " by no agent. A real push changes what a run does next, so the would-be lists of the control are not the"
             " lists of PE or PH: the control's reads, and so its would-be lists, come from a run that never had a list"
             " to follow."))
    add("")

    # ---------------------------------------------------------------- part 0
    add("PART 0. REPRODUCTION GATE (nothing tuned; a number that does not reproduce is printed with its difference)")
    selfcheck = 0
    for lab in R.ARMS:
        for t in data[lab]:
            run = data[lab][t]
            if a1_of(run["reads"], run["pushes"]) != run["a1"] or uptake_of(run["reads"], run["pushes"]) != [
                    {k: u[k] for k in ("other_file", "taken", "inside")} for u in run["uptake"]]:
                selfcheck += 1
    add(wrap("Self-check: the A1 and uptake functions of this script against rederive_23.load_dir on every real run of"
             " PE and PH: %s." % ("identical on every run" if not selfcheck else "DIFFER on %d runs" % selfcheck), "  ",
             "    "))

    def gate(label, got, want):
        word = "reproduced" if got == want else "NOT reproduced: %s, expected %s (difference %+d)" % (
            got, want, got - want)
        add("  %-62s %s" % (label, word))

    def arm_counts(lab, tasks):
        runs = [data[lab][t] for t in tasks]
        ups = [u for r in runs for u in r["uptake"]]
        oth = [u for u in ups if u["other_file"]]
        a1 = [x for r in runs for x in r["a1"]]
        return {"lists": sum(len(r["pushes"]) for r in runs), "runs_push": sum(1 for r in runs if r["pushes"]),
                "entries": len(ups), "taken": sum(u["taken"] for u in ups), "other": len(oth),
                "other_taken": sum(u["taken"] for u in oth), "inside": sum(u["inside"] for u in ups),
                "other_inside": sum(u["inside"] for u in oth), "a1": len(a1),
                "a1_runs": sum(1 for r in runs if r["a1"]), "a1_past": sum(1 for x in a1 if past1(x)),
                "runs": len(runs)}

    expected = {"PE": (493, 98, 1892, 450, 1359, 96, 32, 11, 76, 45, 24),
                "PH": (465, 99, 1786, 434, 1267, 90, 24, 6, 74, 49, 18)}
    names = ("pushed lists", "runs with a pushed list", "entries", "entries whose file is READ within 3 calls",
             "entries in another file", "  of which file READ within 3 calls", "READ starts inside range (all entries)",
             "READ starts inside range (another file)", "A1 READs", "runs with an A1 READ", "A1 READs past line 1")
    keys = ("lists", "runs_push", "entries", "taken", "other", "other_taken", "inside", "other_inside", "a1",
            "a1_runs", "a1_past")
    counts = {}
    for lab in R.ARMS:
        counts[lab] = arm_counts(lab, entered[lab])
        add("  %s (real pushes, %d entered runs):" % (lab, counts[lab]["runs"]))
        for nm, k, w in zip(names, keys, expected[lab]):
            gate("  " + nm, counts[lab][k], w)
    ctl_tasks = [t for t in run_list if t in data[CTL]]
    n_ctl = len(ctl_tasks)
    add("  N of 14 as if pushed (the method of explore_push_23.py, %d stored runs):" % n_ctl)
    gate("  would-be pushes", sum(len(data[CTL][t]["pushes"]) for t in ctl_tasks), 485)
    gate("  runs with at least one", sum(1 for t in ctl_tasks if data[CTL][t]["pushes"]), 101)
    gate("  runs in all", n_ctl, 103)
    gate("  A1 READs (explore_push_23's count)", sum(exp_a1[t][0] for t in ctl_tasks), 71)
    gate("  runs with an A1 READ (explore_push_23's count)", sum(1 for t in ctl_tasks if exp_a1[t][0]), 49)
    gate("  A1 READs past line 1 (explore_push_23's count)", sum(exp_a1[t][1] for t in ctl_tasks), 9)
    counts[CTL] = arm_counts(CTL, entered[CTL])
    c = counts[CTL]
    add(wrap("The same control under rederive_23's definitions (READ: status ok; START: the returned start_line when a"
             " start argument is given; entered runs only, %d): A1 READs %d in %d runs, %d past line 1. These are the"
             " numbers Parts 1 and 2 use." % (c["runs"], c["a1"], c["a1_runs"], c["a1_past"]), "  ", "    "))
    add("")

    # ---------------------------------------------------------------- part 1
    add("PART 1. THE BASELINE: UPTAKE ON THE N RUN OF 14 AS IF PUSHED (rederive_23's definitions, entered runs)")
    for lab in (CTL,) + R.ARMS:
        c = counts[lab]
        tag = "N of 14 as if pushed" if lab == CTL else "%s (real pushes)" % lab
        add(wrap("%s, %d runs, %d lists: all entries %d, file READ within %d calls %s, of those starting inside the"
                 " range %s; entries in another file %d, file READ within %d calls %s, of those starting inside the"
                 " range %s; A1 READs %d in %d runs, past line 1 %s."
                 % (tag, c["runs"], c["lists"], c["entries"], UP, pct(c["taken"], c["entries"]),
                    pct(c["inside"], c["taken"]), c["other"], UP, pct(c["other_taken"], c["other"]),
                    pct(c["other_inside"], c["other_taken"]), c["a1"], c["a1_runs"], pct(c["a1_past"], c["a1"])),
                 "  ", "    "))
    add("  Per run, N of 14 as if pushed (runs with at least one entry of that kind):")
    for label, sel in (("all entries", lambda u: True), ("entries in another file", lambda u: u["other_file"])):
        shares = []
        for t in entered[CTL]:
            ups = [u for u in data[CTL][t]["uptake"] if sel(u)]
            if ups:
                shares.append(sum(u["taken"] for u in ups) / len(ups))
        shares.sort()
        add("    %s: %d runs; mean share %.1f%%, median %.1f%%; runs with no entry taken up %d"
            % (label, len(shares), 100 * R.mean(shares), 100 * r18.median(shares), sum(1 for s in shares if s == 0)))
    add("")

    # ---------------------------------------------------------------- part 2
    add(wrap("PART 2. PAIRED BY TASK (per-run shares; 95% bootstrap by task, 2,000 resamples, random.Random(0) afresh"
             " for each comparison, percentiles 2.5 and 97.5; points of share)"))

    def share_up(run, other_only):
        ups = [u for u in run["uptake"] if (u["other_file"] or not other_only)]
        return (sum(u["taken"] for u in ups), len(ups))

    def share_a1(run):
        return (sum(1 for x in run["a1"] if past1(x)), len(run["a1"]))

    outcomes = (("(a) entries in another file: share whose file is READ within 3 calls", lambda r: share_up(r, True)),
                ("(b) all entries: share whose file is READ within 3 calls", lambda r: share_up(r, False)),
                ("(c) A1 READs: share that start past line 1", share_a1))
    pairs = (("PE", CTL), ("PH", CTL), ("PE", "PH"))
    for title, fn in outcomes:
        add("  " + title)
        for a, b in pairs:
            tasks = [t for t in run_list if t in entered[a] and t in entered[b]
                     and fn(data[a][t])[1] > 0 and fn(data[b][t])[1] > 0]
            sa = [fn(data[a][t]) for t in tasks]
            sb = [fn(data[b][t]) for t in tasks]
            ma = [x / n for x, n in sa]
            mb = [x / n for x, n in sb]
            diffs = [x - y for x, y in zip(ma, mb)]
            lo, hi = R.boot(diffs, 100.0)
            nb = "N14" if b == CTL else b
            add(wrap("%s minus %s: %d tasks; mean share %s %.1f%%, %s %.1f%%; mean difference %s points [%s, %s];"
                     " pooled on these tasks %s %s, %s %s."
                     % (a, nb, len(tasks), a, 100 * R.mean(ma), nb, 100 * R.mean(mb), R.signed(100 * R.mean(diffs)),
                        R.signed(lo), R.signed(hi), a, pct(sum(x for x, _ in sa), sum(n for _, n in sa)), nb,
                        pct(sum(x for x, _ in sb), sum(n for _, n in sb))), "    ", "      "))
    add("")

    # ---------------------------------------------------------------- part 3
    add("PART 3. A1 READs THAT START PAST LINE 1: inside a pushed range? after a search naming the file?")
    for lab in R.ARMS + (CTL,):
        n = inside = searched = both_ = 0
        for t in entered[lab]:
            run = data[lab][t]
            calls = calls_of[t] if lab == CTL else calls_of[(lab, t)]
            for x in run["a1"]:
                if not past1(x):
                    continue
                n += 1
                rngs = [e["range"] for p in run["pushes"] if p["idx"] < x["idx"] for e in p["entries"]
                        if e["file"] == x["file"] and e["range"] is not None]
                ins = any(lo <= x["start"] <= hi for lo, hi in rngs)
                sea = searched_before(calls, x)
                inside += ins
                searched += sea
                both_ += ins and sea
        tag = {"PE": "PE (ranges the agent saw)", "PH": "PH (ranges in the runner record, not seen by the agent)",
               CTL: "N14 as if pushed (would-be ranges)"}[lab]
        add(wrap("%s: A1 READs past line 1 %d; START inside the range of an entry of that file listed by a push"
                 " before the READ %d; made within %d calls after a search whose output names the file %d; both %d;"
                 " neither %d." % (tag, n, inside, UP, searched, both_, n - inside - searched + both_), "  ", "    "))
    add(wrap("A search result: a run_command call whose command contains grep, egrep, fgrep, rg or git grep as a word"
             " (piped or chained commands included), or a search_similar_code call, made at one of the %d call indexes"
             " before the READ; its output names the file when the READ's FILE (path without a leading /workspace/,"
             " workspace/ or ./) is a substring of the command's stdout or stderr (of the tool's result as JSON for"
             " search_similar_code). find, ls, cat, sed and other commands are not counted as searches." % UP, "  ",
             "    "))
    add("")

    add("NOTES")
    for i, text in enumerate([
        "Entered runs and READ, START, A1 READ and uptake are rederive_23's (its section 9). For the control the would-be"
        " lists are put in place of its (empty) pushed lists, and A1 and uptake are computed on them with the same rules.",
        "The offline replay calls the Pusher on every read_file answer whose returned range is readable"
        " (push_23.shown_range), as explore_push_23.py and the runner do; rederive_23's READs are every read_file of"
        " status ok. Part 0's control A1 numbers are explore_push_23's count (its own START and file-opening rule);"
        " Parts 1 and 2 use rederive_23's.",
        "Per-run shares are taken over a run's entries (or A1 READs); a run with none has no share and its task drops out"
        " of that comparison. The pooled counts are on the same tasks as the paired means.",
    ], 1):
        add(wrap(text, "%2d. " % i, "    "))
    if checks:
        add("Checks of rederive_23.load_dir on the stored runs: %d lines (printed in analysis/results/rederive_23.txt)."
            % len(checks))
    sys.stdout.write(("\n".join(out) + "\n").replace("\xa0", " "))


if __name__ == "__main__":
    main()
