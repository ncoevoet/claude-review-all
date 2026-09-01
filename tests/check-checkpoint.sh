#!/usr/bin/env bash
# check-checkpoint.sh — release gate for Phase 2 per-axis checkpointing.
#
# checkpoint.py has unit tests; they cannot cover the orchestration rules that
# make reuse safe, and every one of those lives only in prose:
#   - resume must never happen without the exact key (or a review reports
#     findings from a diff it did not read),
#   - a failed/timed-out/partially-chunked axis must NOT be checkpointed (or a
#     truncated pass is resumed forever),
#   - a resumed axis counts as returned in the completion gate (or Phase 2.75
#     re-spawns what we just resumed),
#   - the report must name resumed axes (provenance — the reader is entitled to
#     know which conclusions were not reached this session).
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
AGENTS_DOC="$ROOT/skills/review-all/references/phase-2-agents.md"
REPORT="$ROOT/skills/review-all/references/phase-3-report.md"
KEYS="$ROOT/skills/review-all/references/config-keys.md"
SCRIPT="$ROOT/skills/review-all/scripts/checkpoint.py"
README="$ROOT/README.md"

for f in "$SKILL" "$AGENTS_DOC" "$REPORT" "$KEYS" "$SCRIPT" "$README"; do
  [[ -f "$f" ]] || { echo "check-checkpoint: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-checkpoint: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-checkpoint: asserting per-axis checkpoint invariants in SKILL.md / phase-2-agents.md / phase-3-report.md"

# --- SKILL.md: the orchestrator loads before spawning and saves on return ---
need "$SKILL" 'checkpoint\.py load' "SKILL.md loads checkpoints before spawning"
need "$SKILL" 'resolved, FILTERED diff' "the key is computed on the filtered diff, not the raw range"
need "$AGENTS_DOC" 'RESOLVED, FILTERED diff' "phase-2-agents.md repeats the filtered-diff rule"
need "$SKILL" 'checkpoint\.py save' "SKILL.md saves each axis on return"
need "$SKILL" 'do \*\*NOT\*\* spawn it' "resumed axes are not re-spawned"
need "$SKILL" 'timed out, errored, returned malformed output' "only complete returns are checkpointed"
need "$SKILL" 'empty findings array is a legitimate result' "[] is a real result, not a miss"
need "$SKILL" 'counts as returned' "Phase 2.75 treats a resumed axis as returned"
need "$SKILL" 'python3.*missing.*checkpointing self-skips|checkpointing self-skips' \
  "checkpointing is optional, never load-bearing"

# --- the key: all four components must be named where the rule is stated ---
for doc in "$SKILL" "$AGENTS_DOC"; do
  need "$doc" 'HEAD' "key covers HEAD ($(basename "$doc"))"
  need "$doc" 'diff bytes' "key covers the exact diff ($(basename "$doc"))"
  need "$doc" 'personas' "key covers the agent personas ($(basename "$doc"))"
  need "$doc" 'REVIEW\.md' "key covers REVIEW.md ($(basename "$doc"))"
done

# --- phase-2-agents.md: the full rule set ---
need "$AGENTS_DOC" 'Checkpoint resume' "checkpoint section present"
need "$AGENTS_DOC" 'all-or-nothing' "no partial or fuzzy key match"
need "$AGENTS_DOC" 'pre-dedupe, pre-verification' "stored as returned, before verification"
need "$AGENTS_DOC" 'independent of .state\.json' "checkpoint store is not the lifecycle store"
need "$AGENTS_DOC" 'Stale files are deleted' "stale checkpoints are dropped, not kept"

# --- report provenance ---
need "$REPORT" 'Resumed from checkpoint' "report names the resumed axes"

# --- config + script contract ---
need "$KEYS" 'checkpointDir' "checkpointDir documented in the key table"
need "$SCRIPT" 'runKey = sha256' "script documents the key composition"
need "$SCRIPT" 'os\.replace' "script writes atomically"
need "$README" 'checkpoints' "README documents the feature"

if [[ $rc -eq 0 ]]; then
  echo "check-checkpoint: CLEAN"
else
  echo "check-checkpoint: FAIL — checkpoint invariant(s) missing above." >&2
fi
exit $rc
