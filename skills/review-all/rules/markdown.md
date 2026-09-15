# Markdown rules

Markdown defect deltas: stale documented claims, broken relative links, docs contradicting the diff.

#### Stale documentation
- A documented invariant or behavior claim whose falsifying code change is present in this same diff — cite the contradicting `file:line`
- A code sample in the doc that no longer matches the current signature/API after a rename in this diff
- A "how this works" description whose described mechanism was replaced by this diff

#### Links & references
- A relative link/path to a file this diff moved, renamed, or deleted
- An anchor link (`#section`) to a heading this diff renamed or removed

#### Do not report
- A stale-sounding claim about code this diff does not touch — no evidence it is newly false
- REVIEW.md's or CLAUDE.md's own directives (severity policy, focus areas, exclusions) — that is configuration, not a reviewable defect
- A broken external (`http`/`https`) link — network reachability is not verifiable from source
- A `TODO`/`FIXME` marker left in prose
- Heading capitalization, line-length, or other prose style nits — Standards agent owns those
