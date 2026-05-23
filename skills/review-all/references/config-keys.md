# Config Keys — `.claude/review-all.json`

Per-key reference for the review-all config. All keys are optional; defaults below apply when a key is absent.

Each default carries a **Why** rationale — Ousterhout's law: no voodoo constants.

## Keys

| Key | Type | Default | Meaning | Why this default |
|-----|------|---------|---------|------------------|
| `devServerPorts` | `number[]` | `[4200, 5173, 3000, 8080]` | Ports probed by Phase 0 dev-server detection. If any is open AND matches the detected framework's typical port, build gate is skipped. | Covers the four highest-share JS frameworks (Angular `4200`, Vite `5173`, Next.js `3000`, generic dev `8080`). Rarer ports hurt probe latency more than they help. |
| `extraAgents` | `string[]` | `[]` | Additional agent IDs spawned in Phase 2 beyond the auto-selected set. Each must match a file under `agents/`. | Empty default; user opts in to extra coverage. |
| `skipAgents` | `string[]` | `[]` | Agent IDs suppressed in Phase 2 even when auto-selection includes them. | Empty default; user opts out per project. |
| `outputDir` | `string` | `.claude/reports` | Where Phase 4 writes report files when user picks "Save report". | Co-located with other Claude artifacts; gitignored by convention. |
| `snoozeFile` | `string` | `.claude/review-all/snooze.json` | **Deprecated**. Legacy snooze store. Read once for migration into `state.json` (see `state-file.md`), then ignored. New runs read snooze status from `state.json`. Removed in a future revision. | Kept for backward compat through one migration cycle. |
| `historyFile` | `string` | `.claude/review-all/history.jsonl` | Append-only audit log of kept/appendix findings. Drives recurrence-escalation rule in Phase 2.5. | JSONL keeps appends atomic and grep-able. |
| `stateFile` | `string` | `.claude/review-all/state.json` | Per-finding lifecycle store (`open\|fixed\|wontfix\|stale\|snoozed`). Schema and rules in `state-file.md`. | Single file rewritten atomically; small enough that whole-file rewrites stay fast. |
| `agentTimeoutSeconds` | `number` | `600` | Wall-clock budget per Phase 2 agent. Exceeded → one retry, then surface as PARTIAL REVIEW in Phase 2.75. | 10 min covers thorough re-read of a 200K-byte slice on slowest model tier with token-throttling headroom; budgets below 300s caused observed false-timeouts on large repos. |
| `verifierTimeoutSeconds` | `number` | `300` | Wall-clock budget per Phase 2.5 verifier (batch verifier per source agent). | Verifier produces bounded JSON output, so half the source-agent budget suffices; cap exists to break runaway batches. |
| `verifierModel` | `string` | `"haiku"` | Model tier for verifier batch agents. Choices: `"haiku"`, `"sonnet"`, `"opus"`, `"inherit"`. Source agents always inherit parent session's tier. | Verifier task is constrained re-read with JSON-schema output — Haiku is fast and cheap. Bump to `sonnet`/`opus` if verifier mis-scoring appears. Estimated 60–70% verifier-token reduction vs `inherit` on most runs. |
| `chunkMaxFiles` | `number` | `40` | Phase 2 slice threshold — slices over this file count are chunked. `0` disables. | 40 files keeps each chunk under ~50K bytes of pure diff for typical repos, leaving agent ~150K tokens of headroom for source-file re-reads. Set lower on very large per-file diffs. |
| `chunkMaxBytes` | `number` | `200000` | Phase 2 slice threshold — slices over this byte size are chunked. `0` disables. | ~200K characters ≈ 50K tokens of diff text — comfortably under any current model context window with room for persona, project profile, and response. |
| `runtimeProbe` | `"auto" \| "off" \| "force"` | `"auto"` | Phase 1.5 mode. `auto` runs only with UI diffs + open dev server. `force` runs Step 1 without requiring UI files in diff (curl still required — see Notes). `off` disables. | `auto` is the least surprising default — never probes when nothing UI changed. |
| `runtimeRoutes` | `string[]` | `[]` | Explicit Phase 1.5 route list. When non-empty, overrides route discovery from changed files. | Empty default; route discovery from changed files is usually correct. |
| `visualDiffThresholdPct` | `number` | `1.0` | Percent of differing pixels in Phase 1.5 visual diff that triggers a 🔵 SUGGESTED finding. | 1% absorbs anti-aliasing and font-hinting noise across headless renders; below 0.5% produces constant false positives. |
| `scopePromptCommits` | `number` | `20` | Commits-ahead threshold above which empty-args resolution triggers the large-range scope prompt (SKILL.md Step 0.1). `0` disables the commit-count branch of the trigger. | 20 commits is roughly a week of sustained work on most teams; below this, the merge-base diff is usually still the user's intended scope. |
| `scopePromptFiles` | `number` | `200` | Files-changed threshold above which empty-args resolution triggers the large-range scope prompt (SKILL.md Step 0.1). `0` disables the files-changed branch of the trigger. | 200 files matches chunkMaxFiles × ~5-chunk practical upper bound — beyond that the user almost always wants to narrow scope before paying the spawn cost. |
| `suggestedGlobalCap` | `number` | `10` | Phase 2.5 Step 2.5a global cap on 🔵 SUGGESTED findings after dedupe (ranked by `confirmed_by` then evidence). `0` = no cap (keep every survivor). | 10 keeps a verified diff readable; raise (or `0`) when user wants the complete list and accepts a longer report. 🔴/🟠/🟡 are never capped. |
| `questionGlobalCap` | `number` | `8` | Phase 2.5 Step 2.5a global cap on ⚪ QUESTION findings after dedupe (same ranking). `0` = no cap. | Same rationale as `suggestedGlobalCap`; QUESTION is the noisiest tier so the default sits slightly lower. |
| `quotaDebt` | `number` | `5` | Per-agent cap on 🟡 DEBT findings. Substituted into `${quota.debt}` in `_shared.md` before each Phase 2 agent spawns. `0` = no per-agent limit. | 5/agent keeps any one persona from flooding the report; raise (or `0`) for exhaustive debt inventory. Agents drop excess silently *before* dedupe, so this is the real ceiling — global caps cannot recover what a quota dropped. |
| `quotaSuggested` | `number` | `3` | Per-agent cap on 🔵 SUGGESTED findings (`${quota.suggested}`). `0` = no per-agent limit. | Pair with `suggestedGlobalCap` for a complete suggestion list — both must be raised/zeroed. |
| `quotaQuestion` | `number` | `2` | Per-agent cap on ⚪ QUESTION findings (`${quota.question}`). `0` = no per-agent limit. | Pair with `questionGlobalCap` for a complete question list. |

## Other defaults documented elsewhere

- `state-file.md` — `miss_count >= 2 → stale`. Why: two consecutive misses without code change rules out single-run flakiness while keeping lifecycle short.
- `state-file.md` — `last_seen_at > 30 days → stale` (open only). Why: bounds lifetime of findings suppressed by `skipAgents` or one-off filter changes.
- `state-file.md` — `code_hash` window = ±3 lines around flagged lines. Why: large enough to survive whitespace-only edits elsewhere in the file, small enough to detect real edits at the flagged location.
- `phase-2.5-verification.md` — main-report threshold `score ≥ 75`, appendix `50–74`, drop `< 50`. Why: 75 matches verifier's "strong, verified" anchor; 50 is "moderate" — keeps borderline cases visible without polluting main report.
- `phase-2.5-verification.md` — recurrence escalation when same `root_cause_key` appears in 3+ history entries. Why: two repeats can be noise; three signals a stable pattern worth tier-bumping.

## Notes

- Keys not listed above are ignored. Forward-compatible: future keys can be added without breaking old configs.
- Treat `snoozeFile` as read-only legacy. After the migration cycle described in `state-file.md`, the file is deleted and the key has no effect.
- `runtimeProbe: "force"` still requires `curl` (see Phase 0.0 preflight). If `curl` absent, phase still skips.
- `verifierModel: "inherit"` is the escape hatch — pins verifier to the same tier as parent session when verifier quality regressions appear on a given codebase.
