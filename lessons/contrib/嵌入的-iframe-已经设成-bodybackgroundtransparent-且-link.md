---
title: "嵌入的 iframe 已经设成 `body{background:transparent}` 且 link 进去的样式里没有不透明底色，但页面**整体仍然刷成不"
domain: "dsh"
tags:
  - "body-background-transparent"
  - "html-color-scheme-light"
  - "color-scheme-only"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5177"
summary_plain: "嵌入的 iframe 已经设成 `body{background:transparent}` 且 link 进去的样式里没有不透明底色，但页面**整体仍然刷成不透明白色**，把宿主壁纸全挡住。宿主的祖先链 background 全是…"
trigger: "iframe 透明 仍然白色 color-scheme 根画布 transparent 不生效"
verify: "同源 iframe 注入 `:root{color-scheme: light dark !important}` 后重新加载，屏���截图中 iframe 区域应能看到宿主壁纸（把 iframe 设 visibility:hidden 前后对比，显示后不应出现白色矩形）。"
provenance:
  issue: "#5177"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

嵌入的 iframe 已经设成 `body{background:transparent}` 且 link 进去的样式里没有不透明底色，但页面**整体仍然刷成不透明白色**，把宿主壁纸全挡住。宿主的祖先链 background 全是 rgba(0,0,0,0)，把 iframe 设 visibility:hidden 后宿主透壁纸、一显示 iframe 就变白 —— 说明白底是 iframe 自己画的，可 CSS 里找不到它是谁画的。

## Root Cause

不是 body 的 background，而是 **根画布**：页面 `<html data-theme="light">` 命中了页面自带的 `:root[data-theme="light"]{color-scheme:light}`。Chromium 会按根元素的 `color-scheme` 用不透明浅色填充根画布，`body{background:transparent}` 盖不住它（body 只覆盖内容盒，不覆盖画布）。验证办法：srcdoc 对照实验 —— `html{color-scheme:light dark}` 透明、`color-scheme:only light` 白、把 `[data-theme="light"]` 那条规则改成 `light dark` 立刻变透明。

## Fix

注入一段 CSS 覆盖根元素（宿主同源时可在 iframe 的 onLoad 里往 contentDocument 塞 <style>，跨源则只能改页面本身）：

```css
:root, :root[data-theme] { color-scheme: light dark !important; }
html, body { background: transparent !important; }
```

跨进程 iframe 里 `backdrop-filter: blur()` 采样不稳，别用它做"玻璃底纱"；要透明就别铺整页底色，只给卡片加薄暗纱（`--bg-elev: rgba(8,11,18,.46)`），否则白字压在亮背景上看不清，再配 `text-shadow: 0 1px 2px rgba(0,0,0,.66)` 给没暗纱的小字兜底。

## Verification

同源 iframe 注入 `:root{color-scheme: light dark !important}` 后重新加载，屏���截图中 iframe 区域应能看到宿主壁纸（把 iframe 设 visibility:hidden 前后对比，显示后不应出现白色矩形）。
