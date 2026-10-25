---
title: "A confirmed injection exclusion is not the fix: three security layers need three separate proofs"
domain: "fanuc"
tags:
  - "roboguide"
  - "rgcore"
  - "endpoint-security"
  - "dll-injection"
  - "wfp"
  - "edr"
  - "acceptance-testing"
  - "virtual-controller"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "给 DLP 做了目录级注入排除、目标进程模块表也干净了，崩溃却在同一偏移原样复现；验收要按用户态/内核/EDR 三层分别取证。"
trigger: "CGEHDll.dll 已从 frrobot.exe 模块表消失但仍崩在 frsock!connect + 0x96 / SEC -004 FSAC SNPX deny connect / 0x2745 WSAECONNABORTED"
verify: "同一工作单元静置 + 激活示教器复测：模块表无挂钩 DLL、logfile 无 Memory access violation / OS -145、无 SEC -004 deny 127.0.0.1、0x2745/0x2746 与 PMON Connected to TP 计数不增长。"
source: "intake-3325"
provenance:
  issue: "#3325"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A confirmed injection exclusion is not the fix: three security layers need three separate proofs

## Problem

ROBOGUIDE 虚拟控制器崩溃，已定位为三层终端安全软件组合冲突（用户态 DLP Detours 注入 + EDR AMSI + 内核 WFP 过滤）。按申请对 FANUC 目录下发 DLP 进程钩子注入排除后，进程模块表确认 `CGEHDll.dll` 已从 `frrobot.exe` / `FRRobotNeighborhood.exe` 的模块表中消失；对照组 58 个其它进程仍在被注入——说明排除只针对 FANUC、确实是「排除」而不是「整体关闭」。

但功能复测**仍崩溃**，且崩溃点偏移与排除前完全一致：

```
frsock!connect + 0x96   Memory access violation
frsock!recv + 0x185B
SEC -004 FSAC SNPX deny connect 1.0.0.127
0x2745 WSAECONNABORTED
PMON 重连风暴依旧
OS -145 Power off controller to reset
```

`OS -145` 仍需断电复位。排除「已生效」与故障「仍复现」同时成立——这正是本条要留存的读数。

## Root Cause

**目录级注入排除只摘掉了三层里的第一层**，另外两层的作用面没有被改动：

| 层 | 机制 | 目录级注入排除会改变它吗 | 本例实测 |
|---|---|---|---|
| 用户态 | DLP Detours 挂钩（`networkSend` 等） | 会（目标进程不再被注入） | 已消失：目标模块表 CLEAN，对照组仍被注入 |
| 内核态 | WFP 过滤驱动拦截回环连接 | 不会 | 仍在：`SEC -004 FSAC SNPX deny connect 127.0.0.1`、`0x2745` |
| 内核/行为 | EDR AMSI Provider 行为监控 | 不会（需单独下发 AMSI/行为排除） | 报料者未给出该层排除状态，需复现确认 |

`frsock.dll` 的 `connect()` 活在第二、三层的作用面上：只要 WFP 还在复位 `127.0.0.1:50005` 的回环连接，崩溃偏移就不会变。所以「模块表干净 + 崩溃照旧」不是矛盾，而是**还差两层**的正常读数。

另一半是沟通口径：「IT 已禁用 DLP 防泄漏软件」这句实测常被实现成「只给目标目录做注入排除」——软件本体与服务仍在运行，对其它进程的注入照旧（本例 58 个进程仍被注入）。这是预期行为，不要据此判断 IT 没执行。

## Solution

验收必须**三层分别取证，缺一不可**：

1. **用户态注入**——查目标进程模块表里还有没有挂钩 DLL（唯一可信判据；不要看安全软件的配置文件时间戳或内容）：

```powershell
Get-Process frrobot,FRRobotNeighborhood,RGCore | ForEach-Object {
  $_.Modules | Where-Object {
    $_.FileName -notmatch '^C:\WINDOWS\' -and $_.FileName -notmatch '<FANUC 安装目录>'
  } | Select-Object ModuleName,FileName
}
```

2. **内核回环**——查崩溃日志里 `SEC -004 FSAC SNPX deny connect 127.0.0.1` 是否消失，`0x2745` / `0x2746` 计数是否停止增长。
3. **EDR 行为监控**——确认 EDR / 杀软对目标进程的 AMSI / 行为监控排除是否真的下发（这一层的配置项与前两层不同，做了目录排除不等于做了行为排除）。

三层全部取证通过才算根治。任一层仍是旧读数，验收结论就写成「已排除 N/3 层」，不要写成「已修复」——本例的教训正是 1/3 被读成了 3/3。

## Verification

在同一工作单元上做静置 + 激活示教器复测，同时满足：

- 进程模块表无注入挂钩 DLL；
- `logfile.txt` 无 `Memory access violation` / `OS -144` / `OS -145`；
- 无 `SEC -004 FSAC SNPX deny connect 127.0.0.1`；
- `0x2745` / `0x2746` 与 `PMON Connected to TP` 计数不增长。

任一项不满足即未根治。本例在模块表已 CLEAN 的前提下，后三项仍全部亮红——这就是「只排除 1/3 层」的实测形态。

报料者未给出第三层（EDR AMSI / 行为监控）的排除取证结果，需复现确认。
