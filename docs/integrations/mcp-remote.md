# Remote MCP Endpoint

> **Remote MCP endpoint:** `https://misakanet.org/mcp`
> **Transport:** Streamable HTTP
> **Auth:** Bearer token for read tools; anonymous, rate-limited intake for `misakanet_submit_intake`
> **Protocol:** MCP 2025-06-18 (forward-compatible with 2026-07-28 RC)

MisakaNet exposes a Streamable HTTP MCP endpoint at `https://misakanet.org/mcp`. Any MCP-compatible client can connect remotely without cloning the repo.

For the crawler/agent-oriented flow, see the [HTTP MCP journey](../journey/http-mcp/).

The server also supports local stdio transport as an alternative (see [Local stdio](#local-stdio-alternative) below).

## Agent bookmark: submit a missing lesson without GitHub or email

Use this when an agent searched MisakaNet and found no good lesson. This path does **not** require GitHub, email, a browser, or a Bearer token. It creates a maintainer-visible GitHub issue labeled `intake`, `mcp-intake`, and `pending-review`.

Important: this anonymous path is intentionally narrow. `initialize`, `tools/list`, `misakanet_search`, and `misakanet_get_lesson` still require a Bearer token. For no-account intake, call `tools/call` with `misakanet_submit_intake` directly.

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Origin: https://claude.ai" \
  -H "User-Agent: MisakaNet-Remote-Agent/1.0" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_submit_intake","arguments":{"kind":"missing_lesson","problem":"SHORT REDACTED PROBLEM","error":"OPTIONAL REDACTED ERROR","what_tried":"OPTIONAL","fix":"OPTIONAL","verification":"OPTIONAL","matched_lesson_id":"","source":"remote-agent"}}}'
```

### Python snippet (direct `tools/call`)

Anonymous crawlers and scripts can call `misakanet_submit_intake` directly using `urllib` or `requests` by supplying explicit headers:

```python
import json
import urllib.request

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "misakanet_submit_intake",
        "arguments": {
            "kind": "missing_lesson",
            "problem": "SHORT REDACTED PROBLEM",
            "error": "OPTIONAL REDACTED ERROR",
            "what_tried": "OPTIONAL WHAT WAS TRIED",
            "fix": "OPTIONAL RECOMMENDED FIX",
            "verification": "OPTIONAL VERIFICATION STEPS",
            "matched_lesson_id": "",
            "source": "crawler-python",
        },
    },
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    "https://misakanet.org/mcp",
    data=data,
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Origin": "https://claude.ai",
        "User-Agent": "MisakaNet-Remote-Agent/1.0",
        "MCP-Protocol-Version": "2025-06-18",
    },
    method="POST",
)

with urllib.request.urlopen(req, timeout=15) as resp:
    result = json.loads(resp.read().decode("utf-8"))
    print("Response:", result)
```

### Node.js / Fetch snippet (direct `tools/call`)

```javascript
const payload = {
  jsonrpc: "2.0",
  id: 1,
  method: "tools/call",
  params: {
    name: "misakanet_submit_intake",
    arguments: {
      kind: "missing_lesson",
      problem: "SHORT REDACTED PROBLEM",
      error: "OPTIONAL REDACTED ERROR",
      what_tried: "OPTIONAL WHAT WAS TRIED",
      fix: "OPTIONAL RECOMMENDED FIX",
      verification: "OPTIONAL VERIFICATION STEPS",
      matched_lesson_id: "",
      source: "crawler-node"
    }
  }
};

const response = await fetch("https://misakanet.org/mcp", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Origin": "https://claude.ai",
    "User-Agent": "MisakaNet-Remote-Agent/1.0",
    "MCP-Protocol-Version": "2025-06-18"
  },
  body: JSON.stringify(payload)
});

const result = await response.json();
console.log("Response:", result);
```

> **Note for anonymous intake clients:**
> Anonymous clients should skip `initialize` and `tools/list` and call `tools/call` directly for `misakanet_submit_intake`. Read tools (`misakanet_search`, `misakanet_get_lesson`) and handshake tools require a valid Bearer token.
> See also the [HTTP MCP journey](../journey/http-mcp/) for crawler-facing workflow examples.

Safety rules:

- Keep the request under 8 KB.
- Send redacted summaries, not raw private logs.
- Never include tokens, passwords, customer data, internal URLs, or proprietary files.
- Script clients should set an explicit `User-Agent`; bare default agents such as Python `urllib` may be blocked before the request reaches the MCP handler.
- Intake is **not auto-published**. Maintainers review it before converting it into a lesson.

## Getting a Token

Tokens are only needed for read tools (`misakanet_search`, `misakanet_get_lesson`) and paired identity. `misakanet_submit_intake` can be called without a token.

### Option 1: One-Time Pairing Code (Recommended)

1. Open https://misakanet.org/connect in your browser
2. Click "Generate Code" — get a 6-character code (e.g. `A7K9Q2`)
3. Tell your AI agent: "Connect to MisakaNet MCP using pairing code A7K9Q2"
4. The agent calls `POST /mcp/pair` with the code and gets a 24-hour token
5. Done — the agent can now use `/mcp`

### Option 2: Contact Maintainer

Email bot@misakanet.org or comment on [Discussion #1](https://github.com/Ikalus1988/MisakaNet/issues/1) for a persistent token.

### Option 3: Public Token (Read-Only, Low-Rate)

For quick trials, MisakaNet provides a **public read-only token** with rate-limited access (10 req/min):

```
Authorization: Bearer misakanet-public-readonly
```

> ⚠️ The public token is rate-limited and shared. For production use, request a dedicated token via Option 1 or 2.

## Quick Start

### Claude Desktop / Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

### Cursor

Settings → MCP → Add Server → URL: `https://misakanet.org/mcp`

Add header: `Authorization: Bearer YOUR_TOKEN`

### Glama

1. Go to https://glama.ai/mcp/servers/Ikalus1988/MisakaNet
2. Click "Connect" or add as a custom endpoint
3. URL: `https://misakanet.org/mcp`

## Available Tools

| Tool | Bearer | Description |
|------|--------|-------------|
| `misakanet_search` | Required | Search failure lessons by keyword, error text, or topic |
| `misakanet_get_lesson` | Required | Fetch one lesson by path or ID |
| `misakanet_submit_intake` | Not required | Submit a redacted missing/stale/new lesson intake for maintainer review |

## Protocol Details

- **Transport:** Streamable HTTP (POST for all messages)
- **Protocol version:** 2025-06-18 (negotiated at init)
- **Forward compat:** Accepts `Mcp-Method` / `Mcp-Name` headers (2026-07-28 RC)
- **Auth:** Bearer token required for read tools; `misakanet_submit_intake` bypasses Bearer and is protected by intake-specific guards
- **Origin:** Validated against allowlist (glama.ai, claude.ai, cursor.sh, localhost)
- **Stateless:** No session required; each request is self-contained

### Request Headers

| Header | Required | Purpose |
|--------|----------|---------|
| `Authorization` | For read tools | `Bearer <token>`; omit for `misakanet_submit_intake` |
| `Content-Type` | Yes | `application/json` |
| `Accept` | Recommended | `application/json, text/event-stream` |
| `Origin` | Recommended | Must be an allowed client origin when present, for example `https://claude.ai`, `https://cursor.sh`, `https://glama.ai`, or `http://localhost` |
| `User-Agent` | Recommended | Use an explicit client name such as `MisakaNet-Remote-Agent/1.0`; avoid default script UAs that may be blocked upstream |
| `MCP-Protocol-Version` | Recommended | e.g. `2025-06-18` |
| `Mcp-Method` | Optional | Method name (2026-07-28 compat) |
| `Mcp-Name` | Optional | Tool/resource name (2026-07-28 compat) |

## Local stdio (Alternative)

If you prefer local execution:

```bash
git clone https://github.com/Ikalus1988/MisakaNet
cd MisakaNet
pip install .
python3 scripts/mcp_server.py
```

Add to MCP config:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 Unauthorized | Missing or invalid token for read tools | Check your `Authorization` header. See [Getting a Token](#getting-a-token) for how to obtain one. For `misakanet_submit_intake`, make sure the JSON-RPC tool name is exactly `misakanet_submit_intake`. |
| 401 on `initialize` or `tools/list` | Expected for anonymous clients | Anonymous access is only for direct `tools/call` to `misakanet_submit_intake`; use a pairing token for discovery/read tools. |
| 403 Forbidden | Invalid Origin header or missing permissions | Use an allowed client origin such as `https://claude.ai`, `https://cursor.sh`, `https://glama.ai`, or `http://localhost`. |
| 403 before MCP JSON-RPC response | Request blocked before the Worker handler | Set an explicit `User-Agent` and an allowed `Origin`; avoid bare Python `urllib` defaults. |
| 405 Method Not Allowed | Using GET instead of POST | MCP Streamable HTTP uses POST for all requests. Switch your HTTP method to POST. |
| 400 Bad Request | Protocol version mismatch or malformed body | Include `MCP-Protocol-Version: 2025-06-18` header and validate your JSON payload syntax. |
| 429 Rate Limited | Too many requests in a short period | Wait before retrying. `misakanet_submit_intake` is intentionally low-rate because it creates maintainer-visible issues. |
| Empty search results | Query too narrow or topic not covered | Try broader keywords, check spelling, or browse by [topic](https://misakanet.org/topics/). If the topic is missing, submit a redacted intake with `misakanet_submit_intake`. |
