---
title: "UI 自动化测试正向断言偶发假红：单独跑全绿，连跑或进 CI 门禁就红，且失败项后面的点击断言却全过（说明元素其实存在、可点）。 场景：表单提交后断言「结果卡片"
domain: "mcp"
tags:
  - "ui"
  - "ci"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-3081"
summary_plain: "UI 自动化测试正向断言偶发假红：单独跑全绿，连跑或进 CI 门禁就红，且失败项后面的点击断言却全过（说明元素其实存在、可点）。"
trigger: "UI 自动化测试正向断言偶发假红：单独跑全绿，连跑或进 CI 门禁就红，且失败项后面的点击断言却全过（说明元素其实存在、可点）。 场景：表单提交后断言「结果卡片. UI 自动化测试正向断言偶发假红：单独跑全绿，连跑或进 CI 门禁就红，且失败项后面的点击断言却全过（说明元素其实存在、可点）。"
verify: "同一测试脚本连跑 3 次全绿（此前 2 跑 1 红 1 绿）；完整门禁 release 层 10 项全绿复验通过。"
provenance:
  issue: "#3081"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

UI 自动化测试正向断言偶发假红：单独跑全绿，连跑或进 CI 门禁就红，且失败项后面的点击断言却全过（说明元素其实存在、可点）。 场景：表单提交后断言「结果卡片里的标签可见」「某按钮可见」。 写法是 await locator.isVisible().catch(() => false)。

## Root Cause

根因：isVisible() 不等待元素出现，调用瞬间不在 DOM 就返回 false。

## Fix

正向断言（「应当出现」）一律 waitFor({state:'visible', timeout}) 再判；负向断言（「应当不出现」）继续用 isVisible 即可——等待对它们无意义。写成 visibleWithin() 助手统一调用。

## Verification

同一测试脚本连跑 3 次全绿（此前 2 跑 1 红 1 绿）；完整门禁 release 层 10 项全绿复验通过。
