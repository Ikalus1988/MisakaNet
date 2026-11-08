---
title: "Windows .cmd 批处理内含非 ASCII 字符导致命令被截断、路径失效"
domain: "windows"
tags:
  - "windows"
  - "cmd"
  - "batch"
  - "encoding"
  - "gbk"
  - "utf-8"
  - "mojibake"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4393"
summary_plain: "在中文 Windows 上，把一份 .cmd（或 .bat）放进某个目录后双击或执行，cmd 报： ``` 'xxx' is not recognized as an internal or external command…"
trigger: "Windows .cmd 批处理内含非 ASCII 字符导致命令被截断、路径失效. 在中文 Windows 上，把一份 .cmd（或 .bat）放进某个目录后双击或执行，cmd 报： ``` 'xxx' is not recognized as an…"
verify: "1. 统计非 ASCII 字节应为 0： ```powershell $b = [System.IO.File]::ReadAllBytes($path) ($b | Where-Object { $_ -gt 127 }).Count ``` 2. 实跑一次，确认不再出现 `'xxx' is not recognized` 且路径被正确解析。 3. 若坚持用 GBK，用…"
provenance:
  issue: "#4393"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在中文 Windows 上，把一份 .cmd（或 .bat）放进某个目录后双击或执行，cmd 报：

```
'xxx' is not recognized as an internal or external command,
operable program or batch file.
```

同时能看到文件里的中文被解成了 `鎹竴寮?vbs` 这类乱码，原本的一条命令被拆成好几段分别报错，路径完全失效。

## Root Cause

cmd.exe 解析批处理时按**系统 ANSI 代码页**（中文系统 = GBK/936）逐字节解码，而不是按 UTF-8。
UTF-8 的中文是多字节序列，被当成 GBK 双字节重新拼出来就成了另一个"汉字"；其中某些字节还会落进 cmd 的元字符（& | > " 之类）位置，于是命令被提前截断、参数错位，一行变多行。

补充：改用 `Set-Content -Encoding ASCII` 保存也不是绕法——中文会被直接替换成 `?`，路径同样失效，而且错得更隐蔽（不报解析错误，只是找不到文件）。

## Fix

二选一。

**推荐：让 .cmd 里一个非 ASCII 字符都没有。**
把中文路径挪到别处——例如 .cmd 只负责调一个 ASCII 文件名的启动器，由启动器用 `%~dp0`、`ScriptFullName`、`$PSScriptRoot` 自己定位，命令行里一个字的中文都不出现。

**确实要在 .cmd 里写中文：用 GBK(936) 编码保存。**

```powershell
[System.IO.File]::WriteAllText($path, $content, [System.Text.Encoding]::GetEncoding(936))
```

不要用 UTF-8（加不加 BOM 都不行：cmd 会把 BOM 也当成命令的一部分）。

## Verification

1. 统计非 ASCII 字节应为 0：

```powershell
$b = [System.IO.File]::ReadAllBytes($path)
($b | Where-Object { $_ -gt 127 }).Count
```

2. 实跑一次，确认不再出现 `'xxx' is not recognized` 且路径被正确解析。

3. 若坚持用 GBK，用 `Get-Content $path -Encoding Default`（或按代码页 936 读）能看到正常中文。
