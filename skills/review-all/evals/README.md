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
| `16-unit-mismatch-seconds-ms` | correctness | A value collected in seconds assigned to a milliseconds field with no ×1000 — a silent 1000× scale bug. |
| `17-unguarded-request-body` | bugs / validation | A handler dereferences the request body without checking it is present → crash/500 on missing input (better: 400). |
| `18-swallowed-exception` | error handling | A catch on a payment path swallows the error (no log, no rethrow) and returns null — silent failure. |
| `19-generated-file-noise-floor` | precision | A regenerated `DO NOT EDIT` file must NOT be nitpicked for DRY / `any` / style. |
| `20-cache-invalidation-storm` | performance | A full `flushAll()` inside a per-item loop → O(n) cache-invalidation storm. |
| `21-subscription-leak` | resource leak | A method resubscribes on every call without unsubscribing → accumulating live subscriptions. |
| `22-cache-on-failure` | resilience | A pending-promise cache never evicts a rejected fetch → the failure is cached permanently. |
| `23-missing-await-floating-promise` | async | An un-awaited promise (floating) → unhandled rejection + unordered side effect. |
| `24-off-by-one-pagination` | logic | A 1-based page with `start = page * pageSize` skips the first page. |
| `25-inverted-access-guard` | security | `!roles.includes(required)` inverts the access decision (authorization bypass). |
| `26-uninitialized-field` | bugs | A field behind a `!` definite-assignment assertion is never initialized → runtime TypeError. |
| `27-path-traversal` | security | A user-controlled file name joined to ROOT without validation → `../` traversal. |
| `28-secret-in-log` | security | A plaintext password written into a log line. |
| `29-memoize-key-collision` | correctness | A shared memo cache keyed only by input value collides across different operations → wrong cached result. |
| `30-switch-missing-case` | completeness | A switch over a string-literal union omits a member with no default → implicit `undefined` return. |
| `31-xss-innerhtml` | security | User text interpolated into `innerHTML` with no escaping → XSS. |
| `32-open-redirect` | security | A redirect to a user-controlled URL with no allowlist/same-origin check. |
| `33-unbounded-cache-growth` | resource leak | A long-lived cache keyed by unbounded user input with no cap/eviction/TTL → memory growth. |
| `34-command-injection` | security | User input interpolated into a shell command passed to `execSync`. |
| `35-regex-redos` | security / perf | A nested-quantifier regex on user input → catastrophic backtracking (ReDoS). |
| `36-insecure-randomness` | security | A session token generated with `Math.random()` (non-cryptographic PRNG). |
| `37-ssrf` | security | A server-side request to a user-controlled URL with no validation (SSRF). |
| `38-tls-verification-disabled` | security | An HTTPS agent with `rejectUnauthorized: false` (MITM exposure). |
| `39-integer-precision-loss` | correctness | A 64-bit id string parsed with `Number()` → precision loss above 2^53. |
| `40-missing-query-limit` | performance | An unbounded `SELECT` with no `LIMIT`/pagination → loads a growing table. |
| `41-async-foreach` | async | `Array.forEach` with an async callback → per-item promises not awaited. |

41 cases as of this writing. Cases 16–41 were grown from real-world bug-fix patterns (anonymized — no provenance in the fixtures). Per the develop-tests guidance, keep growing (remaining ideas: sarcastic/ambiguous comments that should not become findings, huge multi-thousand-line diffs, mixed-language repos). Claude can generate additional cases from this baseline set.

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
