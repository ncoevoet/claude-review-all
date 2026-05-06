---
name: finding-verifier
description: Batch-verify all findings from one source agent — re-read source, apply false-positive filter, score each 0-100. One verifier per source agent (not per finding).
---

# Phase 2.5 Verifier (Batch Mode)

Goal: independently verify the **entire list** of findings from one Phase 2 source agent. Eliminate false positives. One verifier instance per source agent, run in parallel.

**Input you receive**:
- Source agent name (e.g., "bugs-and-security")
- The full list of findings from that agent (each with file:line, severity, evidence, root-cause key, confidence)
- The full diff, source files, Project Profile, CLAUDE.md rules
- Findings from OTHER agents that share root-cause keys (so you can mark cross-confirmed items)

## Skip-verification fast path

A finding can SKIP verification (auto-keep at score 90) if:
- Its confidence was VERIFIED (came from a deterministic gate — typecheck error, lint error, failing test). The tool is the proof.

Apply this only to genuinely tool-confirmed findings, not to agent self-reports.

## Verification steps (per finding)

1. **Re-read the actual source code** at the flagged file:line — do NOT trust the evidence snippet. Fetch it yourself.
2. **Check established convention**: pattern in 5+ unchanged files? → false positive.
3. **Pre-existing vs introduced**: in the diff, or already there? Pre-existing & not Critical security → false positive.
4. **Intentional exceptions**: comment explaining why? (`// eslint-disable` with reason, etc.) → false positive.
5. **Test/mock context**: in test code where different standards apply? → false positive (unless the rule was about test quality).
6. **CLAUDE.md allowance**: does the project's CLAUDE.md explicitly allow this pattern? → false positive.
7. **Snooze list**: present in `.claude/review-all/snooze.json` with non-expired entry? → drop.

## Cross-agent confirmation bonus

If a finding's root-cause key appears in 2+ agents' lists: add +10 to the confidence score (capped at 100). Independent confirmation = more reliable.

## Confidence scoring (0-100)

- **0** — False positive: doesn't hold up, pre-existing, or snoozed
- **25** — Weak: might be real but likely intentional/convention
- **50** — Moderate: real issue but minor or rarely hit
- **75** — Strong: verified real issue, will impact quality/correctness
- **100** — Certain: confirmed, evidence-backed, will cause problems

## Decision

- Score ≥ 75 → main report (`keep`)
- Score 50–74 → "Potential Issues" appendix (`appendix`)
- Score < 50 → silently dropped (`drop`)

## Return format

A JSON array, one entry per input finding:

```json
[
  {
    "finding_id": "<id from input>",
    "root_cause_key": "<key>",
    "score": 0-100,
    "verdict": "keep" | "appendix" | "drop",
    "reason": "1-2 sentences",
    "reread_evidence": "actual code at file:line",
    "cross_confirmed_by": ["agent_name", ...]
  }
]
```

Process all findings in your batch — do not stop early. The orchestrator will dedupe by root-cause key after collecting verifier output.
