# Rule packs

A rule pack is a short, language-specific Markdown checklist of correctness/security/resource
traps that language invites — plus a mandatory `#### Do not report` section naming the false
positives that language invites. It is a delta on top of `agents/_shared.md` and the persona
files: anything already covered there must not be repeated here.

## When it's injected

The orchestrator matches each changed file's glob to a pack via `scripts/file-classes.json`'s
`rule_packs` map, and injects the single matching pack into that review agent's prompt as a
`<language_rules>` block. A file matching no glob falls back to `default.md`. A diff that only
touches Java never pays for the TypeScript pack — only the pack(s) actually present in the diff
are injected.

## Constraints

- Hard cap **60 lines** per pack (`default.md`: 25 lines) — every line is billed on every
  matching diff.
- Terse bullets only, no prose paragraphs.
- Must end with a `#### Do not report` section with at least 4 concrete bullets.
- Defects only (correctness/resource/concurrency/security) — no formatting or naming opinions;
  those belong to the Standards agent.

## Adding a language

1. Add `rules/<lang>.md` following the shape above.
2. Add its glob to the `rule_packs` map in `skills/review-all/scripts/file-classes.json`.
3. Run `tests/check-rule-packs.sh` — it enforces the cap and the mandatory section.
