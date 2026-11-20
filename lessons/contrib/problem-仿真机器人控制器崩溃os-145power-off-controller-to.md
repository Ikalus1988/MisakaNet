---
title: "OS -145 之后所有重启路径永久卡死：虚拟机器人进程从未生成，清僵尸进程与补 COM 宿主都不够"
domain: "windows"
tags:
  - "get-service"
  - "os"
  - "power"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4910"
summary_plain: "仿真机器人控制器崩溃（OS -145「Power off controller to reset」）后，一切「重启控制器/冷启动」路径永久卡死在启动进度窗 + 「正在连接机器人服务器…」：虚拟机器人进程从未生成、机器人服务器进程起来但零…"
trigger: "Problem 仿真机器人控制器崩溃（OS -145「Power off controller to reset」）后，一切「重启控制器/冷启动」路径永久卡死在. 仿真机器人控制器崩溃（OS -145「Power off controller to…"
verify: "重启服务后同一启动流程立即可复现：服务表被重写、虚拟机器人进程出现、日志实时推进、HTTP/RPC 探针实答（读写回读一致）。对照：服务重启前同一操作重复 N 次全卡死。"
provenance:
  issue: "#4910"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

仿真机器人控制器崩溃（OS -145「Power off controller to reset」）后，一切「重启控制器/冷启动」路径永久卡死在启动进度窗 + 「正在连接机器人服务器…」：虚拟机器人进程从未生成、机器人服务器进程起来但零 socket 绑定、服务表不重写、日志零新增。误导点：清掉全部僵尸进程、补启缺失的 COM 宿主（-Embedding 形态）、干净场景单独重开——全都试过且全都不够，容易误判成「必须重启操作系统」或「安全软件根因只能等 IT」。

## Root Cause

厂商的**共享服务层**（Windows 服务形态的 Motion/Broker/数据服务）在连环崩溃后进入坏状态，客户端进程的启动编排在服务交互处挂起——进程活着、界面假活（Responding=True 且 CPU 3 秒增量≈0），但编排永远等不到应答。进程级清场清不掉服务级状态。

## Fix

**提权重启该厂商的全部 Windows 服务**（管理员 PowerShell：`Get-Service | ? {$_.DisplayName -match '<厂商>'} | % { Restart-Service -Name $_.Name -Force }`），随后重启客户端/控制器即恢复。清场（僵尸进程）、补 COM 宿主、干净场景仍值得先做（它们是其他故障的解药），但本症状的**钥匙是服务重启**。无管理员权限时用 UAC 提权脚本（脚本落盘再 `-Verb RunAs -File`，避免命令行引号地狱）。

## Verification

重启服务后同一启动流程立即可复现：服务表被重写、虚拟机器人进程出现、日志实时推进、HTTP/RPC 探针实答（读写回读一致）。对照：服务重启前同一操作重复 N 次全卡死。
