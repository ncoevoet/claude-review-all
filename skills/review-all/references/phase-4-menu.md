# Phase 4 — Post-Report Choices

Loaded by `/review-all` Phase 4. Presents the post-report action menu, including the apply-fixes sub-menu, loop, and guardrails.

After printing the report, present a rich menu via `AskUserQuestion`. Skip Phase 4 entirely if every section says "None found."

Build the option list dynamically — only include options that make sense given the run state. Always offer at least "Skip / done".

## Available choices

| Label | When to offer | Action |
|-------|---------------|--------|
| **Apply fixes (Recommended)** | At least one ❌/⚠️/♻️/🎨 finding exists | Sub-menu of scopes, then apply |
| **Save full report to file** | Always | Write to `outputDir/review-<iso-timestamp>.md` |
| **Deep-dive a finding** | Any finding | Ask for finding number → spawn focused agent that returns full callers/callees, root-cause analysis, 2-3 fix strategies with tradeoffs |
| **Generate fix patches as a diff** | Any actionable finding | Produce a unified diff (no apply) — let user `git apply` later |
| **Draft commit / PR description** | Any actionable finding | Synthesize a commit/PR body covering the changes + how findings were addressed |
| **Post to GitHub PR** | A PR exists for the current branch (probe `gh pr view`) | Comment the report on the PR |
| **Schedule a re-review** | Always | Invoke `/schedule` skill — recurring or one-shot |
| **Snooze a finding** | Any finding | Ask for finding number + reason + expiry → append to `snoozeFile` |
| **Re-run review on the fixed code** | Only after a Fix step succeeded | Re-execute Phase 1 + 2 + 2.5 + 3 on the now-modified tree |
| **Explain a finding** | Any finding | Plain-language explanation of one finding for the user |
| **Skip / done** | Always | Exit |

## Apply-fixes sub-menu

If user picks "Apply fixes":

| Label | Scope |
|-------|-------|
| Fix critical only (Recommended) | ❌ |
| Fix critical + important | ❌ + ⚠️ |
| Fix recommended | ❌ + ⚠️ + ♻️ |
| Fix all findings | ❌ + ⚠️ + ♻️ + 🎨 |
| Fix by agent | Sub-select agent |
| Fix by number | Sub-select finding numbers |
| Cancel | back to main menu |

For each finding in the chosen scope (file-then-line order):
1. Read file at the finding's location to confirm code unchanged.
2. Apply the fix using `Edit` — use the "Fix" text from the finding.
3. If the fix can't be a single targeted Edit (cross-file, new file, architectural) → record as "manual follow-up", do NOT attempt.
4. Record per-finding outcome: `applied` / `manual follow-up` / `skipped (code changed)`.

After all edits, re-run Phase 1 gates against the modified tree:

```
## Fix Results
- Scope: {chosen}
- Applied: N
- Manual follow-up: M (listed below)
- Post-fix gates: Typecheck ✅/❌, Lint ✅/❌, Tests ✅/❌
```

If a previously-passing gate now fails: list failing output, suggest `git diff` / `git checkout --` rollback. **Never auto-rollback** — user decides.

## Loop

After completing a non-terminal choice (anything except "Skip / done"), present the menu again with updated state (e.g., "Re-run review on fixed code" becomes available after fixes apply). Continue until user picks "Skip / done".

## Guardrails

- **Never auto-apply** ❓ QUESTION findings.
- **Never auto-apply** appendix findings (50–74 confidence).
- **Never create new files** as part of a fix (missing-spec → manual follow-up).
- **Never touch files outside the review target's changed-file set** unless a finding explicitly names that file and severity is ❌ or ⚠️.
- **Never post to PR without confirmation** — even if the user picked it, show the comment body and confirm before posting.
- If chosen scope yields zero applicable findings after guardrails, report "nothing to auto-apply" and return to menu.
