---
title: Maintainer Feedback Iteration — Address Blockers, Not Just Comments
domain: meta
tags:
- contrib
- maintainer
- feedback
- iteration
- pr
status: published
created: '2026-07-15'
source: Multiple PR review cycles
confidence: 0.95
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
summary_plain: "When maintainers provide feedback on PRs, contributors often address surface-level comments while missing the core…"
trigger: "Maintainer Feedback Iteration — Address Blockers, Not Just Comments. When maintainers provide feedback on PRs, contributors often address surface-level…"
verify: "双侧：没接住 blocker 的 PR closingIssuesReferences=0；接住的=5。gh pr view $PR --json closingIssuesReferences。"
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

双侧（`gh pr view --json closingIssuesReferences`，本仓真实 PR）：

```console
$ gh pr view 4890 --repo <owner>/<repo> --json closingIssuesReferences --jq '.closingIssuesReferences | length'
0

$ gh pr view 3755 --repo <owner>/<repo> --json closingIssuesReferences --jq '.closingIssuesReferences | length'
5
```

故障侧：只回表面评论、没接住 blocker 的 PR，`closingIssuesReferences` 为 0——PR 与它要关的
问题之间没有线；修复侧：接住 blocker 的 PR 显式挂上 closing 引用（5 条）。命令即正文给出的
检查，两侧输出即判据。

## Related

- PR #479: 6 review cycles before merge
- `pr-strategy.md` — External PR strategy