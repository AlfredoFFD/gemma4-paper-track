# Prior-art search: the reading rule, the caller split and "print addresses" (Nov 10, 2026)

[Claude Code] Search log for three statements of `paper/draft.md` that the earlier logs in this folder do not
cover. Bounded passes by hand with a web search tool and page reads; not an exhaustive sweep. Nothing here was
found by reading a paper's full text unless the row says so.

## The statements searched

1. **The reading rule.** A coding agent's first read of a file starts at line 1 unless the tool result just before
   named a line of that file; then it asks for that line. (Counted in public runs, then tested on our episodes
   against thresholds fixed in advance.)
2. **Names against addresses.** With the same graph neighbors at the same paused agent step, a list written with
   each neighbor's file and line range is followed and a list of names is not.
3. **Callers.** What the address adds is mostly callers of the code just read; the fix sites a run misses that are
   one call from code it saw are mostly callers.

## What was run

| Pass | When (EST) | Searches | Pages read |
|---|---|---|---|
| 2 | 4:26 PM | five search calls, fifteen queries | three |
| 2b | 5:26 PM | none | results section of arXiv 2604.02547 |
| 3 | 6:16 PM | four search calls, twelve queries (below) | arXiv 2606.26979 (abstract page and PDF text), arXiv 2611.07286 (abstract page and HTML), one vendor post through search excerpts and one analysis of it |

Pass 1 is `2026-11-09-encoding-claim-prior-art.md` and `2026-11-10-related-work-check.md` in this folder.

Queries of pass 3: coding agents missed edit locations callers call graph analysis; incomplete patches
multi-location fixes LLM agents call sites not updated; SWE-bench failures agent edits function but not its
callers; CodePlan repository-level coding LLMs planning may-impact analysis; edit propagation callers dependency
graph LLM repository-level; change impact analysis call graph callers LLM code editing agent; tool output format
symbol name versus file line number coding agent experiment; agent-computer interface tool result line numbers
agent follows locations; code graph tool output encoding LLM agent reads referenced code ablation; and three
queries for the vendor post by its title.

## Statement 1, the reading rule

| Work | What it has | What it lacks |
|---|---|---|
| SWE-agent, arXiv 2405.15793 | describes agents zooming in from a directory search to a file search and a jump to a line; an `open` command that takes an optional line; a numbered viewer; an ablation of window size | no count of where a first open starts by what the search printed; no test |
| Mehtiyev and Assunção, arXiv 2604.02547 | its trajectory encoding has one symbol for browsing a whole file and one for a targeted read (results section read) | the two are not conditioned on what the previous output held; its findings are about reading before patching and validation effort |
| CodeGrep, arXiv 2608.05886 | notes that its predicted line ranges went unused because the downstream editor took only paths, and conjectures that editors which take ranges may benefit | no measurement of the downstream agent's reads |
| Xu, arXiv 2608.13568 (excerpt) | a find-references tool returns `path:line` only, the agent then opens those files, and that arm makes more read calls | no count of where the reads start |
| FastContext, arXiv 2606.14066 (excerpt) | an explorer subagent that hands the main agent file paths with line ranges | a design, not a measurement |
| Practitioner posts of 2026 (a code-search vendor, an agent vendor, a survey of nine agents' grep tools) | tools that return paths with line ranges; one survey notes that some grep tools return paths only and describes a find-then-read workflow | no measurement |

**Verdict.** Anticipated in words (zooming in; "give the agent locations" is common tool-design advice) and its
outcome exists as a trajectory feature in one study. Not found: the measured conditional, the same split across
agents, or a test with thresholds fixed in advance.

## Statement 2, names against addresses

| Work | What it has | What it lacks |
|---|---|---|
| A code-quality vendor's post on its graph navigation engine (June 30, 2026) | states the principle: every node and edge carries a file path and a line, so a query returns edit locations rather than names; cost per run on six refactoring tasks | no arm that prints names |
| ARISE, arXiv 2605.03117; LocAgent, arXiv 2503.09089 (App. A.1.2); the logs of pass 1 | graph tools that return file and line; output formats compared on localization accuracy | the next call is not the outcome; the entry's address is not the only thing varied |

**Verdict.** The prescription exists as advice and as a design choice. Not found: the same neighbors at a paused
step with only the writing changed and the next call scored. The paper should say "test" and "measure".

## Statement 3, callers

| Work | What it has | What it lacks |
|---|---|---|
| Lin, Zhou, Yang, Li, arXiv 2606.26979 (ISSTA 2026) | call, called-by, parent and inheritance links written into the source as comments for a Codex agent, SWE-bench Lite and Verified. Callers only against both directions: worse on Lite (Func@5 0.8242 against 0.8540; 55.0 rounds against 33.7), level on Verified (0.6329 against 0.6308). Abstract: hub-heavy projects benefit from inverse-only links. Case analysis: the inverse links do most of the navigating, since walking forward along calls is easy for any agent | no count of which fix sites runs missed, by direction; no rewired baseline; entries name a file and no line |
| CodePlan, arXiv 2309.12499 (FSE 2024) | change may-impact analysis: a changed method signature marks its callers as affected, and edits are planned for them | not about what an agent reads next |
| Xu et al., arXiv 2607.28815 (excerpt) | holds back an edit until the callers of the edited function, from a call graph, have been inspected in the trajectory | a system built on the premise; no count by direction |
| Sepidband et al., arXiv 2611.07286 | call-graph wins on SWE-bench Pro are mostly fixes in a caller or callee of the reported symbol (11 of 20); resolution near the baseline while tokens fall | no split by direction |

**Verdict.** Not new in kind: that reverse call links carry the value an agent cannot read off the code is the
conclusion of arXiv 2606.26979 for large repositories, and edit propagation to callers is older. Ours is a count on
this competition's runs and graph, against rewired graphs, and a post hoc split of a registered contrast. Cite
arXiv 2606.26979 with its caveat: on medium-sized repositories its callers-only variant did worse.

## Not checked

- Full texts of arXiv 2606.17454, 2608.13568, 2606.14066 and 2607.28815 (search excerpts only).
- The SWE-agent appendix with its transition figure and prompts.
- Proceedings and OpenReview by exact phrase; anything behind a login; same-track writeups that are hidden.
