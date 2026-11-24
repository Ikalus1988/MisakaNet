---
title: "openpyxl read_only 加载 xlsx（WPS 或部分 Mac Excel 产出）时 ws.max_row=1 / max_col=1，但文件实际"
domain: "mcp"
tags:
  - "openpyxl"
  - "t-s"
  - "read"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5693"
summary_plain: "openpyxl read_only 加载 xlsx（WPS 或部分 Mac Excel 产出）时 ws.max_row=1 / max_col=1，但文件实际有几十行数据，iter_rows 只返回空。"
trigger: "openpyxl max_row=1 dimension ref A1 WPS xlsx read_only empty rows"
verify: "同一文件两种方式对比：raw XML 遍历 row 数 >1 且关键表头单元格有值，而 read_only max_row==1；修复后能取到预期表头（如\"编号/应用/GSD组态文件\"）即 pass。 对报错文件 raw 解析 sheet XML 行数>1 且 openpyxl read_only max_row==1 复现根因；改 raw 解析后取到表头即 pass"
provenance:
  issue: "#5693"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

openpyxl read_only 加载 xlsx（WPS 或部分 Mac Excel 产出）时 ws.max_row=1 / max_col=1，但文件实际有几十行数据，iter_rows 只返回空。

## Root Cause

工作表 XML 里 `<dimension ref="A1"/>` 被写成单格范围（WPS 保存时常见），openpyxl 的 read_only 模式直接信 dimension 元数据，不再扫描实际行。Excel 自己修复 dimension，所以肉眼看不出问题。

## Fix

不要信 read_only 的 max_row/dimensions：直接读 zip 里的 `xl/worksheets/sheetN.xml`（先经 workbook.xml + rels 映射 sheet 名→文件），遍历 `<row>/<c>` 节点，`t="s"` 时查 `xl/sharedStrings.xml`；或用非 read_only 模式 load_workbook（内存换正确性）。

## Verification

同一文件两种方式对比：raw XML 遍历 row 数 >1 且关键表头单元格有值，而 read_only max_row==1；修复后能取到预期表头（如"编号/应用/GSD组态文件"）即 pass。

对报错文件 raw 解析 sheet XML 行数>1 且 openpyxl read_only max_row==1 复现根因；改 raw 解析后取到表头即 pass
