---
title: "微软商店（Microsoft Store）下载极慢，几十 MB 的应用要下很久，但同机浏览器测速正常。单看\"网速没问题\"会查不出原因。 Root Cause 本"
domain: "windows"
tags:
  - "microsoft"
  - "store"
  - "mb"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4568"
summary_plain: "微软商店（Microsoft Store）下载极慢，几十 MB 的应用要下很久，但同机浏览器测速正常。单看\"网速没问题\"会查不出原因。"
trigger: "微软商店（Microsoft Store）下载极慢，几十 MB 的应用要下很久，但同机浏览器测速正常。单看\"网速没问题\"会查不出原因。 Root Cause 本. 微软商店（Microsoft Store）下载极慢，几十 MB 的应用要下很久，但同机浏览器测速正常。单看\"网速没问题\"会查不出原因。"
verify: "本例修复后实测商店下载 123.8 Mbps；hosts 复核为 0 条活跃劫持记录，NCSI 探测 HTTP 200。"
provenance:
  issue: "#4568"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

微软商店（Microsoft Store）下载极慢，几十 MB 的应用要下很久，但同机浏览器测速正常。单看"网速没问题"会查不出原因。

## Root Cause

本例是三个因素叠加，缺一都不会这么慢：
1. **hosts 被第三方工具劫持**（主因）：`<PATH> 被写进 104 行几乎全是劫持项，把 `dl.delivery.mp.microsoft.com`、`tlu.dl.delivery.mp.microsoft.com`、`1d.tlu.dl.delivery.mp.microsoft.com` 等强制指向某个境外 CDN 节点，延迟高、吞吐差。
2. **Clash 处于全局模式**：全局模式下代理出口只认 `GLOBAL.now`，商店流量绕进代理，速度受节点带宽限制。
3. **NCSI 主动探测被关闭**：`EnableActiveProbing=0` 让 Windows 无法正确判断连通性，影响 CDN 选路。

## Fix

1. 把 hosts 恢复为 Windows 默认模板（只保留注释，约 800 字节），改前备份；
2. Clash 切回**规则模式**（不要用全局），或至少确认商店域名走直连组；
3. `HKLM\SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet\EnableActiveProbing` 置 1，重启 `nlasvc`。
验连通：`curl -I` 打 `dl.delivery.mp.microsoft.com` 应返回 200/302，且解析到就近 CDN。

## Verification

本例修复后实测商店下载 123.8 Mbps；hosts 复核为 0 条活跃劫持记录，NCSI 探测 HTTP 200。
