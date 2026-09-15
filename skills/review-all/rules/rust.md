# Rust rules

Rust defect deltas beyond the shared bug/security/concurrency checks.

#### Panics on reachable paths
- `.unwrap()`/`.expect()` on a `Result`/`Option` derived from untrusted input (parse, network, file)
- `lock().unwrap()` on a `Mutex`/`RwLock` where a prior panic can poison it, propagating the panic
- Array/slice indexing (`v[i]`) where `i` is not already bounds-checked on this path

#### Arithmetic & unsafe
- Integer arithmetic on an untrusted/attacker-influenced size that can overflow in release mode
- `unsafe` block with no invariant justification and no evidence the caller upholds it
- `transmute`/raw-pointer cast used where a safe conversion exists

#### Ownership & concurrency
- `RefCell` borrowed mutably while another borrow of the same cell is live — runtime panic
- `Rc<RefCell<T>>` shared across threads (should be `Arc<Mutex<T>>`) — will not compile or race if forced
- Resource left half-updated because a `Future` was dropped mid-`.await` with no cleanup on drop

#### Do not report
- `.unwrap()`/`.expect()` in `#[test]`/`#[cfg(test)]` code
- `.unwrap()` on a literal or compile-time-constant value that cannot fail (e.g. parsing a hardcoded string)
- An `unsafe` block already carrying a `SAFETY:` justification comment that matches what it does
- `clone()` on a small `Copy`-eligible type flagged purely as an efficiency nit (style/perf, not a defect)
- `#[allow(dead_code)]` on scaffolding for a type not yet wired up in this diff
