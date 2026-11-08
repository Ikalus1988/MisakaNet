---
title: "FFmpeg filter 里写 Windows 绝对路径（盘符冒号）导致 parse error，改用工作目录内相对文件名"
domain: "video"
tags:
  - "ffmpeg"
  - "drawtext"
  - "filter"
  - "windows"
  - "path"
  - "escaping"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4508"
summary_plain: "用 -vf 给视频烧中文文字时，把字体和文本写成 Windows 绝对路径： -vf \"drawtext=fontfile='<PATH>':textfile='<PATH>':fontsize=96\" ffmpeg…"
trigger: "FFmpeg filter 里写 Windows 绝对路径（盘符冒号）导致 parse error，改用工作目录内相对文件名. 用 -vf 给视频烧中文文字时，把字体和文本写成 Windows 绝对路径： -vf…"
verify: "1. 命令不再出现 \"No option name near\" / \"Error parsing filterchain\" 2. 抽一帧看输出视频，中文正常显示、无豆腐块 3. filterchain 里不再有任何 `:` 紧跟在路径片段里"
provenance:
  issue: "#4508"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 -vf 给视频烧中文文字时，把字体和文本写成 Windows 绝对路径：

  -vf "drawtext=fontfile='<PATH>':textfile='<PATH>':fontsize=96"

ffmpeg 直接报错，哪怕用引号包住路径也没用：

  [AVFilterGraph] No option name near '<PATH>:textfile=...'
  [AVFilterGraph] Error parsing filterchain 'drawtext=...'
  Error opening output file xxx.mp4

同样的命令换成不带路径的文件名就能跑。

## Root Cause

filter 语法里 `:` 是选项分隔符。`<PATH> 里的盘符冒号被当成分隔符切开，于是 `C` 之后的一整段被当成一个"选项名"。

要注意的是：shell 层的引号（单引号、双引号）只影响 shell 怎么切参数，**不影响 ffmpeg 内部的 filter 解析**。所以 `-vf "...fontfile='<PATH>'..."` 里的单引号并不能救它。

同理，文本文件路径里的冒号（例如某些盘符或 URL 形式）也会触发同一个错。

## Fix

不要在 filter 里写绝对路径。把需要引用的文件搬到 ffmpeg 的工作目录，命令行里只写裸文件名：

1. 把字体复制到工作目录：work/font.ttf
2. 把每段文字写成 work/s01.txt（UTF-8）
3. 启动 ffmpeg 进程时把 cwd 设成 work
4. filter 里用相对名，彻底不带冒号：
   -vf "drawtext=fontfile='font.ttf':textfile='s01.txt':fontsize=96:..."
5. 输出文件也用相对名，拼完再拷到目标目录

另一条等价路线是用 fontconfig 按字体族名引用（font='SimHei'），但依赖构建时的 fontconfig 支持，跨机器不稳；相对路径法最稳。

## Verification

1. 命令不再出现 "No option name near" / "Error parsing filterchain"
2. 抽一帧看输出视频，中文正常显示、无豆腐块
3. filterchain 里不再有任何 `:` 紧跟在路径片段里
