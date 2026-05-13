#!/usr/bin/env bash
# run-evals.sh — minimal eval runner for /review-all.
#
# For each evals/*.json scenario:
#   1. Print the scenario id.
#   2. Print a checklist of expected behaviors (positive + negative).
#   3. Prompt the user to run `/review-all` against the described fixture in
#      Claude Code and paste the resulting report path.
#   4. Grep the report for each expected_behavior keyword; mark PASS/FAIL.
#
# This is a thin, dependency-light runner — no synthetic-diff fabrication,
# no Claude Code subprocessing. Building those is future work; the JSON
# files are designed to remain valid once a richer runner exists.

set -u
cd "$(dirname "$0")/.."   # skill root: skills/review-all/

filter=${1:-}
fail=0

for f in evals/*.json; do
  id=$(basename "$f" .json)
  case "$id" in
    README*) continue ;;
  esac
  [[ -n "$filter" && "$id" != "$filter"* ]] && continue

  echo
  echo "=== eval: $id ==="
  echo "Scenario file: $f"
  echo

  echo "Expected behavior:"
  python3 -c "import json,sys; d=json.load(open('$f')); [print(' +', x) for x in d.get('expected_behavior',[])]"

  echo "Expected NOT behavior:"
  python3 -c "import json,sys; d=json.load(open('$f')); [print(' -', x) for x in d.get('expected_not_behavior',[])]"

  echo
  read -r -p "Path to /review-all report for this scenario (blank to skip): " report
  [[ -z "$report" ]] && { echo "SKIPPED"; continue; }
  [[ ! -f "$report" ]] && { echo "FAIL: report not found at $report"; fail=$((fail+1)); continue; }

  miss=0
  while IFS= read -r line; do
    # Extract noun phrases to grep — first 3 words is usually enough.
    needle=$(echo "$line" | awk '{print $1, $2, $3}')
    if ! grep -q -i -F "$needle" "$report"; then
      echo "  ✗ missing in report: $line"
      miss=$((miss+1))
    fi
  done < <(python3 -c "import json; d=json.load(open('$f')); [print(x) for x in d.get('expected_behavior',[])]")

  if [[ $miss -eq 0 ]]; then
    echo "PASS"
  else
    echo "FAIL ($miss expected behaviors not found)"
    fail=$((fail+1))
  fi
done

echo
if [[ $fail -eq 0 ]]; then
  echo "all evals passed"
  exit 0
else
  echo "$fail eval(s) failed"
  exit 1
fi
