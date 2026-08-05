---
{
  "domain": "growth",
  "title": "Two Evidence Loops for Failure Lessons",
  "tags": ["evidence", "lessons", "reuse", "growth", "feedback"],
  "status": "published",
  "source": "generalized maintainer retrospective",
  "created": "2026-07-17",
  "confidence": "0.90"
}
---

## Problem

A failure-lesson project can undercount real value if it only treats public feedback signals as proof of reuse. Helpful votes, feedback issues, and usage reports are important, but some lessons have already been reused before they are published.

This creates a misleading conclusion:

> `helpful_votes = 0`, therefore no lesson has ever helped anyone.

That may be true for public post-publication evidence, but false for source evidence.

## Root Cause

There are two different evidence loops:

| Loop | What it proves | Example signals |
|---|---|---|
| Pre-ingest reuse | The lesson came from a real failure and a real fix before publication | maintainer-side reuse, colleague memory dump, field debugging notes, PR repair record |
| Post-publication usefulness | The public lesson helped a new user after publication | helpful vote, feedback issue, usage report, external citation |

Mixing these loops causes bad strategy. If you only chase public votes, you may ignore high-value private or messy knowledge sources. If you only trust source evidence, you may overclaim public adoption.

## Solution

Track both loops separately.

### 1. Add source evidence when a lesson is ingested

```yaml
evidence:
  level: "pre_ingest_reused"
  source_type: "maintainer_reuse"
  verified_by: "maintainer"
  public_quote_allowed: false
```

Useful evidence levels:

```text
draft
self_tested
pre_ingest_reused
post_public_feedback
independently_reproduced
```

### 2. Keep public usefulness metrics separate

Do not merge helpful votes with source evidence. Helpful votes answer a different question:

```text
Did this published lesson help a new user later?
```

Pre-ingest evidence answers:

```text
Was this lesson distilled from a real failure and a working fix?
```

### 3. Use precise release wording

Bad:

```text
No helpful votes means no evidence of value.
```

Better:

```text
Public post-publication reuse is not yet proven. Several lessons have pre-ingest reuse evidence from real debugging sessions and maintainer-side reuse.
```

## Verification

- At least one lesson has explicit `evidence.level` metadata.
- Release notes distinguish source evidence from public usefulness.
- Public claims do not imply adoption unless there is external post-publication evidence.

## Next Agent Prompt

When reviewing a lesson repository, ask two questions separately:

1. What proves this lesson came from a real failure?
2. What proves this published lesson helped someone new?
