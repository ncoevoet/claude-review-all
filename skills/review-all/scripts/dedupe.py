#!/usr/bin/env python3
"""dedupe.py — Phase 2.5 Step 2.5a deduplication.

Reads a JSON array of findings on stdin. Each finding must have at minimum:
  - id (string, unique within this batch)
  - root_cause_key (string, used for grouping)
  - severity (string: CRITICAL|IMPORTANT|DEBT|SUGGESTED|QUESTION)
  - source_agent (string)
  - evidence (string)

Writes a JSON object on stdout with two fields:
  - kept: list of representative findings (one per root_cause_key), each
    annotated with `confirmed_by` = list of source_agent names that flagged
    the same key (excluding the primary).
  - dropped_global_cap: list of finding ids dropped because the per-severity
    global cap fired (SUGGESTED ≤ 10, QUESTION ≤ 8 by default; others uncapped).

Caps are overridable: pass --suggested-cap N / --question-cap N, or set the
env vars REVIEW_ALL_SUGGESTED_CAP / REVIEW_ALL_QUESTION_CAP. CLI args win over
env. A value of 0 disables that cap entirely (keep every finding of that tier).

Exit 0 on success. Exit 2 on malformed input.
"""

import json
import os
import sys
from collections import defaultdict

DEFAULT_SUGGESTED_CAP = 10
DEFAULT_QUESTION_CAP = 8

def resolve_cap(cli_val, env_name, default):
    """CLI arg > env var > default. 0 means unlimited. Bad values fall back."""
    if cli_val is not None:
        return cli_val
    raw = os.environ.get(env_name)
    if raw is not None:
        try:
            v = int(raw)
            if v >= 0:
                return v
        except ValueError:
            pass
    return default

def parse_cli_cap(flag):
    """Return int value for `--flag N` if present in argv, else None."""
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            try:
                v = int(sys.argv[i + 1])
                if v >= 0:
                    return v
            except ValueError:
                pass
        print(f"dedupe: {flag} needs a non-negative integer", file=sys.stderr)
        sys.exit(2)
    return None

# Primary = most evidence-rich finding in the group (longest evidence string).
def pick_primary(findings):
    return max(findings, key=lambda f: len(f.get("evidence", "")))

def main():
    suggested_cap = resolve_cap(
        parse_cli_cap("--suggested-cap"), "REVIEW_ALL_SUGGESTED_CAP", DEFAULT_SUGGESTED_CAP)
    question_cap = resolve_cap(
        parse_cli_cap("--question-cap"), "REVIEW_ALL_QUESTION_CAP", DEFAULT_QUESTION_CAP)

    try:
        items = json.load(sys.stdin)
        if not isinstance(items, list):
            raise ValueError("input must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"dedupe: malformed input: {e}", file=sys.stderr)
        sys.exit(2)

    groups = defaultdict(list)
    for f in items:
        if not isinstance(f, dict) or "root_cause_key" not in f or "id" not in f:
            print("dedupe: every finding needs id + root_cause_key", file=sys.stderr)
            sys.exit(2)
        groups[f["root_cause_key"]].append(f)

    kept = []
    for key, fs in groups.items():
        primary = pick_primary(fs)
        confirmed_by = sorted({
            f.get("source_agent", "") for f in fs if f is not primary
        } - {""})
        primary = dict(primary)
        primary["confirmed_by"] = confirmed_by
        kept.append(primary)

    by_sev = defaultdict(list)
    for f in kept:
        by_sev[f.get("severity", "UNKNOWN")].append(f)

    def score(f):
        # Higher confirmed_by count first; tie-break by evidence length.
        return (len(f.get("confirmed_by", [])), len(f.get("evidence", "")))

    dropped = []
    for sev, cap in (("SUGGESTED", suggested_cap), ("QUESTION", question_cap)):
        if cap == 0:  # 0 = unlimited
            continue
        bucket = sorted(by_sev.get(sev, []), key=score, reverse=True)
        if len(bucket) > cap:
            for f in bucket[cap:]:
                dropped.append(f["id"])
            by_sev[sev] = bucket[:cap]

    kept_final = []
    for sev in ("CRITICAL", "IMPORTANT", "DEBT", "SUGGESTED", "QUESTION"):
        kept_final.extend(by_sev.get(sev, []))
    for sev, fs in by_sev.items():
        if sev not in ("CRITICAL", "IMPORTANT", "DEBT", "SUGGESTED", "QUESTION"):
            kept_final.extend(fs)

    json.dump({"kept": kept_final, "dropped_global_cap": dropped}, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()
