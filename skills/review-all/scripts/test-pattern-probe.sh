#!/usr/bin/env bash
# test-pattern-probe.sh — Phase 0.6 test-file pattern detection.
# Reads up to 50 existing test files, infers location + naming + framework.
# Emits JSON: {"pattern":"co-located"|"separate-tree", "suffix":".spec.ts", "framework":"jest"}.

set -u
cd "${1:-.}"

# Sample plausible test file paths via git ls-files (cheap, no recursion).
mapfile -t candidates < <(git ls-files 2>/dev/null \
  | grep -E '(^|/)tests?/|\.(spec|test)\.(ts|tsx|js|jsx|py|rs|go|java|kt|rb)$' \
  | head -50)

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo '{"pattern":"unknown","suffix":"","framework":"unknown"}'
  exit 0
fi

# Pattern: co-located vs separate-tree
colocated=0; separate=0
for f in "${candidates[@]}"; do
  if [[ "$f" == */tests/* || "$f" == tests/* || "$f" == */test/* || "$f" == test/* ]]; then
    ((separate++))
  else
    ((colocated++))
  fi
done
pattern="co-located"
[[ $separate -gt $colocated ]] && pattern="separate-tree"

# Suffix: most common .X.ext
suffix=$(printf '%s\n' "${candidates[@]}" \
  | grep -oE '\.(spec|test)\.[a-z]+$' \
  | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
[[ -z "$suffix" ]] && suffix=""

# Framework guess
framework="unknown"
if [[ -f package.json ]]; then
  if grep -q '"jest"' package.json 2>/dev/null; then framework="jest"
  elif grep -qE '"vitest"|"@vitest/' package.json 2>/dev/null; then framework="vitest"
  elif grep -q '"mocha"' package.json 2>/dev/null; then framework="mocha"
  elif grep -qE '"karma"|jasmine' package.json 2>/dev/null; then framework="karma"
  elif grep -q '"playwright"' package.json 2>/dev/null; then framework="playwright"
  fi
elif [[ -f pyproject.toml || -f setup.cfg ]]; then
  framework="pytest"
elif [[ -f Cargo.toml ]]; then
  framework="cargo-test"
elif [[ -f go.mod ]]; then
  framework="go-test"
fi

printf '{"pattern":"%s","suffix":"%s","framework":"%s"}\n' "$pattern" "$suffix" "$framework"
