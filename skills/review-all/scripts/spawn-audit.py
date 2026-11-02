#!/usr/bin/env python3
"""spawn-audit.py — show the model and reasoning effort each review subagent ACTUALLY ran at.

The spawn contract (SKILL.md) says every spawn names its model and effort. Whether
the orchestrator honoured it is a runtime claim, and the docs are not proof: the
verifier tier once ran one to two tiers above its documented default, and the
verifiers ran at the session's `medium` effort while the axes ran at `high`. Both
were invisible until someone read the transcripts. This script reads them.

Input: a main-session transcript `<session>.jsonl` (or its `<session>/` dir).
Claude Code stores each subagent at `<session>/subagents/agent-<id>.jsonl`, with
`agent-<id>.meta.json` beside it. Per subagent:
  role    from its first user prompt: the persona file id inside the
          `<persona>` block (`07-performance`, `verifier` — orchestrators often
          pass the persona by path), else the persona heading (`# Phase 2.5
          Verifier`, else the first line-anchored `# Agent N: <name>`), so one
          axis groups into one row across sessions; else the meta.json
          `description` (a free-text label the orchestrator typed); else `other`
  asked   the `model` the spawn requested (meta.json), `?` when absent
  model   distinct `message.model` values of its assistant turns — compare with
          `asked` to catch a tier drift
  effort  distinct top-level `effort` values of its assistant turns
Assistant turns only: tool schemas embedded in request-shape lines also contain
the strings "model" and "effort" and would pollute a naive grep.

Usage: spawn-audit.py <session.jsonl | session-dir> [--json]
Output: one `role<TAB>asked<TAB>model<TAB>effort<TAB>count` row per distinct combination.
Exit 0 = printed, 2 = no subagent transcripts found.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

PERSONA_RE = re.compile(r"<persona>[^<]*?agents/(\d\d-[a-z0-9-]+|verifier)\.md")
VERIFIER_RE = re.compile(r"^#+ *Phase 2\.5 Verifier", re.M)
AXIS_RE = re.compile(r"^#+ *(Agent \d+: [A-Za-z&/0-9 ]+?)\s*(?:\(|$)", re.M)


def _first_prompt(line):
    msg = line.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text") or "" for c in content if isinstance(c, dict))
    return ""


def _meta(path):
    try:
        with open(path[: -len(".jsonl")] + ".meta.json", encoding="utf-8") as fh:
            meta = json.load(fh)
        return meta if isinstance(meta, dict) else {}
    except (OSError, ValueError):
        return {}


def _role_from_prompt(text):
    m = PERSONA_RE.search(text)
    if m:
        return m.group(1)
    if VERIFIER_RE.search(text):
        return "Phase 2.5 Verifier"
    m = AXIS_RE.search(text)
    return m.group(1).strip() if m else ""


def audit_agent(path):
    """Return (role, asked, models, efforts) for one subagent transcript."""
    meta = _meta(path)
    role, seen_prompt, models, efforts = "", False, set(), set()
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            try:
                line = json.loads(raw)
            except ValueError:
                continue
            kind = line.get("type")
            if not seen_prompt and kind == "user":
                seen_prompt = True
                role = _role_from_prompt(_first_prompt(line))
            elif kind == "assistant":
                model = (line.get("message") or {}).get("model")
                if model:
                    models.add(model)
                if line.get("effort"):
                    efforts.add(line["effort"])
    role = role or meta.get("description") or "other"
    return role, meta.get("model") or "?", sorted(models), sorted(efforts)


def audit(session):
    base = session[: -len(".jsonl")] if session.endswith(".jsonl") else session.rstrip("/")
    if os.path.basename(base) == "subagents":
        base = os.path.dirname(base)
    paths = sorted(glob.glob(os.path.join(base, "subagents", "*.jsonl")))
    rows = Counter()
    for p in paths:
        role, asked, models, efforts = audit_agent(p)
        rows[(role, asked, ",".join(models) or "?", ",".join(efforts) or "?")] += 1
    return rows


def main(argv):
    args = [a for a in argv[1:] if a != "--json"]
    if len(args) != 1:
        print("usage: spawn-audit.py <session.jsonl | session-dir> [--json]", file=sys.stderr)
        return 2
    rows = audit(args[0])
    if not rows:
        print("spawn-audit: no subagent transcripts under %s" % args[0], file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps([{"role": r, "asked": a, "model": m, "effort": e, "count": n}
                          for (r, a, m, e), n in sorted(rows.items())], indent=2))
    else:
        for (r, a, m, e), n in sorted(rows.items()):
            print("%s\t%s\t%s\t%s\t%d" % (r, a, m, e, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
