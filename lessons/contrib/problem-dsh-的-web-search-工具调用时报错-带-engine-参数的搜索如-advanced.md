---
title: "DSH web_search 报 multiple usable web providers：seam 的 searchProvider 为空，多 provider 并存"
domain: "dsh"
tags:
  - "problem"
  - "dsh"
  - "web"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4538"
summary_plain: "DSH 的 web_search 工具调用时报错： ``` ToolCallError: multiple usable web providers are registered (deepseek-official…"
trigger: "Problem DSH 的 web_search 工具调用时报错： 带 engine 参数的搜索（如 advanced_search({engine:\"ddg. DSH 的 web_search 工具调用时报错： ``` ToolCallError: multiple usable web providers are…"
verify: "web_search({queries:[\"test\"]}) 返回 8 条来源，不再报 multiple providers 错误。"
provenance:
  issue: "#4538"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 的 web_search 工具调用时报错：

```
ToolCallError: multiple usable web providers are registered (deepseek-official, deepseek-search-api, ddg); configure one explicitly
```

带 engine 参数的搜索（如 advanced_search({engine:"ddg"})）正常，但不带引擎的 web_search 直接失败。环境里同时装了 dsh-free-search（注册 ddg/bing/exa 等免费引擎）和 DSH 自带的 deepseek-official / deepseek-search-api provider。

## Root Cause

web seam（composition 条目 id=web）的 searchProvider 字段为空或为默认值时，seam 无法自动选择唯一 provider。dsh-free-search 的 patch 故意不写 searchProvider（issue #51：写死会在插件禁用时留下 dangling 引用），所以当多个 provider 同时注册就会报这个错。

## Fix

在 profile 的 cordis.patch.yml 中显式给 web 条目设置 searchProvider：

```yaml
- id: web
  config:
    searchProvider: ddg      # 或 bing / exa 等已注册的引擎 id
    fetchProvider: fs-quality-fetch
```

保存后立即生效（volatile config），web_search 不带引擎也能正常返回结果。

## Verification

web_search({queries:["test"]}) 返回 8 条来源，不再报 multiple providers 错误。
