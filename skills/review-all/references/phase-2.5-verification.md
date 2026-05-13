# Phase 2.5 — Dedupe → Verify

Loaded by `/review-all` Phase 2.5. Eliminates duplicates, verifies survivors via batch verifiers, and persists scoring history for recurrence detection.

## Step 2.5.0 — Load lifecycle state

Before dedupe, read `.claude/review-all/state.json` per the schema and rules in **`state-file.md`** (sibling of this file). This file tracks per-finding lifecycle (`open|fixed|wontfix|stale|snoozed`) across runs and lets verification skip findings that are provably unchanged. If `state.json` is absent, treat as empty and continue.

Lifecycle interactions with the steps below:
- Step 2.5a (dedupe): drop any candidate whose `state.json` status is `wontfix` (with matching `code_hash`) or `snoozed` (with future `snoozed_until`) before sending to a verifier.
- Step 2.5b (verify): if a candidate's stored `status == open` AND `code_hash` matches current code AND `last_seen_sha == HEAD` AND the stored `verifier_version` matches the current persona version (see `verifier.md` frontmatter `version` field), reuse the prior verdict and skip the verifier. Count and log: `reused state for <N> findings`. A `verifier_version` bump (e.g., the hostile-stance change) invalidates all prior verdicts — every finding is re-verified next run.
- After Step 2.5b: update the file per the lifecycle rules in `state-file.md` (insert new, refresh existing, sweep missing into `fixed`/`stale`). Write atomically.

## Step 2.5a — Dedupe (cheap, before verify)

Collect all findings from Phase 2 agents into a single JSON array, then pipe through the bundled script:

```bash
echo "$ALL_FINDINGS_JSON" | python3 scripts/dedupe.py
```

The script groups by `root_cause_key`, picks the most evidence-rich finding as primary, annotates each kept finding with `confirmed_by` (the other agents that raised the same key), and applies the global caps below. Output is `{"kept": [...], "dropped_global_cap": [ids]}`.

**Global caps the script enforces** (prevents the report from drowning in noise — with 10 agents the per-agent quotas alone allow up to 30 SUGGESTED + 20 QUESTION):
- Keep at most 10 SUGGESTED findings globally, ranked by `confirmed_by` count then evidence richness.
- Keep at most 8 QUESTION findings globally (same ranking).
- CRITICAL / IMPORTANT / DEBT have no global cap — never drop a real bug for noise reasons.

Build the per-agent verification batches from `kept` (group by original `source_agent` field).

## Step 2.5b — Batch Verification

Persona: `verifier.md`. Spawn ONE verifier per source agent, IN PARALLEL — each verifies that agent's full finding list at once. This is ~5× cheaper than per-finding verifiers.

**Model tier**: verifier agents are spawned at the `verifierModel` config tier (default `haiku`; see `config-keys.md`). Verification is a constrained re-read with JSON-schema output — Haiku handles it cleanly while cutting verifier token cost by 60–70% vs the source-agent tier. Override to `sonnet`/`opus` if you observe verifier mis-scoring on a given codebase, or `inherit` to pin to the parent session's tier.

Each verifier receives: source agent's findings, full diff, source files, Project Profile, CLAUDE.md rules, and the cross-agent confirmation map (so it can apply the +10 cross-confirmation bonus). Snoozed/`wontfix` findings are already filtered in Step 2.5.0 — verifier never sees them.

## Threshold

- Score ≥ 75 → main report (`keep`)
- Score 50–74 → "Potential Issues" appendix (`appendix`)
- Score < 50 → silently dropped (`drop`)

Findings tagged `confidence: VERIFIED` from Phase 1 gates skip verification entirely (auto-keep at 90).

## History persistence

Append each kept/appendix finding to `historyFile` (default `.claude/review-all/history.jsonl`):
```json
{"timestamp": "<iso>", "target": "<resolved>", "root_cause_key": "...", "severity": "...", "file_line": "...", "score": 90}
```
Before reporting, scan history for the same `root_cause_key` appearing in 3+ recent reviews → escalate severity by one tier (DEBT → IMPORTANT, etc.) and annotate "recurring".

## State.json lifecycle sweep

After verification, hand the lifecycle bookkeeping to the bundled script:

```bash
# seen-keys.json = JSON array of root_cause_keys kept + appendix this run
# changed-keys.json (optional) = JSON array of keys whose underlying code hash changed
STATE_SWEEP_CHANGED_KEYS=changed-keys.json \
  python3 scripts/state-sweep.py .claude/review-all/state.json "$HEAD_SHA" seen-keys.json
```

The script applies the transitions documented in `state-file.md`: `snoozed → open` (expired), `open → fixed` (code changed AND not re-seen), `open → stale` (`miss_count >= 2` or >30 days unseen), `wontfix → open` (code changed). It writes the file atomically and prints a one-line summary. The orchestrator does not need to re-implement the rules in prose.
