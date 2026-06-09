#!/usr/bin/env python3
"""materialize-fixture.py — turn an eval fixture JSON into a real temp git repo.

Reads an eval JSON (evals/*.json) and creates a temporary git repository where
the fixture's "before" state is committed and the "after" state is staged
(`git add -A`) — the uncommitted changes `/review-all` reviews. Staging (rather
than intent-to-add) gives new files real content instead of an empty blob, so a
review never sees a spurious "you staged an empty file" issue.
Prints the repo path on stdout so a runner can cd into it.

Supports fixture.kind == "synthetic-diff":
  - fixture.files{path:{before?,after?,delete?}}  — per-file before(commit)/
    after(staged). Omit "after" for an unchanged baseline file; omit "before"
    for an added file; set "delete": true (with a "before") to remove a baseline
    file in the change.
  - fixture.rename_only + fixture.files_changed=N — generates N files and renames
    a symbol (oldName_i -> newName_i) across them (no semantic change).

A fixture whose after-state equals its before-state yields a clean tree (the
empty-diff edge case).

Optional fixture.seed_profile_cache pre-seeds .claude/cache/review-all-profile.json
AFTER the final staging step (untracked -> invisible to the reviewed diff):
  - {"raw": {...}}      — write the object verbatim (poisoned/legacy cache cases)
  - {"rules": "...", "ruleSources": [...]?} — write a VALID v2 profile whose
    cacheKey/schemaVersion come from running the sibling discover.sh in the
    materialized repo, so there is exactly one hash implementation.

Usage: materialize-fixture.py FIXTURE.json [DEST_DIR]
"""
import json
import os
import subprocess
import sys
import tempfile


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def write(repo, rel, content):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path) or repo, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def seed_profile_cache(repo, seed):
    cache_dir = os.path.join(repo, ".claude", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    target = os.path.join(cache_dir, "review-all-profile.json")
    if "raw" in seed:
        with open(target, "w") as f:
            json.dump(seed["raw"], f)
        return
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(["bash", os.path.join(here, "discover.sh"), repo],
                         check=True, capture_output=True, text=True)
    disc = json.loads(out.stdout)
    profile = {
        "schemaVersion": disc["schemaVersion"],
        "cacheKey": disc["cacheKey"],
        "createdAt": "seeded-by-materialize",
        "rules": {"global": seed.get("rules", "")},
        "ruleSources": seed.get("ruleSources", ["CLAUDE.md"]),
    }
    with open(target, "w") as f:
        json.dump(profile, f)


def main():
    if len(sys.argv) < 2:
        print("usage: materialize-fixture.py FIXTURE.json [DEST_DIR]", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    fx = spec.get("fixture", {})
    repo = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="review-all-eval-")
    os.makedirs(repo, exist_ok=True)

    git(repo, "init")
    git(repo, "config", "user.email", "eval@example.com")
    git(repo, "config", "user.name", "review-all-eval")

    files = fx.get("files")
    if files:
        for rel, ba in files.items():
            if "before" in ba:
                write(repo, rel, ba["before"])
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "baseline", "--allow-empty")
        for rel, ba in files.items():
            if ba.get("delete"):
                p = os.path.join(repo, rel)
                if os.path.exists(p):
                    os.remove(p)
            elif "after" in ba:
                write(repo, rel, ba["after"])
    elif fx.get("rename_only") and fx.get("files_changed"):
        n = int(fx["files_changed"])
        for i in range(n):
            write(repo, f"src/mod_{i}.js",
                  f"export function oldName_{i}(x) {{ return x + {i}; }}\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "baseline")
        for i in range(n):
            write(repo, f"src/mod_{i}.js",
                  f"export function newName_{i}(x) {{ return x + {i}; }}\n")
    else:
        print("materialize: unsupported fixture kind/shape", file=sys.stderr)
        sys.exit(3)

    # Stage all changes with real content (new files get real blobs, not the
    # empty intent-to-add blob that would surface as a spurious review finding).
    git(repo, "add", "-A")

    # Seed AFTER staging so the cache file stays untracked and never pollutes
    # the reviewed diff; discover.sh then sees the exact state the review sees.
    seed = fx.get("seed_profile_cache")
    if isinstance(seed, dict):
        seed_profile_cache(repo, seed)

    print(repo)


if __name__ == "__main__":
    main()
