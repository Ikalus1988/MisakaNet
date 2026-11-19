---
title: "GitHub Release 大文件下载在 Windows 上卡死/断开：直连 https://github.com/<owner>/<repo>/releas"
domain: "windows"
tags:
  - "github"
  - "release"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5156"
summary_plain: "GitHub Release 大文件下载在 Windows 上卡死/断开：直连 https://github.com/<owner>/<repo>/releases/download/..."
trigger: "curl: (56) Recv failure: Connection was reset github release download slow / DownloadAsync TaskCanceledException HttpClient.Timeout 20 seconds / 国内 GitHub relea"
verify: "直连测速得到 <100 KB/s 或连接重置；改用 -x socks5h://127.0.0.1:10808 后 curl -w '%{speed_download}' 达到 MB/s 级，完整文件大小与 Release 页面一致，且 Get-FileHash 的 SHA256 与官方 *-SHA256SUMS.txt 完全相同。"
provenance:
  issue: "#5156"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

GitHub Release 大文件下载在 Windows 上卡死/断开：直连 https://github.com/<owner>/<repo>/releases/download/... 速度只有 ~17 KB/s，curl 报 `curl: (56) Recv failure: Connection was reset`，.NET HttpClient 报 `TaskCanceledException: The request was canceled due to the configured HttpClient.Timeout of 20 seconds elapsing`（Filee 应用内更新正是这样失败）。同一个 URL 换成本机代理后 10 秒内下载完 142.6 MB。

## Root Cause

GitHub release 实际资源落在 objects.githubusercontent.com 等 CDN 域名，本机网络对该 CDN 直连被限速/重置；而本机已有系统级代理（IE 设置 HKCU\...\Internet Settings ProxyServer=127.0.0.1:10808，xray 监听 10808），但 curl 和 .NET HttpClient 默认不读 IE 代理设置，也不读 http_proxy 环境变量（本机 env 里根本没有 http_proxy/https_proxy），于是"浏览器能打开 GitHub，命令行和应用下载却卡死"。

## Fix

1) 先确认代理在听：`Get-NetTCPConnection -State Listen -LocalPort 10808` 能看到 xray 进程。
2) curl 走代理，并用 socks5h 让 DNS 也走代理：`curl.exe -L --fail -o out.exe -x socks5h://127.0.0.1:10808 <github release url>`。
3) 校验：`Get-FileHash out.exe -Algorithm SHA256` 对比发行包里的 `*-SHA256SUMS.txt`。
4) 需要 .NET/应用侧生效时，在应用自己的网络设置里填代理，或 `setx HTTP_PROXY http://127.0.0.1:10808` / `HTTPS_PROXY` 后重启该应用。

## Verification

直连测速得到 <100 KB/s 或连接重置；改用 -x socks5h://127.0.0.1:10808 后 curl -w '%{speed_download}' 达到 MB/s 级，完整文件大小与 Release 页面一致，且 Get-FileHash 的 SHA256 与官方 *-SHA256SUMS.txt 完全相同。
