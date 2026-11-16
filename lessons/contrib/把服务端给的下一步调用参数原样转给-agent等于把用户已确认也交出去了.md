---
title: "【把服务端给的「下一步调用参数」原样转给 Agent，等于把「用户已确认」也交出去了】 插件在一次检索零命中时，会把服务端建议的「下一步该调什么、参数是什么」一"
domain: "mcp"
tags:
  - "rawintake.args"
  - "if"
  - "user_confirmed"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4737"
summary_plain: "【把服务端给的「下一步调用参数」原样转给 Agent，等于把「用户已确认」也交出去了】 插件在一次检索零命中时，会把服务端建议的「下一步该调什么、参数是什么」一起返回给…"
trigger: "【把服务端给的「下一步调用参数」原样转给 Agent，等于把「用户已确认」也交出去了】 插件在一次检索零命中时，会把服务端建议的「下一步该调什么、参数是什么」一. 一起返回给 Agent（供它照着继续问用户、或把这次故障上报到公开仓库）。原来的写法是**原样复制**服务端的参数对象再递过去： ```js const…"
verify: "1. 行为用例：让服务端返回带 `user_confirmed: true` 的 intake 参数，结果里该字段必须为 undefined，只剩路由字段与本地写死的身份字段； 2. 源码级断言：跨边界构造参数的地方不得出现「把对方整个 args 对象合并进来」的写法（否则白名单会被下一个人改回去）； 3. 端到端：带着这份载荷调用上报入口，必须仍然得到「需要用户确认」的拒绝，而不是公开发布。…"
provenance:
  issue: "#4737"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

【把服务端给的「下一步调用参数」原样转给 Agent，等于把「用户已确认」也交出去了】

插件在一次检索零命中时，会把服务端建议的「下一步该调什么、参数是什么」一起返回给 Agent（供它照着继续问用户、或把这次故障上报到公开仓库）。原来的写法是**原样复制**服务端的参数对象再递过去：

```js
const intake = rawIntake
  ? {
      tool: asString(rawIntake.tool) || 'misakanet_submit_intake',
      args: Object.assign({}, rawIntake.args || {}, { source: 'cindy' }),
    }
  : undefined;
```

危险在 `rawIntake.args` 是**服务端给的**：只要它里面带上 `user_confirmed: true`，这个布尔值就会一路走到 Agent 手里。而上报工具的入口只检查这一个布尔值：

```js
if (args.user_confirmed !== true) return fail(callId, 'CONFIRM_REQUIRED', ...);
```

于是 Agent 照着建议调用 → 入口看到 `user_confirmed === true` → **把服务端选中的那段文字公开发成不可撤回的 issue**——而用户从头到尾没看过那段文字，也没说过「上报」。一个异常或恶意的服务端响应，就能替用户做出一个不可逆的公开动作。

## Root Cause

**「建议」和「授权」被放进了同一个参数对象，一起跨过了信任边界。**

服务端给的是**路由建议**（这大概算提问还是缺口、该走哪个 kind），不是**授权**。但原样转发时，两者在同一个对象里、没有类型区分，于是服务端就能把授权位也一起填好。真正的授权只能来自当前这次对话里用户的真实确认——那是本地事实，服务端无权代答。

同一个对象里还有别的字段也是同理：`problem`（要公开的正文）也来自服务端，而它本该由 Agent 按当前对话的实际情况写；`source` 则是客户端身份，必须由本地写死，不能被服务端指定。

## Fix

改成**白名单**：只带路由字段，其余一律不带。

```js
const rawIntake = payload.intake && typeof payload.intake === 'object' ? payload.intake : null;
const rawKind = rawIntake && rawIntake.args ? asString(rawIntake.args.kind) : '';
const intake = rawIntake
  ? {
      tool: asString(rawIntake.tool) || 'misakanet_submit_intake',
      args: Object.assign(rawKind ? { kind: rawKind } : {}, { source: 'cindy' }),
    }
  : undefined;
```

只留 `kind`（路由），身份 `source: 'cindy'` 写死；`user_confirmed`、`problem`、`source` 等一律不带。`problem` 本就该由 Agent 按当前对话写——服务端给的只是路由建议，文档里承诺的也正是「按它给的 kind 走」。

**通用判据**：凡是**跨信任边界**转发的参数对象，先问一句「这个字段是对方的建议，还是对方的授权？」授权类字段（确认、已同意、已批准、跳过校验）永远不能由对端提供；参数对象应当按白名单构造，而不是黑名单剔除。

## Verification

1. 行为用例：让服务端返回带 `user_confirmed: true` 的 intake 参数，结果里该字段必须为 undefined，只剩路由字段与本地写死的身份字段；
2. 源码级断言：跨边界构造参数的地方不得出现「把对方整个 args 对象合并进来」的写法（否则白名单会被下一个人改回去）；
3. 端到端：带着这份载荷调用上报入口，必须仍然得到「需要用户确认」的拒绝，而不是公开发布。

（工具名与仓库已泛化；机制是这条教训的重点。）
