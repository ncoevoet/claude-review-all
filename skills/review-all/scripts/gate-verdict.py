#!/usr/bin/env python3
"""gate-verdict.py — review-all `gate` mode pass/fail decision.

Reads the verified KEPT findings (Phase 2.5 survivors, score >= 75) as a JSON
array on stdin and emits a machine-readable gate verdict: does any confirmed
finding meet or exceed the configured severity floor? This is what makes
review-all consumable as a blocking gate by a CI step or an autonomous loop —
no human report, no interactive menu, just `{pass, blocking[]}` + an exit code.

Severity floor (default CRITICAL): a finding blocks only if its severity rank
is >= the floor's. `critical` blocks 🔴 only; `important` blocks 🔴+🟠; etc.
Appendix findings (score 50-74) are NOT passed here by the orchestrator — only
main-report KEPT findings gate, so a borderline guess never blocks a loop.

Reuses `normalize()` + `SEVERITIES` from the sibling export-findings.py (single
source of the finding shape) via path import, since the filename's hyphen makes
it non-importable by name.

Output object (also written to --out):
  { "pass", "severityFloor", "reviewedSha", "blockingCount",
    "blocking": [{id, severity, confidence, file, line, title}],
    "summary": {critical, important, debt, suggested, question},
    "generated_at" }

Exit 0 = pass (nothing at/above floor). Exit 1 = blocked (>=1 blocking finding).
Exit 2 = malformed input or bad arguments.

Usage:
  gate-verdict.py [--severity critical|important|debt|suggested|question]
                  [--out PATH] [--reviewed-sha SHA] [--timestamp TS]
"""

import argparse
import datetime
import importlib.util
import json
import os
import sys

# Severity ordering — higher rank = more severe. A finding blocks when its rank
# is >= the floor's rank. QUESTION is rank 0 (a question is never a defect to
# gate on unless the floor is explicitly lowered to it).
SEVERITY_RANK = {
    "CRITICAL": 4,
    "IMPORTANT": 3,
    "DEBT": 2,
    "SUGGESTED": 1,
    "QUESTION": 0,
}


def _load_sibling_normalize():
    """Import normalize()/SEVERITIES from export-findings.py by path.

    The hyphen in the filename blocks `import export-findings`; load by spec so
    the finding-shape logic stays single-sourced. Falls back to a local minimal
    normalize if the sibling is missing (keeps the gate usable standalone).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "export-findings.py")
    try:
        spec = importlib.util.spec_from_file_location("_export_findings", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.normalize, mod.SEVERITIES
    except (OSError, AttributeError, ImportError):
        severities = ("CRITICAL", "IMPORTANT", "DEBT", "SUGGESTED", "QUESTION")

        def _normalize(f):
            return {
                "id": str(f.get("id") or f.get("finding_id") or ""),
                "severity": str(f.get("severity", "")).upper(),
                "confidence": f.get("confidence"),
                "file": f.get("file") or f.get("path") or "",
                "line": f.get("line"),
                "root_cause_key": f.get("root_cause_key", ""),
                "title": f.get("title", ""),
                "impact": f.get("impact", ""),
                "fix": f.get("fix", ""),
            }

        return _normalize, severities


def build_verdict(findings, floor, reviewed_sha, ts, severities, partial=False):
    floor = floor.upper()
    floor_rank = SEVERITY_RANK.get(floor, SEVERITY_RANK["CRITICAL"])

    summary = {sev.lower(): 0 for sev in severities}
    blocking = []
    for f in findings:
        sev = f["severity"]
        if sev.lower() in summary:
            summary[sev.lower()] += 1
        if SEVERITY_RANK.get(sev, -1) >= floor_rank:
            blocking.append({
                "id": f["id"],
                "severity": sev,
                "confidence": f["confidence"],
                "file": f["file"],
                "line": f["line"],
                "title": f["title"],
            })

    # Fail-closed on partial coverage: a review that could not fully run (a
    # crashed/timed-out agent, per Phase 2.75) must never read as a green gate.
    # "Couldn't verify" is treated as "not done" — the loop keeps working.
    return {
        "tool": "review-all",
        "mode": "gate",
        "generated_at": ts,
        "severityFloor": floor.lower(),
        "reviewedSha": reviewed_sha,
        "partial": partial,
        "pass": len(blocking) == 0 and not partial,
        "blockingCount": len(blocking),
        "blocking": blocking,
        "summary": summary,
    }


def main():
    ap = argparse.ArgumentParser(prog="gate-verdict.py", add_help=True)
    ap.add_argument(
        "--severity", default="critical",
        choices=("critical", "important", "debt", "suggested", "question"),
        help="severity floor — findings at or above this block the gate")
    ap.add_argument("--out", help="also write the verdict JSON to this path")
    ap.add_argument("--reviewed-sha", default=None)
    ap.add_argument("--timestamp", default=None)
    ap.add_argument(
        "--partial", action="store_true",
        help="review coverage was incomplete (Phase 2.75 PARTIAL) — fail closed")
    args = ap.parse_args()

    normalize, severities = _load_sibling_normalize()

    ts = args.timestamp or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        raw = json.load(sys.stdin)
        if not isinstance(raw, list):
            raise ValueError("input must be a JSON array of findings")
    except (json.JSONDecodeError, ValueError) as ex:
        print(f"gate-verdict: malformed input: {ex}", file=sys.stderr)
        sys.exit(2)

    findings = [normalize(f) for f in raw if isinstance(f, dict)]
    verdict = build_verdict(
        findings, args.severity, args.reviewed_sha, ts, severities, args.partial)

    payload = json.dumps(verdict, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")
    sys.stdout.write(payload)
    print()

    sys.exit(0 if verdict["pass"] else 1)


if __name__ == "__main__":
    main()
