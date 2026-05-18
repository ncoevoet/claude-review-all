# Phase 4 — Post-Report Choices

Loaded by `/review-all` Phase 4. Presents the post-report action menu, including the apply-fixes sub-menu, loop, and guardrails.

After printing the report, present a **fix-scope menu** via `AskUserQuestion` (single-select) listing the four primary fix actions below. Skip Phase 4 entirely if every section says "None found."

Every finding in the report MUST be prefixed with its number (Finding 1, Finding 2, …) — main sections AND appendix. The numbered list is what the **Custom** option references via `#N` / `N` / `N-M`.

Build the option list dynamically — only include scopes that have at least one matching finding. The follow-up menu (after the chosen action completes) presents extended options via `AskUserQuestion` with `multiSelect: true`, and always includes "Skip / done" (selecting it terminates the loop even if other options are also selected — `Skip / done` is dominant).

**Composition rules** when multiple options are selected:
1. Apply fixes runs first (if chosen), since later actions may depend on the modified tree.
2. Then deep-dive / generate patch / draft commit / explain (read-only synthesis).
3. Then save / post to PR / schedule (publication).
4. Then snooze / mark wontfix (state writes).
5. Re-run review on fixed code, if chosen, runs last.

The apply-fixes sub-menu stays **single-select** — scopes are mutually exclusive.

## Available choices

AskUserQuestion options cap at 4. The primary menu is the four fix-scope actions below (single-select). Everything else lives in the follow-up extended menu that opens after the chosen action completes (or via **Custom** → Cancel → extended menu).

### Primary fix-scope menu (single-select, in order)

| Label | When to offer | Action |
|-------|---------------|--------|
| **Fix critical (Recommended)** | At least one 🔴 finding | Apply 🔴 findings |
| **Fix critical + important** | At least one 🔴 or 🟠 finding | Apply 🔴 + 🟠 findings |
| **Fix critical + important + debt** | At least one 🔴/🟠/🟡 finding | Apply 🔴 + 🟠 + 🟡 findings |
| **Custom (C/I/D/S + #IDs)** | Any finding exists | Prompt for a free-text expression mixing severity letters and finding IDs (grammar below) → apply the UNION |

If none of the first three scopes have matching findings (e.g. only 🔵 suggestions), still offer **Custom**. If there are zero actionable findings, skip Phase 4 entirely.

#### Custom expression grammar

```
C  I  D  S        severity letters (case-insensitive)
                  C = 🔴 Critical   I = 🟠 Important   D = 🟡 Debt   S = 🔵 Suggested
#11   11          single finding (# prefix optional)
1-7   #3-#9       inclusive range (# optional on either side)
```

Separators: comma, whitespace, or the word `and` — all interchangeable. Result = UNION of every matched finding ID; duplicates collapse. Severity letters expand to all in-report findings of that tier.

Examples:
- `I D #11`    → all 🟠 + all 🟡 + Finding 11
- `1-7, 11`   → Findings 1..7 plus 11
- `C #14-#16` → all 🔴 + Findings 14, 15, 16

Numeric-only input (`1,3,7-9`) remains valid — strict superset of the old "Select by number" behavior.

The bundled "save report" action is no longer in the primary menu — it lives in the extended menu and is also auto-offered after any successful fix run.

### Extended menu (follow-up, multi-select)

Shown after the primary fix action completes, OR if the user cancels the primary menu via AskUserQuestion's `Other` → `more`. Always includes `Skip / done`.

| Label | When to offer | Action |
|-------|---------------|--------|
| **Save full report to file** | Always (if not already included via bundled default) | Write to `outputDir/review-<iso-timestamp>.md` |
| **Deep-dive a finding** | Any finding | Ask for finding number → spawn focused agent that returns full callers/callees, root-cause analysis, 2-3 fix strategies with tradeoffs |
| **Generate fix patches as a diff** | Any actionable finding | Produce a unified diff (no apply) — let user `git apply` later |
| **Draft commit / PR description** | Any actionable finding | Synthesize a commit/PR body covering the changes + how findings were addressed |
| **Post to GitHub PR** | A PR exists for the current branch (probe `gh pr view`) | Comment the report on the PR |
| **Schedule a re-review** | Always | Invoke `/schedule` skill — recurring or one-shot |
| **Snooze a finding** | Any finding | Ask for finding number + reason + expiry → upsert in `stateFile` with `status: snoozed`, `snoozed_until: <expiry>` (see `state-file.md`) |
| **Mark as wontfix** | Any finding | Ask for finding number + reason → upsert in `stateFile` with `status: wontfix` and current `code_hash` (see `state-file.md`) |
| **Re-run review on the fixed code** | Only after a Fix step succeeded | Re-execute Phase 1 + 2 + 2.5 + 3 on the now-modified tree |
| **Explain a finding** | Any finding | Plain-language explanation of one finding for the user |
| **Apply fixes (alternate scopes)** | At least one 🔴/🟠/🟡/🔵 finding exists | Full apply-fixes sub-menu (use when the bundled default isn't the desired scope) |

## Apply-fixes sub-menu

The primary menu IS the apply-fixes scope selector — no extra sub-menu round. Scope mapping:

| Primary choice | Scope |
|----------------|-------|
| Fix critical (Recommended) | 🔴 |
| Fix critical + important | 🔴 + 🟠 |
| Fix critical + important + debt | 🔴 + 🟠 + 🟡 |
| Custom (C/I/D/S + #IDs) | UNION of expanded severity letters and explicit IDs/ranges (see grammar above) |

Additional scopes (Fix all 🔵, Fix by agent) are available from the extended menu under **Apply fixes (alternate scopes)**.

For each finding in the chosen scope (file-then-line order):
1. Read file at the finding's location to confirm code unchanged.
2. Apply the fix using `Edit` — use the "Fix" text from the finding.
3. If the fix can't be a single targeted Edit (cross-file, new file, architectural) → record as "manual follow-up", do NOT attempt.
4. Record per-finding outcome: `applied` / `manual follow-up` / `skipped (code changed)`.

After all edits, re-run Phase 1 gates against the modified tree:

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

Outcome values are exhaustive: `applied` | `manual follow-up` | `skipped` | `guardrail-blocked`. Every finding in the chosen scope appears in the table — silent omission was the #1 user-friction signal observed in real sessions ("why F25 not done?").

If a previously-passing gate now fails: list failing output, suggest `git diff` / `git checkout --` rollback. **Never auto-rollback** — user decides.

## Loop

After completing a non-terminal choice (anything except "Skip / done"), present the menu again with updated state (e.g., "Re-run review on fixed code" becomes available after fixes apply). Continue until user picks "Skip / done".

## Auto-delta after successful apply-fixes

When apply-fixes completes AND **all** post-fix gates pass (Typecheck ✅ + Lint ✅ + Tests ✅, ignoring any gate that was N/A or SKIP before fixes), the orchestrator automatically runs a scoped **delta review** before re-presenting the menu:

- Scope = the just-edited files only (the actual fix target set, not the original review target).
- Phases run: 1 → 2 (parallel agents on the narrow slice) → 2.5 (verify) → 3 (delta report).
- The delta report is appended to the existing report under a new `## Post-fix delta` section. No new file is written.
- The standard menu then re-opens, now including "Re-run review on fixed code" for the full target if the user wants the broader pass too.

**Do NOT trigger auto-delta** when:
- Any post-fix gate failed or timed out → surface the gate output, let the user decide (rollback, manually fix, etc.).
- Zero fixes were applied (all manual follow-up / skipped) → no edits to verify.
- `applied + manual-follow-up == 0` → there's nothing to re-review.

Rationale: in observed sessions the user almost always picked "Re-run review on fixed code" after a clean apply. Auto-delta cuts one menu round; gate-pass gating means it never surprises the user with a destabilized tree.

## Guardrails

- **Never auto-apply** ⚪ QUESTION findings.
- **Never auto-apply** appendix findings (50–74 confidence).
- **Never create new files** as part of a fix (missing-spec → manual follow-up).
- **Never touch files outside the review target's changed-file set** unless a finding explicitly names that file and severity is 🔴 or 🟠.
- **Never post to PR without confirmation** — even if the user picked it, show the comment body and confirm before posting.
- If chosen scope yields zero applicable findings after guardrails, report "nothing to auto-apply" and return to menu.
