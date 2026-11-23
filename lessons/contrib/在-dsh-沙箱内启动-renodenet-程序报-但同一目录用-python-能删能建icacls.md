---
title: "在 DSH 沙箱内启动 Renode（.NET 程序），报： 但同一目录用 Python 能删能建，`icacls` 显示当前用户有完全控制权 (F)、无"
domain: "windows"
tags:
  - "icacls"
  - "cmd"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5234"
summary_plain: "在 DSH 沙箱内启动 Renode（.NET 程序），报： ``` System.UnauthorizedAccessException: Access to the path…"
trigger: "Access denied 但 ACL 正常 独占打开 share=0 沙箱拦截 非权限问题 判别步骤"
verify: "判别流程可复现： 1. `icacls <dir>` 显示当前用户 (F)、无 (DENY) → 权限不是原因。 2. Python 调 `CreateFileW(path, GENERIC_RW, share=0, None, OPEN_ALWAYS, 0, None)` 返回有效句柄 → 文件系统允许独占打开。 3. 最小命令对照：只 `mach create \"x\"; quit` 返回…"
provenance:
  issue: "#5234"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH 沙箱内启动 Renode（.NET 程序），报：

```
System.UnauthorizedAccessException: Access to the path '<PATH><u>\AppData\Roaming\renode\cache_lock' is denied.
```

但同一目录用 Python 能删能建，`icacls` 显示当前用户有完全控制权 (F)、无 Deny 规则。于是误判为"权限问题"，开始 chmod、重建目录、预设锁文件，全部无效，浪费大量时间。

## Root Cause

**误诊层**：看到 Access denied 就去查权限。实际 ACL 是好的，所以查不出东西，越查越迷惑。

**真实层**：这是沙箱对进程的**能力限制**，不是文件系统权限。判别方法是做对照实验——把操作按粒度拆开，看哪一步开始被拒：

```
mach create "x"                    -> 成功    （沙箱允许创建进程内对象）
+ LoadPlatformDescription <cpu>    -> 被拒    （沙箱不允许挂 CPU 外设）
```

**为什么环境变量那条路走不通**：.NET 的 `SpecialFolder.ApplicationData` 走 Win32 Known Folder API（SHGetKnownFolderPath），不读 `APPDATA` 环境变量。所以重定向 `APPDATA` 对这类程序完全无效——试之前不可能知道，试一次就能确认：若换了环境变量仍报原路径，就是这条路。

## Fix

判别步骤（按顺序做，每步都有结论，别跳）：

1. icacls 看 ACL：`icacls "<PATH><u>\AppData\Roaming\renode"`。若当前用户有 (F) 且无 (DENY)，权限不是原因，进第 2 步。
2. 用同语义的 Win32 调用复现：python -c 调 CreateFileW(path, GENERIC_RW, share=0, None, OPEN_ALWAYS, 0, None)。若返回有效句柄 → 文件系统允许它，进第 3 步。
3. 缩小到最小命令：只做 `mach create "x"; quit`（不加载 CPU）。若成功 → 说明沙箱允许创建对象、不允许挂 CPU，边界定位完成。这一条是本次最关键的对照实验。
4. 换目录/换环境变量再试一次就够：--config 指向别处 + 重定向 TEMP。若仍报同一个 %APPDATA% 路径 → 说明程序读的是 Win32 Known Folder，不是环境变量，别再试环境变量。
5. 判定为沙箱拦截后立刻停止旁路尝试，改做两件事：(a) 代码里如实返回 not_ready 并附被拒的完整错误行；(b) 生成可在宿主外执行的脚本（如 run.cmd），并在脚本里预建程序只会写不会建的目录。

反面清单（我这次全试过、全无效，别再花时间）：--config 换位、重定向 APPDATA/TEMP、cmd 包装、Windows 计划任务、预建目录、预建非空锁文件、chmod。

## Verification

判别流程可复现：
1. `icacls <dir>` 显示当前用户 (F)、无 (DENY) → 权限不是原因。
2. Python 调 `CreateFileW(path, GENERIC_RW, share=0, None, OPEN_ALWAYS, 0, None)` 返回有效句柄 → 文件系统允许独占打开。
3. 最小命令对照：只 `mach create "x"; quit` 返回 "System bus created" 并正常退出；加 `LoadPlatformDescription @platforms/cpus/stm32f103.repl` 后同一命令报 UnauthorizedAccessException。两步结果不同即证明是功能级拦截。
4. 判定后在代码中返回 status=not_ready 且 detail 含被拒路径与错误行；产物脚本在宿主外执行成功。
