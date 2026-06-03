# Phase 3 — Unified Report

Loaded by `/review-all` Phase 3. Synthesizes verified findings into a structured markdown report read in a terminal by the engineer who wrote the diff. Optimize for **fast triage**: the reader should learn in one line whether anything blocks merge, then act on each must-fix finding without re-investigating it.

## Verdict line (top of report)

The first line after the title is a one-line verdict, so the reader triages before reading anything else:

- If any 🔴/🟠 exist: `> **Verdict:** N must-fix before merge — X 🔴 Critical, Y 🟠 Important.`
- If none: `> **Verdict:** ✅ No must-fix issues found.` (append ` N optional notes below.` only if there are any).

This mirrors how the report is actually used — "can I merge?" first, details second. Never pad a clean review with low-severity findings to look thorough; a confident clean verdict builds trust, and an empty 🔴/🟠 section is a valid outcome.

## Intent summary

Generate a 2-line "what this change appears to do" summary from:
- Commit message(s)
- File names and structure changed
- PR title/description if available

Helps the user calibrate findings.

## Numbering

Number findings continuously across all sections (Finding 1, 2, 3…) for Phase 4 reference. **Mandatory**: every finding — Critical, Important, Debt, Suggested, Questions, AND Appendix — MUST be prefixed with `**Finding N**:` using a single global counter. The Phase 4 menu's **Custom** option (`#N` syntax) depends on this. Never omit the number, never reset between sections, never reuse a number.

## Severity-letter emphasis

Section headers MUST bold the leading letter so users read legal Custom-menu tokens directly from the report:

- `## 🔴 **C**ritical`
- `## 🟠 **I**mportant`
- `## 🟡 **D**ebt`
- `## 🔵 **S**uggested`
- `## ⚪ Questions` (no severity-letter token)

Mirrors the Phase 4 grammar (`C`/`I`/`D`/`S`) so the report documents the menu syntax.

## Finding anatomy — full for must-fix, one line for optional

Two tiers of detail. **This applies to every section, not just the first one**: Critical and Important findings get the full block; Debt, Suggested, and Questions get exactly one line each.

**Must-fix (🔴 Critical, 🟠 Important)** — full anatomy:
- **Title names the actual failure mode**, quoting the real symbol/identifier from the diff — `Race on `cache` map under concurrent writers`, not `Potential issue`. (Reviews whose titles name the failure mode get acted on without the reader re-investigating; prose that reuses the diff's identifiers predicts a fix.)
- An inline `[SEVERITY · CONFIDENCE]` tag on the title line, e.g. `[🔴 CRITICAL · VERIFIED]`.
- **Impact** — one sentence: what breaks and for whom. Not a restatement of the title.
- **Fix** — one concrete, minimal **suggested** fix (say "suggested", not "the fix"). Show a code/diff snippet only when the fix is unambiguous; for multi-file or design-level fixes give a short "to fix:" instruction instead of a misleadingly precise patch.
- **Evidence** — only the load-bearing source lines (~3–8), fenced and language-tagged. Not the whole function.
- **Confirmed by** — other agents that raised the same root-cause key, if any.

**Optional (🟡 Debt, 🔵 Suggested, ⚪ Questions)** — one line each, no Impact/Fix/Evidence block:
`**Finding N**: `file:line` — <failure mode + concrete identifier>`. If a tier has many entries, lead with the count.

**De-duplicate by root cause**: one root-cause key = one finding, even across agents or files. List the extra sites under that single finding (`also at file:line, file:line`) rather than emitting N near-identical findings — the same issue must not read like N problems.

## Severity encodes confidence at the top tier

A 🔴 CRITICAL finding should be VERIFIED or HIGH confidence — the verifier earns top severity by proof (`verifier.md` → "Severity must be earned by proof"). A 🔴 at MEDIUM confidence is a calibration smell that should already have been hardened or moved to the appendix upstream; render the confidence tag honestly and do not print `🔴 · MEDIUM`.

## Pre-existing findings get a 🟣 marker

A kept finding that this diff did NOT introduce (it survived the security-audit escape in `_shared.md` — a pre-existing 🔴/🟠 in audited auth/crypto/network/build code) carries a 🟣 marker so the reader instantly sees "not the code you just wrote": `**Finding N**: <title> — `file:line` 🟣 `[🔴 CRITICAL · HIGH]` (pre-existing)`. Introduced-vs-pre-existing is an axis independent of severity — surfacing it lets the reader separate "a bug I wrote" from "a bug I touched".

## Merge-readiness score

A `Merge-readiness` line in the Summary gives a graded companion to the binary Verdict. It is a **transparent ratio, not a weighted score** (Ousterhout's law — no voodoo constants):

- `must_fix_total` = count of 🔴 + 🟠 (only these block merge; 🟡/🔵/⚪ do not).
- `resolved` = must-fix findings already addressed (0 at the initial report; rises as fixes apply in the Phase 4 loop).
- `pct = round(100 × resolved / must_fix_total)`.
- **Special case**: `must_fix_total == 0` AND all run gates pass → `100% — ✅ ready to merge`.
- **Gate override**: if any gate FAILed/TIMEOUT, never show 100% even with zero must-fix — show the highest the blockers allow and append `(gates failing)`.

So the initial report on a diff with 3 blockers reads `Merge-readiness: 0% — 0/3 must-fix resolved`; after the Phase 4 apply-fixes/auto-delta resolves two, the re-presented report reads `67% — 2/3 must-fix resolved`. This makes the number genuinely useful in the fix loop, and it never invents a confidence it can't defend.

## Change-type buckets

The Summary's **Files Changed** line breaks the diff down by `git` change type (Added/Modified/Deleted/Renamed), computed in Phase 0.8 via `git diff --name-status`. This is informational AND calibrates scrutiny (SKILL.md Rule 7): newly **Added** code gets the strictest bar (no established-convention cover), **Deleted** code gets downstream-breakage scrutiny. Omit any bucket whose count is 0 to keep the line short (e.g. `12 files (+3 new · ~9 modified; +210, -44)`).

## Report Template

```markdown
# Comprehensive Review Report

> **Verdict:** {N must-fix before merge — X 🔴, Y 🟠 | ✅ No must-fix issues found.}

## Intent
{2-line summary of what the diff does, from commits/PR/files}

## Summary
- **Target**: {resolved target}
- **Files Changed**: X files (+N new · ~M modified · −K deleted · ▷R renamed; +Y lines, -Z lines)
- **Language/Framework**: {auto-detected}
- **Risk Level**: Low / Medium / High
- **Merge-readiness**: {pct}% — {resolved}/{total} must-fix resolved {| ✅ ready to merge}
- **Findings**: X 🔴 Critical, Y 🟠 Important, Z 🟡 Debt, W 🔵 Suggested, V ⚪ Questions
- **Agents run**: {list}

## Automated Gate Results

| Gate | Result | Details |
|------|--------|---------|
| Typecheck | ✅ PASS / ❌ FAIL(N) / ⏭ SKIP / ⏱ TIMEOUT / ➖ N/A | … |
| Lint | … | … |
| Tests | … | … |
| Spec Existence | ✅ PASS / ❌ MISSING(N) | … |
| Dependencies | ➖ N/A / 📦 CHANGED(+X, -Y, Z bumped) | … |

## 🔴 **C**ritical
- **Finding 1**: {failure-mode title naming the real identifier} — `file:line` `[🔴 CRITICAL · VERIFIED]` {🔁 recurring if from history}
  - **Impact**: {one sentence — what breaks}
  - **Fix**: {one concrete suggested fix}
  - **Confirmed by**: {agents, if multi-agent}
  <details><summary>Evidence</summary>

  {3–8 load-bearing source lines, fenced + language-tagged}
  </details>

> Missing spec files for new public code is always Critical.

## 🟠 **I**mportant
{Same full anatomy as Critical}

## 🟡 **D**ebt
- **Finding N**: `file:line` — {smell + identifier, one line}

## 🔵 **S**uggested
- **Finding N**: `file:line` — {measurable improvement, one line}

## ⚪ Questions
- **Finding N**: `file:line` — {question, one line}

## Dependency Changes
{omit if no manifests changed}

## Potential Issues (Appendix)
<details><summary>Findings scoring 50-74</summary>

- **Finding N**: `file:line` — Observation (confidence: {score}/100)
</details>

---
*Scope: {N} files / {agents that ran}. {Skipped: <files + reason (binary / generated / too-large)> | No files skipped.}*

<!-- review-all-severity: {"critical":C,"important":I,"debt":D,"suggested":S,"question":Q} -->
```

## Section rules

- **An empty must-fix section is a valid, trust-building outcome.** If Critical/Important are empty, the Verdict says "✅ No must-fix issues found" and each empty section says "None found." Do NOT pad with low-severity findings to look thorough.
- For other empty sections write "None found." (omit only Dependency Changes / Questions when empty).
- Every main-section finding must score ≥ 75; 50–74 goes to the appendix.
- Risk Level: High if any 🔴, Medium if 🟠/🟡, Low otherwise.
- **Concision drives action.** One-sentence Impact; evidence capped to the load-bearing lines; Debt/Suggested/Questions one line each. The one-line rule applies to Debt, Suggested, AND Questions; the full-anatomy rule applies to Critical AND Important. If Critical+Important runs past ~1–2 screens, that is a calibration problem (over-flagging), not a formatting one — re-check verifier precision rather than just trimming text.
- **Scope footer**: end with the one-line scope note so the reader sees what was and was NOT reviewed (files skipped as binary/generated/too-large), pre-empting "did it even look at X?".
- **Quota overflow is surfaced, not silent**: when a per-agent quota or the global SUGGESTED/QUESTION cap truncates a tier, append `+N more <tier> (capped)` to that section instead of dropping silently — the reader must know coverage was capped, not assume the tier was empty.
- **Machine-readable tally**: the report's final line is an HTML comment `<!-- review-all-severity: {"critical":…,"important":…,"debt":…,"suggested":…,"question":…} -->` so CI and scripts can parse per-tier counts (e.g. with `jq`) and gate on them.
