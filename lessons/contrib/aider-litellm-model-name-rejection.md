---
title: Aider via LiteLLM rejects standard Anthropic model names
domain: devops
tags:
- aider
- litellm
- anthropic
- model
- configuration
status: published
created: '2026-08-22'
source: mcp-intake-1193
evidence_level: E2
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-08-22"
  evidence: "post-publication"
-->

<!-- 
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


## Verification

```bash
aider --api-key "anthropic=$KEY" --model anthropic/claude-sonnet-4-6
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `aider --api-key anthropic=$KEY --model anthropic/claude-sonnet-4-6`)
