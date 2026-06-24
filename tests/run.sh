#!/usr/bin/env bash
# Run the full deterministic test suite (shell scripts + Python).
# No network / API key needed — safe for CI.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
rc=0

echo "== anonymization gate =="
bash "$HERE/check-anonymization.sh" || rc=1

echo
echo "== phase-4 menu invariants gate =="
bash "$HERE/check-phase4-menu.sh" || rc=1

echo
echo "== verifier-votes invariants gate =="
bash "$HERE/check-verifier-votes.sh" || rc=1

echo
echo "== dismissed-digest invariants gate =="
bash "$HERE/check-dismissed-digest.sh" || rc=1

echo
echo "== eval schema validation =="
python3 "$HERE/../skills/review-all/scripts/validate-evals.py" || rc=1

echo
echo "== shell script tests =="
bash "$HERE/test_scripts.sh" || rc=1

echo
echo "== python unittests =="
( cd "$HERE" && python3 -m unittest discover -s . -p "test_*.py" -v ) || rc=1

echo
if [[ $rc -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "TESTS FAILED"; fi
exit $rc
