---
{
  "title": "Agent read_file Silent Truncation in Multi-Brain Meeting Recovery",
  "domain": "agent",
  "tags": [
    "project:hermes-agent-cluster",
    "severity:high",
    "pattern:file-handling",
    "tool:read-file"
  ],
  "status": "published",
  "source": "ninghuagui-debug"
}
---

## Problem

A three-brain AI meeting system (大乔 proposals → 小乔 review → main fusion) writes meeting
agenda files to disk. When an agenda file gets corrupted mid-meeting, a repair agent reads
the file to reconstruct it.

The repair agent called `read_file("path/to/agenda.md")` and processed the result. It produced
a fused decision that looked correct — but was based on **incomplete data**. Content beyond
~15,000 characters was silently missing. The agent never noticed.

## Root Cause

`read_file()` has a built-in character cap, adjustable via `char_limit`, that truncates files
larger than the limit. It returns a head+tail window with this footer:

> ──────── [TRUNCATED] ────────
> Showing 11,198 chars (head) + 3,500 chars (tail) of 86,825 total clean characters.
> Full text saved to: /tmp/cache/...
> To read the omitted middle: read_file offset=...
> ─────────────────────────────

The repair agent's code read the result into a variable like `file_content = read_file(path).content`
and began processing. It never checked for the TRUNCATED marker. The truncated result was still
valid Markdown with all required sections (Problem / Root Cause / Fix / Verification) —
just incomplete. The agent had no reason to suspect data loss.

Three contributing factors:

1. **Silent success**: The truncation isn't an error. `read_file` returns `exit_code: 0` and
   valid-looking content.
2. **No size prefetch**: No one checked the file size before reading.
3. **Cursor blindness**: The agent didn't scan the returned text for truncation markers before
   using it for decision-making.

## Fix

The fix has three layers:

### Layer 1 — Paginated reading (repair agent)

Replace a single `read_file(path)` call with paginated reading:

```python
# Before: reads truncated
content = ""
page = read_file(path, offset=1, limit=500)
content += page.content
total = page.total_lines

offset = 501
while offset <= total:
    page = read_file(path, offset=offset, limit=500)
    content += page.content
    offset += 500
```

### Layer 2 — Size-aware prefetch

Before reading the file, check its size. If it exceeds the char_limit
threshold, paginate automatically.

```python
import os
size = os.path.getsize(path)
# read_file default budget is ~15K chars; if file is bigger, paginate
if size > 14000:
    # use paginated reading strategy
```

### Layer 3 — Agent instruction hardening

Add a system-level rule: **When reading any file, always check the last 200 characters
of the returned content for a TRUNCATED marker before using the data.** If found, paginate
and concatenate.

## Verification

Re-ran the repair on the same corrupted agenda file. The fused decision now contains
all three brains' opinions and references sections from the middle of the document
that were previously invisible. Output diff shows the same 8,432-character file being
fully consumed instead of the first 14,000 characters.

```bash
# Before: 14,000 chars processed (truncated)
grep -c "truncated" /tmp/repair_output.log  # → 0 (never detected)

# After: 86,825 chars processed (complete)
grep "小乔 意见" /tmp/repair_output.log  # → found (was missing before)
```

## Scenario

Any autonomous agent workflow where:
- Agenda, specification, or configuration files exceed ~15K characters
- File content is read once and used for decision-making
- The agent does not verify completeness before processing

This is especially dangerous in multi-agent pipelines where agent A writes
data that agent B reads, because neither agent knows about the truncation.
