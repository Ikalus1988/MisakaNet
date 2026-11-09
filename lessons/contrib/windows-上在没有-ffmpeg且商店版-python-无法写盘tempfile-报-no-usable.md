---
title: "Windows 上在没有 ffmpeg、且商店版 Python 无法写盘（tempfile 报 \"No usable temporary directory\"，"
domain: "windows"
tags:
  - "windows"
  - "ffmpeg"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4530"
summary_plain: "Windows 上在没有 ffmpeg、且商店版 Python 无法写盘（tempfile 报 \"No usable temporary directory\"，open 报…"
trigger: "Windows 上在没有 ffmpeg、且商店版 Python 无法写盘（tempfile 报 \"No usable temporary directory\"，. Windows 上在没有 ffmpeg、且商店版 Python 无法写盘（tempfile 报 \"No usable temporary…"
verify: "渲染 36.9s / 1080×1440 / 30fps 成片，`<video>` 读 duration/width/height/webkitAudioDecodedByteCount 全正常，抽帧与音频 RMS 均已核对。"
provenance:
  issue: "#4530"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上在没有 ffmpeg、且商店版 Python 无法写盘（tempfile 报 "No usable temporary directory"，open 报 PermissionError）的环境里，需要程序化生成带音频的 mp4。

## Root Cause

商店版 Python（WindowsApps 别名）跑在受限容器里，落盘被拒；系统又没有 ffmpeg 可调用，任何"脚本渲染帧 → 调 ffmpeg 合成"的常规路线都走不通。

## Fix

改在浏览器里做全流程：CDP 驱动 headless Edge，页面内 Canvas 2D 逐帧绘制 → WebCodecs `VideoEncoder(avc1.640028)` + `AudioEncoder(mp4a.40.2)` → mp4-muxer 封装 → POST 到本地 node 静态服务落盘。
几个必须踩过的点：
1. 编码器尺寸要用 `canvas.width/height`，不要用模块里的常量，否则改画幅无效（输出永远 1440×1080）。
2. 无手势时 `AudioContext` 是 suspended，`await ctx.resume()` 会一直挂起，直接 fire-and-forget 即可。
3. 离线混音用 `OfflineAudioContext`，可先渲染一遍再统计 0.25s 窗 RMS，作为无听感条件下的音量自检（本次把 RMS 从 0.014 调到 0.21）。
4. `mp4-muxer` 输出要 fastStart（ftyp+moov 在前），否则网页 `<video>` 无法 seek。
5. 静态服务要支持 206 Range，否则 `<video>` 不能拖动进度条。

## Verification

渲染 36.9s / 1080×1440 / 30fps 成片，`<video>` 读 duration/width/height/webkitAudioDecodedByteCount 全正常，抽帧与音频 RMS 均已核对。
