---
title: "keep-alive 后 Playwright .first() 定位到隐藏页的同名元素：间歇性 not visible 超时"
domain: "mcp"
tags:
  - "problem"
  - "ui"
  - "keep"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4381"
summary_plain: "UI 从「切页卸载重建」改成 keep-alive（多页常驻 DOM + display 显隐）后，Playwright 自动化出现一类**间歇性**假红：`.first()` 定位的按钮/输入框「element is not…"
trigger: "Problem UI 从「切页卸载重建」改成 keep-alive（多页常驻 DOM + display 显隐）后，Playwright 自动化出现一类**间歇. UI 从「切页卸载重建」改成 keep-alive（多页常驻 DOM + display 显隐）后，Playwright…"
verify: "三脚本（单台/批量/转换）选择器全部定向后：单跑 48/48、5/5、13/13；release 门禁 14/14 连续全绿（此前连红两轮同一类）。 三脚本 48/48、5/5、13/13；门禁 14/14 连续两轮绿"
provenance:
  issue: "#4381"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

UI 从「切页卸载重建」改成 keep-alive（多页常驻 DOM + display 显隐）后，Playwright 自动化出现一类**间歇性**假红：`.first()` 定位的按钮/输入框「element is not visible」持续 30s 超时——本地单跑连续全绿、CI 门禁连红两次，且两次挂在不同用例的同名元素上（同一个「导出」按钮，一次在场景 A、一次在场景 B）。

## Root Cause

多页常驻后同名元素（各页都有「清除/开始分析/导出」按钮、各自的 file input）同时存在于 DOM。测试写 `page.locator('button', { hasText: 'X' }).first()` 依赖 DOM 顺序恰好把活跃页排前面；在负载环境下（渲染/挂载时序波动）隐藏页的同名元素会抢到 first 匹配，Playwright 对隐藏元素的点击/可见断言就永远失败。单跑时序好 → 复现不了；门禁负载下 → 稳定踩中。

## Fix

data-page 页容器标记 + 选择器定向到页容器；条件渲染按钮 waitFor visible 再点

## Verification

三脚本（单台/批量/转换）选择器全部定向后：单跑 48/48、5/5、13/13；release 门禁 14/14 连续全绿（此前连红两轮同一类）。

三脚本 48/48、5/5、13/13；门禁 14/14 连续两轮绿
