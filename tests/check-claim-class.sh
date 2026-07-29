#!/usr/bin/env bash
# check-claim-class.sh — release gate for claim-class discipline + gate provenance.
#
# Both behaviors are instruction-driven and NON-DETERMINISTIC — an agent deciding
# "this is a runtime claim and I only read the source" cannot be exercised
# headlessly, exactly like the Phase 4 menu and the vote flow. This static gate
# greps the published docs for their invariants so a regression (the claim-class
# table lost, the `unverified` verdict silently collapsing back into keep/drop,
# gate mode blocking on an unobserved claim, PASS reinstated without provenance)
# can't slip through unseen.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
SHARED="$ROOT/skills/review-all/agents/_shared.md"
VERIFIER="$ROOT/skills/review-all/agents/verifier.md"
VERIFY="$ROOT/skills/review-all/references/phase-2.5-verification.md"
REPORT="$ROOT/skills/review-all/references/phase-3-report.md"
GATE="$ROOT/skills/review-all/references/phase-gate.md"
README="$ROOT/README.md"

for f in "$SKILL" "$SHARED" "$VERIFIER" "$VERIFY" "$REPORT" "$GATE" "$README"; do
  [[ -f "$f" ]] || { echo "check-claim-class: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-claim-class: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-claim-class: asserting claim-class + provenance invariants across agents/ references/ SKILL.md README.md"

# --- _shared.md: the taxonomy every finding agent inherits ---
need "$SHARED" 'Claim classes' "shared: Claim classes section"
need "$SHARED" 'Admissible proof' "shared: admissible-proof column"
need "$SHARED" '\*\*Static\*\*' "shared: static class"
need "$SHARED" '\*\*Runtime\*\*' "shared: runtime class"
need "$SHARED" '\*\*Data\*\*' "shared: data class"
need "$SHARED" '\*\*Rendering\*\*' "shared: rendering class"
need "$SHARED" 'UNVERIFIED — would need' "shared: missing-observation phrasing"
need "$SHARED" 'never 🔴/🟠' "shared: severity cap on unbacked claims"

# --- verifier.md: the verdict, its required fields, and the independence rule ---
need "$VERIFIER" 'The .unverified. verdict' "verifier: unverified verdict section"
need "$VERIFIER" '"claim_class"' "verifier: claim_class output field"
need "$VERIFIER" '"needs_observation"' "verifier: needs_observation output field"
need "$VERIFIER" '"drop" \| "unverified"' "verifier: verdict enum includes unverified"
need "$VERIFIER" 'Never assign 🔴/🟠 to an .unverified. finding' "verifier: no top severity when unobserved"
need "$VERIFIER" 'methodologically independent' "verifier: cross-agent bonus independence"
need "$VERIFIER" 'correlated-evidence' "verifier: correlated-evidence marker"

# --- phase-2.5-verification.md: orthogonality + vote interaction + gate fast path ---
need "$VERIFY" 'orthogonal to the score bands' "verify: unverified is not a fourth band"
need "$VERIFY" 'They are never dropped' "verify: unverified never dropped"
need "$VERIFY" 'any voter marks .unverified. stays .unverified.' "verify: vote interaction"
need "$VERIFY" 'command run this session' "verify: VERIFIED fast path needs provenance"

# --- phase-3-report.md: the 🔬 section + the mandatory Provenance column ---
need "$REPORT" '🔬 Unverified' "report: unverified section heading"
need "$REPORT" '\| Gate \| Result \| Provenance \| Details \|' "report: gate table Provenance column"
need "$REPORT" 'may not be rendered .PASS.' "report: no PASS without provenance"
need "$REPORT" 'never merge into a severity tier' "report: unverified stays out of tiers"

# --- SKILL.md: orchestrator plumbing (schema, bands, menu gate, provenance) ---
need "$SKILL" 'keep./.appendix./.drop./.unverified' "SKILL: Phase 2.75 verdict enum includes unverified"
need "$SKILL" 'needs_observation' "SKILL: needs_observation required when unverified"
need "$SKILL" 'orthogonal to those bands' "SKILL: unverified orthogonal to score bands"
need "$SKILL" 'no 🔬 unverified findings' "SKILL: menu-skip accounts for unverified"
need "$SKILL" 'PASS requires a command you executed' "SKILL: gate PASS provenance rule"
need "$SKILL" 'stale-dev-server' "SKILL: dev-server liveness proof"

# --- phase-gate.md: an unobserved claim must never block CI / a loop ---
need "$GATE" 'Exclude every .unverified. finding' "gate: unverified excluded from gateable set"
need "$GATE" 'No blocking on an .unverified. finding' "gate: unverified never blocks"

# --- README.md: the behavior is documented for users ---
need "$README" 'unverified' "README: unverified verdict mentioned"
need "$README" 'Provenance' "README: gate provenance mentioned"

if [[ $rc -eq 0 ]]; then
  echo "check-claim-class: CLEAN"
else
  echo "check-claim-class: FAIL — claim-class/provenance invariant(s) missing above." >&2
fi
exit $rc
