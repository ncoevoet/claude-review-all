#!/usr/bin/env bash
# check-verifier-votes.sh — release gate for the verifierVotes majority-vote flow.
#
# Majority-vote re-verification (Phase 2.5b-vote) is instruction-driven and
# NON-DETERMINISTIC — it cannot be exercised headlessly, so the eval suite is
# blind to it exactly like the Phase 4 menu. This static gate greps the published
# docs for its invariants so a regression (a dropped default, the top-severity
# scoping lost, the majority rule mangled) can't slip through unseen.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
VERIFY="$ROOT/skills/review-all/references/phase-2.5-verification.md"
CONFIG="$ROOT/skills/review-all/references/config-keys.md"
README="$ROOT/README.md"

for f in "$SKILL" "$VERIFY" "$CONFIG" "$README"; do
  [[ -f "$f" ]] || { echo "check-verifier-votes: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-verifier-votes: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-verifier-votes: asserting majority-vote invariants in config-keys.md / phase-2.5-verification.md / SKILL.md / README.md"

# --- config-keys.md: the key, its default, scope, and majority semantics ---
need "$CONFIG" '\| .verifierVotes. \| .number. \| .1. \|' "verifierVotes row with default 1"
need "$CONFIG" 'majority-vote' "config: majority-vote semantics"
need "$CONFIG" 'Only 🔴/🟠 are re-voted' "config: top-severity scoping"

# --- phase-2.5-verification.md: the step, skip-when-1, majority rule, scope, median ---
need "$VERIFY" 'Step 2.5b-vote' "verify: Step 2.5b-vote heading"
need "$VERIFY" 'Skip this step entirely when .verifierVotes' "verify: skip-when-1 guard"
need "$VERIFY" '⌈.verifierVotes. / 2⌉' "verify: majority keep rule"
need "$VERIFY" 'never re-voted' "verify: DEBT/SUGGESTED/QUESTION excluded"
need "$VERIFY" 'median' "verify: median score rule"
need "$VERIFY" 'no shared context' "verify: independence of extra votes"

# --- SKILL.md: the Phase 2.5 pointer ---
need "$SKILL" 'verifierVotes' "SKILL: Phase 2.5 verifierVotes pointer"
need "$SKILL" 'Step 2.5b-vote' "SKILL: pointer to the vote step"

# --- README.md: surfaced as the verifier-misscoring escape + config example ---
need "$README" 'verifierVotes' "README: verifierVotes mentioned"

if [[ $rc -eq 0 ]]; then
  echo "check-verifier-votes: CLEAN"
else
  echo "check-verifier-votes: FAIL — verifier-votes invariant(s) missing above." >&2
fi
exit $rc
