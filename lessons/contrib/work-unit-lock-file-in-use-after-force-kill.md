---
title: "强杀工作单元型仿真工具后重开报「文件被另一个进程使用」：无窗口僵尸实例 + 0 字节锁侧车"
domain: "windows"
tags:
  - "simulation-tooling"
  - "file-lock"
  - "zombie-process"
  - "taskkill"
status: "published"
evidence_level: "E1"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4947"
summary_plain: "强杀仿真/组态工具后重开报「工作单元正被其他进程使用」，真凶是无窗口的僵尸实例加一个 0 字节锁文件；清掉进程就自解。"
trigger: "重开工作单元报 file is in use by another process，桌面上却看不到任何相关窗口"
verify: "进程清零后重开立即成功且不再报占用；锁侧车消失或可删；对照清场前同一条重开命令稳定复现「被占用」。"
provenance:
  issue: "#4947"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

仿真/组态类工具（工作单元型应用）强杀进程（taskkill/Stop-Process -Force）后重开，报「工作单元正在被其他进程使用 / file is in use by another process」，但桌面上看不到任何相关窗口，任务栏也没有——操作者会误判为「幽灵占用/需要重启机器」。误导点：反复重开会**再生成更多隐形僵尸会话**（各自卡在同一模态框），互相加剧占用，现象越来越像「系统级锁死」。

## Root Cause

两层残留：①强杀宿主进程没走应用层清理，留下**0 字节锁侧车**（同名 .lck/.frx 之类）或注册表/ROT 占用标记；②历次失败的「重开」各自拉起新宿主实例，卡在「被占用」模态框上变成**无窗口的僵尸进程**——后续每次重开都被前一个僵尸挡住。锁侧车的时间戳通常对齐第一个僵尸的启动时刻。

## Fix

1. **先清进程再谈锁**：按镜像名扫全量进程表（不要只看窗口/任务栏）——僵尸实例可能无窗口；把本次操作者自己历次启动的实例全算上（每次失败的重开都是一个新占用者）；
2. 清光后锁侧车通常随宿主退出自解；仍在则删除 0 字节侧车（删除前确认宿主进程数=0）；
3. 预防：自动化脚本的「重启」步骤要先枚举+杀干净自己拉起的实例（带镜像名校验防 pid 复用误杀），再启动新的；失败重试要有上限，别无限重开制造僵尸。

## Verification

进程清零后重开立即成功（不再报占用）；锁侧车消失或可删；对照：清场前同样的重开命令稳定复现「被占用」。
