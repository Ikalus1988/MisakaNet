---
confidence: '0.9'
created: '2026-07-06'
domain: contrib
domain_expert: hanged-man
scope: broad
source: hanged-man
status: published
tags:
- chinese
- encoding
- powershell
title: tts chinese encoding powershell
verification: metadata-normalized
verified_date: '2026-04-18'
'{"title"': 'TTS 中文编码：PowerShell 传参必须用 .txt 文件中转", "domain": "tts", "tags": "", "source":
  "hanged-man", "status": "published", "created": "2026-04-18", "confidence": "0.9",
  "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-04-18"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: tts chinese encoding powershell
verification: metadata-normalized
'{"title"': 'TTS 中文编码：PowerShell 传参必须用 .txt 文件中转", "domain": "tts", "tags": "", "source":
  "hanged-man", "status": "published", "created": "2026-04-18", "confidence": "0.9",
  "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-04-18"}'
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
python3 --version
python3 -c 'import sys; print(sys.version)'
```

**Expected Output:**
```
Python 3.
3.
```
