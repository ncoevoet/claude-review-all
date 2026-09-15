"""Unit tests for skills/review-all/scripts/select-agents.py (deterministic spawn decisions)."""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "select-agents.py")

ALWAYS_IDS = {
    "01-standards", "02-bugs-security", "03-dry-smells",
    "04-consistency-history", "05-simplification", "07-performance",
}
CONDITIONAL_IDS = ["06-security-deep-dive", "08-test-quality", "09-api-contract", "10-a11y-i18n"]
AGENT_IDS = ALWAYS_IDS | set(CONDITIONAL_IDS)


def run(payload, args=None, raw=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True, text=True)


def select(reviewable, args=None):
    res = run({"reviewable": reviewable}, args)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def entry(path, status="M", classes=None, size=100):
    return {"path": path, "status": status, "ext": path.rsplit(".", 1)[-1], "bytes": size, "classes": classes or []}


class TestSelectAgents(unittest.TestCase):
    def test_go_only_backend_diff_spawns_exactly_six_always_agents(self):
        result = select([
            entry("main.go", classes=["code"]),
            entry("util.go", classes=["code"]),
        ])
        spawned = {aid for aid, d in result["agents"].items() if d["spawn"]}
        self.assertEqual(spawned, ALWAYS_IDS)
        reasons = set()
        for aid in CONDITIONAL_IDS:
            self.assertFalse(result["agents"][aid]["spawn"])
            self.assertTrue(result["agents"][aid]["reason"])
            reasons.add(result["agents"][aid]["reason"])
        self.assertEqual(len(reasons), 4)

    def test_ui_file_spawns_a11y_i18n_with_that_file(self):
        result = select([entry("src/App.tsx", classes=["code", "ui"])])
        self.assertTrue(result["agents"]["10-a11y-i18n"]["spawn"])
        self.assertEqual(result["agents"]["10-a11y-i18n"]["files"], ["src/App.tsx"])

    def test_added_file_with_no_test_still_spawns_test_quality(self):
        result = select([entry("main.go", status="A", classes=["code"])])
        self.assertTrue(result["agents"]["08-test-quality"]["spawn"])

    def test_added_data_file_alone_does_not_spawn_test_quality(self):
        result = select([entry("package.json", status="A", classes=["data"])])
        self.assertFalse(result["agents"]["08-test-quality"]["spawn"])

    def test_added_code_file_alone_spawns_test_quality(self):
        result = select([entry("src/a.ts", status="A", classes=["code"])])
        self.assertTrue(result["agents"]["08-test-quality"]["spawn"])

    def test_skip_overrides_always_rule(self):
        result = select([entry("a.go", classes=["code"])], ["--skip", "02-bugs-security"])
        self.assertEqual(
            result["agents"]["02-bugs-security"],
            {"spawn": False, "files": [], "reason": "skipAgents"})

    def test_extra_adds_agent_with_every_reviewable_file(self):
        result = select([entry("a.go", classes=["code"]), entry("b.go", classes=["code"])], ["--extra", "custom-axis"])
        self.assertEqual(
            result["agents"]["custom-axis"],
            {"spawn": True, "files": ["a.go", "b.go"], "reason": "extraAgents"})

    def test_empty_reviewable_spawns_nothing(self):
        result = select([])
        self.assertEqual(set(result["agents"].keys()), AGENT_IDS)
        self.assertTrue(all(not d["spawn"] for d in result["agents"].values()))
        self.assertEqual(result["counts"]["spawned"], 0)

    def test_rule_packs_group_python_and_java_files(self):
        result = select([
            entry("a.py", classes=["code"]),
            entry("b.py", classes=["code"]),
            entry("C.java", classes=["code"]),
        ])
        self.assertEqual(set(result["rule_packs"]["python.md"]), {"a.py", "b.py"})
        self.assertEqual(result["rule_packs"]["java.md"], ["C.java"])

    def test_unmatched_file_falls_back_to_default_pack(self):
        result = select([entry("README.txt", classes=["docs"])])
        self.assertEqual(result["rule_packs"]["default.md"], ["README.txt"])

    def test_malformed_stdin_exits_2(self):
        self.assertEqual(run(None, raw="not json").returncode, 2)

    def test_missing_reviewable_key_exits_2(self):
        self.assertEqual(run({"foo": []}).returncode, 2)


if __name__ == "__main__":
    unittest.main()
