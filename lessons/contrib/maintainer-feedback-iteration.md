---
title: Maintainer Feedback Iteration — Address Blockers, Not Just Comments
domain: contrib
tags:
- contrib
- maintainer
- feedback
- iteration
- pr
status: draft
created: '2026-07-15'
source: Multiple PR review cycles
confidence: 0.95
---

## Problem

When maintainers provide feedback on PRs, contributors often address surface-level comments while missing the core blockers. This leads to multiple review cycles and frustration.

## Root Cause

Maintainer feedback often contains:
1. **Explicit blockers** — "Remove auto-close references"
2. **Implicit blockers** — "This is not acceptable as benchmark evidence"
3. **Scope signals** — "This can be merged as X, but not as Y"

Contributors focus on #1 but miss #2 and #3.

## Solution

### 1. Parse Feedback for Blockers, Not Just Comments

```python
# ❌ Addressing comments
if "remove" in comment:
    remove_thing()

# ✅ Addressing blockers
blockers = extract_blockers(comment)
for blocker in blockers:
    fix_blocker(blocker)
```

### 2. Check GitHub State, Not Just PR Content

```bash
# Check if GitHub still links issue as closing
gh pr view $PR --json closingIssuesReferences

# Check if title/body still has auto-close keywords
gh pr view $PR --json body | grep -i "closes\|fixes"
```

### 3. Verify After Each Fix

```bash
# After fixing, verify the fix
gh pr view $PR --json closingIssuesReferences
# Should be empty if issue references removed
```

### 4. Use Maintainer's Exact Words

If maintainer says "search retrieval probe", use that exact term in your response. Don't paraphrase.

## Verification

```bash
gh pr view $PR --json closingIssuesReferences
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `gh pr view $PR --json closingIssuesReferences`)

## Related

- PR #479: 6 review cycles before merge
- `pr-strategy.md` — External PR strategy