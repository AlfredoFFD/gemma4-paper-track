#!/usr/bin/env python3
"""EXPLORATORY, written after the results of pre-registration 23 were seen: does the one-call effect of the replays
(experiment B: the agent's NEXT call reads or edits lines of a listed neighbor in a file it has not opened) show at
the pushed lists of the whole runs? Measured at every pushed list of PE and PH (real lists) and of the N run of 14 with
the push replayed offline (would-be lists, seen by no agent; analysis/explore_push_baseline_23.replay).

Usage: py -I -X utf8 analysis/explore_next_call_23.py   (no arguments; prints the report)
Stored output: analysis/results/explore_next_call_23.txt is exactly this script's stdout (LF line ends).

Scorer: the registered touch of the replays, fork_states.touches with exact character caps from the file's line
lengths (nodes.file_text), graph-tool mentions not counted: the function `hit` of analysis/rederive_s5.py, re-stated
here because rederive_s5 runs its whole analysis at import. "Opens the file": `opens_file` of rederive_s5, re-stated
for the same reason. A file the agent has OPENED before the list: a file some earlier call showed content of, by
fork_states.shows_content (the rule that built `shown_files` of the replay states), up to and including the READ
that carried the list.
"""
import collections
import json
import os
import re
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "modal_h"))
import rederive_14 as r14  # noqa: E402
import rederive_18 as r18  # noqa: E402
import rederive_23 as R  # noqa: E402
import explore_push_baseline_23 as B  # noqa: E402
from fork_states import touches, shows_content  # noqa: E402  registered scorer of the replays
import nodes as N  # noqa: E402

CTL = R.CONTROL
LABS = ("PE", "PH", CTL)
VIEW = {'cat', 'head', 'tail', 'sed', 'grep', 'rg', 'less', 'more', 'awk', 'nl', 'egrep', 'fgrep'}
_ll = {}


def lengths(task, path):
    if (task, path) not in _ll:
        src = N.file_text(task, path)
        _ll[(task, path)] = [len(x) for x in src.splitlines()] if src else None
    return _ll[(task, path)]


def as_call(name, args):
    return {"function_name": name, "arguments": args if isinstance(args, dict) else {}}


def hit(call, span, nid, task):
    """rederive_s5.hit: a read or edit of the node's lines by the call (graph mentions do not count)."""
    if not span:
        return False
    v = touches(call, span, nid, line_lengths=lengths(task, span['path']))
    return bool(v) and v != 'graph'


def shell_stages(cmd):
    st = []
    for part in re.split(r'\|\|?|&&|;', cmd):
        part = part.strip()
        if not part:
            continue
        try:
            toks = shlex.split(part)
        except ValueError:
            toks = part.split()
        st.append(toks)
    return st


def opens_file(call, path):
    """rederive_s5.opens_file: the call opens or views this file at any lines."""
    fn, a = call['function_name'], call['arguments']
    if fn in ('read_file', 'edit_file', 'write_file'):
        return B.P.norm(a.get('filepath')) == path
    if fn == 'run_command':
        for toks in shell_stages(str(a.get('command', ''))):
            if toks and toks[0] in VIEW and any(B.P.norm(t) == path for t in toks[1:]):
                return True
    return False


def opened_before(calls, upto):
    """Files shown by calls 1..upto (fork_states.shows_content on a one-call step)."""
    out = set()
    for name, args, result in calls[:upto]:
        step = {"tool_calls": [as_call(name, args)], "observation": {"content": json.dumps(result)}}
        try:
            sc = shows_content(step)
        except Exception:  # noqa: BLE001  a malformed call shows nothing
            sc = None
        if sc and sc[0]:
            out.add(N._norm(sc[0]))
    return out


def span_of(entry):
    rng = entry["range"]
    return {"path": entry["file"], "start": rng[0], "end": rng[1]} if rng else None


def score_list(task, calls, push):
    """Per list: fresh entries, and for the next call and for any of the next 3 calls, the strict and loose outcome."""
    p = push["idx"]
    opened = opened_before(calls, p)
    fresh = [e for e in push["entries"] if e["file"] and e["file"] not in opened and e["range"]]
    res = {"fresh": len(fresh)}
    for k, window in (("next", 1), ("w3", 3)):
        nxt = [as_call(n, a) for n, a, _r in calls[p:p + window]]
        res[k] = any(hit(c, span_of(e), e["name"], task) for c in nxt for e in fresh)
        res[k + "_open"] = any(opens_file(c, f) for c in nxt for f in {e["file"] for e in fresh})
    return res


def call_steps(trace_path):
    """Per tool call (in load_calls_paired's order), the index of the trace step that issued it: a step with tool
    calls issues all of them, in the order of its tool_calls list; the 'system' steps that follow it carry results and
    issue none (the walk of rederive_18.load_calls_paired)."""
    with open(trace_path, encoding="utf-8") as handle:
        steps = json.load(handle).get("steps") or []
    out = []
    i = 0
    while i < len(steps):
        tcs = steps[i].get("tool_calls") or []
        if not tcs:
            i += 1
            continue
        out.extend([i] * len(tcs))
        j = i + 1
        while (j < len(steps) and not steps[j].get("tool_calls") and steps[j].get("source") == "system"
               and "observation" in steps[j]):
            j += 1
        i = j
    return out


def next_step_call(step_of, p):
    """1-based index of the first call of the first model step after the step of call p, or None (the run ended)."""
    for q in range(p + 1, len(step_of) + 1):
        if step_of[q - 1] != step_of[p - 1]:
            return q
    return None


SEARCH = re.compile(r"(^|[\s|;&(`])(grep|egrep|fgrep|rg|ag|ack|git\s+grep)(\s|$)")


def kind_of(call, push):
    if call is None:
        return "none (the run ended)"
    name, args, _r = call
    if name == "read_file":
        f = r14.norm_path(str(args.get("filepath") or ""))
        if f == push["file"]:
            return "read_file, same file as the READ that carried the list"
        if f in {e["file"] for e in push["entries"]}:
            return "read_file, another file holding a listed entry"
        return "read_file, another file holding none"
    if name == "run_command":
        return "shell search (grep, egrep, fgrep, rg, ag, ack, git grep)" if SEARCH.search(
            str(args.get("command") or "")) else "other shell command"
    if name in ("edit_file", "write_file"):
        return "edit or write"
    if name in R.GRAPH_TOOLS:
        return "graph tool"
    if name == "submit_patch":
        return "submit"
    return "other"


KINDS = ("read_file, same file as the READ that carried the list", "read_file, another file holding a listed entry",
         "read_file, another file holding none", "shell search (grep, egrep, fgrep, rg, ag, ack, git grep)",
         "other shell command", "edit or write", "graph tool", "submit", "none (the run ended)", "other")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except (AttributeError, ValueError):
        pass
    with open(R.TASK_LIST, encoding="utf-8") as h:
        run_list = [line.strip() for line in h if line.strip()]
    meta = {row["instance_id"]: row for row in r14.read_jsonl(os.path.join(ROOT, "data", "tasks.jsonl"))}
    gold = {t: r14.changed_regions(meta[t]["patch"])[0] for t in run_list}
    checks = []
    data = {lab: R.load_dir(R.DEFAULTS[lab], lab, run_list, gold, checks) for lab in LABS}
    entered = {lab: [t for t in run_list if t in data[lab] and data[lab][t]["infra"] is None] for lab in LABS}
    calls_of = {}
    for lab in LABS:
        for t in data[lab]:
            path = os.path.join(R.DEFAULTS[lab], "traces", "trace_%s.json" % t)
            if lab == CTL:
                pushes, _a1, calls = B.replay(t, meta, path)
                data[lab][t]["pushes"] = pushes
                data[lab][t]["uptake"] = B.uptake_of(data[lab][t]["reads"], pushes)
            else:
                calls = r18.load_calls_paired(path)[0] if os.path.exists(path) else []
            calls_of[(lab, t)] = calls

    scored = {lab: {} for lab in LABS}
    step_bad = []
    for lab in LABS:
        for t in entered[lab]:
            calls = calls_of[(lab, t)]
            step_of = call_steps(os.path.join(R.DEFAULTS[lab], "traces", "trace_%s.json" % t))
            if len(step_of) != len(calls):
                step_bad.append("%s %s" % (lab, t))
            rows = []
            for push in data[lab][t]["pushes"]:
                s = score_list(t, calls, push)
                p = push["idx"]
                s["same_step"] = p < len(calls) and step_of[p] == step_of[p - 1]
                q = next_step_call(step_of, p)
                s["q"] = q
                if q is None:
                    s["next_step"] = False
                else:
                    opened = opened_before(calls, p)
                    fresh = [e for e in push["entries"] if e["file"] and e["file"] not in opened and e["range"]]
                    c = as_call(calls[q - 1][0], calls[q - 1][1])
                    s["next_step"] = any(hit(c, span_of(e), e["name"], t) for e in fresh)
                s["kind"] = kind_of(calls[q - 1] if q else None, push)
                rows.append(s)
            scored[lab][t] = rows

    out = []
    add = out.append
    add("EXPLORATORY: THE ONE-CALL OUTCOME OF THE REPLAYS, MEASURED AT THE PUSHED LISTS OF THE WHOLE RUNS OF 23")
    add(B.wrap("EXPLORATORY. Written after the results of 23 were seen; nothing here was registered. The control is the"
               " stored N run of pre-registration 14: another launch and another seed (seed 1; PE and PH ran seed 2)."
               " Its lists are replayed offline (analysis/modal_h/push_23.py on the reads that run made) and were seen"
               " by no agent; a real push changes what a run does next, so the would-be lists are not those of PE or"
               " PH. Reference, one-call replays (paused early steps of September runs): reads a neighbor's code 2.15%"
               " no list, 2.75% names, 8.25% addresses; opens the neighbor's file 4.6%, 7.5%, 11.8%."))
    add("")

    add("0. GATE")
    for lab, want_l, want_i in (("PE", 493, 11), ("PH", 465, 6), (CTL, 485, 2)):
        lists = sum(len(data[lab][t]["pushes"]) for t in entered[lab])
        ins = sum(u["inside"] for t in entered[lab] for u in data[lab][t]["uptake"] if u["other_file"])
        add(B.wrap("%s: lists %d (%s); READs starting inside the range of an entry in another file within 3 calls %d"
                   " (%s)" % (lab, lists, "reproduced" if lists == want_l else "NOT reproduced, expected %d" % want_l,
                              ins, "reproduced" if ins == want_i else "NOT reproduced, expected %d" % want_i),
                   "  ", "    "))
    add("")

    subsets = (("all lists", lambda i, s: True),
               ("lists with an entry in a file not opened before", lambda i, s: s["fresh"] > 0),
               ("first list of each run", lambda i, s: i == 0),
               ("lists 2 and later", lambda i, s: i > 0))
    for title, a, b in (("1. READS A NEIGHBOR'S CODE (the replays' outcome: read or edit of a listed entry's lines, the"
                         " entry in a file not opened before the list)", "next", "w3"),
                        ("2. OPENS THE FILE (looser: the call opens or views a not-yet-opened file that holds a listed"
                         " entry)", "next_open", "w3_open")):
        add(B.wrap(title))
        for name, sel in subsets:
            parts = []
            for lab in LABS:
                rows = [s for t in entered[lab] for i, s in enumerate(scored[lab][t]) if sel(i, s)]
                parts.append("%s next call %s, within 3 calls %s" % (
                    lab, B.pct(sum(r[a] for r in rows), len(rows)), B.pct(sum(r[b] for r in rows), len(rows))))
            add(B.wrap("%s: %s." % (name, "; ".join(parts)), "  ", "    "))
        add("")

    add(B.wrap("3. PAIRED BY TASK (per run: the share of its lists with an entry in an unopened file whose NEXT call"
               " meets the outcome; tasks where both runs have such a list; 95% bootstrap by task, 2,000 resamples,"
               " random.Random(0) afresh for each comparison; points of share)"))
    for title, k in (("reads a neighbor's code, next call", "next"), ("reads a neighbor's code, within 3 calls", "w3"),
                     ("opens the file, next call", "next_open"), ("opens the file, within 3 calls", "w3_open")):
        add("  " + title)
        for a, b in (("PE", "PH"), ("PE", CTL), ("PH", CTL)):
            def frac(lab, t):
                rows = [s for s in scored[lab][t] if s["fresh"] > 0]
                return (sum(s[k] for s in rows), len(rows))
            tasks = [t for t in run_list if t in scored[a] and t in scored[b] and frac(a, t)[1] and frac(b, t)[1]]
            fa = [frac(a, t) for t in tasks]
            fb = [frac(b, t) for t in tasks]
            ma = [x / n for x, n in fa]
            mb = [x / n for x, n in fb]
            d = [x - y for x, y in zip(ma, mb)]
            lo, hi = R.boot(d, 100.0)
            na, nb = ("N14" if x == CTL else x for x in (a, b))
            add(B.wrap("%s minus %s: %d tasks; mean %s %.2f%%, %s %.2f%%; difference %s points [%s, %s]; pooled %s %s,"
                       " %s %s." % (na, nb, len(tasks), na, 100 * R.mean(ma), nb, 100 * R.mean(mb),
                                    R.signed(100 * R.mean(d)), R.signed(lo), R.signed(hi), na,
                                    B.pct(sum(x for x, _ in fa), sum(n for _, n in fa)), nb,
                                    B.pct(sum(x for x, _ in fb), sum(n for _, n in fb))), "    ", "      "))
    add("")

    add(B.wrap("4. SAME-STEP CALLS. The call at index p+1 may belong to the same model step as the READ that carried"
               " the list, so it was written before the agent saw the list. Steps are told apart as"
               " rederive_18.load_calls_paired walks the trace: a trace step with tool_calls issues all of them; the"
               " 'system' steps after it carry their results and issue none; each call gets the index of the step that"
               " issued it. REDEFINED NEXT CALL: the first tool call of the first model step after the step whose"
               " result carried the list."))
    if step_bad:
        add(B.wrap("Runs whose step walk gives another number of calls than load_calls_paired: " + ", ".join(step_bad),
                   "  ", "    "))
    for lab in LABS:
        rows = [s for t in entered[lab] for s in scored[lab][t]]
        add(B.wrap("%s: lists %d; lists whose p+1 call is in the same model step as the READ %s; lists with no later"
                   " model step (the run ended) %d" % (lab, len(rows), B.pct(sum(s["same_step"] for s in rows),
                                                                             len(rows)),
                                                       sum(1 for s in rows if s["q"] is None)), "  ", "    "))
    add("  Reads a neighbor's code, REDEFINED NEXT CALL (section 1's 'next call' beside it):")
    for name, sel in subsets:
        parts = []
        for lab in LABS:
            rows = [s for t in entered[lab] for i, s in enumerate(scored[lab][t]) if sel(i, s)]
            parts.append("%s %s (was %s)" % (lab, B.pct(sum(r["next_step"] for r in rows), len(rows)),
                                             B.pct(sum(r["next"] for r in rows), len(rows))))
        add(B.wrap("%s: %s." % (name, "; ".join(parts)), "    ", "      "))
    add("  Paired by task, reads a neighbor's code, REDEFINED NEXT CALL (as section 3):")
    for a, b in (("PE", "PH"), ("PE", CTL), ("PH", CTL)):
        def frac2(lab, t):
            rows = [s for s in scored[lab][t] if s["fresh"] > 0]
            return (sum(s["next_step"] for s in rows), len(rows))
        tasks = [t for t in run_list if t in scored[a] and t in scored[b] and frac2(a, t)[1] and frac2(b, t)[1]]
        fa = [frac2(a, t) for t in tasks]
        fb = [frac2(b, t) for t in tasks]
        ma = [x / n for x, n in fa]
        mb = [x / n for x, n in fb]
        d = [x - y for x, y in zip(ma, mb)]
        lo, hi = R.boot(d, 100.0)
        na, nb = ("N14" if x == CTL else x for x in (a, b))
        add(B.wrap("%s minus %s: %d tasks; mean %s %.2f%%, %s %.2f%%; difference %s points [%s, %s]; pooled %s %s,"
                   " %s %s." % (na, nb, len(tasks), na, 100 * R.mean(ma), nb, 100 * R.mean(mb),
                                R.signed(100 * R.mean(d)), R.signed(lo), R.signed(hi), na,
                                B.pct(sum(x for x, _ in fa), sum(n for _, n in fa)), nb,
                                B.pct(sum(x for x, _ in fb), sum(n for _, n in fb))), "    ", "      "))
    add("")

    add(B.wrap("5. WHAT THE REDEFINED NEXT CALL IS (counts and shares of all lists; a READ's file and the files of"
               " listed entries without a leading /workspace/, workspace/ or ./; 'holding a listed entry' counts every"
               " entry of the list, opened file or not; a shell search is a run_command whose command contains grep,"
               " egrep, fgrep, rg, ag, ack or git grep as a word)"))
    tallies = {lab: collections.Counter(s["kind"] for t in entered[lab] for s in scored[lab][t]) for lab in LABS}
    totals = {lab: sum(tallies[lab].values()) for lab in LABS}
    add(("  %-58s" % "") + "".join("%-20s" % ("N14" if lab == CTL else lab) for lab in LABS).rstrip())
    for k in KINDS:
        add(("  %-58s" % k + "".join("%-20s" % ("%d (%.1f%%)" % (tallies[lab][k], 100.0 * tallies[lab][k]
                                                                 / totals[lab] if totals[lab] else 0))
                                     for lab in LABS)).rstrip())
    add(("  %-58s" % "lists" + "".join("%-20s" % totals[lab] for lab in LABS)).rstrip())
    add("")

    nolen = sum(1 for v in _ll.values() if v is None)
    add("JUDGMENT CALLS AND WHERE THE WHOLE-RUN DATA FORCED ANOTHER READING")
    for i, text in enumerate([
        "Scorer: fork_states.touches with exact character caps (nodes.file_text line lengths), graph mentions not"
        " counted (rederive_s5.hit), and rederive_s5.opens_file for the looser outcome; both re-stated here because"
        " rederive_s5 runs its analysis at import. Files whose text could not be read for the caps: %d (line caps"
        " only for those)." % nolen,
        "Listed entries: the replay listed one queried node's neighbors from get_code_neighbors; a pushed list has up to"
        " two sources and up to 8 entries, already without nodes shown before (push_23). Every entry of the list is a"
        " candidate, not only true neighbors of one node; no swapped or decoy entry exists here.",
        "A file not opened before: a file shown by an earlier call by fork_states.shows_content (read_file of status ok"
        " with content; cat, sed, head, tail, grep, rg, awk, less or more with stdout), counting every call up to and"
        " including the READ that carried the list. The replays built this set from the steps before a fork in runs"
        " with no edit yet; whole runs also edit and write, and edit_file or write_file of a file do not count as"
        " opening it here (shows_content does not count them).",
        "An entry's span: the file and line range of the pushed list as the runner record stores it (for PH the agent"
        " did not see them; for N14 the would-be range from the address table), not nodes.span as in the replays.",
        "Next call: the tool call at call index p+1, p the index of the READ that carried the list (calls paired with"
        " their results by rederive_18.load_calls_paired). The replays sampled one call from a paused state; here the"
        " next call is whatever the run did, and a step with several calls counts each as its own call. Within 3"
        " calls: indexes p+1 to p+3. A list at the end of a run has fewer next calls.",
        "The replays excluded interface failures (malformed calls) from the denominator; here every list counts, and"
        " a malformed next call never meets the outcome (touches returns nothing for it).",
        "Lists: entered runs (rederive_23), all their pushed lists. The replays were early steps before any edit;"
        " pushed lists come at any point of a run, up to 10 per run.",
        "Paired shares: per run over its lists with at least one entry in an unopened file; a task without such a"
        " list in either run drops out. Pooled counts are on the same tasks.",
    ], 1):
        add(B.wrap(text, "%2d. " % i, "    "))
    sys.stdout.write(("\n".join(out) + "\n").replace("\xa0", " "))


if __name__ == "__main__":
    main()
