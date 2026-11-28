---
title: "Windows 上 Git Bash 与原生 Python 混用时：Bash 重定向写到 `<PATH> 成功，紧接着 Windows Pyth"
domain: "windows"
tags:
  - "ls"
  - "windows"
  - "git"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5918"
summary_plain: "Windows 上 Git Bash 与原生 Python 混用时：Bash 重定向写到 `<PATH> 成功，紧接着 Windows Python（同机同用户）`open('<PATH>')` 报…"
trigger: "git bash /tmp FileNotFoundError Windows python path mismatch temp directory msys"
verify: "复现：Git Bash `echo hi > <PATH> 后 Windows Python `open('<PATH>')` 必报 FileNotFoundError，而 `open(os.environ['TEMP']+'<PATH>')` 能读到；统一用 %TEMP% 路径后两边互通。 file written to /tmp by Git Bash is invisible to…"
provenance:
  issue: "#5918"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 上 Git Bash 与原生 Python 混用时：Bash 重定向写到 `<PATH> 成功，紧接着 Windows Python（同机同用户）`open('<PATH>')` 报 `FileNotFoundError`——文件「明明刚写出来」却找不到；反向（Python 写 /tmp、Bash 读）同样踩空。同会话内反复交错两种 shell 时该坑高频复发，每次都要重新想一遍。

## Root Cause

Git Bash（MSYS2）的 `/tmp` 是**虚拟路径**，实际落盘在用户的 Temp 目录（如 `<PATH><u>/AppData/Local/Temp/`，随 MSYS2 配置而定）；而 Windows 原生 Python 不做 MSYS2 路径映射，把 `<PATH> 当成当前盘符根下的 `\tmp\xxx`。两边说的不是同一个目录——写者和读者各自都「成功」了，只是不在同一处。

## Fix

跨 shell 传递文件一律用**双方都能解析的路径**：
1. 首选：Windows 原生路径（如 `%TEMP%\\xxx.json` / `<PATH> 也能直接读写该路径；
2. 或 Bash 侧写完用 `cygpath -w <PATH> 换算成 Windows 路径传给 Python；
3. 或干脆管道传（`cmd | python -c "import sys; data=sys.stdin.read()"`），绕开文件路径；
4. 队列/日志类常驻文件放项目目录或数据目录，别放 /tmp。
排查判据：同一文件名在两个环境 `ls`<PATH>` 结果不一致 = 本坑，不是权限/编码问题。

## Verification

复现：Git Bash `echo hi > <PATH> 后 Windows Python `open('<PATH>')` 必报 FileNotFoundError，而 `open(os.environ['TEMP']+'<PATH>')` 能读到；统一用 %TEMP% 路径后两边互通。

file written to /tmp by Git Bash is invisible to Windows Python at the same path; both see it after switching to the %TEMP% path or cygpath -w
