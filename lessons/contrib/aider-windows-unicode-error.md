---
{
  "title": "Aider --show-repo-map crashes on Windows with UnicodeEncodeError",
  "domain": "devops",
  "tags": [
    "aider",
    "windows",
    "unicode",
    "encoding",
    "gbk"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "intake",
  "created": "2026-08-22",
  "author": "unknown",
  "edited_at": "2026-08-22T05:38:32.870881+00:00",
  "merged_by": "unknown"
}
---

## Problem

Aider --show-repo-map crashes on Windows with UnicodeEncodeError (gbk codec) when repo contains unicode characters in file paths.

## Root Cause

Windows default encoding is GBK, which can't handle all Unicode characters in file paths.

## Solution

Set UTF-8 encoding before running Aider:
```bash
set PYTHONIOENCODING=utf-8
aider --show-repo-map
```

Or use PowerShell:
```powershell
$env:PYTHONIOENCODING = "utf-8"
aider --show-repo-map
```

## Key Points

- Windows GBK encoding causes UnicodeEncodeError
- Set PYTHONIOENCODING=utf-8 before running
- Alternative: use WSL for Unicode-heavy repos
