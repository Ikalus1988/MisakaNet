---
title: "Node 不信任 Windows 系统 CA：unable to get local issuer certificate → --use-system-ca"
domain: "network"
tags:
  - "nodejs"
  - "windows"
  - "tls"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4421"
summary_plain: "Windows 上 curl 能访问 GitHub/npm，但同一台机器 Node.js 的 fetch/https 全部失败：fetch failed，cause 为 Error: unable to get local issuer…"
trigger: "Node 不信任 Windows 系统 CA：unable to get local issuer certificate → --use-system-ca. Windows 上 curl 能访问 GitHub/npm，但同一台机器 Node.js 的 fetch/https 全部失败：fetch…"
verify: "node -e \"fetch('https://api.github.com').then(r=>console.log(r.status))\" 从报错变为返回 200，npm postinstall 可跑通。"
provenance:
  issue: "#4421"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上 curl 能访问 GitHub/npm，但同一台机器 Node.js 的 fetch/https 全部失败：fetch failed，cause 为 Error: unable to get local issuer certificate。npm postinstall、插件安装器、模板克隆都会中招。

## Root Cause

curl 走 Schannel 读 Windows 证书库；Node 自带 Mozilla CA bundle，不读系统根证书，NODE_EXTRA_CA_CERTS 指单个 CA 文件也补不全。Node 22+ 的 --use-system-ca 可切换到系统证书库。

## Fix

在 Node 命令前加 `NODE_OPTIONS=--use-system-ca`（Node 22+/26 支持），让 Node 改用系统证书库；Windows cmd/PowerShell 用 `set NODE_OPTIONS=--use-system-ca`，npm/pnpm 的 postinstall 子进程会继承该变量。

## Verification

node -e "fetch('https://api.github.com').then(r=>console.log(r.status))" 从报错变为返回 200，npm postinstall 可跑通。
