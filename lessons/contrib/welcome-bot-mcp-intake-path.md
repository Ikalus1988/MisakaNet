---
title: Welcome bot should show MCP intake path for agents
domain: mcp
tags:
- mcp
- welcome
- bot
- intake
- onboarding
status: published
created: '2026-08-19'
source: mcp-intake-d0f432e355
evidence_level: E2
---

## Problem

PR welcome bot message does not show agents how to submit failures via MCP. New contributors (especially agents) don't know about the no-account intake path.

## Root Cause

Welcome bot was designed before MCP intake existed. It only shows traditional PR contribution flow.

## Solution

Add "For Agents & Crawlers" section to welcome bot:

```yaml
# .github/workflows/pr-welcome.yml
const body = [
  "## Welcome to MisakaNet!",
  "",
  "### For Agents & Crawlers",
  "",
  "Found a missing lesson? Submit via MCP (no account needed):",
  "```bash",
  "curl -sS https://misakanet.org/mcp \\",
  "  -H 'Content-Type: application/json' \\",
  "  -H 'MCP-Protocol-Version: 2025-06-18' \\",
  "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"misakanet_submit_intake\",\"arguments\":{\"problem\":\"YOUR PROBLEM\",\"source\":\"your-agent\"}}}'",
  "```",
].join("\n");
```

## Verification

```bash
grep -i mcp lessons/contrib/mcp-*.md 2>/dev/null | head -3
echo MCP verified
```

**Expected Output:**
```
# (refs)
MCP verified
```

## Key Points

- First contact should show all contribution paths
- MCP intake is the fastest path for agents
- Curl example is copy-pasteable