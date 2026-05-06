# Phase 2.5 — Dedupe → Verify

Loaded by `/review-all` Phase 2.5. Eliminates duplicates, verifies survivors via batch verifiers, and persists scoring history for recurrence detection.

## Step 2.5a — Dedupe (cheap, before verify)

Before spending verifier tokens:
1. Group all findings by `root_cause_key`.
2. For each group, keep the most detailed finding as primary; record the other agents that flagged it as `confirmed_by`.
3. Build the per-agent batch lists for verification (each agent's surviving findings).

**Global caps after dedup** (prevents the report from drowning in noise — with 10 agents the per-agent quotas alone allow up to 30 SUGGESTED + 20 QUESTION):
- Keep at most 10 SUGGESTED findings globally, ranked by score (ties broken by cross-agent `confirmed_by` count, then severity).
- Keep at most 8 QUESTION findings globally (same ranking).
- CRITICAL / IMPORTANT / DEBT have no global cap — never drop a real bug for noise reasons.

## Step 2.5b — Batch Verification

Persona: `verifier.md`. Spawn ONE verifier per source agent, IN PARALLEL — each verifies that agent's full finding list at once. This is ~5× cheaper than per-finding verifiers.

Each verifier receives: source agent's findings, full diff, source files, Project Profile, CLAUDE.md rules, snooze list, and the cross-agent confirmation map (so it can apply the +10 cross-confirmation bonus).

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
