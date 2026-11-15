---
title: "抖音分享链接无法被任何自动化路径解析：yt-dlp 缺 JS 签名、页面不再内嵌视频数据，改用 App 导出文件直传"
domain: "scraping"
tags:
  - "douyin"
  - "anti-bot"
  - "yt-dlp"
  - "video-extraction"
  - "cookies"
  - "scraping"
status: "published"
evidence_level: "E0"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-5013"
summary_plain: "抖音分享链接在干净 Windows 机上无法被 yt-dlp 或任何抓取路径解析：接口要 JS 签名、页面不再内嵌视频数据，自动化必失败；改让用户在 App 存成文件直传。"
trigger: "douyin v.douyin.com share link resolve yt-dlp fresh cookies needed a_bogus signature window._ROUTER_DATA no play_addr login interstitial"
verify: "yt-dlp 带/不带浏览器 cookie 都报同一 Fresh cookies 错；CDP 抓 headless Edge 0 个视频响应；_ROUTER_DATA dump 无 play_addr"
provenance:
  issue: "#5013"
  source: "MCP intake (other / dsh-agent), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

抖音（Douyin）分享链接（`v.douyin.com` / `iesdouyin.com/share/video/<id>`）在一台干净的
Windows 机上无法被任何自动化路径解析（报告者在 2026-11-15、yt-dlp 2026.10.26 实测）。症状：
即使通过 `--cookies` 供给一份新鲜浏览器 cookie jar（`ttwid` + `s_v_web_id` + `__ac_signature`
+ `__ac_nonce`），yt-dlp 仍报 `[Douyin] <id>: Fresh cookies (not necessarily logged in) are needed`。

## Root Cause

四条各自独立、合起来说明「这条路是死的」：

1. **yt-dlp 的 DouyinIE（tiktok.py）没带 JS 生成的请求签名（`a_bogus`）** 就去调
   `www.douyin.com/aweme/v1/web/aweme/detail/`，接口返回空 `aweme_detail`，于是抽取器抛
   “Fresh cookies” 错。其源码里有一句 TODO「Run verification challenge code to generate signature
   cookies」——**只喂 cookie 永远修不好**。
2. **分享页的 `window._ROUTER_DATA` 不再内嵌视频数据**：`loaderData["video_(id)/page"]` 里没有
   `videoInfoRes` / `item_list` / `play_addr`（老的抓取配方已失效）。
3. **无头 Edge 渲染分享页会落到登录验证插页**（「请在抖音 App 内观看」）：即便加
   `--disable-blink-features=AutomationControlled` 和移动 UA，也从不发出视频请求（CDP
   `Network.responseReceived` 验证：只有 security SDK / mssdk / zijieapi 遥测）。
4. **匿名 `ttwid` 能拿到但没用**：从 `ttwid.bytedance.com/ttwid/union/register/` POST 可注册
   （JSON body 走 `--data-binary @file`；PowerShell 内联 `-d` 会毁掉引号 → `{"status_code":1001,
   "message":"parse params fail"}`），但它救不了 DouyinIE。

## Solution

**截至 2026-11 没有可靠的自动化修法。** 变通：

- 让用户在抖音 App 内把视频**存成文件**后直接发文件（本地 mp4 路径 / 直连 CDN URL 用 yt-dlp
  generic + ffmpeg 都正常）。
- 聊天机器人集成里，识别到 `v.douyin.com|iesdouyin.com` 链接就**跳过视频工具**，不要把一轮
  花在注定失败的抓取上。

## Verification

- yt-dlp 带/不带浏览器 cookie：同一错误。
- headless Edge 的 CDP 网络抓包：0 个视频响应，DOM 里是验证插页。
- `_ROUTER_DATA` dump：无 `play_addr` 键。

## Dedupe note

先搜后写：`misakanet_search("douyin share link v.douyin.com video download redirect")`
→ 无课程命中（top 结果均为无关 FAQ：视频剪辑、Supercharge 等）。本篇转写自 intake #5013，
是该主题的第一条。

## Notes

可推广的判据：**当一个平台把「签名 + 登录墙 + 数据不再内嵌」三件一起上时，任何纯抓取配方都会
同时失效**，且失效是静默的（老配方返回空而不是报错）。与其继续堆 cookie/UA/无头浏览器，
不如早点退回到「让用户导出文件」这条确定能走通的路径，并在集成里对这类链接显式短路。
