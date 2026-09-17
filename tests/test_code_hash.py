"""Unit tests for skills/review-all/scripts/code-hash.py (state.json code_hash)."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "code-hash.py")


class TestCodeHash(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def write(self, rel, text):
        path = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        return rel

    def run_hash(self, *args):
        p = subprocess.run([sys.executable, SCRIPT] + list(args),
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def test_anchored_window_is_three_lines_either_side(self):
        rel = self.write("src/a.py", "\n".join("l%d" % i for i in range(1, 11)) + "\n")
        got = self.run_hash("anchored", self.d, rel + ":5")
        want = hashlib.sha256("\n".join("l%d" % i for i in range(2, 9)).encode()).hexdigest()
        self.assertEqual(got, want)

    def test_anchored_window_clamps_at_file_start(self):
        rel = self.write("src/b.py", "l1\nl2\nl3\nl4\n")
        got = self.run_hash("anchored", self.d, rel + ":1")
        want = hashlib.sha256("l1\nl2\nl3\nl4".encode()).hexdigest()
        self.assertEqual(got, want)

    def test_edit_at_flagged_line_changes_the_hash(self):
        rel = self.write("src/c.py", "a\nb\nTARGET\nd\ne\n")
        before = self.run_hash("anchored", self.d, rel + ":3")
        self.write("src/c.py", "a\nb\nCHANGED\nd\ne\n")
        self.assertNotEqual(before, self.run_hash("anchored", self.d, rel + ":3"))

    def test_edit_far_from_flagged_line_leaves_the_hash_alone(self):
        body = ["l%d" % i for i in range(1, 31)]
        rel = self.write("src/d.py", "\n".join(body) + "\n")
        before = self.run_hash("anchored", self.d, rel + ":5")
        body[25] = "unrelated edit"
        self.write("src/d.py", "\n".join(body) + "\n")
        self.assertEqual(before, self.run_hash("anchored", self.d, rel + ":5"))

    def test_missing_file_hashes_empty_and_never_matches(self):
        rel = self.write("src/e.py", "a\nb\nc\n")
        present = self.run_hash("anchored", self.d, rel + ":2")
        os.remove(os.path.join(self.d, rel))
        gone = self.run_hash("anchored", self.d, rel + ":2")
        self.assertEqual(gone, hashlib.sha256(b"").hexdigest())
        self.assertNotEqual(gone, present)

    def test_anchorless_is_the_identifying_tuple(self):
        got = self.run_hash("anchorless", "src/x.ts:0", "CRITICAL", "injection:src/x.ts:q")
        want = hashlib.sha256(b"src/x.ts:0|CRITICAL|injection:src/x.ts:q").hexdigest()
        self.assertEqual(got, want)

    def test_bad_usage_exits_nonzero(self):
        p = subprocess.run([sys.executable, SCRIPT, "anchored", self.d, "no-line-number"],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
