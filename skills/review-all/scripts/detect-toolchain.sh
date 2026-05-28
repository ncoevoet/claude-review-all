#!/usr/bin/env bash
# detect-toolchain.sh — Phase 0.3 + 0.4 language/framework/toolchain probe.
# Emits JSON to stdout describing detected ecosystem and discovered commands.
# Pure read-only; never executes test/lint/typecheck — it only locates them.

set -u
cd "${1:-.}" || exit 1

emit_kv() { printf '"%s":%s' "$1" "$2"; }
json_str() { printf '"%s"' "${1//\"/\\\"}"; }

ecosystem=""
framework=""
test_cmd=""
lint_cmd=""
typecheck_cmd=""
build_cmd=""

read_package_json_script() {
  local key=$1
  [[ -f package.json ]] || return 0
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$key" '.scripts[$k] // empty' package.json 2>/dev/null
  elif command -v node >/dev/null 2>&1; then
    node -e 'const s=((require("./package.json").scripts)||{})[process.argv[1]];process.stdout.write(s||"")' "$key" 2>/dev/null
  else
    # jq and node both absent: best-effort scrape of the "scripts" block so JS
    # test/lint/build gates do not silently vanish on a minimal toolchain.
    sed -n '/"scripts"[[:space:]]*:/,/}/p' package.json 2>/dev/null \
      | grep -oE "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
      | head -1 \
      | sed -E "s/.*:[[:space:]]*\"([^\"]*)\"/\1/"
  fi
}

# JS / TS
if [[ -f package.json ]]; then
  ecosystem="js"
  if [[ -f angular.json ]]; then framework="angular"
  elif [[ -f next.config.js || -f next.config.mjs || -f next.config.ts ]]; then framework="next"
  elif [[ -f vite.config.js || -f vite.config.ts || -f vite.config.mjs ]]; then framework="vite"
  elif [[ -f nuxt.config.js || -f nuxt.config.ts ]]; then framework="nuxt"
  elif [[ -f svelte.config.js ]]; then framework="svelte"
  else framework="js"
  fi
  test_cmd=$(read_package_json_script test)
  lint_cmd=$(read_package_json_script lint)
  typecheck_cmd=$(read_package_json_script typecheck)
  build_cmd=$(read_package_json_script build)
  [[ -z "$typecheck_cmd" && -f tsconfig.json ]] && typecheck_cmd="npx tsc --noEmit"

# Python
elif [[ -f pyproject.toml || -f setup.cfg || -f requirements.txt ]]; then
  ecosystem="python"
  framework="python"
  command -v pytest >/dev/null 2>&1 && test_cmd="pytest"
  if command -v ruff >/dev/null 2>&1; then lint_cmd="ruff check ."
  elif command -v flake8 >/dev/null 2>&1; then lint_cmd="flake8"
  fi
  if command -v mypy >/dev/null 2>&1; then typecheck_cmd="mypy ."
  elif command -v pyright >/dev/null 2>&1; then typecheck_cmd="pyright"
  fi

# Rust
elif [[ -f Cargo.toml ]]; then
  ecosystem="rust"
  framework="rust"
  test_cmd="cargo test"
  lint_cmd="cargo clippy"
  typecheck_cmd="cargo check"
  build_cmd="cargo build"

# Go
elif [[ -f go.mod ]]; then
  ecosystem="go"
  framework="go"
  test_cmd="go test ./..."
  command -v golangci-lint >/dev/null 2>&1 && lint_cmd="golangci-lint run"
  typecheck_cmd="go vet ./..."
  build_cmd="go build ./..."

# Java/Kotlin (Maven)
elif [[ -f pom.xml ]]; then
  ecosystem="java"
  framework="maven"
  test_cmd="mvn test"
  build_cmd="mvn package -DskipTests"

# Java/Kotlin (Gradle)
elif [[ -f build.gradle || -f build.gradle.kts ]]; then
  ecosystem="java"
  framework="gradle"
  test_cmd="gradle test"
  build_cmd="gradle build -x test"

# C#/.NET
elif compgen -G "*.sln" >/dev/null || compgen -G "*.csproj" >/dev/null; then
  ecosystem="dotnet"
  framework="dotnet"
  test_cmd="dotnet test"
  build_cmd="dotnet build"

# Ruby
elif [[ -f Gemfile ]]; then
  ecosystem="ruby"
  framework="ruby"
  test_cmd="bundle exec rspec"
  command -v rubocop >/dev/null 2>&1 && lint_cmd="rubocop"

# PHP
elif [[ -f composer.json ]]; then
  ecosystem="php"
  framework="php"
  test_cmd="vendor/bin/phpunit"
fi

printf '{'
emit_kv ecosystem "$(json_str "$ecosystem")"
printf ','
emit_kv framework "$(json_str "$framework")"
printf ','
emit_kv test "$(json_str "$test_cmd")"
printf ','
emit_kv lint "$(json_str "$lint_cmd")"
printf ','
emit_kv typecheck "$(json_str "$typecheck_cmd")"
printf ','
emit_kv build "$(json_str "$build_cmd")"
printf '}\n'
