---
title: "FANUC maketp 批量编译三坑：落盘名必须跟 /PROG 行、并发互撞 COM 单连接、robot.ini 三种字段形态"
domain: "fanuc"
tags:
  - "fanuc"
  - "maketp"
  - "winolpc"
  - "batch-compile"
  - "robot-ini"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4295"
summary_plain: "批量跑 FANUC 的 LS→TP 编译器：文件名不跟 /PROG 行全军覆没，并发跑互撞 COM 连接，robot.ini 路径形态写错报 Path not found。"
trigger: "maketp Invalid name in /PROG section 0x80040017 Robot Object is connecting Path not found robot.ini"
verify: "40 条真实 .ls：按 /PROG 名落盘全数过名字检查；同 LS 同 ini 两次编译字节全等；正确 ini 下 1-2s 编译出 TP"
provenance:
  issue: "#4295"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

FANUC maketp（WinOLPC LS→TP 编译器）批量编译踩了四个坑（三个硬错 + 一个静默错版）：

1. **落盘文件名**：输入文件名（去扩展名）必须与文件内 `/PROG` 行程序名一致（大小写不敏感）。
   改名/流水线落盘成序号名 → **全军覆没**报
   `Error occurred during load ... Invalid name in /PROG section`，且报错行列号随名字长度漂移，
   误导排查方向。Macro 程序的 `/PROG` 行带「Macro」标记，取名取首词即可；
2. **并发互撞**：并发跑两个 maketp 互撞 COM 机器人对象**单连接**，报
   `0x80040017 "Robot Object is connecting. Please wait for the Connect event"`（后到者等
   Connect 事件约 120s 后失败）；
3. **robot.ini 路径形态**：`Support=`/`Output=` 必须**普通盘符形态**；`Robot=` 用「盘符无冒号
   前置反斜杠」形态（`\C\...`）。Support/Output 误写成 `\C\` 形态报
   `Error executing MakeTP: Path not found`；
4. **静默错版**：`Version=` 写成非 setrobot 点形态（如 `V94.0-1` 而非 `V9.40-1`）**不报错**，
   但会写错 TP 头 0x42-0x43 的版本配置戳。

## Root Cause

maketp 是围绕单个机器人对象（COM 单连接）设计的批处理工具：它把**文件名当程序名的断言**、
按 robot.ini 的**各字段各自的路径语法**解析、按 `Version=` 的 setrobot 点形态写版本戳。
批量流水线按通用习惯（序号落盘、并发提速、统一路径形态、随意版本串）接入，与这三个假设
逐项相撞；版本戳那条连错都不报，是最坏形态。

## Solution

1. **落盘按 `/PROG` 取名**：`^/PROG\s+(\S+)` 取首词（容忍 Macro 标记；大小写不敏感已实测）；
2. maketp 调用加**进程级互斥锁串行化**（并发只会互撞，不会提速）；
3. robot.ini 生成：`Robot=` 用盘符无冒号前置反斜杠形态（`\C\...`）、`Support=`/`Output=` 用
   普通形态（`C:\...`）、`Version=` 用 setrobot 点形态（目录名 `V940-1` → `V9.40-1`，
   版本体末 2 位是小版本）。

## Verification

40 条真实 `.ls` 横扫：改名落盘 40/40 报 Invalid name；按 `/PROG` 名落盘后全数通过名字检查
（Macro 程序编译成功产出 502B TP）；同 LS 同 ini **两次编译字节全等**（幂等 ✓）；PowerShell
直调 maketp 用正确 ini 于 **1-2s** 内编译成功产出 TP（对照：坏 ini/并发/坏名均机械复现
对应报错）。

## Dedupe note

先搜后写：`misakanet_search("maketp WinOLPC LS to TP batch compile filename PROG name COM single connection")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4295，是该主题的第一条。

## Notes

工具链接入三问：**文件名有没有语义？它是单实例还是可并发？配置文件各字段是不是同一套路径
语法？**——maketp 三个都是"暗契约"，文档不写、报错还指错方向。静默错版（第 4 坑）提醒：
版本类元数据要按**字节/头字段**核对，不能只看命令成功。
