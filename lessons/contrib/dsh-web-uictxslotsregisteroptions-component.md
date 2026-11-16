---
title: "DSH Web UI：`ctx.slots.register(options, component)` 传了「返回组件的工厂」时，标签页点开全白，且没有任何报错"
domain: "dsh"
tags:
  - "ctx.slots.register-options"
  - "ctx.slots.register"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5041"
summary_plain: "DSH Web UI：`ctx.slots.register(options, component)` 传了「返回组件的工厂」时，标签页点开全白，且没有任何报错。"
trigger: "DSH Web UI：`ctx.slots.register(options, component)` 传了「返回组件的工厂」时，标签页点开全白，且没有任何报错. DSH Web UI：`ctx.slots.register(options, component)`…"
verify: "1. 点开标签页截图：有标题、卡片、表格 → 修好；全白 → 还是这个病。 2. `cordis_inspect_query(platform:'client', provider:'Slots', method:'listSubTree', input:{root:'conversation.view'})` 只能证明 occupant…"
provenance:
  issue: "#5041"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH Web UI：`ctx.slots.register(options, component)` 传了「返回组件的工厂」时，标签页点开全白，且没有任何报错。

症状：一个自写 bundle 的 client 半边把对话区标签页注册成

```
ctx.slots.inject('conversation.view', () => ctx.slots.register({ name: 'conversation.view', id: 'x', order: 40, label: () => 'X' }, () => Panel))
```

结果：标签页出现在 tab 行里，点开后内容区完全空白；Host 的 `/plugin-x/state` 路由 200 且 JSON 正常；
Client 的初始化上报也照常返回；控制台无任何错误（桌面壳没有 devtools，所以更难发现）。

## Root Cause

`SlotCore.register(options, component)` 的第二个参数类型是 `SlotComponent<P> = (props: P) => ReactNode`，
登录的是**组件本身**。传入 `() => Panel` 时，这个函数本身被当成组件调用，返回的是另一个函数，
React 因此拿到「函数返回函数」的非法子节点，静默丢弃渲染结果——不抛错、不进入任何可见的错误边界。

## Fix

传组件本身：`ctx.slots.register({...}, Panel)`。

附带两条同批发现的判据：Host 侧时间给 UTC ISO，Client 直接 slice 会差时区；
改完 client.js 只需刷新应用窗口（Ctrl+R），不用重装、不用重启。

## Verification

1. 点开标签页截图：有标题、卡片、表格 → 修好；全白 → 还是这个病。
2. `cordis_inspect_query(platform:'client', provider:'Slots', method:'listSubTree', input:{root:'conversation.view'})`
   只能证明 occupant 注册成功、active:true，**不能**证明渲染正常（我第一次三条全绿、页面全白）。
