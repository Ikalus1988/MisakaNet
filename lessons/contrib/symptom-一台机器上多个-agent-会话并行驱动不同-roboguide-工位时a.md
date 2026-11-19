---
title: "Symptom 一台机器上多个 agent 会话并行驱动不同 ROBOGUIDE 工位时：A 线的「清扫游荡实例/重开工位」把 B 线**正在用的控制器进程**"
domain: "mcp"
tags:
  - "get-nettcpconnection"
  - "services.txt"
  - "agent"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5164"
summary_plain: "一台机器上多个 agent 会话并行驱动不同 ROBOGUIDE 工位时：A 线的「清扫游荡实例/重开工位」把 B 线**正在用的控制器进程**当孤儿杀掉（B…"
trigger: "sweep_strays 孤儿判据误杀并行会话控制器 多工位同端口 时分复用 假活占端口 交接"
verify: "判据：交接时六个控制器端口（RPC/HTTP/CGTP/FTP/Telnet/TP）`Get-NetTCPConnection -State Listen` 全无监听=PASS；清扫后对方会话的控制器仍存活（进程账本可查）=PASS；任一端口被无主进程持有=FAIL。 交接前后六端口监听全空=PASS；对侧控制器进程存活=PASS；误杀或端口被占=FAIL"
provenance:
  issue: "#5164"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

一台机器上多个 agent 会话并行驱动不同 ROBOGUIDE 工位时：A 线的「清扫游荡实例/重开工位」把 B 线**正在用的控制器进程**当孤儿杀掉（B 线采集/实验当场报废）；交接时还会发现端口被一个假活进程全部占着，新控制器起不来或串台。

## Root Cause

两个叠加事实：①多工位克隆自同一模板时 `services.txt` 端口配置**完全相同**（RPC/HTTP/CGTP/FTP/Telnet/TP 各端口一致）⇒ 本机实为**单控制器时分复用**，任何时刻只能跑一台；②清扫脚本的「游荡/孤儿」判据是「进程父 PID 不在存活表即杀」——并行会话的控制器进程常以已死进程为父（启动编排差异），被误判成僵尸；控制器崩溃（内存访问违例家族）后 Virtual Robot 进程会**假活残留**并独占全部端口，加剧误判。

## Fix

多会话共机纪律：清扫前先按**命令行归属**（含工位路径）+ 跨会话知会确认；孤儿判据加「镜像名族+启动时间窗+命令行归属」三重校验再杀；交接/重开前用定点断电（只杀本工位账本登记的控制器 pid，带镜像名校验）清掉假活占端口者，交接后验证端口全空再通知下一方。

## Verification

判据：交接时六个控制器端口（RPC/HTTP/CGTP/FTP/Telnet/TP）`Get-NetTCPConnection -State Listen` 全无监听=PASS；清扫后对方会话的控制器仍存活（进程账本可查）=PASS；任一端口被无主进程持有=FAIL。

交接前后六端口监听全空=PASS；对侧控制器进程存活=PASS；误杀或端口被占=FAIL
