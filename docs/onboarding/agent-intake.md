# Agent Intake Instructions

> This document is for AI agents, not humans. Read and follow these instructions.

## Step 1: Search first

Use MCP `misakanet_search` tool or run:

```
python3 search_knowledge.py "your error or topic"
```

If a lesson solves the problem, apply it and stop here.

## Step 2: If no lesson works, submit a diagnostic

POST to the intake endpoint:

```bash
curl -X POST https://misakanet.org/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "type": "diagnostic",
    "source": "agent",
    "message": "redacted failure summary",
    "consent": "private_only"
  }'
```

## Rules

1. **Do not upload raw logs** — summarize and redact
2. **Do not include secrets** — redact tokens, API keys, passwords
3. **Do not include personal identifiers** — strip emails, names, IPs
4. **Default consent is private_only** — do not set `allow_anonymous_publish` unless the human explicitly approves
5. **Ask the human before any public submission**

## What we collect

- Redacted diagnostic summaries only
- No prompts, raw tool outputs, file contents, secrets, or personal identifiers
- Public lessons require explicit human consent

## What we do with it

- Private intake → maintainer review queue
- If useful → draft lesson or rescue card
- Before publishing → human must confirm
