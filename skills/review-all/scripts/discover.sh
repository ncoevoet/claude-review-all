#!/usr/bin/env bash
# discover.sh — Phase 0.0 one-call project discovery.
# Composes preflight.sh + detect-toolchain.sh + test-pattern-probe.sh and adds
# the rules-cache check, so Phase 0 costs exactly one tool round trip on every
# run regardless of cache state. Toolchain data is always probed fresh — only
# the LLM-extracted global rules (step 0.5) are ever cached.
#
# Emits one JSON object:
# {
#   "schemaVersion": 2,
#   "available": {"git":true,...},            // preflight.sh output, verbatim
#   "toolchain": {"ecosystem":...,"test":...},// detect-toolchain.sh output, verbatim
#   "testPattern": {"pattern":...},           // test-pattern-probe.sh output, verbatim
#   "codegraphIndex": true|false,             // .codegraph/ directory present
#   "cacheKey": "<sha256>",                   // key for .claude/cache/review-all-profile.json
#   "cache": {"status":"HIT"|"MISS","reason":null|"no-cache|key-mismatch|schema|expired|unreadable"},
#   "cachedProfile": {...}|null               // profile file contents iff HIT
# }
#
# Cache key = sha256 over "v2\n" + sorted "<path> <sha256(content)>" lines for
# every CLAUDE.md in the repo (tracked + untracked-unignored, via git ls-files)
# plus root CLAUDE.local.md (conventionally gitignored, hence listed explicitly).
# A manifest of per-file hashes — not concatenated contents — so renames and
# added empty files change the key. ~/.claude/CLAUDE.md is deliberately NOT in
# the key: it is user memory, not project conventions, and is never cached.
#
# HIT requires ALL of: file exists, parses as JSON (python3, else jq; neither
# available -> MISS unreadable), schemaVersion == 2, cacheKey equal, file mtime
# <= 7 days (max-age backstop for staleness the key cannot see, e.g. an edited
# guide referenced from CLAUDE.md). Legacy claudeMdHash-era files fail the
# schemaVersion check -> MISS schema.
#
# Exit codes: 0 normal, 2 git binary missing (preflight abort contract).

set -u

SCHEMA_VERSION=2
MAX_AGE_DAYS=7
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

cd "${1:-.}" || exit 1

preflight_json=$(bash "$SCRIPT_DIR/preflight.sh")
preflight_rc=$?
if [[ $preflight_rc -eq 2 ]]; then
  printf '{"schemaVersion":%s,"available":%s,"error":"git missing"}\n' \
    "$SCHEMA_VERSION" "$preflight_json"
  exit 2
fi

# Operate from the repo toplevel so subdir and worktree invocations agree on
# paths and on the .claude/cache location. Outside a git repo, stay in cwd —
# the skill fails later at diff resolution with its own clear error.
if top=$(git rev-parse --show-toplevel 2>/dev/null); then
  cd "$top" || exit 1
fi

toolchain_json=$(bash "$SCRIPT_DIR/detect-toolchain.sh" "$PWD")
testpattern_json=$(bash "$SCRIPT_DIR/test-pattern-probe.sh" "$PWD")

codegraph=false
[[ -d .codegraph ]] && codegraph=true

sha256_stdin() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  else
    shasum -a 256 | awk '{print $1}'
  fi
}

cache_key=$(
  {
    printf 'v%s\n' "$SCHEMA_VERSION"
    {
      git ls-files --cached --others --exclude-standard -- 'CLAUDE.md' '*/CLAUDE.md' 2>/dev/null
      [[ -f CLAUDE.local.md ]] && echo CLAUDE.local.md
    } | LC_ALL=C sort -u | while IFS= read -r f; do
      [[ -f $f ]] || continue
      printf '%s %s\n' "$f" "$(sha256_stdin < "$f")"
    done
  } | sha256_stdin
)

CACHE_FILE=".claude/cache/review-all-profile.json"

# json_field FILE KEY — prints the top-level scalar value of KEY, empty if
# absent/unparseable. Also doubles as the parse check (rc != 0 on bad JSON).
json_field() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$1" "$2" <<'PY'
import json, sys
try:
    with open(sys.argv[1]) as fh:
        doc = json.load(fh)
except Exception:
    sys.exit(1)
val = doc.get(sys.argv[2], "")
print(val if val is not None else "")
PY
  elif command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$2" '.[$k] // empty' "$1" 2>/dev/null
  else
    return 1
  fi
}

status=MISS
reason=no-cache
cached_profile=null
if [[ -f $CACHE_FILE ]]; then
  if ! cached_schema=$(json_field "$CACHE_FILE" schemaVersion); then
    reason=unreadable
  elif [[ "$cached_schema" != "$SCHEMA_VERSION" ]]; then
    reason=schema
  elif [[ "$(json_field "$CACHE_FILE" cacheKey)" != "$cache_key" ]]; then
    reason=key-mismatch
  elif [[ -n $(find "$CACHE_FILE" -mtime +"$MAX_AGE_DAYS" -print -quit 2>/dev/null) ]]; then
    reason=expired
  else
    status=HIT
    reason=""
    cached_profile=$(cat "$CACHE_FILE")
  fi
fi

reason_json=null
[[ -n "$reason" ]] && reason_json="\"$reason\""

printf '{"schemaVersion":%s,"available":%s,"toolchain":%s,"testPattern":%s,"codegraphIndex":%s,"cacheKey":"%s","cache":{"status":"%s","reason":%s},"cachedProfile":%s}\n' \
  "$SCHEMA_VERSION" "$preflight_json" "$toolchain_json" "$testpattern_json" \
  "$codegraph" "$cache_key" "$status" "$reason_json" "$cached_profile"
