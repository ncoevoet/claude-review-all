---
name: review-all-shared-rules
description: Shared severity tiers, verification gate, quotas, and auto-drop rules included by every review-all agent prompt.
---

# Shared Rules (all review-all agents)

## Severity tiers

- **❌ CRITICAL** — Breaks functionality, exposes data, crashes systems, violates requirements
- **⚠️ IMPORTANT** — Missing error handling, unhandled edge cases, potential bugs
- **♻️ DEBT** — Code duplication, convention violations, refactoring needed within 6 months
- **🎨 SUGGESTED** — Measurable improvements only (complexity reduction by 3+, vulnerability class elimination, concrete perf gain). If you can't measure the improvement, don't suggest it.
- **❓ QUESTION** — Items requiring human judgment about requirements or intent

## Per-agent quota

To prevent any single agent from crowding the report:
- ❌ / ⚠️: no limit (real bugs always get reported)
- ♻️ DEBT: max 5 per agent
- 🎨 SUGGESTED: max 3 per agent
- ❓ QUESTION: max 2 per agent

If you exceed a quota, keep only the highest-impact items and drop the rest silently.

## Finding requirements

Every potential finding MUST be verified by reading the actual source code at the flagged location. Never report issues from pattern-matching or diff-reading alone. For each finding, include:
- `file:line` — exact location
- **Evidence** — the actual code or tool output proving the issue
- **Severity** — one of the 5 tiers above
- **Confidence** — VERIFIED (tool-confirmed), HIGH (source-confirmed), or MEDIUM (likely but unverified)
- **Root-cause key** — a stable string identifying the root cause, used for cross-agent dedup. Format: `<category>:<file>:<symbol>` (lowercase, kebab-case category, forward-slash file path, symbol name as in source). Categories are drawn from a fixed list — `missing-null-check`, `unbounded-loop`, `n-plus-one`, `injection`, `race-condition`, `resource-leak`, `unhandled-error`, `dead-code`, `duplicated-logic`, `bad-naming`, `bad-typing`, `api-break`, `missing-test`, `a11y`, `i18n`, `perf`, `security`, `style`. Use `other:<file>:<symbol>` if nothing fits. Examples: `missing-null-check:src/users/UserService.ts:load`, `n-plus-one:app/orders/list.py:OrderListView`. Same key = same issue, even on different lines. The verifier normalizes minor variations.

## 3-question gate

Before reporting ANY finding, answer YES to all three:
1. Can you trace the execution path showing incorrect behavior or the concrete problem?
2. Is the concern NOT already addressed by existing safeguards (middleware, validators, framework, upstream checks)?
3. Are you certain about the framework semantics and API contracts involved?

If any answer is NO, drop the finding silently.

## Auto-drop list

Never report findings that are:
- Pre-existing (not introduced in this diff)
- Pedantic (wouldn't concern an experienced engineer)
- Linter-catchable (existing linter/formatter will catch it)
- Generic (no specific traceable problem)
- Explicitly silenced (pragma, `// eslint-disable`, `# noqa` with documented reason)
- Handled elsewhere (middleware, validators, framework guarantees)
- In generated files (unless manually edited)
- Automated dependency updates with all CI passing
- Listed in `.claude/review-all/snooze.json` with non-expired snooze

## Established convention check

For any pattern you're about to flag, check if it exists in 5+ unchanged files. If yes → established convention, do NOT flag it.

## CodeGraph usage

If your environment exposes `codegraph_*` tools (typically when `.codegraph/` exists *and* the codegraph MCP server is wired in), prefer them over grep for cross-file analysis:
- `codegraph_callers` — find what calls a function (impact analysis)
- `codegraph_callees` — find what a function calls
- `codegraph_impact` — see what's affected by changing a symbol
- `codegraph_search` — find symbols by name

If the tools are not available (no MCP, or tool call fails), fall back to `Grep` / `git grep`. Do not abort the review just because codegraph is missing. This matters most for the DRY, Bugs, Security, and API/Contract agents.
