# Confidence Judgment Archive

This directory contains intake issues that need human review before being converted to lessons.

## Purpose

1. **Preserve potential lessons** — Issues with score 40-74 that have value but need verification
2. **Enable search** — Content is indexed for BM25 search
3. **Gather feedback** — Track user reactions to improve confidence
4. **Re-evaluate** — Automatically re-score when algorithms improve

## Directory Structure

```
confidence-judgment/
├── README.md                 # This file
├── index.json               # Index of all archived issues
├── {issue-number}/          # One directory per issue
│   ├── intake.md           # Original intake content
│   ├── metadata.json       # Scoring details
│   └── feedback.md         # Feedback log
```

## How It Works

### Auto-Archive (score 40-74)

When an intake issue receives a score between 40-74, it is automatically archived here with:

- `intake.md` — The original content
- `metadata.json` — Detailed scoring breakdown
- `feedback.md` — Template for collecting feedback

### Search Integration

Archived content is indexed by `search_knowledge.py` and can be found via:

```bash
python3 search_knowledge.py "your search query"
```

Results from this archive are marked with `evidence_level: E0` (unverified).

### Re-evaluation Triggers

Issues are re-evaluated when:

1. **Algorithm updates** — New scoring model released
2. **User feedback** — Comments like "useful" or "resolved"
3. **Related lessons** — Similar content gets approved
4. **Time-based** — After 30 days without feedback

### Promotion to Lessons

An issue is promoted to `lessons/contrib/` when:

- Confidence score >= 80
- At least one positive user feedback
- Or similar lesson gets approved

### Archival to Badcase

An issue moves to `badcase/` when:

- 30 days pass without feedback
- Re-evaluation still scores < 40

## Feedback Format

Add feedback entries to `feedback.md`:

```markdown
| Date | User | Action | Notes |
|------|------|--------|-------|
| 2026-08-24 | @username | useful | This solved my problem |
```

## Maintenance

- **Weekly**: Review new additions
- **Monthly**: Check for stale items
- **Quarterly**: Clean up duplicates
