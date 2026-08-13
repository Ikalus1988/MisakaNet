---
{
  "\"title\"": "Squash-rebase rewrites the patch base and breaks force-push expectations\",",
  "\"domain\"": "development\",",
  "\"tags\"": "[",
  "\"status\"": "published\",",
  "\"evidence_level\"": "E2\",",
  "\"created\"": "2026-08-11 00:00:00 UTC\",",
  "\"updated\"": "2026-08-11 00:00:00 UTC",
  "author": "ElevaSync Solutions",
  "source": "manual",
  "edited_at": "2026-08-11T03:55:00Z",
  "merged_by": "ElevaSync Solutions"
}
---

# Squash-rebase silently changes the base — and force-push races follow

## Problem

A contribution branch had been periodically force-pushed while staying based on an older commit. After a squash-rebase intended to tidy history, the next force-push hit `remote contains work you do not have locally` and reviewers could no longer reconcile the branch with the PR.

## Root cause

Two compounding git behaviors:

1. A squash-rebase (or any rebase that "updates" the branch) changes not just the history but the *base* commit the branch grows from. Reviewers comparing against the PR's recorded base see a rewritten set of files, not an incremental diff.
2. `--force-with-lease` protects against overwriting work *you haven't seen* — but after a local rebase, the local ref diverges from remote in a way that the semantic guard misjudges, and a plain `--force` overwrites something you may have based your squash on.

## Failure & recovery

The fix is to treat squash-rebase as a *conflict resolution*, not a formatting step:

1. Before squashing, capture the current remote head: `git rev-parse origin/<branch>`.
2. `git rebase -i` to squash, then verify `git diff origin/main...HEAD` shows exactly the intended net change.
3. Push with `--force-with-lease=refs/heads/<branch>:<old-remote-sha>` explicitly naming the sha you are allowed to replace — never a naked `--force`.
4. If reviewers already commented on line numbers, say clearly that the patch was rebased/squashed so they re-review by file diff, not by conversation.

## Lesson

Squash is not cosmetic: it rewrites the base and re-opens the merge contract. Name the lease explicitly and re-verify the net diff before force-pushing a squashed branch.
