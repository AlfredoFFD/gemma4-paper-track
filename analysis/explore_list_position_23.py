#!/usr/bin/env python3
"""EXPLORATORY, written after the results of pre-registration 23 were seen: is the pushed list (a key at the END of a
read_file result, after the file content) passed by because it sits after a long listing? Lists are split by how much
content stands before the key, and by their number of source nodes.

Usage: py -I -X utf8 analysis/explore_list_position_23.py   (no arguments; prints the report)
Stored output: analysis/results/explore_list_position_23.txt is exactly this script's stdout (LF line ends).

Reuses by import the scorer and the step walk of analysis/explore_next_call_23.py (hit, opens_file, opened_before,
span_of, as_call, score_list, call_steps, next_step_call) and the offline replay of analysis/explore_push_baseline_23.py
(the N run of 14 as if pushed). Standard library only.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "modal_h"))
import rederive_14 as r14  # noqa: E402
import rederive_18 as r18  # noqa: E402
import rederive_23 as R  # noqa: E402
import explore_push_baseline_23 as B  # noqa: E402
import explore_next_call_23 as X  # noqa: E402

CTL = R.CONTROL
LABS = ("PE", "PH", CTL)
NAME = {"PE": "PE", "PH": "PH", CTL: "N14"}


def replay_with_sources(task, meta, path):
    """B.replay, recording the number of source nodes of every would-be list (in the order of the lists)."""
    sources = []
    original = B.P.Pusher.on_read

    def on_read(self, *args):
        value = original(self, *args)
        if value:
            sources.append(len(value))
        return value
    B.P.Pusher.on_read = on_read
    try:
        pushes, _a1, calls = B.replay(task, meta, path)
    finally:
        B.P.Pusher.on_read = original
    return pushes, calls, sources


def quart(values):
    v = sorted(values)
    if not v:
        return "none"
    return "min %g, q1 %g, median %g, q3 %g, max %g (n=%d)" % (
        v[0], r18.percentile(v, 0.25), r18.percentile(v, 0.5), r18.percentile(v, 0.75), v[-1], len(v))


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

    lists = {lab: {} for lab in LABS}  # task -> [row per list]
    for lab in LABS:
        for t in entered[lab]:
            path = os.path.join(R.DEFAULTS[lab], "traces", "trace_%s.json" % t)
            if lab == CTL:
                pushes, calls, sources = replay_with_sources(t, meta, path)
            else:
                pushes = data[lab][t]["pushes"]
                calls = r18.load_calls_paired(path)[0]
                sources = [len(calls[p["idx"] - 1][2].get(R.KEY) or []) for p in pushes]
            step_of = X.call_steps(path)
            rows = []
            for k, push in enumerate(pushes):
                p = push["idx"]
                result = calls[p - 1][2]
                s0, e0 = result.get("start_line"), result.get("end_line")
                n_lines = e0 - s0 + 1 if r14.is_int(s0) and r14.is_int(e0) and e0 >= s0 else 0
                n_chars = len(result.get("content") or "")
                s = X.score_list(t, calls, push)
                opened = X.opened_before(calls, p)
                fresh = [e for e in push["entries"] if e["file"] and e["file"] not in opened and e["range"]]
                q = X.next_step_call(step_of, p)
                if q is None:
                    reads = opens = False
                else:
                    c = X.as_call(calls[q - 1][0], calls[q - 1][1])
                    reads = any(X.hit(c, X.span_of(e), e["name"], t) for e in fresh)
                    opens = any(X.opens_file(c, f) for f in {e["file"] for e in fresh})
                rows.append({"lines": n_lines, "chars": n_chars, "fresh": len(fresh), "reads": reads,
                             "opens": opens, "w3": s["w3"], "sources": sources[k] if k < len(sources) else None})
            lists[lab][t] = rows

    out = []
    add = out.append
    add("EXPLORATORY: IS THE PUSHED LIST PASSED BY BECAUSE IT SITS AFTER A LONG LISTING? (pre-registration 23)")
    add(B.wrap("EXPLORATORY. Written after the results of 23 were seen; nothing here was registered. The control is the"
               " stored N run of pre-registration 14: another launch and another seed (seed 1; PE and PH ran seed 2)."
               " Its lists are replayed offline (analysis/modal_h/push_23.py on the reads that run made) and were seen"
               " by no agent; a real push changes what a run does next, so the would-be lists are not those of PE or"
               " PH."))
    add("")

    add("0. GATE: lists per arm (expected 493, 465, 485)")
    for lab, want in (("PE", 493), ("PH", 465), (CTL, 485)):
        n = sum(len(v) for v in lists[lab].values())
        add("  %s: %d (%s)" % (NAME[lab], n, "reproduced" if n == want else "NOT reproduced, expected %d" % want))
    add("")

    add(B.wrap("1. CONTENT BEFORE THE KEY, per list: lines the READ returned (end_line - start_line + 1, as the result"
               " reports them) and characters of its content field as the agent received it"))
    for lab in LABS:
        rows = [r for v in lists[lab].values() for r in v]
        add(B.wrap("%s lines: %s" % (NAME[lab], quart([r["lines"] for r in rows])), "  ", "    "))
        add(B.wrap("%s characters: %s" % (NAME[lab], quart([r["chars"] for r in rows])), "  ", "    "))
        add(B.wrap("%s lines, lists with an entry in an unopened file: %s"
                   % (NAME[lab], quart([r["lines"] for r in rows if r["fresh"]])), "  ", "    "))
    allfresh = sorted(r["lines"] for lab in LABS for v in lists[lab].values() for r in v if r["fresh"])
    c150 = collections.Counter(r for r in allfresh if r >= 145)
    add(B.wrap("Lists with an entry in an unopened file, all arms pooled: %d; returned exactly 150 lines %d; 145 to 149"
               " lines %d; more than 150 %d." % (len(allfresh), c150.get(150, 0),
                                                 sum(c150[x] for x in range(145, 150)),
                                                 sum(1 for r in allfresh if r > 150)), "  ", "    "))
    add(B.wrap("Returned lines are capped at 150 by the harness and more than half of these lists sit exactly at the"
               " cap, so thirds of returned lines cannot be cut (the 2/3 point is 150 itself); the second split uses"
               " thirds of the characters of content instead.", "  ", "    "))
    charsfresh = sorted(r["chars"] for lab in LABS for v in lists[lab].values() for r in v if r["fresh"])
    t1 = r18.percentile(charsfresh, 1 / 3)
    t2 = r18.percentile(charsfresh, 2 / 3)
    add("")

    def group_report(title, groups):
        add(B.wrap(title))
        outcomes = (("reads a neighbor's code, redefined next call", "reads"),
                    ("opens the file, redefined next call", "opens"),
                    ("reads a neighbor's code, within 3 calls (p+1 to p+3)", "w3"))
        for gname, sel in groups:
            add("  " + gname)
            for oname, key in outcomes:
                parts = []
                for lab in LABS:
                    rows = [r for v in lists[lab].values() for r in v if r["fresh"] and sel(r)]
                    parts.append("%s %s" % (NAME[lab], B.pct(sum(r[key] for r in rows), len(rows))))
                add(B.wrap("%s: %s" % (oname, "; ".join(parts)), "    ", "      "))
            for a, b in (("PE", "PH"), ("PE", CTL), ("PH", CTL)):
                def frac(lab, t):
                    rows = [r for r in lists[lab].get(t, []) if r["fresh"] and sel(r)]
                    return (sum(r["reads"] for r in rows), len(rows))
                tasks = [t for t in run_list if t in lists[a] and t in lists[b] and frac(a, t)[1] and frac(b, t)[1]]
                fa = [frac(a, t) for t in tasks]
                fb = [frac(b, t) for t in tasks]
                ma = [x / n for x, n in fa]
                mb = [x / n for x, n in fb]
                d = [x - y for x, y in zip(ma, mb)]
                lo, hi = R.boot(d, 100.0)
                if tasks:
                    add(B.wrap("paired, reads a neighbor's code (redefined next call), %s minus %s: %d tasks; mean %s"
                               " %.2f%%, %s %.2f%%; difference %s points [%s, %s]; pooled %s %s, %s %s"
                               % (NAME[a], NAME[b], len(tasks), NAME[a], 100 * R.mean(ma), NAME[b], 100 * R.mean(mb),
                                  R.signed(100 * R.mean(d)), R.signed(lo), R.signed(hi), NAME[a],
                                  B.pct(sum(x for x, _ in fa), sum(n for _, n in fa)), NAME[b],
                                  B.pct(sum(x for x, _ in fb), sum(n for _, n in fb))), "    ", "      "))
                else:
                    add("    paired, %s minus %s: no task with such a list in both runs" % (NAME[a], NAME[b]))
        add("")

    group_report("2. BY RETURNED LINES, FIXED CUTS (lists with an entry in a file not opened before; per-run shares;"
                 " 95% bootstrap by task, 2,000 resamples, random.Random(0) afresh for each comparison)",
                 (("up to 40 lines", lambda r: r["lines"] <= 40), ("41 to 149 lines", lambda r: 41 <= r["lines"] <= 149),
                  ("150 lines or more", lambda r: r["lines"] >= 150)))
    group_report("3. BY CHARACTERS OF CONTENT, THIRDS (cut points the 1/3 and 2/3 percentiles of content characters over"
                 " the lists with an entry in an unopened file, all three arms pooled: %.1f and %.1f)" % (t1, t2),
                 (("lower third (<= %.1f characters)" % t1, lambda r: r["chars"] <= t1),
                  ("middle third (%.1f < characters <= %.1f)" % (t1, t2), lambda r: t1 < r["chars"] <= t2),
                  ("upper third (> %.1f characters)" % t2, lambda r: r["chars"] > t2)))
    group_report("4. BY SOURCE NODES OF THE LIST (as section 2)",
                 (("one source node", lambda r: r["sources"] == 1), ("two source nodes", lambda r: r["sources"] == 2)))

    add("JUDGMENT CALLS")
    for i, text in enumerate([
        "Lists, entries, 'a file not opened before', the scorer, the redefined next call (first tool call of the first"
        " model step after the step whose result carried the list) and 'within 3 calls' (call indexes p+1 to p+3) are"
        " those of analysis/explore_next_call_23.py, imported.",
        "Returned lines: end_line - start_line + 1 of the READ's result, the range the result reports (a read cut by"
        " the character limit can report more lines than its content holds). Characters: the length of the result's"
        " content field; the key follows the content in the result object.",
        "Source nodes: the length of the key's value in the trace for PE and PH (sources whose neighbors were all"
        " dropped are left out of the value, as the agent saw it); for N14 the length of the would-be value, recorded"
        " by wrapping push_23.Pusher.on_read for the duration of the replay.",
        "The thirds are cut on the pooled content characters of the three arms (percentiles with linear"
        " interpolation, rederive_18.percentile), so the same cut points apply to each arm. The fixed cuts by lines"
        " are those asked for; with the cap at 150, '150 or more' is 'exactly 150'.",
    ], 1):
        add(B.wrap(text, "%2d. " % i, "    "))
    sys.stdout.write(("\n".join(out) + "\n").replace("\xa0", " "))


if __name__ == "__main__":
    main()
