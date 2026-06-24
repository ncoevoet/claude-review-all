# Phase 2.5 — Dedupe → Verify

Loaded by `/review-all` Phase 2.5. Eliminates duplicates, verifies survivors via batch verifiers, and persists scoring history for recurrence detection.

## Step 2.5.0 — Load lifecycle state

Before dedupe, read `.claude/review-all/state.json` per the schema and rules in **`state-file.md`** (sibling of this file). Tracks per-finding lifecycle (`open|fixed|wontfix|stale|snoozed`) across runs and lets verification skip findings that are provably unchanged. If `state.json` is absent, treat as empty and continue.

Lifecycle interactions with the steps below:
- Step 2.5a (dedupe): drop any candidate whose `state.json` status is `wontfix` (with matching `code_hash`) or `snoozed` (with future `snoozed_until`) before sending to a verifier.
- Step 2.5b (verify): if a candidate's stored `status == open` AND `code_hash` matches current code AND `last_seen_sha == HEAD` AND stored `verifier_version` matches the current persona version (see `verifier.md` frontmatter `version` field), reuse the prior verdict and skip the verifier. Count and log: `reused state for <N> findings`. A `verifier_version` bump (e.g., the hostile-stance change) invalidates all prior verdicts — every finding re-verified next run.
- After Step 2.5b: update the file per the lifecycle rules in `state-file.md` (insert new, refresh existing, sweep missing into `fixed`/`stale`). Write atomically.

## Step 2.5a — Dedupe (cheap, before verify)

Collect all findings from Phase 2 agents into a single JSON array, then pipe through the bundled script:

```bash
echo "$ALL_FINDINGS_JSON" | python3 scripts/dedupe.py \
  --suggested-cap "${suggestedGlobalCap:-10}" --question-cap "${questionGlobalCap:-8}"
```

Pass `--suggested-cap` / `--question-cap` from the `suggestedGlobalCap` / `questionGlobalCap` config keys (`config-keys.md`). Omit flags to use defaults. A cap of `0` disables that cap — keep every survivor of that tier.

The script groups by `root_cause_key`, picks the most evidence-rich finding as primary, annotates each kept finding with `confirmed_by` (other agents that raised the same key), and applies the global caps below. Output is `{"kept": [...], "dropped_global_cap": [ids]}`.

**Global caps the script enforces** (prevents the report drowning in noise — with 10 agents the per-agent quotas alone allow up to 30 SUGGESTED + 20 QUESTION):
- Keep at most `suggestedGlobalCap` (default 10) SUGGESTED findings globally, ranked by `confirmed_by` count then evidence richness. `0` = no cap.
- Keep at most `questionGlobalCap` (default 8) QUESTION findings globally (same ranking). `0` = no cap.
- CRITICAL / IMPORTANT / DEBT have no global cap — never drop a real bug for noise reasons.

Build per-agent verification batches from `kept` (group by original `source_agent` field).

## Step 2.5b — Batch Verification

Persona: `verifier.md`. Spawn ONE verifier per source agent, IN PARALLEL — each verifies that agent's full finding list at once. ~5× cheaper than per-finding verifiers.

**Model tier**: verifier agents spawned at the `verifierModel` config tier (default `haiku`; see `config-keys.md`). Verification is a constrained re-read with JSON-schema output — Haiku handles it cleanly while cutting verifier token cost by 60–70% vs the source-agent tier. Override to `sonnet`/`opus` if you observe verifier mis-scoring on a given codebase, or `inherit` to pin to the parent session's tier.

Each verifier receives: source agent's findings, the **diff hunks and source for the files its findings reference** (not the whole diff or all source files), Project Profile, CLAUDE.md rules, and the cross-agent confirmation map (to apply the +10 cross-confirmation bonus). Scoping the input to the findings' files — instead of pre-loading the entire diff once per source agent — is the main verifier token saving and costs no precision: the verifier is already instructed to re-read the cited `file:line` itself (step 1), and uses `Read`/`Grep` on demand for the occasional cross-file check ("pattern in 5+ files", "handled by a caller elsewhere"). Snoozed/`wontfix` findings already filtered in Step 2.5.0 — verifier never sees them.

## Step 2.5b-vote — Majority-vote re-verification (top severity only)

Skip this step entirely when `verifierVotes` (config-keys.md, default `1`) is `1` — the single Step 2.5b pass is final. When `verifierVotes > 1`, the first pass is not final for 🔴/🟠 findings; a single hostile verifier can mis-score a genuinely novel top-severity finding (the skill's documented weak spot), so re-verify those independently and decide by majority.

1. **Collect high-severity survivors.** Take every finding the first pass scored `keep` or `appendix` at **🔴 CRITICAL or 🟠 IMPORTANT** (after the cross-confirmation bonus). DEBT / SUGGESTED / QUESTION are never re-voted — they are capped already and the extra cost is not justified. Findings tagged `VERIFIED` from Phase 1 gates skip voting (the tool is the proof — same fast path as single-pass).
2. **Spawn the extra votes.** Re-batch those high-severity survivors **by source agent** and spawn `verifierVotes − 1` additional `verifier.md` instances per affected source agent — one extra batch per source-agent-with-high-sev per extra vote, NOT one verifier per finding. Each extra verifier is a fresh instance with the same scoped inputs as the first pass and **no shared context** with the first pass or the other extra votes — independence is the whole point of voting.
3. **Decide by majority** across the `verifierVotes` independent verdicts each finding now has (the original Step 2.5b verdict + the extra passes):
   - **keep** (main report) iff ⌈`verifierVotes` / 2⌉ or more passes returned `keep`.
   - else if a majority returned `keep` or `appendix` (i.e. not `drop`) → **appendix**.
   - else → **drop**.
   - Recorded score = **median** of the per-pass scores (stable against a single outlier pass).
   - Even `verifierVotes` with no strict keep-majority (a tie) → demote to appendix; a tie never keeps top severity. Odd N avoids ties — recommended.
4. **Completion gate still applies.** The extra-vote verifiers are spawned verifiers — Phase 2.75 requires each to return valid JSON, retries once, else surfaces `⚠️ PARTIAL REVIEW`. A high-severity finding whose extra votes did not all return is decided on the votes that did return (never silently dropped).

Cost: voting multiplies only the high-severity batch-verifier calls, and only when `verifierVotes > 1`. A review with zero 🔴/🟠 survivors costs exactly the single-pass amount regardless of the setting.

## Threshold

- Score ≥ 75 → main report (`keep`)
- Score 50–74 → "Potential Issues" appendix (`appendix`)
- Score < 50 → silently dropped (`drop`)

When `verifierVotes > 1`, the threshold above sets each individual verifier's verdict; the final keep/appendix/drop for a 🔴/🟠 finding is the majority decision from Step 2.5b-vote, not a single pass's score.

Findings tagged `confidence: VERIFIED` from Phase 1 gates skip verification entirely (auto-keep at 90).

## History persistence

Append each kept/appendix finding to `historyFile` (default `.claude/review-all/history.jsonl`):
```json
{"timestamp": "<iso>", "target": "<resolved>", "root_cause_key": "...", "severity": "...", "file_line": "...", "score": 90}
```
Before reporting, scan history for the same `root_cause_key` appearing in 3+ recent reviews → escalate severity by one tier (DEBT → IMPORTANT, etc.) and annotate "recurring".

## State.json lifecycle sweep

After verification, hand lifecycle bookkeeping to the bundled script:

```bash
# seen-keys.json = JSON array of root_cause_keys kept + appendix this run
# changed-keys.json (optional) = JSON array of keys whose underlying code hash changed
STATE_SWEEP_CHANGED_KEYS=changed-keys.json \
  python3 scripts/state-sweep.py .claude/review-all/state.json "$HEAD_SHA" seen-keys.json
```

The script applies the transitions documented in `state-file.md`: `snoozed → open` (expired), `open → fixed` (code changed AND not re-seen), `open → stale` (`miss_count >= 2` or >30 days unseen), `wontfix → open` (code changed), and `fixed/stale → open` (key re-surfaces this run = regression). It writes the file atomically and prints a one-line summary.

The script sweeps **existing** entries only. The orchestrator still inserts entries for newly-seen `root_cause_key`s and refreshes each entry's `code_hash`/severity/`file_line` (`state-file.md` step 3) — the script is not handed that per-finding metadata. Run the script for the sweep; do step-3 insertion/refresh in the orchestrator.
