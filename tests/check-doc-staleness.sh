#!/usr/bin/env bash
# check-doc-staleness.sh — release gate for the CLAUDE.md/README staleness check.
#
# This check points at prose, where "the docs look out of date" is always
# arguable — so its precision rests entirely on two prose rules: quote BOTH the
# doc sentence and the falsifying diff lines, and a merely-related doc is not
# stale. Lose either and the agent starts emitting a docs-review-shaped opinion
# on every PR. The third pinned rule keeps it disjoint from agent 01, which
# reads the same CLAUDE.md sentence from the opposite direction — without it,
# one change can yield two contradictory findings that dedupe cannot merge
# (their root-cause keys differ by design).
# Exit 0 = all present, 1 = an invariant is missing, 2 = misconfig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
AGENT="$ROOT/skills/review-all/agents/04-consistency-history.md"
SHARED="$ROOT/skills/review-all/agents/_shared.md"
README="$ROOT/README.md"

for f in "$AGENT" "$SHARED" "$README"; do
  [[ -f "$f" ]] || { echo "check-doc-staleness: missing file $f" >&2; exit 2; }
done

rc=0
need() {  # need <file> <ERE> <label>
  if ! grep -qiE "$2" "$1"; then
    echo "check-doc-staleness: MISSING in $(basename "$1"): $3" >&2
    rc=1
  fi
}

echo "check-doc-staleness: asserting doc-staleness invariants in 04-consistency-history.md / _shared.md / README.md"

# --- agent 04: the section, the evidence bar, the anti-noise rule, the carve-up ---
need "$AGENT" 'Documentation staleness' "staleness section present"
need "$AGENT" 'only when you can quote both' "quote-both-sides evidence bar"
need "$AGENT" 'the diff lines that falsify it' "falsifying-diff-lines requirement"
need "$AGENT" 'merely \*related\* is \*\*NOT stale\*\*' "anti-noise rule"
need "$AGENT" 'stale-docs:' "stale-docs root-cause key"
need "$AGENT" 'Disambiguation vs agent 01' "agent-01 disambiguation"
need "$AGENT" 'Never raise both' "never-both rule"

# --- _shared.md: the category must exist in the fixed root-cause-key list ---
need "$SHARED" '`stale-docs`' "stale-docs in the fixed category list"

# --- README: user-visible, including the precision bar ---
need "$README" 'docs-need-update finding' "README documents the check"
need "$README" 'not stale' "README states the anti-noise bar"

if [[ $rc -eq 0 ]]; then
  echo "check-doc-staleness: CLEAN"
else
  echo "check-doc-staleness: FAIL — invariant(s) missing above." >&2
fi
exit $rc
