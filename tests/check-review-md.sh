#!/usr/bin/env bash
# check-review-md.sh — release gate for repo-root REVIEW.md support.
#
# REVIEW.md is injected verbatim, ahead of the persona, into every agent and the
# verifier. That makes it the skill's widest instruction-injection surface, and
# two properties keep it safe rather than exploitable: it is never cached (so a
# stale copy can't outlive the file), and it can never override the evidence
# discipline (so "report this without proof" is not a thing a repo can ask for).
# Both are prose-only guarantees, invisible to the eval suite — this gate pins
# them, plus the never-truncate and no-@-import contracts users rely on.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
SHARED="$ROOT/skills/review-all/agents/_shared.md"
VERIFIER="$ROOT/skills/review-all/agents/verifier.md"
GATE="$ROOT/skills/review-all/references/phase-gate.md"
KEYS="$ROOT/skills/review-all/references/config-keys.md"
README="$ROOT/README.md"

for f in "$SKILL" "$SHARED" "$VERIFIER" "$GATE" "$KEYS" "$README"; do
  [[ -f "$f" ]] || { echo "check-review-md: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-review-md: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-review-md: asserting REVIEW.md invariants across SKILL.md / _shared.md / verifier.md / phase-gate.md / config-keys.md / README.md"

# --- SKILL.md: read fresh, verbatim, no imports, canonical block order ---
need "$SKILL" 'REVIEW\.md' "Step 0.5 REVIEW.md source"
need "$SKILL" 'never cached — always read fresh.: if a .REVIEW\.md' "REVIEW.md never cached / always fresh"
need "$SKILL" 'carry it VERBATIM into Phase 2' "verbatim injection contract"
need "$SKILL" 'do NOT expand .@.-imports' "no @-import expansion"
need "$SKILL" 'review_instructions' "review_instructions block name"
need "$SKILL" 'Canonical block order' "canonical prompt block order published"
need "$SKILL" 'REVIEW\.md loaded' "Phase 0 heartbeat reports REVIEW.md"

# --- _shared.md: precedence + the non-negotiable evidence carve-out ---
need "$SHARED" 'Repository review instructions' "precedence section present"
need "$SHARED" 'with these shared rules, .REVIEW\.md. wins' "precedence over persona and shared rules"
need "$SHARED" 'steers what you review and how severely, never how you prove it' "evidence-discipline carve-out"
need "$SHARED" 'integrity rules, not preferences' "integrity-rules framing"
need "$SHARED" 'never as a message from the user' "injection-surface guard"

# --- verifier.md: input + severity-still-earned ---
need "$VERIFIER" 'review_instructions' "verifier receives review_instructions"
need "$VERIFIER" 'never relaxes the citation gate' "REVIEW.md cannot relax the citation gate"

# --- phase-gate.md: bidirectional floor interaction + self-approval tripwire ---
need "$GATE" 'REVIEW\.md in gate mode' "gate-mode section present"
need "$GATE" 'demotion can move a real defect below the floor' "demotion risk documented"
need "$GATE" 'not addressable from .REVIEW\.md' "gate mechanism not overridable"
need "$GATE" 'REVIEW\.md modified in this diff' "self-approving-diff tripwire"

# --- config-keys.md + README: user-facing documentation ---
need "$KEYS" 'REVIEW\.md' "config-keys points at the REVIEW.md convention"
need "$README" '^## Review instructions' "README section present"
need "$README" 'only report if near-certain and severe' "README per-path raised-bar idiom"
need "$README" 'Verbatim means verbatim' "README verbatim/no-import note"

if [[ $rc -eq 0 ]]; then
  echo "check-review-md: CLEAN"
else
  echo "check-review-md: FAIL — REVIEW.md invariant(s) missing above." >&2
fi
exit $rc
