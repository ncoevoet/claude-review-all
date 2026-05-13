#!/usr/bin/env bash
# dev-server-probe.sh — Phase 1 dev-server detection.
# Args: comma-separated port list. Default: 4200,5173,3000,8080.
# Emits one JSON object: {"open":[4200], "closed":[5173,3000,8080]}.
# Uses lsof when available, else ss, else nothing (prints empty).

set -u
PORTS=${1:-4200,5173,3000,8080}
IFS=',' read -r -a PORT_ARR <<<"$PORTS"

open=()
closed=()

check_port() {
  local p=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  elif command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk -v p=":$p$" '$4 ~ p {found=1} END{exit !found}'
    return $?
  fi
  return 1
}

for p in "${PORT_ARR[@]}"; do
  if check_port "$p"; then
    open+=("$p")
  else
    closed+=("$p")
  fi
done

join_csv() {
  local first=1
  for v in "$@"; do
    [[ $first -eq 1 ]] || printf ','
    printf '%s' "$v"
    first=0
  done
}

printf '{"open":[%s],"closed":[%s]}\n' "$(join_csv "${open[@]}")" "$(join_csv "${closed[@]}")"
