---
title: "Problem 给「剩余容量」做水位分级：剩余 ≤10% 判告急（红）、≤25% 判偏低（黄）、取不到判 unknown（灰）。实现写成： 单测一跑就红：`tp"
domain: "mcp"
tags:
  - "problem"
  - "unknown"
  - "tp"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3889"
summary_plain: "给「剩余容量」做水位分级：剩余 ≤10% 判告急（红）、≤25% 判偏低（黄）、取不到判 unknown（灰）。实现写成： ```js const lg = Number(largestKb) const tot =…"
trigger: "Problem 给「剩余容量」做水位分级：剩余 ≤10% 判告急（红）、≤25% 判偏低（黄）、取不到判 unknown（灰）。实现写成： 单测一跑就红：`tp. 给「剩余容量」做水位分级：剩余 ≤10% 判告急（红）、≤25% 判偏低（黄）、取不到判 unknown（灰）。实现写成： ```js const lg…"
verify: "单测必须覆盖**空值各形态**，而不只覆盖数值边界： ```js expect(level(null, 1000)).toBe('unknown') // ← 这条抓到 bug expect(level(100, null)).toBe('unknown') expect(level(100, 0)).toBe('unknown') // 除零 expect(level(undefined…"
provenance:
  issue: "#3889"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

给「剩余容量」做水位分级：剩余 ≤10% 判告急（红）、≤25% 判偏低（黄）、取不到判 unknown（灰）。实现写成：

```js
const lg = Number(largestKb)
const tot = Number(totalKb)
if (!Number.isFinite(lg) || !Number.isFinite(tot) || tot <= 0) return 'unknown'
if (lg / tot <= 0.1) return 'critical'
```

单测一跑就红：`tppLevel(null, 1000)` 返回 `critical`，期望 `unknown`。

后果是**把「没有数据」显示成「容量告急」**——没有控制柜报告的机器本来是「查不到」，界面上却是一片红色告警。这类误报最伤信任：用户看到红的去查，发现根本不是那台机器的问题。

## Root Cause

`Number(null) === 0`，`Number(undefined)` 是 `NaN`，`Number('') === 0`。类型守卫写成了
`!Number.isFinite(lg)`——但 `null` 在**数值化之后**已经是 `0` 了，`Number.isFinite(0)` 是 true，
守卫拦不住。

「空值」被静默折叠成了「数值 0」，而 0 在阈值判定里恰好落在最低档。**类型转换发生在守卫之前**，
是这类 bug 的通用形状：任何 `Number(x)` / `parseFloat(x)` / `+x` 前面必须先挡 null/undefined，
否则守卫看到的是已经被改写过的值。

## Fix

**先挡空值，再数值化**：

```js
if (largestKb == null || totalKb == null) return 'unknown'   // ← 必须在 Number() 之前
const lg = Number(largestKb)
const tot = Number(totalKb)
if (!Number.isFinite(lg) || !Number.isFinite(tot) || tot <= 0) return 'unknown'
```

配套语义：**「查不到」不能等同于「最差档」**。缺失值要有独立状态（unknown/N/A），
UI 上区别呈现（灰 N/A vs 红告急），否则缺数据会被当成坏数据处理。

## Verification

单测必须覆盖**空值各形态**，而不只覆盖数值边界：

```js
expect(level(null, 1000)).toBe('unknown')     // ← 这条抓到 bug
expect(level(100, null)).toBe('unknown')
expect(level(100, 0)).toBe('unknown')          // 除零
expect(level(undefined, undefined)).toBe('unknown')
expect(level(100, 1000)).toBe('critical')      // 数值档位
expect(level(250, 1000)).toBe('low')
expect(level(400, 1000)).toBe('ok')
```

一句话判据：**阈值函数对「无输入」必须返回「无结论」，不能返回任何档位。**
