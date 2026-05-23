# Init Wizard — `/review-all init`

Loaded by `/review-all` when `$ARGUMENTS == "init"`. Replaces review flow with interactive setup that writes a populated `.claude/review-all.json`.

## When to run

User explicitly invoked `/review-all init`. Do NOT auto-trigger from a missing config — silent defaults must keep working.

## Pre-checks

1. If `.claude/review-all.json` already exists → ask via `AskUserQuestion` whether to overwrite, merge, or cancel.
2. Run Phase 0.0 preflight first (so wizard knows which optional tools are available; mention any missing ones in the summary at end).
3. Run Phase 0.3 (language/framework detection) — needed to suggest sensible defaults.

## Questions (via `AskUserQuestion`, one at a time)

Each question must have ≤4 options; user can always pick "Other" for a custom value.

| # | Header | Question | Options | Maps to |
|---|--------|----------|---------|---------|
| 1 | Dev ports | Which dev-server ports should the build gate watch? | Framework default (e.g. `[4200]` for Angular, `[5173]` for Vite, `[3000]` for Next), Common web set `[3000,4200,5173,8080]`, None (always run build) | `devServerPorts` |
| 2 | Output dir | Where should review reports be written? | `.claude/reports` (default), `docs/reviews`, `tmp/reviews` | `outputDir` |
| 3 | Agent set | Which agent set to run? | All (default), Skip a11y/i18n (non-UI repo), Skip performance (small codebase), Custom (free-text comma list) | `skipAgents` |
| 4 | Runtime probe | Run visual/runtime probe when dev-server is up? | Auto (only with UI diffs, default), Off, Force (always) | `runtimeProbe` |
| 5 | Chunking | Default chunk thresholds for big diffs? | Defaults `40 files / 200KB`, Aggressive `20 files / 100KB`, Disabled | `chunkMaxFiles`, `chunkMaxBytes` |

Skip a question if it doesn't apply. Specifically:
- Skip Q4 only when `curl` is unavailable (no curl → Phase 1.5 self-skips regardless; asking is pointless). Do NOT skip Q4 when only Playwright/Puppeteer is missing — Step 1 (health probe) still runs.
- A skipped question records nothing. The "only explicit keys" rule below applies — omitted keys inherit documented defaults.

## Write

Build the config object — only include keys the user explicitly chose; rely on documented defaults for the rest (keeps file small and forward-compatible).

Write atomically to `.claude/review-all.json` after creating parent dir.

Also write `.claude/review-all.json.example` — a fully-populated, plain-JSON copy of the schema with every key set to its documented default. Per-key commentary lives in `references/config-keys.md`, not inline in JSON (keeps example parseable by stock tooling).

## Summary

After write, print:

```
review-all configured.
  Config:   .claude/review-all.json
  Example:  .claude/review-all.json.example
  Preflight: <tool>=ok, <tool>=missing(impact)
Next: run `/review-all` on a dirty tree or `/review-all PR #N`.
```

Exit cleanly. Do NOT chain into a review — user asked to init, not to review.
