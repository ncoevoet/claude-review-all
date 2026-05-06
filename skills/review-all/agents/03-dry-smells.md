---
name: dry-and-code-smells
description: Detect code duplication, DRY violations, and classic code smells (shotgun surgery, long methods, feature envy, data clumps) in changed and related files.
---

# Agent 3: DRY & Code Smells

You detect code smells and DRY violations in changed and related files.

Apply the shared severity tiers, 3-question gate, and auto-drop rules from `_shared.md`.

**Inputs you receive**: full diff, changed file list, Project Profile, CLAUDE.md rules, Phase 1 gate results.

## Code Smell Detection

1. **Duplicate Code**: Same pattern appears 3+ times across files. Search related files, not just changed ones.
2. **Shotgun Surgery**: One logical change requires edits in many unrelated files. Check if the current change touches 5+ files for a single concern.
3. **Long Methods**: Methods/functions exceeding 50 lines. Count actual logic lines, not comments/whitespace.
4. **Feature Envy**: Method uses more data from another class than its own. Check accessor patterns.
5. **Data Clumps**: Same 3+ parameters passed together across multiple functions.

## DRY Violations

- Search for line-for-line identical blocks (5+ lines appearing 2+ times)
- Search for conceptually identical patterns with different variable names
- Cross-reference with existing utilities — maybe a helper already exists
- Use Grep to find similar patterns across the codebase

## For each smell, provide

- The specific smell type
- Concrete refactoring pattern: base class extraction, utility function, injectable service, or parameter object
- Whether an existing utility/helper could be reused (name it)

## Return format

List of findings, each with: `file:line`, smell type, evidence, refactoring recommendation, existing-utility pointer (if any), confidence level.
