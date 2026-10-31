---
title: "PowerShell Start-Process -ArgumentList splits a path at its spaces, silently"
domain: "windows"
tags:
  - "powershell"
  - "start-process"
  - "argument-quoting"
  - "silent-failure"
  - "chrome"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "PowerShell 的 Start-Process 不会给含空格的参数自动加引号，路径被截成两段，进程照常启动但目录没建。"
trigger: "Start-Process -ArgumentList path with space split into two tokens"
verify: "Test-Path $UserDataDir 返回 True，且 Win32_Process 里该进程的 CommandLine 含完整未截断的目录路径"
source: "intake-2562"
provenance:
  issue: "#2562"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# PowerShell Start-Process -ArgumentList splits a path at its spaces, silently

## Problem

PowerShell 的 `Start-Process -ArgumentList` **不会**给含空格的数组元素自动加引号。传
`--user-data-dir="C:\Users\<user>\..."`（路径里带空格）时，参数在空格处被拆成两个 token，目标程序
只拿到前半截。

Reporter's error line:

```
process starts normally, exit code 0, but the expected profile/config directory is never created
```

失败是静默的：**进程正常启动、不报任何错，但指定目录压根没被创建**。排查成本远高于崩溃——没有
非零退出码、没有异常、没有日志，唯一线索是"应该存在的东西不存在"。

## Root Cause

`-ArgumentList` 接受的是一组已经"成型"的参数；PowerShell 把它们拼成命令行时不会为其中的空格
添加引号。含空格的元素在拼接后变成两个独立的命令行 token，被目标程序按两个参数解析：

```
--user-data-dir=C:\Users\<user>     ← token 1，路径在此截断
...                                 ← token 2，路径的剩余部分成为下一个参数
```

目标程序通常不会因为一个无法解析的 `--user-data-dir` 而拒绝启动：它拿到的目录不存在或不可用，
就退回默认配置目录继续跑。于是"启动成功"和"目录没建"同时为真。

报料者的排查顺序也说明了这个失败为什么贵：先怀疑端口占用，再怀疑权限，再怀疑参数顺序，逐个
排除后才定位到空格截断。以上三项都是"进程不工作"的常见原因，而这里进程恰恰是工作的。

## Solution

二选一。

**(A) 手工加引号**，让含空格的路径作为一个 token 传过去：

```powershell
Start-Process $chrome -ArgumentList "--user-data-dir=`"$UserDataDir`""
```

反引号 `` ` `` 是 PowerShell 的转义符，用来在这里产出内层的双引号。

**(B) 直接不用带空格的路径**，例如：

```powershell
$UserDataDir = 'C:\Users\<user>\chrome-cdp-profile'
```

附带一个坑：`$args` 是 PowerShell 的**自动变量**，不要拿它当参数数组名，用 `$progArgs` 之类的名字。

## Verification

`Test-Path $UserDataDir` 必须为 `True`。

或者检查完整命令行，确认路径没有被截断：

```powershell
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
  Where-Object { $_.CommandLine -like '*chrome-cdp-profile*' }
```

The reporter's stated criteria, verbatim:

```
Test-Path $UserDataDir 必须为 True；或 Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*chrome-cdp-profile*' } 检查完整命令行
```

只看 `Start-Process` 是否抛错、或看进程是否出现，都**不能**作为通过判据——这两种情况在失败时
同样成立。

## Notes

- 报料者未给出 Chrome 的具体路径、`$UserDataDir` 的原始取值和完整脚本——需复现确认。本课的路径已
  把用户名脱敏为 `<user>`。
- 同样的截断会发生在任何由 PowerShell 拼命令行的地方；`-ArgumentList @('--x','--y')` 数组形式
  并不会自动补引号，这是本课的关键点。
- 与"进程启动成功即视为成功"的一类判据同源：判据要观察副作用（目录是否存在），而不是观察调用
  有没有报错。
