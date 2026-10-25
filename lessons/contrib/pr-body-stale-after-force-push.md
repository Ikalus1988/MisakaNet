---
title: "A pull request body goes stale the moment you force-push a fix, and nothing signals it"
domain: "github"
tags:
  - "pull-request"
  - "force-push"
  - "code-review"
  - "documentation"
  - "process"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Force-push the fix and the PR description still describes round one, so reviewers read a version that no longer exists."
trigger: "PR description described an earlier version of the change after force-pushed fixes"
verify: "Every identifier named in the PR body must appear in the current diff, and every count it quotes must match the suite's current output."
source: "intake-2703"
provenance:
  issue: "#2703"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A pull request body goes stale the moment you force-push a fix, and nothing signals it

## Problem

A pull request description goes stale the moment you force-push a fix, and nothing signals it.
The reviewer reads a body that describes an earlier, worse version of the change — including, in
the worst case, a version that never had the bug the code now carefully avoids.

Observed on a PR that accumulated three rounds of fixes. The body was written for round one. By
round three it described a status filter that no longer existed and omitted a correctness bug
that had been found and fixed in the same PR. A reviewer would have had no way to know either
fact, and the commit messages alone do not carry the rationale a body is supposed to give.

```text
PR description described an earlier version of the change after three rounds of force-pushed fixes
```

The repository and PR number were not given by the reporter; reproduce against a live PR.

## Root Cause

Force-push replaces commits; the description is a separate artifact and is not versioned with
them. Everything that drives the change — review findings, CI failures, adversarial verification —
happens *after* the body is written, and each fix is a local commit plus a push. The body is only
ever updated when someone remembers to.

It is worst exactly when the work is good: a PR that absorbs review feedback and gets *better* is
the one whose body is furthest from its code.

## Solution

**Treat "push a fix" as a trigger to re-read the body.** Before every push that changes
behaviour, ask: what does this PR's body claim that is no longer true?

Two mechanical habits:

- **Append, do not rewrite.** Add a dated section for each round of fixes, naming the defect, the
  reason and the verification output. That keeps the history honest and is far cheaper than
  re-deriving the whole description.
- **Quote the numbers that changed.** If a test count, a coverage figure or a measured result
  moved, the body must move with it. A body quoting `80 passed` when the suite says `92` is not a
  typo — it is a different claim.

```bash
# before pushing a fix, diff the claims against reality
gh pr view "$N" --repo owner/repo --json body -q .body > /tmp/body.md
grep -nE 'pass [0-9]+|fail [0-9]+|coverage|exits [0-9]' /tmp/body.md
# then re-run each claim and compare it with the actual output
```

The reporter's command block is cut off after this point (`# t…`); the remaining procedure was
not given and needs to be reproduced.

## Verification

Reporter's criterion: grep the body for the symbols and counts it claims, re-run them, and
confirm that every identifier named in the body appears in the current diff. A body that names a
symbol the diff no longer contains, or quotes a count the suite no longer produces, is stale —
and it is stale in the direction that wastes a reviewer's attention, because the reviewer will
look for code that is not there.
