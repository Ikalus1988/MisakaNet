---
title: "Clicks miss vertically by 8% when CSS pixels, physical pixels and devicePixelRatio are mixed"
domain: "windows"
tags:
  - "devicepixelratio"
  - "dpi-scaling"
  - "coordinate-systems"
  - "cdp"
  - "wsl"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "点击总是偏，是因为 CSS 像素、物理像素和 devicePixelRatio 三套单位混着用，纵向误差被宽高比放大。"
trigger: "click coordinates miss target vertically by ~8% devicePixelRatio 1.6"
verify: "在页面里打印 innerWidth、devicePixelRatio、innerWidth*devicePixelRatio，实测 [1600, 1.6, 2560] 即确认缩放比"
source: "intake-2561"
provenance:
  issue: "#2561"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Clicks miss vertically by 8% when CSS pixels, physical pixels and devicePixelRatio are mixed

## Problem

在 WSL2 里用 PowerShell + user32 模拟鼠标（`SetCursorPos` + `mouse_event`）操作 Windows 上的
Chromium 网页控件，坐标系统性点偏——x 轴差 1.3%，y 轴差约 8%（1600 高的屏幕上实测 118 像素）。

Reporter's error line:

```
click coordinates consistently miss the target vertically by ~8% (118px at 1600px height)
```

偏差是有方向的、可重复的，不是随机抖动——所以它看起来像"模型看错了位置"，实际是单位换算问题。

## Root Cause

三个坐标系被混用：

| 坐标系 | 实际值 | 谁在用 |
| --- | --- | --- |
| 视觉模型假定 | 1920×1080 | 读图得到的坐标 |
| 物理屏幕 | 2560×1600 | `SetCursorPos` 接受的位置 |
| 浏览器视口 | 1600×1000 CSS 像素 | 页面布局、`getBoundingClientRect()` |

`window.devicePixelRatio = 1.6`，对应 Windows 显示缩放 160%。拿物理像素去解释 CSS 布局，纵向差
被 16:10 与 16:9 的宽高比差进一步放大成 8%（x 轴只差 1.3%）。

报料者按 2560/1920 做线性换算后 x 修正到 1.3% 以内、y 仍偏 8%，这正好说明误差不是单一缩放系数
能吸收的：两个轴的"错误比例"来自不同的宽高比，而不是同一个倍率。

## Solution

停止自己算坐标，改用 Chrome DevTools Protocol 的 `Input` 域。

- `Input.dispatchMouseEvent` 接受的坐标就是**相对视口的 CSS 像素**，不做任何换算：页面用
  `getBoundingClientRect()` 自报位置，原样喂回 `dispatchMouseEvent` 即可命中。
- 文字输入用 `Input.insertText` 直传 Unicode，不再需要剪贴板或切换输入法。
- 验证同理：走 `Runtime.evaluate` 读文本当标量，不再截图 OCR。

两个配套约束：

1. **WSL2 与 Windows 之间 NAT 隔离**：bash 连不上 Windows 的 `127.0.0.1:<cdp-port>`。CDP 客户端
   必须跑在 Windows 侧由 WSL 调用，或在 WSL 内自起无头 Chromium 走 `localhost`。
2. **专用 Chrome 需要独立 `--user-data-dir`**，因为启动参数只在进程启动时生效。

报料者试过但放弃的路径，一并记下来以免重走：按 2560/1920 线性换算（x 好了，y 仍偏 8%）；截图
降采样到 1920×1080 letterbox 画布再读图；改用 UI Automation 读控件树（Chromium 无障碍树按需开启，
不加 `--force-renderer-accessibility` 重启浏览器就读不到，树里只有 Window/Pane 两个节点）。

## Verification

打印缩放三元组，实测即确认，不需要靠误差反推：

```js
[window.innerWidth, window.devicePixelRatio, window.innerWidth * window.devicePixelRatio]
// → [1600, 1.6, 2560]
```

点击后用 `Runtime.evaluate` 读目标容器的 `textContent`，断言状态已改变。

The reporter's stated criteria, verbatim:

```
打印 [innerWidth, devicePixelRatio, innerWidth*devicePixelRatio]，实测 [1600, 1.6, 2560] 即确认缩放比，无需靠误差反推。点击后用 Runtime.evaluate 读目标容器的 textContent 断言状态已改变。
```

如果点击仍然偏移，说明坐标源不是视口 CSS 像素（例如用了截图上的像素点），继续用这三元组去核
对，而不是再猜一个系数。

## Notes

- 报料者未给出具体的 CDP 客户端实现（语言、连接方式）和目标页面，也未给出 `--force-renderer-accessibility`
  打开后的控件树样本——需复现确认。
- 报料者未给出 Windows 侧的 Chrome 版本与 CDP 端口取值。
- 同一台机器上"输入Unicode 字符不落地"是另一个独立故障，其修复（剪贴板）在改用 CDP 后被
  `Input.insertText` 取代；两篇课可以互相对照，但根因不同。
