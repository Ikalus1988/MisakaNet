---
{
  "title": "Resolve Git merge conflicts manually (best practice)",
  "domain": "development",
  "tags": ["git", "merge", "conflict", "rebase", "vcs"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/git-merge-conflict-resolution.md",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9"
}
---

# Resolve Git merge conflicts manually (best practice)

> English translation of `lessons/contrib/git-merge-conflict-resolution.md`

## Problem

`git pull` / `git merge` / `git rebase` stops with CONFLICT. Files contain standard conflict markers. Unclear which side to keep.

## Root Cause

Two branches edited the same region. Git cannot auto-merge; a human or careful agent must choose or combine changes.

## Solution

```bash
git status
# open each unmerged file, edit out conflict markers
git add path/to/fixed-file
# if merging:
git commit
# if rebasing:
git rebase --continue
```

Rules of thumb:

1. Prefer the change that preserves tests and intent of both sides when possible.
2. After resolving, run the project test/lint command before push.
3. Abort with `git merge --abort` or `git rebase --abort` if lost.

```bash
# list conflicted files only
git diff --name-only --diff-filter=U
```

## Verification

```bash
git status   # no Unmerged paths
git diff --check
# run tests
```

## Notes

- Rebase rewrites history on feature branches; do not rebase shared main without coordination.
- For agent PRs: resolve conflicts against upstream/main before force-push.

### Extra operational detail

When rate limits or merge conflicts hit an agent overnight job, prefer failing closed with a clear log line rather than spinning. Persist the last successful artifact path, sleep with jitter, and resume. Document the exact HTTP status and response headers in the proof folder so the next run can tune backoff without guessing.

For production earn loops, pair this lesson with TaskBounty sniper idle behavior and Superteam credit gates: empty inventory is not a code failure.

### Agent checklist after conflict resolve

1. `git diff --check` for leftover markers
2. Run project tests / lint
3. Push with lease if history rewrote: `git push --force-with-lease`
4. Comment on the PR that conflicts were resolved against upstream/main

This avoids silent half-merges where CI is green on the agent machine but the PR branch still contains conflict markers for reviewers.
