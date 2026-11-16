---
title: "Problem 自动化脚本在「虚拟控制器引导完成」后立刻发起 HTTP/RPC 读写，全部连接被拒（WinError 10061），实验整段报废；引导判据用的是"
domain: "mcp"
tags:
  - "http"
  - "rpc"
  - "winerror"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4724"
summary_plain: "自动化脚本在「虚拟控制器引导完成」后立刻发起 HTTP/RPC 读写，全部连接被拒（WinError 10061），实验整段报废；引导判据用的是「services.txt 文件被重写」。"
trigger: "Problem 自动化脚本在「虚拟控制器引导完成」后立刻发起 HTTP/RPC 读写，全部连接被拒（WinError 10061），实验整段报废；引导判据用的是. 自动化脚本在「虚拟控制器引导完成」后立刻发起 HTTP/RPC 读写，全部连接被拒（WinError…"
verify: "受控重跑实测：services.txt 重写后 HTTP 实测就绪耗时 0s 与 55s 两例（差异巨大，正说明文件判据不可靠）；改用 HTTP 应答判据后，样本抓取/变量读写零拒连。 （相关但不同：对控制器端口做 TCP 探测会弄崩控制器——那是诊断纪律，本条是就绪判据。）"
provenance:
  issue: "#4724"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

自动化脚本在「虚拟控制器引导完成」后立刻发起 HTTP/RPC 读写，全部连接被拒（WinError 10061），实验整段报废；引导判据用的是「services.txt 文件被重写」。

## Root Cause

services.txt 在引导**早期**就被重写（控制器身份/端口表落盘），而 web/RPC 等网络模块在其后才装载绑定端口。把「文件重写」当「服务就绪」信号会稳定抢跑 0~55 秒窗口——期间端口无人监听或半就绪，客户端全部拒连；且脚本往往把拒连误判为「控制器已死」，进入错误分支。

## Fix

就绪判据分两级：
1. 「引导已开始」= services.txt 重写（保留，但只做前置信号）；
2. 「引导已就绪」= **实际网络应答**：轮询 GET <PATH>（或任意已知免登录端点 / RPC ping）直到 2xx/合法 JSON，间隔 3 秒、超时 240~300 秒；超时才报失败。
写实验脚本时把 I/O 前置一个 wait_ready()，拒连别当控制器死亡。

## Verification

受控重跑实测：services.txt 重写后 HTTP 实测就绪耗时 0s 与 55s 两例（差异巨大，正说明文件判据不可靠）；改用 HTTP 应答判据后，样本抓取/变量读写零拒连。
（相关但不同：对控制器端口做 TCP 探测会弄崩控制器——那是诊断纪律，本条是就绪判据。）
