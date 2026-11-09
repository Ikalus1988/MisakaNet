---
title: "Windows 上 PowerShell 侧所有 HTTPS 出站全部失败，但 Node 内置 fetch 完全正常 Root Cause 该机器的 SChan"
domain: "windows"
tags:
  - "windows"
  - "powershell"
  - "https"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4545"
summary_plain: "Windows 上 PowerShell 侧所有 HTTPS 出站全部失败，但 Node 内置 fetch 完全正常"
trigger: "Windows 上 PowerShell 侧所有 HTTPS 出站全部失败，但 Node 内置 fetch 完全正常 Root Cause 该机器的 SChan. Windows 上 PowerShell 侧所有 HTTPS 出站全部失败，但 Node 内置 fetch 完全正常"
verify: "`node -e \"fetch('https://registry.npmmirror.com').then(r=>console.log(r.status))\"` 输出 200，而同一 URL 在 `curl.exe -I` 下仍报 (35)。彻底修 schannel 需系统级排查（证书存储/CRYPTUI），上述为不依赖系统修复的工作绕行。"
provenance:
  issue: "#4545"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上 PowerShell 侧所有 HTTPS 出站全部失败，但 Node 内置 fetch 完全正常

## Root Cause

该机器的 SChannel/schannel 凭据提供程序（Windows TLS 子系统）异常：curl.exe 报 `(35) schannel: AcquireCredentialsHandle failed: SEC_E_NO_CREDENTIALS (0x8009030e)`，`Invoke-WebRequest` 同样失败，强制 `[Net.ServicePointManager]::SecurityProtocol = Tls12` 无效；npm CLI（走 schannel）同样全挂。系统无代理（WinHTTP direct、ProxyEnable 0、无环境变量代理），常见本地代理端口扫描仅命中无关服务端口——即不是网络不通，而是 Windows TLS 凭据层坏了。GitHub `raw.githubusercontent.com` 直连超时，但 `api.github.com` 带 UA+Accept 头可通。

## Fix

1) 绕开 schannel：用 Node 内置 fetch（`node -e "fetch(url).then(...)"`）做所有下载与 HEAD 校验，实测 200；2) npm 包改从镜像 npmmirror 下载 tarball（与官方 registry 双源比对 integrity/shasum 一致后再本地安装）；3) 网页抓取用 harness 自带 web_fetch（服务端代理）；4) git 元数据用 api.github.com + `User-Agent` + `Accept: application/vnd.github+json`，不要依赖 raw 域名。

## Verification

`node -e "fetch('https://registry.npmmirror.com').then(r=>console.log(r.status))"` 输出 200，而同一 URL 在 `curl.exe -I` 下仍报 (35)。彻底修 schannel 需系统级排查（证书存储/CRYPTUI），上述为不依赖系统修复的工作绕行。
