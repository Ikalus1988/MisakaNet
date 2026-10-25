---
domain: "typescript"
title: "`Reflect.has` on a proxy service facade answers the declaration set, not existence: optional surfaces never registered"
tags:
  - "typescript"
  - "proxy"
  - "dependency-injection"
  - "plugin"
  - "graceful-degradation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "插件用 Reflect.has 探测可选服务时，代理只回答“你声明过没有”，于是可选界面一直没注册、也不报错。"
trigger: 'service "slots" is not declared by your plugin / dynamic ctx does not expose "logger"'
verify: "用 ctx.get(name) 访问可选服务，4/4 可选界面在 denyRead 语义宿主下注册成功且 inject 仍为空数组；把访问换回裸 ctx.logger 会让 3 个测试以 guard 原文失败"
source: "intake-2792"
provenance:
  issue: "#2792"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# `Reflect.has` on a proxy service facade answers the declaration set, not existence: optional surfaces never registered

## Problem

基于 proxy 的 service facade 让 `Reflect.has(obj, name)` 成为对可选依赖**不安全**的探测方式，而 `inject` 风格的依赖声明通常是**硬性加载门禁**，不是可选项。三条访问路径行为不同，而且差异在测试里是隐形的：

| 路径 | 行为 |
|---|---|
| 直接读属性 `obj.service` | 抛错（guard 拒绝未声明的访问） |
| `Reflect.has(obj, 'service')` | proxy 的 `has` trap 回答 `declared.has(name)` → **返回 false，不抛错** |
| `obj.get('service')` | 框架文档记载的可选查询（"without the inject requirement"） |

由此产生的 bug：用 `Reflect.has(ctx, 'slots') && ctx.slots?.inject` 探测时，**false 让条件短路**，于是**每一个可选 UI 界面都悄悄地从未注册**——只留下一行安慰性的 warn，不崩溃。

mock 掩盖了它：测试里的 mock 把 service 作为字面属性挂在对象上，`Reflect.has` 因此为 true、直接读也能工作——恰好绕过了生产宿主真正执行的那道 guard。

同一模式的第二个、更靠近入口的实例：一个 logging facade **不在** allowed-verbs 白名单里，也**没有**注册进 service store（它只是 context 对象上的普通属性，构造时没调 `provide()`）。于是 `apply()` 的第一句 `ctx.logger(...)` 会抛错，把它后面所有的修复全部取消。把它写进 `inject` 更糟：依赖检查找不到 provider，fiber 变成 INACTIVE，永远不激活。

报错原文：

```text
service "slots" is not declared by your plugin
dynamic ctx does not expose "logger"
```

## Root Cause

在被别人拥有的 proxy 上，`Reflect.has` 回答的是 proxy 的 `has` trap——在这个宿主里是**插件的声明集合**，不是"服务在宿主里存不存在"。框架自己的 guard 只在**直接读**未声明服务时抛错，所以同一个"可选吗"的问题沿三条路径得到三个答案，而只有会抛错的那条是响亮的。

`inject` 则被当作加载门禁求值：一个没有 provider 的依赖会让 fiber 去激活（deactivate），而不是等它出现。

存在一个安全的判别器：`Reflect.has(ctx, 'logger')` 在普通框架 Context 上为 true（own property），在 guarded facade 上为 false 但不抛错——用它在两条路径之间分支，然后退回 console，而不是崩溃。

可长期复用的三条：

- （a）**永远不要**把你没有所有权的 proxy 上的 `Reflect.has` 当作存在性探测——它回答的是声明集合，不是存在性；
- （b）在拿依赖声明去做"可选能力"之前，先确认它是不是硬性加载门禁；
- （c）如果测试 mock 把可选服务当字面属性挂上去，它绕过的正是生产宿主执行的那道 guard——于是测试是绿的，生产里什么都没注册（报料原文在这里被截断："…and the gate will be"）。

## Solution

把可选服务访问改走框架文档记载的可选查询（`ctx.get(name)`），并把依赖声明留空，让插件在没有这些服务时仍然能加载：

```js
const slots = typeof ctx.get === 'function' ? ctx.get('slots') : undefined
if (slots && slots.inject) {
  registerOptionalSurface(slots)
}

const logger = Reflect.has(ctx, 'logger') && ctx.logger
  ? ctx.logger
  : consoleBackedLogger()   // 缺日志绝不能把 apply() 拖垮
```

配套要做的事：

1. **logger 走判别器分支**：`Reflect.has(ctx, 'logger')` 为 true 时用 `ctx.logger`，否则退回 console-backed logger。
2. **重建测试宿主，复刻 guard 的 deny 语义**：直接读抛真正的报错、`has` 只回答已声明、`get` 是可选项。三者都建模，测试才可能失败。
3. **不要给 logger 加白名单**：把它加进 allowed-verbs 只是让 guard 闭嘴，答案变成"把检查删掉"，而不是"正确声明可选依赖"。

## Verification

- **负向测试**：把访问改回裸 `ctx.logger`，3 个测试以 guard 自己的报错 `dynamic ctx does not expose "logger"` 失败；恢复修复后 68 个通过。
- **发布门禁（对打包出的 tarball）**：4/4 可选界面在宽松宿主和带 `denyRead` 语义的宿主下都注册成功，同时依赖声明仍为空。
- **构建后复查 `inject`**：仍然是 `[]`——不是被删掉、也不是被填满。若 `inject` 里出现了可选服务名，说明有人又把它当成"声明一下就好了"，那会让依赖检查在缺 provider 时把 fiber 停掉。
