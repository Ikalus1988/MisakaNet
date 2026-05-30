---
  title: ST2 danielstarman MCP：选 Rare Relic 会卡死
  domain: mcp
  tags:
    - st2
    - slay-the-spire-2
    - mcp
    - automation
  source: hanged-man
  status: published
  created: 2026-03-27
  confidence: 0.95
  scope: narrow
---

## 问题

选择 Neow Rare Relic 选项后，游戏进入 `overlay` 状态，`screen: UNKNOWN`，`available_actions: []`，自动化卡死。

## 根因

Rare Relic 选择触发游戏内 modal dialog，MCP API 无法处理 overlay 状态。

## 规避方案

**不选 Rare Relic 选项**，使用其他 Neow 祝福。

## 相关

- `state_type: overlay` = 游戏有模态弹窗，需手动处理
- `overlay` 状态下 STS2AIAgent (port 8080) `POST` 仍可返回，不超时
- danielstarman STS2MCP (port 15526) 在 overlay 状态会卡死（超时 15s+）
