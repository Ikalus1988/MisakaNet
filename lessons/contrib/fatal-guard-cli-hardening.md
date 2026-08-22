---
{
  "title": "Fatal-guard CLI: harden entry point with --help, --version, exit codes",
  "domain": "devops",
  "tags": [
    "fatal-guard",
    "cli",
    "harden",
    "exit-codes"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "rescue",
  "created": "2026-08-22",
  "author": "unknown",
  "edited_at": "2026-08-22T05:38:37.014661+00:00",
  "merged_by": "unknown"
}
---

## Problem

Fatal-guard CLI lacks --help, --version, and proper exit codes.

## Solution

Add standard Unix CLI conventions: --help, --version, --timeout, exit codes (0/1/2/3).

## Key Points

- Exit codes help CI/CD pipelines detect failure types
- --help and --version are expected by all users
