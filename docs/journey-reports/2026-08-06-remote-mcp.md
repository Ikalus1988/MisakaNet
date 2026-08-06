# Remote MCP Journey Report — 2026-08-06

## Test Environment
- Client: curl 8.x from macOS terminal
- System: macOS, Asia/Shanghai timezone
- Time: 2026-08-06 10:55 CST
- Entry point: GitHub README → `docs/integrations/mcp-remote.md` → direct endpoint `https://misakanet.org/mcp`
- Target issue: #830 — Validate remote MCP first-call user journey

## Steps and Results

### 1. Discover endpoint
- Entry: GitHub README and `docs/integrations/mcp-remote.md`
- Result: ✅
- Evidence: `docs/integrations/mcp-remote.md` clearly lists `https://misakanet.org/mcp` as the remote MCP endpoint.
- Friction: Minor. The top-level README prominently covers local stdio MCP setup, while the remote endpoint is easier to find once the user already knows to open the remote integration doc.

### 2. Understand authentication
- Result: ❌
- Evidence: `docs/integrations/mcp-remote.md` says `Auth: Bearer token` and uses `Bearer YOUR_TOKEN` in examples.
- Friction: The doc does not explain where a first-time user gets `YOUR_TOKEN`, whether there is a public demo token, whether the token is issued through Glama, GitHub, email registration, a website flow, or by contacting maintainers.
- Severity: Blocking. A first-time remote MCP user can discover the endpoint, but cannot complete initialize/tools/list/tools/call without a token source.

### 3. Configure client
- Configuration method: curl with Streamable HTTP headers
- Result: ⚠️ Partially successful
- What worked: The required URL, POST method, JSON content type, `Accept`, and protocol version headers are documented enough to build a curl request.
- What blocked completion: Valid `Authorization: Bearer <token>` value was unavailable from the journey.

### 4. initialize
- Request:

```bash
curl -i https://misakanet.org/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"codex-journey-test","version":"0.1.0"}}}'
```

- Response:

```http
HTTP/2 401
content-type: application/json

{"jsonrpc":"2.0","error":{"code":-32000,"message":"Unauthorized"}}
```

- Result: ❌
- Friction: The error confirms authentication is enforced, but the error message does not guide the user to the token acquisition path.

### 5. tools/list
- Request:

```bash
curl -i https://misakanet.org/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

- Response:

```http
HTTP/2 401
content-type: application/json

{"jsonrpc":"2.0","error":{"code":-32000,"message":"Unauthorized"}}
```

- Result: ❌
- Tool count: Not available because authentication blocks the request before tool discovery.

### 6. tools/call — search
- Query: planned query was `database locked`
- Result: ❌ Not reached
- Reason: `initialize` and `tools/list` both return `401 Unauthorized` without a documented way to obtain a valid bearer token.
- Returned result count: N/A

## Additional Endpoint Behavior

### GET request behavior
- Request:

```bash
curl -i https://misakanet.org/mcp
```

- Response:

```http
HTTP/2 405
content-type: application/json
accept-post: application/json, text/event-stream

{"error":"Method Not Allowed. Use POST for MCP Streamable HTTP transport."}
```

- Result: ✅
- Positive note: This is helpful. A user who accidentally opens the endpoint in a browser or uses GET gets a clear correction to use POST.

## Friction Summary

| Severity | Description | Suggested Fix |
|---|---|---|
| Blocking | `YOUR_TOKEN` is required but no token acquisition path is documented. | Add a “How to get a token” section before client config examples. State whether users should use Glama Connect, request a token, register through a MisakaNet page/email flow, or use a public read-only demo token. |
| Blocking | `401 Unauthorized` response does not tell users what to do next. | Return an auth error message such as `Unauthorized: missing Bearer token. See docs/integrations/mcp-remote.md#get-a-token`. |
| Experience gap | README strongly emphasizes local stdio setup; remote endpoint path is less visible for first-time remote users. | Add a short README section: “Remote MCP, no clone required” linking directly to `docs/integrations/mcp-remote.md`. |
| Experience gap | curl examples are not included in the remote doc, even though they are ideal for validating `initialize`, `tools/list`, and `tools/call`. | Add copy-paste curl smoke tests for unauthenticated 401 and authenticated initialize/tools/list/search. |
| Suggestion | GET `/mcp` already gives a useful 405 message. | Keep this behavior; optionally include the remote docs URL in the response body. |

## Suggested Documentation Patch

Add near the top of `docs/integrations/mcp-remote.md`, before “Quick Start”:

```markdown
## Get a Bearer Token

Remote MCP requires `Authorization: Bearer <token>`.

Choose one token path:

1. Glama: open the MisakaNet listing and use Connect/custom endpoint if token injection is provided there.
2. MisakaNet registration: [link to token registration page or email flow].
3. Maintainer-issued token: request a read-only token in a GitHub issue/comment.

If you only want to verify transport, a request without `Authorization` should return `401 Unauthorized`.
```

Add a curl smoke test:

```bash
TOKEN="<your-token>"

curl -i https://misakanet.org/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl-smoke","version":"0.1.0"}}}'
```

## Overall Evaluation

The remote MCP endpoint is discoverable and the transport behavior is partially self-explanatory: GET returns a helpful `405` with a POST hint, and unauthenticated POST returns JSON-RPC-shaped `401` errors. However, the first-call journey is currently blocked at authentication because the documentation says Bearer token is required but does not explain how a new user obtains one. As a result, a fresh user can reach the endpoint but cannot complete `initialize`, `tools/list`, or `tools/call` from the published docs alone.

## Privacy
- [x] This report contains no private secrets, API tokens, or confidential system data.
- [x] All evidence was gathered from public docs and unauthenticated endpoint responses.
