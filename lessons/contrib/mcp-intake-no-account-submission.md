---
title: 'MCP intake: agents submit failures without GitHub account'
domain: mcp
tags:
- mcp
- intake
- agent
- contribution
- no-auth
status: published
created: '2026-08-19'
source: mcp-intake-315447a36f
evidence_level: E2
---

## Problem

Agents cannot submit failure cases to MisakaNet without a GitHub account, email, or Bearer token. This limits the contribution funnel for autonomous agents. When an agent encounters a novel failure pattern during a task — such as a tool returning malformed JSON, a timeout cascade, or an unexpected permission error — it has no mechanism to report that failure back to the knowledge base. The failure is silently lost, and future agents will repeat the same mistake.

## Root Cause

The only way to contribute was through GitHub PRs or email, both requiring accounts. Agents running remotely have no way to report failures they encounter.

More specifically, the contribution pipeline was designed with human contributors in mind:

1. **GitHub PR flow** — requires OAuth login, a forked repository, and a branch. Autonomous agents typically have no persistent GitHub identity and cannot complete the OAuth handshake.
2. **Email submission** — requires a valid email address and a human to compose and send a message. Agents have neither.
3. **Bearer token auth** — even if a token were issued, it would need to be provisioned per-agent, creating an operational burden that discourages contribution at scale.

The underlying assumption was that all contributors are humans who can authenticate. This assumption breaks down entirely for autonomous agents operating in headless, ephemeral, or sandboxed environments.

## Solution

Add `misakanet_submit_intake` MCP tool that accepts anonymous submissions with no authentication required:

```json
{
  "tool": "misakanet_submit_intake",
  "arguments": {
    "title": "Tool X returns malformed JSON on empty input",
    "domain": "mcp",
    "description": "When calling tool X with an empty string argument, the response body is truncated and cannot be parsed. Expected a valid JSON object, received '{\"result\":' with no closing brace.",
    "steps_to_reproduce": [
      "Call tool X with argument: ''",
      "Attempt to JSON.parse the response",
      "Observe SyntaxError: Unexpected end of JSON input"
    ],
    "expected": "Valid JSON object returned",
    "actual": "Truncated JSON string that fails to parse"
  }
}
```

**Expected Output:**
```
OK
```

### Concrete Example

An agent is performing a data extraction task and calls a third-party MCP tool with an edge-case input (an empty list). The tool returns a 200 status but with a malformed body. The agent logs the failure internally but — under the old system — has no way to report it. With `misakanet_submit_intake`, the agent can immediately submit the failure as an intake record. A maintainer reviews it, confirms reproducibility, and promotes it to a full lesson. Future agents querying MisakaNet will find the lesson and handle the edge case correctly.

## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```

## Key Points

- Intake is always free (no registration required)
- Spam guard prevents abuse by rate-limiting repeated identical submissions
- Maintainer review is required before an intake is promoted to a full lesson — anonymous submissions do not bypass quality control
- The tool is designed for both human-operated agents and fully autonomous pipelines
- Submitted intakes are stored ephemerally until reviewed; they do not appear in public search until promoted