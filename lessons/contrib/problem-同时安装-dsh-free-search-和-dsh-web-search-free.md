---
title: "同时装 dsh-free-search 与 dsh-web-search-free：fetchProvider 报 not registered"
domain: "dsh"
tags:
  - "problem"
  - "dsh"
  - "free"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4539"
summary_plain: "同时装 dsh-free-search 与 dsh-web-search-free：fetchProvider 报 not registered"
trigger: "同时装 dsh-free-search 与 dsh-web-search-free：fetchProvider 报 not registered"
verify: "卸载 dsh-web-search-free 后，web.searchProvider=ddg + web.fetchProvider=fs-quality-fetch 均验证正常。"
provenance:
  issue: "#4539"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

同时安装 dsh-free-search 和 dsh-web-search-free 两个搜索插件后，设置 fetchProvider: web-search-free 时报：

```
configured web provider "web-search-free" is not registered
```

dsh-web-search-free 的 patch 里明确写了它注册的 provider id 就是 web-search-free，但运行时找不到。

## Root Cause

两个插件的 cordis.patch.yml 都注册了**同一条目 id = web-search-free**：

- dsh-web-search-free：name: dsh-web-search-free，注册 provider id=web-search-free
- dsh-free-search：name: dsh-free-search，注册 provider id=ddg + fs-quality-fetch

DSH 的 bundle patch 按 dsh.profile.bundles 顺序叠加，**同 id 条目后者整段覆盖前者 config**。dsh-free-search 在 bundles 列表中排在 dsh-web-search-free 之后，所以 dsh-web-search-free 的条目被覆盖，它的 search/fetch provider（id=web-search-free）从未注册。

## Fix

二选一：
1. 卸载功能较弱的 dsh-web-search-free（它搜索必须配 API Key，且无 keyless 引擎；dsh-free-search 有 10 个 keyless 免费引擎 + platform_search/domain_search/research 等工具，功能完全覆盖）。
2. 或在 dsh.profile.bundles 中把 dsh-web-search-free 放到 dsh-free-search 之后，并只给其中一个插件的 web-search-free 条目配 config。

## Verification

卸载 dsh-web-search-free 后，web.searchProvider=ddg + web.fetchProvider=fs-quality-fetch 均验证正常。
