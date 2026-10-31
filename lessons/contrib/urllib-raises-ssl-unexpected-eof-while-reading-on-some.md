---
title: "urllib raises SSL: UNEXPECTED_EOF_WHILE_READING on some public JSON APIs while others work on the same host"
domain: "python"
tags:
  - "python"
  - "urllib"
  - "ssl"
  - "unexpected-eof"
  - "proxy"
  - "retry"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4191"
summary_plain: "In one batch probe from Windows, `urllib.request.urlopen()` returned `<urlopen error [SSL…"
trigger: "urllib raises SSL: UNEXPECTED_EOF_WHILE_READING on some public JSON APIs while others work on the same host. In one batch probe from Windows…"
verify: "Re-run the batch and check that every host has an explicit status line; per-host success rate above zero for the previously failing host after the UA change, or a documented alternate endpoint…"
provenance:
  issue: "#4191"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

In one batch probe from Windows, `urllib.request.urlopen()` returned `<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)>` for api.quotable.io, api.coincap.io/v2/assets and worldtimeapi.org/api, while api.coingecko.com, api.frankfurter.app and api.github.com answered 200 in the same process and second. Observed 2026-10-31, Python 3.12, traffic routed through a local HTTP proxy (127.0.0.1:7897).

## Root Cause

The TLS handshake succeeds far enough to negotiate, then the peer closes the socket without a close_notify, which Python reports as UNEXPECTED_EOF. With an intercepting/proxying egress this is typical of a middlebox or edge that resets connections to hosts it does not proxy cleanly (SNI-based routing, Cloudflare/edge hiccups, or a host that blackholes non-browser Clients). It is not a certificate problem, so patching the SSL context or disabling verification does not help, and the same request usually works from a different network.

## Fix

Treat it as a transient/host-level failure and route around it instead of retrying blindly:
1. Wrap each probe in its own try/except and record the per-host result; never let one host abort the batch.
2. Send a browser-shaped User-Agent (and Accept header) — some edges terminate non-browser clients at the TLS layer.
3. Retry the single host once with `urllib.request.urlopen(req, timeout=15)` in a fresh connection; if it fails twice, use an alternate endpoint for the same data rather than a third retry.
4. On Windows, compare against `curl.exe` in the same shell: if curl succeeds and urllib fails, it is the proxy path, not the API.

## Verification

Re-run the batch and check that every host has an explicit status line; per-host success rate above zero for the previously failing host after the UA change, or a documented alternate endpoint recorded in the probe output.
