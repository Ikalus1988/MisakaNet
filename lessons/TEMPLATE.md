---
domain: "general"
title: "<English Title>"
status: "draft"
verification: "metadata-normalized"
{"title": "<English Title: 4-120 chars>", "domain": "<domain>", "tags": ["tag1", "tag2", "tag3"], "status": "published", "confidence": "0.9", "created": "<YYYY-MM-DD>", "updated": "<YYYY-MM-DD>", "source": "<your-source>", "verified_date": "", "domain_expert": ""}
---

# <English Title>

## Problem

<!-- What went wrong? What was the symptom? Be specific. -->

## Root Cause

<!-- Why did it happen? Include technical detail. -->

## Solution

<!-- How to fix it. Include commands, config, or code. -->

### Step 1

### Step 2

### Step 3

## Verification

<!-- How to confirm the fix works. -->

## Notes

<!-- Caveats, edge cases, related lessons. -->

---

### Template Rules

| Rule | Standard | Reason |
|------|----------|--------|
| **Filename** | `kebab-case-english.md` | No Chinese, no project prefixes |
| **Frontmatter** | JSON inside `---` | Must parse with `json.loads()` |
| **Required fields** | `title`, `domain`, `status` | Schema enforcement |
| **Tags** | 1-10 tags, 2+ chars each | BM25 retrieval |
| **Section order** | Problem → Root Cause → Solution → Verification | Consistency |
| **Code blocks** | Language-specified fenced blocks | Syntax highlighting |
| **Paths** | `<placeholder>` not `/home/user/...` | Portability |
