---
{
  "title": "Aider CLI --api-key parameter leaks API key to history files",
  "domain": "security",
  "tags": [
    "aider",
    "security",
    "api-key",
    "leak",
    "history"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "intake",
  "created": "2026-08-22",
  "author": "unknown",
  "edited_at": "2026-08-22T05:38:32.688329+00:00",
  "merged_by": "unknown"
}
---

## Problem

Aider CLI --api-key parameter leaks API key to .aider.chat.history.md, bash history, and /proc/pid/cmdline.

## Root Cause

CLI arguments are visible in process listing and may be logged to history files.

## Solution

Use environment variable instead of CLI argument:
```bash
export ANTHROPIC_API_KEY="your-key"
aider  # don't use --api-key flag
```

Or use .env file:
```bash
echo "ANTHROPIC_API_KEY=your-key" > .env
aider  # reads from .env automatically
```

## Key Points

- Never pass API keys as CLI arguments
- Use environment variables or .env files
- CLI args are visible in process listing and history
