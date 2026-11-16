---
title: "Electron 桌面壳里，「打开 Web UI」按钮点击后完全无反应：无报错、无新窗口、无进程变化。 现象细节 Web 插件面板内嵌的 iframe 显示正常"
domain: "dsh"
tags:
  - "openexternal"
  - "location"
  - "streambaseurl"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5040"
summary_plain: "Electron 桌面壳里，「打开 Web UI」按钮点击后完全无反应：无报错、无新窗口、无进程变化。"
trigger: "Electron 桌面壳里，「打开 Web UI」按钮点击后完全无反应：无报错、无新窗口、无进程变化。 现象细节 Web 插件面板内嵌的 iframe 显示正常. Electron 桌面壳里，「打开 Web UI」按钮点击后完全无反应：无报错、无新窗口、无进程变化。"
verify: "1. 页面重载后按钮的 title/description 变成 `http://127.0.0.1:PORT/__bili/`；2. 点击后 tasklist 出现 msedge.exe 且 desktop 出现标题为该页面标题的新窗口；3. 该 URL curl 返回 200。"
provenance:
  issue: "#5040"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Electron 桌面壳里，「打开 Web UI」按钮点击后完全无反应：无报错、无新窗口、无进程变化。

## Root Cause

1. 该按钮的 URL 基址来自宿主注入的 global（插件在 adminRelay 模式下注入 origin=null 且 relay=true），插件只能用 `location`/注入值拼出 `dsh-app://app` 这种自定义协议基址。
2. 桌面壳主窗口的 Electron 策略是：`setWindowOpenHandler(({url}) => { if (["http:","https:"].includes(new URL(url).protocol)) shell.openExternal(url); return {action:"deny"} })` —— 非 http(s) 协议直接 deny，且 deny 是**静默**的。
3. 插件侧 `openExternal` 用 `window.open(url,"_blank","noopener,noreferrer")`，于是窗口请求被静默丢弃，看起来就是“按钮坏了”。

## Fix

在插件侧解析“可打开的外部基址”：渲染进程里 `globalThis.__DSH_TRANSPORT__.streamBaseUrl` 是桌面壳注入的宿主真实 origin（形如 http://127.0.0.1:PORT，由 Electron 主进程 `streamBaseUrl: new URL(hostUrl).origin` 提供），当按钮基址不是 http(s) 时改用它，再拼 `/__bili/` 交给 window.open。不要硬编码端口——端口是随机的，必须走运行时注入值。

## Verification

1. 页面重载后按钮的 title/description 变成 `http://127.0.0.1:PORT/__bili/`；2. 点击后 tasklist 出现 msedge.exe 且 desktop 出现标题为该页面标题的新窗口；3. 该 URL curl 返回 200。
