---
title: "DSH profile 的 dsh.profile.bundles 要写包全名，写裸名该插件静默不加载"
domain: "dsh"
tags:
  - "dsh"
  - "plugin"
  - "package-json"
  - "bundles"
  - "scoped-package"
  - "scoped"
  - "plugin-not-loading"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4241"
summary_plain: "在 DSH(DeepSeek Harness) profile 的 package.json 里，把新装的 scoped 包写成裸名放进 dsh.profile.bundles（例如包名是…"
trigger: "DSH profile 的 dsh.profile.bundles 要写包全名，写裸名该插件静默不加载. 在 DSH(DeepSeek Harness) profile 的 package.json 里，把新装的 scoped 包写成裸名放进…"
verify: "重启后插件页能看到该插件；它的 RPC 路由（如 /api/<插件名>/status）返回 401/200 而不是 404。"
provenance:
  issue: "#4241"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH(DeepSeek Harness) profile 的 package.json 里，把新装的 scoped 包写成裸名放进 dsh.profile.bundles（例如包名是 @scope/dsh-heartbeat，bundles 里写 dsh-heartbeat），重启后该插件不加载：没有报错、没有日志、插件页看不到，但 node_modules 里包是完整的、dependencies 也写对了。

## Root Cause

bundles 里的每一项按 npm 包名原样解析，加载器不做去 scope 的模糊匹配。scoped 包的完整名是 @scope/pkg，写裸名解析不到任何包，加载器静默跳过且不告警——所以现象是「装好了但什么都没发生」。

## Fix

在 dsh.profile.bundles 里写完整包名 @scope/pkg。参照同一列表里已存在的其它 scoped 条目确认格式（它们都是带 scope 的全名）。改完必须重启宿主，bundles 只在启动时读。

## Verification

重启后插件页能看到该插件；它的 RPC 路由（如 /api/<插件名>/status）返回 401/200 而不是 404。
