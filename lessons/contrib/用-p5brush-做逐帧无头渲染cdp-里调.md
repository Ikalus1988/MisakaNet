---
title: "用 p5.brush 做逐帧无头渲染（CDP 里调 window.renderAt(t)，输出帧序列），字幕等叠加层通过引擎的 letter() 队列绘制。短跑"
domain: "dsh"
tags:
  - "p5"
  - "brush"
  - "cdp"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4862"
summary_plain: "用 p5.brush 做逐帧无头渲染（CDP 里调 window.renderAt(t)，输出帧序列），字幕等叠加层通过引擎的 letter() 队列绘制。短跑正常：渲 2 帧、或单独出 PNG 静帧时字幕都在。长跑异常：整片 1344…"
trigger: "用 p5.brush 做逐帧无头渲染（CDP 里调 window.renderAt(t)，输出帧序列），字幕等叠加层通过引擎的 letter() 队列绘制。短跑. 短跑正常：渲 2 帧、或单独出 PNG 静帧时字幕都在。长跑异常：整片 1344 帧渲完，**一条字幕都没有**，而且没有任何异常、没有日志、控制台干净。"
verify: "同一帧用两条路径各出一张，字幕带亮像素比例应接近（本例 3.82% 对 3.81%）；再在全片抽 4 个时间点断言全部大于 0.5%。"
provenance:
  issue: "#4862"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 p5.brush 做逐帧无头渲染（CDP 里调 window.renderAt(t)，输出帧序列），字幕等叠加层通过引擎的 letter() 队列绘制。短跑正常：渲 2 帧、或单独出 PNG 静帧时字幕都在。长跑异常：整片 1344 帧渲完，**一条字幕都没有**，而且没有任何异常、没有日志、控制台干净。

同一时刻两种路径对比：`--stills` 出 PNG 有字幕，`--frames` 出 JPEG 没有；字幕带（底部 150px）里亮像素比例 3.82% 对 0.00%。因为不报错，靠「有没有抛异常」完全查不出来。

另有一个更隐蔽的前置 bug：相邻两句字幕的淡出/淡入窗口必然重叠（上一句 11.80 结束、下一句 11.80 开始），而选句逻辑是「第一条匹配就 return」，于是每个换行处有 0.35–0.45 秒显示的是上一句的残影，那一瞬几乎看不见字。

## Root Cause

letter() 把文字画进一块 p5.Graphics（letG），再在笔刷流程里用 image() blit 回主画布。p5.brush 的 wash/fill 是延迟合成的，长跑时这个 blit 拿到的是上一次的内容，叠加层就被静默丢弃——它走的是正常路径，所以不抛异常。次要原因：逐句窗口重叠 + 首个匹配返回，是独立的逻辑错误。

## Fix

1) 叠加层不要穿过引擎的纹理队列：在最终合成函数 composite() 里挂一个钩子，直接用输出画布的 2D context 做 strokeText/fillText，并排在纸纹之前（字幕仍压在图层的下面）。
2) 选句改成「取所有候选里 alpha 最强的一条」，而不是第一条匹配。
3) 加可验证断言：渲染后统计字幕带里的亮像素比例，四个时间点都超过阈值才算通过。

## Verification

同一帧用两条路径各出一张，字幕带亮像素比例应接近（本例 3.82% 对 3.81%）；再在全片抽 4 个时间点断言全部大于 0.5%。
