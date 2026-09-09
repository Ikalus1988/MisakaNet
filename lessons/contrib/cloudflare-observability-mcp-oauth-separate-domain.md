---
title: 'Cloudflare Observability MCP OAuth: Separate Authorization Domain + mcporter Client Trap'
domain: devops
tags:
  - mcporter
  - oauth
  - cloudflare
  - mcp
  - observability
  - workers
  - wsl
status: published
created: '2026-09-10'
source: cf-workers-errors-2026-09-10
evidence_level: E0

provenance:
  source: "external"
  contributor: "cf-workers-errors-2026-09-10"
  merged_at: "2026-09-10"
  evidence: "post-publication"
---

# Cloudflare Observability MCP OAuth: Separate Authorization Domain + mcporter Client Trap

## Problem

Authorizing `cloudflare-observability` MCP (`https://observability.mcp.cloudflare.com/mcp`)
to diagnose Workers errors (e.g. "misakanet-register-proxy: 225 errors" in the dashboard)
failed repeatedly:

1. Reusing the known-good `mcp.cloudflare.com` OAuth client for the observability endpoint
   returns `invalid_token: Access token appears malformed` — the two MCP servers do **not**
   share an OAuth audience.
2. mcporter's own auth flow (`mcporter auth cloudflare-observability`) produced a client_id
   that `mcp.cloudflare.com/authorize` rejected with `invalid_request / 无效的 client_id`
   (its dynamic registration targets the wrong domain or silently falls back to a
   locally-generated id).

## Root Cause

- `observability.mcp.cloudflare.com` runs a **separate OAuth authorization server**
  (issuer `https://observability.mcp.cloudflare.com`). Discovery:
  `https://observability.mcp.cloudflare.com/.well-known/oauth-authorization-server`
  → `authorization_endpoint: .../oauth/authorize`, `token_endpoint: .../token`,
  `registration_endpoint: .../register`. It is NOT the same as
  `https://mcp.cloudflare.com/.well-known/oauth-authorization-server`
  (`.../authorize`, `.../token`, `.../register`).
- Access tokens are audience-bound: a token from `mcp.cloudflare.com/token` is rejected by
  the observability MCP with `invalid_token` even though the scope list looks identical.
- mcporter's PKCE state files must contain **JSON string literals** (`state.txt` content is
  read with `JSON.parse`, e.g. `"<uuid>"`), otherwise the client errors with
  `Unexpected token ... is not valid JSON`.
- WSL callback trap (see mcporter-cloudflare-oauth-endpoint-scope-wsl-callback): the
  callback on `127.0.0.1` inside WSL never arrives from a Windows browser — capture the
  `code=` from the address bar and exchange it manually.

## Fix (fully manual, no mcporter needed)

1. **DCR on the observability domain** (not mcp.cloudflare.com):

   ```bash
   curl -sS -X POST https://observability.mcp.cloudflare.com/register \
     -H "Content-Type: application/json" \
     -d '{"redirect_uris":["http://127.0.0.1:40399/callback"],"token_endpoint_auth_method":"none",
          "grant_types":["authorization_code","refresh_token"],"response_types":["code"],
          "client_name":"misakanet-probe"}'
   # → {"client_id": "...", ...}
   ```

2. Build the authorize URL (no scope — discovery has no scopes_supported):

   ```python
   import hashlib, base64, urllib.parse, secrets
   verifier = secrets.token_urlsafe(48)
   challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
   url = ("https://observability.mcp.cloudflare.com/oauth/authorize?"
          + urllib.parse.urlencode({"response_type":"code","client_id":CLIENT_ID,
             "redirect_uri":"http://127.0.0.1:40399/callback","code_challenge":challenge,
             "code_challenge_method":"S256","state":secrets.token_urlsafe(16)}))
   ```

3. User opens URL, clicks Allow; browser redirect to `127.0.0.1` fails on WSL — copy the
   full address-bar URL (`code=...`). Exchange (browser User-Agent avoids CF WAF 1010):

   ```bash
   curl -sS -X POST https://observability.mcp.cloudflare.com/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36" \
     -d "grant_type=authorization_code&code=<CODE>&redirect_uri=http://127.0.0.1:40399/callback&client_id=<CLIENT_ID>&code_verifier=<VERIFIER>"
   ```

4. Call the MCP directly over streamable HTTP (no mcporter):

   ```bash
   curl -sS -X POST https://observability.mcp.cloudflare.com/mcp \
     -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'
   # then tools/list, tools/call query_worker_observability ...
   ```

## Verification

```bash
# initialize returns workers-observability serverInfo (not invalid_token)
# tools/list shows query_worker_observability / workers_list / observability_keys ...
```

## Lesson

- Every Cloudflare MCP product may run its **own OAuth domain** — always read
  `<host>/.well-known/oauth-authorization-server` before authorizing; tokens are
  audience-bound and not interchangeable.
- Workers dashboard error counters (invocation exceptions) are visible **without** Workers
  Observability, but the message/stack detail requires
  `[observability] enabled = true` in the worker's wrangler config — enable it first when
  you need to diagnose an error spike.
- When mcporter's own auth flow misbehaves (invalid client_id), skip it: manual DCR +
  authorize + token exchange over curl is ~30s and fully debuggable.
- mcporter `state.txt` must be a JSON string literal (`"uuid"`), not a bare uuid.

---

## Update (2026-09-10): one-shot tool — STOP doing this manually

This manual flow was painful to get right (5 failed rounds: wrong endpoint, invalid
client_id, wrong-domain token, WSL callback, state format). It is now encapsulated in
**`scripts/cf_mcp_auth.py`** — one command, all lessons baked in:

```bash
# authorize a CF MCP server (prints URL → click Allow → paste address-bar URL back)
python3 scripts/cf_mcp_auth.py --server cloudflare-observability
# token expired (30 min)? refresh without a browser:
python3 scripts/cf_mcp_auth.py --server cloudflare-observability --refresh
# check current token:
python3 scripts/cf_mcp_auth.py --server cloudflare-observability --verify
```

The script: discovers the correct OAuth domain per server (never assumes
mcp.cloudflare.com), does explicit DCR, omits scope, uses a browser UA for token
exchange (WAF 1010), stores `state.txt` as a JSON literal, and verifies with an MCP
`initialize` round-trip before exiting 0.
