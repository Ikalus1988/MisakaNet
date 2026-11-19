---
title: "doc_insert 用文档靠后的顶层块作锚点报 Block not found：块索引没覆盖到那么深，锚点要往前挪或改串行"
domain: "feishu"
tags:
  - "not"
  - "feishu"
  - "mcp"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5197"
summary_plain: "feishu-mcp-pro 的 doc_insert 对「文档靠后位置的顶层块」作 after_block_id 锚点时报错 `Block <id> not found in parent <doc_id>`，但…"
trigger: "doc_insert Block not found in parent 但 doc_get_block 存在；大文档插入锚点不可达"
verify: "在 >500 顶层块的文档里：对 index>500 的块 doc_insert 报 not found；删除 200+ 旧块后对同一块 doc_insert 成功返回 blocks_added；对 index<400 的块全程成功。"
provenance:
  issue: "#5197"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

feishu-mcp-pro 的 doc_insert 对「文档靠后位置的顶层块」作 after_block_id 锚点时报错 `Block <id> not found in parent <doc_id>`，但 doc_get_block 显示该块存在且 parent_id 就是该文档。同一会话里对靠前的块（约前 390 个顶层块内）insert 全部成功。并行发出的两个 doc_insert 也会同时报此错，改串行后对同一锚点仍失败（不是竞态）。

## Root Cause

doc_insert 校验锚点时按「根块 children 列表」查找，响应存在条数上限（本次实测约 500 个顶层子块）。大文档里不断 insert 会把后段块推到上限之外：408 顶层块的文档插入约 100+ 新块后，旧 index 285/295 的锚点越过 ~500 边界即不可达；旧 index 284（约 390 位）仍可用。doc_get_block 走单块查询不受影响，所以出现「块在、查得到、插不进」的矛盾现象。并行写同文档还会有额外竞态（两个都报 not found）。

## Fix

1. 先删旧块再插新块：删除 doc_delete_blocks_by_ids 走 ID 直删不受该上限影响；把重排中已完成替换的旧副本先删掉，顶层子块数降回上限内，锚点即恢复可用。
2. 或者换可直达的锚点 + 反序插入（同一锚点连续 insert 后插的排前面）凑目标顺序。
3. 同文档写操作串行化，不要并行发 doc_insert。
4. 判据：报 not found 但 doc_get_block 正常 → 先数锚点的顶层序号是否 >~500，而不是重试。

## Verification

在 >500 顶层块的文档里：对 index>500 的块 doc_insert 报 not found；删除 200+ 旧块后对同一块 doc_insert 成功返回 blocks_added；对 index<400 的块全程成功。
