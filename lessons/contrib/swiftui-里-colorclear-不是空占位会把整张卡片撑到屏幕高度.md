---
title: "SwiftUI 里 Color.clear 不是「空占位」：会把整张卡片撑到屏幕高度"
domain: "mobile"
tags:
  - "swiftui"
  - "ios"
  - "layout"
  - "color-clear"
  - "spacer"
  - "hstack"
  - "flexible-view"
  - "geometry"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4181"
summary_plain: "为了给卡片右列留出「和另一张卡箭头同宽」的空位，写了 `Color.clear.frame(width: 14)` 放进 `HStack`。结果整张卡片被撑到接近屏幕高度，原本的 `frame(minHeight: 76)`…"
trigger: "SwiftUI 里 Color.clear 不是「空占位」：会把整张卡片撑到屏幕高度. 为了给卡片右列留出「和另一张卡箭头同宽」的空位，写了 `Color.clear.frame(width: 14)` 放进…"
verify: "预览图里两张卡片高度都等于 `cardH`（76pt）；iPhone SE 这类小屏也不会被撑高；把占位换回 `Color.clear` 能复现「卡片撑满屏幕」，证明判据真的覆盖到了这个坑。"
provenance:
  issue: "#4181"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

为了给卡片右列留出「和另一张卡箭头同宽」的空位，写了 `Color.clear.frame(width: 14)` 放进 `HStack`。结果整张卡片被撑到接近屏幕高度，原本的 `frame(minHeight: 76)` 完全失效，两张并排的卡片背景块一大一小，看起来像布局崩了。

## Root Cause

`Color` 是**双向可伸缩**视图（没有固有尺寸），放进 `HStack` 会把可用空间全部吃掉，**包括竖直方向**。`.frame(width: 14)` 只约束宽度、不约束高度，所以 `frame(minHeight: 76)` 只能保证「不小于」，不能保证「不大于」。同理 `Spacer`、`Rectangle`、`EmptyView().background(...)` 都不是「什么都不占」的意思。

## Fix

用「同尺寸 + 透明」的**真实视图**占位（`Image` 有固有尺寸，不会抢高度）：

```swift
// WARNING: 不要用 Color.clear
Image(systemName: "chevron.down")
    .bmsFont(11, weight: .bold)
    .frame(width: Self.chevronW)   // 和另一张卡的箭头同一个常量
    .opacity(0)
    .accessibilityHidden(true)
```

如果确实需要空白弹性区域（比如把内容推到左边），才用 `Spacer()`，并且给容器显式 `.frame(height:)`。
判据：占位视图必须**自己有固有尺寸**；没有固有尺寸的视图不能当占位。

## Verification

预览图里两张卡片高度都等于 `cardH`（76pt）；iPhone SE 这类小屏也不会被撑高；把占位换回 `Color.clear` 能复现「卡片撑满屏幕」，证明判据真的覆盖到了这个坑。
