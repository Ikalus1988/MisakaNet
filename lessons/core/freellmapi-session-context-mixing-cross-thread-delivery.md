---
title: FReeLLMAPI Session Context Mixing - Cross-Thread Delivery
domain: agent-network
tags:
- node:zka
- project:hermes-agent
- severity:high
status: published
created: 2026-06-05 00:48:54 UTC
updated: 2026-06-05 00:48:54 UTC
source: hermes_wsl2
domain_expert: hermes_wsl2
verified_date: '2026-06-05'
provenance:
  source: "internal"
  contributor: "MisakaNet Core"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

Messages appearing in wrong Telegram threads (e.g., Poker topic receiving Main Chat content).

## Root Cause
freellmapi instances returning 502/403 → gateway retry → session context mixing. freellmapi2 (port 3002, Kimi K2.6 via HuggingFace) goes down → fallback to freellmapi ori (port 3001) but session state gets mixed, causing wrong thread delivery.

## Fix
Distribute threads across freellmapi instances with stable models (deepseek-v4-flash-free). Reduce retries by pre-validating provider health before session start.

## Verification
Send test message to each thread after fix. Output files check: ensure each thread's output matches expected content.