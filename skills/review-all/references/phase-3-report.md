# Phase 3 — Unified Report

Loaded by `/review-all` Phase 3. Synthesizes verified findings into a structured markdown report.

## Intent summary

Generate a 2-line "what this change appears to do" summary derived from:
- Commit message(s)
- File names and structure changed
- PR title/description if available

This helps the user calibrate findings.

## Numbering

Number findings continuously across all sections (Finding 1, 2, 3…) for easy reference in Phase 4.

## Report Template

```markdown
# Comprehensive Review Report

## Intent
{2-line summary of what the diff does, from commits/PR/files}

## Summary
- **Target**: {resolved target}
- **Files Changed**: X files (+Y lines, -Z lines)
- **Language/Framework**: {auto-detected}
- **Risk Level**: Low / Medium / High
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

## 🔴 Critical
- **Finding 1**: `file:line` — Description {🔁 recurring if from history}
  - **Impact**: …
  - **Fix**: …
  - **Confirmed by**: {agents, if multi-agent}
  <details><summary>Evidence</summary>

  {code/tool output}
  </details>

> Missing spec files for new public code is always Critical.

## 🟠 Important
{Same shape}

## 🟡 Debt
- **Finding N**: {Smell type} — `file:line`
  - **Refactor**: concrete pattern
  - **Existing utility**: {if any}

## 🔵 Suggested
- **Finding N**: `file:line` — **Current**: … → **Suggested**: …

## ⚪ Questions
- **Finding N**: `file:line` — Question and context

## Dependency Changes
{omit if no manifests changed}

## Potential Issues (Appendix)
<details><summary>Findings scoring 50-74</summary>

- `file:line` — Observation (confidence: {score}/100)
</details>
```

## Section rules

- If a section has no findings, write "None found." (omit only Dependency Changes / Questions when empty)
- Every main-section finding must have score ≥ 75
- Risk Level: High if any 🔴, Medium if 🟠/🟡, Low otherwise
