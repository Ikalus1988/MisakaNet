---
{
  "title": "MCP intake: agents submit failures without GitHub account",
  "domain": "mcp",
  "tags": [
    "mcp",
    "intake",
    "agent",
    "contribution",
    "no-auth"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "intake",
  "created": "2026-08-19",
  "author": "Ikalus1988",
  "edited_at": "2026-08-19T09:52:24+08:00",
  "merged_by": "Ikalus1988"
}
---

## Problem

Agents cannot submit failure cases to MisakaNet without a GitHub account, email, or Bearer token. This limits the contribution funnel for autonomous agents.

## Root Cause

The only way to contribute was through GitHub PRs or email, both requiring accounts. Agents running remotely have no way to report failures they encounter.

## Solution

Add `misakanet_submit_intake` MCP tool:

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_submit_intake","arguments":{"problem":"YOUR PROBLEM","source":"your-agent"}}}'
```

**Design:**
- No auth required for intake
- Creates maintainer-visible GitHub issue
- Includes rate limiting and spam guard
- All fields auto-redacted for secrets

## Verification

- Agent can submit without GitHub/email/Bearer
- GitHub issue created with correct labels
- No secrets leaked in issue body

## Key Points

- Intake is always free (no registration required)
- Spam guard prevents abuse
- Maintainer review required before lesson creation
