"""Unit tests for skills/review-all/scripts/select-files.py (deterministic pre-dispatch)."""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "select-files.py")

EXCLUDE_REASONS = ["binary", "secret", "user_rule", "generated", "too_large"]


def run(records=None, args=None, raw=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=raw if raw is not None else json.dumps(records),
        capture_output=True, text=True)


def select(records, args=None):
    res = run(records, args)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def rec(path, status="M", insertions=1, deletions=1, size=100, diff=None):
    record = {"path": path, "status": status, "insertions": insertions, "deletions": deletions, "bytes": size}
    if diff is not None:
        record["diff"] = diff
    return record


def binary_rec(path, size=2000):
    return {"path": path, "status": "M", "insertions": None, "deletions": None, "bytes": size}


def excluded_reason(result, path):
    for entry in result["excluded"]:
        if entry["path"] == path:
            return entry["reason"]
    return None


class TestSelectFiles(unittest.TestCase):
    def test_mixed_input_each_excluded_file_has_correct_distinct_reason(self):
        records = [
            rec("package-lock.json"),
            binary_rec("assets/logo.png"),
            rec(".env"),
            rec("src/big.ts", size=300000),
            rec("Old.java", status="D"),
            rec("src/a.ts"),
        ]
        result = select(records)
        self.assertEqual([f["path"] for f in result["reviewable"]], ["Old.java", "src/a.ts"])
        self.assertEqual(excluded_reason(result, "package-lock.json"), "generated")
        self.assertEqual(excluded_reason(result, "assets/logo.png"), "binary")
        self.assertEqual(excluded_reason(result, ".env"), "secret")
        self.assertEqual(excluded_reason(result, "src/big.ts"), "too_large")

    def test_secret_beats_include(self):
        result = select([rec(".env")], ["--paths", ".env"])
        self.assertEqual(excluded_reason(result, ".env"), "secret")

    def test_secret_beats_user_exclude(self):
        result = select([rec(".env")], ["--exclude", ".env"])
        self.assertEqual(excluded_reason(result, ".env"), "secret")

    def test_test_files_are_not_excluded(self):
        result = select([rec("src/a.test.ts"), rec("FooTest.java")])
        by_path = {f["path"]: f for f in result["reviewable"]}
        self.assertIn("src/a.test.ts", by_path)
        self.assertIn("FooTest.java", by_path)
        self.assertIn("test", by_path["src/a.test.ts"]["classes"])
        self.assertIn("test", by_path["FooTest.java"]["classes"])

    def test_markdown_is_not_excluded_and_classified_docs(self):
        result = select([rec("README.md")])
        self.assertEqual(result["excluded"], [])
        self.assertEqual(result["reviewable"][0]["classes"], ["docs"])

    def test_deleted_files_are_reviewable(self):
        result = select([rec("Old.java", status="D")])
        self.assertEqual(result["excluded"], [])
        self.assertEqual(len(result["reviewable"]), 1)
        self.assertEqual(result["reviewable"][0]["status"], "D")

    def test_deleted_file_matching_generated_glob_is_still_excluded_generated(self):
        result = select([rec("dist/Old.js", status="D")])
        self.assertEqual(excluded_reason(result, "dist/Old.js"), "generated")

    def test_deleted_file_over_size_ceiling_is_still_too_large(self):
        result = select([rec("Old.java", status="D", size=300000)])
        self.assertEqual(excluded_reason(result, "Old.java"), "too_large")

    def test_counts_excluded_has_all_six_reason_keys_even_when_zero(self):
        result = select([rec("src/a.ts")])
        self.assertEqual(set(result["counts"]["excluded"].keys()), set(EXCLUDE_REASONS))
        self.assertTrue(all(v == 0 for v in result["counts"]["excluded"].values()))

    def test_brace_expansion_classifies_tsx_and_js(self):
        result = select([rec("src/a.tsx"), rec("src/a.js")])
        by_path = {f["path"]: f["classes"] for f in result["reviewable"]}
        self.assertEqual(by_path["src/a.tsx"], ["code", "ui"])
        self.assertEqual(by_path["src/a.js"], ["code"])

    def test_double_star_crosses_directory_separators(self):
        result = select([rec("a/b/c/node_modules/x.js")])
        self.assertEqual(excluded_reason(result, "a/b/c/node_modules/x.js"), "generated")

    def test_order_preserved_and_deterministic(self):
        records = [rec("z.ts"), rec("a.java", status="D"), rec("m.py")]
        result = select(records)
        self.assertEqual([f["path"] for f in result["reviewable"]], ["z.ts", "a.java", "m.py"])
        res1 = run(records)
        res2 = run(records)
        self.assertEqual(res1.stdout, res2.stdout)

    def test_pascal_case_filenames_still_classify_security(self):
        result = select([
            rec("src/AuthService.java"),
            rec("src/LoginForm.tsx"),
            rec("src/TokenStore.go"),
        ])
        by_path = {f["path"]: f["classes"] for f in result["reviewable"]}
        self.assertIn("security", by_path["src/AuthService.java"])
        self.assertIn("security", by_path["src/LoginForm.tsx"])
        self.assertIn("security", by_path["src/TokenStore.go"])

    def test_uppercase_extension_classifies_docs_and_resolves_markdown_pack(self):
        result = select([rec("README.MD")])
        self.assertEqual(result["reviewable"][0]["classes"], ["docs"])
        explained = json.loads(run(None, ["--explain", "README.MD"]).stdout)
        self.assertEqual(explained["rule_pack"], "markdown.md")

    def test_uppercase_directory_is_still_excluded_generated(self):
        result = select([rec("Frontend/DIST/bundle.js")])
        self.assertEqual(excluded_reason(result, "Frontend/DIST/bundle.js"), "generated")

    def test_user_exclude_prefix_stays_case_sensitive(self):
        result = select([rec("src/a.ts")], ["--exclude", "Src/"])
        self.assertEqual([f["path"] for f in result["reviewable"]], ["src/a.ts"])

    def test_json_config_file_classifies_data_not_code(self):
        result = select([rec("package.json")])
        self.assertEqual(result["reviewable"][0]["classes"], ["data"])

    def test_locale_json_classifies_data_and_i18n_only(self):
        result = select([rec("locales/fr.json")])
        self.assertEqual(result["reviewable"][0]["classes"], ["data", "i18n"])

    def test_github_workflow_yml_still_carries_security(self):
        result = select([rec(".github/workflows/ci.yml")])
        self.assertIn("security", result["reviewable"][0]["classes"])

    def test_content_signal_adds_security_class_despite_neutral_path(self):
        diff = 'export function render(el, comment) {\n  el.innerHTML = comment;\n}\n'
        result = select([rec("src/ui/widget.ts", diff=diff)])
        self.assertIn("security", result["reviewable"][0]["classes"])

    def test_content_signal_does_not_fire_without_a_diff_field(self):
        result = select([rec("src/ui/widget.ts")])
        self.assertNotIn("security", result["reviewable"][0]["classes"])

    def test_deleted_code_file_also_gets_contract(self):
        result = select([rec("src/legacy.ts", status="D")])
        classes = result["reviewable"][0]["classes"]
        self.assertIn("code", classes)
        self.assertIn("contract", classes)

    def test_api_directory_carries_contract_by_path(self):
        result = select([rec("src/api/user.ts")])
        self.assertIn("contract", result["reviewable"][0]["classes"])

    def test_benign_arithmetic_diff_gains_no_security_class(self):
        diff = "export function add(a, b) {\n  return a + b;\n}\n"
        result = select([rec("src/math/add.ts", diff=diff)])
        self.assertNotIn("security", result["reviewable"][0]["classes"])

    def test_malformed_stdin_exits_2(self):
        self.assertEqual(run(raw="not json").returncode, 2)

    def test_missing_path_key_exits_2(self):
        self.assertEqual(run(raw=json.dumps([{"status": "M"}])).returncode, 2)

    def test_non_list_stdin_exits_2(self):
        self.assertEqual(run(raw=json.dumps({"path": "a.ts"})).returncode, 2)


if __name__ == "__main__":
    unittest.main()
