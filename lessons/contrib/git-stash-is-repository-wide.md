---
domain: "git"
title: "git stash is repository-wide, not worktree-local — a bare stash pop can apply another session's work"
tags:
  - "git"
  - "stash"
  - "worktree"
  - "multi-agent"
  - "data-loss"
  - "reflog"
  - "recovery"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2606"
summary_plain: "git stash 是仓库级的：所有 worktree 与 agent 共用 refs/stash，裸 git stash pop 取的是最新一条——很可能是别人的。先 show -p 确认是谁的，再用 apply 而不是 pop。"
trigger: "git stash pop another session worktree shared stash refs/stash applies someone else's changes dropped stash"
verify: "git stash list shows an entry carrying your own message at stash@{0}, and the diff it applies touches only files you changed"
provenance:
  issue: "#2606"
---

## Problem

Two agent sessions work on the same repository in two different worktrees. Session A finishes a change, stashes
it, and later runs `git stash pop` to get it back. What comes back is **session B's** work — because B ran
`git stash` a few minutes earlier and its entry is newer.

The pop usually *succeeds*. That is what makes it expensive: A's working tree now holds someone else's change,
B's stash entry has been **dropped**, and neither session has an error to look at. The first sign of trouble is
usually a diff that makes no sense, or a missing change in the other worktree.

## Root Cause

`git stash` does not create per-worktree storage. It writes to `refs/stash` — **one ref, one reflog, belonging
to the repository** — and every worktree of that clone reads and writes the same stack:

```bash
git rev-parse --git-common-dir     # the shared directory all worktrees point at, not --git-dir
git stash list                     # repository-wide, no worktree column
```

`git stash pop` is defined as "apply `stash@{0}` and drop it if the apply succeeded", and `stash@{0}` is simply
**the most recent entry**, whoever created it. Nothing in the command asks whether that entry is yours, and
nothing in a worktree changes the answer. The more agents share a clone, the more often someone else's entry is
on top.

The reason nobody notices in single-agent use is that there is no interleaving: your stash is always the newest
one. Parallelism is what turns a convenient assumption into a data-loss bug.

## Solution

**Do not use a bare `git stash pop` in a shared clone.** Pick one of these, in order of how much they
eliminate the problem:

1. **Label every stash and read before you take.**

   ```bash
   git stash push -m "session-A: auth refactor"          # label at creation
   git stash list                                        # find your entry, note its index or SHA
   git stash show -p stash@{0}                           # read it: is this diff mine?
   git stash apply stash@{0}                             # apply, do NOT pop
   git stash drop stash@{0}                              # drop only after the apply is verified
   ```

   `apply` keeps the entry until you choose to remove it, which turns "someone's work vanished" into "there is an
   extra entry I can drop later".

2. **Do not stash at all when the unit of work is a branch.** In a worktree-per-agent setup, a temporary commit
   is strictly better: it is per-branch (so it cannot collide), it appears in `git log`/`git reflog` where the
   other session can see it, and it survives a wrong `reset` that a stash would not.

   ```bash
   git switch -c wip/session-a-auth
   git commit -am "wip: auth refactor (do not merge)"
   ```

3. **Give each agent its own clone when both must stash.** Separate clones have separate `refs/stash`. If the
   agents are long-lived and the workflow depends on stashing, this is the only arrangement where `stash pop` is
   safe by construction.

## Recovery, after the wrong pop

The dropped entry is still reachable — `refs/stash`'s reflog no longer lists it, but the commit object exists
until gc:

```bash
git fsck --unreachable 2>/dev/null | grep commit          # candidate stashes
git show --stat <sha>                                     # identify the other session's change
git stash apply <sha>                                     # put it back
```

Then tell the other session what happened, and let *it* re-apply its own work: what you restore is the snapshot,
not the intent behind it.

## Verification

A shared-clone workflow is safe when this holds for every stash you consume:

```
git stash list                       -> stash@{0} carries a message you wrote
git stash show -p stash@{0}          -> every touched file is one you changed
git reflog show refs/stash | head    -> the newest entry is yours, not "wip on <branch>" from a peer
```

If you cannot show the first two, apply by explicit SHA instead of index — an index is a moving target in a
repository someone else is also writing to.

## What not to do

- Do not run `git stash pop` in a shared clone "just to see" what comes back; `pop` drops on success.
- Do not assume `stash@{0}` is yours because you ran `git stash` "a while ago" — newer entries win.
- Do not recover by re-running `git stash` over the other session's applied change: you would stack a third
  mess on top and bury the original entry further.
- Do not script `git stash pop` in an agent loop. Stash is a human convenience; a loop should use branches.

## For agents working on this

Before any `stash pop`/`apply`, print `git stash list` and `git stash show -p stash@{0}` into your transcript,
and say whose entry you are taking. In a repository with more than one writer, an unlabelled stash is
indistinguishable from a stranger's — and the command that consumes it is the one that drops it.
