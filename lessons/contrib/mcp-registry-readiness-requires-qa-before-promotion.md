---
{
  "domain": "mcp",
  "title": "MCP Registry Readiness Requires QA Before Promotion",
  "tags": ["mcp", "registry", "qa", "glama", "tooling"],
  "status": "published",
  "source": "generalized MCP listing readiness analysis",
  "created": "2026-07-17",
  "confidence": "0.86"
}
---

## Problem

Submitting an MCP server to a public registry before its smoke tests, tool descriptions, and user-facing install path are ready can waste the first discovery wave. Registry traffic is only useful if new users can connect, understand the tools, and get a helpful result quickly.

## Root Cause

MCP discovery has multiple gates:

```text
listing -> README -> install -> client connects -> model calls tool -> correct result -> useful answer
```

A server can be technically valid but still fail because:

- smoke tests fail on a common OS
- tool schemas do not nudge models to call the right tool
- README promises a package install that does not exist
- an experimental telemetry tool is described as production-ready
- registry listing frames a memory server as a skill marketplace

## Solution

### 1. Define a registry readiness gate

Before promoting a server, verify:

```text
MCP smoke test passes
Windows/macOS/Linux instructions are clear
README uses real install commands only
experimental tools are labeled experimental
registry metadata has the right category and positioning
```

### 2. Run chat-style QA, not only unit tests

Use a matrix like:

| Query | Tool called? | Correct lesson? | Helpful answer? | No hallucination? |
|---|---|---|---|---|
| DCO failed on GitHub | | | | |
| pip install times out | | | | |
| secret scan blocked PR | | | | |
| irrelevant negative query | | | | |

This tests whether models actually use the MCP tool in realistic workflows.

### 3. Position the server precisely

For a failure-memory server:

```text
Not a skill marketplace. A failure-memory MCP server.
```

Avoid claiming adoption before there is public usage evidence.

### 4. Sequence promotion

Recommended order:

```text
local smoke -> registry metadata -> upstream registry PR -> listing indexed -> chat QA -> broader community post
```

## Verification

- Public listing points to a README with working setup commands.
- Chat QA includes positive and negative queries.
- The model calls the search tool for relevant failures and avoids hallucinated fixes for irrelevant prompts.

## Next Agent Prompt

Before announcing an MCP registry listing, test the whole path from discovery to useful answer. A directory entry is not adoption until an agent can connect and retrieve the right memory.
