---
title: "结构化文档按显示文本 select 必然落空：标题被拍平成正文、加粗段落匹配不上、图片题注够不到"
domain: "feishu"
tags:
  - "no"
  - "mcp"
  - "doc"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5065"
summary_plain: "某飞书文档 MCP 的 doc_update（select 匹配 + replace/insert/delete）在改结构化文档时大面积「No match found」或静默改坏：①replace…"
trigger: "Problem 某飞书文档 MCP 的 doc_update（select 匹配 + replace/insert/delete）在改结构化文档时大面积「No. 某飞书文档 MCP 的 doc_update（select 匹配 + replace/insert/delete）在改结构化文档时大面积「No match…"
verify: "同一篇 2 万字结构化长文完成 20+ 次块级改写（标题改号、条目整段重写、33 行表格整表迁移、样式段清词），全部成功且大纲层级/表格完整；拍平事故发生后用「带 ### 的 markdown 替换」修复并回读确认块类型恢复；引号+加粗组合的匹配失败经对照块原始 run 数据（加粗字段/直引号）定位后改用块 ID 删除法清掉。 20+…"
provenance:
  issue: "#5065"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

某飞书文档 MCP 的 doc_update（select 匹配 + replace/insert/delete）在改结构化文档时大面积「No match found」或静默改坏：①replace 一个标题块后标题被拍平成正文（大纲层级丢失）；②带加粗等样式的段落用纯文本 select 永远匹配不上；③同一段内 start...end 省略号跨度匹配失败，跨块跨度却成功；④含直引号 + 加粗组合的 select 静默不匹配；⑤图片题注里的文字 select 根本够不到。错误全是「No match found」或成功但变样，无任何提示指向根因。

## Root Cause

1. replace 语义 = 删块 + 按 markdown 重建块：块级类型（heading3/正文/列表）只存在于 markdown 语法标记里，替换 markdown 不带 `###` 等标记就把标题块降级成 text 块。
2. select 匹配的是块的 **markdown 序列化文本**而非纯文本：加粗 run 会序列化成 `**文本**`，select 必须按同样形态写；引号、破折号等字符形态（直/弯引号）必须与存储一致（存储为直引号）。
3. 省略号跨度要求起点对齐块首、终点对齐块尾，且单块内跨度不成立（需 ≥2 块）。
4. 图片题注是图片块的子元素，块级 select 不覆盖。

## Fix

- 动结构化块前先列块看真实形态（run 组成/样式字段/block_type），照抄 markdown 形态写 select：标题替换值带层级标记（`### …`）、样式段带 `**…**`、引号用直引号。
- 同段单块的改写用整块精确 select（带样式标记）；跨度 select 只用于 ≥2 块。
- select 匹配反复失败（尤其「引号+加粗」组合）时，改走底层块 API：用块 ID 删除目标块，再以邻近可匹配块为锚 insert-before/after。
- 每次 replace 后看 blocks_deleted/blocks_added 计数，改后整篇回读核对；标题块尤其要回读确认层级没被拍平。

## Verification

同一篇 2 万字结构化长文完成 20+ 次块级改写（标题改号、条目整段重写、33 行表格整表迁移、样式段清词），全部成功且大纲层级/表格完整；拍平事故发生后用「带 ### 的 markdown 替换」修复并回读确认块类型恢复；引号+加粗组合的匹配失败经对照块原始 run 数据（加粗字段/直引号）定位后改用块 ID 删除法清掉。

20+ 次块级改写全绿，整篇回读确认层级/表格/编号完整；块类型拍平修复后回读恢复 heading3。
