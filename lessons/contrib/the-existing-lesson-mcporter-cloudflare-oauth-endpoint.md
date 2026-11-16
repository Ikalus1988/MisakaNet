---
title: "The existing lesson `mcporter-cloudflare-oauth-endpoint-scope-wsl-callback` says"
domain: "windows"
tags:
  - "localhost"
  - "code"
  - "invalid_grant"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4903"
summary_plain: "The existing lesson `mcporter-cloudflare-oauth-endpoint-scope-wsl-callback` says WSL2's automatic forwarding works for…"
trigger: "The existing lesson `mcporter-cloudflare-oauth-endpoint-scope-wsl-callback` says. WSL2's automatic forwarding works for `localhost` but not for `127.0.0.1`…"
verify: "The token exchange succeeding with a pasted URL and the listener stopped is the proof that the escape hatch works independently of the delivery path: ```console $ token_tool --oauth-credentials…"
provenance:
  issue: "#4903"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

The existing lesson `mcporter-cloudflare-oauth-endpoint-scope-wsl-callback` says WSL2's automatic forwarding works for `localhost` but not for `127.0.0.1`, and its fix is to capture the `code=` from the address bar. Measured 2026-11-14 on a Windows host with an HTTP proxy configured, that is **not sufficient**:

1. **`localhost` is intercepted too.** The browser redirected to `http://localhost:<port>/` and hung — "无法访问此网站 / localhost 的响应时间过长" — instead of refusing. The listener was bound and healthy. The tell is the *shape* of the failure: `ERR_CONNECTION_REFUSED` means nothing is listening; a timeout means something (the proxy) is swallowing it. The lesson's advice (use `localhost` rather than `127.0.0.1`) is necessary but not sufficient when a proxy is in the path.

2. **A single-request listener loses the race.** The first implementation accepted exactly one request and then stopped serving. A browser — or a proxy in front of it — can deliver the same redirect twice; the listener consumed one delivery, the exchange was refused with

   ```json
   {"error": "invalid_grant", "error_description": "Bad Request"}
   ```

   and the second delivery hit a listener that had already gone. `invalid_grant` here says "that code is spent", not "your client is wrong", and the diagnostic cost is hours if the listener is already torn down.

3. **The wait window was a hidden constant.** The listener gave up after 5 minutes while every message describing it said "30 minutes". A listener that exits quietly is indistinguishable from one that was never reachable — two runs were lost to this.

## Root Cause

The lesson covers the *delivery path* (which loopback host reaches WSL) but not the *listener's own robustness*: how many requests it serves, how long it waits, and what it does when the exchange is refused. Those are the failure modes that remain after the forwarding problem is known.

## Fix

- Serve the loopback listener in a loop, and try each new `code` once: duplicate deliveries are normal, and a code can only be spent once.
- Keep listening after `invalid_grant` instead of exiting — a second navigation may carry a fresh code.
- Make the wait window an explicit argument and print it, so "no callback arrived" and "the listener quit" are different sentences.
- Always ship a listener-free escape hatch: accept the redirect URL from the browser's address bar and exchange the code directly, reusing the exact `redirect_uri` the code was issued for (some redirects are issued for a port the listener no longer owns).
- For a proxied Windows host, add `localhost`/`127.0.0.1` to the proxy bypass list (`NO_PROXY` or the client's `<local>` rule) *before* debugging the listener.

## Verification

The token exchange succeeding with a pasted URL and the listener stopped is the proof that the escape hatch works independently of the delivery path:

```console
$ token_tool --oauth-credentials <stored.json> --list-sites
1 property visible to this credential:
  https://misakanet.org/  [siteOwner]
```

With the listener stopped, exchanging the URL pasted from the browser's address bar returns a usable token (`sites.list` → `siteOwner`). With the loop listener, a duplicate redirect no longer produces `invalid_grant` on the first delivery.
