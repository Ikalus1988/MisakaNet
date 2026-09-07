---
title: mergeable_state blocked does not mean failing CI
domain: development
tags:
- github
- ci
- pull-request
- merge-queue
- workflow
status: published
created: 2026-08-11 00:00:00 UTC
updated: 2026-08-11 00:00:00 UTC
evidence_level: E2
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# `mergeable_state: blocked` does not mean failing CI

## Problem

After pushing a fix, the GitHub API reported `mergeable_state: blocked` on the pull request and all attention (and worry) shifted to "why is my PR blocked". In fact the branch had no failing checks at all.

## Root cause

The PR API field `mergeable_state` has several values: `clean`, `dirty`, `has_hooks`, `unknown`, `blocked`, and `behind`. `blocked` does **not** mean a check failed. It means the branch protection or merge settings prevent an automatic merge right now — most commonly a *required review* (human or bot) is still pending, or the branch is behind the base and needs an update.

## Failure & recovery

- The lesson validator in this very repo initially failed because the frontmatter was not JSON — that is a real, actionable failure and was the actual root cause of the red CI, not the `blocked` status.
- Mistaking `blocked` for a failing check sends you chasing a non-existent test failure. Fix is to read `statuses`/`check-runs` endpoints, not the summary field, to find whether anything truly failed.

## Use evidence, not vibes

Cross-check with the concrete evidence: `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` returns each check exactly, and `mergeable`/`mergeable_state` is only about whether the *merge button* can be used. A green `mergeable_state: clean` plus all-success checks is the only thing to rely on.

## What I do now

1. Never panic on `blocked`.
2. Always enumerate `check-runs` before concluding failure.
3. If a real check fails, fix the *content* the check validates — not cosmetic retries.

## Lesson

Separate "cannot merge right now" (reviews, behind) from "should not merge" (failed checks). The API summary tells you about the first; only the individual checks tell you about the second.


## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```