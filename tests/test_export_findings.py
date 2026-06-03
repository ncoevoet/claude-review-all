"""Unit tests for skills/review-all/scripts/export-findings.py (Phase 4 export)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "export-findings.py")

TS = "2026-06-03T12:00:00Z"

FINDINGS = [
    {"id": "1", "severity": "CRITICAL", "confidence": 95, "file": "src/a.py",
     "line": 12, "root_cause_key": "race-condition:src/a.py:run", "title": "Race on cache",
     "impact": "lost updates", "fix": "use a lock"},
    {"id": "2", "severity": "IMPORTANT", "confidence": 80, "file": "src/b.ts",
     "line": 3, "root_cause_key": "perf:src/b.ts:load", "title": "N+1 query"},
    {"id": "3", "severity": "DEBT", "file": "src/c.go", "root_cause_key": "style:src/c.go:x",
     "title": "dup logic"},
    {"id": "4", "severity": "QUESTION", "file": "src/d.java", "line": 9,
     "root_cause_key": "other:src/d.java:y", "title": "intended?"},
]


def run(findings, args=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=json.dumps(findings), capture_output=True, text=True)


class TestExportFindings(unittest.TestCase):
    def test_json_stdout_shape(self):
        p = run(FINDINGS, ["--format", "json", "--timestamp", TS])
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["tool"], "review-all")
        self.assertEqual(out["generated_at"], TS)
        self.assertEqual(out["summary"]["critical"], 1)
        self.assertEqual(out["summary"]["question"], 1)
        self.assertEqual(len(out["findings"]), 4)

    def test_sarif_stdout_shape_and_levels(self):
        p = run(FINDINGS, ["--format", "sarif", "--timestamp", TS])
        self.assertEqual(p.returncode, 0, p.stderr)
        sarif = json.loads(p.stdout)
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertEqual(len(sarif["runs"]), 1)
        results = sarif["runs"][0]["results"]
        # QUESTION omitted -> 3 results, not 4
        self.assertEqual(len(results), 3)
        levels = {r["ruleId"]: r["level"] for r in results}
        self.assertEqual(levels["race-condition:src/a.py:run"], "error")
        self.assertEqual(levels["perf:src/b.ts:load"], "warning")
        self.assertEqual(levels["style:src/c.go:x"], "note")
        self.assertEqual(sarif["runs"][0]["tool"]["driver"]["name"], "review-all")
        a = next(r for r in results if r["ruleId"] == "race-condition:src/a.py:run")
        self.assertEqual(a["locations"][0]["physicalLocation"]["region"]["startLine"], 12)

    def test_both_requires_out_dir(self):
        self.assertEqual(run(FINDINGS, ["--format", "both"]).returncode, 2)

    def test_out_dir_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = run(FINDINGS, ["--format", "both", "--out-dir", d, "--timestamp", TS])
            self.assertEqual(p.returncode, 0, p.stderr)
            files = sorted(os.listdir(d))
            self.assertEqual(
                files, ["review-20260603T120000Z.json", "review-20260603T120000Z.sarif"])
            with open(os.path.join(d, "review-20260603T120000Z.sarif")) as fh:
                self.assertEqual(json.load(fh)["version"], "2.1.0")

    def test_finding_id_fallback(self):
        out = json.loads(run(
            [{"finding_id": "x", "severity": "DEBT", "file": "a",
              "root_cause_key": "k", "title": "t"}],
            ["--format", "json", "--timestamp", TS]).stdout)
        self.assertEqual(out["findings"][0]["id"], "x")

    def test_malformed_input_exits_2(self):
        p = subprocess.run([sys.executable, SCRIPT, "--format", "json"],
                           input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)

    def test_empty_findings_valid(self):
        out = json.loads(run([], ["--format", "json", "--timestamp", TS]).stdout)
        self.assertEqual(out["findings"], [])
        sarif = json.loads(run([], ["--format", "sarif", "--timestamp", TS]).stdout)
        self.assertEqual(sarif["runs"][0]["results"], [])


if __name__ == "__main__":
    unittest.main()
