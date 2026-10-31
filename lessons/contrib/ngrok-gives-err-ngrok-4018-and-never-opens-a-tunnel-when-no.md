---
title: "ngrok gives ERR_NGROK_4018 and never opens a tunnel when no authtoken is configured"
domain: "network"
tags:
  - "ngrok"
  - "tunnel"
  - "localhost.run"
  - "ngrok-4018"
  - "reverse-proxy"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4190"
summary_plain: "Running `ngrok http 8123` on a fresh Windows install exits with `ERR_NGROK_4018 authentication failed: This ngrok…"
trigger: "ngrok gives ERR_NGROK_4018 and never opens a tunnel when no authtoken is configured. Running `ngrok http 8123` on a fresh Windows install exits with…"
verify: "Run `curl -sS -o /dev/null -w \"%{http_code}\" https://<subdomain>.lhr.life/` and expect 200, then re-run it after a tunnel restart to see that the subdomain changed (localhost.run free tier issues a…"
provenance:
  issue: "#4190"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Running `ngrok http 8123` on a fresh Windows install exits with `ERR_NGROK_4018 authentication failed: This ngrok session is not authenticated. ngrok requires an account and a valid credential to start a session.` The local port is fine (curl 127.0.0.1:8123 returns 200) and the config file is empty. Observed 2026-10-31 on ngrok v3.39.13, Windows 10/11, no account created.

## Root Cause

Since 2021 ngrok requires an authtoken for every session, including the free tier. There is no anonymous mode: the binary installs and reports `ngrok config check` as clean, so the failure looks like a network or firewall problem when it is actually a missing credential. The tunnel is never established, so nothing listens on the public side.

## Fix

Pick an exit that needs no account instead of trying to bypass the [REDACTED://[REDACTED:url_credential]@host gives a free https subdomain with no signup; parse the subdomain from stdout with `grep -oE "[a-z0-9]+\.lhr\.life"`.
2. If you do want ngrok, sign up once, then `ngrok config add-authtoken <token>`; the token is required even on the free plan.
3. Do not use `--domain`, `--subdomain` or a stable hostname on free localhost.run: `<REDACTED:email>` with a named tunnel answers 502 because fixed hostnames are paid.

## Verification

Run `curl -sS -o /dev/null -w "%{http_code}" https://<subdomain>.lhr.life/` and expect 200, then re-run it after a tunnel restart to see that the subdomain changed (localhost.run free tier issues a new random subdomain on every reconnect, so any hardcoded URL stops working).
