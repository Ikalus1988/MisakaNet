---
{
  "title": "GitHub PR ready checklist for agent docs PRs",
  "domain": "ops",
  "tags": ["github", "pr", "dco", "ci", "agent", "checklist"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# GitHub PR ready checklist for agent docs PRs

## Problem

Docs PRs sit red for trivial reasons: missing DCO, quality score, or dirty base.

## Root Cause

Agents push without a final gate checklist.

## Solution

```bash
git fetch upstream main
git rebase upstream/main
git commit -s --amend --no-edit  # ensure Signed-off-by
python3 scripts/quality_scorer.py path/to/lesson.md --json | tee /tmp/q.json
# total_score must be >= 0.5 for MisakaNet CI
git push --force-with-lease
gh pr create --fill
gh pr comment --body "/try"
```

## Verification

```bash
git log -1 --format=%B | grep Signed-off-by
gh pr checks
```

## Notes

- Rebase often; force-with-lease only on your branch.
- Fork comment permission failures are not content failures.

