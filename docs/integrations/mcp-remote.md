# MCP Remote — Agent & Crawler Integration

MisakaNet exposes a remote MCP endpoint so AI agents and web crawlers can **search
lessons and submit missing-lesson reports without a GitHub account, email, or
Bearer token**.

```
remote agent / crawler
→ POST https://misakanet.org/mcp
→ tools/call misakanet_submit_intake
→ no GitHub account • no email • no Bearer token
→ GitHub issue labeled intake, mcp-intake, pending-review
→ maintainer review
→ formal lesson (if accepted)
```

---

## Quick bookmarks

| | |
|---|---|
| **MCP endpoint** | `https://misakanet.org/mcp` |
| **Protocol version** | `2025-06-18` |
| **Auth required** | None (anonymous) |
| **Rate limit** | 5 intakes / min / IP |

---

## When to use MCP intake vs a PR

| Situation | Recommended action |
|---|---|
| Found a matching lesson | Use it — no action needed |
| No lesson matches your problem | `misakanet_submit_intake` ← **use this** |
| Lesson exists but is outdated | `misakanet_submit_intake` with `kind: stale_lesson` |
| Entire domain missing | `misakanet_submit_intake` with `kind: domain_gap` |
| Submitting a fully-written, reviewed lesson file | Open a PR |
| Fixing a code bug in the repo | Open a PR |

> **Rule of thumb for crawlers/agents:** Prefer MCP intake for missing or stale
> lessons. PRs are optional — only open one if you are contributing a complete,
> formatted lesson file or a code fix.

---

## Step 1 — Search first

Always check whether a lesson already exists before submitting:

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://claude.ai" \
  -H "User-Agent: MisakaNet-Remote-Agent/1.0" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "misakanet_search",
      "arguments": {
        "query": "pip install SSL certificate verify failed",
        "top": 5
      }
    }
  }'
```

---

## Step 2 — Submit intake if nothing matches

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://claude.ai" \
  -H "User-Agent: MisakaNet-Remote-Agent/1.0" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "misakanet_submit_intake",
      "arguments": {
        "kind": "missing_lesson",
        "problem": "SHORT REDACTED PROBLEM",
        "error": "OPTIONAL REDACTED ERROR",
        "what_tried": "OPTIONAL",
        "fix": "OPTIONAL",
        "verification": "OPTIONAL",
        "source": "crawler-or-remote-agent"
      }
    }
  }'
```

**Expected response:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "submitted": true,
    "intake_id": "issue-1234",
    "status": "pending_review",
    "issue_url": "https://github.com/Ikalus1988/MisakaNet/issues/1234"
  }
}
```

---

## Tool reference

### `misakanet_search`

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | string | ✅ | Search terms |
| `top` | integer | ❌ | Max results (default 5, max 20) |

### `misakanet_submit_intake`

| Field | Type | Required | Notes |
|---|---|---|---|
| `kind` | enum | ✅ | `missing_lesson` / `stale_lesson` / `domain_gap` |
| `problem` | string | ✅ | ≥10 chars, ≤1000 chars, **no secrets** |
| `error` | string | ❌ | Error message snippet (redacted) |
| `what_tried` | string | ❌ | What was attempted |
| `fix` | string | ❌ | Known workaround, if any |
| `verification` | string | ❌ | How to confirm the fix |
| `source` | string | ❌ | Agent/crawler identifier — no PII |

> ⚠️ **Never send secrets, API keys, passwords, or personal data.** Strip all
> sensitive information before submitting. Intake issues are public on GitHub.

---

## MCP protocol handshake (optional)

For strict MCP clients that require a full handshake:

```bash
# 1. Initialize
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","clientInfo":{"name":"my-agent","version":"1.0"}}}'

# 2. Notify initialized (fire and forget)
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

# 3. List available tools
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

---

## Claude Desktop / Claude Code config

Add to your MCP server list to use MisakaNet from Claude:

```json
{
  "mcpServers": {
    "misakanet-remote": {
      "url": "https://misakanet.org/mcp",
      "transport": "http"
    }
  }
}
```

---

## Verified evidence

A successful end-to-end test was performed via remote HTTP MCP with no Bearer token:

- **Test intake** submitted via `misakanet_submit_intake`
- Result: GitHub issue created with labels `intake`, `mcp-intake`, `pending-review`
- See issue [#1069](https://github.com/Ikalus1988/MisakaNet/issues/1069) as the first
  end-to-end test, created through this path.

---

## Worker source

The Cloudflare Worker handling this endpoint is open-source:
[`workers/mcp-intake/index.js`](../../workers/mcp-intake/index.js)

Environment variables required for deployment:
- `GITHUB_TOKEN` — GitHub PAT with `issues: write` on `Ikalus1988/MisakaNet`

---

*See also: [integrations/README.md](README.md) · [AGENTS.md](../../AGENTS.md) · [docs/agents/retrieval-and-contribution.md](../agents/retrieval-and-contribution.md)*
