---
title: "Local proxy to NapCat returns WinError 10061 because OneBot HTTP port is not listening"
domain: "network"
tags:
  - "napcat"
  - "onebot"
  - "proxy"
  - "winerror10061"
  - "port"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3782"
summary_plain: "A client connects to a local HTTP proxy (127.0.0.1:3001) that forwards to the NapCat OneBot HTTP port (127.0.0.1:3000)…"
trigger: "Local proxy to NapCat returns WinError 10061 because OneBot HTTP port is not listening. A client connects to a local HTTP proxy (127.0.0.1:3001) that forwards…"
verify: "Upstream port listening (Test-NetConnection) and a direct get_login_info against it returns status ok; the proxy call then succeeds too."
provenance:
  issue: "#3782"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A client connects to a local HTTP proxy (127.0.0.1:3001) that forwards to the NapCat OneBot HTTP port (127.0.0.1:3000) adding an [REDACTED:bearer_token] Every call fails with "proxy error: [WinError 10061]" (connection refused), while the proxy port itself is listening.

## Root Cause

NapCat never bound its OneBot HTTP port because the QQ side failed to inject (expired login session, or several NapCatWinBootMain instances fighting each other). The proxy is healthy; its upstream is not.

## Fix

Check whether the upstream port is actually listening. If not, kill all QQ and NapCatWinBootMain processes, relaunch one launcher, wait at least 60-90 seconds, and log in again if the session expired. Only then treat the proxy as the problem.

## Verification

Upstream port listening (Test-NetConnection) and a direct get_login_info against it returns status ok; the proxy call then succeeds too.
