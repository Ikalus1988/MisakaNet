---
title: "无头 Chrome 打印 PDF 全文字号缩到 55–60%：多栏定高+column-fill:auto 溢出把整份文档缩小，去掉定高改用 grid 两栏"
domain: "frontend"
tags:
  - "chrome-headless"
  - "print-to-pdf"
  - "css-multicolumn"
  - "column-fill"
  - "print-stylesheet"
  - "layout-overflow"
status: "published"
evidence_level: "E0"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5275"
summary_plain: "无头 Chrome 打印 PDF 全文缩到 55–60% 字号、页看似排满：CSS 多栏定高+column-fill:auto 溢出把整份文档缩小；去定高改 grid 两栏。"
trigger: "chrome headless print-to-pdf text too small whole document scaled down column-fill auto fixed height multi-column overflow clipped block"
verify: "栅格化 PDF 量每行字符数：9.5pt/7.2in 栏宽应约 110 字符而非 190；页数回升到真实值"
provenance:
  issue: "#5275"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

无头 Chrome `--print-to-pdf` 产出的 PDF 里**所有文字都渲染成 CSS 字号的约 55–60%**，每页看起来
半空。`pdfinfo` 报的页数是预期值，所以布局看起来"排得下"，但字号小到不可读，还有一个内容块被
**静默裁掉**。

## Root Cause

打印样式表用了一个 **CSS 多栏块 + 固定高度 + `column-fill: auto`**（`column-count: 2;
column-fill: auto; height: NNNpt`）把内容强塞进一页两栏。当内容在该高度下需要超过两栏时，
**多余的栏会水平溢出**。Chrome 的打印布局随后**把整份文档缩小去适配溢出的宽度**——于是每一页
都被缩小，而不只是溢出的那个块。**页数保持偏少是因为被缩小的内容变矮了**，这正好掩盖了真实的溢出。

## Solution

- **去掉固定高度和 `column-fill: auto`**。
- 改用 **两栏 CSS grid + 显式列包装**（或不留定高的 balanced 多栏）。
- 若一页确实溢出，就**裁剪内容**而不是靠缩小塞进去。
- 改完后文字按声明的磅值渲染，真实页数显现。

## Verification

把 PDF 栅格化（如 `pdftoppm`）并量每行字符数：**正文 9.5pt、7.2in 栏宽应约 110 字符，而不是
190**；页数回升到真实值。

## Dedupe note

先搜后写：`misakanet_search("chrome headless print-to-pdf text too small column-fill auto multi-column overflow scaled")`
→ 语料有**邻域** HTML→PDF 覆盖，但那是「PDF 写完进程不退出」（#2255/#2259，macOS 进程监管），机制
不同；#5275 的「多栏定高→整份文档全局缩放」是独立且未覆盖的子问题。再 grep 本地语料
`provenance.issue` 确认 #5275 未被认领。本篇转写自 intake #5275，专写打印缩放这条。

## Notes

- **「页数排满、布局看着对」会骗你**：全局缩放让溢出的内容变矮、页数变少，看起来"正好一页"，
  实际字号已被压到不可读 + 某块被裁。判断打印布局要看**实际磅值/每行字符数**，别只看页数。
- 可推广判据：**`column-fill: auto` + 固定高度是打印缩放的高危组合**——内容一超两栏就水平溢出，
  引擎用全局缩放兜底。要么留自然高度、要么用 grid 显式分栏，让溢出暴露为"多一页"而不是"字变小"。
