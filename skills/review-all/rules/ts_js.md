# TypeScript/JavaScript rules

TypeScript/JavaScript defect deltas beyond the shared bug/security/performance checks.

#### Type-erasure & assertions
- `any` (or an `as X` cast) papering over a shape mismatch the compiler would otherwise catch
- Non-null assertion (`!`) on a value not actually guaranteed non-null on this path
- Widened union narrowed incorrectly in a branch (discriminant field not checked before use)

#### Promises & async
- Floating promise: an async call with no `await`/`.catch`/`void` whose rejection is unhandled
- `.then()` chain with no terminal `.catch` on a call that can reject
- `async` function whose caller treats the return value synchronously (missing `await`)
- `Promise.all` where one rejection should not abort the others (needs `allSettled`)

#### Equality & mutation
- `==`/`!=` relying on coercion where the operand types can genuinely differ
- In-place mutation (`sort`, `splice`, `push`) on an array received as a prop/argument, not a copy
- Shallow spread (`{...obj}`) assumed to deep-copy a nested object/array

#### Security
- Untrusted input merged into an object via spread/`Object.assign` — prototype pollution if a key like `__proto__` reaches it unfiltered
- User-controlled string built into a `RegExp` — catastrophic backtracking (ReDoS) risk
- `JSON.parse` on untrusted/network input with no surrounding `try/catch`

#### Do not report
- `any` inside a `.d.ts` shim or third-party type-augmentation file — that is its purpose
- A non-null assertion immediately guarded by an early return/throw a few lines above
- An intentionally fire-and-forget call explicitly marked `void promise` for logging/analytics
- `console.log`/`debugger` left in a `*.test.ts`/`*.spec.ts` file
- `==` used against `null` to catch both `null` and `undefined` in one check (idiomatic)
