---
domain: "search"
title: "anysearch_batch_search rejects tag academic with HTTP 400 Invalid tag: academic"
tags:
  - "search"
  - "api"
  - "http-400"
  - "academic"
  - "crossref"
  - "anonymous-auth"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3821"
summary_plain: "Batch search with the tag academic is rejected with HTTP 400, so search by exact title or Crossref instead."
trigger: "Invalid tag: academic. anysearch_batch_search HTTP 400 under anonymous auth"
verify: "A title search returns the target ScienceDirect article, and the request no longer carries tag=academic (the 400 is gone)."
provenance:
  issue: "#3821"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# anysearch_batch_search rejects tag academic with HTTP 400 Invalid tag: academic

## Problem

Calling `anysearch_batch_search` with `tag: academic` under anonymous authentication failed on the
request, before any search ran:

```
HTTP 400 Invalid tag: academic.
```

The call produced no result set at all — not an empty list, not a partial result. The
reporter's note says the call was made with anonymous auth, which is the only configuration they
tested.

## Root Cause

**The failure is in the request, not in the index.** `Invalid tag` is parameter validation: the
server checked the `tag` value against its own allow-list and rejected it before executing the
query. That has two consequences worth separating:

- Retrying the same request cannot succeed. There is no transient condition to wait out; the same
  bytes will get the same 400.
- The absence of results says nothing about whether the index holds the paper. A 400 and a
  "no matches" outcome look similar downstream if the error is swallowed into the result list, and
  that is how a rejected parameter gets mistaken for "the search engine does not have it".

`academic` is not a value that allow-list accepts — the error text is the server stating that
directly. The intake does not record what the accepted values are, and does not establish whether
`academic` is rejected for every caller or only for anonymous ones; the reporter only exercised
anonymous auth. Both remain open questions rather than findings.

## Solution

### Step 1: do not send the rejected tag

Use a title search instead of a tag-filtered batch search. The tag is a filter over a corpus class;
when the filter value is rejected, the same target can usually be reached through the query text:

```
web_search: "<exact paper title>"
```

The reporter's working path was this one: a direct `web_search` by title, which retrieved the
ScienceDirect articles reliably.

### Step 2: use Crossref for bibliographic lookup

For a known title, Crossref answers the metadata question without depending on the search tool's
tag vocabulary:

```bash
curl -sS "https://api.crossref.org/works?query.bibliographic=<url-encoded+paper+title>&rows=3"
```

The response contains matching works with `DOI`, `container-title`, `issued` and `author`, which is
more than the tag filter was being used to obtain. From a DOI, the publisher page (including
ScienceDirect) is addressable directly.

### Step 3: treat a 400 from a search tool as a request-shape error

Do not fold the response into an empty result list. A batch search wrapper should surface the status
code and body:

```python
resp = client.batch_search(query=..., tag="academic")
if resp.status_code == 400:
    raise SearchRequestError(resp.status_code, resp.text)   # not: return []
```

The distinction matters for the caller: "0 hits" invites a different query, while
"400 Invalid tag" invites a different parameter.

### Step 4: get the accepted tag values before guessing another one

If tag filtering is required, take the allow-list from the tool's documentation or from a single
deliberate probe, and pass only values from it. Do not substitute a synonym (`scholar`, `paper`,
`journal`) and hope — the reporter did not record the accepted values, so any other tag is
unverified until it returns 200.

## Verification

The reporter's criterion: a direct `web_search` by the paper's exact title retrieves the
ScienceDirect articles reliably. That is the replacement path working, not the tag working.

Two additional checks that a reader can run:

1. The corrected request returns HTTP 200 with the expected work in the result set; no response in
   the path returns 400.
2. The wrapper reports a 400 as a request error rather than an empty result — feed it the original
   failing body and confirm the error surfaces instead of `0 results`.

The reporter did not include the exact request body or the tool's response beyond the error line, so
the behaviour with an authenticated caller and the full set of valid tags still need to be
confirmed by reproduction.

## Notes

- The same shape appears whenever a "tag" or "category" parameter is validated server-side: the
  failure is a 400 at the door, and the cost is that it is easy to misread as "nothing found".
- `academic` was likely being used to narrow the corpus to scholarly sources. Crossref (metadata) and
  a title search (discovery) cover that need without the tag, but they answer different questions:
  Crossref cannot tell you what a general web index contains.
- Evidence level E1: one anonymous caller's report, with the exact error text and a replacement path
  they verified; not reproduced in this repository.
