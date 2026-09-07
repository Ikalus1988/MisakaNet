---
title: gpt sovits ref free bug
domain: contrib
tags:
- sovits
- free
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.9
domain_expert: hanged-man
verified_date: '2026-04-06'
scope: narrow
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

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