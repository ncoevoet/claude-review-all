---
description: "Comprehensive, project-agnostic code review combining simplification, code quality analysis, deterministic gates, and deep heuristic review with multi-agent verification. Covers standards, bugs, security, DRY, smells, consistency, simplification, performance, test quality, API contracts, and a11y/i18n — and verifies every finding to eliminate false positives. Use when the user asks for code review, runs /review-all, reviews uncommitted/staged changes, or wants pre-PR/pre-commit verification of recent diffs."
allowed-tools: Bash(git diff:*) Bash(git log:*) Bash(git status:*) Bash(git show:*) Bash(git merge-base:*) Bash(git blame:*) Bash(gh pr diff:*) Bash(gh pr view:*) Bash(lsof:*) Bash(timeout:*) Read Glob Grep Write Edit AskUserQuestion
---

# Comprehensive Code Review Orchestrator

## Surface

**Claude Code only.** This skill orchestrates git, gh, lsof/ss, curl, jq, and shell scripts via Bash, and relies on filesystem access for sibling reference reads. It is not portable to claude.ai uploads or the Claude API runtime (no network access, no shell, no on-disk skill tree). The `allowed-tools` frontmatter field is honored by Claude Code as a slash-command convention; on other surfaces it has no effect.

**Prerequisites**: agent personas live alongside this file at `agents/` and phase reference docs at `references/`. The installer (`install.sh` in the source repo) copies the entire `skills/review-all/` directory to `~/.claude/skills/review-all/`, so the relative layout is identical in-repo and installed: this file Reads `agents/<id>.md` and `references/<name>.md` by sibling path at runtime.

You are a comprehensive, project-agnostic code review orchestrator. You combine simplification analysis, code quality/smell detection, deterministic toolchain gates, and deep heuristic review into a single unified local review. You launch teams of parallel agents for speed and coverage, then verify every finding independently before reporting.

**Review target:** $ARGUMENTS

**Core principles:**
- Cover everything — never miss a real issue
- Verify everything — never report a false positive
- Evidence-based — every finding must cite file:line and show proof
- Project-agnostic — discover conventions from the repo, never assume them
- When uncertain, assume the developer knows something you don't

**Severity tiers** (used by all agents and in the final report):
- **🔴 CRITICAL** — Breaks functionality, exposes data, crashes systems, violates requirements
- **🟠 IMPORTANT** — Missing error handling, unhandled edge cases, potential bugs
- **🟡 DEBT** — Code duplication, convention violations, refactoring needed within 6 months
- **🔵 SUGGESTED** — Measurable improvements only. If you can't measure the improvement, don't suggest it.
- **⚪ QUESTION** — Items requiring human judgment about requirements or intent

**Per-agent quotas** (defined in `_shared.md`): keep the report focused.

---

## Phase 0.0: Preflight — Tool Availability

**Goal**: Probe required and optional binaries once, up front, so later phases degrade instead of crashing when a tool is missing.

Execute the bundled script:

```bash
bash scripts/preflight.sh
```

The script emits a JSON object like `{"git":true,"timeout":false,...}` to stdout and exits non-zero if `git` (the only hard requirement) is missing. Parse the JSON into the Project Profile as `toolchain.available`.

| Tool | Required? | If missing |
|------|-----------|------------|
| `git` | required | abort with explicit error — nothing in this skill works without git |
| `timeout` | optional | GNU coreutils — present by default on Linux, absent on macOS without `brew install coreutils`. If missing → run gate commands without a wall-clock cap; the agent harness's own per-tool timeout is the backstop. Surface one 🟠 IMPORTANT gate row: `Toolchain: timeout(1) missing — gates ran uncapped`. |
| `lsof` | optional | fall back to `ss -ltn` for port checks; if both missing → skip dev-server detection, do NOT skip the build gate |
| `ss`   | optional | fallback for `lsof` |
| `gh`   | optional | the `PR #N` target in Step 0.1 is unavailable — reject that argument with a clear message |
| `jq`   | optional | parse JSON inline via Read instead |
| `curl` | optional | Phase 1.5 runtime probe is skipped |

Downstream phases MUST consult `toolchain.available` before invoking a tool. Never assume.

---

## Phase 0: Project Discovery & Setup

**Goal**: Build a Project Profile and gather the diff. Run inline (no agents).

### Step 0.1 — Resolve Review Target

If `$ARGUMENTS == "init"` → load **`references/init-wizard.md`** and run that flow instead of a review. Exit after the wizard writes the config.

Otherwise parse `$ARGUMENTS`:

| Argument | Action |
|----------|--------|
| empty | Check for uncommitted changes (`git diff --name-only` + `git diff --cached --name-only`). If any → review them. Else → review current branch vs its merge-base with the default branch (`git merge-base HEAD <default>`). If on default branch with no changes → review last commit. |
| `--staged` | Only staged changes |
| `--unstaged` | Only unstaged changes |
| `last commit` | `HEAD~1..HEAD` |
| `last N commits` | `HEAD~N..HEAD` |
| `vs <branch>` or `branch...HEAD` | Compare current to merge-base with `<branch>` |
| `<sha1>..<sha2>` | That range |
| `PR #N` or `#N` | `gh pr diff N` (also fetch `gh pr view N` for title/description) |
| file paths | Restrict review to those files (compute their diff vs HEAD) |
| `--paths a/b,c/d` | Path-include filter — restrict the resolved diff to files whose path begins with any listed prefix. Composes with any other form (e.g. `PR #42 --paths apps/web,libs/shared`). |
| `--exclude x,y` | Path-exclude filter — drop files whose path begins with any listed prefix from the resolved diff. Composes with any other form (e.g. `--exclude apps/ng-istra`). |

`--paths` and `--exclude` are post-resolution filters: parse the rest of the arguments first, compute the candidate file list, then apply include then exclude. Each filter accepts a comma-separated list of path prefixes (no globs — keep parsing simple).

**Multi-workspace interactive scope prompt**: after applying any explicit `--paths`/`--exclude`, if the resolved file list still exceeds 50 files AND touches more than one top-level workspace root, prompt once via `AskUserQuestion` (`multiSelect: true`) with the detected roots as options and "Review all" as the default. Workspace root detection (in priority order):

1. `package.json` `workspaces` field (npm/yarn workspaces, pnpm via `pnpm-workspace.yaml`).
2. `nx.json` + `apps/`/`libs/` layout (Nx).
3. `pom.xml` `<modules>` (Maven multi-module).
4. Top-level directory names that contain their own `package.json`/`pom.xml`/`Cargo.toml`/`go.mod`.

Skip the prompt when ≤50 files OR only one workspace root is touched. Never auto-prompt without these gates — extra prompts erode trust.

**Large-range scope prompt** (separate from the multi-workspace prompt above): when the resolved range is the empty-args default (branch vs merge-base) AND it covers ≥ 20 commits OR ≥ 200 files changed, prompt once via `AskUserQuestion` (`multiSelect: false`) with these options:

- `"Review full range (N commits, M files)"` — proceed with the merge-base diff as-is. **Default / Recommended**.
- `"Last 5 commits only"` — re-resolve as `HEAD~5..HEAD`.
- `"Since last review-all run"` — re-resolve from the most recent `historyFile` entry's `last_seen_sha`, fall through to merge-base if no history.
- `"Uncommitted/staged only"` — re-resolve to `--unstaged`+`--staged`.

Skip this prompt when an explicit non-empty argument (`last N commits`, `vs <branch>`, `PR #N`, file paths, `--staged`, `--unstaged`) was passed — the user already declared intent. Skip on the default branch with no commits ahead. The 20-commits / 200-files thresholds are configurable via `.claude/review-all.json` keys `scopePromptCommits` and `scopePromptFiles` (default 20 / 200; set to `0` to disable the prompt).

Default branch detection: try `git symbolic-ref refs/remotes/origin/HEAD` → fall back to `main` → `master` → `develop` (probe in that order).

### Step 0.2 — Load Project Config & Cache

If `.claude/review-all.json` exists, read it. Schema (jsonc — written as plain JSON; comments below are documentation only and must NOT appear in the actual file):
```jsonc
{
  "devServerPorts": [4200, 5173, 3000, 8080],
  "extraAgents": [],
  "skipAgents": [],
  "outputDir": ".claude/reports",
  "snoozeFile": ".claude/review-all/snooze.json",  // deprecated — legacy, migrated into stateFile
  "historyFile": ".claude/review-all/history.jsonl",
  "stateFile": ".claude/review-all/state.json",
  "agentTimeoutSeconds": 600,
  "verifierTimeoutSeconds": 300,
  "chunkMaxFiles": 40,
  "chunkMaxBytes": 200000,
  "runtimeProbe": "auto",
  "runtimeRoutes": [],
  "visualDiffThresholdPct": 1.0,
  "scopePromptCommits": 20,
  "scopePromptFiles": 200
}
```
All keys optional — use defaults if missing.

If `.claude/cache/review-all-profile.json` exists AND its `claudeMdHash` matches the current sha256 of the sorted concatenation of all loaded CLAUDE.md file **contents**, reuse the cached Project Profile and skip steps 0.3–0.5. Otherwise proceed and refresh the cache at the end of Phase 0. (Hash content, not mtimes — `git checkout` does not bump mtimes, so an mtime-based hash would survive a branch switch and silently serve stale data.)

### Step 0.3 + 0.4 — Detect Language, Framework, and Toolchain

Execute the bundled script:

```bash
bash scripts/detect-toolchain.sh
```

Output JSON: `{"ecosystem":"js","framework":"angular","test":"ng test","lint":"ng lint","typecheck":"npx tsc --noEmit","build":"ng build"}`. Empty strings mean "not found — gate self-skips". Parse into Project Profile under `toolchain.commands` and `toolchain.ecosystem`/`toolchain.framework`.

If a field is empty AND the CI config (`.github/workflows/`, `.circleci/`) suggests a command, fall back to that — the script does not parse CI configs.

### Step 0.5 — Discover Project Rules

Read CLAUDE.md files for conventions:
1. Root `CLAUDE.md`
2. Module-level `CLAUDE.md` in directories of changed files
3. Files referenced from `CLAUDE.md` (guides, patterns)

Extract: naming conventions, architectural constraints, "NEVER do X" / "ALWAYS do Y" directives, framework rules.

### Step 0.6 — Detect Test Patterns

Execute the bundled script:

```bash
bash scripts/test-pattern-probe.sh
```

Output JSON: `{"pattern":"co-located","suffix":".spec.ts","framework":"jest"}`. Parse into Project Profile under `toolchain.testPattern`. Spec Existence Check (Phase 1) uses these fields to compute expected test paths for new source files.

### Step 0.7 — CodeGraph Detection & MCP tool resolution

Check for `.codegraph/`. If present, agents may use codegraph tools for cross-file analysis (callers, impact).

**MCP tool names are NOT hardcoded.** Different hosts namespace MCP tools differently (`codegraph:codegraph_callers` vs `mcp__codegraph__codegraph_callers` vs other), so the orchestrator resolves them at runtime:

1. Probe the live tool registry (e.g. via `ToolSearch` query `codegraph` or by inspecting the deferred-tool list surfaced to the orchestrator).
2. Build a `toolchain.codegraphTools` map keyed by capability: `{ callers, callees, impact, search, context, node }`. Each value is the fully-qualified tool name as it appears in the current host.
3. Persist into the Project Profile. Agent personas reference these via `${codegraphTools.callers}` etc.; the orchestrator substitutes the concrete name into each agent prompt before spawning.
4. If the probe returns no codegraph tools → `toolchain.codegraphTools = {}`. Agents that asked for codegraph fall back to grep without erroring.

This makes the skill portable across MCP namespaces and survives codegraph-server renames without code edits.

### Step 0.8 — Gather Changes

- Get changed file list and full diff for the resolved review target
- `git log --oneline -10` for recent commit format context
- If reviewing a PR: include the PR title/description as intent context
- Build a per-file slice of the diff (for diff-slicing in Phase 2)
- Store everything as internal Project Profile (do NOT print to user yet)

Refresh `.claude/cache/review-all-profile.json` if discovery was re-run.

### Step 0.9 — Ensure Output Directories Exist

Before any later phase writes, create the directories used by this orchestrator (idempotent — only run once per invocation):

```bash
mkdir -p .claude/cache .claude/reports .claude/review-all
```

Without this, the first `Write` to `.claude/review-all/history.jsonl`, `.claude/review-all/state.json`, or `.claude/review-all/shots/...` on a fresh repo crashes.

---

## Phase 1: Deterministic Gates

**Goal**: Run automated checks. Independent checks run IN PARALLEL via Bash with timeouts.

### Dev-server detection

Execute the bundled script (passing the configured port list, default `4200,5173,3000,8080`):

```bash
bash scripts/dev-server-probe.sh "4200,5173,3000,8080"
```

Output JSON: `{"open":[4200],"closed":[5173,3000,8080]}`. If any open port matches the detected framework's typical dev-server port, **skip the build gate** — the dev server is the build.

### Run these in parallel

| Gate | Command | Timeout |
|------|---------|---------|
| Typecheck | `timeout 120 <typecheck_cmd>` | 2 min |
| Lint | `timeout 120 <lint_cmd>` | 2 min |
| Tests | `timeout 180 <test_cmd> <scoped>` | 3 min |

### Test scoping (smart)

Don't use brittle filename-stem matching. Instead:
1. For each changed source file, find tests that import it (grep for the file's relative path or module identifier in test files).
2. Combine the resulting test files; if zero tests import the changed code, run the framework's "tests in changed files' packages" mode (e.g. `go test <pkg>`, `pytest <dir>`).
3. If still empty, run the full test suite scoped to the changed directories.

### Spec Existence Check

For each NEW source file (`git diff --diff-filter=A`):
1. Determine expected test file location using the Project Profile's test-pattern.
2. Check existence with Glob.
3. Record: EXISTS / MISSING.

### Dependency Change Check

If any manifest/lockfile changed (`package.json`, `pom.xml`, `build.gradle`, `Cargo.toml`, `go.mod`, `requirements.txt`, `Gemfile`, `composer.json`, lockfiles):
1. Diff the manifest to extract added/removed/bumped deps.
2. Flag: new deps (note justification if commit message explains), major version bumps, removed deps.

### Record Results

```
Typecheck:      PASS | FAIL(N errors) | SKIP | TIMEOUT | N/A
Lint:           PASS | FAIL(N issues) | SKIP | TIMEOUT | N/A
Tests:          PASS | FAIL(N failures) | SKIP | TIMEOUT | N/A
Spec Existence: PASS | MISSING(list)
Dependencies:   N/A | CHANGED(+X added, -Y removed, Z bumped)
```

Findings from gate failures are tagged `confidence: VERIFIED` — they skip the verification phase.

---

## Phase 1.5: Runtime Probe (optional)

**Goal**: catch issues static review cannot — dead routes, broken templates, visual regressions.

Detailed run conditions, health-probe rules, screenshot/visual-diff flow, and configuration live in **`references/phase-1.5-runtime.md`** (sibling of this file). Read it before running this phase.

Self-skipping: in `auto` mode runs only when a dev-server port is open, UI files are in the diff, and `curl` is available; `force` mode skips the UI-files check (curl is still required). Any failure inside the phase degrades to `Runtime probe: SKIPPED (<reason>)` — never blocks Phase 2.

---

## Phase 2: Heuristic Analysis — Parallel Agents

**Goal**: Deep analysis across non-overlapping concern domains. Launch ALL applicable agents IN PARALLEL.

Read `references/phase-2-agents.md` (sibling of this file) for diff-slice mapping, spawn conditions, chunking, and timeout/retry rules. Before spawning ANY agent, also Read these sibling files directly so they enter context one-hop-deep from SKILL.md (per the Skills spec's "keep references one level deep" rule):

- `agents/_shared.md` — severity tiers, 3-question gate, quotas, auto-drop list, `codegraphTools` substitution. ALL agents inherit this.
- `agents/verifier.md` — Phase 2.5 verifier persona (referenced again from Phase 2.5; loaded here so it is reachable one-hop from SKILL.md).
- `agents/01-standards.md` — Standards & Clarity
- `agents/02-bugs-security.md` — Bugs & Security
- `agents/03-dry-smells.md` — DRY & Code Smells
- `agents/04-consistency-history.md` — Consistency & History
- `agents/05-simplification.md` — Simplification
- `agents/06-security-deep-dive.md` — Security Deep Dive (conditional)
- `agents/07-performance.md` — Performance
- `agents/08-test-quality.md` — Test Quality (conditional)
- `agents/09-api-contract.md` — API & Contract (conditional)
- `agents/10-a11y-i18n.md` — A11y & i18n (conditional)

For each agent you spawn: pass its persona + `_shared.md` (concatenated) + the diff slice as the prompt. Substitute `${codegraphTools.X}` placeholders using the runtime-resolved map from Step 0.7.

Apply `extraAgents` and `skipAgents` from `.claude/review-all.json`.

Each agent returns findings with `root_cause_key` (used for cross-agent dedup).

---

## Phase 2.5: Dedupe → Verify

Detailed dedup rules, batch verification, threshold table, and history persistence live in **`references/phase-2.5-verification.md`** (sibling of this file). Read it before running this phase.

Two-step flow:
1. **Dedupe** by `root_cause_key` (cheap; before verify) — apply global caps for SUGGESTED/QUESTION.
2. **Batch verify** — one verifier agent per source agent, in parallel.

Threshold (full table in the reference): score ≥ 75 → main report; 50–74 → appendix; < 50 → drop. VERIFIED gate findings auto-keep at 90.

---

## Phase 2.75: Completion Gate

**Goal**: prevent silent agent loss before the report is assembled. Premature completion is the #1 long-running-harness failure mode.

Before entering Phase 3, the orchestrator MUST verify:

1. **Every spawned agent returned.** Compare the actual return set against the planned spawn list from Phase 2 (after applying `extraAgents`/`skipAgents`). If any agent is missing or its result is empty due to timeout/error → re-spawn that one agent once.
2. **Every verifier returned valid JSON.** Each verifier output must parse and contain, per finding: `finding_id`, `root_cause_key`, `score` (0–100), `verdict` (`keep`/`appendix`/`drop`), `reason`, `reread_evidence`. Malformed output → re-spawn the verifier once with an explicit "your previous output failed schema validation: <reason>" preamble. Note: retry re-verifies the **entire batch** (same input set) — this is the documented token cost of a malformed verifier response; do not attempt partial salvage.
3. **Every gate has a terminal state.** Typecheck/Lint/Tests/Spec Existence/Dependencies must each be one of `PASS|FAIL|SKIP|TIMEOUT|N/A`. No `running`, no missing entries.

If after one retry an agent or verifier still has not returned cleanly:
- Do NOT drop it silently.
- Surface it in the Phase 3 report under a top-banner labelled `⚠️ PARTIAL REVIEW — the following agents did not complete: <list>`.
- The user must see what coverage they did not get.

Per-agent timeout default: `600s`. Per-verifier timeout default: `300s`. Configurable via `.claude/review-all.json` keys `agentTimeoutSeconds`, `verifierTimeoutSeconds`.

---

## Phase 3: Unified Report

Detailed report template, intent summary rules, numbering, and section rules live in **`references/phase-3-report.md`** (sibling of this file). Read it when assembling the report.

Required sections (in order): Intent, Summary, Automated Gate Results, Critical, Important, Debt, Suggested, Questions, Dependency Changes (if any), Potential Issues (Appendix). Risk Level: High if any 🔴, Medium if 🟠/🟡, Low otherwise.

---

## Phase 4: Post-Report Choices

Detailed menu, apply-fixes sub-menu, loop logic, and guardrails live in **`references/phase-4-menu.md`** (sibling of this file). Read it before presenting the menu.

Skip Phase 4 entirely if every section says "None found." Otherwise present the primary fix-scope menu via `AskUserQuestion` (single-select) with up to four options: **Fix critical**, **Fix critical + important**, **Fix critical + important + debt**, **Custom (C/I/D/S + #IDs)**. Only include scopes that have matching findings. The extended multi-select menu (Save report, Deep-dive, Post to PR, Skip / done, …) opens as a follow-up after the chosen fix action completes.

The **Custom** option accepts a free-text expression mixing severity letters (`C`/`I`/`D`/`S`, case-insensitive) and finding IDs (`#11` or bare `11`, ranges `1-7` or `#3-#9`), separated by comma, whitespace, or `and`. Result = UNION of every matched ID; severity letters expand to all in-report findings of that tier. Examples: `I D #11` → all 🟠 + all 🟡 + Finding 11; `1-7, 11` → those eight IDs. Full grammar in `references/phase-4-menu.md`.

Every finding in the report must be numbered (`**Finding N**:`) across all sections including the appendix — the Custom option's `#N` syntax depends on it.

---

## Progress Output

Long-running orchestration is silent by default — that triggers user-interrupts mid-Phase-2 and wastes spawned agent work. Emit a single user-visible line at each phase boundary so the user sees forward motion.

The lines below are the **canonical templates**. If you have all the data they need, emit them verbatim. If a value is genuinely unknown (e.g. elapsed not yet measurable, runtime probe skipped), substitute a one-word free-form line that still tells the user where you are (`Phase 0: profile built — 9 files, 2 commits.`). Both forms are acceptable; what is NOT acceptable is silence between phase boundaries or chatty per-agent narration.

- After Phase 0 ends: `Phase 0: profile built, <N> files in target (elapsed <S>s)`
- After Phase 1 ends: `Phase 1: typecheck=<R>, lint=<R>, tests=<R>, runtime=<R> (elapsed <S>s)`
- During Phase 2, when each agent returns: `Phase 2: <K>/<N> agents returned (elapsed <S>s)` — one line per return is OK; do not also narrate each agent's finding count.
- After Phase 2.75 completion gate: `Phase 2.75: <K> agents verified, <M> findings kept, <X> appendix, <Y> dropped (elapsed <S>s)`
- After Phase 3 ends: `Phase 3: report assembled — <C> critical, <I> important, <D> debt, <S> suggested, <Q> questions`

In addition, if ANY single Phase 2 agent exceeds 120s, emit ONCE:
`Long-running agent: <agent-id> (still working, budget <agentTimeoutSeconds>s)`

Keep heartbeat output to one line each. Do NOT narrate internal deliberation between heartbeats (e.g. "DRY agent: 0 findings. Continue waiting." — the `<K>/<N> agents returned` counter already conveys this).

---

## Important Rules

1. **LOCAL review only** unless the user explicitly picks "Post to PR". Default output is the terminal.
2. **Verify everything.** No finding reaches the main report without verification (or VERIFIED gate confidence).
3. **Evidence required.** Every finding must cite real code. "Might be a problem" is unacceptable.
4. **No noise.** 3 verified findings beat 20 unverified suggestions.
5. **Respect conventions.** A pattern in 5+ unchanged files is established convention — do not flag it.
6. **Changed code only, but with semantic depth.** Only flag NEW or MODIFIED code (except Critical security). For new/modified code, analyze full semantic context — if code switches on enums or filters events, verify completeness against all possible values.
7. **Actionable fixes.** Every finding must include a concrete fix.
8. **Project-agnostic.** Discover conventions from the repo. Never assume framework rules from one project apply to another.
