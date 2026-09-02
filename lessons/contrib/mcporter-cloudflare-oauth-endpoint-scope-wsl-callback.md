---
title: 'mcporter Cloudflare OAuth: Correct Endpoint, No Scope, and WSL Callback Trap'
domain: devops
tags:
- mcporter
- oauth
- cloudflare
- mcp
- wsl
- localhost
- benchmark
- workers-ai
status: published
created: '2026-09-02'
source: benchmark-oauth-2026-09-02
evidence_level: E0

provenance:
  source: "external"
  contributor: "benchmark-oauth-2026-09-02"
  merged_at: "2026-09-02"
  evidence: "post-publication"
---

## Problem

Authorizing mcporter for Cloudflare MCP (`mcporter auth cloudflare`) failed in three distinct ways before success:

1. Browser showed `路由 /oauth/error 不存在` (page not found) — wrong **authorization endpoint**.
2. Browser showed `无效范围 未知的 OAuth 范围: mcp:tools` (invalid scope) — the **scope** parameter was rejected.
3. After authorizing successfully in the browser, mcporter still timed out (`OAuthTimeoutError: timed out after 60s`) — the **local callback** never reached WSL.

## Root Cause

1. **Wrong endpoint.** The Cloudflare OAuth authorization endpoint is **`https://mcp.cloudflare.com/authorize`**, NOT `https://dash.cloudflare.com/oauth2/auth`. The discovery document at `https://mcp.cloudflare.com/.well-known/oauth-authorization-server` is authoritative:
   ```json
   {"authorization_endpoint": "https://mcp.cloudflare.com/authorize", "token_endpoint": "https://mcp.cloudflare.com/token", ...}
   ```
   (No `scopes_supported` key is present.)
2. **Invalid scope.** Cloudflare MCP does **not** accept `mcp:tools` — there is no `scopes_supported` in its discovery, so **omit the `scope` parameter entirely**.
3. **WSL callback trap.** mcporter's callback server listens on `127.0.0.1:<port>` inside WSL. When the user authorizes from a **Windows browser**, the redirect to `http://127.0.0.1:<port>/callback` hits **Windows' own loopback**, not WSL's — the callback never arrives and mcporter times out. WSL2's automatic `localhost` forwarding works for `localhost` but NOT for `127.0.0.1` in this direction.

## Fix

1. **Build the authorize URL manually with the correct endpoint and NO scope** (read the live PKCE values from mcporter's token cache while the auth process is running):

   ```python
   import hashlib, base64, urllib.parse, json
   verifier = open('.tools/mcporter-tokens/cloudflare/code_verifier.txt').read().strip()
   challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
   client = json.load(open('.tools/mcporter-tokens/cloudflare/client.json'))
   params = {
       "response_type": "code",
       "client_id": client["client_id"],
       "redirect_uri": client["redirect_uris"][0],
       "code_challenge": challenge,
       "code_challenge_method": "S256",
       # NO scope — Cloudflare MCP rejects mcp:tools
   }
   url = "https://mcp.cloudflare.com/authorize?" + urllib.parse.urlencode(params)
   ```

2. **Keep the mcporter auth process running** while the user opens the URL — it must listen for the callback. It times out after 60s; re-run if needed.

3. **For WSL**: if the callback still doesn't arrive (Windows browser can't reach WSL's `127.0.0.1`), capture the redirect URL's `code=` from the browser address bar after a successful authorization, then exchange it manually:

   ```bash
   curl -sS -X POST https://mcp.cloudflare.com/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=authorization_code&code=<CODE>&redirect_uri=<REDIRECT>&client_id=<CLIENT_ID>&code_verifier=<VERIFIER>"
   ```
   Then write the returned `access_token`/`refresh_token` into `.tools/mcporter-tokens/cloudflare/tokens.json`.

## Verification

```bash
# tokens.json now exists with access_token + refresh_token
ls .tools/mcporter-tokens/cloudflare/tokens.json

# Model call succeeds (returns content, not empty/timeout)
.tools/bin/mcporter call cloudflare.execute 'code=async () => { const r = await cloudflare.request({ method: "POST", path: "/accounts/<ACCOUNT>/ai/run/@cf/meta/llama-3.2-3b-instruct", body: { messages: [{ role: "user", content: "Reply with exactly: OK" }] } }); return r.result?.choices?.[0]?.message?.content || "EMPTY"; }' --config .tools/mcporter.json
# → OK

# Benchmark now produces real scores (len>0, hit>0), e.g. len=1051-1255, hit=16-100%
python3 scripts/benchmark_workers_ai.py --output docs/benchmarks/benchmark-2026-09-02.json
```

## Lesson

- Always read the OAuth **discovery document** (`.well-known/oauth-authorization-server`) for the authoritative endpoints — don't guess `dash.cloudflare.com/oauth2/auth`.
- If the server's discovery has no `scopes_supported`, **omit scope**.
- In WSL + Windows-browser setups, the local callback server on `127.0.0.1` inside WSL is unreachable from the Windows browser; prefer `localhost` in `oauthRedirectUrl` or capture the `code=` from the address bar and exchange it manually.
- A benchmark that returns `len=0 hit=0%` for every run usually means the model call is failing (auth/network), not that the lessons are bad — check the model call first.
