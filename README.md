# /review-all

A comprehensive, project-agnostic code review slash command for [Claude Code](https://docs.claude.com/en/docs/claude-code/overview). Combines simplification analysis, code quality / smell detection, deterministic toolchain gates, and deep heuristic review into one local pass — and **independently verifies every finding** before reporting, so false positives stay out of the report.

It launches teams of parallel sub-agents covering: standards, bugs, security, DRY, smells, consistency, simplification, performance, test quality, API contracts, and a11y/i18n.

## Severity tiers

- **❌ CRITICAL** — Breaks functionality, exposes data, crashes systems, violates requirements
- **⚠️ IMPORTANT** — Missing error handling, unhandled edge cases, potential bugs
- **♻️ DEBT** — Code duplication, convention violations, refactoring needed within 6 months
- **🎨 SUGGESTED** — Measurable improvements only. If you can't measure the improvement, don't suggest it.
- **❓ QUESTION** — Items requiring human judgment about requirements or intent

## Install

This repo is a [Claude Code plugin marketplace](https://docs.claude.com/en/docs/claude-code/plugins). Inside Claude Code, run:

```
/plugin marketplace add ncoevoet/claude-review-all
/plugin install review-all@ncoevoet
```

That's it — `/review-all` is now available in every project. Updates land via `/plugin update review-all@ncoevoet` after a new release is tagged.

### Manual install (alternative)

If you'd rather not use the plugin system, copy the skill directory into your Claude Code config:

```bash
git clone https://github.com/ncoevoet/claude-review-all.git
mkdir -p ~/.claude/skills
cp -r claude-review-all/skills/review-all ~/.claude/skills/review-all
```

## Use

Inside Claude Code, run `/review-all` with any of these targets:

| Argument | Reviews |
|---|---|
| _(empty)_ | Uncommitted changes if any, else current branch vs default branch, else last commit |
| `--staged` | Only staged changes |
| `--unstaged` | Only unstaged changes |
| `last commit` | `HEAD~1..HEAD` |
| `last N commits` | `HEAD~N..HEAD` |
| `vs <branch>` | Current branch vs merge-base with `<branch>` |
| `<sha1>..<sha2>` | A specific commit range |
| `PR #N` or `#N` | A GitHub PR (requires `gh`) |
| _file paths_ | Restrict review to those files |

Examples:

```
/review-all
/review-all --staged
/review-all PR #123
/review-all last 3 commits
/review-all vs main
/review-all src/auth/login.ts src/auth/session.ts
```

## Optional configuration

Drop a `.claude/review-all.json` into any project to tune behavior:

```json
{
  "devServerPorts": [4200, 5173, 3000],
  "extraAgents": []
}
```

- `devServerPorts` — ports the command should probe to detect a running dev server before suggesting "run the build".
- `extraAgents` — additional agent persona files (under `~/.claude/skills/review-all/agents/`) to launch alongside the built-ins.

## Requirements

- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview)
- `git` (you've got this)
- `gh` — only required for `PR #N` review mode

## How it works

`/review-all` runs in phases:

1. **Project discovery** — detects language, frameworks, conventions, and resolves the diff target.
2. **Parallel agents** — 10+ specialized agents review the diff in parallel (standards, security deep-dive, performance, etc.).
3. **Verification** — every finding is independently re-checked against the actual code; unverifiable claims are dropped.
4. **Report** — consolidated, severity-ranked findings with `file:line` citations and proof.
5. **Menu** — optional follow-ups (post to PR, write fixes, etc.).

Agent personas live under `skills/review-all/agents/` and reference docs under `skills/review-all/references/` — both are plain Markdown, so you can read or fork them.

## License

MIT — see [LICENSE](LICENSE).
