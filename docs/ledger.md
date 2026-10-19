# Change ledger

One row per shipped or reverted change, built only from commit messages and tag annotations. The `observed` column quotes the evidence as the message states it; nothing is inferred.

Verdict vocabulary (borrowed from the edit-row record of google-research/harness2):

- `helped` / `hurt`: a stated eval contrast supports the direction.
- `no observed effect`: a stated eval shows the baseline arm already matches the treatment arm.
- `confounded`: a single run, or several simultaneous component changes, stand behind a difference. Prefer this over `helped`/`hurt` in those cases.
- `unmeasured`: no eval evidence is stated.

A lesson that rests only on `confounded` rows is a guess.

| SHA | Component | Change | Observed | Verdict |
|---|---|---|---|---|
| 08f90ba | scripts/eval-scorecard.py, run-evals-headless.sh | v0.7.0 A: suite recall/precision/F1/SNR scorecard, SCORE lines, config hook | "each eval-validated for non-regression"; no case ids or k/N stated | unmeasured |
| 08f90ba | verifierVotes (verifier) | v0.7.0 B: opt-in majority-vote verifier, default 1 | same non-regression claim; no case ids or k/N | unmeasured |
| 08f90ba | SKILL.md Phase 2 | v0.7.0 D: previously-dismissed digest passed to finding agents | same non-regression claim; no case ids or k/N | unmeasured |
| 08f90ba | beyond-the-diff blast-radius prototype | removed before the v0.7.0 commit | "prototyped and evaluated but removed before this commit: the skill already performs cross-file caller analysis — the control arm caught a designed cross-file break and executed the code to confirm the runtime error — so the feature was redundant" | no observed effect |
| 36c88b0 | agents/_shared.md, verifier, Phase 1 gates | v0.7.1: claim classes, `unverified` verdict (v5 to v6), gate provenance | none stated (tests/check-claim-class.sh added as a doc gate) | unmeasured |
| f78c517 | REVIEW.md support | v0.8.0: repo-root REVIEW.md injected into agents and verifier | case 90, per 206787c: baseline FAIL (1/3) vs treatment PASS (3/3); contrast was v0.7.1 baseline vs whole v0.8.0 tree (REVIEW.md, diff ordering, gate_results, staleness rule shipped together); case 90 targets REVIEW.md | confounded |
| f78c517 | scripts/agent-order.py | v0.8.0: per-agent diff ordering | only case 02 exercises it; 02 returned PASS (2/3) then FAIL (1/3) on identical baseline code (206787c) | unmeasured |
| f78c517 | gate_results block, dedupe.py corroboration | v0.8.0: failing-gate output to agents; corroborating_agents | case 92 passes on both arms (206787c) | no observed effect |
| 206787c | consistency persona | v0.8.1: staleness rule removed | case 91, two fixture designs, N=3, both arms: v0.7.1 baseline PASS 3/3, same as treatment | no observed effect |
| 2589d55 | evals cases 90, 91, 92 | rewritten so each case needs its feature; 92 added (gates genuinely fail) | "A/B of the rewritten cases has not run yet" | unmeasured |
| 642f017 | per-axis checkpointing, model tiers | v0.9.0: HEAD+diff-keyed resume; 4 opus / 6 sonnet tiers | none stated (tag message only) | unmeasured |
| eb01031 | phase-4-menu.md, config-keys.md | v0.9.1: pin every Phase 4 spawn, drop verifierModel "inherit" | refusal by the model-pin hook stated as observed; no eval | unmeasured |
| fc19e9b | SKILL.md, phase-3-report.md, runner | v0.9.2: severity tally named in required sections; `SCORE,<id>,MISSING` | two captured headless reports lacked the tally comment; no A/B | unmeasured |
| 3205fe9 | agents/_shared.md | exploration budget (tool order, ~15 search calls) | 78 review subagents: 1813 Bash / 238 Read / 10 CodeGraph / 1 Grep; "no A/B" | unmeasured |
| 4f15f63 | Phase 2.5 spawn site | verifier model stated where the orchestrator reads it; persona loaded once | 19 verifiers: 12 sonnet, 7 opus, 0 haiku; no A/B | unmeasured |
| be5146d | agents/_shared.md, Phase 2.5 | v0.9.3: packages 3205fe9 + 4f15f63 | "No eval A/B this cycle"; pass-rate signal below noise floor | unmeasured |
| 86b2bc4 | run-evals-headless.sh | REVIEW_ALL_EVAL_MODEL, CONFIG line, exit 3 on empty filter | harness tooling; haiku-vs-sonnet verifier A/B "not included" | unmeasured |
| bfebcfb | select-agents.py, select-files.py, rules/ | pre-dispatch agent and file selection; language rule packs | deterministic counts only (630 vs 910 spawns over 91 fixtures); no graded review quality | unmeasured |
| a17b670 | same as bfebcfb | v0.10.0 release of bfebcfb | "No eval A/B backs this release"; baseline arm running, treatment not | unmeasured |
| 33a8bf3 | state.json `rejected`, code-hash.py | machine dismissals remembered across runs | payoff is spend avoided; "unmeasured and unmeasurable by this harness"; case 98 non-discriminating by construction | unmeasured |
| 33a8bf3 | reverted security evidence-discipline rules (cases 93-98) | convention carve-out, 3 severity-inflation guards, boundary+trace schema; reverted pre-release | baseline at opus: 93 PASS (2/3), 94 PASS (1/1), 95-98 PASS (3/3) each | no observed effect |
| f328056 | v0.10.1 release | packages 33a8bf3; 93 left open | N=3 cannot separate 2/3 from 3/3; about N=10 per arm needed | unmeasured |
| f4c52fb | scripts/severity-tally.py | recover per-tier counts when the tally comment is dropped | 7 of 9 headless runs carried the comment; a harness repair, no review-quality claim | unmeasured |
| f27c30e | agents/_shared.md | attempt the observation before the unverified cap | case 01 over six runs: 0, 0, 1, 2, 5 findings; N=10 A/B stopped after three baseline runs (2, 0, 0) | unmeasured |
| 9689f52 | v0.10.2 release | packages f4c52fb + f27c30e | "Neither fix has a demonstrated recall or precision effect" | unmeasured |
| fe3c4ab | SKILL.md layout, references/troubleshooting.md | v0.10.3: hard rules hoisted, examples moved; text unchanged | "No eval was run"; effect of placement unmeasured | unmeasured |
