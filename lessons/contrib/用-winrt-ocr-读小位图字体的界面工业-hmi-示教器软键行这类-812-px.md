---
title: "用 WinRT OCR 读**小位图字体**的界面（工业 HMI / 示教器软键行这类 8~12 px 的点阵字）时，会出现很怪的「部分读得出、部分读不出」：同"
domain: "mcp"
tags:
  - "winrt"
  - "ocr"
  - "hmi"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5168"
summary_plain: "用 WinRT OCR 读**小位图字体**的界面（工业 HMI / 示教器软键行这类 8~12 px 的点阵字）时，会出现很怪的「部分读得出、部分读不出」：同一排软键里 `HOLD` 读得到、`MENU`…"
trigger: "WinRT OCR 读小位图字体界面读不全：scale 2~3 读不到 MENU、6× 整条读空、8× 一次读全九个软键；反色无效"
verify: "同一块软键带裁剪图，scale=8 的 OCR 输出里 PREV/SHIFT/MENU/SELECT/EDIT/DATA/FCTN/SHIFT/NEXT 九个词全部命中；scale=2~3 时 MENU 缺失、scale=6 时全空；invert 与否结果一致。"
provenance:
  issue: "#5168"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用 WinRT OCR 读**小位图字体**的界面（工业 HMI / 示教器软键行这类 8~12 px 的点阵字）时，会出现很怪的「部分读得出、部分读不出」：同一排软键里 `HOLD` 读得到、`MENU` 读不到，`PREV`/`SHIFT`/`NEXT` 读得到、`SELECT`/`EDIT`/`DATA`/`FCTN` 读不到。放大倍数调小（2~3×）读不全，调到 6× 反而**整条读空**，调到 **8× 才一次读全**。反色（invert）不解决问题——明底和反底读出来一样。

## Root Cause

WinRT OCR 对小点阵字形的召回率强烈依赖**输入里的字高像素数**：2~3× 时每个字只有几像素高，识别器在候选集里只保留下划线/直笔画明显的几个（于是 `HOLD` 这种有横有竖的活下来，`MENU` 这种圆弧多的丢掉）；6× 时二值化/缩放插值把笔画糊成块，反而全灭；8× 时字形特征足够完整，识别器才把整行都收进来。**反色不是关键变量，放大倍数才是。**

## Fix

1. 读这类区域时**先裁剪出那一行/那一小块再放大**，不要整图放大；
2. 放大倍数**直接上 8×**（LANCZOS），并保持灰度图；
3. 判据：同一块区域换几个 scale 各跑一次，**取能读出最多词的那个**；若某块永远读不出，先怀疑「字太小」而不是「引擎坏了」——用一张已知文字的图做引擎探针（探针过了就说明引擎没问题）；
4. 如果这行字其实是**真按钮**（很多 HMI 的软键是独立控件），更稳的路是**几何定位**：枚举控件子窗拿到每个键的矩形，再逐个裁剪 8× OCR 读标签，避免依赖整行 OCR。

## Verification

同一块软键带裁剪图，scale=8 的 OCR 输出里 PREV/SHIFT/MENU/SELECT/EDIT/DATA/FCTN/SHIFT/NEXT 九个词全部命中；scale=2~3 时 MENU 缺失、scale=6 时全空；invert 与否结果一致。
