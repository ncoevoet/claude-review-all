#!/usr/bin/env python3
"""severity-tally.py — recover the per-tier finding counts from a review report.

Phase 3 requires the report's last line to be a machine-readable
`<!-- review-all-severity: {...} -->` comment. That requirement is an
INSTRUCTION, so it holds only as often as the model obeys it: measured across
nine headless runs on 2026-09-17, seven carried the comment and two did not.
The per-tier counts are the only CONTINUOUS signal an A/B has — binary PASS/FAIL
at N=3 sits inside this suite's noise floor — so a 22% loss rate falls on the
one measurement that cannot be replaced by re-running.

This script removes the model from that loop for any consumer that has the
report text. It tries three sources, in descending order of trust, and always
reports WHICH one answered so a derived count can never be mistaken for the
emitted one:

  comment    the `<!-- review-all-severity: {...} -->` line. Authoritative.
  summary    the Summary section's required `- **Findings**: X 🔴 Critical, …`
             field. Same numbers in prose; the observed failure mode is a report
             that emits this line and drops the comment, which is exactly the
             case this recovers.
  sections   counts `- **Finding …**` entries under each severity heading. Last
             resort: it is structural rather than stated, so a report that
             deviates from the template miscounts here.

A derived count is a repair, not a measurement of compliance. Callers that care
whether the model obeyed the instruction must look at the source field, not just
the numbers — `run-evals-headless.sh` prints it on the SCORE line for that
reason.

Usage:
  severity-tally.py [REPORT_FILE]          # reads stdin when no file is given
  severity-tally.py --source [REPORT_FILE] # append the source to the output

Output: `c,i,d,s,q,total` on one line (plus `,<source>` with --source).
Exit 0 when a tally was recovered, 1 when no source matched, 2 on bad usage.
"""
import json
import re
import sys

TIERS = ("critical", "important", "debt", "suggested", "question")

COMMENT_RE = re.compile(r"review-all-severity:\s*(\{.*?\})\s*-->")
SUMMARY_RE = re.compile(r"^\s*[-*]\s*\*\*Findings\*\*\s*:\s*(.+)$", re.M)
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.M)
ENTRY_RE = re.compile(r"^\s*[-*]\s+\*\*Finding\b")

# The heading glyph is what identifies a tier — the words around it vary with
# the template's bold-letter styling (`## 🟠 **I**mportant`).
TIER_GLYPHS = {
    "\U0001f534": "critical",
    "\U0001f7e0": "important",
    "\U0001f7e1": "debt",
    "\U0001f535": "suggested",
    "⚪": "question",
}
# Sections that also contain `- **Finding …**` entries but are NOT severity
# tiers: the appendix holds sub-threshold findings and 🔬 holds unverified ones,
# and neither is counted by the tally the template specifies.
EXCLUDED_HEADINGS = ("appendix", "unverified", "\U0001f52c")


def from_comment(text):
    matches = COMMENT_RE.findall(text)
    if not matches:
        return None
    try:
        d = json.loads(matches[-1])
    except ValueError:
        return None
    return [int(d.get(k, 0)) for k in TIERS]


def from_summary(text):
    m = SUMMARY_RE.search(text)
    if not m:
        return None
    line = m.group(1)
    counts = []
    for glyph in ("\U0001f534", "\U0001f7e0", "\U0001f7e1", "\U0001f535", "⚪"):
        found = re.search(r"(\d+)\s*" + glyph, line)
        if not found:
            return None
        counts.append(int(found.group(1)))
    return counts


def from_sections(text):
    counts = dict.fromkeys(TIERS, 0)
    seen = False
    current = None
    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(1)
            lowered = title.lower()
            current = None
            if not any(x in lowered for x in EXCLUDED_HEADINGS):
                for glyph, tier in TIER_GLYPHS.items():
                    if glyph in title:
                        current = tier
                        seen = True
                        break
            continue
        if current and ENTRY_RE.match(line):
            counts[current] += 1
    if not seen:
        return None
    return [counts[k] for k in TIERS]


def tally(text):
    for name, fn in (("comment", from_comment), ("summary", from_summary),
                     ("sections", from_sections)):
        counts = fn(text)
        if counts is not None:
            return counts, name
    return None, None


def main(argv):
    show_source = "--source" in argv
    args = [a for a in argv if a != "--source"]
    if len(args) > 1:
        sys.stderr.write("usage: severity-tally.py [--source] [REPORT_FILE]\n")
        return 2
    if args:
        try:
            with open(args[0], encoding="utf-8") as fh:
                text = fh.read()
        except OSError as ex:
            sys.stderr.write("severity-tally: cannot read %s: %s\n" % (args[0], ex))
            return 2
    else:
        text = sys.stdin.read()

    counts, source = tally(text)
    if counts is None:
        sys.stderr.write("severity-tally: no tally recoverable — no comment, no "
                         "Findings summary line, no severity sections.\n")
        return 1
    fields = [str(x) for x in counts] + [str(sum(counts))]
    if show_source:
        fields.append(source)
    print(",".join(fields))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
