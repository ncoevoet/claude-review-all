"""Unit tests for skills/review-all/scripts/eval-scorecard.py (eval scorecard)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "eval-scorecard.py")


def write_cases(evals_dir, cases):
    """cases: {id: must_detect_count}. must_detect_count 0 => precision counter-case."""
    for cid, n in cases.items():
        crit = {"id": cid, "skill": "review-all", "query": "/review-all",
                "success_criteria": {}}
        if n:
            crit["success_criteria"]["must_detect"] = [
                {"root_cause_key_like": "k", "file": "f"} for _ in range(n)]
        with open(os.path.join(evals_dir, f"{cid}.json"), "w") as fh:
            json.dump(crit, fh)


def run(lines, cases):
    with tempfile.TemporaryDirectory() as evals_dir:
        write_cases(evals_dir, cases)
        return subprocess.run(
            [sys.executable, SCRIPT, "--evals", evals_dir],
            input="\n".join(lines), capture_output=True, text=True)


def scorecard_fields(stdout):
    line = next(ln for ln in stdout.splitlines() if ln.startswith("SCORECARD,"))
    out = {}
    for pair in line[len("SCORECARD,"):].split(","):
        k, v = pair.split("=")
        out[k] = v
    return out


class TestScorecard(unittest.TestCase):
    def test_recall_and_precision_rates(self):
        # 2 recall cases (1 pass, 1 fail) -> 50%; 2 precision (both pass) -> 100%.
        lines = [
            "RESULT,r1,PASS (3/3)", "RESULT,r2,FAIL (0/3)",
            "RESULT,p1,PASS (3/3)", "RESULT,p2,PASS (2/3)",
        ]
        p = run(lines, {"r1": 1, "r2": 1, "p1": 0, "p2": 0})
        self.assertEqual(p.returncode, 0, p.stderr)
        f = scorecard_fields(p.stdout)
        self.assertEqual(f["recall"], "50.00")
        self.assertEqual(f["precision"], "100.00")
        # F1 of 50 and 100 = 2*50*100/150 = 66.67
        self.assertEqual(f["f1"], "66.67")

    def test_errored_excluded_from_rates(self):
        lines = ["RESULT,r1,PASS (3/3)", "RESULT,r2,ERROR (0/3 graded)"]
        f = scorecard_fields(run(lines, {"r1": 1, "r2": 1}).stdout)
        self.assertEqual(f["recall"], "100.00")  # r2 errored -> not counted

    def test_snr_signal_capped_noise_counted(self):
        # recall r1 (must_detect=1) reports 3 crit+imp -> signal capped at 1.
        # precision p1 reports 2 crit+imp -> noise=2. SNR = 1/2 = 0.5.
        lines = [
            "RESULT,r1,PASS (1/1)", "SCORE,r1,2,1,0,4,0,7",
            "RESULT,p1,FAIL (0/1)", "SCORE,p1,1,1,0,0,0,2",
        ]
        f = scorecard_fields(run(lines, {"r1": 1, "p1": 0}).stdout)
        self.assertEqual(f["signal"], "1.0")
        self.assertEqual(f["noise"], "2.0")
        self.assertEqual(f["snr"], "0.5000")

    def test_snr_averages_multiple_runs_per_case(self):
        # two SCORE rows for p1: noise = mean(2, 4) crit+imp = mean(2,4)=3.
        lines = [
            "RESULT,p1,FAIL (0/2)",
            "SCORE,p1,1,1,0,0,0,2", "SCORE,p1,2,2,0,0,0,4",
        ]
        f = scorecard_fields(run(lines, {"p1": 0}).stdout)
        self.assertEqual(f["noise"], "3.0")

    def test_no_score_lines_omits_snr(self):
        lines = ["RESULT,r1,PASS (1/1)"]
        out = run(lines, {"r1": 1}).stdout
        self.assertNotIn("SNR (proxy)", out)
        self.assertIn("snr=,", scorecard_fields_line(out))

    def test_unknown_id_ignored(self):
        lines = ["RESULT,ghost,PASS (1/1)", "RESULT,r1,PASS (1/1)"]
        f = scorecard_fields(run(lines, {"r1": 1}).stdout)
        self.assertEqual(f["recall"], "100.00")  # ghost not in evals -> unknown


def scorecard_fields_line(stdout):
    return next(ln for ln in stdout.splitlines() if ln.startswith("SCORECARD,"))


if __name__ == "__main__":
    unittest.main()
