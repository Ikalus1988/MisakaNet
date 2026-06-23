---
{"title": "TTS 中文编码：PowerShell 传参必须用 .txt File中转", "domain": "tts", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-04-18", "confidence": "0.9", "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-04-18"}
---

## Problem

中文文本Via PowerShell 脚本内联传给 mmx CLI，TTS 返回空音频（"嗯嗯"声）。

## 根因

PowerShell 5.1 将 UTF-8 字节误读为 GBK/CP936，导致传给 API 的是乱码。

## Error做法

```ps1
node mmx.mjs speech synthesize --text "早安愚者" --voice Japanese_CalmLady --out "out.mp3"
```

## 正确做法

1. 文本写入独立 `.txt` File（write 工具保证 UTF-8）
2. ps1 用 `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)` 读取
3. 将 UTF-8 字符串传给 mmx CLI

## 验证

正确 UTF-8 bytes：`E6 97 A9 E5 AE 89` = "早安"；Error GBK 解读：`E5 8F 82 E5 90 88`
