# Java rules

Java defect deltas beyond the shared bug/security/concurrency checks.

#### Exceptions
- Checked exception caught and discarded (empty catch, or a log line with no rethrow/recovery)
- Broad `catch (Exception e)` around a block that can also throw an unrelated `RuntimeException`
- Cause dropped when wrapping: `throw new FooException(msg)` instead of `(msg, e)`

#### Nulls & Optional
- Autoboxed `Integer`/`Long` compared with `==` outside the small-value cache range
- `Optional.get()` called without `isPresent()`/`orElseThrow` where emptiness is reachable
- `Optional` used as a method parameter or field type (should be a nullable/absent value instead)

#### Equality & collections
- `equals()` overridden without a matching `hashCode()` (or vice versa) — breaks hash-based collections
- Mutable object used as a `HashMap`/`HashSet` key, then mutated after insertion
- Mutable `static` field holding request- or session-scoped data — shared across all callers

#### Streams & serialization
- Stream pipeline with a side effect inside `map`/`filter` instead of a terminal operation
- `readObject`/deserialization of a stream from an untrusted source with no type/allow-list check

#### Do not report
- `Optional.get()` immediately after `isPresent()`/`isEmpty()` guards the same value on the prior line
- `==` on two enum constants (identity comparison is correct and idiomatic for enums)
- Missing `serialVersionUID` (compiler warning, not a functional defect)
- A checked exception wrapped in an unchecked one with the original cause preserved
- `equals`/`hashCode` intentionally left at `Object` identity for a short-lived, never-collected DTO
