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
need "$SKILL" 'Bash\(gh pr comment:\*\)' "allowed-tools: gh pr comment"
need "$SKILL" 'Bash\(gh issue create:\*\)' "allowed-tools: gh issue create"
need "$SKILL" 'Fix by scope' "primary mode: Fix by scope"
need "$SKILL" 'Triage one-by-one' "primary mode: Triage one-by-one"
need "$SKILL" 'More actions' "primary mode: More actions"
need "$SKILL" 'Skip / done' "primary mode: Skip / done"

# --- phase-4-menu.md: three modes, the 4-cap rule, Custom grammar, new actions ---
need "$MENU" 'Fix by scope' "Mode A: Fix by scope"
need "$MENU" 'Triage one-by-one' "Mode B: Triage one-by-one"
need "$MENU" 'More actions' "Mode C: More actions"
need "$MENU" 'Skip / done' "Skip / done (dominant terminator)"
need "$MENU" 'array too_big' ">4-findings cap crash warning"
need "$MENU" 'caps option' "AskUserQuestion 4-option cap note"
need "$MENU" 'C = .*Critical' "Custom expression grammar legend"
need "$MENU" 'Ask a follow-up question' "action: Ask a follow-up question"
need "$MENU" 'Generate tests' "action: Generate tests"
need "$MENU" 'Create a ticket' "action: Create a ticket/issue"
need "$MENU" 'Export findings' "action: Export findings (JSON + SARIF)"

# --- phase-4-menu.md: triage micro-menu — all six verbs + the 6-vs-4 resolution ---
need "$MENU" 'Fix this' "triage verb: Fix this"
need "$MENU" 'Ask a question' "triage verb: Ask a question"
need "$MENU" 'Create ticket' "triage verb: Create ticket"
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

# --- README.md: the three modes named (anti-drift doc sync) ---
need "$README" 'Fix by scope' "README: Fix by scope mode"
need "$README" 'Triage' "README: Triage mode"
need "$README" 'More actions' "README: More actions mode"

if [[ $rc -eq 0 ]]; then
  echo "check-phase4-menu: CLEAN"
else
  echo "check-phase4-menu: FAIL — menu invariant(s) missing above." >&2
fi
exit $rc
