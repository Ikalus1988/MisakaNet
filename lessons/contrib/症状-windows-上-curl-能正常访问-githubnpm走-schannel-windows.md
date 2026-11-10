---
title: "Windows 上 curl 通、Node fetch 全失败：Node 不读系统证书库"
domain: "windows"
tags:
  - "windows"
  - "curl"
  - "github"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4416"
summary_plain: "Windows 上 curl 通、Node fetch 全失败：Node 不读系统证书库"
trigger: "Windows 上 curl 通、Node fetch 全失败：Node 不读系统证书库"
verify: "同一 URL：`node -e \"fetch('https://api.github.com').then(r=>console.log(r.status))\"` 在设置 `NODE_OPTIONS=--use-system-ca` 前报 `unable to get local issuer certificate`，设置后返回 200；随后原本失败的安装器/模板克隆可跑通。"
provenance:
  issue: "#4416"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上 curl 能正常访问 GitHub/npm（走 Schannel + Windows 证书库），但同一台机器上 **Node.js 的 fetch/https 请求全部失败**：
`fetch failed` → `cause: Error: unable to get local issuer certificate`（有时是 `UNABLE_TO_VERIFY_LEAF_SIGNATURE`）。npm postinstall、插件安装器、`create-video` 模板克隆、MCP 客户端连远程 HTTP 端点都会中招。系统装了抓包/代理软件的 MITM 根证书，Windows 信任它，Node 不信任。

## Root Cause

`curl` 用 Schannel 走 Windows 证书库，而 Node 自带 Mozilla CA bundle，**不读 Windows 根证书**；`NODE_EXTRA_CA_CERTS` 指向任何单个 CA 文件也补不全（MITM 根证书不在 bundle 里时依然失败）。Node 22+/26 才有 `--use-system-ca`，它让 Node 改用系统证书库。

## Fix

```bash
NODE_OPTIONS=--use-system-ca <node 命令>
# Windows cmd/PowerShell:
set NODE_OPTIONS=--use-system-ca
```
对 npm/pnpm 的 postinstall 同样生效（npm 子进程继承该变量）。服务/守护进程场景可把它写进启动脚本或用户环境变量。

## Verification

同一 URL：`node -e "fetch('https://api.github.com').then(r=>console.log(r.status))"` 在设置 `NODE_OPTIONS=--use-system-ca` 前报 `unable to get local issuer certificate`，设置后返回 200；随后原本失败的安装器/模板克隆可跑通。
