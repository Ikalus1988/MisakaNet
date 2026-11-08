---
title: "ffmpeg subtitles 的 force_style 在 shell 里被静默丢弃，字幕按默认样式满屏乱跑"
domain: "video"
tags:
  - "ffmpeg"
  - "subtitles"
  - "ass"
  - "force_style"
  - "windows"
  - "powershell"
  - "escaping"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4526"
summary_plain: "想把 SRT 烧进竖屏视频并指定字幕样式： & ffmpeg -i in.mp4 -filter_complex \"[0:v]subtitles=subs.srt:force_style='FontName=Microsoft…"
trigger: "ffmpeg subtitles 的 force_style 在 shell 里被静默丢弃，字幕按默认样式满屏乱跑. 想把 SRT 烧进竖屏视频并指定字幕样式： & ffmpeg -i in.mp4 -filter_complex…"
verify: "1. 抽帧检查：字幕在底部、字号与设计一致 2. 命令行里不再出现 force_style 3. 同一时间点静帧，修改前后对比"
provenance:
  issue: "#4526"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

想把 SRT 烧进竖屏视频并指定字幕样式：

& ffmpeg -i in.mp4 -filter_complex "[0:v]subtitles=subs.srt:force_style='FontName=Microsoft YaHei,FontSize=52,MarginV=250,Alignment=2'[v]" -map "[v]" out.mp4

出片后发现字幕完全没按指定样式：字号巨大（约 150px）、位置跑到画面顶部、挡住主体内容。命令行没有任何报错。

## Root Cause

force_style 的值里有逗号，而 ffmpeg 的 filter 参数用冒号分隔选项、逗号分隔多个 filter。先过一层 shell（PowerShell / bash）再交给 ffmpeg 解析时，引号层数不够或转义方式不对，这段值会被切断，force_style 变成一个无法解析的参数被静默丢弃。

关键点：丢弃是静默的。ffmpeg 不报错、不清不响地用 libass 默认样式渲染。默认样式字号大、位置贴顶，在竖屏上完全不可用，很容易被误判成"样式参数写错了"。

## Fix

不要在命令行里传样式。改用 ASS 字幕，把样式写进文件：

1. 生成 subs.ass，头部写死样式：
   [V4+ Styles]
   Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
   Style: Default,Microsoft YaHei,54,&H00FFFFFF,&H00141414,1,3.5,0,2,70,70,250,1
2. 烧录时只引用文件，不传任何样式参数：
   -filter_complex "[0:v]subtitles=subs.ass[v]"
3. 1080x1920 竖屏：PlayResX/PlayResY 写 1080/1920，MarginV 取 250 左右避开平台底部 UI 遮挡区
4. ASS 文件用 UTF-8 BOM 写，避免 libass 读中文乱码

## Verification

1. 抽帧检查：字幕在底部、字号与设计一致
2. 命令行里不再出现 force_style
3. 同一时间点静帧，修改前后对比
