#!/usr/bin/env python3
"""Independent re-derivation of pre-registration 22 (told where the fix is, a
second seed, with the functions and the lines apart) from the stored runs.

Usage:  py -I -X utf8 analysis/rederive_22.py [--no-write]

Read: analysis/oracle_18/tasks_18.txt (the 40 tasks in run order), the harness
results directories analysis/results/22/<arm>/seed3/ for the arms N, ON, OF
and OA, analysis/results/18/<arm>/seed2/ for N, ON and OA, data/tasks.jsonl
(the reference patches) and analysis/oracle_22/manifest.json (the md5 of each
note, for a check). The report is printed and, unless --no-write is given, the
same text is written to analysis/results/rederive_22.txt with LF line endings.

Written blind from the text of prereg/22-told-where-the-fix-is-second-seed.md
(with its dated note), of prereg/18 and of prereg/14, without sight of the
registered analysis (analyze_22.py, analyze_18.py, analyze_14.py) or of their
outputs. It reuses, by import, the two independent second scripts that already
exist: analysis/rederive_14.py (patch parser and CHANGED REGIONS, views of a
file, the infrastructure-failure rule) and analysis/rederive_18.py (every tool
call paired with its own result, "shown every changed region", "patch touches
every changed region", the paired comparison with its bootstrap, seed 0, and
the exact McNemar p). Everything new in 22 is written here: the fourth arm, the
seven rules, the three cuts of the dated note, the pooling over seeds 2 and 3
and the two seeds side by side. Whatever shards are stored are read; the
script needs no change when the second shard of seed 3 is stored.
Standard library only.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rederive_14 as r14  # noqa: E402  (independent second script of 14)
import rederive_18 as r18  # noqa: E402  (independent second script of 18)

ARMS_22 = ("N", "ON", "OF", "OA")
ARMS_POOL = ("N", "ON", "OA")
SEEDS = ((2, os.path.join("results", "18"), "seed2", ("N", "ON", "OA")),
         (3, os.path.join("results", "22"), "seed3", ARMS_22))
MIN_TASKS = 34
BOOT_RESAMPLES = 2000
BOOT_SEED = 0
INF = float("inf")
CONTEXT = "context window"
wrap = r18.wrap
rate = r18.rate
signed = r18.signed
counted = r18.counted


# ----------------------------------------------------------------- loading

def load_arm(base, arm, seed, run_list, gold_by_task, manifest):
    """Runs of one arm and seed: {task: record}, plus checks. The last result line of a task counts."""
    stats = {"present": os.path.isdir(base), "lines": 0, "distinct": 0, "off_list": [], "no_trace": [],
             "no_test_output": [], "no_extra": [], "arm_mismatch": [], "seed_mismatch": [], "note_wrong": [],
             "md5_wrong": [], "crash": [], "patch_mismatch": [], "multi": 0, "mismatched": 0, "unparsed": 0,
             "harness": {}, "ending_vs_error": [], "positions": []}
    sessions = {}
    if not stats["present"]:
        return sessions, stats
    lines = r14.read_jsonl(os.path.join(base, "task_results.jsonl"))
    last = {}
    for row in lines:
        last[row.get("instance_id")] = row
    extra = {}
    extra_path = os.path.join(base, "extra.jsonl")
    if os.path.exists(extra_path):
        for row in r14.read_jsonl(extra_path):
            extra[row.get("task")] = row
    stats["lines"] = len(lines)
    stats["distinct"] = len(last)
    stats["off_list"] = sorted(t for t in last if t not in run_list)
    for task in run_list:
        if task not in last:
            continue
        row = last[task]
        gold = gold_by_task[task]
        regions = r18.region_list(gold)
        trace_path = os.path.join(base, "traces", "trace_%s.json" % task)
        calls = []
        calls_14 = []
        if os.path.exists(trace_path):
            calls, multi, unparsed, mismatched = r18.load_calls_paired(trace_path)
            calls_14, _multi, _unparsed = r14.load_calls(trace_path)
            stats["multi"] += multi
            stats["unparsed"] += unparsed
            stats["mismatched"] += mismatched
        else:
            stats["no_trace"].append(task)
        if not os.path.exists(os.path.join(base, "test_outputs", "%s.log" % task)):
            stats["no_test_output"].append("%s (exit %s)" % (task, row.get("test_exit_code")))
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
            if record.get("seed") != seed:
                stats["seed_mismatch"].append(task)
            in_message = record.get("note_in_first_message")
            if (arm == "N" and in_message not in (0, None)) or (arm != "N" and in_message != 1):
                stats["note_wrong"].append(task)
            if manifest is not None and arm != "N":
                entry = (manifest.get("tasks") or {}).get(task) or {}
                if record.get("note_md5") != entry.get("%s_md5" % arm):
                    stats["md5_wrong"].append(task)
            if record.get("crash"):
                stats["crash"].append(task)
            key = str(record.get("harness"))
            stats["harness"][key] = stats["harness"].get(key, 0) + 1
            stats["positions"].append(record.get("order_index"))
        ending = str(record.get("agent_ending")) if record else "no runner record"
        if (ending == CONTEXT) != (r14.error_kind(row.get("error")) == CONTEXT):
            stats["ending_vs_error"].append(task)
        each = r18.first_shown_each(views, regions)
        edited = [r14.overlaps(agent_regions.get(path), low, high) for path, (low, high) in regions]
        shown_each = [v < INF for v in each]
        sessions[task] = {
            "resolved": row.get("resolved") is True,
            "infra": r14.infra_kind(row.get("error")),
            "error": row.get("error"),
            "calls": len(calls),
            "regions": len(regions),
            "shown_each": shown_each,
            "edited_each": edited,
            "shown_line": r14.first_shown(views, gold) < INF,
            "every": bool(regions) and all(shown_each),
            "every_14": bool(regions) and all(v < INF for v in r18.first_shown_each(views_14, regions)),
            "overlap": r14.patch_overlaps(agent_regions, gold),
            "touch_every": r18.touches_every(agent_regions, regions),
            "ending": ending,
            "context": ending == CONTEXT,
        }
    return sessions, stats


# ------------------------------------------------------------------ tests

def verdict(result):
    if result["n"] < MIN_TASKS:
        return "no verdict (too few tasks)"
    if result["low"] > 0:
        return "more"
    if result["high"] < 0:
        return "fewer"
    return "no detectable difference"


def pooled_compare(per_task):
    """per_task: [(sum of first minus second over the task's included runs, number of included runs)], in task order.

    Difference of the pooled shares in points; the bootstrap resamples tasks (a task's runs together),
    random.Random(0), 2,000 resamples, percentile interval.
    """
    n_tasks = len(per_task)
    total = sum(n for _, n in per_task)
    if n_tasks == 0 or total == 0:
        return float("nan"), float("nan"), float("nan")
    point = 100.0 * sum(d for d, _ in per_task) / total
    rng = random.Random(BOOT_SEED)
    values = []
    for _ in range(BOOT_RESAMPLES):
        diff = runs = 0
        for _ in range(n_tasks):
            d, n = per_task[rng.randrange(n_tasks)]
            diff += d
            runs += n
        values.append(100.0 * diff / runs)
    values.sort()
    return point, r18.percentile(values, 0.025), r18.percentile(values, 0.975)


# -------------------------------------------------------------------- main

def build_report():
    with open(os.path.join(HERE, "oracle_18", "tasks_18.txt"), encoding="utf-8") as handle:
        run_list = [line.strip() for line in handle if line.strip()]
    position = {t: i for i, t in enumerate(run_list, 1)}
    reference = {}
    for row in r14.read_jsonl(os.path.join(HERE, os.pardir, "data", "tasks.jsonl")):
        reference[row.get("instance_id")] = row
    gold_by_task = {t: r14.changed_regions(reference[t]["patch"])[0] for t in run_list}
    n_regions = {t: sum(len(v) for v in gold_by_task[t].values()) for t in run_list}
    manifest = None
    manifest_path = os.path.join(HERE, "oracle_22", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)

    data, stats = {}, {}
    for seed, root, seed_dir, arms in SEEDS:
        for arm in arms:
            base = os.path.join(HERE, root, arm, seed_dir)
            data[(arm, seed)], stats[(arm, seed)] = load_arm(base, arm, seed, run_list, gold_by_task,
                                                             manifest if seed == 3 else None)
    entered = {key: [t for t in run_list if t in data[key] and data[key][t]["infra"] is None] for key in data}

    out = []
    add = out.append

    def table(header, labels_outcomes, keys, runs_of):
        add(("%-38s" % "" + "".join("%-19s" % h for h in header)).rstrip())
        for label, outcome in labels_outcomes:
            cells = []
            for key in keys:
                runs = runs_of(key)
                cells.append(rate(sum(1 for t in runs if outcome(data[key][t])), len(runs)))
            add(("%-38s" % label + "".join("%-19s" % c for c in cells)).rstrip())

    add("RE-DERIVATION OF PRE-REGISTRATION 22 (told where the fix is, second seed: N, ON names, OF names with their"
        " lines,")
    add("OA addresses; seed 3; pooled with seed 2 of pre-registration 18)")
    add(wrap("Written blind from the registration texts of 22, 18 and 14 and the stored runs; loading and scoring"
             " imported from analysis/rederive_14.py and analysis/rederive_18.py (every tool call paired with its own"
             " result). A run is (task, arm, seed)."))
    add("")

    # ---- 1
    add("1. WHICH TASKS OF THE 40 HAVE RUNS OF 22, AND HOW MANY ENTERED")
    for arm in ARMS_22:
        key = (arm, 3)
        st = stats[key]
        have = [t for t in run_list if t in data[key]]
        infra = sorted(t for t in have if data[key][t]["infra"] is not None)
        add(wrap("%s (seed 3): directory %s; result lines %d (distinct tasks %d, off the list %d); runs with a result"
                 " %d of %d; infrastructure failures %d%s; entered %d."
                 % (arm, "present" if st["present"] else "MISSING", st["lines"], st["distinct"], len(st["off_list"]),
                    len(have), len(run_list), len(infra),
                    (" (" + ", ".join("%s: %s" % (t, data[key][t]["infra"]) for t in infra) + ")") if infra else "",
                    len(entered[key])), "  ", "    "))
    sets = [set(t for t in run_list if t in data[(a, 3)]) for a in ARMS_22]
    same = all(s == sets[0] for s in sets)
    add(wrap("The four arms have results for the same tasks: %s." % ("yes" if same else "NO")))
    union = [t for t in run_list if any(t in s for s in sets)]
    add(wrap("Tasks with a run of 22 (%d), by position in the run order: %s"
             % (len(union), ", ".join("%d %s" % (position[t], t) for t in union) or "none"), "", "    "))
    odd = sum(1 for t in union if position[t] % 2 == 1)
    add(wrap("Of them at odd positions %d, at even positions %d. Tasks with no run of 22 (%d): %s"
             % (odd, len(union) - odd, len(run_list) - len(union),
                ", ".join(t for t in run_list if t not in union) or "none"), "", "    "))
    all_four = [t for t in run_list if all(t in entered[(a, 3)] for a in ARMS_22)]
    add("Tasks entered in all four arms of 22: %d." % len(all_four))
    add("")

    # ---- 2
    add("2. PER ARM OF 22 (seed 3), ON THE RUNS THAT ENTERED")
    outcomes = (
        ("RESOLVED", lambda s: s["resolved"]),
        ("shown a changed line (ever)", lambda s: s["shown_line"]),
        ("shown every changed region", lambda s: s["every"]),
        ("final patch overlaps a changed region", lambda s: s["overlap"]),
        ("patch touches every changed region", lambda s: s["touch_every"]),
        ("ended on the context window", lambda s: s["context"]),
    )
    keys22 = [(a, 3) for a in ARMS_22]
    table(ARMS_22, outcomes, keys22, lambda key: entered[key])
    add(("%-38s" % "mean tool calls (trace)"
         + "".join("%-19s" % ("%.2f" % (sum(data[k][t]["calls"] for t in entered[k]) / len(entered[k]))
                               if entered[k] else "n/a") for k in keys22)).rstrip())
    add("How the sessions ended (runner record agent_ending), all runs with a result:")
    for arm in ARMS_22:
        key = (arm, 3)
        endings = {}
        for t in data[key]:
            endings[data[key][t]["ending"]] = endings.get(data[key][t]["ending"], 0) + 1
        add(wrap("%s: %s" % (arm, counted(endings)), "  ", "    "))
    add("")

    # ---- 3
    add(wrap("3. THE RULES L1 TO L7 ON THE RUNS OF 22 (seed 3; first arm minus second, paired by task, on the tasks"
             " where both runs entered; points; 95%% bootstrap interval by task, %s resamples, percentile,"
             " random.Random(%d) afresh for each comparison; exact McNemar p, two-sided; a verdict needs at least %d"
             " tasks)" % ("{:,}".format(BOOT_RESAMPLES), BOOT_SEED, MIN_TASKS), "", "   "))
    res_ = ("RESOLVED", lambda s: s["resolved"])
    ovl = ("final patch overlaps a changed region", lambda s: s["overlap"])
    evr = ("shown every changed region", lambda s: s["every"])
    rules = (
        ("L1", res_, "OA", "N"),
        ("L2", res_, "ON", "N"),
        ("L3", ovl, "OA", "ON"),
        ("L4", ovl, "ON", "N"),
        ("L5", ovl, "OF", "ON"),
        ("L5", ovl, "OA", "OF"),
        ("L6", res_, "OF", "N"),
        ("L6", res_, "OA", "OF"),
        ("L7", evr, "ON", "N"),
        ("L7", evr, "OF", "ON"),
    )
    for name, (label, outcome), first, second in rules:
        a, b = (first, 3), (second, 3)
        tasks = [t for t in run_list if t in entered[a] and t in entered[b]]
        if label != "RESOLVED":
            tasks = [t for t in tasks if gold_by_task[t]]
        shim = {first: data[a], second: data[b]}
        res = r18.compare(shim, tasks, first, second, outcome)
        add(wrap("%s, %s, %s against %s: %s %s, %s %s; difference %s points, interval [%s, %s]; discordant pairs:"
                 " %s only %d, %s only %d; exact McNemar p = %.4g; verdict: \"%s\"."
                 % (name, label, first, second, first, rate(res["first"], res["n"]), second,
                    rate(res["second"], res["n"]), signed(res["point"]), signed(res["low"]), signed(res["high"]),
                    first, res["b"], second, res["c"], res["p"], verdict(res)), "", "    "))
        add(wrap("yes in %s only: %s; yes in %s only: %s" % (first, ", ".join(res["only_first"]) or "none", second,
                                                            ", ".join(res["only_second"]) or "none"), "    ", "      "))
    sens = []
    for first, second in (("ON", "N"), ("OF", "ON")):
        a, b = (first, 3), (second, 3)
        tasks = [t for t in run_list if t in entered[a] and t in entered[b] and gold_by_task[t]]
        res = r18.compare({first: data[a], second: data[b]}, tasks, first, second, lambda s: s["every_14"])
        sens.append("%s against %s: %d against %d of %d, difference %s [%s, %s], p = %.4g"
                    % (first, second, res["first"], res["second"], res["n"], signed(res["point"]),
                       signed(res["low"]), signed(res["high"]), res["p"]))
    add(wrap("Sensitivity (not the rule): L7 with only the first result of a step that holds several tool calls"
             " credited (the loader of rederive_14): " + "; ".join(sens) + ". Per arm, shown every changed region"
             " so counted: " + ", ".join("%s %s" % (arm, rate(sum(data[(arm, 3)][t]["every_14"]
                                                                  for t in entered[(arm, 3)]),
                                                              len(entered[(arm, 3)])))
                                         for arm in ARMS_22) + ".", "", "    "))
    add("")

    # ---- 4
    add("4. THE THREE CUTS OF THE DATED NOTE (EXPLORATORY, no rule; seed 3, runs that entered)")
    add("(a) Runs that end on the context window (runner record agent_ending), per arm")
    for arm in ARMS_22:
        key = (arm, 3)
        runs = entered[key]
        add(wrap("%s: %s; tasks: %s" % (arm, rate(sum(data[key][t]["context"] for t in runs), len(runs)),
                                        ", ".join(t for t in runs if data[key][t]["context"]) or "none"), "  ", "    "))
    add("(b) Among the runs that do not end on the context window: final patch overlaps a changed region; resolved")
    for arm in ARMS_22:
        key = (arm, 3)
        runs = [t for t in entered[key] if not data[key][t]["context"]]
        add(wrap("%s: %d runs; patch overlaps %s; resolved %s"
                 % (arm, len(runs), rate(sum(data[key][t]["overlap"] for t in runs), len(runs)),
                    rate(sum(data[key][t]["resolved"] for t in runs), len(runs))), "  ", "    "))
    add(wrap("(c) Per arm and CHANGED REGION (every region of every GOLD FILE of every run that entered): shown"
             " (a view of the file overlaps it); edited by the final patch (a region of the agent's patch in the same"
             " file intersects it); edited when shown; edited when not shown", "", "    "))
    for label, keep in (("all runs that entered", lambda s: True),
                        ("runs not ending on the context window", lambda s: not s["context"])):
        add("  %s:" % label)
        for arm in ARMS_22:
            key = (arm, 3)
            total = shown = edited = edited_shown = edited_unshown = 0
            for t in entered[key]:
                s = data[key][t]
                if not keep(s):
                    continue
                for sh, ed in zip(s["shown_each"], s["edited_each"]):
                    total += 1
                    shown += sh
                    edited += ed
                    edited_shown += sh and ed
                    edited_unshown += (not sh) and ed
            add(wrap("%s: regions %d; shown %s; edited %s; edited when shown %s; edited when not shown %s"
                     % (arm, total, rate(shown, total), rate(edited, total), rate(edited_shown, shown),
                        rate(edited_unshown, total - shown)), "    ", "      "))
    add("")

    # ---- 5
    add("5. POOLED OVER SEEDS 2 (pre-registration 18) AND 3 (22), ARMS N, ON, OA")
    pool_outcomes = (res_, evr, ovl)

    def pool_block(title, included):
        """included(task, arm) -> list of seeds whose run of that arm counts for the task."""
        add(title)
        add(("%-38s" % "" + "".join("%-19s" % a for a in ARMS_POOL)).rstrip())
        for label, outcome in pool_outcomes:
            cells = []
            for arm in ARMS_POOL:
                hits = runs = 0
                for t in run_list:
                    if label != "RESOLVED" and not gold_by_task[t]:
                        continue
                    for seed in included(t, arm):
                        runs += 1
                        hits += 1 if outcome(data[(arm, seed)][t]) else 0
                cells.append(rate(hits, runs))
            add(("%-38s" % label + "".join("%-19s" % c for c in cells)).rstrip())
        n_tasks = {arm: sum(1 for t in run_list if included(t, arm)) for arm in ARMS_POOL}
        add("  tasks contributing: " + ", ".join("%s %d" % (a, n_tasks[a]) for a in ARMS_POOL))
        for label, outcome in pool_outcomes:
            parts = []
            for first, second in (("OA", "N"), ("ON", "N"), ("OA", "ON")):
                per_task = []
                for t in run_list:
                    if label != "RESOLVED" and not gold_by_task[t]:
                        continue
                    seeds = [s for s in included(t, first) if s in included(t, second)]
                    if not seeds:
                        continue
                    d = sum((1 if outcome(data[(first, s)][t]) else 0) - (1 if outcome(data[(second, s)][t]) else 0)
                            for s in seeds)
                    per_task.append((d, len(seeds)))
                point, low, high = pooled_compare(per_task)
                parts.append("%s minus %s %s [%s, %s] (%d task-runs, %d tasks)"
                             % (first, second, signed(point), signed(low), signed(high),
                                sum(n for _, n in per_task), len(per_task)))
            add(wrap("%s, differences in points: %s" % (label, "; ".join(parts)), "  ", "    "))

    both_seeds = [t for t in run_list
                  if all(t in entered[(a, s)] for a in ARMS_POOL for s in (2, 3))]
    pool_block("(i) On the tasks that have both seeds (all three arms entered at seeds 2 and 3: %d tasks)"
               % len(both_seeds),
               lambda t, arm: [2, 3] if t in both_seeds else [])
    pool_block("(ii) On every task-run (each run that entered, at either seed)",
               lambda t, arm: [s for s in (2, 3) if t in entered[(arm, s)]])
    add("")

    # ---- 6
    add("6. THE TWO SEEDS ON THE SAME TASKS (tasks of 22: those where the arm entered at both seeds; OF has seed 3 only)")
    side_outcomes = outcomes[:5] + (outcomes[5],)
    header = []
    keys = []
    for arm in ARMS_POOL:
        header += ["%s seed 2" % arm, "%s seed 3" % arm]
        keys += [(arm, 2), (arm, 3)]
    tasks_both = {arm: [t for t in run_list if t in entered[(arm, 2)] and t in entered[(arm, 3)]] for arm in ARMS_POOL}
    add("  tasks: " + ", ".join("%s %d" % (a, len(tasks_both[a])) for a in ARMS_POOL))
    add(("%-38s" % "" + "".join("%-19s" % h for h in header)).rstrip())
    for label, outcome in side_outcomes:
        cells = []
        for arm, seed in keys:
            runs = tasks_both[arm]
            cells.append(rate(sum(1 for t in runs if outcome(data[(arm, seed)][t])), len(runs)))
        add(("%-38s" % label + "".join("%-19s" % c for c in cells)).rstrip())
    runs_of = [t for t in run_list if t in entered[("OF", 3)]]
    add(wrap("OF seed 3 on its %d tasks: " % len(runs_of)
             + "; ".join("%s %s" % (label, rate(sum(1 for t in runs_of if o(data[("OF", 3)][t])), len(runs_of)))
                         for label, o in side_outcomes), "  ", "    "))
    add(wrap("Seed 2 on the tasks without a run of 22 (for comparison): "
             + "; ".join("%s resolved %s, every region %s, overlap %s"
                         % (a, rate(sum(data[(a, 2)][t]["resolved"] for t in rest), len(rest)),
                            rate(sum(data[(a, 2)][t]["every"] for t in rest), len(rest)),
                            rate(sum(data[(a, 2)][t]["overlap"] for t in rest), len(rest)))
                         for a in ARMS_POOL
                         for rest in [[t for t in entered[(a, 2)] if t not in tasks_both[a]]]), "  ", "    "))
    add("")

    # ---- 7
    add("7. CHECKS ON THE STORED RUNS")
    for seed, _root, _dir, arms in SEEDS:
        for arm in arms:
            st = stats[(arm, seed)]
            if not st["present"]:
                add("  %s seed %d: no directory" % (arm, seed))
                continue
            add(wrap("%s seed %d: missing traces %s; missing test outputs %s; no runner record %s; runner record names"
                     " another arm %s or seed %s; note not where it should be %s;%s crash %s; patch file and size"
                     " disagree %s; runner ending 'context window' and error text disagree %s; steps with several"
                     " tool calls %d (count of results differs from count of calls in %d); tool results not a JSON"
                     " object %d; harness %s."
                     % (arm, seed, ", ".join(st["no_trace"]) or "none", ", ".join(st["no_test_output"]) or "none",
                        ", ".join(st["no_extra"]) or "none", ", ".join(st["arm_mismatch"]) or "none",
                        ", ".join(st["seed_mismatch"]) or "none", ", ".join(st["note_wrong"]) or "none",
                        (" note md5 differs from the manifest of 22 %s;" % (", ".join(st["md5_wrong"]) or "none"))
                        if seed == 3 and arm != "N" else "",
                        ", ".join(st["crash"]) or "none", ", ".join(st["patch_mismatch"]) or "none",
                        ", ".join(st["ending_vs_error"]) or "none", st["multi"], st["mismatched"], st["unparsed"],
                        counted(st["harness"])), "  ", "    "))
    add("")

    # ---- 8
    add("8. JUDGMENT CALLS")
    notes = [
        "A run enters if its arm has a result line for the task (the last line counts) and the error text is not an"
        " infrastructure failure by the rule of 14 (rederive_14.infra_kind). Each comparison uses the tasks where"
        " both of its runs entered, not the tasks entered in all four arms.",
        "Outcomes as in rederive_18: shown every changed region and shown a changed line count read_file results"
        " and shell views of one file, with every tool call paired with its own result (the registration says the"
        " rules are read from the registered script, which credits only the first result of a step with several"
        " calls; this script does not reproduce that loss, so a difference in L7 can come from it).",
        "Final patch overlaps / touches every changed region: the agent's patch parsed by the same parser, regions"
        " in the same file intersecting; an empty or missing patch is false. Comparisons on these and on shown every"
        " region use tasks with at least one GOLD FILE.",
        "Verdict: 'more' if the lower bound is strictly above 0, 'fewer' if the upper bound strictly below; with"
        " fewer than 34 paired tasks the verdict reads 'no verdict (too few tasks)' and the numbers are printed.",
        "Ending on the context window: the runner record's agent_ending is 'context window' (cross-checked against"
        " the error text of the result line, section 7).",
        "Cut (c) counts CHANGED REGIONS (hunk regions of the reference patch, before the merging into places used"
        " by the notes), summed over runs; 'edited when shown' is over the shown regions, 'when not shown' over the"
        " others. It is printed for all entered runs and for the runs that do not end on the context window.",
        "Pooling: a task-run is (task, seed). (i) uses the tasks where N, ON and OA all entered at both seeds, so"
        " each task gives two runs per arm. (ii) uses every entered run; a difference uses the (task, seed) pairs"
        " where both arms entered. A difference is the pooled share of the first arm minus that of the second, in"
        " points; the bootstrap resamples tasks with replacement (a task's runs at both seeds together),"
        " random.Random(0) afresh for each difference, 2,000 resamples, percentile interval of the ratio of sums.",
        "Section 6 restricts each arm to the tasks where it entered at both seeds, so the two columns of an arm are"
        " the same tasks.",
        "Note checks: N must carry no note, the other arms the note once in the first message"
        " (note_in_first_message); for seed 3 the note md5 recorded by the runner is compared with"
        " analysis/oracle_22/manifest.json.",
    ]
    for number, note in enumerate(notes, 1):
        add(wrap(note, "%2d. " % number, "    "))
    add("")

    # ---- per task
    add("PER TASK OF 22 (position in the run order, k CHANGED REGIONS; per run: r RESOLVED, e shown every region,"
        " o patch overlaps, w ended on the context window)")
    for task in union:
        parts = []
        for arm, seed in [("N", 2), ("N", 3), ("ON", 2), ("ON", 3), ("OF", 3), ("OA", 2), ("OA", 3)]:
            s = data[(arm, seed)].get(task)
            if s is None:
                parts.append("%s%d -" % (arm, seed))
            else:
                parts.append("%s%d %d%d%d%d" % (arm, seed, s["resolved"], s["every"], s["overlap"], s["context"]))
        add(("  %2d %-14s k=%-3d %s" % (position[task], task, n_regions[task], " ".join(parts))).rstrip())
    return ("\n".join(out) + "\n").replace("\xa0", " ")


def main(argv):
    write = "--no-write" not in argv[1:]
    if [a for a in argv[1:] if a != "--no-write"]:
        sys.stderr.write("usage: rederive_22.py [--no-write]\n")
        return 2
    report = build_report()
    if write:
        with open(os.path.join(HERE, "results", "rederive_22.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
