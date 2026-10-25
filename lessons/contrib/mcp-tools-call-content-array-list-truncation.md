---
domain: "mcp"
title: "MCP tools/call envelope: a list result is one `content[]` item per element, not one JSON array in `content[0]`"
tags:
  - "mcp"
  - "fastmcp"
  - "tools-call"
  - "envelope"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "MCP 工具返回列表时，content[] 是一条记录一项；只解析 content[0] 会把 11 条记录静默截成 1 条，而且不报错。"
trigger: "tools/call list result silently truncated to first element content[0].text"
verify: "同一个 list 工具分别经 MCP 传输与 Python 直调，记录条数相等；单测断言多个 content 项被还原成完整数组，单 content 项仍返回单值"
source: "intake-2765"
provenance:
  issue: "#2765"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# MCP tools/call envelope: a list result is one `content[]` item per element, not one JSON array in `content[0]`

## Problem

FastMCP `tools/call` 的信封解包有一个坑：工具返回 **list** 时，`content[]` 是**一项一个元素**（每一项的 `text` 是一个 JSON 对象），而不是把整个列表序列化进 `content[0].text`。

只解析 `content[0]` 会把列表静默截断成第一条记录。实测：一个 list 类工具返回 11 条记录 = 11 个 content 项，取第一项后只剩 1 条，**且不报错**。

暴露它的不是解包代码，而是下游的一条断言——`Array.isArray(payload)` 失败。也就是说，如果没有那条断言，截断会一路传下去。

报错/现象原文：`tools/call list result silently truncated to first element`。

## Root Cause

解包代码把 dict 返回的形状当成了通用形状：工具返回单个 dict 时，`content[0].text` 确实包含那一个序列化的对象，所以"只读第一项"在 dict 场景下一直是正确的——错误因此在很长一段时间里不可能被发现。

而 list 返回时，FastMCP 把**每个元素**序列化成自己的一个 content 项，于是 `content.length` 等于记录数，而不是 1。任何"只取一项"的客户端都会丢掉 `n-1` 条记录，并且**协议层面这个响应是完全合法的**：没有错误、没有 warning、没有畸形结构，只有客户端自己的假设错了。

## Solution

解 `tools/call` 信封时**逐项解析 `content[]`**，再按条目数决定返回单值还是数组：

```js
function unwrap(result) {
  if (result && result.isError) throw new Error(collectText(result.content))

  const parts = Array.isArray(result.content)
    ? result.content.map(item => JSON.parse(item.text))
    : []

  if (parts.length === 1) return parts[0]   // dict 返回：单值
  if (parts.length > 1) return parts        // list 返回：完整数组
  return result.structuredContent ?? result // 兼容分支
}
```

四条规则：

1. **`content.length === 1` 返回单值，`> 1` 返回数组。** 不要假设"第一个就是全部"。
2. **用 `isError` 标志处理错误信封**，而不是把错误项的 `text` 当数据 `JSON.parse` 掉。
3. **保留 `structuredContent` 分支**：同一份客户端要能读懂不同宿主（以及我们自己的服务端）返回的结构化载荷。
4. **保留裸对象兼容分支**：测试里的假服务端常常直接返回一个普通对象，而不是完整的 `content[]` 信封。

## Verification

- **条数一致**：对同一个 list 工具，分别经 MCP 传输调用与在 Python 里直调，返回的记录条数相等（11 条对 11 条）。
- **字段一致**：对 dict 返回的工具，经 MCP 与直调得到的字段一致。
- **单测判据**：断言一个含多个 content 项的响应被还原为完整数组（11 项进、11 项出）；单个 content 项的响应仍然返回单值，而不是被包成一层数组。
- **失败判据**：把解包改回 `JSON.parse(result.content[0].text)`，上面第一条就会变成"11 条变 1 条，但没有任何异常"——这正是需要用断言而不是靠"看起来成功"来兜住的地方。
