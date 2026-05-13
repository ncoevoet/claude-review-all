#!/usr/bin/env python3
"""state-sweep.py — Phase 2.5 state.json lifecycle sweep.

Applies the rules from references/state-file.md to an existing state.json
given the set of root_cause_keys observed in the current run.

Usage:
  state-sweep.py STATE_FILE HEAD_SHA SEEN_KEYS_JSON

Where SEEN_KEYS_JSON is the path to a JSON array of root_cause_keys that
the current run flagged (post-verification, kept + appendix). Reads the
existing state.json, applies the open/fixed/stale/snoozed transitions,
writes the file atomically, and prints a one-line summary on stdout.

Transitions implemented:
  - snoozed → open when snoozed_until is in the past
  - open → stale when not re-seen AND miss_count >= 2 (incremented this run)
  - open with last_seen_at > 30 days → stale
  - open whose code_hash no longer matches current file → fixed
    (this script can't read code; the caller passes a separate JSON of
    keys-whose-code-changed via env var STATE_SWEEP_CHANGED_KEYS=path)
  - wontfix whose code_hash no longer matches → open

This script intentionally does NOT compute code hashes; the orchestrator
provides them. It only applies the lifecycle bookkeeping.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

STALE_DAYS = 30
MISS_LIMIT = 2

def now_iso():
    return datetime.now(tz=timezone.utc).isoformat()

def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None

def write_atomic(path, obj):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state.", dir=d)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise

def main():
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} STATE_FILE HEAD_SHA SEEN_KEYS_JSON", file=sys.stderr)
        sys.exit(2)
    state_path, head_sha, seen_path = sys.argv[1:]

    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
    else:
        state = {"version": 1, "migrations": [], "findings": {}}

    state.setdefault("findings", {})
    state.setdefault("migrations", [])

    with open(seen_path) as f:
        seen_keys = set(json.load(f))

    changed_path = os.environ.get("STATE_SWEEP_CHANGED_KEYS")
    changed_keys = set()
    if changed_path and os.path.exists(changed_path):
        with open(changed_path) as f:
            changed_keys = set(json.load(f))

    now = datetime.now(tz=timezone.utc)
    transitions = {"snoozed_to_open": 0, "open_to_fixed": 0,
                   "open_to_stale": 0, "wontfix_to_open": 0}

    for key, entry in state["findings"].items():
        status = entry.get("status", "open")
        snoozed_until = parse_iso(entry.get("snoozed_until"))
        last_seen_at = parse_iso(entry.get("last_seen_at"))
        seen_this_run = key in seen_keys
        code_changed = key in changed_keys

        if status == "snoozed" and snoozed_until and snoozed_until < now:
            entry["status"] = "open"
            transitions["snoozed_to_open"] += 1
            status = "open"

        if status == "wontfix" and code_changed:
            entry["status"] = "open"
            entry["fix_commit_sha"] = None
            transitions["wontfix_to_open"] += 1
            status = "open"

        if status == "open" and not seen_this_run:
            if code_changed:
                entry["status"] = "fixed"
                entry["fix_commit_sha"] = head_sha
                transitions["open_to_fixed"] += 1
            else:
                entry["miss_count"] = int(entry.get("miss_count", 0)) + 1
                if entry["miss_count"] >= MISS_LIMIT:
                    entry["status"] = "stale"
                    transitions["open_to_stale"] += 1
                elif last_seen_at and (now - last_seen_at) > timedelta(days=STALE_DAYS):
                    entry["status"] = "stale"
                    transitions["open_to_stale"] += 1

        if seen_this_run and status == "open":
            entry["last_seen_sha"] = head_sha
            entry["last_seen_at"] = now_iso()
            entry["miss_count"] = 0

    write_atomic(state_path, state)

    summary = ", ".join(f"{k}={v}" for k, v in transitions.items() if v)
    print(f"state-sweep: {summary or 'no transitions'}")

if __name__ == "__main__":
    main()
