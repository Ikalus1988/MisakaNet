---
title: "Uncommitted work has no undo: `git checkout -- .` and reset --hard during branch juggling"
domain: "git"
tags: ["git", "worktree", "recovery", "lost-work", "index"]
status: "published"
evidence_level: "E2"
created: "2026-09-13"
provenance:
  source: "MisakaNet maintainer session, 2026-09-13"
---

# Uncommitted work has no undo: `git checkout -- .` and reset --hard during branch juggling

## Problem

While reviewing a pull request, a maintainer fetched the PR into a local branch
and staged its files to read the diff in the working tree:

```bash
git fetch origin pull/1656/head:pr1656
git checkout pr1656 -- .        # stages the PR's files for inspection
git checkout -                  # back to the previous branch
git reset -q HEAD && git checkout -q -- . && rm -f <the added file>   # "clean up"
```

The cleanup did remove the PR's files. It also removed the session's actual
work — an uncommitted change to a script and its tests — which had been verified
and passing minutes earlier. `git status` was clean afterwards: the change simply
no longer existed. Nothing in the transcript could restore it, because the
recovery had to be done from the text of earlier tool output.

## Root Cause

Two Git behaviours combine into a silent data-loss trap:

1. `git checkout -- .` (and `git restore .`) **does not discard changes that are
   in the index** — it restores tracked files *from the index*. Anything staged
   therefore survives; anything only in the working tree is overwritten with the
   indexed version and is gone, because the working tree is not an object store:
   an unstaged edit has never been written into `.git/objects` and exists nowhere
   else.
2. `git checkout <branch> -- .` writes the other branch's version into **both**
   the index and the working tree. So the stage used minutes earlier to inspect a
   foreign PR became the baseline that the "cleanup" restored from — that is how
   the PR's files were removed, and it is also why a subsequent blanket
   `checkout -- .` looked like a plain cleanup.

The tempting mental model — "the file is on disk, so it is safe until I commit" —
is exactly inverted: on disk means "not stored anywhere". Verified on Git 2.55:

```bash
printf 'v1\n' > f.txt && git add f.txt && git commit -m "f v1"
printf 'v2 STAGED\n'   > f.txt && git add f.txt
printf 'v3 UNSTAGED\n' > f.txt
git checkout -- .
cat f.txt          # → v2 STAGED   (index copy survives)
```

and after a `reset --hard` the staged content is still recoverable, because it
reached the object store:

```bash
printf 'v4 STAGED-THEN-RESET\n' > f.txt && git add f.txt && git reset --hard
git fsck --unreachable | awk '/blob/{print $3}' | while read b; do git cat-file -p "$b"; done
# → v4 STAGED-THEN-RESET
```

## Solution

- **Commit before any operation that rewrites the working tree.** A two-line WIP
  commit is the whole insurance policy: `git add -A && git commit -m "wip: <what>
  --signoff"`. Amend or squash it later; nobody sees the intermediate state.
- When inspecting a foreign PR, do it in a **separate worktree** rather than by
  moving files through the main working tree:
  `git worktree add /tmp/pr1656 pr1656` — the main checkout is then untouched and
  needs no cleanup at all.
- If a cleanup is unavoidable, be specific about paths
  (`git restore path/to/file`) and never use a bare `git checkout -- .`,
  `git restore .`, or `git reset --hard` in a tree with uncommitted work.
- Prefer `git stash push -m "..."` (or a WIP commit) to a naked reset: the stash
  is recoverable via `git stash list`, a discarded working-tree file is not.
- Push work as soon as it is green. "It is only local for a moment" is how a
  verified change becomes a retyped one.

## Verification

- Reproduce the two behaviours in a scratch repository with the four-command
  sequence above: after `git checkout -- .` the staged version is present and the
  unstaged one is gone; after `git reset --hard` the staged blob is listed by
  `git fsck --unreachable` and its content can be printed with `git cat-file -p`.
- In a repository with uncommitted work, run `git status --porcelain` before any
  branch switch or restore, and confirm it is either empty or intentionally
  stashed.
- Recovery only works for content that entered the object store (staged or
  committed) and before `git gc` prunes unreachable objects: run
  `git fsck --lost-found` and check `.git/lost-found/` immediately, not later.
