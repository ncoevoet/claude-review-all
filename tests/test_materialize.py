"""Unit tests for materialize-fixture.py — fixtures must become real git repos."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts",
    "materialize-fixture.py")


def materialize(spec):
    d = tempfile.mkdtemp()
    fx = os.path.join(d, "fx.json")
    with open(fx, "w") as f:
        json.dump(spec, f)
    return subprocess.run([sys.executable, SCRIPT, fx], capture_output=True, text=True)


def git_diff(repo):
    # Fixtures stage their after-state, so the reviewable diff is the cached one.
    return subprocess.run(["git", "-C", repo, "--no-pager", "diff", "--cached"],
                          capture_output=True, text=True).stdout


class TestMaterialize(unittest.TestCase):
    def test_before_after_produces_diff(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"a.ts": {"before": "x\n", "after": "y\n"}}}})
        self.assertEqual(p.returncode, 0, p.stderr)
        d = git_diff(p.stdout.strip())
        self.assertIn("-x", d)
        self.assertIn("+y", d)

    def test_added_file_shows_in_diff(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"new.ts": {"after": "hello\n"}}}})
        d = git_diff(p.stdout.strip())
        self.assertIn("new.ts", d)
        self.assertIn("+hello", d)

    def test_rename_only_generates_n_files(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "rename_only": True, "files_changed": 5}})
        names = subprocess.run(
            ["git", "-C", p.stdout.strip(), "--no-pager", "diff", "--cached", "--name-only"],
            capture_output=True, text=True).stdout.split()
        self.assertEqual(len(names), 5)

    def test_clean_tree_when_no_after(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"a.ts": {"before": "x\n"}}}})
        self.assertEqual(git_diff(p.stdout.strip()).strip(), "")

    def test_delete_shows_as_removed(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"gone.ts": {"before": "x\n", "delete": True}}}})
        self.assertEqual(p.returncode, 0, p.stderr)
        ns = subprocess.run(
            ["git", "-C", p.stdout.strip(), "--no-pager", "diff", "--cached", "--name-status"],
            capture_output=True, text=True).stdout
        self.assertIn("D", ns)
        self.assertIn("gone.ts", ns)

    def test_unsupported_shape_exits_3(self):
        self.assertEqual(materialize({"fixture": {"kind": "description-only"}}).returncode, 3)

    def test_seed_raw_writes_verbatim_and_stays_out_of_diff(self):
        raw = {"claudeMdHash": "abc", "toolchain": {"test": "mvn test"}}
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"a.ts": {"before": "x\n", "after": "y\n"}},
                                     "seed_profile_cache": {"raw": raw}}})
        self.assertEqual(p.returncode, 0, p.stderr)
        repo = p.stdout.strip()
        with open(os.path.join(repo, ".claude", "cache", "review-all-profile.json")) as f:
            self.assertEqual(json.load(f), raw)
        self.assertNotIn("review-all-profile", git_diff(repo))

    def test_seed_rules_yields_discover_hit(self):
        p = materialize({"fixture": {"kind": "synthetic-diff",
                                     "files": {"CLAUDE.md": {"before": "# Never use eval\n"},
                                               "a.ts": {"before": "x\n", "after": "y\n"}},
                                     "seed_profile_cache": {"rules": "Never use eval"}}})
        self.assertEqual(p.returncode, 0, p.stderr)
        repo = p.stdout.strip()
        discover = os.path.join(os.path.dirname(SCRIPT), "discover.sh")
        out = subprocess.run(["bash", discover, repo], capture_output=True, text=True)
        disc = json.loads(out.stdout)
        self.assertEqual(disc["cache"]["status"], "HIT", disc["cache"])
        self.assertEqual(disc["cachedProfile"]["rules"]["global"], "Never use eval")


if __name__ == "__main__":
    unittest.main()
