#!/usr/bin/env python3
"""code-hash.py - the ONE implementation of state.json's code_hash.

`state.json` decides whether a stored verdict, a `wontfix` suppression, or a
`rejected` machine-dismissal still applies by comparing a hash of the code at
the finding's location. That comparison is only meaningful if every producer
computes the hash the same way, so the rule lives here rather than in prose
that each caller re-implements by hand.

Anchored form (the finding has a concrete file:line):

    code-hash.py anchored REPO_ROOT path/to/file.py:42

  -> sha256 of the 3 lines before, the flagged line, and the 3 lines after,
     joined with "\\n". Line numbers are 1-based and clamped to the file. A
     missing or unreadable file hashes the empty string, which never matches a
     hash taken while the file existed - so a deleted file reopens its entry.

Anchorless form (cross-file findings, missing-spec findings, repo-wide rules):

    code-hash.py anchorless FILE_LINE SEVERITY ROOT_CAUSE_KEY

  -> sha256 of "<file_line>|<severity>|<root_cause_key>". Changes only when the
     finding's identifying tuple changes.

Both forms print the lowercase hex digest and nothing else.
"""
import hashlib
import os
import sys

CONTEXT_LINES = 3


def anchored(repo_root, file_line):
    path, _, line_s = file_line.rpartition(":")
    if not path or not line_s.isdigit():
        print(f"code-hash: expected path:line, got {file_line!r}", file=sys.stderr)
        sys.exit(2)
    target = os.path.join(repo_root, path)
    try:
        with open(target, encoding="utf-8", errors="surrogateescape") as f:
            lines = f.read().split("\n")
    except OSError:
        return hashlib.sha256(b"").hexdigest()
    line = int(line_s)
    start = max(0, line - 1 - CONTEXT_LINES)
    end = min(len(lines), line + CONTEXT_LINES)
    window = "\n".join(lines[start:end])
    return hashlib.sha256(window.encode("utf-8", "surrogateescape")).hexdigest()


def anchorless(file_line, severity, root_cause_key):
    payload = f"{file_line}|{severity}|{root_cause_key}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main():
    argv = sys.argv[1:]
    if len(argv) == 3 and argv[0] == "anchored":
        print(anchored(argv[1], argv[2]))
    elif len(argv) == 4 and argv[0] == "anchorless":
        print(anchorless(argv[1], argv[2], argv[3]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
