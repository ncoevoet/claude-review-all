#!/usr/bin/env bash
# check-severity-tally.sh — release gate: the report's machine-readable tally.
#
# The report is required to end with `<!-- review-all-severity: {...} -->`; CI and
# the eval harness parse it for per-tier counts. Two captured headless reports
# (2026-09-11) omitted it, and the cause was visible in the docs rather than the
# model: SKILL.md's "Required sections (in order)" list stopped at the Scope
# footer and never named the tally, while the Phase 3 heartbeat instructed a PROSE
# line carrying the same counts. The orchestrator emitted the prose and dropped
# the comment — counts reported, report unparseable — then appended commentary
# after the report, so even a correct final line would no longer have been final.
#
# Nothing at runtime can catch this: a report with no tally renders perfectly to a
# human. So the invariants are pinned here, on all four surfaces that carry them.
# Exit 0 = clean, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/review-all/SKILL.md"
REPORT="$ROOT/skills/review-all/references/phase-3-report.md"
RUNNER="$ROOT/skills/review-all/scripts/run-evals-headless.sh"
README="$ROOT/README.md"

for f in "$SKILL" "$REPORT" "$RUNNER" "$README"; do
  [[ -f "$f" ]] || { echo "check-severity-tally: missing file $f" >&2; exit 2; }
done

echo "check-severity-tally: asserting tally invariants in SKILL.md / phase-3-report.md / run-evals-headless.sh / README.md"

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-severity-tally: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

# --- SKILL.md: the section list must NAME the tally, or it is not a section ---
need "$SKILL" 'machine-readable tally' "required-sections list names the machine-readable tally"
need "$SKILL" "last emitted line is the machine-readable tally" "terminal-line contract"
need "$SKILL" 'including one where every count is zero' "tally is emitted even when all counts are zero"
need "$SKILL" 'Nothing follows it in the report text' "no-commentary-after-the-tally rule"
need "$SKILL" 'does \*\*not\*\* discharge' "Phase 3 heartbeat is marked non-discharging"

# --- phase-3-report.md: same contract, stated where the template lives ---
need "$REPORT" 'review-all-severity' "template carries the tally comment"
need "$REPORT" 'Emit it on every run' "tally is unconditional"
need "$REPORT" 'Nothing follows' "no-commentary-after-the-tally rule"
need "$REPORT" 'neither is parseable' "prose counts do not substitute for the comment"

# --- the consumer must not fail silently ---
need "$RUNNER" 'SCORE,\$id,MISSING' "runner reports a missing tally instead of skipping it"

# --- README advertises it as a CI affordance, so it has to keep saying so ---
need "$README" 'review-all-severity' "README documents the machine-readable tally"

# The template block and the prose rule must agree on the key set, or a consumer
# written against one will miss a field the other promises.
tpl_keys="$(grep -o 'review-all-severity: {[^}]*}' "$REPORT" | head -1 \
  | grep -oE '"(critical|important|debt|suggested|question)"' | tr -d '"' | LC_ALL=C sort -u)"
want="$(printf 'critical\ndebt\nimportant\nquestion\nsuggested\n')"
if [[ "$tpl_keys" != "$want" ]]; then
  echo "check-severity-tally: template tally keys differ from the five severity tiers:" >&2
  diff <(echo "$want") <(echo "$tpl_keys") | sed 's/^/  /' >&2
  rc=1
fi

if [[ $rc -eq 0 ]]; then
  echo "check-severity-tally: CLEAN (5 tiers, 4 surfaces asserted)"
else
  echo "check-severity-tally: FAIL — see above." >&2
fi
exit $rc
