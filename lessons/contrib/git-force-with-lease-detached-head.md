---
title: Git Push Force-With-Lease — Detached HEAD Recovery After Hash Change
domain: devops
subdomain: git
tags:
  - git
  - force-push
  - detached-head
  - rebase
  - recovery
source: hermes-agent
status: published
confidence: 0.90
created: 2026-07-21
verified_date: ''
domain_expert: ''
---

{"title": "Git Push Force-With-Lease — Detached HEAD Recovery After Hash Change", "domain": "devops", "subdomain": "git", "tags": ["git", "force-push", "detached-head", "rebase", "recovery"], "source": "hermes-agent", "status": "published", "confidence": "0.90", "created": "2026-07-21", "verified_date": "", "domain_expert": ""}


## Problem

After a `git rebase` on a feature branch that was force-pushed, the local branch's commit history no longer matches the remote. Running `git pull` produces:

```
Your branch and 'origin/feat/foo' have diverged,
and have 3 and 3 different commits each, respectively.
```

Running `git push --force` creates risk of overwriting others' work. But `git pull --rebase` fails because the branch has already been rebased and force-pushed elsewhere (e.g., from another machine or CI pipeline).

The real danger: `git push --force` can silently destroy commits pushed by collaborators that you haven't seen.

## Root Cause

The standard `git push --force` (`-f`) overwrites the remote ref unconditionally. This is dangerous because:

```bash
# Dangerous — overwrites remote without checking
git push --force origin feature-branch
```

Between the time you last fetched and your push, someone else could have pushed new commits to the same branch (e.g., from CI auto-fix, a colleague's hotfix, or another machine). A force push would wipe those commits.

## Fix

Use `--force-with-lease` instead of `--force`. This checks that the remote ref is still at the commit you expect before overwriting:

```bash
# Safe — only overwrites if remote hasn't moved
git push --force-with-lease origin feature-branch
```

If someone else has pushed in the meantime, Git rejects the push with:

```
! [rejected]    feature-branch -> feature-branch (stale info)
error: failed to push some refs to 'github.com:user/repo.git'
hint: Updates were rejected because the remote contains work that you do
hint: not have locally.
```

This is exactly what you want — it stops you from destroying someone else's work.

### Scenario: After Rebase + Force Push

When you rebase and need to push:

```bash
# 1. Rebase onto latest main
git rebase main

# 2. Push with safety check
git push --force-with-lease origin feature-branch
```

If the push fails with "stale info":

```bash
# 3. Fetch the latest remote state and see what changed
git fetch origin
git log origin/feature-branch --oneline -5

# 4. Decide: are these commits you want to preserve?
#    If yes: merge or cherry-pick them
#    If no (they're from a stale CI run): force with explicit reference
git push --force-with-lease origin feature-branch \
  refs/remotes/origin/feature-branch:<expected-old-sha>
```

### Detached HEAD Recovery

If you end up in detached HEAD state after a botched rebase:

```bash
# 1. Find your lost commits
git reflog | head -10

# 2. Create a temporary branch at the lost commit
git checkout -b recovery-branch HEAD@{2}

# 3. Cherry-pick any commits onto the real branch
git checkout feature-branch
git cherry-pick recovery-branch~3..recovery-branch

# 4. Clean up
git branch -D recovery-branch
```

## Verification

1. Before any force push, always run `git fetch origin` first
2. Check `git log origin/feature-branch --oneline -3` to see what's on remote
3. Run `git push --force-with-lease` and confirm it succeeds
4. Verify the remote branch has the expected commits: `git log origin/feature-branch --oneline -5`
5. To make this the default, configure: `git config --global push.default current` and make `--force-with-lease` your muscle memory

## Bonus: Configuration

Set force-with-lease as the default push behavior:

```bash
git config --global alias.pushf "push --force-with-lease"
```

Then use `git pushf` instead of `git push -f`.
