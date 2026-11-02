---
title: "Windows + WSL2 环境下 Node 的 fetch/undici 访问 GitHub release 资源会 connect timeout（10"
domain: "windows"
tags:
  - "windows"
  - "wsl2"
  - "node"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4127"
summary_plain: "Windows + WSL2 环境下 Node 的 fetch/undici 访问 GitHub release 资源会 connect timeout（10 秒后 fetch failed），而同机 curl 走系统代理…"
trigger: "Windows + WSL2 环境下 Node 的 fetch/undici 访问 GitHub release 资源会 connect timeout（10. Windows + WSL2 环境下 Node 的 fetch/undici 访问 GitHub release 资源会 connect…"
verify: "同 URL 对比实测：curl -L --proxy http://127.0.0.1:7890 约 1s 拿到 206；Node fetch 直连 10s 后 fetch failed。注入 undici ProxyAgent 后 Node fetch 约 0.6s 拿到 206，api.github.com 约 0.7s 返回 200 且 tag_name 正确。清除…"
provenance:
  issue: "#4127"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows + WSL2 环境下 Node 的 fetch/undici 访问 GitHub release 资源会 connect timeout（10 秒后 fetch failed），而同机 curl 走系统代理 127.0.0.1:7890 却能在 1 秒内正常下载。

## Root Cause

根因是 Node 内置 fetch/undici 默认不读 https_proxy 环境变量，也不读 Windows 系统代理设置。

## Fix

1) Node 侧注入代理：Node 24+ 用 NODE_USE_ENV_PROXY=1；Node 18-23 需显式设置 undici 全局 dispatcher —— preload 模块里 import { ProxyAgent, setGlobalDispatcher } from 'undici'，setGlobalDispatcher(new ProxyAgent('http://127.0.0.1:7890'))，然后 node --import <PATH> 启动。注意 Windows 上 --import 必须是 file:// URL，相对路径在 pnpm workspace 子目录会解析失败。2) 大文件（>100MB）不要用 Node fetch 直连代理，代理长连接会断流（terminated / socket hang up），改用 curl --proxy --retry 5 --retry-all-errors -C - 下载，校验 sha256 匹配 GitHub release asset 的 digest 字段后再本地解压安装。

## Verification

同 URL 对比实测：curl -L --proxy http://127.0.0.1:7890 约 1s 拿到 206；Node fetch 直连 10s 后 fetch failed。注入 undici ProxyAgent 后 Node fetch 约 0.6s 拿到 206，api.github.com 约 0.7s 返回 200 且 tag_name 正确。清除 GITHUB_TOKEN 后同一 URL 从 401 变为 200。
