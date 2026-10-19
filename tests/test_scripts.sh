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

echo "discover.sh (one-call discovery + rules cache)"
drepo=$(mktemp -d)
( cd "$drepo" && git init -q && git config user.email t@t && git config user.name t \
    && printf '# Rules: never use eval\n' > CLAUDE.md \
    && printf '{"scripts":{"test":"jest"}}\n' > package.json \
    && git add -A && git commit -qm init ) >/dev/null 2>&1
out=$(bash "$SCRIPTS/discover.sh" "$drepo")
assert_json "$out" "emits valid JSON"
assert_in "$out" '"status":"MISS","reason":"no-cache"' "fresh repo → MISS(no-cache)"
assert_in "$out" '"test":"jest"' "toolchain probed through (never cached)"
key=$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["cacheKey"])')
key2=$(bash "$SCRIPTS/discover.sh" "$drepo" | python3 -c 'import json,sys; print(json.load(sys.stdin)["cacheKey"])')
assert_eq "$key2" "$key" "cacheKey stable across runs"
mkdir -p "$drepo/.claude/cache"
printf '{"schemaVersion":2,"cacheKey":"%s","rules":{"global":"never use eval"},"ruleSources":["CLAUDE.md"]}' "$key" \
  > "$drepo/.claude/cache/review-all-profile.json"
out=$(bash "$SCRIPTS/discover.sh" "$drepo")
assert_in "$out" '"status":"HIT"' "valid seeded cache → HIT"
assert_in "$out" 'never use eval' "HIT embeds cachedProfile rules"
echo extra >> "$drepo/CLAUDE.md"
out=$(bash "$SCRIPTS/discover.sh" "$drepo")
assert_in "$out" '"reason":"key-mismatch"' "CLAUDE.md edit → MISS(key-mismatch)"
( cd "$drepo" && git checkout -q CLAUDE.md )
printf '{"claudeMdHash":"abc","toolchain":{"test":"mvn test"}}' > "$drepo/.claude/cache/review-all-profile.json"
out=$(bash "$SCRIPTS/discover.sh" "$drepo")
assert_in "$out" '"reason":"schema"' "legacy claudeMdHash file → MISS(schema)"
printf '{broken' > "$drepo/.claude/cache/review-all-profile.json"
out=$(bash "$SCRIPTS/discover.sh" "$drepo")
assert_in "$out" '"reason":"unreadable"' "corrupt JSON → MISS(unreadable)"
printf '{"schemaVersion":2,"cacheKey":"%s","rules":{"global":"x"}}' "$key" \
  > "$drepo/.claude/cache/review-all-profile.json"
if touch -d '8 days ago' "$drepo/.claude/cache/review-all-profile.json" 2>/dev/null; then
  out=$(bash "$SCRIPTS/discover.sh" "$drepo")
  assert_in "$out" '"reason":"expired"' "8-day-old cache → MISS(expired)"
else
  ok "touch -d unsupported — expired test skipped"
fi
echo local-rule > "$drepo/CLAUDE.local.md"
key3=$(bash "$SCRIPTS/discover.sh" "$drepo" | python3 -c 'import json,sys; print(json.load(sys.stdin)["cacheKey"])')
[[ "$key3" != "$key" ]] && ok "untracked CLAUDE.local.md changes cacheKey" || no "untracked CLAUDE.local.md changes cacheKey"

echo "run-evals-headless.sh (REVIEW_ALL_EVAL_KEEP_DIR parity, stubbed claude)"
stub=$(mktemp -d "${TMPDIR:-/tmp}/review-all-stub.XXXXXX")
cat > "$stub/claude" <<'STUB'
#!/usr/bin/env bash
echo "called" >> "$STUB_LOG"
if [[ "${2:-}" == Run* ]]; then
  printf '## Review\n\n<!-- review-all-severity: {"critical":0,"important":1,"decision":0,"suggestion":0,"question":0} -->\n'
else
  cat >/dev/null
  echo PASS
fi
STUB
chmod +x "$stub/claude"
export STUB_LOG="$stub/calls.log"
RUNNER="$SCRIPTS/run-evals-headless.sh"
out_a=$(PATH="$stub:$PATH" REVIEW_ALL_EVAL_RUNS=2 bash "$RUNNER" 01 2>/dev/null); rc_a=$?
keep="$stub/keep"
out_b=$(PATH="$stub:$PATH" REVIEW_ALL_EVAL_RUNS=2 REVIEW_ALL_EVAL_KEEP_DIR="$keep" bash "$RUNNER" 01 2>/dev/null); rc_b=$?
assert_eq "$out_b" "$out_a" "KEEP_DIR set: stdout identical to unset"
assert_eq "$rc_b" "$rc_a" "KEEP_DIR set: exit status identical to unset"
assert_in "$out_a" "RESULT,01" "stubbed runner produced a RESULT line"
cdir=$(ls -d "$keep"/01*/ | head -n 1); cdir="${cdir%/}"
for f in CONFIG.txt run1.report.md run1.judge.txt run2.report.md run2.judge.txt; do
  [[ -s "$cdir/$f" ]] && ok "kept $f" || no "kept $f"
done
assert_in "$(cat "$cdir/run2.report.md")" "review-all-severity" "kept report has the report text"
assert_eq "$(cat "$cdir/run1.judge.txt")" "PASS" "kept judge output is the judge text"
assert_in "$(cat "$cdir/CONFIG.txt")" "CONFIG,model=" "CONFIG.txt carries the CONFIG line"
assert_in "$(cat "$cdir/CONFIG.txt")" "skill_head=" "CONFIG.txt records skill HEAD"
assert_in "$(cat "$cdir/CONFIG.txt")" "skill_dirty=" "CONFIG.txt records dirty flag"
assert_in "$(cat "$cdir/CONFIG.txt")" "installed_cache=" "CONFIG.txt records installed cache path"
: > "$STUB_LOG"
err=$(PATH="$stub:$PATH" REVIEW_ALL_EVAL_KEEP_DIR="$keep" bash "$RUNNER" 01 2>&1 >/dev/null); rc_c=$?
assert_eq "$rc_c" "3" "non-empty keep dir: exit 3"
assert_in "$err" "refusing to overwrite" "non-empty keep dir: stderr explains"
[[ ! -s "$STUB_LOG" ]] && ok "refusal happens before any claude call" || no "refusal happens before any claude call"
# Multi-case filter: evidence on the SECOND selected case must refuse before the first spends a call.
keep2="$stub/keep2"; mkdir -p "$keep2/91-claude-md-stale-claim"; echo x > "$keep2/91-claude-md-stale-claim/old"
: > "$STUB_LOG"
err=$(PATH="$stub:$PATH" REVIEW_ALL_EVAL_KEEP_DIR="$keep2" bash "$RUNNER" 9 2>&1 >/dev/null); rc_d=$?
assert_eq "$rc_d" "3" "non-empty later case dir: exit 3"
assert_in "$err" "91-claude-md-stale-claim" "non-empty later case dir: names it"
[[ ! -s "$STUB_LOG" ]] && ok "later-case refusal: zero claude calls" || no "later-case refusal: zero claude calls"
[[ ! -e "$keep2/90-review-md-raised-bar" ]] && ok "later-case refusal: earlier case dir not created" || no "later-case refusal: earlier case dir not created"
rm -rf "$stub"

echo
echo "scripts: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
