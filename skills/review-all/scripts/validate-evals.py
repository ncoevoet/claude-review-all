#!/usr/bin/env python3
"""validate-evals.py — schema/validity gate for review-all eval cases.

Validates every evals/*.json (skipping README*) against the contract the
headless runner (run-evals-headless.sh) and materialize-fixture.py depend on,
so a malformed case is caught cheaply HERE instead of wasting an expensive
`claude -p` eval run on it.

Per case (ERROR = fails the gate):
  - parses as a JSON object
  - id == filename stem
  - non-empty string fields: skill, query
  - grader.rubric is a non-empty string — the rubric is the ONLY field the LLM
    judge reads, so an empty one silently grades the report against nothing
  - fixture.kind == "synthetic-diff"
  - fixture materializes, EITHER:
      * files{} non-empty, each value an object with >=1 of before/after/delete,
        and any delete:true entry also supplies a "before"
      * OR rename_only truthy AND files_changed is an int >= 1
  - the fixture yields a reviewable diff (a changed/added/deleted file, or
    rename_only) UNLESS the id is on EMPTY_DIFF_ALLOWLIST (the no-op edge case)
  - fixture.seed_profile_cache (optional) is an object with either a 'raw'
    object (written verbatim) or a non-empty 'rules' string (valid v2 profile)

  - the fixture survives pre-dispatch selection (SKILL.md Step 0.8): at least
    one file stays reviewable, and every success_criteria.must_detect[].file
    is one of them. An exclude pattern that swallows a planted defect turns a
    caught case into an invisible one, and the eval suite would read that as a
    model regression rather than the config bug it is.

WARN (informational, does not fail): grader.method != llm-rubric, unknown
per-file keys (likely a before/after typo), missing success_criteria,
select-files.py absent (recall guard skipped).

Exit 0 if all valid, 1 if any ERROR, 2 on bad usage.
Usage: validate-evals.py [EVALS_DIR]   (defaults to ../evals next to this file)
"""
import json
import os
import subprocess
import sys

SUPPORTED_KINDS = {"synthetic-diff"}
FILE_ENTRY_KEYS = {"before", "after", "delete"}
# The single intentional no-op fixture: a committed baseline, clean working
# tree, nothing to review. Any other empty-diff fixture is a mistake.
EMPTY_DIFF_ALLOWLIST = {"04-empty-diff-noop"}


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def validate_case(path):
    """Return (errors, warnings) — lists of human-readable strings."""
    errors, warnings = [], []
    name = os.path.basename(path)
    stem = name[:-5] if name.endswith(".json") else name

    try:
        with open(path) as f:
            spec = json.load(f)
    except (OSError, ValueError) as ex:
        return [f"{name}: not valid JSON ({ex})"], warnings

    if not isinstance(spec, dict):
        return [f"{name}: top-level JSON must be an object"], warnings

    if spec.get("id") != stem:
        errors.append(f"{name}: id ({spec.get('id')!r}) != filename stem ({stem!r})")

    for fld in ("skill", "query"):
        if not _nonempty_str(spec.get(fld)):
            errors.append(f"{name}: missing/empty string field {fld!r}")

    grader = spec.get("grader")
    if not isinstance(grader, dict):
        errors.append(f"{name}: missing 'grader' object")
    else:
        if not _nonempty_str(grader.get("rubric")):
            errors.append(f"{name}: grader.rubric missing/empty (judge would grade against nothing)")
        method = grader.get("method")
        if method is not None and method != "llm-rubric":
            warnings.append(f"{name}: grader.method {method!r} != 'llm-rubric'")

    if "success_criteria" not in spec:
        warnings.append(f"{name}: no success_criteria (documentation aid, not enforced)")

    fx = spec.get("fixture")
    if not isinstance(fx, dict):
        errors.append(f"{name}: missing 'fixture' object")
        return errors, warnings

    if fx.get("kind") not in SUPPORTED_KINDS:
        errors.append(f"{name}: fixture.kind {fx.get('kind')!r} not in {sorted(SUPPORTED_KINDS)}")

    files = fx.get("files")
    has_diff = False
    if isinstance(files, dict) and files:
        for rel, entry in files.items():
            if not isinstance(entry, dict):
                errors.append(f"{name}: fixture.files[{rel!r}] must be an object")
                continue
            keys = set(entry)
            if not keys & FILE_ENTRY_KEYS:
                errors.append(f"{name}: fixture.files[{rel!r}] has none of before/after/delete")
            unknown = keys - FILE_ENTRY_KEYS
            if unknown:
                warnings.append(f"{name}: fixture.files[{rel!r}] unknown keys {sorted(unknown)} (typo? materialize ignores them)")
            if entry.get("delete"):
                if "before" not in entry:
                    errors.append(f"{name}: fixture.files[{rel!r}] delete:true needs a 'before'")
                else:
                    has_diff = True
            elif "after" in entry and entry.get("after") != entry.get("before"):
                has_diff = True
    elif fx.get("rename_only"):
        fc = fx.get("files_changed")
        if isinstance(fc, bool) or not isinstance(fc, int) or fc < 1:
            errors.append(f"{name}: rename_only needs integer files_changed >= 1 (got {fc!r})")
        else:
            has_diff = True
    else:
        errors.append(f"{name}: fixture has neither a non-empty 'files' map nor rename_only+files_changed")

    if not has_diff and stem not in EMPTY_DIFF_ALLOWLIST:
        errors.append(f"{name}: fixture yields an empty diff (nothing to review) and is not allowlisted")

    seed = fx.get("seed_profile_cache")
    if seed is not None:
        if not isinstance(seed, dict):
            errors.append(f"{name}: fixture.seed_profile_cache must be an object")
        elif "raw" in seed:
            if not isinstance(seed["raw"], dict):
                errors.append(f"{name}: seed_profile_cache.raw must be an object")
        elif not _nonempty_str(seed.get("rules")):
            errors.append(f"{name}: seed_profile_cache needs 'raw' (verbatim) or non-empty 'rules' (valid v2)")

    return errors, warnings


def _selector_records(files):
    """Turn a fixture's files{} map into select-files.py stdin records.

    A fixture is a synthetic diff, so the status letter and the diff size come
    from which of before/after/delete the entry carries, not from git.
    """
    records = []
    for path, entry in files.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("delete"):
            status, body = "D", entry.get("before") or ""
        elif entry.get("before") is None:
            status, body = "A", entry.get("after") or ""
        else:
            status, body = "M", (entry.get("after") or "") + (entry.get("before") or "")
        records.append({
            "path": path, "status": status,
            "insertions": body.count("\n"), "deletions": 0,
            "bytes": len(body),
        })
    return records


def check_selection(case_path, selector):
    """Return errors where pre-dispatch selection would hide a planted defect.

    The selection layer (SKILL.md Step 0.8) drops files before any agent sees
    them. A fixture whose planted defect sits in a path the default exclude
    list happens to match would stop being detectable — and the eval suite
    would score that as a recall regression in the model rather than as the
    config bug it is. This makes the config bug fail here instead.
    """
    with open(case_path) as fh:
        case = json.load(fh)
    name = os.path.basename(case_path)
    fixture = case.get("fixture") or {}
    files = fixture.get("files")
    if not isinstance(files, dict) or not files:
        return []
    records = _selector_records(files)
    if not records:
        return []
    proc = subprocess.run(
        [sys.executable, selector], input=json.dumps(records),
        capture_output=True, text=True)
    if proc.returncode != 0:
        return [f"{name}: select-files.py exited {proc.returncode}: {proc.stderr.strip()[:200]}"]
    result = json.loads(proc.stdout)
    reviewable = {f["path"] for f in result.get("reviewable", [])}
    excluded = {f["path"]: f.get("reason") for f in result.get("excluded", [])}

    errors = []
    stem = os.path.splitext(name)[0]
    if not reviewable and stem not in EMPTY_DIFF_ALLOWLIST:
        reasons = ", ".join(sorted(set(excluded.values())))
        errors.append(
            f"{name}: pre-dispatch selection excludes EVERY fixture file ({reasons}) — "
            f"this case can no longer be detected by any agent")
    for want in (case.get("success_criteria") or {}).get("must_detect") or []:
        target = want.get("file") if isinstance(want, dict) else None
        if not target or target not in files:
            continue
        if target in reviewable:
            continue
        errors.append(
            f"{name}: must_detect targets '{target}' but selection excludes it "
            f"(reason: {excluded.get(target, 'not in output')}) — the planted defect is unreachable")
    return errors


def validate_dir(evals_dir):
    """Return (errors, warnings, n_cases, n_selection) aggregated over evals_dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    selector = os.path.join(here, "select-files.py")
    have_selector = os.path.isfile(selector)
    errors, warnings, n, n_sel = [], [], 0, 0
    if not have_selector:
        warnings.append(
            "select-files.py absent — recall guard SKIPPED, 0 cases checked against "
            "pre-dispatch selection")
    for fn in sorted(os.listdir(evals_dir)):
        if not fn.endswith(".json") or fn.lower().startswith("readme"):
            continue
        n += 1
        path = os.path.join(evals_dir, fn)
        e, w = validate_case(path)
        errors += e
        warnings += w
        if have_selector and not e:
            errors += check_selection(path, selector)
            n_sel += 1
    return errors, warnings, n, n_sel


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    evals_dir = argv[1] if len(argv) > 1 else os.path.join(here, "..", "evals")
    if not os.path.isdir(evals_dir):
        print(f"validate-evals: no such dir: {evals_dir}", file=sys.stderr)
        return 2
    errors, warnings, n, n_sel = validate_dir(evals_dir)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"validate-evals: {len(errors)} error(s) across {n} case(s)")
        return 1
    tail = f", {len(warnings)} warning(s)" if warnings else ""
    print(f"validate-evals: {n} case(s) valid{tail}; "
          f"recall guard checked {n_sel} case(s) against pre-dispatch selection")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
