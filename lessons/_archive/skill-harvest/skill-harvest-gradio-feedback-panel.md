---
domain: "archive"
title: "Gradio Feedback Panel"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## 背景

（此 lesson 从 skill `gradio-feedback-panel` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Gradio Feedback Panel for RAG Web UI

Add a complete user feedback management system to a Gradio-based RAG web application. Collects thumbs-up/down, tracks category errors, displays statistics, and lists problematic queries — all from a single SQLite database.

## Architecture

```
rag_core.py                  rag_web.py
 ┌─────────────────┐         ┌─────────────────────┐
 │ log_feedback()   │◄───────│ submit_feedback_up()│
 │ get_feedback_stats()─────►│ submit_feedback_down│
 │ get_feedback_list()       │ show_feedback_panel │
 └─────────────────┘         └─────────────────────┘
        │                          │
        ▼                          ▼
  SQLite (feedback table)    Gradio Tab "反馈管理"
```

## Procedure

### 1. Add SQLite feedback queries in the core module

In `rag_core.py` (or equivalent core RAG module), add two functions:

**`get_feedback_stats(days=7)`** — returns dict with:
- `total`, `good`, `bad`, `wrong_category`, `satisfaction_rate`
- `by_type`: list of {feedback_type, count}
- `by_day`: daily trend {day, good, bad, wrong_cat, total}
- `bad_list`: recent bad/wrong_category feedback with comments

**`get_feedback_list(limit, offset, min_date, max_date, filter_type)`** — paginated feedback list with optional filters.

SQL queries pattern:
```python
# By feedback_type aggregation
conn.execute("SELECT feedback_type, COUNT(*) c FROM feedback WHERE ts >= ? GROUP BY feedback_type", (cutoff,))

# Bad queries detail (for review panel)
conn.execute("""SELECT fb.id, fb.ts, fb.query, fb.feedback_type, fb.feedback_text, fb.category, fb.sender
   FROM feedback fb WHERE fb.ts >= ? AND fb.feedback_type IN ('bad','wrong_category')
   ORDER BY fb.id DESC LIMIT 50""", (cutoff,))

# Daily trend
conn.execute("""SELECT substr(ts,1,10) AS day,
    SUM(CASE WHEN feedback_type IN ('good','up') THEN 1 ELSE 0 END) good,
    SUM(CASE WHEN feedback_type IN ('bad','down') THEN 1 ELSE 0 END) bad, ...
   FROM feedback WHERE ts >= ? GROUP BY day ORDER BY day""", (cutoff,))
```

Make sure the feedback table exists (created in `_init_log_db()`):
```sql
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
    query_id INTEGER REFERENCES query_log(id),
    query TEXT NOT NULL,
    feedback_type TEXT NOT NULL,   -- 'good'|'bad'|'wrong_category'|'other' (also 'up'/'down' for legacy)
    feedback_text TEXT,
    category TEXT,
    sender TEXT
);
```

### 2. Add feedback UI handlers in web UI module

In `rag_web.py`:

**`submit_feedback_up(query_id)`** — 👍 handler. Calls `log_feedback(int(query_id), "good", "", "")` from the core module (not kb_learning.json).

**`submit_feedback_down(query_id, comment)`** — 👎 handler. Calls `log_feedback(int(query_id), "bad", comment or "")`.

**`show_feedback_panel(days)`** — generates Markdown for the feedback tab:
- If no data: show instruction message
- If data: stats table (total, good, bad, wrong_category, satisfa

## 验证

（待补充）
