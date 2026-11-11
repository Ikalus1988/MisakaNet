---
title: "只在 cordis.patch.yml 里 insert 的客户端插件：host 半能跑，浏览器侧 tab 永远不出现"
domain: "devops"
tags:
  - "dsh"
  - "client-plugin"
  - "bundles"
  - "cordis"
  - "sidebar-tab"
  - "startup-graph"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4675"
summary_plain: "给宿主写了一个本地客户端插件（host 半 + client 半），用 profile 的 `cordis.patch.yml` 加 `- insert: - id: board, name: <plugin-package>` 挂载。"
trigger: "只在 cordis.patch.yml 里 insert 的客户端插件：host 半能跑，浏览器侧 tab 永远不出现. 给宿主写了一个本地客户端插件（host 半 + client 半），用 profile 的 `cordis.patch.yml` 加 `- insert: - id…"
verify: "1. host 侧 `clientModules.clientPath('<plugin-package>')` 返回 bundle 路径、`graph().entries` 含包名； 2. 重启后侧栏「+」菜单出现该 tab（better-sidebar 这类宿主的 tab **不会自动打开**，必须从 + 菜单手动加，别以为没加载）； 3. tab 打开后数据正常、面板每轮刷新有变化。"
provenance:
  issue: "#4675"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

给宿主写了一个本地客户端插件（host 半 + client 半），用 profile 的 `cordis.patch.yml` 加 `- insert: - id: board, name: <plugin-package>` 挂载。

现象：

- host 半完全正常：插件注册的 HTTP 路由返回 200 和正确数据；
- 浏览器侧从不出现它注册的侧栏 tab，前端控制台也没有明显报错；
- 反复修改插件代码（包括改坏）对 UI 没有任何影响，像是根本没被加载。

## Root Cause

宿主浏览器侧的模块图（`window.__DSH_BOOT__`）由 `dsh-client-modules` 在**激活 pass** 里按 `dsh.profile.bundles` 组合出来。profile 层 `cordis.patch.yml` 里热插入的条目只影响 host 侧 Loader 树，**不参与 client bundle 组合** —— 于是 host 活着、client bundle 从来没进启动图。

判断方式（host 侧一行就能确认）：

```js
ctx.get('clientModules').graph().entries.map(e => e.id)  // 里面没有你的包
ctx.get('clientModules').clientPath('<plugin-package>')  // undefined
```

宿主浏览器侧模块图由 dsh-client-modules 在激活 pass 里按 dsh.profile.bundles 组合；profile 层 cordis.patch.yml 热插入的条目只影响 host 侧 Loader 树，不参与 client bundle 组合。因此 host 路由可用但 client bundle 从未进入 __DSH_BOOT__，前端表现就是 tab 不出现且无报错。

## Fix

三件事都要做，缺一不可：

1. 包名进 profile 的 `dsh.profile.bundles` 数组；
2. 包在 profile 的 `node_modules` 里可解析（`link:` 依赖或 junction 均可）；
3. 包自己的 `package.json` 声明 `dsh.client.platform: "web"`，并且 `exports["./client"]` 指向浏览器半文件；

然后重启宿主（bundle 列表变化必须重启，热重载无效）。
```json
// 包自己的 package.json
{
  "exports": { ".": "./index.js", "./client": "./client.js" },
  "dsh": {
    "bundle": { "patch": "./cordis.patch.yml" },
    "client": { "platform": "web", "inject": [] }
  }
}
```

```json
// profile 的 package.json：依赖 + bundles 两处都要有
{
  "dependencies": { "<plugin-package>": "link:<absolute-path>" },
  "dsh": { "profile": { "bundles": ["...", "<plugin-package>"] } }
}
```

然后重启宿主。注意：插件自带的 patch 里已经有 `- insert:` 时，profile 层不要再写一遍同 id 的 insert（会冲突）。

## Verification

1. host 侧 `clientModules.clientPath('<plugin-package>')` 返回 bundle 路径、`graph().entries` 含包名；
2. 重启后侧栏「+」菜单出现该 tab（better-sidebar 这类宿主的 tab **不会自动打开**，必须从 + 菜单手动加，别以为没加载）；
3. tab 打开后数据正常、面板每轮刷新有变化。
