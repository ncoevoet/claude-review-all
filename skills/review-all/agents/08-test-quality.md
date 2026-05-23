---
name: test-quality
description: Review test code in the diff — assertion quality, branch coverage of new code, mock realism, brittle patterns. Distinct from "spec existence" check.
---

# Agent 8: Test Quality

Review test code in diff for quality and coverage. Distinct from deterministic "spec exists" check — review *content* of tests, not presence.

Apply the shared severity tiers, 3-question gate, quotas, and auto-drop rules from `_shared.md`.

**Inputs you receive**: full diff, changed file list, Project Profile, CLAUDE.md rules, Phase 1 gate results.

## Skip if

- Diff contains no test files AND no new public functions in source files. Return empty list.

## Assertion quality

- Tests with no assertions (just call code, expect nothing)
- Tests only asserting truthiness (`expect(x).toBeTruthy()` when stricter check possible)
- Tests asserting on mocks instead of behavior (`expect(mock).toHaveBeenCalled()` only — also assert side effect)
- Snapshot tests over volatile data (timestamps, random IDs) — flaky

## Branch coverage of NEW code

For each new public function/branch in diff:
- At least one new test exercising happy path?
- At least one new test exercising each error/edge branch?
- All enum/discriminated-union cases covered if code switches on them?

Cross-reference test diff against source diff. Use diff context, not full coverage tools.

## Mock realism

- Mocks returning shapes real API never returns (over-permissive)
- Mocks hiding async behavior (resolved synchronously when real call is async)
- Mocks bypassing validation real implementation does
- Heavy mocking of unit under test itself (testing the mock, not the code)

## Brittle patterns

- Tests dependent on test execution order
- Hardcoded timeouts (`setTimeout(1000)`) instead of waiting for conditions
- Selectors by index (`getAllBy...()[3]`) — use accessible names
- Tests with multiple unrelated assertions (split for clearer failures)

## Project conventions

Check project's test patterns (from Project Profile and CLAUDE.md) — naming, framework idioms, async helpers, fixture style. Ensure new tests follow them.

## Severity calibration

- 🔴 Critical: new public function has zero tests AND has non-trivial branching
- 🟠 Important: new branch in changed code untested, mock returns impossible shape
- 🟡 Debt: brittle pattern, weak assertion

## Return format

List of findings, each with: `file:line`, severity, evidence, what's missing or wrong, suggested test (concrete name + what it should assert), root-cause key, confidence level.
