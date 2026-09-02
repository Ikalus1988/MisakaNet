---
title: gpt sovits hubert 16khz
domain: contrib
tags:
- sovits
- hubert
- 16khz
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.9
domain_expert: hanged-man
verified_date: '2026-04-05'
scope: narrow
---

---
## Problem

HuBERT SSL 特征提取失败，音频克隆效果异常。

## 正确 API 流程

1. `cnhubert_mod = inf.cnhubert`（模块，非实例）
2. `hmodel = cnhubert_mod.get_model()` → 返回**单个** `CNHubert` 实例，不是元组
3. `librosa.load(wav, sr=16000)` → **必须是 16kHz**（不是 32kHz）
4. `feat = cnhubert_mod.get_content(hmodel, wav_tensor)` → 签名是 `(hmodel, wav_16k_tensor)`
## Verification

```bash
echo "Lesson: gpt sovits hubert 16khz"
wc -l lessons/contrib/gpt-sovits-hubert-16khz.md
```

**Expected Output:**
```
Lesson: gpt sovits hubert 16khz
# (line count)
```

## 常见错误

- `get_model()` 返回值解包为元组 → 实际是单个对象
- `get_content(data, sr)` → 实际签名是 `(hmodel, wav_16k_tensor)`
- 音频 32kHz → HuBERT 要求 16kHz