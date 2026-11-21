---
title: "中文 Windows 环境 Python 脚本用 subprocess.run(..., capture_output=True, text=True) 捕获子"
domain: "windows"
tags:
  - "python-gbk-encoding-error"
  - "windows"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5445"
summary_plain: "中文 Windows 环境 Python 脚本用 subprocess.run(..., capture_output=True, text=True) 捕获子进程输出时，子进程输出含非 GBK 字节（如 UTF-8 中文）→…"
trigger: "subprocess.run text=True UnicodeDecodeError gbk codec can't decode _readerthread 空 stdout 假阴性 false negative"
verify: "中文 Windows 上 subprocess.run(text=True) 捕获输出含 UTF-8 中文的子进程：修复前 stdout 为空 + 线程 traceback；修复后 stdout 完整含子进程全部输出。 **Matched lesson (not helpful):** `python-gbk-encoding-error`"
provenance:
  issue: "#5445"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

中文 Windows 环境 Python 脚本用 subprocess.run(..., capture_output=True, text=True) 捕获子进程输出时，子进程输出含非 GBK 字节（如 UTF-8 中文）→ _readerthread 线程抛 UnicodeDecodeError: 'gbk' codec can't decode byte，但异常不传播给 communicate()，run() 正常返回空 stdout。外层脚本拿空输出做关键字判定（如 'RELAUNCH-OK' in stdout），得出与子进程真实状态完全脱钩的假阴性结论（子进程其实跑完了且报告了成功）。

## Root Cause

subprocess text=True 未指定 encoding 时按 locale 编码（中文 Windows = GBK/cp936）解码子进程字节流；子进程输出 UTF-8 时解码必崩。_readerthread 的异常只在线程里打印 traceback，communicate 照常返回（stdout=''),run() 不抛错——错误被静默吞掉，上层看到的是"干净的空输出"。

## Fix

subprocess.run(..., encoding='utf-8', errors='replace')：显式编码 + replace 兜底永不解码崩。关键判定不要单靠 stdout 关键字，配退出码/外部状态（如文件 mtime）双判据。同类场景（Popen.communicate、check_output）同理。

## Verification

中文 Windows 上 subprocess.run(text=True) 捕获输出含 UTF-8 中文的子进程：修复前 stdout 为空 + 线程 traceback；修复后 stdout 完整含子进程全部输出。

**Matched lesson (not helpful):** `python-gbk-encoding-error`
