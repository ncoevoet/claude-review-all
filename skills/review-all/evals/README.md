# Evals — `/review-all`

A labeled scenario suite that probes whether the orchestrator catches what it should and stays quiet otherwise. Designed around Anthropic's [Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) guidance: measurable criteria, automated grading, edge cases, volume over per-case polish.

## Scenarios

| ID | Category | What it tests |
|----|----------|---------------|
| `01-small-diff-null-deref` | recall | A clear null-deref in a small diff must be flagged 🔴/🟠 and survive verification. |
| `02-large-refactor-no-noise` | precision / noise floor | A pure 200-file rename with green gates must yield ≤2 findings, zero 🔴. |
| `03-auth-crypto-change` | severity calibration | An MD5 downgrade in `src/auth/` must spawn Security Deep Dive and surface 🔴. |
| `04-empty-diff-noop` | edge: empty diff | No working-tree changes → graceful no-op, no fabricated findings, no crash. |
| `05-false-positive-resistance` | edge: intentional pattern | An `any` with a documented `eslint-disable` must NOT be flagged (auto-drop). |
| `06-preexisting-vuln-in-audit` | edge: security-audit escape | In-diff code feeding user input to a pre-existing SQL sink must surface despite the sink line being unchanged. |
| `07-dry-duplication` | DRY agent | New code re-implementing an existing helper's logic must surface as duplicated-logic. |
| `08-n-plus-one` | performance agent | A parameterized query inside a loop must surface as N+1. |
| `09-missing-test-gate` | spec-existence gate | A new exported function with no co-located `*.spec.ts` must be flagged. |
| `10-api-contract-break` | API/contract agent | Renaming a public field while an unchanged consumer still reads the old name. |
| `11-a11y-missing-label` | a11y agent | An icon-only button with no accessible name. |
| `12-i18n-hardcoded-string` | i18n agent | A hardcoded user-facing string where the repo uses a `t()` helper. |
| `13-race-lost-update` | concurrency | A non-atomic read-modify-write across an `await` (lost update). |
| `14-resource-leak` | resource leak | A file handle not closed on the error path. |
| `15-deleted-file-breaks-importer` | deletion handling | A deleted module still imported by an unchanged consumer. |

15 cases as of this writing — all passing in headless cycles. Per the develop-tests guidance, keep growing toward ~20 (remaining ideas: generated files, sarcastic/ambiguous comments, huge multi-thousand-line diffs, mixed-language repos). Claude can generate additional cases from this baseline set.

## Schema

Each scenario is a `*.json` file:

| Field | Purpose |
|-------|---------|
| `id`, `skill`, `query` | Identity + the `/review-all` invocation to run. |
| `fixture` | A materializable spec. `kind: "synthetic-diff"` with `files{path:{before?,after?}}` (omit `after` for an unchanged file, `before` for an added file), or `rename_only`+`files_changed` for a generated mass-rename. |
| `success_criteria` | **Measurable** targets: `must_detect[]` (root-cause-key shape, file, `min_severity`, `verdict`), `must_not_flag[]`, `max_critical`, `max_total_findings`, `must_spawn_agent`, `must_not_error`. |
| `grader` | `method: "llm-rubric"` + a `rubric` string for LLM-as-judge grading (the method the develop-tests doc recommends for nuanced report grading). |
| `expected_behavior[]` / `expected_not_behavior[]` | Legacy keyword assertions, kept for the manual runner. |

## Running

### Headless + LLM-graded (automated — for iteration cycles)

```bash
make install                                  # so /review-all resolves globally
bash ../scripts/run-evals-headless.sh         # all cases, 1 run each
bash ../scripts/run-evals-headless.sh 03      # one case by id prefix
REVIEW_ALL_EVAL_RUNS=3 bash ../scripts/run-evals-headless.sh   # 3 runs/case, scored by majority
REVIEW_ALL_EVAL_EFFORT=low bash ../scripts/run-evals-headless.sh  # workaround a headless thinking-block API error
```

LLM review/grade output is non-deterministic, so a single run is a noisy signal (a clean case can flip PASS↔FAIL between runs). For a trustworthy baseline — and before attributing a prompt change to a score delta — set `REVIEW_ALL_EVAL_RUNS` to 3+ and compare pass-rates, not single results. A review that errors out (empty/`API Error`) is retried once and, if still bad, reported as `ERROR` (not `FAIL`) so infra flakes don't masquerade as quality regressions.

For each case it materializes the fixture into a throwaway temp git repo (`scripts/materialize-fixture.py`), runs `/review-all` there via `claude -p`, then grades the report against the case's `grader.rubric` with a second `claude -p` call. Prints `RESULT,<id>,PASS|FAIL` lines so you can diff scores across prompt revisions. Requires the `claude` CLI; the fixture repos are isolated and disposable.

### Manual (no API — quick smoke check)

```bash
bash ../scripts/run-evals.sh        # prompts you to paste a report path; keyword-grades
```

## Iteration loop (develop-tests cycle)

1. Run `run-evals-headless.sh` to get a baseline PASS rate.
2. Change one prompt (e.g. an agent persona or the verifier rubric).
3. Re-run; compare PASS rate against the baseline. Keep the change only if it improves the suite without regressing other cases.
4. Grow the suite when a real-world miss/false-positive escapes it — every escape becomes a new case.

The JSON files are the authoritative artifact; both runners consume them unchanged.
