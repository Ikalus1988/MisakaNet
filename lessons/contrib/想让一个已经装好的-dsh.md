---
title: "想让一个已经装好的 DSH 客户端插件在左栏「插件」组常驻，但插件只注册了设置行（plugins.row.config）和会话标题按钮，没有 sidebar.p"
domain: "dsh"
tags:
  - "sidebar.panellist"
  - "main"
  - "if"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4885"
summary_plain: "想让一个已经装好的 DSH 客户端插件在左栏「插件」组常驻，但插件只注册了设置行（plugins.row.config）和会话标题按钮，没有 sidebar.panellist。"
trigger: "想让一个已经装好的 DSH 客户端插件在左栏「插件」组常驻，但插件只注册了设置行（plugins.row.config）和会话标题按钮，没有 sidebar.p. panellist。"
verify: "渲染进程 ctrl+r 重载后左栏出现入口；点开面板顶部完整、语言已翻译、admin/status 数据能拉到；点 ✕ 回到会话。"
provenance:
  issue: "#4885"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

想让一个已经装好的 DSH 客户端插件在左栏「插件」组常驻，但插件只注册了设置行（plugins.row.config）和会话标题按钮，没有 sidebar.panellist。

## Root Cause

1) 插件 apply() 里注册的槽位决定了它的入口位置，没有同时注册 `sidebar.panellist`（左栏图标）和 `main`（整页面板）就不会有常驻入口；两者 id/key 必须同名，否则 layout.selectPanel 抛错。
2) 注册代码若放在 `if (isDesktopShell()) return` 之后（插件里常见这种桌面门，因为桌面 App 自己就是主服务端），桌面端永远不执行。
3) 复用插件内部设置组件时，翻译命名空间不是包名：插件用 `ctx.locale.register(NS, …)` 注册字典（本例 NS='mobileNav'），bind 包名会直接渲染出 `settings.roleTitle` 这类原始 key。

## Fix

在已安装插件的客户端 bundle（node_modules/<pkg><PATH>，单文件 CJS，模块名形如 __modules["client/index.js"]）里，于 `function apply(ctx) {` 前插入一个 installXxx(ctx) 辅助块，并在桌面门之前调用它：探测 `typeof layout.selectPanel === 'function'`，然后双注册 panellist 与 main；面板自己画标题栏和滚动区，关闭用 layout.selectPanel(null)，组件 props 用 {view:'page', t: ctx.locale.bind(locales_ts_1.NS), config: new XxxSettingsForm(...), shares: getSharesStore()}。补丁写成幂等脚本（锚点唯一才改、含 MARK 跳过、支持 --revert、写前备份 .orig）。写 ~/.dsh 目录需要危险全访问权限（超出 workspace 沙箱）。

## Verification

渲染进程 ctrl+r 重载后左栏出现入口；点开面板顶部完整、语言已翻译、admin/status 数据能拉到；点 ✕ 回到会话。
