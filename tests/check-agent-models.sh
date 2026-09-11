#!/usr/bin/env bash
# check-agent-models.sh — release gate: every spawn in the skill declares an
# explicit model — the Phase 2 axes, the Phase 4 follow-up agents, and the verifier.
#
# A spawn with no `model` does not fail — it silently inherits the session tier,
# which is exactly how ten axes ended up on the same expensive model, mechanical
# ones included. Nothing at runtime can detect that, so the invariant has to be
# pinned here. Three halves:
#   1. MECHANICAL set diff — each agents/NN-*.md frontmatter `model:` must equal
#      the tier the phase-2-agents.md table gives that persona. A per-file grep
#      list would drift the way the config-key lists once did; a set diff cannot.
#   2. Prose invariants — the never-spawn-without-a-model rule and the default
#      for an extraAgents persona live only in docs.
#   3. The spawn sites half 1 cannot see. The three Phase 4 agents (Deep-dive,
#      Ask-a-question, test generator) have no persona file, and the verifier has
#      one but deliberately no `model:` frontmatter (one persona, config-driven
#      tier). Both shipped unpinned once because nothing checked them: an Agent
#      spawn carrying no model — or `inherit`, which is not a model id — is
#      refused outright by a harness that validates the model on a spawn.
# Exit 0 = clean, 1 = a declaration or invariant is missing/divergent, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
AGENTS_DOC="$ROOT/skills/review-all/references/phase-2-agents.md"
KEYS="$ROOT/skills/review-all/references/config-keys.md"
AGENTS_DIR="$ROOT/skills/review-all/agents"
README="$ROOT/README.md"
MENU="$ROOT/skills/review-all/references/phase-4-menu.md"
VERIFIER="$ROOT/skills/review-all/agents/verifier.md"

for f in "$SKILL" "$AGENTS_DOC" "$KEYS" "$README" "$MENU" "$VERIFIER"; do
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

# --- half 3: the spawn sites with no persona frontmatter ---
# Phase 4: every "Spawn ... agent" line must carry a `model: <tier>`.
p4_spawns="$(grep -cE 'Spawn [A-Za-z ]+agent' "$MENU" || true)"
p4_pinned="$(grep -cE 'Spawn .*`model: (haiku|sonnet|opus)`' "$MENU" || true)"
if [[ "$p4_spawns" -ne "$p4_pinned" || "$p4_pinned" -lt 3 ]]; then
  echo "check-agent-models: phase-4-menu.md has $p4_spawns spawn site(s) but $p4_pinned pinned (expected equal, >=3):" >&2
  grep -nE 'Spawn [A-Za-z ]+agent' "$MENU" \
    | grep -vE 'Spawn .*`model: (haiku|sonnet|opus)`' | sed 's/^/  - /' >&2
  rc=1
fi
if grep -qiE 'inherits the session tier' "$MENU"; then
  echo "check-agent-models: phase-4-menu.md still lets a spawn inherit the session tier" >&2
  rc=1
fi

# verifierModel: an explicit tier only. `inherit` is not a model id, so a spawn
# carrying it is refused; the row must offer haiku|sonnet|opus and nothing else.
vm_row="$(grep -E '^\| *`verifierModel` *\|' "$KEYS" || true)"
if [[ -z "$vm_row" ]]; then
  echo "check-agent-models: no verifierModel row found in config-keys.md" >&2
  rc=1
else
  for tier in haiku sonnet opus; do
    grep -q "\"$tier\"" <<<"$vm_row" || {
      echo "check-agent-models: verifierModel row does not offer \"$tier\"" >&2; rc=1; }
  done
  if grep -qE '(Choices|choices)[^|]*inherit' <<<"$vm_row"; then
    echo "check-agent-models: verifierModel still offers \"inherit\" — not a model id, rejected on spawn" >&2
    rc=1
  fi
fi
need "$KEYS" 'no .?.?inherit.?.? value' "config-keys.md records why verifierModel has no inherit"
need "$VERIFIER" 'verifierModel' "verifier.md names the config tier it spawns at"
need "$MENU" 'Every Phase 4 spawn names its model' "phase-4-menu.md states the Phase 4 spawn contract"
need "$SKILL" 'Phase 4 spawn' "SKILL.md extends the spawn contract to Phase 4"

if [[ $rc -eq 0 ]]; then
  echo "check-agent-models: CLEAN ($(echo "$frontmatter" | wc -l | tr -d ' ') axes + $p4_pinned phase-4 spawns + verifier pinned)"
else
  echo "check-agent-models: FAIL — see above." >&2
fi
exit $rc
