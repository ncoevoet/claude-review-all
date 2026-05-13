# Phase 2 — Agent Inputs and Spawn Conditions

Loaded by `/review-all` Phase 2. Lists every parallel agent, the diff slice it receives, and when to spawn it.

Agent personas are listed directly in SKILL.md's Phase 2 section so they live one-hop-deep from SKILL.md (per the Skills spec's reference-depth rule). This file holds only the spawn-condition table, slice mapping, chunking, and timeout/retry rules — it does not introduce new agent references.

## Agent inputs (per agent)

All slices below are computed from the **filtered diff** — i.e. after `--paths` / `--exclude` and the multi-workspace scope prompt from Step 0.1 have been applied. No agent ever sees files outside the user-resolved scope.

To reduce token duplication, send each agent only the slice of the diff it needs:

| Agent | Diff slice |
|-------|-----------|
| Standards (01) | Full diff |
| Bugs & Security (02) | Full diff |
| DRY & Smells (03) | Full diff + related files (callers/callees if codegraph) |
| Consistency & History (04) | Full diff + git blame on changed sections |
| Simplification (05) | Full diff |
| Security Deep Dive (06) | Auth/crypto/API/infra files only |
| Performance (07) | Full diff |
| Test Quality (08) | Test files in diff + new public functions in source diff |
| API & Contract (09) | Files with public exports / schemas / routes / migrations |
| A11y & i18n (10) | UI files + translation files only |

All agents also receive: changed file list, Project Profile, CLAUDE.md rules, Phase 1 gate results, and PR description if applicable. (Snoozed/`wontfix` findings are filtered later in Phase 2.5 from `stateFile` — agents do not need the suppression list.)

## Agents to spawn

| # | Agent | Persona | Spawn condition |
|---|-------|---------|-----------------|
| 1 | Standards & Clarity | `01-standards.md` | Always |
| 2 | Bugs & Security | `02-bugs-security.md` | Always |
| 3 | DRY & Code Smells | `03-dry-smells.md` | Always |
| 4 | Consistency & History | `04-consistency-history.md` | Always |
| 5 | Simplification | `05-simplification.md` | Always |
| 6 | Security Deep Dive | `06-security-deep-dive.md` | Files match auth/crypto/API/infra patterns |
| 7 | Performance | `07-performance.md` | Always |
| 8 | Test Quality | `08-test-quality.md` | Test files in diff OR new public functions |
| 9 | API & Contract | `09-api-contract.md` | Public exports / schemas / routes / migrations changed |
| 10 | A11y & i18n | `10-a11y-i18n.md` | UI / translation files changed |

Apply `extraAgents` and `skipAgents` from `.claude/review-all.json`.

Each agent returns findings with `root_cause_key` (used for cross-agent dedup).

## Chunking large slices

A single agent's diff slice can blow past the model context window on big refactors. Before spawning, measure the slice:

- `slice_files = number of files in the slice`
- `slice_bytes = byte size of the slice (diff text + any related files attached)`

If `slice_files > chunkMaxFiles` (default `40`) OR `slice_bytes > chunkMaxBytes` (default `200000`):

1. Split the slice into N chunks, each respecting both limits. Prefer splitting on file boundaries; only split inside a file if a single file exceeds the byte limit.
2. Spawn the agent N times in parallel, each with: the persona + `_shared.md` + the chunk + `"chunk index i of N — only review the files in this chunk; do NOT speculate about omitted files"`.
3. Merge findings by `root_cause_key` before handing to Phase 2.5. Duplicate keys across chunks collapse into one, with `confirmed_by` listing the chunk indices that flagged it.

Both thresholds are configurable via `.claude/review-all.json` keys `chunkMaxFiles` and `chunkMaxBytes`. Set either to `0` to disable that limit.

Chunked agent status in the Phase 2.75 map: an agent is `returned` only when **all** of its chunks returned; any chunk failure follows the normal retry-once rule below.

## Timeouts & retry

- Spawn every Phase 2 agent with an explicit wall-clock budget. Default `agentTimeoutSeconds: 600`; override via `.claude/review-all.json`.
- If an agent exceeds its budget or returns malformed output, re-spawn it ONCE with the preamble: `"Previous run failed (<timeout|schema|empty>). Re-attempting with same inputs."`.
- After one retry, surrender — do not loop. Phase 2.75 will surface the missing agent in the report banner.
- Track per-agent status in an internal map: `pending | running | returned | failed`. Phase 2.75 reads this map.
