# Pointer audit: blind re-derivation vs the original

Blind script: `analysis/rederive_audit.py`, output in `analysis/results/rederive_audit.txt`. It was written from the
Sep 30 definitions only, before `experiments/00-pointer-audit/` or NOTES.md was opened. The original is
`experiments/00-pointer-audit/pointer_audit.py` and `decoy_bite.py`, with outputs in `results/`. Both scripts read the
same `data/tasks.jsonl`, snapshots and graphs. Everything here is EXPLORATORY, as the original was.

| Quantity | Original | Re-derived | Status | Diagnosis |
|---|---|---|---|---|
| K1, tasks with all units addressable | 103/122 (84.4%) | 103/122 (84.4%) | MATCH | Same 122 eligible tasks and same 103 passing tasks |
| K1 failures by repo | fastapi 18/64, httpx 1/1 | fastapi 18/64, httpx 1/1 | MATCH | rich and requests are 100% in both |
| Unit level | 466/523 (89.1%) | 458/515 (88.9%) | CLOSE | 8 extra units in the original; their only edit is an added function-local `import` plus a blank line (see below) |
| Missing units / of which async | 57 / 55 | 57 / 55 | MATCH | Same 57 missing units (the other 2 are nested `Config` classes in docs_src) |
| Reach, 1 hop, cap 50 | 13/129 (10.1%) | 13/129 (10.1%) | MATCH | Same 13 tasks, same per-task bite counts |
| Reach by repo | fastapi 8/67, rich 4/48, requests 0/13, httpx 1/1 | same | MATCH | |
| Reach, 1 hop, no cap | 15/129 (11.6%) | 15/129 (11.6%) | MATCH | Same 15 tasks |
| Reach, 2 hops | 25/129 (19.4%) | capped: 19/129 (14.7%); uncapped: 25/129 (19.4%) | MISMATCH under the stated definition | The original's 2-hop set has no degree cap at either hop; with the cap on each expanded node it is 14.7% |
| Issue names a gold unit directly | 35/129 (27.1%) | 35/129 (27.1%) | MATCH | Same 35 tasks |
| Issue mentions at least one graph node | 97/129 (75.2%) | 97/129 (75.2%) | MATCH | Same 97 tasks, same mentioned-node count in every task |

## Causes of the differences (from task- and unit-level sets)

**Unit level, 466/523 vs 458/515.** The unit sets differ in exactly 8 units, in 2 tasks, and nowhere else. The
re-derivation has no unit that the original lacks, and every shared unit has the same addressability and the same
graph id.
- `fastapi_14186`: `fastapi/utils.py::create_cloned_field`.
- `rich_4070`: `Console.export_html`, `Console.export_svg`, `Console.log`, `Emoji.__init__`, `RichHandler.emit`,
  `auto.do_replace.auto_rich_repr`, `Theme.from_file`.

In each one, the gold patch's only change inside the function is an added local import (for example
`from html import escape`) followed by a blank line. `pointer_audit.py` (lines 149-152) collects import lines from
`tree.body` only, so it ignores module-level imports and counts imports inside a def as edits. The re-derivation
ignores import statements at every level. The definition says "Import lines ... are ignored" and does not name a
level, so both readings are defensible. The difference does not change any task-level number, because both tasks are
all-addressable under either reading. It does change these per-task counts in the original's decoy table:
- `rich_4070`: gold nodes 17 vs 10, named directly 6 vs 2, two-hop bites 11 vs 8.
- `fastapi_14186`: gold nodes 30 vs 29.

No task's yes/no status changes.

**Two hops, 19.4% vs 14.7%.** `decoy_bite.py` builds the set as `one_hop_any | {neighbors of every node in
one_hop_any}`, with no cap at either hop. The registered NOTES entry gives no 2-hop definition; the 19:24 results
entry says "At 2 hops: 19.4%" and does not mention the cap. The re-derivation's uncapped variant reproduces the
original exactly: 25 tasks, the same set. With the cap applied to each expanded node, 6 tasks drop out, all of them
rich: `rich_2943`, `rich_3061`, `rich_3470`, `rich_3480`, `rich_3521`, `rich_3777`. In each, the only path to the gold
node runs through a mentioned or intermediate node with more than 50 unique neighbors. A paper that says "19% at two
hops" next to a capped 1-hop number mixes two tool models.

**Mention matching.** The two implementations match dotted names differently:
- The original requires a node suffix to equal a whole dotted token from the text.
- The re-derivation accepts any contiguous sub-chain of a dotted token.

On this data the two give identical mentioned-node counts in all 129 tasks, so the difference is moot here.

## Ranges a careful paper can state (Wilson 95% intervals)

- K1: 103/122 = 84.4% [77.0, 89.8]. Unit level: 88.9-89.1%, depending on how local imports are treated.
- Reach, 1 hop, cap 50: 13/129 = 10.1% [6.0, 16.5]. The kill line was 12 tasks, so the WEAKENED verdict rests on a
  single task.
- Reach, 2 hops: 14.7% [9.6, 21.9] with the cap, 19.4% [13.5, 27.0] without it. State which one.
- Direct naming: 27.1% [20.2, 35.4]. At least one mentioned node: 75.2% [67.1, 81.8].

## Not checked

- Whether the graph builder really names nested defs as `outer.inner` or flattens them. Both scripts share this
  assumption, so their agreement does not test it.
- Whether `get_code_neighbors`' default of 50 caps unique neighbors or edges, and what it does past the cap (truncate
  or refuse). Both scripts treat a node over 50 as giving nothing, which comes from HARNESS_README, not the wheelhouse
  source.
- The embedding bite, K2, K3, and K1 on package source only. These were outside this brief.
