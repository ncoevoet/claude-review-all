#!/usr/bin/env bash
# check-agent-selection.sh — release gate: the deterministic pre-dispatch
# selection layer and the docs that describe it cannot drift apart.
#
# Phase 2's spawn set used to be prose the orchestrator judged. It is now a
# computation (scripts/select-agents.py over scripts/file-classes.json), and a
# computation has a failure mode prose did not: the table can say one thing
# while the script does another, and nothing at runtime notices. Five halves:
#   1. SET DIFF — the axis ids select-agents.py emits vs the persona files in
#      agents/. An axis that exists in one and not the other is either an agent
#      that can never spawn or a spawn with no persona.
#   2. SET DIFF — the file classes the spawn-condition table names vs the
#      classes file-classes.json can actually assign. A table row gated on a
#      class nothing produces is an axis that silently never runs.
#   3. SET DIFF — the exclusion reasons select-files.py emits vs the reasons
#      SKILL.md and phase-3-report.md promise the reader.
#   4. The two exclusions this project deliberately does NOT make. The
#      comparable tool this layer is modelled on excludes every test file and
#      every .md; adopting either verbatim would delete the whole subject of
#      agent 08 and zero out this repo's Markdown eval fixtures. A future edit
#      that pastes in a fuller upstream list must fail here, loudly.
#   5. Every rule pack named in file-classes.json exists on disk.
# Exit 0 = clean, 1 = a set diverged or an invariant broke, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
AGENTS_DOC="$ROOT/skills/review-all/references/phase-2-agents.md"
REPORT_DOC="$ROOT/skills/review-all/references/phase-3-report.md"
AGENTS_DIR="$ROOT/skills/review-all/agents"
RULES_DIR="$ROOT/skills/review-all/rules"
SCRIPTS="$ROOT/skills/review-all/scripts"
CLASSES="$SCRIPTS/file-classes.json"
SELECT_FILES="$SCRIPTS/select-files.py"
SELECT_AGENTS="$SCRIPTS/select-agents.py"

for f in "$SKILL" "$AGENTS_DOC" "$REPORT_DOC" "$CLASSES" "$SELECT_FILES" "$SELECT_AGENTS"; do
  [[ -f "$f" ]] || { echo "check-agent-selection: missing file $f" >&2; exit 2; }
done
command -v python3 >/dev/null || { echo "check-agent-selection: python3 required" >&2; exit 2; }

echo "check-agent-selection: comparing the selection scripts against the docs that describe them"
rc=0

# --- half 1: axis ids emitted by the selector vs persona files on disk ---
script_axes="$(printf '{"reviewable":[],"excluded":[],"counts":{}}' \
  | python3 "$SELECT_AGENTS" 2>/dev/null \
  | python3 -c 'import json,sys; print("\n".join(sorted(json.load(sys.stdin)["agents"])))')"
persona_axes="$(for f in "$AGENTS_DIR"/[0-9][0-9]-*.md; do basename "$f" .md; done | sort)"

if [[ -z "$script_axes" ]]; then
  echo "check-agent-selection: select-agents.py emitted no axes — extractor or script broken" >&2
  exit 2
fi
only_script="$(comm -23 <(echo "$script_axes") <(echo "$persona_axes"))"
only_persona="$(comm -13 <(echo "$script_axes") <(echo "$persona_axes"))"
if [[ -n "$only_script" ]]; then
  echo "check-agent-selection: select-agents.py can spawn axes with NO persona file:" >&2
  echo "$only_script" | sed 's/^/  - /' >&2; rc=1
fi
if [[ -n "$only_persona" ]]; then
  echo "check-agent-selection: persona files the selector can never spawn:" >&2
  echo "$only_persona" | sed 's/^/  - /' >&2; rc=1
fi

# --- half 2: classes the spawn-condition table gates on vs classes the data file assigns ---
assigned_classes="$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
out=set()
for v in d.get("classes",{}).values(): out.update(v)
print("\n".join(sorted(out)))' "$CLASSES")"
table_classes="$(sed -n '/^| # | Agent | Persona | Model | Spawn condition |/,/^$/p' "$AGENTS_DOC" \
  | grep -o 'class `[a-z0-9]*`' | sed 's/class `//; s/`//' | sort -u)"

if [[ -z "$table_classes" ]]; then
  echo "check-agent-selection: extracted no classes from the phase-2-agents.md table — extractor broken" >&2
  exit 2
fi
undefined="$(comm -13 <(echo "$assigned_classes") <(echo "$table_classes"))"
if [[ -n "$undefined" ]]; then
  echo "check-agent-selection: spawn conditions gate on classes file-classes.json never assigns:" >&2
  echo "$undefined" | sed 's/^/  - /' >&2; rc=1
fi

# --- half 3: exclusion reasons the script emits vs the reasons the docs promise ---
script_reasons="$(printf '[]' | python3 "$SELECT_FILES" 2>/dev/null \
  | python3 -c 'import json,sys; print("\n".join(sorted(json.load(sys.stdin)["counts"]["excluded"])))')"
if [[ -z "$script_reasons" ]]; then
  echo "check-agent-selection: select-files.py emitted no exclusion-reason keys on empty input" >&2
  echo "  counts.excluded must carry every reason key even at zero, or a 0 reads as a missing key." >&2
  rc=1
else
  for r in $script_reasons; do
    grep -q "\`$r\`" "$SKILL" || { echo "check-agent-selection: reason '$r' emitted but undocumented in SKILL.md" >&2; rc=1; }
  done
fi
grep -q 'Files excluded' "$REPORT_DOC" || {
  echo "check-agent-selection: phase-3-report.md must report excluded files — silent dropping is this layer's failure mode" >&2; rc=1; }
grep -q 'Agents skipped' "$REPORT_DOC" || {
  echo "check-agent-selection: phase-3-report.md must name skipped axes and their reason" >&2; rc=1; }

# --- half 4: the two exclusions this project deliberately does NOT make ---
bad_excludes="$(python3 -c '
import json,sys,re
pats=json.load(open(sys.argv[1])).get("exclude",[])
bad=[p for p in pats if re.search(r"test|spec|\bTest\b|\.md\b|\.mdx\b", p, re.I)]
print("\n".join(bad))' "$CLASSES")"
if [[ -n "$bad_excludes" ]]; then
  echo "check-agent-selection: file-classes.json 'exclude' contains a test-file or Markdown pattern:" >&2
  echo "$bad_excludes" | sed 's/^/  - /' >&2
  echo "  Test files are the subject of agent 08-test-quality and .md is the subject of the" >&2
  echo "  90/91 eval fixtures. Classify them, never exclude them." >&2
  rc=1
fi
grep -q 'never dropped\|never dropped;\|classified' "$SKILL" || true
grep -q 'test files are \*classified\*' "$SKILL" || {
  echo "check-agent-selection: SKILL.md must state that test files are classified, not excluded" >&2; rc=1; }

# --- half 5: every rule pack the data file names exists ---
packs="$(python3 -c '
import json,sys
print("\n".join(sorted(set(json.load(open(sys.argv[1])).get("rule_packs",{}).values()))))' "$CLASSES")"
pack_n=0
for p in $packs; do
  pack_n=$((pack_n+1))
  [[ -f "$RULES_DIR/$p" ]] || { echo "check-agent-selection: rule pack '$p' referenced but missing from rules/" >&2; rc=1; }
done

axis_n="$(echo "$script_axes" | wc -l | tr -d ' ')"
class_n="$(echo "$assigned_classes" | wc -l | tr -d ' ')"
if [[ $rc -eq 0 ]]; then
  echo "check-agent-selection: CLEAN ($axis_n axes, $class_n classes, $pack_n rule packs checked)"
else
  echo "check-agent-selection: FAIL — see the divergences above." >&2
fi
exit $rc
