# SQL rules

SQL/migration defect deltas beyond the shared injection and N+1 checks.

#### Migrations
- `ALTER TABLE` on a large table with no online/concurrent option — locks writers for the duration
- Multi-statement migration with no transaction wrapper — a mid-migration failure leaves partial state
- `CREATE TABLE`/`CREATE INDEX` with no `IF NOT EXISTS` in a migration system that can re-run
- New foreign key or frequently-joined column added with no supporting index

#### Data integrity
- `DELETE`/`UPDATE` with no `WHERE` clause (or a `WHERE` that always evaluates true)
- Money/quantity column typed `FLOAT`/`REAL` instead of a fixed-point/decimal type
- New column with no `NOT NULL`/`DEFAULT` where the application always expects a value
- `UNION` used where `UNION ALL` is intended (or vice versa) — changes both cost and result rows

#### Query correctness
- Comparison between mismatched types relying on implicit coercion (string vs. numeric column)
- Aggregate (`SUM`/`COUNT`/`AVG`) over a nullable column with no `COALESCE`, skewing the result
- String comparison across columns with different collations, silently changing match semantics

#### Do not report
- Missing index on a column used only for single-row primary-key lookups
- `ALTER TABLE` on a table documented/known to be small (seed data, config/reference table)
- `UNION` (not `ALL`) where the spec explicitly requires de-duplicated rows
- A `DROP`/`TRUNCATE` inside a migration that is explicitly reversible and gated behind a flag
- Non-indexed column that is write-only (never appears in a `WHERE`/`JOIN`/`ORDER BY`)
