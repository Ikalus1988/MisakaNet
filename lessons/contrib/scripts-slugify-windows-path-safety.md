---
{"title": "scripts slugify Windows path safety", "domain": "scripts", "source": "agent", "status": "published", "tags": ["slugify", "windows", "path", "filename"], "created": "2026-05-30 20:40:00 UTC", "updated": "2026-05-30 20:40:00 UTC"}
---

## Problem

The `scripts/new_lesson.py` lesson generator used the raw slug as the Markdown filename stem after replacing unsupported title characters. Titles made only from slashes, emoji, or punctuation could collapse to an empty stem, and Windows-reserved names such as `CON` or `LPT1` could still become invalid filenames.

## Root cause

The original slugify path only lowercased, replaced non-word runs, stripped dashes, and truncated. It did not provide a fallback after sanitation, normalize Unicode compatibility forms, trim unsafe trailing filename characters, or disarm reserved Windows basenames.

## Fix

The slugify wrapper now normalizes titles with the Python standard library, collapses separator runs, trims unsafe edges, falls back to `lesson` for empty sanitized titles, and appends `-lesson` to reserved Windows names.

## Verification

`python tests/test_new_lesson_slugify.py` verifies slash/backslash replacement, symbol-only fallback, Windows reserved name handling, and long-title truncation. `python search_knowledge.py "slugify windows path"` finds this lesson card.
