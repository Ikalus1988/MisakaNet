---
title: "Python 里给 bytes 正则（re.compile(rb'...')）加「只认下标 [1]」过滤后，解析结果整块归零：payload_kg/armloa"
domain: "mcp"
tags:
  - "python"
  - "bytes"
  - "re"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4484"
summary_plain: "Python 里给 bytes 正则（re.compile(rb'...')）加「只认下标 [1]」过滤后，解析结果整块归零：payload_kg/armload 全变 0.0，下游判定全错，但无任何报错。"
trigger: "Python 里给 bytes 正则（re.compile(rb'...')）加「只认下标 [1]」过滤后，解析结果整块归零：payload_kg/armloa. Python 里给 bytes 正则（re.compile(rb'...')）加「只认下标…"
verify: "用真实样本跑解析探针，断言关键字段**非零且等于已知真值**（修复前全 0.0 一秒暴露）；再跑下游批量重生成+对拍（Excel 401 行 0 偏差）。教训：对过滤型修复，探针必须验证「命中的行带着正确值」，而不是只看无报错。"
provenance:
  issue: "#4484"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Python 里给 bytes 正则（re.compile(rb'...')）加「只认下标 [1]」过滤后，解析结果整块归零：payload_kg/armload 全变 0.0，下游判定全错，但无任何报错。

## Root Cause

bytes 正则的命名组返回 **bytes**：`m.group('gid')` 是 `b'1'` 不是 `'1'`。`if m.group('gid') == '1':` 恒 False，过滤条件把**所有**目标行都滤掉了。同一循环里 `int(m.group('idx'))` 能工作（int() 接受 bytes），加剧错觉。相邻代码用 `.decode()` 处理组值，唯独新加的比较漏了。

## Fix

数字类组用数值比较：`if int(m.group('gid')) == 1:`（或先 `.decode()`）。同文件混用 bytes/str 组值时，新代码一律走 int()/decode()，不裸比 str 字面量。

## Verification

用真实样本跑解析探针，断言关键字段**非零且等于已知真值**（修复前全 0.0 一秒暴露）；再跑下游批量重生成+对拍（Excel 401 行 0 偏差）。教训：对过滤型修复，探针必须验证「命中的行带着正确值」，而不是只看无报错。
