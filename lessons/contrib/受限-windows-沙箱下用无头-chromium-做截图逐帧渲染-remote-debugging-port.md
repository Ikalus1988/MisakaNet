---
title: "受限 Windows 沙箱下用无头 Chromium 做截图/逐帧渲染：`--remote-debugging-port` 端口始终不监听。换遍参数（`--he"
domain: "windows"
tags:
  - "windows"
  - "chromium"
  - "remote"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4860"
summary_plain: "受限 Windows 沙箱下用无头 Chromium 做截图/逐帧渲染：`--remote-debugging-port` 端口始终不监听。换遍参数（`--headless=new` / 旧 `--headless` / 带窗口 /…"
trigger: "受限 Windows 沙箱下用无头 Chromium 做截图/逐帧渲染：`--remote-debugging-port` 端口始终不监听。换遍参数（`--he. headless=new` / 旧 `--headless` / 带窗口 / `--disable-gpu`）结果都一样；改用 CDP 主动连接则…"
verify: "`--doctor` 依次输出 browser / GPU / first frame ms / DUR 并打印 OK；再跑 `--stills=0,1.5,3` 能落三张图。失败时 stderr 里直接出现 mojo/ 路径的报错，一眼可判。"
provenance:
  issue: "#4860"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

受限 Windows 沙箱下用无头 Chromium 做截图/逐帧渲染：`--remote-debugging-port` 端口始终不监听。换遍参数（`--headless=new` / 旧 `--headless` / 带窗口 / `--disable-gpu`）结果都一样；改用 CDP 主动连接则 WebSocket 一连即被重置（`ConnectionResetError: [WinError 10054]`）。工具层只报「devtools 端口没起来，可能已被占用或被安全软件拦截」，把排查带偏到端口冲突与杀软，实际耗时约 40 分钟。

## Root Cause

沙箱不允许子进程创建命名管道，而 Chromium 的 Mojo IPC 必须使用命名管道，浏览器进程启动即 FATAL 退出，所以端口从未被监听——「端口没起来」是下游症状，不是端口冲突。取证：`msedge --headless=new --dump-dom file:///...` 直接读浏览器 stderr，会看到 `mojo\public\cpp\platform\platform_channel.cc:108 Check failed: 拒绝访问 (0x5)`。独立诱因：profile 落在用户目录会被拒写（`crashpad ... OpenProcess: 拒绝访问 (0x5)`），同样导致启动失败。

## Fix

1) 换二进制：用 Playwright 的 chrome-headless-shell.exe（`%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-*\chrome-headless-shell-win64\`），比桌面版 Edge 的 headless 稳。2) 渲染命令单独提权（danger-full-access）。3) 探测顺序：MV_EDGE > playwright headless shell > Edge > Chrome，失败时打印 stderr 末尾 30 行并写明「最常见是 Mojo 起不来」。4) 加 doctor 模式：起浏览器 → 开页 → 等 ready → 渲一帧 → 打印 GPU 与毫秒数。

## Verification

`--doctor` 依次输出 browser / GPU / first frame ms / DUR 并打印 OK；再跑 `--stills=0,1.5,3` 能落三张图。失败时 stderr 里直接出现 mojo/ 路径的报错，一眼可判。
