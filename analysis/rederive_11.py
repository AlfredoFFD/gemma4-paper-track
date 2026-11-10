#!/usr/bin/env python3
"""Independent re-derivation of pre-registration 11 (the reading rule on the fresh episodes).

Written blind: from the text of prereg/11-reading-rule-fresh-episodes.md and a written statement of
the class definitions, without reading the project's analysis scripts, their stored outputs, the
logs or the paper. It imports nothing from the repository, uses only the standard library, reads
one file (results_09.jsonl of the run directory) and writes nothing.

One limit on the blindness: three counts of the registered analysis (the ADDRESS, PATH ONLY and
GRAPH NAME counts for all arms) had been seen in a commit subject line before this script was
written. Every reading below was fixed from the written definitions before the first run, and none
was changed after it; the readings that were open are listed in part 6 with their effect.

Usage:  py -I -X utf8 analysis/rederive_11.py <run_dir>

The report has six parts: (1) episodes and reads per arm, (2) first reads by class, (3) rule R1,
(4) rule R2, (5) first reads after a graph answer that carries lines, (6) the judgment calls, with
a table of how the counts move under the other readings of each open point.

Definitions, as implemented here
  read          an executed read_file call whose arguments are a dictionary; its file is filepath
                without any leading /workspace/ , workspace/ or ./ ; its asked start and end are
                the integer arguments named start_line and end_line once quotes, backslashes and
                whitespace are removed from the argument name
  first read    no earlier read_file of that file in the episode, and no earlier run_command that
                uses a viewer (cat head tail sed nl less more awk) and names the file
  just before   the executed call immediately before the read, and its result; the text of a
                result is every string value inside it, joined by newlines
  classes       GRAPH ADDRESS (arms NA and NAF, checked first), ADDRESS, GRAPH NAME, PATH ONLY,
                OTHER: see classify()
  past line 1   the asked start is greater than 1
"""
import json
import os
import random
import re
import sys
import textwrap

ROWS_NAME = "results_09.jsonl"
ARMS = ("N", "NA", "NAF")
GRAPH_TOOLS = ("get_code_neighbors", "get_code_subgraph", "search_similar_code")
GRAPH_LISTS = ("neighbors", "nodes", "results")
GRAPH_ECHO = ("query", "node")
VIEWERS = ("cat", "head", "tail", "sed", "nl", "less", "more", "awk")
GREPS = ("grep", "egrep", "fgrep", "rg")
PREFIXES = ("/workspace/", "workspace/", "./")
CLASSES = ("GRAPH ADDRESS", "ADDRESS", "GRAPH NAME", "PATH ONLY", "OTHER")

BOOT_RESAMPLES = 2000
BOOT_SEED = 20261110
OTHER_SEEDS = range(1, 21)   # only to show how far the bound of check (c) moves with the seed
WINDOW = 150                 # a read with no end asked covers start .. start + 149

R1_FLOOR = 30                # first reads needed in each of the two classes
R1_ADDRESS_MIN = 65          # (a) at least this percentage after an ADDRESS
R1_PATH_MAX = 5              # (b) at most this percentage after a PATH ONLY
R1_DIFF_LOW = 50.0           # (c) lower bound of the difference above this many points
R2_FLOOR = 20
R2_MAX = 10
R1_WORDS = "The reading rule holds in our fresh episodes"
R2_WORDS = "A graph answer is read from the top"
TOO_FEW = "too few reads to test"

# The reading used for the report. The other values are only used for the table of part 6.
DEFAULTS = {
    # any: any directory prefix ending in a slash may precede the path;
    # known: only ./ , /workspace/ and workspace/
    "dir_prefix": "any",
    # name: a whole path is not followed by a letter, digit, _ or /, nor by . or - plus one of them;
    # word: not followed by a letter, digit or _ ; strict: not followed by any of [A-Za-z0-9_./-]
    "trail": "name",
    # word: a viewer name as a whole word anywhere in the command;
    # command: only as the first word of a pipeline segment; off: no viewer rule
    "viewer": "word",
    # count: a read_file that failed is a read; skip: it is not
    "failed_reads": "count",
    # clean: quotes, backslashes, whitespace removed from argument names; raw: names as written
    "names": "clean",
    # numbered lines may start with blanks (as nl and cat -n print them)
    "lead_blank": True,
    # the query or node echoed in a graph answer is part of its text
    "echo": True,
    # True: a path that swallowed its bounds (path`,start_line:N) is split back
    "repair": False,
    # True: a path given in two pieces (its directory in the command or as an ls -R header, its
    # base name in the output) counts as PATH ONLY
    "two_pieces": False,
}


# ----------------------------------------------------------------------------------------------
# reads
# ----------------------------------------------------------------------------------------------

def norm_path(path):
    """Remove any leading /workspace/ , workspace/ or ./ (repeatedly)."""
    again = True
    while again:
        again = False
        for prefix in PREFIXES:
            if path.startswith(prefix):
                path = path[len(prefix):]
                again = True
    return path


def clean_name(name):
    return re.sub(r"[\"'\\\s]", "", name)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def asked_bounds(arguments, opts):
    """Asked start and end of a read_file call; None when absent or not an integer."""
    start = None
    end = None
    for name, value in arguments.items():
        if not isinstance(name, str) or not is_int(value):
            continue
        key = clean_name(name) if opts["names"] == "clean" else name
        if key == "start_line" and start is None:
            start = value
        elif key == "end_line" and end is None:
            end = value
    return start, end


SWALLOWED_RE = re.compile(
    r"^(.*?)`\s*,\s*((?:start_line|end_line)\s*:\s*\d+(?:\s*,\s*(?:start_line|end_line)\s*:\s*\d+)*)\s*$")


def split_swallowed(filepath):
    """For the 'repair' reading only: path`,start_line:N[,end_line:M] -> (path, {bound: value})."""
    m = SWALLOWED_RE.match(filepath)
    if not m:
        return filepath, {}
    bounds = {}
    for part in m.group(2).split(","):
        name, value = part.split(":")
        bounds.setdefault(name.strip(), int(value))
    return m.group(1), bounds


def result_text(result, opts, graph=False):
    """Every string value inside a result, depth first, joined by newlines."""
    if graph and not opts["echo"] and isinstance(result, dict):
        result = dict((k, v) for k, v in result.items() if k not in GRAPH_ECHO)
    parts = []

    def walk(node):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(result)
    return "\n".join(parts)


# ----------------------------------------------------------------------------------------------
# shell commands
# ----------------------------------------------------------------------------------------------

def split_command(command):
    """Split a shell command into pipeline segments at unquoted | ; & ( ) ` and newlines.

    Each segment is a list of (word, quoted); quoted is True when any part of the word was inside
    quotes. Quotes are removed, a backslash keeps the next character.
    """
    segments = []
    words = []
    chars = []
    state = {"open": False, "quoted": False}
    quote = None
    i = 0
    n = len(command)

    def end_word():
        if state["open"]:
            words.append(("".join(chars), state["quoted"]))
        del chars[:]
        state["open"] = False
        state["quoted"] = False

    def end_segment():
        end_word()
        if words:
            segments.append(list(words))
        del words[:]

    while i < n:
        ch = command[i]
        if quote is not None:
            if ch == quote:
                quote = None
            elif ch == "\\" and quote == '"' and i + 1 < n:
                chars.append(command[i + 1])
                i += 1
            else:
                chars.append(ch)
        elif ch == "'" or ch == '"':
            quote = ch
            state["open"] = True
            state["quoted"] = True
        elif ch == "\\" and i + 1 < n:
            chars.append(command[i + 1])
            state["open"] = True
            i += 1
        elif ch in " \t\r":
            end_word()
        elif ch in "|;&\n()`":
            end_segment()
        else:
            chars.append(ch)
            state["open"] = True
        i += 1
    end_segment()
    return segments


def base_name(word):
    return word.rsplit("/", 1)[-1]


VIEWER_WORD_RE = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(VIEWERS) + r")(?![A-Za-z0-9_])")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./~+@%\-]+")
SHORT_N_RE = re.compile(r"^-[A-Za-z0-9]*n[A-Za-z0-9]*$")


def uses_viewer(command, opts):
    if opts["viewer"] == "off":
        return False
    if opts["viewer"] == "word":
        return VIEWER_WORD_RE.search(command) is not None
    for segment in split_command(command):
        word, quoted = segment[0]
        if not quoted and base_name(word) in VIEWERS:
            return True
    return False


def command_names(command):
    """The path-like tokens of a command, normalized."""
    return set(norm_path(token) for token in PATH_TOKEN_RE.findall(command))


def numbering_program(command):
    """'grep -n', 'cat -n' or 'nl' when some pipeline segment runs one of them, else None."""
    for segment in split_command(command):
        for index, (word, quoted) in enumerate(segment):
            if quoted:
                continue
            name = base_name(word)
            later = [w for (w, q) in segment[index + 1:] if not q]
            if name in GREPS:
                if any(w == "--line-number" or SHORT_N_RE.match(w) for w in later):
                    return "grep -n"
            elif name == "cat":
                if any(w == "--number" or SHORT_N_RE.match(w) for w in later):
                    return "cat -n"
            elif name == "nl":
                return "nl"
    return None


# ----------------------------------------------------------------------------------------------
# classes
# ----------------------------------------------------------------------------------------------

LEAD_ANY = r"(?<![A-Za-z0-9_.\-])"
LEAD_KNOWN = r"(?<![A-Za-z0-9_.\-/])(?:/workspace/|workspace/|\./)*"
TRAILS = {
    "name": r"(?![A-Za-z0-9_/])(?![.\-][A-Za-z0-9_])",
    "word": r"(?![A-Za-z0-9_])",
    "strict": r"(?![A-Za-z0-9_./\-])",
}
NUMBERED_BLANK_RE = re.compile(r"(?m)^[ \t]*(\d+)[:\-\t]")
NUMBERED_RE = re.compile(r"(?m)^(\d+)[:\-\t]")

_patterns = {}


def patterns(file, opts):
    """Compiled patterns for one file under one reading."""
    key = (file, opts["dir_prefix"], opts["trail"])
    found = _patterns.get(key)
    if found is not None:
        return found
    lead = LEAD_ANY if opts["dir_prefix"] == "any" else LEAD_KNOWN
    trail = TRAILS[opts["trail"]]
    esc = re.escape(file)
    module = file[:-3] if file.endswith(".py") else file
    module = module.replace("/", ".")
    found = {
        # the file's path as a whole path
        "whole": re.compile(lead + esc + trail),
        # way (i): path:N: or path-N-
        "grep": re.compile(lead + esc + r"(?::(\d+):|-(\d+)-)"),
        # way (ii): path", line N
        "trace": re.compile(lead + esc + r'",?\s*line\s+(\d+)'),
        # the dotted module followed by a dot
        "module": re.compile(r"(?<![A-Za-z0-9_])" + re.escape(module) + r"\.") if module else None,
    }
    _patterns[key] = found
    return found


def call_command(call):
    arguments = call.get("arguments")
    if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
        return arguments["command"]
    return None


def address_ways(file, before, text, opts):
    """Way -> named line numbers, for the ways (i), (ii), (iii) in which the text is an ADDRESS."""
    pats = patterns(file, opts)
    ways = {}
    numbers = [int(m.group(1) if m.group(1) is not None else m.group(2)) for m in pats["grep"].finditer(text)]
    if numbers:
        ways["i"] = numbers
    numbers = [int(m.group(1)) for m in pats["trace"].finditer(text)]
    if numbers:
        ways["ii"] = numbers
    if before.get("function_name") == "run_command":
        command = call_command(before)
        if command is not None and pats["whole"].search(command) and numbering_program(command):
            numbered = NUMBERED_BLANK_RE if opts["lead_blank"] else NUMBERED_RE
            numbers = [int(m.group(1)) for m in numbered.finditer(text)]
            if numbers:
                ways["iii"] = numbers
    return ways


def listed_lines(file, before):
    """The 'lines' of the entries of a graph answer that list the file; [] when there is none."""
    result = before.get("result")
    if before.get("function_name") not in GRAPH_TOOLS or not isinstance(result, dict):
        return []
    found = []
    for key in GRAPH_LISTS:
        entries = result.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_file = entry.get("file")
            lines = entry.get("lines")
            if not isinstance(entry_file, str) or norm_path(entry_file) != file:
                continue
            if isinstance(lines, str):
                lines = lines.strip()
            if lines:
                found.append(lines)
    return found


def in_two_pieces(file, before, text, opts):
    """True when a shell command or an ls -R header names the file's directory and the output
    holds the file's base name on its own. Not a class of the pre-registration: only counted."""
    command = call_command(before)
    if before.get("function_name") != "run_command" or command is None or "/" not in file:
        return False
    directory, base = file.rsplit("/", 1)
    if not directory or not base:
        return False
    bare = re.compile(r"(?<![A-Za-z0-9_.\-/])" + re.escape(base) + TRAILS[opts["trail"]])
    if not bare.search(text):
        return False
    in_command = re.search(LEAD_ANY + re.escape(directory) + r"/?(?![A-Za-z0-9_.\-/])", command)
    as_header = re.search(r"(?m)^(?:\./)?" + re.escape(directory) + r"/?:$", text)
    return bool(in_command or as_header)


def classify(arm, file, before, opts):
    """(class, details) of a first read, from the call just before it and that call's result."""
    if before is None:
        return "OTHER", {"first_call": True}
    graph = before.get("function_name") in GRAPH_TOOLS
    # GRAPH ADDRESS: a graph answer lists the file with lines (arms NA and NAF only; checked first)
    if arm in ("NA", "NAF"):
        lines = listed_lines(file, before)
        if lines:
            return "GRAPH ADDRESS", {"lines": lines}
    text = result_text(before.get("result"), opts, graph)
    # ADDRESS: the text names the file together with a line number
    ways = address_ways(file, before, text, opts)
    if ways:
        return "ADDRESS", {"ways": ways}
    pats = patterns(file, opts)
    # GRAPH NAME: a graph answer holds the file's dotted module followed by a dot
    if graph and pats["module"] is not None and pats["module"].search(text):
        return "GRAPH NAME", {}
    # PATH ONLY: the path appears as a whole path in the text or in the command just before
    if pats["whole"].search(text):
        return "PATH ONLY", {"where": "text"}
    command = call_command(before)
    if command is not None and pats["whole"].search(command):
        return "PATH ONLY", {"where": "command"}
    pieces = in_two_pieces(file, before, text, opts)
    if pieces and opts["two_pieces"]:
        return "PATH ONLY", {"where": "two pieces"}
    return "OTHER", {"two_pieces": pieces, "after": before.get("function_name")}


# ----------------------------------------------------------------------------------------------
# episodes
# ----------------------------------------------------------------------------------------------

def load_rows(run_dir):
    path = os.path.join(run_dir, ROWS_NAME) if os.path.isdir(run_dir) else run_dir
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def executed_calls(row):
    calls = []
    for step in row.get("steps") or []:
        for call in step.get("calls") or []:
            if isinstance(call, dict) and call.get("executed"):
                calls.append(call)
    return calls


def new_counts():
    return {"episodes": 0, "errors": 0, "reads": 0, "first": 0, "reads_left_out": 0}


def collect(rows, opts):
    """Per-arm counts and the first reads of the episodes that have no error."""
    arms = dict((arm, new_counts()) for arm in ARMS)
    first_reads = []
    for row in rows:
        arm = row.get("arm")
        counts = arms.setdefault(arm, new_counts())
        counts["episodes"] += 1
        calls = executed_calls(row)
        if row.get("error"):
            counts["errors"] += 1
            counts["reads_left_out"] += sum(
                1 for c in calls if c.get("function_name") == "read_file" and isinstance(c.get("arguments"), dict))
            continue
        files_read = set()
        commands = []
        for index, call in enumerate(calls):
            name = call.get("function_name")
            arguments = call.get("arguments")
            if name == "run_command":
                command = call_command(call)
                if command is not None:
                    commands.append(command)
                continue
            if name != "read_file" or not isinstance(arguments, dict):
                continue
            filepath = arguments.get("filepath")
            if not isinstance(filepath, str):
                continue
            result = call.get("result")
            ok = isinstance(result, dict) and result.get("status") == "ok"
            if opts["failed_reads"] == "skip" and not ok:
                continue
            start, end = asked_bounds(arguments, opts)
            swallowed = "`" in filepath
            if opts["repair"] and swallowed:
                filepath, bounds = split_swallowed(filepath)
                if start is None:
                    start = bounds.get("start_line")
                if end is None:
                    end = bounds.get("end_line")
            file = norm_path(filepath)
            counts["reads"] += 1
            first = file not in files_read
            if first:
                for command in commands:
                    if uses_viewer(command, opts) and file in command_names(command):
                        first = False
                        break
            files_read.add(file)
            if not first:
                continue
            counts["first"] += 1
            before = calls[index - 1] if index > 0 else None
            cls, details = classify(arm, file, before, opts)
            first_reads.append({
                "task": row.get("task"), "arm": arm, "seed": row.get("seed"), "index": index,
                "file": file, "start": start, "end": end, "past1": start is not None and start > 1,
                "class": cls, "details": details, "ok": ok, "swallowed": swallowed,
                "mangled": any(isinstance(k, str) and clean_name(k) != k for k in arguments),
            })
    return arms, first_reads


# ----------------------------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------------------------

def percentile(sorted_values, q):
    """Percentile by linear interpolation between order statistics (q in 0..1)."""
    n = len(sorted_values)
    if n == 0:
        return None
    position = q * (n - 1)
    low = int(position)
    high = min(low + 1, n - 1)
    weight = position - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def interval(values):
    values = sorted(values)
    return percentile(values, 0.025), percentile(values, 0.975)


def bootstrap(tasks, per_task, seed):
    """Percentile intervals over tasks for the two shares (in percent) and their difference.

    per_task maps a task to [ADDRESS reads, of them past line 1, PATH ONLY reads, of them past line 1].
    Each resample draws len(tasks) tasks with replacement; a resample in which a class has no read
    gives no value for that class (and none for the difference).
    """
    rng = random.Random(seed)
    table = [per_task.get(task, (0, 0, 0, 0)) for task in tasks]
    size = len(table)
    shares_a = []
    shares_p = []
    diffs = []
    for _ in range(BOOT_RESAMPLES):
        na = ka = np_ = kp = 0
        for _ in range(size):
            row = table[rng.randrange(size)]
            na += row[0]
            ka += row[1]
            np_ += row[2]
            kp += row[3]
        a = 100.0 * ka / na if na else None
        p = 100.0 * kp / np_ if np_ else None
        if a is not None:
            shares_a.append(a)
        if p is not None:
            shares_p.append(p)
        if a is not None and p is not None:
            diffs.append(a - p)
    return {
        "a": interval(shares_a), "p": interval(shares_p), "d": interval(diffs),
        "empty": (BOOT_RESAMPLES - len(shares_a), BOOT_RESAMPLES - len(shares_p)),
    }


def r1(first_reads, tasks, seed=BOOT_SEED):
    """Counts, intervals and the three checks of R1 for one set of first reads."""
    per_task = {}
    na = ka = np_ = kp = 0
    for read in first_reads:
        if read["class"] not in ("ADDRESS", "PATH ONLY"):
            continue
        row = per_task.setdefault(read["task"], [0, 0, 0, 0])
        past = 1 if read["past1"] else 0
        if read["class"] == "ADDRESS":
            row[0] += 1
            row[1] += past
            na += 1
            ka += past
        else:
            row[2] += 1
            row[3] += past
            np_ += 1
            kp += past
    out = {"na": na, "ka": ka, "np": np_, "kp": kp,
           "tasks_a": sum(1 for row in per_task.values() if row[0]),
           "tasks_p": sum(1 for row in per_task.values() if row[2]),
           "tested": na >= R1_FLOOR and np_ >= R1_FLOOR, "boot": None}
    if na and np_:
        out["boot"] = bootstrap(tasks, per_task, seed)
    if out["tested"]:
        out["a"] = ka * 100 >= R1_ADDRESS_MIN * na
        out["b"] = kp * 100 <= R1_PATH_MAX * np_
        out["c"] = out["boot"]["d"][0] > R1_DIFF_LOW
        out["holds"] = out["a"] and out["b"] and out["c"]
    return out


def parse_ranges(lines):
    """A listed 'lines' value as a list of (first, last)."""
    ranges = []
    if isinstance(lines, str):
        pairs = re.findall(r"(\d+)\s*-\s*(\d+)", lines)
        if pairs:
            ranges = [(int(a), int(b)) for a, b in pairs]
        else:
            ranges = [(int(a), int(a)) for a in re.findall(r"\d+", lines)]
    elif isinstance(lines, (list, tuple)):
        if len(lines) == 2 and all(is_int(v) for v in lines):
            ranges = [(lines[0], lines[1])]
        else:
            for item in lines:
                ranges.extend(parse_ranges(item))
    elif is_int(lines):
        ranges = [(lines, lines)]
    return ranges


def window(read):
    """Lines a read asks for: start to the smaller of end and start + 149."""
    start = read["start"]
    last = start + WINDOW - 1
    if read["end"] is not None:
        last = min(read["end"], last)
    return start, last


# ----------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------

def share(k, n):
    if n == 0:
        return "%d of %d" % (k, n)
    return "%d of %d = %.1f%%" % (k, n, 100.0 * k / n)


def span(pair, unit="%"):
    if pair is None or pair[0] is None:
        return "[no interval]"
    return "[%.1f%s, %.1f%s]" % (pair[0], unit, pair[1], unit)


def yes(flag):
    return "true" if flag else "false"


def class_counts(first_reads):
    table = {}
    for read in first_reads:
        for scope in ("all", read["arm"]):
            cell = table.setdefault((scope, read["class"]), [0, 0])
            cell[0] += 1
            cell[1] += 1 if read["past1"] else 0
    return table


def print_r1(title, reads, tasks):
    res = r1(reads, tasks)
    boot = res["boot"]
    print("  " + title)
    print("    after an ADDRESS:   %s of the first reads ask past line 1   95%% interval %s   (reads from %d tasks)"
          % (share(res["ka"], res["na"]), span(boot["a"]) if boot else "[no interval]", res["tasks_a"]))
    print("    after a PATH ONLY:  %s of the first reads ask past line 1   95%% interval %s   (reads from %d tasks)"
          % (share(res["kp"], res["np"]), span(boot["p"]) if boot else "[no interval]", res["tasks_p"]))
    if boot:
        diff = 100.0 * res["ka"] / res["na"] - 100.0 * res["kp"] / res["np"]
        print("    difference:         %.1f points   95%% interval %s" % (diff, span(boot["d"], "")))
        if boot["empty"] != (0, 0):
            print("    resamples left out because a class had no read: ADDRESS %d, PATH ONLY %d" % boot["empty"])
    print("    floor (at least %d first reads in each class): %s (%d and %d)"
          % (R1_FLOOR, "met" if res["tested"] else "not met", res["na"], res["np"]))
    if not res["tested"]:
        print("    result: %s" % TOO_FEW)
        return TOO_FEW
    print("    (a) at least %d%% after an ADDRESS:                  %s (%s)"
          % (R1_ADDRESS_MIN, yes(res["a"]), share(res["ka"], res["na"])))
    print("    (b) at most %d%% after a PATH ONLY:                   %s (%s)"
          % (R1_PATH_MAX, yes(res["b"]), share(res["kp"], res["np"])))
    print("    (c) lower bound of the difference above %d points:  %s (%.1f)"
          % (int(R1_DIFF_LOW), yes(res["c"]), boot["d"][0]))
    lows = [r1(reads, tasks, seed)["boot"]["d"][0] for seed in OTHER_SEEDS]
    print("        with %d other seeds (%d to %d) that lower bound runs from %.1f to %.1f"
          % (len(lows), min(OTHER_SEEDS), max(OTHER_SEEDS), min(lows), max(lows)))
    if res["holds"]:
        print('    verdict: all three are true: "%s"' % R1_WORDS)
        return "holds"
    print('    verdict: not all three are true: "%s" is NOT established'
          " (the pre-registration gives no words for this outcome)" % R1_WORDS)
    return "does not hold"


def variant_line(label, arms, first_reads):
    table = class_counts(first_reads)
    cells = []
    for scope, cls in (("all", "ADDRESS"), ("all", "PATH ONLY"), ("N", "ADDRESS"), ("N", "PATH ONLY"),
                       ("N", "GRAPH NAME"), ("all", "GRAPH ADDRESS"), ("all", "OTHER")):
        n, k = table.get((scope, cls), (0, 0))
        cells.append("%d/%d" % (k, n))
    first = sum(arms[arm]["first"] for arm in arms)
    print("    %-58s %6d  %8s %9s %8s %9s %8s %8s %8s" % ((label, first) + tuple(cells)))


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    run_dir = argv[1]
    rows = load_rows(run_dir)
    opts = dict(DEFAULTS)
    arms, first_reads = collect(rows, opts)
    table = class_counts(first_reads)

    tasks_all = sorted(set(row.get("task") for row in rows if not row.get("error")))
    tasks_n = sorted(set(row.get("task") for row in rows if not row.get("error") and row.get("arm") == "N"))
    episodes = [(row.get("task"), row.get("arm"), row.get("seed")) for row in rows]
    seeds = sorted(set(str(row.get("seed")) for row in rows))

    print("Re-derivation of pre-registration 11: the reading rule, tested on the fresh episodes")
    print("rows: %s" % (os.path.join(run_dir, ROWS_NAME) if os.path.isdir(run_dir) else run_dir).replace("\\", "/"))
    print("episodes %d, distinct (task, arm, seed) %d, tasks %d, arms %s, seeds %s"
          % (len(rows), len(set(episodes)), len(set(row.get("task") for row in rows)),
             ", ".join(sorted(set(str(row.get("arm")) for row in rows))), ", ".join(seeds)))
    print("intervals: 95%% bootstrap over tasks, %d resamples of the tasks with replacement, percentile, seed %d"
          % (BOOT_RESAMPLES, BOOT_SEED))
    print()

    # 1 ----------------------------------------------------------------------------------------
    print("1. Episodes and reads, per arm")
    print("    %-5s %9s %19s %6s %15s %12s"
          % ("arm", "episodes", "left out (error)", "kept", "executed reads", "first reads"))
    total = new_counts()
    for arm in sorted(arms, key=lambda a: (ARMS.index(a) if a in ARMS else len(ARMS), str(a))):
        c = arms[arm]
        for key in total:
            total[key] += c[key]
        print("    %-5s %9d %19d %6d %15d %12d"
              % (arm, c["episodes"], c["errors"], c["episodes"] - c["errors"], c["reads"], c["first"]))
    print("    %-5s %9d %19d %6d %15d %12d"
          % ("all", total["episodes"], total["errors"], total["episodes"] - total["errors"],
             total["reads"], total["first"]))
    print("    executed reads and first reads are those of the kept episodes;"
          " the episodes left out hold %d more executed reads" % total["reads_left_out"])
    print()

    # 2 ----------------------------------------------------------------------------------------
    print("2. First reads by class: reads, and how many ask past line 1")
    for scope in ("all",) + ARMS:
        print("    %s" % ("all arms together" if scope == "all" else "arm " + scope))
        scope_reads = 0
        scope_past = 0
        for cls in CLASSES:
            n, k = table.get((scope, cls), (0, 0))
            scope_reads += n
            scope_past += k
            print("        %-14s %5d reads   %s ask past line 1" % (cls, n, share(k, n)))
        print("        %-14s %5d reads   %s ask past line 1"
              % ("every class", scope_reads, share(scope_past, scope_reads)))
    print()

    # 3 ----------------------------------------------------------------------------------------
    print("3. R1, shell output: first reads after an ADDRESS against first reads after a PATH ONLY")
    verdict_all = print_r1("all three arms together (%d tasks resampled)" % len(tasks_all), first_reads, tasks_all)
    verdict_n = print_r1("arm N alone (%d tasks resampled)" % len(tasks_n),
                         [read for read in first_reads if read["arm"] == "N"], tasks_n)
    if verdict_all == verdict_n:
        print("  the two agree: %s" % ('"%s"' % R1_WORDS if verdict_all == "holds" else verdict_all))
    else:
        print("  the two disagree (all arms: %s; arm N alone: %s); both are stated and the claim is the weaker one"
              % (verdict_all, verdict_n))
    print()

    # 4 ----------------------------------------------------------------------------------------
    print("4. R2, the graph tools as shipped: arm N, first reads after a GRAPH NAME")
    n, k = table.get(("N", "GRAPH NAME"), (0, 0))
    print("    %s of the first reads ask past line 1" % share(k, n))
    print("    floor (at least %d such reads): %s (%d)" % (R2_FLOOR, "met" if n >= R2_FLOOR else "not met", n))
    if n >= R2_FLOOR:
        met = k * 100 <= R2_MAX * n
        print("    at most %d%% ask past line 1: %s" % (R2_MAX, yes(met)))
        if met:
            print('    verdict: "%s"' % R2_WORDS)
        else:
            print('    verdict: "%s" is NOT established (the pre-registration gives no words for this outcome)'
                  % R2_WORDS)
    else:
        print("    result: %s" % TOO_FEW)
    print()

    # 5 ----------------------------------------------------------------------------------------
    print("5. Arms NA and NAF: first reads after a GRAPH ADDRESS (no rule)")
    print("    %-9s %6s %17s %45s" % ("arm", "reads", "ask past line 1", "of those, window overlaps a listed range"))
    outside = []
    unparsed = 0
    sums = [0, 0, 0]
    for arm in ("NA", "NAF"):
        reads = [read for read in first_reads if read["arm"] == arm and read["class"] == "GRAPH ADDRESS"]
        past = [read for read in reads if read["past1"]]
        overlap = 0
        for read in past:
            ranges = []
            for lines in read["details"]["lines"]:
                parsed = parse_ranges(lines)
                if not parsed:
                    unparsed += 1
                ranges.extend(parsed)
            first, last = window(read)
            if any(first <= b and a <= last for a, b in ranges):
                overlap += 1
            else:
                outside.append((read, first, last, ranges))
        sums[0] += len(reads)
        sums[1] += len(past)
        sums[2] += overlap
        print("    %-9s %6d %17s %45s" % (arm, len(reads), share(len(past), len(reads)), share(overlap, len(past))))
    print("    %-9s %6d %17s %45s" % ("NA + NAF", sums[0], share(sums[1], sums[0]), share(sums[2], sums[1])))
    print("    window: start to the smaller of end and start + %d (start + %d when no end was asked)"
          % (WINDOW - 1, WINDOW - 1))
    if unparsed:
        print("    listed 'lines' values that could not be parsed: %d" % unparsed)
    for read, first, last, ranges in outside:
        print("    no overlap: %s arm %s seed %s, %s, asked %d-%d, listed %s"
              % (read["task"], read["arm"], read["seed"], read["file"], first, last,
                 ", ".join("%d-%d" % r for r in sorted(ranges))))
    print()

    # extras -----------------------------------------------------------------------------------
    print("Also named by the pre-registration as reported without a rule (my own counting)")
    address = [read for read in first_reads if read["class"] == "ADDRESS"]
    for way, words in (("i", "(i) path:N: or path-N-"), ("ii", "(ii) traceback"),
                       ("iii", "(iii) numbered lines of a named file")):
        hits = [read for read in address if way in read["details"]["ways"]]
        print("    ADDRESS by way %-38s %4d reads, %s ask past line 1"
              % (words + ":", len(hits), share(sum(1 for read in hits if read["past1"]), len(hits))))
    print("    ADDRESS reads named in more than one way: %d"
          % sum(1 for read in address if len(read["details"]["ways"]) > 1))
    ranged = [read for read in address if read["past1"]]
    covered = 0
    for read in ranged:
        first, last = window(read)
        named = set()
        for numbers in read["details"]["ways"].values():
            named.update(numbers)
        if any(first <= number <= last for number in named):
            covered += 1
    print("    ADDRESS reads that ask past line 1 and whose window holds a named line: %s"
          % share(covered, len(ranged)))
    opening = [read for read in first_reads if read["details"].get("first_call")]
    print("    first reads at the first call of an episode (class OTHER): %d, %s ask past line 1"
          % (len(opening), share(sum(1 for read in opening if read["past1"]), len(opening))))
    other = [read for read in first_reads if read["class"] == "OTHER" and not read["details"].get("first_call")]
    for after in sorted(set(read["details"].get("after") for read in other), key=str):
        hits = [read for read in other if read["details"].get("after") == after]
        print("    OTHER first reads after %-20s %4d, %s ask past line 1"
              % (str(after) + ":", len(hits), share(sum(1 for read in hits if read["past1"]), len(hits))))
    print()

    # 6 ----------------------------------------------------------------------------------------
    swallowed = [read for read in first_reads if read["swallowed"]]
    failed = [read for read in first_reads if not read["ok"]]
    mangled = [read for read in first_reads if read["mangled"]]
    pieces = [read for read in first_reads if read["details"].get("two_pieces")]
    print("6. Judgment calls (where the written definitions left room)")
    calls = [
        "Path: the three prefixes are removed repeatedly; nothing else is cleaned. A read_file call without a"
        " string filepath would not be counted (there is none). A filepath that swallowed its bounds"
        " (path`,start_line:N) is kept as written, so it is a file of its own with no asked start:"
        " %d first reads, of class %s." % (len(swallowed), "/".join(sorted(set(r["class"] for r in swallowed))) or "-"),
        "A read_file that failed is still a read, and still an earlier read of its file: %d first reads have a"
        " result that is not ok (%d of them the swallowed paths above)."
        % (len(failed), sum(1 for r in failed if r["swallowed"])),
        "Argument names: double quotes, single quotes, backslashes and whitespace are removed; a boolean is not"
        " an integer; if two names clean to the same bound the first integer wins (there is no such call)."
        " %d first reads carry a mangled name." % len(mangled),
        "Viewer: a viewer name counts as a whole word (no letter, digit or underscore on either side) anywhere"
        " in the command, a quoted pattern included. A path-like token is a maximal run of letters, digits and"
        " _ . / ~ + @ % - .",
        "Whole path (PATH ONLY, and the command of way iii): not preceded by a letter, digit, _ . or - (a slash"
        " before it is a directory prefix, any directory, and is allowed); not followed by a letter, digit, _ or"
        " /, nor by a . or - that is itself followed by one of them. Ways (i) and (ii) use the same rule on the"
        " left. A path given in two pieces (ls of its directory, base name in the output) is not a whole path:"
        " %d such first reads are OTHER, %d of them ask past line 1."
        % (len(pieces), sum(1 for r in pieces if r["past1"])),
        "Way (ii): path, double quote, optional comma, optional blanks, the word line, blanks, a number.",
        "Way (iii): the command is split into segments at unquoted | ; & ( ) ` and newlines. A segment runs a"
        " numbering program if an unquoted word (its base name) is grep, egrep, fgrep or rg followed in that"
        " segment by an unquoted --line-number or a one-dash group of letters and digits containing n (git grep"
        " is covered by its word grep); or is cat followed by such a group or --number; or is nl. Numbered lines"
        " may begin with blanks.",
        "GRAPH ADDRESS: only the lists neighbors, nodes and results at the top level of the result; lines is"
        " non-empty after stripping blanks.",
        "GRAPH NAME: the text of a graph answer includes the query or node it echoes (they are string values of"
        " the result); a path that does not end in .py keeps its extension in the dotted name.",
        "PATH ONLY in the command: the argument named command of the call just before, whatever the tool.",
        "Bootstrap: the tasks resampled are those with at least one kept episode in the scope; a task with no"
        " read in a class adds zero; both shares and the difference use the same resample; a resample in which a"
        " class has no read is left out; percentiles by linear interpolation; checks (a) and (b) are applied to"
        " the point shares, (c) to the lower end of the interval of the difference.",
        "Part 5: a listed range a-b is read as two integers; overlap is inclusive at both ends.",
        "Wording: the pre-registration gives words only for a rule that is met; the wording of a rule that is"
        " not met is mine.",
    ]
    for number, text in enumerate(calls, 1):
        print(textwrap.fill(text, width=112, initial_indent="    %2d. " % number, subsequent_indent="        "))
    print()
    print("  How the counts move under the other readings (k/n = ask past line 1 / first reads; not registered results)")
    print("    %-58s %6s  %8s %9s %8s %9s %8s %8s %8s"
          % ("reading", "first", "ADDRESS", "PATH ONLY", "N: ADDR", "N: PATH", "N: GNAME", "G. ADDR", "OTHER"))
    variant_line("as reported above", arms, first_reads)
    variants = [
        ("directory prefix: only ./ /workspace/ workspace/", {"dir_prefix": "known"}),
        ("whole path: only letter, digit, _ may not follow", {"trail": "word"}),
        ("whole path: none of letter, digit, _ . / - may follow", {"trail": "strict"}),
        ("path in two pieces counted as PATH ONLY", {"two_pieces": True}),
        ("viewer: only as first word of a pipeline segment", {"viewer": "command"}),
        ("no viewer rule (first read = no earlier read_file)", {"viewer": "off"}),
        ("a failed read_file is not a read", {"failed_reads": "skip"}),
        ("argument names as written (mangled names not recognized)", {"names": "raw"}),
        ("numbered lines must start at the first column", {"lead_blank": False}),
        ("echoed query/node left out of a graph answer's text", {"echo": False}),
        ("swallowed bounds split back into path and bounds", {"repair": True}),
    ]
    for label, change in variants:
        other_opts = dict(DEFAULTS)
        other_opts.update(change)
        other_arms, other_reads = collect(rows, other_opts)
        variant_line(label, other_arms, other_reads)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
