#!/usr/bin/env bash
# check-gate-results.sh — release gate for <gate_results> + the corroboration signal.
#
# Two prose rules carry this feature's whole safety margin. "A failing gate line
# is a lead, not a finding" is what stops ten agents from each re-reporting the
# same failing test (which would also inflate the corroboration count on a
# gate-shaped root cause). "Never a substitute for verification" is what stops
# corroborating_agents from decaying into a popularity score — the exact failure
# the verifier's correlated-evidence rule exists to prevent. Neither is
# observable to the eval suite, so this gate pins both, plus the verifier
# version bump that invalidates stale cached verdicts.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
VERIFIER="$ROOT/skills/review-all/agents/verifier.md"
VERIFY_DOC="$ROOT/skills/review-all/references/phase-2.5-verification.md"
REPORT="$ROOT/skills/review-all/references/phase-3-report.md"
DEDUPE="$ROOT/skills/review-all/scripts/dedupe.py"
README="$ROOT/README.md"

for f in "$SKILL" "$VERIFIER" "$VERIFY_DOC" "$REPORT" "$DEDUPE" "$README"; do
  [[ -f "$f" ]] || { echo "check-gate-results: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-gate-results: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-gate-results: asserting <gate_results> + corroboration invariants"

# --- SKILL.md: the block, its bounds, and the lead-not-a-finding rule ---
need "$SKILL" 'gate_results' "gate_results block defined"
need "$SKILL" '\*\*Failures only\*\*' "failures-only rule"
need "$SKILL" '20 lines or 2 000 characters per gate and 4 000 characters total' "truncation caps"
need "$SKILL" 'lead, not a finding' "lead-not-a-finding rule"
need "$SKILL" 'Never restate gate output as a finding' "no-restating rule"

# --- verifier.md: both new inputs, the corroboration ceiling, the version bump ---
need "$VERIFIER" '^version: 7$' "verifier version bumped to 7"
need "$VERIFIER" 'gate_results' "verifier receives gate_results"
need "$VERIFIER" 'corroborating_agents' "verifier receives corroborating_agents"
need "$VERIFIER" 'never a substitute for verification' "corroboration is not proof"
need "$VERIFIER" 'Agreement is not independence' "correlation caveat"
need "$VERIFIER" 'feeds no scoring bonus' "rubric deliberately untouched"

# --- phase-2.5-verification.md: input list kept in sync ---
need "$VERIFY_DOC" 'corroborating_agents' "verification doc lists corroborating_agents"
need "$VERIFY_DOC" 'gate_results' "verification doc lists gate_results"

# --- dedupe.py + report + README ---
need "$DEDUPE" 'corroborating_agents' "dedupe emits corroborating_agents"
need "$REPORT" 'Flagged independently by' "report renders the corroboration count"
need "$README" 'Flagged independently by N agents' "README documents the corroboration count"
need "$README" 'gate_results' "README documents the gate_results block"

if [[ $rc -eq 0 ]]; then
  echo "check-gate-results: CLEAN"
else
  echo "check-gate-results: FAIL — invariant(s) missing above." >&2
fi
exit $rc
