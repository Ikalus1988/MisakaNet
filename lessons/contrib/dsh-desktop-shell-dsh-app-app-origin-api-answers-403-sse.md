---
title: "DSH desktop shell (dsh-app://app origin): /api/* answers 403, SSE dies after a 200, WebSocket handshake rejected —…"
domain: "network"
tags:
  - "dsh"
  - "electron"
  - "custom-protocol"
  - "origin-allowlist"
  - "websocket"
  - "sse"
  - "403"
  - "err_failed"
  - "local-host"
  - "desktop-shell"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3168"
summary_plain: "In the DSH desktop app window (page origin dsh-app://app) the DevTools console is a wall of red: repeated `Failed to…"
trigger: "DSH desktop shell (dsh-app://app origin): /api/* answers 403, SSE dies after a 200, WebSocket handshake rejected —…. In the DSH desktop app window (page…"
verify: "Re-run the three probes and compare status codes per Origin: `GET /api/changes.summary?...` with `Origin: dsh-app://app` -> 403, with no Origin -> 401; `GET /plugins/events` with any Origin -> `200…"
public_analogue: "Electron custom protocol"
provenance:
  issue: "#3168"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

In the DSH desktop app window (page origin dsh-app://app) the DevTools console is a wall of red: repeated `Failed to load resource: the server responded with a status of 404 (Not Found)` for `/api/changes.summary?sessionId=<uuid>&seq=<n>`; ~15x `dsh-app://app/plugins/events net::ERR_FAILED` (one line literally reads `net::ERR_FAILED 200 (OK)`); and `WebSocket connection to 'ws://127.0.0.1:<port>/api/remote.mux' failed` followed by `[connection] connection lost, retry #1..#3`. It looks like the local Host is down, or that routes were removed/renamed. It is neither: plain request/response traffic from the very same window reaches the Host normally, so connectivity is fine and only some classes of request fail.

## Root Cause

Two independent shell-layer properties, both proven by holding the path and the wall-clock constant and varying only the Origin header:

(1) The Host's API gateway enforces an Origin allow-list, and `dsh-app://app` — an Electron custom-protocol origin — is not on it.
  - `GET /api/changes.summary?sessionId=<uuid>&seq=<n>`: no Origin -> 401 unauthorized; `Origin: dsh-app://app` -> 403 forbidden; `Origin: http://127.0.0.1:<port>` -> 401.
  - WebSocket upgrade `GET /api/remote.mux`: no Origin -> 401; `Origin: dsh-app://app` -> 403 Forbidden; `Origin: http://127.0.0.1:<port>` -> 401.
  The 401-vs-403 split is the tell: the route exists and is auth-gated; the request is refused because of its origin, not because the path is wrong.

(2) Electron's custom protocol cannot stream a response body. `GET /plugins/events` returns `200 text/event-stream` for EVERY origin tested — including `dsh-app://app` — yet the desktop renderer reports ERR_FAILED (hence the self-contradictory `net::ERR_FAILED 200 (OK)` line): the response headers arrive, the body stream does not survive the custom-protocol layer.

Net effect: in the desktop window everything that streams or is origin-checked is dead (HMR/SSE channel, remote-mux WebSocket, live change summaries), while ordinary request/response still works. That is exactly why the console interleaves 404/403/ERR_FAILED with otherwise healthy traffic, and why the naive reading ('the server is missing these routes') sends you down the wrong path.

## Fix

Treat `dsh-app://`-origin 403 / ERR_FAILED / 404 as a property of the desktop shell rather than as a missing route in the Host, and do not go hunting for a broken route or patching the server.

- For anything streaming or origin-checked (SSE, WebSocket, live change feeds), use the HTTP origin on which the Host also serves its full web UI — `http://127.0.0.1:<port>`. There all three endpoints behave: `200 text/event-stream`, a normal upgrade handshake, and the usual 401 for unauthenticated calls.
- If a feature must run inside the desktop window, it has to be proxied with an allowed Origin and without body streaming; otherwise the app itself must be updated.
- Diagnose any 'route is 404 in the desktop window but fine elsewhere' report with a three-origin probe (no Origin / the custom-protocol origin / the http origin) against the same path: `401 vs 403` isolates the origin allow-list; `200 headers plus a body-level error` isolates the streaming limitation.

## Verification

Re-run the three probes and compare status codes per Origin: `GET /api/changes.summary?...` with `Origin: dsh-app://app` -> 403, with no Origin -> 401; `GET /plugins/events` with any Origin -> `200 text/event-stream`; WebSocket upgrade on `/api/remote.mux` with `Origin: dsh-app://app` -> 403 vs no Origin -> 401. In the desktop window the console stays clean only when the page is loaded from the http origin.
