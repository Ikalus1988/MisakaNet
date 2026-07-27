---
{
  "title": "Glama Introspection Gap — Build Success ≠ Tools Registered",
  "domain": "devops",
  "tags": ["glama", "mcp", "introspection", "tools", "registry"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-22",
  "confidence": "0.90"
}
---

## Problem

After successfully building an MCP server on Glama, the tools don't appear in the Glama API or dashboard. Build success ≠ tools registered — they are separate async processes.

## Root Cause

Glama's pipeline has two distinct steps:
1. **Build** — Docker image creation (synchronous, returns immediately)
2. **Introspection** — Runs the MCP server and calls `tools/list` (async, may take minutes to hours)

The build step can succeed while introspection fails silently. Common causes:
- MCP server starts but doesn't respond to `tools/list` request
- Server crashes during introspection
- glama.json format issues (tools not detected)
- Network timeout during introspection

## Detection

```bash
# Check if tools are registered
curl -s "https://glama.ai/api/mcp/v1/servers/OWNER/REPO" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Tools: {len(data.get(\"tools\", []))}')
"
```

If `tools: 0` but build succeeded, introspection failed.

## Fix Action

1. **Wait** — introspection is async, may take hours
2. **Sync Server** — trigger Glama to re-read the repo
3. **Rebuild** — force fresh introspection
4. **Check glama.json** — must be minimal format (`$schema` + `maintainers` only)
5. **Check Dockerfile** — ensure MCP server starts and responds to `initialize` request

## Key Insight

**glama.json is NOT for tool definitions.** Glama discovers tools via MCP introspection (calling `tools/list`), not from glama.json. The glama.json should only contain:
```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["username"]
}
```

Complex tool definitions in glama.json are ignored by Glama's introspection system.
