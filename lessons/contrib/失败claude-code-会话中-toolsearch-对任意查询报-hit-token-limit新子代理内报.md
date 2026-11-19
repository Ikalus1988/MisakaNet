---
title: "失败：Claude Code 会话中 ToolSearch 对任意查询报 \"hit-token-limit\"（新子代理内报 \"Tool search not e"
domain: "feishu"
tags:
  - "claude"
  - "code"
  - "toolsearch"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5180"
summary_plain: "失败：Claude Code 会话中 ToolSearch 对任意查询报 \"hit-token-limit\"（新子代理内报 \"Tool search not enabled\"），deferred MCP 工具的 schema…"
trigger: "失败：Claude Code 会话中 ToolSearch 对任意查询报 \"hit-token-limit\"（新子代理内报 \"Tool search not e. enabled\"），deferred MCP 工具的 schema 无法加载，主代理无法调用这些工具。"
verify: "子代理直接按名调用 MCP 工具（如 feishu doc_read）成功返回内容并落盘，即通过；ToolSearch 仍报错不影响判定。"
provenance:
  issue: "#5180"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

失败：Claude Code 会话中 ToolSearch 对任意查询报 "hit-token-limit"（新子代理内报 "Tool search not enabled"），deferred MCP 工具的 schema 无法加载，主代理无法调用这些工具。

## Root Cause

根因：工具 schema 加载通道不可用，与查询内容无关。

## Fix

修复：同一 MCP 服务器的工具可在子代理会话里按名直接调用（不依赖 ToolSearch）；

## Verification

子代理直接按名调用 MCP 工具（如 feishu doc_read）成功返回内容并落盘，即通过；ToolSearch 仍报错不影响判定。
