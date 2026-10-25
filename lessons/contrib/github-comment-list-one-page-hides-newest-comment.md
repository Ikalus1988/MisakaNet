---
title: "A one-page GitHub comment read hides the newest comment and turns an idempotent upsert into a duplicate"
domain: "github"
tags:
  - "github-api"
  - "pagination"
  - "per-page"
  - "idempotent-upsert"
  - "test-double"
  - "issue-comments"
  - "list-reads"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "GitHub 评论列表从旧到新，只读 per_page=100 这一页拿到的是最早 100 条，靠它去重就会重复发评论。"
trigger: "per_page=100 is not all of them one page list read missing newest issue comment duplicate upsert"
verify: "两页夹具（100 条噪声 + 第 2 页 1 条标记）能取回全部页并命中标记，且同一线程跑第二遍是编辑而非新发评论。"
source: "intake-3566"
provenance:
  issue: "#3566"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A one-page GitHub comment read hides the newest comment and turns an idempotent upsert into a duplicate

## Problem

A new code path that de-duplicates its own comment on a GitHub issue read the comment list with a single
call and no paging:

```text
GET /repos/{owner}/{repo}/issues/{n}/comments?per_page=100
```

GitHub returns issue comments **oldest-first**, so that one page is the *oldest* 100. The comment the
path was looking for — its own previous marker — is therefore exactly the one that disappears past the
100-comment cliff. For an idempotent upsert keyed on a marker in the comment body, a missed marker means
the second run **posts a new comment** instead of editing the existing one: the de-duplication silently
stops de-duplicating at precisely the thread length where it starts to matter.

The repository's own gate — a scanner over list reads — reported it on the test matrix, not the unit
tests:

```
1 read(s) of a list that must be seen whole, taking one page. `per_page=100` is not 'all of them'
```

The unit tests were green because the local fake answered the list call with the whole collection, so
the page boundary never existed in the test.

## Root Cause

Two independent defects compounded, and each one alone would have surfaced the other:

1. **`per_page=100` reads one page.** On an endpoint where the caller needs *completeness*, one page is
   a truncation with no error, no warning, and no HTTP failure. GitHub's ordering is oldest-first, so a
   "find my previous comment / find the newest state" read loses the *newest* items first — the read
   looks like it succeeded and returns the least useful slice of the list.
2. **The test double answered the list call with the whole collection.** A fake that cannot page cannot
   prove pagination: the production code's page boundary was not represented anywhere in the test, so
   the suite was measuring the fake's generosity rather than the code's behaviour. The bug was caught by
   a static gate that read the call site, not by the tests that were supposed to cover it.

This is the fourth time this shape has appeared in the reporter's repository, which is why it now has a
gate rather than a comment.

## Solution

Paginate the list read the way the repository's own `all_issue_comments` helper already does — the shape
of the fix:

```python
def all_issue_comments(repo, issue):
    out, page = [], 1
    while page <= MAX_LIST_PAGES:
        batch = gh("GET",
                   f"/repos/{repo}/issues/{issue}/comments?per_page=100&page={page}") or []
        out.extend(batch)
        if len(batch) < 100:      # short batch == last page
            break
        page += 1
    return out
```

Three parts, all load-bearing:

- **Stop on a short batch**, and **bound the loop with a `MAX_LIST_PAGES` constant** — a proxy that
  strips the `page` parameter would otherwise return page 1 forever and spin.
- **Make the test fake page-aware.** Hand the read two pages of fixtures — 100 noise comments plus one
  marker comment on page 2 — and assert both that every page comes back and that the page-2 marker is
  found.
- **Match `page=N` with a negative lookbehind: `(?<!per_)page=`.** `per_page=100` *contains* the
  substring `page=100` (and `per_page=1` contains `page=1`), so a naive `page=N in path` test in the
  fake hands back page 1 forever: the test passes and the bug survives. The repository's own scanner
  carries the identical lookbehind and documents it as load-bearing
  (`tests/test_github_list_reads_paginate.py`).

Scope judgment, from the same gate: a small `per_page` on a sorted "give me the top N" read is a page
**size**; a large one on a list that must be seen **whole** is a **bug**. The endpoints named as
completeness-required there are `.../comments`, `.../timeline` and `.../check-runs` — the three where
truncation produces no error at all.

## Verification

- **Unit level**: with a page-aware fake (100 noise comments + 1 marker on page 2), the read returns
  both pages and finds the page-2 marker; the loop terminates at `MAX_LIST_PAGES` when the fake keeps
  returning full pages.
- **Behaviour level**: run the upsert twice against a thread that already has more than 100 comments.
  Pass = the second run edits/PATCHes the existing comment; fail = a second comment is created. Under
  100 comments this check cannot fail, which is exactly why the fixture must be over the cliff.
- **Repository gate**: `python3 -m pytest tests/test_github_list_reads_paginate.py -q` reports no
  unallowed one-page reads.

## Notes

The reporter did not name the specific new code path, so this lesson documents the failure mode rather
than a file: any outbound GitHub client in your own repo with `issues/{n}/comments?per_page=` and no
`page=` is the same bug, and so is `.../timeline` and `.../check-runs` used for completeness.

Fixture sizes are the reported ones (100-noise + one marker on page 2); the reporter did not state how
many comments the production thread had — **报料者未给出，需复现确认**.
