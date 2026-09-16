---
{
  "title": "Provenance gate red-team probe (must never be merged)",
  "domain": "devops",
  "tags": ["provenance", "gate", "redteam"],
  "status": "draft",
  "lang": "en",
  "evidence_level": "E3",
  "source": "https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652",
  "created": "2026-09-16",
  "updated": "2026-09-16"
}
---

## Problem

This pull request exists only to prove that the provenance gate fires in CI, and it must
never be merged. Every other check is meant to pass on it, so that a red build can only come
from the provenance job — which is the property worth verifying, because a gate that is only
tested locally is a gate nobody has seen work.

## Root Cause

A corpus that cannot tell a real citation from an invented one cannot keep the promise its
value rests on, and reading every pull request by hand does not scale past a few hundred
lessons. The citation in this file is copied verbatim from four real pull requests (#1713,
#1714, #1715, #1716), each of which passed every check this repository had at the time.

## Solution

Open the checks on this pull request: the Provenance Gate job fails with
`source does not resolve ... HTTP 404`, while the Lesson Quality Gate passes on the same file.
That is the evidence that the two are independent and that the new one is what caught it.

## Verification

After the provenance job goes red, this file and its branch are deleted; no trace is meant to
remain in the corpus. The structural gate passing on the same file is part of the evidence.
