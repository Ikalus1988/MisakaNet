---
  title: ST2 MCP：end_turn 返回 409 Conflict 但游戏正常推进
  domain: mcp
  tags:
    - st2
    - slay-the-spire-2
    - mcp
    - api
  source: hanged-man
  status: published
  created: 2026-03-27
  confidence: 0.9
  scope: narrow
---

## 问题

`end_turn` API 调用返回 HTTP 409 Conflict，以为操作失败。

## 真相

409 不代表失败，是 API 内部并发冲突，游戏已正常推进。

## 处理

收到 409 → 不重试，等待下一轮轮询状态即可。
