---
title: "Windows 上只有一个商店版 Python 3.13（WindowsApps 别名）时，所有需要落盘的脚本都失败：tempfile 抛 \"No usable"
domain: "windows"
tags:
  - "windows"
  - "python"
  - "windowsapps"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4495"
summary_plain: "Windows 上只有一个商店版 Python 3.13（WindowsApps 别名）时，所有需要落盘的脚本都失败：tempfile 抛 \"No usable temporary directory\"，open() 抛…"
trigger: "Windows 上只有一个商店版 Python 3.13（WindowsApps 别名）时，所有需要落盘的脚本都失败：tempfile 抛 \"No usable. Windows 上只有一个商店版 Python 3.13（WindowsApps 别名）时，所有需要落盘的脚本都失败：tempfile 抛 \"No…"
verify: "`node render.mjs` 产出的 mp4 用 `<video>` 载入后 `duration/videoWidth/webkitAudioDecodedByteCount` 均非 0；`ftyp`+`moov` 在文件头（fastStart 正常）。"
provenance:
  issue: "#4495"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上只有一个商店版 Python 3.13（WindowsApps 别名）时，所有需要落盘的脚本都失败：tempfile 抛 "No usable temporary directory"，open() 抛 PermissionError，连 uv.exe 都创建不了目录；而同一台机器 node/pwsh 写文件完全正常。

## Root Cause

WindowsApps 里的 python.exe 是应用商店占位符 / 受控执行别名，运行时没有可用写权限，也无法通过普通环境变量修复；它不是「Python 环境没配好」，而是这个二进制本身被夹在包沙箱里。

## Fix

判断链：先跑 `python -c "import tempfile;print(tempfile.gettempdir())"`，报 No usable temporary directory 就换栈，不要在 Python 里继续折腾。
可行的替代：把整套处理搬到 Node/浏览器侧——用 headless Edge + CDP（`--remote-debugging-port`）在页面里跑 Canvas 2D 绘制，VideoEncoder(avc1.640028) + AudioEncoder(mp4a.40.2) 编码，mp4-muxer 封装，`POST` 到本地 node 静态服务落盘。这样无 ffmpeg、无 Python 也能产出 mp4。

## Verification

`node render.mjs` 产出的 mp4 用 `<video>` 载入后 `duration/videoWidth/webkitAudioDecodedByteCount` 均非 0；`ftyp`+`moov` 在文件头（fastStart 正常）。
