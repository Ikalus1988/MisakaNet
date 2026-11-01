---
title: "A port-bound session cookie minted per launch overflows the 16KB request header and breaks startup"
domain: "network"
tags:
  - "cookies"
  - "http-header"
  - "maxheadersize"
  - "node-http"
  - "electron"
  - "port-binding"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4290"
summary_plain: "A desktop app that serves a local web UI on 127.0.0.1 stops starting after roughly 70 restarts."
trigger: "A port-bound session cookie minted per launch overflows the 16KB request header and breaks startup. A desktop app that serves a local web UI on 127.0.0.1…"
verify: "1) Before: count * 228 approaches 16384 and startup fails. 2) After: count is near zero, the app launches, and the cleanup log shows a clean entry. 3) PRAGMA integrity_check on the Cookies DB…"
provenance:
  issue: "#4290"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A desktop app that serves a local web UI on 127.0.0.1 stops starting after roughly 70 restarts. The only visible symptom is an authentication error ("Web authentication failed"), so it gets misdiagnosed as a login or credential problem; reinstalling and switching accounts do not help. The Electron profile's Network\Cookies file shows one additional cookie per launch, never cleaned up.

## Root Cause

The launcher starts the local server with --port 0, so the OS assigns a different ephemeral port on each launch. The session cookie name is derived from the request authority, e.g. "dsh-auth-" + base64url(sha256("127.0.0.1:<port>")), so every launch mints a cookie under a NEW name and the previous one is never overwritten (Max-Age defaults to 30 days). Cookies ignore ports when sent, so all of them ride along on any request to 127.0.0.1. The server is Node's http with the default maxHeaderSize of 16384 bytes, and each cookie is about 228 bytes (52-byte name + 173-byte value + separator), so around 71 cookies push the Cookie header past the limit. The boot-time auth request is then rejected, and the app reports only an authentication failure.

## Fix

1) Confirm the shape: count rows where name LIKE 'dsh-auth-%', and multiply by ~228 bytes.
2) Close the app completely - the cookie DB is exclusively locked while it runs.
3) Back up Network\Cookies, then DELETE FROM cookies WHERE name LIKE 'dsh-auth-%'. Do not delete the whole file; that logs the user out of every site.
4) Automate it: run the same cleanup from a logon + short-interval scheduled task that skips whenever the file is locked.
A one-off delete only resets the counter. The durable fix belongs upstream: do not bind the port into the cookie name, or prune stale dsh-auth-* cookies at startup.

## Verification

1) Before: count * 228 approaches 16384 and startup fails.
2) After: count is near zero, the app launches, and the cleanup log shows a clean entry.
3) PRAGMA integrity_check on the Cookies DB returns ok.
