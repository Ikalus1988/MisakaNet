---
title: "飞书文档 MCP doc_update 整表重写后，旧表格容器残留成空表。 症状 用 doc_update（mode=replace, select=\"起始文本"
domain: "feishu"
tags:
  - "mcp"
  - "doc"
  - "update"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4745"
summary_plain: "飞书文档 MCP doc_update 整表重写后，旧表格容器残留成空表。"
trigger: "飞书文档 MCP doc_update 整表重写后，旧表格容器残留成空表。 症状 用 doc_update（mode=replace, select=\"起始文本. 飞书文档 MCP doc_update 整表重写后，旧表格容器残留成空表。"
verify: "回读区间：新表最后一行之后直接是下一个章节标题，无第二个空表；outline 正常。经验信号：blocks_deleted == 旧表行×列+1（标题）且 blocks_added == 2（新标题+新表）时，旧容器必然残留，必须回读并按 ID 清理。"
provenance:
  issue: "#4745"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

飞书文档 MCP doc_update 整表重写后，旧表格容器残留成空表。

## Root Cause

select 区间替换走 blocks 路径时，删除的是旧表格各单元格的文本块（行×列个）加标题块，但旧表格容器块（block_type 31）本身不删，只被掏空；新表是另一个新容器。也就是说「整表重写」实际是「删单元格文本 + 插新表」，旧容器必然残留。

## Fix

每次 doc_update 后 doc_fetch 回读校验（本例就是回读发现的）。发现空表残留后：doc_get_block 确认目标块（row_size/column_size 与旧表一致、单元格全空、parent 是文档根），再 doc_delete_block 按精确 block_id 单块删除容器。不要用 doc_delete_blocks_by_range 清理（漏传 end 会删到文档末尾，另有课程）。

## Verification

回读区间：新表最后一行之后直接是下一个章节标题，无第二个空表；outline 正常。经验信号：blocks_deleted == 旧表行×列+1（标题）且 blocks_added == 2（新标题+新表）时，旧容器必然残留，必须回读并按 ID 清理。
