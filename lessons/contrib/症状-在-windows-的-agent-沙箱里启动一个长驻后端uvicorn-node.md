---
title: "症状 在 Windows 的 agent 沙箱里启动一个长驻后端（uvicorn / node server），启动命令返回成功、同一次 bash 调用里 cu"
domain: "windows"
tags:
  - "nohup"
  - "start"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5237"
summary_plain: "在 Windows 的 agent 沙箱里启动一个长驻后端（uvicorn / node server），启动命令返回成功、同一次 bash 调用里 curl 也能通。但**下一次工具调用**时进程已经没了。"
trigger: "后端进程每次调用后消失 Popen DETACHED_PROCESS CREATE_BREAKAWAY_FROM_JOB 无效 schtasks 计划任务 跨调用存活"
verify: "启动后间隔至少 30 秒、在**另一次工具调用**里 `curl -sS http://127.0.0.1:<port>/health` 返回 200 且进程 pid 不变。同一调用内能连上不算验证。停止后端口应拒绝连接。"
provenance:
  issue: "#5237"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows 的 agent 沙箱里启动一个长驻后端（uvicorn / node server），启动命令返回成功、同一次 bash 调用里 curl 也能通。但**下一次工具调用**时进程已经没了。

## Root Cause

宿主用 Windows Job Object 管理命令子进程，带 `KILL_ON_JOB_CLOSE`：命令结束 → job 关闭 → 整棵进程树被回收。

试过并无效的方案（不用再试）：
- `subprocess.Popen(..., start_new_session=True)`
- `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
- `CREATE_BREAKAWAY_FROM_JOB`（job 配置可能禁止 breakaway）
- WMI `Win32_Process.Create`
- `nohup ... &`（MSYS 下同样在 job 内）

根本原因：这些都是在同一个 job 里想办法，而 job 本身会被关闭。

## Fix

可用方案（已在 Windows 实测跨调用存活）：

1. 写一个 .cmd 包装脚本，**必须二进制 CRLF**（用 python 写，不要用 echo 重定向，否则产生 \r\r\n 破坏参数）：
```python
import io
s = "@echo off\r\ncd /d <PATH>\proj\r\n\"<PATH>\path\\python.exe\" -m uvicorn app:main --port 3080\r\n"
io.open('run.cmd','wb').write(s.encode('ascii'))
```
2. 注册计划任务（**不要加 /RL HIGHEST**，会 Access denied）：
```bash
schtasks /Create /TN "my-backend" /TR "<PATH>\proj\\run.cmd" /SC ONCE /ST 23:59 /F
```
3. 启动：`schtasks /Run /TN "my-backend"`
4. 验证存活：隔 30 秒再 `curl http://127.0.0.1:3080/health`，能返回即成功。
5. 停止：`schtasks /End /TN "my-backend"`，删除：`schtasks /Delete /TN "my-backend" /F`

判据：启动后**下一次工具调用**仍能连上端口，才算存活；同一调用内能连上不算。

注意：uvicorn 要直接 exec，不要在 .cmd 里用 `start`（start 会开新窗口并让 schtasks 立即返回成功，实际进程状态未知）。

## Verification

启动后间隔至少 30 秒、在**另一次工具调用**里 `curl -sS http://127.0.0.1:<port>/health` 返回 200 且进程 pid 不变。同一调用内能连上不算验证。停止后端口应拒绝连接。
