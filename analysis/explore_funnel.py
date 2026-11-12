#!/usr/bin/env python3
"""EXPLORATORY: where whole runs are lost, stage by stage (the funnel), in every arm of experiments 14, 23, 18 and 22.

Usage:  py -I -X utf8 analysis/explore_funnel.py

Written after all results were seen; nothing here was registered. No arguments; the report goes to stdout (stored as
analysis/results/explore_funnel.txt, LF line ends). Standard library only, plus the repository's own second scripts
(analysis/rederive_14.py, rederive_18.py, rederive_23.py), imported for the stages a per-run table lacks.

Read:
  analysis/results/14/runs_14.csv   arms N and NAF (column condition), seed 1, 103 tasks
  analysis/results/23/runs_23.csv   arms PE and PH (column arm), seed 2, 103 tasks; its rows of arm N (the N run of 14)
                                    are left out
  analysis/results/18/runs_18.csv   arms N, ON and OA, seed 2, 40 tasks; its rows N14 and NAF14 are left out
  analysis/results/22/runs_22.csv   rows with experiment 22: arms N, ON, OF and OA, seed 3, 20 tasks
  the raw records of each arm (analysis/results/<experiment>/<arm>/seed<k>/: task_results.jsonl, extra.jsonl, patches/,
  traces/), the task lists analysis/results/14/validate/tasks_ok.txt and analysis/oracle_18/tasks_18.txt, the
  reference patches in data/tasks.jsonl, and the stored outputs of the second scripts analysis/results/rederive_14.txt,
  rederive_18.txt, rederive_22.txt and rederive_23.txt (section 5 compares with them).

The functions load() and funnel_counts() and the constants ARMS, GROUPS and STAGES are what
paper/figures/make_fig_funnel.py imports.
"""
import csv
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
sys.path.insert(0, HERE)
import rederive_14 as r14  # noqa: E402  (second script of 14: patch parser, CHANGED REGIONS, views, first loader)
import rederive_18 as r18  # noqa: E402  (second script of 18: paired loader, regions shown, touches every region)
import rederive_23 as r23  # noqa: E402  (second script of 23: load_dir, a whole results directory scored)

INF = float("inf")
BOOT_RESAMPLES = 2000
BOOT_SEED = 0
TASKS_103 = os.path.join(RES, "14", "validate", "tasks_ok.txt")
TASKS_40 = os.path.join(HERE, "oracle_18", "tasks_18.txt")

# key, experiment, arm, table, arm column, experiment filter, raw directory, seed, task list, words
ARMS = (
    ("14 N", "14", "N", "14/runs_14.csv", "condition", None, "14/N/seed1", 1, TASKS_103, "the agent as shipped"),
    ("14 NAF", "14", "NAF", "14/runs_14.csv", "condition", None, "14/NAF/seed1", 1, TASKS_103,
     "graph answers with file and line range, line-bound repair"),
    ("23 PE", "23", "PE", "23/runs_23.csv", "arm", None, "23/PE/seed2", 2, TASKS_103,
     "graph neighbors pushed into reads, with file and line range"),
    ("23 PH", "23", "PH", "23/runs_23.csv", "arm", None, "23/PH/seed2", 2, TASKS_103,
     "graph neighbors pushed into reads, names only"),
    ("18 N", "18", "N", "18/runs_18.csv", "arm", None, "18/N/seed2", 2, TASKS_40, "control"),
    ("18 ON", "18", "ON", "18/runs_18.csv", "arm", None, "18/ON/seed2", 2, TASKS_40,
     "told the names of what the fix changes"),
    ("18 OA", "18", "OA", "18/runs_18.csv", "arm", None, "18/OA/seed2", 2, TASKS_40, "told the changed lines"),
    ("22 N", "22", "N", "22/runs_22.csv", "arm", "22", "22/N/seed3", 3, TASKS_40, "control"),
    ("22 ON", "22", "ON", "22/runs_22.csv", "arm", "22", "22/ON/seed3", 3, TASKS_40, "told the names"),
    ("22 OF", "22", "OF", "22/runs_22.csv", "arm", "22", "22/OF/seed3", 3, TASKS_40,
     "told the names with line ranges"),
    ("22 OA", "22", "OA", "22/runs_22.csv", "arm", "22", "22/OA/seed3", 3, TASKS_40, "told the changed lines"),
)
GROUPS = (("whole runs, 103 tasks", ("14 N", "14 NAF", "23 PE", "23 PH")),
          ("told where the fix is, first seed (18), 40 tasks", ("18 N", "18 ON", "18 OA")),
          ("told where the fix is, second seed (22), 20 of those 40 tasks", ("22 N", "22 ON", "22 OF", "22 OA")))

# stage key, letter, words, column of the per-run table
STAGES = (
    ("entered", "a", "entered", "entered"),
    ("shown_one", "b", "shown at least one changed region", "t_shown"),
    ("shown_every", "c", "shown every changed region", "every_region"),
    ("nonempty", "d", "final patch non-empty", "patch_nonempty"),
    ("gold_file", "e", "patch changes a file of the fix", "patch_gold_file"),
    ("overlaps", "f", "patch overlaps a changed region", "patch_overlaps"),
    ("touches_every", "g", "patch touches every changed region", "patch_touches_every_region"),
    ("resolved", "h", "resolved", "resolved"),
)
STAGE_WORDS = {key: words for key, _l, words, _c in STAGES}
STAGE_LETTER = {key: letter for key, letter, _w, _c in STAGES}


def fail(msg):
    raise SystemExit("explore_funnel: " + msg)


def task_list(path):
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def flag(value, what):
    if value == "1":
        return True
    if value == "0":
        return False
    fail("%s: %r is neither 1 nor 0" % (what, value))


def shown_flag(value, what):
    """t_shown is the call index of the first view of a changed line, or inf when none."""
    if value == "inf":
        return False
    if re.fullmatch(r"\d+", value or ""):
        return True
    fail("%s: t_shown %r is neither a call index nor inf" % (what, value))


def wrap(text, first="  ", rest="    "):
    return r18.wrap(text, first, rest)


# ------------------------------------------------------------------------------------------------- loading

def read_table(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def derive_arm(base, label, run_list, gold):
    """Every stage, the ending and four readings of 'shown every changed region', from the raw records, with the
    second scripts' functions: rederive_23.load_dir (resolved, T_SHOWN, every region shown with every call paired
    with its own result and shell views counted, patch overlaps, patch touches every region, runner ending,
    infrastructure rule), rederive_14.changed_regions on the final patch (non-empty, a file of the fix), and
    rederive_14.load_calls / rederive_18.first_shown_each for the other readings of 'shown every changed region'."""
    runs = r23.load_dir(base, label, run_list, gold, [])
    out = {}
    for task, x in runs.items():
        g = gold[task]
        regions = r18.region_list(g)
        text = ""
        patch_path = os.path.join(base, "patches", "%s.patch" % task)
        if os.path.exists(patch_path):
            with open(patch_path, "rb") as handle:
                text = handle.read().decode("utf-8", errors="replace")
        agent_regions = r14.changed_regions(text)[0] if text.strip() else {}
        trace_path = os.path.join(base, "traces", "trace_%s.json" % task)
        calls_paired = r18.load_calls_paired(trace_path)[0] if os.path.exists(trace_path) else []
        calls_first = r14.load_calls(trace_path)[0] if os.path.exists(trace_path) else []
        views_paired = r14.session_views(calls_paired, g)[0]
        views_first = r14.session_views(calls_first, g)[0]

        def every(views, shell):
            return bool(regions) and all(v < INF for v in r18.first_shown_each(views, regions, shell=shell))

        out[task] = {
            "entered": x["infra"] is None,
            "shown_one": x["t"] < INF,
            "shown_every": x["every"],
            "nonempty": bool(text.strip()),
            "gold_file": any(path in g for path in agent_regions),
            "overlaps": x["overlap"],
            "touches_every": x["touch_every"],
            "resolved": x["resolved"],
            "ending": x["ending"],
            # the readings of 'shown every changed region': paired calls and shell views (the second scripts'),
            # paired calls and read_file results only, first result of a step only and shell views, and both
            # restrictions together (the first scripts' reading)
            "every_paired_shell": every(views_paired, True),
            "every_paired_reads": every(views_paired, False),
            "every_first_shell": every(views_first, True),
            "every_first_reads": every(views_first, False),
        }
    return out


def load():
    """({arm key: {'tasks': [run-list order], 'runs': {task: {stage: bool}}, 'source': {stage: 'table' or 'raw'},
    'derived': {task: {...}}, 'ended': {task: str}, ...}}, facts about the tables read)."""
    reference = {row["instance_id"]: row for row in r14.read_jsonl(os.path.join(ROOT, "data", "tasks.jsonl"))}
    lists = {TASKS_103: task_list(TASKS_103), TASKS_40: task_list(TASKS_40)}
    gold = {}
    for run_list in lists.values():
        for task in run_list:
            if task not in gold:
                gold[task] = r14.changed_regions(reference[task]["patch"])[0]
    tables = {}
    data = {}
    for key, exp, arm, table, col, exp_filter, raw, seed, list_path, words in ARMS:
        if table not in tables:
            tables[table] = read_table(os.path.join(RES, table))
        rows_all = tables[table]
        header = list(rows_all[0].keys()) if rows_all else []
        rows = [r for r in rows_all if r[col] == arm and (exp_filter is None or r.get("experiment") == exp_filter)]
        run_list = lists[list_path]
        position = {t: i for i, t in enumerate(run_list)}
        tasks = [r["task"] for r in rows]
        if len(set(tasks)) != len(tasks):
            fail("%s: a task has more than one row in %s" % (key, table))
        if any(t not in position for t in tasks):
            fail("%s: a task of %s is not on its task list" % (key, table))
        if any(r["seed"] != str(seed) for r in rows):
            fail("%s: a row of %s is not seed %d" % (key, table, seed))
        tasks.sort(key=position.get)
        by_task = {r["task"]: r for r in rows}
        derived = derive_arm(os.path.join(RES, raw), key, run_list, gold)
        if set(derived) != set(tasks):
            fail("%s: the raw records hold other tasks than the table" % key)
        source = {}
        runs = {t: {} for t in tasks}
        for stage, _letter, _words, column in STAGES:
            if column in header:
                source[stage] = "table"
                for t in tasks:
                    what = "%s %s %s" % (table, key, t)
                    runs[t][stage] = (shown_flag(by_task[t][column], what) if stage == "shown_one"
                                      else flag(by_task[t][column], what))
            else:
                source[stage] = "raw"
                for t in tasks:
                    runs[t][stage] = derived[t][stage]
        for t in tasks:
            if not runs[t]["entered"]:
                fail("%s %s: a run that did not enter; the funnel assumes every stored run entered" % (key, t))
        data[key] = {"key": key, "experiment": exp, "arm": arm, "seed": seed, "table": table, "raw": raw,
                     "words": words, "tasks": tasks, "runs": runs, "source": source, "derived": derived,
                     "ended": {t: by_task[t]["ended"] for t in tasks},
                     "no_gold": [t for t in tasks if not gold[t]]}
    facts = {"rows": {}, "left_out": {}}
    for table, rows_all in tables.items():
        facts["rows"][table] = len(rows_all)
        kept = {d["arm"] for d in data.values() if d["table"] == table}
        left = {}
        for r in rows_all:
            if table == "22/runs_22.csv":
                if r["experiment"] == "22":
                    continue
                label = "rows of experiment %s" % r["experiment"]
            else:
                arm = r.get("arm", r.get("condition"))
                if arm in kept:
                    continue
                label = "arm %s" % arm
            left[label] = left.get(label, 0) + 1
        facts["left_out"][table] = left
    return data, facts


# ------------------------------------------------------------------------------------------------- counts

def funnel_counts(data):
    """{arm key: {stage: count of runs}} over the runs that entered."""
    return {key: {stage: sum(1 for t in d["tasks"] if d["runs"][t][stage]) for stage, _l, _w, _c in STAGES}
            for key, d in data.items()}


def share(k, n):
    return "%d of %d (%.1f%%)" % (k, n, 100.0 * k / n) if n else "%d of 0 (n/a)" % k


def boot_share(tasks, num, den):
    """95% interval of sum(num)/sum(den) over the arm's tasks: 2,000 resamples of tasks with replacement (randrange
    over the tasks in run-list order), random.Random(0) created afresh; resamples with no run in the denominator are
    dropped (their number is returned)."""
    n = len(tasks)
    rng = random.Random(BOOT_SEED)
    values, dropped = [], 0
    for _ in range(BOOT_RESAMPLES):
        s_num = s_den = 0
        for _ in range(n):
            t = tasks[rng.randrange(n)]
            s_num += num[t]
            s_den += den[t]
        if s_den == 0:
            dropped += 1
            continue
        values.append(100.0 * s_num / s_den)
    values.sort()
    if not values:
        return float("nan"), float("nan"), dropped
    return r18.percentile(values, 0.025), r18.percentile(values, 0.975), dropped


# ------------------------------------------------------------------------------------------------- stored outputs

class Stored:
    """A stored output of a second script, read as lines."""

    def __init__(self, name):
        self.name = name
        with open(os.path.join(RES, name), encoding="utf-8") as handle:
            self.lines = handle.read().splitlines()
        self.joined = " ".join(line.strip() for line in self.lines)

    def section(self, head):
        for i, line in enumerate(self.lines):
            if line.startswith(head):
                return i
        fail("%s: no line starts with %r" % (self.name, head))

    def row(self, head, label, ncols):
        """[(k, n)] of the first line after the section `head` that starts (after any indent) with `label`, then
        blank(s) and a count."""
        start = self.section(head)
        rx = re.compile(r"^\s*%s\s+\d+/\d+ \(" % re.escape(label))
        for line in self.lines[start:]:
            if rx.match(line):
                cols = [(int(a), int(b)) for a, b in re.findall(r"(\d+)/(\d+) \(", line)]
                if len(cols) != ncols:
                    fail("%s: the row %r has %d counts, not %d" % (self.name, label, len(cols), ncols))
                return cols
        fail("%s: no row %r after %r" % (self.name, label, head))

    def search(self, pattern, what):
        m = re.search(pattern, self.joined)
        if not m:
            fail("%s: no text for %s" % (self.name, what))
        return m


def stored_counts():
    """([(arm key, stage, k, n, file, what)] read from the stored outputs of the second scripts; {arm key: count of
    'shown every changed region' that a second script prints under the first script's loader}; {arm key: the runner
    endings the second script prints})."""
    out = []
    loader = {}
    s14 = Stored("rederive_14.txt")
    sec = "2. PER CONDITION"
    for stage, label in (("resolved", "RESOLVED"), ("shown_one", "T_SHOWN ever"), ("overlaps", "FINAL PATCH OVERLAPS")):
        for key, (k, n) in zip(("14 N", "14 NAF"), s14.row(sec, label, 2)):
            out.append((key, stage, k, n, s14.name, label))
    m = s14.search(r"Tasks that enter the paired analysis: (\d+);", "the tasks that enter")
    for key in ("14 N", "14 NAF"):
        out.append((key, "entered", int(m.group(1)), int(m.group(1)), s14.name, "Tasks that enter the paired analysis"))
    m = s14.search(r"Sessions whose patch has a region in a GOLD FILE at all: N (\d+)/(\d+) \([\d.]+%\), NAF (\d+)/(\d+)",
                   "the sessions whose patch has a region in a GOLD FILE")
    out.append(("14 N", "gold_file", int(m.group(1)), int(m.group(2)), s14.name, "patch has a region in a GOLD FILE"))
    out.append(("14 NAF", "gold_file", int(m.group(3)), int(m.group(4)), s14.name, "patch has a region in a GOLD FILE"))

    s23 = Stored("rederive_23.txt")
    sec = "7. WITHOUT A RULE"
    for stage, label in (("resolved", "RESOLVED"), ("shown_every", "shown every changed region"),
                         ("overlaps", "final patch overlaps a changed region"),
                         ("touches_every", "final patch touches every changed region")):
        for key, (k, n) in zip(("23 PE", "23 PH", "14 N"), s23.row(sec, label, 3)):
            out.append((key, stage, k, n, s23.name, label + (" (column N14)" if key == "14 N" else "")))
    for label, key in (("PE", "23 PE"), ("PH", "23 PH"), ("N14", "14 N")):
        m = s23.search(r"\b%s: runs with a result (\d+) .*?; entered (\d+);" % label, "entered " + label)
        out.append((key, "entered", int(m.group(2)), int(m.group(1)), s23.name,
                    "entered" + (" (N14)" if key == "14 N" else "")))

    s18 = Stored("rederive_18.txt")
    sec = "2. PER ARM, ON THE RUNS THAT ENTERED"
    for stage, label in (("resolved", "RESOLVED"), ("shown_one", "shown a changed line (ever)"),
                         ("shown_every", "shown every changed region"),
                         ("overlaps", "patch overlaps a changed region"),
                         ("touches_every", "patch touches every changed region")):
        for key, (k, n) in zip(("18 N", "18 ON", "18 OA"), s18.row(sec, label, 3)):
            out.append((key, stage, k, n, s18.name, label))
    for key, (k, n) in zip(("18 N", "18 ON", "18 OA"), s18.row(sec, "the same, loader of rederive_14", 3)):
        loader[key] = (k, s18.name, "the same, loader of rederive_14")
    for arm in ("N", "ON", "OA"):
        m = s18.search(r"\b%s: result lines (\d+) .*?; entered (\d+)\." % arm, "entered " + arm)
        out.append(("18 " + arm, "entered", int(m.group(2)), int(m.group(1)), s18.name, "entered"))

    s22 = Stored("rederive_22.txt")
    sec = "2. PER ARM OF 22"
    for stage, label in (("resolved", "RESOLVED"), ("shown_one", "shown a changed line (ever)"),
                         ("shown_every", "shown every changed region"),
                         ("overlaps", "final patch overlaps a changed region"),
                         ("touches_every", "patch touches every changed region")):
        for key, (k, n) in zip(("22 N", "22 ON", "22 OF", "22 OA"), s22.row(sec, label, 4)):
            out.append((key, stage, k, n, s22.name, label))
    m = s22.search(r"Per arm, shown every changed region so counted: N (\d+)/\d+ \([\d.]+%\), ON (\d+)/\d+ \([\d.]+%\), "
                   r"OF (\d+)/\d+ \([\d.]+%\), OA (\d+)/\d+", "the counts with the loader of rederive_14")
    for i, arm in enumerate(("N", "ON", "OF", "OA")):
        loader["22 " + arm] = (int(m.group(i + 1)), s22.name, "L7 sensitivity, per arm, the loader of rederive_14")
    for arm in ("N", "ON", "OF", "OA"):
        m = s22.search(r"\b%s \(seed 3\): directory present; result lines (\d+) .*?; entered (\d+)\." % arm,
                       "entered " + arm)
        out.append(("22 " + arm, "entered", int(m.group(2)), int(m.group(1)), s22.name, "entered"))

    endings = {}
    for label, key in (("N", "14 N"), ("NAF", "14 NAF")):
        m = s14.search(r"Condition %s: \d+ sessions, \d+ with a runner record how sessions ended: (.*?) changes the "
                       r"runner applied" % label, "the endings of " + label)
        endings[key] = (m.group(1).strip(), s14.name)
    for label, key in (("PE", "23 PE"), ("PH", "23 PH")):
        m = s23.search(r"How runs ended \(runner record agent_ending\), all runs with a result: .*?\b%s: (.*?) "
                       r"(?:PE|PH|N14): " % label, "the endings of " + label)
        endings[key] = (m.group(1).strip(), s23.name)
    for arm in ("N", "ON", "OA"):
        m = s18.search(r"How the sessions ended \(runner record agent_ending\), all runs with a result: .*?\b%s: (.*?) "
                       r"(?:ON|OA|Error text)" % arm, "the endings of " + arm)
        endings["18 " + arm] = (m.group(1).strip(), s18.name)
    for arm in ("N", "ON", "OF", "OA"):
        m = s22.search(r"How the sessions ended \(runner record agent_ending\), all runs with a result: .*?\b%s: (.*?) "
                       r"(?:ON|OF|OA|3\. THE RULES)" % arm, "the endings of " + arm)
        endings["22 " + arm] = (m.group(1).strip(), s22.name)
    return out, loader, endings


# ------------------------------------------------------------------------------------------------- report

def counted(values):
    tally = {}
    for v in values:
        tally[v] = tally.get(v, 0) + 1
    return "; ".join("%s %d" % (k, n) for k, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])))


def build_report():
    data, facts = load()
    counts = funnel_counts(data)
    stored, loader, endings = stored_counts()
    out = []
    add = out.append

    # ---- 0
    add("WHERE WHOLE RUNS ARE LOST: THE FUNNEL, PER ARM (experiments 14, 23, 18, 22)")
    add("EXPLORATORY, written after all results were seen; nothing here was registered.")
    add("Tables read (rows of other arms left out):")
    for table in ("14/runs_14.csv", "23/runs_23.csv", "18/runs_18.csv", "22/runs_22.csv"):
        used = ", ".join("%s %d" % (d["arm"], len(d["tasks"])) for d in data.values() if d["table"] == table)
        left = facts["left_out"][table]
        left_text = "; left out: " + ", ".join("%s %d" % kv for kv in sorted(left.items())) if left else ""
        add(wrap("analysis/results/%s: %d rows; runs per arm: %s%s" % (table, facts["rows"][table], used, left_text)))
    add(wrap("Runs per arm (every one entered): " + "; ".join("%s %d (seed %d)" % (k, len(d["tasks"]), d["seed"])
                                                            for k, d in data.items()) + ".", "", "  "))
    add(wrap("Raw records read for every arm: analysis/results/<experiment>/<arm>/seed<k>/ (task_results.jsonl,"
             " extra.jsonl, patches/, traces/), with data/tasks.jsonl for the reference patches.", "", "  "))
    add("")

    # ---- 1
    add("1. THE FUNNEL: runs reaching each stage (counts of runs; each stage on its own, not nested)")
    for key, letter, words, column in STAGES:
        add("  (%s) %s  [table column %s]" % (letter, words, column))
    add(wrap("(b) is the table's t_shown being a call index rather than inf: a read_file result or a shell view of one"
             " file returned a changed line.", "  ", "      "))
    add("")
    head = "  %-8s" % "arm" + "".join("%7s" % ("(%s)" % l) for _k, l, _w, _c in STAGES)
    for title, keys in GROUPS:
        add("  " + title)
        add(head)
        for key in keys:
            d = data[key]
            cells = ["%7s" % (str(counts[key][stage]) + ("*" if d["source"][stage] == "raw" else ""))
                     for stage, _l, _w, _c in STAGES]
            add("  %-8s" % key + "".join(cells))
        add("")
    add("  * derived from the raw records with the second scripts' functions, as the table has no such column:")
    for key, d in data.items():
        raw = [s for s, _l, _w, _c in STAGES if d["source"][s] == "raw"]
        if raw:
            add("    %s: %s (analysis/results/%s)" % (key, ", ".join("(%s) %s" % (STAGE_LETTER[s], STAGE_WORDS[s])
                                                                     for s in raw), d["raw"]))
    add(wrap("how: rederive_23.load_dir on the arm's results directory gives (g) (rederive_18.touches_every on"
             " rederive_14.changed_regions of the final patch); (d) is a stored patch file with any non-blank character"
             " (as rederive_14/18/22 read it); (e) is a region of the parsed final patch in a GOLD FILE (rederive_14's"
             " 'patch has a region in a GOLD FILE'). Stages available neither way: none.", "    ", "    "))
    no_gold = {}
    for key, d in data.items():
        for t in d["no_gold"]:
            no_gold.setdefault(t, []).append(key)
    for t, keys in no_gold.items():
        add(wrap("A task whose reference patch modifies no existing file (no GOLD FILE): %s, in %s; (b), (c), (e), (f)"
                 " and (g) are false for its runs by construction." % (t, ", ".join(keys))))
    nest = (("shown_every", "shown_one"), ("gold_file", "nonempty"), ("overlaps", "gold_file"),
            ("touches_every", "overlaps"))
    broken = []
    for key, d in data.items():
        for inner, outer in nest:
            off = [t for t in d["tasks"] if d["runs"][t][inner] and not d["runs"][t][outer]]
            if off:
                broken.append("%s: (%s) without (%s): %s" % (key, STAGE_LETTER[inner], STAGE_LETTER[outer],
                                                             ", ".join(off)))
    add(wrap("Stages that must nest, checked run by run: (c) within (b), (e) within (d), (f) within (e), (g) within"
             " (f); runs that break it: " + ("; ".join(broken) if broken else "none") + "."))
    add("")

    # ---- 2
    add("2. THE SAME, NESTED: entered -> shown every changed region -> patch overlaps a changed region -> resolved")
    add("  each count is of the runs at the stage before, with its share of them")
    add("    %-7s %8s   %-24s %-26s %s" % ("arm", "entered", "shown every region", "of them, patch overlaps",
                                          "of them, resolved"))
    for title, keys in GROUPS:
        add("  " + title)
        for key in keys:
            d = data[key]
            T, R = d["tasks"], d["runs"]
            s0 = [t for t in T if R[t]["entered"]]
            s1 = [t for t in s0 if R[t]["shown_every"]]
            s2 = [t for t in s1 if R[t]["overlaps"]]
            s3 = [t for t in s2 if R[t]["resolved"]]
            add("    %-7s %8d   %-24s %-26s %s" % (key, len(s0), share(len(s1), len(s0)), share(len(s2), len(s1)),
                                                 share(len(s3), len(s2))))
    add("  Leaks:")
    add("    %-7s %-34s %-34s %s" % ("arm", "resolved, patch overlaps no region", "resolved, not shown every region",
                                    "patch touches every region,"))
    add("    %-7s %-34s %-34s %s" % ("", "", "", "not resolved"))
    for title, keys in GROUPS:
        for key in keys:
            d = data[key]
            T, R = d["tasks"], d["runs"]
            res = [t for t in T if R[t]["resolved"]]
            touch = [t for t in T if R[t]["touches_every"]]
            a = sum(1 for t in res if not R[t]["overlaps"])
            b = sum(1 for t in res if not R[t]["shown_every"])
            c = sum(1 for t in touch if not R[t]["resolved"])
            add("    %-7s %-34s %-34s %s" % (key, "%d of %d resolved" % (a, len(res)), "%d of %d resolved" % (b, len(res)),
                                            "%d of %d touching every region" % (c, len(touch))))
    add("")

    # ---- 3
    add("3. CONVERSION, per arm (share in percent [95% bootstrap interval by task: 2,000 resamples of the arm's tasks,")
    add("   random.Random(0) created afresh for each interval, percentiles 2.5 and 97.5 of the ratio of sums])")
    add("   C1: of the runs shown every changed region, final patch overlaps a changed region")
    add("   C2: of the runs shown every changed region, resolved")
    add("   C3: of the runs whose patch overlaps a changed region, resolved")
    for title, keys in GROUPS:
        add("  " + title)
        for key in keys:
            d = data[key]
            T, R = d["tasks"], d["runs"]
            cells = []
            for den_stage, num_stage in (("shown_every", "overlaps"), ("shown_every", "resolved"),
                                         ("overlaps", "resolved")):
                den = {t: 1 if R[t][den_stage] else 0 for t in T}
                num = {t: 1 if (R[t][den_stage] and R[t][num_stage]) else 0 for t in T}
                k, n = sum(num.values()), sum(den.values())
                lo, hi, dropped = boot_share(T, num, den)
                text = "%d/%d %.1f [%.1f, %.1f]" % (k, n, 100.0 * k / n, lo, hi) if n else "%d/0 n/a" % k
                if dropped:
                    text += " (%d resample(s) with an empty denominator dropped)" % dropped
                cells.append(text)
            add(wrap("%-7s C1 %s; C2 %s; C3 %s" % (key, cells[0], cells[1], cells[2]), "    ", "            "))
    add("")

    # ---- 4
    add("4. HOW RUNS END, per arm (the table's column ended)")
    for title, keys in GROUPS:
        for key in keys:
            add(wrap("%-7s %s" % (key, counted(data[key]["ended"].values())), "    ", "            "))
    add(wrap("Beside it, the runner record's agent_ending as the second script prints it, and the runs where the"
             " table's ended and the runner record (read here with rederive_23.load_dir) name different endings:"))
    for title, keys in GROUPS:
        for key in keys:
            d = data[key]
            text, name = endings[key]
            differ = ["%s (table '%s', runner record '%s')" % (t, d["ended"][t], d["derived"][t]["ending"])
                      for t in d["tasks"] if d["ended"][t] != d["derived"][t]["ending"]]
            add(wrap("%-7s %s: %s" % (key, name, text), "    ", "            "))
            add(wrap("differ: %s" % ("; ".join(differ) if differ else "none"), "            ", "              "))
    add("")

    # ---- 5
    add("5. CROSS-CHECK AGAINST THE SECOND SCRIPTS' STORED OUTPUTS (count of the funnel against the count printed)")
    add("    %-7s %-39s %-14s %-16s %s" % ("arm", "stage", "funnel", "stored output", "count printed"))
    unreconciled = []
    for title, keys in GROUPS:
        for key in keys:
            d = data[key]
            T = d["tasks"]
            for stage, _l, _w, _c in STAGES:
                for akey, astage, k, n, name, what in stored:
                    if akey != key or astage != stage:
                        continue
                    mine = counts[key][stage]
                    line = "    %-7s (%s) %-35s %3d %-10s %-16s %3d/%-3d" % (
                        key, STAGE_LETTER[stage], STAGE_WORDS[stage], mine, "(%s)" % d["source"][stage], name, k, n)
                    if mine == k:
                        add(line + "  agree")
                        continue
                    add(line + "  differ by %+d" % (mine - k))
                    if stage != "shown_every":
                        unreconciled.append((key, stage))
                        add("            NOT RECONCILED")
                        continue
                    der = d["derived"]
                    n_ps = sum(1 for t in T if der[t]["every_paired_shell"])
                    n_pr = sum(1 for t in T if der[t]["every_paired_reads"])
                    n_fs = sum(1 for t in T if der[t]["every_first_shell"])
                    n_fr = sum(1 for t in T if der[t]["every_first_reads"])
                    by_loader = [t for t in T if der[t]["every_paired_shell"] != der[t]["every_first_shell"]]
                    by_shell = [t for t in T if der[t]["every_paired_shell"] != der[t]["every_paired_reads"]]
                    ind = ("            ", "              ")
                    add(wrap("recomputed here: the second scripts' reading %d; read_file results only %d; first result"
                             " of a step only %d; both (the first script's reading) %d" % (n_ps, n_pr, n_fs, n_fr), *ind))
                    if key in loader:
                        add(wrap("%s itself prints %d with the loader that keeps the first result of a step only"
                                 " (its line: %s)" % (loader[key][1], loader[key][0], loader[key][2]), *ind))
                    if by_loader:
                        add(wrap("cause: the first script credits a step with several tool calls with its first result"
                                 " only; %d run(s): %s" % (len(by_loader), ", ".join(by_loader)), *ind))
                    if by_shell:
                        add(wrap("cause: the first script does not count shell views of one file (cat, head, tail,"
                                 " sed -n) for (c); %d run(s): %s" % (len(by_shell), ", ".join(by_shell)), *ind))
                    if n_fr != mine or n_ps != k or (key in loader and loader[key][0] != mine):
                        unreconciled.append((key, stage))
                        add("            NOT RECONCILED")
    add(wrap("Which count the funnel uses for (c): the table's (the first script's), because every stage is taken from"
             " the per-run table where it has a column; the second scripts' count is the fuller one (every call paired"
             " with its own result, shell views counted), and the two differ only in the runs listed above."))
    add(wrap("Stages the table has, recomputed here from the raw records with the second scripts' functions (a check"
             " of the derivation used for the starred cells of section 1):"))
    for title, keys in GROUPS:
        for key in keys:
            d = data[key]
            diffs = []
            for stage, _l, _w, _c in STAGES:
                if d["source"][stage] != "table":
                    continue
                k = sum(1 for t in d["tasks"] if d["derived"][t][stage])
                runs_off = [t for t in d["tasks"] if d["derived"][t][stage] != d["runs"][t][stage]]
                if runs_off:
                    diffs.append("(%s) table %d, raw %d (%s)" % (STAGE_LETTER[stage], counts[key][stage], k,
                                                                ", ".join(runs_off)))
            n_table = sum(1 for s, _l, _w, _c in STAGES if d["source"][s] == "table")
            add(wrap("%-7s %s" % (key, "; ".join(diffs) if diffs else "the %d table stages agree run by run" % n_table),
                     "    ", "            "))
    add("  Unreconciled differences: %s" % ("none" if not unreconciled else
                                           ", ".join("%s (%s)" % (k, STAGE_LETTER[s]) for k, s in unreconciled)))
    add("")

    # ---- 6
    c = counts
    whole, told, second = GROUPS[0][1], GROUPS[1][1], GROUPS[2][1]

    def arms_text(keys, stage):
        return ", ".join("%d" % c[k][stage] for k in keys)

    def runs_where(keys, *conds):
        return sum(1 for k in keys for t in data[k]["tasks"]
                   if all(data[k]["runs"][t][st] == want for st, want in conds))

    add("6. IN PLAIN WORDS")
    add(wrap("In the four whole-run arms (%s, 103 tasks each), %d to %d runs were shown at least one changed region, %s"
             " (in that order) were shown every changed region, %s had a final patch overlapping a changed region, and"
             " %s were resolved." % (", ".join(whole), min(c[k]["shown_one"] for k in whole),
                                     max(c[k]["shown_one"] for k in whole), arms_text(whole, "shown_every"),
                                     arms_text(whole, "overlaps"), arms_text(whole, "resolved")), "  ", "  "))
    add(wrap("In those arms, of the runs shown every changed region whose final patch overlapped one, %s were resolved."
             % ", ".join("%d of %d" % (runs_where([k], ("shown_every", True), ("overlaps", True), ("resolved", True)),
                                       runs_where([k], ("shown_every", True), ("overlaps", True))) for k in whole),
             "  ", "  "))
    add(wrap("Pooled over those four arms, %d of the %d resolved runs had a final patch that overlaps no changed region,"
             " and %d of the %d runs whose patch touches every changed region were not resolved."
             % (runs_where(whole, ("resolved", True), ("overlaps", False)), runs_where(whole, ("resolved", True)),
                runs_where(whole, ("touches_every", True), ("resolved", False)),
                runs_where(whole, ("touches_every", True))), "  ", "  "))
    stored_oa = [k for a, st, k, _n, _f, _w in stored if a == "18 OA" and st == "shown_every"][0]
    add(wrap("In experiment 18 (40 tasks), the runs shown every changed region were %d in N, %d in ON and %d in OA (%d"
             " in OA by the second script), the runs whose final patch overlaps a changed region %s, and the runs"
             " resolved %s." % (c["18 N"]["shown_every"], c["18 ON"]["shown_every"], c["18 OA"]["shown_every"],
                                stored_oa, arms_text(told, "overlaps"), arms_text(told, "resolved")), "  ", "  "))
    add(wrap("In 18, %d runs had a final patch touching every changed region, and %d of them were not resolved."
             % (runs_where(told, ("touches_every", True)), runs_where(told, ("touches_every", True), ("resolved", False))),
             "  ", "  "))
    add(wrap("In 22 (N, ON, OF, OA on 20 tasks), the runs shown every changed region were %s, those whose final patch"
             " overlaps a changed region %s, and those resolved %s." % (arms_text(second, "shown_every"),
                                                                         arms_text(second, "overlaps"),
                                                                         arms_text(second, "resolved")), "  ", "  "))
    add("")

    # ---- 7
    add("7. JUDGMENT CALLS")
    calls = [
        "Runs and arms. A run is a row of the per-run table for its arm (one per task); the N rows of runs_23.csv, the"
        " N14 and NAF14 rows of runs_18.csv and the rows of runs_22.csv whose experiment is not 22 are left out. Every"
        " row kept has entered = 1 (the script stops otherwise), so every stage is counted over all stored runs.",
        "Shown at least one changed region (b): t_shown is a call index, not inf. The table's t_shown counts read_file"
        " results and shell views of one file (cat, head, tail, sed -n), so (b) is wider than 'a file read' in the"
        " strict sense. The tables give (c) from read_file results only, so (b) and (c) do not use the same views;"
        " section 1 checks run by run that no run is in (c) without being in (b).",
        "Shown every changed region (c): the table's column (the first scripts' reading) wherever the table has one,"
        " which is every arm; section 5 prints the second scripts' fuller count where they differ.",
        "Patch changes a file of the fix (e) and patch non-empty (d) for 23, and patch touches every changed region (g)"
        " for 14: derived from the raw records (section 1). The function for (g) is rederive_18.touches_every, which"
        " rederive_23.load_dir applies; it is that second script that already scores the N run of 14 this way.",
        "Patch non-empty (d) derived: the stored patch file has a non-blank character. A file of the fix (e) derived:"
        " the parsed final patch has a region (a hunk on an existing file) in a GOLD FILE; a file the agent creates"
        " does not count.",
        "The task without a GOLD FILE (fastapi_15661, in the four 103-task arms) stays in every count: it enters, and"
        " (b), (c), (e), (f), (g) are false for it. The second scripts print those stages over 102 tasks; the counts"
        " are the same.",
        "Nested chain (section 2): entered, then shown every changed region, then patch overlaps a changed region,"
        " then resolved; each share is over the runs at the stage before. The leaks count resolved runs outside the"
        " chain, and runs touching every changed region that are not resolved.",
        "Conversion intervals (section 3): one run per task in an arm, so resampling tasks resamples runs; the share is"
        " the ratio of the resampled sums (numerator and denominator drawn together), percentiles with linear"
        " interpolation (rederive_18.percentile); a resample with an empty denominator is dropped and counted.",
        "Endings (section 4): the table's ended column as stored. It is the first scripts' classification and can"
        " differ from the runner record; the differing runs are listed, not corrected.",
        "Cross-check (section 5): the second scripts' counts are read from their stored outputs by matching the"
        " printed lines; nothing is typed. For N of 14 two second scripts print counts (rederive_14 and the N14"
        " column of rederive_23); both are compared.",
        "Differences in (c) are attributed by recomputing (c) here four ways (paired or first-result loader, with or"
        " without shell views); a difference counts as reconciled when the first script's reading reproduces the"
        " table, the second scripts' reading reproduces their stored count, and (where the second script prints one)"
        " its own count under the first-result loader equals the table.",
    ]
    for i, text in enumerate(calls, 1):
        add(r18.wrap(text, " %2d. " % i, "     "))
    return "\n".join(out) + "\n", data, counts


def main():
    report, _data, _counts = build_report()
    sys.stdout.reconfigure(newline="\n")   # LF line ends also when stdout is a file on Windows
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
