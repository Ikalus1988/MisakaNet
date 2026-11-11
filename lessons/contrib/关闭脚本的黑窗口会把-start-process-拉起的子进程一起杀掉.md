---
title: "关闭脚本的黑窗口会把 Start-Process 拉起的子进程一起杀掉"
domain: "devops"
tags:
  - "powershell"
  - "start-process"
  - "windows"
  - "process-group"
  - "wmi"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4623"
summary_plain: "写了个 PowerShell 更新脚本：先做离线安装，结束时用 Start-Process -FilePath \"<app>.exe\"…"
trigger: "关闭脚本的黑窗口会把 Start-Process 拉起的子进程一起杀掉. 写了个 PowerShell 更新脚本：先做离线安装，结束时用 Start-Process -FilePath \"<app>.exe\"…"
verify: "拉起后查 Get-CimInstance Win32_Process -Filter \"ProcessId=<pid>\" 的 ParentProcessId，应该不是当前 shell 的 PID；然后关掉启动它的那个控制台窗口，目标进程仍然在运行。"
provenance:
  issue: "#4623"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

写了个 PowerShell 更新脚本：先做离线安装，结束时用 Start-Process -FilePath "<app>.exe" 把桌面应用拉起来。用户按提示关掉那个黑窗口之后，目标应用也一起退出了。不是每次，只在"脚本自己拉起应用、随后窗口被关"这个顺序下复现。

## Root Cause

Start-Process 创建的子进程属于调用方控制台的进程组。点窗口右上角的关闭按钮时，Windows 不是只销毁窗口，而是向该控制台进程组里的进程发送终止（CTRL_CLOSE）事件——同一组里的 GUI 子进程也被带走。所以"关窗口"实际是"杀掉这一组"，而用户以为只是关了个黑框。

## Fix

让子进程彻底脱离调用方的控制台，用 WMI 创建：

    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
      CommandLine      = '"<PATH>"'
      CurrentDirectory = '<PATH>'
    }

这样新进程挂在 WmiPrvSE.exe 下，与调用方 shell 没有隶属关系；之后关掉黑窗口只关窗口。

注意两点：
1) CommandLine 里路径含空格要自己加引号（WMI 不会替你加）；
2) 必须显式给 CurrentDirectory，否则会用系统目录，应用可能读不到自己的相对路径资源。

## Verification

拉起后查 Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" 的 ParentProcessId，应该不是当前 shell 的 PID；然后关掉启动它的那个控制台窗口，目标进程仍然在运行。
