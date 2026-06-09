# Phase 4 — Post-Report Choices

Loaded by `/review-all` Phase 4. Presents the post-report menu (three modes), the guided triage loop, the three follow-up actions, the apply-fixes sub-menu, the loop, and guardrails.

**Mandatory menu gate.** Presenting this menu is the closing step of every review, not an optional extra — see the gate in SKILL.md Phase 4. After printing the Phase 3 report you MUST present the primary menu via `AskUserQuestion` **in the same turn**. The ONLY case that skips it: every report section reads "None found." AND there is no appendix — then state `✅ No actionable findings — nothing to triage.` and stop. Ending the turn on the report without the menu is a silent failure (the #1 Phase 4 failure mode after a long `effort: high` review).

**Report-before-menu ordering (hard rule).** Emit the COMPLETE Phase 3 report as user-visible text FIRST; the `AskUserQuestion` menu call must be the IMMEDIATELY NEXT action — zero tool calls between the report text and the menu call (no Write, no Bash, no export). Text emitted between tool calls may not render for the user, and the interactive menu pins to the prompt — any tool call in between makes the menu appear before (or without) the report, leaving the user to choose blind. Artifact writes (saving the report, exports) happen only after a menu choice. The menu's question text MUST carry the verdict summary (`Review done — N must-fix: X 🔴, Y 🟠 (+Z optional). Full report above ↑`) so the choice is decidable even when the report has scrolled off-screen.

## Table of Contents

- [Primary menu — three modes](#primary-menu--three-modes)
- [Mode A — Fix by scope…](#mode-a--fix-by-scope)
- [Mode B — Triage one-by-one](#mode-b--triage-one-by-one)
- [Mode C — More actions… (extended, multi-select)](#mode-c--more-actions-extended-multi-select)
- [The three follow-up actions](#the-three-follow-up-actions)
- [Apply-fixes sub-menu](#apply-fixes-sub-menu)
- [Fix Results](#fix-results)
- [Loop](#loop)
- [Auto-delta after successful apply-fixes](#auto-delta-after-successful-apply-fixes)
- [Guardrails](#guardrails)

Every finding in the report MUST be prefixed with its number (Finding 1, Finding 2, …) — main sections AND appendix. The numbered list is what **Custom** references via `#N` / `N` / `N-M`, and what the per-finding actions (Triage, Ask, Generate tests, Create ticket) select by.

## Primary menu — three modes

Present a single-select menu via `AskUserQuestion` with at most four options, built dynamically. The four are *modes*, not fix-scopes — fixing is one mode among several so the other actions stay discoverable (the previous fix-only primary menu buried them).

| Mode | Show when | Opens |
|------|-----------|-------|
| **Fix by scope…** | ≥1 fixable finding (🔴/🟠/🟡) | the fix-scope selector below (Fix critical / +important / +debt / Custom grammar) |
| **Triage one-by-one** | ≥1 fixable finding (🔴/🟠/🟡) | the guided per-finding loop (Mode B) |
| **More actions…** | always | the extended multi-select menu (Mode C) |
| **Skip / done** | always | terminate Phase 4 |

**Assembly algorithm** (deterministic):
1. `fixable = (#🔴) + (#🟠) + (#🟡)`.
2. If `fixable > 0`: options = [Fix by scope…, Triage one-by-one, More actions…, Skip / done] (exactly 4 — cap-safe). Mark **Fix by scope…** Recommended when any 🔴 exists, else mark **Triage one-by-one** Recommended.
3. If `fixable == 0` but ≥1 🔵/⚪ or an appendix exists: drop both fix modes; options = [More actions…, Skip / done], **leading with More actions…** (this is the discoverability path when only suggestions/questions exist — 🔵 still fix via Mode C → "Apply fixes (alternate scopes)").
4. If every section says "None found." AND no appendix → skip Phase 4 entirely (per the mandatory-menu gate's one exception).

## Mode A — Fix by scope…

Reached via Primary → **Fix by scope…**. This is the former primary fix-scope menu, now one level down. Present the scopes as a single-select (`AskUserQuestion`), only the scopes with ≥1 matching finding:

| Label | When to offer | Action |
|-------|---------------|--------|
| **Fix critical (Recommended)** | At least one 🔴 finding | Apply 🔴 findings |
| **Fix critical + important** | At least one 🔴 or 🟠 finding | Apply 🔴 + 🟠 findings |
| **Fix critical + important + debt** | At least one 🔴/🟠/🟡 finding | Apply 🔴 + 🟠 + 🟡 findings |
| **Custom (C/I/D/S + #IDs)** | Any finding exists | Prompt for a free-text expression mixing severity letters and finding IDs (grammar below) → apply the UNION |

The chosen scope feeds the [apply-fixes sub-menu](#apply-fixes-sub-menu) (same routine for all scopes). Additional scopes (Fix all 🔵, Fix by agent) live in Mode C under **Apply fixes (alternate scopes)**.

### Custom expression grammar

```
C  I  D  S        severity letters (case-insensitive)
                  C = 🔴 Critical   I = 🟠 Important   D = 🟡 Debt   S = 🔵 Suggested
#11   11          single finding (# prefix optional)
1-7   #3-#9       inclusive range (# optional on either side)
```

Separators: comma, whitespace, or the word `and` — interchangeable. Result = UNION of every matched finding ID; duplicates collapse. Severity letters expand to all in-report findings of that tier.

Examples:
- `I D #11`    → all 🟠 + all 🟡 + Finding 11
- `1-7, 11`   → Findings 1..7 plus 11
- `C #14-#16` → all 🔴 + Findings 14, 15, 16

Numeric-only input (`1,3,7-9`) remains valid — strict superset of the old "Select by number" behavior.

### Custom prompt mechanism (hard rule)

`AskUserQuestion` caps options at 4. Do NOT build a picker with one option per finding when `Custom` is picked — crashes with `InputValidationError: array too_big` whenever a report has >4 findings (observed twice in real sessions).

Decision tree for the `Custom` follow-up:

1. **Total in-report findings ≤ 4** → AskUserQuestion with `multiSelect: true`, one option per finding (`"Finding N (Sev: title)"`). Cap-safe.
2. **Total > 4** → AskUserQuestion with `multiSelect: false` and exactly these 2 options:
   - `"Type expression (grammar shown above)"` — user picks this, types the expression via `Other` free-text.
   - `"Cancel — back to primary menu"`.
   Print the grammar block (the table above) as plain text in the question body for reference.
3. **Never auto-bundle** findings into ad-hoc groups like `"All debt + suggested (4-8)"` to dodge the cap — bundles obscure intent, the grammar handles it cleanly (`D S` for the same union).

## Mode B — Triage one-by-one

Reached via Primary → **Triage one-by-one**. A guided loop that walks each must-fix finding and offers a per-finding micro-menu, so the user decides finding-by-finding instead of by batch scope. (No surveyed CLI reviewer offers guided triage — this is the per-thread resolve flow brought to the terminal.)

**Iteration set + order:**
1. `queue = [🔴 in file:line order] + [🟠 in file:line order]` — must-fix first.
2. After the must-fix queue is exhausted, ask ONCE (single-select, 2 options): `"Continue into 🟡 Debt (N findings)?"` / `"Done with triage"`. If continue → append 🟡 in file:line order. Never auto-include 🟡 (keeps the default pass short).
3. Never include 🔵/⚪ in triage (⚪ is never auto-actionable; 🔵 stays in Mode A / Mode C).

**Per-finding micro-menu — the 6-actions-vs-4-cap resolution.** The desired verbs (Fix this / Ask a question / Create ticket / Snooze / Wontfix / Skip → next) number six, but `AskUserQuestion` caps at 4. Resolve with a shallow 1-hop drill-down so every call stays ≤4 — do NOT flatten these into one 6-option call (the documented `array too_big` crash):

- **Round 1** (per finding) — single-select, exactly 4 options:
  - `Fix this` (Recommended) — run the [apply-fixes per-finding routine](#apply-fixes-sub-menu) for THIS finding only (mandatory Read-before-Edit, drift handling, record outcome), honoring all guardrails. Then advance to the next finding.
  - `Skip → next` — advance with no action.
  - `Dismiss…` — open Round 2.
  - `More for this finding…` — open Round 3.
- **Round 2 (`Dismiss…`)** — single-select, ≤4: `Snooze` (ask reason + expiry → `state.json` upsert `status: snoozed`, `snoozed_until`) / `Wontfix` (ask reason → `state.json` upsert `status: wontfix` + current `code_hash`) / `Back`. Both reuse the exact `state-file.md` upsert semantics — no new schema. Then return to THIS finding's Round 1.
- **Round 3 (`More for this finding…`)** — single-select, ≤4: `Ask a question` / `Create ticket` (single-finding) / `Generate tests` (single-finding) / `Back`. Each runs the corresponding action below, then returns to THIS finding's Round 1 (so the user can ask, then still fix).

**Termination & safety:** the queue is finite; each finding is visited at most once in Round 1; Round 2/3 always return to the same finding's Round 1; only `Fix this` / `Skip → next` advance — so no finding is re-queued and the loop always terminates (also exits on `Done with triage` at the 🟡 gate). After the pass, print a compact [Fix Results](#fix-results) table for the findings that got `Fix this`. If ≥1 fix applied AND all post-fix gates pass → run the [auto-delta](#auto-delta-after-successful-apply-fixes) once, then re-present the PRIMARY three-mode menu.

## Mode C — More actions… (extended, multi-select)

Reached via Primary → **More actions…**. Present via `AskUserQuestion` with `multiSelect: true`. Always includes `Skip / done` (selecting it terminates the loop even if other options are also selected — `Skip / done` is dominant). Only include rows whose "When to offer" holds.

| Label | When to offer | Action |
|-------|---------------|--------|
| **Save full report to file** | Always | Write to `outputDir/review-<iso-timestamp>.md` |
| **Ask a follow-up question about a finding** | Any finding | Free-text Q about one finding, answered by a focused read-only agent (see below) |
| **Generate tests for a finding** | Any finding | Generate tests for the finding's scenario; confirm before writing (see below) |
| **Create a ticket/issue from a finding** | Any finding | Turn a finding into a tracker issue, confirmation-gated (see below) |
| **Export findings (JSON + SARIF)** | Any finding | Run `scripts/export-findings.py` → write `review-<iso>.json` + `review-<iso>.sarif` to `outputDir` for CI ingestion |
| **Deep-dive a finding** | Any finding | Spawn focused agent that returns full callers/callees, root-cause analysis, 2-3 fix strategies with tradeoffs |
| **Generate fix patches as a diff** | Any actionable finding | Produce a unified diff (no apply) — let user `git apply` later |
| **Draft commit / PR description** | Any actionable finding | Synthesize a commit/PR body covering the changes + how findings were addressed |
| **Post to GitHub PR** | A PR exists for the current branch (probe `gh pr view`) | Comment the report on the PR (uses `gh pr comment` — confirm body first) |
| **Schedule a re-review** | Always | Invoke `/schedule` skill — recurring or one-shot |
| **Snooze a finding** | Any finding | Ask for finding number + reason + expiry → upsert in `stateFile` with `status: snoozed`, `snoozed_until: <expiry>` (see `state-file.md`) |
| **Mark as wontfix** | Any finding | Ask for finding number + reason → upsert in `stateFile` with `status: wontfix` and current `code_hash` (see `state-file.md`) |
| **Re-run review on the fixed code** | Only after a Fix step succeeded | Re-execute Phase 1 + 2 + 2.5 + 3 on the now-modified tree |
| **Explain a finding** | Any finding | Plain-language explanation of one finding for the user |
| **Apply fixes (alternate scopes)** | At least one 🔴/🟠/🟡/🔵 finding exists | Full apply-fixes sub-menu incl. Fix all 🔵 / Fix by agent (use when Mode A's scopes aren't the desired set) |

**Composition rules** when multiple Mode C options are selected — run in this order (supersedes any earlier ordering):
1. **Apply fixes** (if chosen via "Apply fixes (alternate scopes)") — later actions may depend on the modified tree.
2. **Generate tests** (confirm + Write) — right after fixes so a later re-run/delta sees the written tests.
3. **Read-only synthesis**: Deep-dive / Ask a question / Generate fix patch / Draft commit-PR / Explain.
4. **Publication**: Save report / Post to GitHub PR / Create ticket / Schedule (Create-ticket sits with Post-to-PR — they share the confirmation gate).
5. **State writes**: Snooze / Wontfix.
6. **Re-run review on fixed code** — last.

## The three follow-up actions

### Ask a follow-up question about a finding
Builds on Deep-dive but is driven by the user's specific question (keep both: Deep-dive is canned root-cause + strategies; Ask answers a free-text question).
1. Prompt for the finding number (validate it exists) + a free-text question. No question → default `"Why does this happen and how would you fix it?"`.
2. Gather, read-only: the finding's frozen evidence + suggested fix; **re-Read the full enclosing function** at `file_line` (not just the evidence line — it may have drifted); the file's diff hunk; if `toolchain.codegraphTools` is non-empty, resolved `${codegraphTools.callers}` / `${codegraphTools.callees}`; a Grep for the symbol's tests scoped by `toolchain.testPattern.suffix`.
3. Spawn ONE agent (inherits the session tier) with an XML-tagged prompt (`<finding>`, `<question>`, `<enclosing_function>`, `<diff_hunk>`, `<callers_callees>`, `<sibling_tests>`): answer the question, then give 1–2 fix approaches with tradeoffs. The agent has NO Edit/Write — it never changes code.
4. Print the answer; return to the caller (Mode C → primary menu; Triage Round 3 → that finding's Round 1). It is NOT a multi-turn chat loop.

### Generate tests for a finding
A deliberate, **confirmed** exception to the "never create new files as part of a fix" guardrail — that rule stays in force for AUTO-fixes; this is a separate, user-initiated, confirmation-gated action. Also auto-offered after a clean apply-fixes/auto-delta.
1. Prompt for the finding number (validate). Resolve the source file from `file_line`.
2. Read `toolchain.testPattern` (from `scripts/test-pattern-probe.sh`: framework + suffix + layout). Compute the conventional test path:
   - co-located → sibling `<basename><suffix>`;
   - separate-tree → mirror under `tests/`/`test/` with `<suffix>`;
   - **DEGRADED** (`framework == "unknown"` OR `suffix == ""`): do NOT guess a framework. Tell the user the convention couldn't be detected, show the finding + a language-appropriate skeleton, and offer "write to <best-guess path>" vs "show only". Never fabricate a jest/pytest setup the repo doesn't use (project-agnostic principle).
3. Glob the computed path to check existence (append vs create). Read it + 1–2 sibling tests for style, and pass them to the generator as exemplars.
4. Spawn a generator agent (read-only inputs; returns test code as text — does NOT write).
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

## Apply-fixes sub-menu

Reached via Mode A (a chosen scope) and via Triage Round 1 (`Fix this`, single finding). The scope→severity mapping:

| Scope source | Severity set |
|--------------|--------------|
| Fix critical (Recommended) | 🔴 |
| Fix critical + important | 🔴 + 🟠 |
| Fix critical + important + debt | 🔴 + 🟠 + 🟡 |
| Custom (C/I/D/S + #IDs) | UNION of expanded severity letters and explicit IDs/ranges (see grammar above) |
| Triage `Fix this` | the single finding selected |

For each finding in the chosen scope (file-then-line order):
1. **Mandatory — never skip**: `Read` the target file before `Edit`. The Edit tool rejects writes without a prior Read in the same session, so skipping guarantees `<tool_use_error>File has not been read yet</tool_use_error>`. Re-Read for every fix even on adjacent lines and even if the file was Read earlier in the same apply batch — earlier Edits invalidate the cached read state.
2. Apply the fix using `Edit` — use the "Fix" text from the finding.
3. If the fix can't be a single targeted Edit (cross-file, new file, architectural) → record as `manual follow-up`, do NOT attempt.
4. If `Edit` returns `String to replace not found` → record as `manual follow-up: code drifted since review-time` and move on. Do NOT retry on a guessed string — the evidence string is frozen at review-time, the file may have moved on (especially during multi-fix batches where earlier fixes shifted line numbers).
5. Record per-finding outcome: `applied` / `manual follow-up` / `skipped (code changed)` / `guardrail-blocked`.

After all edits, re-run Phase 1 gates against the modified tree:

## Fix Results

```
## Fix Results
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

After any non-terminal choice — a completed fix, a finished triage pass, or any Mode C item — re-present the PRIMARY three-mode menu with updated state (e.g., "Re-run review on fixed code" becomes available in Mode C after fixes apply). Continue until the user picks **Skip / done**.

## Auto-delta after successful apply-fixes

When apply-fixes (Mode A, Triage, or Mode C alternate-scopes) completes AND **all** post-fix gates pass (Typecheck ✅ + Lint ✅ + Tests ✅, ignoring any gate that was N/A or SKIP before fixes), the orchestrator runs a scoped **delta review** before re-presenting the menu:

- Scope = the just-edited files only (the actual fix target set, not the original review target).
- Phases run: 1 → 2 (parallel agents on the narrow slice) → 2.5 (verify) → 3 (delta report).
- Delta report appended to the existing report under a new `## Post-fix delta` section. No new file written.
- **Also auto-offer "Generate tests for a finding"** for any just-fixed finding whose source file gained no co-located test — surface it as a one-line suggestion before re-opening the menu.
- Standard menu then re-opens, now including "Re-run review on fixed code" for the full target if user wants the broader pass.

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
