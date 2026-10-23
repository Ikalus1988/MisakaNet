---
domain: "devops"
title: "A manually stacked pull request is closed, not retargeted, when the upstream branch is deleted"
tags:
  - "github"
  - "pull-request"
  - "stacked-pr"
  - "gh-cli"
  - "branch"
  - "recovery"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-10-23"
updated: "2026-10-23"
source: "intake-3762"
summary_plain: "Merging the bottom PR of a hand-made stack with --delete-branch closes the PR above it."
trigger: "gh pr merge --delete-branch closed the downstream PR; Cannot change the base branch of a closed pull request; stacked pull request base branch deleted"
verify: "Before deleting a branch, `gh pr list --state open --json number,baseRefName` must show no open PR whose base is that branch; after the merge the downstream PR must be OPEN with base main."
url: "https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/deleting-and-restoring-branches-in-a-pull-request"
link: "https://docs.github.com/en/pull-requests/get-started/about-stacked-prs"
provenance:
  issue: "#3762"
  source: "MCP intake (claude-code), contributor-reported"
  evidence: "Maintainer review: the branch-deletion rule and the stack-retarget behaviour were checked against GitHub's own documentation (2026-10-23); the failure itself is contributor-reported, not locally reproduced."
---

## Problem

A stack of pull requests was built by hand: PR #2's base was PR #1's head branch
(the shape GitHub documents as a *manual* stack).

Merging the bottom PR with the ordinary incantation closed the PR above it:

```bash
gh pr merge <upstream> --merge --delete-branch
```

Within seconds, the downstream PR was **closed** — not moved to `main`. The upstream
branch had been deleted, so the downstream PR's base branch no longer existed.

The PR object could not be brought back:

| Command | Result |
|---|---|
| `gh pr edit <downstream> --base main` | `Cannot change the base branch of a closed pull request` |
| `gh pr reopen <downstream>` | `Could not open the pull request` (the base branch is gone) |

The commits survived — the head branch was still intact — but the PR was unrecoverable
as an object: its discussion, its review history, and its CI runs all stayed attached
to a closed PR.

## Root Cause

Two rules met, and only one of them is enforced by the tool you called.

1. **GitHub's rule is explicit**: a branch may be deleted only when *no open pull
   request references it*. "You cannot delete branches that are associated with open
   pull requests… you can delete a branch that is associated with a pull request if the
   pull request has been merged or closed and there are no other open pull requests
   referencing the branch."
2. **The UI enforces it; `gh` does not.** GitHub's own **Delete branch** button is not
   even rendered when another open PR references that branch. `gh pr merge
   --delete-branch` performs the same deletion through the API — where that check does
   not exist. The merge reports success; the branch is gone.

So the branch deleted by `--delete-branch` was, in a manual stack, **the base of the PR
above it**.

3. **Losing the base closes the PR; it does not retarget it.** Retargeting is a
   *stack-aware* behaviour. GitHub documents it for its own stacked PRs: "the pull
   requests above stay open and automatically re-target the stack's base branch" when a
   mid-stack PR is merged. A hand-made stack gets none of that — the dependent PR
   simply loses its base, and GitHub closes it.

4. **The failure is silent, fast, and lands on a PR you did not touch.** `--delete-branch`
   is one flag on a command that reports success about *the PR you named*. The damage
   appears seconds later, on a different PR.

## Solution

Order of operations: merge the upstream PR first, delete its branch **last**, and
retarget the downstream PR yourself.

### Step 0: Before merging anything, find out who is pointing at that branch

```bash
gh pr list --state open --json number,baseRefName,headRefName \
  --jq '.[] | "PR #\(.number)  base=\(.baseRefName)  head=\(.headRefName)"'
```

If any row has `base=` equal to the branch you are about to delete, you are in a manual
stack and the delete is unsafe.

### Step 1: Merge the upstream PR *without* `--delete-branch`

```bash
gh pr merge <upstream> --merge
```

Use a **merge commit**, not a squash: a squash rewrites the commits, so the downstream
PR's history stops being a subset of `main`, and the downstream diff changes shape
under you. (GitHub's own docs make the same distinction for stacks: "Stacks support
merge commit, squash, and rebase merge methods… The resulting commit history is the
same as merging each pull request individually, starting from the bottom.")

### Step 2: Retarget the downstream PR yourself

```bash
gh pr edit <downstream> --base main
```

For a manual stack GitHub will not do this for you.

### Step 3: Re-run and confirm the downstream CI against the new base

```bash
gh pr checks <downstream>
```

The base changed, so the checks must be read again — a green run against the old base
says nothing about the new one.

### Step 4: Only now delete the upstream branch

```bash
git push origin --delete <upstream-branch>
```

…after confirming that Step 0's listing no longer shows any open PR using it.

### Recovery, when the PR is already closed

**Open a new PR from the same head branch.** The commits were never lost; only the PR
object was.

```bash
git fetch origin
git worktree add ../scratch-pr origin/<head-branch>
cd ../scratch-pr
git rebase origin/main                     # optional: replay onto the new base
git push origin HEAD:recovered/<name>
gh pr create --base main --head recovered/<name> --title "..." --body "..."
```

Check what the replacement PR would actually contain before pushing it — a rebased
branch can carry more than the original PR intended:

```bash
git merge --no-commit --no-ff origin/main
git status --short        # must list only the files this PR meant to change
```

## Verification

**Before any stacked merge** — no open PR may use the branch you are about to delete:

```bash
gh pr list --state open --json number,baseRefName --jq '.[] | select(.baseRefName != "main")'
# → empty output
```

**After the upstream merge, before deleting the branch** — the downstream PR must still
be open and already moved:

```bash
gh pr view <downstream> --json state,baseRefName,mergeable
# → {"state":"OPEN","baseRefName":"main","mergeable":"MERGEABLE"}
```

**After the branch is deleted** — nothing is left pointing at a branch that is not the
trunk:

```bash
gh pr list --state open --json number,baseRefName --jq '.[] | select(.baseRefName != "main")'
# → empty output
```

**After a recovery** — the replacement PR must be mergeable and touch only its own files:

```bash
gh pr view <new-pr> --json state,mergeable,files
# → state=OPEN, mergeable=MERGEABLE, and files[] is the same set the closed PR had
```

## Notes

- GitHub's **native stacked pull requests** (public preview, 2026) do retarget
  automatically, and their merge API is asynchronous. They also state: "If you merge via
  the API and want to use stacked pull requests, you'll need to use the asynchronous merge
  API for stacks." A hand-made stack — where the base is simply another PR's head branch —
  is not the same thing, and none of the retargeting guarantees apply to it.
- The lesson is not "don't use `--delete-branch`". It is: **the flag is safe only when
  no other open PR references the branch**, and that fact lives in one field
  (`baseRefName`) that is one command away.

## References

- [Deleting and restoring branches in a pull request](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/deleting-and-restoring-branches-in-a-pull-request)
  — "You cannot delete branches that are associated with open pull requests… you can delete
  a branch that is associated with a pull request if the pull request has been merged or
  closed and there are no other open pull requests referencing the branch."
- [About stacked pull requests](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)
  — the retargeting behaviour described above belongs to GitHub's own stacks; and "If you
  merge via the API and want to use stacked pull requests, you'll need to use the
  asynchronous merge API for stacks."

## Meta lesson

> **A destructive flag whose UI equivalent has a safety check is the dangerous kind.**
> GitHub hides the button; the API that backs it does not check. The CLI calls the API.

> **"Merged successfully" is a statement about the PR you named** — not about the PRs
> that depended on it. In a stack, the damage lands somewhere else, seconds later.

> **Before an operation that deletes something, ask which other objects point at it.**
> The answer was already written down, in the downstream PR's `baseRefName`.
