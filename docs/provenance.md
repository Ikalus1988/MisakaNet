# Lesson Provenance Tracking

## What is provenance?

Every lesson in MisakaNet can have a `provenance` field in its frontmatter that tracks where it came from, who contributed it, and how it was verified.

## Provenance fields

| Field | Type | Description |
|---|---|---|
| `source` | string | Where the lesson came from |
| `contributor` | string | Who contributed it (GitHub username or "unknown") |
| `merged_at` | string | When it was merged (YYYY-MM-DD) |
| `original_issue` | string | Related issue number (optional) |
| `evidence` | string | Evidence level for the lesson |

## Source types

| Source | Description |
|---|---|
| `agent-debugging` | From agent debugging sessions |
| `agent-memory-dump` | From agent memory dumps |
| `colleague-memory` | From colleague verbal descriptions |
| `manual` | Manually written |
| `unknown` | Source not tracked |

## Evidence types

| Evidence | Description |
|---|---|
| `pre-ingest-reuse` | Lesson was used before being added to MisakaNet |
| `pr-merged` | Lesson came from a merged PR |
| `common-pattern` | Common pattern observed multiple times |
| `common-pip-issue` | Common pip/Python issue |

## Example

```yaml
---
title: "pip install timeout fix"
domain: "devops"
provenance:
  source: "agent-memory-dump"
  contributor: "unknown"
  merged_at: "2026-07-06"
  evidence: "common-pip-issue"
---
```

## How to add provenance

1. Add the `provenance` block to the lesson's frontmatter
2. Fill in at least `source`, `contributor`, `merged_at`
3. If the lesson came from an issue, add `original_issue`

## Why track provenance?

- **Trust**: Know where lessons come from
- **Quality**: Lessons with evidence are more trustworthy
- **Attribution**: Credit contributors
- **Debugging**: Trace issues back to their source
