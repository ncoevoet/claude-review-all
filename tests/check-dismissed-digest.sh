#!/usr/bin/env bash
# check-dismissed-digest.sh — release gate for the <previously_dismissed> digest.
#
# Feeding the team's wontfix/snooze decisions back to the agents is orchestrator-
# prompt behavior, and a single headless review CANNOT prove it: the dismissed
# finding is already omitted by the Phase 2.5 Step 2.5.0 central drop, so a
# PASS/FAIL report check can't tell digest-suppression from the post-hoc drop —
# the digest's real benefit is saved generation/verifier spend, invisible to a
# report. So the eval suite is blind to it (like the menu and verifier-votes);
# this static gate greps the published docs for its invariants instead.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
SHARED="$ROOT/skills/review-all/agents/_shared.md"
AGENTS="$ROOT/skills/review-all/references/phase-2-agents.md"
README="$ROOT/README.md"

for f in "$SKILL" "$SHARED" "$AGENTS" "$README"; do
  [[ -f "$f" ]] || { echo "check-dismissed-digest: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-dismissed-digest: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-dismissed-digest: asserting digest invariants in SKILL.md / _shared.md / phase-2-agents.md / README.md"

# --- SKILL.md: the build step, source, cap, and spend-saving-not-the-gate framing ---
need "$SKILL" 'Dismissed-finding digest' "SKILL: digest build heading"
need "$SKILL" 'previously_dismissed' "SKILL: <previously_dismissed> tag"
need "$SKILL" 'status: wontfix' "SKILL: sources wontfix entries"
need "$SKILL" 'snoozed_until' "SKILL: sources non-expired snoozed entries"
need "$SKILL" 'Step 2.5.0 central drop stays the guarantee' "SKILL: central-drop remains the guarantee"
need "$SKILL" 'diff-membership' "SKILL: diff-membership match (not a recomputed hash)"

# --- _shared.md: the handling section, the unchanged-vs-changed rule, the guarantee ---
need "$SHARED" 'Previously-dismissed findings' "shared: handling section heading"
need "$SHARED" 'unchanged in this diff' "shared: suppress only when location unchanged"
need "$SHARED" 'dismissal may no longer hold' "shared: changed location re-raises"
need "$SHARED" 'Step 2.5.0 central filter still drops' "shared: central filter remains the guarantee"

# --- phase-2-agents.md: the reversal of the old no-suppression-list stance ---
need "$AGENTS" 'previously_dismissed' "agents: digest now in agent inputs"
need "$AGENTS" 'reverses the earlier' "agents: explicit reversal of prior stance"

# --- README.md: surfaced as a lifecycle/learning Pro ---
need "$README" 'previously_dismissed' "README: digest mentioned"

if [[ $rc -eq 0 ]]; then
  echo "check-dismissed-digest: CLEAN"
else
  echo "check-dismissed-digest: FAIL — dismissed-digest invariant(s) missing above." >&2
fi
exit $rc
