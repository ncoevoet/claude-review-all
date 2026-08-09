# Gate Mode — headless pass/fail (no report, no menu)

Loaded by `/review-all` when the target resolves to **gate mode** (Step 0.1: `$ARGUMENTS` begins with `gate`, or the `--ci` flag is present). Gate mode makes review-all consumable by a CI step or an autonomous loop (e.g. the `goal-loop` plugin's oracle): it runs the full review machinery but replaces the human-facing Phase 3 report + Phase 4 menu with a single machine-readable verdict and an exit code.

**The contract in one line:** run Phases 0–2.75 unchanged, then emit `gate-verdict.json` and terminate. **Never** call `AskUserQuestion`. **Never** present the Phase 4 menu. **Never** print the prose report.

## Why a separate mode

Normal `/review-all` is interactive by design — Phase 4's menu is a *mandatory* gate (SKILL.md), and the skill treats ending the turn without it as a silent failure. An autonomous caller cannot answer a menu, and a loop needs a `{pass, blocking[]}` decision, not prose. Gate mode is the headless contract: same finding quality (same agents, same hostile verifier), different terminal step.

## Flow

1. **Phases 0.0 → 2.75 run exactly as in a normal review.** Discovery, deterministic gates (Phase 1), optional runtime probe (1.5), parallel heuristic agents (Phase 2), dedupe + batch verification (Phase 2.5), and the completion gate (Phase 2.75). No behavioural change — gate mode reuses all of it. Honor every config key (`verifierModel`, `skipAgents`, timeouts, etc.).
2. **Resolve the severity floor.** `--severity <floor>` argument if given, else config key `gateSeverityFloor` (default `critical`). See `config-keys.md`.
3. **Assemble the gateable finding set.** Take only the **main-report KEPT findings** — verdict `keep` AND Phase 2.5 score ≥ 75. **Exclude the appendix** (score 50–74): a borderline, lower-confidence guess must never block a loop. **Exclude every `unverified` finding regardless of its score**: the verdict marks a runtime/data/rendering claim that nobody observed (`verifier.md` → *The `unverified` verdict*), and a score does not promote it out of that bucket. Gate mode is a blocking oracle — an unobserved claim cannot carry that weight, and it is reported to humans in the 🔬 section instead. Each finding is reduced to the export shape:
   `{ "id", "severity", "file", "line", "root_cause_key", "title", "confidence" }`
   (this is exactly what `scripts/export-findings.py` `normalize()` accepts, and what `gate-verdict.py` consumes).
4. **Determine partial coverage.** If Phase 2.75 surfaced a `⚠️ PARTIAL REVIEW` (an agent or verifier never returned cleanly after its one retry), the review could not fully run. Pass `--partial` so the verdict **fails closed** — "couldn't verify" is treated as "not done", never as a green gate.
5. **Emit the verdict.** Pipe the assembled findings array to:
   ```bash
   echo "$KEPT_FINDINGS_JSON" | python3 scripts/gate-verdict.py \
     --severity "${gateSeverityFloor:-critical}" \
     --out "${gateVerdictFile:-.claude/review-all/gate-verdict.json}" \
     --reviewed-sha "$HEAD_SHA" \
     ${PARTIAL:+--partial}
   ```
   The script writes `gate-verdict.json`, prints the same JSON to stdout, and **exits 0 (pass) or 1 (blocked) or 2 (malformed)**. A finding blocks when its severity rank ≥ the floor's (`critical` → 🔴 only; `important` → 🔴+🟠; …).
6. **Terminate.** Print one human-readable summary line, then stop the turn:
   - pass → `✅ review-all gate: PASS (floor=<floor>, 0 blocking, <N> findings reviewed)`
   - blocked → `⛔ review-all gate: BLOCKED (floor=<floor>, <K> blocking) — see <gateVerdictFile>`
   - partial → `⛔ review-all gate: BLOCKED (partial coverage — review did not fully run)`

   Do **not** open any menu, ask any question, or apply any fix. The caller (CI / loop) reads the exit code + `gate-verdict.json` and decides what to do.

## REVIEW.md in gate mode

Gate mode runs Phases 0–2.75 unchanged, so a repo's `REVIEW.md` (SKILL.md Step 0.5) is honored headlessly exactly as in an interactive review. This is the supported way to raise the CI bar per repository or per path — a `REVIEW.md` line promoting a class of finding to 🔴 makes it blocking under the default `critical` floor, without touching any config.

**The same lever cuts both ways: a demotion can move a real defect below the floor and turn a blocked gate green.** That is the same trust model as `CLAUDE.md` — text committed to the repo is authoritative — but it has a sharper consequence here, because nobody reads a gate's reasoning. Two limits keep it bounded:

- `REVIEW.md` may recalibrate a finding's severity; it may **not** override the gate mechanism itself. The floor resolution (`--severity` / `gateSeverityFloor`), the ≥ 75 keep threshold, the appendix and `unverified` exclusions, and the fail-closed partial rule are not addressable from `REVIEW.md`.
- **When `REVIEW.md` is itself modified in the reviewed diff, say so in the terminal summary line** — append `(REVIEW.md modified in this diff)`. A change to the rules that grade a diff, arriving inside that same diff, is exactly the shape of a self-approving PR; the gate does not block on it, but it must never pass silently either.

## State & history

Gate mode still runs Phase 2.5's `state.json` lifecycle sweep and appends to `history.jsonl` (it is a real review). Idempotent re-runs on the same SHA reuse prior verdicts via the normal state-reuse fast path. This means a loop that re-invokes the gate on an unchanged tree pays near-zero verifier cost.

## Verdict shape

```json
{
  "tool": "review-all", "mode": "gate",
  "generated_at": "<iso>", "severityFloor": "critical",
  "reviewedSha": "<sha>", "partial": false,
  "pass": false, "blockingCount": 1,
  "blocking": [
    {"id": "F3", "severity": "CRITICAL", "confidence": 85,
     "file": "src/x.ts", "line": 42, "title": "unguarded null deref"}
  ],
  "summary": {"critical": 1, "important": 0, "debt": 2, "suggested": 0, "question": 0}
}
```

`summary` counts all kept findings by tier (context); `blocking` lists only those at/above the floor. `pass` is `false` whenever `blockingCount > 0` **or** `partial` is `true`.

## What gate mode must NOT do

- No `AskUserQuestion` — anywhere in the gate path.
- No Phase 3 prose report, no Phase 4 menu, no fix application, no ticket/PR writes.
- No blocking on appendix (50–74) or ⚪ QUESTION findings (QUESTION rank is below every normal floor).
- No blocking on an `unverified` finding, whatever it scored — the claim has no observation behind it.
- No silent pass on partial coverage — `--partial` forces a fail.
