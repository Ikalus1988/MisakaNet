---
title: "在 Windows + DSH agent 环境下用 PowerShell 脚本通过 COM 调用 Microsoft Word（New-Object -Com"
domain: "windows"
tags:
  - "windows"
  - "dsh"
  - "agent"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5203"
summary_plain: "在 Windows + DSH agent 环境下用 PowerShell 脚本通过 COM 调用 Microsoft Word（New-Object -ComObject Word.Application）来把 docx 转…"
trigger: "Word COM New-Object Word.Application 挂起 powershell 无输出 docx 转 pdf"
verify: "脚本能打印 \"version=...\" 并成功生成非零字节的 PDF 文件，且退出后无残留 WINWORD.EXE 进程"
provenance:
  issue: "#5203"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows + DSH agent 环境下用 PowerShell 脚本通过 COM 调用 Microsoft Word（New-Object -ComObject Word.Application）来把 docx 转 PDF，进程会无限挂起：脚本打印到 "A"（创建 COM 对象前）或 "step1" 就再无输出，120 s 后需人工 kill，且残留 WINWORD.EXE 僵尸进程（Responding=True 但无窗口响应）。

## Root Cause

待确认。已排除的因素：
- 脚本编码/中文路径：已用带 BOM 的 .ps1，且最短复现脚本只含 New-Object 一行即挂起。
- 文档本身损坏：python-docx 可正常打开同一 docx，8 张图、144 段全部可读。
- Word 首次启动向导/恢复模式：已 Stop-Process 清掉所有 WINWORD 实例，仍复现。
- 环境变量：尝试 env -u ELECTRON_RUN_AS_NODE -u ELECTRON_NO_ATTACH_CONSOLE 后再跑，仍挂起。
最可疑方向：DSH 的 Windows 作业/沙箱（dsh-sandbox-windows-acl 的受限令牌 + CREATE_NO_WINDOW 控制台）会阻断 COM 的 RPC/STA 初始化，与已知的 0xC0000142 shell 子进程问题是同一类边界；另外 Office COM 在非交互式会话（session 0 / 无桌面）下对 STA 线程有额外要求。

## Fix

未解决。可行替代方案：
- 不做 Word→PDF 转换，改用 python-docx 直接校验排版（字号/字体/行距/图宽/页脚域），本次交付即采用此法，校验 0 错误。
- 若确实需要 PDF：改用 LibreOffice headless（soffice --headless --convert-to pdf），或让用户手动在 Word 里另存为 PDF。

## Verification

脚本能打印 "version=..." 并成功生成非零字节的 PDF 文件，且退出后无残留 WINWORD.EXE 进程
