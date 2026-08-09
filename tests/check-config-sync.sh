#!/usr/bin/env bash
# check-config-sync.sh — release gate: SKILL.md's inline config schema must list
# exactly the keys documented in references/config-keys.md.
#
# These two lists drifted apart silently once already (SKILL.md's Step 0.2 block
# lagged nine keys behind the table), and a per-key grep list would drift the same
# way. So this gate is a mechanical SET DIFF: it extracts key names from both
# sources and fails on any asymmetry, which makes the drift class unrepeatable.
# Exit 0 = sets identical, 1 = a key is missing on one side, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
KEYS="$ROOT/skills/review-all/references/config-keys.md"

for f in "$SKILL" "$KEYS"; do
  [[ -f "$f" ]] || { echo "check-config-sync: missing file $f" >&2; exit 2; }
done

echo "check-config-sync: comparing SKILL.md Step 0.2 schema against config-keys.md table"

table_keys="$(sed -n 's/^| *`\([A-Za-z][A-Za-z0-9_]*\)` *|.*/\1/p' "$KEYS" | sort -u)"
schema_keys="$(awk '/^```jsonc$/{inblock=1; next} inblock && /^```$/{exit} inblock' "$SKILL" \
  | sed -n 's/^ *"\([A-Za-z][A-Za-z0-9_]*\)" *:.*/\1/p' | sort -u)"

if [[ -z "$table_keys" ]]; then
  echo "check-config-sync: extracted no keys from config-keys.md — extractor broken" >&2
  exit 2
fi
if [[ -z "$schema_keys" ]]; then
  echo "check-config-sync: extracted no keys from SKILL.md — extractor broken" >&2
  exit 2
fi

rc=0
missing_in_skill="$(comm -23 <(echo "$table_keys") <(echo "$schema_keys"))"
missing_in_table="$(comm -13 <(echo "$table_keys") <(echo "$schema_keys"))"

if [[ -n "$missing_in_skill" ]]; then
  echo "check-config-sync: documented in config-keys.md but ABSENT from SKILL.md schema:" >&2
  echo "$missing_in_skill" | sed 's/^/  - /' >&2
  rc=1
fi
if [[ -n "$missing_in_table" ]]; then
  echo "check-config-sync: present in SKILL.md schema but UNDOCUMENTED in config-keys.md:" >&2
  echo "$missing_in_table" | sed 's/^/  - /' >&2
  rc=1
fi

if [[ $rc -eq 0 ]]; then
  echo "check-config-sync: CLEAN ($(echo "$table_keys" | wc -l | tr -d ' ') keys in sync)"
else
  echo "check-config-sync: FAIL — config key sets diverged above." >&2
fi
exit $rc
