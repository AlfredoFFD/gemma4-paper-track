#!/usr/bin/env python3
"""Independent re-derivation of the registered results of pre-registration 14
(whole runs scored by tests) from the raw outputs of the run.

Usage:  py -I -X utf8 analysis/rederive_14.py <root> [--no-write]

<root> is analysis/results/14. Read under <root>: the two harness results
directories N/seed1 and NAF/seed1 (task_results.jsonl, extra.jsonl, patches/,
traces/) and validate/tasks_ok.txt. Read beside the analysis folder:
data/tasks.jsonl (the reference patches). The script prints a report and,
unless --no-write is given, writes the same text to
analysis/results/rederive_14.txt with LF line endings.

It imports nothing from the repository and uses only the standard library.
Every definition is implemented from its written statement, not from the
project's analysis code or its stored output. Section 6 of the report lists
the choices made where that statement left room.
"""
import json
import os
import random
import re
import shlex
import sys
import textwrap

CONDITIONS = ("N", "NAF")
THRESHOLDS = (3, 5, 8, 10, 20)
RULE_THRESHOLD = 8
MIN_TASKS = 60
BOOT_RESAMPLES = 2000
BOOT_SEED = 14
OUTPUT_CAP = 5000
WIDTH = 112
INF = float("inf")

INFRA_PHRASES = (
    "Snapshot file not found",
    "Unexpected evaluation worker error",
    "Missing test specification",
    "Failed to apply test_patch",
    "Evaluation error:",
)
SERVICE_KIND = "Sandbox execution error naming a failure of the model service"
SERVICE_WORDS = re.compile(
    r"connection|connect\w*error|server|service ?unavailable|bad gateway|time[ _-]?out|timed out"
    r"|rate[ _-]?limit|too many requests|authenticat|unauthori[sz]ed|api[ _-]?key|permission ?denied",
    re.IGNORECASE,
)
CONTEXT_WORDS = re.compile(r"context ?window|context length", re.IGNORECASE)
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
VIEW_KINDS = ("cat", "head", "tail", "sed")
VIEWERS = VIEW_KINDS + ("awk", "nl", "less", "more", "tac", "bat")
WRITTEN, RETURNED, WHOLE = 4, 5, 6  # positions, in a view, of the three readings of the lines shown


# ----------------------------------------------------------------- reading

def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def norm_path(path):
    """Remove any leading /workspace/, workspace/ or ./ (repeatedly)."""
    path = path.strip()
    again = True
    while again:
        again = False
        for prefix in ("/workspace/", "workspace/", "./"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                again = True
    return path


# ----------------------------------------------------------------- patches

def unquote(text):
    """Undo git's quoting of an unusual path ("a/b\\"c")."""
    simple = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            if text[i + 1] in simple:
                out.append(simple[text[i + 1]])
                i += 2
                continue
            octal = re.match(r"[0-7]{1,3}", text[i + 1:])
            if octal:
                out.append(chr(int(octal.group(0), 8)))
                i += 1 + len(octal.group(0))
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def header_path(text):
    """Path named on a '--- ' or '+++ ' line; None for /dev/null."""
    text = text.rstrip("\r")
    if text.startswith('"'):
        end = text.rfind('"')
        if end > 0:
            text = unquote(text[1:end])
    elif "\t" in text:
        text = text.split("\t", 1)[0]
    text = text.strip()
    if text == "/dev/null":
        return None
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    return norm_path(text)


def new_file_record():
    return {"old": None, "new": None, "named": False, "created": False, "deleted": False, "hunks": []}


def parse_patch(text):
    """Files of a unified diff, with or without 'diff --git' lines.

    A hunk body is delimited by the line counts of its header, so that a
    '--- a/...' file header that follows a hunk is not read as a removed line.
    Returns (files, skipped). A file is a dict with old, new, created, deleted
    and hunks; a hunk is (old_start, old_count, new_start, new_count, tags,
    complete), tags being ' ', '-', '+' in order and complete saying that the
    body held the counts of its header. skipped counts lines inside hunks that
    are not diff lines.
    """
    lines = text.split("\n")
    total = len(lines)
    files = []
    current = None
    skipped = 0
    i = 0
    while i < total:
        line = lines[i]
        if line.startswith("diff --git "):
            current = new_file_record()
            files.append(current)
            i += 1
            continue
        if line.startswith("--- ") and i + 1 < total and lines[i + 1].startswith("+++ "):
            if current is None or current["named"]:
                current = new_file_record()
                files.append(current)
            current["old"] = header_path(line[4:])
            current["new"] = header_path(lines[i + 1][4:])
            current["named"] = True
            if current["old"] is None:
                current["created"] = True
            if current["new"] is None:
                current["deleted"] = True
            i += 2
            continue
        match = HUNK_RE.match(line)
        if match and current is not None and current["named"]:
            old_start = int(match.group(1))
            old_count = 1 if match.group(2) is None else int(match.group(2))
            new_start = int(match.group(3))
            new_count = 1 if match.group(4) is None else int(match.group(4))
            tags = []
            seen_old = seen_new = 0
            i += 1
            while i < total and (seen_old < old_count or seen_new < new_count):
                body = lines[i]
                first = body[:1]
                if first == " ":
                    tags.append(" ")
                    seen_old += 1
                    seen_new += 1
                elif first == "-":
                    tags.append("-")
                    seen_old += 1
                elif first == "+":
                    tags.append("+")
                    seen_new += 1
                elif first == "\\":
                    pass
                elif body.startswith("diff --git "):
                    break
                elif body.rstrip("\r") == "":
                    if i == total - 1:
                        break
                    tags.append(" ")
                    seen_old += 1
                    seen_new += 1
                else:
                    skipped += 1
                i += 1
            while i < total and lines[i].startswith("\\"):
                i += 1
            complete = seen_old == old_count and seen_new == new_count
            current["hunks"].append((old_start, old_count, new_start, new_count, tags, complete))
            continue
        if current is not None and not current["named"]:
            if line.startswith("new file mode"):
                current["created"] = True
            elif line.startswith("deleted file mode"):
                current["deleted"] = True
        i += 1
    for item in files:
        hunks = item["hunks"]
        if hunks and all(h[0] == 0 and h[1] == 0 for h in hunks):
            item["created"] = True  # the old side has no lines
        if hunks and all(h[2] == 0 and h[3] == 0 for h in hunks):
            item["deleted"] = True  # the new side has no lines
    return files, skipped


def hunk_pieces(old_start, old_count, tags):
    """Marked old-file lines of one hunk, as spans (first, last).

    The first piece is the span from the first to the last removed line, when
    the hunk removes any. Then, for each block of added lines that does not
    directly follow a removed line, the old line before and the old line after
    the place it is inserted, when those lines exist. Context lines are not
    marked.
    """
    if old_start == 0 and old_count == 0:
        return []  # the old file has no lines
    next_old = old_start if old_count > 0 else old_start + 1
    last_old = old_start + old_count - 1 if old_count > 0 else None
    removed = []
    around = []
    previous = None
    for tag in tags:
        if tag == " ":
            next_old += 1
        elif tag == "-":
            removed.append(next_old)
            next_old += 1
        elif previous not in ("-", "+"):
            pair = []
            if next_old - 1 >= 1:
                pair.append(next_old - 1)
            if last_old is None or next_old <= last_old:
                pair.append(next_old)
            if pair:
                around.append((pair[0], pair[-1]))
        previous = tag
    pieces = [(removed[0], removed[-1])] if removed else []
    return pieces + around


def hunk_region(old_start, old_count, tags):
    """The CHANGED REGION of one hunk: from its first to its last marked line."""
    pieces = hunk_pieces(old_start, old_count, tags)
    if not pieces:
        return None
    return (min(low for low, _ in pieces), max(high for _, high in pieces))


def changed_regions(patch_text):
    """({old path: [(first, last), ...]}, facts) over the files a patch modifies.

    Files the patch creates are left out. facts: files, created, emptied (the
    paths of files with a region whose new side has no lines), skipped (lines
    inside hunks that are not diff lines), short (hunks whose body does not
    hold the counts of its header), apart (the same regions kept as separate
    pieces, for a second reading of the definition).
    """
    files, skipped = parse_patch(patch_text)
    regions = {}
    facts = {"files": len(files), "created": 0, "emptied": set(), "skipped": skipped, "short": 0, "apart": {}}
    for item in files:
        facts["short"] += sum(1 for h in item["hunks"] if not h[5])
        if item["created"] or item["old"] is None:
            facts["created"] += 1
            continue
        found = []
        pieces = []
        for old_start, old_count, _new_start, _new_count, tags, _complete in item["hunks"]:
            region = hunk_region(old_start, old_count, tags)
            if region is not None:
                found.append(region)
                pieces.extend(hunk_pieces(old_start, old_count, tags))
        if found:
            regions.setdefault(item["old"], []).extend(found)
            facts["apart"].setdefault(item["old"], []).extend(pieces)
            if item["deleted"]:
                facts["emptied"].add(item["old"])
    return regions, facts


def overlaps(regions, first, last):
    for low, high in regions or ():
        if first <= high and low <= last:
            return True
    return False


def patch_overlaps(agent_regions, gold):
    """A region of the agent's patch in a GOLD FILE intersects a reference region."""
    for path, regions in agent_regions.items():
        for low, high in regions:
            if overlaps(gold.get(path), low, high):
                return True
    return False


# ------------------------------------------------------------------ traces

def load_calls(path):
    """Tool calls of a session in order: [(function name, arguments, result)]."""
    with open(path, encoding="utf-8") as handle:
        trace = json.load(handle)
    calls = []
    multi = 0
    unparsed = 0
    for step in trace.get("steps") or []:
        tool_calls = step.get("tool_calls") or []
        observation = step.get("observation")
        if len(tool_calls) > 1:
            multi += 1
        for tool_call in tool_calls:
            result = None
            if len(tool_calls) == 1 and isinstance(observation, dict):
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
    return calls, multi, unparsed


def count_lines(text):
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def shell_tokens(command):
    if not isinstance(command, str) or not command.strip():
        return None
    try:
        lexer = shlex.shlex(command.strip(), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def is_operator(token):
    return token != "" and all(ch in "();<>|&" for ch in token)


def parse_view_command(command):
    """(kind, path, lines) when the command is one simple command that views one
    file in a listed form: cat F; head -n K F or head -K F; tail -n K F or
    tail -K F; sed -n 'A,Bp' F (or 'Ap'). Anything else (a pipe, a grep, a
    second command, a redirection, another option) is None."""
    if not isinstance(command, str) or "\n" in command.strip() or "`" in command:
        return None
    tokens = shell_tokens(command)
    if not tokens or len(tokens) < 2 or any(is_operator(t) for t in tokens):
        return None
    program, path, middle = tokens[0], tokens[-1], tokens[1:-1]
    if path.startswith("-") or re.search(r"[*?\[\]{}$~]", path):
        return None
    if program == "cat":
        return ("cat", path, None) if not middle else None
    if program in ("head", "tail"):
        count = None
        if len(middle) == 2 and middle[0] == "-n" and middle[1].isdigit():
            count = int(middle[1])
        elif len(middle) == 1:
            match = re.fullmatch(r"-n?(\d+)", middle[0]) or re.fullmatch(r"--lines=(\d+)", middle[0])
            if match:
                count = int(match.group(1))
        if count is None or count < 1:
            return None
        return (program, path, count)
    if program == "sed" and len(middle) == 2 and middle[0] == "-n":
        match = re.fullmatch(r"(\d+)(?:,(\d+))?p", middle[1])
        if match:
            first = int(match.group(1))
            last = first if match.group(2) is None else int(match.group(2))
            if 1 <= first <= last:
                return ("sed", path, (first, last))
    return None


def command_output(result):
    if result.get("status") == "ok":
        out = result.get("stdout")
    else:
        details = result.get("details")
        out = details.get("stdout") if isinstance(details, dict) else None
    return out if isinstance(out, str) else ""


def names_viewed_file(command, gold):
    """cat, head, tail, sed, ... is run on a GOLD FILE somewhere in the command."""
    if not isinstance(command, str):
        return False
    for line in command.split("\n"):
        segment = []
        segments = [segment]
        for token in shell_tokens(line) or []:
            if is_operator(token):
                segment = []
                segments.append(segment)
            else:
                segment.append(token)
        for segment in segments:
            if segment and segment[0] in VIEWERS and any(norm_path(t) in gold for t in segment[1:]):
                return True
    return False


def session_views(calls, gold):
    """Every call that shows lines of one file.

    Returns (views, uncounted). A view is (index, source, kind, path, written,
    returned, whole): three readings of the lines shown. For (a) all three are
    the returned start_line..end_line. For (b), written follows the definition
    (cat: the lines in the first 5,000 characters of output; head: 1..K; tail:
    the last K; sed: A..B); returned cuts head and sed to the number of lines
    present in the output; whole also drops a last line that the cut at 5,000
    characters left unfinished. uncounted lists (index, command) of commands
    with output that run a viewer on a GOLD FILE in a form that is not counted.
    """
    views = []
    uncounted = []
    lengths = {}
    for index, (name, arguments, result) in enumerate(calls, 1):
        if name == "read_file":
            if result.get("status") != "ok":
                continue
            path = result.get("filepath")
            if not isinstance(path, str):
                path = arguments.get("filepath")
            first, last = result.get("start_line"), result.get("end_line")
            if not isinstance(path, str) or not is_int(first) or not is_int(last):
                continue
            path = norm_path(path)
            if is_int(result.get("total_lines")):
                lengths[path] = result["total_lines"]
            span = (first, last)
            views.append((index, "a", "read_file", path, span, span, span))
        elif name == "run_command":
            command = arguments.get("command")
            output = command_output(result)[:OUTPUT_CAP]
            parsed = parse_view_command(command)
            if parsed is None or output == "":
                if output != "" and names_viewed_file(command, gold):
                    uncounted.append((index, command))
                continue
            kind, path, lines = parsed
            path = norm_path(path)
            shown = count_lines(output)
            whole = shown - 1 if len(output) >= OUTPUT_CAP and not output.endswith("\n") else shown
            if kind == "cat":
                written = returned = (1, shown)
                complete = (1, whole)
            elif kind == "head":
                written = (1, lines)
                returned = (1, min(lines, shown))
                complete = (1, min(lines, whole))
            elif kind == "sed":
                written = lines
                returned = (lines[0], min(lines[1], lines[0] + shown - 1))
                complete = (lines[0], min(lines[1], lines[0] + whole - 1))
            else:  # tail: placed only when the length of the file is known from an earlier read
                if path not in lengths:
                    if path in gold:
                        uncounted.append((index, command))
                    continue
                end = lengths[path]
                written = returned = complete = (max(1, end - lines + 1), end)
            views.append((index, "b", kind, path, written, returned, complete))
    return views, uncounted


def first_shown(views, gold, reading=WRITTEN, shell=True):
    """T_SHOWN: the smallest call index at which a changed line is shown; INF if never.

    reading picks which lines a shell view is taken to show (WRITTEN is the
    definition); shell=False leaves the shell views out, that is (a) alone.
    """
    for view in views:
        if view[1] == "b" and not shell:
            continue
        first, last = view[reading]
        if overlaps(gold.get(view[3]), first, last):
            return view[0]
    return INF


def bound_names(arguments):
    """(carried, misspelled): the call carries a line bound; it carries one
    under a name that is not exactly start_line or end_line."""
    carried = misspelled = False
    for key in arguments:
        if not isinstance(key, str):
            continue
        if key in ("start_line", "end_line"):
            carried = True
        elif re.sub(r"[^a-z]", "", key.lower()) in ("startline", "endline"):
            carried = True
            misspelled = True
    return carried, misspelled


# ------------------------------------------------------------------- rules

def infra_kind(error):
    if not isinstance(error, str) or not error:
        return None
    for phrase in INFRA_PHRASES:
        if phrase in error:
            return phrase
    if ("Sandbox execution error" in error and not CONTEXT_WORDS.search(error)
            and "budget" not in error.lower() and SERVICE_WORDS.search(error)):
        return SERVICE_KIND
    return None


def error_kind(error):
    if not isinstance(error, str) or not error:
        return "no error"
    if CONTEXT_WORDS.search(error):
        return "context window"
    match = re.search(r"exceeded (.+?) budget", error)
    if match:
        return match.group(1) + " budget"
    if "budget" in error.lower():
        return "budget"
    if "Failed to apply agent patch" in error:
        return "agent patch did not apply"
    return "other"


def percentile(ordered, q):
    position = (len(ordered) - 1) * q
    low = int(position)
    if low + 1 >= len(ordered):
        return ordered[-1]
    return ordered[low] + (position - low) * (ordered[low + 1] - ordered[low])


def bootstrap_interval(diffs):
    """95% percentile interval of the mean paired difference, in points."""
    count = len(diffs)
    if count == 0:
        return (float("nan"), float("nan"))
    rng = random.Random(BOOT_SEED)
    means = []
    for _ in range(BOOT_RESAMPLES):
        total = 0
        for _ in range(count):
            total += diffs[int(rng.random() * count)]
        means.append(100.0 * total / count)
    means.sort()
    return (percentile(means, 0.025), percentile(means, 0.975))


def paired(data, tasks, outcome):
    """Counts, difference in points and interval of an outcome, NAF minus N."""
    pairs = [(1 if outcome(data["N"][t]) else 0, 1 if outcome(data["NAF"][t]) else 0) for t in tasks]
    diffs = [b - a for a, b in pairs]
    count = len(pairs)
    point = 100.0 * sum(diffs) / count if count else float("nan")
    low, high = bootstrap_interval(diffs)
    return {"pairs": pairs, "n": count, "hits_n": sum(a for a, _ in pairs), "hits_naf": sum(b for _, b in pairs),
            "point": point, "low": low, "high": high}


def verdict(result, words):
    if result["low"] > 0:
        return words[0]
    if result["high"] < 0 and words[1] is not None:
        return words[1]
    return words[2]


def rate(hits, total):
    if total == 0:
        return "0/0 (n/a)"
    return "%d/%d (%.1f%%)" % (hits, total, 100.0 * hits / total)


def signed(value):
    if abs(value) < 0.005:
        value = 0.0
    return "%+.2f" % value


def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def counted(mapping):
    """'kind count; kind count' by falling count; \\xa0 keeps a kind and its count on one line."""
    items = sorted(mapping.items(), key=lambda kv: (-kv[1], kv[0]))
    return "; ".join(("%s %d" % (kind, count)).replace(" ", "\xa0") for kind, count in items)


def wrap(text, first="", rest=""):
    return textwrap.fill(text, width=WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


# -------------------------------------------------------------------- main

def load_condition(root, condition, run_list, gold_by_task):
    base = os.path.join(root, condition, "seed1")
    lines = read_jsonl(os.path.join(base, "task_results.jsonl"))
    last = {}
    for row in lines:
        last[row.get("instance_id")] = row
    extra = {}
    for row in read_jsonl(os.path.join(base, "extra.jsonl")):
        extra[row.get("task")] = row
    stats = {"lines": len(lines), "distinct": len(last), "off_list": sum(1 for t in last if t not in gold_by_task),
             "no_trace": 0, "multi": 0, "unparsed": 0, "patch_skipped": [], "patch_short": 0, "patch_mismatch": 0,
             "read_calls": 0, "bound_calls": 0, "bound_misspelled": 0, "bound_sessions": 0,
             "bound_misspelled_sessions": 0, "inline_bound": 0, "arg_names": {}, "other_absolute": 0,
             "short_reads": 0, "short_reads_gold": 0, "view_kinds": {kind: 0 for kind in VIEW_KINDS}}
    sessions = {}
    for task in run_list:
        if task not in last:
            continue
        row = last[task]
        gold = gold_by_task[task]
        trace_path = os.path.join(base, "traces", "trace_%s.json" % task)
        calls = []
        if os.path.exists(trace_path):
            calls, multi, unparsed = load_calls(trace_path)
            stats["multi"] += multi
            stats["unparsed"] += unparsed
        else:
            stats["no_trace"] += 1
        views, uncounted = session_views(calls, gold)
        for view in views:
            if view[1] == "b":
                stats["view_kinds"][view[2]] += 1
            if view[3].startswith("/"):
                stats["other_absolute"] += 1
        any_bound = any_misspelled = False
        for name, arguments, result in calls:
            if name != "read_file":
                continue
            stats["read_calls"] += 1
            for key in arguments:
                stats["arg_names"][key] = stats["arg_names"].get(key, 0) + 1
            carried, misspelled = bound_names(arguments)
            stats["bound_calls"] += 1 if carried else 0
            stats["bound_misspelled"] += 1 if misspelled else 0
            any_bound = any_bound or carried
            any_misspelled = any_misspelled or misspelled
            path = arguments.get("filepath")
            if isinstance(path, str) and re.search(r"(start|end)_?line", path, re.IGNORECASE):
                stats["inline_bound"] += 1
            content = result.get("content")
            if (result.get("status") == "ok" and isinstance(content, str) and is_int(result.get("start_line"))
                    and is_int(result.get("end_line"))
                    and content.count("\n") != result["end_line"] - result["start_line"]):
                # the content is the returned lines joined by newlines
                stats["short_reads"] += 1
                if isinstance(result.get("filepath"), str) and norm_path(result["filepath"]) in gold:
                    stats["short_reads_gold"] += 1
        stats["bound_sessions"] += 1 if any_bound else 0
        stats["bound_misspelled_sessions"] += 1 if any_misspelled else 0
        agent_regions = {}
        agent_apart = {}
        has_patch = False
        patch_path = os.path.join(base, "patches", "%s.patch" % task)
        if os.path.exists(patch_path):
            with open(patch_path, "rb") as handle:
                patch_text = handle.read().decode("utf-8", errors="replace")
            if patch_text.strip():
                has_patch = True
                agent_regions, facts = changed_regions(patch_text)
                agent_apart = facts["apart"]
                stats["patch_short"] += facts["short"]
                if facts["skipped"]:
                    stats["patch_skipped"].append("%s %d" % (task, facts["skipped"]))
        size = row.get("agent_patch_size")
        if is_int(size) and (size > 0) != has_patch:
            stats["patch_mismatch"] += 1
        sessions[task] = {
            "resolved": row.get("resolved") is True,
            "error": row.get("error"),
            "infra": infra_kind(row.get("error")),
            "calls": len(calls),
            "harness_calls": row.get("tool_calls") if is_int(row.get("tool_calls")) else 0,
            "views": views,
            "uncounted": uncounted,
            "agent_regions": agent_regions,
            "agent_apart": agent_apart,
            "t": first_shown(views, gold),
            "t_a": first_shown(views, gold, shell=False),
            "t_returned": first_shown(views, gold, reading=RETURNED),
            "t_whole": first_shown(views, gold, reading=WHOLE),
            "overlap": patch_overlaps(agent_regions, gold),
            "in_gold": any(path in gold for path in agent_regions),
            "extra": extra.get(task),
        }
    return sessions, stats


def build_report(root):
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(root, "validate", "tasks_ok.txt"), encoding="utf-8") as handle:
        run_list = [line.strip() for line in handle if line.strip()]
    reference = {}
    for row in read_jsonl(os.path.join(here, os.pardir, "data", "tasks.jsonl")):
        reference[row.get("instance_id")] = row
    gold_by_task = {}
    kept_by_task = {}  # the same without the files the reference patch empties or deletes
    apart_by_task = {}  # the same with the pieces of a region kept apart
    ref = {"files": 0, "created": 0, "emptied": 0, "emptied_tasks": 0, "skipped": 0, "short": 0, "gold": 0, "regions": 0}
    for task in run_list:
        regions, facts = changed_regions(reference[task]["patch"])
        gold_by_task[task] = regions
        kept_by_task[task] = {path: spans for path, spans in regions.items() if path not in facts["emptied"]}
        apart_by_task[task] = facts["apart"]
        ref["files"] += facts["files"]
        ref["created"] += facts["created"]
        ref["emptied"] += len(facts["emptied"])
        ref["emptied_tasks"] += 1 if facts["emptied"] else 0
        ref["skipped"] += facts["skipped"]
        ref["short"] += facts["short"]
        ref["gold"] += len(regions)
        ref["regions"] += sum(len(spans) for spans in regions.values())

    data = {}
    stats = {}
    for condition in CONDITIONS:
        data[condition], stats[condition] = load_condition(root, condition, run_list, gold_by_task)

    both = [t for t in run_list if all(t in data[c] for c in CONDITIONS)]
    enter = [t for t in both if all(data[c][t]["infra"] is None for c in CONDITIONS)]
    with_gold = [t for t in enter if gold_by_task[t]]
    without_gold = sorted(t for t in enter if not gold_by_task[t])
    n_enter = len(enter)
    n_gold = len(with_gold)

    out = []
    add = out.append
    add("RE-DERIVATION OF PRE-REGISTRATION 14 (whole runs scored by tests)")
    add(wrap("Written from the raw outputs alone (result lines, patches, traces, runner records, reference patches),"
             " without sight of the project's analysis or its stored output. Conditions: N = the harness as shipped,"
             " NAF = the harness with the two changes. One seed. A session is (task, condition)."))
    add("")

    # ---- 1
    add("1. TASKS WITH A RESULT, INFRASTRUCTURE FAILURES, TASKS THAT ENTER")
    add("Run list (validate/tasks_ok.txt): %s." % plural(len(run_list), "task"))
    for condition in CONDITIONS:
        st = stats[condition]
        sessions = data[condition]
        add("Condition %s: %s with a result (result lines %d, distinct tasks %d, of them not on the run list %d)."
            % (condition, plural(len(sessions), "task"), st["lines"], st["distinct"], st["off_list"]))
        failures = {}
        for task in run_list:
            if task in sessions and sessions[task]["infra"] is not None:
                failures.setdefault(sessions[task]["infra"], []).append(task)
        add("  infrastructure failures: %d" % sum(len(v) for v in failures.values()))
        for kind in INFRA_PHRASES + (SERVICE_KIND,):
            tasks = sorted(failures.get(kind, []))
            add(wrap("%s: %d%s" % (kind.rstrip(":"), len(tasks), (" (" + ", ".join(tasks) + ")") if tasks else ""),
                     "    ", "      "))
        kinds = {}
        for task in run_list:
            if task in sessions and sessions[task]["infra"] is None:
                kind = error_kind(sessions[task]["error"])
                kinds[kind] = kinds.get(kind, 0) + 1
        add(wrap("error text of the other sessions (outcomes, not exclusions): " + counted(kinds), "  ", "    "))
    add("Tasks with a result in both conditions: %d. Left out for an infrastructure failure in either condition: %d."
        % (len(both), len(both) - n_enter))
    add(wrap("Tasks that enter the paired analysis: %d; of them %d have a GOLD FILE%s."
             % (n_enter, n_gold, (" (without one: " + ", ".join(without_gold) + ")") if without_gold else "")))
    add(wrap("Reference patches of the run list: %d files; %d created by the patch (left out); %d GOLD FILES with"
             " %d CHANGED REGIONS." % (ref["files"], ref["created"], ref["gold"], ref["regions"])))
    add("")

    # ---- 2
    add("2. PER CONDITION, ON THE %d TASKS THAT ENTER" % n_enter)
    add("(T_SHOWN and FINAL PATCH OVERLAPS on the %d of them with a GOLD FILE)" % n_gold)

    def row(label, values):
        add(("%-26s%-24s%s" % (label, values[0], values[1])).rstrip())

    row("", CONDITIONS)
    row("RESOLVED", [rate(sum(data[c][t]["resolved"] for t in enter), n_enter) for c in CONDITIONS])
    for limit in THRESHOLDS:
        row("T_SHOWN at most %d" % limit,
            [rate(sum(data[c][t]["t"] <= limit for t in with_gold), n_gold) for c in CONDITIONS])
    row("T_SHOWN ever", [rate(sum(data[c][t]["t"] < INF for t in with_gold), n_gold) for c in CONDITIONS])
    row("FINAL PATCH OVERLAPS", [rate(sum(data[c][t]["overlap"] for t in with_gold), n_gold) for c in CONDITIONS])
    means = []
    for condition in CONDITIONS:
        total = sum(data[condition][t]["calls"] for t in enter)
        means.append("%.2f (%d/%d)" % (total / n_enter, total, n_enter) if n_enter else "n/a")
    row("mean tool calls (trace)", means)
    add("Dependence on (b), the shell views (a run_command with cat, head, tail or sed -n on one file):")
    for condition in CONDITIONS:
        sessions = data[condition]
        forms = {}
        with_view = 0
        for task in with_gold:
            gold = gold_by_task[task]
            hit = False
            for view in sessions[task]["views"]:
                if view[1] == "b" and overlaps(gold.get(view[3]), view[WRITTEN][0], view[WRITTEN][1]):
                    forms[view[2]] = forms.get(view[2], 0) + 1
                    hit = True
            with_view += 1 if hit else 0
        rests = sorted(t for t in with_gold if sessions[t]["t"] != sessions[t]["t_a"])
        add(wrap("%s: %s with a shell view of a changed line (%s). T_SHOWN rests on (b) in %d of them%s;"
                 " never shown without it: %d; T_SHOWN at most %d only with it: %d."
                 % (condition, plural(with_view, "session"),
                    ", ".join("%s %d" % (k, forms[k]) for k in sorted(forms)) if forms else "no such call",
                    len(rests), (" (" + ", ".join(rests) + ")") if rests else "",
                    sum(sessions[t]["t_a"] == INF for t in rests), RULE_THRESHOLD,
                    sum(sessions[t]["t"] <= RULE_THRESHOLD < sessions[t]["t_a"] for t in rests)), "  ", "    "))
    alone = paired(data, with_gold, lambda s: s["t_a"] <= RULE_THRESHOLD)
    add(wrap("With (a) alone, T_SHOWN at most %d: N %s, NAF %s; difference %s points, interval [%s, %s]."
             % (RULE_THRESHOLD, rate(alone["hits_n"], alone["n"]), rate(alone["hits_naf"], alone["n"]),
                signed(alone["point"]), signed(alone["low"]), signed(alone["high"])), "  ", "    "))
    add("")

    # ---- 3
    add(wrap("3. THE THREE RULES (NAF minus N, paired by task, in percentage points; 95%% bootstrap interval over"
             " tasks: %s resamples of tasks with replacement, percentile, seed %d)"
             % ("{:,}".format(BOOT_RESAMPLES), BOOT_SEED), "", "   "))
    applies = n_enter >= MIN_TASKS
    add("The rules %s: %d tasks enter the paired analysis (at least %d are needed)."
        % ("apply" if applies else "DO NOT apply", n_enter, MIN_TASKS))
    rules = (
        ("T1", "RESOLVED", enter, lambda s: s["resolved"],
         ("More tasks solved", "fewer", "no detectable difference")),
        ("T2", "T_SHOWN at most %d" % RULE_THRESHOLD, with_gold, lambda s: s["t"] <= RULE_THRESHOLD,
         ("Sooner", None, "not detected")),
        ("T3", "FINAL PATCH OVERLAPS", with_gold, lambda s: s["overlap"],
         ("The final patch reaches the fix more often", "less often", "no detectable difference")),
    )
    results = {}
    for name, label, tasks, outcome, words in rules:
        result = paired(data, tasks, outcome)
        results[name] = (tasks, result)
        add(wrap("%s, %s: N %s, NAF %s; difference %s points, interval [%s, %s]; verdict: \"%s\"%s."
                 % (name, label, rate(result["hits_n"], result["n"]), rate(result["hits_naf"], result["n"]),
                    signed(result["point"]), signed(result["low"]), signed(result["high"]), verdict(result, words),
                    "" if applies else " (the rule does not apply)"), "", "    "))
    add("")

    # ---- 4
    add("4. TWO BY TWO TABLES (tasks; rows N, columns NAF)")
    for name, label in (("T1", "RESOLVED"), ("T2", "T_SHOWN at most %d" % RULE_THRESHOLD)):
        tasks, result = results[name]
        cell = {(a, b): 0 for a in (0, 1) for b in (0, 1)}
        for a, b in result["pairs"]:
            cell[(a, b)] += 1
        add("%s (%s)" % (label, plural(len(tasks), "task")))
        add("  %-10s%10s%10s%10s" % ("", "NAF yes", "NAF no", "total"))
        add("  %-10s%10d%10d%10d" % ("N yes", cell[(1, 1)], cell[(1, 0)], cell[(1, 1)] + cell[(1, 0)]))
        add("  %-10s%10d%10d%10d" % ("N no", cell[(0, 1)], cell[(0, 0)], cell[(0, 1)] + cell[(0, 0)]))
        add("  %-10s%10d%10d%10d" % ("total", cell[(1, 1)] + cell[(0, 1)], cell[(1, 0)] + cell[(0, 0)], len(tasks)))
        only_n = sorted(t for t, (a, b) in zip(tasks, result["pairs"]) if a == 1 and b == 0)
        only_naf = sorted(t for t, (a, b) in zip(tasks, result["pairs"]) if a == 0 and b == 1)
        add(wrap("yes in N only (%d): %s" % (len(only_n), ", ".join(only_n) if only_n else "none"), "  ", "    "))
        add(wrap("yes in NAF only (%d): %s" % (len(only_naf), ", ".join(only_naf) if only_naf else "none"), "  ", "    "))
    add("")

    # ---- 5
    add("5. RUNNER RECORDS (extra.jsonl) AND LINE BOUNDS ON READS (traces), ALL SESSIONS WITH A RESULT")
    for condition in CONDITIONS:
        sessions = data[condition]
        st = stats[condition]
        tasks = [t for t in run_list if t in sessions]
        records = [sessions[t]["extra"] for t in tasks if isinstance(sessions[t]["extra"], dict)]
        add("Condition %s: %s, %d with a runner record" % (condition, plural(len(tasks), "session"), len(records)))
        endings = {}
        applied = {}
        for record in records:
            kind = str(record.get("agent_ending"))
            endings[kind] = endings.get(kind, 0) + 1
            changes = record.get("changes_applied")
            key = " + ".join(str(c) for c in changes) if isinstance(changes, list) and changes else "none"
            applied[key] = applied.get(key, 0) + 1
        add("  how sessions ended: " + counted(endings))
        add("  changes the runner applied: " + counted(applied))
        did = {}
        for field, label in (("addressed_answers", "a graph answer was given a file and a line range"),
                             ("restored_calls", "a misspelled line bound was restored")):
            did[field] = [record.get(field) if is_int(record.get(field)) else 0 for record in records]
            add("  %s in %s sessions (%d times in all)"
                % (label, rate(sum(v > 0 for v in did[field]), len(records)), sum(did[field])))
        add("  either of the two in %s sessions"
            % rate(sum(a > 0 or b > 0 for a, b in zip(did["addressed_answers"], did["restored_calls"])), len(records)))
        add("  read_file calls in the traces: %d; carrying a line bound under any spelling: %d (in %s)"
            % (st["read_calls"], st["bound_calls"], plural(st["bound_sessions"], "session")))
        add("    of those, with a bound under a name that is not exactly start_line or end_line: %d (in %s)"
            % (st["bound_misspelled"], plural(st["bound_misspelled_sessions"], "session")))
        names = sorted(st["arg_names"].items(), key=lambda kv: (-kv[1], kv[0]))
        add(wrap("argument names on read_file calls: " + ", ".join("%s x%d" % (json.dumps(k), v) for k, v in names),
                 "    ", "      "))
        add("    not counted above: %d read_file calls with a bound written inside the filepath value" % st["inline_bound"])
    add("")

    # ---- 6
    add("6. JUDGMENT CALLS")
    both_conditions = [(c, t) for c in CONDITIONS for t in with_gold]
    returned = {c: sum(data[c][t]["t"] != data[c][t]["t_returned"] for t in with_gold) for c in CONDITIONS}
    returned_rule = sum((data[c][t]["t"] <= RULE_THRESHOLD) != (data[c][t]["t_returned"] <= RULE_THRESHOLD)
                        for c, t in both_conditions)
    returned_ever = sum((data[c][t]["t"] < INF) != (data[c][t]["t_returned"] < INF) for c, t in both_conditions)
    whole = sum(data[c][t]["t_returned"] != data[c][t]["t_whole"] for c, t in both_conditions)
    uncounted = {c: [(t, i, cmd) for t in with_gold for i, cmd in data[c][t]["uncounted"]] for c in CONDITIONS}
    # second readings of the regions: pieces kept apart; emptied or deleted files left out
    apart_t = sum(first_shown(data[c][t]["views"], apart_by_task[t]) != data[c][t]["t"] for c, t in both_conditions)
    apart_o = sum(patch_overlaps(data[c][t]["agent_apart"], apart_by_task[t]) != data[c][t]["overlap"]
                  for c, t in both_conditions)
    kept = [(c, t) for c, t in both_conditions if kept_by_task[t]]
    kept_t = {(c, t): first_shown(data[c][t]["views"], kept_by_task[t]) for c, t in kept}
    kept_changed = sum(kept_t[(c, t)] != data[c][t]["t"] for c, t in kept)
    kept_rule = sum((kept_t[(c, t)] <= RULE_THRESHOLD) != (data[c][t]["t"] <= RULE_THRESHOLD) for c, t in kept)
    kept_o = sum(patch_overlaps(data[c][t]["agent_regions"], kept_by_task[t]) != data[c][t]["overlap"] for c, t in kept)
    notes = [
        "Patches. A hunk body is delimited by the line counts of its header: the reference patches have no"
        " 'diff --git' lines, so a '--- a/' file header after a hunk is told from a removed line by the counts."
        " A file counts as created when its old side is /dev/null, it carries 'new file mode', or its old range"
        " is 0,0 (the reference patches mark created files only this last way: %d files)." % ref["created"],
        "CHANGED REGION. One span per hunk, from the smallest to the largest marked old line. Marked: every"
        " removed line; for a block of added lines whose preceding hunk line is not a removed line, the old line"
        " before and the old line after the insertion, when they exist (at the top of a file only the line"
        " after, at its end only the line before). 'No newline' markers are ignored. Read instead as separate"
        " pieces (the span of removed lines, and each pair around an insertion on its own), T_SHOWN would change"
        " in %d sessions and FINAL PATCH OVERLAPS in %d." % (apart_t, apart_o),
        "Files the reference patch empties or deletes (new range 0,0) are files it modifies: the region is the"
        " whole file. This concerns %d GOLD FILES in %s. Leaving those files out, %d of the %d tasks would lose"
        " their last GOLD FILE; in the others T_SHOWN would change in %d sessions ('at most %d' in %d) and FINAL"
        " PATCH OVERLAPS in %d."
        % (ref["emptied"], plural(ref["emptied_tasks"], "task"), sum(1 for t in with_gold if not kept_by_task[t]),
           n_gold, kept_changed, RULE_THRESHOLD, kept_rule, kept_o),
        "Paths. The three prefixes are removed repeatedly; 'a/' and 'b/' are removed from patch headers; paths"
        " are then compared as exact strings. Other absolute paths (the sandbox under /tmp) are not mapped to"
        " the workspace: N %d, NAF %d reads or views use one."
        % (stats["N"]["other_absolute"], stats["NAF"]["other_absolute"]),
        "(a). The file and the lines are those of the result (filepath, start_line, end_line: what was"
        " returned, at most 150 lines), not those asked for. Line numbers are taken as they are, also after"
        " the agent has edited the file. Reads whose content holds fewer lines than start_line to end_line say:"
        " N %d, NAF %d, of them on a GOLD FILE %d and %d."
        % (stats["N"]["short_reads"], stats["NAF"]["short_reads"], stats["N"]["short_reads_gold"],
           stats["NAF"]["short_reads_gold"]),
        "(b), which commands. Only a command that is one simple command in a listed form (no pipe, redirection,"
        " second command or other option); output is stdout (for a failed command the stdout kept in its"
        " details); non-empty means at least one character. A tail is placed only when an earlier read gave the"
        " length of the file. Views recognized, on any file: %s. Viewer commands with output on a GOLD FILE that"
        " are not counted: %s."
        % ("; ".join("%s %s" % (c, ", ".join("%s %d" % (k, stats[c]["view_kinds"][k]) for k in VIEW_KINDS))
                     for c in CONDITIONS),
           "; ".join("%s %d%s" % (c, len(uncounted[c]),
                                  (" (" + "; ".join("%s call %d: %s" % (t, i, " ".join(str(cmd).split())[:80])
                                                    for t, i, cmd in uncounted[c][:6]) + ")") if uncounted[c] else "")
                     for c in CONDITIONS)),
        "(b), which lines. cat: the lines present in the output (the harness cuts every output at 5,000"
        " characters), the last one even if cut short. sed and head: the lines the command names (A to B, 1 to"
        " K), as the definition says, although the same cut applies. Reading sed and head as the lines present"
        " in the output would change T_SHOWN in %d sessions (N %d, NAF %d), 'at most %d' in %d and 'ever' in %d;"
        " dropping a last line cut short would change %d more."
        % (returned["N"] + returned["NAF"], returned["N"], returned["NAF"], RULE_THRESHOLD, returned_rule,
           returned_ever, whole),
        "FINAL PATCH OVERLAPS. The agent's patch is parsed by the same code. A file it creates has no region. A"
        " region of the agent's patch must lie in a GOLD FILE (same path) and intersect a reference region of"
        " that file; touching the neighbouring line is not enough. Sessions whose patch has a region in a GOLD"
        " FILE at all: N %s, NAF %s. Lines inside a hunk that are not diff lines are skipped: %s."
        % (rate(sum(data["N"][t]["in_gold"] for t in with_gold), n_gold),
           rate(sum(data["NAF"][t]["in_gold"] for t in with_gold), n_gold),
           "; ".join("%s %s" % (c, ", ".join(stats[c]["patch_skipped"]) if stats[c]["patch_skipped"] else "none")
                     for c in CONDITIONS)),
        "INFRASTRUCTURE FAILURE. The five phrases are searched as written. 'Sandbox execution error' counts only"
        " with a word for a connection, server, timeout, rate-limit or authentication failure (connection,"
        " server, unavailable, gateway, timeout, timed out, rate limit, too many requests, authentication,"
        " unauthorized, API key, permission denied) and never when the text names the context window or a budget.",
        "Universe. The tasks of the run list. The last line per task counts in task_results.jsonl and likewise"
        " in extra.jsonl. T2 and T3 are computed, and their tasks resampled, on the tasks with a GOLD FILE; T1"
        " on all tasks that enter.",
        "Bootstrap. random.Random(%d), started afresh for each rule (the same stream of draws), indexing the"
        " tasks in run-list order; the interval is the 2.5th to 97.5th percentile of the %s resampled mean"
        " differences, with linear interpolation between order statistics. A verdict needs a bound strictly"
        " above or below 0."
        % (BOOT_SEED, "{:,}".format(BOOT_RESAMPLES)),
        "Tool calls. Every tool call in the trace counts, also calls that were refused (budget exhausted, a"
        " mandatory argument missing) and submit_patch and get_status. This is not the tool_calls field of the"
        " result line, whose mean on the same tasks is N %s, NAF %s."
        % tuple("%.2f" % (sum(data[c][t]["harness_calls"] for t in enter) / n_enter) if n_enter else "n/a"
                for c in CONDITIONS),
        "Line bounds on reads. An argument name carries a bound when, with everything but letters removed, it"
        " is startline or endline; 'not exactly' means the name is not the string start_line or end_line. A"
        " bound written inside the filepath value is not an argument and is counted apart.",
    ]
    for number, note in enumerate(notes, 1):
        add(wrap(note, "%2d. " % number, "    "))
    add("")

    # ---- checks and per-task values
    add("CHECKS ON THE INPUTS")
    add(wrap("reference patches: hunks whose body does not hold the line counts of its header %d; lines inside"
             " hunks that are not diff lines %d" % (ref["short"], ref["skipped"]), "  ", "    "))
    for condition in CONDITIONS:
        st = stats[condition]
        add(wrap("%s: sessions without a trace file %d; steps with more than one tool call %d; tool results that"
                 " are not a JSON object %d; patch file present though the result line gives size 0, or the"
                 " reverse %d; agent-patch hunks whose body does not hold the counts of its header %d"
                 % (condition, st["no_trace"], st["multi"], st["unparsed"], st["patch_mismatch"], st["patch_short"]),
                 "  ", "    "))
    add("")
    add("PER TASK (r RESOLVED, t T_SHOWN, o FINAL PATCH OVERLAPS, c tool calls in the trace; '-' no GOLD FILE)")
    for task in sorted(both):
        parts = []
        for condition in CONDITIONS:
            session = data[condition][task]
            if gold_by_task[task]:
                shown = "never" if session["t"] == INF else "%d" % session["t"]
                over = "%d" % (1 if session["overlap"] else 0)
            else:
                shown = over = "-"
            parts.append("%-3s r=%d t=%-5s o=%s c=%-2d"
                         % (condition, 1 if session["resolved"] else 0, shown, over, session["calls"]))
        flag = "" if task in enter else "   [left out: infrastructure failure]"
        add(("  %-14s %s%s" % (task, " | ".join(parts), flag)).rstrip())
    return ("\n".join(out) + "\n").replace("\xa0", " ")


def main(argv):
    arguments = [a for a in argv[1:] if a != "--no-write"]
    write = "--no-write" not in argv[1:]
    if len(arguments) != 1:
        sys.stderr.write("usage: rederive_14.py <root> [--no-write]\n")
        return 2
    report = build_report(arguments[0])
    if write:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "results", "rederive_14.txt"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
