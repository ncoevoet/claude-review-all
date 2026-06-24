#!/usr/bin/env python3
"""eval-scorecard.py — aggregate precision / recall / SNR scorecard for the
/review-all eval suite.

Consumes the RESULT / SCORE lines emitted by run-evals-headless.sh (from a file
argument or stdin) plus the evals/*.json case metadata, and prints a suite-level
scorecard the per-case PASS/FAIL stream cannot give on its own:

  Recall%      pass-rate over RECALL cases (success_criteria.must_detect present).
  Precision%   pass-rate over PRECISION counter-cases (no must_detect; correct
               code that must NOT be flagged) — i.e. noise-resistance.
  F1           harmonic mean of Recall% and Precision%.
  SNR (proxy)  finding-count signal-to-noise from the SCORE lines:
                 signal = sum of (critical+important) findings on recall cases,
                          capped per case at its must_detect count so one
                          over-flagging recall case cannot inflate it;
                 noise  = sum of (critical+important) findings on precision
                          counter-cases (correct code; any 🔴/🟠 there is noise).
               A PROXY: suite-derived from case labels + the report's severity
               tally, NOT a CR-Bench per-comment ground-truth SNR. Reported as
               approximate, and only when SCORE lines are present.

Recall/Precision/F1 need only RESULT lines, so the scorecard is useful against an
existing results file with no harness change; SNR additionally needs SCORE lines
and is omitted when they are absent.

Usage:
  eval-scorecard.py [results_file] [--evals DIR]
  run-evals-headless.sh ... | eval-scorecard.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EVALS = os.path.join(HERE, "..", "evals")
SIGNAL_KEYS = ("critical", "important")


def load_cases(evals_dir):
    """Map case id -> {category, must_detect} from evals/*.json."""
    cases = {}
    if not os.path.isdir(evals_dir):
        return cases
    for name in sorted(os.listdir(evals_dir)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(evals_dir, name)) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        cid = data.get("id") or name[:-5]
        must_detect = (data.get("success_criteria") or {}).get("must_detect") or []
        cases[cid] = {
            "category": "recall" if must_detect else "precision",
            "must_detect": len(must_detect),
        }
    return cases


def parse_lines(lines):
    """Parse RESULT,<id>,<verdict> ... and SCORE,<id>,c,i,d,s,q,total lines."""
    results = {}
    scores = {}
    for raw in lines:
        line = raw.strip()
        if line.startswith("RESULT,"):
            parts = line.split(",", 2)
            if len(parts) == 3 and parts[2].strip():
                results[parts[1]] = parts[2].split()[0].upper()
        elif line.startswith("SCORE,"):
            parts = line.split(",")
            if len(parts) == 8:
                try:
                    scores.setdefault(parts[1], []).append([int(x) for x in parts[2:8]])
                except ValueError:
                    continue
    return results, scores


def mean_row(rows):
    """Element-wise mean of equal-length integer rows (a case's per-run counts)."""
    n = len(rows)
    return [sum(col) / n for col in zip(*rows)]


def pct(num, den):
    return 100.0 * num / den if den else None


def fmt_pct(value):
    return "  n/a" if value is None else f"{value:5.1f}%"


def f1(recall, precision):
    if recall is None or precision is None or (recall + precision) == 0:
        return None
    return 2 * recall * precision / (recall + precision)


def compute(cases, results, scores):
    tallies = {"recall": [0, 0], "precision": [0, 0]}  # category -> [passed, graded]
    errored = unknown = 0
    for cid, verdict in results.items():
        case = cases.get(cid)
        if case is None:
            unknown += 1
            continue
        if verdict == "ERROR":
            errored += 1
            continue
        bucket = tallies[case["category"]]
        bucket[1] += 1
        if verdict == "PASS":
            bucket[0] += 1

    signal = noise = 0.0
    for cid, rows in scores.items():
        case = cases.get(cid)
        if case is None:
            continue
        crit, imp = mean_row(rows)[:2]
        sig_imp = crit + imp
        if case["category"] == "recall":
            signal += min(sig_imp, max(1, case["must_detect"]))
        else:
            noise += sig_imp

    recall = pct(tallies["recall"][0], tallies["recall"][1])
    precision = pct(tallies["precision"][0], tallies["precision"][1])
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1(recall, precision),
        "recall_pass": tallies["recall"][0],
        "recall_total": tallies["recall"][1],
        "precision_pass": tallies["precision"][0],
        "precision_total": tallies["precision"][1],
        "errored": errored,
        "unknown": unknown,
        "signal": signal,
        "noise": noise,
        "has_scores": bool(scores),
    }


def snr_value(signal, noise):
    if noise == 0:
        return float("inf") if signal > 0 else None
    return signal / noise


def render(s):
    lines = []
    lines.append("review-all eval scorecard")
    lines.append("=========================")
    graded = s["recall_total"] + s["precision_total"]
    lines.append(
        f"Graded: {graded} ({s['recall_total']} recall, {s['precision_total']} precision)"
        f" · errored: {s['errored']} · unknown-id: {s['unknown']}")
    lines.append("")
    lines.append(f"Recall      : {fmt_pct(s['recall'])}"
                 f"  ({s['recall_pass']}/{s['recall_total']} recall cases passed)")
    lines.append(f"Precision   : {fmt_pct(s['precision'])}"
                 f"  ({s['precision_pass']}/{s['precision_total']} counter-cases passed)"
                 f"  [noise-resistance]")
    lines.append(f"F1          : {fmt_pct(s['f1'])}")
    if s["has_scores"]:
        snr = snr_value(s["signal"], s["noise"])
        snr_str = "  inf" if snr == float("inf") else ("  n/a" if snr is None else f"{snr:5.2f}")
        lines.append("")
        lines.append(f"SNR (proxy) : {snr_str}"
                     f"  (signal={s['signal']:.1f} / noise={s['noise']:.1f} 🔴+🟠 findings)"
                     f"  [approx — see evals/README.md]")
    lines.append("")
    snr = snr_value(s["signal"], s["noise"]) if s["has_scores"] else None
    snr_machine = ("inf" if snr == float("inf")
                   else "" if snr is None else f"{snr:.4f}")
    lines.append(
        "SCORECARD,"
        f"recall={_m(s['recall'])},precision={_m(s['precision'])},f1={_m(s['f1'])},"
        f"snr={snr_machine},signal={s['signal']:.1f},noise={s['noise']:.1f}")
    return "\n".join(lines)


def _m(value):
    return "" if value is None else f"{value:.2f}"


def main(argv):
    evals_dir = DEFAULT_EVALS
    path = None
    i = 0
    while i < len(argv):
        if argv[i] == "--evals":
            evals_dir = argv[i + 1]
            i += 2
        else:
            path = argv[i]
            i += 1
    src = open(path) if path else sys.stdin
    try:
        results, scores = parse_lines(src)
    finally:
        if path:
            src.close()
    cases = load_cases(evals_dir)
    print(render(compute(cases, results, scores)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
