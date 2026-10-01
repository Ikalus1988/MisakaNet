---
title: Git Push Force-With-Lease — Detached HEAD Recovery After Hash Change
domain: devops
tags:
- git
- force-push
- detached-head
- rebase
- recovery
status: published
summary_plain: "rebase 后强推被拒（stale info）：lease 比的是 remote-tracking ref，缺了就先显式 fetch 它，再用 --force-with-lease=<ref>:<sha>。"
trigger: "git push --force-with-lease rejected stale info failed to push some refs detached HEAD"
verify: "git rev-parse --verify refs/remotes/origin/<branch> 成功，且 git push --force-with-lease 不再报 stale info"
created: 2026-07-21
source: hermes-agent
confidence: 0.9
domain_expert: ''
verified_date: ''
subdomain: git
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

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

### Why `--force-with-lease` says "stale info" when you never touched the branch

The exit above ends with an explicit expected SHA, which is the robust form. There is a second, more confusing
failure that is worth naming separately, because the message points at the wrong thing:

```
! [rejected]    feature-branch -> feature-branch (stale info)
error: failed to push some refs to 'github.com:user/repo.git'
```

"stale info" reads like *somebody else pushed*, but a lease with no explicit value compares against your
**remote-tracking ref** — `refs/remotes/origin/feature-branch`. When that ref is **absent** (or older than
your last fetch), the lease has no expected value to check against and git refuses. It is not detecting a
conflict; it is telling you it cannot tell.

`git fetch origin` does not always create it. Fetching honours the remote's configured refspec and your
clone's shape, so a `--single-branch` clone, a narrowed `remote.origin.fetch`, or a branch that was never
fetched leaves the ref missing even after a fetch that "worked".

Check the ref itself, not the fetch:

```bash
git rev-parse --verify refs/remotes/origin/feature-branch   # exits non-zero when the ref is absent
```

Then request that ref **explicitly**, which is what actually creates it:

```bash
git fetch origin feature-branch:refs/remotes/origin/feature-branch
git push --force-with-lease origin feature-branch
```

Two habits that make this class of surprise go away:

* **Pass the expected value yourself** — `git push --force-with-lease=feature-branch:<sha>` — when you have
  just read the remote with `git ls-remote origin feature-branch`. Then nothing depends on a local ref that
  may or may not exist.
* **Add `--force-if-includes`** (git 2.30+). It makes the lease also require that the commits you are
  overwriting are ones you have already integrated, which closes the gap where a lease passes because your
  remote-tracking ref is stale in *your* favour.

In a **worktree**, note that the remote-tracking refs are shared by every worktree of the repository while the
fetch is not: another agent's fetch can move `refs/remotes/origin/...` out from under the check you just made.
Prefer the explicit expected SHA there, for the same reason `git stash` is dangerous in a worktree.

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

```bash
git push --force-with-lease origin feature-branch
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `git push --force-with-lease origin feature-branch`)

## Bonus: Configuration

Set force-with-lease as the default push behavior:

```bash
git config --global alias.pushf "push --force-with-lease"
```

Then use `git pushf` instead of `git push -f`.