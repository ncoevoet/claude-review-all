"""Unit tests for skills/review-all/scripts/state-sweep.py (Phase 2.5 lifecycle)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "state-sweep.py")


class TestStateSweep(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def sweep(self, findings, seen, changed=None, head="HEAD1"):
        sp = os.path.join(self.d, "state.json")
        with open(sp, "w") as fh:
            json.dump({"version": 1, "migrations": [], "findings": findings}, fh)
        kp = os.path.join(self.d, "seen.json")
        with open(kp, "w") as fh:
            json.dump(seen, fh)
        env = dict(os.environ)
        if changed is not None:
            cp = os.path.join(self.d, "changed.json")
            with open(cp, "w") as fh:
                json.dump(changed, fh)
            env["STATE_SWEEP_CHANGED_KEYS"] = cp
        p = subprocess.run([sys.executable, SCRIPT, sp, head, kp],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(sp) as fh:
            return json.load(fh)["findings"]

    # --- F1 regression: a resolved finding that re-surfaces must reopen ---
    def test_fixed_reopens_on_resight(self):
        f = self.sweep({"k": {"status": "fixed", "fix_commit_sha": "x"}}, ["k"])
        self.assertEqual(f["k"]["status"], "open")
        self.assertIsNone(f["k"]["fix_commit_sha"])

    def test_stale_reopens_on_resight(self):
        f = self.sweep({"k": {"status": "stale", "miss_count": 2}}, ["k"])
        self.assertEqual(f["k"]["status"], "open")

    # --- contract: the script does NOT insert brand-new keys ---
    def test_new_key_is_not_inserted_by_script(self):
        f = self.sweep({"k": {"status": "open"}}, ["k", "newkey"])
        self.assertNotIn("newkey", f)

    # --- existing documented transitions ---
    def test_open_to_fixed_when_changed_and_unseen(self):
        f = self.sweep({"k": {"status": "open"}}, [], changed=["k"])
        self.assertEqual(f["k"]["status"], "fixed")

    def test_open_to_stale_after_two_misses(self):
        f = self.sweep({"k": {"status": "open", "miss_count": 1}}, [])
        self.assertEqual(f["k"]["status"], "stale")

    def test_open_first_miss_stays_open(self):
        f = self.sweep({"k": {"status": "open", "miss_count": 0}}, [])
        self.assertEqual(f["k"]["status"], "open")
        self.assertEqual(f["k"]["miss_count"], 1)

    def test_snoozed_expired_reopens(self):
        f = self.sweep({"k": {"status": "snoozed",
                              "snoozed_until": "2000-01-01T00:00:00+00:00"}}, [])
        self.assertEqual(f["k"]["status"], "open")

    def test_snoozed_future_stays_snoozed(self):
        f = self.sweep({"k": {"status": "snoozed",
                              "snoozed_until": "2999-01-01T00:00:00+00:00"}}, [])
        self.assertEqual(f["k"]["status"], "snoozed")

    def test_wakeup_does_not_cascade_to_miss_or_fixed(self):
        # Expired snooze, not re-seen: becomes open and is left for next run --
        # it must NOT also be counted as a miss in the same pass.
        f = self.sweep({"k": {"status": "snoozed", "miss_count": 0,
                              "snoozed_until": "2000-01-01T00:00:00+00:00"}}, [])
        self.assertEqual(f["k"]["status"], "open")
        self.assertEqual(f["k"].get("miss_count", 0), 0)

    def test_wontfix_reopens_when_code_changed(self):
        f = self.sweep({"k": {"status": "wontfix", "fix_commit_sha": "y"}}, [], changed=["k"])
        self.assertEqual(f["k"]["status"], "open")

    def test_resight_refreshes_last_seen_and_resets_miss(self):
        f = self.sweep({"k": {"status": "open", "miss_count": 3}}, ["k"], head="NEWSHA")
        self.assertEqual(f["k"]["miss_count"], 0)
        self.assertEqual(f["k"]["last_seen_sha"], "NEWSHA")


if __name__ == "__main__":
    unittest.main()
