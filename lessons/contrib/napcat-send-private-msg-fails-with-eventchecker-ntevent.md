---
title: "NapCat send_private_msg fails with EventChecker NTEvent Listener while receive works"
domain: "network"
tags:
  - "napcat"
  - "onebot"
  - "qq"
  - "sendmsg"
  - "eventchecker"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3781"
summary_plain: "OneBot send_private_msg through NapCat returns {\"status\":\"failed\",\"retcode\":200,\"data\":null,\"message\":\"EventChecker…"
trigger: "NapCat send_private_msg fails with EventChecker NTEvent Listener while receive works. OneBot send_private_msg through NapCat returns…"
verify: "send_private_msg returns {\"status\":\"ok\"} with a numeric message_id and the target account receives it."
provenance:
  issue: "#3781"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

OneBot send_private_msg through NapCat returns {"status":"failed","retcode":200,"data":null,"message":"EventChecker Failed: NTEvent serviceAndMethod:NodeIKernelMsgService/sendMsg Listener"}. Incoming messages still arrive and message-history calls still work, so port and login checks all pass.

## Root Cause

The QQNT client internal send-message listener is dead while the receive path stays alive. NapCat is a client-side injection: when that listener stops, the OneBot HTTP layer answers 200 with status=failed instead of a transport error, so a watchdog that only probes port reachability never notices.

## Fix

Restart the QQ client behind NapCat: kill every QQ process under the NapCat install directory and the NapCatWinBootMain launcher, then relaunch. If the saved login session was invalidated, log in again (QR scan). Add a send-path probe to any watchdog: after a health check, call send_private_msg with a tiny message and treat status!=ok as unhealthy.

## Verification

send_private_msg returns {"status":"ok"} with a numeric message_id and the target account receives it.
