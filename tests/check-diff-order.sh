#!/usr/bin/env bash
# check-diff-order.sh — release gate for per-agent diff ordering.
#
# The ordering script has unit tests; what those cannot cover is the two prose
# rules that keep the reorder safe. Drop "chunk composition on canonical order
# first" and agents silently diverge on chunk membership, which desynchronizes
# Phase 2.75 accounting. Drop "never reorder hunks" and a future edit could
# permute inside a file, scrambling the diff an agent reads. Both live only in
# docs, so this gate pins them.
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
AGENTS="$ROOT/skills/review-all/references/phase-2-agents.md"
SCRIPT="$ROOT/skills/review-all/scripts/agent-order.py"
README="$ROOT/README.md"

for f in "$SKILL" "$AGENTS" "$SCRIPT" "$README"; do
  [[ -f "$f" ]] || { echo "check-diff-order: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-diff-order: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-diff-order: asserting per-agent diff-ordering invariants in SKILL.md / phase-2-agents.md / README.md"

# --- phase-2-agents.md: the full rule set ---
need "$AGENTS" 'Per-agent diff ordering' "ordering section present"
need "$AGENTS" 'agent-order\.py' "ordering script named"
need "$AGENTS" 'sha256' "reproducible content-addressed permutation"
need "$AGENTS" 'Hunks within a file are NEVER reordered' "never-reorder-hunks rule"
need "$AGENTS" 'Chunk composition is computed on the canonical .git. order first' "chunk-composition-canonical rule"
need "$AGENTS" 'slice holds ≥ 3 files' "3-file threshold"
need "$AGENTS" 'verifier is unaffected' "verifier order-independence"
need "$AGENTS" 'blame. block moves with its file' "attached context travels with its file"

# --- SKILL.md: the orchestrator actually calls it, once ---
need "$SKILL" 'agent-order\.py' "SKILL.md calls the ordering script"
need "$SKILL" 'ONCE with the union of changed files' "single call per review"
need "$SKILL" 'hunks inside a file are never reordered' "SKILL.md restates the hunk rule"

# --- the script itself keeps its two load-bearing properties documented ---
need "$SCRIPT" 'Filter-stable' "script documents filter stability"
need "$SCRIPT" 'Never reorders hunks within a file' "script documents file-level-only scope"

# --- README: user-visible ---
need "$README" 'agent-order\.py' "README mentions the ordering feature"

if [[ $rc -eq 0 ]]; then
  echo "check-diff-order: CLEAN"
else
  echo "check-diff-order: FAIL — diff-ordering invariant(s) missing above." >&2
fi
exit $rc
