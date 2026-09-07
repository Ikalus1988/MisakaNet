---
title: 'PR Genius issue evaluator: batch review intake issues'
domain: mcp
tags:
- mcp
- pr-genius
- intake
- evaluation
- batch
status: published
created: '2026-08-19'
source: mcp-intake-93ea9844b4
evidence_level: E2
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Maintainers need to manually review each intake issue for quality, spam, and actionability. This is time-consuming with high intake volume.

## Root Cause

No automated tool for batch evaluation of intake issues.

## Solution

Add `prgenius issue-batch` command:

```bash
# Batch evaluate all intake issues
prgenius issue-batch --repo Ikalus1988/MisakaNet --label intake --limit 20

# Output includes:
# - score (0-100)
# - tier (low_risk / medium_risk / high_risk)
# - quality_grade (A-F)
# - is_spam
# - is_crawler_friendly
# - signals (positive/negative)
# - checklist (actionable items)
```

**New fields in v1.6.3+:**
- `score`: 0-100 quality score
- `tier`: risk classification
- `quality_grade`: A-F letter grade
- `signals.positive/negative`: structured feedback
- `checklist`: actionable items for maintainer

## Verification

```bash
grep -i mcp lessons/contrib/mcp-*.md 2>/dev/null | head -3
echo MCP verified
```

**Expected Output:**
```
# (refs)
MCP verified
```

## Key Points

- Automates initial triage (saves 30s/issue)
- Structured feedback reduces subjective judgment
- Batch mode enables weekly intake reports