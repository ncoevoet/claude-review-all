#!/usr/bin/env bash
# check-rule-packs.sh — release gate: every language rule pack under
# skills/review-all/rules/ is well-formed.
#
# A pack with no `#### Do not report` section (or a token one) silently loses
# the precision half of the OCR technique this directory exists to reproduce —
# nothing at runtime would notice, since the orchestrator just injects
# whatever text is in the file. So the invariant is pinned here instead:
#   1. Every pack (README.md exempt) has a `#### Do not report` section.
#   2. That section has at least 4 bullet lines.
#   3. No pack exceeds 60 lines (README.md exempt, capped at 30).
#   4. Every pack file is non-empty and starts with a `#` heading.
#   5. At least 9 packs exist (fails loudly if someone deletes one).
#
# Usage: check-rule-packs.sh [rules-dir]
# An optional first argument points the gate at a different rules directory
# (used by the negative self-test; defaults to the real tree).
# Exit 0 = clean, 1 = a pack failed an assertion, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
RULES_DIR="${1:-$ROOT/skills/review-all/rules}"

[[ -d "$RULES_DIR" ]] || { echo "check-rule-packs: missing dir $RULES_DIR" >&2; exit 2; }

shopt -s nullglob
all_files=("$RULES_DIR"/*.md)
shopt -u nullglob
if [[ ${#all_files[@]} -eq 0 ]]; then
  echo "check-rule-packs: no .md files found in $RULES_DIR — extractor broken" >&2
  exit 2
fi

echo "check-rule-packs: checking rule packs in $RULES_DIR"

rc=0
pack_count=0

for f in "${all_files[@]}"; do
  base="$(basename "$f")"

  # --- assertion 4: non-empty, starts with a # heading (applies to all, incl. README) ---
  if [[ ! -s "$f" ]]; then
    echo "check-rule-packs: FAIL $base — file is empty" >&2
    rc=1
    continue
  fi
  first_line="$(head -n 1 "$f")"
  if [[ "$first_line" != \#* ]]; then
    echo "check-rule-packs: FAIL $base — does not start with a '#' heading (found: ${first_line:0:40})" >&2
    rc=1
  fi

  lines=$(wc -l < "$f" | tr -d ' ')

  if [[ "$base" == "README.md" ]]; then
    # --- assertion 3 (README variant): capped at 30 lines ---
    if [[ "$lines" -gt 30 ]]; then
      echo "check-rule-packs: FAIL README.md — $lines lines, exceeds the 30-line README cap" >&2
      rc=1
    fi
    continue
  fi

  pack_count=$((pack_count + 1))

  # --- assertion 3: hard cap 60 lines ---
  if [[ "$lines" -gt 60 ]]; then
    echo "check-rule-packs: FAIL $base — $lines lines, exceeds the 60-line pack cap" >&2
    rc=1
  fi

  # --- assertion 1: mandatory '#### Do not report' section ---
  section_line="$(grep -n '^#### Do not report$' "$f" | head -n 1 | cut -d: -f1)"
  if [[ -z "$section_line" ]]; then
    echo "check-rule-packs: FAIL $base — missing mandatory '#### Do not report' section" >&2
    rc=1
    continue
  fi

  # --- assertion 2: at least 4 bullet lines in that section ---
  bullets=$(tail -n "+$((section_line + 1))" "$f" | awk '/^#### /{exit} /^- /{c++} END{print c+0}')
  if [[ "$bullets" -lt 4 ]]; then
    echo "check-rule-packs: FAIL $base — '#### Do not report' has only $bullets bullet(s), need >= 4" >&2
    rc=1
  fi
done

# --- assertion 5: at least 9 packs exist ---
if [[ "$pack_count" -lt 9 ]]; then
  echo "check-rule-packs: FAIL — only $pack_count pack(s) found (README.md excluded), need >= 9" >&2
  rc=1
fi

if [[ $rc -eq 0 ]]; then
  echo "check-rule-packs: CLEAN ($pack_count packs checked)"
else
  echo "check-rule-packs: FAIL — see above ($pack_count packs checked)" >&2
fi
exit $rc
