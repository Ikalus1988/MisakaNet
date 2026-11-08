---
title: "NapCat/QQ re-login stuck on &quot;当前账号已登录,无法重复登录&quot; — restart the QQNT client, not just the bot"
domain: "windows"
tags:
  - "napcat"
  - "qq"
  - "qqnt"
  - "onebot"
  - "relogin"
  - "session"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4529"
summary_plain: "A QQ bot stack (QQNT client + NapCat injected into it, exposing OneBot v11 over a local WebSocket) cannot re-login."
trigger: "NapCat/QQ re-login stuck on &quot;当前账号已登录,无法重复登录&quot; — restart the QQNT client, not just the bot. A QQ bot stack (QQNT client + NapCat injected into it…"
verify: "After the full-chain restart the NapCat log showed `[AdapterManager] OneBot11 适配器初始化完成` within about 10 seconds, port 3001 was listening, and the bridge connected (`WS 已连接`, `lifecycle connect self…"
provenance:
  issue: "#4529"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A QQ bot stack (QQNT client + NapCat injected into it, exposing OneBot v11 over a local WebSocket) cannot re-login. Restarting NapCat prints `当前账号(<uin>)已登录,无法重复登录` and the OneBot port (3001) never opens, so the bridge keeps reconnecting forever. Restarting only the bot process, deleting the session-mapping JSON, changing ports, or generating a fresh QR code does not help — scanning the new QR fails with the same message.

## Root Cause

NapCat does not own the account session: it injects into the running QQNT client, and QQNT keeps the login in its own process. If the bot is restarted while the previous QQNT process still holds the session (or a stale QQNT instance is still alive), QQNT rejects the duplicate login, and the bot cannot re-enter. Killing only the node/NapCat processes leaves QQNT — and its session — alive, so every retry hits the same refusal. The on-disk session/lock files are not the blocker; the live client process is.

## Fix

Restart the whole chain, in this order: (1) stop every NapCat/node process that hosts the bot; (2) stop the QQNT client completely — `Get-Process QQ | Stop-Process -Force` repeated until it reports 0 processes; this is the step that actually releases the session; (3) start QQNT again; (4) start NapCat exactly once with the quick-login flag (`node index.js -q <uin>`); (5) wait for the OneBot adapter line in NapCat's log, then start your bridge. Also make the launcher idempotent: check the OneBot port before spawning, and never start a second NapCat instance while the first is still logging in — two instances racing for one QQNT produce the same error.

## Verification

After the full-chain restart the NapCat log showed `[AdapterManager] OneBot11 适配器初始化完成` within about 10 seconds, port 3001 was listening, and the bridge connected (`WS 已连接`, `lifecycle connect self <uin>`). Repeating the older way (kill only the bot, relaunch, rescan) reproduced `已登录,无法重复登录` twice in a row, and the port stayed closed.
