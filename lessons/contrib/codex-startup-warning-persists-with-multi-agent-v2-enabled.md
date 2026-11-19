---
title: "Codex startup warning persists with multi-agent V2 enabled. Root Cause The expli"
domain: "mcp"
tags:
  - "codex"
  - "startup"
  - "warning"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5267"
summary_plain: "Codex startup warning persists with multi-agent V2 enabled."
trigger: "Codex [features].multi_agent is deprecated agents.enabled multi_agent_v2 startup warning"
verify: "Codex0.170.0 strict Doctor exits0 with21checks ok/no warnings; fresh config/read confirms supported subagent settings; complete MCP discovery and independent semantic-diff review pass. codex…"
provenance:
  issue: "#5267"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

Codex startup warning persists with multi-agent V2 enabled.

## Root Cause

The explicit deprecated features.multi_agent key remains inherited from user configuration.

## Fix

Remove only that deprecated key while retaining agents.enabled=true and features.multi_agent_v2=true. Audit effective configuration separately in every relevant launch directory. Do not blanket-enable development features or alter managed controls.

## Verification

Codex0.170.0 strict Doctor exits0 with21checks ok/no warnings; fresh config/read confirms supported subagent settings; complete MCP discovery and independent semantic-diff review pass.

codex --strict-config doctor --json returns exit0, overallStatus ok,21checks ok. Fresh config/read has no explicit multi_agent key and keeps V2 enabled.
