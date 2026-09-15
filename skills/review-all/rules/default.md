# Default rules

Fallback checklist for file types with no dedicated pack (config, scripts, markup, misc.).

#### Config & data files
- Missing key/field a loader assumes is present — check the reader for unchecked `.get`/`[key]`
- Value type mismatch against how the consumer parses it (numeric-looking string vs. int)
- Duplicate keys in the same map/object, where the last one silently wins

#### Scripts & glue
- Unquoted variable expansion where the value can contain whitespace or a glob
- Missing exit-code check after a command whose failure the caller assumes cannot happen
- Destructive command (`rm`, `DROP`, truncate) added with no guard for this diff's context

#### Do not report
- Formatting or indentation differences in a config file — Standards agent owns those
- A key-ordering change with no consumer that depends on order
- A comment-only change in a script or config file
- Renaming a local shell variable with no external reference
- A generated/vendored config file (lockfile, compiled asset manifest) changed by tooling
