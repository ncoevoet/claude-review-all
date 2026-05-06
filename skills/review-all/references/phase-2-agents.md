# Phase 2 — Agent Inputs and Spawn Conditions

Loaded by `/review-all` Phase 2. Lists every parallel agent, the diff slice it receives, and when to spawn it.

Each agent's persona lives at `agents/<id>.md` (sibling of `references/`, both inside the skill directory). Before spawning, Read its persona and `_shared.md` (same dir), and pass them concatenated as the agent's prompt.

## Agent inputs (per agent)

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

All agents also receive: changed file list, Project Profile, CLAUDE.md rules, Phase 1 gate results, the snooze list (`snoozeFile`), and PR description if applicable.

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
