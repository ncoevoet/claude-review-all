#!/usr/bin/env python3
"""export-findings.py — Phase 4 "Export findings (JSON + SARIF)".

Reads a JSON array of verified findings on stdin and emits machine-readable
exports for CI ingestion (a companion to the human Markdown report). Each
finding should carry:
  - id (string)
  - severity (CRITICAL|IMPORTANT|DEBT|SUGGESTED|QUESTION)
  - file (path), line (int, optional)
  - root_cause_key (string)
  - title (string)
  - confidence (number 0-100 or string, optional)
  - impact / fix / evidence (string, optional)

Outputs:
  - JSON  -> a normalized object {tool, generated_at, summary, findings}
            (review-<ts>.json)
  - SARIF -> a SARIF 2.1.0 log (review-<ts>.sarif). Level map:
            CRITICAL->error, IMPORTANT->warning, DEBT/SUGGESTED->note;
            QUESTION is omitted (a question is not a defect to gate on).

Usage:
  export-findings.py [--format json|sarif|both] [--out-dir DIR] [--timestamp TS]
  - With --out-dir: write the file(s) there and print each written path.
  - Without --out-dir: print the single requested format to stdout
    (--format both then requires --out-dir).

Exit 0 on success; 2 on malformed input or bad arguments.
"""

import argparse
import datetime
import json
import os
import sys

SEVERITIES = ("CRITICAL", "IMPORTANT", "DEBT", "SUGGESTED", "QUESTION")
SARIF_LEVEL = {
    "CRITICAL": "error",
    "IMPORTANT": "warning",
    "DEBT": "note",
    "SUGGESTED": "note",
    # QUESTION intentionally absent -> excluded from SARIF results
}
TOOL_NAME = "review-all"
TOOL_URI = "https://github.com/ncoevoet/claude-review-all"


def normalize(f):
    """Project a raw finding onto the stable export shape (id always present)."""
    sev = str(f.get("severity", "")).upper()
    return {
        "id": str(f.get("id") or f.get("finding_id") or ""),
        "severity": sev,
        "confidence": f.get("confidence"),
        "file": f.get("file") or f.get("path") or "",
        "line": f.get("line"),
        "root_cause_key": f.get("root_cause_key", ""),
        "title": f.get("title", ""),
        "impact": f.get("impact", ""),
        "fix": f.get("fix", ""),
    }


def build_json(findings, ts):
    summary = {sev.lower(): 0 for sev in SEVERITIES}
    for f in findings:
        sev = f["severity"].lower()
        if sev in summary:
            summary[sev] += 1
    return {
        "tool": TOOL_NAME,
        "generated_at": ts,
        "summary": summary,
        "findings": findings,
    }


def build_sarif(findings, ts):
    rules = {}
    results = []
    for f in findings:
        level = SARIF_LEVEL.get(f["severity"])
        if level is None:  # QUESTION (or unknown) — not a gateable defect
            continue
        rule_id = f["root_cause_key"] or f["id"] or "review-all.finding"
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": f["title"] or rule_id},
            }
        text = f["title"] or rule_id
        if f["impact"]:
            text = f"{text} — {f['impact']}"
        region = {}
        if isinstance(f["line"], int) and f["line"] > 0:
            region["startLine"] = f["line"]
        location = {
            "physicalLocation": {
                "artifactLocation": {"uri": f["file"]},
            }
        }
        if region:
            location["physicalLocation"]["region"] = region
        props = {"severity": f["severity"]}
        if f["confidence"] is not None:
            props["confidence"] = f["confidence"]
        results.append({
            "ruleId": rule_id,
            "level": level,
            "message": {"text": text},
            "locations": [location],
            "properties": props,
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": TOOL_NAME,
                "informationUri": TOOL_URI,
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }


def main():
    ap = argparse.ArgumentParser(prog="export-findings.py", add_help=True)
    ap.add_argument("--format", choices=("json", "sarif", "both"), default="both")
    ap.add_argument("--out-dir")
    ap.add_argument("--timestamp")
    args = ap.parse_args()

    ts = args.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")

    try:
        raw = json.load(sys.stdin)
        if not isinstance(raw, list):
            raise ValueError("input must be a JSON array of findings")
    except (json.JSONDecodeError, ValueError) as ex:
        print(f"export-findings: malformed input: {ex}", file=sys.stderr)
        sys.exit(2)

    findings = [normalize(f) for f in raw if isinstance(f, dict)]

    artifacts = {}
    if args.format in ("json", "both"):
        artifacts["json"] = json.dumps(build_json(findings, ts), indent=2)
    if args.format in ("sarif", "both"):
        artifacts["sarif"] = json.dumps(build_sarif(findings, ts), indent=2)

    if not args.out_dir:
        if args.format == "both":
            print("export-findings: --format both requires --out-dir", file=sys.stderr)
            sys.exit(2)
        sys.stdout.write(artifacts[args.format])
        print()
        return

    os.makedirs(args.out_dir, exist_ok=True)
    safe_ts = ts.replace(":", "").replace("-", "")
    ext = {"json": "json", "sarif": "sarif"}
    for kind, content in artifacts.items():
        path = os.path.join(args.out_dir, f"review-{safe_ts}.{ext[kind]}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.write("\n")
        print(path)


if __name__ == "__main__":
    main()
