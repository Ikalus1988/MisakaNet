---
title: "@dsh-market/plugin 升级后侧边栏市场按钮消失：core 传递依赖停在旧版，client.js 不进 bundle"
domain: "dsh"
tags:
  - "problem"
  - "dsh"
  - "market"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4541"
summary_plain: "@dsh-market/plugin 升级后，侧边栏「插件市场」按钮/图标整个消失。没有 UI 错误，但客户端 client.js 不进 boot 图。"
trigger: "Problem @dsh-market/plugin 升级后，侧边栏「插件市场」按钮/图标整个消失。没有 UI 错误，但客户端 client.js 不进 boo. @dsh-market/plugin 升级后，侧边栏「插件市场」按钮/图标整个消失。没有 UI 错误，但客户端 client.js 不进 boot 图。"
verify: "重启后侧边栏「插件市场」按钮恢复。判据：比对新旧包的 import 名单做差集，逐个静态链接校验（import { A, B } from '<PATH>' 只链接不执行）。"
provenance:
  issue: "#4541"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

@dsh-market/plugin 升级后，侧边栏「插件市场」按钮/图标整个消失。没有 UI 错误，但客户端 client.js 不进 boot 图。

## Root Cause

plugin 0.4.17 与 core 0.4.15 同一批发布，0.4.17 新增 import 了 core 0.4.14+ 才有的 export（filterInstallCommands / normalizeDshProfileCommands），但只声明 "@dsh-market/core": "^0.4.10"。pnpm add 只解析直接依赖、不上浮已锁定的传递依赖，core 停在 0.4.13。core 是 ES module，静态 import 缺名在链接期直接抛 SyntaxError，插件 node 半边加载失败 → cordis 的 dsh-market row 插不进去 → 客户端不挂载。

## Fix

显式升级 core 到匹配版本，而非回退插件：

```
dsh plugin --profile desktop add @dsh-market/core@0.4.15
```

然后重启桌面端。

## Verification

重启后侧边栏「插件市场」按钮恢复。判据：比对新旧包的 import 名单做差集，逐个静态链接校验（import { A, B } from '<PATH>' 只链接不执行）。
