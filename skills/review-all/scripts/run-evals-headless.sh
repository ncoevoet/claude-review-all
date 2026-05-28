#!/usr/bin/env bash
# run-evals-headless.sh — headless, LLM-graded eval runner for /review-all.
#
# For each evals/*.json case, REVIEW_ALL_EVAL_RUNS times:
#   1. Materialize the fixture into a throwaway temp git repo (fresh per run).
#   2. Run `/review-all` headlessly there with `claude -p` to produce a report.
#   3. Grade the report against the case's grader.rubric with a second
#      `claude -p` call (LLM-as-judge) -> PASS/FAIL.
# A case is scored by majority pass-rate across its graded runs. Prints
# `RESULT,<id>,PASS|FAIL|ERROR (k/n)` lines so iteration cycles can diff scores.
#
# Env:
#   REVIEW_ALL_EVAL_RUNS=N    runs per case (default 1). >1 smooths LLM noise.
#   REVIEW_ALL_EVAL_EFFORT=L  pass --effort L (low|medium|high) to the review;
#                             works around a headless thinking-block API error.
#
# Prereqs:
#   - `claude` CLI on PATH, authenticated.
#   - The skill INSTALLED globally (`make install`) so `/review-all` resolves
#     from any cwd, including the temp fixture repo.
# Runs the review with --dangerously-skip-permissions because every target is an
# isolated, throwaway fixture repo created by materialize-fixture.py.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"        # skills/review-all/scripts
SKILL_ROOT="$HERE/.."
EVALS="$SKILL_ROOT/evals"
filter="${1:-}"

if ! command -v claude >/dev/null 2>&1; then
  echo "run-evals-headless: 'claude' CLI not found on PATH." >&2
  echo "Use scripts/run-evals.sh for manual mode, or install Claude Code." >&2
  exit 127
fi

field() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$1" "$2"; }
rubric() {
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));g=d.get('grader',{});\
print(g.get('rubric','') or '\n'.join(d.get('expected_behavior',[])))" "$1"
}
bad_report() { [[ -z "${1// }" || "$1" == *"API Error"* || "$1" == *"Execution error"* ]]; }

eff=()
[[ -n "${REVIEW_ALL_EVAL_EFFORT:-}" ]] && eff=(--effort "$REVIEW_ALL_EVAL_EFFORT")
runs=${REVIEW_ALL_EVAL_RUNS:-1}

review_once() { ( cd "$1" && claude -p "$2" --dangerously-skip-permissions "${eff[@]}" 2>/dev/null ); }

pass=0; fail=0; err=0
for f in "$EVALS"/*.json; do
  id=$(basename "$f" .json)
  case "$id" in README*) continue ;; esac
  [[ -n "$filter" && "$id" != "$filter"* ]] && continue

  query=$(field "$f" query); [[ -z "$query" ]] && query="/review-all"
  # Natural-language invocation: appending prose AFTER the slash command would be
  # parsed as the skill's $ARGUMENTS (a bogus review target). Phrase it as an
  # instruction instead, and steer away from the interactive Phase 4 menu.
  prompt="Run the ${query} skill on this repository's changes. Output ONLY the final review report through Phase 3. Do NOT run the Phase 4 interactive menu and do NOT call AskUserQuestion."
  rb=$(rubric "$f")

  cp=0; graded=0
  for ((r=1; r<=runs; r++)); do
    repo=$(python3 "$HERE/materialize-fixture.py" "$f") || continue
    report=$(review_once "$repo" "$prompt")
    bad_report "$report" && report=$(review_once "$repo" "$prompt")   # one retry
    if bad_report "$report"; then rm -rf "$repo"; continue; fi
    graded=$((graded+1))
    judge=$(printf 'You are grading a code-review report against a rubric. Reason briefly, then on the LAST line output exactly PASS or FAIL.\n\n<rubric>\n%s\n</rubric>\n\n<report>\n%s\n</report>\n' \
        "$rb" "$report" | claude -p --dangerously-skip-permissions 2>/dev/null)
    if echo "$judge" | grep -qiE '\bPASS\b' && ! echo "$judge" | tail -1 | grep -qiE '\bFAIL\b'; then
      cp=$((cp+1))
    fi
    rm -rf "$repo"
  done

  if [[ $graded -eq 0 ]]; then
    err=$((err+1)); echo "RESULT,$id,ERROR (0/$runs graded — infra/transient)"
  elif [[ $((cp * 2)) -gt $graded ]]; then
    pass=$((pass+1)); echo "RESULT,$id,PASS ($cp/$graded)"
  else
    fail=$((fail+1)); echo "RESULT,$id,FAIL ($cp/$graded)"
  fi
done

echo "headless evals: $pass passed, $fail failed, $err errored (runs/case=$runs)"
[[ $fail -eq 0 && $err -eq 0 ]]
