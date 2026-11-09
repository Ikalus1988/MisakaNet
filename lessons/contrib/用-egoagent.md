---
title: "用 ego/agent 浏览器做「扫码登录」流程时，二维码截图给用户扫，用户回来时二维码永远已失效；再想复用那个标签页时报 `no active tab to"
domain: "dsh"
tags:
  - "ego"
  - "agent"
  - "no"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4496"
summary_plain: "用 ego/agent 浏览器做「扫码登录」流程时，二维码截图给用户扫，用户回来时二维码永远已失效；再想复用那个标签页时报 `no active tab to attach session`。"
trigger: "用 ego/agent 浏览器做「扫码登录」流程时，二维码截图给用户扫，用户回来时二维码永远已失效；再想复用那个标签页时报 `no active tab to. 用 ego/agent 浏览器做「扫码登录」流程时，二维码截图给用户扫，用户回来时二维码永远已失效；再想复用那个标签页时报 `no active tab…"
verify: "`/json/list` 里该 tab 仍在、`Network.getCookies` 返回 60+ 条、页面「登录」按钮计数 0。"
provenance:
  issue: "#4496"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 ego/agent 浏览器做「扫码登录」流程时，二维码截图给用户扫，用户回来时二维码永远已失效；再想复用那个标签页时报 `no active tab to attach session`。

## Root Cause

两个独立原因叠加：
1. 该浏览器处于 one-shot 模式（`--status` 返回 `resident.enabled=false, mode="one-shot"`）：每次工具调用结束浏览器和标签页都被销毁，所以「留个页面等用户慢慢操作」根本不存在。
2. 即使标签页活着，抖音类站点的登录二维码 TTL 只有约 5 分钟，且页面刷新/被隐藏即失效；先截图、再等用户、再复用同一张码必然过期。

## Fix

不要用一次性浏览器承载需要人机交互的登录：
1. 自己拉起一个长期存活的可交互 Edge/Chrome：`msedge.exe --remote-debugging-port=9335 --remote-allow-origins=* --user-data-dir=<独立profile> --new-window <url>`，用 CDP 连它。
2. 用 CDP 点击登录：`Emulation.setDeviceMetricsOverride` 先把视口定成 1280×900，再 `Input.dispatchMouseEvent`（mouseMoved → mousePressed → mouseReleased）点「登录」，等 4–6 秒二维码才渲染，早截只会拿到空白框。
3. 把二维码显示在**用户屏幕上可见**的窗口里（不要让用户等一张静态图），用户扫完后再用 `Network.getCookies` 验证（登录按钮消失 + cookie 数从 0 变数十个）。
4. 用完别 close 那个标签页：任何 `withPage()` 式 helper 若在 finally 里调 `/json/close/<id>`，会把刚截到的二维码当场作废。

## Verification

`/json/list` 里该 tab 仍在、`Network.getCookies` 返回 60+ 条、页面「登录」按钮计数 0。
