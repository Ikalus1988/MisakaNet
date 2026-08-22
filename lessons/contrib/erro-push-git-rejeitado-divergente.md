---
{
  "title": "Erro de push rejeitado no Git: branches divergentes e como resolver",
  "domain": "devops",
  "tags": "[git, push, merge, rebase, divergente]",
  "language": "pt",
  "status": "published",
  "source": "manual",
  "created": "2026-07-29",
  "confidence": 0.9,
  "verified_date": "2026-07-29",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Problem

This error occurs when Git refuses to push local commits because the remote branch has commits that the local branch does not. The push fails with:

```
! [rejected]        main -> main (non-fast-forward)
error: failed to push some refs to 'https://github.com/usuario/repo.git'
hint: Updates were rejected because the remote contains work that you do not
hint: have locally.
```

This happens when you and another collaborator modified the same files and the Git history diverged.

## Root Cause

Git requires the local history to be a linear superset of the remote history to accept a `push`. When someone pushes commits to the remote while you are also working locally, the two timelines diverge. Git rejects the push to prevent overwriting someone else's work.

Two approaches exist to resolve this: **merge** (creates a merge commit) or **rebase** (rewrites history linearly).

## Solution

**Approach 1: Merge (recommended for beginners)**
```bash
git pull origin main
git push origin main
```

If conflicts occur during merge:
```bash
git pull origin main
# Git shows: CONFLICT in arquivo.txt
# Edit the conflicting files manually
git add arquivo.txt
git commit -m "Resolve merge conflicts with origin/main"
git push origin main
```

**Approach 2: Rebase (linear history, more advanced)**
```bash
git pull --rebase origin main
git push origin main
```

If conflicts occur during rebase:
```bash
git pull --rebase origin main
# Resolve conflicts in the affected files
git add arquivo.txt
git rebase --continue
git push origin main
```

To abort the rebase if something goes wrong:
```bash
git rebase --abort
```

**Approach 3: Force push (ONLY if you are certain)**
```bash
git push --force-with-lease
```

`--force-with-lease` is safer than `--force` because it checks that the remote has not changed since your last fetch.

## Verification

- Run `git log --oneline --graph --all` to visualize the branch history
- Confirm the local branch is ahead of the remote: `git status`
- Run `git push` and confirm there is no rejection
- Verify on GitHub/GitLab that the commits appear correctly

## Notes

- `git pull` is equivalent to `git fetch` followed by `git merge`
- Run `git fetch` before `git push` to check for remote changes without automatically merging
- Prefer `--force-with-lease` over `--force` in all situations
- Agree with your team on whether to use merge or rebase to maintain consistent history
- Set `git config --global pull.rebase true` to use rebase as the default pull strategy
- Reference: [GitHub docs on non-fast-forward errors](https://docs.github.com/en/get-started/using-git/dealing-with-non-fast-forward-errors)
