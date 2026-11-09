---
title: "dsh-session-groups 装好却调不通：apply() 取 webServer/tools 服务失败，桥接路由没注册"
domain: "dsh"
tags:
  - "problem"
  - "dsh"
  - "session"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4540"
summary_plain: "dsh-session-groups 插件安装后，session_groups 工具调用失败，HTTP GET /dsh-session-groups-bridge/config 返回 404。插件没有报错日志，但桥接路由和工具都没注册。"
trigger: "Problem dsh-session-groups 插件安装后，session_groups 工具调用失败，HTTP GET /dsh-session-gro. dsh-session-groups 插件安装后，session_groups 工具调用失败，HTTP GET…"
verify: "session_groups.read 返回工作区列表，/dsh-session-groups-bridge/config 正常响应。 注意：该补丁是对插件源码的修改，升级插件会被覆盖，需重新应用。"
provenance:
  issue: "#4540"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

dsh-session-groups 插件安装后，session_groups 工具调用失败，HTTP GET /dsh-session-groups-bridge/config 返回 404。插件没有报错日志，但桥接路由和工具都没注册。

## Root Cause

插件 index.js 的 apply() 用 ctx.get('webServer') / ctx.get('tools') / ctx.get('approval') 取服务：

```js
const webServer = ctx.get('webServer');
const tools = ctx.get('tools');
const approval = ctx.get('approval');
if (!webServer || !tools || !approval) return;   // 静默返回，不注册任何东西
```

但该 bundle 的 inject 列表为空，这三个服务不在 fiber 解析链上，ctx.get() 返回 undefined → apply() 静默 return → 桥接路由和工具都没注册。没有错误日志，表现就是「插件装了但工具不存在」。

## Fix

改用 ctx.inject() 回调，只有三个服务都就绪时才执行挂载：

```js
ctx.inject(['webServer', 'tools', 'approval'], (webCtx) => mountBridge(webCtx));
```

## Verification

session_groups.read 返回工作区列表，/dsh-session-groups-bridge/config 正常响应。
注意：该补丁是对插件源码的修改，升级插件会被覆盖，需重新应用。
