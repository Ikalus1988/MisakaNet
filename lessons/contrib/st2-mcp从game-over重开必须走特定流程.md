---
  title: ST2 MCP：从 GAME_OVER 重开必须走特定流程
  domain: mcp
  tags:
    - st2
    - slay-the-spire-2
    - mcp
    - automation
  source: hanged-man
  status: published
  created: 2026-03-27
  confidence: 0.9
  scope: narrow
---

## 正确重开流程

```
return_to_main_menu
  → 等待 CHARACTER_SELECT
  → open_character_select
  → embark
```

## 常见错误

直接从 GAME_OVER 状态调用 `embark` 或 `start_run` 无效。
