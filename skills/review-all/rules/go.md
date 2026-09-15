# Go rules

Go defect deltas beyond the shared bug/security/concurrency checks.

#### Errors
- Error return value discarded (`_ = f()` or ignored entirely) on a call whose failure matters here
- Sentinel error compared with `==` instead of `errors.Is`/`errors.As` through a wrapped chain
- Error wrapped with `fmt.Errorf` missing `%w`, losing the chain for later `errors.Is`/`As`

#### Goroutines & channels
- Goroutine started with no way to signal it to stop (no `context.Context`, no done channel)
- Loop variable captured by reference in a goroutine/closure (pre-Go-1.22 semantics)
- Send on a channel with no receiver guaranteed to still be listening — permanent block
- Send on a channel that may already be closed by another path — panic

#### Context & slices
- `context.Context` accepted but never passed downstream, or its `Done()`/cancellation ignored
- `append` on a slice shared with another owner — reallocation vs. in-place aliasing is inconsistent
- Struct embedding a type whose method is shadowed by the outer type, silently changing dispatch

#### Do not report
- Unchecked error from `defer f.Close()` on a read-only file/handle with nothing left to flush
- `_ = err` immediately followed by an equivalent explicit check (e.g. `os.IsNotExist`) on the same value
- Ignored error from `fmt.Println`/`fmt.Fprintf` to stdout/stderr in a CLI tool
- A short-lived goroutine in `main()` for a one-shot CLI with no shutdown/lifecycle requirement
- Range-variable capture on Go 1.22+ modules (per-iteration variable semantics already fixed it)
