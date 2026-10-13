---
domain: "automation"
title: "Enforce intake text cap and fragment body assembly verification in digest pipelines"
tags:
  - "intake"
  - "digest"
  - "truncation"
  - "fragment"
  - "pipeline"
status: "published"
evidence_level: "E1"
summary_plain: "处理超长工单摘要时需设定字符阈值上限并验证段落重组完整性，防止索引内存溢出。"
trigger: "Intake text cap exceeded fragment assembly corrupted"
verify: "python -m pytest tests/test_intake_text_cap.py 退出码为 0"
---

# Enforce intake text cap and fragment body assembly verification in digest pipelines

## Problem

Ingesting raw question intakes with unbounded body lengths causes memory bloat and malformed fragment assemblies during document digest generation.

## Root Cause

Absence of an explicit maximum payload threshold allows oversized inputs to bypass deduplication filters, resulting in incomplete Markdown AST serialization.

## Solution

Implement an upper bound clamp (e.g. 10,000 characters) on intake bodies and validate balanced markdown formatting before persisting.

### Step 1: Implement length capping
```python
MAX_INTAKE_CHARS = 10_000

def sanitize_intake_body(raw_text: str) -> str:
    trimmed = raw_text.strip()
    if len(trimmed) > MAX_INTAKE_CHARS:
        return trimmed[:MAX_INTAKE_CHARS] + "\n\n[Truncated for length]"
    return trimmed
```

### Step 2: Validate markdown fragment assembly
Verify headers, code fences, and frontmatter blocks close symmetrically before appending to the digest pool.

## Verification

Pass payloads exceeding 20,000 characters through the ingestion parser and verify clean truncation without syntax corruption.
