---
title: "飞书 doc_delete_blocks_by_range 不传 end 会删到文档末尾"
domain: "feishu"
subdomain: "mcp-api"
tags:
  - feishu
  - mcp
  - data-loss
  - api-pitfall
  - docx
source: "zsxh1990"
status: "published"
confidence: "1.0"
created: "2026-06-25"
domain_expert: "zsxh1990"
verified_date: "2026-07-06"
---

## Problem

调用飞书 `doc_delete_blocks_by_range` 时只传了 `start=0` 没传 `end`，想删5行残留旧内容，结果工具从 start 一直删到文档末尾，**删掉 172 个块，整篇文档被清空**（含标题、阶段性汇报、backup 全部内容）。用户靠飞书历史版本才恢复。

## Root Cause

`doc_delete_blocks_by_range` 的 `end` 参数省略时语义是"删到末尾"（`Omit to delete to the last child`），不是"删一个块"。与直觉相反，且工具描述容易被忽略。

## Solution

1. **删少量块时不要用 `doc_delete_blocks_by_range`**，改用 `doc_delete_blocks_by_ids`（显式传 block_id 列表，精确控制删什么）。
2. **必须用 range 时，始终显式传 `end`**（`end = start + count`），绝不省略。
3. 删之前先用 `doc_fetch` scope=keyword 或 range 确认要删的块范围和数量，核对 start/end 对应的实际块。
4. 替换单个子节内容优先用 `doc_update` 的 `select_title`（替换整个子节到下一个同级标题）或 `select`（精确文本），不会误伤后续内容。
5. 飞书 wiki 文档有历史版本可回滚——出事后第一时间让用户从历史版本恢复，比尝试重建可靠得多。

## Verification

```python
# ❌ 危险：不传 end 会删到末尾
doc_delete_blocks_by_range(document_id, parent_block_id, start=0)

# ✅ 安全：显式传 end
doc_delete_blocks_by_range(document_id, parent_block_id, start=0, end=5)

# ✅ 更安全：用 block_ids 精确删除
doc_delete_blocks_by_ids(document_id, ["block_id_1", "block_id_2"])
```
