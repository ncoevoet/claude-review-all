#!/usr/bin/env bash
# Dependency-free tests for the review-all shell scripts (no bats required).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../skills/review-all/scripts"
pass=0; fail=0
ok(){ pass=$((pass+1)); printf '  ok   %s\n' "$1"; }
no(){ fail=$((fail+1)); printf '  FAIL %s\n' "$1"; }
assert_eq(){ [[ "$1" == "$2" ]] && ok "$3" || { no "$3"; printf '       expected=[%s] got=[%s]\n' "$2" "$1"; }; }
assert_in(){ [[ "$1" == *"$2"* ]] && ok "$3" || { no "$3"; printf '       [%s] not found in: %s\n' "$2" "$1"; }; }
assert_json(){ printf '%s' "$1" | python3 -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1 && ok "$2" || no "$2"; }

echo "preflight.sh"
out=$(bash "$SCRIPTS/preflight.sh"); rc=$?
assert_json "$out" "emits valid JSON"
assert_in "$out" '"git":true' "reports git available"
assert_eq "$rc" "0" "exits 0 when git present"

echo "detect-toolchain.sh (jq path)"
tmp=$(mktemp -d)
cat > "$tmp/package.json" <<'JSON'
{"scripts":{"test":"jest --ci","build":"tsc -b","lint":"eslint ."}}
JSON
out=$(bash "$SCRIPTS/detect-toolchain.sh" "$tmp")
assert_json "$out" "emits valid JSON"
assert_in "$out" '"ecosystem":"js"' "detects js ecosystem"
assert_in "$out" '"test":"jest --ci"' "reads scripts.test (jq branch)"

echo "detect-toolchain.sh (node fallback expression — F2)"
if command -v node >/dev/null 2>&1; then
  fb=$(cd "$tmp" && node -e 'const s=((require("./package.json").scripts)||{})[process.argv[1]];process.stdout.write(s||"")' build)
  assert_eq "$fb" "tsc -b" "node fallback reads scripts.build"
else
  ok "node absent — fallback expression test skipped"
fi

echo "detect-toolchain.sh (empty dir self-skips)"
empty=$(mktemp -d)
out=$(bash "$SCRIPTS/detect-toolchain.sh" "$empty")
assert_in "$out" '"ecosystem":""' "empty dir → empty ecosystem"

echo "dev-server-probe.sh"
out=$(bash "$SCRIPTS/dev-server-probe.sh" "59123,59124")
assert_json "$out" "emits valid JSON"
assert_in "$out" '"open":[]' "unlikely ports reported closed"

echo "test-pattern-probe.sh"
repo=$(mktemp -d)
( cd "$repo" && git init -q && git config user.email t@t && git config user.name t \
    && mkdir -p src && echo "x" > src/a.spec.ts && git add -A ) >/dev/null 2>&1
out=$(bash "$SCRIPTS/test-pattern-probe.sh" "$repo")
assert_json "$out" "emits valid JSON"
assert_in "$out" '.spec.ts' "detects .spec.ts suffix"
assert_in "$out" 'co-located' "classifies co-located layout"

echo
echo "scripts: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
