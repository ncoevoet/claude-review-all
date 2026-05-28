# Finding Lifecycle — `.claude/review-all/state.json`

Loaded by `/review-all` Phase 2.5. Tracks each unique finding across runs so unchanged findings skip re-verification and stale findings auto-decay.

## Why this exists

`history.jsonl` is append-only and only counts recurrence. It cannot answer: "is finding X still present?", "was finding Y fixed?", "is finding Z snoozed?". `state.json` is the authoritative per-finding lifecycle store. `history.jsonl` remains the audit log.

## Schema

Path: `.claude/review-all/state.json` (location overridable via `.claude/review-all.json` key `stateFile`).

```json
{
  "version": 1,
  "migrations": [],
  "findings": {
    "<root_cause_key>": {
      "status": "open|fixed|wontfix|stale|snoozed",
      "severity": "CRITICAL|IMPORTANT|DEBT|SUGGESTED|QUESTION",
      "first_seen_sha": "<commit sha when first reported>",
      "last_seen_sha": "<commit sha of most recent run that re-saw it>",
      "last_seen_at": "<ISO timestamp>",
      "file_line": "<path:line at last sighting>",
      "code_hash": "<sha256 of the flagged lines at last sighting>",
      "fix_commit_sha": "<sha that resolved it, or null>",
      "snoozed_until": "<ISO timestamp, or null>",
      "miss_count": 0,
      "verifier_version": 2
    }
  }
}
```

## Status semantics

| Status | Meaning | Set by |
|--------|---------|--------|
| `open` | Finding present in latest run, not suppressed | default on first sight |
| `fixed` | Code at `file_line` changed AND finding no longer surfaced | Phase 2.5 transition: was `open`, not re-seen, code hash differs |
| `wontfix` | User explicitly dismissed in Phase 4 menu | Phase 4 user action |
| `stale` | Not re-seen for 2+ consecutive runs while code unchanged | Phase 2.5 promotion: `miss_count >= 2` |
| `snoozed` | Suppressed until `snoozed_until` | Phase 4 user action; replaces old `snooze.json` |

## Lifecycle rules (run by Phase 2.5)

1. **Load** `state.json`. If absent, treat as empty.
2. **Before verification**, for each candidate finding:
   - If status is `wontfix` and `code_hash` matches current code at `file_line` → drop without spending a verifier.
   - If status is `snoozed` and `snoozed_until` is in the future → drop.
   - If status is `open` AND `last_seen_sha == HEAD` AND `code_hash` matches current code → reuse prior verdict (skip verifier). Log "reused state for N findings". This is the idempotent-re-run case (running `/review-all` twice on the same commit).
3. **After verification**, for every kept/appendix finding (orchestrator-owned — needs per-finding metadata):
   - If new key → insert as `open`, `first_seen_sha = HEAD`, `last_seen_sha = HEAD`, `miss_count = 0`.
   - If existing → update `last_seen_sha = HEAD`, `last_seen_at`, `file_line`, `code_hash`, reset `miss_count = 0`.
   - If existing AND status was `fixed` or `stale` → set status back to `open` and clear `fix_commit_sha` (regression: a resolved finding re-surfaced). `scripts/state-sweep.py` also performs this reopen for any seen-key it finds.
4. **Sweep** existing entries not re-seen in this run:
   - `open` entry, `code_hash` no longer matches code at `file_line` (or file deleted) → transition to `fixed`, set `fix_commit_sha = HEAD`.
   - `open` entry, code still matches → increment `miss_count`. If `miss_count >= 2` → transition to `stale`.
   - `snoozed` entry, `snoozed_until` in the past → transition to `open` (resume normal lifecycle; will be re-evaluated next run that surfaces it).
   - `wontfix` entry, `code_hash` no longer matches → transition to `open` (clear `fix_commit_sha`). Rationale: a code rewrite at the flagged location may have moved/altered the issue rather than fixed it; do not silently mark `fixed`. Next run that re-surfaces it will re-evaluate; if it does not re-surface, the normal `open`-sweep rules promote it to `fixed` or `stale`.
   - Time-bound fallback: for `open` entries only, if `last_seen_at` is older than 30 days → transition to `stale`. Prevents entries with `miss_count == 1` (or suppressed by `skipAgents`) from sitting around indefinitely. `snoozed` entries are NOT subject to this rule — their lifetime is bounded by `snoozed_until` (handled by the preceding `snoozed → open` transition), and a long snooze (e.g. 90 days) must not be silently promoted to `stale` at day 30.
5. **Write** state back atomically (`Write` full file, do not append).

### Division of labor: script vs orchestrator

`scripts/state-sweep.py` performs the **sweep** of existing entries (step 4) plus the `fixed`/`stale` → `open` regression reopen, given only the run's seen-keys (and optional changed-keys). It does **not** insert entries for brand-new `root_cause_key`s or recompute `code_hash`/severity/`file_line` — that is step 3, which stays in the orchestrator because it needs per-finding metadata the script is not handed. Run the script for the sweep, then have the orchestrator insert/refresh seen findings.

## Migration from `snooze.json`

Each one-shot migration is identified by a string id stored in the top-level `migrations` array. Before running a migration, check membership; after running, append its id and write atomically. Re-runs are no-ops.

`snooze-v1` migration. Run BOTH passes every invocation — they are independent and the cleanup pass must remain reachable after the migration is recorded.

1. **Cleanup pass** (runs first, every invocation): if `"snooze-v1"` ∈ `migrations` AND `.claude/review-all/snooze.json` still exists → delete `snooze.json`. Then go to step 5.
2. **Migration pass**: if `"snooze-v1"` ∈ `migrations` → skip steps 3–4 (already migrated).
3. Read legacy `.claude/review-all/snooze.json` if present. For each entry, create/update the matching `state.json` finding with `status: snoozed`, `snoozed_until: <legacy expiry>`.
4. Append `"snooze-v1"` to `migrations`. Leave `snooze.json` in place this cycle (rollback safety); the next run's cleanup pass deletes it.
5. Done.

## Interaction with `history.jsonl`

`history.jsonl` keeps its current append-only role for audit + recurrence detection. The recurrence escalation rule in `phase-2.5-verification.md` still uses it — `state.json` does NOT replace history, it complements it.

## Code hash computation

For each finding with a concrete `file:line`, compute `code_hash = sha256(<3 lines before>\n<flagged lines>\n<3 lines after>)`. The ±3 context lines make the hash robust to whitespace-only edits elsewhere in the file while still detecting real code changes at the flagged location.

Findings without a line anchor (cross-file findings, missing-spec findings, repo-wide rules) compute `code_hash = sha256("<file_line>|<severity>|<root_cause_key>")`. These hashes change only when the finding's identifying tuple changes, so reuse semantics still work; `fixed` transitions for these findings depend on the finding no longer surfacing rather than on code-window divergence.
