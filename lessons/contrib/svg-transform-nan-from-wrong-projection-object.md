---
title: "translate(NaN NaN) is silently ignored: read the isometric trig values from the camera object, not the projection"
domain: "frontend"
tags:
  - "svg"
  - "isometric"
  - "nan"
  - "transform"
  - "headless-chrome"
  - "debugging"
  - "animation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "等距 SVG 动画不生效、控制台干净，往往是算出了 translate(NaN NaN) 被浏览器静默忽略——三角值取错了对象。"
trigger: "translate(NaN NaN) / 读数变了画面不动 / 动画设置了但没有位移 / SVG transform 含 NaN 却无报错"
verify: "headless Chrome --dump-dom 查目标 g 元素的 transform 属性为数字（如 translate(272.3 155)）而非 NaN，且分步截图可见零件真实位移。"
source: "intake-3273"
provenance:
  issue: "#3273"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# translate(NaN NaN) is silently ignored: read the isometric trig values from the camera object, not the projection

## Problem

做等距 SVG 交互图（anatomy kit 类）时，自写的屏幕位移函数直接从 projection 对象上取 `sinA` / `cosA` / `k` 来算 `translate`——但该 projection 只存 `scale` / `azimuth` / `elevation` / `origin`，三角值在 `cameraOf(projection)` 的返回里。

结果：`transform="translate(NaN NaN)"`，浏览器静默忽略。读数区文字正常更新、`console` 干净、没有任何报错，但零件就是不动，截图上完全看不出已经「设置」了动画。

## Root Cause

`projection` 是**参数包**（可序列化、可持久化）；`cameraOf(projection)` 才是**派生相机**（含 `sinA` / `cosA` / `k` 等三角值与缩放系数）。两者字段不同，取错对象就是 `undefined`：

```
undefined * 数值 → NaN
```

SVG 的 `transform` 属性语法上不接受 `NaN`：解析失败即整条变换被丢弃，按规范是静默的——不抛异常、不写 `console`、元素留在原位。于是故障表现成「JS 都跑了，画面没动」，最容易被误判成动画没触发或渲染没刷新。

构建侧同型问题：把「以为有字段」的对象直接序列化进 live 脚本的坐标参数，同样得到 `NaN`，而且静态存在于构建产物里，比运行时更难发现。

## Solution

1. **三角值从相机取**：在 `cameraOf(P)`（或自建 camera 结构）上取 `sinA` / `cosA` / `k`，不要直接读 `projection` 字段：

```js
const cam = cameraOf(projection);           // { sinA, cosA, k, ... }
const sx = cam.k * (x * cam.cosA - y * cam.sinA);
const sy = cam.k * (x * cam.sinA + y * cam.cosA);
g.setAttribute('transform', `translate(${sx} ${sy})`);
```

2. **构建期序列化计算后的值**，不要序列化「以为有字段」的对象——`JSON.stringify` 会把 `undefined` 静默丢掉，读回来就是 `NaN`。
3. **诊断用 `--dump-dom`，不要用截图对比**：动画「读数变了画面不动」时，用 headless Chrome `--dump-dom` 直接查目标 `<g>` 的 `transform` 属性是否含 `NaN`——比截图对比快且确定：

```bash
google-chrome --headless --disable-gpu --dump-dom '<页面地址>' | grep -o 'transform="[^"]*"'
```

报料者未给出完整的 `--dump-dom` 调用与页面路径，需复现确认。

## Verification

1. `--dump-dom` 输出 `transform="translate(272.3 155)"`（数字正常），不再是 `translate(NaN NaN)`；
2. 分步截图确认焊钳从拆帽位真实移动到修磨位（截图只是二次确认，判据仍是属性值）；
3. kit 自带 `lines.mjs` 校验输出 `line ends: 0` 收口。
