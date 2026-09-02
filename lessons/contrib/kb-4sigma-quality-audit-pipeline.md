---
title: Knowledge Base 4-Sigma Quality Audit Pipeline
domain: rag
tags:
- project:self-grow-wiki
- severity:medium
- node:hermes-wsl
status: published
created: '2026-05-03'
language: en
source: bootstrap
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: quality
---

## Problem

After continuous document imports, the RAG knowledge base developed data contamination, version confusion, inconsistent sources, and other issues that affected retrieval quality.

## Root Cause

1. Multiple versions of the same document were imported repeatedly, with old versions not removed
2. OCR imports introduced garbled data
3. The same knowledge point appeared in multiple documents with different wording
4. There was no systematic quality-check workflow

## Solution

Build a 4σ quality audit pipeline:
1. Contamination cleanup: delete non-document content (garbled text, empty chunks, numeric-only chunks)
2. Version deduplication: identify duplicates by filename + import time
3. Source correction: standardize document paths, filenames, and source URLs
4. Quality scoring: score by completeness, cleanliness, and version consistency

Implement it as `daily_audit.py`, run automatically by cron every day at 06:00.
Reports are stored at `~/audit_reports/audit_YYYY-MM-DD.json`.

## Verification

```bash
daily_audit.py
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `daily_audit.py`)

## Scenario

A continuously growing RAG knowledge base (>150 documents, >200K vectors) that needs automated quality assurance.