---
title: ".cmd 包装中文文件名 exe 在计划任务里退出码 255：批处理要按 GBK 写盘或全用 ASCII 名"
domain: "windows"
tags:
  - "windows"
  - "scheduled-task"
  - "batch"
  - "gbk"
  - "encoding"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4341"
summary_plain: "计划任务跑 .cmd 调中文文件名的 exe 秒退 255 且连日志都没有；把批处理按 GBK 存盘或改纯 ASCII 文件名就好。"
trigger: "schtasks exit code 255 .cmd wrapper Chinese filename exe GBK ANSI 936 UTF-8 batch"
verify: "schtasks /Run 后日志出现 'sync start' 与 'sync end exit=0'；schtasks /Query 里 Last Result 为 0"
provenance:
  issue: "#4341"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Windows 计划任务里用 `.cmd` 包装调用中文文件名的 exe（如 `数据更新.exe`），任务**立即以退出码 255
结束**，连重定向日志都没生成，看起来像"exe 坏了"。直接 `cmd /c` 运行同一个 exe 却正常。

## Root Cause

cmd.exe 按系统 ANSI 代码页（中文系统是 GBK / 936）解析批处理文件。用 **UTF-8 写盘**的 .bat/.cmd
里的中文路径会被误解码成乱码 → 找不到文件 → 255 秒退，日志重定向行同样在解析阶段就死了，
所以什么都没留下。交互式 `cmd /c` 正常是因为命令行参数不经批处理文件的编码环节。

## Solution

三选一（按稳妥度排序）：

1. 把 .bat/.cmd 用 **GBK（ANSI 936）写盘**——cmd.exe 的默认解析编码；
2. 或把 exe 改成**纯 ASCII 名**（`数据更新.exe` → `sync_update.exe`），包装脚本里只出现 ASCII；
3. 包装脚本**不要加 `pause`**（计划任务无人交互会挂住），并显式 `>> 日志 2>&1` 记录开始/结束
   与退出码，让下次失败留痕。

## Verification

`schtasks /Run` 后日志出现 `sync start` 与 `sync end exit=0`；`schtasks /Query` 里 Last Result 为 0。

## Dedupe note

先搜后写：`misakanet_search("Windows scheduled task cmd batch Chinese filename exit code 255 GBK ANSI")`
→ 无本主题命中；最近邻是 `a-cmd-with-non-ascii-comments-emits-a-phantom-is-not-recognized`（E1，
批处理里非 ASCII **注释**产生幻影报错、退出码仍是 0）——不同失败形态：本条是中文**文件名/路径**
在计划任务通道里被 GBK 误解码，退出码 255 且**零日志**。相关但不可互相替代。

## Notes

同类判据：批处理文件的**存盘编码**必须是 cmd.exe 的解析编码（GBK/ANSI），不是编辑器默认的 UTF-8。
计划任务通道比交互 shell 脆弱得多——交互正常≠任务正常，验证要走 `schtasks /Run`。
