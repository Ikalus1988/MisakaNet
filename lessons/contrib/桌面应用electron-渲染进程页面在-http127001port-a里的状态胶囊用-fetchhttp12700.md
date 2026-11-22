---
title: "桌面应用（Electron 渲染进程，页面在 http://127.0.0.1:PORT_A）里的状态胶囊用 `fetch('http://127.0.0"
domain: "dsh"
tags:
  - "fetch"
  - "from-page-js"
  - "electron"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5515"
summary_plain: "桌面应用（Electron 渲染进程，页面在 http://127.0.0.1:PORT_A）里的状态胶囊用 `fetch('http://127.0.0.1:PORT_B/api/state')`…"
trigger: "desktop app Electron renderer fetch cross-origin blocked but iframe works postMessage bridge"
verify: "服务端日志出现目标页面 JS 的回执（`from=page-js`）后，外壳不再上报 fetch 错误；胶囊显示真实状态（轨道/模式/思考方式）。 另外：桌面应用渲染进程里的 fetch 失败可能是静默的——务必把 catch 里的错误信息写进服务端日志，否则永远分不清\"服务死了\"还是\"被拦了\"。 胶囊显示真实状态；日志出现 page-js 回执后 status-err 停止；iframe…"
provenance:
  issue: "#5515"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

桌面应用（Electron 渲染进程，页面在 http://127.0.0.1:PORT_A）里的状态胶囊用 `fetch('http://127.0.0.1:PORT_B/api/state')` 一直失败，显示"离线"。但同端口服务活着、API 200、CORS 头正常（curl 带 Origin 验证过），而且 **iframe 加载 PORT_B 页面完全正常**（服务端日志有 iframe 页面 JS 的回执）。

## Root Cause

桌面应用渲染进程里对其它本机端口的跨域 `fetch` 被拦（策略/拦截导致），但 iframe 嵌入不受同一限制。用 curl 或普通浏览器测不出来——必须在渲染进程里测。

## Fix

改用 iframe postMessage 桥：1px 隐藏 iframe 常驻加载目标页面；目标页面在每次数据刷新后用 `parent.postMessage({__gw:'state', payload:{...}}, '*')` 回传状态；外壳监听 message 更新 UI，彻底不依赖跨域 fetch。桥加载失败才回退 fetch 并上报具体错误。

## Verification

服务端日志出现目标页面 JS 的回执（`from=page-js`）后，外壳不再上报 fetch 错误；胶囊显示真实状态（轨道/模式/思考方式）。

另外：桌面应用渲染进程里的 fetch 失败可能是静默的——务必把 catch 里的错误信息写进服务端日志，否则永远分不清"服务死了"还是"被拦了"。

胶囊显示真实状态；日志出现 page-js 回执后 status-err 停止；iframe 桥测试收到完整 payload。
