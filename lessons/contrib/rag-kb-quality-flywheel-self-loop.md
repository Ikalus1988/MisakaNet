---
domain: "contrib"
title: "rag kb quality flywheel self loop"
verification: "metadata-normalized"
{"title": "RAG 知识库质量飞轮：自闭环建设", "domain": "rag", "tags": ["rag", "flywheel", "quality", "audit", "feedback", "self-learning"], "confidence": 0.92, "created": "2026-05-21", "domain_expert": "unknown", "verified_date": "2026-05-21"}
---

## Background

A vertical-domain RAG knowledge base (190+ PDFs, 200K+ vectors) was already online, supporting natural-language Q&A and daily automated inspections. However, issues found by inspections still had to be handled manually, so the whole loop lacked automation:

- Inspection failure → manually summarize into a badcase document → manually send to AI for repair
- No feedback channel when users are dissatisfied
- The synonym expansion table is empty, so some terms cannot be retrieved
- No queue management, making review progress untraceable

## Root Cause

The "flywheel" in the design document only covered the first half:

- The daily inspection concept exists (`daily_audit` is planned)
- Wrong-question aggregation exists (badcase records)
- But the self-learning module (`kb_learning.py`), review tool (`badcase_review.py`), and synonym file (`synonyms.json`) are all missing
- The code has imports but silently degrades with try/except, and the files were never created

## Fix

Implement a four-layer closed loop, where each layer can work independently:

### Layer 1: Synonym Expansion (`synonyms.json`)
- Create an independent JSON file with 32 groups of vertical-domain synonyms (alarms/servo/zero calibration/encoder, etc.)
- `rag_core.py` already has `_load_synonyms()`, which hot-loads incrementally by mtime
- Convention: keys that start with `_` are metadata and are filtered out; all other entries are automatically used by `expand_query()`

### Layer 2: Self-Learning Engine (`kb_learning.py`)
- `log_query(query, top_score, chunks_count)` matches the existing call in `rag_core.py`
- Automatically classify badcase thresholds: top_score < 0.45 is failure level; < 0.6 is warning level; chunks_count == 0 is empty retrieval
- Write to a JSONL queue file (`badcase_pending.jsonl`) with append support
- Provide approve/reject operations; approved items move to the approved queue and rejected items move to the rejected queue

### Layer 3: Daily Inspection (`daily_audit.py`)
- Stratified sample 7 questions from a 200-question bank (2 L2 + 5 L3, stratified by tag)
- Call the RAG API for live checks: keyword hits, minimum answer length, brand contamination, semantic gap
- Output a JSON report + Markdown summary + automatically append to `badcase_pending`
- `--cron` mode is for crontab, and the exit code reflects pass-rate status

### Layer 4: Review Tool (`badcase_review.py`)
- Five atomic CLI operations: list / show / approve / reject / auto
- `auto` automatically approves high-confidence badcases (empty retrieval, score < 0.3, "low-quality retrieval" features)
- Shares the same JSONL queue files with `kb_learning`

### Additional: IM Feedback Collection (WeChat Bot)
- Intercept "good" and "bad" feedback in the existing wxauto bot
- Track each user's previous question and associate feedback with the original query
- Call `kb_learning.add_feedback()` to write into the queue

## Verification

Data-flow validation:
- `daily_audit`: 7 questions, 2 failures, appends 2 entries to `badcase_pending.jsonl`
- User says "bad", appends 1 entry to `badcase_pending.jsonl`
- `badcase_review.py list` shows 3 pending items
- `badcase_review.py approve 1` moves the item into the approved queue
- `badcase_review.py auto` automatically approves low-score badcases

## File Structure

```
project_root/
  synonyms.json            Synonym table (auto-loaded by rag_core)
  kb_learning.py           Self-learning engine
  daily_audit.py           Daily inspection
  badcase_review.py        Review CLI
  audit_reports/
    badcase_pending.jsonl   Pending review queue
    badcase_approved.jsonl  Approved
    badcase_rejected.jsonl  Rejected
    audit_YYYY-MM-DD.json   Daily report
```

## Key Design Decisions

1. **JSONL instead of SQLite**: Queue files need to be read/written/edited by humans; JSONL is more transparent than SQLite
2. **Command mode instead of a daemon**: Review is a low-frequency operation, and a CLI is simpler and more reliable than a background service
3. **Layer independence**: Each layer can run independently; `rag_core`'s dependency on `kb_learning` is optional with try/except degradation
4. **Shared review queue files**: `daily_audit` and `add_feedback()` write to the same pending file, and `badcase_review` manages them centrally
