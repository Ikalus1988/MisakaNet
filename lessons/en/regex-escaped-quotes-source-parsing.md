---
title: "Regex Trap — Escaped Quotes in Source Code Cause Premature Non-Greedy Match Termination"
domain: development
tags:
  - regex
  - python
  - source-parsing
  - escape-sequences
  - debug
status: published
source: practical-experience
confidence: 0.9
created: 2026-07-07
lang: en
---

## Problem

When using regex to extract default values from Python source code like `os.environ.get("KEY", "default_value")`, the extraction gets truncated:

```python
source = 'exclude = os.environ.get("EXCLUDE_CHARACTERS", "/@\\"'+:?&!=% ")'
# Actual default: /@"'+:?&!=%  (contains escaped quote \")
# Regex extracts: /@\  (stops at \")
```

## Root Cause

The standard non-greedy regex `(["'])(.*?)\1` fails at `\"` because:

1. `(.*?)` matches up to `/@\`
2. Next character is `"` (the escaped quote after `\`)
3. `\1` backreference matches this `"` (because it IS a `"` character)
4. Regex stops here, ignoring the rest `'+:?&!=% "`

The regex doesn't know `\"` is an escape sequence — it just sees a `"` character.

## Solution

Replace `.` with `[^\\]|\\.` to skip escaped characters:

```python
# ❌ Breaks on escaped quotes
pattern = r'(["\'])(.*?)\1'

# ✅ Handles escaped quotes
pattern = r'(["\'])((?:[^\\]|\\.)*?)\1'
```

The `(?:[^\\]|\\.)` means: match either a non-backslash character, OR a backslash followed by any character. This correctly skips `\"`, `\\`, and other escape sequences.

## Verification

```python
import re

source = 'os.environ.get("KEY", "/@\\"'+:?&!=% ")'
pattern = r'(["\'])((?:[^\\]|\\.)*?)\1'
match = re.search(pattern, source)
print(match.group(2))  # /@"'+:?&!=% 
```

## Notes

- This pattern works for any escape sequence: `\"`, `\\`, `\'`, `\n`, etc.
- For multi-line strings, add `re.DOTALL` flag
- For production code, consider using a proper parser instead of regex

## Source

Translated from Chinese lesson by zsxh1990.
