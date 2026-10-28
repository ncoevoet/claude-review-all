# Phase 4 — Post-Report Choices

Loaded by `/review-all` Phase 4. Presents the one-step post-report menu, the free-text actions reachable through its `Other` field, the guided triage loop, the apply-fixes routine, the loop, and guardrails.

**Mandatory menu gate.** Presenting this menu is the closing step of every review, not an optional extra — see the gate in SKILL.md Phase 4. After printing the Phase 3 report you MUST present the primary menu via `AskUserQuestion` **in the same turn**. The ONLY case that skips it: every report section reads "None found." AND there is no appendix AND no 🔬 unverified findings (nothing scoring 50–74, nothing awaiting observation) — then state `✅ No actionable findings — nothing to triage.` and stop. Ending the turn on the report without the menu is a silent failure (the #1 Phase 4 failure mode after a long `effort: high` review).

**Report-before-menu ordering (hard rule).** Emit the COMPLETE Phase 3 report as user-visible text FIRST; the `AskUserQuestion` menu call must be the IMMEDIATELY NEXT action — zero tool calls between the report text and the menu call (no Write, no Bash, no export). Text emitted between tool calls may not render for the user, and the interactive menu pins to the prompt — any tool call in between makes the menu appear before (or without) the report, leaving the user to choose blind. Artifact writes (saving the report, exports) happen only after a menu choice. The menu's question text MUST carry the verdict summary (`Review done — N must-fix: X 🔴, Y 🟠 (+Z optional). Full report above ↑`) so the choice is decidable even when the report has scrolled off-screen.

## Table of Contents

- [Primary menu — one step](#primary-menu--one-step)
- [Other: expression grammar](#other-expression-grammar)
- [Free-text actions](#free-text-actions)
- [Triage one-by-one](#triage-one-by-one)
- [The three follow-up actions](#the-three-follow-up-actions)
- [Apply-fixes routine](#apply-fixes-routine)
- [Fix Results](#fix-results)
- [Loop](#loop)
- [Auto-delta after successful apply-fixes](#auto-delta-after-successful-apply-fixes)
- [Guardrails](#guardrails)

Every finding in the report MUST be prefixed with its number (Finding 1, Finding 2, …) — main sections AND appendix. The numbered list is what the menu labels, the `Other` expression (`#N` / `N` / `N-M`) and the per-finding actions select by.

## Primary menu — one step

Present a single-select menu via `AskUserQuestion` with at most four options whose labels name the **concrete finding IDs** the choice acts on. One click fixes: there is no scope sub-menu. (Observed usage: the fix path won ~2/3 of primary choices, the broadest scope won every scope sub-menu, and the extended actions menu was never opened — so the fix scope goes on the first screen and everything else moves to free text.)

**Assembly algorithm** (deterministic):
1. `fixable = 🔴 + 🟠 + 🟡`; `mustfix = 🔴 + 🟠`. Findings are numbered in section order, so each tier set is a contiguous run of IDs — always write it in range form (`#1–34`), never as a list, so labels stay short on large reports.
2. If `fixable > 0`, options in this order:
   1. `Fix <tiers present> (#a–b)` — e.g. `Fix 🟠 + 🟡 (#1–10)`. Always **Recommended**, including when only 🟡 exists (deliberate: the broadest fixable scope is what users pick).
   2. `Fix must-fix only (#a–b)` — only when `mustfix > 0` AND 🟡 > 0 (otherwise it would duplicate option 1).
   3. `Triage one-by-one` — only when `fixable ≥ 2`.
   4. `Done`.
3. If `fixable == 0` and ≥1 🔵 → [`Fix suggested (#a–b)`, `Done`].
4. If `fixable == 0`, no 🔵, but ⚪ / appendix / 🔬 findings exist → [`Ask about a finding`, `Done`] (⚪ and appendix are never auto-applied, so there is nothing to fix; every menu has at least 2 options).
5. If every section says "None found." AND no appendix AND no 🔬 unverified findings → skip Phase 4 entirely (per the mandatory-menu gate's one exception).

**Question text** = the verdict summary, then one hint line for the `Other` field:
`Other: an expression (e.g. "I #7 #9") or a request — export, ticket #3, tests #2, ask #4, snooze #5, post to PR, re-run.`

`AskUserQuestion` caps options at 4 — never build a picker with one option per finding (crashes with `InputValidationError: array too_big` whenever a report has >4 findings; observed twice in real sessions). Never auto-bundle findings into ad-hoc groups (`"All debt + suggested (4-8)"`) beyond the tier ranges above — anything finer goes through the `Other` expression.

## Other: expression grammar

When the `Other` answer parses as an expression, it is a fix scope — apply the UNION through the [apply-fixes routine](#apply-fixes-routine):

```
C  I  D  S        severity letters (case-insensitive)
                  C = 🔴 Critical   I = 🟠 Important   D = 🟡 Debt   S = 🔵 Suggested
#11   11          single finding (# prefix optional)
1-7   #3-#9       inclusive range (# optional on either side)
```

Separators: comma, whitespace, or the word `and` — interchangeable. Result = UNION of every matched finding ID; duplicates collapse. Severity letters expand to all in-report findings of that tier. Prefixed with `fix` it still parses (`fix I #11`).

Examples:
- `I D #11`    → all 🟠 + all 🟡 + Finding 11
- `1-7, 11`   → Findings 1..7 plus 11
- `C #14-#16` → all 🔴 + Findings 14, 15, 16

When the `Other` answer does not parse as an expression, match it against the [free-text actions](#free-text-actions). If it matches neither, answer it as a question about the review and re-present the menu.

## Free-text actions

No menu lists these — the user names them in `Other` (or in a later message). A finding number is required where the action targets one finding; if it is missing or doesn't exist, ask for it in plain text. Each action returns to the primary menu ([Loop](#loop)).

| Request | Action |
|---------|--------|
| **Export findings (JSON + SARIF)** — `export` | Run `scripts/export-findings.py` → write `review-<iso>.json` + `review-<iso>.sarif` to `outputDir` for CI ingestion |
| **Create a ticket** — `ticket #N` (or several IDs) | [Create a ticket/issue from a finding](#create-a-ticketissue-from-a-finding), confirmation-gated |
| **Generate tests** — `tests #N` | [Generate tests for a finding](#generate-tests-for-a-finding), confirmation-gated |
| **Ask a question** — `ask #N <question>` | [Ask a follow-up question about a finding](#ask-a-follow-up-question-about-a-finding) |
| **Deep-dive** — `deep-dive #N` | Spawn focused agent (`subagent_type: general-purpose`, `model: opus`) that returns full callers/callees, root-cause analysis, 2-3 fix strategies with tradeoffs |
| **Post to PR** — `post to PR` | Only when a PR exists for the current branch (probe `gh pr view`): comment the report with `gh pr comment` — show the body and confirm first |
| **Snooze** — `snooze #N` | Ask reason + expiry → upsert in `stateFile` with `status: snoozed`, `snoozed_until: <expiry>` (see `state-file.md`) |
| **Wontfix** — `wontfix #N` | Ask reason → upsert in `stateFile` with `status: wontfix` and current `code_hash` (see `state-file.md`) |
| **Re-run review on the fixed code** — `re-run` | Only after a fix step succeeded: re-execute Phase 1 + 2 + 2.5 + 3 on the now-modified tree |
| **Fix by agent** — `fix <agent-id>` | Apply-fixes routine over every 🔴/🟠/🟡/🔵 finding raised by that agent (🔵 alone: the `S` expression) |
| Save report — `save` | Write to `outputDir/review-<iso-timestamp>.md` |
| Generate patch — `patch` | Unified diff of the fixes, not applied — user runs `git apply` later |
| Draft commit / PR description — `draft PR` | Synthesize a commit/PR body covering the changes and how findings were addressed |
| Explain — `explain #N` | Plain-language explanation of one finding |
| Schedule — `schedule` | Invoke the `/schedule` skill — recurring or one-shot re-review |

When one answer names several actions, run them in this order: fixes → generate tests → read-only synthesis (deep-dive, ask, patch, draft, explain) → publication (save, post to PR, ticket, schedule — they share the confirmation gate) → state writes (snooze, wontfix) → re-run last.

## Triage one-by-one

Reached via Primary → **Triage one-by-one**. A guided loop that walks each finding and offers a per-finding micro-menu, so the user decides finding-by-finding instead of by batch scope.

**Iteration set + order:**
1. `queue = [🔴 in file:line order] + [🟠 in file:line order]` — must-fix first.
2. After the must-fix queue is exhausted (or immediately, when there is no must-fix), ask ONCE (single-select, 2 options): `"Continue into 🟡 Debt (N findings)?"` / `"Done with triage"`. If continue → append 🟡 in file:line order. Never auto-include 🟡 (keeps the default pass short).
3. Never include 🔵/⚪ in triage (⚪ is never auto-actionable; 🔵 is fixed via `Fix suggested` or the `S` expression).

**Per-finding micro-menu** — `AskUserQuestion` caps at 4, so the verbs split over two rounds (do NOT flatten them into one >4-option call — the documented `array too_big` crash):

- **Round 1** (per finding) — single-select, exactly 4 options:
  - `Fix this` (Recommended) — run the [apply-fixes routine](#apply-fixes-routine) for THIS finding only (mandatory Read-before-Edit, drift handling, record outcome), honoring all guardrails. Then advance to the next finding.
  - `Skip → next` — advance with no action.
  - `Dismiss…` — open Round 2.
  - `Stop triage` — end the pass now (findings not yet visited are left untouched).
  - The question text carries the `Other` hint: `ask`, `ticket`, `tests` for THIS finding run the matching action, then return to THIS finding's Round 1 (so the user can ask, then still fix).
- **Round 2 (`Dismiss…`)** — single-select, ≤4: `Snooze` (ask reason + expiry → `state.json` upsert `status: snoozed`, `snoozed_until`) / `Wontfix` (ask reason → `state.json` upsert `status: wontfix` + current `code_hash`) / `Back`. Both reuse the exact `state-file.md` upsert semantics — no new schema. Snooze/Wontfix advance to the next finding; `Back` returns to THIS finding's Round 1.

**Termination & safety:** the queue is finite; each finding is visited at most once in Round 1; only `Fix this` / `Skip → next` / a dismissal advance, `Stop triage` and `Done with triage` exit — so no finding is re-queued and the loop always terminates. After the pass, print a compact [Fix Results](#fix-results) table for the findings that got `Fix this`. If ≥1 fix applied AND all post-fix gates pass → run the [auto-delta](#auto-delta-after-successful-apply-fixes) once, then re-present the primary menu.

## The three follow-up actions

**Every Phase 4 spawn names its model, exactly as the Phase 2 axes do** (`SKILL.md` → *Spawn contract*). An omitted `model` silently falls back to the session's own tier, so the same menu action costs whatever the user happened to start the review on. The tier follows what the agent has to do: Deep-dive is root-cause work → `opus`; Ask-a-question reads the evidence it is handed and reports → `sonnet`; the test generator writes code from a spec plus sibling exemplars → `sonnet`.

### Ask a follow-up question about a finding
Builds on Deep-dive but is driven by the user's specific question (keep both: Deep-dive is canned root-cause + strategies; Ask answers a free-text question).
1. Prompt for the finding number (validate it exists) + a free-text question. No question → default `"Why does this happen and how would you fix it?"`.
2. Gather, read-only: the finding's frozen evidence + suggested fix; **re-Read the full enclosing function** at `file_line` (not just the evidence line — it may have drifted); the file's diff hunk; if `toolchain.codegraphTools` is non-empty, resolved `${codegraphTools.callers}` / `${codegraphTools.callees}`; a Grep for the symbol's tests scoped by `toolchain.testPattern.suffix`.
3. Spawn ONE agent (`subagent_type: general-purpose`, `model: sonnet`) with an XML-tagged prompt (`<finding>`, `<question>`, `<enclosing_function>`, `<diff_hunk>`, `<callers_callees>`, `<sibling_tests>`): answer the question, then give 1–2 fix approaches with tradeoffs. The agent has NO Edit/Write — it never changes code.
4. Print the answer; return to the caller (primary menu; from Triage → that finding's Round 1). It is NOT a multi-turn chat loop.

### Generate tests for a finding
A deliberate, **confirmed** exception to the "never create new files as part of a fix" guardrail — that rule stays in force for AUTO-fixes; this is a separate, user-initiated, confirmation-gated action. Also auto-offered after a clean apply-fixes/auto-delta.
1. Prompt for the finding number (validate). Resolve the source file from `file_line`.
2. Read `toolchain.testPattern` (from `scripts/test-pattern-probe.sh`: framework + suffix + layout). Compute the conventional test path:
   - co-located → sibling `<basename><suffix>`;
   - separate-tree → mirror under `tests/`/`test/` with `<suffix>`;
   - **DEGRADED** (`framework == "unknown"` OR `suffix == ""`): do NOT guess a framework. Tell the user the convention couldn't be detected, show the finding + a language-appropriate skeleton, and offer "write to <best-guess path>" vs "show only". Never fabricate a jest/pytest setup the repo doesn't use (project-agnostic principle).
3. Glob the computed path to check existence (append vs create). Read it + 1–2 sibling tests for style, and pass them to the generator as exemplars.
4. Spawn a generator agent (`subagent_type: general-purpose`, `model: sonnet`; read-only inputs; returns test code as text — does NOT write).
5. **SHOW the proposed path + full test code, then CONFIRM before any Write** (`AskUserQuestion`: `Write to <path>` / `Append to existing <path>` / `Show only` / `Cancel`). Only an explicit write choice triggers `Write` (append case: Read-then-Edit — Read-before-Edit still applies).
6. Optionally run the SCOPED test command (`<test_cmd> <path>` via `timeout`) if `toolchain.commands.test` exists.
7. If tests FAIL: show the failure and STOP — do NOT auto-fix the test or the source (consistent with never-auto-rollback; the user decides).
8. Return to the caller.

### Create a ticket/issue from a finding
Portable by design — review-all is project-agnostic, so it never hardcodes a tracker-specific request shape. Confirmation-gated.
1. **Build the issue body** (same shape regardless of destination): title = the finding's failure-mode line; body = `Severity` + `file:line` + Evidence + Suggested fix + footer `Generated by /review-all`.
2. **MANDATORY confirmation preview** before ANY external write — show the exact title + body + destination (same gate as Post-to-GitHub-PR).
3. **Destination priority:**
   - **Tier 1 — GitHub:** `gh` available AND a GitHub repo (probe `gh pr view` / remote = github.com) → `gh issue create --title … --body …` (after confirmation). Uses the `gh issue create` permission in `allowed-tools`.
   - **Tier 2 — host tracker:** if an installed issue-tracker skill (e.g. `gitlab`/`atlassian`) or tracker env is present, deeper wiring can DELEGATE to that skill/CLI. This is a documented extension point — do NOT embed any tracker-specific curl/credentials in this skill (would break portability + the anonymization gate).
   - **Tier 3 — fallback (default, universal):** write the formatted markdown to `outputDir/issue-<finding>-<iso-timestamp>.md` (or show it inline if declined) for manual filing. No new permission needed (Write is already allowed); works in every project — use it whenever Tier 1/2 don't cleanly apply.
4. **Batch:** multiple findings → ONE issue per finding (separately triageable), never a merged blob; confirm the batch count first. In Tier 3, one markdown file per finding.
5. Return to the caller.

## Apply-fixes routine

Reached via the primary menu's fix options, an `Other` expression, `fix <agent-id>`, and Triage Round 1 (`Fix this`, single finding). The scope→finding mapping:

| Scope source | Severity set |
|--------------|--------------|
| `Fix <tiers> (#a–b)` (Recommended) | every 🔴 + 🟠 + 🟡 |
| `Fix must-fix only (#a–b)` | 🔴 + 🟠 |
| `Fix suggested (#a–b)` | 🔵 |
| `Other` expression (C/I/D/S + #IDs) | UNION of expanded severity letters and explicit IDs/ranges (see grammar above) |
| `fix <agent-id>` | every 🔴/🟠/🟡/🔵 finding raised by that agent |
| Triage `Fix this` | the single finding selected |

For each finding in the chosen scope (file-then-line order):
1. **Mandatory — never skip**: `Read` the target file before `Edit`. The Edit tool rejects writes without a prior Read in the same session, so skipping guarantees `<tool_use_error>File has not been read yet</tool_use_error>`. Re-Read for every fix even on adjacent lines and even if the file was Read earlier in the same apply batch — earlier Edits invalidate the cached read state.
2. Apply the fix using `Edit` — use the "Fix" text from the finding.
3. If the fix can't be a single targeted Edit (cross-file, new file, architectural) → record as `manual follow-up`, do NOT attempt.
4. If `Edit` returns `String to replace not found` → record as `manual follow-up: code drifted since review-time` and move on. Do NOT retry on a guessed string — the evidence string is frozen at review-time, the file may have moved on (especially during multi-fix batches where earlier fixes shifted line numbers).
5. Record per-finding outcome: `applied` / `manual follow-up` / `skipped (code changed)` / `guardrail-blocked`.

After all edits, re-run Phase 1 gates against the modified tree, then print this block under the `## Fix Results` heading:

## Fix Results

```
- Scope: {chosen}
- Applied: N | Manual follow-up: M | Skipped: K | Guardrail-blocked: G
- Post-fix gates: Typecheck ✅/❌, Lint ✅/❌, Tests ✅/❌

| ID  | Sev | Outcome             | Why                                          |
|-----|-----|---------------------|----------------------------------------------|
| F1  | 🔴  | applied             |                                              |
| F25 | 🟡  | manual follow-up    | cross-file: extract helper to new file       |
| F31 | 🟠  | skipped             | flagged lines no longer match (hash diverged)|
| F44 | 🔵  | guardrail-blocked   | finding scope=suggested; not in chosen scope |
```

Outcome values are exhaustive: `applied` | `manual follow-up` | `skipped` | `guardrail-blocked`. Every finding in the chosen scope appears in the table — silent omission was the #1 user-friction signal in real sessions ("why F25 not done?").

If a previously-passing gate now fails: list failing output, suggest `git diff` / `git checkout --` rollback. **Never auto-rollback** — user decides.

## Loop

After any non-terminal choice — a completed fix, a finished triage pass, or any free-text action — re-present the primary menu rebuilt from the updated state: fixed, snoozed and wontfixed findings drop out of the ID ranges, and after a successful fix the `Other` hint names `re-run` (Re-run review on the fixed code). Continue until the user picks **Done**.

## Auto-delta after successful apply-fixes

When apply-fixes (a primary fix option, an `Other` expression, `fix <agent-id>`, or Triage) completes AND **all** post-fix gates pass (Typecheck ✅ + Lint ✅ + Tests ✅, ignoring any gate that was N/A or SKIP before fixes), the orchestrator runs a scoped **delta review** before re-presenting the menu:

- Scope = the just-edited files only (the actual fix target set, not the original review target).
- Phases run: 1 → 2 (parallel agents on the narrow slice) → 2.5 (verify) → 3 (delta report).
- Delta report appended to the existing report under a new `## Post-fix delta` section. No new file written.
- **Also auto-offer "Generate tests for a finding"** for any just-fixed finding whose source file gained no co-located test — surface it as a one-line suggestion before re-opening the menu.
- The primary menu then re-opens; its `Other` hint now offers `re-run` (Re-run review on the fixed code) for the full target if the user wants the broader pass.

**Do NOT trigger auto-delta** when:
- Any post-fix gate failed or timed out → surface the gate output, let user decide (rollback, manually fix, etc.).
- Zero fixes applied (all manual follow-up / skipped) → no edits to verify.
- `applied + manual-follow-up == 0` → nothing to re-review.

Rationale: in observed sessions user almost always picked "Re-run review on fixed code" after a clean apply. Auto-delta cuts one menu round; gate-pass gating means it never surprises user with a destabilized tree.

## Guardrails

- **Never auto-apply** ⚪ QUESTION findings.
- **Never auto-apply** appendix findings (50–74 confidence).
- **Never create new files** as part of an AUTO-fix (missing-spec → manual follow-up). The sole sanctioned new-file write is **Generate tests for a finding**, and only after the user explicitly confirms the path + content.
- **Ask-a-question agents are read-only** — no Edit/Write in their toolset; they explain and propose, never change code.
- **Never touch files outside the review target's changed-file set** unless a finding explicitly names that file and severity is 🔴 or 🟠.
- **Never write externally without confirmation** — Post to PR, Create ticket (Tier 1/2), and any tracker write show the exact body and confirm first. Create-ticket's Tier-3 markdown fallback is the default whenever GitHub+`gh` isn't cleanly detected.
- **No tracker-specific curl in the skill** — Create-ticket Tier 2 is a documented delegation hook, never a hardcoded request shape (preserves portability + the anonymization gate).
- If chosen scope yields zero applicable findings after guardrails, report "nothing to auto-apply" and return to menu.
