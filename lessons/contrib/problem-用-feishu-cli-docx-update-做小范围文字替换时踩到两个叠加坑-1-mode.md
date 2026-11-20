---
title: "feishu CLI 的 replace 会假成功：success 为真、matched_text 也回显了，文档的 modified_time 与内容却没变"
domain: "feishu"
tags:
  - "docx"
  - "success"
  - "batch-update-blocks"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4729"
summary_plain: "用 feishu CLI `docx update` 做小范围文字替换时踩到两个叠加坑： 1."
trigger: "Problem 用 feishu CLI `docx update` 做小范围文字替换时踩到两个叠加坑： 1. `--mode replace --select. 用 feishu CLI `docx update` 做小范围文字替换时踩到两个叠加坑： 1."
verify: "对同一批 5 处修改分别用三种方式实测：docs_ai 含换行 select → modified_time 不变（假成功）；replace-all 片段 → 块被截断（keyword \"存得进\" 检索命中 0，条目只剩替换片段）；最后用 replace 锚点回填完整条目 → keyword 回读 6 个案例条目全部完整、断行消失。 5 处断行缝合：docs_ai 含换行 select 三次…"
provenance:
  issue: "#4729"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用 feishu CLI `docx update` 做小范围文字替换时踩到两个叠加坑：
1. `--mode replace --select "A\nB"`（选区含换行，bash $'...' 传入）返回 `success: true` 且 echoed matched_text，但实际**没有写入**（文档 modified_time 不变、内容无变化）——比 1770002 更隐蔽的"假成功"。
2. 改用 `--mode replace-all --select "片段" -c "新片段"` 修补后，实际行为是**把整个块的内容替换为 -c 的内容**，不是只替换匹配片段——原条目里选区之外的文字全部被截掉（一条长条目被截得只剩替换进去的几个字）。
3. 另外 `--mode replace --select "纯文本片段"` 在块内替换成功时，常在拼接处把块拆成两行（markdown 导出显示 `文本␣␣\n文本`，飞书里视觉断行）。

## Root Cause

1. docs_ai 匹配路径对含换行的 str_replace：匹配成功但写入阶段静默失败，响应结构与成功无异，无任何 warning。
2. replace-all 的语义是"把命中块整体换成新内容"（类似 batch-update-blocks 的 content 语义），而不是 str_replace 的子串替换；工具文档只写"替换所有匹配片段"，未提示整块覆盖。
3. 块内子串替换会在替换边界插入软换行/拆块，是 docs_ai 写入的已知副作用。

## Fix

1. 含换行的选区（拼接断行缝合）不要用 docs_ai 的 replace：改用本地路径或先 `docx blocks` 拿块 ID 后 `batch-update-blocks` 整块写入完整文本；或者把新文本作为完整条目用纯文本片段 replace 回填。
2. 修补块内文字时优先 `--mode replace --select "完整旧片段"` + `-c "完整新片段"`（子串级，安全）；**禁止用 replace-all 做片段修补**——它会截掉块内其余内容。若误用，按 `fetch --scope keyword` 回读发现条目被截成只剩替换文本，立即用 replace 以残留文本为 select 锚点回填完整条目。
3. 每次写入后核对 modified_time 是否推进 + keyword 回读目标文本；success:true 不可信，matched_text 回显也不可信。

## Verification

对同一批 5 处修改分别用三种方式实测：docs_ai 含换行 select → modified_time 不变（假成功）；replace-all 片段 → 块被截断（keyword "存得进" 检索命中 0，条目只剩替换片段）；最后用 replace 锚点回填完整条目 → keyword 回读 6 个案例条目全部完整、断行消失。

5 处断行缝合：docs_ai 含换行 select 三次 success 但 modified_time 不变；replace-all 触发整块截断（条目残缺）；最终 replace 完整条目回填后六个案例 3×6 条目全文回读无残缺、无断行
