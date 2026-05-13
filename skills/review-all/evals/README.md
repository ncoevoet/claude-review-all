# Evals — `/review-all`

Three scenarios that probe whether the orchestrator catches what it should and stays quiet otherwise. Aligned with the Anthropic Skills authoring spec ("at least three evaluations").

## Scenarios

| ID | What it tests |
|----|---------------|
| `01-small-diff-null-deref` | Surface coverage — a clear bug in a small diff must be flagged as 🔴/🟠 and survive verification. |
| `02-large-refactor-no-noise` | Noise floor — a pure 200-file rename with green gates must produce ≤2 findings and zero 🔴. |
| `03-auth-crypto-change` | Severity calibration — an MD5 downgrade in `src/auth/` must spawn Security Deep Dive and surface as 🔴. |

Each scenario is a `*.json` file. The schema mirrors the cookbook example: `id`, `skill`, `query`, `fixture`, `expected_behavior[]`, `expected_not_behavior[]`.

## Running

```bash
bash ../scripts/run-evals.sh        # iterates *.json, prints PASS/FAIL per scenario
bash ../scripts/run-evals.sh 03     # run a single scenario by id prefix
```

The runner is convenience; the JSON files are the authoritative artifact. If Anthropic ships a built-in eval runner later, these files plug in unchanged.
