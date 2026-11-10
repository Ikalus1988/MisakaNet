---
title: "DSH 桌面版装 dsh-windows-mcp：工具注入失败，惰性工具永久隐藏"
domain: "windows"
tags:
  - "dsh"
  - "rc"
  - "profile"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4606"
summary_plain: "DSH 桌面版装 dsh-windows-mcp：工具注入失败，惰性工具永久隐藏"
trigger: "DSH 桌面版装 dsh-windows-mcp：工具注入失败，惰性工具永久隐藏"
verify: "脚本 `tools/list` 返回 18 个工具；用 `tools/call` 截图并用截图坐标点击，成功驱动 WeGame 登录并在其中启动英雄联盟，全程不依赖 DSH 工具注入。 tools/list 返回 18 个工具；截图+坐标点击实测驱动 WeGame 登录并启动英雄联盟"
provenance:
  issue: "#4606"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

症状：DSH 桌面版（0.2.2-rc.1，profile desktop）装 dsh-windows-mcp 0.2.4 后，电脑操作开关已打开、`windows-mcp.exe serve` 子进程在跑、profile 里 `windows-mcp-bridge` 行是 `disabled: false` 且 command 指向已装 exe、状态文件 `~/.dsh/dsh-windows-mcp.state.json` 为 `enabled: true`，agent 上下文里也能看到 MCP 资源服务器 `windows`，**但模型工具表里既没有 `mcp__windows__*` 工具，也没有解锁用的 `windows_desktop`**。报错链条：先提示 "电脑操作 is switched off"（打开胶囊后），再提示 "mcp__windows__Snapshot is hidden to save context. Call windows_desktop first"，而 `windows_desktop` 本身不在工具表里 → 死锁。

## Root Cause

插件的 host 半部靠注入 DSH 的 `tools` 服务来注册 `windows_desktop`（惰性解锁工具）与桥接工具的白名单；该 DSH 版本下这条注入没生效（插件代码里存在 "could not inject the tools service for the reveal tool" 告警路径）。reveal 工具没注册，惰性模式永不解除，于是桥工具对模型永久隐藏。重启 DSH、把 windows-mcp 从 0.8.5 升到 0.8.8 都无效，说明与版本/进程无关，卡在注册链路。

## Fix

绕开 DSH 插件注入，自己实现一个最小 MCP stdio 客户端：spawn `windows-mcp.exe serve --exclude-tools App,PowerShell,FileSystem`，依次发送 `initialize` → `notifications/initialized` → `tools/list` / `tools/call`，按行解析 JSON-RPC，图片 base64 直接落盘。18 个工具（Screenshot/Click/Type/Scroll/Clipboard/Registry 等）全部可用。

## Verification

脚本 `tools/list` 返回 18 个工具；用 `tools/call` 截图并用截图坐标点击，成功驱动 WeGame 登录并在其中启动英雄联盟，全程不依赖 DSH 工具注入。

tools/list 返回 18 个工具；截图+坐标点击实测驱动 WeGame 登录并启动英雄联盟
