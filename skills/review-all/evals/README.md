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
| `42-concurrent-modification` | concurrency | Removing from a `List` inside an enhanced-for loop → `ConcurrentModificationException`. |
| `43-jdbc-resource-leak` | resource leak | A JDBC `Connection`/`Statement`/`ResultSet` opened without try-with-resources → leaked on early return / exception. |
| `44-blank-secret-auth-bypass` | security | A shared secret defaulting to `""` accepts an empty secret header → trust bypass. |
| `45-non-thread-safe-map` | concurrency | A plain `HashMap` mutated concurrently from pool threads with no synchronization → data race. |
| `46-broken-double-checked-locking` | concurrency | Double-checked locking on a non-`volatile` field → unsafe publication / visibility race. |
| `47-io-under-lock` | performance | A blocking remote call inside a `synchronized` block → serializes every caller behind one round-trip. |
| `48-swallowed-interrupt` | error handling | An empty `catch (InterruptedException)` that neither restores the interrupt flag nor exits → lost cancellation. |
| `49-locale-dependent-case` | i18n correctness | `toLowerCase()` with no `Locale` used as a map key → Turkish-i style mismatch (distinct from hardcoded-string i18n). |
| `50-negative-count-underflow` | logic | A decrement with no zero floor → a negative, invalid count reported to callers. |
| `51-exception-as-control-flow` | performance | `NoSuchMethodException` thrown/caught per hierarchy step in a hot loop (stack-fill cost). |
| `52-non-atomic-id-collision` | concurrency | `currentTimeMillis()` + `Math.random()` ID collides within a millisecond → duplicate primary key. |
| `53-db-column-truncation` | data loss | An unbounded value written to a `VARCHAR(64)` column (declared in an unchanged migration) with no length check. |
| `54-mutable-internal-exposure` | encapsulation | A getter returns the internal mutable `List` directly → callers mutate private state. |
| `55-thread-confined-no-race` | precision / noise floor | Correctly thread-safe code (`ConcurrentHashMap` + `AtomicLong`) must NOT be flagged as a race. |
| `56-format-string-specifier-mismatch` | bugs / correctness | Invalid `String.format` specifiers (`%z`, dangling `%`) that throw `IllegalFormatException` at runtime; a correct `%%`-escaped sibling must NOT be flagged. |
| `57-default-charset-encode-decode` | correctness / portability | `getBytes()`/`new String(byte[])` with no `Charset` in a crypto codec → platform-default-dependent, corrupts non-ASCII across hosts (Base64 is not the bug). |
| `58-lock-ordering-deadlock` | concurrency | Nested `synchronized(from){synchronized(to){}}` → AB-BA deadlock when two threads call it in opposite directions. |
| `59-signal-before-state` | concurrency | `CountDownLatch.countDown()` called before the guarded result is assigned → a released waiter reads null/stale (single-writer ordering, not a lost-update race). |
| `60-shallow-clone-shared-collection` | encapsulation / aliasing | `super.clone()` copies a mutable `Map` by reference → clone and original share one backing collection. |
| `61-comparator-vs-head-insert` | logic | Descending sort then `add(0, …)` head-insertion reverses priority (the `Double.compare` comparator itself is correct). |
| `62-python-import-shadowing` | recall / Python scoping | A function-local `from m import x` shadows the module-level name → `UnboundLocalError` on an earlier branch. |
| `63-python-clock-domain-mismatch` | recall / correctness | Wall-clock `time.time()` stored, then subtracted from monotonic `time.monotonic()` → garbage TTL, entries never expire. |
| `64-python-bare-except-platform` | recall / error handling | One over-broad/narrow `except` collapses independent probes, hiding a platform-specific error. |
| `65-python-dict-mutation-unlocked` | recall / concurrency | A shared dict `.clear()`/mutated without the lock readers hold → race. |
| `66-sql-null-three-valued-logic` | recall / SQL | `WHERE col = 0` on a nullable column silently drops NULL rows (needs `COALESCE`). |
| `67-sql-fk-cascade-orphans` | recall / data integrity | Deleting a parent row without removing non-cascaded child references → orphaned rows. |
| `68-csv-formula-injection` | recall / security (CWE-1236) | CSV export quotes per RFC-4180 but doesn't neutralize a leading `= + - @` → spreadsheet formula injection. |
| `69-stale-async-response` | recall / concurrency | Overlapping async loads where a slower earlier response overwrites newer state (needs a generation guard). |
| `70-generation-counter-correct` | precision | A correct generation-counter guard against stale responses — must NOT be flagged as a race. |
| `71-monotonic-timeout-correct` | precision | A correct single-domain `monotonic()` timeout — must NOT be flagged as a clock-domain bug. |
| `72-go-nil-map-write` | recall / Go | A constructor leaves a map nil (no `make`); a later write panics (`assignment to entry in nil map`). |
| `73-go-err-shadowing` | recall / Go | Inner `:=` shadows the outer `err`, so the post-block error check is dead and an error is silently dropped. |
| `74-go-goroutine-leak` | recall / Go | A goroutine blocks forever on a channel send with no cancellation/drain → goroutine leak. |
| `75-go-defer-in-loop` | recall / Go | `defer f.Close()` inside a loop defers to function return → handles accumulate (fd exhaustion). |
| `76-rust-unwrap-panic` | recall / Rust | `.unwrap()`/`.expect()` on a reachable `Err`/`None` (parse/lookup) → runtime panic. |
| `77-rust-blocking-in-async` | recall / Rust | A blocking call (`std::thread::sleep` / sync IO) inside an `async fn` stalls the executor. |
| `78-rust-mutex-across-await` | recall / Rust | A `std::sync::Mutex` guard held across `.await` → deadlock risk / non-`Send` future. |
| `79-go-goroutine-cancellation-correct` | precision | A goroutine with proper `ctx.Done()`/quit-channel exit — must NOT be flagged as a leak. |
| `80-rust-guard-dropped-before-await` | precision | A lock guard dropped before `.await` — must NOT be flagged as held-across-await. |
| `81-boundary-catch-correct` | precision (guards `64`) | A correct top-level `except Exception` boundary that logs + surfaces (correlation id) — must NOT be flagged as a swallowed/over-broad catch. |
| `82-sql-intentional-equality-correct` | precision (guards `66`) | An intentional `WHERE col = 1` on a NOT-NULL column where excluding NULL is correct — must NOT be flagged as a NULL-logic bug. |
| `83-consistent-lock-discipline-correct` | precision (guards `65`) | A shared dict read/written/cleared always under the same lock — must NOT be flagged as a race. |
| `84-csv-formula-neutralized-correct` | precision (guards `68`) | A CSV export that already prefixes `'` on `= + - @` fields — must NOT be flagged as CSV/formula injection. |
| `85-todo-not-defect` | precision | A correct function carrying a `# TODO` for a FUTURE enhancement — the deferred-work note must NOT be flagged as a defect / missing-handling in the current change. |
| `86-gate-blocking-critical` | gate mode | A CRITICAL command-injection diff reviewed via `/review-all gate` must yield a machine verdict with `pass:false`, `blockingCount>=1`, and NO Phase 4 menu. |
| `87-gate-debt-only-pass` | gate mode | A DEBT-only duplication reviewed via `/review-all gate --severity critical` must yield `pass:true` (debt is below the floor) and NO menu. |
| `88-stale-profile-cache` | profile cache | A poisoned LEGACY (`claudeMdHash`) profile cache claiming a Java/`mvn test` toolchain in a plainly-JS repo — must report cache MISS, detect the toolchain fresh (jest), and still catch the diff's null-deref regression. |
| `89-warm-profile-cache` | profile cache | A VALID seeded v2 cache (`fixture.seed_profile_cache`, key computed by `discover.sh`) whose rules ban `console.log` under `src/lib/` — must report cache HIT and still flag the violation, proving cached rules are applied, not merely skipped. |
| `90-review-md-raised-bar` | REVIEW.md | An unchanged repo-root `REVIEW.md` promotes swallowed errors under `src/payments/` to CRITICAL and suppresses style findings under `scripts/`. The diff supplies both — must promote the refund `catch` to CRITICAL *and* attribute it to REVIEW.md, while staying silent on the deliberate naming bait in `scripts/`. **Known non-discriminating** — see the note below. |
| `91-claude-md-stale-claim` | doc staleness (emergent) | A `CLAUDE.md` architectural invariant stated in prose that shares no identifier with the diff — no third-party call during request handling — falsified by a `fetch()` added inside a handler. The consistency agent catches this **without any explicit rule**, which is why the rule was reverted; the case now guards that emergent behavior against regression. |

| `92-failing-test-gate-lead` | gate results | The first fixture with a **runnable toolchain whose gates genuinely fail**: `package.json` points `test` at plain `node tests/run-tests.js` (no dependencies to install), and the diff breaks `applyDiscount` so it subtracts the percent as flat cents. Must show the test gate FAIL *with provenance* in the gate table and name the underlying percentage bug. Exercises Phase 1 end-to-end and the `<gate_results>` block. |

> **What the A/B of these cases established (v0.8.0, N=3, both arms).**
>
> - **`90` proves `REVIEW.md` support works.** Baseline v0.7.1 **FAIL (1/3)**, treatment **PASS (3/3)**. Its first version was non-discriminating — it used a defect default calibration already rated CRITICAL and bait the baseline already ignored — so it was rebuilt around a two-line rounding duplication (defaults to DEBT, `REVIEW.md` promotes to CRITICAL) plus an unvalidated-input defect under `scripts/` that a review normally *does* report and `REVIEW.md` suppresses. Both directions now require the feature.
> - **`91` proved the doc-staleness rule was redundant, and the rule was reverted.** Two independent fixture designs, both **PASS 3/3 on the baseline**: first a doc claim naming a symbol the diff changed (reachable by the existing stale-reference grep), then an architectural invariant in prose sharing *no* identifier with the diff — deliberately built to be out of that mechanic's reach. The consistency agent found it anyway. The case is kept as a regression guard for behavior that is emergent rather than instructed.
> - **`92` is a regression guard, not evidence.** Both arms **PASS 3/3**: a failing Phase 1 gate is caught with or without the `<gate_results>` block, since the gate itself already produces a VERIFIED finding. Its value is that it is the only fixture whose gates genuinely run and fail.
> - **`02` cannot serve as an A/B instrument.** Run twice on identical baseline code it returned `PASS (2/3)` then `FAIL (1/3)`, with no timeouts or errors in the raw logs. Per-agent diff ordering, which only `02` exercises, therefore remains **unmeasured** — neither proven nor regressing.
>
> **The rule all of this produced: a case proves nothing until the baseline arm has been shown to fail it.** Run the baseline arm on every new case, not just the treatment. A case both arms pass is a regression guard; only a case the baseline fails and the treatment passes is evidence.

