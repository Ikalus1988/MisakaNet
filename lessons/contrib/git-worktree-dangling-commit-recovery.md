---
{
  "title": "git worktree commit lost after pushing from the wrong directory",
  "domain": "development",
  "tags": [
    "git",
    "worktree",
    "reflog",
    "recovery",
    "branch"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-11 00:00:00 UTC",
  "updated": "2026-08-11 00:00:00 UTC",
  "author": "Liona Can",
  "source": "manual",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

# git worktree commits "disappear" after pushing from the wrong directory

## Problem

A commit made inside a `git worktree add <path> <branch>` appeared to vanish: the remote branch did not move, and the local branch was suddenly empty. The work had taken hours and seemed unrecoverable.

## Root cause

`git worktree` attaches a worktree to a *branch*. When a push or commit runs from the wrong place (for example a second worktree, or the main clone, or a bare path) the HEAD you commit on can be a different branch or a detached HEAD:

- Commits made on a detached HEAD or an unexpected branch are not referenced by any branch name, so they are invisible in normal `git log`.
- The original branch ref itself was not updated — it still pointed at the old commit. The work exists in the object database but nothing references it.

The commit is not lost; it is simply *unreferenced*.

## Failure & recovery

Panic-driven string searches for the files failed because the working tree had been cleaned. The reliable recovery path:

1. `git fsck --lost-found` — lists dangling commits. Look for commits whose dates/messages match the work.
2. Or `git reflog --all` — shows every HEAD movement including the detached-HEAD history.
3. `git branch <name> <sha>` or `git checkout -b <name> <sha>` — re-attach a branch to the recovered commit.
4. Push from the correct worktree (or folder), or from the re-attached branch directly.

## Prevent it

- Always confirm `git rev-parse --abbrev-ref HEAD` and `git status -b` before committing/pushing when using worktrees.
- Verify the remote moved: after push, `git ls-remote origin <branch>`.
- Keep a habit of writing useful commit messages you can grep for in `fsck --lost-found` output.

## Lesson

A "missing" git commit is almost always a dangling object. Recover with `fsck --lost-found`/`reflog` instead of rewriting from memory, and fix the workflow that created it.
