---
{
  "title": "Git merge conflict resolution — manual best practices",
  "domain": "development",
  "tags": ["git", "merge", "conflict", "rebase"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/git-merge-conflict-resolution.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# Git merge conflict resolution — manual best practices

> English translation of `lessons/contrib/git-merge-conflict-resolution.md`

## Problem

`git pull` or `git merge` reports `CONFLICT` and the file contains `<<<<<<<` markers. You don't know which version to keep.

## Root Cause

Two branches modified the same region of the same file. Git cannot automatically decide which version to keep.

## Fix

```bash
# 1. Check status
git status

# 2. View conflict details
git diff

# 3. View both sides of each conflicting file
git checkout --ours filename.py   # keep current branch version
git checkout --theirs filename.py # keep incoming branch version

# 4. Manual edit (recommended): open the conflicted file and find the <<<<<<< markers
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> branch-name
#
# Keep the parts you want, delete the marker lines

# 5. Mark as resolved
git add filename.py

# 6. Complete the merge
git commit  # uses the auto-generated merge message

# 7. If you regret it, abort the merge
git merge --abort
```

## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior

## Prevention

```bash
# Rebase before pulling to reduce conflicts
git pull --rebase

# Commit and push frequently to minimize divergence
```

## Related

- `git-merge-conflict-resolution` (Chinese original)
