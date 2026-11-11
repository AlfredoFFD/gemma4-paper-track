#!/usr/bin/env python3
"""Independent re-derivation of the registered results of pre-registration 18
(whole runs told where the fix is, as names or as addresses) from the stored
runs.

Usage:  py -I -X utf8 analysis/rederive_18.py [--no-write]

Read: analysis/oracle_18/tasks_18.txt (the 40 tasks in run order), the three
harness results directories analysis/results/18/<arm>/seed2/ for the arms N,
ON and OA (task_results.jsonl, extra.jsonl, patches/, traces/, test_outputs/),
and data/tasks.jsonl (the reference patches). The report is printed and,
unless --no-write is given, the same text is written to
analysis/results/rederive_18.txt with LF line endings.

Written blind from the text of prereg/18-whole-runs-told-where-the-fix-is.md
and of prereg/14-whole-runs-scored-by-tests.md, without sight of the project's
registered analysis (analyze_18.py, analyze_14.py) or of their outputs. It
reuses, by import, the loading and scoring of analysis/rederive_14.py, the
independent second script of pre-registration 14 (written blind from the text
of 14): the patch parser and CHANGED REGIONS, the reading of a trace, the views
of a file (read_file results and shell views), the infrastructure-failure rule
and the kinds of error text. Everything new in 18 is written here: the arms,
"patch touches every changed region", the four rules with the exact McNemar p,
the bootstrap (seed 0) and the descriptive cuts (a), (b) and (d) of the dated
note. Standard library only.
"""
import json
import math
import os
import random
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rederive_14 as r14  # noqa: E402  (the independent second script of 14)

ARMS = ("N", "ON", "OA")
SEED_DIR = "seed2"
MIN_TASKS = 34
BOOT_RESAMPLES = 2000
BOOT_SEED = 0
WIDTH = 112
INF = float("inf")
BINS = (("1", 1, 1), ("2 or 3", 2, 3), ("4 to 9", 4, 9), ("10 or more", 10, 10 ** 9))


# ------------------------------------------------------------------ traces

def load_calls_paired(path):
    """Tool calls of a session in order: [(function name, arguments, result)].

    A step of the agent with k tool calls carries the result of the first in its
    own observation and the results of the others in the k - 1 'system' steps
    that follow it, in order. rederive_14.load_calls reads only steps with one
    tool call and gives the calls of a step with several an empty result; this
    loader pairs them. Returns (calls, steps with several calls, calls whose
    result is not a JSON object, steps whose count of results differs from
    their count of calls).
    """
    with open(path, encoding="utf-8") as handle:
        trace = json.load(handle)
    steps = trace.get("steps") or []
    calls = []
    multi = unparsed = mismatched = 0
    i = 0
    while i < len(steps):
        step = steps[i]
        tool_calls = step.get("tool_calls") or []
        if not tool_calls:
            i += 1
            continue
        observations = [step.get("observation")]
        j = i + 1
        while (j < len(steps) and not steps[j].get("tool_calls") and steps[j].get("source") == "system"
               and "observation" in steps[j]):
            observations.append(steps[j]["observation"])
            j += 1
        if len(tool_calls) > 1:
            multi += 1
        if len(observations) != len(tool_calls):
            mismatched += 1
        for k, tool_call in enumerate(tool_calls):
            result = None
            observation = observations[k] if k < len(observations) else None
            if isinstance(observation, dict):
                content = observation.get("content")
                if isinstance(content, str):
                    try:
                        result = json.loads(content)
                    except ValueError:
                        result = None
                elif isinstance(content, dict):
                    result = content
            if not isinstance(result, dict):
                result = {}
                unparsed += 1
            arguments = tool_call.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append((tool_call.get("function_name"), arguments, result))
        i = j
    return calls, multi, unparsed, mismatched


# ----------------------------------------------------------------- scoring

def region_list(gold):
    """[(path, (first, last))] over every CHANGED REGION of every GOLD FILE, in a fixed order."""
    return [(path, span) for path in sorted(gold) for span in gold[path]]


def first_shown_each(views, regions, reading=r14.WRITTEN, shell=True):
    """For each region, the smallest call index of a view of its file whose lines overlap it; INF if never."""
    out = []
    for path, (low, high) in regions:
        found = INF
        for view in views:
            if view[1] == "b" and not shell:
                continue
            if view[3] != path:
                continue
            first, last = view[reading]
            if first <= high and low <= last:
                found = view[0]
                break  # views are in call order
        out.append(found)
    return out


def touches_every(agent_regions, regions):
    """Every reference region is intersected by a region of the agent's final patch in the same file."""
    if not regions:
        return False
    for path, (low, high) in regions:
        if not r14.overlaps(agent_regions.get(path), low, high):
            return False
    return True


# ----------------------------------------------------------------- loading

def load_arm(root, arm, run_list, gold_by_task):
    base = os.path.join(root, arm, SEED_DIR)
    lines = r14.read_jsonl(os.path.join(base, "task_results.jsonl"))
    last = {}
    for row in lines:
        last[row.get("instance_id")] = row
    extra = {}
    extra_lines = r14.read_jsonl(os.path.join(base, "extra.jsonl"))
    for row in extra_lines:
        extra[row.get("task")] = row
    stats = {"lines": len(lines), "distinct": len(last), "extra_lines": len(extra_lines),
             "off_list": sorted(t for t in last if t not in run_list), "no_trace": [], "no_test_output": [],
             "multi": 0, "unparsed": 0, "unparsed_14": 0, "mismatched": 0, "count_differs": [], "patch_mismatch": [], "no_extra": [], "arm_mismatch": [],
             "seed_mismatch": [], "note_wrong": [], "crash": []}
    sessions = {}
    for task in run_list:
        if task not in last:
            continue
        row = last[task]
        gold = gold_by_task[task]
        regions = region_list(gold)
        trace_path = os.path.join(base, "traces", "trace_%s.json" % task)
        calls = []
        calls_14 = []
        if os.path.exists(trace_path):
            calls, multi, unparsed, mismatched = load_calls_paired(trace_path)
            calls_14, _multi, unparsed_14 = r14.load_calls(trace_path)
            stats["multi"] += multi
            stats["unparsed"] += unparsed
            stats["unparsed_14"] += unparsed_14
            stats["mismatched"] += mismatched
            if len(calls_14) != len(calls):
                stats["count_differs"].append(task)
        else:
            stats["no_trace"].append(task)
        if not os.path.exists(os.path.join(base, "test_outputs", "%s.log" % task)):
            stats["no_test_output"].append("%s (test exit code %s)" % (task, row.get("test_exit_code")))
        views, _uncounted = r14.session_views(calls, gold)
        views_14, _uncounted_14 = r14.session_views(calls_14, gold)
        agent_regions = {}
        has_patch = False
        patch_path = os.path.join(base, "patches", "%s.patch" % task)
        if os.path.exists(patch_path):
            with open(patch_path, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace")
            if text.strip():
                has_patch = True
                agent_regions, _facts = r14.changed_regions(text)
        size = row.get("agent_patch_size")
        if r14.is_int(size) and (size > 0) != has_patch:
            stats["patch_mismatch"].append(task)
        record = extra.get(task)
        if not isinstance(record, dict):
            stats["no_extra"].append(task)
            record = {}
        else:
            if record.get("arm", record.get("condition")) != arm:
                stats["arm_mismatch"].append(task)
            if record.get("seed") != 2:
                stats["seed_mismatch"].append(task)
            in_message = record.get("note_in_first_message")
            if (arm == "N" and in_message not in (0, None)) or (arm != "N" and in_message != 1):
                stats["note_wrong"].append(task)
            if record.get("crash"):
                stats["crash"].append(task)
        each = first_shown_each(views, regions)
        each_a = first_shown_each(views, regions, shell=False)
        each_14 = first_shown_each(views_14, regions)
        shown = sum(1 for v in each if v < INF)
        sessions[task] = {
            "resolved": row.get("resolved") is True,
            "error": row.get("error"),
            "infra": r14.infra_kind(row.get("error")),
            "calls": len(calls),
            "regions": len(regions),
            "shown_regions": shown,
            "share": (shown / len(regions)) if regions else None,
            "every": bool(regions) and shown == len(regions),
            "every_a": bool(regions) and all(v < INF for v in each_a),
            "every_14": bool(regions) and all(v < INF for v in each_14),
            "t_14": r14.first_shown(views_14, gold),
            "share_14": (sum(1 for v in each_14 if v < INF) / len(regions)) if regions else None,
            "t_all": max(each) if regions and shown == len(regions) else INF,
            "t": r14.first_shown(views, gold),
            "overlap": r14.patch_overlaps(agent_regions, gold),
            "touch_every": touches_every(agent_regions, regions),
            "ending": str(record.get("agent_ending")) if record else "no runner record",
            "interface": list(record.get("interface_failures") or []) if record else [],
            "test_exit": row.get("test_exit_code"),
        }
    return sessions, stats


# ------------------------------------------------------------------ rules

def percentile(ordered, q):
    position = (len(ordered) - 1) * q
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def boot_interval(diffs):
    """95% percentile interval, in points, of the mean of the per-task differences; tasks resampled."""
    n = len(diffs)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    means = []
    for _ in range(BOOT_RESAMPLES):
        total = 0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(100.0 * total / n)
    means.sort()
    return (percentile(means, 0.025), percentile(means, 0.975))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p: binomial(b + c, 1/2), twice the smaller tail, capped at 1."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def compare(data, tasks, first, second, outcome):
    """first minus second, paired by task."""
    pairs = [(1 if outcome(data[first][t]) else 0, 1 if outcome(data[second][t]) else 0) for t in tasks]
    diffs = [a - b for a, b in pairs]
    n = len(pairs)
    low, high = boot_interval(diffs)
    b = sum(1 for a, s in pairs if a == 1 and s == 0)
    c = sum(1 for a, s in pairs if a == 0 and s == 1)
    return {"n": n, "first": sum(a for a, _ in pairs), "second": sum(s for _, s in pairs),
            "point": 100.0 * sum(diffs) / n if n else float("nan"), "low": low, "high": high,
            "b": b, "c": c, "p": mcnemar_exact(b, c),
            "only_first": sorted(t for t, (a, s) in zip(tasks, pairs) if a == 1 and s == 0),
            "only_second": sorted(t for t, (a, s) in zip(tasks, pairs) if a == 0 and s == 1)}


def verdict(result):
    if result["n"] < MIN_TASKS:
        return "no verdict (fewer than %d tasks)" % MIN_TASKS
    if result["low"] > 0:
        return "more"
    if result["high"] < 0:
        return "fewer"
    return "no detectable difference"


# ------------------------------------------------------------------ format

def rate(hits, total):
    if total == 0:
        return "0/0 (n/a)"
    return "%d/%d (%.1f%%)" % (hits, total, 100.0 * hits / total)


def signed(value):
    if abs(value) < 0.005:
        value = 0.0
    return "%+.2f" % value


def wrap(text, first="", rest=""):
    return textwrap.fill(text, width=WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def counted(mapping):
    items = sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
    return "; ".join(("%s %d" % (k, v)).replace(" ", "\xa0") for k, v in items) if items else "none"


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return float("nan")
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


# -------------------------------------------------------------------- main

def build_report():
    root = os.path.join(HERE, "results", "18")
    with open(os.path.join(HERE, "oracle_18", "tasks_18.txt"), encoding="utf-8") as handle:
        run_list = [line.strip() for line in handle if line.strip()]
    reference = {}
    for row in r14.read_jsonl(os.path.join(HERE, os.pardir, "data", "tasks.jsonl")):
        reference[row.get("instance_id")] = row
    gold_by_task = {}
    ref = {"files": 0, "created": 0, "gold_files": 0, "regions": 0, "short": 0, "skipped": 0}
    for task in run_list:
        regions, facts = r14.changed_regions(reference[task]["patch"])
        gold_by_task[task] = regions
        ref["files"] += facts["files"]
        ref["created"] += facts["created"]
        ref["gold_files"] += len(regions)
        ref["regions"] += sum(len(v) for v in regions.values())
        ref["short"] += facts["short"]
        ref["skipped"] += facts["skipped"]
    n_regions = {t: sum(len(v) for v in gold_by_task[t].values()) for t in run_list}

    data, stats = {}, {}
    for arm in ARMS:
        data[arm], stats[arm] = load_arm(root, arm, run_list, gold_by_task)
    entered = {arm: [t for t in run_list if t in data[arm] and data[arm][t]["infra"] is None] for arm in ARMS}

    out = []
    add = out.append
    add("RE-DERIVATION OF PRE-REGISTRATION 18 (whole runs told where the fix is: N, ON names, OA addresses; seed 2)")
    add(wrap("Written blind from the registration texts of 18 and 14 and the stored runs; loading and scoring imported"
             " from the independent second script of 14 (analysis/rederive_14.py). A run is (task, arm)."))
    add("")

    # ---- 1
    add("1. RUNS PER ARM AND HOW MANY ENTERED")
    add(wrap("Task list (analysis/oracle_18/tasks_18.txt): %d tasks. Reference patches of these tasks: %d files, %d"
             " created by the patch (left out), %d GOLD FILES with %d CHANGED REGIONS; tasks without a GOLD FILE: %d."
             % (len(run_list), ref["files"], ref["created"], ref["gold_files"], ref["regions"],
                sum(1 for t in run_list if not gold_by_task[t]))))
    for arm in ARMS:
        st = stats[arm]
        infra = sorted(t for t in data[arm] if data[arm][t]["infra"] is not None)
        add(wrap("%s: result lines %d (distinct tasks %d, off the list %d); runs with a result on the list %d;"
                 " infrastructure failures %d%s; entered %d."
                 % (arm, st["lines"], st["distinct"], len(st["off_list"]), len(data[arm]), len(infra),
                    (" (" + ", ".join("%s: %s" % (t, data[arm][t]["infra"]) for t in infra) + ")") if infra else "",
                    len(entered[arm])), "  ", "    "))
    all_three = [t for t in run_list if all(t in entered[a] for a in ARMS)]
    add("Tasks entered in all three arms: %d." % len(all_three))
    missing = {arm: [t for t in run_list if t not in data[arm]] for arm in ARMS}
    add("Tasks with no result in an arm: " + "; ".join("%s %s" % (a, ", ".join(missing[a]) if missing[a] else "none")
                                                       for a in ARMS))
    add("")

    # ---- 2
    add("2. PER ARM, ON THE RUNS THAT ENTERED")

    def row(label, values):
        add(("%-40s%-22s%-22s%s" % ((label,) + tuple(values))).rstrip())

    row("", ARMS)
    outcomes = (
        ("RESOLVED", lambda s: s["resolved"]),
        ("shown a changed line (ever)", lambda s: s["t"] < INF),
        ("shown every changed region", lambda s: s["every"]),
        ("  the same, read_file results only", lambda s: s["every_a"]),
        ("  the same, loader of rederive_14", lambda s: s["every_14"]),
        ("shown a changed line, loader of 14", lambda s: s["t_14"] < INF),
        ("patch overlaps a changed region", lambda s: s["overlap"]),
        ("patch touches every changed region", lambda s: s["touch_every"]),
    )
    for label, outcome in outcomes:
        row(label, [rate(sum(1 for t in entered[a] if outcome(data[a][t])), len(entered[a])) for a in ARMS])
    row("mean tool calls (trace)", ["%.2f" % (sum(data[a][t]["calls"] for t in entered[a]) / len(entered[a]))
                                    if entered[a] else "n/a" for a in ARMS])
    add("How the sessions ended (runner record agent_ending), all runs with a result:")
    for arm in ARMS:
        endings = {}
        for t in data[arm]:
            endings[data[arm][t]["ending"]] = endings.get(data[arm][t]["ending"], 0) + 1
        add(wrap("%s: %s" % (arm, counted(endings)), "  ", "    "))
    add("Error text of the result line (outcomes, not exclusions), all runs with a result:")
    for arm in ARMS:
        kinds = {}
        for t in data[arm]:
            kind = r14.error_kind(data[arm][t]["error"])
            kinds[kind] = kinds.get(kind, 0) + 1
        add(wrap("%s: %s" % (arm, counted(kinds)), "  ", "    "))
    add("Interface failures named by the runner record (a run may have more than one):")
    for arm in ARMS:
        kinds = {}
        for t in data[arm]:
            for kind in data[arm][t]["interface"]:
                kinds[kind] = kinds.get(kind, 0) + 1
        add(wrap("%s: %s" % (arm, counted(kinds)), "  ", "    "))
    add("Test exit code of the result line:")
    for arm in ARMS:
        codes = {}
        for t in data[arm]:
            key = str(data[arm][t]["test_exit"])
            codes[key] = codes.get(key, 0) + 1
        add(wrap("%s: %s" % (arm, counted(codes)), "  ", "    "))
    add("")

    # ---- 3
    add(wrap("3. THE FOUR RULES (first arm minus second, paired by task, on the tasks where both runs entered; points;"
             " 95%% bootstrap interval by task: %s resamples, percentile, random.Random(%d); exact McNemar p, two-sided;"
             " a verdict needs at least %d tasks)" % ("{:,}".format(BOOT_RESAMPLES), BOOT_SEED, MIN_TASKS), "", "   "))
    rules = (
        ("U1", "RESOLVED", "OA", "N", lambda s: s["resolved"]),
        ("U2", "RESOLVED", "OA", "ON", lambda s: s["resolved"]),
        ("U3", "shown every changed region", "OA", "N", lambda s: s["every"]),
        ("U3", "shown every changed region", "OA", "ON", lambda s: s["every"]),
        ("U4", "RESOLVED", "ON", "N", lambda s: s["resolved"]),
    )
    for name, label, first, second, outcome in rules:
        tasks = [t for t in run_list if t in entered[first] and t in entered[second]]
        if label != "RESOLVED":
            tasks = [t for t in tasks if gold_by_task[t]]
        res = compare(data, tasks, first, second, outcome)
        add(wrap("%s, %s, %s against %s: %s %s, %s %s; difference %s points, interval [%s, %s]; discordant pairs:"
                 " %s only %d, %s only %d; exact McNemar p = %.4g; verdict: \"%s\"."
                 % (name, label, first, second, first, rate(res["first"], res["n"]), second,
                    rate(res["second"], res["n"]), signed(res["point"]), signed(res["low"]), signed(res["high"]),
                    first, res["b"], second, res["c"], res["p"], verdict(res)), "", "    "))
        add(wrap("yes in %s only: %s" % (first, ", ".join(res["only_first"]) or "none"), "    ", "      "))
        add(wrap("yes in %s only: %s" % (second, ", ".join(res["only_second"]) or "none"), "    ", "      "))
    for key, words in (("every_a", "counted on read_file results alone"),
                       ("every_14", "counted with the results of steps that hold one tool call only (the loader of"
                                    " rederive_14, which gives the calls of a step with several an empty result)")):
        sens = []
        for first, second in (("OA", "N"), ("OA", "ON")):
            tasks = [t for t in run_list if t in entered[first] and t in entered[second] and gold_by_task[t]]
            res = compare(data, tasks, first, second, lambda s, key=key: s[key])
            sens.append("%s against %s: %d against %d of %d, difference %s [%s, %s], p = %.4g, \"%s\""
                        % (first, second, res["first"], res["second"], res["n"], signed(res["point"]),
                           signed(res["low"]), signed(res["high"]), res["p"], verdict(res)))
        add(wrap("Sensitivity (not the rule): U3 with shown every changed region %s: " % words
                 + "; ".join(sens) + ".", "", "    "))
    add("")

    # ---- 4
    add("4. RESOLVED IN OA BY RESOLVED IN ON (tasks where both entered)")
    tasks = [t for t in run_list if t in entered["OA"] and t in entered["ON"]]
    cell = {(a, b): 0 for a in (0, 1) for b in (0, 1)}
    for t in tasks:
        cell[(1 if data["OA"][t]["resolved"] else 0, 1 if data["ON"][t]["resolved"] else 0)] += 1
    add("  %-10s%10s%10s%10s" % ("", "ON yes", "ON no", "total"))
    add("  %-10s%10d%10d%10d" % ("OA yes", cell[(1, 1)], cell[(1, 0)], cell[(1, 1)] + cell[(1, 0)]))
    add("  %-10s%10d%10d%10d" % ("OA no", cell[(0, 1)], cell[(0, 0)], cell[(0, 1)] + cell[(0, 0)]))
    add("  %-10s%10d%10d%10d" % ("total", cell[(1, 1)] + cell[(0, 1)], cell[(1, 0)] + cell[(0, 0)], len(tasks)))
    add("")

    # ---- 5
    add("5. DESCRIPTIVE CUTS OF THE DATED NOTE (EXPLORATORY, no rule; cut (c) left out)")
    add("(a) By the number of CHANGED REGIONS of the task: resolved and shown every changed region, per arm")
    for label, low, high in BINS:
        in_bin = [t for t in run_list if low <= n_regions[t] <= high]
        parts = []
        for arm in ARMS:
            runs = [t for t in in_bin if t in entered[arm]]
            parts.append("%s resolved %s, every region %s"
                         % (arm, rate(sum(data[arm][t]["resolved"] for t in runs), len(runs)),
                            rate(sum(data[arm][t]["every"] for t in runs), len(runs))))
        add(wrap("%s region%s (%d tasks): %s" % (label, "" if label == "1" else "s", len(in_bin), "; ".join(parts)),
                 "  ", "    "))
    add("(b) Per arm, mean over tasks of the share of the task's CHANGED REGIONS the run was shown")
    for arm in ARMS:
        runs = [t for t in entered[arm] if gold_by_task[t]]
        shares = [data[arm][t]["share"] for t in runs]
        shown = sum(data[arm][t]["shown_regions"] for t in runs)
        total = sum(data[arm][t]["regions"] for t in runs)
        shares_14 = [data[arm][t]["share_14"] for t in runs]
        add(wrap("%s: %.3f over %d runs (pooled: %d of %d regions, %.3f); runs shown no region %d; shown every"
                 " region %d; mean share with the loader of rederive_14 %.3f"
                 % (arm, sum(shares) / len(shares) if shares else float("nan"), len(runs), shown, total,
                    shown / total if total else float("nan"),
                    sum(1 for t in runs if data[arm][t]["shown_regions"] == 0),
                    sum(1 for t in runs if data[arm][t]["every"]),
                    sum(shares_14) / len(shares_14) if shares_14 else float("nan")), "  ", "    "))
    add(wrap("(d) Per arm, in the runs shown every changed region: the CALL INDEX at which the last of the task's"
             " regions is first shown (the tool calls before it are that index minus 1)", "", "    "))
    for arm in ARMS:
        runs = [t for t in entered[arm] if data[arm][t]["every"]]
        values = [data[arm][t]["t_all"] for t in runs]
        if values:
            add(wrap("%s: %d runs; index mean %.2f, median %s, min %d, max %d; calls before it: mean %.2f, median %s;"
                     " values: %s"
                     % (arm, len(values), sum(values) / len(values), ("%g" % median(values)), min(values), max(values),
                        sum(values) / len(values) - 1, ("%g" % (median(values) - 1)),
                        ", ".join("%s %d" % (t, data[arm][t]["t_all"]) for t in runs)), "  ", "    "))
        else:
            add("  %s: no run shown every changed region" % arm)
    add("")

    # ---- 6
    add("6. CHECKS ON THE STORED RUNS")
    add(wrap("Reference patches: hunks whose body does not hold the counts of its header %d; lines inside hunks"
             " that are not diff lines %d." % (ref["short"], ref["skipped"]), "  ", "    "))
    for arm in ARMS:
        st = stats[arm]
        add(wrap("%s: extra.jsonl lines %d; missing traces %s; missing test outputs %s; runs without a runner"
                 " record %s; runner record names another arm %s or seed %s; note not where it should be"
                 " (note_in_first_message) %s; crash recorded %s; patch file present though size 0 or the reverse"
                 " %s; steps with more than one tool call %d (steps whose count of results differs from their"
                 " count of calls %d; sessions where the two loaders count a different number of calls %s);"
                 " tool results that are not a JSON object %d (with the loader of rederive_14: %d)."
                 % (arm, st["extra_lines"], ", ".join(st["no_trace"]) or "none",
                    ", ".join(st["no_test_output"]) or "none", ", ".join(st["no_extra"]) or "none",
                    ", ".join(st["arm_mismatch"]) or "none", ", ".join(st["seed_mismatch"]) or "none",
                    ", ".join(st["note_wrong"]) or "none", ", ".join(st["crash"]) or "none",
                    ", ".join(st["patch_mismatch"]) or "none", st["multi"], st["mismatched"],
                    ", ".join(st["count_differs"]) or "none", st["unparsed"], st["unparsed_14"]), "  ", "    "))
    add("")

    # ---- 7
    add("7. JUDGMENT CALLS")
    notes = [
        "A run enters if its arm has a result line for the task (the last line counts) and the error text is not an"
        " infrastructure failure by the rule of 14 (rederive_14.infra_kind). A rule uses the tasks where both of its"
        " runs entered; the four rules are computed on their own pairs, not on the tasks entered in all three arms.",
        "Shown every changed region: every CHANGED REGION of every GOLD FILE is overlapped by the lines of some view"
        " of that file, the same views that define 'shown a changed line' in 14: a read_file result with status ok"
        " (its returned start_line to end_line) or a shell view of one file (cat, head, tail, sed -n), lines as"
        " written. The outcome text of 18 says '(reads)'; read as read_file results alone the counts are printed"
        " beside it and as a sensitivity of U3.",
        "Patch touches every changed region: every CHANGED REGION of every GOLD FILE is intersected by a region of"
        " the agent's final patch in the same file, the agent's regions computed by the same parser on the same"
        " old-file numbering; an empty or missing patch is false.",
        "Traces. When the model makes several tool calls in one step, the trace stores the first result in that"
        " step's observation and the others in the 'system' steps that follow, in order (in every stored session"
        " the counts match and each read_file result names the file its call asked for). The calls are paired with"
        " those results here. The loader of rederive_14 gives such calls an empty result, so their reads are not"
        " seen; the counts with that loader are printed as a sensitivity. The CALL INDEX is the same under both.",
        "A note in the task statement of ON or OA does not count as being shown a line: only tool results do.",
        "Bootstrap: the per-task differences (first arm minus second, -1, 0 or 1) are resampled with replacement,"
        " random.Random(0) started afresh for each comparison, tasks indexed in run-list order with randrange; the"
        " interval is the 2.5th to 97.5th percentile of the resampled means, linear interpolation; 'more' needs the"
        " lower bound strictly above 0, 'fewer' the upper bound strictly below.",
        "Exact McNemar p: twice the smaller binomial(b + c, 1/2) tail at min(b, c), capped at 1; 1 when there is no"
        " discordant pair.",
        "Cut (a): the number of CHANGED REGIONS of a task is the count of hunk regions over its GOLD FILES (before"
        " the merging into places that the note of ON and OA uses). Cut (b): the share is over the task's CHANGED"
        " REGIONS, averaged over the runs that entered with equal weight per task. Cut (d): the call index of the"
        " view that completes the set (every call in the trace counts, from 1).",
        "'tests_could_not_run' in a runner record, with test exit code 2 and an empty error text, is read as an"
        " outcome (the tests were collected against the agent's patch), not an infrastructure failure: the rule of"
        " 14 decides from the error text.",
    ]
    for number, note in enumerate(notes, 1):
        add(wrap(note, "%2d. " % number, "    "))
    add("")

    # ---- per task
    add("PER TASK (k CHANGED REGIONS; per arm: r RESOLVED, s regions shown, e shown every region, o patch overlaps,"
        " v patch touches every region, c tool calls)")
    for task in run_list:
        parts = []
        for arm in ARMS:
            if task not in data[arm]:
                parts.append("%-2s missing" % arm)
                continue
            s = data[arm][task]
            parts.append("%-2s r=%d s=%-2d e=%d o=%d v=%d c=%-2d" % (arm, s["resolved"], s["shown_regions"], s["every"],
                                                                   s["overlap"], s["touch_every"], s["calls"]))
        add(("  %-14s k=%-3d %s" % (task, n_regions[task], " | ".join(parts))).rstrip())
    return ("\n".join(out) + "\n").replace("\xa0", " ")


def main(argv):
    write = "--no-write" not in argv[1:]
    if [a for a in argv[1:] if a != "--no-write"]:
        sys.stderr.write("usage: rederive_18.py [--no-write]\n")
        return 2
    report = build_report()
    if write:
        with open(os.path.join(HERE, "results", "rederive_18.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
