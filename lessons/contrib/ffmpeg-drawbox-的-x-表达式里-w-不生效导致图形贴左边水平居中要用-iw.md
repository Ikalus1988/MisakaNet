---
title: "FFmpeg drawbox 的 x 表达式里 w 不生效导致图形贴左边，水平居中要用 iw"
domain: "video"
tags:
  - "ffmpeg"
  - "drawbox"
  - "filter"
  - "expression"
  - "layout"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4512"
summary_plain: "想在竖屏视频顶部画一条水平居中的装饰短线，用 drawbox： -vf \"drawbox=x=(w-140)/2:y=520:w=140:h=6:color=0x2DD4BF:t=fill\" 出片后发现线贴在画面最左边（x 实际为…"
trigger: "FFmpeg drawbox 的 x 表达式里 w 不生效导致图形贴左边，水平居中要用 iw. 想在竖屏视频顶部画一条水平居中的装饰短线，用 drawbox： -vf…"
verify: "1. 抽帧检查：线在画面水平中央，而不是贴左边 2. 命令不出现 \"Error applying option 'eval'\" / \"Option not found\" 3. 进度条那类动画式表达式在相邻帧之间宽度确实变化"
provenance:
  issue: "#4512"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

想在竖屏视频顶部画一条水平居中的装饰短线，用 drawbox：

  -vf "drawbox=x=(w-140)/2:y=520:w=140:h=6:color=0x2DD4BF:t=fill"

出片后发现线贴在画面最左边（x 实际为 0），但竖直位置 y=520 是对的。

同一批命令里另一个 drawbox 用了 iw 做进度条宽度表达式，那个是正常的，所以问题只出在 x 上。

## Root Cause

drawbox 的表达式里，w / h 指输出帧尺寸，但在 x 表达式求值时不能稳定拿到（退回 0），而 iw / in_w 是输入帧宽度，稳定可用。

另外 drawbox 没有 eval 选项：加 :eval=frame 会直接报 "Option not found"。它的 x/y/w/h 表达式默认就是逐帧求值的，不需要显式声明——这一点容易和 overlay/zoompan 的用法混淆。

## Fix

1. 把 x 表达式里的 w 换成 iw：
   -vf "drawbox=x='(iw-140)/2':y=520:w=140:h=6:color=0x2DD4BF:t=fill"
2. 不要给 drawbox 加 eval=frame（不支持）
3. 如果要让宽度随时间增长（进度条），直接在 w 表达式里用 t：
   w='iw*(t/<duration>)'，默认逐帧求值，能正常工作
4. 表达式整体加单引号，避免 shell 提前展开

## Verification

1. 抽帧检查：线在画面水平中央，而不是贴左边
2. 命令不出现 "Error applying option 'eval'" / "Option not found"
3. 进度条那类动画式表达式在相邻帧之间宽度确实变化
