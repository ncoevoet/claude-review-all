#!/usr/bin/env python3
"""Tests for scripts/severity-tally.py — the three recovery sources and the
guarantee that a derived count is always labelled as derived."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "review-all", "scripts", "severity-tally.py")

COMMENT = '<!-- review-all-severity: {"critical":2,"important":3,"debt":1,"suggested":0,"question":4} -->'
SUMMARY = "- **Findings**: 2 \U0001f534 Critical, 3 \U0001f7e0 Important, 1 \U0001f7e1 Debt, 0 \U0001f535 Suggested, 4 ⚪ Questions"

SECTIONS = """# Comprehensive Review Report

## \U0001f534 **C**ritical
- **Finding 1**: SQL injection — `a.js:1` `[\U0001f534 CRITICAL · VERIFIED]`
  - **Impact**: bad
- **Finding 2**: path traversal — `b.js:2`

## \U0001f7e0 **I**mportant
- **Finding 3**: race — `c.js:3`

## \U0001f7e1 **D**ebt
None found.

## \U0001f535 **S**uggested
- **Finding 4**: rename — `d.js:4`

## ⚪ Questions
- **Finding 5**: why? — `e.js:5`

## \U0001f52c Unverified — needs observation
- **Finding 6**: unproven — `f.js:6`

## Potential Issues (Appendix)
- **Finding 7**: maybe — `g.js:7`
"""


def run(text, *args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args),
                          input=text, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class TestSeverityTally(unittest.TestCase):
    def test_comment_is_preferred_and_labelled(self):
        rc, out, _ = run("body\n" + SUMMARY + "\n" + COMMENT, "--source")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "2,3,1,0,4,10,comment")

    def test_summary_recovers_a_dropped_comment(self):
        rc, out, _ = run("# Report\n\n## Summary\n" + SUMMARY + "\n", "--source")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "2,3,1,0,4,10,summary")

    def test_sections_counted_when_comment_and_summary_absent(self):
        rc, out, _ = run(SECTIONS, "--source")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "2,1,0,1,1,5,sections")

    def test_appendix_and_unverified_are_not_counted_as_tiers(self):
        rc, out, _ = run(SECTIONS)
        self.assertEqual(rc, 0)
        self.assertEqual(out.split(",")[5], "5", "\U0001f52c and Appendix entries must not inflate the tally")

    def test_all_zero_tally_is_recovered_not_treated_as_missing(self):
        zero = '<!-- review-all-severity: {"critical":0,"important":0,"debt":0,"suggested":0,"question":0} -->'
        rc, out, _ = run(zero, "--source")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "0,0,0,0,0,0,comment")

    def test_last_comment_wins_when_a_report_quotes_the_template(self):
        earlier = '<!-- review-all-severity: {"critical":9,"important":9,"debt":9,"suggested":9,"question":9} -->'
        rc, out, _ = run(earlier + "\n...\n" + COMMENT)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "2,3,1,0,4,10")

    def test_malformed_comment_falls_through_to_summary(self):
        rc, out, _ = run("<!-- review-all-severity: {not json} -->\n" + SUMMARY, "--source")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "2,3,1,0,4,10,summary")

    def test_partial_summary_line_is_rejected_rather_than_guessed(self):
        partial = "- **Findings**: 2 \U0001f534 Critical, 3 \U0001f7e0 Important"
        rc, out, _ = run("## Summary\n" + partial + "\n", "--source")
        self.assertEqual(rc, 1, "a summary line missing tiers must not be half-parsed")

    def test_unrecoverable_report_exits_1(self):
        rc, _, err = run("# Report\n\nNothing structured here.\n")
        self.assertEqual(rc, 1)
        self.assertIn("no tally recoverable", err)

    def test_too_many_arguments_exits_2(self):
        proc = subprocess.run([sys.executable, SCRIPT, "a", "b"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_unreadable_file_exits_2(self):
        proc = subprocess.run([sys.executable, SCRIPT, "/nonexistent/report.md"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
