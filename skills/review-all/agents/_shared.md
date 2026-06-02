---
name: review-all-shared-rules
description: Shared severity tiers, verification gate, quotas, and auto-drop rules included by every review-all agent prompt.
---

# Shared Rules (all review-all agents)

## Severity tiers

- **🔴 CRITICAL** — Breaks functionality, exposes data, crashes systems, violates requirements
- **🟠 IMPORTANT** — Missing error handling, unhandled edge cases, potential bugs
- **🟡 DEBT** — Code duplication, convention violations, refactoring needed within 6 months
- **🔵 SUGGESTED** — Measurable improvements only (complexity reduction by 3+, vulnerability class elimination, concrete perf gain). If you can't measure the improvement, don't suggest it.
- **⚪ QUESTION** — Items requiring human judgment about requirements or intent

## Finding-stage stance: coverage over filtering

Your job at this stage is **coverage, not curation**. A separate Phase 2.5 stage (dedupe → adversarial verifier → global caps) is the precision filter — it independently re-reads every finding and silently drops false positives, so you do not pre-filter for confidence or importance here.

Report every issue you can trace, including ones you are uncertain about, as long as it clears the 3-question traceability gate below. Attach an honest **Confidence** (VERIFIED / HIGH / MEDIUM) and **Severity** so the downstream filter can rank and cut — do **not** silently drop a traceable 🔴/🟠 because you suspect it might be intentional or below some importance bar. Surfacing a real bug the verifier later trims beats dropping it here, where nothing can recover it.

This division (broad finding → hostile verify) is the whole design. Models told to "be conservative" or "only report important issues" tend to investigate just as deeply but report fewer findings — silently lowering recall. Push that judgment to the verifier instead.

The per-agent quotas below still apply to the noise tiers (🟡/🔵/⚪) to keep the report focused; 🔴/🟠 are never quota-capped.

## Per-agent quota

To prevent any single agent from crowding the report:
- 🔴 / 🟠: no limit (real bugs always get reported)
- 🟡 DEBT: max ${quota.debt} per agent
- 🔵 SUGGESTED: max ${quota.suggested} per agent
- ⚪ QUESTION: max ${quota.question} per agent

If you exceed a quota, keep only the highest-impact items and drop the rest silently. A quota of `0` means **no limit** for that tier — report every qualifying finding.

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

If any answer is NO, drop the finding silently — with one carve-out: if the finding is 🔴/🟠 and only question 3 is uncertain (you cannot fully confirm framework semantics), do not drop it; report it at MEDIUM confidence and let the Phase 2.5 verifier adjudicate. Questions 1 (traceability) and 2 (not already safeguarded) stay hard gates for all severities — a finding you cannot trace, or that is already handled, is noise at any severity.

## Auto-drop list

Never report findings that are:
- Pre-existing (not introduced in this diff) — **but see security-audit escape below**
- Pedantic (wouldn't concern an experienced engineer)
- Linter-catchable (existing linter/formatter will catch it)
- Generic (no specific traceable problem)
- Explicitly silenced (pragma, `// eslint-disable`, `# noqa` with documented reason)
- Handled elsewhere (middleware, validators, framework guarantees)
- Defensive code for states that cannot occur on any reachable path — validation belongs at real system boundaries (where untrusted input enters), not for values the code's own invariants already guarantee. Flag a *missing* check only where untrusted data actually arrives; do not flag missing handling for impossible states, and never rank unrequested hardening above 🔵 SUGGESTED. (This is a Question-1 failure — you cannot trace incorrect behavior from a state that cannot arise.)
- In generated files (unless manually edited)
- Automated dependency updates with all CI passing
- Marked `snoozed` (non-expired) or `wontfix` in `stateFile` (`.claude/review-all/state.json`) — see `references/state-file.md`. (Filtering happens centrally in Phase 2.5 Step 2.5.0; agents don't need to re-check.)

### Security-audit escape on pre-existing 🔴/🟠

The "pre-existing" rule above silently kills real findings when the review target IS the audit (security sweeps, large feature branches, follow-up commits where the in-diff code references unchanged-but-vulnerable code). Treat a finding as **in-scope even if the flagged lines are unchanged** when ALL of:

1. Severity would be 🔴 CRITICAL or 🟠 IMPORTANT.
2. The file matches an auth/crypto/API/network/IPC/build-pipeline pattern (the same set that triggers Security Deep Dive — see persona `06`), OR the agent is `02-bugs-security.md` / `06-security-deep-dive.md`.
3. The review target signals an audit, i.e. ANY of:
   - resolved range covers ≥ 10 commits, OR
   - resolved range was `vs <branch>` where N (commits between branches) > 20, OR
   - PR title / description / labels contain `security`, `audit`, `CVE`, or `RM-` (audit-finding code), OR
   - the in-diff code calls into, imports, or modifies a symbol on the pre-existing vulnerable line (semantic adjacency — agent must trace the path).

Report these as normal findings, tagged `pre_existing: true` in the JSON output. The verifier (`verifier.md`) accepts them without penalty when the escape conditions are met. Do NOT use this escape for 🟡 DEBT or 🔵 SUGGESTED — those remain auto-dropped when pre-existing.

## Established convention check

For any pattern you're about to flag, check if it exists in 5+ unchanged files. If yes → established convention, do NOT flag it.

## CodeGraph usage

The orchestrator resolves codegraph MCP tool names at runtime (see SKILL.md Step 0.7) and passes a `codegraphTools` map to each agent. Reference tools symbolically:

- `${codegraphTools.callers}` — find what calls a function (impact analysis)
- `${codegraphTools.callees}` — find what a function calls
- `${codegraphTools.impact}` — see what's affected by changing a symbol
- `${codegraphTools.search}` — find symbols by name

The orchestrator substitutes each `${codegraphTools.X}` placeholder with the host-qualified tool name (e.g. `codegraph:codegraph_callers` or `mcp__codegraph__codegraph_callers`) before spawning you. If `codegraphTools` is empty, those tools are unavailable for this run — fall back to `Grep` / `git grep` and do not abort the review. This matters most for the DRY, Bugs, Security, and API/Contract agents.
