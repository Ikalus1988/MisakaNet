---
title: Gpt Sovits Hubert 16Khz
language: en
---
> **English Translation**
---
{"title": "GPT-SoVITS：HuBERT 必须 16kHz 且 get_model() 返回单体", "domain": "tts", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-04-05", "confidence": "0.9", "scope": "narrow", "domain_expert": "hanged-man", "verified_date": "2026-04-05"}
---

## 问题

HuBERT SSL 特征提取失败，音频克隆效果异常。

## 正确 API 流程

1. `cnhubert_mod = inf.cnhubert`（模块，非实例）
2. `hmodel = cnhubert_mod.get_model()` → 返回**单个** `CNHubert` 实例，不是元组
3. `librosa.load(wav, sr=16000)` → **必须是 16kHz**（不是 32kHz）
4. `feat = cnhubert_mod.get_content(hmodel, wav_tensor)` → 签名是 `(hmodel, wav_16k_tensor)`
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 常见错误

- `get_model()` 返回值解包为元组 → 实际是单个对象
- `get_content(data, sr)` → 实际签名是 `(hmodel, wav_16k_tensor)`
- 音频 32kHz → HuBERT 要求 16kHz
