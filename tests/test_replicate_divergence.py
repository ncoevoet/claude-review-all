#!/usr/bin/env python3
"""Tests for scripts/replicate-divergence.py — matrix cells, DIVERGENT rule,
clustering, judge-parse parity with the runner's bash expression."""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "review-all", "scripts", "replicate-divergence.py")
_spec = importlib.util.spec_from_file_location("replicate_divergence", SCRIPT)
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)

CRIT, IMP, DEBT, SUG = "\U0001f534", "\U0001f7e0", "\U0001f7e1", "\U0001f535"
UNV = "\U0001f52c"


def report(sections):
    """sections: list of (heading, [entry lines])."""
    parts = ["# Comprehensive Review Report", ""]
    n = 0
    for heading, entries in sections:
        parts.append("## " + heading)
        for e in entries:
            n += 1
            parts.append("- **Finding %d**: %s" % (n, e))
        parts.append("")
    return "\n".join(parts)


def imp(*entries):
    return (IMP + " Important", list(entries))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rdtest_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def case(self, arm, reports, judges=None, case_id="c1"):
        d = os.path.join(self.tmp, arm, case_id)
        os.makedirs(d)
        for r, text in reports.items():
            with open(os.path.join(d, "run%d.report.md" % r), "w", encoding="utf-8") as fh:
                fh.write(text)
        for r, text in (judges or {}).items():
            with open(os.path.join(d, "run%d.judge.txt" % r), "w", encoding="utf-8") as fh:
                fh.write(text)
        return d

    def run_script(self, *dirs):
        p = subprocess.run([sys.executable, SCRIPT] + list(dirs), capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def row(self, out, needle):
        rows = [ln for ln in out.splitlines() if ln.startswith("| ") and needle in ln.split("|")[1]]
        self.assertEqual(len(rows), 1, "rows for %r: %r\n%s" % (needle, rows, out))
        return rows[0]


class TestMatrix(Base):
    def test_stable_row(self):
        rep = report([imp("race — `a.ts:10`")])
        d = self.case("k", {1: rep, 2: rep, 3: rep})
        rc, out, _ = self.run_script(d)
        self.assertEqual(rc, 0)
        self.assertIn("3 runs read", out)
        row = self.row(out, "a.ts:10")
        self.assertIn("| %s | %s | %s | 3/3 |" % (IMP, IMP, IMP), row)
        self.assertNotIn("DIVERGENT", row)

    def test_absent_in_one_run(self):
        with_f = report([imp("race — `a.ts:10`")])
        without = report([imp("other — `z.ts:1`")])
        d = self.case("k", {1: with_f, 2: without, 3: with_f})
        row = self.row(self.run_script(d)[1], "a.ts:10")
        self.assertIn("| %s | — | %s | 2/3 | DIVERGENT" % (IMP, IMP), row)

    def test_tier_flip_to_unverified(self):
        main = report([imp("x — `a.ts:10`")])
        unv = report([(UNV + " Unverified — needs observation", ["x — `a.ts:10`"])])
        d = self.case("k", {1: main, 2: unv, 3: main})
        row = self.row(self.run_script(d)[1], "a.ts:10")
        self.assertIn("| %s | %s | %s | 3/3 | DIVERGENT" % (IMP, UNV, IMP), row)

    def test_tier_flip_to_appendix(self):
        main = report([imp("x — `a.ts:10`")])
        app = report([("Potential Issues (Appendix)", ["x — `a.ts:10`"])])
        d = self.case("k", {1: main, 2: app})
        row = self.row(self.run_script(d)[1], "a.ts:10")
        self.assertIn("DIVERGENT", row)
        self.assertIn("\U0001f4ce", row)

    def test_line_fuzz_merges_and_far_line_splits(self):
        r1 = report([imp("a — `a.ts:10`")])
        r2 = report([imp("a — `a.ts:13`")])
        r3 = report([imp("b — `a.ts:14`")])
        d = self.case("k", {1: r1, 2: r2, 3: r3})
        out = self.run_script(d)[1]
        merged = self.row(out, "a.ts:10-13")
        self.assertIn("| %s | %s | — | 2/3 | DIVERGENT" % (IMP, IMP), merged)
        far = self.row(out, "a.ts:14")
        self.assertIn("| — | — | %s | 1/3 | DIVERGENT" % IMP, far)

    def test_path_suffix_unification_and_dot_slash(self):
        r1 = report([imp("a — `./src/app/a.ts:10`")])
        r2 = report([imp("a — `a.ts:11`")])
        r3 = report([imp("a — `app/a.ts:10`")])
        d = self.case("k", {1: r1, 2: r2, 3: r3})
        out = self.run_script(d)[1]
        row = self.row(out, "src/app/a.ts:10-11")
        self.assertIn("3/3", row)
        self.assertNotIn("DIVERGENT", row)

    def test_same_run_collision_joins_glyphs(self):
        r1 = report([imp("a — `a.ts:10`"), (DEBT + " Debt", ["`a.ts:11` — smell"])])
        r2 = report([imp("a — `a.ts:10`")])
        d = self.case("k", {1: r1, 2: r2})
        row = self.row(self.run_script(d)[1], "a.ts:10-11")
        self.assertIn("%s+%s" % (IMP, DEBT), row)
        self.assertIn("DIVERGENT", row)

    def test_title_ignored(self):
        r1 = report([imp("title one — `a.ts:10`")])
        r2 = report([imp("completely different words — `a.ts:10`")])
        d = self.case("k", {1: r1, 2: r2})
        out = self.run_script(d)[1]
        self.assertEqual(len([ln for ln in out.splitlines() if "a.ts" in ln]), 1)
        self.assertIn("2/2", self.row(out, "a.ts:10"))

    def test_first_location_span_not_first_backtick(self):
        r = report([imp("`foo()` misused — `a.ts:10`")])
        out = self.run_script(self.case("k", {1: r}))[1]
        self.assertIn("a.ts:10", out)

    def test_no_location_bucket(self):
        r1 = report([imp("vague concern")])
        r2 = report([(DEBT + " Debt", ["vague concern"])])
        out = self.run_script(self.case("k", {1: r1, 2: r2}))[1]
        self.assertIn("<no-location> " + IMP, out)
        self.assertIn("<no-location> " + DEBT, out)

    def test_divergent_sorted_first(self):
        stable = "stable — `a.ts:5`"
        r1 = report([imp(stable, "flaky — `z.ts:1`")])
        r2 = report([imp(stable)])
        out = self.run_script(self.case("k", {1: r1, 2: r2}))[1]
        lines = [ln for ln in out.splitlines() if ".ts:" in ln]
        self.assertIn("z.ts:1", lines[0])
        self.assertIn("a.ts:5", lines[1])

    def test_repeat_count_is_divergent(self):
        r1 = report([(CRIT + " Critical", ["one — `a.ts:5`"])])
        r2 = report([(CRIT + " Critical", ["one — `a.ts:5`", "two — `a.ts:5`"])])
        out = self.run_script(self.case("k", {1: r1, 2: r2}))[1]
        self.assertIn("DIVERGENT", self.row(out, "a.ts:5"))

    def test_canonical_glyph_order(self):
        r1 = report([(SUG + " Suggested", ["s — `a.ts:5`"]), (CRIT + " Critical", ["c — `a.ts:5`"])])
        r2 = report([(CRIT + " Critical", ["c — `a.ts:5`"]), (SUG + " Suggested", ["s — `a.ts:5`"])])
        out = self.run_script(self.case("k", {1: r1, 2: r2}))[1]
        row = self.row(out, "a.ts:5")
        self.assertIn(CRIT + "+" + SUG, row)
        self.assertNotIn("DIVERGENT", row)

    def test_label_collision_lengthens_dir(self):
        r = report([imp("x — `a.ts:5`")])
        d1 = os.path.join(self.tmp, "a", "keep", "99")
        d2 = os.path.join(self.tmp, "b", "keep", "99")
        for d in (d1, d2):
            os.makedirs(d)
            with open(os.path.join(d, "run1.report.md"), "w", encoding="utf-8") as fh:
                fh.write(r)
        out = self.run_script(d1, d2)[1]
        header = [ln for ln in out.splitlines() if ln.startswith("| cluster")][0]
        cols = [c.strip() for c in header.split("|")[2:4]]
        self.assertEqual(len(set(cols)), 2)
        self.assertTrue(cols[0].endswith("a/keep/run1"))

    def test_unique_labels_unchanged(self):
        d1 = self.case("armA", {1: report([imp("x — `a.ts:5`")])})
        d2 = self.case("armB", {1: report([imp("x — `a.ts:5`")])})
        out = self.run_script(d1, d2)[1]
        self.assertIn("| armA/run1 | armB/run1 |", out)


class TestHeader(Base):
    def test_missing_tally(self):
        d = self.case("k", {1: "just prose, no sections\n"})
        out = self.run_script(d)[1]
        self.assertIn("MISSING", out)
        self.assertIn("no findings in any run (1 runs read)", out)

    def test_tally_total_and_source(self):
        r = report([imp("a — `a.ts:1`")])
        out = self.run_script(self.case("k", {1: r}))[1]
        self.assertIn("| k/run1 | FAIL(empty) | 0/1/0/0/0 | 1 | sections |", out)

    def test_empty_and_missing_judge(self):
        r = report([imp("a — `a.ts:1`")])
        d = self.case("k", {1: r, 2: r}, judges={2: ""})
        out = self.run_script(d)[1]
        self.assertIn("| k/run1 | FAIL(empty) |", out)
        self.assertIn("| k/run2 | FAIL(empty) |", out)

    def test_real_run_indices_in_labels(self):
        r = report([imp("a — `a.ts:1`")])
        out = self.run_script(self.case("k", {1: r, 3: r}))[1]
        self.assertIn("k/run1", out)
        self.assertIn("k/run3", out)
        self.assertNotIn("k/run2", out)

    def test_multi_dir_labels(self):
        r = report([imp("a — `a.ts:1`")])
        d1 = self.case("armA", {1: r, 2: r})
        d2 = self.case("armB", {1: r})
        rc, out, _ = self.run_script(d1, d2)
        self.assertEqual(rc, 0)
        self.assertIn("3 runs read", out)
        for lab in ("armA/run1", "armA/run2", "armB/run1"):
            self.assertIn(lab, out)
        self.assertIn("3/3", self.row(out, "a.ts:1"))


class TestJudgeParity(Base):
    RUNNER_EXPR = ("judge=$(cat \"$1\"); "
                   "if echo \"$judge\" | grep -qiE '\\bPASS\\b' && "
                   "! echo \"$judge\" | tail -1 | grep -qiE '\\bFAIL\\b'; "
                   "then echo PASS; else echo FAIL; fi")

    def test_parity_with_runner_bash(self):
        texts = [
            "reasoning\nPASS", "reasoning\nFAIL", "PASS\nreasoning\nFAIL",
            "FAIL\nthen reconsidered\nPASS", "pass", "fail", "PASSED\nPASSING",
            "no verdict here", "PASS\n\n\n", "bypass\nFAIL", "The report would PASS but\nFAIL.",
            "Verdict: pass. Not a fail.", "x PASS y\nlast line mentions failing",
        ]
        for i, text in enumerate(texts):
            path = os.path.join(self.tmp, "j%d.txt" % i)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            bash = subprocess.run(["bash", "-c", self.RUNNER_EXPR, "_", path],
                                  capture_output=True, text=True).stdout.strip()
            self.assertEqual(rd.judge_verdict(path), bash, repr(text))


class TestExitCodes(Base):
    def test_zero_findings(self):
        r = "# Comprehensive Review Report\n\n## " + CRIT + " Critical\nNone found.\n"
        rc, out, _ = self.run_script(self.case("k", {1: r, 2: r}))
        self.assertEqual(rc, 0)
        self.assertIn("no findings in any run (2 runs read)", out)

    def test_zero_runs_exit_2(self):
        d = os.path.join(self.tmp, "k", "empty")
        os.makedirs(d)
        rc, out, err = self.run_script(d)
        self.assertEqual(rc, 2)
        self.assertIn("0 runs read", err)

    def test_bad_usage_exit_2(self):
        rc, _, err = self.run_script()
        self.assertEqual(rc, 2)
        self.assertIn("usage", err)
        rc, _, _ = self.run_script(os.path.join(self.tmp, "nope"))
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
