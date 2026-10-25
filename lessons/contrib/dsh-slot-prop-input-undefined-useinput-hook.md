---
domain: "dsh"
title: "DSH slot prop `props.input` never exists: reads undefined and silently overwrites user input"
tags:
  - "dsh"
  - "client-plugin"
  - "slot-catalog"
  - "useinput"
  - "silent-degradation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 插件里 props.input 这个 prop 根本不存在，读到的永远是 undefined，于是把用户已经输入的草稿覆盖掉且不报错。"
trigger: "props.input undefined dsh slot standardProps useInput always undefined"
verify: "slot-catalog 里 conversation.input.left / conversation.input.overlay 两段没有 input 字段但有 useInput；插件打字后点表情是追加，关面板重开再点是继续追加，连点多张换行依次追加"
source: "intake-2847"
provenance:
  issue: "#2847"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH slot prop `props.input` never exists: reads undefined and silently overwrites user input

## Problem

为 DSH 写一个 Web 客户端插件时，需要在输入框 slot 里读写用户当前草稿，于是按 `props.input.draft` 取值：

```js
const draft = props.input.draft
```

不报错、不告警、控制台无任何异常，但行为悄悄错了：取到的草稿永远是空字符串，插件于是把用户已经输入的内容整段覆盖掉。

出问题的 slot 是 `conversation.input.left` 和 `conversation.input.overlay`。

第一次误判是把原因归到"时序"上：先直接按 `props.input.draft` 取草稿，无效后加了一层 store 快照兜底（打开面板时拍一次）。结果快照停留在打开面板那一刻，用户后续输入仍然被覆盖——兜底修的是症状，不是那个恒为 `undefined` 的 prop。

## Root Cause

DSH 的 slot（例如 `conversation.input.left` 和 `conversation.input.overlay`）的 `standardProps` 里**根本不存在 `input` 这个 prop**。宿主提供的是：

```ts
useInput: SnapshotSelectorHook<InputState>
```

——一个 hook，不是一个对象。插件按对象访问时，`props.input` 恒为 `undefined`，`props.input.draft` 这类表达式被短路成 fallback 值（空字符串），于是"读取草稿"变成了"读到空草稿"，后续写入就以空草稿为准把用户内容盖掉。

没有任何一层会抛错：访问一个不存在的对象属性在 JavaScript 里是合法的，返回 `undefined`；对 `undefined` 再取 `.draft` 也只是 TypeError 风险，而这里的表达式被刻意写成了带 fallback 的形式，连 TypeError 都被吞掉了。

**判据**：在 DSH 的 slot 目录（`packages/extensions/cordis-client-runner/src/client/slot-catalog.ts`）里找到该 slot 段落，`input:` 字段出现 0 次，而 `useInput` 存在。也就是说，这个 prop 从来不存在，不是"这个版本暂时没有"。

同类陷阱：写 DSH 插件时应当先查 slot-catalog 里该 slot 的 `standardProps` 清单，凡是不在清单里的 prop 一律按"永远 `undefined`"处理；不要依据其他插件的写法或直觉命名来推断 prop 存在。

## Solution

改用宿主提供的 `useInput` selector hook 读取实时状态，快照降级为兜底：

```js
function selectDraft(s) {
  return s && typeof s.draft === 'string' ? s.draft : null
}

const useInput = props && props.useInput
const liveDraft = typeof useInput === 'function' ? useInput(selectDraft) : null
```

三个配套改动，缺一个就还会覆盖：

1. **以 selector 结果为准写入**：写入草稿时以 `liveDraft`（每次渲染从宿主状态选取的当前值）为准，而不是以打开面板时拍的快照为准。
2. **把 `useInput` 一起传给子组件**：原来只传了 `inputActions`，子组件拿不到 hook，只能继续读不存在的 `props.input`。
3. **保留兜底但不依赖它**：`useInput` 不可用时才退回快照，并且不要用兜底值去覆盖非空草稿。

写插件前的检查顺序也应固定下来：先读 slot 的 `standardProps` 清单 → 只使用清单内的 prop → 需要实时状态时找清单里的 hook（如 `useInput`），而不是自己从上下文对象上猜字段。

## Verification

1. **契约判据**：在 `packages/extensions/cordis-client-runner/src/client/slot-catalog.ts` 中找到 `conversation.input.left` 和 `conversation.input.overlay` 两段，逐行看 `standardProps`：`input:` 出现 0 次，`useInput` 存在。

   ```bash
   grep -n "'input:" packages/extensions/cordis-client-runner/src/client/slot-catalog.ts
   grep -n "useInput" packages/extensions/cordis-client-runner/src/client/slot-catalog.ts
   ```

   第一条命令应无任何输出（0 命中），第二条能命中该 slot 段落。

2. **三条行为路径**（修复后全部通过）：
   - 打字后点选表情 → 追加在原文之后，不覆盖；
   - 关掉面板重开再点选 → 继续追加，而不是退回最初草稿；
   - 连续点选多张 → 依次换行追加。

3. **失败判据**：把写入目标改回 `props.input.draft`，上面三条里第一条就会变成"原文被表情替换"——即使用户已经打了字。这说明修复点确实是那个不存在的 prop。
