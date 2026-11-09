---
title: "Playwright/CDP 驱动 antd UI 验收时，点击嵌套 Collapse 的内层面板把已展开的外层又合上了：面板命中数=1、点击无报错，但内容始终"
domain: "mcp"
tags:
  - "playwright"
  - "cdp"
  - "antd"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4435"
summary_plain: "Playwright/CDP 驱动 antd UI 验收时，点击嵌套 Collapse 的内层面板把已展开的外层又合上了：面板命中数=1、点击无报错，但内容始终不出现（截图看才是折叠箭头朝右）。"
trigger: "Playwright/CDP 驱动 antd UI 验收时，点击嵌套 Collapse 的内层面板把已展开的外层又合上了：面板命中数=1、点击无报错，但内容始终. Playwright/CDP 驱动 antd UI 验收时，点击嵌套 Collapse…"
verify: "点击后截图必须能看到箭头朝下+表体行；断言表体单元格值（如越界 Tag、值 300）出现且界内行不误标。改造前 3 红（点击\"成功\"但内容不出现）、改造后 21/21 全绿。"
provenance:
  issue: "#4435"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Playwright/CDP 驱动 antd UI 验收时，点击嵌套 Collapse 的内层面板把已展开的外层又合上了：面板命中数=1、点击无报错，但内容始终不出现（截图看才是折叠箭头朝右）。

## Root Cause

两层选择器陷阱叠加：
1. `locator('.ant-collapse-item', { hasText: '字段明细' })` 的 hasText 会把**包含**该文案的外层父面板也命中——嵌套 Collapse（外层变化点条目包内层字段表）时 `.first()` 命中的是外层；点它的头部=把刚展开的外层又合上。
2. 同类问题：Modal 场景 `.ant-modal` 可能命中多个容器（页面挂着 FeedbackModal 等），`.last()` 抓到隐藏的那个，后续查找全部 count=0 静默跳过。

## Fix

1. 点折叠面板按**头部文案**定位 `.ant-collapse-header`（头部自身文案不含子面板内容，不会父子连坐）。
2. Modal 用内容特征筛选：`.ant-modal` + hasText 记录标题，取可见那个。
3. 关键步骤落 count 日志（modal 命中=1 变化点头部=1 …），别让 count=0 静默跳过。

## Verification

点击后截图必须能看到箭头朝下+表体行；断言表体单元格值（如越界 Tag、值 300）出现且界内行不误标。改造前 3 红（点击"成功"但内容不出现）、改造后 21/21 全绿。
