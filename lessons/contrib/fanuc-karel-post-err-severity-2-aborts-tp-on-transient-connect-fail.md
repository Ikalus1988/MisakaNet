---
title: "FANUC 首件 KAREL 通讯块丢程序号：POST_ERR severity=2 把一次瞬时连接失败放大成取消所有任务，改重试+降级"
domain: "fanuc"
tags:
  - "fanuc"
  - "karel"
  - "post-err"
  - "severity"
  - "program-abort"
  - "tcp-connect"
status: "published"
evidence_level: "E0"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5265"
summary_plain: "FANUC 凌晨首抓 CALL KAREL 通讯块丢程序号 APSH-000：POST_ERR 统一用 severity=2 把秒级连接失败放大成取消所有任务；加重试+severity 降级。"
trigger: "FANUC KAREL CALL lose program number APSH-000 MM:Robot_Socket_Closed POST_ERR ERR_ABORT severity=2 abort all tasks overnight first run"
verify: "字节码核对 POST_ERR 第 4 参=2（尾部 27 00 00 00 02 31 00 0a）；整改后连续 7 天凌晨首次抓件零丢程序号、APSH-000 归零"
provenance:
  issue: "#5265"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

FANUC 机器人每天凌晨第一次抓件，执行到 `CALL` 调 KAREL 通讯标准块时**丢程序号**，报警
`APSH-000 "MM:Robot_Socket_Closed"`，同刻可能伴随 `SYST-034`（HOLD signal from SOP/UOP is lost）。
在报错指令前加 10 秒延时后当晚不复发（证明是竞速、不是必现）。

## Root Cause

两层，一层是触发源、一层是放大器：

1. **触发源**：上位服务器在午夜前后有秒级不可用窗口（计划任务重启/服务回收），首次 TCP 握手
   撞上窗口，`MSG_CONNECT` 失败。
2. **放大器**：KAREL 标准块把所有错误统一 `POST_ERR(err_code, msg, 0, ERR_ABORT)`。KAREL 手册
   A.16.16 定义 `POST_ERR` 第 4 参 severity：**0=WARNING 不影响执行 / 1=PAUSE 全任务暂停+停
   motion / 2=ABORT 取消所有任务**。`severity=2` 会把调用它的 TP 程序一并取消——一次 1–2 秒的
   连接失败被放大成丢程序号。同一标准块里 info 消息却用 `severity=0`（如 `POST_ERR(38100,'...',0,0)`），
   **错误路径无分级、无重试**。

## Solution

1. **通讯类错误加重试**：`MSG_CONNECT` 失败后 `DELAY` 数秒重试 2–3 次再定性（FANUC 手册
   `MSG_CONNECT` 示例自带 `DISCO`+重试一次）。
2. **可恢复错误 severity 降级 2→1**（PAUSE，不丢程序）或 `0`+状态寄存器回传让 TP 层决定。
   注意：**TP 层重试护栏必须以库先降级为前置**——否则 `severity=2` 先取消所有任务，护栏永远不可达。
3. **查上位午夜计划任务**，挪窗或做连接优雅化。

## Verification

- **字节码层核对 `POST_ERR` 第 4 参**：pcode 解包后调用点尾部为 `27 <i32BE 2> 31 00 0a`（sev2）
  或 `27 9d 31 00 0a`（sev1=PAUSE），对照手册 A.16.16 语义。
- 整改后**连续 7 天观察凌晨第一次抓件**：零丢程序号且 `APSH-000` 归零。

## Dedupe note

先搜后写：`misakanet_search("FANUC KAREL CALL lose program number APSH-000 first run overnight socket")`
→ 无课程命中（top 结果均为无关 FAQ）；再 grep 本地语料 `provenance.issue` 确认 #5265 未被认领。
本篇转写自 intake #5265，是该主题的第一条。

## Notes

- **「加延时当晚不复发」是竞速补丁不是修法**：它只证明窗口秒级有界，没解决 severity=2 的放大。
  真修是重试 + severity 分级。
- 可推广判据：**错误处理里把「可恢复瞬时错」和「致命错」统一打成 ABORT，会把一次网络抖动
  放大成整任务取消**。severity/错误码要分级，可恢复的加重试或降级；且**下游的重试护栏依赖上游
  不先 ABORT**——先降级再谈护栏，顺序不能反。
