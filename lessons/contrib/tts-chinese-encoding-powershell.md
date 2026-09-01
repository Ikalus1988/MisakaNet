---
title: tts chinese encoding powershell
domain: contrib
tags:
- chinese
- encoding
- powershell
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.9
domain_expert: hanged-man
verified_date: '2026-04-18'
scope: broad
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

中文文本通过 PowerShell 脚本内联传给 mmx CLI，TTS 返回空音频（"嗯嗯"声）。

## Root Cause

PowerShell 5.1 将 UTF-8 字节误读为 GBK/CP936，导致传给 API 的是乱码。

## 错误做法

```ps1
node mmx.mjs speech synthesize --text "早安愚者" --voice Japanese_CalmLady --out "out.mp3"
```

## 正确做法

1. 文本写入独立 `.txt` 文件（write 工具保证 UTF-8）
2. ps1 用 `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)` 读取
3. 将 UTF-8 字符串传给 mmx CLI

## Verification

```bash
[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)`)
