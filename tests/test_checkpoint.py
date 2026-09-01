"""Unit tests for skills/review-all/scripts/checkpoint.py (Phase 2 per-axis resume)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all")
SCRIPT = os.path.join(SKILL_ROOT, "scripts", "checkpoint.py")

DIFF = b"diff --git a/src/x.ts b/src/x.ts\n+const x = 1;\n"
FINDINGS = [{"root_cause_key": "rck-1", "severity": "CRITICAL", "file": "src/x.ts"}]


class CheckpointCase(unittest.TestCase):
    """Each test gets its own repo cwd, checkpoint dir, and skill-root copy.

    The skill-root copy is what makes the fingerprint half of the key testable:
    editing a persona in the copy must invalidate a checkpoint, and that cannot
    be shown by mutating the real skill tree.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="review-all-checkpoint-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        self.dir = os.path.join(self.repo, ".claude", "review-all", "checkpoints")
        os.makedirs(self.repo)
        self.skill = os.path.join(self.tmp, "skill")
        os.makedirs(os.path.join(self.skill, "scripts"))
        os.makedirs(os.path.join(self.skill, "agents"))
        shutil.copy(SCRIPT, os.path.join(self.skill, "scripts", "checkpoint.py"))
        self.write(os.path.join(self.skill, "SKILL.md"), "# skill\n")
        self.write(os.path.join(self.skill, "agents", "01-standards.md"), "persona v1\n")
        self.script = os.path.join(self.skill, "scripts", "checkpoint.py")

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_cmd(self, args, stdin=b""):
        return subprocess.run(
            [sys.executable, self.script] + args + ["--dir", self.dir],
            input=stdin, capture_output=True, cwd=self.repo)

    def load(self, head="sha1", diff=DIFF):
        res = self.run_cmd(["load", "--head", head], diff)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def save(self, run_key, axis="01-standards", findings=None, head="sha1"):
        payload = json.dumps(FINDINGS if findings is None else findings).encode()
        return self.run_cmd(
            ["save", "--run-key", run_key, "--axis", axis, "--head", head], payload)


class TestKey(CheckpointCase):
    def test_key_is_stable_across_invocations(self):
        self.assertEqual(self.load()["runKey"], self.load()["runKey"])

    def test_key_changes_with_head(self):
        self.assertNotEqual(self.load(head="sha1")["runKey"],
                            self.load(head="sha2")["runKey"])

    def test_key_changes_with_diff(self):
        self.assertNotEqual(self.load()["runKey"],
                            self.load(diff=DIFF + b"+const y = 2;\n")["runKey"])

    def test_key_changes_with_persona_edit(self):
        before = self.load()["runKey"]
        self.write(os.path.join(self.skill, "agents", "01-standards.md"), "persona v2\n")
        self.assertNotEqual(before, self.load()["runKey"])

    def test_key_changes_with_review_md(self):
        before = self.load()["runKey"]
        self.write(os.path.join(self.repo, "REVIEW.md"), "only report tenant scoping\n")
        self.assertNotEqual(before, self.load()["runKey"])

    def test_key_changes_with_config(self):
        before = self.load()["runKey"]
        os.makedirs(os.path.join(self.repo, ".claude"), exist_ok=True)
        self.write(os.path.join(self.repo, ".claude", "review-all.json"),
                   '{"quotaDebt": 0}\n')
        self.assertNotEqual(before, self.load()["runKey"])


class TestRoundTrip(CheckpointCase):
    def test_load_on_empty_store_resumes_nothing(self):
        result = self.load()
        self.assertEqual(result["resumed"], {})
        self.assertEqual(result["ignored"], [])

    def test_saved_axis_is_resumed_on_identical_run(self):
        key = self.load()["runKey"]
        self.assertEqual(self.save(key).returncode, 0)
        resumed = self.load()["resumed"]
        self.assertEqual(list(resumed), ["01-standards"])
        self.assertEqual(resumed["01-standards"]["findings"], FINDINGS)

    def test_empty_findings_is_a_real_result_not_a_miss(self):
        """An axis that correctly found nothing must not be re-run."""
        key = self.load()["runKey"]
        self.save(key, findings=[])
        self.assertEqual(self.load()["resumed"]["01-standards"]["findings"], [])

    def test_axes_are_independent(self):
        key = self.load()["runKey"]
        self.save(key, axis="01-standards")
        self.save(key, axis="02-bugs-security", findings=[])
        self.assertEqual(sorted(self.load()["resumed"]), ["01-standards", "02-bugs-security"])

    def test_save_overwrites_a_stale_file_for_the_same_axis(self):
        self.save("stale-key", findings=[{"root_cause_key": "old"}])
        key = self.load()["runKey"]  # stale file dropped by load
        self.save(key)
        self.assertEqual(self.load()["resumed"]["01-standards"]["findings"], FINDINGS)


class TestInvalidation(CheckpointCase):
    def test_new_head_invalidates_and_deletes(self):
        self.save(self.load(head="sha1")["runKey"])
        result = self.load(head="sha2")
        self.assertEqual(result["resumed"], {})
        self.assertEqual(result["ignored"],
                         [{"axis": "01-standards", "reason": "key-mismatch"}])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "01-standards.json")))

    def test_changed_diff_invalidates(self):
        self.save(self.load()["runKey"])
        self.assertEqual(self.load(diff=b"other diff\n")["resumed"], {})

    def test_unreadable_checkpoint_is_ignored_and_deleted(self):
        os.makedirs(self.dir, exist_ok=True)
        self.write(os.path.join(self.dir, "07-performance.json"), "{not json")
        result = self.load()
        self.assertEqual(result["ignored"],
                         [{"axis": "07-performance", "reason": "unreadable"}])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "07-performance.json")))

    def test_axis_mismatch_is_ignored(self):
        key = self.load()["runKey"]
        self.save(key, axis="01-standards")
        os.rename(os.path.join(self.dir, "01-standards.json"),
                  os.path.join(self.dir, "09-api-contract.json"))
        self.assertEqual(self.load()["ignored"],
                         [{"axis": "09-api-contract", "reason": "axis-mismatch"}])

    def test_wrong_schema_version_is_ignored(self):
        key = self.load()["runKey"]
        self.save(key)
        path = os.path.join(self.dir, "01-standards.json")
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        doc["schemaVersion"] = 99
        self.write(path, json.dumps(doc))
        self.assertEqual(self.load()["ignored"],
                         [{"axis": "01-standards", "reason": "schema"}])


class TestSaveContract(CheckpointCase):
    def test_saved_file_carries_the_full_key_record(self):
        key = self.load()["runKey"]
        self.save(key, head="sha1")
        with open(os.path.join(self.dir, "01-standards.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["schemaVersion"], 1)
        self.assertEqual(doc["runKey"], key)
        self.assertEqual(doc["axis"], "01-standards")
        self.assertEqual(doc["head"], "sha1")
        self.assertTrue(doc["savedAt"])

    def test_save_creates_the_directory(self):
        self.assertFalse(os.path.isdir(self.dir))
        self.assertEqual(self.save("k").returncode, 0)
        self.assertTrue(os.path.isdir(self.dir))

    def test_path_traversal_axis_is_rejected(self):
        self.assertEqual(self.save("k", axis="../../escape").returncode, 2)

    def test_non_array_stdin_is_rejected(self):
        res = self.run_cmd(["save", "--run-key", "k", "--axis", "01-standards"],
                           b'{"findings": []}')
        self.assertEqual(res.returncode, 2)

    def test_malformed_stdin_is_rejected(self):
        res = self.run_cmd(["save", "--run-key", "k", "--axis", "01-standards"],
                           b"not json")
        self.assertEqual(res.returncode, 2)

    def test_no_temp_files_left_behind(self):
        self.save("k")
        self.assertEqual([f for f in os.listdir(self.dir) if f.startswith(".")], [])


if __name__ == "__main__":
    unittest.main()
