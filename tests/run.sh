#!/usr/bin/env bash
# Run the full deterministic test suite (shell scripts + Python).
# No network / API key needed — safe for CI.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
rc=0

echo "== shell script tests =="
bash "$HERE/test_scripts.sh" || rc=1

echo
echo "== python unittests =="
( cd "$HERE" && python3 -m unittest discover -s . -p "test_*.py" -v ) || rc=1

echo
if [[ $rc -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "TESTS FAILED"; fi
exit $rc
