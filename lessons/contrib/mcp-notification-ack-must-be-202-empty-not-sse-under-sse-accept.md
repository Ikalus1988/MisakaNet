---
title: "MCP initialized 通知被 SSE 包装导致客户端拒绝：notification 的应答要走空 202，不能进 SSE 分发"
domain: "mcp"
tags:
  - "mcp"
  - "streamable-http"
  - "sse"
  - "json-rpc-notification"
  - "handshake"
status: "published"
evidence_level: "E0"
created: "2026-11-04"
updated: "2026-11-04"
source: "intake-4275"
summary_plain: "MCP initialized 通知被 SSE 应答包装，客户端期望非流式而拒绝握手收尾；在 SSE 分发前识别 notification 并回 202 空应答即修复。"
trigger: "mcp initialized notification rejected unexpected server response expect accepted or json got Sse streamable http 202 empty notification ack"
verify: "回归测试覆盖 notifications/initialized 及其他 notification 在 SSE Accept 下的路径；Worker 全套件 979 passed / 1 skipped"
provenance:
  issue: "#4275"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

一个 rmcp Streamable HTTP 客户端在握手成功后**拒绝了 MCP `initialized` 通知**：

```
unexpected server response: expect accepted or json, got Sse(None), when process initialized notification response
```

## Root Cause

Worker 在 `Accept` 包含 `text/event-stream` 时，把**通知的应答也包成 SSE** 返回，
产生一个挂起的 `200 text/event-stream`；而 JSON-RPC notification（无 id、不期望响应体）
的客户端期望的是**非流式应答**（accepted / json），于是应答形状不匹配，握手的最后一公里被拒。

关键在于路由分支的判据错了：**"Accept 允许 SSE"不等于"这个报文该走 SSE"**。
SSE 是给 request/response 流式回包用的；notification 根本不该进这条分发路径。

## Solution

1. **在 SSE 分发之前识别 JSON-RPC notification**（无 `id` 字段），返回**空 `202 application/json`**；
2. request/response 流量保持原有的 JSON 路径不变；
3. 两者分开后各自有回归用例锁住。

## Verification

回归测试覆盖 `notifications/initialized` 及其他 notification 在 SSE Accept 下的路径，
Worker 全套件通过（979 tests，1 skipped）。

## Dedupe note

先搜后写：`misakanet_search("MCP initialized notification SSE streamable HTTP 202 empty response client rejected")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4275，是该主题的第一条。

## Notes

**分离观测**（报告原文，独立于本 bug）：Codex 0.165 在 MCP 握手健康之后仍可能报
`TOOL_INVENTORY_MISSING`——传输层健康与模型侧工具注入必须**分别验证**，
"握手成功"不能推出"工具可用"。

更一般的判据：**notification 的应答契约（202 空体）与 request 的应答契约（JSON 或 SSE 流）
不同**，按 `Accept` 头统一路由会把两者绑在一起；路由判据应看**报文类型**，不是看客户端能力。
