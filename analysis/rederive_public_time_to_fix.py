#!/usr/bin/env python3
"""Third, independent derivation of the skill-arm timing counts. Standard library only.

Written from the written rules alone. It imports nothing from the repository and
shares no code with the other implementations of these counts.

Run from the repository root:
    py -I -X utf8 analysis/rederive_public_time_to_fix.py

Inputs (relative to the repository root)
    data/tasks.jsonl
        one JSON object per line: instance_id, patch (the reference fix, a unified diff)
    data/graphloc/out/<notebook>/e2e/results/<arm>/w<worker>/traces/trace_<task>.json
        agent traces, arm = base | skill
    data/graphloc/out/<notebook>/e2e/records/rec_w*.jsonl
        run records: arm, id, resolved, patch (the agent's final patch)

Rules, in the order the code applies them
    pair            (notebook, task) with both a base and a skill trace
    created file    every hunk of the file has old range -0,0; created files are ignored
    changed region  one per hunk of a modified file, in old-file line numbers:
                    [min(points), max(points)] where the points are every removed
                    line's old number and, for each block of added lines that follows
                    a context line or opens the hunk, max(p - 1, 1) and p (p = the old
                    line counter at the insertion). Added lines after a removed line
                    add nothing. Backslash lines are ignored.
    gold files      modified files of the reference patch with at least one region
    call index      position of a tool call in the run, every call of every step, from 1
    shown           a read_file call whose result has status ok, whose file is a gold
                    file, and whose start_line..end_line overlaps a region of that file
    final patch     not empty / touches a gold file / overlaps a changed region

Output: sections 1 to 6 (the numbers), then diagnostics, then the same numbers under
four other readings of the rules, to show which numbers a different reading would move.
"""

import json
import os
import random
import re
import sys
from fractions import Fraction

NOTEBOOKS = (
    "graphloc-end-to-end-gemma-4-agent-skill",
    "graphloc-end-to-end-repeat-run-2",
    "graphloc-end-to-end-repeat-run-3",
)
ARMS = ("base", "skill")
WITHIN = (2, 3, 5, 8, 10, 15, 20)

BOOT_SEED = 0
BOOT_DRAWS = 2000
BOOT_LOW_INDEX = 50
BOOT_HIGH_INDEX = 1949
BOOT_WITHIN = 5

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

# Other readings of the rules. All off: sections 1 to 6 follow the rules as written.
# main() switches them on one at a time at the very end.
OPTIONS = {
    "second_added_line_opens_block": False,
    "name_files_by_plus_line_only": False,
    "skip_calls_without_status": False,
    "bootstrap_over_all_paired_tasks": False,
}
VARIANTS = (
    ("second_added_line_opens_block",
     "A. In a replacement (removed lines, then two or more added lines) the second added line\n"
     "   is read as opening an insertion block, so it adds the points p - 1 and p"),
    ("name_files_by_plus_line_only",
     "B. A file of a patch is named by its +++ line only, so a file the agent deleted\n"
     "   (+++ /dev/null) is not a file of the patch"),
    ("skip_calls_without_status",
     "C. A call whose result has no status field does not advance the call index\n"
     "   (the diagnostics list those calls by tool)"),
    ("bootstrap_over_all_paired_tasks",
     "D. The bootstrap draws from all paired tasks, not only from the kept ones"),
)

# Counters for everything that could make a rule ambiguous. Printed in the diagnostics,
# so a key that is absent there means the question never came up in this data.
NOTES = {}
PHASE = [""]


def note(key, amount=1):
    key = PHASE[0] + key
    NOTES[key] = NOTES.get(key, 0) + amount


# --------------------------------------------------------------------------- paths


def norm_path(path):
    """Strip a leading a/ or b/; then strip a leading /workspace/, workspace/ or ./ ."""
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    for prefix in ("/workspace/", "workspace/", "./"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    return path


# --------------------------------------------------------------------------- diffs


def _header_name(text):
    """The file name of a '--- ' or '+++ ' header line (the text after the 4-char marker)."""
    text = text.rstrip("\r")
    if "\t" in text:  # the "name<TAB>timestamp" form of plain diff
        note("patch header with a TAB (timestamp form; text after the TAB dropped)")
        text = text.split("\t", 1)[0]
    return text


def _git_line_name(rest):
    """The 'a/<name>' part of a 'diff --git a/<name> b/<name>' line (text after 'diff --git ')."""
    rest = rest.rstrip("\r")
    half = (len(rest) - 1) // 2
    if len(rest) % 2 == 1 and rest[half:half + 1] == " ":
        left, right = rest[:half], rest[half + 1:]
        if left.startswith("a/") and right.startswith("b/") and left[2:] == right[2:]:
            return left
    found = re.match(r"^(a/.+?) b/.+$", rest)
    return found.group(1) if found else None


def parse_patch(text):
    """Unified diff -> ({normalised path: [(old_start, old_len, body lines), ...]}, deleted paths).

    Hunk bodies are delimited by the line counts of the hunk header, so a removed line
    whose text begins with '-- ' cannot be mistaken for a file header. Lines are split
    on '\\n' only (str.splitlines would also split on a form feed inside a source line).
    A file is named by its '--- ' line, or by its '+++ ' line when the '--- ' line is
    /dev/null. A section with a 'diff --git' line and no ---/+++ pair (an empty new
    file, a mode change) is kept as a file with no hunk.
    """
    lines = text.split("\n")
    total = len(lines)
    sections = []
    current = None
    i = 0
    while i < total:
        line = lines[i]
        if line.startswith("diff --git "):
            current = {"git": line[len("diff --git "):], "old": None, "new": None, "hunks": []}
            sections.append(current)
            i += 1
            continue
        if line.startswith("--- ") and i + 1 < total and lines[i + 1].startswith("+++ "):
            if current is None or current["old"] is not None:
                current = {"git": None, "old": None, "new": None, "hunks": []}
                sections.append(current)
            current["old"] = _header_name(line[4:])
            current["new"] = _header_name(lines[i + 1][4:])
            i += 2
            continue
        header = HUNK_HEADER.match(line)
        if header is None:
            i += 1
            continue
        old_start = int(header.group(1))
        old_len = 1 if header.group(2) is None else int(header.group(2))
        new_len = 1 if header.group(4) is None else int(header.group(4))
        body = []
        seen_old = seen_new = 0
        i += 1
        while i < total and (seen_old < old_len or seen_new < new_len):
            entry = lines[i]
            if entry.startswith("\\"):
                pass
            elif entry.startswith("+"):
                seen_new += 1
            elif entry.startswith("-"):
                seen_old += 1
            elif entry.startswith(" "):
                seen_old += 1
                seen_new += 1
            elif entry == "":
                note("empty line inside a hunk (read as a context line)")
                seen_old += 1
                seen_new += 1
            else:
                break
            body.append(entry)
            i += 1
        while i < total and lines[i].startswith("\\"):  # "\ No newline at end of file"
            body.append(lines[i])
            i += 1
        if seen_old != old_len or seen_new != new_len:
            note("hunk shorter or longer than its header says")
        if old_len == 0 and old_start != 0:
            note("hunk with old length 0 and old start above 0")
        if current is None:
            note("hunk with no file header before it (dropped)")
            continue
        current["hunks"].append((old_start, old_len, body))

    files = {}
    deleted = set()
    for section in sections:
        old, new = section["old"], section["new"]
        raw = None
        gone = False
        if old is None:  # no ---/+++ pair in this section
            if section["git"] is not None:
                raw = _git_line_name(section["git"])
                note("file section with no ---/+++ pair (named by its diff --git line)")
        elif OPTIONS["name_files_by_plus_line_only"]:
            raw = None if new == "/dev/null" else new
        elif old != "/dev/null":
            raw = old
            if new == "/dev/null":
                gone = True
                note("file section whose +++ line is /dev/null (a deleted file, named by its --- line)")
            elif norm_path(new) != norm_path(old):
                note("file section whose old and new names differ (old name used)")
        elif new != "/dev/null":
            raw = new
        if raw is None:
            note("file section with no usable name (dropped)")
            continue
        path = norm_path(raw)
        if path in files:
            note("same file in two sections of one patch (hunks merged)")
        files.setdefault(path, []).extend(section["hunks"])
        if gone:
            deleted.add(path)
    return files, deleted


def is_created(hunks):
    """Created file: every hunk has old range -0,0 (true as well for a file with no hunk)."""
    return all(old_start == 0 and old_len == 0 for old_start, old_len, _ in hunks)


def hunk_region(old_start, body):
    """The changed region of one hunk in old-file line numbers, or None."""
    counter = old_start
    points = []
    previous = None  # kind of the last line walked: "context", "removed" or "added"
    opened = False   # only used by the other reading A
    for entry in body:
        if entry.startswith("\\"):
            continue
        if entry.startswith("-"):
            points.append(counter)
            counter += 1
            previous = "removed"
            opened = False
        elif entry.startswith("+"):
            if OPTIONS["second_added_line_opens_block"]:
                insertion = previous != "removed" and not opened
            else:
                insertion = previous != "removed" and previous != "added"
            if insertion:
                points.append(max(counter - 1, 1))
                points.append(counter)
                opened = True
            previous = "added"
        else:
            counter += 1
            previous = "context"
            opened = False
    if not points:
        return None
    return (min(points), max(points))


def file_regions(hunks):
    regions = []
    for old_start, _old_len, body in hunks:
        region = hunk_region(old_start, body)
        if region is not None:
            regions.append(region)
    return regions


def overlap(start, end, region):
    return not (end < region[0] or start > region[1])


def gold_files(reference_patch):
    """{path: [regions]} for the modified files of the reference patch that have a region."""
    gold = {}
    files, _deleted = parse_patch(reference_patch)
    for path, hunks in files.items():
        if is_created(hunks):
            continue
        regions = file_regions(hunks)
        if regions:
            gold[path] = regions
    return gold


def final_patch_facts(patch, gold):
    """(not empty, touches a gold file, overlaps a changed region)."""
    if not isinstance(patch, str) or not patch.strip():
        return False, False, False
    touches = overlaps = False
    files, deleted = parse_patch(patch)
    for path, hunks in files.items():
        if path not in gold:
            continue
        touches = True
        if is_created(hunks):
            note("a file the patch creates is a gold file (touches: yes; overlap: not tested)")
            continue
        if path in deleted:
            note("a file the patch deletes is a gold file (a modified file by the rule)")
        for start, end in file_regions(hunks):
            if any(overlap(start, end, region) for region in gold[path]):
                overlaps = True
    return True, touches, overlaps


def self_test():
    """The rules on hand-made input."""
    PHASE[0] = "self-test: "
    ctx = " x"
    assert hunk_region(10, [ctx, ctx, ctx, "-a", "+b", ctx, ctx, ctx]) == (13, 13)
    assert hunk_region(10, [ctx, ctx, ctx, "-a", "+b", "+c", ctx, ctx]) == (13, 13)
    assert hunk_region(10, [ctx, ctx, ctx, "+a", "+b", ctx, ctx, ctx]) == (12, 13)
    assert hunk_region(1, ["+a", ctx, ctx, ctx]) == (1, 1)
    assert hunk_region(5, [ctx, "-a", "-b", ctx, ctx]) == (6, 7)
    assert hunk_region(1, [ctx, "-a", "+b", ctx, "+c", ctx]) == (2, 4)
    assert hunk_region(7, [ctx, "-a", "\\ No newline at end of file", "+b", "+c"]) == (8, 8)
    assert hunk_region(3, [ctx, ctx]) is None
    assert hunk_region(1, ["-a", "-b", "-c"]) == (1, 3)
    sample = ("--- a/pkg/m.py\n+++ b/pkg/m.py\n@@ -3,4 +3,5 @@\n x\n--- y\n+z\n+w\n x\n x\n"
              "--- a/n.py\n+++ b/n.py\n@@ -0,0 +1 @@\n+q")
    files, deleted = parse_patch(sample)
    assert list(files) == ["pkg/m.py", "n.py"] and not deleted
    assert file_regions(files["pkg/m.py"]) == [(4, 4)] and not is_created(files["pkg/m.py"])
    assert is_created(files["n.py"])
    assert gold_files(sample) == {"pkg/m.py": [(4, 4)]}
    git = ("diff --git a/e/__init__.py b/e/__init__.py\nnew file mode 100644\nindex 000..e69\n"
           "diff --git a/d.py b/d.py\ndeleted file mode 100644\nindex 1..0\n--- a/d.py\n+++ /dev/null\n"
           "@@ -1,2 +0,0 @@\n-a\n-b\n"
           "diff --git a/c.py b/c.py\nnew file mode 100644\nindex 0..1\n--- /dev/null\n+++ b/c.py\n"
           "@@ -0,0 +1,2 @@\n+a\n+b\n")
    files, deleted = parse_patch(git)
    assert list(files) == ["e/__init__.py", "d.py", "c.py"] and deleted == {"d.py"}
    assert files["e/__init__.py"] == [] and is_created(files["e/__init__.py"])
    assert file_regions(files["d.py"]) == [(1, 2)] and not is_created(files["d.py"])
    assert is_created(files["c.py"])
    assert final_patch_facts(git, {"d.py": [(2, 2)]}) == (True, True, True)
    assert final_patch_facts(git, {"z.py": [(2, 2)]}) == (True, False, False)
    assert final_patch_facts("  \n", {"d.py": [(2, 2)]}) == (False, False, False)
    assert norm_path("a//workspace/x.py") == "x.py" and norm_path("./x.py") == "x.py"
    assert norm_path("/workspace/d/x.py") == "d/x.py" and norm_path("b/d/x.py") == "d/x.py"
    ok = {"status": "ok", "filepath": "d.py", "start_line": 1, "end_line": 9, "total_lines": 9, "content": "{}"}
    step = lambda name, obs: {"tool_calls": [{"function_name": name, "arguments": {}}], "observation": obs}
    trace = {"steps": [
        {"message": "no call"},
        step("run_command", {"content": json.dumps({"status": "ok", "stdout": ""})}),
        step("read_file", {"content": json.dumps(dict(ok, start_line=3))}),
        step("edit_file", {"content": json.dumps({"error": "refused"})}),
        step("read_file", {"content": json.dumps({"result": json.dumps(ok)})}),
        step("read_file", ok),
        step("read_file", [{"content": json.dumps(dict(ok, status="error"))}]),
    ]}
    calls = trace_calls(trace)
    assert [c[0] for c in calls] == ["run_command", "read_file", "edit_file", "read_file", "read_file", "read_file"]
    assert [c[1] for c in calls] == [True, True, False, True, True, True]
    assert [c[2] is not None for c in calls] == [False, True, False, True, True, False]
    assert first_shown(calls, {"d.py": [(2, 2)]}) == 4
    assert first_shown(calls, {"d.py": [(5, 6)]}) == 2
    assert first_shown(calls, {"e.py": [(5, 6)]}) is None
    NOTES.clear()
    PHASE[0] = ""


# --------------------------------------------------------------------------- traces


def tool_result(observation, shape, depth=0):
    """Unwrap a step's observation to the tool's result object (a dict), or None.

    Handles a JSON string, a dict that already is the result (it has 'status'), a
    wrapper dict holding the result under content / result / results / output, and a
    list of results (the last usable one, since the step's result goes to its last call).
    'shape' collects the path taken, for the diagnostics.
    """
    if depth > 8:
        return None
    if isinstance(observation, str):
        shape.append("JSON string")
        try:
            value = json.loads(observation)
        except ValueError:
            shape.append("not JSON")
            return None
        if isinstance(value, (dict, list, str)):
            return tool_result(value, shape, depth + 1)
        shape.append(type(value).__name__)
        return None
    if isinstance(observation, list):
        for item in reversed(observation):
            trial = ["list"]
            found = tool_result(item, trial, depth + 1)
            if found is not None:
                shape.extend(trial)
                return found
        shape.append("list with no result")
        return None
    if isinstance(observation, dict):
        if "status" in observation:
            shape.append("object with status")
            return observation
        for key in ("content", "result", "results", "output"):
            if key in observation:
                trial = ["dict key '%s'" % key]
                found = tool_result(observation[key], trial, depth + 1)
                if found is not None:
                    shape.extend(trial)
                    return found
        shape.append("dict with no status")
        return None
    shape.append(type(observation).__name__)
    return None


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def trace_calls(trace):
    """A trace -> its tool calls in run order, one tuple per call:

        (function name, the call's result has a status field, read)

    where read is (path, start_line, end_line) for a read_file call whose result has
    status ok, and None for every other call. A step's result belongs to its last call.
    """
    calls = []
    steps = trace.get("steps") if isinstance(trace, dict) else None
    if not isinstance(steps, list):
        note("trace without a list of steps")
        return calls
    ids = [s.get("step_id") for s in steps if isinstance(s, dict) and is_integer(s.get("step_id"))]
    if any(b <= a for a, b in zip(ids, ids[1:])):
        note("trace whose step_id values do not increase in list order")
    for step in steps:
        if not isinstance(step, dict):
            continue
        tool_calls = step.get("tool_calls")
        if not isinstance(tool_calls, list) or not tool_calls:
            if step.get("observation") is not None:
                note("step with an observation and no tool call")
            continue
        if len(tool_calls) > 1:
            note("step with several tool calls (its result given to the last)")
        for position, call in enumerate(tool_calls):
            name = call.get("function_name") if isinstance(call, dict) else None
            result = None
            if position == len(tool_calls) - 1:
                shape = []
                result = tool_result(step.get("observation"), shape)
                if name == "read_file":
                    note("read_file result stored as: " + " > ".join(shape))
            read = None
            if name == "read_file" and isinstance(result, dict) and result.get("status") == "ok":
                path = result.get("filepath")
                if not isinstance(path, str) or not path:
                    note("ok read_file result without a filepath (the call's argument used)")
                    arguments = call.get("arguments")
                    path = arguments.get("filepath") if isinstance(arguments, dict) else None
                if isinstance(path, str) and (path.startswith("a/") or path.startswith("b/")):
                    note("ok read_file path starting with a/ or b/ (the path rule strips it)")
                read = (path, result.get("start_line"), result.get("end_line"))
            calls.append((name, isinstance(result, dict) and "status" in result, read))
    return calls


def first_shown(calls, gold):
    """Call index of the first read_file that shows a changed line, or None."""
    index = 0
    for _name, has_status, read in calls:
        if OPTIONS["skip_calls_without_status"] and not has_status:
            continue
        index += 1
        if read is None:
            continue
        path, start, end = read
        if not isinstance(path, str):
            continue
        regions = gold.get(norm_path(path))
        if not regions:
            continue
        if not (is_integer(start) and is_integer(end)):
            note("ok read_file of a gold file with a non-integer start_line or end_line (not counted)")
            continue
        if any(overlap(start, end, region) for region in regions):
            return index
    return None


# --------------------------------------------------------------------------- loading


def find_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.getcwd(), os.path.dirname(here)):
        if os.path.isfile(os.path.join(candidate, "data", "tasks.jsonl")):
            return candidate
    sys.exit("data/tasks.jsonl not found: run this from the repository root")


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def is_resolved(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    if value is not None:
        note("resolved value that is neither a boolean nor a string (read as not resolved)")
    return False


def load_inputs(root):
    """Everything the derivation needs, read once."""
    inputs = {"tasks": [], "calls": {}, "records": {}}

    PHASE[0] = "tasks.jsonl: "
    seen = set()
    for row in read_jsonl(os.path.join(root, "data", "tasks.jsonl")):
        if row["instance_id"] in seen:
            note("instance_id twice (last kept)")
        seen.add(row["instance_id"])
        inputs["tasks"].append((row["instance_id"], row.get("patch") or ""))

    for notebook in NOTEBOOKS:
        e2e_dir = os.path.join(root, "data", "graphloc", "out", notebook, "e2e")

        PHASE[0] = "traces (all, before any filter): "
        for arm in ARMS:
            found = {}
            arm_dir = os.path.join(e2e_dir, "results", arm)
            for worker in sorted(os.listdir(arm_dir)):
                traces_dir = os.path.join(arm_dir, worker, "traces")
                if not (worker.startswith("w") and os.path.isdir(traces_dir)):
                    continue
                for name in sorted(os.listdir(traces_dir)):
                    if not (name.startswith("trace_") and name.endswith(".json")):
                        continue
                    task = name[len("trace_"):-len(".json")]
                    if task in found:
                        note("task with two traces in one arm of one notebook (first kept)")
                        continue
                    with open(os.path.join(traces_dir, name), encoding="utf-8") as handle:
                        found[task] = trace_calls(json.load(handle))
            inputs["calls"][(notebook, arm)] = found

        PHASE[0] = "records: "
        found = {}
        records_dir = os.path.join(e2e_dir, "records")
        for name in sorted(os.listdir(records_dir)):
            if not (name.startswith("rec_w") and name.endswith(".jsonl")):
                continue
            for row in read_jsonl(os.path.join(records_dir, name)):
                key = (row.get("arm"), row.get("id"))
                if key in found:
                    note("two records for one (arm, task) in one notebook (last kept)")
                found[key] = {
                    "resolved": is_resolved(row.get("resolved")),
                    "patch": row.get("patch"),
                    "tool_calls": row.get("tool_calls"),
                }
        inputs["records"][notebook] = found
    PHASE[0] = ""
    return inputs


# --------------------------------------------------------------------------- derivation


def derive(inputs):
    """Apply the rules. Returns the pairs, the kept pairs and one row per run of a kept pair."""
    PHASE[0] = "reference patches: "
    gold_by_task = {}
    for instance_id, patch in inputs["tasks"]:
        gold_by_task[instance_id] = gold_files(patch)

    PHASE[0] = "pairs: "
    pairs = []
    for notebook in NOTEBOOKS:
        base = inputs["calls"][(notebook, "base")]
        skill = inputs["calls"][(notebook, "skill")]
        if set(base) ^ set(skill):
            note("task with a trace in one arm only (no pair)", len(set(base) ^ set(skill)))
        pairs.extend((notebook, task) for task in sorted(set(base) & set(skill)))
    kept = [(notebook, task) for notebook, task in pairs if gold_by_task.get(task)]

    runs = {}
    for notebook, task in kept:
        gold = gold_by_task[task]
        for arm in ARMS:
            calls = inputs["calls"][(notebook, arm)][task]
            PHASE[0] = "reads: "
            first = first_shown(calls, gold)
            record = inputs["records"][notebook].get((arm, task))
            if record is None:
                PHASE[0] = "records: "
                note("run with a trace and no record (read as not resolved, empty patch)")
                record = {"resolved": False, "patch": "", "tool_calls": None}
            PHASE[0] = "agent patches: "
            not_empty, touches, overlaps = final_patch_facts(record["patch"], gold)
            runs[(notebook, task, arm)] = {
                "first": first,
                "calls": len(calls),
                "calls_without_status": [c[0] for c in calls if not c[1]],
                "record_tool_calls": record["tool_calls"],
                "resolved": record["resolved"],
                "not_empty": not_empty,
                "touches": touches,
                "overlaps": overlaps,
            }
    PHASE[0] = ""
    return {
        "gold_by_task": gold_by_task,
        "pairs": pairs,
        "kept": kept,
        "paired_tasks": sorted({task for _, task in pairs}),
        "kept_tasks": sorted({task for _, task in kept}),
        "runs": runs,
    }


# --------------------------------------------------------------------------- report


def pct(count, total):
    return "n/a" if total == 0 else "%.1f%%" % (100.0 * count / total)


def share(count, total):
    return "%d of %d (%s)" % (count, total, pct(count, total))


def median(values):
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        return None
    middle = size // 2
    if size % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def number(value):
    if value is None:
        return "n/a"
    if float(value).is_integer():
        return str(int(value))
    return "%.1f" % value


def sections(data):
    """Sections 1 to 6 as a list of lines."""
    pairs, kept, runs = data["pairs"], data["kept"], data["runs"]
    kept_tasks, gold_by_task = data["kept_tasks"], data["gold_by_task"]
    out = []
    say = out.append

    # ---- 1
    dropped = [task for task in data["paired_tasks"] if not gold_by_task.get(task)]
    unknown = [task for task in dropped if task not in gold_by_task]
    say("1. PAIRS")
    say("   pairs (notebook, task) with a base and a skill trace: %d" % len(pairs))
    say("   pairs kept (the task has a gold file):                %d" % len(kept))
    say("   distinct tasks kept:                                  %d" % len(kept_tasks))
    say("   distinct tasks in the pairs:                          %d" % len(data["paired_tasks"]))
    say("   tasks in the pairs with no gold file (%d): %s" % (len(dropped), ", ".join(dropped) or "none"))
    if unknown:
        say("   of those, not in tasks.jsonl at all: " + ", ".join(unknown))
    say("")

    # ---- 2
    say("2. PER ARM, over the kept pairs")
    for arm in ARMS:
        rows = [runs[(notebook, task, arm)] for notebook, task in kept]
        total = len(rows)
        firsts = [row["first"] for row in rows if row["first"] is not None]
        say("   arm %s" % arm)
        say("      runs:                          %d" % total)
        say("      resolved:                      %s" % share(sum(row["resolved"] for row in rows), total))
        say("      ever shown a changed line:     %s" % share(len(firsts), total))
        for limit in WITHIN:
            say("      shown within %2d calls:         %s"
                % (limit, share(sum(1 for f in firsts if f <= limit), total)))
        say("      median call index (runs ever shown, n = %d): %s" % (len(firsts), number(median(firsts))))
    say("")

    # ---- 3
    say("3. PAIRS WHERE BOTH ARMS WERE EVER SHOWN")
    both_shown = [
        (notebook, task)
        for notebook, task in kept
        if runs[(notebook, task, "base")]["first"] is not None
        and runs[(notebook, task, "skill")]["first"] is not None
    ]
    deltas = [runs[(n, t, "skill")]["first"] - runs[(n, t, "base")]["first"] for n, t in both_shown]
    say("   pairs:                                %d" % len(both_shown))
    say("   distinct tasks:                       %d" % len({task for _, task in both_shown}))
    if deltas:
        say("   mean of (skill index - base index):   %+.2f   (exactly %d / %d = %+.4f)"
            % (sum(deltas) / len(deltas), sum(deltas), len(deltas), sum(deltas) / len(deltas)))
        say("   median of (skill index - base index): %s" % number(median(deltas)))
        say("   pairs with skill earlier / same call / skill later: %d / %d / %d"
            % (sum(1 for d in deltas if d < 0), sum(1 for d in deltas if d == 0), sum(1 for d in deltas if d > 0)))
    say("")

    # ---- 4
    say("4. BOTH ARMS POOLED")
    pooled = list(runs.items())
    total = len(pooled)
    shown = [(key, row) for key, row in pooled if row["first"] is not None]
    never = [(key, row) for key, row in pooled if row["first"] is None]
    unresolved = [(key, row) for key, row in pooled if not row["resolved"]]
    say("   runs:                                          %d" % total)
    say("   shown a changed line:                          %s" % share(len(shown), total))
    say("   final patch not empty:                         %s" % share(sum(row["not_empty"] for _, row in pooled), total))
    say("   final patch touches a gold file:               %s" % share(sum(row["touches"] for _, row in pooled), total))
    say("   final patch overlaps a changed region:         %s" % share(sum(row["overlaps"] for _, row in pooled), total))
    say("   resolved:                                      %s" % share(sum(row["resolved"] for _, row in pooled), total))
    say("   among runs NOT resolved, shown a changed line: %s"
        % share(sum(1 for _, row in unresolved if row["first"] is not None), len(unresolved)))
    say("   among runs shown, final patch overlaps:        %s" % share(sum(row["overlaps"] for _, row in shown), len(shown)))
    say("   among runs shown, resolved:                    %s" % share(sum(row["resolved"] for _, row in shown), len(shown)))
    say("   among runs never shown, resolved:              %s" % share(sum(row["resolved"] for _, row in never), len(never)))
    never_tasks = sorted({key[1] for key, _ in never})
    shown_tasks = {key[1] for key, _ in shown}
    never_in_any = [task for task in kept_tasks if task not in shown_tasks]
    say("   never-shown runs:                              %d" % len(never))
    say("   distinct tasks holding the never-shown runs:   %d" % len(never_tasks))
    say("   tasks never shown in any of their runs:        %d  (%s)" % (len(never_in_any), ", ".join(never_in_any) or "none"))
    say("")

    # ---- 5
    say("5. QUANTITY C = (never-shown runs / all runs) x (resolved rate among shown - resolved rate among never shown)")
    if shown and never:
        rate_shown = Fraction(sum(row["resolved"] for _, row in shown), len(shown))
        rate_never = Fraction(sum(row["resolved"] for _, row in never), len(never))
        quantity = Fraction(len(never), total) * (rate_shown - rate_never)
        say("   never-shown share:               %s" % share(len(never), total))
        say("   resolved rate among shown:       %s" % share(sum(row["resolved"] for _, row in shown), len(shown)))
        say("   resolved rate among never shown: %s" % share(sum(row["resolved"] for _, row in never), len(never)))
        say("   C = %.1f%%   (unrounded %.4f%%)" % (100 * float(quantity), 100 * float(quantity)))
    else:
        say("   not defined: one of the two groups is empty")
    say("")

    # ---- 6
    say("6. BOOTSTRAP over tasks: share of skill runs shown within %d calls - share of base runs shown within %d calls"
        % (BOOT_WITHIN, BOOT_WITHIN))
    per_task = {}
    for notebook, task in kept:
        cell = per_task.setdefault(task, [0, 0, 0, 0])  # skill hits, skill runs, base hits, base runs
        for offset, arm in ((0, "skill"), (2, "base")):
            first = runs[(notebook, task, arm)]["first"]
            cell[offset] += 1 if (first is not None and first <= BOOT_WITHIN) else 0
            cell[offset + 1] += 1
    hits_skill = sum(cell[0] for cell in per_task.values())
    runs_skill = sum(cell[1] for cell in per_task.values())
    hits_base = sum(cell[2] for cell in per_task.values())
    runs_base = sum(cell[3] for cell in per_task.values())
    point = Fraction(hits_skill, runs_skill) - Fraction(hits_base, runs_base)
    task_list = data["paired_tasks"] if OPTIONS["bootstrap_over_all_paired_tasks"] else kept_tasks
    rng = random.Random(BOOT_SEED)
    values = []
    for _ in range(BOOT_DRAWS):
        a = b = c = d = 0
        for _ in range(len(task_list)):
            cell = per_task.get(rng.choice(task_list), (0, 0, 0, 0))
            a += cell[0]
            b += cell[1]
            c += cell[2]
            d += cell[3]
        values.append(Fraction(a, b) - Fraction(c, d))
    values.sort()
    low, high = values[BOOT_LOW_INDEX], values[BOOT_HIGH_INDEX]
    say("   skill: %s    base: %s" % (share(hits_skill, runs_skill), share(hits_base, runs_base)))
    say("   difference (skill - base): %+.1f points   (unrounded %+.4f)" % (100 * float(point), 100 * float(point)))
    say("   95%% interval: %d resamples of %d tasks, random.Random(%d), sorted values at indices %d and %d"
        % (BOOT_DRAWS, len(task_list), BOOT_SEED, BOOT_LOW_INDEX, BOOT_HIGH_INDEX))
    say("      [%+.1f, %+.1f] points   (unrounded [%+.4f, %+.4f])"
        % (100 * float(low), 100 * float(high), 100 * float(low), 100 * float(high)))
    return out


def diagnostics(data):
    kept, runs, gold_by_task = data["kept"], data["runs"], data["gold_by_task"]
    out = []
    say = out.append
    say("DIAGNOSTICS (not asked for: what the data looked like where a rule could be read two ways)")
    say("   reference patches: %d tasks in tasks.jsonl, %d with a gold file; the %d kept tasks have %d gold files and %d regions"
        % (len(gold_by_task), sum(1 for g in gold_by_task.values() if g), len(data["kept_tasks"]),
           sum(len(gold_by_task[t]) for t in data["kept_tasks"]),
           sum(len(r) for t in data["kept_tasks"] for r in gold_by_task[t].values())))
    say("   per notebook and arm: runs / resolved / ever shown / shown within %d calls" % BOOT_WITHIN)
    for notebook in NOTEBOOKS:
        for arm in ARMS:
            rows = [runs[(n, t, arm)] for n, t in kept if n == notebook]
            say("      %-42s %-5s %3d / %3d / %3d / %3d" % (
                notebook, arm, len(rows), sum(r["resolved"] for r in rows),
                sum(1 for r in rows if r["first"] is not None),
                sum(1 for r in rows if r["first"] is not None and r["first"] <= BOOT_WITHIN)))
    counts = [r["calls"] for r in runs.values()]
    say("   tool calls in the traces of the kept runs: %d in all; per run min %d, median %s, max %d"
        % (sum(counts), min(counts), number(median(counts)), max(counts)))
    by_tool = {}
    for row in runs.values():
        for name in row["calls_without_status"]:
            by_tool[name] = by_tool.get(name, 0) + 1
    say("   of those calls, %d have a result with no status field, in %d runs; by tool: %s"
        % (sum(by_tool.values()), sum(1 for r in runs.values() if r["calls_without_status"]),
           ", ".join("%s %d" % (name, by_tool[name]) for name in sorted(by_tool, key=str)) or "none"))
    say("      (they are counted in the call index, as every tool call is; reading C below leaves them out)")
    more = sum(1 for r in runs.values() if is_integer(r["record_tool_calls"]) and r["calls"] > r["record_tool_calls"])
    say("   runs whose trace holds more tool calls than the tool_calls field of their record: %d of %d"
        % (more, len(runs)))
    say("   shown only in base / only in skill / in neither arm (pairs): %d / %d / %d" % (
        sum(1 for n, t in kept if runs[(n, t, "base")]["first"] is not None and runs[(n, t, "skill")]["first"] is None),
        sum(1 for n, t in kept if runs[(n, t, "base")]["first"] is None and runs[(n, t, "skill")]["first"] is not None),
        sum(1 for n, t in kept if runs[(n, t, "base")]["first"] is None and runs[(n, t, "skill")]["first"] is None)))
    say("   notes (count, where: what):")
    if NOTES:
        for key in sorted(NOTES):
            say("      %6d  %s" % (NOTES[key], key))
    else:
        say("      none")
    return out


def main():
    self_test()
    inputs = load_inputs(find_root())
    data = derive(inputs)
    lines = sections(data)

    print("INDEPENDENT RE-DERIVATION 3: when a run is first shown a changed line (base and skill arms)")
    print("notebooks: " + ", ".join(NOTEBOOKS))
    print("")
    print("\n".join(lines))
    print("")
    print("\n".join(diagnostics(data)))
    print("")

    print("OTHER READINGS OF THE RULES (not the rules: only to explain a difference with another implementation)")
    print("Each reading is switched on alone; the lines of sections 1 to 6 that change are listed.")
    saved = dict(NOTES)
    for option, label in VARIANTS:
        OPTIONS[option] = True
        try:
            other = sections(derive(inputs))
        finally:
            OPTIONS[option] = False
        print("")
        print(label)
        changed = [(a, b) for a, b in zip(lines, other) if a != b]
        if not changed:
            print("      no line of sections 1 to 6 changes")
        for a, b in changed:
            print("      as written: " + a.strip())
            print("      this way:   " + b.strip())
    NOTES.clear()
    NOTES.update(saved)


if __name__ == "__main__":
    main()
