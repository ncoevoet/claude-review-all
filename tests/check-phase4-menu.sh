#!/usr/bin/env bash
# check-phase4-menu.sh — release gate for the Phase 4 interactive menu.
#
# The menu is instruction-driven and CANNOT be exercised headlessly (the eval
# runner tells `claude -p` not to call AskUserQuestion, since headless mode
# can't answer it). So the 60+ case eval suite is BLIND to the menu, and a
# regression here (e.g. the fix-only-primary-menu regression that buried the
# other actions, or a dropped mandatory-menu gate) slips through unseen. This
# static gate greps the published docs for the menu invariants so that can't
# happen silently. Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
MENU="$ROOT/skills/review-all/references/phase-4-menu.md"
REPORT="$ROOT/skills/review-all/references/phase-3-report.md"
README="$ROOT/README.md"

for f in "$SKILL" "$MENU" "$REPORT" "$README"; do
  [[ -f "$f" ]] || { echo "check-phase4-menu: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-phase4-menu: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-phase4-menu: asserting menu invariants in SKILL.md / phase-4-menu.md / phase-3-report.md / README.md"

# --- SKILL.md: mandatory menu gate + allowed-tools + the four primary modes ---
need "$SKILL" 'MUST present the Phase 4 menu in the SAME turn' "mandatory-menu gate sentence"
need "$SKILL" 'every report section reads .None found' "only-skip condition"
need "$SKILL" 'no appendix AND no 🔬 unverified findings \(no 🔴' "only-skip condition includes unverified clause (Phase 4 gate)"
need "$SKILL" 'skip it only when every section says .None found\.. and there is no appendix and no 🔬 unverified' "only-skip condition includes unverified clause (Important Rule 2)"
need "$SKILL" 'Report-before-menu ordering' "report-before-menu ordering rule"
need "$SKILL" 'zero tool calls between the report text and the menu call' "zero-tool-calls-between sentence"
need "$SKILL" 'Full report above' "verdict summary in menu question text"
need "$SKILL" 'Bash\(gh pr comment:\*\)' "allowed-tools: gh pr comment"
need "$SKILL" 'Bash\(gh issue create:\*\)' "allowed-tools: gh issue create"
need "$SKILL" 'in ONE step' "one-step primary menu (no scope sub-menu)"
need "$SKILL" 'Fix must-fix only' "primary option: Fix must-fix only"
need "$SKILL" 'Triage one-by-one' "primary option: Triage one-by-one"
need "$SKILL" '\*\*Done\*\*' "primary option: Done"
need "$SKILL" 'at least 2 options' "every menu has at least 2 options"

# --- phase-4-menu.md: one-step menu, the 4-cap rule, Other grammar, free-text actions ---
need "$MENU" 'Primary menu — one step' "one-step primary menu section"
need "$MENU" 'Fix must-fix only' "primary option: Fix must-fix only"
need "$MENU" 'Fix suggested' "primary option when only 🔵: Fix suggested"
need "$MENU" 'Ask about a finding' "primary option when only ⚪/appendix/🔬: Ask about a finding"
need "$MENU" 'Triage one-by-one' "primary option: Triage one-by-one"
need "$MENU" 'range form' "ID labels written as ranges"
need "$MENU" 'at least 2 options' "every menu has at least 2 options"
need "$MENU" '## Free-text actions' "free-text actions table"
need "$MENU" 'Re-run review on the fixed code' "free-text action: Re-run review on the fixed code"
need "$MENU" 'Fix by agent' "free-text action: Fix by agent"
need "$MENU" 'Deep-dive' "free-text action: Deep-dive"
need "$MENU" 'Post to PR' "free-text action: Post to PR"
need "$MENU" 'array too_big' ">4-findings cap crash warning"
need "$MENU" 'caps option' "AskUserQuestion 4-option cap note"
need "$MENU" 'C = .*Critical' "Custom expression grammar legend"
need "$MENU" 'Ask a follow-up question' "action: Ask a follow-up question"
need "$MENU" 'Generate tests' "action: Generate tests"
need "$MENU" 'Create a ticket' "action: Create a ticket/issue"
need "$MENU" 'Export findings' "action: Export findings (JSON + SARIF)"
need "$MENU" 'Report-before-menu ordering' "report-before-menu ordering rule"
need "$MENU" 'zero tool calls between the report text and the menu call' "zero-tool-calls-between sentence"
need "$MENU" 'Full report above' "verdict summary in menu question text"
need "$MENU" 'no appendix AND no 🔬 unverified findings \(nothing scoring' "only-skip condition includes unverified clause (mandatory-menu gate)"
need "$MENU" 'no appendix AND no 🔬 unverified findings → skip Phase 4' "only-skip condition includes unverified clause (assembly algorithm)"

# --- phase-4-menu.md: triage micro-menu — Round 1 + Round 2 verbs, 4-cap resolution ---
need "$MENU" 'Fix this' "triage verb: Fix this"
need "$MENU" 'Stop triage' "triage verb: Stop triage"
need "$MENU" 'Snooze' "triage verb: Snooze"
need "$MENU" 'Wontfix' "triage verb: Wontfix"
need "$MENU" 'Skip .* next' "triage verb: Skip -> next"
need "$MENU" 'caps at 4' "triage drill-down 4-cap resolution note"

# --- phase-4-menu.md: Generate-tests new-file exception scoped to AUTO-fixes ---
need "$MENU" 'never create new files.*auto' "new-files guardrail scoped to auto-fix"
need "$MENU" 'issue-<finding>-' "Create-ticket Tier-3 markdown fallback"

# --- phase-3-report.md: merge-readiness + change-type buckets ---
need "$REPORT" 'Merge-readiness' "report: merge-readiness line"
need "$REPORT" 'new.*modified.*deleted' "report: change-type buckets"

# --- README.md: the one-step menu named (anti-drift doc sync) ---
need "$README" 'Triage' "README: Triage option"
need "$README" '`Other`' "README: free-text Other field"

# --- negative: the retired three-mode menu must not drift back ---
for f in "$SKILL" "$MENU" "$README"; do
  if grep -nE 'Mode [ABC]\b|More actions|Fix by scope|Skip / done|Round 3' "$f" >&2; then
    echo "check-phase4-menu: RETIRED menu term in $(basename "$f") (lines above)" >&2
    rc=1
  fi
done

if [[ $rc -eq 0 ]]; then
  echo "check-phase4-menu: CLEAN"
else
  echo "check-phase4-menu: FAIL — menu invariant(s) missing above." >&2
fi
exit $rc
