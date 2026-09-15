# Phase 2 — Agent Inputs and Spawn Conditions

Loaded by `/review-all` Phase 2. Lists every parallel agent, the diff slice it receives, and when to spawn it.

Agent personas are listed directly in SKILL.md's Phase 2 section so they live one-hop-deep from SKILL.md (per the Skills spec's reference-depth rule). This file holds only the spawn-condition table, slice mapping, chunking, and timeout/retry rules — no new agent references.

## Agent inputs (per agent)

All slices below are computed from the **filtered diff** — i.e. after `--paths` / `--exclude` and the multi-workspace scope prompt from Step 0.1 have been applied. No agent ever sees files outside the user-resolved scope.

To reduce token duplication, send each agent only the diff slice it needs. **The slice is not chosen by hand — it is the `files` array `scripts/select-agents.py` returns for that axis** (SKILL.md Phase 2). The table below states what that computes to:

| Agent | Diff slice |
|-------|-----------|
| Standards (01) | Reviewable diff |
| Bugs & Security (02) | Reviewable diff |
| DRY & Smells (03) | Reviewable diff + related files (callers/callees if codegraph) |
| Consistency & History (04) | Reviewable diff + git blame on changed sections |
| Simplification (05) | Reviewable diff |
| Security Deep Dive (06) | Files with class `security` |
| Performance (07) | Reviewable diff |
| Test Quality (08) | Files with class `test`, plus Added files with class `code` |
| API & Contract (09) | Files with class `contract` |
| A11y & i18n (10) | Files with class `ui` or `i18n` |

**"Reviewable diff" is narrower than "full diff" was.** It is the changed-file set after Step 0.8's pre-dispatch gates — binary, secret paths, the generated/vendor/lock list, and any single file whose diff exceeds `maxFileDiffBytes`. Six of these ten axes receive it, so a lockfile or a `dist/` bundle that slipped through used to be duplicated six times over. What is *not* done here is concern-based narrowing of those six — Performance still sees every reviewable file, not a guess at which files have hot paths. That is where a missed bug would hide, and it is deliberately not attempted.

All agents also receive: changed file list, Project Profile, CLAUDE.md rules, Phase 1 gate results, PR description if applicable, and the `<previously_dismissed>` digest of `wontfix` / non-expired-`snoozed` findings from `stateFile` (built in SKILL.md Phase 2). Agents suppress a matching finding only when its location is **unchanged in this diff** — see `agents/_shared.md` → Previously-dismissed findings. (This reverses the earlier "agents don't need the suppression list" stance: feeding the team's own dismissals up front spares re-deriving and re-verifying them; the Phase 2.5 Step 2.5.0 central filter still drops any that slip through, so it remains the guarantee — the digest is a spend-saving hint, not the gate.)

## Per-agent diff ordering

Every agent sees the same diff content, but **each sees the files in a different order**. Attention is not uniform across a long prompt, so ten agents handed an identically ordered diff share the same weak middle; permuting per agent decorrelates that blind spot at zero token cost. (Same lever as the randomized-order passes Cursor's Bugbot reports, and the multi-pass aggregation gain measured in SWR-Bench — here it comes free, because ten passes already run.)

Before spawning, call the ordering script **once** with the union of changed files:

```bash
echo "$CHANGED_FILES_JSON" | python3 scripts/agent-order.py --agents 10
```

It returns a permutation per agent number, derived from `sha256("<agent>:<path>")` — reproducible across runs and machines, so a review stays replayable. Assemble each agent's `<diff>` by concatenating its per-file diff slices in that agent's order.

Rules:

1. **Apply only when the agent's slice holds ≥ 3 files.** Below that a permutation carries no information; skip the reorder (the script call is still made once for the run, not per agent).
2. **Chunk composition is computed on the canonical `git` order first; the per-agent order is then applied to the files *within* each chunk.** Chunk membership must stay identical across agents and runs — otherwise related siblings (a source file and its spec) land in different chunks for different agents, and the Phase 2.75 chunk accounting stops being comparable.
3. **Hunks within a file are NEVER reordered.** The unit is the file; a file's hunks stay in source order, and per-file attached context travels with it (agent 04's `git blame` block moves with its file, never decouples from it).
4. **The verifier is unaffected.** It re-reads cited sources by `file:line`, so its judgment is order-independent by construction.

## Agents to spawn

**Spawn conditions are data, not prose.** Each condition below names a *file class* assigned by `scripts/file-classes.json` and evaluated by `scripts/select-agents.py`. The orchestrator spawns what the script returns; it does not re-derive these conditions by reading the diff.

| # | Agent | Persona | Model | Spawn condition |
|---|-------|---------|-------|-----------------|
| 1 | Standards & Clarity | `01-standards.md` | `sonnet` | Always |
| 2 | Bugs & Security | `02-bugs-security.md` | `opus` | Always |
| 3 | DRY & Code Smells | `03-dry-smells.md` | `sonnet` | Always |
| 4 | Consistency & History | `04-consistency-history.md` | `sonnet` | Always |
| 5 | Simplification | `05-simplification.md` | `sonnet` | Always |
| 6 | Security Deep Dive | `06-security-deep-dive.md` | `opus` | Any file with class `security` |
| 7 | Performance | `07-performance.md` | `opus` | Always |
| 8 | Test Quality | `08-test-quality.md` | `sonnet` | Any file with class `test`, OR any Added file with class `code` |
| 9 | API & Contract | `09-api-contract.md` | `opus` | Any file with class `contract` |
| 10 | A11y & i18n | `10-a11y-i18n.md` | `sonnet` | Any file with class `ui` or `i18n` |

Every axis is `spawn: false` when the reviewable set is empty — a review whose every changed file was excluded spawns nothing and says so.

`extraAgents` and `skipAgents` from `.claude/review-all.json` are passed to the script as `--extra` / `--skip`; `skipAgents` overrides an `Always` row.

**Why this moved out of the personas.** Axes 6, 8, 9 and 10 each still carry an `**Only spawn this agent if** …` / `## Skip if` line, and that line can only execute once the agent is already running. As the sole mechanism it bought nothing: a backend-only diff paid four spawns — persona plus `_shared.md` plus project profile, a measured **73 545-character floor** before any diff — to receive four empty arrays. The persona lines stay as a fallback for a hand-spawned agent; the gate is now the script.

Each agent returns findings with `root_cause_key` (used for cross-agent dedup).

## Model per axis

**Every spawn passes an explicit `model`, and a `subagent_type` of `general-purpose`.** Omitting `model` is not "use the default" — it silently inherits the parent session's tier, so a review started on an expensive model runs all ten axes there, including the ones that gain nothing from it. The column above is the source of truth for the orchestrator; the same value is declared in each persona's frontmatter `model:` field so the tier travels with the persona it describes. **An agent whose persona declares no `model` — anything added via `extraAgents` — spawns at `sonnet`.**

The split is by **what the axis has to prove**, not by how important it feels:

- **`opus` — the finding is a claim about behavior.** Bugs & Security, Security Deep Dive, Performance, API & Contract each have to simulate execution, adversarial input, or a downstream consumer to know whether the finding holds at all. That is the reasoning the larger model buys, and it is also where a false negative is most expensive.
- **`sonnet` — the finding is a mismatch against a known shape.** Standards, DRY & Smells, Consistency & History, Simplification, Test Quality, A11y & i18n compare the diff against a convention, a sibling occurrence, a git-history precedent, or a checklist. The evidence is in the diff and the cited file; a bigger model re-reads the same lines to the same conclusion.

Precision is preserved from the other end regardless of tier: **every finding still passes the Phase 2.5 hostile verifier**, so a weaker axis over-flagging costs a verifier call, not a false positive in the report. The asymmetric risk is a missed bug, which is why the behavioral axes stay on `opus`.

Verifiers are out of scope for this table — they already spawn with an explicit model, the `verifierModel` config tier (default `haiku`, see `config-keys.md`), and that covers the Step 2.5b-vote passes too.

## Checkpoint resume (per axis)

An interrupted review must not re-pay for the axes that already finished. Each completed axis is persisted to `<checkpointDir>/<axis>.json` (default `.claude/review-all/checkpoints/`) and reused on a later run **only** when that run is provably the same review.

```bash
# before spawning — returns runKey + the axes already done.
# Pipe the RESOLVED, FILTERED diff (post --paths/--exclude, post scope prompt):
# it must be the exact bytes the agents will review, or a narrowed re-run
# resumes findings from a wider diff.
git diff <resolved range> -- <filtered file list> | python3 scripts/checkpoint.py load --head "$(git rev-parse HEAD)" --dir <checkpointDir>

# as each agent returns
echo "$AGENT_FINDINGS_JSON" | python3 scripts/checkpoint.py save \
  --run-key "<runKey>" --axis "<agent id>" --head "$HEAD_SHA" --dir <checkpointDir>
```

Rules:

1. **The key is all-or-nothing.** `runKey` = sha256 over the skill fingerprint (`SKILL.md` + every `agents/*.md`), the reviewed repo's HEAD sha, the exact diff bytes, and a manifest of `REVIEW.md` + `.claude/review-all.json`. A new commit, an edited working tree, a narrowed `--paths` scope, an edited persona, or an edited `REVIEW.md` changes the key and invalidates **every** axis. There is no partial or fuzzy match — a resumed axis reviewed byte-identical input under byte-identical instructions.
2. **Only complete returns are saved.** Timeout, error, malformed output, or a chunked agent missing a chunk → no checkpoint, so the next run re-runs that axis. A chunked agent is checkpointed once, after its chunks are merged. `[]` is a complete result and IS saved.
3. **Saved pre-dedupe, pre-verification.** The store holds the agent's own return. It is independent of `state.json`, which tracks finding lifecycle *across different diffs*; conflating them would let a verified-away finding resurrect, or a diff change go unnoticed.
4. **Resumed counts as returned** in the Phase 2.75 completion gate, and the Phase 3 report names the resumed axes (`references/phase-3-report.md` → *Agents run*) — a reader must never mistake reused findings for a fresh pass.
5. **Stale files are deleted, not kept.** `load` removes every checkpoint whose key, schema, or filename does not match, so the directory holds at most one file per axis for the current key. Force a full re-run by deleting the directory.
6. **Optional, never load-bearing.** No `python3` (Phase 0.0 `available`) → no checkpointing; spawn every axis as before.

## Chunking large slices

A single agent's diff slice can blow past the model context window on big refactors. Before spawning, measure the slice:

- `slice_files = number of files in the slice`
- `slice_bytes = byte size of the slice (diff text + any related files attached)`

If `slice_files > chunkMaxFiles` (default `40`) OR `slice_bytes > chunkMaxBytes` (default `200000`):

1. Split the slice into N chunks, each respecting both limits. Prefer splitting on file boundaries; only split inside a file if a single file exceeds the byte limit.
2. Spawn the agent N times in parallel, each with: persona + `_shared.md` + the chunk + `"chunk index i of N — only review the files in this chunk; do NOT speculate about omitted files"`.
3. Merge findings by `root_cause_key` before handing to Phase 2.5. Duplicate keys across chunks collapse into one, with `confirmed_by` listing chunk indices that flagged it.

Both thresholds configurable via `.claude/review-all.json` keys `chunkMaxFiles` and `chunkMaxBytes`. Set either to `0` to disable that limit.

Chunked agent status in the Phase 2.75 map: an agent is `returned` only when **all** chunks returned; any chunk failure follows the normal retry-once rule below.

## Timeouts & retry

- Spawn every Phase 2 agent with an explicit wall-clock budget. Default `agentTimeoutSeconds: 600`; override via `.claude/review-all.json`.
- A timed-out, failed, or retried-then-failed agent is **never checkpointed** — only a clean return is (see *Checkpoint resume*).
- If an agent exceeds its budget or returns malformed output, re-spawn ONCE with the preamble: `"Previous run failed (<timeout|schema|empty>). Re-attempting with same inputs."`.
- After one retry, surrender — do not loop. Phase 2.75 surfaces the missing agent in the report banner.
- Track per-agent status in an internal map: `pending | running | returned | failed`. Phase 2.75 reads this map.
