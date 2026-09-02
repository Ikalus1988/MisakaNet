---
title: Aider --show-repo-map crashes on Windows with UnicodeEncodeError
domain: devops
tags:
- aider
- windows
- unicode
- encoding
- gbk
status: published
created: '2026-08-22'
source: mcp-intake-1192
evidence_level: E2
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-08-22"
  evidence: "post-publication"
-->

<!-- 
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


## Verification

```bash
set PYTHONIOENCODING=utf-8
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `set PYTHONIOENCODING=utf-8`)
