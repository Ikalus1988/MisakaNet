---
confidence: '0.9'
created: '2026-07-06'
domain: contrib
domain_expert: hanged-man
scope: narrow
source: hanged-man
status: published
tags:
- sovits
- hubert
- 16khz
title: gpt sovits hubert 16khz
verification: metadata-normalized
verified_date: '2026-04-05'
'{"title"': 'GPT-SoVITS：HuBERT 必须 16kHz 且 get_model() 返回单体", "domain": "tts", "tags":
  "", "source": "hanged-man", "status": "published", "created": "2026-04-05", "confidence":
  "0.9", "scope": "narrow", "domain_expert": "hanged-man", "verified_date": "2026-04-05"}'
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
title: gpt sovits hubert 16khz
verification: metadata-normalized
'{"title"': 'GPT-SoVITS：HuBERT 必须 16kHz 且 get_model() 返回单体", "domain": "tts", "tags":
  "", "source": "hanged-man", "status": "published", "created": "2026-04-05", "confidence":
  "0.9", "scope": "narrow", "domain_expert": "hanged-man", "verified_date": "2026-04-05"}'
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
