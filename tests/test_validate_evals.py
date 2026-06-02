"""Tests for scripts/validate-evals.py — the eval schema/validity gate.

Loads the (hyphenated) script by path, asserts the real 55-case suite validates
clean, and feeds synthetic bad cases to confirm each check fires.
"""
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MOD_PATH = os.path.join(HERE, "..", "skills", "review-all", "scripts", "validate-evals.py")
EVALS_DIR = os.path.join(HERE, "..", "skills", "review-all", "evals")

_spec = importlib.util.spec_from_file_location("validate_evals", MOD_PATH)
ve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ve)


def _good():
    return {
        "id": "x",
        "skill": "review-all",
        "query": "/review-all",
        "fixture": {"kind": "synthetic-diff", "files": {"a.ts": {"after": "const a = 1;\n"}}},
        "success_criteria": {"must_detect": []},
        "grader": {"method": "llm-rubric", "rubric": "PASS if X is flagged."},
    }


class TestValidateEvals(unittest.TestCase):
    def _run(self, obj, name="x.json"):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, name), "w") as f:
                json.dump(obj, f)
            return ve.validate_dir(d)

    def test_real_suite_is_valid(self):
        errors, _warnings, n = ve.validate_dir(EVALS_DIR)
        self.assertGreaterEqual(n, 55, "expected the full eval suite")
        self.assertEqual(errors, [], f"real eval suite must validate clean, got: {errors}")

    def test_good_case_passes(self):
        errors, _w, _n = self._run(_good())
        self.assertEqual(errors, [])

    def test_missing_rubric_fails(self):
        obj = _good()
        obj["grader"]["rubric"] = "   "
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("rubric" in e for e in errors), errors)

    def test_id_mismatch_fails(self):
        obj = _good()
        obj["id"] = "not-the-filename"
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("id" in e for e in errors), errors)

    def test_bad_fixture_kind_fails(self):
        obj = _good()
        obj["fixture"]["kind"] = "magic"
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("kind" in e for e in errors), errors)

    def test_empty_diff_not_allowlisted_fails(self):
        obj = _good()
        obj["fixture"]["files"] = {"a.ts": {"before": "const a = 1;\n"}}  # no after
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("empty diff" in e for e in errors), errors)

    def test_empty_diff_allowlisted_passes(self):
        obj = _good()
        obj["id"] = "04-empty-diff-noop"
        obj["fixture"]["files"] = {"a.ts": {"before": "const a = 1;\n"}}
        errors, _w, _n = self._run(obj, name="04-empty-diff-noop.json")
        self.assertEqual(errors, [])

    def test_delete_without_before_fails(self):
        obj = _good()
        obj["fixture"]["files"] = {"a.ts": {"delete": True}}
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("delete" in e for e in errors), errors)

    def test_rename_only_needs_count(self):
        obj = _good()
        del obj["fixture"]["files"]
        obj["fixture"]["rename_only"] = True
        errors, _w, _n = self._run(obj)
        self.assertTrue(any("files_changed" in e for e in errors), errors)

    def test_invalid_json_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.json"), "w") as f:
                f.write("{ not json")
            errors, _w, _n = ve.validate_dir(d)
            self.assertTrue(any("JSON" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
