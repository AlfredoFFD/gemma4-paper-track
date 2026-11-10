# Pre-registration 09: fresh episodes, the graph tools' answers as shipped or with addresses

Status: FROZEN on Nov 10, 2026, 2:04 PM EST, by the commit that adds this file, before any episode of arms NA or
NAF ran on any platform and before any full-run episode of arm N. It adds to pre-registrations 02 to 08 and changes
none of their rules.
Tags: [Claude Code] wrote it; [team] had asked for whatever runs the paper still needs and had not read this text when
it was frozen.

File hashes at freezing (md5): `analysis/modal_g/forks_09_runner.py` `1cff77481df8a0b077e3b888ef4fe7e9`, `analysis/modal_g/forks_09_modal.py`
`5565cfc6eee97fb897e28e1b87934ac6`, `analysis/analyze_09.py` `cd70863fd28dd6e12e04891ced4ecc3d`, `analysis/make_spans_g.py` `bff3f3c10b3f25d83c1c74426b9d7d09`,
`analysis/fork_states_g/spans_manifest.json` `edd04029c88e9e3788934f0a3d6fa63c` (one md5 per task's address table),
`analysis/fork_states_g/fresh_states.jsonl` `2bb8662de0f614d8cbf3be1c9a244f36`. Used unchanged: `analysis/replay.py`
`446b85be41d90e0e8fdb7c32dd5ea2f1`, `analysis/replay_k.py` `6d4e2f73274b9bc77b67eb86488c915d`, `analysis/nodes.py`
`94b67ad0c693c8ef584d39e9538f4f78`, `analysis/analyze_g.py` `87cee4f91cc6d1a6bc8a591979d41a24`, `analysis/analyze_k.py`
`20294af5a37d5348f9bd0e20887b722b`. Code changes that the platform forces after this freeze are recorded at the end
of this file as dated amendments with the new hashes; the outcome definitions and the rules cannot change.

## Why

1. Every one-step result so far pushes the neighbor list at the agent. In the original runs the agent called
   `get_code_neighbors` 8 times in 318 runs, so a reader can ask whether a better-written answer would ever be seen.
2. The smoke tests of pre-registration 08 (12 fresh episodes on the newest harness wheels) showed that the agent
   calls `search_similar_code` early: five of the first six episodes ended at such a call before the graph tools were
   allowed to execute. So the tools' own answers can be tested where the agent asks for them.
3. The three graph tools return names (and, for `search_similar_code`, the code of each result) and no file or line.
   The one-step experiments found that file and line range are what the agent acts on (pre-registrations 03 to 05).
4. A second session's first look at other teams' public runs (EXPLORATORY, not yet re-derived in this repository)
   points the same way: a first read of a file asks for lines past line 1 when the observation just before named
   the file with a line number, and almost never when it named only the file.
5. Blind readers of the draft asked for a test of the proposed change on the tool itself, in fresh episodes.

## Design

Platform, model (Gemma-4-31B QAT W4A16), server settings and replay code as in pre-registration 08; the newest
harness wheels (adk_submission 0.2.13, swegemma 0.2.11). One new episode per task and seed for the 106 tasks with a
public base trace (`analysis/fork_states_g/fresh_states.jsonl`), seeds 1 to 3: nothing is seeded, the task prompt the
original harness logged for the task is the first message. Up to 8 model calls. `read_file`, read-only shell
commands and the three graph tools execute through the harness's own tool functions; the episode stops before the
first other call, after the eighth model call, or on a response with no call (pre-registration 08 as amended).

Three arms with the same tasks and seeds, 954 episodes:

| Arm | Graph tools' answers | Argument names |
|---|---|---|
| N | as shipped | as the harness handles them |
| NA | every returned entity that resolves in the task's snapshot gets its file and line range: `neighbors` of `get_code_neighbors` and `nodes` of `get_code_subgraph` become `{"name", "file", "lines"}` entries (the entry format of arm EL), each of `search_similar_code`'s `results` gets `"file"` and `"lines"` after its `"node_name"`; an entity that does not resolve keeps its name only; nothing else changes | the same |
| NAF | as NA | a mangled line-bound name of `read_file` is restored before the call runs (arm AF of pre-registration 08) |

The addresses come from `analysis/make_spans_g.py`, which applies the resolver of every earlier experiment
(`analysis/nodes.py`) to every node of the task's code graph. Arm N of this run is the arm of pre-registration 08's
part "fresh": rule N1 is evaluated on it, unchanged.

## Outcomes

- **Ynext.** The episode has a first graph answer that returns at least one entity with a line range in a file the
  episode has not read with `read_file`, and the first call of the next model response reads that entity: the frozen
  scorer `fork_states.touches` (a `read_file` whose range overlaps the entity's lines within the harness's caps, an
  edit of its file, or a shell view of those lines or its name; a graph-tool call does not count). An episode without
  such an answer, or with no next call, scores 0. In arm NAF a call is scored as it was executed (bounds restored).
- **Yline.** The agent is shown a line the gold patch changes within the eight calls (pre-registration 06's
  definition, with every file the gold patch modifies as a target).

## Rules

Analysis: `analysis/analyze_09.py <run_dir>`.

**N1** (pre-registration 08, unchanged), on arm N.

**A1, addresses in the tool's own answer.** NA minus N on Ynext, over all episodes of complete tasks. "Addresses in
the graph tools' own answers bring the next call to a returned entity's code" if the lower 95% bound is above 0;
otherwise "no detectable difference". Reported beside it: the rate among episodes that have such an answer, how often
the next call is instead a shell command naming a returned entity or its file, and how often a returned entity is
read at some later call.

**A2, the patched harness in fresh episodes.** NAF minus N on Yline, over the complete tasks whose gold patch
modifies a file. "The patched harness brings the agent to the fix's lines within eight calls of a fresh start" if the
lower 95% bound is above 0; otherwise "no detectable gain".

Descriptive, with no rule: every arm's rates with intervals; NA minus N and NAF minus NA on Yline and on opening a
changed file; the share shown a changed line by the end of each call; how many episodes call a graph tool, which
tool and at which call; mangled ranged reads by arm; stop reasons and call counts; and a check that every address
printed in an answer equals the resolver's.

## Common rules

- An episode that ended in an error is excluded and counted by arm. A task is complete if all nine of its episodes
  finished without an error; the contrasts use complete tasks only.
- 95% bootstrap intervals clustered by task, 2,000 resamples, seed 0 (`analyze_forks.boot_ci`, `diff_ci`).
- Tasks run in a fixed shuffled order, so a run cut short is a random subset; the rules apply if at least 60 tasks
  are complete, below that everything is EXPLORATORY.
- Every contrast uses arms of this run. Anything not listed here is EXPLORATORY.

## Stated limits

- `search_similar_code` already shows the code of each result. An address there tells the agent where that code
  lives; the next call may have no reason to read it again. A1 counts what the next call does, so it can understate
  an address that is used only later (the later reads are reported).
- The addresses are added after the tool applied its own character cap, so addressed answers are longer than the
  shipped ones.
- The arms are paired by task and seed, and see the same prompt until the first graph answer; the pairing is by
  design, not exact, because the server batches concurrent requests.
- As in pre-registration 08: these episodes are the harness's compiled agent, its tools and the same model server,
  started from the task prompt an earlier harness version logged; they are read-only and end at the first edit,
  write or other command; the full evaluation loop's plugins and compaction are not installed; no test runs.
- A2 has little power (below); a null there does not show that the changes are useless.
- One model, two repositories and one task of a third.

## Power, stated as assumptions

No earlier estimate of either rate exists for fresh episodes. If about 60% of episodes have a qualifying graph
answer and the next call reads a returned entity in 15% of them with addresses against 2% without, A1's difference
is about 8 points over all episodes, with a half-width near 4 by task (assumed from the spread of the one-step
experiments). A2: with 105 tasks and three seeds the half-width is assumed near 8 points, so only a large gain can
be detected.

## What is reported regardless of outcome

Every rule above with its interval, met or not; every arm's rates; errors by arm; the checkout fingerprints; the raw
per-episode records; and the versions recorded by the run.
