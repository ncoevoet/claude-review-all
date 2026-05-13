#!/usr/bin/env bash
# preflight.sh — Phase 0.0 tool-availability probe.
# Outputs JSON to stdout: {"git":true,"timeout":false,...}
# Always exits 0 unless git is missing (the only hard requirement).

set -u

declare -A REQUIRED=( [git]=1 )
TOOLS=(git timeout lsof ss gh jq curl rsync)

declare -A AVAIL
missing_required=""

for t in "${TOOLS[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    AVAIL[$t]=true
  else
    AVAIL[$t]=false
    if [[ ${REQUIRED[$t]:-0} == 1 ]]; then
      missing_required="$missing_required $t"
    fi
  fi
done

# Emit JSON without depending on jq (jq may itself be missing).
printf '{'
first=1
for t in "${TOOLS[@]}"; do
  [[ $first -eq 1 ]] || printf ','
  printf '"%s":%s' "$t" "${AVAIL[$t]}"
  first=0
done
printf '}\n'

if [[ -n "$missing_required" ]]; then
  echo "preflight: required tool missing:$missing_required" >&2
  exit 2
fi

exit 0
