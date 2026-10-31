---
title: "SimaticML LAD 块 XML 导入 TIA V16：UId 必须全块唯一、并联分支不支持、SCoil/RCoil 名称"
domain: "automation"
tags:
  - "tia"
  - "portal"
  - "simaticml"
  - "lad"
  - "scoil"
  - "rcoil"
  - "uid"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3573"
summary_plain: "手写 SimaticML LAD 块 XML 导入 OB1 反复失败：There are at least two definitions for UIds."
trigger: "SimaticML LAD 块 XML 导入 TIA V16：UId 必须全块唯一、并联分支不支持、SCoil/RCoil 名称. 手写 SimaticML LAD 块 XML 导入 OB1 反复失败：There are at least two definitions for UIds."
verify: "导入后查 MCP 日志出现 Successfully imported file，再 compile_plc(scope=software) 返回 0 错误，最后 export_program_blocks 能导出该块且网络与中文注释完整；get_plc_inventory 的 tags 非空。"
provenance:
  issue: "#3573"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

手写 SimaticML LAD 块 XML 导入 OB1 反复失败：There are at least two definitions for UIds. The incorrect unique ID is X；UId 为 N 的元素不存在、无效连接；导入工具仍返回 ok:true 但实际未导入。

## Root Cause

(1) FlgNet 的 UId 与块 ObjectList 的 ID 共用一个命名空间，必须整个块内唯一；多个网络都从 1 开始编号会撞车。(2) 一条 Wire 放多个 NameCon（三点连接）或手写并联分支结构（Openbranch/OpenCon）在 V16 不被接受，导入报无效连接。(3) 变量表 XML 必须带 ObjectList 注释结构且 ID 不与块内冲突，否则导入返回 ok 但 tags 为空。

## Fix

1) UId 统一用 100 以上且全块唯一（Parts 用 101..，Wires 用 201..；第二个网络从 121/221 起）。2) 避免并联：用 SCoil/RCoil（置位/复位）串联实现自锁与互锁，Part Name 分别是 SCoil、RCoil，Contact/Coil 不变；操作数用 <Access Scope="Address" UId="…"><Address Area="Input" Type="Bool" BitOffset="0"/></Access> 配合 <IdentCon UId="…"/>。3) 变量表用 <SW.Tags.PlcTagTable ID="0"> 下的 <SW.Tags.PlcTag ID="n">，含 DataTypeName/LogicalAddress/Name 并带 MultilingualText 注释。

## Verification

导入后查 MCP 日志出现 Successfully imported file，再 compile_plc(scope=software) 返回 0 错误，最后 export_program_blocks 能导出该块且网络与中文注释完整；get_plc_inventory 的 tags 非空。
