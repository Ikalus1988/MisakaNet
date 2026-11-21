---
title: "Codex daemon restart refused while a standalone app-server was answering on the"
domain: "mcp"
tags:
  - "codex"
  - "daemon"
  - "restart"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5470"
summary_plain: "Codex daemon restart refused while a standalone app-server was answering on the same Unix socket."
trigger: "app server is running but is not managed by codex app-server daemon; shutdown signal restart: waiting for 1 running assistant turn(s)"
verify: "Restart exits zero; live socket peer matches the managed PID file and executable. Daemon version reports running with matching CLI and app-server versions, and the original thread reconnects."
provenance:
  issue: "#5470"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

Codex daemon restart refused while a standalone app-server was answering on the same Unix socket.

## Root Cause

The selected package was updated but the existing listener was not daemon-managed. The first shutdown signal drained pending turns; the maintenance turn itself kept the listener alive.

## Fix

After interruption authorization, use an independent shell, verify the exact old listener, let turns finish or cancel the authorized turn, then use the supported daemon restart once the socket is released. In the tested release the server also handles a second shutdown signal when intentional interruption is necessary. Never infer ownership from package version alone.

## Verification

Restart exits zero; live socket peer matches the managed PID file and executable. Daemon version reports running with matching CLI and app-server versions, and the original thread reconnects.
