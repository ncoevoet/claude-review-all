#!/usr/bin/env python3
"""agent-order.py — Phase 2 per-agent diff file ordering.

Reads a JSON array of changed file paths on stdin (the union of files in the
review target). Writes a JSON object on stdout mapping each agent number
("1".."N", as strings) to that agent's permutation of the same paths.

Purpose: LLMs attend unevenly across a long context, so every agent handed an
identically ordered diff shares the same positional blind spots. Giving each
agent a different order decorrelates those blind spots without changing what any
agent sees, so a defect buried mid-diff for one persona sits near an edge for
another.

The permutation is content-addressed — files are sorted by
sha256("<agent>:<path>") — which buys two properties a shuffle would not:

  * Reproducible. Same inputs give the same orders on every machine, Python
    build, and run, so a review is replayable and an eval is stable.
  * Filter-stable. An agent that reviews only a subset of files (security on
    auth paths, a11y on UI paths) can take the subsequence of its own files
    from its full permutation and get exactly the order it would have had if
    the subset were permuted directly. One call therefore serves every agent,
    whatever slice each ends up with.

Never reorders hunks within a file — this script only ever sees paths.

Exit 0 on success. Exit 2 on malformed input.
"""

import argparse
import hashlib
import json
import sys

DEFAULT_AGENTS = 10


def order_for_agent(paths, agent):
    return sorted(paths, key=lambda p: hashlib.sha256(f"{agent}:{p}".encode()).hexdigest())


def build_orders(paths, agents):
    return {str(agent): order_for_agent(paths, agent) for agent in range(1, agents + 1)}


def main():
    parser = argparse.ArgumentParser(description="Per-agent deterministic diff file ordering.")
    parser.add_argument("--agents", type=int, default=DEFAULT_AGENTS)
    args = parser.parse_args()

    if args.agents < 1:
        print("agent-order: --agents must be >= 1", file=sys.stderr)
        return 2

    try:
        paths = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        print(f"agent-order: malformed JSON on stdin: {ex}", file=sys.stderr)
        return 2

    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        print("agent-order: expected a JSON array of strings", file=sys.stderr)
        return 2

    json.dump(build_orders(paths, args.agents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
