---
title: "UTF-8 编码的 .bat 含中文时，cmd 逐行解码错位、吞掉下一行行首字符"
domain: "devops"
tags:
  - "batch"
  - "cmd"
  - "encoding"
  - "utf-8"
  - "chinese"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4446"
summary_plain: "双击桌面快捷方式启动的 .bat 脚本完全不执行，黑窗口一闪而过。脚本里有 netstat 端口检测、if 分支、start 调起浏览器、前台跑服务等逻辑。"
trigger: "UTF-8 编码的 .bat 含中文时，cmd 逐行解码错位、吞掉下一行行首字符. 双击桌面快捷方式启动的 .bat 脚本完全不执行，黑窗口一闪而过。脚本里有 netstat 端口检测、if 分支、start 调起浏览器、前台跑服务等逻辑。"
verify: "1. 诊断：#cmd /c \"xxx.bat > out.txt 2>&1\"# 后读 out.txt，不应出现 'xxx is not recognized' 的缺字错误 2. 功能验证：双击后目标服务端口进入 LISTENING 状态，且能通过 HTTP 探活 3. 回归：文件里 grep 一遍，确认 bat 部分没有非 ASCII 字符"
provenance:
  issue: "#4446"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

双击桌面快捷方式启动的 .bat 脚本完全不执行，黑窗口一闪而过。脚本里有 netstat 端口检测、if 分支、start 调起浏览器、前台跑服务等逻辑。

把 bat 输出重定向抓下来才看到真相（cmd /c "xxx.bat > out.txt 2>&1"）：

'port_check.txt" 2>&1' is not recognized as an internal or external command
'tart' is not recognized ...
'cho' is not recognized ...
'xit' is not recognized ...

命令名全部丢了第一个字母：start 变 tart、echo 变 cho、exit 变 xit。整个脚本从第一处中文之后全面崩坏。

排除了两个错误猜测：
1. 以为是管道符 | 在批处理里的特殊含义（改成文件重定向后仍然失败）
2. 以为是 UTF-8 BOM（检查字节前三位是 40 65 63 68 6F 20，即 "@echo "，无 BOM）

## Root Cause

bat 文件是 UTF-8 编码且包含中文注释和 echo 文本。

cmd.exe 读取批处理文件时按当前代码页（中文 Windows 默认 936 / GBK）逐行解码。UTF-8 的一个中文字符是三字节序列，GBK 按双字节解，字节边界就错位了——解码器把下一行开头的 ASCII 字符当成上一个字符的延续而吞掉。

现象就是：每行第一个字母消失，命令名被破坏，cmd 报"不是内部或外部命令"。

关键点：这个错误只在"文件含非 ASCII 字符"时出现，纯 ASCII 的 bat 在任何代码页下都正常。

## Fix

按可靠性从高到低：

1. 最稳（推荐）：.bat 内容保持纯 ASCII，界面提示用英文；需要中文提示或复杂逻辑时，把那段逻辑拆到外部 .ps1，由 bat 用 start "" powershell -File "xxx.ps1" 调用。ps1 对 UTF-8 宽容得多。

2. 次选：用 GBK / ANSI（代码页 936）保存 bat 文件。PowerShell 里可以：
   [System.IO.File]::WriteAllText(, , [System.Text.Encoding]::GetEncoding(936))
   注意：机器代码页不是 936 的环境会反过来出问题。

3. 不要指望 chcp 65001 兜底。chcp 写在脚本第 2 行，但 cmd 读取文件的解码发生在执行之前/逐行进行，chcp 无法修复已经错位的中文行。

## Verification

1. 诊断：#cmd /c "xxx.bat > out.txt 2>&1"# 后读 out.txt，不应出现 'xxx is not recognized' 的缺字错误
2. 功能验证：双击后目标服务端口进入 LISTENING 状态，且能通过 HTTP 探活
3. 回归：文件里 grep 一遍，确认 bat 部分没有非 ASCII 字符
