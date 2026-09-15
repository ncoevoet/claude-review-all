#!/usr/bin/env python3
"""select-files.py — deterministic pre-dispatch file selection for /review-all.

Reads a JSON array of changed-file records (path/status/insertions/deletions/
bytes, the shape `git diff --numstat` plus per-file diff size maps onto) on
stdin. Writes the reviewable subset and the excluded subset with a reason
and the pattern that caused it.

Deleted files stay reviewable: this skill calibrates scrutiny specifically
on deletions (downstream-breakage focus on removed exports/files), and a
deletion can be the entire diff — the file that imports it is unchanged and
so never appears — so excluding `status == "D"` would make that whole class
of defect undetectable. Unlike Alibaba's open-code-review, which reviews new
content and rightly drops deletions, this script never gates on status.

Today "spawn only if relevant" is PROSE in `references/phase-2-agents.md`,
duplicated inside the personas, so it can only act *after* an agent is
already spawned and reading files it should never have seen. This script
(and `select-agents.py`, which consumes its output) is the deterministic
pre-dispatch layer that replaces that prose — modelled on Alibaba's
open-code-review (`internal/agent/selection.go`,
`internal/config/rules/system_rules.json`), but scoped to what review-all
actually needs: no default exclusion of test files or Markdown, because
those are the subject of the Test Quality agent and a slice of the eval
fixtures.

Gate order (first match wins) is deliberately not "generated excludes first":
a secret file must never be rescued by `--paths`, and a `--exclude`d secret
must still be reported as `secret`, not the softer `user_rule` — see
`select()` below for the exact order.

Path globs alone miss relevance that only lives in the diff body — nothing
in `src/export/csv.ts` says "security", the CSV-injection sink is in the
code. A record may carry an optional `diff` field (that file's diff text);
when present, `content_signals` regexes from file-classes.json add classes
on top of the path-based ones (currently only `security`). Content signals
are additive and never required: metadata-only input (no `diff` field, the
shape `validate-evals.py`'s recall guard and `check-agent-selection.sh` both
feed this script) works exactly as before. Content regexes are matched
case-sensitively against the raw diff text — these are code identifiers
(`innerHTML`, `execSync(`, `rejectUnauthorized: false`, ...), not filenames,
so lowercasing them the way glob patterns are lowercased would blur exactly
the tokens that make them precise. `--explain` never sees a diff, so it
cannot evaluate these — its output says so instead of looking like a clean
non-match.

A deleted file that carries class `code` also gets class `contract`:
removing a module is an API change even though there is no new content to
scan for it (see `15-deleted-file-breaks-importer`).

braceexpand is not installed, so `**/*.{ts,tsx}`-style brace groups are
expanded by hand (`expand_braces`), and `**` is translated to a regex by
hand (`glob_to_regex`) since `fnmatch` does not treat it as crossing `/`.

Exit 0 on success. Exit 2 on malformed input.
"""

import argparse
import json
import os
import re
import sys

DEFAULT_MAX_FILE_DIFF_BYTES = 160000
DEFAULT_CLASSES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file-classes.json")
EXCLUDE_REASONS = ["binary", "secret", "user_rule", "generated", "too_large"]


def expand_braces(pattern):
    """Expand the leftmost {a,b,c} group and recurse, so multiple groups in one
    pattern (e.g. `*.{test,spec}.{ts,tsx,js,jsx}`) yield their full cross product.
    """
    match = re.search(r"\{([^{}]*)\}", pattern)
    if not match:
        return [pattern]
    prefix, options, suffix = pattern[:match.start()], match.group(1).split(","), pattern[match.end():]
    expanded = []
    for option in options:
        expanded.extend(expand_braces(prefix + option + suffix))
    return expanded


def glob_to_regex(pattern):
    """Translate one brace-free glob into an anchored regex.

    `**/` and a bare `**` become `.*` (cross `/`); a single `*` becomes
    `[^/]*` (does not); `?` becomes `[^/]`. Everything else is a literal.
    """
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
    """Compile a file-classes.json glob case-insensitively.

    PascalCase dominates Java/TS filenames (`AuthService.java`, `LoginForm.tsx`),
    so a case-sensitive `*auth*`/`*Test.java` style pattern would silently miss
    most of them — a recall regression that looks clean because nothing errors.
    User-supplied `--exclude`/`--paths` prefixes are a different function
    (`match_prefix`) and stay case-sensitive: those are literal paths the user
    typed for this tree, not filename-convention patterns.
    """
    return [re.compile(glob_to_regex(variant.lower())) for variant in expand_braces(pattern)]


def glob_matches(compiled, path):
    lowered = path.lower()
    return any(rx.match(lowered) for rx in compiled)


def compile_rule_list(patterns):
    return [(pattern, compile_glob(pattern)) for pattern in patterns]


def first_match(rules, path):
    for pattern, compiled in rules:
        if glob_matches(compiled, path):
            return pattern
    return None


def compile_class_rules(classes_map):
    return [(pattern, compile_glob(pattern), tags) for pattern, tags in classes_map.items()]


def classes_for(class_rules, path):
    classes = set()
    for _pattern, compiled, tags in class_rules:
        if glob_matches(compiled, path):
            classes.update(tags)
    return classes


def compile_content_signals(content_signals_map):
    return {cls: [re.compile(pattern) for pattern in patterns] for cls, patterns in content_signals_map.items()}


def content_classes_for(content_rules, diff_text):
    if not diff_text:
        return set()
    return {cls for cls, regexes in content_rules.items() if any(rx.search(diff_text) for rx in regexes)}


def resolve_classes(class_rules, content_rules, path, status, diff_text):
    classes = classes_for(class_rules, path)
    classes |= content_classes_for(content_rules, diff_text)
    if status == "D" and "code" in classes:
        classes.add("contract")
    return sorted(classes)


def match_prefix(prefixes, path):
    for prefix in prefixes:
        if path.startswith(prefix):
            return prefix
    return None


def split_csv(value):
    return [v for v in value.split(",") if v] if value else []


def load_classes(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def select(records, secret_rules, exclude_user, include_user, exclude_rules, max_bytes, class_rules, content_rules):
    reviewable, excluded = [], []
    counts_excluded = {reason: 0 for reason in EXCLUDE_REASONS}

    for record in records:
        path, status, insertions, size = record["path"], record.get("status"), record.get("insertions"), record.get("bytes")
        reason, pattern = None, None

        if insertions is None:
            reason = "binary"
        else:
            secret_pattern = first_match(secret_rules, path)
            if secret_pattern is not None:
                reason, pattern = "secret", secret_pattern
            else:
                user_exclude_pattern = match_prefix(exclude_user, path)
                if user_exclude_pattern is not None:
                    reason, pattern = "user_rule", user_exclude_pattern
                else:
                    force_keep = match_prefix(include_user, path) is not None
                    if not force_keep:
                        generated_pattern = first_match(exclude_rules, path)
                        if generated_pattern is not None:
                            reason, pattern = "generated", generated_pattern
                    if reason is None and size > max_bytes:
                        reason = "too_large"

        if reason is not None:
            counts_excluded[reason] += 1
            excluded.append({"path": path, "reason": reason, "pattern": pattern})
        else:
            ext = os.path.splitext(path)[1].lstrip(".")
            classes = resolve_classes(class_rules, content_rules, path, status, record.get("diff"))
            reviewable.append({"path": path, "status": status, "ext": ext, "bytes": size, "classes": classes})

    counts = {
        "total": len(records),
        "reviewable": len(reviewable),
        "excluded": counts_excluded,
    }
    return {"reviewable": reviewable, "excluded": excluded, "counts": counts}


def explain(exclude_rules, secret_rules, class_rules, rule_pack_rules, path):
    pack_pattern, pack = None, None
    for pattern, compiled, resolved_pack in rule_pack_rules:
        if glob_matches(compiled, path):
            pack_pattern, pack = pattern, resolved_pack
            break
    return {
        "path": path,
        "exclude": first_match(exclude_rules, path),
        "secret": first_match(secret_rules, path),
        "classes": sorted(classes_for(class_rules, path)),
        "rule_pack": pack,
        "rule_pack_pattern": pack_pattern,
        "content_signals": "not evaluated (path-only mode)",
    }


def build_parser():
    parser = argparse.ArgumentParser(description="Deterministic pre-dispatch file selection for /review-all.")
    parser.add_argument("--exclude", default="", help="comma-separated user path prefixes (SKILL.md --exclude semantics)")
    parser.add_argument("--paths", default="", help="comma-separated user include path prefixes")
    parser.add_argument("--max-file-diff-bytes", type=int, default=DEFAULT_MAX_FILE_DIFF_BYTES)
    parser.add_argument("--classes", default=DEFAULT_CLASSES_PATH)
    parser.add_argument("--explain", default=None, help="print matched patterns for one path and exit, ignoring stdin")
    return parser.parse_args()


def main():
    args = build_parser()
    data = load_classes(args.classes)
    exclude_rules = compile_rule_list(data["exclude"])
    secret_rules = compile_rule_list(data["secret"])
    class_rules = compile_class_rules(data["classes"])
    content_rules = compile_content_signals(data.get("content_signals", {}))
    rule_pack_rules = [(pattern, compile_glob(pattern), pack) for pattern, pack in data["rule_packs"].items()]

    if args.explain is not None:
        json.dump(explain(exclude_rules, secret_rules, class_rules, rule_pack_rules, args.explain), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    try:
        records = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        print(f"select-files: malformed JSON on stdin: {ex}", file=sys.stderr)
        return 2

    if not isinstance(records, list) or not all(isinstance(r, dict) and "path" in r for r in records):
        print("select-files: expected a JSON array of objects with a 'path' field", file=sys.stderr)
        return 2

    result = select(
        records, secret_rules, split_csv(args.exclude), split_csv(args.paths),
        exclude_rules, args.max_file_diff_bytes, class_rules, content_rules)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
