---
title: "症状 在 PowerShell 里用 `& $yt-dlp \"bilisearch5:关键词\" --print \"%(title)s\"` 抓搜索结果，标题里的中"
domain: "windows"
tags:
  - "node"
  - "curl.exe"
  - "powershell"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4899"
summary_plain: "在 PowerShell 里用 `& $yt-dlp \"bilisearch5:关键词\" --print \"%(title)s\"` 抓搜索结果，标题里的中文全部变成 `��`（U+FFFD 替换字符），UP 主名字同样是乱码。"
trigger: "症状 在 PowerShell 里用 `& $yt-dlp \"bilisearch5:关键词\" --print \"%(title)s\"` 抓搜索结果，标题里的中. 在 PowerShell 里用 `& $yt-dlp \"bilisearch5:关键词\" --print \"%(title)s\"`…"
verify: "改之前： ``` UP: �ʼǱ�ά���� 标题: ��տ֮· EP807 ... ``` 改之后： ``` UP: 笔记本维修厮 UP: 元新電腦 UP: 精湛電腦 标题: 組裝電腦維修紀錄：電腦一直在重開機，沒辦法開機 這個零件千萬不能省 ``` **顺带一个同源问题**：`Invoke-WebRequest` 在 PowerShell 里拿 npm registry 的 JSON…"
provenance:
  issue: "#4899"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 PowerShell 里用 `& $yt-dlp "bilisearch5:关键词" --print "%(title)s"` 抓搜索结果，标题里的中文全部变成 `��`（U+FFFD 替换字符），UP 主名字同样是乱码。

环境：Windows 11 + PowerShell 7 + yt-dlp 2026.10.26（PyInstaller 打包的 `.exe`）。

## Root Cause

**Windows 版 yt-dlp 是 PyInstaller 打包的 exe，它的 stdout 默认按系统 ANSI 代码页（CP936 / GBK）输出，不是 UTF-8。** PowerShell 按 UTF-8 去读，每个 GBK 双字节序列都成了非法 UTF-8，全部变成 U+FFFD。

和常见的「UTF-8 被当 GBK 读」是反方向的：这一次是**对方按 GBK 写，你按 UTF-8 读**。

判别口诀：

| 现象 | 谁的问题 |
|---|---|
| 出现 `��`（U+FFFD 替换字符） | 对方 GBK，你按 UTF-8 读 |
| 出现 `锟斤拷` | UTF-8 字节被当 GBK 读了两遍 |

## Fix

**两件事一起做：**

**1. 让 Python 侧输出 UTF-8**

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
```

PyInstaller 打包的 exe 也认这两个环境变量，因为它们由 CPython 运行时读取。

**2. 读回来的时候如果还是见到连续 U+FFFD，退回 GBK 再解一次**

```powershell
$raw = & $yt-dlp @args 2>&1
if ($raw -match '\uFFFD\uFFFD') {
    # 兜底：按 GBK 重新解释
    $enc = [System.Text.Encoding]::GetEncoding(936)
    $raw = $enc.GetString($enc.GetBytes($raw))
}
```

## Verification

改之前：

```
UP: �ʼǱ�ά����
标题: ��տ֮· EP807 ...
```

改之后：

```
UP: 笔记本维修厮
UP: 元新電腦
UP: 精湛電腦
标题: 組裝電腦維修紀錄：電腦一直在重開機，沒辦法開機  這個零件千萬不能省
```

**顺带一个同源问题**：`Invoke-WebRequest` 在 PowerShell 里拿 npm registry 的 JSON 也会失败（`$o.'dist-tags'.latest` 取不到），换成 `node fetch` 或 `curl.exe` 就正常。同样是 PowerShell 的 HTTP 客户端对编码和 UA 的处理和裸 HTTP 不一致。
