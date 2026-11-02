#!/usr/bin/env python3
"""Tests for scripts/spawn-audit.py — role/model/effort per subagent transcript."""
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "review-all", "scripts", "spawn-audit.py")
_spec = importlib.util.spec_from_file_location("spawn_audit", SCRIPT)
sa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sa)


def write_agent(sub, agent_id, prompt, turns, description=None, asked=None, meta_raw=None):
    lines = [{"type": "user", "message": {"role": "user", "content": prompt}},
             # request-shape noise: tool schemas mention model/effort and must be ignored
             {"type": "api-request-shape",
              "shape": {"tools": [{"model": "claude-decoy", "input_schema": {"properties": {"effort": {}}}}]}}]
    for model, effort in turns:
        lines.append({"type": "assistant", "message": {"model": model}, "effort": effort})
    with open(os.path.join(sub, "agent-%s.jsonl" % agent_id), "w") as fh:
        fh.write("\n".join(json.dumps(x) for x in lines) + "\nnot json\n")
    meta_path = os.path.join(sub, "agent-%s.meta.json" % agent_id)
    if meta_raw is not None:
        with open(meta_path, "w") as fh:
            fh.write(meta_raw)
    elif description is not None or asked is not None:
        with open(meta_path, "w") as fh:
            json.dump({"description": description, "model": asked}, fh)


class SpawnAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.session = os.path.join(self.tmp, "sess.jsonl")
        open(self.session, "w").close()
        self.sub = os.path.join(self.tmp, "sess", "subagents")
        os.makedirs(self.sub)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_roles_models_efforts(self):
        write_agent(self.sub, "a1", "intro\n# Agent 2: Bugs & Security\nbody",
                    [("claude-opus-5-5", "xhigh"), ("claude-opus-5-5", "xhigh")])
        write_agent(self.sub, "a2", "# Phase 2.5 Verifier (Batch Mode)\n", [("claude-haiku-5-5", "medium")])
        write_agent(self.sub, "a3", "# Phase 2.5 Verifier (Batch Mode)\n", [("claude-haiku-5-5", "medium")])
        rows = sa.audit(self.session)
        self.assertEqual(rows[("Agent 2: Bugs & Security", "?", "claude-opus-5-5", "xhigh")], 1)
        self.assertEqual(rows[("Phase 2.5 Verifier", "?", "claude-haiku-5-5", "medium")], 2)
        self.assertNotIn("claude-decoy", " ".join(m for _, _, m, _ in rows))

    def test_persona_beats_free_text_description_and_mixed_effort_listed(self):
        # Two spawns of one axis with different orchestrator-typed labels must group into one row.
        for i, label in enumerate(["Review: performance axis", "418 review: 07 performance"]):
            write_agent(self.sub, "b%d" % i, "<persona>Read and follow: /x/agents/07-performance.md</persona>",
                        [("claude-opus-5-5", "high"), ("claude-opus-5-5", "medium")], description=label, asked="opus")
        rows = sa.audit(os.path.join(self.tmp, "sess") + "/")
        self.assertEqual(dict(rows), {("07-performance", "opus", "claude-opus-5-5", "high,medium"): 2})

    def test_verifier_quoting_an_axis_heading_is_still_the_verifier(self):
        write_agent(self.sub, "v1", "# Phase 2.5 Verifier (Batch Mode)\nfindings from\n# Agent 2: Bugs & Security\n",
                    [("claude-haiku-5-5", "high")])
        self.assertEqual(list(sa.audit(self.session)), [("Phase 2.5 Verifier", "?", "claude-haiku-5-5", "high")])

    def test_description_fallback_null_text_and_malformed_meta(self):
        write_agent(self.sub, "c1", [{"type": "text", "text": None}, {"type": "text", "text": "free-form"}], [],
                    description="Deep-dive #3", asked="opus")
        write_agent(self.sub, "c2", "free-form task", [], meta_raw="{not json")
        self.assertEqual(dict(sa.audit(self.session)),
                         {("Deep-dive #3", "opus", "?", "?"): 1, ("other", "?", "?", "?"): 1})

    def test_subagents_dir_argument_is_accepted(self):
        write_agent(self.sub, "e1", "<persona>agents/verifier.md</persona>", [("claude-haiku-5-5", "high")])
        self.assertEqual(list(sa.audit(self.sub)), [("verifier", "?", "claude-haiku-5-5", "high")])

    def test_main_exit_codes(self):
        empty = os.path.join(self.tmp, "none.jsonl")
        self.assertEqual(sa.main(["x", empty]), 2)
        self.assertEqual(sa.main(["x"]), 2)
        write_agent(self.sub, "d1", "# Agent 1: Standards & Clarity\n", [("claude-sonnet-5-5", "medium")])
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(sa.main(["x", self.session, "--json"]), 0)
        self.assertEqual(json.loads(buf.getvalue())[0]["effort"], "medium")


if __name__ == "__main__":
    unittest.main()
