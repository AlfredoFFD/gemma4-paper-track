#!/usr/bin/env python3
"""Independent re-derivation of pre-registration 23 (whole runs in which the graph's own answers are pushed at the
agent, as names PH or with addresses PE) from the stored runs.

Usage:  py -I -X utf8 analysis/rederive_23.py [--pe DIR] [--ph DIR] [--control DIR] [--no-write]

Defaults: --pe analysis/results/23/PE/seed2, --ph analysis/results/23/PH/seed2, --control analysis/results/14/N/seed1
(the stored N run of pre-registration 14, another launch). Each is a harness results directory (task_results.jsonl,
extra.jsonl, patches/, traces/). Also read: analysis/results/14/validate/tasks_ok.txt (the 103 tasks in 14's order)
and data/tasks.jsonl (the reference patches). The report is printed; unless --no-write is given, and only when the two
arm directories are the registered defaults, the same text is written to analysis/results/rederive_23.txt (LF line
endings). If a run directory is missing, one line says so and the script stops (exit code 1).

Written blind from the text of prereg/23-whole-runs-graph-answers-pushed.md, without sight of the registered analysis
(analyze_23.py, analyze_14.py, analyze_18.py, explore_push_23.py) or of any of their outputs. The format of what the
runner stores was learned from analysis/modal_h/push_23.py and the runner; every number is computed from the stored
runs. Reused by import, from the independent second scripts written blind before: analysis/rederive_14.py (patch parser
and CHANGED REGIONS, views of a file, T_SHOWN, the infrastructure-failure rule, error kinds) and analysis/rederive_18.py
(every tool call paired with its own result, "shown every changed region", "patch touches every changed region", the
percentile, the exact McNemar p). Everything particular to 23 is written here. Standard library only. The script reads
whatever tasks are stored: with one shard it prints every number and no verdict.
"""
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rederive_14 as r14  # noqa: E402  (independent second script of 14)
import rederive_18 as r18  # noqa: E402  (independent second script of 18)

ARMS = ("PE", "PH")
CONTROL = "N14"
DEFAULTS = {"PE": os.path.join(HERE, "results", "23", "PE", "seed2"),
            "PH": os.path.join(HERE, "results", "23", "PH", "seed2"),
            CONTROL: os.path.join(HERE, "results", "14", "N", "seed1")}
TASK_LIST = os.path.join(HERE, "results", "14", "validate", "tasks_ok.txt")
OUT = os.path.join(HERE, "results", "rederive_23.txt")
KEY = "code_graph"
GRAPH_TOOLS = ("get_code_neighbors", "get_code_subgraph", "search_similar_code")
MIN_TASKS = 80
MIN_A1_TASKS = 20
GATE_SHARE = 0.80
UPTAKE_CALLS = 3
SHOWN_CALLS = 8
BOOT_RESAMPLES = 2000
BOOT_SEED = 0
INF = float("inf")
CONTEXT = "context window"
wrap = r18.wrap
rate = r18.rate
signed = r18.signed
counted = r18.counted
median = r18.median


class MissingRuns(Exception):
    pass


# ------------------------------------------------------------------ helpers

def mean(values):
    return sum(values) / len(values) if values else float("nan")


def num(value, digits=2):
    if value != value:  # nan
        return "n/a"
    return ("%." + str(digits) + "f") % value


def boot(diffs, scale=1.0):
    """95% percentile interval of the mean of per-task differences: tasks resampled with replacement (randrange over
    the tasks in run-list order), 2,000 resamples, random.Random(0) started afresh for each comparison."""
    n = len(diffs)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    means = []
    for _ in range(BOOT_RESAMPLES):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(scale * total / n)
    means.sort()
    return (r18.percentile(means, 0.025), r18.percentile(means, 0.975))


def start_argument(arguments):
    """(present, misspelled): the call gives a start_line argument under any spelling (letters only, lower case:
    'startline'); it gives one under a name that is not exactly start_line."""
    present = misspelled = False
    for key in arguments:
        if isinstance(key, str) and re.sub(r"[^a-z]", "", key.lower()) == "startline":
            present = True
            if key != "start_line":
                misspelled = True
    return present, misspelled


def parse_range(text):
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", str(text or ""))
    if not match:
        return None
    low, high = int(match.group(1)), int(match.group(2))
    return (min(low, high), max(low, high))


def neighbor_names(value):
    """[(source, name)] of a code_graph value, in order."""
    out = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        for entry in item.get("neighbors") or []:
            if isinstance(entry, dict):
                out.append((item.get("node"), entry.get("name")))
    return out


def trace_entries(value):
    """[dict(source, name, file, lines)] of a code_graph value as the agent received it."""
    out = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        for entry in item.get("neighbors") or []:
            if isinstance(entry, dict):
                out.append({"source": item.get("node"), "name": entry.get("name"), "file": entry.get("file"),
                            "lines": entry.get("lines"), "fields": tuple(sorted(entry))})
    return out


# ------------------------------------------------------------------ loading

def load_dir(base, label, run_list, gold_by_task, checks):
    """{task: run} for one results directory; the last result line of a task counts, likewise in extra.jsonl."""
    results_path = os.path.join(base, "task_results.jsonl")
    if not os.path.isfile(results_path):
        raise MissingRuns("%s: no stored runs at %s (task_results.jsonl is missing)" % (label, base))
    last = {}
    for row in r14.read_jsonl(results_path):
        last[row.get("instance_id")] = row
    extra = {}
    extra_path = os.path.join(base, "extra.jsonl")
    if os.path.isfile(extra_path):
        for row in r14.read_jsonl(extra_path):
            extra[row.get("task")] = row
    else:
        checks.append("%s: extra.jsonl is missing" % label)

    def note(text):
        checks.append("%s: %s" % (label, text))

    off = sorted(t for t in last if t not in run_list)
    if off:
        note("result lines for tasks off the task list: " + ", ".join(off))
    runs = {}
    for task in run_list:
        if task not in last:
            continue
        row = last[task]
        gold = gold_by_task[task]
        rec = extra.get(task)
        if not isinstance(rec, dict):
            note("%s: no runner record" % task)
            rec = {}
        trace_path = os.path.join(base, "traces", "trace_%s.json" % task)
        calls = []
        if os.path.exists(trace_path):
            calls, _multi, _unparsed, mismatched = r18.load_calls_paired(trace_path)
            if mismatched:
                note("%s: %d steps whose count of results differs from their count of calls" % (task, mismatched))
        else:
            note("%s: no trace" % task)

        # READs and the pushed lists as the trace records them
        reads = []
        trace_pushes = []
        misspelled_other_start = 0
        written = set()  # files written by an ok write_file call so far (for the OWN FILE sensitivity of A2)
        for index, (name, arguments, result) in enumerate(calls, 1):
            if name == "write_file" and result.get("status") == "ok" and isinstance(arguments.get("filepath"), str):
                written.add(r14.norm_path(arguments["filepath"]))
            if name != "read_file" or result.get("status") != "ok":
                if KEY in result:
                    note("%s: call %d (%s) is not an ok READ but its result carries the key" % (task, index, name))
                continue
            path = result.get("filepath")
            if not isinstance(path, str):
                path = arguments.get("filepath")
            path = r14.norm_path(path) if isinstance(path, str) else ""
            first, last_line = result.get("start_line"), result.get("end_line")
            if not (r14.is_int(first) and r14.is_int(last_line)):
                first = last_line = None
            present, misspelled = start_argument(arguments)
            if not present:
                start = None
            elif first is not None:
                start = first
                if misspelled and first != 1:
                    misspelled_other_start += 1
            else:
                start = 1 if misspelled else (arguments.get("start_line") if r14.is_int(arguments.get("start_line"))
                                              else None)
            lines = (last_line - first + 1) if first is not None and last_line >= first else 0
            read = {"idx": index, "file": path, "start": start, "first": first, "last": last_line, "lines": lines,
                    "misspelled": misspelled, "own": path in written}
            reads.append(read)
            if KEY in result:
                trace_pushes.append((index, path, result[KEY]))
        if misspelled_other_start:
            note("%s: %d READs with a misspelled start argument returned a start other than 1"
                 % (task, misspelled_other_start))

        # the pushed lists of the runner record, matched in order to those of the trace, checked by name
        record_pushes = rec.get("pushes") or []
        if not isinstance(record_pushes, list):
            record_pushes = []
        if len(record_pushes) != len(trace_pushes):
            note("%s: %d pushed lists in the trace, %d in the runner record"
                 % (task, len(trace_pushes), len(record_pushes)))
        pushes = []
        off_index = []
        for k, (index, path, value) in enumerate(trace_pushes):
            got = trace_entries(value)
            stored = record_pushes[k] if k < len(record_pushes) and isinstance(record_pushes[k], dict) else None
            entries = []
            if stored is not None:
                stored_entries = [e for e in stored.get("entries") or [] if isinstance(e, dict)]
                if [(e.get("node"), e.get("name")) for e in stored_entries] != [(g["source"], g["name"]) for g in got]:
                    note("%s: pushed list at call %d: names in the trace differ from the runner record" % (task, index))
                if r14.norm_path(str(stored.get("file") or "")) != path:
                    note("%s: pushed list at call %d: the runner record names file %s, the READ %s"
                         % (task, index, stored.get("file"), path))
                if stored.get("tool_result") != index:
                    off_index.append("%d->%s" % (index, stored.get("tool_result")))
                for g, e in zip(got, stored_entries):
                    if g["file"] is not None and (r14.norm_path(str(g["file"])) != r14.norm_path(str(e.get("file")))
                                                  or str(g["lines"]) != str(e.get("lines"))):
                        note("%s: pushed list at call %d: an entry's address in the trace differs from the runner"
                             " record" % (task, index))
                for e in stored_entries:
                    entries.append({"name": e.get("name"), "file": r14.norm_path(str(e.get("file") or "")),
                                    "range": parse_range(e.get("lines"))})
            else:
                for g in got:  # no runner record for this push: the addresses of the trace, if it holds them
                    entries.append({"name": g["name"], "file": r14.norm_path(str(g["file"])) if g["file"] else None,
                                    "range": parse_range(g["lines"])})
            fields = sorted({f for g in got for f in g["fields"]})
            pushes.append({"idx": index, "file": path, "entries": entries, "n_trace": len(got),
                           "chars": len(json.dumps(value, ensure_ascii=False)), "fields": fields})
        if off_index:
            note("%s: the runner's tool_result counter differs from the trace call index (call->counter: %s)"
                 % (task, ", ".join(off_index)))

        # A1 READs: per file that holds an entry of a pushed list, the run's first READ of that file, if it is made
        # after the earliest push listing the file (no READ of the file before it, which includes the READ that
        # carried the push)
        listed_at = {}
        for push in pushes:
            for entry in push["entries"]:
                if entry["file"]:
                    listed_at.setdefault(entry["file"], push["idx"])
        first_read = {}
        for read in reads:
            first_read.setdefault(read["file"], read)
        a1 = []
        for path, pushed_idx in listed_at.items():
            read = first_read.get(path)
            if read is not None and read["idx"] > pushed_idx:
                a1.append(read)
        a1.sort(key=lambda r: r["idx"])

        # uptake: per pushed entry, a READ of its file within the three calls after the push
        uptake = []
        regions_of = gold
        for push in pushes:
            for entry in push["entries"]:
                hit = None
                for read in reads:
                    if push["idx"] < read["idx"] <= push["idx"] + UPTAKE_CALLS and read["file"] == entry["file"]:
                        hit = read
                        break
                rng = entry["range"]
                uptake.append({
                    "other_file": entry["file"] != push["file"],
                    "taken": hit is not None,
                    "inside": (hit is not None and rng is not None and hit["start"] is not None
                               and rng[0] <= hit["start"] <= rng[1]),
                    "holds": rng is not None and r14.overlaps(regions_of.get(entry["file"]), rng[0], rng[1]),
                    "contains": rng is not None and any(rng[0] <= lo and hi <= rng[1]
                                                        for lo, hi in regions_of.get(entry["file"]) or ()),
                    "has_range": rng is not None,
                })

        # views, patch, outcomes of 14 and 18
        views, _uncounted = r14.session_views(calls, gold)
        regions = r18.region_list(gold)
        each = r18.first_shown_each(views, regions)
        agent_regions = {}
        patch_path = os.path.join(base, "patches", "%s.patch" % task)
        if os.path.exists(patch_path):
            with open(patch_path, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace")
            if text.strip():
                agent_regions, _facts = r14.changed_regions(text)
        ending = str(rec.get("agent_ending")) if rec else "no runner record"
        runs[task] = {
            "repo": row.get("repo") or rec.get("repo") or "?",
            "resolved": row.get("resolved") is True,
            "error": row.get("error"),
            "infra": r14.infra_kind(row.get("error")),
            "ending": ending,
            "ctx": ending == CONTEXT,
            "ctx_text": r14.error_kind(row.get("error")) == CONTEXT,
            "calls": len(calls),
            "graph_calls": sum(1 for c in calls if c[0] in GRAPH_TOOLS),
            "reads": reads,
            "n_reads": len(reads),
            "lines": sum(r["lines"] for r in reads),
            "lines_not_own": sum(r["lines"] for r in reads if not r["own"]),
            "pushes": pushes,
            "entries": sum(len(p["entries"]) for p in pushes),
            "chars": sum(p["chars"] for p in pushes),
            "a1": a1,
            "uptake": uptake,
            "has_gold": bool(gold),
            "every": bool(regions) and all(v < INF for v in each),
            "t": r14.first_shown(views, gold),
            "overlap": r14.patch_overlaps(agent_regions, gold),
            "touch_every": r18.touches_every(agent_regions, regions),
            "harness": "%s [%s]" % (rec.get("harness"), rec.get("harness_variant")),
            "launch": str(rec.get("launch")),
            "shard": str(rec.get("shard")),
            "scripted": rec.get("scripted_model"),
            "condition": rec.get("condition", rec.get("arm")),
            "seed": rec.get("seed"),
            "rec_pushed_reads": rec.get("pushed_reads"),
            "rec_push_chars": rec.get("push_chars"),
            "rec_fields": sorted({tuple(p.get("agent_fields") or ()) for p in record_pushes if isinstance(p, dict)}),
        }
    return runs


# ------------------------------------------------------------------ comparisons

def compare_binary(data, tasks, first, second, outcome):
    pairs = [(1 if outcome(data[first][t]) else 0, 1 if outcome(data[second][t]) else 0) for t in tasks]
    diffs = [a - b for a, b in pairs]
    low, high = boot(diffs, 100.0)
    b = sum(1 for a, s in pairs if a == 1 and s == 0)
    c = sum(1 for a, s in pairs if a == 0 and s == 1)
    return {"n": len(pairs), "first": sum(a for a, _ in pairs), "second": sum(s for _, s in pairs),
            "point": 100.0 * sum(diffs) / len(diffs) if diffs else float("nan"), "low": low, "high": high,
            "b": b, "c": c, "p": r18.mcnemar_exact(b, c),
            "only_first": [t for t, (a, s) in zip(tasks, pairs) if a == 1 and s == 0],
            "only_second": [t for t, (a, s) in zip(tasks, pairs) if a == 0 and s == 1]}


def word(low, high, above, below, neither):
    if low != low:
        return neither
    if low > 0 and above is not None:
        return above
    if high < 0 and below is not None:
        return below
    return neither


# ------------------------------------------------------------------ report

def build_report(dirs):
    with open(TASK_LIST, encoding="utf-8") as handle:
        run_list = [line.strip() for line in handle if line.strip()]
    position = {t: i for i, t in enumerate(run_list, 1)}
    reference = {}
    for row in r14.read_jsonl(os.path.join(HERE, os.pardir, "data", "tasks.jsonl")):
        reference[row.get("instance_id")] = row
    gold_by_task = {t: r14.changed_regions(reference[t]["patch"])[0] for t in run_list}

    checks = []
    data = {}
    for label in ARMS + (CONTROL,):
        data[label] = load_dir(dirs[label], label, run_list, gold_by_task, checks)
    entered = {label: [t for t in run_list if t in data[label] and data[label][t]["infra"] is None]
               for label in data}
    both = [t for t in run_list if t in entered["PE"] and t in entered["PH"]]
    n_both = len(both)
    enough = n_both >= MIN_TASKS

    out = []
    add = out.append
    add("RE-DERIVATION OF PRE-REGISTRATION 23 (whole runs, the graph's own answers pushed: PE with addresses, PH as"
        " names)")
    add(wrap("Written blind from the registration text and the stored runs. A run is (task, arm). Rules compare the"
             " two runs of a task on the tasks where both entered; 95%% bootstrap by task, 2,000 resamples, seed 0;"
             " a verdict needs at least %d such tasks and the gate G0 met." % MIN_TASKS))
    add("Inputs: " + "; ".join("%s %s" % (label, os.path.relpath(dirs[label], os.path.join(HERE, os.pardir))
                                          .replace("\\", "/")) for label in ARMS + (CONTROL,)))
    add("")

    # ---- 1
    add("1. RUNS PER ARM, ENTERED, HARNESS")
    add("Task list (analysis/results/14/validate/tasks_ok.txt): %d tasks." % len(run_list))
    for label in ARMS + (CONTROL,):
        runs = data[label]
        odd = sum(1 for t in runs if position[t] % 2 == 1)
        even = len(runs) - odd
        infra = [t for t in run_list if t in runs and runs[t]["infra"] is not None]
        missing = [t for t in run_list if t not in runs]
        add(wrap("%s: runs with a result %d (at odd positions of the order %d of %d, at even positions %d of %d);"
                 " failures outside the agent %d%s; entered %d; no result: %s."
                 % (label, len(runs), odd, (len(run_list) + 1) // 2, even, len(run_list) // 2, len(infra),
                    (" (" + ", ".join("%s: %s" % (t, runs[t]["infra"]) for t in infra) + ")") if infra else "",
                    len(entered[label]),
                    (str(len(missing)) + " tasks" + (" (" + ", ".join(missing) + ")" if len(missing) <= 12 else ""))
                    if missing else "none"), "  ", "    "))
        harness = {}
        launches = {}
        for t in runs:
            harness[runs[t]["harness"]] = harness.get(runs[t]["harness"], 0) + 1
            key = "%s (shard %s)" % (runs[t]["launch"], runs[t]["shard"])
            launches[key] = launches.get(key, 0) + 1
        add(wrap("harness recorded: " + counted(harness), "    ", "      "))
        add(wrap("launches: " + counted(launches), "    ", "      "))
        scripted = sum(1 for t in runs if runs[t]["scripted"] is not False)
        add("    runs not marked scripted_model false: %d" % scripted)
    same = {label: sorted({data[label][t]["harness"] for t in data[label]}) for label in data}
    add(wrap("Harness of PE and PH equal to that of the control run: %s."
             % ("yes" if same["PE"] == same["PH"] == same[CONTROL] else "NO (see above)")))
    add("Tasks where both PE and PH entered: %d%s." % (n_both, "" if enough else
                                                      " (fewer than %d: no verdict below)" % MIN_TASKS))
    add("")

    # ---- 2
    add("2. G0, THE GATE (no verdict): entered runs with at least one pushed list")
    gate = {}
    for arm in ARMS:
        runs = [data[arm][t] for t in entered[arm]]
        hit = sum(1 for r in runs if r["pushes"])
        gate[arm] = hit / len(runs) if runs else float("nan")
        lists = [len(r["pushes"]) for r in runs]
        entries = [r["entries"] for r in runs]
        chars = [r["chars"] for r in runs]
        add(wrap("%s: %s; pushed lists per run median %s, mean %s (in all %d); entries per run median %s, mean %s"
                 " (in all %d; per list %s); characters received per run median %s, mean %s."
                 % (arm, rate(hit, len(runs)), "%g" % median(lists) if lists else "n/a", num(mean(lists)), sum(lists),
                    "%g" % median(entries) if entries else "n/a", num(mean(entries)), sum(entries),
                    num(sum(entries) / sum(lists)) if sum(lists) else "n/a",
                    "%g" % median(chars) if chars else "n/a", num(mean(chars))), "  ", "    "))
    no_push = all(not data[a][t]["pushes"] for a in ARMS for t in data[a])
    gate_met = all(gate[a] == gate[a] and gate[a] >= GATE_SHARE for a in ARMS)
    if no_push:
        add(wrap("No run of either arm carries a pushed list (no result in the traces has the key %s): the gate and"
                 " A1 have nothing to count; the gate is not met and no rule is read." % KEY, "  ", "    "))
    else:
        add("  Gate: %s (both shares must be at least %d%%)." % ("met" if gate_met else "NOT met: the push did not reach"
                                                                 " enough runs; the rules are not read",
                                                                 round(100 * GATE_SHARE)))
    verdicts_on = enough and gate_met

    def why_none():
        reasons = []
        if not gate_met:
            reasons.append("gate G0 not met")
        if not enough:
            reasons.append("%d tasks where both entered, fewer than %d" % (n_both, MIN_TASKS))
        return "no verdict (" + "; ".join(reasons) + ")"
    add("")

    # ---- 3
    add("3. A1, THE ADDRESS AT THE FIRST READ (PE minus PH, share of a run's A1 READs that start past line 1)")
    shares = {arm: {} for arm in ARMS}
    for arm in ARMS:
        for t in entered[arm]:
            a1 = data[arm][t]["a1"]
            if a1:
                shares[arm][t] = sum(1 for r in a1 if r["start"] is not None and r["start"] > 1) / len(a1)
    a1_tasks = [t for t in both if t in shares["PE"] and t in shares["PH"]]
    for arm in ARMS:
        pool = [r for t in entered[arm] for r in data[arm][t]["a1"]]
        past = sum(1 for r in pool if r["start"] is not None and r["start"] > 1)
        nostart = sum(1 for r in pool if r["start"] is None)
        add(wrap("%s: A1 READs pooled: past line 1 %s (no start argument %d, start 1 %d); runs with at least one A1"
                 " READ %d of %d entered; mean per-run share over those runs %s."
                 % (arm, rate(past, len(pool)), nostart, len(pool) - past - nostart, len(shares[arm]),
                    len(entered[arm]), num(100 * mean(list(shares[arm].values()))) + "%" if shares[arm] else "n/a"),
                 "  ", "    "))
    diffs = [shares["PE"][t] - shares["PH"][t] for t in a1_tasks]
    low, high = boot(diffs, 100.0)
    if not a1_tasks:
        add("  No task where both runs have an A1 READ: A1 has nothing to compare.")
    add(wrap("Tasks where both runs have at least one A1 READ: %d (at least %d needed). Mean per-task share: PE %s,"
             " PH %s. Mean difference PE minus PH %s points, interval [%s, %s]."
             % (len(a1_tasks), MIN_A1_TASKS,
                num(100 * mean([shares["PE"][t] for t in a1_tasks])) + "%" if a1_tasks else "n/a",
                num(100 * mean([shares["PH"][t] for t in a1_tasks])) + "%" if a1_tasks else "n/a",
                signed(100 * mean(diffs)) if diffs else "n/a", signed(low) if diffs else "n/a",
                signed(high) if diffs else "n/a"), "  ", "    "))
    if verdicts_on and len(a1_tasks) >= MIN_A1_TASKS:
        a1_verdict = word(low, high, "an address moves the read", None, "not detected")
    elif verdicts_on:
        a1_verdict = "no verdict (%d tasks with an A1 READ in both, fewer than %d)" % (len(a1_tasks), MIN_A1_TASKS)
    else:
        a1_verdict = why_none()
    add("  Verdict A1: \"%s\"." % a1_verdict)
    add("")

    # ---- 4
    add("4. A2, READING (LINES READ per run, PE minus PH, paired by task)")
    for arm in ARMS:
        runs = [data[arm][t] for t in entered[arm]]
        add("  %s, %d entered runs: LINES READ mean %s, median %s; READs per run mean %s, median %s."
            % (arm, len(runs), num(mean([r["lines"] for r in runs])),
               "%g" % median([r["lines"] for r in runs]) if runs else "n/a", num(mean([r["n_reads"] for r in runs])),
               "%g" % median([r["n_reads"] for r in runs]) if runs else "n/a"))
    d_lines = [data["PE"][t]["lines"] - data["PH"][t]["lines"] for t in both]
    d_reads = [data["PE"][t]["n_reads"] - data["PH"][t]["n_reads"] for t in both]
    lo2, hi2 = boot(d_lines)
    lo2r, hi2r = boot(d_reads)
    a2_verdict = word(lo2, hi2, None, "an address saves reading", "not detected") if verdicts_on else why_none()
    add(wrap("On the %d tasks where both entered: PE mean %s, PH mean %s; mean difference %s lines, interval [%s, %s];"
             " READs per run: mean difference %s, interval [%s, %s]."
             % (n_both, num(mean([data["PE"][t]["lines"] for t in both])),
                num(mean([data["PH"][t]["lines"] for t in both])), num(mean(d_lines)), num(lo2), num(hi2),
                num(mean(d_reads)), num(lo2r), num(hi2r)), "  ", "    "))
    d_own = [data["PE"][t]["lines_not_own"] - data["PH"][t]["lines_not_own"] for t in both]
    lo2o, hi2o = boot(d_own)
    add(wrap("Sensitivity, not the rule: without READs of an OWN FILE (a file the run had written earlier with an ok"
             " write_file call): PE mean %s, PH mean %s; mean difference %s lines, interval [%s, %s]."
             % (num(mean([data["PE"][t]["lines_not_own"] for t in both])),
                num(mean([data["PH"][t]["lines_not_own"] for t in both])), num(mean(d_own)), num(lo2o), num(hi2o)),
             "  ", "    "))
    add("  Verdict A2: \"%s\"." % a2_verdict)
    add("")

    # ---- 5
    add("5. A3, RESOLVED, PE AGAINST PH")
    res = compare_binary(data, both, "PE", "PH", lambda s: s["resolved"])
    a3_verdict = word(res["low"], res["high"], "more", "fewer", "no detectable difference") if verdicts_on else why_none()
    add(wrap("PE %s, PH %s; difference %s points, interval [%s, %s]; discordant pairs: PE only %d, PH only %d; exact"
             " McNemar p = %.4g. Verdict A3: \"%s\"."
             % (rate(res["first"], res["n"]), rate(res["second"], res["n"]), signed(res["point"]),
                signed(res["low"]), signed(res["high"]), res["b"], res["c"], res["p"], a3_verdict), "  ", "    "))
    add(wrap("resolved in PE only: %s" % (", ".join(res["only_first"]) or "none"), "    ", "      "))
    add(wrap("resolved in PH only: %s" % (", ".join(res["only_second"]) or "none"), "    ", "      "))
    if verdicts_on:
        a1_met = a1_verdict == "an address moves the read"
        a2_met = a2_verdict == "an address saves reading"
        a3_met = a3_verdict in ("more", "fewer")
        fixed = a1_met or a2_met
        add(wrap("The reading fixed in advance (\"Pushed with addresses, the graph's own answers change what a run reads,"
                 " and not detectably what it resolves\") %s: A1 %s, A2 %s, A3 %s."
                 % ("APPLIES" if fixed and not a3_met else "does not apply", "met" if a1_met else "not met",
                    "met" if a2_met else "not met", "met" if a3_met else "not met"), "  ", "    "))
    else:
        add("  The reading fixed in advance is not decided: %s." % why_none()[len("no verdict ("):-1])
    add("")

    # ---- 6
    add(wrap("6. P1, P2, H1 AGAINST THE STORED N RUN OF 14 (seed 1; ANOTHER LAUNCH: no verdict), on the tasks where the"
             " arm and that N run both entered", "", "   "))
    for name, arm in (("P1", "PE"), ("P2", "PH")):
        tasks = [t for t in run_list if t in entered[arm] and t in entered[CONTROL]]
        r = compare_binary(data, tasks, arm, CONTROL, lambda s: s["resolved"])
        add(wrap("%s, resolved, %s against N of 14 (%d tasks): %s %s, N %s; difference %s points, interval [%s, %s];"
                 " discordant: %s only %d, N only %d; exact McNemar p = %.4g. (Read as the rule would: \"%s\"; not a"
                 " verdict.)"
                 % (name, arm, r["n"], arm, rate(r["first"], r["n"]), rate(r["second"], r["n"]), signed(r["point"]),
                    signed(r["low"]), signed(r["high"]), arm, r["b"], r["c"], r["p"],
                    word(r["low"], r["high"], "more", "fewer", "no detectable difference")), "  ", "    "))
    for arm in ARMS:
        tasks = [t for t in run_list if t in entered[arm] and t in entered[CONTROL]]
        r = compare_binary(data, tasks, arm, CONTROL, lambda s: s["ctx"])
        add(wrap("H1, runs that end on the context window, %s minus N of 14 (%d tasks): %s %s, N %s; difference %s"
                 " points, interval [%s, %s]; discordant: %s only %d, N only %d; exact McNemar p = %.4g. (Read as the"
                 " rule would: \"%s\"; not a verdict.)"
                 % (arm, r["n"], arm, rate(r["first"], r["n"]), rate(r["second"], r["n"]), signed(r["point"]),
                    signed(r["low"]), signed(r["high"]), arm, r["b"], r["c"], r["p"],
                    word(r["low"], r["high"], "harm", None, "no detectable harm")), "  ", "    "))
    r = compare_binary(data, both, "PE", "PH", lambda s: s["ctx"])
    add(wrap("Beside it (no rule): context-window endings PE minus PH (%d tasks): PE %s, PH %s; difference %s points,"
             " interval [%s, %s]; exact McNemar p = %.4g."
             % (r["n"], rate(r["first"], r["n"]), rate(r["second"], r["n"]), signed(r["point"]), signed(r["low"]),
                signed(r["high"]), r["p"]), "  ", "    "))
    add("")

    # ---- 7
    add("7. WITHOUT A RULE (all entered runs of each arm)")
    add("Uptake: pushed entries whose file is READ within the %d calls after the push" % UPTAKE_CALLS)
    for arm in ARMS:
        ups = [u for t in entered[arm] for u in data[arm][t]["uptake"]]
        for label, subset in (("all entries", ups), ("entries in another file than the READ that got the push",
                                                      [u for u in ups if u["other_file"]])):
            taken = [u for u in subset if u["taken"]]
            add(wrap("%s, %s: %d; file READ within %d calls %s; of those, the READ starts inside the pushed range %s;"
                     " pushed range holds (overlaps) a changed region: all %s, taken up %s (contains a whole changed"
                     " region: all %d, taken up %d)."
                     % (arm, label, len(subset), UPTAKE_CALLS, rate(len(taken), len(subset)),
                        rate(sum(u["inside"] for u in taken), len(taken)),
                        rate(sum(u["holds"] for u in subset), len(subset)),
                        rate(sum(u["holds"] for u in taken), len(taken)),
                        sum(u["contains"] for u in subset), sum(u["contains"] for u in taken)), "  ", "    "))
        no_range = sum(1 for u in ups if not u["has_range"])
        if no_range:
            add("  %s: entries without a readable line range: %d" % (arm, no_range))

    def row(label, values):
        add(("  %-46s%-26s%-26s%s" % ((label,) + tuple(values))).rstrip())

    labels = ARMS + (CONTROL,)
    row("", labels)

    def gold_rate(outcome):
        vals = []
        for lab in labels:
            runs = [data[lab][t] for t in entered[lab] if data[lab][t]["has_gold"]]
            vals.append(rate(sum(1 for r in runs if outcome(r)), len(runs)))
        return vals

    row("RESOLVED", [rate(sum(data[lab][t]["resolved"] for t in entered[lab]), len(entered[lab])) for lab in labels])
    row("shown every changed region", gold_rate(lambda r: r["every"]))
    row("shown a changed line within %d calls" % SHOWN_CALLS, gold_rate(lambda r: r["t"] <= SHOWN_CALLS))
    row("final patch overlaps a changed region", gold_rate(lambda r: r["overlap"]))
    row("final patch touches every changed region", gold_rate(lambda r: r["touch_every"]))
    row("context-window ending (runner record)",
        [rate(sum(data[lab][t]["ctx"] for t in entered[lab]), len(entered[lab])) for lab in labels])
    row("  the same by the error text",
        [rate(sum(data[lab][t]["ctx_text"] for t in entered[lab]), len(entered[lab])) for lab in labels])
    for key, label in (("calls", "tool calls"), ("n_reads", "READs"), ("lines", "LINES READ"),
                       ("graph_calls", "graph-tool calls")):
        row(label + " per run: mean / median",
            ["%s / %s" % (num(mean([data[lab][t][key] for t in entered[lab]])),
                          "%g" % median([data[lab][t][key] for t in entered[lab]]) if entered[lab] else "n/a")
             for lab in labels])
    row("runs with a graph-tool call",
        [rate(sum(1 for t in entered[lab] if data[lab][t]["graph_calls"]), len(entered[lab])) for lab in labels])
    row("A1 READs per run: mean", [num(mean([len(data[lab][t]["a1"]) for t in entered[lab]])) for lab in labels])
    add("How runs ended (runner record agent_ending), all runs with a result:")
    for lab in labels:
        endings = {}
        for t in data[lab]:
            endings[data[lab][t]["ending"]] = endings.get(data[lab][t]["ending"], 0) + 1
        add(wrap("%s: %s" % (lab, counted(endings)), "  ", "    "))
    add("Error text of the result line (outcomes, not exclusions), all runs with a result:")
    for lab in labels:
        kinds = {}
        for t in data[lab]:
            kind = r14.error_kind(data[lab][t]["error"])
            kinds[kind] = kinds.get(kind, 0) + 1
        add(wrap("%s: %s" % (lab, counted(kinds)), "  ", "    "))
    add("By repository (entered runs): resolved; pushed lists per run; A1 READs past line 1; LINES READ per run")
    repos = sorted({data[lab][t]["repo"] for lab in labels for t in entered[lab]})
    for repo in repos:
        parts = []
        for lab in labels:
            runs = [data[lab][t] for t in entered[lab] if data[lab][t]["repo"] == repo]
            pool = [r for run in runs for r in run["a1"]]
            parts.append("%s resolved %s, lists %s, A1 past 1 %s, lines %s"
                         % (lab, rate(sum(r["resolved"] for r in runs), len(runs)),
                            num(mean([len(r["pushes"]) for r in runs])),
                            rate(sum(1 for r in pool if r["start"] is not None and r["start"] > 1), len(pool)),
                            num(mean([r["lines"] for r in runs]), 1)))
        add(wrap("%s: %s" % (repo, "; ".join(parts)), "  ", "    "))
    for repo in repos:
        tasks = [t for t in both if data["PE"][t]["repo"] == repo]
        r = compare_binary(data, tasks, "PE", "PH", lambda s: s["resolved"])
        dl = [data["PE"][t]["lines"] - data["PH"][t]["lines"] for t in tasks]
        lo, hi = boot(dl)
        add(wrap("%s, PE minus PH (%d tasks): resolved %s points [%s, %s], McNemar p = %.4g; LINES READ %s [%s, %s]"
                 % (repo, len(tasks), signed(r["point"]), signed(r["low"]), signed(r["high"]), r["p"], num(mean(dl)),
                    num(lo), num(hi)), "  ", "    "))
    add("")

    # ---- 8
    add("8. CHECKS ON THE STORED RUNS")
    for arm in ARMS:
        runs = data[arm]
        cond = {}
        for t in runs:
            key = "%s/seed %s" % (runs[t]["condition"], runs[t]["seed"])
            cond[key] = cond.get(key, 0) + 1
        fields = {}
        for t in runs:
            for p in runs[t]["pushes"]:
                key = ",".join(p["fields"])
                fields[key] = fields.get(key, 0) + 1
        rec_fields = {}
        for t in runs:
            for f in runs[t]["rec_fields"]:
                rec_fields[",".join(f)] = rec_fields.get(",".join(f), 0) + 1
        over = sum(1 for t in runs if len(runs[t]["pushes"]) > 10)
        rec_count = sum(1 for t in runs if r14.is_int(runs[t]["rec_pushed_reads"])
                        and runs[t]["rec_pushed_reads"] != len(runs[t]["pushes"]))
        rec_chars = sum(1 for t in runs if r14.is_int(runs[t]["rec_push_chars"])
                        and runs[t]["rec_push_chars"] != runs[t]["chars"])
        add(wrap("%s: runner record condition/seed: %s; entry fields the agent received (trace): %s; agent_fields in"
                 " the runner record: %s; runs with more than 10 pushed lists %d; runs whose runner count of pushed"
                 " reads differs from the trace %d; whose runner character count differs from the trace %d."
                 % (arm, counted(cond), counted(fields), counted(rec_fields), over, rec_count, rec_chars), "  ", "    "))
    ctl = data[CONTROL]
    add("  %s: runs carrying a pushed list (expected none): %d" % (CONTROL, sum(1 for t in ctl if ctl[t]["pushes"])))
    disagree = {lab: sum(1 for t in data[lab] if data[lab][t]["ctx"] != data[lab][t]["ctx_text"]) for lab in labels}
    add("  context-window ending, runner record against error text, runs that disagree: "
        + "; ".join("%s %d" % (lab, disagree[lab]) for lab in labels))
    if checks:
        shown = checks[:60]
        for c in shown:
            add(wrap(c, "  - ", "    "))
        if len(checks) > len(shown):
            add("  ... and %d more" % (len(checks) - len(shown)))
    else:
        add("  no other finding")
    add("")

    # ---- 9
    add("9. JUDGMENT CALLS")
    notes = [
        "Entered: the arm has a result line for the task (the last one counts) and its error text is not a failure"
        " outside the agent by the rule of 14 (rederive_14.infra_kind). Each rule uses the tasks where both of its runs"
        " entered; the floor of %d tasks is applied to that count (for A1 also %d tasks with an A1 READ in both)."
        " Verdicts are printed only when G0 is met (both shares at least 80%%) and the floor is reached."
        % (MIN_TASKS, MIN_A1_TASKS),
        "Calls are paired with their own results (rederive_18.load_calls_paired); the CALL INDEX counts every tool call"
        " of the trace from 1. A READ is a read_file call whose result has status ok; its FILE is the result's filepath"
        " (the argument's if the result names none) without a leading /workspace/, workspace/ or ./.",
        "START: none when no argument whose letters, lower-cased, spell 'startline' is given; otherwise the start_line"
        " the result returned. A READ starts past line 1 when START > 1; a READ with no START counts as not past line 1."
        " LINES READ: returned end_line - start_line + 1 summed over READs (the returned range, not the content of a"
        " read cut by the character limit). READs of a file the run itself wrote count (the definition excludes"
        " nothing); the count without them is printed beside A2 as a sensitivity.",
        "PUSHED LIST: a READ whose result in the trace carries the key '%s'. The k-th pushed list of the trace is"
        " matched to the k-th push of the runner record (extra.jsonl 'pushes'), checked by (source, name) of every"
        " entry; the entry's file and line range come from the record (for PE also checked against the trace). The"
        " push's CALL INDEX is that of the READ that carried it. Characters: the length of the key's value as the trace"
        " holds it, re-serialised with json.dumps(ensure_ascii=False) (the runner's own count is checked against it)."
        " Entries per list are the entries of the record." % KEY,
        "A1 READ: for each file that holds an entry of a pushed list of the run, the run's first READ of that file, if"
        " its call index is above that of the earliest push that lists the file. A file whose first READ came before"
        " that push (including the READ that carried it) gives none. Per run: the share of its A1 READs past line 1;"
        " per task PE minus PH on tasks where both runs have one; the interval is in points of share.",
        "Uptake: for each pushed entry (a file listed twice in one push counts twice), a READ of its file at call index"
        " p+1 to p+%d, p the push's call index; the first such READ is the one judged. 'Starts inside the pushed range':"
        " START within the entry's lines, ends included (no START: no). 'Holds a changed region': the pushed range"
        " overlaps a CHANGED REGION of the reference patch in that file (printed beside it: contains a whole region)."
        " PH entries are judged by the file and range of the record though the agent did not receive them." % UPTAKE_CALLS,
        "Resolved: the result line's resolved field. Shown every changed region, shown a changed line within %d calls"
        " (T_SHOWN at most %d, views of read_file and of shell commands as in 14), final patch overlaps a changed region"
        " and touches every one: the functions of rederive_14 and rederive_18, on runs whose task has a GOLD FILE."
        % (SHOWN_CALLS, SHOWN_CALLS),
        "Context-window ending: the runner record's agent_ending is 'context window' (the reading of rederive_18); the"
        " error-text reading of rederive_14 is printed beside it and their disagreements counted in the checks.",
        "Graph-tool calls: calls to get_code_neighbors, get_code_subgraph or search_similar_code, refused calls"
        " included. Tool calls: every tool call in the trace.",
        "Bootstrap: per-task differences resampled with replacement, random.Random(0) started afresh for each"
        " comparison, randrange over the tasks in run-list order, 2,000 resamples, 2.5th and 97.5th percentiles with"
        " linear interpolation; a verdict needs a bound strictly above or below 0. Exact McNemar p: twice the smaller"
        " binomial(b + c, 1/2) tail, capped at 1.",
        "P1, P2, H1: the stored N run of 14 (seed 1) is another launch; the rule's words are shown beside the numbers"
        " as what the rule would read, never as a verdict.",
    ]
    for number, text in enumerate(notes, 1):
        add(wrap(text, "%2d. " % number, "    "))
    add("")

    # ---- per task
    add("PER TASK (per arm: r resolved, p pushed lists, e entries, a A1 READs past line 1 / all, l LINES READ, c tool"
        " calls, w context-window ending; '-' no result; '!' failure outside the agent)")
    for task in run_list:
        if not any(task in data[a] for a in ARMS):
            continue
        parts = []
        for lab in labels:
            s = data[lab].get(task)
            if s is None:
                parts.append("%-3s -" % lab)
                continue
            past = sum(1 for r in s["a1"] if r["start"] is not None and r["start"] > 1)
            if lab == CONTROL:
                parts.append("%s r=%d w=%d%s" % (lab, s["resolved"], s["ctx"], "!" if s["infra"] else ""))
            else:
                parts.append("%-2s r=%d p=%-2d e=%-2d a=%d/%d l=%-4d c=%-2d w=%d%s"
                             % (lab, s["resolved"], len(s["pushes"]), s["entries"], past, len(s["a1"]), s["lines"],
                                s["calls"], s["ctx"], "!" if s["infra"] else ""))
        add(("  %-14s %s" % (task, " | ".join(parts))).rstrip())
    return ("\n".join(out) + "\n").replace("\xa0", " ")


def main(argv):
    args = argv[1:]
    write = "--no-write" not in args
    args = [a for a in args if a != "--no-write"]
    dirs = dict(DEFAULTS)
    flags = {"--pe": "PE", "--ph": "PH", "--control": CONTROL}
    i = 0
    while i < len(args):
        if args[i] in flags and i + 1 < len(args):
            dirs[flags[args[i]]] = os.path.abspath(args[i + 1])
            i += 2
            continue
        sys.stderr.write("usage: rederive_23.py [--pe DIR] [--ph DIR] [--control DIR] [--no-write]\n")
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    try:
        report = build_report(dirs)
    except MissingRuns as missing:
        sys.stdout.write("rederive_23: %s; nothing to analyse.\n" % missing)
        return 1
    registered = all(os.path.normcase(os.path.abspath(dirs[a])) == os.path.normcase(os.path.abspath(DEFAULTS[a]))
                     for a in ARMS + (CONTROL,))
    if write and registered:
        with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    sys.stdout.write(report)
    if write and not registered:
        sys.stderr.write("rederive_23: run directories other than the registered ones: %s not written\n" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
