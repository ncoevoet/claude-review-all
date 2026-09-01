#!/usr/bin/env bash
# check-agent-models.sh — release gate: every Phase 2 axis declares an explicit model.
#
# A spawn with no `model` does not fail — it silently inherits the session tier,
# which is exactly how ten axes ended up on the same expensive model, mechanical
# ones included. Nothing at runtime can detect that, so the invariant has to be
# pinned here. Two halves:
#   1. MECHANICAL set diff — each agents/NN-*.md frontmatter `model:` must equal
#      the tier the phase-2-agents.md table gives that persona. A per-file grep
#      list would drift the way the config-key lists once did; a set diff cannot.
#   2. Prose invariants — the never-spawn-without-a-model rule and the default
#      for an extraAgents persona live only in docs.
# Exit 0 = clean, 1 = a declaration or invariant is missing/divergent, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
AGENTS_DOC="$ROOT/skills/review-all/references/phase-2-agents.md"
KEYS="$ROOT/skills/review-all/references/config-keys.md"
AGENTS_DIR="$ROOT/skills/review-all/agents"
README="$ROOT/README.md"

for f in "$SKILL" "$AGENTS_DOC" "$KEYS" "$README"; do
  [[ -f "$f" ]] || { echo "check-agent-models: missing file $f" >&2; exit 2; }
done
[[ -d "$AGENTS_DIR" ]] || { echo "check-agent-models: missing dir $AGENTS_DIR" >&2; exit 2; }

echo "check-agent-models: comparing persona frontmatter model: against the phase-2-agents.md table"

rc=0

# --- half 1: frontmatter vs table, as sets of "<persona-file> <model>" ---
# Frontmatter: the model: line inside the leading --- block of each numbered persona.
frontmatter="$(for f in "$AGENTS_DIR"/[0-9][0-9]-*.md; do
  m=$(awk 'NR==1&&$0!="---"{exit} NR>1&&/^---$/{exit} /^model:[[:space:]]*/{sub(/^model:[[:space:]]*/,""); print; exit}' "$f")
  printf '%s %s\n' "$(basename "$f")" "${m:-MISSING}"
done | LC_ALL=C sort)"

# Table rows: | N | Name | `NN-x.md` | `model` | condition |
table="$(sed -n 's/^|[^|]*|[^|]*| *`\([0-9][0-9][^`]*\.md\)` *| *`\([a-z]*\)` *|.*/\1 \2/p' \
  "$AGENTS_DOC" | LC_ALL=C sort)"

if [[ -z "$frontmatter" || -z "$table" ]]; then
  echo "check-agent-models: extracted nothing (frontmatter or table) — extractor broken" >&2
  exit 2
fi

if grep -q ' MISSING$' <<<"$frontmatter"; then
  echo "check-agent-models: persona(s) with no model: in frontmatter:" >&2
  grep ' MISSING$' <<<"$frontmatter" | sed 's/^/  - /' >&2
  rc=1
fi

bad="$(grep -vE ' (sonnet|opus|MISSING)$' <<<"$frontmatter" || true)"
if [[ -n "$bad" ]]; then
  echo "check-agent-models: unexpected tier (expected sonnet|opus):" >&2
  echo "$bad" | sed 's/^/  - /' >&2
  rc=1
fi

if ! diff_out=$(diff <(echo "$frontmatter") <(echo "$table")); then
  echo "check-agent-models: persona frontmatter and phase-2-agents.md table diverged:" >&2
  echo "$diff_out" | sed 's/^/  /' >&2
  rc=1
fi

# --- half 2: the rules that live only in prose ---
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-agent-models: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

need "$SKILL" 'explicit .?model' "SKILL.md requires an explicit model on every spawn"
need "$SKILL" 'subagent_type' "SKILL.md pins the subagent type"
need "$SKILL" 'extraAgents.*spawns at .?sonnet|no .?model.*spawns at .?sonnet' \
  "SKILL.md gives the default tier for a persona that declares none"
need "$AGENTS_DOC" 'Model per axis' "phase-2-agents.md documents the per-axis model split"
need "$AGENTS_DOC" 'spawns at .?sonnet' "phase-2-agents.md gives the extraAgents default"
need "$KEYS" 'persona frontmatter' "config-keys.md points verifierModel readers at the per-axis tiers"
need "$README" 'Every spawn names its model' "README documents the per-axis model split"

if [[ $rc -eq 0 ]]; then
  echo "check-agent-models: CLEAN ($(echo "$frontmatter" | wc -l | tr -d ' ') axes pinned)"
else
  echo "check-agent-models: FAIL — see above." >&2
fi
exit $rc
