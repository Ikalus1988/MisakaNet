---
domain: "python"
title: "Python UnicodeEncodeError on Windows with GBK codec"
verification: "metadata-normalized"
---
---{"title": "Python UnicodeEncodeError on Windows with GBK codec", "domain": "python", "tags": ["python", "unicode", "gbk", "windows", "encoding"]}---

## Problem

Python script fails with `UnicodeEncodeError: 'gbk' codec can't encode character` when printing output containing emoji or non-ASCII characters on Windows.

## Root Cause

Windows console default encoding is GBK/CP936 (Chinese), which cannot encode characters outside its charset (e.g., emoji, special Unicode symbols). Python's print() uses the console encoding, causing the error.

## Fix

Call `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at the start of the script. This sets stdout to UTF-8 with 'replace' fallback for unencodable characters. If reconfigure() is unavailable (Python < 3.7), use `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')`.

## Verification

Run `python -c "import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace'); print('emoji test: ')😀"`. Should print without error.
