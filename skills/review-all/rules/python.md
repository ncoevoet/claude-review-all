# Python rules

Python defect deltas beyond the shared bug/security/concurrency checks.

#### Mutable & shared state
- Mutable default argument (`def f(x=[])`, `x={}`) accumulating state across calls
- Class-level mutable attribute (`items = []`) shared across all instances instead of set in `__init__`
- `functools.lru_cache`/`cache` on an instance method — caches across instances, leaks via `self`

#### Iteration & resources
- Generator consumed once, then reused as if it were a list (silently yields nothing the 2nd time)
- File/socket/lock opened without `with`, left open on an exception path
- Context manager's `__exit__` returning truthy, silently swallowing the exception it wrapped

#### Async
- Blocking call (sync I/O, `time.sleep`) inside an `async def`, stalling the event loop
- Coroutine created but never awaited or scheduled (`asyncio.create_task` result dropped)

#### Error handling
- Bare `except:` (or `except Exception:`) around a call that raises one specific, expected error
- `assert` used to validate external/user input — stripped under `-O`, not a real guard

#### Do not report
- Unused imports or parameters in a `.pyi` stub file — required by the stub format
- `except Exception` where the wrapped call is documented to raise a heterogeneous set of errors (e.g. a plugin/dispatch boundary)
- A mutable default that is never mutated (e.g. `=()`, or a frozen/immutable value)
- An un-awaited coroutine created purely for its side effect and fired via `asyncio.ensure_future` with an explicit "fire and forget" contract
- `assert` used in test files — that is its intended use there
