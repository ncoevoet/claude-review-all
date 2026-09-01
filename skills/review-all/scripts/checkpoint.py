#!/usr/bin/env python3
"""checkpoint.py — Phase 2 per-axis checkpointing (resume on re-run).

A review that is interrupted mid-Phase-2 (session cut, CI cancellation, user
interrupt) currently loses every agent that had already returned: the re-run
re-spawns all ten axes and pays for identical work. Observed cost of one such
double-run group: ~285K output + 14.3M cache-read tokens discarded, with Phase 0
profiling and every axis re-executed to the same conclusions.

This script persists ONE JSON file per axis under the reviewed repo's
`.claude/review-all/checkpoints/` and hands them back on the next run — but only
when the next run is reviewing *exactly* the same thing with *exactly* the same
reviewer definitions. That is the whole safety argument, so the key is broad:

  runKey = sha256(
      "review-all-checkpoint-v1"
    + skillFingerprint   # sha256 manifest of SKILL.md + agents/*.md
    + headSha            # git HEAD of the reviewed repo
    + diffHash           # sha256 of the exact diff under review (stdin)
    + promptInputsHash   # sha256 manifest of REVIEW.md + .claude/review-all.json
  )

Any of: a new commit, an edited working tree, a narrowed `--paths` scope, an
edited agent persona, an edited REVIEW.md or config → different key → every
checkpoint is stale, ignored, and deleted. There is no partial reuse and no
"close enough" match: a checkpoint either describes this exact review or it does
not exist. `promptInputsHash` is in the key because REVIEW.md and the config
shape every agent prompt and can change without touching HEAD or the diff.

`skillFingerprint` is derived from file contents rather than a hand-maintained
version constant for the same reason discover.sh hashes CLAUDE.md contents: a
constant that must be bumped by hand is a constant that will not be.

Commands
  load  --head SHA [--dir DIR]   < diff        → {runKey, resumed{}, ignored[]}
  save  --run-key K --axis A [--head SHA] [--dir DIR]  < findings JSON array

`load` also DELETES every stale file it finds, so the directory only ever holds
checkpoints for the current key (bounded by the axis count, self-cleaning).

Exit 0 on success. Exit 2 on malformed input or bad arguments.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile

SCHEMA_VERSION = 1
KEY_PREFIX = "review-all-checkpoint-v1"
DEFAULT_DIR = ".claude/review-all/checkpoints"
# Files whose content defines what a reviewer axis does. An edit to any of them
# can change that axis's findings, so it must invalidate the checkpoint.
SKILL_FILES = ("SKILL.md",)
SKILL_DIRS = ("agents",)
# Repo files that shape every agent prompt without being part of the diff.
PROMPT_INPUT_FILES = ("REVIEW.md", ".claude/review-all.json")
AXIS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def manifest_hash(entries):
    """Hash a sorted "<name> <sha256>" manifest — not concatenated contents.

    A manifest makes renames and added empty files change the hash, which a
    concatenation would silently absorb.
    """
    lines = "".join(f"{name} {digest}\n" for name, digest in sorted(entries))
    return sha256_bytes(lines.encode())


def skill_fingerprint(skill_root):
    entries = []
    for name in SKILL_FILES:
        path = os.path.join(skill_root, name)
        if os.path.isfile(path):
            entries.append((name, sha256_file(path)))
    for subdir in SKILL_DIRS:
        directory = os.path.join(skill_root, subdir)
        if not os.path.isdir(directory):
            continue
        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            if entry.endswith(".md") and os.path.isfile(path):
                entries.append((f"{subdir}/{entry}", sha256_file(path)))
    return manifest_hash(entries)


def prompt_inputs_hash():
    entries = [(name, sha256_file(name))
               for name in PROMPT_INPUT_FILES if os.path.isfile(name)]
    return manifest_hash(entries)


def run_key(skill_root, head, diff_bytes):
    parts = (KEY_PREFIX, skill_fingerprint(skill_root), head,
             sha256_bytes(diff_bytes), prompt_inputs_hash())
    return sha256_bytes("\n".join(parts).encode())


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_atomic(path, obj):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".checkpoint.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def cmd_load(args, skill_root):
    key = run_key(skill_root, args.head, sys.stdin.buffer.read())
    resumed, ignored = {}, []

    if os.path.isdir(args.dir):
        for name in sorted(os.listdir(args.dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(args.dir, name)
            axis = name[: -len(".json")]
            reason = None
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, json.JSONDecodeError):
                doc, reason = None, "unreadable"
            if doc is not None:
                if doc.get("schemaVersion") != SCHEMA_VERSION:
                    reason = "schema"
                elif doc.get("runKey") != key:
                    reason = "key-mismatch"
                elif doc.get("axis") != axis:
                    reason = "axis-mismatch"
                elif not isinstance(doc.get("findings"), list):
                    reason = "malformed-findings"
            if reason:
                # Stale checkpoints are never reused; drop them so the directory
                # only ever holds entries for the current key.
                ignored.append({"axis": axis, "reason": reason})
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            resumed[axis] = {"savedAt": doc.get("savedAt"), "findings": doc["findings"]}

    json.dump({"runKey": key, "checkpointDir": args.dir,
               "resumed": resumed, "ignored": ignored}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_save(args, _skill_root):
    if not AXIS_RE.match(args.axis):
        print(f"checkpoint: invalid --axis {args.axis!r}", file=sys.stderr)
        return 2
    try:
        findings = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        print(f"checkpoint: malformed JSON on stdin: {ex}", file=sys.stderr)
        return 2
    if not isinstance(findings, list):
        print("checkpoint: expected a JSON array of findings on stdin", file=sys.stderr)
        return 2

    path = os.path.join(args.dir, f"{args.axis}.json")
    write_atomic(path, {
        "schemaVersion": SCHEMA_VERSION,
        "runKey": args.run_key,
        "axis": args.axis,
        "head": args.head,
        "savedAt": now_iso(),
        "findings": findings,
    })
    print(f"checkpoint: saved {args.axis} ({len(findings)} findings) -> {path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="checkpoint.py", description="Phase 2 per-axis checkpoint store.")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="compute the run key and return resumable axes")
    load.add_argument("--head", required=True, help="git HEAD sha of the reviewed repo")
    load.add_argument("--dir", default=DEFAULT_DIR)
    load.set_defaults(func=cmd_load)

    save = sub.add_parser("save", help="persist one axis's findings")
    save.add_argument("--run-key", required=True, help="runKey printed by `load`")
    save.add_argument("--axis", required=True, help="axis id, e.g. 02-bugs-security")
    save.add_argument("--head", default="")
    save.add_argument("--dir", default=DEFAULT_DIR)
    save.set_defaults(func=cmd_save)

    args = parser.parse_args()
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return args.func(args, skill_root)


if __name__ == "__main__":
    sys.exit(main())
