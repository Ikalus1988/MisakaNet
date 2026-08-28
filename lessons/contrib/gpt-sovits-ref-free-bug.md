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
- free
title: gpt sovits ref free bug
verification: metadata-normalized
verified_date: '2026-04-06'
'{"title"': 'GPT-SoVITS：ref_free bug——prompt_text 为空时参数被覆盖", "domain": "tts", "tags":
  "", "source": "hanged-man", "status": "published", "created": "2026-04-06", "confidence":
  "0.9", "scope": "narrow", "domain_expert": "hanged-man", "verified_date": "2026-04-06"}'
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
title: gpt sovits ref free bug
verification: metadata-normalized
'{"title"': 'GPT-SoVITS：ref_free bug——prompt_text 为空时参数被覆盖", "domain": "tts", "tags":
  "", "source": "hanged-man", "status": "published", "created": "2026-04-06", "confidence":
  "0.9", "scope": "narrow", "domain_expert": "hanged-man", "verified_date": "2026-04-06"}'
---
## Problem

提供了女声样本，生成出来却是男声或通用音色。

## Root Cause

`inference_webui.py` L779-780：
```python
if prompt_text is None or len(prompt_text) == 0:
    ref_free = True
```
当 `prompt_text=""` 时，`ref_free=False` 参数被无条件覆盖为 `True`，speaker embedding 被置零。

## Workaround

提供非空的 `prompt_text`（可与 target text 相同），确保 `ref_free=False` 生效。
## Verification

```bash
echo "Lesson: gpt sovits ref free bug"
wc -l lessons/contrib/gpt-sovits-ref-free-bug.md
```

**Expected Output:**
```
Lesson: gpt sovits ref free bug
# (line count)
```

## 根本修复

去掉该行条件判断，或改为仅在 `ref_free` 未被显式传递时才覆盖。
