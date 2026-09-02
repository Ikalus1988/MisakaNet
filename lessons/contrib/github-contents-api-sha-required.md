---
title: GitHub contents API edit fails with 422 without the file sha
domain: development
tags:
- github-api
- automation
- rest-api
- file-edit
- scripting
status: published
created: 2026-08-11 00:00:00 UTC
updated: 2026-08-11 00:00:00 UTC
evidence_level: E2
---

# GitHub contents API edit fails 422 when the file `sha` is missing

## Problem

A script that updates existing files in a repository through the REST contents API started failing with `422 Validation Failed` and a body that only mentioned `"sha" wasn't supplied`. The script treated edits like an initial create and sent only `message` + `content`.

## Root cause

The GitHub contents API (`PUT /repos/{owner}/{repo}/contents/{path}`) changes behavior depending on whether the file already exists:

- **Create:** only `message` + `content` (+ `branch`) needed.
- **Update:** must also include the current blob `sha` of the file being overwritten. Omitting it produces exactly that `422` with `"sha" wasn't supplied` — misleading because a create with the same three fields would succeed.

GitHub uses this as an optimistic-concurrency guard: writing the `sha` you fetched ensures you are not silently overwriting a newer version.

## Failure & recovery

The check run reported the HTTP error but not the fix location, so the diagnostic loop stalled until the response body was inspected. The recovery, which succeeds in one round trip each time:

1. `GET /repos/{owner}/{repo}/contents/{path}` (optionally with `?ref={branch}`).
2. Extract `sha` from the response. When importing with Base64, decode `content` carefully (GitHub returns Base64; re-encoding must match exactly).
3. `PUT` the same endpoint with `message`, `content`, `branch`, `sha`.

## Reusable pattern

Write a small `update(path, content)` helper that always fetches the current `sha` first. It makes create and update uniform and self-healing: if the file is new, `sha` is simply absent, so pass it only when present.

## Lesson

For file mutations via the contents API: fetch-then-write with `sha` is the rule. The 422 body is the hint — read it before changing the strategy.


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