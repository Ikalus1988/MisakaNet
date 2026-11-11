---
title: "FANUC DCS .dg 固定宽度解析：校准脚本报状态列非 OK=0，真语料却有数千 CHGD"
domain: "fanuc"
tags:
  - "symptom"
  - "fanuc"
  - "dcs"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4683"
summary_plain: "FANUC DCS .dg 固定宽度解析：校准脚本报状态列非 OK=0，真语料却有数千 CHGD"
trigger: "FANUC DCS .dg 固定宽度解析：校准脚本报状态列非 OK=0，真语料却有数千 CHGD"
verify: "- 单测：粘连行 ` CSO[ 20]= CPC[ 11] ---[ 0]CHGD` 解析出 `status=\"CHGD\"`、`terms=[CPC[11]]` - 单测：正常行 ` SSO[ 1]= CSI[ 3] OR SSI[ 11] OK ` 解析出 `status=\"OK\"`、归一化 `CSI[3] OR SSI[11]` - 全语料横扫（7934 个 .dg）：基准侧 ≠OK…"
provenance:
  issue: "#4683"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

解析工业固定宽度文本（FANUC DCS .dg 安全链表）时，校准脚本报「状态列非 OK = 0」，但真语料里其实有数千行 CHGD。期望值与实测严重不符，且两边都「看起来合理」。

## Root Cause

状态列在行尾有两种形态，空白分词（split on whitespace）只吃下一种：
- 正常：`  ---[  0]=  ---[  0]      ---[  0] OK `（状态词前有空格 → 末 [REDACTED:credential]
- 粘连：`  CSO[ 20]=  CPC[ 11]      ---[  0]CHGD`（状态词无空格贴着 `]` → 末 [REDACTED:credential] 或 `CHGD` 被并进占位 token）

按空白分词时，粘连形态的状态词被吞进前一个 token（`]CHGD` ≠ `CHGD`，或被当成 `---[0]CHGD` 整体丢弃），于是非-OK 计数恒为 0——假阴性看起来像「全绿」。

同文件括号内还有对齐空格（`SSI[ 11]`），空白分词会把 `11]` 拆碎，这是第二个信号：这类行根本不该用空白分词。

## Fix

放弃空白分词，用**词法正则整行扫描**：
1. 先用锚定正则取左值 `^\s*([A-Za-z-]+)\[\s*(\d+)\s*\]\s*=\s*`
2. 右式用 `^(!\s*)?([A-Za-z-]+)\[\s*(\d+)\s*\]` 循环吃项（括号内空白在 `\s*` 里吸收）
3. 操作符 `OR|AND` 单独匹配
4. **剩余整段 trim 即状态词**——粘连形态下剩余是 `CHGD`，正常形态下剩余是 `OK`

关键：状态词不要试图「找词」，而是**消费完结构后的残余**。这样 `]CHGD` 里 `]` 已被结构正则吃掉，残余自然是 `CHGD`。

## Verification

- 单测：粘连行 `  CSO[ 20]=  CPC[ 11]      ---[  0]CHGD` 解析出 `status="CHGD"`、`terms=[CPC[11]]`
- 单测：正常行 `  SSO[  1]=  CSI[  3] OR   SSI[ 11] OK ` 解析出 `status="OK"`、归一化 `CSI[3] OR SSI[11]`
- 全语料横扫（7934 个 .dg）：基准侧 ≠OK 计数从「假 0」修正为真 0（基准确实干净）；变更视图 CHGD 8382 行被正确捕获并分类
- 对比：同一语料用空白分词的校准脚本输出非-OK=0，词法正则输出 8382，差值全部是粘连形态

粘连行/正常行单测 + 全语料横扫 8382 行 CHGD 正确捕获
