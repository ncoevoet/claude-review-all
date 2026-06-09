"""Unit tests for skills/review-all/scripts/gate-verdict.py (gate mode verdict)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "gate-verdict.py")

TS = "2026-06-03T12:00:00Z"

CRIT = {"id": "F1", "severity": "CRITICAL", "confidence": 90, "file": "src/a.ts",
        "line": 42, "root_cause_key": "cmd-injection:src/a.ts", "title": "command injection"}
IMP = {"id": "F2", "severity": "IMPORTANT", "file": "src/b.ts", "title": "missing guard"}
DEBT = {"id": "F3", "severity": "DEBT", "file": "src/c.ts", "title": "dup logic"}


def run(findings, args=None, raw=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=raw if raw is not None else json.dumps(findings),
        capture_output=True, text=True)


class TestGateVerdict(unittest.TestCase):
    def test_empty_passes(self):
        p = run([], ["--timestamp", TS])
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertTrue(out["pass"])
        self.assertEqual(out["blockingCount"], 0)
        self.assertFalse(out["partial"])

    def test_critical_blocks_at_critical_floor(self):
        p = run([CRIT], ["--severity", "critical", "--timestamp", TS])
        self.assertEqual(p.returncode, 1, p.stderr)
        out = json.loads(p.stdout)
        self.assertFalse(out["pass"])
        self.assertEqual(out["blockingCount"], 1)
        self.assertEqual(out["blocking"][0]["id"], "F1")
        self.assertEqual(out["blocking"][0]["severity"], "CRITICAL")

    def test_important_passes_at_critical_floor(self):
        p = run([IMP], ["--severity", "critical", "--timestamp", TS])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)["pass"])

    def test_important_blocks_at_important_floor(self):
        p = run([IMP], ["--severity", "important", "--timestamp", TS])
        self.assertEqual(p.returncode, 1, p.stderr)
        out = json.loads(p.stdout)
        self.assertFalse(out["pass"])
        self.assertEqual(out["blockingCount"], 1)

    def test_debt_never_blocks_at_critical_floor(self):
        p = run([DEBT], ["--severity", "critical", "--timestamp", TS])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)["pass"])

    def test_summary_counts_all_tiers(self):
        out = json.loads(run([CRIT, IMP, DEBT], ["--severity", "important", "--timestamp", TS]).stdout)
        self.assertEqual(out["summary"]["critical"], 1)
        self.assertEqual(out["summary"]["important"], 1)
        self.assertEqual(out["summary"]["debt"], 1)
        # critical + important block at the important floor; debt does not.
        self.assertEqual(out["blockingCount"], 2)

    def test_partial_fails_closed(self):
        p = run([], ["--partial", "--timestamp", TS])
        self.assertEqual(p.returncode, 1, p.stderr)
        out = json.loads(p.stdout)
        self.assertFalse(out["pass"])
        self.assertTrue(out["partial"])
        self.assertEqual(out["blockingCount"], 0)

    def test_field_aliases_from_export_normalize(self):
        # finding_id -> id, path -> file (reused from export-findings.normalize)
        out = json.loads(run(
            [{"finding_id": "X9", "severity": "CRITICAL", "path": "src/z.ts", "title": "t"}],
            ["--severity", "critical", "--timestamp", TS]).stdout)
        self.assertEqual(out["blocking"][0]["id"], "X9")
        self.assertEqual(out["blocking"][0]["file"], "src/z.ts")

    def test_out_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            out_path = os.path.join(d, "nested", "gate-verdict.json")
            p = run([CRIT], ["--severity", "critical", "--out", out_path,
                             "--reviewed-sha", "abc123", "--timestamp", TS])
            self.assertEqual(p.returncode, 1, p.stderr)
            with open(out_path) as fh:
                disk = json.load(fh)
            self.assertEqual(disk["reviewedSha"], "abc123")
            self.assertFalse(disk["pass"])

    def test_malformed_input_exits_2(self):
        p = run(None, ["--severity", "critical"], raw="not json")
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
