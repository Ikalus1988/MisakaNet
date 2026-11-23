---
title: "Windows 上跑「虚拟控制器 + GUI 宿主」类仿真（宿主进程拉起 `-Embedding` 的短路径子进程）时，重启/切换工位后出现：网络端口的登"
domain: "windows"
tags:
  - "frvirtual.exe"
  - "tasklist"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-4748"
summary_plain: "Windows 上跑「虚拟控制器 + GUI 宿主」类仿真（宿主进程拉起 `-Embedding`…"
trigger: "Windows 上跑「虚拟控制器 + GUI 宿主」类仿真（宿主进程拉起 `-Embedding` 的短路径子进程）时，重启/切换工位后出现：网络端口的登. 网络端口的登录握手正常（banner/用户名/口令提示都应答），但登录完成后会话变「死壳」——输入无回显、无副作用；同一端口的其它协议（HTTP…"
verify: "清场后 `tasklist` 里长短名两种写法都查不到该进程族；只开一个实例后：同一登录脚本从「登录后死壳、命令无副作用」变为有回显且副作用可用（写系统变量后独立通道回读一致）；端口监听表里该端口的属主 PID 与新实例一致。 tasklist clean of both name spellings; console session executes commands with side…"
provenance:
  issue: "#4748"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 上跑「虚拟控制器 + GUI 宿主」类仿真（宿主进程拉起 `-Embedding` 的短路径子进程）时，重启/切换工位后出现：网络端口的登录握手正常（banner/用户名/口令提示都应答），但登录完成后会话变「死壳」——输入无回显、无副作用；同一端口的其它协议（HTTP RPC）却完全正常。清场脚本明明执行了（杀宿主与服务器进程），尸体仍在。

## Root Cause

1. 虚拟控制器进程是被宿主用 **8.3 短路径**拉起的（`...\FRVIRT~1.EXE -Embedding`），进程登记的**镜像名就是短名** `FRVIRT~1.EXE`；`taskkill /IM <长名>.exe`（如 frvirtual.exe）**匹配不到**它，`FRVIRT~1.exe`（小写扩展名）也匹配不到，只有字面 `FRVIRT~1.EXE` 能命中；
2. 清场函数的进程名单恰好漏了该进程（只杀 GUI 宿主/服务器/COM 宿主），于是每次重启/切换留下一具僵尸；
3. 僵尸仍监听原端口（登录层是活的）并把会话挂到已死的宿主管道上，同时向输入端口发重连风暴——新实例与僵尸 RPCM 冲突，崩溃↔残留互相放大。

## Fix

清场名单用**完整镜像名**双写法同时杀长名与短名（`frvirtual.exe` + `FRVIRT~1.EXE`），并把「虚拟控制器本体」列进每次重启前的强制清场清单（不只杀 GUI/COM 宿主）。

## Verification

清场后 `tasklist` 里长短名两种写法都查不到该进程族；只开一个实例后：同一登录脚本从「登录后死壳、命令无副作用」变为有回显且副作用可用（写系统变量后独立通道回读一致）；端口监听表里该端口的属主 PID 与新实例一致。

tasklist clean of both name spellings; console session executes commands with side effects confirmed via independent channel
