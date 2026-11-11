---
title: "Tauri 更新弹窗「去下载页」点了没反应：按钮在，打开外部浏览器失败"
domain: "mcp"
tags:
  - "symptom"
  - "tauri"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4685"
summary_plain: "Tauri 更新弹窗「去下载页」点了没反应：按钮在，打开外部浏览器失败"
trigger: "Tauri 更新弹窗「去下载页」点了没反应：按钮在，打开外部浏览器失败"
verify: "- Rust 白名单纯函数 2 组单测：放行 3 个真实 URL（内网 issue / releases/latest / releases/tag/vX）+ 拒绝 5 个仿冒/近似 - 全量 cargo 97/97、vitest 846/846 - 手工：改后点「去下载页」能拉起默认浏览器到发布页；故意改回窄白名单并去掉 catch，复现「点了没反应」 cargo 97/97 +…"
provenance:
  issue: "#4685"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

桌面应用（Tauri）更新弹窗里点「去下载页」完全无反应——没有报错、没有浏览器窗口、弹窗还照常关闭。装机版/免安装版都中招。同弹窗的「稍后」正常，说明按钮本身没挂。

## Root Cause

两层缺陷叠加，任何一层单独存在都只是半残：
1. **后端 URL 白名单过窄**：打开外链的命令只放行了内网域名前缀，而「去下载页」要开的是公开发布页（自家 GitHub Releases）。后端返回 `Err("不允许打开该链接")`。
2. **前端 onClick 没 await/catch**：命令返回 rejected promise，onClick 是同步箭头函数直接调用后就执行下一行关弹窗，rejection 变成 unhandled——UI 层完全静默。

关键教训：**白名单拒绝 + 未 catch 的 promise = 「按钮坏了」**。用户报「点了没反应」时，先查是不是权限/白名单在静默拒绝，而不是先怀疑事件绑定。

同弹窗里另一个按钮（打开 issue 链接）有 try/catch + message.error，所以那个从不出这问题——对照组就在同一文件里。

## Fix

1. 白名单补齐真正需要的前缀（自家发布页仓库），并抽成纯函数 `is_allowed_external_url(url)` 便于单测：
   - 放行：内网 issue 前缀、自家发布页仓库前缀
   - 拒绝：异主机子串仿冒（`https://evil.com/https://git.n.xiaomi.com/`）、同主机其他仓库、去掉尾斜杠的近似拼写、非 https、`javascript:`
2. onClick 改 `async` + `try/catch`，失败 `message.error(e.message)`，不再静默。
3. 文档注释同步（「只放行内网」→「放行内网 issue + 自家发布页」）。

## Verification

- Rust 白名单纯函数 2 组单测：放行 3 个真实 URL（内网 issue / releases/latest / releases/tag/vX）+ 拒绝 5 个仿冒/近似
- 全量 cargo 97/97、vitest 846/846
- 手工：改后点「去下载页」能拉起默认浏览器到发布页；故意改回窄白名单并去掉 catch，复现「点了没反应」

cargo 97/97 + vitest 846/846 + 白名单仿冒拒绝单测
