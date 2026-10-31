---
title: "SwiftUI 动态字体三个雷：lineLimit(1) 挡不住压缩、ContentSizeCategory 没有 isAccessibilitySize、大字号必须分级封顶"
domain: "mobile"
tags:
  - "swiftui"
  - "ios"
  - "dynamic-type"
  - "line-limit"
  - "fixed-size"
  - "minimum-scale-factor"
  - "layout"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4147"
summary_plain: "1) 三栏布局右侧日期被压成逐字换行（显示成「10-1 / 9 / 13:2 / 0」）；2) 想用 `ContentSizeCategory.isAccessibilitySize` 判断超大字号，编译不过；3) 系统字号调大后…"
trigger: "SwiftUI 动态字体三个雷：lineLimit(1) 挡不住压缩、ContentSizeCategory 没有 isAccessibilitySize、大字号必须分级封顶. 1) 三栏布局右侧日期被压成逐字换行（显示成「10-1 / 9 / 13:2 / 0」）；2) 想用…"
verify: "系统字号调到最大：首页三栏不换行、按钮不出屏、不裁字；默认字号下与改动前截图逐像素一致。"
provenance:
  issue: "#4147"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

1) 三栏布局右侧日期被压成逐字换行（显示成「10-1 / 9 / 13:2 / 0」）；2) 想用 `ContentSizeCategory.isAccessibilitySize` 判断超大字号，编译不过；3) 系统字号调大后 46pt 的按钮变成 74pt，直接挤出屏幕。

## Root Cause

1) lineLimit(1) 只限制行数，不阻止父容器在空间不足时把文本压缩到逐字换行，需要 fixedSize 或 minimumScaleFactor 才能真正锁宽；2) isAccessibilitySize 是 UIKit `UIContentSizeCategory` 的成员，SwiftUI 的 `ContentSizeCategory` 没有；3) 动态字体倍率是统一乘数，基数字号越大绝对增量越大，必须分档封顶。

## Fix

```swift
// 1) 锁宽
Text(dateText).lineLimit(1).fixedSize(horizontal: true, vertical: false)
// 或允许缩字
Text(label).lineLimit(1).minimumScaleFactor(0.7)

// 2) 自己补扩展
extension ContentSizeCategory { var bmsIsAccessibility: Bool { ... } }

// 3) 按基准字号分档封顶：≤10pt→1.60×、21pt→1.40×、46pt→1.12×，默认档恒 1.0
```
默认档必须恒为 1.0，保证不改系统字号时逐像素不变。

## Verification

系统字号调到最大：首页三栏不换行、按钮不出屏、不裁字；默认字号下与改动前截图逐像素一致。
