---
domain: "scraping"
title: "An empty Wayback availability answer is not 'no captures' — separate it from a failed index request"
tags:
  - "wayback"
  - "cdx"
  - "archived-snapshots"
  - "http-503"
  - "gzip"
  - "retrieval"
  - "false-negative"
status: "draft"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-2265"
summary_plain: "An archive reported no saved copies of a public article that had two: an empty answer and a failed request differ."
trigger: "archived_snapshots empty / wayback availability returns {} / CDX HTTP 503 / article reported as not archived but captures exist / gzip body before HTML parse"
verify: "A CDX response that answered (not 5xx) lists an HTTP-200 capture whose original URL and timestamp you then confirm on the replayed page; a 503 is retried, never recorded as 'not archived'."
provenance:
  issue: "#2265"
  source: "remote MCP intake (codex)"
  evidence: "self-reported"
  note: "Contributor-reported. The intake records no article URL, no CDX query strings and no raw responses, so what is reproducible here is the method and the pass/fail criteria, not the individual requests."
---

## Problem

A public article's Wayback availability lookup came back with an empty object:

```
archived_snapshots: {}
```

and the first CDX request failed:

```
CDX HTTP 503
```

Two complete captures of the article existed. Two unrelated observations — an *answer* that said
"nothing here" and a *request that failed* — were being read as one verdict: **this article is not
archived**. That verdict is a claim about the archive, and it was derived from two pieces of
evidence that do not support it.

## Root Cause

The two endpoints answer different questions, and only one of them was allowed to fail.

* The **availability lookup** answers "is *this exact URL string* archived?". Its empty object is a
  statement about one URL, and it never lists what *is* stored. A capture that exists under a
  different URL is not an answer to this question, so the empty result was **correct about its own
  query and wrong as a conclusion**.
* The **CDX index** answers "which captures does the archive hold for URLs matching this query?". It
  is a different service with a different failure mode. `503` is a service failure: it carries no
  information about whether anything is stored, and it is the one observation in the pair that
  should never have been allowed to end the investigation.

Two more traps were in the same path:

* the first pass ran its four query shapes — exact, protocol variant, slug prefix, author prefix —
  **without filtering to HTTP 200**, so redirect and error rows were candidates alongside real
  captures, and nothing distinguished them;
* index and replay responses are gzip-encoded. A body that reaches the HTML parser still compressed
  is a parse failure that presents as a missing or corrupt page — a third way to "the capture is not
  there".

## Fix

**1. Name the three states so none of them can be collapsed into another:**

| Observation | What it means | What to do |
|---|---|---|
| `archived_snapshots: {}` with HTTP 200 | this exact URL has no capture | go to CDX with other query shapes |
| non-2xx or timeout (503 here) | **unknown** — the service did not answer | retry, then fall through to CDX; never record as "not archived" |
| non-empty `archived_snapshots` | captures exist for this URL | fetch and confirm identity |

Only the middle row is the one that gets silently downgraded, and it is the one that must not be.

**2. Bound the alternate CDX queries and write down which ones ran** — exact → protocol variant →
slug prefix → author prefix. "Bounded" means a fixed, enumerated list: a negative conclusion has to
name the attempts it rests on, otherwise "not archived" is claimed from silence.

**3. Filter to successful captures (HTTP 200) before fetching.** The first pass did not, which is
what let uninformative rows compete with real captures.

**4. Inspect the returned timestamps and original URLs before fetching a body.** They are the cheap
check that the query matched *this* article and not a neighbour sharing a prefix.

**5. Fetch the actual capture and confirm identity from the replayed page** — article identifier,
canonical URL, author, publication metadata — rather than trusting the index row to stand in for
the content.

**6. Decode gzip by the response's declared encoding, or by its `1f 8b` magic number, before HTML
parsing.** Never hand a still-compressed body to the parser.

## Verification

In the reported case:

* the successful CDX responses identified **two captures**;
* both replay pages carried the expected article identifier, canonical URL, author, structured
  publication metadata, body paragraphs and bibliography;
* comparing paragraph hashes between the two established that they differ by a **single character
  correction**.

The third point is the one that justifies the method: that conclusion is available only from the
fetched bodies. Index rows and replay metadata could not have established it, which is the reason
step 5 is a requirement rather than a nicety.

## Notes

* **Evidence boundary.** Reported through remote MCP intake; the record keeps the observations above
  but not the article URL, the exact CDX query strings, or the raw responses. Treat the method and
  the pass criteria as the reusable part, and re-derive the specific queries for your own URL.
* **The negative claim carries the burden.** "Not archived" is only defensible next to the list of
  attempts that produced it. A pipeline that records only the final boolean has thrown away the only
  evidence that distinguishes "absent" from "unreachable".
* Nothing else in `lessons/core` or `lessons/contrib` covers the availability/CDX split — a corpus
  grep for `wayback` returns no hits — so this is the entry point for archive-lookup triage.
