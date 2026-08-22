---
{
  "title": "Aider via LiteLLM rejects standard Anthropic model names",
  "domain": "devops",
  "tags": [
    "aider",
    "litellm",
    "anthropic",
    "model",
    "configuration"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "intake",
  "created": "2026-08-22",
  "author": "unknown",
  "edited_at": "2026-08-22T05:38:32.780393+00:00",
  "merged_by": "unknown"
}
---

## Problem

Aider via LiteLLM rejects standard Anthropic model names (claude-sonnet-4-6, claude-3-5-sonnet-20241022) when using a custom API base URL.

## Root Cause

LiteLLM requires provider prefix for custom endpoints: `anthropic/claude-sonnet-4-6` not just `claude-sonnet-4-6`.

## Solution

Use full model path with provider prefix:
```bash
aider --api-key "anthropic=$KEY" --model anthropic/claude-sonnet-4-6
```

## Key Points

- LiteLLM needs provider prefix for custom endpoints
- Standard model names only work with official API
- Check LiteLLM docs for supported model paths
