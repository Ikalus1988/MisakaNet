---
{
  "title": "PR Cleanup SOP — Stale/Duplicate/Resolved PR Disposition",
  "domain": "devops",
  "lang": "en",
  "source": "codewhale",
  "status": "published",
  "tags": [
    "github-actions",
    "pr-management",
    "cleanup",
    "maintenance",
    "sop"
  ],
  "created": "2026-06-13 00:00:00 UTC",
  "updated": "2026-06-13 00:00:00 UTC",
  "domain_expert": "codewhale",
  "verified_date": "2026-06-13"
}
---

> Translated from: [lessons/core/pr-cleanup-sop.md](../core/pr-cleanup-sop.md)

## Root Cause

Open PR accumulation drains maintainer energy. In high-frequency AI Agent contribution scenarios, duplicate/stale/resolved PRs are especially common. A systematic disposition strategy is needed.

**Config issue**: GitHub does not auto-close merged PRs by default (requires `Closes #N` keyword or bot configuration). When multiple AI Agents contribute simultaneously:
- Same issue solved by multiple agents, producing competing PRs
- PR already merged via other means (e.g., bot direct push), but PR itself remains open
- PR has excessive changes or conflicts with main, cannot merge
- High volume of format noise, CRLF pollution, and other low-quality submissions

## PR Classification & Disposition Decision Tree

### 1. Code already merged to main (most common)

**Action**: Close with comment explaining the code was merged via another path.
```
Thank you for this contribution! The changes have been incorporated
via [commit/PR reference]. Closing this PR to keep the queue clean.
```

### 2. Duplicate of another open PR

**Action**: Close, reference the canonical PR, thank the contributor.
```
This is a duplicate of #N which is currently under review.
Closing in favor of the earlier submission. Thank you for your effort!
```

### 3. Stale (>30 days no activity, conflicts with main)

**Action**: Post a "still interested?" comment. If no response in 7 days, close.
```
This PR has been inactive for 30+ days and has merge conflicts.
If you'd like to continue, please rebase and ping a maintainer.
Otherwise, this will be closed in 7 days.
```

### 4. Low quality / noise PRs

**Action**: Close immediately with brief explanation. Do not engage in lengthy discussion.

## Automation

- Use a scheduled GitHub Action to label PRs stale after 30 days
- Auto-close after 7 more days of inactivity
- Exception: PRs with `wip` or `do-not-close` labels
