---
title: "用 WMI 脱离父子关系的守卫进程，仍会随宿主退出被杀：别指望\"等宿主死了再干活"
domain: "devops"
tags:
  - "windows"
  - "wmi"
  - "job-object"
  - "process-lifecycle"
  - "powershell"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4551"
summary_plain: "要给一个运行中的 Electron 宿主（它会锁住 node_modules 里的原生模块）做离线安装，思路是：起一个守卫进程，等宿主完全退出后自动跑安装、装完再把宿主拉起来。守卫用 WMI `Win32_Process.Create`…"
trigger: "用 WMI 脱离父子关系的守卫进程，仍会随宿主退出被杀：别指望\"等宿主死了再干活. 要给一个运行中的 Electron 宿主（它会锁住 node_modules…"
verify: "在宿主退出后 check：安装日志里出现了本该由它写的下一条记录；进程在宿主退出后仍然存活（任务管理器能看到）；最终 node_modules 里目标包版本正确。"
provenance:
  issue: "#4551"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

要给一个运行中的 Electron 宿主（它会锁住 node_modules 里的原生模块）做离线安装，思路是：起一个守卫进程，等宿主完全退出后自动跑安装、装完再把宿主拉起来。守卫用 WMI `Win32_Process.Create` 创建（不是调用方的子进程），进程确实起来了、也写日志了、也检测到宿主退出并记了一行「DSH 进程已清空（等了 40 秒）」。**紧接着就没了**——下一条日志（"开始 pnpm install"）再也没出现，进程列表里也查不到它。

## Root Cause

WMI 创建只解决了"父子关系"，没解决"任务归属"。Windows 的 Job Object 是按 Job 记账的，宿主（或它的宿主链）在启动时把派生进程放进同一个 Job，最后一个进程退出时 Job 关闭，属主设置了 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 就会把 Job 里剩下的进程一起杀掉。守卫进程在 Job 里、又不是宿主的父子，所以"宿主退出"这个事件既等于它被唤起的时机，也等于它的死期——两件事撞在同一毫秒。前端表现就是"日志停在宿主退出那一行，之后什么都没有"。

## Fix

不要用"等宿主退出"作为离线任务的触发条件。可用的替代（按可靠度排）：① 用一个真正独立的宿主来跑——计划任务/服务/另一个已登录会话的 shell，它不属于宿主的 Job；② 反过来做：先让宿主退出，再由人（或另一个已存在的入口）启动安装；③ 若只是想改依赖树，改用不触发 rename 的路线（新增目录而非替换，例如零依赖包直接解 tarball 到 node_modules，再用 `pnpm install --lockfile-only` 只同步账本），这样根本不需要宿主退出。

## Verification

在宿主退出后 check：安装日志里出现了本该由它写的下一条记录；进程在宿主退出后仍然存活（任务管理器能看到）；最终 node_modules 里目标包版本正确。
