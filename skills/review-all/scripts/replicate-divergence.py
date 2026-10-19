#!/usr/bin/env python3
"""replicate-divergence.py — show WHERE replicate runs of one eval case disagree.

A binary PASS/FAIL at N=3 hides which finding flickered. With the runner's
REVIEW_ALL_EVAL_KEEP_DIR set, each case leaves `run<r>.report.md` and
`run<r>.judge.txt` behind; this script lines the final reports up as a matrix
so a finding that appears in 2 of 3 runs, or moves from a severity tier into the
🔬 Unverified section, is visible instead of averaged away. It reads FINAL
reports only, never trajectories.

Clustering: a finding is keyed by its location, never by its title (titles are
reworded run to run). Location = the first backtick span of the entry line that
matches `path:line`. Paths are normalised (leading `./` stripped) and unify
when one is a path-suffix of the other. Within one path, lines within 3 of a
cluster's first line share a row. Findings with no location go to a
`<no-location>` row per tier. Two findings of one run in one cluster show both
glyphs joined by `+`.

Tier glyphs: 🔴🟠🟡🔵⚪ for the severity sections, 🔬 for Unverified, 📎 for the
sub-threshold appendix. A row is DIVERGENT when present in 0<k<N runs OR when
its tier set differs between the runs that have it. Sorted DIVERGENT first.
The tally counts reuse severity-tally.py; the PASS/FAIL parse mirrors the
runner's grep pipeline exactly (a missing/empty judge file is FAIL(empty)).

Usage:
  replicate-divergence.py CASE_DIR [CASE_DIR ...]

Limitation: on small fixtures, distinct findings within +-3 lines of one another
collapse into one cluster, so the cell reads as that run's tier multiset, not a
per-finding row; reports carry no root-cause key to separate them. Observed on
eval 99 (7-line fixture).

Each CASE_DIR is `<keep>/<case-id>`; columns are labelled `<keep>/run<r>` after
the directory's parent name so two arms stay distinguishable.
Exit 0 on a report (divergence is information, not a gate); 2 on bad usage or
when no `run*.report.md` was read (stderr `0 runs read`).
"""
import importlib.util
from collections import Counter
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "severity_tally", os.path.join(HERE, "severity-tally.py"))
severity_tally = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(severity_tally)

TIER_GLYPH = {name: glyph for glyph, name in severity_tally.TIER_GLYPHS.items()}
UNVERIFIED_GLYPH = "\U0001f52c"
APPENDIX_GLYPH = "\U0001f4ce"
LOC_RE = re.compile(r"^[\w./-]+:\d+$")
SPAN_RE = re.compile(r"`([^`]+)`")
RUN_RE = re.compile(r"^run(\d+)\.report\.md$")
PASS_RE = re.compile(r"\bPASS\b", re.I)
FAIL_RE = re.compile(r"\bFAIL\b", re.I)
NO_LOC = "<no-location>"
FUZZ = 3
ABSENT = "—"
TIER_ORDER = "\U0001f534\U0001f7e0\U0001f7e1\U0001f535\u26aa\U0001f52c\U0001f4ce"


def tier_key(glyph):
    i = TIER_ORDER.find(glyph[:1])
    return i if i >= 0 else len(TIER_ORDER)


def judge_verdict(path):
    """Mirror run-evals-headless.sh: PASS iff PASS anywhere and no FAIL on the last line."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return "FAIL(empty)"
    text = text.rstrip("\n")  # $(...) strips trailing newlines
    if not text.strip():
        return "FAIL(empty)"
    last = text.split("\n")[-1]
    return "PASS" if PASS_RE.search(text) and not FAIL_RE.search(last) else "FAIL"


def section_glyph(title):
    lowered = title.lower()
    if "appendix" in lowered:
        return APPENDIX_GLYPH
    if "unverified" in lowered or UNVERIFIED_GLYPH in title:
        return UNVERIFIED_GLYPH
    for glyph in severity_tally.TIER_GLYPHS:
        if glyph in title:
            return glyph
    return None


def parse_findings(text):
    """Return [(glyph, path_or_None, line_or_None)] in document order."""
    out = []
    current = None
    for line in text.splitlines():
        heading = severity_tally.HEADING_RE.match(line)
        if heading:
            current = section_glyph(heading.group(1))
            continue
        if current and severity_tally.ENTRY_RE.match(line):
            loc = next((s for s in SPAN_RE.findall(line) if LOC_RE.match(s)), None)
            if loc:
                path, _, num = loc.rpartition(":")
                out.append((current, norm_path(path), int(num)))
            else:
                out.append((current, None, None))
    return out


def norm_path(path):
    while path.startswith("./"):
        path = path[2:]
    return path


def suffix_related(a, b):
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def unify_paths(paths):
    """Map each path to the longest member of its suffix-connected group."""
    paths = sorted(set(paths), key=lambda p: (-len(p), p))
    canon = {}
    for p in paths:
        canon[p] = next((c for c in dict.fromkeys(canon.values()) if suffix_related(p, c)), p)
    return canon


def dir_labels(dirs):
    """Parent-dir label per dir; lengthened with more parent components until unique."""
    parts = [[c for c in os.path.dirname(os.path.abspath(d.rstrip("/") or d)).split(os.sep) if c] or [d]
             for d in dirs]
    depth = 1
    while True:
        labels = ["/".join(p[-depth:]) for p in parts]
        if len(set(labels)) == len(set(os.path.abspath(d.rstrip("/") or d) for d in dirs)) \
                or depth >= max(len(p) for p in parts):
            return labels
        depth += 1


def load_runs(dirs):
    runs = []
    labels = dir_labels(dirs)
    for d, label_dir in zip(dirs, labels):
        d = d.rstrip("/") or d
        try:
            names = os.listdir(d)
        except OSError:
            continue
        found = sorted((int(m.group(1)), n) for n in names for m in [RUN_RE.match(n)] if m)
        for r, name in found:
            with open(os.path.join(d, name), encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            counts, source = severity_tally.tally(text)
            runs.append({
                "label": "%s/run%d" % (label_dir, r),
                "judge": judge_verdict(os.path.join(d, "run%d.judge.txt" % r)),
                "counts": counts, "source": source,
                "findings": parse_findings(text),
            })
    return runs


def build_rows(runs):
    """Return rows: dict(label, cells[list of glyph-lists per run])."""
    n = len(runs)
    canon = unify_paths([p for r in runs for _, p, _ in r["findings"] if p])
    by_path = {}
    for ri, run in enumerate(runs):
        for glyph, path, line in run["findings"]:
            if path:
                by_path.setdefault(canon[path], []).append((line, ri, glyph))
    rows = []
    for path, items in by_path.items():
        items.sort(key=lambda t: t[0])
        clusters = []
        for line, ri, glyph in items:
            if clusters and line - clusters[-1][0] <= FUZZ:
                clusters[-1][1].append((line, ri, glyph))
            else:
                clusters.append((line, [(line, ri, glyph)]))
        for _, members in clusters:
            lo, hi = members[0][0], members[-1][0]
            cells = [sorted((g for _, ri, g in members if ri == i), key=tier_key) for i in range(n)]
            rows.append({"label": "%s:%s" % (path, lo if lo == hi else "%d-%d" % (lo, hi)),
                         "cells": cells, "order": (path, lo)})
    nolocs = {}
    for ri, run in enumerate(runs):
        for glyph, path, _ in run["findings"]:
            if not path:
                nolocs.setdefault(glyph, [[] for _ in range(n)])[ri].append(glyph)
    for glyph, cells in nolocs.items():
        rows.append({"label": "%s %s" % (NO_LOC, glyph), "cells": cells, "order": (NO_LOC, 0)})
    for row in rows:
        present = [c for c in row["cells"] if c]
        k = len(present)
        row["k"] = k
        row["divergent"] = (0 < k < n or
                            len({tuple(sorted(Counter(c).items())) for c in present}) > 1 or
                            (row["label"].startswith(NO_LOC) and len({len(c) for c in present}) > 1))
    rows.sort(key=lambda r: (not r["divergent"], r["order"]))
    return rows


def render(runs):
    n = len(runs)
    out = ["%d runs read" % n, "",
           "| run | judge | c/i/d/s/q | total | tally source |", "|---|---|---|---|---|"]
    for r in runs:
        if r["counts"] is None:
            out.append("| %s | %s | MISSING | MISSING | MISSING |" % (r["label"], r["judge"]))
        else:
            out.append("| %s | %s | %s | %d | %s |" % (
                r["label"], r["judge"], "/".join(str(x) for x in r["counts"]),
                sum(r["counts"]), r["source"]))
    rows = build_rows(runs)
    out.append("")
    if not rows:
        out.append("no findings in any run (%d runs read)" % n)
        return "\n".join(out)
    out.append("| cluster | " + " | ".join(r["label"] for r in runs) + " | k/N | status |")
    out.append("|---|" + "---|" * n + "---|---|")
    for row in rows:
        cells = ["+".join(c) if c else ABSENT for c in row["cells"]]
        out.append("| %s | %s | %d/%d | %s |" % (
            row["label"], " | ".join(cells), row["k"], n, "DIVERGENT" if row["divergent"] else ""))
    out.append("")
    out.append("Findings without a `path:line` location are bucketed per tier as `%s`." % NO_LOC)
    return "\n".join(out)


def main(argv):
    if not argv or any(a.startswith("-") for a in argv):
        sys.stderr.write("usage: replicate-divergence.py CASE_DIR [CASE_DIR ...]\n")
        return 2
    runs = load_runs(argv)
    if not runs:
        sys.stderr.write("replicate-divergence: 0 runs read (no run*.report.md in %s)\n" % ", ".join(argv))
        return 2
    print(render(runs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
