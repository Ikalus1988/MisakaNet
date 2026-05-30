---
{"title": "Slugify Windows path safe filenames", "domain": "scripts", "source": "agent", "status": "published", "tags": ["slugify", "windows", "path", "filename", "stdlib"]}
---

## Problem

`scripts/new_lesson.py` built lesson filenames directly from `_slugify(title)`. Titles with path separators such as `/` or `\\`, emoji-only text, control-style punctuation, or Windows reserved device names could produce unsafe or empty filename stems. On Windows or WSL boundaries, that means the path could be truncated, rejected, or collapse to a surprising file like `.md`.

## Root cause

The previous slugify logic only lowercased the title, replaced non-ASCII/CJK runs with `-`, stripped hyphens, and truncated. It did not normalize Unicode, guarantee a non-empty result, or guard against reserved Windows filename stems such as `CON`, `PRN`, `AUX`, `NUL`, `COM1`, and `LPT1`.

## Fix

Normalize titles with Python stdlib `unicodedata.normalize("NFKC", ...)`, collapse all filesystem-hostile runs to single hyphens, and return a stable fallback stem of `lesson` when sanitization removes everything. Prefix reserved Windows device names with `lesson-` before appending `.md`. Keep the implementation dependency-free and readable.

## Verification

Add regression tests for slash/backslash/emoji input, emoji-only fallback, and reserved Windows names. Verify that `python3 search_knowledge.py "slugify windows path"` finds this lesson so future agents can retrieve the Windows path filename lesson offline.
