"""Unit tests for skills/review-all/scripts/dedupe.py (Phase 2.5 dedupe)."""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "dedupe.py")


def run(findings, args=None, env=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=json.dumps(findings),
        capture_output=True, text=True,
        env={**os.environ, **(env or {})})


def suggested(n):
    return [{"id": str(i), "root_cause_key": f"k{i}", "severity": "SUGGESTED",
             "source_agent": "a", "evidence": "e"} for i in range(n)]


class TestDedupe(unittest.TestCase):
    def test_groups_by_key_and_keeps_richest_evidence(self):
        findings = [
            {"id": "1", "root_cause_key": "k", "severity": "DEBT",
             "source_agent": "a", "evidence": "short"},
            {"id": "2", "root_cause_key": "k", "severity": "DEBT",
             "source_agent": "b", "evidence": "much longer evidence string"},
        ]
        p = run(findings)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(len(out["kept"]), 1)
        self.assertEqual(out["kept"][0]["id"], "2")
        self.assertEqual(out["kept"][0]["confirmed_by"], ["a"])

    def test_suggested_cap_drops_overflow(self):
        out = json.loads(run(suggested(5), ["--suggested-cap", "2"]).stdout)
        self.assertEqual(len([f for f in out["kept"] if f["severity"] == "SUGGESTED"]), 2)
        self.assertEqual(len(out["dropped_global_cap"]), 3)

    def test_cap_zero_is_unlimited(self):
        out = json.loads(run(suggested(20), ["--suggested-cap", "0"]).stdout)
        self.assertEqual(len([f for f in out["kept"] if f["severity"] == "SUGGESTED"]), 20)

    def test_critical_never_capped(self):
        findings = [{"id": str(i), "root_cause_key": f"k{i}", "severity": "CRITICAL",
                     "source_agent": "a", "evidence": "e"} for i in range(30)]
        out = json.loads(run(findings, ["--suggested-cap", "1", "--question-cap", "1"]).stdout)
        self.assertEqual(len(out["kept"]), 30)

    def test_env_var_cap_applies(self):
        out = json.loads(run(suggested(5), env={"REVIEW_ALL_SUGGESTED_CAP": "1"}).stdout)
        self.assertEqual(len([f for f in out["kept"] if f["severity"] == "SUGGESTED"]), 1)

    def test_cli_beats_env(self):
        out = json.loads(run(suggested(5), ["--suggested-cap", "3"],
                             env={"REVIEW_ALL_SUGGESTED_CAP": "1"}).stdout)
        self.assertEqual(len([f for f in out["kept"] if f["severity"] == "SUGGESTED"]), 3)

    def test_malformed_input_exits_2(self):
        p = subprocess.run([sys.executable, SCRIPT], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)

    def test_missing_root_cause_key_exits_2(self):
        self.assertEqual(run([{"id": "1", "severity": "DEBT"}]).returncode, 2)


if __name__ == "__main__":
    unittest.main()
