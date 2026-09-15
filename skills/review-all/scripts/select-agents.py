#!/usr/bin/env python3
"""select-agents.py — deterministic Phase 2 spawn decisions for /review-all.

Reads the stdout of `select-files.py` on stdin and decides, for each of the
ten review agents, whether to spawn it and which reviewable files it gets —
replacing the spawn-condition prose in `references/phase-2-agents.md` (and
its duplicates inside the personas) with a decision made once, before any
agent is spawned, instead of re-derived after the fact by each one.

Also groups every reviewable path by its resolved rule pack (from the same
file-classes.json `select-files.py` reads) so the orchestrator injects each
language checklist once per run instead of once per file.

The glob engine (brace expansion + `**`-aware regex translation) is
duplicated from `select-files.py` rather than imported: this script's
exclusive file list has no shared module to put it in, and the engine is
small enough that a second copy is cheaper than inventing one.

Exit 0 on success. Exit 2 on malformed input.
"""

import argparse
import json
import os
import re
import sys

DEFAULT_CLASSES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file-classes.json")

AGENT_IDS = [
    "01-standards", "02-bugs-security", "03-dry-smells", "04-consistency-history", "05-simplification",
    "06-security-deep-dive", "07-performance", "08-test-quality", "09-api-contract", "10-a11y-i18n",
]
ALWAYS_IDS = ["01-standards", "02-bugs-security", "03-dry-smells", "04-consistency-history", "05-simplification", "07-performance"]


def expand_braces(pattern):
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    prefix, options, suffix = pattern[:match.start()], match.group(1).split(","), pattern[match.end():]
    expanded = []
    for option in options:
        expanded.extend(expand_braces(prefix + option + suffix))
    return expanded


def glob_to_regex(pattern):
    i, n, out = 0, len(pattern), []
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "^" + "".join(out) + "$"


def compile_glob(pattern):
    """Compile a file-classes.json glob case-insensitively — see select-files.py's
    compile_glob for why (PascalCase Java/TS filenames must still match)."""
    return [re.compile(glob_to_regex(variant.lower())) for variant in expand_braces(pattern)]


def glob_matches(compiled, path):
    lowered = path.lower()
    return any(rx.match(lowered) for rx in compiled)


def resolve_pack(rule_pack_rules, path):
    for pattern, compiled, pack in rule_pack_rules:
        if glob_matches(compiled, path):
            return pack
    return None


def group_by_pack(reviewable, rule_pack_rules):
    groups = {}
    for entry in reviewable:
        pack = resolve_pack(rule_pack_rules, entry["path"])
        if pack is None:
            continue
        groups.setdefault(pack, []).append(entry["path"])
    return dict(sorted(groups.items()))


def files_with_class(reviewable, *class_names):
    wanted = set(class_names)
    return [entry["path"] for entry in reviewable if wanted & set(entry["classes"])]


def build_base_decisions(reviewable):
    all_paths = [entry["path"] for entry in reviewable]
    decisions = {agent_id: {"spawn": True, "files": all_paths, "reason": "always"} for agent_id in ALWAYS_IDS}

    security_files = files_with_class(reviewable, "security")
    decisions["06-security-deep-dive"] = (
        {"spawn": True, "files": security_files, "reason": "files with class security"} if security_files
        else {"spawn": False, "files": [], "reason": "no files with class security"})

    test_quality_files = [
        entry["path"] for entry in reviewable
        if "test" in entry["classes"] or (entry.get("status") == "A" and "code" in entry["classes"])]
    decisions["08-test-quality"] = (
        {"spawn": True, "files": test_quality_files, "reason": "test files or added code files"} if test_quality_files
        else {"spawn": False, "files": [], "reason": "no test files or added code files"})

    contract_files = files_with_class(reviewable, "contract")
    decisions["09-api-contract"] = (
        {"spawn": True, "files": contract_files, "reason": "files with class contract"} if contract_files
        else {"spawn": False, "files": [], "reason": "no files with class contract"})

    ui_i18n_files = files_with_class(reviewable, "ui", "i18n")
    decisions["10-a11y-i18n"] = (
        {"spawn": True, "files": ui_i18n_files, "reason": "files with class ui or i18n"} if ui_i18n_files
        else {"spawn": False, "files": [], "reason": "no files with class ui or i18n"})

    return decisions


def build_agents(reviewable, extra, skip):
    if not reviewable:
        agents = {agent_id: {"spawn": False, "files": [], "reason": "no reviewable files"} for agent_id in AGENT_IDS}
        for agent_id in extra + skip:
            agents[agent_id] = {"spawn": False, "files": [], "reason": "no reviewable files"}
        return agents

    agents = build_base_decisions(reviewable)
    all_paths = [entry["path"] for entry in reviewable]
    for agent_id in extra:
        agents[agent_id] = {"spawn": True, "files": all_paths, "reason": "extraAgents"}
    for agent_id in skip:
        agents[agent_id] = {"spawn": False, "files": [], "reason": "skipAgents"}
    return agents


def split_csv(value):
    return [v for v in value.split(",") if v] if value else []


def load_classes(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_parser():
    parser = argparse.ArgumentParser(description="Deterministic Phase 2 agent spawn decisions for /review-all.")
    parser.add_argument("--extra", default="", help="comma-separated agent ids to always spawn (.claude/review-all.json extraAgents)")
    parser.add_argument("--skip", default="", help="comma-separated agent ids to force-skip (.claude/review-all.json skipAgents)")
    parser.add_argument("--classes", default=DEFAULT_CLASSES_PATH)
    return parser.parse_args()


def main():
    args = build_parser()

    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        print(f"select-agents: malformed JSON on stdin: {ex}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict) or not isinstance(payload.get("reviewable"), list):
        print("select-agents: expected the JSON object produced by select-files.py", file=sys.stderr)
        return 2

    data = load_classes(args.classes)
    rule_pack_rules = [(pattern, compile_glob(pattern), pack) for pattern, pack in data["rule_packs"].items()]

    reviewable = payload["reviewable"]
    agents = build_agents(reviewable, split_csv(args.extra), split_csv(args.skip))

    result = {
        "agents": agents,
        "rule_packs": group_by_pack(reviewable, rule_pack_rules),
        "counts": {
            "spawned": sum(1 for decision in agents.values() if decision["spawn"]),
            "skipped": sum(1 for decision in agents.values() if not decision["spawn"]),
        },
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
