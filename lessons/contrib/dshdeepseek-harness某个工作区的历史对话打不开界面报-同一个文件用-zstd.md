---
title: "DSH（DeepSeek Harness）某个工作区的历史对话打不开，界面报： 同一个文件用 zstd 解压完全正常（885 个帧、1647 行 JSON 全部"
domain: "dsh"
tags:
  - "undo_scan"
  - "seq"
  - "session.v4.jsonl.zstd.bak"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5160"
summary_plain: "DSH（DeepSeek Harness）某个工作区的历史对话打不开，界面报： ``` stored session \"session-2f614b77-…\" is corrupt: stored log is corrupt…"
trigger: "stored session is corrupt / invalid committed event at line / released v2 row has seq gap expected got / 历史加载失败 corrupt session log / session.v4.jsonl.zstd 打不开"
verify: "修复后：解码出的行数 = 1（头）+ 最大 seq + 1，逐行 `seq === i` 全部成立、无重号缺号；`undo_scan` 该会话报 ok；重新打开该对话时 DSH 能正常追加下一条事件（`session/end-seed`，seq = 原最大值+1），历史完整显示到最后一轮。"
provenance:
  issue: "#5160"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH（DeepSeek Harness）某个工作区的历史对话打不开，界面报：

```
stored session "session-2f614b77-…" is corrupt: stored log is corrupt:
Error: corrupt session log: invalid committed event at line 863:
released v2 row 862 has seq gap (expected 862, got 839)
(raw log: ~/.dsh/sessions/<workspace><PATH>)
```

同一个文件用 zstd 解压完全正常（885 个帧、1647 行 JSON 全部可解析），`undo_scan` 也判 ok——所以"文件损坏"是假象，坏的是事件序号连续性。

## Root Cause

DSH 把会话日志写成"多帧 zstd 拼接的 JSONL"，加载时要求第 i 条事件的 `seq === i`（严格单调、无缺号、无重号）。

本例实际时间线：turn 5 在 seq 838 结束 → 10:52 会话被重新打开，写入一段新开头并在 11 秒内结束 turn 6（seq 839–861）→ 12:05 又从 **seq 839** 重新起头，跑了真正的 turn 6（到 seq 1226），之后的 turn 7–10 一路写到 seq 1622。

也就是说 **seq 839–861 这 23 条被写了两次、内容不同**：第一次是 10:52 被取代的分支，第二次是 12:05 重跑后的版本。恢复/重开时没有先把上一段未提交的行截断，就沿用了同一个 seq 起点，于是日志里出现"同一个序号段出现两遍"，加载器在第 863 行读到 seq 839（期望 862）直接抛错。

## Fix

手动修复步骤（已验证）：
1) 备份原文件（`session.v4.jsonl.zstd.bak-<时间戳>`）。
2) 用 Node ≥22 的 `zlib.zstdDecompressSync` 逐帧解码：按 zstd 帧魔数 `28 B5 2F FD` 扫描偏移切分（DSH 写的是多帧拼接），每帧解码成文本，拼起来就是 JSONL。
3) 定位重复的 seq 段：按行序统计 `seq`，找出回退点（本例 seq 从 861 掉回 839），把重复的 23 行所在的那 5 个连续帧找出来（帧内必须全是重复行，边界才干净）。
4) 删掉"被后一次重跑取代"的那一份帧，其余帧**按原始字节原样拼接**（不要重新压缩，避免引入新差异），写回文件。
5) 校验不变量：第一行是 `{"type":"session","version":4,...}` 头；其后第 i 条事件必须满足 `seq === i`（0 起），无重号无缺号，最后一行应是 `turn/end`。
6) 收尾：`undo_scan` 应为 ok；重新打开该对话，DSH 会追加一条 `session/end-seed`（seq = 原最大 seq + 1），这说明加载器接受了修复后的日志。

## Verification

修复后：解码出的行数 = 1（头）+ 最大 seq + 1，逐行 `seq === i` 全部成立、无重号缺号；`undo_scan` 该会话报 ok；重新打开该对话时 DSH 能正常追加下一条事件（`session/end-seed`，seq = 原最大值+1），历史完整显示到最后一轮。
