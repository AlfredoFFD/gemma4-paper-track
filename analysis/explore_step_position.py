#!/usr/bin/env python3
"""EXPLORATORY, written after the results of pre-registration 23 were seen; the split was not registered.

Does the one-call effect of experiment B (pre-registration 03: the next call reads or edits lines of a listed true
neighbor in a file not opened before) depend on how far into its run the paused step is? Splits the 388 complete
paused steps by call index, by files opened so far, and by first versus later paused step of a run, and sets the
pushed lists of the whole runs of 23 beside them by the call index of the READ that carried the list.

Usage: py -I -X utf8 analysis/explore_step_position.py   (no arguments; prints the report)
Stored output: analysis/results/explore_step_position.txt is exactly this script's stdout (LF line ends).

Replays: the scorer, exclusions, completeness rule and bootstrap of analysis/analyze_b.py (run v5 + B (v6) +
rewired (v8); analyze_forks.boot_ci / diff_ci, 2,000 resamples, seed 0), re-stated here because analyze_b only has
a main. Whole runs: the functions of analysis/explore_next_call_23.py, imported.
"""
import collections
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "modal_h"))
import nodes as N  # noqa: E402
from analyze_forks import KNOWN_TOOLS, boot_ci, diff_ci  # noqa: E402
from fork_states import touches, valid_call, shows_content, norm_path  # noqa: E402
import explore_next_call_23 as X  # noqa: E402

ARMS_ALL = ['A', 'P', 'Pp', 'H', 'Hp', 'D', 'Dp', 'E', 'RD', 'RE']
OUT = []


def add(s=""):
    OUT.append(s)


def fmt(trip, pts=False):
    p, lo, hi = trip
    if p is None:
        return "n/a"
    if pts:
        return "%+.2f [%+.2f, %+.2f]" % (100 * p, 100 * lo, 100 * hi)
    return "%.2f%% [%.2f, %.2f]" % (100 * p, 100 * lo, 100 * hi)


def quart(vals):
    q = st.quantiles(vals, n=4, method="inclusive")
    return "min %s, Q1 %s, median %s, Q3 %s, max %s (n %d)" % (
        min(vals), ("%g" % q[0]), ("%g" % q[1]), ("%g" % q[2]), max(vals), len(vals))


def counts(vals):
    c = collections.Counter(vals)
    return ", ".join("%s: %d" % (k, c[k]) for k in sorted(c))


def thirds(vals):
    """Cut points t1, t2: the smallest values with at least 1/3 and 2/3 of the steps at or below them."""
    s = sorted(vals)
    n = len(s)
    t1 = next(v for v in s if sum(1 for x in s if x <= v) >= n / 3)
    t2 = next(v for v in s if sum(1 for x in s if x <= v) >= 2 * n / 3)
    return t1, t2


# ---------------------------------------------------------------- replays
def load_replays():
    states = {}
    for line in open(os.path.join(HERE, "fork_states", "states.jsonl"), encoding="utf-8"):
        s = json.loads(line)
        states[(s["task"], s["run"], s.get("fork", 0))] = s
    rows = []
    for v in ("v5", "v6", "v8"):
        rows += [json.loads(l) for l in open(os.path.join(HERE, "results", v, "forks", "results.jsonl"),
                                             encoding="utf-8")]
    ok = []
    for r in rows:
        call = r.get("next_call")
        if r.get("error") or not call or call["function_name"] not in KNOWN_TOOLS or not valid_call(call):
            continue
        ok.append(r)
    by_state = collections.defaultdict(dict)
    for r in ok:
        by_state[(r["task"], r["run"], r.get("fork", 0))][(r["arm"], r["seed"])] = r
    seeds = sorted({r["seed"] for r in ok})
    arms = sorted({r["arm"] for r in ok}, key=ARMS_ALL.index)
    complete = {k: v for k, v in by_state.items() if len(v) == len(arms) * len(seeds)}
    return states, rows, complete


def score(states, complete):
    """{arm: {step key: [0/1 per seed]}}: any listed true neighbor in an unopened file touched (analyze_b any_true)."""
    any_true = {a: {} for a in ("A", "H", "E")}
    for key, reps in complete.items():
        s = states[key]
        spans = s["neighbor_spans"]
        unshown = set(s.get("unshown_true_neighbors", s["true_neighbors"]))

        def lengths(path):
            src = N.file_text(s["task"], path)
            return [len(x) for x in src.splitlines()] if src else None

        for (arm, seed), r in sorted(reps.items()):
            if arm not in any_true:
                continue
            call = r["next_call"]
            touched = {n: touches(call, spans[n], n, line_lengths=lengths(spans[n]["path"]))
                       for n in s["true_neighbors"] if spans.get(n) and n in unshown}
            hit = [bool(v) and v != "graph" for v in touched.values()]
            any_true[arm].setdefault(key, []).append(int(any(hit)))
    return any_true


def position(s):
    """Call index, distinct files opened, edited or written so far, from the stored paused history."""
    agent = [x for x in s["steps"] if x["source"] == "agent"]
    ci = sum(len(x.get("tool_calls") or []) for x in agent)
    files = set()
    edited = False
    for x in agent:
        sc = shows_content(x)
        if sc and sc[0]:
            files.add(N._norm(sc[0]))
        for tc in x.get("tool_calls") or []:
            if tc["function_name"] in ("edit_file", "write_file"):
                edited = True
    return ci, len(files), edited


def by_task(d):
    out = collections.defaultdict(list)
    for key, vals in d.items():
        out[key[0]].extend(vals)
    return dict(out)


def group_report(name, keys, sc):
    sub = {a: {k: sc[a][k] for k in keys} for a in sc}
    n = len(keys)
    tasks = len({k[0] for k in keys})
    add("  %s: %d steps, %d tasks, %d replays per arm" % (name, n, tasks, sum(len(v) for v in sub["A"].values())))
    add("    rates (95%% bootstrap by step): A %s; H %s; E %s" % (
        fmt(boot_ci(sub["A"])), fmt(boot_ci(sub["H"])), fmt(boot_ci(sub["E"]))))
    add("    E minus H, points: by step %s; by task %s" % (
        fmt(diff_ci(sub["E"], sub["H"]), True), fmt(diff_ci(by_task(sub["E"]), by_task(sub["H"])), True)))
    add("    E minus A, points: by step %s; by task %s" % (
        fmt(diff_ci(sub["E"], sub["A"]), True), fmt(diff_ci(by_task(sub["E"]), by_task(sub["A"])), True)))


# ---------------------------------------------------------------- whole runs
def whole_runs():
    """Per lab, a list of (task, list number in run, call index of the READ, fresh entries, next call meets outcome)."""
    R, B, r14, r18 = X.R, X.B, X.r14, X.r18
    with open(R.TASK_LIST, encoding="utf-8") as h:
        run_list = [line.strip() for line in h if line.strip()]
    meta = {row["instance_id"]: row for row in r14.read_jsonl(os.path.join(X.ROOT, "data", "tasks.jsonl"))}
    gold = {t: r14.changed_regions(meta[t]["patch"])[0] for t in run_list}
    checks = []
    data = {lab: R.load_dir(R.DEFAULTS[lab], lab, run_list, gold, checks) for lab in X.LABS}
    entered = {lab: [t for t in run_list if t in data[lab] and data[lab][t]["infra"] is None] for lab in X.LABS}
    out = {}
    for lab in X.LABS:
        rows = []
        for t in entered[lab]:
            path = os.path.join(R.DEFAULTS[lab], "traces", "trace_%s.json" % t)
            if lab == X.CTL:
                pushes, _a1, calls = B.replay(t, meta, path)
            else:
                pushes = data[lab][t]["pushes"]
                calls = r18.load_calls_paired(path)[0] if os.path.exists(path) else []
            for i, push in enumerate(pushes):
                s = X.score_list(t, calls, push)
                rows.append((t, i, push["idx"], s["fresh"], s["next"]))
        out[lab] = rows
    return out


def pct(k, n):
    return "%d/%d (%.1f%%)" % (k, n, 100.0 * k / n) if n else "0/0"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    states, rows, complete = load_replays()
    sc = score(states, complete)
    keys = sorted(complete)

    add("EXPLORATORY: DOES THE ONE-CALL EFFECT OF THE REPLAYS DEPEND ON HOW FAR INTO ITS RUN THE PAUSED STEP IS?")
    add("EXPLORATORY. Written after the results of 23 were seen; the split was not registered. Outcome: the")
    add("  registered one of experiment B (the next call reads or edits lines of a listed true neighbor in a file not")
    add("  opened before; analyze_b any_true). Arms A (no list), H (names), E (names, file and line range).")
    add("")

    # 0. gate
    add("0. GATE (analyze_b: v5 + v6 + v8 replays, interface failures out, steps complete across all 10 arms and")
    add("  all seeds; boot_ci / diff_ci by step, 2,000 resamples, seed 0)")
    add("  %d replays read; %d complete steps" % (len(rows), len(keys)))
    got = {a: boot_ci(sc[a]) for a in ("A", "H", "E")}
    nrep = {a: sum(len(v) for v in sc[a].values()) for a in ("A", "H", "E")}
    eh = diff_ci(sc["E"], sc["H"])
    want = {"A": 0.0215, "H": 0.0275, "E": 0.0825}
    okg = len(keys) == 388 and all(nrep[a] == 1164 for a in nrep)
    for a in ("A", "H", "E"):
        add("  %s: %s of %d replays (want %.2f%% of 1164)" % (a, fmt(got[a]), nrep[a], 100 * want[a]))
        okg = okg and round(got[a][0], 4) == want[a]
    add("  E minus H: %s points (want +5.50 [+3.44, +7.65])" % fmt(eh, True))
    okg = okg and tuple(round(x, 4) for x in eh) == (0.0550, 0.0344, 0.0765)
    add("  " + ("reproduced" if okg else "NOT reproduced: see the differences above"))
    add("")

    # 1. distributions
    pos = {}
    mism = 0
    for k in keys:
        ci, nf, ed = position(states[k])
        if ci != states[k]["tool_calls_before_fork"]:
            mism += 1
        if nf != len(states[k]["shown_files"]):
            mism += 1
        pos[k] = (ci, nf, ed)
    add("1. POSITION OF THE 388 COMPLETE STEPS")
    add("  Call index (tool calls of the recorded run up to and including the call whose result ends the paused")
    add("  history): " + quart([pos[k][0] for k in keys]))
    add("    per value: " + counts([pos[k][0] for k in keys]))
    add("  Distinct files opened so far (fork_states.shows_content, as shown_files): "
        + quart([pos[k][1] for k in keys]))
    add("    per value: " + counts([pos[k][1] for k in keys]))
    add("  Edited or written a file so far (edit_file or write_file called; fork_states allows only write_file of a")
    add("  new file before a fork): %d of %d steps" % (sum(pos[k][2] for k in keys), len(keys)))
    add("  Stored fields disagreeing with the recount (tool_calls_before_fork, shown_files): %d" % mism)
    forks = collections.Counter(k[2] for k in keys)
    add("  Paused steps per fork number (0 = first content-showing step of the run): " + counts([k[2] for k in keys]))
    add("")

    # 2. split by call index
    t1, t2 = thirds([pos[k][0] for k in keys])
    add("2. BY CALL INDEX (thirds by the rule: cut at the smallest values with at least 1/3 and 2/3 of the steps at")
    add("  or below them; t1 = %d, t2 = %d)" % (t1, t2))
    mid = ("call index %d" % t2) if t2 == t1 + 1 else ("call index %d to %d" % (t1 + 1, t2))
    g_ci = [("call index <= %d" % t1, lambda c: c <= t1), (mid, lambda c: t1 < c <= t2),
            ("call index > %d" % t2, lambda c: c > t2)]
    for name, f in g_ci:
        group_report(name, [k for k in keys if f(pos[k][0])], sc)
        ks = [k for k in keys if f(pos[k][0])]
        add("    steps where A or H hits at least once: %d; of them every replay of A, H and E hits: %d" % (
            sum(1 for k in ks if sum(sc["A"][k]) or sum(sc["H"][k])),
            sum(1 for k in ks if (sum(sc["A"][k]) or sum(sc["H"][k]))
                and all(sum(sc[a][k]) == len(sc[a][k]) for a in ("A", "H", "E")))))
    runs = collections.defaultdict(list)
    for k in keys:
        runs[(k[0], k[1])].append(k)
    first = {min(v, key=lambda k: k[2]) for v in runs.values()}
    add("  First versus later paused step of a run (first = the lowest fork number among the run's complete steps;")
    add("  %d runs, %d with more than one complete step)" % (len(runs), sum(1 for v in runs.values() if len(v) > 1)))
    group_report("first paused step of its run", [k for k in keys if k in first], sc)
    group_report("later paused step of the same run", [k for k in keys if k not in first], sc)
    multi = {k for v in runs.values() if len(v) > 1 for k in v}
    group_report("first step, runs with several complete steps only",
                 [k for k in keys if k in first and k in multi], sc)
    add("")

    # 3. split by files opened
    add("3. BY DISTINCT FILES OPENED SO FAR")
    add("  (the brief's groups 0 or 1, 2, 3 or more leave 3 steps in the last; 2 and 3 or more are merged)")
    g_nf = [("0 or 1 file", lambda n: n <= 1), ("2 or more files", lambda n: n >= 2)]
    for name, f in g_nf:
        group_report(name, [k for k in keys if f(pos[k][1])], sc)
    add("")

    # 4. whole runs
    wr = whole_runs()
    add("4. WHOLE RUNS OF 23 (explore_next_call_23: score_list, the 'next call' of its section 1; N14 = the stored N")
    add("  run of 14 with its lists replayed offline, seen by no agent). Call index of the READ that carried the list")
    add("  = its call number in the run (push idx; calls paired by rederive_18.load_calls_paired)")
    for lab in X.LABS:
        rws = wr[lab]
        add("  %s, first lists: %s" % (lab, quart([r[2] for r in rws if r[1] == 0])))
        add("  %s, all lists:   %s" % (lab, quart([r[2] for r in rws])))
    add("  PE first lists, per value: " + counts([r[2] for r in wr["PE"] if r[1] == 0]))
    add("  Outcome (next call reads a listed entry's code in a file not opened before), by the call-index groups of")
    add("  section 2; over all lists | over lists with an entry in a file not opened before:")
    for name, f in g_ci + [("all", lambda c: True)]:
        parts = []
        for lab in X.LABS:
            al = [r for r in wr[lab] if f(r[2])]
            fr = [r for r in al if r[3] > 0]
            parts.append("%s %s | %s" % (lab, pct(sum(r[4] for r in al), len(al)), pct(sum(r[4] for r in fr), len(fr))))
        add("    %s: %s" % (name, "; ".join(parts)))
    add("  Same, first lists only:")
    for name, f in g_ci + [("all", lambda c: True)]:
        parts = []
        for lab in X.LABS:
            al = [r for r in wr[lab] if f(r[2]) and r[1] == 0]
            fr = [r for r in al if r[3] > 0]
            parts.append("%s %s | %s" % (lab, pct(sum(r[4] for r in al), len(al)), pct(sum(r[4] for r in fr), len(fr))))
        add("    %s: %s" % (name, "; ".join(parts)))
    add("")

    add("JUDGMENT CALLS")
    for i, text in enumerate([
        "Call index: tool calls in the agent steps of the stored paused history (states.jsonl 'steps'); fork_states"
        " cuts at the agent step whose result shows content and stops at any step with parallel calls, so each agent"
        " step there has at most one call. Checked against the stored tool_calls_before_fork (disagreements above).",
        "Files opened: distinct paths shown by fork_states.shows_content over the paused history (the rule that built"
        " shown_files and decides 'not opened before'); a grep or rg with stdout counts its last .py path.",
        "Edited or written: any edit_file or write_file call; fork_states forks only before edit_file, submit_patch,"
        " or write_file onto an existing repository file, so only a write_file of a new file can appear.",
        "Thirds: cut points chosen by the stated rule on the 388 steps, not by looking at rates; ties make the groups"
        " unequal. Files opened: 0 or 1 against 2 or more (the brief's 3-or-more group would hold 3 steps).",
        "First paused step: the lowest fork number among the run's complete steps (a run's fork 0 may be incomplete"
        " and dropped). A run is (task, run).",
        "By task: diff_ci and boot_ci of analyze_forks with the clusters taken as tasks instead of steps (all replays"
        " of all the task's steps in the group pooled), same 2,000 resamples, seed 0.",
        "Whole runs: every pushed list of an entered run counts (section 1 of explore_next_call_23); the 'next call'"
        " is call p+1 (that report shows the redefinition by model step changes one PH list). The rates are given"
        " over all lists and over lists with an entry in an unopened file.",
    ], 1):
        words = text.split()
        line = "%2d." % i
        lines = []
        for w in words:
            if len(line) + 1 + len(w) > 112:
                lines.append(line)
                line = "   "
            line += " " + w
        lines.append(line)
        for l in lines:
            add(l)
    sys.stdout.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
