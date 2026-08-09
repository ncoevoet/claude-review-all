"""Unit tests for skills/review-all/scripts/agent-order.py (Phase 2 diff ordering)."""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "skills", "review-all", "scripts", "agent-order.py")


def run(paths, args=None, raw=None):
    return subprocess.run(
        [sys.executable, SCRIPT] + (args or []),
        input=raw if raw is not None else json.dumps(paths),
        capture_output=True, text=True)


def orders(paths, args=None):
    res = run(paths, args)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def files(n):
    return [f"src/module{i}/file{i}.ts" for i in range(n)]


class TestAgentOrder(unittest.TestCase):
    def test_is_deterministic_across_invocations(self):
        paths = files(12)
        self.assertEqual(orders(paths), orders(paths))

    def test_each_agent_gets_a_permutation_of_the_input(self):
        paths = files(10)
        for agent, order in orders(paths).items():
            self.assertEqual(sorted(order), sorted(paths), f"agent {agent} lost or gained files")

    def test_agents_receive_different_orders(self):
        result = orders(files(10))
        self.assertNotEqual(result["1"], result["2"])

    def test_agent_count_is_configurable(self):
        self.assertEqual(sorted(orders(files(5), ["--agents", "3"]).keys()), ["1", "2", "3"])

    def test_order_is_stable_under_filtering(self):
        """An agent reviewing a subset must get the subset's order from the full permutation.

        This is what lets one call serve every agent even though the security and
        a11y personas each see only their own slice of the diff.
        """
        paths = files(20)
        subset = [p for i, p in enumerate(paths) if i % 3 == 0]
        full = orders(paths)["6"]
        direct = orders(subset)["6"]
        self.assertEqual([p for p in full if p in set(subset)], direct)

    def test_empty_input_yields_empty_orders(self):
        result = orders([])
        self.assertEqual(result["1"], [])

    def test_malformed_json_exits_2(self):
        self.assertEqual(run(None, raw="not json").returncode, 2)

    def test_non_string_elements_exit_2(self):
        self.assertEqual(run([1, 2, 3]).returncode, 2)

    def test_zero_agents_exits_2(self):
        self.assertEqual(run(files(3), ["--agents", "0"]).returncode, 2)


if __name__ == "__main__":
    unittest.main()
